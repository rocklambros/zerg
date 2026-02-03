"""Extended unit tests for levels controller (TC-022).

Tests edge cases and error conditions for LevelController.
"""

import pytest

from zerg.constants import TaskStatus
from zerg.exceptions import LevelError
from zerg.levels import LevelController


@pytest.fixture
def sample_tasks():
    """Create sample tasks for testing."""
    return [
        {"id": "TASK-001", "level": 1, "title": "Task 1"},
        {"id": "TASK-002", "level": 1, "title": "Task 2"},
        {"id": "TASK-003", "level": 2, "title": "Task 3"},
        {"id": "TASK-004", "level": 2, "title": "Task 4"},
        {"id": "TASK-005", "level": 3, "title": "Task 5"},
    ]


class TestLevelControllerInit:
    """Tests for LevelController initialization."""

    def test_init_empty(self) -> None:
        """Test initialization creates empty state."""
        controller = LevelController()

        assert controller.current_level == 0
        assert controller.total_levels == 0
        assert not controller._started

    def test_init_levels_empty(self) -> None:
        """Test levels dict is empty on init."""
        controller = LevelController()

        assert len(controller._levels) == 0

    def test_init_tasks_empty(self) -> None:
        """Test tasks dict is empty on init."""
        controller = LevelController()

        assert len(controller._tasks) == 0


class TestInitialize:
    """Tests for initialize method."""

    def test_initialize_with_tasks(self, sample_tasks) -> None:
        """Test initializing with tasks."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        assert controller.total_levels == 3
        assert len(controller._tasks) == 5

    def test_initialize_creates_levels(self, sample_tasks) -> None:
        """Test initialize creates level structures."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        assert 1 in controller._levels
        assert 2 in controller._levels
        assert 3 in controller._levels

    def test_initialize_level_task_counts(self, sample_tasks) -> None:
        """Test level task counts are correct."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        assert controller._levels[1].total_tasks == 2
        assert controller._levels[2].total_tasks == 2
        assert controller._levels[3].total_tasks == 1

    def test_initialize_clears_previous(self, sample_tasks) -> None:
        """Test initialize clears previous state."""
        controller = LevelController()
        controller.initialize(sample_tasks)
        controller._current_level = 2
        controller._started = True

        # Reinitialize
        controller.initialize([{"id": "NEW-001", "level": 1, "title": "New"}])

        assert controller.current_level == 0
        assert not controller._started
        assert controller.total_levels == 1

    def test_initialize_empty_tasks(self) -> None:
        """Test initializing with empty task list."""
        controller = LevelController()
        controller.initialize([])

        assert controller.total_levels == 0
        assert len(controller._tasks) == 0


class TestStartLevel:
    """Tests for starting levels."""

    def test_start_level_one(self, sample_tasks) -> None:
        """Test starting level 1."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        tasks = controller.start_level(1)

        assert len(tasks) == 2
        assert controller.current_level == 1
        assert controller._started is True

    def test_start_level_nonexistent(self, sample_tasks) -> None:
        """Test starting nonexistent level raises error."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        with pytest.raises(LevelError, match="does not exist"):
            controller.start_level(99)

    def test_start_level_out_of_order(self, sample_tasks) -> None:
        """Test starting level before previous is complete."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        with pytest.raises(LevelError, match="not complete"):
            controller.start_level(2)

    def test_start_level_sets_status(self, sample_tasks) -> None:
        """Test starting level sets status to running."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        controller.start_level(1)

        assert controller._levels[1].status == "running"

    def test_start_level_sets_started_at(self, sample_tasks) -> None:
        """Test starting level sets started_at timestamp."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        controller.start_level(1)

        assert controller._levels[1].started_at is not None


