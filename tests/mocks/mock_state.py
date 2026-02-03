"""Mock StateManager for testing state.py functionality.

Provides MockStateManager for testing state persistence, worker state,
task state, level state, and event tracking with configurable behaviors.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zerg.constants import LevelMergeStatus, TaskStatus, WorkerStatus
from zerg.types import ExecutionEvent, WorkerState

if TYPE_CHECKING:
    from zerg.types import FeatureMetrics


@dataclass
class StateEvent:
    """Record of a state change event."""

    event_type: str
    timestamp: datetime = field(default_factory=datetime.now)
    details: dict = field(default_factory=dict)


class MockStateManager:
    """Mock StateManager with configurable state simulation.

    Simulates state management operations with configurable behaviors
    for testing state persistence, worker tracking, task tracking,
    level management, and event history.

    Example:
        state_mgr = MockStateManager("test-feature")
        state_mgr.configure(
            fail_on_save=True,  # Simulate save failures
            corrupt_on_load=True,  # Simulate corrupt state file
        )

        # Test worker state
        worker = WorkerState(worker_id=1, status=WorkerStatus.RUNNING)
        state_mgr.set_worker_state(worker)
        retrieved = state_mgr.get_worker_state(1)
        assert retrieved.status == WorkerStatus.RUNNING

        # Test task state
        state_mgr.set_task_status("TASK-001", TaskStatus.IN_PROGRESS, worker_id=1)
        status = state_mgr.get_task_status("TASK-001")
        assert status == TaskStatus.IN_PROGRESS.value
    """

    def __init__(
        self,
        feature: str,
        state_dir: str | Path | None = None,
    ) -> None:
        """Initialize mock state manager.

        Args:
            feature: Feature name for state isolation
            state_dir: Directory for state files (ignored in mock)
        """
        self.feature = feature
        self.state_dir = Path(state_dir or ".zerg/state")
        self._state_file = self.state_dir / f"{feature}.json"

        # Internal state storage
        self._state: dict[str, Any] = self._create_initial_state()
        self._mock_events: list[StateEvent] = []  # Renamed to avoid conflict

        # Configurable behavior
        self._fail_on_save: bool = False
        self._fail_on_load: bool = False
        self._corrupt_on_load: bool = False
        self._save_delay: float = 0.0
        self._load_delay: float = 0.0
        self._fail_on_worker_id: int | None = None
        self._fail_on_task_id: str | None = None
        self._max_events: int = 1000
        self._file_exists: bool = False

        # Tracking for verification
        self._save_count: int = 0
        self._load_count: int = 0
        self._last_save_time: datetime | None = None
        self._last_load_time: datetime | None = None

    def configure(
        self,
        fail_on_save: bool = False,
        fail_on_load: bool = False,
        corrupt_on_load: bool = False,
        save_delay: float = 0.0,
        load_delay: float = 0.0,
        fail_on_worker_id: int | None = None,
        fail_on_task_id: str | None = None,
        max_events: int = 1000,
        file_exists: bool = True,
    ) -> MockStateManager:
        """Configure mock behavior.

        Args:
            fail_on_save: Raise exception on save
            fail_on_load: Raise exception on load
            corrupt_on_load: Return corrupt/invalid state on load
            save_delay: Simulated save delay in seconds
            load_delay: Simulated load delay in seconds
            fail_on_worker_id: Worker ID that triggers failures
            fail_on_task_id: Task ID that triggers failures
            max_events: Maximum events to track before truncation
            file_exists: Simulate whether state file exists

        Returns:
            Self for chaining
        """
        self._fail_on_save = fail_on_save
        self._fail_on_load = fail_on_load
        self._corrupt_on_load = corrupt_on_load
        self._save_delay = save_delay
        self._load_delay = load_delay
        self._fail_on_worker_id = fail_on_worker_id
        self._fail_on_task_id = fail_on_task_id
        self._max_events = max_events
        self._file_exists = file_exists
        return self

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

    # === Load/Save Methods ===

    def load(self) -> dict[str, Any]:
        """Load state from file.

        Returns:
            State dictionary

        Raises:
            Exception: If fail_on_load or corrupt_on_load is configured
        """
        if self._load_delay > 0:
            time.sleep(self._load_delay)

        if self._fail_on_load:
            from zerg.exceptions import StateError

            raise StateError("Simulated load failure")

        if self._corrupt_on_load:
            from zerg.exceptions import StateError

            raise StateError("Failed to parse state file: Simulated corruption")

        self._load_count += 1
        self._last_load_time = datetime.now()

        if not self._file_exists:
            self._state = self._create_initial_state()

        self._record_mock_event(
            "state_loaded",
            {
                "path": str(self._state_file),
                "load_count": self._load_count,
            },
        )

        return self._state.copy()

    def save(self) -> None:
        """Save state to file.

        Raises:
            IOError: If fail_on_save is configured
        """
        if self._save_delay > 0:
            time.sleep(self._save_delay)

        if self._fail_on_save:
            raise OSError("Simulated save failure")

        self._save_count += 1
        self._last_save_time = datetime.now()
        self._file_exists = True

        self._record_mock_event(
            "state_saved",
            {
                "path": str(self._state_file),
                "save_count": self._save_count,
            },
        )

    # === Task State Methods ===

    def get_task_status(self, task_id: str) -> str | None:
        """Get the status of a task.

        Args:
            task_id: Task identifier

        Returns:
            Task status or None if not found

        Raises:
            ValueError: If task_id matches fail_on_task_id
        """
        if task_id == self._fail_on_task_id:
            raise ValueError(f"Simulated failure for task: {task_id}")

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

        Raises:
            ValueError: If task_id matches fail_on_task_id
        """
        if task_id == self._fail_on_task_id:
            raise ValueError(f"Simulated failure for task: {task_id}")

        status_str = status.value if isinstance(status, TaskStatus) else status

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

        self.save()

        self._record_mock_event(
            "task_status_changed",
            {
                "task_id": task_id,
                "status": status_str,
                "worker_id": worker_id,
            },
        )

    def get_tasks_by_status(self, status: TaskStatus | str) -> list[str]:
        """Get task IDs with a specific status.

        Args:
            status: Status to filter by

        Returns:
            List of task IDs
        """
        status_str = status.value if isinstance(status, TaskStatus) else status

        return [tid for tid, task in self._state.get("tasks", {}).items() if task.get("status") == status_str]

    def claim_task(self, task_id: str, worker_id: int) -> bool:
        """Attempt to claim a task for a worker.

        Args:
            task_id: Task to claim
            worker_id: Worker claiming the task

        Returns:
            True if claim succeeded
        """
        self.load()  # Refresh state

        task_state = self._state.get("tasks", {}).get(task_id, {})
        current_status = task_state.get("status", TaskStatus.PENDING.value)

        # Can only claim pending tasks
        if current_status not in (TaskStatus.TODO.value, TaskStatus.PENDING.value):
            return False

        # Check if already claimed by a different worker
        existing_worker = task_state.get("worker_id")
        if existing_worker is not None and existing_worker != worker_id:
            return False

        # Claim it
        self.set_task_status(task_id, TaskStatus.CLAIMED, worker_id=worker_id)
        self.record_task_claimed(task_id, worker_id)
        return True

    def release_task(self, task_id: str, worker_id: int) -> None:
        """Release a task claim.

        Args:
            task_id: Task to release
            worker_id: Worker releasing the task
        """
        task_state = self._state.get("tasks", {}).get(task_id, {})

        # Only release if we own it
        if task_state.get("worker_id") != worker_id:
            return

        task_state["status"] = TaskStatus.PENDING.value
        task_state["worker_id"] = None

        self.save()

    # === Worker State Methods ===

    def get_worker_state(self, worker_id: int) -> WorkerState | None:
        """Get state of a worker.

        Args:
            worker_id: Worker identifier

        Returns:
            WorkerState or None if not found

        Raises:
            ValueError: If worker_id matches fail_on_worker_id
        """
        if worker_id == self._fail_on_worker_id:
            raise ValueError(f"Simulated failure for worker: {worker_id}")

        worker_data = self._state.get("workers", {}).get(str(worker_id))
        if not worker_data:
            return None
        return WorkerState.from_dict(worker_data)

    def set_worker_state(self, worker_state: WorkerState) -> None:
        """Set state of a worker.

        Args:
            worker_state: Worker state to save

        Raises:
            ValueError: If worker_id matches fail_on_worker_id
        """
        if worker_state.worker_id == self._fail_on_worker_id:
            raise ValueError(f"Simulated failure for worker: {worker_state.worker_id}")

        if "workers" not in self._state:
            self._state["workers"] = {}

        self._state["workers"][str(worker_state.worker_id)] = worker_state.to_dict()

        self.save()

        self._record_mock_event(
            "worker_state_changed",
            {
                "worker_id": worker_state.worker_id,
                "status": worker_state.status.value,
            },
        )

    def get_all_workers(self) -> dict[int, WorkerState]:
        """Get all worker states.

        Returns:
            Dictionary of worker_id to WorkerState
        """
        workers = {}
        for wid_str, data in self._state.get("workers", {}).items():
            workers[int(wid_str)] = WorkerState.from_dict(data)
        return workers

    def set_worker_ready(self, worker_id: int) -> None:
        """Mark a worker as ready to receive tasks.

        Args:
            worker_id: Worker identifier
        """
        worker_data = self._state.get("workers", {}).get(str(worker_id), {})
        if worker_data:
            worker_data["status"] = WorkerStatus.READY.value
            worker_data["ready_at"] = datetime.now().isoformat()

        self.save()

    def get_ready_workers(self) -> list[int]:
        """Get list of workers in ready state.

        Returns:
            List of ready worker IDs
        """
        ready = []
        for wid_str, worker_data in self._state.get("workers", {}).items():
            if worker_data.get("status") == WorkerStatus.READY.value:
                ready.append(int(wid_str))
        return ready

    def wait_for_workers_ready(self, worker_ids: list[int], timeout: float = 60.0) -> bool:
        """Wait for specified workers to become ready.

        Args:
            worker_ids: Workers to wait for
            timeout: Maximum wait time in seconds

        Returns:
            True if all workers became ready before timeout
        """
        start = time.time()
        while time.time() - start < timeout:
            self.load()  # Refresh state
            ready = self.get_ready_workers()
            if all(wid in ready for wid in worker_ids):
                return True
            time.sleep(0.1)  # Shorter sleep for tests
        return False

    # === Level State Methods ===

    def get_current_level(self) -> int:
        """Get the current execution level.

        Returns:
            Current level number
        """
        return self._state.get("current_level", 0)

    def set_current_level(self, level: int) -> None:
        """Set the current execution level.

        Args:
            level: Level number
        """
        self._state["current_level"] = level
        self.save()

        self._record_mock_event("level_changed", {"level": level})

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

        self.save()

    def get_level_status(self, level: int) -> dict[str, Any] | None:
        """Get status of a level.

        Args:
            level: Level number

        Returns:
            Level status dict or None
        """
        return self._state.get("levels", {}).get(str(level))

    def get_level_merge_status(self, level: int) -> LevelMergeStatus | None:
        """Get the merge status for a level.

        Args:
            level: Level number

        Returns:
            LevelMergeStatus or None if not set
        """
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

        self.save()

    # === Event Methods ===

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

        if "execution_log" not in self._state:
            self._state["execution_log"] = []
        self._state["execution_log"].append(event)

        self.save()

    def get_events(self, limit: int | None = None) -> list[ExecutionEvent]:
        """Get execution events.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of events (most recent last)
        """
        events = self._state.get("execution_log", [])
        if limit:
            return events[-limit:]
        return events.copy()

    # === Pause/Error Methods ===

    def set_paused(self, paused: bool) -> None:
        """Set paused state.

        Args:
            paused: Whether execution is paused
        """
        self._state["paused"] = paused
        self.save()

    def is_paused(self) -> bool:
        """Check if execution is paused.

        Returns:
            True if paused
        """
        return self._state.get("paused", False)

    def set_error(self, error: str | None) -> None:
        """Set error state.

        Args:
            error: Error message or None to clear
        """
        self._state["error"] = error
        self.save()

    def get_error(self) -> str | None:
        """Get current error.

        Returns:
            Error message or None
        """
        return self._state.get("error")

    # === Retry Methods ===

    def get_task_retry_count(self, task_id: str) -> int:
        """Get the retry count for a task.

        Args:
            task_id: Task identifier

        Returns:
            Number of retries (0 if never retried)
        """
        task_state = self._state.get("tasks", {}).get(task_id, {})
        return task_state.get("retry_count", 0)

    def increment_task_retry(self, task_id: str, next_retry_at: str | None = None) -> int:
        """Increment and return the retry count for a task.

        Args:
            task_id: Task identifier
            next_retry_at: Optional ISO timestamp for when retry becomes eligible

        Returns:
            New retry count
        """
        if "tasks" not in self._state:
            self._state["tasks"] = {}

        if task_id not in self._state["tasks"]:
            self._state["tasks"][task_id] = {}

        task_state = self._state["tasks"][task_id]
        retry_count = task_state.get("retry_count", 0) + 1
        task_state["retry_count"] = retry_count
        task_state["last_retry_at"] = datetime.now().isoformat()

        if next_retry_at:
            task_state["next_retry_at"] = next_retry_at

        self.save()
        return retry_count

    def reset_task_retry(self, task_id: str) -> None:
        """Reset the retry count for a task.

        Args:
            task_id: Task identifier
        """
        if task_id in self._state.get("tasks", {}):
            self._state["tasks"][task_id]["retry_count"] = 0
            self._state["tasks"][task_id].pop("last_retry_at", None)

        self.save()

    def get_failed_tasks(self) -> list[dict[str, Any]]:
        """Get all failed tasks with their retry information.

        Returns:
            List of failed task info dictionaries
        """
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

    # === Metrics Methods ===

    def record_task_claimed(self, task_id: str, worker_id: int) -> None:
        """Record when a task was claimed by a worker.

        Args:
            task_id: Task identifier
            worker_id: Worker that claimed the task
        """
        if "tasks" not in self._state:
            self._state["tasks"] = {}

        if task_id not in self._state["tasks"]:
            self._state["tasks"][task_id] = {}

        self._state["tasks"][task_id]["claimed_at"] = datetime.now().isoformat()
        self._state["tasks"][task_id]["worker_id"] = worker_id

        self.save()

    def record_task_duration(self, task_id: str, duration_ms: int) -> None:
        """Record task execution duration.

        Args:
            task_id: Task identifier
            duration_ms: Execution duration in milliseconds
        """
        if task_id in self._state.get("tasks", {}):
            self._state["tasks"][task_id]["duration_ms"] = duration_ms

        self.save()

    def store_metrics(self, metrics: FeatureMetrics) -> None:
        """Store computed metrics to state.

        Args:
            metrics: FeatureMetrics to persist
        """
        self._state["metrics"] = metrics.to_dict()
        self.save()

    def get_metrics(self) -> FeatureMetrics | None:
        """Retrieve stored metrics.

        Returns:
            FeatureMetrics if available, None otherwise
        """
        metrics_data = self._state.get("metrics")
        if not metrics_data:
            return None

        from zerg.types import FeatureMetrics

        return FeatureMetrics.from_dict(metrics_data)

    # === File Operations ===

    def delete(self) -> None:
        """Delete state file."""
        self._state = self._create_initial_state()
        self._file_exists = False

    def exists(self) -> bool:
        """Check if state file exists.

        Returns:
            True if state file exists
        """
        return self._file_exists

    # === Mock-specific Methods ===

    def _record_mock_event(self, event_type: str, details: dict) -> None:
        """Record a mock state change event.

        Args:
            event_type: Type of event
            details: Event details
        """
        self._mock_events.append(
            StateEvent(
                event_type=event_type,
                details=details,
            )
        )

        # Truncate if over limit
        if len(self._mock_events) > self._max_events:
            self._mock_events = self._mock_events[-self._max_events :]

    def get_mock_events(self, event_type: str | None = None) -> list[StateEvent]:
        """Get recorded mock events.

        Args:
            event_type: Optional filter by event type

        Returns:
            List of StateEvent records
        """
        if event_type is None:
            return self._mock_events.copy()
        return [e for e in self._mock_events if e.event_type == event_type]

    def get_mock_event_count(self, event_type: str | None = None) -> int:
        """Get count of recorded mock events.

        Args:
            event_type: Optional filter by event type

        Returns:
            Number of matching events
        """
        return len(self.get_mock_events(event_type))

    def get_save_count(self) -> int:
        """Get number of save operations.

        Returns:
            Save count
        """
        return self._save_count

    def get_load_count(self) -> int:
        """Get number of load operations.

        Returns:
            Load count
        """
        return self._load_count

    def get_last_save_time(self) -> datetime | None:
        """Get timestamp of last save.

        Returns:
            Last save time or None
        """
        return self._last_save_time

    def get_last_load_time(self) -> datetime | None:
        """Get timestamp of last load.

        Returns:
            Last load time or None
        """
        return self._last_load_time

    def get_state(self) -> dict[str, Any]:
        """Get the current internal state.

        Returns:
            Current state dictionary
        """
        return self._state.copy()

    def set_state(self, state: dict[str, Any]) -> None:
        """Set the internal state directly.

        Args:
            state: New state dictionary
        """
        self._state = state.copy()

    def get_statistics(self) -> dict[str, Any]:
        """Get state manager statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "feature": self.feature,
            "current_level": self._state.get("current_level", 0),
            "total_workers": len(self._state.get("workers", {})),
            "total_tasks": len(self._state.get("tasks", {})),
            "total_events": len(self._state.get("execution_log", [])),
            "save_count": self._save_count,
            "load_count": self._load_count,
            "paused": self._state.get("paused", False),
            "has_error": self._state.get("error") is not None,
        }

    def reset(self) -> None:
        """Reset mock state to initial."""
        self._state = self._create_initial_state()
        self._mock_events.clear()
        self._save_count = 0
        self._load_count = 0
        self._last_save_time = None
        self._last_load_time = None
        self._file_exists = False
