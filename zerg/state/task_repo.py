"""Task state repository — CRUD operations for task status and claims.

Manages task status transitions, worker claims, and task queries.
All operations delegate file I/O to the PersistenceLayer.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from zerg.constants import TaskStatus
from zerg.logging import get_logger

if TYPE_CHECKING:
    from zerg.dependency_checker import DependencyChecker
    from zerg.state.persistence import PersistenceLayer

logger = get_logger("state.task_repo")


class TaskStateRepo:
    """Task state CRUD operations.

    Reads and mutates task entries in the in-memory state dict
    managed by a PersistenceLayer instance.
    """

    def __init__(self, persistence: PersistenceLayer) -> None:
        """Initialize task state repository.

        Args:
            persistence: PersistenceLayer instance for data access
        """
        self._persistence = persistence

    def get_task_status(self, task_id: str) -> str | None:
        """Get the status of a task.

        Args:
            task_id: Task identifier

        Returns:
            Task status or None if not found
        """
        with self._persistence.lock:
            task_state = self._persistence.state.get("tasks", {}).get(task_id)
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

        with self._persistence.atomic_update():
            if "tasks" not in self._persistence.state:
                self._persistence.state["tasks"] = {}

            if task_id not in self._persistence.state["tasks"]:
                self._persistence.state["tasks"][task_id] = {}

            task_state = self._persistence.state["tasks"][task_id]
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
        with self._persistence.atomic_update():
            task_state = self._persistence.state.get("tasks", {}).get(task_id, {})
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

            # Claim it (inline mutation -- atomic_update is reentrant)
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
        with self._persistence.atomic_update():
            task_state = self._persistence.state.get("tasks", {}).get(task_id, {})

            # Only release if we own it
            if task_state.get("worker_id") != worker_id:
                return

            task_state["status"] = TaskStatus.PENDING.value
            task_state["worker_id"] = None

        logger.info(f"Worker {worker_id} released task {task_id}")

    def get_tasks_by_status(self, status: TaskStatus | str) -> list[str]:
        """Get task IDs with a specific status.

        Args:
            status: Status to filter by

        Returns:
            List of task IDs
        """
        status_str = status.value if isinstance(status, TaskStatus) else status

        with self._persistence.lock:
            return [
                tid
                for tid, task in self._persistence.state.get("tasks", {}).items()
                if task.get("status") == status_str
            ]

    def get_failed_tasks(self) -> list[dict[str, Any]]:
        """Get all failed tasks with their retry information.

        Returns:
            List of failed task info dictionaries
        """
        with self._persistence.lock:
            failed = []
            for task_id, task_state in self._persistence.state.get("tasks", {}).items():
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

        with self._persistence.lock:
            stale = []
            for task_id, task_state in self._persistence.state.get("tasks", {}).items():
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

    def record_task_claimed(self, task_id: str, worker_id: int) -> None:
        """Record when a task was claimed by a worker.

        Sets the claimed_at timestamp for task metrics tracking.

        Args:
            task_id: Task identifier
            worker_id: Worker that claimed the task
        """
        with self._persistence.atomic_update():
            if "tasks" not in self._persistence.state:
                self._persistence.state["tasks"] = {}

            if task_id not in self._persistence.state["tasks"]:
                self._persistence.state["tasks"][task_id] = {}

            self._persistence.state["tasks"][task_id]["claimed_at"] = datetime.now().isoformat()
            self._persistence.state["tasks"][task_id]["worker_id"] = worker_id

        logger.debug(f"Task {task_id} claimed by worker {worker_id}")