class TestGetTasks:
    """Tests for getting tasks."""

    def test_get_tasks_for_level(self, sample_tasks) -> None:
        """Test getting tasks for a level."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        tasks = controller.get_tasks_for_level(1)

        assert len(tasks) == 2
        assert "TASK-001" in tasks
        assert "TASK-002" in tasks

    def test_get_tasks_for_nonexistent_level(self, sample_tasks) -> None:
        """Test getting tasks for nonexistent level."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        tasks = controller.get_tasks_for_level(99)

        assert tasks == []

    def test_get_pending_tasks_for_level(self, sample_tasks) -> None:
        """Test getting pending tasks."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        pending = controller.get_pending_tasks_for_level(1)

        assert len(pending) == 2

    def test_get_pending_excludes_complete(self, sample_tasks) -> None:
        """Test pending tasks excludes completed."""
        controller = LevelController()
        controller.initialize(sample_tasks)
        controller.start_level(1)
        controller.mark_task_complete("TASK-001")

        pending = controller.get_pending_tasks_for_level(1)

        assert "TASK-001" not in pending
        assert "TASK-002" in pending


class TestMarkTaskComplete:
    """Tests for marking tasks complete."""

    def test_mark_task_complete(self, sample_tasks) -> None:
        """Test marking a task complete."""
        controller = LevelController()
        controller.initialize(sample_tasks)
        controller.start_level(1)

        controller.mark_task_complete("TASK-001")

        assert controller._tasks["TASK-001"]["status"] == TaskStatus.COMPLETE.value
        assert controller._levels[1].completed_tasks == 1

    def test_mark_task_complete_returns_true_on_level_complete(self, sample_tasks) -> None:
        """Test returns True when level completes."""
        controller = LevelController()
        controller.initialize(sample_tasks)
        controller.start_level(1)
        controller.mark_task_complete("TASK-001")

        result = controller.mark_task_complete("TASK-002")

        assert result is True

    def test_mark_task_complete_returns_false_when_more_tasks(self, sample_tasks) -> None:
        """Test returns False when more tasks remain."""
        controller = LevelController()
        controller.initialize(sample_tasks)
        controller.start_level(1)

        result = controller.mark_task_complete("TASK-001")

        assert result is False

    def test_mark_unknown_task_complete(self, sample_tasks) -> None:
        """Test marking unknown task returns False."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        result = controller.mark_task_complete("UNKNOWN")

        assert result is False


class TestMarkTaskFailed:
    """Tests for marking tasks failed."""

    def test_mark_task_failed(self, sample_tasks) -> None:
        """Test marking a task failed."""
        controller = LevelController()
        controller.initialize(sample_tasks)
        controller.start_level(1)

        controller.mark_task_failed("TASK-001", "Test error")

        assert controller._tasks["TASK-001"]["status"] == TaskStatus.FAILED.value
        assert controller._levels[1].failed_tasks == 1

    def test_mark_unknown_task_failed(self, sample_tasks) -> None:
        """Test marking unknown task failed does nothing."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        # Should not raise
        controller.mark_task_failed("UNKNOWN")


class TestMarkTaskInProgress:
    """Tests for marking tasks in progress."""

    def test_mark_task_in_progress(self, sample_tasks) -> None:
        """Test marking a task in progress."""
        controller = LevelController()
        controller.initialize(sample_tasks)
        controller.start_level(1)

        controller.mark_task_in_progress("TASK-001", worker_id=1)

        assert controller._tasks["TASK-001"]["status"] == TaskStatus.IN_PROGRESS.value
        assert controller._tasks["TASK-001"]["assigned_worker"] == 1
        assert controller._levels[1].in_progress_tasks == 1

    def test_mark_task_in_progress_without_worker(self, sample_tasks) -> None:
        """Test marking in progress without worker ID."""
        controller = LevelController()
        controller.initialize(sample_tasks)
        controller.start_level(1)

        controller.mark_task_in_progress("TASK-001")

        assert controller._tasks["TASK-001"]["status"] == TaskStatus.IN_PROGRESS.value

    def test_mark_unknown_task_in_progress(self, sample_tasks) -> None:
        """Test marking unknown task does nothing."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        # Should not raise
        controller.mark_task_in_progress("UNKNOWN")


