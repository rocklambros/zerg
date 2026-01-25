"""State persistence and management for ZERG."""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from zerg.constants import STATE_DIR, TaskStatus, WorkerStatus
from zerg.exceptions import StateError
from zerg.logging import get_logger
from zerg.types import ExecutionEvent, WorkerState

logger = get_logger("state")


class StateManager:
    """Manage ZERG execution state with file-based persistence."""

    def __init__(self, feature: str, state_dir: str | Path | None = None) -> None:
        """Initialize state manager.

        Args:
            feature: Feature name for state isolation
            state_dir: Directory for state files (defaults to .zerg/state)
        """
        self.feature = feature
        self.state_dir = Path(state_dir or STATE_DIR)
        self._state_file = self.state_dir / f"{feature}.json"
        self._lock = threading.Lock()
        self._state: dict[str, Any] = {}
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Ensure state directory exists."""
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        """Load state from file.

        Returns:
            State dictionary
        """
        with self._lock:
            if not self._state_file.exists():
                self._state = self._create_initial_state()
            else:
                try:
                    with open(self._state_file) as f:
                        self._state = json.load(f)
                except json.JSONDecodeError as e:
                    raise StateError(f"Failed to parse state file: {e}")

            logger.debug(f"Loaded state for feature {self.feature}")
            return self._state.copy()

    def save(self) -> None:
        """Save state to file."""
        with self._lock:
            with open(self._state_file, "w") as f:
                json.dump(self._state, f, indent=2, default=str)
            logger.debug(f"Saved state for feature {self.feature}")

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

        with self._lock:
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
        with self._lock:
            if "workers" not in self._state:
                self._state["workers"] = {}

            self._state["workers"][str(worker_state.worker_id)] = worker_state.to_dict()

        self.save()
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

    def claim_task(self, task_id: str, worker_id: int) -> bool:
        """Attempt to claim a task for a worker.

        Uses file-based locking to prevent race conditions.

        Args:
            task_id: Task to claim
            worker_id: Worker claiming the task

        Returns:
            True if claim succeeded
        """
        with self._lock:
            # Reload state to get latest
            self.load()

            task_state = self._state.get("tasks", {}).get(task_id, {})
            current_status = task_state.get("status", TaskStatus.PENDING.value)

            # Can only claim pending tasks
            if current_status not in (TaskStatus.TODO.value, TaskStatus.PENDING.value):
                return False

            # Check if already claimed
            if task_state.get("worker_id") is not None:
                return False

            # Claim it
            self.set_task_status(task_id, TaskStatus.CLAIMED, worker_id=worker_id)
            logger.info(f"Worker {worker_id} claimed task {task_id}")
            return True

    def release_task(self, task_id: str, worker_id: int) -> None:
        """Release a task claim.

        Args:
            task_id: Task to release
            worker_id: Worker releasing the task
        """
        with self._lock:
            task_state = self._state.get("tasks", {}).get(task_id, {})

            # Only release if we own it
            if task_state.get("worker_id") != worker_id:
                return

            task_state["status"] = TaskStatus.PENDING.value
            task_state["worker_id"] = None

        self.save()
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

        with self._lock:
            if "execution_log" not in self._state:
                self._state["execution_log"] = []
            self._state["execution_log"].append(event)

        self.save()
        logger.debug(f"Event: {event_type}")

    def get_events(self, limit: int | None = None) -> list[ExecutionEvent]:
        """Get execution events.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of events (most recent last)
        """
        with self._lock:
            events = self._state.get("execution_log", [])
            if limit:
                return events[-limit:]
            return events.copy()

    def set_current_level(self, level: int) -> None:
        """Set the current execution level.

        Args:
            level: Level number
        """
        with self._lock:
            self._state["current_level"] = level
        self.save()

    def get_current_level(self) -> int:
        """Get the current execution level.

        Returns:
            Current level number
        """
        with self._lock:
            return self._state.get("current_level", 0)

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
        with self._lock:
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
        with self._lock:
            return self._state.get("levels", {}).get(str(level))

    def get_tasks_by_status(self, status: TaskStatus | str) -> list[str]:
        """Get task IDs with a specific status.

        Args:
            status: Status to filter by

        Returns:
            List of task IDs
        """
        status_str = status.value if isinstance(status, TaskStatus) else status

        with self._lock:
            return [
                tid
                for tid, task in self._state.get("tasks", {}).items()
                if task.get("status") == status_str
            ]

    def set_paused(self, paused: bool) -> None:
        """Set paused state.

        Args:
            paused: Whether execution is paused
        """
        with self._lock:
            self._state["paused"] = paused
        self.save()

    def is_paused(self) -> bool:
        """Check if execution is paused.

        Returns:
            True if paused
        """
        with self._lock:
            return self._state.get("paused", False)

    def set_error(self, error: str | None) -> None:
        """Set error state.

        Args:
            error: Error message or None to clear
        """
        with self._lock:
            self._state["error"] = error
        self.save()

    def get_error(self) -> str | None:
        """Get current error.

        Returns:
            Error message or None
        """
        with self._lock:
            return self._state.get("error")

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
