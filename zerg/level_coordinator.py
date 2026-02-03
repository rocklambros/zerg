"""Level coordination for ZERG orchestrator.

Handles level START, COMPLETE, and MERGE workflows extracted from the
Orchestrator class.
"""

from __future__ import annotations

import concurrent.futures
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from zerg.assign import WorkerAssignment
from zerg.config import QualityGate, ZergConfig
from zerg.constants import (
    LevelMergeStatus,
    LogEvent,
    PluginHookEvent,
    TaskStatus,
)
from zerg.gates import GateRunner
from zerg.levels import LevelController
from zerg.log_writer import StructuredLogWriter
from zerg.logging import get_logger
from zerg.merge import MergeCoordinator, MergeFlowResult
from zerg.metrics import MetricsCollector
from zerg.parser import TaskParser
from zerg.plugins import LifecycleEvent, PluginRegistry
from zerg.state import StateManager
from zerg.task_sync import TaskSyncBridge, load_design_manifest
from zerg.types import GateRunResult, WorkerState

if TYPE_CHECKING:
    from zerg.backpressure import BackpressureController

logger = get_logger("level_coordinator")


class LevelCoordinator:
    """Coordinate level lifecycle: start, complete, and merge workflows.

    This class manages the level-related orchestration logic, including
    starting levels, handling level completion with merge protocol,
    rebasing workers, and pausing for intervention.
    """

    def __init__(
        self,
        feature: str,
        config: ZergConfig,
        state: StateManager,
        levels: LevelController,
        parser: TaskParser,
        merger: MergeCoordinator,
        task_sync: TaskSyncBridge,
        plugin_registry: PluginRegistry,
        workers: dict[int, WorkerState],
        on_level_complete_callbacks: list[Callable[[int], None]],
        assigner: WorkerAssignment | None = None,
        structured_writer: StructuredLogWriter | None = None,
        backpressure: BackpressureController | None = None,
    ) -> None:
        """Initialize level coordinator.

        Args:
            feature: Feature name being executed
            config: ZERG configuration
            state: State manager instance
            levels: Level controller instance
            parser: Task parser instance
            merger: Merge coordinator instance
            task_sync: Task sync bridge instance
            plugin_registry: Plugin registry instance
            workers: Workers dict (passed by reference from Orchestrator)
            on_level_complete_callbacks: Callbacks list (passed by reference)
            assigner: Optional worker assignment instance
            structured_writer: Optional structured log writer
            backpressure: Optional backpressure controller for level failure management
        """
        self.feature = feature
        self.config = config
        self.state = state
        self.levels = levels
        self.parser = parser
        self.merger = merger
        self.task_sync = task_sync
        self._plugin_registry = plugin_registry
        self._workers = workers
        self._on_level_complete = on_level_complete_callbacks
        self.assigner = assigner
        self._structured_writer = structured_writer
        self._backpressure = backpressure
        self._paused = False

    @property
    def paused(self) -> bool:
        """Whether execution is paused."""
        return self._paused

    @paused.setter
    def paused(self, value: bool) -> None:
        """Set paused state."""
        self._paused = value

    def start_level(self, level: int) -> None:
        """Start a level.

        Args:
            level: Level number to start
        """
        logger.info(f"Starting level {level}")

        task_ids = self.levels.start_level(level)

        # Register level with backpressure controller
        if self._backpressure is not None:
            self._backpressure.register_level(level, len(task_ids))

        self.state.set_current_level(level)
        self.state.set_level_status(level, "running")
        self.state.append_event("level_started", {"level": level, "tasks": len(task_ids)})

        if self._structured_writer:
            self._structured_writer.emit(
                "info",
                f"Level {level} started with {len(task_ids)} tasks",
                event=LogEvent.LEVEL_STARTED,
                data={"level": level, "tasks": len(task_ids)},
            )

        # Emit plugin lifecycle event for level started
        try:
            self._plugin_registry.emit_event(
                LifecycleEvent(
                    event_type=PluginHookEvent.LEVEL_COMPLETE.value,  # Reused for level start
                    data={"level": level, "tasks": len(task_ids)},
                )
            )
        except Exception as e:
            logger.warning(f"Failed to emit LEVEL_COMPLETE event: {e}")

        # Create Claude Tasks for this level
        level_tasks = cast(
            list[dict[str, Any]],
            [t for tid in task_ids for t in [self.parser.get_task(tid)] if t is not None],
        )
        if level_tasks:
            self.task_sync.create_level_tasks(level, level_tasks)
            logger.info(f"Created {len(level_tasks)} Claude Tasks for level {level}")

        # Log design manifest status (informational only)
        spec_dir = Path(".gsd/specs") / self.feature
        manifest_tasks = load_design_manifest(spec_dir)
        if manifest_tasks is not None:
            logger.info("Design manifest found with %d tasks", len(manifest_tasks))
        else:
            logger.info("No design manifest found for feature %s", self.feature)

        # Assign tasks to workers
        for task_id in task_ids:
            if self.assigner:
                worker_id = self.assigner.get_task_worker(task_id)
                if worker_id is not None:
                    self.state.set_task_status(task_id, TaskStatus.PENDING, worker_id=worker_id)

    def handle_level_complete(self, level: int) -> bool:
        """Handle level completion.

        Args:
            level: Completed level

        Returns:
            True if merge succeeded and we can advance
        """
        logger.info(f"Level {level} complete")

        # Update merge status to indicate we're starting merge
        self.state.set_level_merge_status(level, LevelMergeStatus.MERGING)

        # Execute merge protocol with timeout and retry (BF-007)
        merge_timeout = getattr(self.config, "merge_timeout_seconds", 600)  # 10 min default
        max_retries = getattr(self.config, "merge_max_retries", 3)

        merge_result = None
        for attempt in range(max_retries):
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.merge_level, level)
                try:
                    merge_result = future.result(timeout=merge_timeout)
                    if merge_result.success:
                        break
                except concurrent.futures.TimeoutError:
                    merge_result = MergeFlowResult(
                        success=False,
                        level=level,
                        source_branches=[],
                        target_branch="main",
                        error="Merge timed out",
                    )
                    logger.warning(f"Merge timed out for level {level} (attempt {attempt + 1})")

            if not merge_result.success and attempt < max_retries - 1:
                backoff = 2**attempt * 10  # 10s, 20s, 40s
                logger.warning(
                    f"Merge attempt {attempt + 1} failed for level {level}, "
                    f"retrying in {backoff}s: {merge_result.error}"
                )
                self.state.append_event(
                    "merge_retry",
                    {
                        "level": level,
                        "attempt": attempt + 1,
                        "backoff_seconds": backoff,
                        "error": merge_result.error,
                    },
                )
                time.sleep(backoff)

        if merge_result and merge_result.success:
            # Record success in backpressure controller
            if self._backpressure is not None:
                self._backpressure.record_success(level)

            self.state.set_level_status(level, "complete", merge_commit=merge_result.merge_commit)
            self.state.set_level_merge_status(level, LevelMergeStatus.COMPLETE)
            self.state.append_event(
                "level_complete",
                {
                    "level": level,
                    "merge_commit": merge_result.merge_commit,
                },
            )

            if self._structured_writer:
                self._structured_writer.emit(
                    "info",
                    f"Level {level} merge complete",
                    event=LogEvent.MERGE_COMPLETE,
                    data={"level": level, "merge_commit": merge_result.merge_commit},
                )
                self._structured_writer.emit(
                    "info",
                    f"Level {level} complete",
                    event=LogEvent.LEVEL_COMPLETE,
                    data={"level": level},
                )

            # Compute and store metrics
            try:
                collector = MetricsCollector(self.state)
                metrics = collector.compute_feature_metrics()
                self.state.store_metrics(metrics)
                logger.info(
                    f"Level {level} metrics: "
                    f"{metrics.tasks_completed}/{metrics.tasks_total} tasks, "
                    f"{metrics.total_duration_ms}ms total"
                )
            except Exception as e:
                logger.warning(f"Failed to compute metrics: {e}")

            # Emit plugin lifecycle events
            try:
                self._plugin_registry.emit_event(
                    LifecycleEvent(
                        event_type=PluginHookEvent.LEVEL_COMPLETE.value,
                        data={"level": level, "merge_commit": merge_result.merge_commit},
                    )
                )
                self._plugin_registry.emit_event(
                    LifecycleEvent(
                        event_type=PluginHookEvent.MERGE_COMPLETE.value,
                        data={"level": level, "merge_commit": merge_result.merge_commit},
                    )
                )
            except Exception as e:
                logger.debug(f"Status update failed: {e}")

            # Rebase worker branches onto merged base
            self.rebase_all_workers(level)

            # Generate STATE.md after level completion
            try:
                self.state.generate_state_md()
            except Exception as e:
                logger.warning(f"Failed to generate STATE.md: {e}")

            # Notify callbacks
            for callback in self._on_level_complete:
                callback(level)

            return True
        else:
            error_msg = merge_result.error if merge_result else "Unknown merge error"
            logger.error(f"Level {level} merge failed after {max_retries} attempts: {error_msg}")

            # Record failure in backpressure controller and check for pause
            if self._backpressure is not None:
                self._backpressure.record_failure(level)
                if self._backpressure.should_pause(level):
                    self._backpressure.pause_level(level)
                    logger.warning(
                        f"Level {level} paused by backpressure controller "
                        f"(failure rate: {self._backpressure.get_failure_rate(level):.0%})"
                    )

            if "conflict" in str(error_msg).lower():
                self.state.set_level_merge_status(
                    level,
                    LevelMergeStatus.CONFLICT,
                    details={"error": error_msg},
                )
                self.pause_for_intervention(f"Merge conflict in level {level}")
            else:
                # BF-007: Set recoverable error state (pause) instead of stop
                self.state.set_level_merge_status(level, LevelMergeStatus.FAILED)
                self.set_recoverable_error(f"Level {level} merge failed after {max_retries} attempts: {error_msg}")

            return False

    def merge_level(self, level: int) -> MergeFlowResult:
        """Execute merge protocol for a level.

        Args:
            level: Level to merge

        Returns:
            MergeFlowResult with outcome
        """
        logger.info(f"Starting merge for level {level}")
        if self._structured_writer:
            self._structured_writer.emit(
                "info",
                f"Merge started for level {level}",
                event=LogEvent.MERGE_STARTED,
                data={"level": level},
            )

        # Collect worker branches
        worker_branches = []
        for _worker_id, worker in self._workers.items():
            if worker.branch:
                worker_branches.append(worker.branch)

        if not worker_branches:
            logger.warning("No worker branches to merge")
            return MergeFlowResult(
                success=True,
                level=level,
                source_branches=[],
                target_branch="main",
            )

        # Execute full merge flow
        return self.merger.full_merge_flow(
            level=level,
            worker_branches=worker_branches,
            target_branch="main",
        )

    def rebase_all_workers(self, level: int) -> None:
        """Rebase all worker branches onto merged base.

        Args:
            level: Level that was just merged
        """
        logger.info(f"Rebasing worker branches after level {level} merge")

        self.state.set_level_merge_status(level, LevelMergeStatus.REBASING)

        for worker_id, worker in self._workers.items():
            if not worker.branch:
                continue

            try:
                # Workers will need to pull the merged changes
                # This is handled when they start their next task
                logger.debug(f"Worker {worker_id} branch {worker.branch} marked for rebase")
            except Exception as e:
                logger.warning(f"Failed to track rebase for worker {worker_id}: {e}")

    def pause_for_intervention(self, reason: str) -> None:
        """Pause execution for manual intervention.

        Args:
            reason: Why we're pausing
        """
        logger.warning(f"Pausing for intervention: {reason}")

        self._paused = True
        self.state.set_paused(True)
        self.state.append_event("paused_for_intervention", {"reason": reason})

        # Log helpful info
        logger.info("Intervention required. Options:")
        logger.info("  1. Resolve conflicts and run /zerg:merge")
        logger.info("  2. Use /zerg:retry to re-run failed tasks")
        logger.info("  3. Use /zerg:rush --resume to continue")

    def set_recoverable_error(self, error: str) -> None:
        """Set recoverable error state (pause instead of stop).

        Args:
            error: Error message
        """
        logger.warning(f"Setting recoverable error state: {error}")
        self.state.set_error(error)
        self._paused = True
        self.state.set_paused(True)
        self.state.append_event("recoverable_error", {"error": error})