class TestIsLevelComplete:
    """Tests for checking level completion."""

    def test_is_level_complete_false_initially(self, sample_tasks) -> None:
        """Test level is not complete initially."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        assert controller.is_level_complete(1) is False

    def test_is_level_complete_true_all_done(self, sample_tasks) -> None:
        """Test level is complete when all tasks done."""
        controller = LevelController()
        controller.initialize(sample_tasks)
        controller.start_level(1)
        controller.mark_task_complete("TASK-001")
        controller.mark_task_complete("TASK-002")

        assert controller.is_level_complete(1) is True

    def test_is_level_complete_with_failures(self, sample_tasks) -> None:
        """Test level is not complete when tasks have failed, but is resolved."""
        controller = LevelController()
        controller.initialize(sample_tasks)
        controller.start_level(1)
        controller.mark_task_complete("TASK-001")
        controller.mark_task_failed("TASK-002")

        # Level is NOT complete (has failures)
        assert controller.is_level_complete(1) is False
        # But level IS resolved (all tasks in terminal state)
        assert controller.is_level_resolved(1) is True

    def test_is_level_complete_nonexistent(self, sample_tasks) -> None:
        """Test nonexistent level returns False."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        assert controller.is_level_complete(99) is False


class TestCanAdvance:
    """Tests for checking if can advance."""

    def test_can_advance_initially(self, sample_tasks) -> None:
        """Test can advance initially (to start level 1)."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        assert controller.can_advance() is True

    def test_can_advance_after_level_complete(self, sample_tasks) -> None:
        """Test can advance after level complete."""
        controller = LevelController()
        controller.initialize(sample_tasks)
        controller.start_level(1)
        controller.mark_task_complete("TASK-001")
        controller.mark_task_complete("TASK-002")

        assert controller.can_advance() is True

    def test_cannot_advance_level_incomplete(self, sample_tasks) -> None:
        """Test cannot advance with incomplete level."""
        controller = LevelController()
        controller.initialize(sample_tasks)
        controller.start_level(1)

        assert controller.can_advance() is False

    def test_cannot_advance_last_level(self) -> None:
        """Test cannot advance past last level."""
        tasks = [{"id": "T1", "level": 1, "title": "Only task"}]
        controller = LevelController()
        controller.initialize(tasks)
        controller.start_level(1)
        controller.mark_task_complete("T1")

        assert controller.can_advance() is False


class TestAdvanceLevel:
    """Tests for advancing levels."""

    def test_advance_level(self, sample_tasks) -> None:
        """Test advancing to next level."""
        controller = LevelController()
        controller.initialize(sample_tasks)
        controller.start_level(1)
        controller.mark_task_complete("TASK-001")
        controller.mark_task_complete("TASK-002")

        new_level = controller.advance_level()

        assert new_level == 2
        assert controller.current_level == 2

    def test_advance_level_from_start(self, sample_tasks) -> None:
        """Test advancing from unstarted state."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        new_level = controller.advance_level()

        assert new_level == 1

    def test_advance_level_returns_none_at_end(self) -> None:
        """Test advance returns None at end."""
        tasks = [{"id": "T1", "level": 1, "title": "Only task"}]
        controller = LevelController()
        controller.initialize(tasks)
        controller.start_level(1)
        controller.mark_task_complete("T1")

        result = controller.advance_level()

        assert result is None


