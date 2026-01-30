"""ZERG orchestrator - main coordination engine."""

import concurrent.futures
import contextlib
import subprocess as sp
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from zerg.assign import WorkerAssignment
from zerg.config import ZergConfig
from zerg.constants import (
    LOGS_TASKS_DIR,
    LOGS_WORKERS_DIR,
    LevelMergeStatus,
    LogEvent,
    PluginHookEvent,
    TaskStatus,
    WorkerStatus,
)
from zerg.containers import ContainerManager
from zerg.gates import GateRunner
from zerg.launcher import (
    ContainerLauncher,
    LauncherConfig,
    LauncherType,
    SubprocessLauncher,
    WorkerLauncher,
)
from zerg.levels import LevelController
from zerg.log_writer import StructuredLogWriter
from zerg.logging import get_logger, setup_structured_logging
from zerg.merge import MergeCoordinator, MergeFlowResult
from zerg.metrics import MetricsCollector, duration_ms
from zerg.parser import TaskParser
from zerg.plugins import LifecycleEvent, PluginRegistry
from zerg.ports import PortAllocator
from zerg.retry_backoff import RetryBackoffCalculator
from zerg.state import StateManager
from zerg.task_sync import TaskSyncBridge
from zerg.types import WorkerState
from zerg.worktree import WorktreeManager

logger = get_logger("orchestrator")


