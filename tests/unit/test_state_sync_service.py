"""Tests for StateSyncService component."""

from unittest.mock import MagicMock

import pytest

from zerg.constants import TaskStatus
from zerg.levels import LevelController
from zerg.state import StateManager
from zerg.state_sync_service import StateSyncService


@pytest.fixture
def mock_state():
    state = MagicMock(spec=StateManager)
    state._state = {"tasks": {}, "workers": {}}
    return state


@pytest.fixture
def mock_levels():
    levels = MagicMock(spec=LevelController)
    levels.get_task_status.return_value = None
    return levels


@pytest.fixture
def sync_service(mock_state, mock_levels):
    return StateSyncService(state=mock_state, levels=mock_levels)


class TestSyncFromDisk:
    """Tests for sync_from_disk."""

    def test_syncs_completed_tasks(self, sync_service, mock_state, mock_levels):
        """Completed task on disk is synced to LevelController."""
        mock_state._state = {
            "tasks": {
                "TASK-001": {"status": TaskStatus.COMPLETE.value},
            }
        }
        mock_levels.get_task_status.return_value = TaskStatus.PENDING.value

        sync_service.sync_from_disk()

        mock_levels.mark_task_complete.assert_called_once_with("TASK-001")

    def test_syncs_failed_tasks(self, sync_service, mock_state, mock_levels):
        """Failed task on disk is synced to LevelController."""
        mock_state._state = {
            "tasks": {
                "TASK-001": {"status": TaskStatus.FAILED.value},
            }
        }
        mock_levels.get_task_status.return_value = TaskStatus.PENDING.value

        sync_service.sync_from_disk()

        mock_levels.mark_task_failed.assert_called_once_with("TASK-001")

    def test_syncs_in_progress_tasks(self, sync_service, mock_state, mock_levels):
        """In-progress task on disk is synced to LevelController."""
        mock_state._state = {
            "tasks": {
                "TASK-001": {"status": TaskStatus.IN_PROGRESS.value, "worker_id": 0},
            }
        }
        mock_levels.get_task_status.return_value = TaskStatus.PENDING.value

        sync_service.sync_from_disk()

        mock_levels.mark_task_in_progress.assert_called_once_with("TASK-001", 0)

    def test_skips_already_synced_tasks(self, sync_service, mock_state, mock_levels):
        """Already-synced complete task is not re-synced."""
        mock_state._state = {
            "tasks": {
                "TASK-001": {"status": TaskStatus.COMPLETE.value},
            }
        }
        mock_levels.get_task_status.return_value = TaskStatus.COMPLETE.value

        sync_service.sync_from_disk()

        mock_levels.mark_task_complete.assert_not_called()


class TestReassignStrandedTasks:
    """Tests for reassign_stranded_tasks."""

    def test_clears_dead_worker_assignments(self, sync_service, mock_state):
        """Pending tasks on dead workers are unassigned."""
        mock_state._state = {
            "tasks": {
                "TASK-001": {"status": "pending", "worker_id": 5},
            }
        }
        active_workers = {1, 2, 3}  # Worker 5 is dead

        sync_service.reassign_stranded_tasks(active_workers)

        assert mock_state._state["tasks"]["TASK-001"]["worker_id"] is None
        mock_state.save.assert_called_once()

    def test_preserves_active_worker_assignments(self, sync_service, mock_state):
        """Pending tasks on active workers keep their assignment."""
        mock_state._state = {
            "tasks": {
                "TASK-001": {"status": "pending", "worker_id": 2},
            }
        }
        active_workers = {1, 2, 3}

        sync_service.reassign_stranded_tasks(active_workers)

        assert mock_state._state["tasks"]["TASK-001"]["worker_id"] == 2

    def test_ignores_completed_tasks(self, sync_service, mock_state):
        """Completed tasks are not reassigned even if worker is dead."""
        mock_state._state = {
            "tasks": {
                "TASK-001": {"status": TaskStatus.COMPLETE.value, "worker_id": 5},
            }
        }
        active_workers = {1, 2}

        sync_service.reassign_stranded_tasks(active_workers)

        # Worker ID should remain unchanged (status isn't pending/todo)
        assert mock_state._state["tasks"]["TASK-001"]["worker_id"] == 5
