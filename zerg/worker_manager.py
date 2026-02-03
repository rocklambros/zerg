"""ZERG WorkerManager - worker lifecycle management extracted from Orchestrator."""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from zerg.assign import WorkerAssignment
from zerg.capability_resolver import ResolvedCapabilities
from zerg.config import ZergConfig
from zerg.constants import (
    PluginHookEvent,
    TaskStatus,
    WorkerStatus,
)
from zerg.launcher import WorkerLauncher
from zerg.levels import LevelController
from zerg.log_writer import StructuredLogWriter
from zerg.logging import get_logger
from zerg.metrics import duration_ms
from zerg.parser import TaskParser
from zerg.plugins import LifecycleEvent, PluginRegistry
from zerg.ports import PortAllocator
from zerg.state import StateManager
from zerg.types import WorkerState
from zerg.worktree import WorktreeManager

if TYPE_CHECKING:
    from zerg.circuit_breaker import CircuitBreaker

logger = get_logger("worker_manager")


class WorkerManager:
    """Manages worker lifecycle: spawning, initialization, termination, and exit handling.

    This component owns worker spawning, monitoring initialization, termination,
    and respawning logic. The workers dict is shared by reference with the
    Orchestrator so both see the same state.
    """

    def __init__(
        self,
        feature: str,
        config: ZergConfig,
        state: StateManager,
        levels: LevelController,
        parser: TaskParser,
        launcher: WorkerLauncher,
        worktrees: WorktreeManager,
        ports: PortAllocator,
        assigner: WorkerAssignment | None,
        plugin_registry: PluginRegistry,
        workers: dict[int, WorkerState],
        on_task_complete: list[Callable[[str], None]],
        on_task_failure: Callable[[str, int, str], bool] | None = None,
        structured_writer: StructuredLogWriter | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        capabilities: ResolvedCapabilities | None = None,
    ) -> None:
        """Initialize WorkerManager.

        Args:
            feature: Feature name being executed
            config: ZERG configuration
            state: State manager for persisting worker/task state
            levels: Level controller for tracking level progress
            parser: Task parser for accessing task definitions
            launcher: Worker launcher (subprocess or container)
            worktrees: Git worktree manager
            ports: Port allocator for worker ports
            assigner: Worker assignment mapper (may be None before start)
            plugin_registry: Plugin registry for lifecycle events
            workers: Shared workers dict (passed by reference from Orchestrator)
            on_task_complete: Shared callbacks list for task completion
            on_task_failure: Callback for task failure/retry (from TaskRetryManager)
            structured_writer: Optional structured log writer
            circuit_breaker: Optional circuit breaker for worker failure management
            capabilities: Resolved cross-cutting capabilities for env injection
        """
        self.feature = feature
        self.config = config
        self.state = state
        self.levels = levels
        self.parser = parser
        self.launcher = launcher
        self.worktrees = worktrees
        self.ports = ports
        self.assigner = assigner
        self._plugin_registry = plugin_registry
        self._workers = workers
        self._on_task_complete = on_task_complete
        self._on_task_failure = on_task_failure
        self._structured_writer = structured_writer
        self._circuit_breaker = circuit_breaker
        self._capabilities = capabilities
        self._running = False

    def spawn_worker(self, worker_id: int) -> WorkerState:
        """Spawn a single worker.

        Allocates a port, creates a git worktree, launches the worker process
        via the launcher, creates a WorkerState, and emits lifecycle events.

        Args:
            worker_id: Worker identifier

        Returns:
            WorkerState for the spawned worker

        Raises:
            RuntimeError: If the worker fails to spawn or circuit is open
        """
        # Check circuit breaker before spawning
        if self._circuit_breaker is not None and not self._circuit_breaker.can_accept_task(worker_id):
            logger.warning(f"Worker {worker_id} circuit is open, skipping spawn")
            raise RuntimeError(f"Worker {worker_id} circuit breaker is open")

        logger.info(f"Spawning worker {worker_id}")

        # Allocate port
        port = self.ports.allocate_one()

        # Create worktree
        wt_info = self.worktrees.create(self.feature, worker_id)

        # Build capability env vars if resolved capabilities are available
        capability_env = self._capabilities.to_env_vars() if self._capabilities else None

        # Use the unified launcher interface (works for both subprocess and container)
        result = self.launcher.spawn(
            worker_id=worker_id,
            feature=self.feature,
            worktree_path=wt_info.path,
            branch=wt_info.branch,
            env=capability_env,
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
        self.state.append_event(
            "worker_started",
            {
                "worker_id": worker_id,
                "port": port,
                "container_id": container_id,
                "mode": "container" if container_id else "subprocess",
            },
        )

        # Emit plugin lifecycle event
        with contextlib.suppress(Exception):
            self._plugin_registry.emit_event(
                LifecycleEvent(
                    event_type=PluginHookEvent.WORKER_SPAWNED.value,
                    data={"worker_id": worker_id, "feature": self.feature},
                )
            )

        return worker_state

    def spawn_workers(self, count: int) -> int:
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
                self.spawn_worker(worker_id)
                spawned += 1
            except Exception as e:
                logger.error(f"Failed to spawn worker {worker_id}: {e}")
                # Continue with other workers

        return spawned

    def wait_for_initialization(self, timeout: int = 600) -> bool:
        """Wait for all workers to initialize.

        Polls worker status via the launcher until all workers report as ready,
        or until the timeout elapses. Workers that fail during initialization
        are removed from the workers dict.

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
                        self.state.append_event(
                            "worker_ready",
                            {
                                "worker_id": worker_id,
                                "worktree": worker.worktree_path,
                                "branch": worker.branch,
                            },
                        )
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

    def terminate_worker(self, worker_id: int, force: bool = False) -> None:
        """Terminate a worker.

        Stops the worker via the launcher, deletes its worktree, releases its
        port, updates state, and removes it from the workers dict.

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

    def handle_worker_exit(self, worker_id: int) -> None:
        """Handle worker exit.

        Emits lifecycle events, checks task verification, records duration,
        marks tasks complete, invokes on_task_complete callbacks, releases
        resources, and respawns the worker if tasks remain.

        Args:
            worker_id: Worker that exited
        """
        worker = self._workers.get(worker_id)
        if not worker:
            return

        # Emit plugin lifecycle event
        with contextlib.suppress(Exception):
            self._plugin_registry.emit_event(
                LifecycleEvent(
                    event_type=PluginHookEvent.WORKER_EXITED.value,
                    data={"worker_id": worker_id, "feature": self.feature},
                )
            )

        # Record crash in circuit breaker
        if worker.status == WorkerStatus.CRASHED and self._circuit_breaker is not None:
            self._circuit_breaker.record_failure(worker_id, task_id=worker.current_task, error="Worker crashed")

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

                    # Record success in circuit breaker
                    if self._circuit_breaker is not None:
                        self._circuit_breaker.record_success(worker_id)

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
                self.spawn_worker(worker_id)
                # Reset circuit breaker on successful respawn
                if self._circuit_breaker is not None:
                    self._circuit_breaker.reset(worker_id)
            except Exception as e:
                logger.error(f"Failed to restart worker {worker_id}: {e}")
                # Clean up worktree if spawn failed
                if old_worktree:
                    try:
                        self.worktrees.delete(Path(old_worktree), force=True)
                    except Exception as cleanup_err:
                        logger.warning(f"Failed to clean up worktree: {cleanup_err}")

    def respawn_workers_for_level(self, level: int) -> int:
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
            wid for wid, w in self._workers.items() if w.status not in (WorkerStatus.STOPPED, WorkerStatus.CRASHED)
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
            wid for wid, w in list(self._workers.items()) if w.status in (WorkerStatus.STOPPED, WorkerStatus.CRASHED)
        ]
        for wid in stopped_ids:
            del self._workers[wid]
            available_ids.append(wid)

        available_ids = sorted(set(available_ids))[:need]

        for worker_id in available_ids:
            try:
                self.spawn_worker(worker_id)
                spawned += 1
            except Exception as e:
                logger.error(f"Failed to respawn worker {worker_id}: {e}")

        if spawned > 0:
            # Wait for new workers to initialize
            self.wait_for_initialization(timeout=300)

        return spawned

    @property
    def running(self) -> bool:
        """Whether orchestration is currently running.

        Set by the Orchestrator to control respawn behavior in
        handle_worker_exit.
        """
        return self._running

    @running.setter
    def running(self, value: bool) -> None:
        self._running = value

    def _get_remaining_tasks_for_level(self, level: int) -> list[str]:
        """Get remaining tasks for a level.

        Args:
            level: Level number

        Returns:
            List of incomplete task IDs
        """
        pending = self.levels.get_pending_tasks_for_level(level)
        return pending