class Orchestrator:
    """Main ZERG orchestration engine.

    Coordinates workers, manages levels, and handles state transitions.
    """

    def __init__(
        self,
        feature: str,
        config: ZergConfig | None = None,
        repo_path: str | Path = ".",
        launcher_mode: str | None = None,
    ) -> None:
        """Initialize orchestrator.

        Args:
            feature: Feature name being executed
            config: ZERG configuration
            repo_path: Path to git repository
            launcher_mode: Launcher mode (subprocess, container, auto)
        """
        self.feature = feature
        self.config = config or ZergConfig.load()
        self.repo_path = Path(repo_path).resolve()
        self._launcher_mode = launcher_mode

        # Initialize plugin registry first (needed by other components)
        self._plugin_registry = PluginRegistry()
        if hasattr(self.config, 'plugins') and self.config.plugins.enabled:
            try:
                self._plugin_registry.load_yaml_hooks(
                    [h.model_dump() for h in self.config.plugins.hooks]
                )
                self._plugin_registry.load_entry_points()
            except Exception as e:
                logger.warning(f"Failed to load plugins: {e}")

        # Initialize components
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
        self.task_sync = TaskSyncBridge(feature, self.state)

        # Initialize launcher based on config and mode
        self.launcher: WorkerLauncher = self._create_launcher(mode=launcher_mode)

        # Clean up orphan containers from previous runs (container mode only)
        try:
            if isinstance(self.launcher, ContainerLauncher):
                self._cleanup_orphan_containers()
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

    def _create_launcher(self, mode: str | None = None) -> WorkerLauncher:
        """Create worker launcher based on config and mode.

        Args:
            mode: Launcher mode override (subprocess, container, auto)
                  If None, uses config setting

        Returns:
            Configured WorkerLauncher instance
        """
        # Check plugin registry first for custom launcher
        if mode and mode not in ("subprocess", "container", "auto"):
            from zerg.launcher import get_plugin_launcher
            plugin_launcher = get_plugin_launcher(mode, self._plugin_registry)
            if plugin_launcher is not None:
                logger.info(f"Using plugin launcher: {mode}")
                return plugin_launcher

        # Determine launcher type
        if mode == "subprocess":
            launcher_type = LauncherType.SUBPROCESS
        elif mode == "container":
            launcher_type = LauncherType.CONTAINER
        elif mode == "auto" or mode is None:
            # Auto-detect based on environment
            launcher_type = self._auto_detect_launcher_type()
        else:
            # Try plugin launcher for unrecognized mode
            from zerg.launcher import get_plugin_launcher
            plugin_launcher = get_plugin_launcher(mode, self._plugin_registry)
            if plugin_launcher is not None:
                logger.info(f"Using plugin launcher: {mode}")
                return plugin_launcher
            # Fall back to config setting if plugin not found
            launcher_type = self.config.get_launcher_type()

        config = LauncherConfig(
            launcher_type=launcher_type,
            timeout_seconds=self.config.workers.timeout_minutes * 60,
            log_dir=Path(self.config.logging.directory),
        )

        if launcher_type == LauncherType.CONTAINER:
            # Use ContainerLauncher with resource limits from config
            launcher = ContainerLauncher(
                config=config,
                image_name=self._get_worker_image_name(),
                memory_limit=self.config.resources.container_memory_limit,
                cpu_limit=self.config.resources.container_cpu_limit,
            )
            # Ensure network exists
            network_ok = launcher.ensure_network()
            if not network_ok:
                if mode == "container":
                    raise RuntimeError(
                        "Container mode explicitly requested but Docker network "
                        "creation failed. Check that Docker is running and accessible."
                    )
                # Auto-detected container mode: fall back gracefully
                logger.warning(
                    "Docker network setup failed, falling back to subprocess"
                )
                return SubprocessLauncher(config)
            logger.info("Using ContainerLauncher")
            return launcher
        else:
            logger.info("Using SubprocessLauncher")
            return SubprocessLauncher(config)

    def _cleanup_orphan_containers(self) -> None:
        """Remove leftover zerg-worker containers from previous runs."""
        try:
            result = sp.run(
                ["docker", "ps", "-a", "--filter", "name=zerg-worker",
                 "--format", "{{.ID}}"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return
            for cid in result.stdout.strip().split("\n"):
                if cid:
                    sp.run(
                        ["docker", "rm", "-f", cid],
                        capture_output=True, timeout=10,
                    )
                    logger.info(f"Removed orphan container {cid[:12]}")
        except (sp.TimeoutExpired, FileNotFoundError):
            pass  # Docker not available, skip

    def _check_container_health(self) -> None:
        """Mark containers stuck beyond timeout as CRASHED."""
        try:
            is_container = isinstance(self.launcher, ContainerLauncher)
        except TypeError:
            return
        if not is_container:
            return
        timeout_seconds = self.config.workers.timeout_minutes * 60
        for worker_id, worker in list(self._workers.items()):
            if worker.status == WorkerStatus.RUNNING and worker.started_at:
                elapsed = (datetime.now() - worker.started_at).total_seconds()
                if elapsed > timeout_seconds:
                    logger.warning(
                        f"Worker {worker_id} exceeded timeout "
                        f"({elapsed:.0f}s > {timeout_seconds}s), terminating"
                    )
                    self.launcher.terminate(worker_id)
                    worker.status = WorkerStatus.CRASHED
                    self.state.set_worker_state(worker)

    def _auto_detect_launcher_type(self) -> LauncherType:
        """Auto-detect whether to use container or subprocess launcher.

        Detection logic:
        1. Check if devcontainer.json exists
        2. Check if worker image is built
        3. Fall back to subprocess if containers not available

        Returns:
            Detected LauncherType
        """
        devcontainer_path = self.repo_path / ".devcontainer" / "devcontainer.json"

        # No devcontainer config = use subprocess
        if not devcontainer_path.exists():
            logger.debug("No devcontainer.json found, using subprocess mode")
            return LauncherType.SUBPROCESS

        # Check if image exists
        image_name = self._get_worker_image_name()

        try:
            import subprocess as sp
            result = sp.run(
                ["docker", "image", "inspect", image_name],
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                logger.debug(f"Found worker image {image_name}, using container mode")
                return LauncherType.CONTAINER
            else:
                logger.debug(f"Worker image {image_name} not found, using subprocess mode")
                return LauncherType.SUBPROCESS
        except Exception as e:
            logger.debug(f"Docker check failed ({e}), using subprocess mode")
            return LauncherType.SUBPROCESS

    def _get_worker_image_name(self) -> str:
        """Get the worker image name.

        Returns:
            Docker image name for workers
        """
        # Check config first
        if hasattr(self.config, "container_image"):
            return self.config.container_image

        # Default to standard worker image
        return "zerg-worker"

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

        # Initialize state
        self.state.load()
        self.state.append_event("rush_started", {
            "workers": worker_count,
            "total_tasks": len(tasks),
        })

        if dry_run:
            logger.info("Dry run - not spawning workers")
            self._print_plan(assignments)
            return

        # Start execution
        self._running = True
        spawned = self._spawn_workers(worker_count)
        if spawned == 0:
            self.state.append_event("rush_failed", {
                "reason": "No workers spawned",
                "requested": worker_count,
                "mode": self._launcher_mode,
            })
            self.state.save()
            raise RuntimeError(
                f"All {worker_count} workers failed to spawn"
                f" (mode={self._launcher_mode}). Cannot proceed."
            )
        if spawned < worker_count:
            logger.warning(
                f"Only {spawned}/{worker_count} workers spawned."
                " Continuing with reduced capacity."
            )

        # Wait for workers to initialize before starting level
        self._wait_for_initialization(timeout=600)

        self._start_level(start_level or 1)
        self._main_loop()

    def stop(self, force: bool = False) -> None:
        """Stop orchestration.

        Args:
            force: Force stop without graceful shutdown
        """
        logger.info(f"Stopping orchestration (force={force})")
        self._running = False

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
        }

    def _check_retry_ready_tasks(self) -> None:
        """Check for tasks whose backoff period has elapsed and requeue them."""
        ready_tasks = self.state.get_tasks_ready_for_retry()
        for task_id in ready_tasks:
            logger.info(f"Task {task_id} backoff elapsed, requeueing for retry")
            self.state.set_task_status(task_id, TaskStatus.PENDING)
            # Clear the schedule so it's not picked up again
            self.state.set_task_retry_schedule(task_id, "")
            self.state.append_event("task_retry_ready", {"task_id": task_id})

    def _main_loop(self) -> None:
        """Main orchestration loop."""
        logger.info("Starting main loop")
        _handled_levels: set[int] = set()  # Guard against re-triggering

        while self._running:
            try:
                # Poll worker status
                self._poll_workers()

                # Check for tasks ready to retry after backoff
                self._check_retry_ready_tasks()

                # Check level completion (guard: only handle each level once)
                current = self.levels.current_level
                if (
                    current > 0
                    and current not in _handled_levels
                    and self.levels.is_level_complete(current)
                ):
                    _handled_levels.add(current)
                    merge_ok = self._on_level_complete_handler(current)

                    if not merge_ok:
                        # Merge failed — don't advance, wait for intervention
                        logger.warning(f"Level {current} merge failed, pausing execution")
                        continue

                    # Advance to next level if possible
                    if self.levels.can_advance():
                        next_level = self.levels.advance_level()
                        if next_level:
                            self._start_level(next_level)
                            # Respawn workers for the new level
                            self._respawn_workers_for_level(next_level)
                    else:
                        # Check if all done
                        status = self.levels.get_status()
                        if status["is_complete"]:
                            logger.info("All tasks complete!")
                            self._running = False
                            break

                # Check if all workers are gone but tasks remain
                active_workers = [
                    w for w in self._workers.values()
                    if w.status not in (WorkerStatus.STOPPED, WorkerStatus.CRASHED)
                ]
                if not active_workers and self._running:
                    remaining = self._get_remaining_tasks_for_level(current)
                    if remaining:
                        logger.warning(
                            f"All workers exited but {len(remaining)} tasks remain "
                            f"at level {current}. Respawning workers."
                        )
                        self._respawn_workers_for_level(current)

                # Sleep before next poll
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
            self._plugin_registry.emit_event(LifecycleEvent(
                event_type=PluginHookEvent.RUSH_FINISHED.value,
                data={"feature": self.feature},
            ))

        logger.info("Main loop ended")

    def _start_level(self, level: int) -> None:
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
        level_tasks = [self.parser.get_task(tid) for tid in task_ids]
        level_tasks = [t for t in level_tasks if t is not None]
        if level_tasks:
            self.task_sync.create_level_tasks(level, level_tasks)
            logger.info(f"Created {len(level_tasks)} Claude Tasks for level {level}")

        # Assign tasks to workers
        for task_id in task_ids:
            if self.assigner:
                worker_id = self.assigner.get_task_worker(task_id)
                if worker_id is not None:
                    self.state.set_task_status(task_id, TaskStatus.PENDING, worker_id=worker_id)

    def _on_level_complete_handler(self, level: int) -> bool:
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
                future = executor.submit(self._merge_level, level)
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
            except Exception:
                pass

            # Rebase worker branches onto merged base
            self._rebase_all_workers(level)

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
                self._pause_for_intervention(f"Merge conflict in level {level}")
            else:
                # BF-007: Set recoverable error state (pause) instead of stop
                self.state.set_level_merge_status(level, LevelMergeStatus.FAILED)
                self._set_recoverable_error(
                    f"Level {level} merge failed after {max_retries} attempts: {error_msg}"
                )

            return False

    def _set_recoverable_error(self, error: str) -> None:
        """Set recoverable error state (pause instead of stop).

        Args:
            error: Error message
        """
        logger.warning(f"Setting recoverable error state: {error}")
        self.state.set_error(error)
        self._paused = True
        self.state.set_paused(True)
        self.state.append_event("recoverable_error", {"error": error})

    def _merge_level(self, level: int) -> MergeFlowResult:
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

    def _rebase_all_workers(self, level: int) -> None:
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

    def _pause_for_intervention(self, reason: str) -> None:
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

    def _spawn_worker(self, worker_id: int) -> WorkerState:
        """Spawn a single worker.

        Args:
            worker_id: Worker identifier

        Returns:
            WorkerState for the spawned worker
        """
        logger.info(f"Spawning worker {worker_id}")

        # Allocate port
        port = self.ports.allocate_one()

        # Create worktree
        wt_info = self.worktrees.create(self.feature, worker_id)

        # Use the unified launcher interface (works for both subprocess and container)
        result = self.launcher.spawn(
            worker_id=worker_id,
            feature=self.feature,
            worktree_path=wt_info.path,
            branch=wt_info.branch,
        )

        if not result.success:
            raise RuntimeError(f"Failed to spawn worker: {result.error}")

        # Get container ID if using ContainerLauncher
        container_id = None
        if result.handle and result.handle.container_id:
            container_id = result.handle.container_id

        # Create worker state
        worker_state = WorkerState(
            worker_id=worker_id,
            status=WorkerStatus.RUNNING,
            port=port,
            container_id=container_id,
            worktree_path=str(wt_info.path),
            branch=wt_info.branch,
            started_at=datetime.now(),
        )

        self._workers[worker_id] = worker_state
        self.state.set_worker_state(worker_state)
        self.state.append_event("worker_started", {
            "worker_id": worker_id,
            "port": port,
            "container_id": container_id,
            "mode": "container" if container_id else "subprocess",
        })

        # Emit plugin lifecycle event
        with contextlib.suppress(Exception):
            self._plugin_registry.emit_event(LifecycleEvent(
                event_type=PluginHookEvent.WORKER_SPAWNED.value,
                data={"worker_id": worker_id, "feature": self.feature},
            ))

        return worker_state

    def _spawn_workers(self, count: int) -> int:
        """Spawn multiple workers.

        Args:
            count: Number of workers to spawn

        Returns:
            Number of workers successfully spawned.
        """
        logger.info(f"Spawning {count} workers")
        spawned = 0

        for worker_id in range(count):
            try:
                self._spawn_worker(worker_id)
                spawned += 1
            except Exception as e:
                logger.error(f"Failed to spawn worker {worker_id}: {e}")
                # Continue with other workers

        return spawned

    def _wait_for_initialization(self, timeout: int = 600) -> bool:
        """Wait for all workers to initialize.

        Args:
            timeout: Maximum wait time in seconds (default 600 = 10 minutes)

        Returns:
            True if all workers initialized successfully
        """
        logger.info("Waiting for workers to initialize...")

        start_time = time.time()
        check_interval = 2  # seconds

        while time.time() - start_time < timeout:
            all_ready = True
            failed_workers = []

            for worker_id, worker in list(self._workers.items()):
                status = self.launcher.monitor(worker_id)

                if status in (WorkerStatus.RUNNING, WorkerStatus.READY, WorkerStatus.IDLE):
                    # Worker is ready - record ready_at if not already recorded
                    if worker.ready_at is None:
                        worker.ready_at = datetime.now()
                        self.state.set_worker_ready(worker_id)
                        self.state.append_event("worker_ready", {
                            "worker_id": worker_id,
                            "worktree": worker.worktree_path,
                            "branch": worker.branch,
                        })
                    worker.status = status
                    continue
                elif status in (WorkerStatus.CRASHED, WorkerStatus.STOPPED):
                    # Worker failed during init
                    failed_workers.append(worker_id)
                    logger.warning(f"Worker {worker_id} failed during initialization")
                else:
                    # Still initializing
                    all_ready = False

            # Handle failed workers
            for worker_id in failed_workers:
                if worker_id in self._workers:
                    del self._workers[worker_id]

            if all_ready and self._workers:
                elapsed = time.time() - start_time
                logger.info(f"All {len(self._workers)} workers initialized in {elapsed:.1f}s")
                return True

            if not self._workers:
                logger.error("All workers failed during initialization")
                return False

            time.sleep(check_interval)

        logger.warning(f"Initialization timeout after {timeout}s")
        return len(self._workers) > 0  # Continue if any workers are ready

    def _terminate_worker(self, worker_id: int, force: bool = False) -> None:
        """Terminate a worker.

        Args:
            worker_id: Worker identifier
            force: Force termination
        """
        worker = self._workers.get(worker_id)
        if not worker:
            return

        logger.info(f"Terminating worker {worker_id}")

        # Stop via unified launcher interface
        self.launcher.terminate(worker_id, force=force)

        # Delete worktree
        try:
            wt_path = self.worktrees.get_worktree_path(self.feature, worker_id)
            self.worktrees.delete(wt_path, force=True)
        except Exception as e:
            logger.warning(f"Failed to delete worktree for worker {worker_id}: {e}")

        # Release port
        if worker.port:
            self.ports.release(worker.port)

        # Update state
        worker.status = WorkerStatus.STOPPED
        self.state.set_worker_state(worker)
        self.state.append_event("worker_stopped", {"worker_id": worker_id})

        del self._workers[worker_id]

    def _sync_levels_from_state(self) -> None:
        """Sync LevelController with task completions from disk state.

        Workers write task completions directly to the shared state JSON.
        The orchestrator's in-memory LevelController must be updated to
        reflect these completions so level advancement can trigger.
        """
        tasks_state = self.state._state.get("tasks", {})
        for task_id, task_state in tasks_state.items():
            disk_status = task_state.get("status", "")
            level_status = self.levels.get_task_status(task_id)

            # Task is complete on disk but not in LevelController
            if disk_status == TaskStatus.COMPLETE.value and level_status != TaskStatus.COMPLETE.value:
                self.levels.mark_task_complete(task_id)
                logger.info(f"Synced task {task_id} completion to LevelController")

            # Task is failed on disk but not in LevelController
            elif disk_status == TaskStatus.FAILED.value and level_status != TaskStatus.FAILED.value:
                self.levels.mark_task_failed(task_id)
                logger.info(f"Synced task {task_id} failure to LevelController")

            # Task is in progress on disk but not in LevelController
            elif disk_status in (TaskStatus.IN_PROGRESS.value, TaskStatus.CLAIMED.value):
                if level_status not in (TaskStatus.IN_PROGRESS.value, TaskStatus.CLAIMED.value):
                    worker_id = task_state.get("worker_id")
                    self.levels.mark_task_in_progress(task_id, worker_id)

    def _reassign_stranded_tasks(self) -> None:
        """Reassign tasks stuck on stopped/crashed workers.

        When a worker exits, tasks pre-assigned to it (via worker_id in state)
        remain stuck because claim_task() blocks cross-worker claims.
        This method clears the worker_id for pending tasks whose assigned
        worker is no longer active, allowing any worker to claim them.
        """
        tasks_state = self.state._state.get("tasks", {})
        workers_state = self.state._state.get("workers", {})

        # Build set of active worker IDs
        active_worker_ids = set()
        for wid_str, wdata in workers_state.items():
            status = wdata.get("status", "")
            if status not in ("stopped", "crashed"):
                active_worker_ids.add(int(wid_str))

        # Also check in-memory workers
        for wid, w in self._workers.items():
            if w.status not in (WorkerStatus.STOPPED, WorkerStatus.CRASHED):
                active_worker_ids.add(wid)

        for task_id, task_state in tasks_state.items():
            status = task_state.get("status", "")
            worker_id = task_state.get("worker_id")

            # Only reassign pending/todo tasks with a dead worker assignment
            if status in (TaskStatus.PENDING.value, TaskStatus.TODO.value, "pending", "todo"):
                if worker_id is not None and worker_id not in active_worker_ids:
                    # Clear the worker assignment so any worker can claim it
                    task_state["worker_id"] = None
                    logger.info(
                        f"Reassigned stranded task {task_id} "
                        f"(was worker {worker_id}, now unassigned)"
                    )

        # Persist changes
        self.state.save()

    def _poll_workers(self) -> None:
        """Poll worker status and handle completions."""
        # Reload state from disk to pick up worker-written changes
        self.state.load()

        # Sync disk state to in-memory LevelController
        self._sync_levels_from_state()

        # Reassign tasks stuck on dead workers
        self._reassign_stranded_tasks()

        # Check container health (timeout detection)
        self._check_container_health()

        # Sync Claude Tasks with current state
        self.task_sync.sync_state()

        # Sync launcher state to clean up terminated workers
        self.launcher.sync_state()

        for worker_id, worker in list(self._workers.items()):
            # Skip workers already marked as stopped/crashed (already handled)
            if worker.status in (WorkerStatus.STOPPED, WorkerStatus.CRASHED):
                continue

            # Check status via unified launcher interface
            status = self.launcher.monitor(worker_id)

            if status == WorkerStatus.CRASHED:
                logger.error(f"Worker {worker_id} crashed")
                worker.status = WorkerStatus.CRASHED
                self.state.set_worker_state(worker)

                # Mark current task as failed and handle retry
                if worker.current_task:
                    self._handle_task_failure(
                        worker.current_task,
                        worker_id,
                        "Worker crashed",
                    )

                # Handle exit (will respawn if needed)
                self._handle_worker_exit(worker_id)

            elif status == WorkerStatus.CHECKPOINTING:
                logger.info(f"Worker {worker_id} checkpointing")
                worker.status = WorkerStatus.CHECKPOINTING
                self.state.set_worker_state(worker)
                self._handle_worker_exit(worker_id)

            elif status == WorkerStatus.STOPPED:
                # Worker exited - check for completion
                worker.status = WorkerStatus.STOPPED
                self.state.set_worker_state(worker)
                self._handle_worker_exit(worker_id)

            # Update health check
            worker.health_check_at = datetime.now()

    def _handle_task_failure(
        self,
        task_id: str,
        worker_id: int,
        error: str,
    ) -> bool:
        """Handle a task failure with retry logic and backoff.

        Args:
            task_id: Failed task ID
            worker_id: Worker that failed
            error: Error message

        Returns:
            True if task will be retried
        """
        retry_count = self.state.get_task_retry_count(task_id)

        if retry_count < self._max_retry_attempts:
            # Calculate backoff delay
            delay = RetryBackoffCalculator.calculate_delay(
                attempt=retry_count + 1,
                strategy=self.config.workers.backoff_strategy,
                base_seconds=self.config.workers.backoff_base_seconds,
                max_seconds=self.config.workers.backoff_max_seconds,
            )

            # Schedule retry
            next_retry_at = (
                datetime.now() + timedelta(seconds=delay)
            ).isoformat()

            new_count = self.state.increment_task_retry(task_id, next_retry_at=next_retry_at)
            self.state.set_task_retry_schedule(task_id, next_retry_at)

            logger.warning(
                f"Task {task_id} failed (attempt {new_count}/{self._max_retry_attempts}), "
                f"will retry in {delay:.0f}s: {error}"
            )

            # Mark as waiting_retry instead of immediately pending
            self.state.set_task_status(task_id, "waiting_retry")
            self.state.append_event("task_retry_scheduled", {
                "task_id": task_id,
                "worker_id": worker_id,
                "retry_count": new_count,
                "backoff_seconds": round(delay),
                "next_retry_at": next_retry_at,
                "error": error,
            })

            if self._structured_writer:
                self._structured_writer.emit(
                    "warn",
                    f"Task {task_id} retry {new_count} scheduled in {delay:.0f}s",
                    event=LogEvent.TASK_FAILED,
                    data={"task_id": task_id, "backoff_seconds": round(delay)},
                )

            return True
        else:
            # Exceeded retry limit
            logger.error(
                f"Task {task_id} failed after {retry_count} retries: {error}"
            )
            self.levels.mark_task_failed(task_id, error)
            self.state.set_task_status(
                task_id,
                TaskStatus.FAILED,
                worker_id=worker_id,
                error=f"Failed after {retry_count} retries: {error}",
            )
            self.state.append_event("task_failed_permanent", {
                "task_id": task_id,
                "worker_id": worker_id,
                "retry_count": retry_count,
                "error": error,
            })
            return False

    def _handle_worker_exit(self, worker_id: int) -> None:
        """Handle worker exit.

        Args:
            worker_id: Worker that exited
        """
        worker = self._workers.get(worker_id)
        if not worker:
            return

        # Emit plugin lifecycle event
        with contextlib.suppress(Exception):
            self._plugin_registry.emit_event(LifecycleEvent(
                event_type=PluginHookEvent.WORKER_EXITED.value,
                data={"worker_id": worker_id, "feature": self.feature},
            ))

        # Check exit code (would need to get from container)
        # For now, assume clean exit means task complete

        if worker.current_task:
            # Check if task verification passes
            task = self.parser.get_task(worker.current_task)
            if task:
                verification = task.get("verification", {})
                if verification.get("command"):
                    # Compute and record task duration before marking complete
                    # Guard: only record if worker didn't already record it
                    task_id = worker.current_task
                    task_state = self.state._state.get("tasks", {}).get(task_id, {})
                    started_at = task_state.get("started_at")
                    if started_at and task_state.get("duration_ms") is None:
                        task_duration = duration_ms(started_at, datetime.now())
                        if task_duration:
                            self.state.record_task_duration(task_id, task_duration)

                    # Task should have been verified by worker
                    self.levels.mark_task_complete(worker.current_task)
                    self.state.set_task_status(worker.current_task, TaskStatus.COMPLETE)

                    for callback in self._on_task_complete:
                        callback(worker.current_task)

        # Remove worker from tracking FIRST to prevent respawn loops
        old_worktree = worker.worktree_path
        old_port = worker.port
        del self._workers[worker_id]

        # Release port
        if old_port:
            self.ports.release(old_port)

        # Restart worker for more tasks (with new state)
        remaining = self._get_remaining_tasks_for_level(self.levels.current_level)
        if remaining and self._running:
            try:
                self._spawn_worker(worker_id)
            except Exception as e:
                logger.error(f"Failed to restart worker {worker_id}: {e}")
                # Clean up worktree if spawn failed
                if old_worktree:
                    try:
                        self.worktrees.delete(Path(old_worktree), force=True)
                    except Exception as cleanup_err:
                        logger.warning(f"Failed to clean up worktree: {cleanup_err}")

    def _get_remaining_tasks_for_level(self, level: int) -> list[str]:
        """Get remaining tasks for a level.

        Args:
            level: Level number

        Returns:
            List of incomplete task IDs
        """
        pending = self.levels.get_pending_tasks_for_level(level)
        return pending

    def _respawn_workers_for_level(self, level: int) -> int:
        """Respawn workers for a new level.

        After a level completes and the next level starts, workers may have
        already exited. This method spawns fresh workers to execute the new
        level's tasks.

        Args:
            level: Level number that needs workers

        Returns:
            Number of workers successfully spawned
        """
        # Determine how many workers we need
        remaining = self._get_remaining_tasks_for_level(level)
        if not remaining:
            return 0

        # Count still-active workers
        active = [
            wid for wid, w in self._workers.items()
            if w.status not in (WorkerStatus.STOPPED, WorkerStatus.CRASHED)
        ]

        # Determine target worker count from original assignments
        target_count = self.assigner.worker_count if self.assigner else 2
        need = min(target_count - len(active), len(remaining))

        if need <= 0:
            return 0

        logger.info(f"Respawning {need} workers for level {level} ({len(remaining)} tasks remaining)")

        spawned = 0
        # Find available worker IDs (prefer reusing IDs from stopped workers)
        used_ids = set(self._workers.keys())
        available_ids = [i for i in range(target_count) if i not in used_ids]

        # Also add IDs from stopped/crashed workers after cleaning them out
        stopped_ids = [
            wid for wid, w in list(self._workers.items())
            if w.status in (WorkerStatus.STOPPED, WorkerStatus.CRASHED)
        ]
        for wid in stopped_ids:
            del self._workers[wid]
            available_ids.append(wid)

        available_ids = sorted(set(available_ids))[:need]

        for worker_id in available_ids:
            try:
                self._spawn_worker(worker_id)
                spawned += 1
            except Exception as e:
                logger.error(f"Failed to respawn worker {worker_id}: {e}")

        if spawned > 0:
            # Wait for new workers to initialize
            self._wait_for_initialization(timeout=300)

        return spawned

    def _print_plan(self, assignments: Any) -> None:
        """Print execution plan (for dry run).

        Args:
            assignments: WorkerAssignments
        """
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

    def on_task_complete(self, callback: Callable[[str], None]) -> None:
        """Register callback for task completion.

        Args:
            callback: Function to call with task_id
        """
        self._on_task_complete.append(callback)

    def on_level_complete(self, callback: Callable[[int], None]) -> None:
        """Register callback for level completion.

        Args:
            callback: Function to call with level number
        """
        self._on_level_complete.append(callback)

    def retry_task(self, task_id: str) -> bool:
        """Manually retry a failed task.

        Args:
            task_id: Task to retry

        Returns:
            True if task was queued for retry
        """
        current_status = self.state.get_task_status(task_id)

        if current_status not in (TaskStatus.FAILED.value, "failed"):
            logger.warning(f"Task {task_id} is not in failed state: {current_status}")
            return False

        # Reset retry count and status
        self.state.reset_task_retry(task_id)
        self.state.set_task_status(task_id, TaskStatus.PENDING)
        self.state.append_event("task_manual_retry", {"task_id": task_id})

        logger.info(f"Task {task_id} queued for retry")
        return True

    def retry_all_failed(self) -> list[str]:
        """Retry all failed tasks.

        Returns:
            List of task IDs queued for retry
        """
        failed = self.state.get_failed_tasks()
        retried = []

        for task_info in failed:
            task_id = task_info["task_id"]
            if self.retry_task(task_id):
                retried.append(task_id)

        logger.info(f"Queued {len(retried)} tasks for retry")
        return retried

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
        """Verify a task with retry logic.

        Args:
            task_id: Task being verified
            command: Verification command
            timeout: Timeout in seconds
            max_retries: Override max retry attempts

        Returns:
            True if verification passed
        """
        from zerg.verify import VerificationExecutor

        verifier = VerificationExecutor()
        max_attempts = max_retries if max_retries is not None else self._max_retry_attempts

        for attempt in range(max_attempts + 1):
            result = verifier.verify(
                command,
                task_id,
                timeout=timeout,
                cwd=self.repo_path,
            )

            if result.success:
                return True

            if attempt < max_attempts:
                logger.warning(
                    f"Verification failed for {task_id} "
                    f"(attempt {attempt + 1}/{max_attempts + 1}), retrying..."
                )
                time.sleep(1)  # Brief pause before retry

        return False
