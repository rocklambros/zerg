"""Level-based execution control for ZERG."""

from datetime import datetime
from typing import Any

from zerg.constants import LEVEL_NAMES, Level, TaskStatus
from zerg.exceptions import LevelError
from zerg.logging import get_logger
from zerg.types import LevelStatus, Task

logger = get_logger("levels")


class LevelController:
    """Control level-based task execution.

    Manages level transitions and tracks task completion within levels.
    Enforces the rule that level N+1 cannot start until level N is complete.
    """

    def __init__(self) -> None:
        """Initialize level controller."""
        self._levels: dict[int, LevelStatus] = {}
        self._tasks: dict[str, Task] = {}
        self._current_level: int = 0
        self._started: bool = False

    def initialize(self, tasks: list[Task]) -> None:
        """Initialize controller with tasks.

        Args:
            tasks: List of tasks from task graph
        """
        self._tasks.clear()
        self._levels.clear()
        self._current_level = 0
        self._started = False

        # Index tasks and build level structure
        level_tasks: dict[int, list[str]] = {}

        for task in tasks:
            task_id = task["id"]
            level = task["level"]
            self._tasks[task_id] = task

            if level not in level_tasks:
                level_tasks[level] = []
            level_tasks[level].append(task_id)

        # Create level status objects
        for level_num, task_ids in level_tasks.items():
            level_enum = Level(level_num) if level_num <= 5 else Level.QUALITY
            name = LEVEL_NAMES.get(level_enum, f"level_{level_num}")

            self._levels[level_num] = LevelStatus(
                level=level_enum,
                name=name,
                total_tasks=len(task_ids),
                status="pending",
            )

        logger.info(f"Initialized with {len(tasks)} tasks across {len(self._levels)} levels")

    def start_level(self, level: int) -> list[str]:
        """Start execution of a level.

        Args:
            level: Level number to start

        Returns:
            List of task IDs in the level

        Raises:
            LevelError: If level cannot be started
        """
        if level not in self._levels:
            raise LevelError(f"Level {level} does not exist", level=level)

        # Check previous levels are complete
        for prev_level in range(1, level):
            if prev_level in self._levels and not self._levels[prev_level].is_resolved:
                raise LevelError(
                    f"Cannot start level {level}: level {prev_level} not complete",
                    level=level,
                    details={"blocking_level": prev_level},
                )

        level_status = self._levels[level]
        level_status.status = "running"
        level_status.started_at = datetime.now()
        self._current_level = level
        self._started = True

        task_ids = self.get_tasks_for_level(level)
        logger.info(f"Started level {level} ({level_status.name}) with {len(task_ids)} tasks")

        return task_ids

    def get_tasks_for_level(self, level: int) -> list[str]:
        """Get all task IDs for a level.

        Args:
            level: Level number

        Returns:
            List of task IDs
        """
        return [tid for tid, task in self._tasks.items() if task.get("level") == level]

    def get_pending_tasks_for_level(self, level: int) -> list[str]:
        """Get pending task IDs for a level.

        Args:
            level: Level number

        Returns:
            List of pending task IDs
        """
        return [
            tid
            for tid, task in self._tasks.items()
            if task.get("level") == level
            and task.get("status", TaskStatus.TODO.value) in (TaskStatus.TODO.value, TaskStatus.PENDING.value)
        ]

    def mark_task_complete(self, task_id: str) -> bool:
        """Mark a task as complete.

        Args:
            task_id: Task ID to mark complete

        Returns:
            True if this completed the level
        """
        if task_id not in self._tasks:
            logger.warning(f"Unknown task: {task_id}")
            return False

        task = self._tasks[task_id]
        task["status"] = TaskStatus.COMPLETE.value
        level = task["level"]

        if level in self._levels:
            self._levels[level].completed_tasks += 1
            self._levels[level].in_progress_tasks = max(0, self._levels[level].in_progress_tasks - 1)

        logger.info(f"Task {task_id} complete")

        # Check if level is now resolved (all tasks in terminal state)
        if self.is_level_resolved(level):
            self._levels[level].status = "complete"
            self._levels[level].completed_at = datetime.now()
            logger.info(f"Level {level} resolved")
            return True

        return False

    def mark_task_failed(self, task_id: str, error: str | None = None) -> None:
        """Mark a task as failed.

        Args:
            task_id: Task ID to mark failed
            error: Optional error message
        """
        if task_id not in self._tasks:
            logger.warning(f"Unknown task: {task_id}")
            return

        task = self._tasks[task_id]
        task["status"] = TaskStatus.FAILED.value
        level = task["level"]

        if level in self._levels:
            self._levels[level].failed_tasks += 1
            self._levels[level].in_progress_tasks = max(0, self._levels[level].in_progress_tasks - 1)

        logger.error(f"Task {task_id} failed: {error or 'unknown error'}")

    def mark_task_in_progress(self, task_id: str, worker_id: int | None = None) -> None:
        """Mark a task as in progress.

        Args:
            task_id: Task ID
            worker_id: Optional worker ID
        """
        if task_id not in self._tasks:
            return

        task = self._tasks[task_id]
        task["status"] = TaskStatus.IN_PROGRESS.value
        if worker_id is not None:
            task["assigned_worker"] = worker_id

        level = task["level"]
        if level in self._levels:
            self._levels[level].in_progress_tasks += 1

        suffix = f" (worker {worker_id})" if worker_id else ""
        logger.debug(f"Task {task_id} in progress{suffix}")

    def is_level_complete(self, level: int) -> bool:
        """Check if a level is complete (all tasks completed successfully).

        Args:
            level: Level number

        Returns:
            True if all tasks in the level completed successfully
        """
        if level not in self._levels:
            return False

        level_status = self._levels[level]
        return level_status.completed_tasks == level_status.total_tasks

    def is_level_resolved(self, level: int) -> bool:
        """Check if a level is resolved (all tasks in a terminal state).

        A level is resolved when all tasks are either completed or failed.
        Failed tasks don't block advancement; the orchestrator logs warnings.

        Args:
            level: Level number

        Returns:
            True if all tasks in the level are in a terminal state
        """
        if level not in self._levels:
            return False

        level_status = self._levels[level]
        resolved = level_status.completed_tasks + level_status.failed_tasks
        return resolved == level_status.total_tasks

    def can_advance(self) -> bool:
        """Check if we can advance to the next level.

        Returns:
            True if current level is complete and next level exists
        """
        if not self._started or self._current_level == 0:
            return True  # Can start level 1

        if not self.is_level_resolved(self._current_level):
            return False

        next_level = self._current_level + 1
        return next_level in self._levels

    def advance_level(self) -> int | None:
        """Advance to the next level.

        Returns:
            New level number, or None if no more levels
        """
        if not self._started:
            next_level = min(self._levels.keys()) if self._levels else None
        else:
            next_level = self._current_level + 1

        if next_level is None or next_level not in self._levels:
            logger.info("No more levels to advance to")
            return None

        self.start_level(next_level)
        return next_level

    def get_status(self) -> dict[str, Any]:
        """Get overall execution status.

        Returns:
            Status dictionary
        """
        total_tasks = len(self._tasks)
        completed_tasks = sum(1 for t in self._tasks.values() if t.get("status") == TaskStatus.COMPLETE.value)
        failed_tasks = sum(1 for t in self._tasks.values() if t.get("status") == TaskStatus.FAILED.value)
        in_progress_tasks = sum(1 for t in self._tasks.values() if t.get("status") == TaskStatus.IN_PROGRESS.value)

        return {
            "current_level": self._current_level,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "in_progress_tasks": in_progress_tasks,
            "progress_percent": (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0,
            "levels": {level: status.to_dict() for level, status in self._levels.items()},
            "is_complete": (completed_tasks + failed_tasks) == total_tasks,
        }

    def get_level_status(self, level: int) -> LevelStatus | None:
        """Get status for a specific level.

        Args:
            level: Level number

        Returns:
            LevelStatus or None if not found
        """
        return self._levels.get(level)

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID.

        Args:
            task_id: Task ID

        Returns:
            Task or None if not found
        """
        return self._tasks.get(task_id)

    def get_task_status(self, task_id: str) -> str | None:
        """Get the status of a task.

        Args:
            task_id: Task ID

        Returns:
            Task status string or None
        """
        task = self._tasks.get(task_id)
        return task.get("status") if task else None

    def reset_task(self, task_id: str) -> None:
        """Reset a task to pending status.

        Args:
            task_id: Task ID to reset
        """
        if task_id not in self._tasks:
            return

        task = self._tasks[task_id]
        old_status = task.get("status", TaskStatus.TODO.value)
        task["status"] = TaskStatus.PENDING.value

        level = task["level"]
        if level in self._levels:
            if old_status == TaskStatus.COMPLETE.value:
                self._levels[level].completed_tasks -= 1
            elif old_status == TaskStatus.FAILED.value:
                self._levels[level].failed_tasks -= 1
            elif old_status == TaskStatus.IN_PROGRESS.value:
                self._levels[level].in_progress_tasks -= 1

        logger.info(f"Reset task {task_id} to pending")

    @property
    def current_level(self) -> int:
        """Get current level number."""
        return self._current_level

    @property
    def total_levels(self) -> int:
        """Get total number of levels."""
        return len(self._levels)
