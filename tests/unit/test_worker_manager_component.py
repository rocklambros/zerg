"""Tests for WorkerManager component."""

from unittest.mock import MagicMock, patch

import pytest

from zerg.config import ZergConfig
from zerg.constants import WorkerStatus
from zerg.launcher import WorkerLauncher
from zerg.levels import LevelController
from zerg.parser import TaskParser
from zerg.plugins import PluginRegistry
from zerg.ports import PortAllocator
from zerg.state import StateManager
from zerg.types import WorkerState
from zerg.worker_manager import WorkerManager
from zerg.worktree import WorktreeManager


@pytest.fixture
def mock_config():
    config = MagicMock(spec=ZergConfig)
    config.workers = MagicMock()
    config.workers.timeout_minutes = 30
    config.workers.retry_attempts = 3
    config.logging = MagicMock()
    config.logging.directory = ".zerg/logs"
    return config


@pytest.fixture
def mock_deps(mock_config, tmp_path):
    """Create all WorkerManager dependencies."""
    state = MagicMock(spec=StateManager)
    state._state = {"tasks": {}, "workers": {}}

    levels = MagicMock(spec=LevelController)
    levels.current_level = 1
    levels.get_pending_tasks_for_level.return_value = []

    parser = MagicMock(spec=TaskParser)
    parser.get_task.return_value = None

    launcher = MagicMock(spec=WorkerLauncher)
    spawn_result = MagicMock()
    spawn_result.success = True
    spawn_result.handle = MagicMock()
    spawn_result.handle.container_id = None
    spawn_result.error = None
    launcher.spawn.return_value = spawn_result
    launcher.monitor.return_value = WorkerStatus.RUNNING
    launcher.terminate.return_value = True

    worktrees = MagicMock(spec=WorktreeManager)
    wt_info = MagicMock()
    wt_info.path = tmp_path / "worktree"
    wt_info.branch = "zerg/test/worker-0"
    worktrees.create.return_value = wt_info
    worktrees.get_worktree_path.return_value = tmp_path / "worktree"

    ports = MagicMock(spec=PortAllocator)
    ports.allocate_one.return_value = 49152

    assigner = MagicMock()
    assigner.worker_count = 3

    plugin_registry = MagicMock(spec=PluginRegistry)
    workers: dict[int, WorkerState] = {}

    return {
        "feature": "test-feature",
        "config": mock_config,
        "state": state,
        "levels": levels,
        "parser": parser,
        "launcher": launcher,
        "worktrees": worktrees,
        "ports": ports,
        "assigner": assigner,
        "plugin_registry": plugin_registry,
        "workers": workers,
        "on_task_complete": [],
        "on_task_failure": None,
    }


@pytest.fixture
def worker_manager(mock_deps):
    return WorkerManager(**mock_deps)


class TestSpawnWorker:
    """Tests for spawn_worker."""

    def test_creates_worker_state(self, worker_manager, mock_deps):
        """spawn_worker creates a WorkerState and adds it to workers dict."""
        ws = worker_manager.spawn_worker(0)

        assert isinstance(ws, WorkerState)
        assert ws.worker_id == 0
        assert ws.status == WorkerStatus.RUNNING
        assert 0 in mock_deps["workers"]
        mock_deps["state"].set_worker_state.assert_called_once()

    def test_raises_on_spawn_failure(self, worker_manager, mock_deps):
        """spawn_worker raises RuntimeError on launcher failure."""
        fail_result = MagicMock()
        fail_result.success = False
        fail_result.error = "Spawn failed"
        mock_deps["launcher"].spawn.return_value = fail_result

        with pytest.raises(RuntimeError, match="Failed to spawn worker"):
            worker_manager.spawn_worker(0)


class TestSpawnWorkers:
    """Tests for spawn_workers."""

    def test_returns_count_of_successful_spawns(self, worker_manager):
        """spawn_workers returns number of successfully spawned workers."""
        count = worker_manager.spawn_workers(3)
        assert count == 3

    def test_continues_on_individual_failure(self, worker_manager, mock_deps):
        """spawn_workers continues past individual failures."""
        success_result = MagicMock()
        success_result.success = True
        success_result.handle = MagicMock()
        success_result.handle.container_id = None

        fail_result = MagicMock()
        fail_result.success = False
        fail_result.error = "Failed"

        mock_deps["launcher"].spawn.side_effect = [
            success_result,
            fail_result,
            success_result,
        ]

        count = worker_manager.spawn_workers(3)
        assert count == 2


