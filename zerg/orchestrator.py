"""ZERG orchestrator - main coordination engine."""

import concurrent.futures
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from zerg.assign import WorkerAssignment
from zerg.config import ZergConfig
from zerg.constants import LevelMergeStatus, TaskStatus, WorkerStatus
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
from zerg.logging import get_logger
from zerg.merge import MergeCoordinator, MergeFlowResult
from zerg.metrics import MetricsCollector, duration_ms
from zerg.parser import TaskParser
from zerg.ports import PortAllocator
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

        # Initialize components
        self.state = StateManager(feature)
        self.levels = LevelController()
        self.parser = TaskParser()
        self.gates = GateRunner(self.config)
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
        # Determine launcher type
        if mode == "subprocess":
            launcher_type = LauncherType.SUBPROCESS
        elif mode == "container":
            launcher_type = LauncherType.CONTAINER
        elif mode == "auto" or mode is None:
            # Auto-detect based on environment
            launcher_type = self._auto_detect_launcher_type()
        else:
            launcher_type = self.config.get_launcher_type()

        config = LauncherConfig(
            launcher_type=launcher_type,
            timeout_seconds=self.config.workers.timeout_minutes * 60,
            log_dir=Path(self.config.logging.directory),
        )

        if launcher_type == LauncherType.CONTAINER:
            # Use ContainerLauncher
            launcher = ContainerLauncher(
                config=config,
                image_name=self._get_worker_image_name(),
            )
            # Ensure network exists
            launcher.ensure_network()
            logger.info("Using ContainerLauncher")
            return launcher
        else:
            logger.info("Using SubprocessLauncher")
            return SubprocessLauncher(config)

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
        self._spawn_workers(worker_count)

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

    def _main_loop(self) -> None:
        """Main orchestration loop."""
        logger.info("Starting main loop")

        while self._running:
            try:
                # Poll worker status
                self._poll_workers()

                # Check level completion
                if self.levels.is_level_complete(self.levels.current_level):
                    self._on_level_complete_handler(self.levels.current_level)

                    # Advance to next level if possible
                    if self.levels.can_advance():
                        next_level = self.levels.advance_level()
                        if next_level:
                            self._start_level(next_level)
                    else:
                        # Check if all done
                        status = self.levels.get_status()
                        if status["is_complete"]:
                            logger.info("All tasks complete!")
                            self._running = False
                            break

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

    def _on_level_complete_handler(self, level: int) -> None:
        """Handle level completion.

        Args:
            level: Completed level
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

        return worker_state

    def _spawn_workers(self, count: int) -> None:
        """Spawn multiple workers.

        Args:
            count: Number of workers to spawn
        """
        logger.info(f"Spawning {count} workers")

        for worker_id in range(count):
            try:
                self._spawn_worker(worker_id)
            except Exception as e:
                logger.error(f"Failed to spawn worker {worker_id}: {e}")
                # Continue with other workers

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

    def _poll_workers(self) -> None:
        """Poll worker status and handle completions."""
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
        """Handle a task failure with retry logic.

        Args:
            task_id: Failed task ID
            worker_id: Worker that failed
            error: Error message

        Returns:
            True if task will be retried
        """
        retry_count = self.state.get_task_retry_count(task_id)

        if retry_count < self._max_retry_attempts:
            # Increment retry and requeue
            new_count = self.state.increment_task_retry(task_id)
            logger.warning(
                f"Task {task_id} failed (attempt {new_count}/{self._max_retry_attempts}), "
                f"will retry: {error}"
            )

            # Reset task to pending for retry
            self.state.set_task_status(task_id, TaskStatus.PENDING)
            self.state.append_event("task_retry", {
                "task_id": task_id,
                "worker_id": worker_id,
                "retry_count": new_count,
                "error": error,
            })
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

        # Check exit code (would need to get from container)
        # For now, assume clean exit means task complete

        if worker.current_task:
            # Check if task verification passes
            task = self.parser.get_task(worker.current_task)
            if task:
                verification = task.get("verification", {})
                if verification.get("command"):
                    # Compute and record task duration before marking complete
                    task_id = worker.current_task
                    task_state = self.state._state.get("tasks", {}).get(task_id, {})
                    started_at = task_state.get("started_at")
                    if started_at:
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
