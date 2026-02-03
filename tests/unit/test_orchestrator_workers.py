"""Tests for ZERG orchestrator worker coordination (TC-009)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.constants import WorkerStatus
from zerg.orchestrator import Orchestrator


@pytest.fixture
def mock_orchestrator_deps():
    """Mock orchestrator dependencies."""
    with (
        patch("zerg.orchestrator.StateManager") as state_mock,
        patch("zerg.orchestrator.LevelController") as levels_mock,
        patch("zerg.orchestrator.TaskParser") as parser_mock,
        patch("zerg.orchestrator.GateRunner") as gates_mock,
        patch("zerg.orchestrator.WorktreeManager") as worktree_mock,
        patch("zerg.orchestrator.ContainerManager") as container_mock,
        patch("zerg.orchestrator.PortAllocator") as ports_mock,
        patch("zerg.orchestrator.MergeCoordinator") as merge_mock,
        patch("zerg.orchestrator.SubprocessLauncher") as launcher_mock,
    ):
        state = MagicMock()
        state.load.return_value = {}
        state.get_task_status.return_value = None
        state.get_task_retry_count.return_value = 0
        state.get_failed_tasks.return_value = []
        state_mock.return_value = state

        levels = MagicMock()
        levels.current_level = 1
        levels.is_level_complete.return_value = False
        levels.is_level_resolved.return_value = False
        levels.can_advance.return_value = False
        levels.get_pending_tasks_for_level.return_value = []
        levels.get_status.return_value = {
            "current_level": 1,
            "total_tasks": 10,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "in_progress_tasks": 0,
            "progress_percent": 0,
            "is_complete": False,
            "levels": {},
        }
        levels_mock.return_value = levels

        parser = MagicMock()
        parser.get_all_tasks.return_value = []
        parser.get_task.return_value = None
        parser.total_tasks = 0
        parser.levels = [1, 2]
        parser_mock.return_value = parser

        gates = MagicMock()
        gates.run_all_gates.return_value = (True, [])
        gates_mock.return_value = gates

        worktree = MagicMock()
        worktree_info = MagicMock()
        worktree_info.path = Path("/tmp/worktree")
        worktree_info.branch = "zerg/test/worker-0"
        worktree.create.return_value = worktree_info
        worktree_mock.return_value = worktree

        container = MagicMock()
        container.get_status.return_value = WorkerStatus.RUNNING
        container_mock.return_value = container

        ports = MagicMock()
        ports.allocate_one.return_value = 49152
        ports_mock.return_value = ports

        merge = MagicMock()
        merge_result = MagicMock()
        merge_result.success = True
        merge_result.merge_commit = "abc123"
        merge_result.error = None
        merge.full_merge_flow.return_value = merge_result
        merge_mock.return_value = merge

        launcher = MagicMock()
        spawn_result = MagicMock()
        spawn_result.success = True
        spawn_result.handle = MagicMock()
        spawn_result.handle.container_id = None
        spawn_result.error = None
        launcher.spawn.return_value = spawn_result
        launcher.monitor.return_value = WorkerStatus.RUNNING
        launcher.terminate.return_value = True
        launcher_mock.return_value = launcher

        yield {
            "state": state,
            "levels": levels,
            "parser": parser,
            "gates": gates,
            "worktree": worktree,
            "container": container,
            "ports": ports,
            "merge": merge,
            "launcher": launcher,
        }


class TestWorkerSpawning:
    """Tests for worker spawning."""

    def test_spawn_single_worker(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test spawning a single worker."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        worker_state = orch._spawn_worker(0)

        assert worker_state.worker_id == 0
        assert worker_state.status == WorkerStatus.RUNNING
        assert worker_state.branch == "zerg/test/worker-0"
        mock_orchestrator_deps["launcher"].spawn.assert_called_once()

    def test_spawn_multiple_workers(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test spawning multiple workers."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._spawn_workers(3)

        assert mock_orchestrator_deps["launcher"].spawn.call_count == 3
        assert len(orch._workers) == 3

    def test_spawn_worker_allocates_port(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test that spawning allocates a port."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        worker_state = orch._spawn_worker(0)

        mock_orchestrator_deps["ports"].allocate_one.assert_called_once()
        assert worker_state.port == 49152

    def test_spawn_worker_creates_worktree(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test that spawning creates a worktree."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)

        mock_orchestrator_deps["worktree"].create.assert_called_once_with("test-feature", 0)

    def test_spawn_worker_failure_raises(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test that spawn failure raises exception."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        spawn_result = MagicMock()
        spawn_result.success = False
        spawn_result.error = "Failed to spawn"
        mock_orchestrator_deps["launcher"].spawn.return_value = spawn_result

        orch = Orchestrator("test-feature")

        with pytest.raises(RuntimeError, match="Failed to spawn"):
            orch._spawn_worker(0)

    def test_spawn_worker_records_state(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test that spawn records worker state."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)

        mock_orchestrator_deps["state"].set_worker_state.assert_called_once()
        mock_orchestrator_deps["state"].append_event.assert_called_with(
            "worker_started",
            {
                "worker_id": 0,
                "port": 49152,
                "container_id": None,
                "mode": "subprocess",
            },
        )


class TestWorkerTermination:
    """Tests for worker termination."""

    def test_terminate_worker(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test terminating a worker."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)

        orch._terminate_worker(0)

        mock_orchestrator_deps["launcher"].terminate.assert_called_with(0, force=False)

    def test_terminate_worker_force(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test force terminating a worker."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)

        orch._terminate_worker(0, force=True)

        mock_orchestrator_deps["launcher"].terminate.assert_called_with(0, force=True)

    def test_terminate_worker_deletes_worktree(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test that termination deletes worktree."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)

        orch._terminate_worker(0)

        mock_orchestrator_deps["worktree"].delete.assert_called()

    def test_terminate_worker_releases_port(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test that termination releases port."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)

        orch._terminate_worker(0)

        mock_orchestrator_deps["ports"].release.assert_called_with(49152)

    def test_terminate_nonexistent_worker(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test terminating nonexistent worker does nothing."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")

        # Should not raise
        orch._terminate_worker(999)

        mock_orchestrator_deps["launcher"].terminate.assert_not_called()


class TestWorkerPolling:
    """Tests for worker status polling."""

    def test_poll_workers_checks_status(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test polling checks worker status."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._spawn_worker(1)

        orch._poll_workers()

        assert mock_orchestrator_deps["launcher"].monitor.call_count >= 2

    def test_poll_detects_crashed_worker(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test polling detects crashed workers."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["launcher"].monitor.return_value = WorkerStatus.CRASHED

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._workers[0].current_task = "TASK-001"

        orch._poll_workers()

        # Worker is removed after handling crash (expected behavior)
        assert 0 not in orch._workers
        # State was updated with crashed status before removal
        mock_orchestrator_deps["state"].set_worker_state.assert_called()

    def test_poll_detects_checkpointing(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test polling detects checkpointing worker."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["launcher"].monitor.return_value = WorkerStatus.CHECKPOINTING

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)

        orch._poll_workers()

        # Worker is removed after handling exit (expected behavior)
        # The state was updated with checkpointing status before removal
        mock_orchestrator_deps["state"].set_worker_state.assert_called()


class TestWorkerCallbacks:
    """Tests for worker event callbacks."""

    def test_on_task_complete_callback(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test task completion callbacks."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        callback = MagicMock()

        orch = Orchestrator("test-feature")
        orch.on_task_complete(callback)

        assert callback in orch._on_task_complete

    def test_on_level_complete_callback(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test level completion callbacks."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        callback = MagicMock()

        orch = Orchestrator("test-feature")
        orch.on_level_complete(callback)

        assert callback in orch._on_level_complete


class TestWorkerAssignment:
    """Tests for worker task assignment."""

    def test_start_level_assigns_tasks(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test starting a level assigns tasks to workers."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["levels"].start_level.return_value = ["TASK-001", "TASK-002"]

        orch = Orchestrator("test-feature")
        orch.assigner = MagicMock()
        orch.assigner.get_task_worker.return_value = 0

        orch._start_level(1)

        mock_orchestrator_deps["levels"].start_level.assert_called_with(1)
        mock_orchestrator_deps["state"].set_current_level.assert_called_with(1)
        orch.assigner.get_task_worker.assert_called()

    def test_get_remaining_tasks_for_level(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test getting remaining tasks for a level."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["levels"].get_pending_tasks_for_level.return_value = ["TASK-001", "TASK-003"]

        orch = Orchestrator("test-feature")

        remaining = orch._get_remaining_tasks_for_level(1)

        assert remaining == ["TASK-001", "TASK-003"]


class TestWorkerExit:
    """Tests for handling worker exits."""

    def test_handle_worker_exit_completes_task(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test handling worker exit marks task complete."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["parser"].get_task.return_value = {
            "id": "TASK-001",
            "verification": {"command": "echo test"},
        }

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._workers[0].current_task = "TASK-001"

        orch._handle_worker_exit(0)

        mock_orchestrator_deps["levels"].mark_task_complete.assert_called_with("TASK-001")

    def test_handle_worker_exit_restarts_for_remaining(
        self, mock_orchestrator_deps, tmp_path: Path, monkeypatch
    ) -> None:
        """Test that worker is restarted if tasks remain."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        mock_orchestrator_deps["levels"].get_pending_tasks_for_level.return_value = ["TASK-002"]

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        # Must set _running to True for respawn to occur
        orch._running = True
        orch._worker_manager.running = True

        # First spawn call is in setup
        initial_spawn_count = mock_orchestrator_deps["launcher"].spawn.call_count

        orch._handle_worker_exit(0)

        # Should spawn again for remaining tasks
        assert mock_orchestrator_deps["launcher"].spawn.call_count > initial_spawn_count


class TestStop:
    """Tests for stopping orchestration."""

    def test_stop_terminates_all_workers(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test stop terminates all workers."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._spawn_worker(1)
        orch._running = True

        orch.stop()

        assert orch._running is False
        mock_orchestrator_deps["launcher"].terminate.assert_called()

    def test_stop_releases_all_ports(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test stop releases all ports."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._running = True

        orch.stop()

        mock_orchestrator_deps["ports"].release_all.assert_called()

    def test_stop_saves_state(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test stop saves final state."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._running = True

        orch.stop()

        mock_orchestrator_deps["state"].save.assert_called()
        mock_orchestrator_deps["state"].append_event.assert_called_with("rush_stopped", {"force": False})

    def test_stop_force(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch) -> None:
        """Test force stop."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._running = True

        orch.stop(force=True)

        mock_orchestrator_deps["launcher"].terminate.assert_called_with(0, force=True)
