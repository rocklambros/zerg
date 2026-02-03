"""ZERG orchestrator - thin coordination engine.

Delegates to extracted components:
- LauncherConfigurator: launcher creation and container lifecycle
- TaskRetryManager: retry logic, backoff, verification retries
- StateSyncService: disk-to-memory state synchronization
- WorkerManager: worker spawning, initialization, termination
- LevelCoordinator: level start, complete, merge workflows
- Resilience: spawn_with_retry, check_stale_tasks, auto_respawn, crash recovery
"""

import asyncio
import contextlib
import os
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from zerg.assign import WorkerAssignment
from zerg.backpressure import BackpressureController
from zerg.capability_resolver import ResolvedCapabilities
from zerg.circuit_breaker import CircuitBreaker
from zerg.config import ZergConfig
from zerg.constants import (
    LOGS_TASKS_DIR,
    LOGS_WORKERS_DIR,
    GateResult,
    PluginHookEvent,
    TaskStatus,
    WorkerStatus,
)
from zerg.containers import ContainerManager
from zerg.context_plugin import ContextEngineeringPlugin
from zerg.gates import GateRunner
from zerg.launcher import (
    ContainerLauncher,
    LauncherConfig,
    LauncherType,
    SubprocessLauncher,
    WorkerLauncher,
    get_plugin_launcher,
)
from zerg.launcher_configurator import LauncherConfigurator
from zerg.level_coordinator import GatePipeline, LevelCoordinator
from zerg.levels import LevelController
from zerg.log_writer import StructuredLogWriter
from zerg.logging import get_logger, setup_structured_logging
from zerg.loops import LoopController
from zerg.merge import MergeCoordinator, MergeFlowResult
from zerg.metrics import MetricsCollector
from zerg.modes import BehavioralMode, ModeContext, ModeDetector
from zerg.parser import TaskParser
from zerg.plugin_config import ContextEngineeringConfig
from zerg.plugins import LifecycleEvent, PluginRegistry
from zerg.ports import PortAllocator
from zerg.state import StateManager
from zerg.state_sync_service import StateSyncService
from zerg.task_retry_manager import TaskRetryManager
from zerg.task_sync import TaskSyncBridge
from zerg.types import WorkerState
from zerg.worker_manager import WorkerManager
from zerg.worktree import WorktreeManager

logger = get_logger("orchestrator")


def _now() -> datetime:
    """Return current datetime (extracted for testability)."""
    return datetime.now()


