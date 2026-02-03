"""Task sync bridge for ZERG Claude Tasks integration.

Bridges ZERG's JSON state with Claude Tasks API for orchestrator-level visibility.
Workers remain subprocess-isolated using JSON state; this provides a one-way sync
from JSON state to Claude Tasks for the orchestrator.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from zerg.constants import TaskStatus
from zerg.logging import get_logger
from zerg.state import StateManager

logger = get_logger("task_sync")

DESIGN_MANIFEST_FILENAME = "design-tasks-manifest.json"


def load_design_manifest(spec_dir: Path) -> list[dict[str, Any]] | None:
    """Load the design tasks manifest written by design.py.

    The manifest bridges the CLI (which cannot call Claude Task tools) with
    the rush orchestrator (which registers Claude Tasks). design.py writes
    this file for every execution path so the orchestrator can pick it up.

    Args:
        spec_dir: Path to the feature spec directory, e.g.
            ``.gsd/specs/{feature}/``.

    Returns:
        The ``tasks`` list from the manifest, or ``None`` if the manifest
        file does not exist.
    """
    manifest_path = spec_dir / DESIGN_MANIFEST_FILENAME
    if not manifest_path.exists():
        logger.debug("No design manifest at %s", manifest_path)
        return None

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    tasks: list[dict[str, Any]] = data.get("tasks", [])
    logger.info("Loaded design manifest with %d tasks from %s", len(tasks), manifest_path)
    return tasks


@dataclass
class ClaudeTask:
    """Representation of a Claude Task for sync purposes."""

    task_id: str
    subject: str
    description: str
    status: str  # pending, in_progress, completed
    level: int
    feature: str
    worker_id: int | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    active_form: str | None = None
    task_list_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API calls."""
        return {
            "task_id": self.task_id,
            "subject": self.subject,
            "description": self.description,
            "status": self.status,
            "level": self.level,
            "feature": self.feature,
            "worker_id": self.worker_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "active_form": self.active_form,
            "task_list_id": self.task_list_id,
        }


