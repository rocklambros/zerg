"""Dependency checking for ZERG tasks.

This module provides the DependencyChecker class that combines TaskParser
and StateManager to verify task dependencies are complete before execution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from zerg.constants import TaskStatus
from zerg.logging import get_logger

if TYPE_CHECKING:
    from zerg.parser import TaskParser
    from zerg.state import StateManager

logger = get_logger(__name__)


class DependencyChecker:
    """Check task dependencies using parser and state.

    Combines TaskParser (for dependency graph) with StateManager
    (for completion status) to verify dependencies are met.
    """

    def __init__(self, parser: TaskParser, state: StateManager) -> None:
        """Initialize dependency checker.

        Args:
            parser: TaskParser instance with loaded task graph
            state: StateManager instance with current state
        """
        self._parser = parser
        self._state = state

    def are_dependencies_complete(self, task_id: str) -> bool:
        """Check if all dependencies of a task are complete.

        Args:
            task_id: Task identifier to check

        Returns:
            True if all dependencies have status COMPLETE
        """
        deps = self.get_incomplete_dependencies(task_id)
        return len(deps) == 0

    def get_incomplete_dependencies(self, task_id: str) -> list[str]:
        """Get list of incomplete dependencies for a task.

        Args:
            task_id: Task identifier to check

        Returns:
            List of task IDs that are not yet complete
        """
        dependencies = self._parser.get_dependencies(task_id)
        incomplete = []

        for dep_id in dependencies:
            status = self._state.get_task_status(dep_id)
            if status != TaskStatus.COMPLETE.value:
                incomplete.append(dep_id)
                logger.debug(f"Task {task_id} blocked by {dep_id} (status: {status})")

        return incomplete

    def get_all_dependencies(self, task_id: str) -> list[str]:
        """Get all dependencies for a task.

        Args:
            task_id: Task identifier

        Returns:
            List of dependency task IDs
        """
        return self._parser.get_dependencies(task_id)

    def get_dependency_status(self, task_id: str) -> dict[str, str]:
        """Get status of all dependencies for a task.

        Args:
            task_id: Task identifier

        Returns:
            Dict mapping dependency task_id to status
        """
        dependencies = self._parser.get_dependencies(task_id)
        return {dep_id: self._state.get_task_status(dep_id) for dep_id in dependencies}
