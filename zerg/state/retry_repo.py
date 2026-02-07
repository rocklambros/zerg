"""Retry repository — retry counts, schedules, and cooldowns.

Manages retry state for failed tasks including count tracking,
scheduling next retry timestamps, and determining retry eligibility.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, cast

from zerg.constants import TaskStatus
from zerg.logging import get_logger

if TYPE_CHECKING:
    from zerg.state.persistence import PersistenceLayer

logger = get_logger("state.retry_repo")


class RetryRepo:
    """Retry state management for tasks.

    Tracks retry counts, schedules, and eligibility for failed tasks.
    All operations delegate file I/O to the PersistenceLayer.
    """

    def __init__(self, persistence: PersistenceLayer) -> None:
        """Initialize retry repository.

        Args:
            persistence: PersistenceLayer instance for data access
        """
        self._persistence = persistence

    def get_retry_count(self, task_id: str) -> int:
        """Get the retry count for a task.

        Args:
            task_id: Task identifier

        Returns:
            Number of retries (0 if never retried)
        """
        with self._persistence.lock:
            task_state = self._persistence.state.get("tasks", {}).get(task_id, {})
            return int(task_state.get("retry_count", 0))

    def increment_retry(self, task_id: str, next_retry_at: str | None = None) -> int:
        """Increment and return the retry count for a task.

        Args:
            task_id: Task identifier
            next_retry_at: Optional ISO timestamp for when retry becomes eligible

        Returns:
            New retry count
        """
        with self._persistence.atomic_update():
            if "tasks" not in self._persistence.state:
                self._persistence.state["tasks"] = {}

            if task_id not in self._persistence.state["tasks"]:
                self._persistence.state["tasks"][task_id] = {}

            task_state = self._persistence.state["tasks"][task_id]
            retry_count: int = int(task_state.get("retry_count", 0)) + 1
            task_state["retry_count"] = retry_count
            task_state["last_retry_at"] = datetime.now().isoformat()

            if next_retry_at:
                task_state["next_retry_at"] = next_retry_at

        logger.debug(f"Task {task_id} retry count: {retry_count}")
        return retry_count

    def get_retry_schedule(self, task_id: str) -> str | None:
        """Get the next retry timestamp for a task.

        Args:
            task_id: Task identifier

        Returns:
            ISO timestamp string or None if not scheduled
        """
        with self._persistence.lock:
            task_state = self._persistence.state.get("tasks", {}).get(task_id, {})
            return cast(str | None, task_state.get("next_retry_at"))

    def set_retry_schedule(self, task_id: str, next_retry_at: str) -> None:
        """Set the next retry timestamp for a task.

        Args:
            task_id: Task identifier
            next_retry_at: ISO timestamp for when retry becomes eligible
        """
        with self._persistence.atomic_update():
            if "tasks" not in self._persistence.state:
                self._persistence.state["tasks"] = {}

            if task_id not in self._persistence.state["tasks"]:
                self._persistence.state["tasks"][task_id] = {}

            self._persistence.state["tasks"][task_id]["next_retry_at"] = next_retry_at

        logger.debug(f"Task {task_id} next retry at: {next_retry_at}")

    def get_tasks_ready_for_retry(self) -> list[str]:
        """Get task IDs whose scheduled retry time has passed.

        Returns:
            List of task IDs ready for retry
        """
        now = datetime.now().isoformat()
        with self._persistence.lock:
            ready = []
            for task_id, task_state in self._persistence.state.get("tasks", {}).items():
                next_retry = task_state.get("next_retry_at")
                if next_retry and next_retry <= now:
                    # Only include tasks that are still in a retryable state
                    status = task_state.get("status")
                    if status in (TaskStatus.FAILED.value, "waiting_retry"):
                        ready.append(task_id)
            return ready

    def reset_retries(self, task_id: str) -> None:
        """Reset the retry count for a task.

        Args:
            task_id: Task identifier
        """
        with self._persistence.atomic_update():
            if task_id in self._persistence.state.get("tasks", {}):
                self._persistence.state["tasks"][task_id]["retry_count"] = 0
                self._persistence.state["tasks"][task_id].pop("last_retry_at", None)

        logger.debug(f"Task {task_id} retry count reset")