class GatePipeline:
    """Wraps GateRunner with artifact storage and staleness checking.

    Delegates gate execution to GateRunner, but adds:
    - Artifact storage: gate results saved to .zerg/artifacts/{level}/
    - Staleness check: skip re-running gates if results are fresh and code unchanged
    """

    def __init__(
        self,
        gate_runner: GateRunner,
        artifacts_dir: Path | None = None,
        staleness_threshold_seconds: int = 300,
    ) -> None:
        """Initialize GatePipeline.

        Args:
            gate_runner: Underlying GateRunner to delegate execution to
            artifacts_dir: Directory for storing gate artifacts
            staleness_threshold_seconds: Seconds before a cached result is
                considered stale (default 300, configurable via
                verification.staleness_threshold_seconds)
        """
        self._runner = gate_runner
        self._artifacts_dir = artifacts_dir or Path(".zerg/artifacts")
        self._staleness_threshold = staleness_threshold_seconds

    def run_gates_for_level(
        self,
        level: int,
        gates: list[QualityGate],
        cwd: str | Path | None = None,
    ) -> list[GateRunResult]:
        """Run gates for a level with artifact storage and staleness check.

        For each gate, checks whether a cached result exists and is still
        fresh (younger than staleness_threshold_seconds). If so, the cached
        result is returned without re-executing. Otherwise, the gate is
        delegated to the underlying GateRunner, and the result is persisted
        as a JSON artifact under .zerg/artifacts/{level}/.

        Args:
            level: Level number
            gates: List of QualityGate configs to run
            cwd: Working directory for gate execution

        Returns:
            List of GateRunResult (one per gate, in order)
        """
        level_dir = self._artifacts_dir / str(level)
        level_dir.mkdir(parents=True, exist_ok=True)

        results: list[GateRunResult] = []
        for gate in gates:
            cached = self._load_cached_result(level_dir, gate.name)
            if cached is not None and not self._is_stale(cached):
                logger.info("Gate '%s' result still fresh, skipping", gate.name)
                restored = self._restore_result(cached, gate)
                results.append(restored)
                continue

            result = self._runner.run_gate(gate, cwd=cwd)
            results.append(result)
            self._store_result(level_dir, gate.name, result)

        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_cached_result(self, level_dir: Path, gate_name: str) -> dict[str, Any] | None:
        """Load cached gate result if it exists.

        Args:
            level_dir: Artifact directory for the level
            gate_name: Name of the gate

        Returns:
            Parsed JSON dict or None if not found / unreadable
        """
        import json

        artifact_path = level_dir / f"{gate_name}.json"
        if not artifact_path.exists():
            return None
        try:
            with open(artifact_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load cached artifact for '%s': %s", gate_name, exc)
            return None

    def _is_stale(self, cached: dict[str, Any]) -> bool:
        """Check if a cached result is stale (older than threshold).

        Args:
            cached: Cached artifact dict (must contain 'timestamp')

        Returns:
            True if the result is stale and should be re-run
        """
        import time as _time

        timestamp = cached.get("timestamp", 0)
        age = _time.time() - timestamp
        return age > self._staleness_threshold

    def _restore_result(self, cached: dict[str, Any], gate: QualityGate) -> GateRunResult:
        """Reconstruct a GateRunResult from a cached artifact.

        Args:
            cached: Cached artifact dict with a 'result' sub-dict
            gate: The QualityGate config (used as fallback for fields)

        Returns:
            Reconstituted GateRunResult
        """
        from zerg.constants import GateResult

        r = cached.get("result", {})
        gate_result_str = r.get("result", "unknown")
        try:
            gate_result = GateResult(gate_result_str)
        except ValueError:
            gate_result = GateResult.ERROR

        return GateRunResult(
            gate_name=r.get("name", gate.name),
            result=gate_result,
            command=r.get("command", gate.command),
            exit_code=r.get("exit_code", 0),
            stdout=r.get("stdout", ""),
            stderr=r.get("stderr", ""),
            duration_ms=r.get("duration_ms", 0),
        )

    def _store_result(self, level_dir: Path, gate_name: str, result: GateRunResult) -> None:
        """Store gate result as a JSON artifact.

        Args:
            level_dir: Artifact directory for the level
            gate_name: Name of the gate
            result: GateRunResult to persist
        """
        import json
        import time as _time

        artifact_path = level_dir / f"{gate_name}.json"
        try:
            data = {
                "gate_name": gate_name,
                "timestamp": _time.time(),
                "result": {
                    "name": result.gate_name,
                    "result": result.result.value,
                    "command": result.command,
                    "exit_code": result.exit_code,
                    "duration_ms": result.duration_ms,
                    "stdout": result.stdout[:500],
                    "stderr": result.stderr[:500],
                },
            }
            with open(artifact_path, "w") as f:
                json.dump(data, f, indent=2)
        except OSError as exc:
            logger.warning("Failed to store gate artifact for '%s': %s", gate_name, exc)
