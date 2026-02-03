"""End-to-end tests for ZERG container mode (TC-016).

Tests the complete workflow of container-based worker execution.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.constants import WorkerStatus
from zerg.launcher import ContainerLauncher, LauncherConfig, SpawnResult
from zerg.orchestrator import Orchestrator


@pytest.fixture
def mock_container_launcher():
    """Mock container launcher for E2E tests."""
    with patch("zerg.orchestrator.ContainerLauncher") as launcher_mock:
        launcher = MagicMock()

        # Mock spawn to return success
        spawn_result = MagicMock(spec=SpawnResult)
        spawn_result.success = True
        spawn_result.handle = MagicMock()
        spawn_result.handle.container_id = "abc123def456"
        spawn_result.handle.process = None
        spawn_result.error = None
        launcher.spawn.return_value = spawn_result

        # Mock monitor to return RUNNING
        launcher.monitor.return_value = WorkerStatus.RUNNING

        # Mock terminate
        launcher.terminate.return_value = True

        launcher_mock.return_value = launcher
        yield launcher


@pytest.fixture
def container_e2e_setup(tmp_path: Path, monkeypatch):
    """Set up container E2E test environment."""
    monkeypatch.chdir(tmp_path)

    # Create project structure
    zerg_dir = tmp_path / ".zerg"
    zerg_dir.mkdir()

    # Create devcontainer
    devcontainer_dir = tmp_path / ".devcontainer"
    devcontainer_dir.mkdir()
    (devcontainer_dir / "devcontainer.json").write_text(json.dumps({"image": "python:3.11", "features": {}}))

    # Create task graph
    task_graph = {
        "feature": "container-test",
        "levels": {"1": ["TASK-001"]},
        "tasks": {"TASK-001": {"id": "TASK-001", "title": "Container task", "level": 1, "files": ["app.py"]}},
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
        patch("zerg.orchestrator.SubprocessLauncher") as subprocess_launcher_mock,
        patch("zerg.orchestrator.ContainerLauncher") as container_launcher_mock,
    ):
        state = MagicMock()
        state.load.return_value = {}
        state_mock.return_value = state

        levels = MagicMock()
        levels.current_level = 1
        levels_mock.return_value = levels

        parser = MagicMock()
        parser.total_tasks = 1
        parser_mock.return_value = parser

        worktree = MagicMock()
        worktree_info = MagicMock()
        worktree_info.path = Path("/tmp/worktree")
        worktree_info.branch = "zerg/container-test/worker-0"
        worktree.create.return_value = worktree_info
        worktree_mock.return_value = worktree

        ports = MagicMock()
        ports.allocate_one.return_value = 49152
        ports_mock.return_value = ports

        # Create a shared launcher mock for both subprocess and container
        launcher = MagicMock()
        spawn_result = MagicMock(spec=SpawnResult)
        spawn_result.success = True
        spawn_result.handle = MagicMock()
        spawn_result.handle.container_id = "abc123def456"
        spawn_result.error = None
        launcher.spawn.return_value = spawn_result
        launcher.monitor.return_value = WorkerStatus.RUNNING
        launcher.terminate.return_value = True

        # Set both launcher types to return the same mock
        subprocess_launcher_mock.return_value = launcher
        container_launcher_mock.return_value = launcher

        yield {
            "state": state,
            "levels": levels,
            "parser": parser,
            "worktree": worktree,
            "ports": ports,
            "launcher": launcher,
        }


class TestContainerSpawning:
    """Tests for container worker spawning."""

    def test_spawn_container_worker(self, container_e2e_setup: Path, mock_orchestrator_deps) -> None:
        """Test spawning a container worker."""
        orch = Orchestrator("container-test")

        worker_state = orch._spawn_worker(0)

        # Worker should be tracked
        assert 0 in orch._workers
        assert worker_state is not None

    def test_container_id_tracked(self, container_e2e_setup: Path, mock_orchestrator_deps) -> None:
        """Test container ID is tracked in worker state."""
        # Set up mock to return container ID
        mock_orchestrator_deps["launcher"].spawn.return_value.handle.container_id = "abc123def456"

        orch = Orchestrator("container-test")

        orch._spawn_worker(0)

        # Check that spawn was called
        mock_orchestrator_deps["launcher"].spawn.assert_called()


class TestContainerNetworking:
    """Tests for container networking."""

    def test_network_constant_defined(self) -> None:
        """Test Docker network constant is defined."""
        assert hasattr(ContainerLauncher, "DEFAULT_NETWORK")
        assert ContainerLauncher.DEFAULT_NETWORK == "bridge"

    def test_container_prefix_defined(self) -> None:
        """Test container prefix is defined."""
        assert hasattr(ContainerLauncher, "CONTAINER_PREFIX")
        assert ContainerLauncher.CONTAINER_PREFIX == "zerg-worker"


class TestContainerVolumes:
    """Tests for container volume mounting configuration."""

    def test_worktree_path_passed_to_spawn(self, container_e2e_setup: Path, mock_orchestrator_deps) -> None:
        """Test worktree path is passed to launcher spawn."""
        orch = Orchestrator("container-test")
        orch._spawn_worker(0)

        # Check spawn was called with worktree_path
        call_args = mock_orchestrator_deps["launcher"].spawn.call_args
        assert "worktree_path" in call_args.kwargs or len(call_args.args) >= 3


class TestContainerLifecycle:
    """Tests for container lifecycle management."""

    def test_container_monitoring(self, container_e2e_setup: Path, mock_orchestrator_deps) -> None:
        """Test container status monitoring."""
        orch = Orchestrator("container-test")

        orch._spawn_worker(0)
        orch._poll_workers()

        mock_orchestrator_deps["launcher"].monitor.assert_called()

    def test_container_termination(self, container_e2e_setup: Path, mock_orchestrator_deps) -> None:
        """Test container termination."""
        orch = Orchestrator("container-test")

        orch._spawn_worker(0)
        orch._terminate_worker(0)

        mock_orchestrator_deps["launcher"].terminate.assert_called()

    def test_container_crash_detection(self, container_e2e_setup: Path, mock_orchestrator_deps) -> None:
        """Test container crash detection."""
        # Container crashes
        mock_orchestrator_deps["launcher"].monitor.return_value = WorkerStatus.CRASHED

        orch = Orchestrator("container-test")

        orch._spawn_worker(0)
        orch._poll_workers()

        # State should record crash
        mock_orchestrator_deps["state"].set_worker_state.assert_called()


class TestContainerEnvironment:
    """Tests for container environment setup."""

    def test_environment_passed_to_spawn(self, container_e2e_setup: Path, mock_orchestrator_deps) -> None:
        """Test environment is passed to launcher spawn."""
        orch = Orchestrator("container-test")
        orch._spawn_worker(0)

        # Check spawn was called with feature parameter
        call_args = mock_orchestrator_deps["launcher"].spawn.call_args
        assert "feature" in call_args.kwargs or len(call_args.args) >= 2


class TestContainerCleanup:
    """Tests for container cleanup."""

    def test_cleanup_on_stop(self, container_e2e_setup: Path, mock_orchestrator_deps) -> None:
        """Test containers are cleaned up on stop."""
        mock_orchestrator_deps["ports"].allocate_one.side_effect = [49152, 49153]

        orch = Orchestrator("container-test")
        orch._running = True

        orch._spawn_worker(0)
        orch._spawn_worker(1)

        orch.stop()

        # All containers should be terminated
        assert mock_orchestrator_deps["launcher"].terminate.call_count >= 2

    def test_launcher_config_accepted(self) -> None:
        """Test ContainerLauncher accepts LauncherConfig."""
        config = LauncherConfig(
            timeout_seconds=60,
        )
        # Should not raise
        launcher = ContainerLauncher(config=config, image_name="test-image")
        assert launcher.image_name == "test-image"


class TestContainerLauncherInterface:
    """Tests for ContainerLauncher interface."""

    def test_launcher_has_spawn_method(self) -> None:
        """Test ContainerLauncher has spawn method."""
        assert hasattr(ContainerLauncher, "spawn")

    def test_launcher_has_monitor_method(self) -> None:
        """Test ContainerLauncher has monitor method."""
        assert hasattr(ContainerLauncher, "monitor")

    def test_launcher_has_terminate_method(self) -> None:
        """Test ContainerLauncher has terminate method."""
        assert hasattr(ContainerLauncher, "terminate")

    def test_launcher_has_terminate_all_method(self) -> None:
        """Test ContainerLauncher has terminate_all method."""
        assert hasattr(ContainerLauncher, "terminate_all")

    def test_launcher_has_ensure_network_method(self) -> None:
        """Test ContainerLauncher has ensure_network method."""
        assert hasattr(ContainerLauncher, "ensure_network")

    def test_launcher_has_image_exists_method(self) -> None:
        """Test ContainerLauncher has image_exists method."""
        assert hasattr(ContainerLauncher, "image_exists")
