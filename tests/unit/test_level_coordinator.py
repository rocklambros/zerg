"""Tests for LevelCoordinator component."""

from unittest.mock import MagicMock, patch

import pytest

from zerg.config import ZergConfig
from zerg.constants import LevelMergeStatus
from zerg.level_coordinator import LevelCoordinator
from zerg.levels import LevelController
from zerg.merge import MergeCoordinator, MergeFlowResult
from zerg.parser import TaskParser
from zerg.plugins import PluginRegistry
from zerg.state import StateManager
from zerg.task_sync import TaskSyncBridge
from zerg.types import WorkerState


@pytest.fixture
def mock_config():
    config = MagicMock(spec=ZergConfig)
    config.merge_timeout_seconds = 10
    config.merge_max_retries = 2
    return config


@pytest.fixture
def mock_deps(mock_config):
    """Create all LevelCoordinator dependencies."""
    state = MagicMock(spec=StateManager)
    levels = MagicMock(spec=LevelController)
    levels.start_level.return_value = ["TASK-001", "TASK-002"]

    parser = MagicMock(spec=TaskParser)
    parser.get_task.side_effect = lambda tid: {"id": tid, "title": f"Task {tid}"}

    merger = MagicMock(spec=MergeCoordinator)
    task_sync = MagicMock(spec=TaskSyncBridge)
    plugin_registry = MagicMock(spec=PluginRegistry)
    workers: dict[int, WorkerState] = {}

    return {
        "feature": "test-feature",
        "config": mock_config,
        "state": state,
        "levels": levels,
        "parser": parser,
        "merger": merger,
        "task_sync": task_sync,
        "plugin_registry": plugin_registry,
        "workers": workers,
        "on_level_complete_callbacks": [],
    }


@pytest.fixture
def coordinator(mock_deps):
    return LevelCoordinator(**mock_deps)


class TestStartLevel:
    """Tests for start_level."""

    def test_initializes_state_and_creates_tasks(self, coordinator, mock_deps):
        """start_level sets level state and creates Claude Tasks."""
        coordinator.start_level(1)

        mock_deps["levels"].start_level.assert_called_once_with(1)
        mock_deps["state"].set_current_level.assert_called_once_with(1)
        mock_deps["state"].set_level_status.assert_called_once_with(1, "running")
        mock_deps["task_sync"].create_level_tasks.assert_called_once()

    def test_assigns_tasks_with_assigner(self, mock_deps):
        """Tasks are assigned to workers when assigner is present."""
        assigner = MagicMock()
        assigner.get_task_worker.return_value = 0
        mock_deps["assigner"] = assigner

        coord = LevelCoordinator(**mock_deps)
        coord.start_level(1)

        assert mock_deps["state"].set_task_status.call_count == 2

    def test_skips_claude_tasks_when_parser_returns_none(self, mock_deps):
        """No Claude Tasks created when parser returns None for all tasks."""
        mock_deps["parser"].get_task.side_effect = lambda _: None

        coord = LevelCoordinator(**mock_deps)
        coord.start_level(1)

        mock_deps["task_sync"].create_level_tasks.assert_not_called()


class TestHandleLevelComplete:
    """Tests for handle_level_complete."""

    @patch("time.sleep")
    def test_succeeds_with_merge(self, mock_sleep, coordinator, mock_deps):
        """Level completion succeeds when merge passes."""
        merge_result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["b1"],
            target_branch="main",
            merge_commit="abc123",
        )
        mock_deps["merger"].full_merge_flow.return_value = merge_result

        # Add a worker with a branch so merge is called
        ws = MagicMock()
        ws.branch = "zerg/test/worker-0"
        mock_deps["workers"][0] = ws

        result = coordinator.handle_level_complete(1)

        assert result is True
        mock_deps["state"].set_level_status.assert_any_call(1, "complete", merge_commit="abc123")
        mock_deps["state"].set_level_merge_status.assert_any_call(1, LevelMergeStatus.COMPLETE)

    @patch("time.sleep")
    def test_fails_with_merge_failure(self, mock_sleep, coordinator, mock_deps):
        """Level completion fails when merge fails."""
        merge_result = MergeFlowResult(
            success=False,
            level=1,
            source_branches=["b1"],
            target_branch="main",
            error="Pre-merge gate failed",
        )
        mock_deps["merger"].full_merge_flow.return_value = merge_result

        ws = MagicMock()
        ws.branch = "zerg/test/worker-0"
        mock_deps["workers"][0] = ws

        result = coordinator.handle_level_complete(1)

        assert result is False
        mock_deps["state"].set_level_merge_status.assert_any_call(1, LevelMergeStatus.FAILED)

    @patch("time.sleep")
    def test_conflict_pauses_for_intervention(self, mock_sleep, coordinator, mock_deps):
        """Merge conflict triggers pause for intervention."""
        merge_result = MergeFlowResult(
            success=False,
            level=1,
            source_branches=["b1"],
            target_branch="main",
            error="CONFLICT in file.py",
        )
        mock_deps["merger"].full_merge_flow.return_value = merge_result

        ws = MagicMock()
        ws.branch = "zerg/test/worker-0"
        mock_deps["workers"][0] = ws

        coordinator.handle_level_complete(1)

        assert coordinator.paused is True
        mock_deps["state"].set_level_merge_status.assert_any_call(
            1, LevelMergeStatus.CONFLICT, details={"error": "CONFLICT in file.py"}
        )


class TestMergeLevel:
    """Tests for merge_level."""

    def test_collects_worker_branches(self, coordinator, mock_deps):
        """merge_level passes worker branches to merger."""
        ws = MagicMock()
        ws.branch = "zerg/test/worker-0"
        mock_deps["workers"][0] = ws

        merge_result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["zerg/test/worker-0"],
            target_branch="main",
        )
        mock_deps["merger"].full_merge_flow.return_value = merge_result

        result = coordinator.merge_level(1)

        mock_deps["merger"].full_merge_flow.assert_called_once_with(
            level=1,
            worker_branches=["zerg/test/worker-0"],
            target_branch="main",
        )
        assert result.success is True

    def test_handles_no_worker_branches(self, coordinator, mock_deps):
        """merge_level returns success with no branches to merge."""
        # No workers in dict
        result = coordinator.merge_level(1)

        assert result.success is True
        mock_deps["merger"].full_merge_flow.assert_not_called()


class TestPauseAndError:
    """Tests for pause_for_intervention and set_recoverable_error."""

    def test_pause_for_intervention_sets_paused(self, coordinator, mock_deps):
        """pause_for_intervention sets paused state."""
        coordinator.pause_for_intervention("Merge conflict")

        assert coordinator.paused is True
        mock_deps["state"].set_paused.assert_called_with(True)
        mock_deps["state"].append_event.assert_called_with("paused_for_intervention", {"reason": "Merge conflict"})

    def test_set_recoverable_error_sets_paused(self, coordinator, mock_deps):
        """set_recoverable_error pauses and records error."""
        coordinator.set_recoverable_error("Merge failed after retries")

        assert coordinator.paused is True
        mock_deps["state"].set_error.assert_called_with("Merge failed after retries")
        mock_deps["state"].set_paused.assert_called_with(True)
        mock_deps["state"].append_event.assert_called_with("recoverable_error", {"error": "Merge failed after retries"})

    def test_paused_property_default(self, coordinator):
        """Paused property defaults to False."""
        assert coordinator.paused is False

    def test_paused_property_setter(self, coordinator):
        """Paused property can be set."""
        coordinator.paused = True
        assert coordinator.paused is True
