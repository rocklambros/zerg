"""StateManager facade — thin delegation layer preserving the original public API.

Instantiates the specialized submodules (PersistenceLayer, TaskStateRepo,
RetryRepo, WorkerStateRepo, LevelStateRepo, ExecutionLog, MetricsStore,
StateRenderer) and delegates every public method of the original StateManager
to the appropriate submodule. Callers see the same interface they always have.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from zerg.state.execution import ExecutionLog
from zerg.state.level_repo import LevelStateRepo
from zerg.state.metrics_store import MetricsStore
from zerg.state.persistence import PersistenceLayer
from zerg.state.renderer import StateRenderer
from zerg.state.retry_repo import RetryRepo
from zerg.state.task_repo import TaskStateRepo
from zerg.state.worker_repo import WorkerStateRepo

if TYPE_CHECKING:
    from zerg.constants import LevelMergeStatus, TaskStatus
    from zerg.dependency_checker import DependencyChecker
    from zerg.types import ExecutionEvent, FeatureMetrics, WorkerState


class StateManager:
    """Manage ZERG execution state with file-based persistence.

    Thin facade that delegates to specialized submodules while preserving
    the exact public API of the original monolithic StateManager.

    Uses fcntl.flock for cross-process file locking to prevent race conditions
    when multiple container workers share the same state file via bind mounts.
    """

    def __init__(self, feature: str, state_dir: str | Path | None = None) -> None:
        """Initialize state manager.

        Args:
            feature: Feature name for state isolation
            state_dir: Directory for state files (defaults to .zerg/state)
        """
        # Core persistence layer (file I/O, locking, serialization)
        self._persistence = PersistenceLayer(feature, state_dir)

        # Specialized repositories
        self._tasks = TaskStateRepo(self._persistence)
        self._retries = RetryRepo(self._persistence)
        self._workers = WorkerStateRepo(self._persistence)
        self._levels = LevelStateRepo(self._persistence)
        self._execution = ExecutionLog(self._persistence)
        self._metrics = MetricsStore(self._persistence)
        self._renderer = StateRenderer(self._persistence)

    # === Properties delegated to PersistenceLayer ===

    @property
    def _state(self) -> dict[str, Any]:
        """Access the in-memory state dict (backward compat for direct access)."""
        return self._persistence.state

    @_state.setter
    def _state(self, value: dict[str, Any]) -> None:
        """Set the in-memory state dict (backward compat)."""
        self._persistence.state = value

    @property
    def feature(self) -> str:
        """Feature name for state isolation."""
        return self._persistence.feature

    @property
    def state_dir(self) -> Path:
        """Directory for state files."""
        return self._persistence.state_dir

    # === Persistence methods ===

    def load(self) -> dict[str, Any]:
        """Load state from file.

        Returns:
            State dictionary
        """
        return self._persistence.load()

    def save(self) -> None:
        """Save state to file with cross-process locking."""
        self._persistence.save()

    def inject_state(self, state_dict: dict[str, Any]) -> None:
        """Inject external state for read-only display (no disk write).

        Used by the dashboard to display state from Claude Code Tasks
        when the state JSON file has no task data.

        Args:
            state_dict: State dictionary to inject.
        """
        self._persistence.inject_state(state_dict)

    async def load_async(self) -> dict[str, Any]:
        """Async version of load() - wraps blocking file I/O in thread.

        Returns:
            State dictionary
        """
        return await self._persistence.load_async()

    async def save_async(self) -> None:
        """Async version of save() - wraps blocking file I/O in thread."""
        await self._persistence.save_async()

    def delete(self) -> None:
        """Delete state file."""
        self._persistence.delete()

    def exists(self) -> bool:
        """Check if state file exists.

        Returns:
            True if state file exists
        """
        return self._persistence.exists()

    # === Task methods (delegated to TaskStateRepo) ===

    def get_task_status(self, task_id: str) -> str | None:
        """Get the status of a task.

        Args:
            task_id: Task identifier

        Returns:
            Task status or None if not found
        """
        return self._tasks.get_task_status(task_id)

    def set_task_status(
        self,
        task_id: str,
        status: TaskStatus | str,
        worker_id: int | None = None,
        error: str | None = None,
    ) -> None:
        """Set the status of a task.

        Args:
            task_id: Task identifier
            status: New status
            worker_id: Worker ID (if assigned)
            error: Error message (if failed)
        """
        self._tasks.set_task_status(task_id, status, worker_id=worker_id, error=error)

    def claim_task(
        self,
        task_id: str,
        worker_id: int,
        current_level: int | None = None,
        dependency_checker: DependencyChecker | None = None,
    ) -> bool:
        """Attempt to claim a task for a worker.

        Uses cross-process file locking to prevent race conditions.

        Args:
            task_id: Task to claim
            worker_id: Worker claiming the task
            current_level: If provided, verify task is at this level
            dependency_checker: If provided, verify all dependencies are complete

        Returns:
            True if claim succeeded
        """
        return self._tasks.claim_task(
            task_id, worker_id, current_level=current_level, dependency_checker=dependency_checker
        )

    def release_task(self, task_id: str, worker_id: int) -> None:
        """Release a task claim.

        Args:
            task_id: Task to release
            worker_id: Worker releasing the task
        """
        self._tasks.release_task(task_id, worker_id)

    def get_tasks_by_status(self, status: TaskStatus | str) -> list[str]:
        """Get task IDs with a specific status.

        Args:
            status: Status to filter by

        Returns:
            List of task IDs
        """
        return self._tasks.get_tasks_by_status(status)

    def get_failed_tasks(self) -> list[dict[str, Any]]:
        """Get all failed tasks with their retry information.

        Returns:
            List of failed task info dictionaries
        """
        return self._tasks.get_failed_tasks()

    def get_stale_in_progress_tasks(self, timeout_seconds: int) -> list[dict[str, Any]]:
        """Get tasks that have been in_progress longer than the timeout.

        Args:
            timeout_seconds: Maximum seconds a task can be in_progress before
                considered stale

        Returns:
            List of dicts with task_id, worker_id, started_at, elapsed_seconds
        """
        return self._tasks.get_stale_in_progress_tasks(timeout_seconds)

    def record_task_claimed(self, task_id: str, worker_id: int) -> None:
        """Record when a task was claimed by a worker.

        Sets the claimed_at timestamp for task metrics tracking.

        Args:
            task_id: Task identifier
            worker_id: Worker that claimed the task
        """
        self._tasks.record_task_claimed(task_id, worker_id)

    # === Retry methods (delegated to RetryRepo) ===

    def get_task_retry_count(self, task_id: str) -> int:
        """Get the retry count for a task.

        Args:
            task_id: Task identifier

        Returns:
            Number of retries (0 if never retried)
        """
        return self._retries.get_retry_count(task_id)

    def increment_task_retry(self, task_id: str, next_retry_at: str | None = None) -> int:
        """Increment and return the retry count for a task.

        Args:
            task_id: Task identifier
            next_retry_at: Optional ISO timestamp for when retry becomes eligible

        Returns:
            New retry count
        """
        return self._retries.increment_retry(task_id, next_retry_at=next_retry_at)

    def set_task_retry_schedule(self, task_id: str, next_retry_at: str) -> None:
        """Set the next retry timestamp for a task.

        Args:
            task_id: Task identifier
            next_retry_at: ISO timestamp for when retry becomes eligible
        """
        self._retries.set_retry_schedule(task_id, next_retry_at)

    def get_task_retry_schedule(self, task_id: str) -> str | None:
        """Get the next retry timestamp for a task.

        Args:
            task_id: Task identifier

        Returns:
            ISO timestamp string or None if not scheduled
        """
        return self._retries.get_retry_schedule(task_id)

    def get_tasks_ready_for_retry(self) -> list[str]:
        """Get task IDs whose scheduled retry time has passed.

        Returns:
            List of task IDs ready for retry
        """
        return self._retries.get_tasks_ready_for_retry()

    def reset_task_retry(self, task_id: str) -> None:
        """Reset the retry count for a task.

        Args:
            task_id: Task identifier
        """
        self._retries.reset_retries(task_id)

    # === Worker methods (delegated to WorkerStateRepo) ===

    def get_worker_state(self, worker_id: int) -> WorkerState | None:
        """Get state of a worker.

        Args:
            worker_id: Worker identifier

        Returns:
            WorkerState or None if not found
        """
        return self._workers.get_worker_state(worker_id)

    def set_worker_state(self, worker_state: WorkerState) -> None:
        """Set state of a worker.

        Args:
            worker_state: Worker state to save
        """
        self._workers.set_worker_state(worker_state)

    def get_all_workers(self) -> dict[int, WorkerState]:
        """Get all worker states.

        Returns:
            Dictionary of worker_id to WorkerState
        """
        return self._workers.get_all_workers()

    def set_worker_ready(self, worker_id: int) -> None:
        """Mark a worker as ready to receive tasks.

        Args:
            worker_id: Worker identifier
        """
        self._workers.set_worker_ready(worker_id)

    def get_ready_workers(self) -> list[int]:
        """Get list of workers in ready state.

        Returns:
            List of ready worker IDs
        """
        return self._workers.get_ready_workers()

    def wait_for_workers_ready(self, worker_ids: list[int], timeout: float = 60.0) -> bool:
        """Wait for specified workers to become ready.

        Note: This is a polling implementation. For production, consider
        using proper synchronization.

        Args:
            worker_ids: Workers to wait for
            timeout: Maximum wait time in seconds

        Returns:
            True if all workers became ready before timeout
        """
        return self._workers.wait_for_workers_ready(worker_ids, timeout=timeout)

    # === Level methods (delegated to LevelStateRepo) ===

    def set_current_level(self, level: int) -> None:
        """Set the current execution level.

        Args:
            level: Level number
        """
        self._levels.set_current_level(level)

    def get_current_level(self) -> int:
        """Get the current execution level.

        Returns:
            Current level number
        """
        return self._levels.get_current_level()

    def set_level_status(
        self,
        level: int,
        status: str,
        merge_commit: str | None = None,
    ) -> None:
        """Set status of a level.

        Args:
            level: Level number
            status: Level status
            merge_commit: Merge commit SHA (if merged)
        """
        self._levels.set_level_status(level, status, merge_commit=merge_commit)

    def get_level_status(self, level: int) -> dict[str, Any] | None:
        """Get status of a level.

        Args:
            level: Level number

        Returns:
            Level status dict or None
        """
        return self._levels.get_level_status(level)

    def get_level_merge_status(self, level: int) -> LevelMergeStatus | None:
        """Get the merge status for a level.

        Args:
            level: Level number

        Returns:
            LevelMergeStatus or None if not set
        """
        return self._levels.get_level_merge_status(level)

    def set_level_merge_status(
        self,
        level: int,
        merge_status: LevelMergeStatus,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Set the merge status for a level.

        Args:
            level: Level number
            merge_status: New merge status
            details: Additional details (conflicting files, etc.)
        """
        self._levels.set_level_merge_status(level, merge_status, details=details)

    # === Execution log methods (delegated to ExecutionLog) ===

    def append_event(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Append an event to the execution log.

        Args:
            event_type: Type of event
            data: Event data
        """
        self._execution.append_event(event_type, data=data)

    def get_events(self, limit: int | None = None) -> list[ExecutionEvent]:
        """Get execution events.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of events (most recent last)
        """
        return self._execution.get_events(limit=limit)

    def set_paused(self, paused: bool) -> None:
        """Set paused state.

        Args:
            paused: Whether execution is paused
        """
        self._execution.set_paused(paused)

    def is_paused(self) -> bool:
        """Check if execution is paused.

        Returns:
            True if paused
        """
        return self._execution.is_paused()

    def set_error(self, error: str | None) -> None:
        """Set error state.

        Args:
            error: Error message or None to clear
        """
        self._execution.set_error(error)

    def get_error(self) -> str | None:
        """Get current error.

        Returns:
            Error message or None
        """
        return self._execution.get_error()

    # === Metrics methods (delegated to MetricsStore) ===

    def record_task_duration(self, task_id: str, duration_ms: int) -> None:
        """Record task execution duration.

        Args:
            task_id: Task identifier
            duration_ms: Execution duration in milliseconds
        """
        self._metrics.record_task_duration(task_id, duration_ms)

    def store_metrics(self, metrics: FeatureMetrics) -> None:
        """Store computed metrics to state.

        Args:
            metrics: FeatureMetrics to persist
        """
        self._metrics.store_metrics(metrics)

    def get_metrics(self) -> FeatureMetrics | None:
        """Retrieve stored metrics.

        Returns:
            FeatureMetrics if available, None otherwise
        """
        return self._metrics.get_metrics()

    # === Rendering methods (delegated to StateRenderer) ===

    def generate_state_md(self, gsd_dir: str | Path | None = None) -> Path:
        """Generate a human-readable STATE.md file from current state.

        Creates a markdown file in the GSD directory summarizing the current
        execution state, task progress, and any decisions or blockers.

        Args:
            gsd_dir: GSD directory path (defaults to .gsd)

        Returns:
            Path to generated STATE.md file
        """
        return self._renderer.generate_state_md(gsd_dir=gsd_dir)