class TaskSyncBridge:
    """Bridge between ZERG JSON state and Claude Tasks API.

    Provides one-way sync from ZERG state to Claude Tasks for orchestrator visibility.
    Workers continue to use JSON state directly (subprocess isolation).
    """

    # Map ZERG TaskStatus to Claude Task status
    STATUS_MAP = {
        TaskStatus.TODO.value: "pending",
        TaskStatus.PENDING.value: "pending",
        TaskStatus.CLAIMED.value: "in_progress",
        TaskStatus.IN_PROGRESS.value: "in_progress",
        TaskStatus.PAUSED.value: "in_progress",
        TaskStatus.COMPLETE.value: "completed",
        TaskStatus.FAILED.value: "completed",  # Failed is a terminal state
        TaskStatus.BLOCKED.value: "in_progress",
    }

    def __init__(
        self,
        feature: str,
        state_manager: StateManager | None = None,
        task_list_id: str | None = None,
    ) -> None:
        """Initialize task sync bridge.

        Args:
            feature: Feature name for task context
            state_manager: Optional state manager (created if not provided)
            task_list_id: CLAUDE_CODE_TASK_LIST_ID for cross-session coordination
        """
        self.feature = feature
        self.task_list_id = task_list_id or os.environ.get("CLAUDE_CODE_TASK_LIST_ID", feature)
        self.state = state_manager or StateManager(feature)
        self._synced_tasks: dict[str, ClaudeTask] = {}

    def create_level_tasks(
        self,
        level: int,
        tasks: list[dict[str, Any]],
    ) -> list[ClaudeTask]:
        """Create Claude Task representations for a level.

        Tasks can originate from the task graph JSON or from the design
        manifest (see :func:`load_design_manifest`).  The manifest is the
        standard handoff mechanism between ``design.py`` and the rush
        orchestrator.

        Args:
            level: Level number
            tasks: List of task specifications from task graph or manifest

        Returns:
            List of created ClaudeTask objects
        """
        created = []

        for task in tasks:
            task_id = task.get("id", "")
            subject = task.get("title", f"Task {task_id}")
            description = task.get("description", "")

            claude_task = ClaudeTask(
                task_id=task_id,
                subject=f"[L{level}] {subject}",
                description=description,
                status="pending",
                level=level,
                feature=self.feature,
                active_form=f"Executing {subject}",
                task_list_id=self.task_list_id,
            )

            self._synced_tasks[task_id] = claude_task
            created.append(claude_task)

            logger.debug(f"Created Claude task for {task_id}: {subject}")

        logger.info(f"Created {len(created)} Claude tasks for level {level}")
        return created

    def create_level_tasks_resumable(
        self,
        level: int,
        tasks: list[dict[str, Any]],
        existing_subjects: set[str] | None = None,
    ) -> list[ClaudeTask]:
        """Create tasks, skipping any that already exist (resume-safe).

        Args:
            level: Level number
            tasks: List of task specifications from task graph or manifest
            existing_subjects: Set of existing task subjects to skip

        Returns:
            List of newly created ClaudeTask objects
        """
        if existing_subjects is None:
            return self.create_level_tasks(level, tasks)

        new_tasks = []
        for task in tasks:
            title = task.get("title", f"Task {task.get('id', '')}")
            subject = f"[L{level}] {title}"
            if subject not in existing_subjects:
                new_tasks.append(task)
            else:
                logger.info("Skipping existing task: %s", subject)

        if not new_tasks:
            logger.info("All %d tasks at level %d already exist", len(tasks), level)
            return []
        return self.create_level_tasks(level, new_tasks)

    def sync_state(self, state: dict[str, Any] | None = None) -> int:
        """Sync ZERG state to Claude Tasks.

        Updates Claude Task statuses based on current ZERG state.

        Args:
            state: Optional state dict (loads from StateManager if not provided)

        Returns:
            Number of tasks updated
        """
        if state is None:
            state = self.state.load()

        tasks_state = state.get("tasks", {})
        updated_count = 0

        for task_id, task_state in tasks_state.items():
            if task_id not in self._synced_tasks:
                # Task not tracked yet - skip
                continue

            zerg_status = task_state.get("status", TaskStatus.PENDING.value)
            claude_status = self.STATUS_MAP.get(zerg_status, "pending")
            worker_id = task_state.get("worker_id")

            synced_task = self._synced_tasks[task_id]

            # Check if update needed
            if synced_task.status != claude_status or synced_task.worker_id != worker_id:
                synced_task.status = claude_status
                synced_task.worker_id = worker_id
                synced_task.updated_at = datetime.now()
                updated_count += 1

                logger.debug(f"Synced task {task_id}: status={claude_status}, worker={worker_id}")

        if updated_count > 0:
            logger.info(f"Synced {updated_count} task status updates")

        return updated_count

    def get_task_list(self) -> list[dict[str, Any]]:
        """Get current task statuses.

        Returns:
            List of task status dictionaries
        """
        return [task.to_dict() for task in self._synced_tasks.values()]

    def get_level_summary(self, level: int) -> dict[str, Any]:
        """Get summary for a specific level.

        Args:
            level: Level number

        Returns:
            Summary dictionary with counts by status
        """
        level_tasks = [t for t in self._synced_tasks.values() if t.level == level]

        by_status: dict[str, int] = {}
        for task in level_tasks:
            by_status[task.status] = by_status.get(task.status, 0) + 1

        return {
            "level": level,
            "total": len(level_tasks),
            "by_status": by_status,
            "pending": by_status.get("pending", 0),
            "in_progress": by_status.get("in_progress", 0),
            "completed": by_status.get("completed", 0),
        }

    def is_level_complete(self, level: int) -> bool:
        """Check if all tasks in a level are complete.

        Args:
            level: Level number

        Returns:
            True if all tasks in level are completed
        """
        level_tasks = [t for t in self._synced_tasks.values() if t.level == level]

        if not level_tasks:
            return True

        # Level is resolved when all tasks are either completed or failed
        return all(t.status in ("completed", "failed") for t in level_tasks)

    def get_task(self, task_id: str) -> ClaudeTask | None:
        """Get a specific task.

        Args:
            task_id: Task identifier

        Returns:
            ClaudeTask or None if not found
        """
        return self._synced_tasks.get(task_id)

    def update_task_status(
        self,
        task_id: str,
        status: str,
        worker_id: int | None = None,
    ) -> bool:
        """Manually update a task status.

        Args:
            task_id: Task identifier
            status: New status (pending, in_progress, completed)
            worker_id: Optional worker ID

        Returns:
            True if task was updated
        """
        if task_id not in self._synced_tasks:
            logger.warning(f"Task {task_id} not found for update")
            return False

        task = self._synced_tasks[task_id]
        task.status = status
        task.updated_at = datetime.now()

        if worker_id is not None:
            task.worker_id = worker_id

        logger.debug(f"Updated task {task_id}: status={status}")
        return True

    def clear(self) -> None:
        """Clear all synced tasks."""
        self._synced_tasks.clear()
        logger.debug("Cleared all synced tasks")