class Orchestrator:
    """Main ZERG orchestration engine.

    Thin coordinator that wires and delegates to extracted components:
    LauncherConfigurator, TaskRetryManager, StateSyncService,
    WorkerManager, and LevelCoordinator.
    """

    def __init__(
        self,
        feature: str,
        config: ZergConfig | None = None,
        repo_path: str | Path = ".",
        launcher_mode: str | None = None,
        capabilities: ResolvedCapabilities | None = None,
    ) -> None:
        """Initialize orchestrator.

        Args:
            feature: Feature name being executed
            config: ZERG configuration
            repo_path: Path to git repository
            launcher_mode: Launcher mode (subprocess, container, auto)
            capabilities: Resolved cross-cutting capabilities for worker env injection
        """
        self.feature = feature
        self.config = config or ZergConfig.load()
        self.repo_path = Path(repo_path).resolve()
        self._launcher_mode = launcher_mode
        self._capabilities = capabilities

        # Initialize plugin registry first (needed by other components)
        self._plugin_registry = PluginRegistry()
        if hasattr(self.config, "plugins") and self.config.plugins.enabled:
            try:
                self._plugin_registry.load_yaml_hooks([h.model_dump() for h in self.config.plugins.hooks])
                self._plugin_registry.load_entry_points()
            except Exception as e:
                logger.warning(f"Failed to load plugins: {e}")

        # Register context engineering plugin
        try:
            ctx_config = ContextEngineeringConfig()
            if hasattr(self.config, "plugins") and hasattr(self.config.plugins, "context_engineering"):
                ctx_config = self.config.plugins.context_engineering
            if ctx_config.enabled:
                ctx_plugin = ContextEngineeringPlugin(ctx_config)
                self._plugin_registry.register_context_plugin(ctx_plugin)
                logger.info("Registered context engineering plugin")
        except Exception:
            logger.warning("Failed to register context engineering plugin", exc_info=True)

        # Initialize core components
        self.state = StateManager(feature)
        self.levels = LevelController()
        self.parser = TaskParser()
        self.gates = GateRunner(self.config, plugin_registry=self._plugin_registry)
        self.worktrees = WorktreeManager(repo_path)
        self.containers = ContainerManager(self.config)
        self.ports = PortAllocator(
            range_start=self.config.ports.range_start,
            range_end=self.config.ports.range_end,
        )
        self.assigner: WorkerAssignment | None = None
        self.merger = MergeCoordinator(feature, self.config, repo_path)
        self.task_sync = TaskSyncBridge(
            feature,
            self.state,
            task_list_id=os.environ.get("CLAUDE_CODE_TASK_LIST_ID", feature),
        )

        # Create extracted components
        self._launcher_config = LauncherConfigurator(self.config, self.repo_path, self._plugin_registry)
        # Launcher creation stays inline so test patches on zerg.orchestrator work
        self.launcher: WorkerLauncher = self._create_launcher(mode=launcher_mode)

        # Clean up orphan containers from previous runs (container mode only)
        try:
            if isinstance(self.launcher, ContainerLauncher):
                self._launcher_config._cleanup_orphan_containers()
        except TypeError:
            pass  # Mocked launcher in tests

        # Set up structured logging for orchestrator
        self._structured_writer: StructuredLogWriter | None = None
        try:
            log_dir = Path(self.config.logging.directory)
            (self.repo_path / LOGS_WORKERS_DIR).mkdir(parents=True, exist_ok=True)
            (self.repo_path / LOGS_TASKS_DIR).mkdir(parents=True, exist_ok=True)
            self._structured_writer = setup_structured_logging(
                log_dir=self.repo_path / log_dir,
                worker_id="orchestrator",
                feature=feature,
                level=self.config.logging.level,
                max_size_mb=self.config.logging.max_log_size_mb,
            )
        except Exception as e:
            logger.warning(f"Failed to set up structured orchestrator logging: {e}")

        # Runtime state
        self._running = False
        self._paused = False
        self._workers: dict[int, WorkerState] = {}
        self._on_task_complete: list[Callable[[str], None]] = []
        self._on_level_complete: list[Callable[[int], None]] = []
        self._poll_interval = 5  # seconds
        self._max_retry_attempts = self.config.workers.retry_attempts
        self._restart_counts: dict[int, int] = {}  # worker_id -> restart count
        self._respawn_counts: dict[int, int] = {}  # worker_id -> respawn count for auto_respawn
        self._target_worker_count: int = 0  # Target worker count for auto-respawn

        # Wire extracted components
        self._retry_manager = TaskRetryManager(
            config=self.config,
            state=self.state,
            levels=self.levels,
            repo_path=self.repo_path,
            structured_writer=self._structured_writer,
        )
        self._state_sync = StateSyncService(state=self.state, levels=self.levels)

        # Error recovery components
        er_config = self.config.error_recovery
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=er_config.circuit_breaker.failure_threshold,
            cooldown_seconds=er_config.circuit_breaker.cooldown_seconds,
            enabled=er_config.circuit_breaker.enabled,
        )
        self._backpressure = BackpressureController(
            failure_rate_threshold=er_config.backpressure.failure_rate_threshold,
            window_size=er_config.backpressure.window_size,
            enabled=er_config.backpressure.enabled,
        )

        self._worker_manager = WorkerManager(
            feature=self.feature,
            config=self.config,
            state=self.state,
            levels=self.levels,
            parser=self.parser,
            launcher=self.launcher,
            worktrees=self.worktrees,
            ports=self.ports,
            assigner=self.assigner,
            plugin_registry=self._plugin_registry,
            workers=self._workers,
            on_task_complete=self._on_task_complete,
            on_task_failure=self._retry_manager.handle_task_failure,
            structured_writer=self._structured_writer,
            circuit_breaker=self._circuit_breaker,
            capabilities=self._capabilities,
        )
        self._level_coord = LevelCoordinator(
            feature=self.feature,
            config=self.config,
            state=self.state,
            levels=self.levels,
            parser=self.parser,
            merger=self.merger,
            task_sync=self.task_sync,
            plugin_registry=self._plugin_registry,
            workers=self._workers,
            on_level_complete_callbacks=self._on_level_complete,
            assigner=self.assigner,
            structured_writer=self._structured_writer,
            backpressure=self._backpressure,
        )

        # Create loop controller if capabilities enable it
        self._loop_controller: LoopController | None = None
        if self._capabilities and self._capabilities.loop_enabled:
            loop_config = self.config.improvement_loops
            self._loop_controller = LoopController(
                max_iterations=self._capabilities.loop_iterations,
                convergence_threshold=loop_config.convergence_threshold,
                plateau_threshold=loop_config.plateau_threshold,
            )
            logger.info(f"Loop controller enabled: max_iterations={self._capabilities.loop_iterations}")

        # Create gate pipeline if capabilities enable it
        self._gate_pipeline: GatePipeline | None = None
        if self._capabilities and self._capabilities.gates_enabled:
            artifacts_dir = Path(self.config.verification.artifact_dir)
            self._gate_pipeline = GatePipeline(
                gate_runner=self.gates,
                artifacts_dir=artifacts_dir,
                staleness_threshold_seconds=self._capabilities.staleness_threshold,
            )
            logger.info(f"Gate pipeline enabled: staleness_threshold={self._capabilities.staleness_threshold}s")

        # Create mode context from resolved capabilities
        self._mode_context: ModeContext | None = None
        if self._capabilities:
            try:
                mode_enum = BehavioralMode(self._capabilities.mode)
            except ValueError:
                mode_enum = BehavioralMode.PRECISION
            detector = ModeDetector(
                auto_detect=self.config.behavioral_modes.auto_detect,
                default_mode=mode_enum,
                log_transitions=self.config.behavioral_modes.log_transitions,
            )
            self._mode_context = detector.detect(
                explicit_mode=mode_enum,
                depth_tier=self._capabilities.depth_tier,
            )
            logger.info(
                f"Mode context: mode={self._mode_context.mode.value}, "
                f"verification_level={self._mode_context.mode.verification_level}"
            )

    # ------------------------------------------------------------------
    # Backward-compatible thin wrappers (delegate to components)
    # ------------------------------------------------------------------

    def _create_launcher(self, mode: str | None = None) -> WorkerLauncher:
        """Create worker launcher based on config and mode.

        Kept inline (not delegated) so test patches on zerg.orchestrator
        module-level ContainerLauncher/SubprocessLauncher work correctly.
        """
        if mode and mode not in ("subprocess", "container", "auto"):
            plugin_launcher = get_plugin_launcher(mode, self._plugin_registry)
            if plugin_launcher is not None:
                logger.info(f"Using plugin launcher: {mode}")
                return plugin_launcher

        if mode == "subprocess":
            launcher_type = LauncherType.SUBPROCESS
        elif mode == "container":
            launcher_type = LauncherType.CONTAINER
        elif mode == "auto" or mode is None:
            launcher_type = self._auto_detect_launcher_type()
        else:
            plugin_launcher = get_plugin_launcher(mode, self._plugin_registry)
            if plugin_launcher is not None:
                logger.info(f"Using plugin launcher: {mode}")
                return plugin_launcher
            raise ValueError(f"Unsupported launcher mode: '{mode}'. Valid modes: subprocess, container, auto")

        logger.info(f"Launcher mode resolved: {mode!r} → {launcher_type.value}")

        config = LauncherConfig(
            launcher_type=launcher_type,
            timeout_seconds=self.config.workers.timeout_minutes * 60,
            log_dir=Path(self.config.logging.directory),
        )

        if launcher_type == LauncherType.CONTAINER:
            launcher = ContainerLauncher(
                config=config,
                image_name=self._get_worker_image_name(),
                memory_limit=self.config.resources.container_memory_limit,
                cpu_limit=self.config.resources.container_cpu_limit,
            )
            network_ok = launcher.ensure_network()
            if not network_ok:
                if mode == "container":
                    raise RuntimeError(
                        "Container mode explicitly requested but Docker network "
                        "creation failed. Check that Docker is running and accessible."
                    )
                logger.warning("Docker network setup failed, falling back to subprocess")
                return SubprocessLauncher(config)
            logger.info("Using ContainerLauncher")
            return launcher
        else:
            logger.info("Using SubprocessLauncher")
            return SubprocessLauncher(config)

    def _cleanup_orphan_containers(self) -> None:
        self._launcher_config._cleanup_orphan_containers()

    def _check_container_health(self) -> None:
        # Snapshot statuses before health check to detect newly crashed workers
        pre_statuses = {wid: w.status for wid, w in self._workers.items()}
        self._launcher_config._check_container_health(self._workers, self.launcher)
        # Persist state for workers that were marked CRASHED by health check
        for wid, worker in self._workers.items():
            if worker.status == WorkerStatus.CRASHED and pre_statuses.get(wid) != WorkerStatus.CRASHED:
                self.state.set_worker_state(worker)

    def _auto_detect_launcher_type(self) -> LauncherType:
        return self._launcher_config._auto_detect_launcher_type()

    def _get_worker_image_name(self) -> str:
        return self._launcher_config._get_worker_image_name()

    def _handle_task_failure(self, task_id: str, worker_id: int, error: str) -> bool:
        return self._retry_manager.handle_task_failure(task_id, worker_id, error)

    def _check_retry_ready_tasks(self) -> None:
        self._retry_manager.check_retry_ready_tasks()

    def _check_stale_tasks(self) -> None:
        """Check for tasks stuck in in_progress beyond timeout (FR-2).

        Detects tasks that have been in_progress for longer than the configured
        stale timeout and marks them as failed, triggering retry logic.
        This is the task timeout watchdog integration.
        """
        # Use default timeout from config if available, otherwise use reasonable default
        timeout_seconds = getattr(self.config.workers, "task_stale_timeout_seconds", 600)
        try:
            # check_stale_tasks is added by RES-L2-002
            stale_tasks = self._retry_manager.check_stale_tasks(timeout_seconds)
            if stale_tasks:
                logger.warning(f"Detected {len(stale_tasks)} stale tasks: {stale_tasks}")
                self.state.append_event(
                    "stale_tasks_detected",
                    {
                        "task_ids": stale_tasks,
                        "timeout_seconds": timeout_seconds,
                    },
                )
        except AttributeError:
            # check_stale_tasks not yet implemented (dependency not merged)
            pass

    def _handle_worker_crash(self, task_id: str, worker_id: int) -> None:
        """Handle task reassignment after worker crash (FR-5).

        Unlike task failures, worker crashes do NOT increment the retry count.
        The task is marked failed with reason=worker_crash and reassigned.

        Args:
            task_id: ID of the task that was running when worker crashed
            worker_id: ID of the crashed worker
        """
        logger.warning(f"Worker {worker_id} crashed with task {task_id}, reassigning")

        # Mark task failed with crash reason (don't increment retry count)
        self.state.set_task_status(
            task_id,
            TaskStatus.FAILED,
            worker_id=worker_id,
            error="Worker crashed (infrastructure failure)",
        )

        # Record failure reason for analytics
        self.state.append_event(
            "task_crash_reassign",
            {
                "task_id": task_id,
                "worker_id": worker_id,
                "failure_reason": "worker_crash",
                "retry_count_incremented": False,
            },
        )

        # Reset task to pending for reassignment (no retry count change)
        self.levels.reset_task(task_id)
        self.state.set_task_status(task_id, TaskStatus.PENDING)

        logger.info(f"Task {task_id} reset to pending for reassignment after crash")

    def _auto_respawn_workers(self, level: int, remaining_task_count: int) -> None:
        """Auto-respawn workers with respawn count tracking (FR-6).

        Spawns replacement workers up to the configured limit, tracking respawn
        counts per worker slot to prevent infinite respawn loops.

        Args:
            level: Current level being processed
            remaining_task_count: Number of tasks still needing completion
        """
        # Get max respawn attempts from config (default 5 if not set)
        max_respawn = getattr(self.config.workers, "max_respawn_attempts", 5)
        auto_respawn_enabled = getattr(self.config.workers, "auto_respawn", True)

        if not auto_respawn_enabled:
            logger.warning(f"Auto-respawn disabled, {remaining_task_count} tasks remain at level {level}")
            return

        # Determine how many workers to spawn (min of remaining tasks and target count)
        workers_to_spawn = min(remaining_task_count, self._target_worker_count or 1)

        spawned = 0
        for worker_id in range(workers_to_spawn):
            respawn_count = self._respawn_counts.get(worker_id, 0)

            if respawn_count >= max_respawn:
                logger.warning(f"Worker {worker_id} exceeded max respawns ({max_respawn}), skipping")
                continue

            try:
                self._respawn_counts[worker_id] = respawn_count + 1
                logger.info(
                    f"Auto-respawning worker {worker_id} (respawn {respawn_count + 1}/{max_respawn}) for level {level}"
                )
                self._spawn_worker(worker_id)
                spawned += 1

                # Record respawn event
                self.state.append_event(
                    "worker_auto_respawn",
                    {
                        "worker_id": worker_id,
                        "level": level,
                        "respawn_count": respawn_count + 1,
                        "max_respawn": max_respawn,
                    },
                )
            except Exception as e:
                logger.error(f"Failed to auto-respawn worker {worker_id}: {e}")

        if spawned == 0 and remaining_task_count > 0:
            logger.error(
                f"Could not spawn any workers for {remaining_task_count} remaining tasks - "
                f"all workers have exceeded max respawn limit ({max_respawn})"
            )
            self.state.append_event(
                "auto_respawn_exhausted",
                {
                    "level": level,
                    "remaining_tasks": remaining_task_count,
                    "max_respawn": max_respawn,
                },
            )
        else:
            logger.info(f"Auto-respawned {spawned} workers for level {level}")

    def _sync_levels_from_state(self) -> None:
        self._state_sync.sync_from_disk()

    def _reassign_stranded_tasks(self) -> None:
        # Compute active worker IDs from both disk state and in-memory workers
        active_ids: set[int] = set()
        workers_state = self.state._state.get("workers", {})
        for wid_str, wdata in workers_state.items():
            if wdata.get("status") not in ("stopped", "crashed"):
                active_ids.add(int(wid_str))
        for wid, w in self._workers.items():
            if w.status not in (WorkerStatus.STOPPED, WorkerStatus.CRASHED):
                active_ids.add(wid)
        self._state_sync.reassign_stranded_tasks(active_ids)

    def _spawn_worker(self, worker_id: int) -> WorkerState:
        return self._worker_manager.spawn_worker(worker_id)

    def _spawn_workers(self, count: int) -> int:
        # Track target worker count for auto-respawn (FR-6)
        self._target_worker_count = count
        return self._worker_manager.spawn_workers(count)

    def _wait_for_initialization(self, timeout: int = 600) -> bool:
        return self._worker_manager.wait_for_initialization(timeout)

    def _terminate_worker(self, worker_id: int, force: bool = False) -> None:
        self._worker_manager.terminate_worker(worker_id, force=force)

    def _handle_worker_exit(self, worker_id: int) -> None:
        self._worker_manager.handle_worker_exit(worker_id)

    def _respawn_workers_for_level(self, level: int) -> int:
        return self._worker_manager.respawn_workers_for_level(level)

    def _start_level(self, level: int) -> None:
        self._level_coord.assigner = self.assigner
        self._level_coord.start_level(level)

    def _on_level_complete_handler(self, level: int) -> bool:
        result = self._level_coord.handle_level_complete(level)
        # Sync paused state back from LevelCoordinator
        if self._level_coord.paused:
            self._paused = True

        # Run improvement loop if enabled and level merge succeeded
        if result and self._loop_controller is not None:
            self._run_level_loop(level)

        return result

    def _run_level_loop(self, level: int) -> None:
        """Run improvement loop for a completed level.

        Scores the level by gate pass rate and re-runs if the loop
        controller determines improvement is still possible.

        When a GatePipeline is available, gates are run through the pipeline
        for artifact storage and staleness detection.  When a ModeContext is
        present, its verification_level controls which gates are executed:
        - "none": skip all gates (score = 1.0)
        - "minimal": run only required gates
        - "full" / "verbose" (or any other value): run all gates

        Args:
            level: Level that just completed.
        """
        # Determine gate filtering from mode context
        verification_level = "full"
        if self._mode_context:
            verification_level = self._mode_context.mode.verification_level

        if verification_level == "none":
            logger.info(f"Skipping gates for level {level} (verification_level=none)")
            return

        required_only = verification_level == "minimal"

        def score_level(iteration: int) -> float:
            """Score current level by running quality gates."""
            try:
                if self._gate_pipeline:
                    # Use pipeline for artifact storage and staleness
                    gates_to_run = list(self.config.quality_gates)
                    if required_only:
                        gates_to_run = [g for g in gates_to_run if g.required]
                    gate_results = self._gate_pipeline.run_gates_for_level(
                        level=level,
                        gates=gates_to_run,
                    )
                    if not gate_results:
                        return 1.0
                    passed = sum(1 for r in gate_results if r.result == GateResult.PASS)
                    return passed / len(gate_results)
                else:
                    # Fallback to direct GateRunner
                    all_passed, gate_results = self.gates.run_all_gates(
                        feature=self.feature,
                        level=level,
                        required_only=required_only,
                    )
                    if not gate_results:
                        return 1.0
                    passed = sum(1 for r in gate_results if r.result == GateResult.PASS)
                    return passed / len(gate_results)
            except Exception as e:
                logger.warning(f"Gate scoring failed in loop iteration {iteration}: {e}")
                return 0.0

        # Get initial score
        initial_score = score_level(0)
        if initial_score >= 1.0:
            logger.info(f"Level {level} already at perfect score, skipping loop")
            return

        logger.info(f"Running improvement loop for level {level} (initial score: {initial_score:.2f})")
        summary = self._loop_controller.run(score_level, initial_score=initial_score)
        logger.info(
            f"Loop completed: status={summary.status.value}, "
            f"best_score={summary.best_score:.2f}, "
            f"iterations={len(summary.iterations)}"
        )
        self.state.append_event(
            "loop_completed",
            {
                "level": level,
                "status": summary.status.value,
                "best_score": summary.best_score,
                "iterations": len(summary.iterations),
                "improvement": summary.improvement,
            },
        )

    def _merge_level(self, level: int) -> MergeFlowResult:
        return self._level_coord.merge_level(level)

    def _rebase_all_workers(self, level: int) -> None:
        self._level_coord.rebase_all_workers(level)

    def _pause_for_intervention(self, reason: str) -> None:
        self._level_coord.pause_for_intervention(reason)
        self._paused = True

    def _set_recoverable_error(self, error: str) -> None:
        self._level_coord.set_recoverable_error(error)
        self._paused = True

    # ------------------------------------------------------------------
    # Lifecycle methods (retained directly)
    # ------------------------------------------------------------------

    def start(
        self,
        task_graph_path: str | Path,
        worker_count: int = 5,
        start_level: int | None = None,
        dry_run: bool = False,
    ) -> None:
        """Start orchestration.

        Args:
            task_graph_path: Path to task-graph.json
            worker_count: Number of workers to spawn
            start_level: Starting level (default: 1)
            dry_run: If True, don't actually spawn workers
        """
        logger.info(f"Starting orchestration for {self.feature}")

        # Load and parse task graph
        self.parser.parse(task_graph_path)
        tasks = self.parser.get_all_tasks()

        # Initialize level controller
        self.levels.initialize(tasks)

        # Create assignments
        self.assigner = WorkerAssignment(worker_count)
        assignments = self.assigner.assign(tasks, self.feature)

        # Save assignments
        assignments_path = Path(f".gsd/specs/{self.feature}/worker-assignments.json")
        self.assigner.save_to_file(str(assignments_path), self.feature)

        # Update components that depend on assigner
        self._worker_manager.assigner = self.assigner
        self._level_coord.assigner = self.assigner

        # Initialize state
        self.state.load()
        self.state.save()  # Persist initial state to disk immediately
        self.state.append_event(
            "rush_started",
            {
                "workers": worker_count,
                "total_tasks": len(tasks),
            },
        )

        if dry_run:
            logger.info("Dry run - not spawning workers")
            self._print_plan(assignments)
            return

        # Start execution
        self._running = True
        self._worker_manager.running = True
        spawned = self._spawn_workers(worker_count)
        if spawned == 0:
            self.state.append_event(
                "rush_failed",
                {
                    "reason": "No workers spawned",
                    "requested": worker_count,
                    "mode": self._launcher_mode,
                },
            )
            self.state.save()
            raise RuntimeError(
                f"All {worker_count} workers failed to spawn (mode={self._launcher_mode}). Cannot proceed."
            )
        if spawned < worker_count:
            logger.warning(f"Only {spawned}/{worker_count} workers spawned. Continuing with reduced capacity.")

        # Wait for workers to initialize before starting level
        self._wait_for_initialization(timeout=600)

        effective_start = start_level or 1
        # When resuming from a later level, mark all prior levels as complete
        if effective_start > 1:
            for prev in range(1, effective_start):
                if prev in self.levels._levels:
                    lvl = self.levels._levels[prev]
                    lvl.completed_tasks = lvl.total_tasks
                    lvl.failed_tasks = 0
                    lvl.status = "complete"
                    for _tid, task in self.levels._tasks.items():
                        if task.get("level") == prev:
                            task["status"] = TaskStatus.COMPLETE.value
                    logger.info(f"Pre-marked level {prev} as complete (resuming from {effective_start})")

        self._start_level(effective_start)
        self._main_loop()

    def stop(self, force: bool = False) -> None:
        """Stop orchestration.

        Args:
            force: Force stop without graceful shutdown
        """
        logger.info(f"Stopping orchestration (force={force})")
        self._running = False
        self._worker_manager.running = False

        # Stop all workers
        for worker_id in list(self._workers.keys()):
            self._terminate_worker(worker_id, force=force)

        # Release ports
        self.ports.release_all()

        # Save final state
        self.state.append_event("rush_stopped", {"force": force})
        self.state.save()

        # Generate STATE.md for human-readable status
        try:
            self.state.generate_state_md()
        except Exception as e:
            logger.warning(f"Failed to generate STATE.md: {e}")

        logger.info("Orchestration stopped")

    def status(self) -> dict[str, Any]:
        """Get current orchestration status.

        Returns:
            Status dictionary with metrics
        """
        level_status = self.levels.get_status()

        # Compute fresh metrics
        try:
            collector = MetricsCollector(self.state)
            metrics = collector.compute_feature_metrics()
            metrics_dict = metrics.to_dict()
        except Exception as e:
            logger.warning(f"Failed to compute metrics for status: {e}")
            metrics_dict = None

        return {
            "feature": self.feature,
            "running": self._running,
            "current_level": level_status["current_level"],
            "progress": {
                "total": level_status["total_tasks"],
                "completed": level_status["completed_tasks"],
                "failed": level_status["failed_tasks"],
                "in_progress": level_status["in_progress_tasks"],
                "percent": level_status["progress_percent"],
            },
            "workers": {
                wid: {
                    "status": w.status.value,
                    "current_task": w.current_task,
                    "tasks_completed": w.tasks_completed,
                }
                for wid, w in self._workers.items()
            },
            "levels": level_status["levels"],
            "is_complete": level_status["is_complete"],
            "metrics": metrics_dict,
            "circuit_breaker": self._circuit_breaker.get_status(),
            "backpressure": self._backpressure.get_status(),
        }

    def _main_loop(self) -> None:
        """Main orchestration loop."""
        logger.info("Starting main loop")
        _handled_levels: set[int] = set()

        while self._running:
            try:
                self._poll_workers()
                self._check_retry_ready_tasks()

                # Check level completion (guard: only handle each level once)
                current = self.levels.current_level
                if current > 0 and current not in _handled_levels and self.levels.is_level_resolved(current):
                    _handled_levels.add(current)
                    merge_ok = self._on_level_complete_handler(current)

                    if not merge_ok:
                        logger.warning(f"Level {current} merge failed, pausing execution")
                        continue

                    if self.levels.can_advance():
                        next_level = self.levels.advance_level()
                        if next_level:
                            self._start_level(next_level)
                            self._respawn_workers_for_level(next_level)
                    else:
                        status = self.levels.get_status()
                        if status["is_complete"]:
                            logger.info("All tasks complete!")
                            self._running = False
                            break

                # Check if all workers are gone but tasks remain (FR-6: Auto-respawn)
                active_workers = [
                    w for w in self._workers.values() if w.status not in (WorkerStatus.STOPPED, WorkerStatus.CRASHED)
                ]
                if not active_workers and self._running:
                    remaining = self._get_remaining_tasks_for_level(current)
                    if remaining:
                        # FR-6: Auto-spawn replacement workers with respawn cap
                        self._auto_respawn_workers(current, len(remaining))

                time.sleep(self._poll_interval)

            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                self.stop()
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                self.state.set_error(str(e))
                self.stop(force=True)
                raise

        # Emit rush finished event
        with contextlib.suppress(Exception):
            self._plugin_registry.emit_event(
                LifecycleEvent(
                    event_type=PluginHookEvent.RUSH_FINISHED.value,
                    data={"feature": self.feature},
                )
            )

        logger.info("Main loop ended")

    def _poll_workers(self) -> None:
        """Poll worker status and handle completions."""
        self.state.load()
        self._sync_levels_from_state()
        self._reassign_stranded_tasks()
        self._check_container_health()
        self.task_sync.sync_state()
        self.launcher.sync_state()

        # Check escalations (auto-interrupt)
        self._check_escalations()
        # Aggregate progress for status
        self._aggregate_progress()

        # Check for stale tasks (FR-2: Task timeout watchdog)
        # This detects tasks stuck in in_progress beyond the configured timeout
        self._check_stale_tasks()

        for worker_id, worker in list(self._workers.items()):
            if worker.status in (WorkerStatus.STOPPED, WorkerStatus.CRASHED):
                continue
            status = self.launcher.monitor(worker_id)
            if status == WorkerStatus.STALLED:
                logger.warning(f"Worker {worker_id} stalled (heartbeat timeout)")
                worker.status = WorkerStatus.STALLED
                self.state.set_worker_state(worker)
                restart_count = self._restart_counts.get(worker_id, 0)
                if restart_count < self.config.heartbeat.max_restarts:
                    self._restart_counts[worker_id] = restart_count + 1
                    logger.info(f"Auto-restarting stalled worker {worker_id} (attempt {restart_count + 1})")
                    self._handle_worker_exit(worker_id)
                else:
                    logger.warning(f"Worker {worker_id} exceeded max restarts, reassigning tasks")
                    if worker.current_task:
                        self._handle_task_failure(worker.current_task, worker_id, "Worker stalled repeatedly")
                    self._handle_worker_exit(worker_id)
            elif status == WorkerStatus.CRASHED:
                logger.error(f"Worker {worker_id} crashed")
                worker.status = WorkerStatus.CRASHED
                self.state.set_worker_state(worker)
                if worker.current_task:
                    # FR-5: Worker crash → mark task failed with reason=worker_crash
                    # This does NOT increment retry count (crash != task failure)
                    self._handle_worker_crash(worker.current_task, worker_id)
                self._handle_worker_exit(worker_id)
            elif status == WorkerStatus.CHECKPOINTING:
                logger.info(f"Worker {worker_id} checkpointing")
                worker.status = WorkerStatus.CHECKPOINTING
                self.state.set_worker_state(worker)
                self._handle_worker_exit(worker_id)
            elif status == WorkerStatus.STOPPED:
                worker.status = WorkerStatus.STOPPED
                self.state.set_worker_state(worker)
                self._handle_worker_exit(worker_id)
            worker.health_check_at = _now()

    def _check_escalations(self) -> None:
        """Check for unresolved worker escalations and alert if configured."""
        if not self.config.escalation.auto_interrupt:
            return
        try:
            from zerg.escalation import EscalationMonitor

            monitor = EscalationMonitor()
            unresolved = monitor.get_unresolved()
            for esc in unresolved:
                monitor.alert_terminal(esc)
        except Exception:
            logger.debug("Escalation check failed", exc_info=True)

    def _aggregate_progress(self) -> None:
        """Read worker progress files for status aggregation."""
        try:
            from zerg.progress_reporter import ProgressReporter

            all_progress = ProgressReporter.read_all()
            # Store on state for status command consumption
            progress_summary = {}
            for wid, wp in all_progress.items():
                progress_summary[str(wid)] = {
                    "tasks_completed": wp.tasks_completed,
                    "tasks_total": wp.tasks_total,
                    "current_task": wp.current_task,
                    "current_step": wp.current_step,
                }
            # Update state with progress data
            self.state._state.setdefault("worker_progress", {}).update(progress_summary)
        except Exception:
            logger.debug("Progress aggregation failed", exc_info=True)

    # ------------------------------------------------------------------
    # Async lifecycle methods
    # ------------------------------------------------------------------

    async def start_async(
        self,
        task_graph_path: str | Path,
        worker_count: int = 5,
        start_level: int | None = None,
        dry_run: bool = False,
    ) -> None:
        """Async entry point for orchestration.

        Same behavior as start() but uses asyncio.sleep in the main loop
        and async state loading in poll_workers.

        Args:
            task_graph_path: Path to task-graph.json
            worker_count: Number of workers to spawn
            start_level: Starting level (default: 1)
            dry_run: If True, don't actually spawn workers
        """
        logger.info(f"Starting async orchestration for {self.feature}")

        # Load and parse task graph
        self.parser.parse(task_graph_path)
        tasks = self.parser.get_all_tasks()

        # Initialize level controller
        self.levels.initialize(tasks)

        # Create assignments
        self.assigner = WorkerAssignment(worker_count)
        assignments = self.assigner.assign(tasks, self.feature)

        # Save assignments
        assignments_path = Path(f".gsd/specs/{self.feature}/worker-assignments.json")
        self.assigner.save_to_file(str(assignments_path), self.feature)

        # Update components that depend on assigner
        self._worker_manager.assigner = self.assigner
        self._level_coord.assigner = self.assigner

        # Initialize state (async)
        await self.state.load_async()
        self.state.append_event(
            "rush_started",
            {
                "workers": worker_count,
                "total_tasks": len(tasks),
            },
        )

        if dry_run:
            logger.info("Dry run - not spawning workers")
            self._print_plan(assignments)
            return

        # Start execution
        self._running = True
        self._worker_manager.running = True
        spawned = self._spawn_workers(worker_count)
        if spawned == 0:
            self.state.append_event(
                "rush_failed",
                {
                    "reason": "No workers spawned",
                    "requested": worker_count,
                    "mode": self._launcher_mode,
                },
            )
            await self.state.save_async()
            raise RuntimeError(
                f"All {worker_count} workers failed to spawn (mode={self._launcher_mode}). Cannot proceed."
            )
        if spawned < worker_count:
            logger.warning(f"Only {spawned}/{worker_count} workers spawned. Continuing with reduced capacity.")

        # Wait for workers to initialize before starting level
        self._wait_for_initialization(timeout=600)

        effective_start = start_level or 1
        # When resuming from a later level, mark all prior levels as complete
        if effective_start > 1:
            for prev in range(1, effective_start):
                if prev in self.levels._levels:
                    lvl = self.levels._levels[prev]
                    lvl.completed_tasks = lvl.total_tasks
                    lvl.failed_tasks = 0
                    lvl.status = "complete"
                    for _tid, task in self.levels._tasks.items():
                        if task.get("level") == prev:
                            task["status"] = TaskStatus.COMPLETE.value
                    logger.info(f"Pre-marked level {prev} as complete (resuming from {effective_start})")

        self._start_level(effective_start)
        await self._main_loop_async()

    def start_sync(
        self,
        task_graph_path: str | Path,
        worker_count: int = 5,
        start_level: int | None = None,
        dry_run: bool = False,
    ) -> None:
        """Synchronous entry point - wraps async start_async() in asyncio.run().

        Args:
            task_graph_path: Path to task-graph.json
            worker_count: Number of workers to spawn
            start_level: Starting level (default: 1)
            dry_run: If True, don't actually spawn workers
        """
        asyncio.run(
            self.start_async(
                task_graph_path,
                worker_count=worker_count,
                start_level=start_level,
                dry_run=dry_run,
            )
        )

    async def stop_async(self, force: bool = False) -> None:
        """Async stop orchestration.

        Args:
            force: Force stop without graceful shutdown
        """
        logger.info(f"Stopping orchestration async (force={force})")
        self._running = False
        self._worker_manager.running = False

        # Stop all workers
        for worker_id in list(self._workers.keys()):
            self._terminate_worker(worker_id, force=force)

        # Release ports
        self.ports.release_all()

        # Save final state (async)
        self.state.append_event("rush_stopped", {"force": force})
        await self.state.save_async()

        # Generate STATE.md for human-readable status
        try:
            self.state.generate_state_md()
        except Exception as e:
            logger.warning(f"Failed to generate STATE.md: {e}")

        logger.info("Orchestration stopped (async)")

    async def _main_loop_async(self) -> None:
        """Async main orchestration loop.

        Uses asyncio.sleep() instead of time.sleep() for non-blocking waits.
        """
        logger.info("Starting async main loop")
        _handled_levels: set[int] = set()

        while self._running:
            try:
                await self._poll_workers_async()
                self._check_retry_ready_tasks()

                # Check level completion (guard: only handle each level once)
                current = self.levels.current_level
                if current > 0 and current not in _handled_levels and self.levels.is_level_resolved(current):
                    _handled_levels.add(current)
                    merge_ok = self._on_level_complete_handler(current)

                    if not merge_ok:
                        logger.warning(f"Level {current} merge failed, pausing execution")
                        continue

                    if self.levels.can_advance():
                        next_level = self.levels.advance_level()
                        if next_level:
                            self._start_level(next_level)
                            self._respawn_workers_for_level(next_level)
                    else:
                        status = self.levels.get_status()
                        if status["is_complete"]:
                            logger.info("All tasks complete!")
                            self._running = False
                            break

                # Check if all workers are gone but tasks remain (FR-6: Auto-respawn)
                active_workers = [
                    w for w in self._workers.values() if w.status not in (WorkerStatus.STOPPED, WorkerStatus.CRASHED)
                ]
                if not active_workers and self._running:
                    remaining = self._get_remaining_tasks_for_level(current)
                    if remaining:
                        # FR-6: Auto-spawn replacement workers with respawn cap
                        self._auto_respawn_workers(current, len(remaining))

                await asyncio.sleep(self._poll_interval)

            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                await self.stop_async()
                break
            except Exception as e:
                logger.error(f"Error in async main loop: {e}")
                self.state.set_error(str(e))
                await self.stop_async(force=True)
                raise

        # Emit rush finished event
        with contextlib.suppress(Exception):
            self._plugin_registry.emit_event(
                LifecycleEvent(
                    event_type=PluginHookEvent.RUSH_FINISHED.value,
                    data={"feature": self.feature},
                )
            )

        logger.info("Async main loop ended")

    async def _poll_workers_async(self) -> None:
        """Async poll worker status and handle completions.

        Uses async state loading for non-blocking I/O.
        """
        await self.state.load_async()
        self._sync_levels_from_state()
        self._reassign_stranded_tasks()
        self._check_container_health()
        self.task_sync.sync_state()
        self.launcher.sync_state()

        # Check for stale tasks (FR-2: Task timeout watchdog)
        self._check_stale_tasks()

        for worker_id, worker in list(self._workers.items()):
            if worker.status in (WorkerStatus.STOPPED, WorkerStatus.CRASHED):
                continue
            status = self.launcher.monitor(worker_id)
            if status == WorkerStatus.CRASHED:
                logger.error(f"Worker {worker_id} crashed")
                worker.status = WorkerStatus.CRASHED
                self.state.set_worker_state(worker)
                if worker.current_task:
                    # FR-5: Worker crash → don't increment retry count
                    self._handle_worker_crash(worker.current_task, worker_id)
                self._handle_worker_exit(worker_id)
            elif status == WorkerStatus.CHECKPOINTING:
                logger.info(f"Worker {worker_id} checkpointing")
                worker.status = WorkerStatus.CHECKPOINTING
                self.state.set_worker_state(worker)
                self._handle_worker_exit(worker_id)
            elif status == WorkerStatus.STOPPED:
                worker.status = WorkerStatus.STOPPED
                self.state.set_worker_state(worker)
                self._handle_worker_exit(worker_id)
            worker.health_check_at = _now()

    # Alias for backward compatibility
    _poll_workers_sync = _poll_workers

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    def _get_remaining_tasks_for_level(self, level: int) -> list[str]:
        """Get remaining tasks for a level."""
        return self.levels.get_pending_tasks_for_level(level)

    def _print_plan(self, assignments: Any) -> None:
        """Print execution plan (for dry run)."""
        print("\n=== ZERG Execution Plan ===\n")
        print(f"Feature: {self.feature}")
        print(f"Total Tasks: {self.parser.total_tasks}")
        print(f"Levels: {self.parser.levels}")
        print(f"Workers: {assignments.worker_count}")
        print()

        for level in self.parser.levels:
            tasks = self.parser.get_tasks_for_level(level)
            print(f"Level {level}:")
            for task in tasks:
                worker = self.assigner.get_task_worker(task["id"]) if self.assigner else "?"
                print(f"  [{task['id']}] {task['title']} -> Worker {worker}")
            print()

    # ------------------------------------------------------------------
    # Callback registration (retained directly)
    # ------------------------------------------------------------------

    def on_task_complete(self, callback: Callable[[str], None]) -> None:
        """Register callback for task completion."""
        self._on_task_complete.append(callback)

    def on_level_complete(self, callback: Callable[[int], None]) -> None:
        """Register callback for level completion."""
        self._on_level_complete.append(callback)

    # ------------------------------------------------------------------
    # Public retry/resume API (thin wrappers)
    # ------------------------------------------------------------------

    def retry_task(self, task_id: str) -> bool:
        """Manually retry a failed task."""
        return self._retry_manager.retry_task(task_id)

    def retry_all_failed(self) -> list[str]:
        """Retry all failed tasks."""
        return self._retry_manager.retry_all_failed()

    def resume(self) -> None:
        """Resume paused execution."""
        if not self._paused:
            logger.info("Execution not paused")
            return

        logger.info("Resuming execution")
        self._paused = False
        self.state.set_paused(False)
        self.state.append_event("resumed", {})

    def verify_with_retry(
        self,
        task_id: str,
        command: str,
        timeout: int = 60,
        max_retries: int | None = None,
    ) -> bool:
        """Verify a task with retry logic."""
        return self._retry_manager.verify_with_retry(task_id, command, timeout, max_retries)

    def generate_task_contexts(self, task_graph: dict) -> dict:
        """Populate task['context'] for tasks missing it.

        Called by rush to enrich task-graph entries that don't already
        have context from the design phase.

        Returns dict mapping task_id -> context string.
        """
        contexts: dict[str, str] = {}
        feature = task_graph.get("feature", "")
        for task in task_graph.get("tasks", []):
            if task.get("context"):
                continue  # Already populated by design phase
            try:
                ctx = self._plugin_registry.build_task_context(task, task_graph, feature)
                if ctx:
                    task["context"] = ctx
                    contexts[task["id"]] = ctx
            except Exception:
                logger.warning(
                    "Failed to generate context for task %s",
                    task.get("id", "unknown"),
                    exc_info=True,
                )
        return contexts
