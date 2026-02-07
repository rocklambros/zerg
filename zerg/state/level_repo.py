"""Level state repository — level progression and merge status.

Manages execution level state including current level tracking,
level status transitions, and merge status for level completion protocol.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from zerg.constants import LevelMergeStatus
from zerg.logging import get_logger

if TYPE_CHECKING:
    from zerg.state.persistence import PersistenceLayer

logger = get_logger("state.level_repo")


class LevelStateRepo:
    """Level state CRUD operations.

    Reads and mutates level entries in the in-memory state dict
    managed by a PersistenceLayer instance.
    """

    def __init__(self, persistence: PersistenceLayer) -> None:
        """Initialize level state repository.

        Args:
            persistence: PersistenceLayer instance for data access
        """
        self._persistence = persistence

    def set_current_level(self, level: int) -> None:
        """Set the current execution level.

        Args:
            level: Level number
        """
        with self._persistence.atomic_update():
            self._persistence.state["current_level"] = level

    def get_current_level(self) -> int:
        """Get the current execution level.

        Returns:
            Current level number
        """
        with self._persistence.lock:
            return int(self._persistence.state.get("current_level", 0))

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
        with self._persistence.atomic_update():
            if "levels" not in self._persistence.state:
                self._persistence.state["levels"] = {}

            if str(level) not in self._persistence.state["levels"]:
                self._persistence.state["levels"][str(level)] = {}

            level_state = self._persistence.state["levels"][str(level)]
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
        with self._persistence.lock:
            return cast(
                dict[str, Any] | None,
                self._persistence.state.get("levels", {}).get(str(level)),
            )

    def get_level_merge_status(self, level: int) -> LevelMergeStatus | None:
        """Get the merge status for a level.

        Args:
            level: Level number

        Returns:
            LevelMergeStatus or None if not set
        """
        with self._persistence.lock:
            level_data = self._persistence.state.get("levels", {}).get(str(level), {})
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
        with self._persistence.atomic_update():
            if "levels" not in self._persistence.state:
                self._persistence.state["levels"] = {}

            if str(level) not in self._persistence.state["levels"]:
                self._persistence.state["levels"][str(level)] = {}

            level_state = self._persistence.state["levels"][str(level)]
            level_state["merge_status"] = merge_status.value
            level_state["merge_updated_at"] = datetime.now().isoformat()

            if details:
                level_state["merge_details"] = details

            if merge_status == LevelMergeStatus.COMPLETE:
                level_state["merge_completed_at"] = datetime.now().isoformat()

        logger.debug(f"Level {level} merge status: {merge_status.value}")