class TestGetStatus:
    """Tests for getting status."""

    def test_get_status_initial(self, sample_tasks) -> None:
        """Test status after initialization."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        status = controller.get_status()

        assert status["current_level"] == 0
        assert status["total_tasks"] == 5
        assert status["completed_tasks"] == 0
        assert status["is_complete"] is False

    def test_get_status_in_progress(self, sample_tasks) -> None:
        """Test status during execution."""
        controller = LevelController()
        controller.initialize(sample_tasks)
        controller.start_level(1)
        controller.mark_task_complete("TASK-001")

        status = controller.get_status()

        assert status["completed_tasks"] == 1
        assert status["progress_percent"] == 20.0

    def test_get_status_complete(self) -> None:
        """Test status when complete."""
        tasks = [{"id": "T1", "level": 1, "title": "Only"}]
        controller = LevelController()
        controller.initialize(tasks)
        controller.start_level(1)
        controller.mark_task_complete("T1")

        status = controller.get_status()

        assert status["is_complete"] is True
        assert status["progress_percent"] == 100.0


class TestResetTask:
    """Tests for resetting tasks."""

    def test_reset_complete_task(self, sample_tasks) -> None:
        """Test resetting a complete task."""
        controller = LevelController()
        controller.initialize(sample_tasks)
        controller.start_level(1)
        controller.mark_task_complete("TASK-001")

        controller.reset_task("TASK-001")

        assert controller._tasks["TASK-001"]["status"] == TaskStatus.PENDING.value
        assert controller._levels[1].completed_tasks == 0

    def test_reset_failed_task(self, sample_tasks) -> None:
        """Test resetting a failed task."""
        controller = LevelController()
        controller.initialize(sample_tasks)
        controller.start_level(1)
        controller.mark_task_failed("TASK-001")

        controller.reset_task("TASK-001")

        assert controller._tasks["TASK-001"]["status"] == TaskStatus.PENDING.value
        assert controller._levels[1].failed_tasks == 0

    def test_reset_in_progress_task(self, sample_tasks) -> None:
        """Test resetting an in-progress task."""
        controller = LevelController()
        controller.initialize(sample_tasks)
        controller.start_level(1)
        controller.mark_task_in_progress("TASK-001")

        controller.reset_task("TASK-001")

        assert controller._tasks["TASK-001"]["status"] == TaskStatus.PENDING.value
        assert controller._levels[1].in_progress_tasks == 0

    def test_reset_unknown_task(self, sample_tasks) -> None:
        """Test resetting unknown task does nothing."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        # Should not raise
        controller.reset_task("UNKNOWN")


class TestGetMethods:
    """Tests for getter methods."""

    def test_get_level_status(self, sample_tasks) -> None:
        """Test getting level status."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        status = controller.get_level_status(1)

        assert status is not None
        assert status.total_tasks == 2

    def test_get_level_status_nonexistent(self, sample_tasks) -> None:
        """Test getting nonexistent level returns None."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        status = controller.get_level_status(99)

        assert status is None

    def test_get_task(self, sample_tasks) -> None:
        """Test getting a task."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        task = controller.get_task("TASK-001")

        assert task is not None
        assert task["id"] == "TASK-001"

    def test_get_task_nonexistent(self, sample_tasks) -> None:
        """Test getting nonexistent task returns None."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        task = controller.get_task("UNKNOWN")

        assert task is None

    def test_get_task_status(self, sample_tasks) -> None:
        """Test getting task status."""
        controller = LevelController()
        controller.initialize(sample_tasks)
        controller.start_level(1)
        controller.mark_task_complete("TASK-001")

        status = controller.get_task_status("TASK-001")

        assert status == TaskStatus.COMPLETE.value

    def test_get_task_status_nonexistent(self, sample_tasks) -> None:
        """Test getting status of nonexistent task."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        status = controller.get_task_status("UNKNOWN")

        assert status is None


class TestProperties:
    """Tests for properties."""

    def test_current_level_property(self, sample_tasks) -> None:
        """Test current_level property."""
        controller = LevelController()
        controller.initialize(sample_tasks)
        controller.start_level(1)

        assert controller.current_level == 1

    def test_total_levels_property(self, sample_tasks) -> None:
        """Test total_levels property."""
        controller = LevelController()
        controller.initialize(sample_tasks)

        assert controller.total_levels == 3
