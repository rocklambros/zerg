"""Level coordination for ZERG orchestrator.

Handles level START, COMPLETE, and MERGE workflows extracted from the
Orchestrator class.
"""

import concurrent.futures
import time
from collections.abc import Callable
from typing import Any, cast

from zerg.assign import WorkerAssignment
from zerg.config import ZergConfig
from zerg.constants import (
    LevelMergeStatus,
    LogEvent,
    PluginHookEvent,
    TaskStatus,
)
from zerg.levels import LevelController
from zerg.log_writer import StructuredLogWriter
from zerg.logging import get_logger
from zerg.merge import MergeCoordinator, MergeFlowResult
from zerg.metrics import MetricsCollector
from zerg.parser import TaskParser
from zerg.plugins import LifecycleEvent, PluginRegistry
from zerg.state import StateManager
from zerg.task_sync import TaskSyncBridge
from zerg.types import WorkerState

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
        self.state.set_current_level(level)
        self.state.set_level_status(level, "running")
        self.state.append_event("level_started", {"level": level, "tasks": len(task_ids)})

        if self._structured_writer:
            self._structured_writer.emit(
                "info", f"Level {level} started with {len(task_ids)} tasks",
                event=LogEvent.LEVEL_STARTED, data={"level": level, "tasks": len(task_ids)},
            )

        # Emit plugin lifecycle event for level started
        try:
            self._plugin_registry.emit_event(LifecycleEvent(
                event_type=PluginHookEvent.LEVEL_COMPLETE.value,  # Reused for level start
                data={"level": level, "tasks": len(task_ids)},
            ))
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
        merge_timeout = getattr(self.config, 'merge_timeout_seconds', 600)  # 10 min default
        max_retries = getattr(self.config, 'merge_max_retries', 3)

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
                backoff = 2 ** attempt * 10  # 10s, 20s, 40s
                logger.warning(
                    f"Merge attempt {attempt + 1} failed for level {level}, "
                    f"retrying in {backoff}s: {merge_result.error}"
                )
                self.state.append_event("merge_retry", {
                    "level": level,
                    "attempt": attempt + 1,
                    "backoff_seconds": backoff,
                    "error": merge_result.error,
                })
                time.sleep(backoff)

        if merge_result and merge_result.success:
            self.state.set_level_status(level, "complete", merge_commit=merge_result.merge_commit)
            self.state.set_level_merge_status(level, LevelMergeStatus.COMPLETE)
            self.state.append_event("level_complete", {
                "level": level,
                "merge_commit": merge_result.merge_commit,
            })

            if self._structured_writer:
                self._structured_writer.emit(
                    "info", f"Level {level} merge complete",
                    event=LogEvent.MERGE_COMPLETE,
                    data={"level": level, "merge_commit": merge_result.merge_commit},
                )
                self._structured_writer.emit(
                    "info", f"Level {level} complete",
                    event=LogEvent.LEVEL_COMPLETE, data={"level": level},
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
                self._plugin_registry.emit_event(LifecycleEvent(
                    event_type=PluginHookEvent.LEVEL_COMPLETE.value,
                    data={"level": level, "merge_commit": merge_result.merge_commit},
                ))
                self._plugin_registry.emit_event(LifecycleEvent(
                    event_type=PluginHookEvent.MERGE_COMPLETE.value,
                    data={"level": level, "merge_commit": merge_result.merge_commit},
                ))
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
                self.set_recoverable_error(
                    f"Level {level} merge failed after {max_retries} attempts: {error_msg}"
                )

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
                "info", f"Merge started for level {level}",
                event=LogEvent.MERGE_STARTED, data={"level": level},
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
