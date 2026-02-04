"""Unit tests for DependencyChecker."""

from __future__ import annotations

from unittest.mock import Mock

from zerg.dependency_checker import DependencyChecker


class TestDependencyChecker:
    """Tests for DependencyChecker."""

    def test_are_dependencies_complete_no_dependencies(self) -> None:
        """Task with no dependencies should always be ready."""
        parser = Mock()
        state = Mock()

        parser.get_dependencies.return_value = []
        checker = DependencyChecker(parser, state)

        assert checker.are_dependencies_complete("TASK-001") is True
        parser.get_dependencies.assert_called_once_with("TASK-001")
        state.get_task_status.assert_not_called()

    def test_are_dependencies_complete_all_complete(self) -> None:
        """Task should be ready when all dependencies are complete."""
        parser = Mock()
        state = Mock()

        parser.get_dependencies.return_value = ["DEP-001", "DEP-002"]
        state.get_task_status.side_effect = ["complete", "complete"]
        checker = DependencyChecker(parser, state)

        assert checker.are_dependencies_complete("TASK-001") is True

    def test_are_dependencies_complete_some_incomplete(self) -> None:
        """Task should not be ready when any dependency is incomplete."""
        parser = Mock()
        state = Mock()

        parser.get_dependencies.return_value = ["DEP-001", "DEP-002"]
        state.get_task_status.side_effect = ["complete", "PENDING"]
        checker = DependencyChecker(parser, state)

        assert checker.are_dependencies_complete("TASK-001") is False

    def test_get_incomplete_dependencies_none_incomplete(self) -> None:
        """Should return empty list when all dependencies complete."""
        parser = Mock()
        state = Mock()

        parser.get_dependencies.return_value = ["DEP-001", "DEP-002"]
        state.get_task_status.side_effect = ["complete", "complete"]
        checker = DependencyChecker(parser, state)

        result = checker.get_incomplete_dependencies("TASK-001")
        assert result == []

    def test_get_incomplete_dependencies_some_incomplete(self) -> None:
        """Should return list of incomplete dependency IDs."""
        parser = Mock()
        state = Mock()

        parser.get_dependencies.return_value = ["DEP-001", "DEP-002", "DEP-003"]
        state.get_task_status.side_effect = ["complete", "PENDING", "IN_PROGRESS"]
        checker = DependencyChecker(parser, state)

        result = checker.get_incomplete_dependencies("TASK-001")
        assert result == ["DEP-002", "DEP-003"]

    def test_get_incomplete_dependencies_all_incomplete(self) -> None:
        """Should return all dependencies when none are complete."""
        parser = Mock()
        state = Mock()

        parser.get_dependencies.return_value = ["DEP-001", "DEP-002"]
        state.get_task_status.side_effect = ["PENDING", "PENDING"]
        checker = DependencyChecker(parser, state)

        result = checker.get_incomplete_dependencies("TASK-001")
        assert result == ["DEP-001", "DEP-002"]

    def test_various_incomplete_statuses(self) -> None:
        """All non-complete statuses should be considered incomplete."""
        parser = Mock()
        state = Mock()

        parser.get_dependencies.return_value = [
            "DEP-PENDING",
            "DEP-PROGRESS",
            "DEP-FAILED",
            "DEP-PAUSED",
        ]
        state.get_task_status.side_effect = ["PENDING", "IN_PROGRESS", "FAILED", "PAUSED"]
        checker = DependencyChecker(parser, state)

        result = checker.get_incomplete_dependencies("TASK-001")
        assert len(result) == 4

    def test_mixed_complete_and_incomplete(self) -> None:
        """Should correctly identify mixed status dependencies."""
        parser = Mock()
        state = Mock()

        parser.get_dependencies.return_value = ["DEP-A", "DEP-B", "DEP-C", "DEP-D"]
        # Provide enough values for both calls (8 total: 4 for get_incomplete, 4 for are_complete)
        state.get_task_status.side_effect = [
            "complete",
            "PENDING",
            "complete",
            "FAILED",  # First call
            "complete",
            "PENDING",
            "complete",
            "FAILED",  # Second call
        ]
        checker = DependencyChecker(parser, state)

        result = checker.get_incomplete_dependencies("TASK-001")
        assert result == ["DEP-B", "DEP-D"]
        assert checker.are_dependencies_complete("TASK-001") is False
