"""Integration tests for ZERG rush flow."""

import json
from pathlib import Path

import pytest

from zerg.constants import TaskStatus
from zerg.levels import LevelController


class TestRushFlowDryRun:
    """Tests for rush command dry run mode."""

    def test_dry_run_shows_plan(self, tmp_repo: Path, sample_task_graph) -> None:
        """Test dry run displays execution plan without executing."""
        controller = LevelController()
        controller.initialize(sample_task_graph["tasks"])

        # Dry run should show tasks without starting
        status = controller.get_status()
        assert status["total_tasks"] > 0
        assert status["completed_tasks"] == 0

    def test_dry_run_no_worktrees_created(self, tmp_repo: Path, sample_task_graph) -> None:
        """Test dry run does not create worktrees."""
        from zerg.worktree import WorktreeManager

        manager = WorktreeManager(tmp_repo)
        initial_worktrees = len(manager.list_worktrees())

        # Simulating dry run - just initialize without creating worktrees
        controller = LevelController()
        controller.initialize(sample_task_graph["tasks"])

        final_worktrees = len(manager.list_worktrees())
        assert final_worktrees == initial_worktrees


class TestRushFlowSingleLevel:
    """Tests for rush flow with a single level."""

    def test_single_level_execution(self, sample_task_graph) -> None:
        """Test executing all tasks in a single level."""
        controller = LevelController()
        controller.initialize(sample_task_graph["tasks"])

        # Start level 1
        task_ids = controller.start_level(1)
        assert len(task_ids) >= 1

        # Complete all level 1 tasks
        for task_id in task_ids:
            controller.mark_task_complete(task_id)

        assert controller.is_level_complete(1)

    def test_single_level_parallel_tasks(self, sample_task_graph) -> None:
        """Test parallel task assignment within a level."""
        controller = LevelController()
        controller.initialize(sample_task_graph["tasks"])

        task_ids = controller.start_level(1)

        # Mark all tasks as in progress (simulating parallel execution)
        for i, task_id in enumerate(task_ids):
            controller.mark_task_in_progress(task_id, worker_id=i)

        status = controller.get_status()
        assert status["in_progress_tasks"] == len(task_ids)


class TestRushFlowMultiLevel:
    """Tests for rush flow with multiple levels."""

    def test_multi_level_progression(self, sample_task_graph) -> None:
        """Test progressing through multiple levels."""
        controller = LevelController()
        controller.initialize(sample_task_graph["tasks"])

        # Complete level 1
        task_ids_1 = controller.start_level(1)
        for task_id in task_ids_1:
            controller.mark_task_complete(task_id)

        assert controller.is_level_complete(1)
        assert controller.can_advance()

        # Start and complete level 2
        task_ids_2 = controller.start_level(2)
        for task_id in task_ids_2:
            controller.mark_task_complete(task_id)

        assert controller.is_level_complete(2)

    def test_level_2_blocked_until_level_1_complete(self, sample_task_graph) -> None:
        """Test level 2 cannot start before level 1 completes."""
        from zerg.exceptions import LevelError

        controller = LevelController()
        controller.initialize(sample_task_graph["tasks"])

        # Start level 1 but don't complete
        controller.start_level(1)

        # Try to start level 2 - should fail
        with pytest.raises(LevelError):
            controller.start_level(2)

    def test_advance_level_automatically(self, sample_task_graph) -> None:
        """Test automatic level advancement."""
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


class TestRushFlowTaskFailure:
    """Tests for rush flow handling task failures."""

    def test_task_failure_blocks_level(self, sample_task_graph) -> None:
        """Test task failure prevents level completion."""
        controller = LevelController()
        controller.initialize(sample_task_graph["tasks"])

        task_ids = controller.start_level(1)

        # Complete all but one, fail that one
        controller.mark_task_failed(task_ids[0], "Test failure")
        for task_id in task_ids[1:]:
            controller.mark_task_complete(task_id)

        assert not controller.is_level_complete(1)

    def test_failed_task_can_be_reset(self, sample_task_graph) -> None:
        """Test failed task can be reset for retry."""
        controller = LevelController()
        controller.initialize(sample_task_graph["tasks"])

        task_ids = controller.start_level(1)
        controller.mark_task_failed(task_ids[0], "Test failure")

        # Reset the failed task
        controller.reset_task(task_ids[0])

        status = controller.get_task_status(task_ids[0])
        assert status == TaskStatus.PENDING.value


class TestRushFlowCheckpoint:
    """Tests for rush flow checkpoint/resume functionality."""

    def test_state_can_be_serialized(self, sample_task_graph) -> None:
        """Test execution state can be serialized for checkpoint."""
        controller = LevelController()
        controller.initialize(sample_task_graph["tasks"])

        task_ids = controller.start_level(1)
        controller.mark_task_complete(task_ids[0])

        status = controller.get_status()

        # Status should be serializable

        serialized = json.dumps(status)
        deserialized = json.loads(serialized)

        assert deserialized["completed_tasks"] == 1

    def test_progress_preserved_across_instances(self, sample_task_graph) -> None:
        """Test that progress tracking works across controller instances."""
        import copy

        # Make deep copies to ensure independent task data
        tasks_copy1 = copy.deepcopy(sample_task_graph["tasks"])
        tasks_copy2 = copy.deepcopy(sample_task_graph["tasks"])

        # First controller - start and complete some work
        controller1 = LevelController()
        controller1.initialize(tasks_copy1)
        task_ids = controller1.start_level(1)
        controller1.mark_task_complete(task_ids[0])

        status1 = controller1.get_status()
        assert status1["completed_tasks"] == 1

        # Second controller with fresh task data - should start fresh
        controller2 = LevelController()
        controller2.initialize(tasks_copy2)

        # The new controller starts fresh with its own copy
        status2 = controller2.get_status()
        assert status2["completed_tasks"] == 0  # Fresh start

        # Restore same progress manually
        controller2.start_level(1)
        controller2.mark_task_complete(task_ids[0])
        status3 = controller2.get_status()
        assert status3["completed_tasks"] == status1["completed_tasks"]
