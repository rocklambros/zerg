"""Tests for zerg.levels module."""

import pytest

from zerg.constants import Level, TaskStatus
from zerg.exceptions import LevelError
from zerg.levels import LevelController
from zerg.types import Task


class TestLevelController:
    """Tests for LevelController class."""

    def test_create_controller(self) -> None:
        """Test creating a LevelController."""
        controller = LevelController()

        assert controller is not None
        assert controller.current_level == 0
        assert controller.total_levels == 0

    def test_initialize_with_tasks(self, sample_task: Task, sample_task_graph) -> None:
        """Test initializing controller with tasks."""
        controller = LevelController()
        tasks = sample_task_graph["tasks"]

        controller.initialize(tasks)

        assert controller.total_levels > 0

    def test_get_tasks_for_level(self, sample_task_graph) -> None:
        """Test getting tasks for a specific level."""
        controller = LevelController()
        controller.initialize(sample_task_graph["tasks"])

        level_1_tasks = controller.get_tasks_for_level(1)

        assert isinstance(level_1_tasks, list)
        assert len(level_1_tasks) > 0

    def test_start_level(self, sample_task_graph) -> None:
        """Test starting a level."""
        controller = LevelController()
        controller.initialize(sample_task_graph["tasks"])

        task_ids = controller.start_level(1)

        assert isinstance(task_ids, list)
        assert controller.current_level == 1

    def test_cannot_start_level_2_before_level_1(self, sample_task_graph) -> None:
        """Test that level 2 cannot start before level 1 completes."""
        controller = LevelController()
        controller.initialize(sample_task_graph["tasks"])

        with pytest.raises(LevelError):
            controller.start_level(2)

    def test_mark_task_complete(self, sample_task_graph) -> None:
        """Test marking a task as complete."""
        controller = LevelController()
        controller.initialize(sample_task_graph["tasks"])
        controller.start_level(1)

        level_completed = controller.mark_task_complete("TASK-001")

        status = controller.get_task_status("TASK-001")
        assert status == TaskStatus.COMPLETE.value

    def test_mark_task_failed(self, sample_task_graph) -> None:
        """Test marking a task as failed."""
        controller = LevelController()
        controller.initialize(sample_task_graph["tasks"])
        controller.start_level(1)

        controller.mark_task_failed("TASK-001", "test error")

        status = controller.get_task_status("TASK-001")
        assert status == TaskStatus.FAILED.value

    def test_mark_task_in_progress(self, sample_task_graph) -> None:
        """Test marking a task as in progress."""
        controller = LevelController()
        controller.initialize(sample_task_graph["tasks"])
        controller.start_level(1)

        controller.mark_task_in_progress("TASK-001", worker_id=1)

        status = controller.get_task_status("TASK-001")
        assert status == TaskStatus.IN_PROGRESS.value

    def test_is_level_complete(self, sample_task_graph) -> None:
        """Test checking if level is complete."""
        controller = LevelController()
        controller.initialize(sample_task_graph["tasks"])
        controller.start_level(1)

        # Initially not complete
        assert not controller.is_level_complete(1)

        # Mark all level 1 tasks complete
        for task_id in controller.get_tasks_for_level(1):
            controller.mark_task_complete(task_id)

        assert controller.is_level_complete(1)

    def test_can_advance(self, sample_task_graph) -> None:
        """Test checking if can advance to next level."""
        controller = LevelController()
        controller.initialize(sample_task_graph["tasks"])

        # Can start initially
        assert controller.can_advance()

        controller.start_level(1)

        # Cannot advance while level 1 incomplete
        assert not controller.can_advance()

        # Complete level 1
        for task_id in controller.get_tasks_for_level(1):
            controller.mark_task_complete(task_id)

        # Now can advance
        assert controller.can_advance()

    def test_advance_level(self, sample_task_graph) -> None:
        """Test advancing to next level."""
        controller = LevelController()
        controller.initialize(sample_task_graph["tasks"])

        # Advance to level 1
        next_level = controller.advance_level()
        assert next_level == 1

        # Complete level 1
        for task_id in controller.get_tasks_for_level(1):
            controller.mark_task_complete(task_id)

        # Advance to level 2
        next_level = controller.advance_level()
        assert next_level == 2

    def test_get_status(self, sample_task_graph) -> None:
        """Test getting overall status."""
        controller = LevelController()
        controller.initialize(sample_task_graph["tasks"])
        controller.start_level(1)

        status = controller.get_status()

        assert "current_level" in status
        assert "total_tasks" in status
        assert "completed_tasks" in status
        assert "progress_percent" in status
        assert "levels" in status

    def test_get_level_status(self, sample_task_graph) -> None:
        """Test getting status for a specific level."""
        controller = LevelController()
        controller.initialize(sample_task_graph["tasks"])
        controller.start_level(1)

        level_status = controller.get_level_status(1)

        assert level_status is not None
        assert level_status.status == "running"

    def test_reset_task(self, sample_task_graph) -> None:
        """Test resetting a task to pending."""
        controller = LevelController()
        controller.initialize(sample_task_graph["tasks"])
        controller.start_level(1)
        controller.mark_task_complete("TASK-001")

        controller.reset_task("TASK-001")

        status = controller.get_task_status("TASK-001")
        assert status == TaskStatus.PENDING.value

    def test_get_task(self, sample_task_graph) -> None:
        """Test getting a task by ID."""
        controller = LevelController()
        controller.initialize(sample_task_graph["tasks"])

        task = controller.get_task("TASK-001")

        assert task is not None
        assert task["id"] == "TASK-001"

    def test_get_pending_tasks_for_level(self, sample_task_graph) -> None:
        """Test getting pending tasks for a level."""
        controller = LevelController()
        controller.initialize(sample_task_graph["tasks"])
        controller.start_level(1)

        pending = controller.get_pending_tasks_for_level(1)

        assert isinstance(pending, list)
        # All tasks should be pending initially
        all_tasks = controller.get_tasks_for_level(1)
        assert len(pending) == len(all_tasks)

    def test_level_not_complete_with_failed_tasks(self, sample_task_graph) -> None:
        """Test that level is not complete if any task failed."""
        controller = LevelController()
        controller.initialize(sample_task_graph["tasks"])
        controller.start_level(1)

        level_1_tasks = controller.get_tasks_for_level(1)
        # Complete all but mark one as failed
        controller.mark_task_failed(level_1_tasks[0], "test error")
        for task_id in level_1_tasks[1:]:
            controller.mark_task_complete(task_id)

        assert not controller.is_level_complete(1)
