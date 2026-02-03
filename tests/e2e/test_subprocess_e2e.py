"""End-to-end tests for ZERG subprocess mode (TC-015).

Tests the complete workflow of subprocess-based worker execution.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.constants import WorkerStatus
from zerg.launcher import LauncherConfig, SpawnResult, SubprocessLauncher
from zerg.orchestrator import Orchestrator


@pytest.fixture
def e2e_orchestrator(tmp_path: Path, monkeypatch):
    """Set up orchestrator with mocked dependencies for E2E testing."""
    monkeypatch.chdir(tmp_path)

    # Create minimal project structure
    zerg_dir = tmp_path / ".zerg"
    zerg_dir.mkdir()

    # Create task graph
    task_graph = {
        "feature": "test-feature",
        "tasks": [
            {"id": "TASK-001", "title": "First task", "level": 1, "files": ["src/a.py"]},
            {"id": "TASK-002", "title": "Second task", "level": 1, "files": ["src/b.py"]},
        ],
    }
    (zerg_dir / "task-graph.json").write_text(json.dumps(task_graph))

    return tmp_path


@pytest.fixture
def mock_orchestrator_deps():
    """Mock all orchestrator dependencies."""
    with (
        patch("zerg.orchestrator.StateManager") as state_mock,
        patch("zerg.orchestrator.LevelController") as levels_mock,
        patch("zerg.orchestrator.TaskParser") as parser_mock,
        patch("zerg.orchestrator.GateRunner"),
        patch("zerg.orchestrator.WorktreeManager") as worktree_mock,
        patch("zerg.orchestrator.ContainerManager"),
        patch("zerg.orchestrator.PortAllocator") as ports_mock,
        patch("zerg.orchestrator.MergeCoordinator"),
        patch("zerg.orchestrator.SubprocessLauncher") as launcher_mock,
    ):
        state = MagicMock()
        state.load.return_value = {}
        state_mock.return_value = state

        levels = MagicMock()
        levels.current_level = 1
        levels.get_status.return_value = {
            "current_level": 1,
            "total_tasks": 2,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "in_progress_tasks": 0,
            "progress_percent": 0,
            "levels": {},
            "is_complete": False,
        }
        levels_mock.return_value = levels

        parser = MagicMock()
        parser.total_tasks = 2
        parser_mock.return_value = parser

        worktree = MagicMock()
        worktree_info = MagicMock()
        worktree_info.path = Path("/tmp/worktree")
        worktree_info.branch = "zerg/test/worker-0"
        worktree.create.return_value = worktree_info
        worktree_mock.return_value = worktree

        ports = MagicMock()
        ports.allocate_one.return_value = 49152
        ports_mock.return_value = ports

        launcher = MagicMock()
        spawn_result = MagicMock(spec=SpawnResult)
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
            "worktree": worktree,
            "ports": ports,
            "launcher": launcher,
        }


class TestSubprocessSpawning:
    """Tests for subprocess worker spawning."""

    def test_spawn_worker_creates_handle(self, e2e_orchestrator: Path, mock_orchestrator_deps) -> None:
        """Test spawning a subprocess worker creates handle."""
        orch = Orchestrator("test-feature")

        worker_state = orch._spawn_worker(0)

        assert worker_state is not None
        assert 0 in orch._workers

    def test_spawn_multiple_workers(self, e2e_orchestrator: Path, mock_orchestrator_deps) -> None:
        """Test spawning multiple subprocess workers."""
        mock_orchestrator_deps["ports"].allocate_one.side_effect = [49152, 49153, 49154]

        orch = Orchestrator("test-feature")

        for i in range(3):
            orch._spawn_worker(i)

        assert len(orch._workers) == 3


class TestSubprocessWorkflow:
    """Tests for complete subprocess workflow."""

    def test_worker_lifecycle(self, e2e_orchestrator: Path, mock_orchestrator_deps) -> None:
        """Test worker lifecycle: spawn -> work -> terminate."""
        orch = Orchestrator("test-feature")

        # Spawn
        orch._spawn_worker(0)
        assert 0 in orch._workers

        # Terminate
        orch._terminate_worker(0)
        mock_orchestrator_deps["launcher"].terminate.assert_called()

    def test_worker_polling(self, e2e_orchestrator: Path, mock_orchestrator_deps) -> None:
        """Test worker status polling."""
        orch = Orchestrator("test-feature")

        orch._spawn_worker(0)
        orch._poll_workers()

        mock_orchestrator_deps["launcher"].monitor.assert_called()


class TestSubprocessCleanup:
    """Tests for subprocess cleanup."""

    def test_cleanup_on_stop(self, e2e_orchestrator: Path, mock_orchestrator_deps) -> None:
        """Test cleanup when orchestrator stops."""
        mock_orchestrator_deps["ports"].allocate_one.side_effect = [49152, 49153]

        orch = Orchestrator("test-feature")
        orch._running = True

        orch._spawn_worker(0)
        orch._spawn_worker(1)

        orch.stop()

        assert orch._running is False
        # Terminate should be called for each worker
        assert mock_orchestrator_deps["launcher"].terminate.call_count >= 2


class TestOrchestratorStatus:
    """Tests for orchestrator status reporting."""

    def test_status_includes_feature(self, e2e_orchestrator: Path, mock_orchestrator_deps) -> None:
        """Test status includes feature name."""
        orch = Orchestrator("test-feature")
        status = orch.status()

        assert status["feature"] == "test-feature"

    def test_status_includes_workers(self, e2e_orchestrator: Path, mock_orchestrator_deps) -> None:
        """Test status includes worker info."""
        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)

        status = orch.status()

        assert "workers" in status
        assert 0 in status["workers"]


class TestWorkerAssignment:
    """Tests for worker task assignment."""

    def test_task_assigned_to_worker(self, e2e_orchestrator: Path, mock_orchestrator_deps) -> None:
        """Test tasks are assigned to workers."""
        mock_orchestrator_deps["levels"].start_level.return_value = ["TASK-001"]

        orch = Orchestrator("test-feature")
        orch.assigner = MagicMock()
        orch.assigner.get_task_worker.return_value = 0

        orch._start_level(1)

        orch.assigner.get_task_worker.assert_called()


class TestLevelStarting:
    """Tests for level starting."""

    def test_start_level_emits_event(self, e2e_orchestrator: Path, mock_orchestrator_deps) -> None:
        """Test starting level emits event."""
        mock_orchestrator_deps["levels"].start_level.return_value = ["TASK-001"]

        orch = Orchestrator("test-feature")
        orch._start_level(1)

        mock_orchestrator_deps["state"].append_event.assert_called()

    def test_start_level_sets_state(self, e2e_orchestrator: Path, mock_orchestrator_deps) -> None:
        """Test starting level sets state."""
        mock_orchestrator_deps["levels"].start_level.return_value = ["TASK-001"]

        orch = Orchestrator("test-feature")
        orch._start_level(1)

        mock_orchestrator_deps["state"].set_current_level.assert_called_with(1)


class TestSubprocessLauncherInterface:
    """Tests for SubprocessLauncher interface."""

    def test_launcher_has_spawn_method(self) -> None:
        """Test SubprocessLauncher has spawn method."""
        assert hasattr(SubprocessLauncher, "spawn")

    def test_launcher_has_monitor_method(self) -> None:
        """Test SubprocessLauncher has monitor method."""
        assert hasattr(SubprocessLauncher, "monitor")

    def test_launcher_has_terminate_method(self) -> None:
        """Test SubprocessLauncher has terminate method."""
        assert hasattr(SubprocessLauncher, "terminate")

    def test_launcher_config_accepted(self) -> None:
        """Test SubprocessLauncher accepts LauncherConfig."""
        config = LauncherConfig(
            timeout_seconds=60,
        )
        # Should not raise
        launcher = SubprocessLauncher(config=config)
        assert launcher.config is not None
