"""State persistence and management for ZERG."""

import asyncio
import contextlib
import fcntl
import json
import tempfile
import threading
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from zerg.constants import GSD_DIR, STATE_DIR, LevelMergeStatus, TaskStatus, WorkerStatus
from zerg.exceptions import StateError
from zerg.logging import get_logger
from zerg.types import ExecutionEvent, WorkerState

if TYPE_CHECKING:
    from zerg.dependency_checker import DependencyChecker
    from zerg.types import FeatureMetrics

logger = get_logger("state")


class StateManager:
    """Manage ZERG execution state with file-based persistence.

    Uses fcntl.flock for cross-process file locking to prevent race conditions
    when multiple container workers share the same state file via bind mounts.
    """

    def __init__(self, feature: str, state_dir: str | Path | None = None) -> None:
        """Initialize state manager.

        Args:
            feature: Feature name for state isolation
            state_dir: Directory for state files (defaults to .zerg/state)
        """
        self.feature = feature
        self.state_dir = Path(state_dir or STATE_DIR)
        self._state_file = self.state_dir / f"{feature}.json"
        self._lock = threading.RLock()  # In-process thread safety
        self._file_lock_depth = 0  # Reentrant counter for cross-process file lock
        self._state: dict[str, Any] = {}
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Ensure state directory exists."""
        self.state_dir.mkdir(parents=True, exist_ok=True)

    @contextlib.contextmanager
    def _atomic_update(self) -> Iterator[None]:
        """Cross-process atomic read-modify-write.

        Acquires an exclusive file lock, reloads state from disk,
        yields for caller to mutate self._state, then saves to disk
        and releases the lock.

        Supports reentrant calls (nested _atomic_update contexts skip
        reload/save -- the outermost context handles both).

        The in-process RLock (self._lock) is held for the entire duration
        including the yield, so threads sharing this StateManager instance
        are fully serialized. The RLock is reentrant, so nested calls from
        the same thread (e.g. claim_task -> set_task_status) work correctly.
        """
        with self._lock:
            if self._file_lock_depth > 0:
                # Already holding file lock (nested/reentrant call)
                self._file_lock_depth += 1
                try:
                    yield
                finally:
                    self._file_lock_depth -= 1
                return

            lock_path = self._state_file.with_suffix(".lock")
            lock_fd = open(lock_path, "w")  # noqa: SIM115
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
                self._file_lock_depth = 1

                # Reload latest state from disk under lock
                if self._state_file.exists():
                    try:
                        with open(self._state_file) as f:
                            self._state = json.load(f)
                    except json.JSONDecodeError:
                        if not self._state:
                            self._state = self._create_initial_state()
                elif not self._state:
                    self._state = self._create_initial_state()

                yield

                # Save to disk under lock
                self._raw_save()
            finally:
                self._file_lock_depth = 0
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                except Exception as e:
                    logger.debug(f"Lock release failed: {e}")
                lock_fd.close()

    def _raw_save(self) -> None:
        """Write state to disk. Called under _atomic_update file lock."""
        with self._lock:
            # Create backup if file already exists
            if self._state_file.exists():
                backup_path = self._state_file.with_suffix(".json.bak")
                existing_content = self._state_file.read_text()
                backup_path.write_text(existing_content)

            # Atomic write: write to temp file, then rename
            temp_fd, temp_path = tempfile.mkstemp(
                suffix=".tmp",
                prefix=f"{self.feature}_",
                dir=self.state_dir,
            )
            temp_file = Path(temp_path)
            try:
                with open(temp_fd, "w") as f:
                    json.dump(self._state, f, indent=2, default=str)
                # Atomic rename (on POSIX systems)
                temp_file.replace(self._state_file)
            except Exception:
                # Clean up temp file on failure
                if temp_file.exists():
                    temp_file.unlink()
                raise

            logger.debug(f"Saved state for feature {self.feature}")

    def load(self) -> dict[str, Any]:
        """Load state from file.

        Returns:
            State dictionary
        """
        # Use shared file lock to prevent reading during a write
        lock_path = self._state_file.with_suffix(".lock")
        lock_fd = open(lock_path, "w")  # noqa: SIM115
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_SH)
            with self._lock:
                if not self._state_file.exists():
                    self._state = self._create_initial_state()
                else:
                    try:
                        with open(self._state_file) as f:
                            self._state = json.load(f)
                    except json.JSONDecodeError as e:
                        raise StateError(f"Failed to parse state file: {e}") from e

                logger.debug(f"Loaded state for feature {self.feature}")
                return self._state.copy()
        finally:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except Exception as e:
                logger.debug(f"Lock release failed: {e}")
            lock_fd.close()

    def save(self) -> None:
        """Save state to file with cross-process locking.

        Public save method -- acquires file lock, writes, and releases.
        """
        lock_path = self._state_file.with_suffix(".lock")
        lock_fd = open(lock_path, "w")  # noqa: SIM115
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            self._raw_save()
        finally:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except Exception as e:
                logger.debug(f"Lock release failed: {e}")
            lock_fd.close()

    def inject_state(self, state_dict: dict[str, Any]) -> None:
        """Inject external state for read-only display (no disk write).

        Used by the dashboard to display state from Claude Code Tasks
        when the state JSON file has no task data.

        Args:
            state_dict: State dictionary to inject.
        """
        with self._lock:
            self._state = state_dict

    async def load_async(self) -> dict[str, Any]:
        """Async version of load() - wraps blocking file I/O in thread.

        Returns:
            State dictionary
        """
        return await asyncio.to_thread(self.load)

    async def save_async(self) -> None:
        """Async version of save() - wraps blocking file I/O in thread."""
        await asyncio.to_thread(self.save)

    def _create_initial_state(self) -> dict[str, Any]:
        """Create initial state structure.

        Returns:
            Initial state dictionary
        """
        return {
            "feature": self.feature,
            "started_at": datetime.now().isoformat(),
            "current_level": 0,
            "tasks": {},
            "workers": {},
            "levels": {},
            "execution_log": [],
            "metrics": None,
            "paused": False,
            "error": None,
        }

    def get_task_status(self, task_id: str) -> str | None:
        """Get the status of a task.

        Args:
            task_id: Task identifier

        Returns:
            Task status or None if not found
        """
        with self._lock:
            task_state = self._state.get("tasks", {}).get(task_id)
            return task_state.get("status") if task_state else None

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
        status_str = status.value if isinstance(status, TaskStatus) else status

        with self._atomic_update():
            if "tasks" not in self._state:
                self._state["tasks"] = {}

            if task_id not in self._state["tasks"]:
                self._state["tasks"][task_id] = {}

            task_state = self._state["tasks"][task_id]
            task_state["status"] = status_str
            task_state["updated_at"] = datetime.now().isoformat()

            if worker_id is not None:
                task_state["worker_id"] = worker_id
            if error:
                task_state["error"] = error
            if status_str == TaskStatus.COMPLETE.value:
                task_state["completed_at"] = datetime.now().isoformat()
            if status_str == TaskStatus.IN_PROGRESS.value:
                task_state["started_at"] = datetime.now().isoformat()

        logger.debug(f"Task {task_id} status: {status_str}")

    def get_worker_state(self, worker_id: int) -> WorkerState | None:
        """Get state of a worker.

        Args:
            worker_id: Worker identifier

        Returns:
            WorkerState or None if not found
        """
        with self._lock:
            worker_data = self._state.get("workers", {}).get(str(worker_id))
            if not worker_data:
                return None
            return WorkerState.from_dict(worker_data)

    def set_worker_state(self, worker_state: WorkerState) -> None:
        """Set state of a worker.

        Args:
            worker_state: Worker state to save
        """
        with self._atomic_update():
            if "workers" not in self._state:
                self._state["workers"] = {}

            self._state["workers"][str(worker_state.worker_id)] = worker_state.to_dict()

        logger.debug(f"Worker {worker_state.worker_id} state: {worker_state.status.value}")

    def get_all_workers(self) -> dict[int, WorkerState]:
        """Get all worker states.

        Returns:
            Dictionary of worker_id to WorkerState
        """
        with self._lock:
            workers = {}
            for wid_str, data in self._state.get("workers", {}).items():
                workers[int(wid_str)] = WorkerState.from_dict(data)
            return workers

    def claim_task(
        self,
        task_id: str,
        worker_id: int,
        current_level: int | None = None,
        dependency_checker: "DependencyChecker | None" = None,
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
        with self._atomic_update():
            task_state = self._state.get("tasks", {}).get(task_id, {})
            current_status = task_state.get("status", TaskStatus.PENDING.value)

            # Level enforcement: verify task is at expected level
            if current_level is not None:
                task_level = task_state.get("level")
                if task_level != current_level:
                    logger.warning(f"Level mismatch for {task_id}: expected L{current_level}, task is L{task_level}")
                    return False

            # Dependency enforcement: verify all dependencies are complete
            if dependency_checker is not None:
                incomplete = dependency_checker.get_incomplete_dependencies(task_id)
                if incomplete:
                    logger.warning(f"Cannot claim {task_id}: incomplete dependencies {incomplete}")
                    return False

            # Can only claim pending tasks
            if current_status not in (TaskStatus.TODO.value, TaskStatus.PENDING.value):
                return False

            # Check if already claimed by a different worker
            existing_worker = task_state.get("worker_id")
            if existing_worker is not None and existing_worker != worker_id:
                return False

            # Claim it (inline mutation -- _atomic_update is reentrant)
            self.set_task_status(task_id, TaskStatus.CLAIMED, worker_id=worker_id)
            self.record_task_claimed(task_id, worker_id)
            logger.info(f"Worker {worker_id} claimed task {task_id}")
            return True

    def release_task(self, task_id: str, worker_id: int) -> None:
        """Release a task claim.

        Args:
            task_id: Task to release
            worker_id: Worker releasing the task
        """
        with self._atomic_update():
            task_state = self._state.get("tasks", {}).get(task_id, {})

            # Only release if we own it
            if task_state.get("worker_id") != worker_id:
                return

            task_state["status"] = TaskStatus.PENDING.value
            task_state["worker_id"] = None

        logger.info(f"Worker {worker_id} released task {task_id}")

    def append_event(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Append an event to the execution log.

        Args:
            event_type: Type of event
            data: Event data
        """
        event: ExecutionEvent = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "data": data or {},
        }

        with self._atomic_update():
            if "execution_log" not in self._state:
                self._state["execution_log"] = []
            self._state["execution_log"].append(event)

        logger.debug(f"Event: {event_type}")

    def get_events(self, limit: int | None = None) -> list[ExecutionEvent]:
        """Get execution events.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of events (most recent last)
        """
        with self._lock:
            events = cast(list[ExecutionEvent], self._state.get("execution_log", []))
            if limit:
                return events[-limit:]
            return events.copy()

    def set_current_level(self, level: int) -> None:
        """Set the current execution level.

        Args:
            level: Level number
        """
        with self._atomic_update():
            self._state["current_level"] = level

    def get_current_level(self) -> int:
        """Get the current execution level.

        Returns:
            Current level number
        """
        with self._lock:
            return int(self._state.get("current_level", 0))

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
        with self._atomic_update():
            if "levels" not in self._state:
                self._state["levels"] = {}

            if str(level) not in self._state["levels"]:
                self._state["levels"][str(level)] = {}

            level_state = self._state["levels"][str(level)]
            level_state["status"] = status
            level_state["updated_at"] = datetime.now().isoformat()

            if merge_commit:
                level_state["merge_commit"] = merge_commit
            if status == "running":
                level_state["started_at"] = datetime.now().isoformat()
            if status == "complete":
                level_state["completed_at"] = datetime.now().isoformat()

    def get_level_status(self, level: int) -> dict[str, Any] | None:
        """Get status of a level.

        Args:
            level: Level number

        Returns:
            Level status dict or None
        """
        with self._lock:
            return cast(dict[str, Any] | None, self._state.get("levels", {}).get(str(level)))

    def get_tasks_by_status(self, status: TaskStatus | str) -> list[str]:
        """Get task IDs with a specific status.

        Args:
            status: Status to filter by

        Returns:
            List of task IDs
        """
        status_str = status.value if isinstance(status, TaskStatus) else status

        with self._lock:
            return [tid for tid, task in self._state.get("tasks", {}).items() if task.get("status") == status_str]

    def set_paused(self, paused: bool) -> None:
        """Set paused state.

        Args:
            paused: Whether execution is paused
        """
        with self._atomic_update():
            self._state["paused"] = paused

    def is_paused(self) -> bool:
        """Check if execution is paused.

        Returns:
            True if paused
        """
        with self._lock:
            return bool(self._state.get("paused", False))

    def set_error(self, error: str | None) -> None:
        """Set error state.

        Args:
            error: Error message or None to clear
        """
        with self._atomic_update():
            self._state["error"] = error

    def get_error(self) -> str | None:
        """Get current error.

        Returns:
            Error message or None
        """
        with self._lock:
            return cast(str | None, self._state.get("error"))

    def delete(self) -> None:
        """Delete state file."""
        if self._state_file.exists():
            self._state_file.unlink()
            logger.info(f"Deleted state for feature {self.feature}")

    def exists(self) -> bool:
        """Check if state file exists.

        Returns:
            True if state file exists
        """
        return self._state_file.exists()

    # === Merge Status Tracking ===

    def get_level_merge_status(self, level: int) -> LevelMergeStatus | None:
        """Get the merge status for a level.

        Args:
            level: Level number

        Returns:
            LevelMergeStatus or None if not set
        """
        with self._lock:
            level_data = self._state.get("levels", {}).get(str(level), {})
            merge_status = level_data.get("merge_status")
            if merge_status:
                return LevelMergeStatus(merge_status)
            return None

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
        with self._atomic_update():
            if "levels" not in self._state:
                self._state["levels"] = {}

            if str(level) not in self._state["levels"]:
                self._state["levels"][str(level)] = {}

            level_state = self._state["levels"][str(level)]
            level_state["merge_status"] = merge_status.value
            level_state["merge_updated_at"] = datetime.now().isoformat()

            if details:
                level_state["merge_details"] = details

            if merge_status == LevelMergeStatus.COMPLETE:
                level_state["merge_completed_at"] = datetime.now().isoformat()

        logger.debug(f"Level {level} merge status: {merge_status.value}")

    # === Retry Tracking ===

    def get_task_retry_count(self, task_id: str) -> int:
        """Get the retry count for a task.

        Args:
            task_id: Task identifier

        Returns:
            Number of retries (0 if never retried)
        """
        with self._lock:
            task_state = self._state.get("tasks", {}).get(task_id, {})
            return int(task_state.get("retry_count", 0))

    def increment_task_retry(self, task_id: str, next_retry_at: str | None = None) -> int:
        """Increment and return the retry count for a task.

        Args:
            task_id: Task identifier
            next_retry_at: Optional ISO timestamp for when retry becomes eligible

        Returns:
            New retry count
        """
        with self._atomic_update():
            if "tasks" not in self._state:
                self._state["tasks"] = {}

            if task_id not in self._state["tasks"]:
                self._state["tasks"][task_id] = {}

            task_state = self._state["tasks"][task_id]
            retry_count: int = int(task_state.get("retry_count", 0)) + 1
            task_state["retry_count"] = retry_count
            task_state["last_retry_at"] = datetime.now().isoformat()

            if next_retry_at:
                task_state["next_retry_at"] = next_retry_at

        logger.debug(f"Task {task_id} retry count: {retry_count}")
        return retry_count

    def set_task_retry_schedule(self, task_id: str, next_retry_at: str) -> None:
        """Set the next retry timestamp for a task.

        Args:
            task_id: Task identifier
            next_retry_at: ISO timestamp for when retry becomes eligible
        """
        with self._atomic_update():
            if "tasks" not in self._state:
                self._state["tasks"] = {}

            if task_id not in self._state["tasks"]:
                self._state["tasks"][task_id] = {}

            self._state["tasks"][task_id]["next_retry_at"] = next_retry_at

        logger.debug(f"Task {task_id} next retry at: {next_retry_at}")

    def get_task_retry_schedule(self, task_id: str) -> str | None:
        """Get the next retry timestamp for a task.

        Args:
            task_id: Task identifier

        Returns:
            ISO timestamp string or None if not scheduled
        """
        with self._lock:
            task_state = self._state.get("tasks", {}).get(task_id, {})
            return cast(str | None, task_state.get("next_retry_at"))

    def get_tasks_ready_for_retry(self) -> list[str]:
        """Get task IDs whose scheduled retry time has passed.

        Returns:
            List of task IDs ready for retry
        """
        now = datetime.now().isoformat()
        with self._lock:
            ready = []
            for task_id, task_state in self._state.get("tasks", {}).items():
                next_retry = task_state.get("next_retry_at")
                if next_retry and next_retry <= now:
                    # Only include tasks that are still in a retryable state
                    status = task_state.get("status")
                    if status in (TaskStatus.FAILED.value, "waiting_retry"):
                        ready.append(task_id)
            return ready

    def reset_task_retry(self, task_id: str) -> None:
        """Reset the retry count for a task.

        Args:
            task_id: Task identifier
        """
        with self._atomic_update():
            if task_id in self._state.get("tasks", {}):
                self._state["tasks"][task_id]["retry_count"] = 0
                self._state["tasks"][task_id].pop("last_retry_at", None)

        logger.debug(f"Task {task_id} retry count reset")

    def get_stale_in_progress_tasks(self, timeout_seconds: int) -> list[dict[str, Any]]:
        """Get tasks that have been in_progress longer than the timeout.

        Args:
            timeout_seconds: Maximum seconds a task can be in_progress before
                considered stale

        Returns:
            List of dicts with task_id, worker_id, started_at, elapsed_seconds
        """
        cutoff = datetime.now() - timedelta(seconds=timeout_seconds)
        cutoff_iso = cutoff.isoformat()

        with self._lock:
            stale = []
            for task_id, task_state in self._state.get("tasks", {}).items():
                status = task_state.get("status")
                if status != TaskStatus.IN_PROGRESS.value:
                    continue

                started_at = task_state.get("started_at")
                if not started_at:
                    continue

                if started_at <= cutoff_iso:
                    started_dt = datetime.fromisoformat(started_at)
                    elapsed = (datetime.now() - started_dt).total_seconds()
                    stale.append(
                        {
                            "task_id": task_id,
                            "worker_id": task_state.get("worker_id"),
                            "started_at": started_at,
                            "elapsed_seconds": round(elapsed),
                        }
                    )
            return stale

    def get_failed_tasks(self) -> list[dict[str, Any]]:
        """Get all failed tasks with their retry information.

        Returns:
            List of failed task info dictionaries
        """
        with self._lock:
            failed = []
            for task_id, task_state in self._state.get("tasks", {}).items():
                if task_state.get("status") == TaskStatus.FAILED.value:
                    failed.append(
                        {
                            "task_id": task_id,
                            "retry_count": task_state.get("retry_count", 0),
                            "error": task_state.get("error"),
                            "last_retry_at": task_state.get("last_retry_at"),
                        }
                    )
            return failed

    # === Worker Ready Status ===

    def set_worker_ready(self, worker_id: int) -> None:
        """Mark a worker as ready to receive tasks.

        Args:
            worker_id: Worker identifier
        """
        with self._atomic_update():
            worker_data = self._state.get("workers", {}).get(str(worker_id), {})
            if worker_data:
                worker_data["status"] = WorkerStatus.READY.value
                worker_data["ready_at"] = datetime.now().isoformat()

        logger.debug(f"Worker {worker_id} marked ready")

    # === Metrics Methods ===

    def record_task_claimed(self, task_id: str, worker_id: int) -> None:
        """Record when a task was claimed by a worker.

        Sets the claimed_at timestamp for task metrics tracking.

        Args:
            task_id: Task identifier
            worker_id: Worker that claimed the task
        """
        with self._atomic_update():
            if "tasks" not in self._state:
                self._state["tasks"] = {}

            if task_id not in self._state["tasks"]:
                self._state["tasks"][task_id] = {}

            self._state["tasks"][task_id]["claimed_at"] = datetime.now().isoformat()
            self._state["tasks"][task_id]["worker_id"] = worker_id

        logger.debug(f"Task {task_id} claimed by worker {worker_id}")

    def record_task_duration(self, task_id: str, duration_ms: int) -> None:
        """Record task execution duration.

        Args:
            task_id: Task identifier
            duration_ms: Execution duration in milliseconds
        """
        with self._atomic_update():
            if task_id in self._state.get("tasks", {}):
                self._state["tasks"][task_id]["duration_ms"] = duration_ms

        logger.debug(f"Task {task_id} duration: {duration_ms}ms")

    def store_metrics(self, metrics: "FeatureMetrics") -> None:
        """Store computed metrics to state.

        Args:
            metrics: FeatureMetrics to persist
        """
        with self._atomic_update():
            self._state["metrics"] = metrics.to_dict()

        logger.debug("Stored feature metrics")

    def get_metrics(self) -> "FeatureMetrics | None":
        """Retrieve stored metrics.

        Returns:
            FeatureMetrics if available, None otherwise
        """
        with self._lock:
            metrics_data = self._state.get("metrics")
            if not metrics_data:
                return None

            # Import here to avoid circular import
            from zerg.types import FeatureMetrics

            return FeatureMetrics.from_dict(metrics_data)

    def get_ready_workers(self) -> list[int]:
        """Get list of workers in ready state.

        Returns:
            List of ready worker IDs
        """
        with self._lock:
            ready = []
            for wid_str, worker_data in self._state.get("workers", {}).items():
                if worker_data.get("status") == WorkerStatus.READY.value:
                    ready.append(int(wid_str))
            return ready

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
        import time

        start = time.time()
        while time.time() - start < timeout:
            self.load()  # Refresh state
            ready = self.get_ready_workers()
            if all(wid in ready for wid in worker_ids):
                return True
            time.sleep(0.5)
        return False

    # === STATE.md Generation ===

    def generate_state_md(self, gsd_dir: str | Path | None = None) -> Path:
        """Generate a human-readable STATE.md file from current state.

        Creates a markdown file in the GSD directory summarizing the current
        execution state, task progress, and any decisions or blockers.

        Args:
            gsd_dir: GSD directory path (defaults to .gsd)

        Returns:
            Path to generated STATE.md file
        """
        gsd_path = Path(gsd_dir or GSD_DIR)
        gsd_path.mkdir(parents=True, exist_ok=True)
        state_md_path = gsd_path / "STATE.md"

        with self._lock:
            lines = self._build_state_md_content()

        state_md_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"Generated STATE.md at {state_md_path}")
        return state_md_path

    def _build_state_md_content(self) -> list[str]:
        """Build the content lines for STATE.md.

        Returns:
            List of markdown lines
        """
        lines = []
        now = datetime.now().isoformat()

        # Header
        lines.append(f"# ZERG State: {self.feature}")
        lines.append("")

        # Current phase info
        current_level = self._state.get("current_level", 0)
        started_at = self._state.get("started_at", "unknown")
        is_paused = self._state.get("paused", False)
        error = self._state.get("error")

        lines.append("## Current Phase")
        lines.append(f"- **Level:** {current_level}")
        lines.append(f"- **Started:** {started_at}")
        lines.append(f"- **Last Update:** {now}")
        if is_paused:
            lines.append("- **Status:** PAUSED")
        if error:
            lines.append(f"- **Error:** {error}")
        lines.append("")

        # Task progress table
        lines.append("## Tasks")
        lines.append("")
        lines.append("| ID | Status | Worker | Updated |")
        lines.append("|----|--------|--------|---------|")

        tasks = self._state.get("tasks", {})
        for task_id, task_state in sorted(tasks.items()):
            status = task_state.get("status", "unknown")
            worker = task_state.get("worker_id", "-")
            updated = task_state.get("updated_at", "-")
            # Truncate timestamp for display
            if isinstance(updated, str) and "T" in updated:
                updated = updated.split("T")[1][:8]
            lines.append(f"| {task_id} | {status} | {worker} | {updated} |")

        lines.append("")

        # Workers section
        workers = self._state.get("workers", {})
        if workers:
            lines.append("## Workers")
            lines.append("")
            lines.append("| ID | Status | Tasks Done | Branch |")
            lines.append("|----|--------|------------|--------|")
            for wid, worker_data in sorted(workers.items(), key=lambda x: int(x[0])):
                status = worker_data.get("status", "unknown")
                tasks_done = worker_data.get("tasks_completed", 0)
                branch = worker_data.get("branch", "-")
                # Truncate branch name
                if len(branch) > 30:
                    branch = "..." + branch[-27:]
                lines.append(f"| {wid} | {status} | {tasks_done} | {branch} |")
            lines.append("")

        # Levels section
        levels = self._state.get("levels", {})
        if levels:
            lines.append("## Levels")
            lines.append("")
            for level, level_data in sorted(levels.items(), key=lambda x: int(x[0])):
                status = level_data.get("status", "pending")
                merge_status = level_data.get("merge_status", "-")
                lines.append(f"- **Level {level}:** {status}")
                if merge_status != "-":
                    lines.append(f"  - Merge: {merge_status}")
                if merge_commit := level_data.get("merge_commit"):
                    lines.append(f"  - Commit: {merge_commit[:8]}")
            lines.append("")

        # Failed tasks details
        failed = self.get_failed_tasks()
        if failed:
            lines.append("## Blockers")
            lines.append("")
            for task_info in failed:
                task_id = task_info["task_id"]
                error_msg = task_info.get("error", "Unknown error")
                retry_count = task_info.get("retry_count", 0)
                lines.append(f"- **{task_id}** (retries: {retry_count})")
                lines.append(f"  - {error_msg}")
            lines.append("")

        # Recent events
        events = self._state.get("execution_log", [])[-10:]  # Last 10 events
        if events:
            lines.append("## Recent Events")
            lines.append("")
            for event in reversed(events):
                timestamp = event.get("timestamp", "")
                if isinstance(timestamp, str) and "T" in timestamp:
                    timestamp = timestamp.split("T")[1][:8]
                event_type = event.get("event", "unknown")
                lines.append(f"- `{timestamp}` {event_type}")
            lines.append("")

        return lines