class TestTerminateWorker:
    """Tests for terminate_worker."""

    def test_stops_and_cleans_up(self, worker_manager, mock_deps):
        """terminate_worker stops launcher, deletes worktree, releases port."""
        worker_manager.spawn_worker(0)

        worker_manager.terminate_worker(0)

        mock_deps["launcher"].terminate.assert_called_once_with(0, force=False)
        mock_deps["ports"].release.assert_called_once_with(49152)
        assert 0 not in mock_deps["workers"]

    def test_nonexistent_worker_is_noop(self, worker_manager, mock_deps):
        """Terminating a nonexistent worker does nothing."""
        worker_manager.terminate_worker(999)
        mock_deps["launcher"].terminate.assert_not_called()

    def test_handles_worktree_delete_failure(self, worker_manager, mock_deps):
        """Worktree deletion failure is handled gracefully."""
        worker_manager.spawn_worker(0)
        mock_deps["worktrees"].delete.side_effect = Exception("Delete failed")

        # Should not raise
        worker_manager.terminate_worker(0)
        assert 0 not in mock_deps["workers"]


class TestHandleWorkerExit:
    """Tests for handle_worker_exit."""

    def test_respawns_when_tasks_remain(self, worker_manager, mock_deps):
        """Worker is respawned when tasks remain for the level."""
        worker_manager.spawn_worker(0)
        mock_deps["levels"].get_pending_tasks_for_level.return_value = ["TASK-002"]
        worker_manager._running = True

        worker_manager.handle_worker_exit(0)

        # Worker should be respawned (spawn called twice: initial + respawn)
        assert mock_deps["launcher"].spawn.call_count == 2

    def test_no_respawn_when_not_running(self, worker_manager, mock_deps):
        """Worker is not respawned when _running is False."""
        worker_manager.spawn_worker(0)
        mock_deps["levels"].get_pending_tasks_for_level.return_value = ["TASK-002"]
        worker_manager._running = False

        worker_manager.handle_worker_exit(0)

        # Only the initial spawn
        assert mock_deps["launcher"].spawn.call_count == 1

    def test_completes_task_with_verification(self, worker_manager, mock_deps):
        """Worker exit marks task complete when verification exists."""
        worker_manager.spawn_worker(0)
        mock_deps["workers"][0].current_task = "TASK-001"
        mock_deps["parser"].get_task.return_value = {
            "id": "TASK-001",
            "verification": {"command": "echo ok"},
        }
        mock_deps["state"]._state = {"tasks": {"TASK-001": {"started_at": None}}}

        worker_manager.handle_worker_exit(0)

        mock_deps["levels"].mark_task_complete.assert_called_once_with("TASK-001")

    def test_noop_for_unknown_worker(self, worker_manager, mock_deps):
        """Exit for unknown worker is a no-op."""
        worker_manager.handle_worker_exit(999)
        mock_deps["levels"].mark_task_complete.assert_not_called()


class TestRespawnWorkersForLevel:
    """Tests for respawn_workers_for_level."""

    def test_spawns_needed_workers(self, worker_manager, mock_deps):
        """Spawns workers up to the needed count."""
        mock_deps["levels"].get_pending_tasks_for_level.return_value = ["T1", "T2"]

        with patch.object(worker_manager, "wait_for_initialization"):
            count = worker_manager.respawn_workers_for_level(2)

        assert count > 0

    def test_returns_zero_when_no_tasks(self, worker_manager, mock_deps):
        """Returns 0 when no remaining tasks."""
        mock_deps["levels"].get_pending_tasks_for_level.return_value = []

        count = worker_manager.respawn_workers_for_level(2)
        assert count == 0


class TestRunningProperty:
    """Tests for running property."""

    def test_running_getter_setter(self, worker_manager):
        """Running property works correctly."""
        assert worker_manager.running is False
        worker_manager.running = True
        assert worker_manager.running is True
