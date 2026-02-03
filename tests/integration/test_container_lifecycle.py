"""Integration tests for ZERG container lifecycle (TC-013).

Tests ContainerLauncher spawn, monitor, terminate cycle.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from zerg.constants import WorkerStatus
from zerg.launcher import (
    ContainerLauncher,
    LauncherConfig,
    LauncherType,
    WorkerHandle,
    validate_env_vars,
)


class TestEnvVarValidation:
    """Tests for environment variable validation."""

    def test_allowed_env_vars_pass(self) -> None:
        """Test allowed environment variables pass validation."""
        env = {
            "ZERG_WORKER_ID": "1",
            "ZERG_FEATURE": "test",
            "ANTHROPIC_API_KEY": "sk-test",
            "CI": "true",
        }

        validated = validate_env_vars(env)

        assert "ZERG_WORKER_ID" in validated
        assert "ZERG_FEATURE" in validated
        assert "ANTHROPIC_API_KEY" in validated
        assert "CI" in validated

    def test_dangerous_env_vars_blocked(self) -> None:
        """Test dangerous environment variables are blocked."""
        env = {
            "LD_PRELOAD": "/evil.so",
            "PATH": "/malicious",
            "ZERG_WORKER_ID": "1",
        }

        validated = validate_env_vars(env)

        assert "LD_PRELOAD" not in validated
        assert "PATH" not in validated
        assert "ZERG_WORKER_ID" in validated

    def test_shell_metacharacters_blocked(self) -> None:
        """Test env vars with shell metacharacters are blocked."""
        env = {
            "BAD_VAR": "value; rm -rf /",
            "ANOTHER_BAD": "$(whoami)",
            "ZERG_WORKER_ID": "1",
        }

        validated = validate_env_vars(env)

        assert "BAD_VAR" not in validated
        assert "ANOTHER_BAD" not in validated
        assert "ZERG_WORKER_ID" in validated

    def test_zerg_prefixed_vars_allowed(self) -> None:
        """Test ZERG_ prefixed vars are always allowed."""
        env = {
            "ZERG_CUSTOM_VAR": "value",
            "ZERG_ANOTHER": "test",
        }

        validated = validate_env_vars(env)

        assert "ZERG_CUSTOM_VAR" in validated
        assert "ZERG_ANOTHER" in validated

    def test_unlisted_vars_skipped(self) -> None:
        """Test unlisted environment variables are skipped."""
        env = {
            "RANDOM_VAR": "value",
            "UNKNOWN": "test",
        }

        validated = validate_env_vars(env)

        assert "RANDOM_VAR" not in validated
        assert "UNKNOWN" not in validated


class TestLauncherConfig:
    """Tests for LauncherConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = LauncherConfig()

        assert config.launcher_type == LauncherType.SUBPROCESS
        assert config.timeout_seconds == 3600
        assert config.env_vars == {}

    def test_custom_config(self, tmp_path: Path) -> None:
        """Test custom configuration."""
        config = LauncherConfig(
            launcher_type=LauncherType.CONTAINER,
            timeout_seconds=1800,
            working_dir=tmp_path,
            log_dir=tmp_path / "logs",
        )

        assert config.launcher_type == LauncherType.CONTAINER
        assert config.timeout_seconds == 1800
        assert config.working_dir == tmp_path


class TestWorkerHandle:
    """Tests for WorkerHandle."""

    def test_is_alive_initializing(self) -> None:
        """Test is_alive returns True for initializing worker."""
        handle = WorkerHandle(worker_id=0, status=WorkerStatus.INITIALIZING)

        assert handle.is_alive() is True

    def test_is_alive_running(self) -> None:
        """Test is_alive returns True for running worker."""
        handle = WorkerHandle(worker_id=0, status=WorkerStatus.RUNNING)

        assert handle.is_alive() is True

    def test_is_alive_stopped(self) -> None:
        """Test is_alive returns False for stopped worker."""
        handle = WorkerHandle(worker_id=0, status=WorkerStatus.STOPPED)

        assert handle.is_alive() is False

    def test_is_alive_crashed(self) -> None:
        """Test is_alive returns False for crashed worker."""
        handle = WorkerHandle(worker_id=0, status=WorkerStatus.CRASHED)

        assert handle.is_alive() is False


class TestContainerLauncherInit:
    """Tests for ContainerLauncher initialization."""

    def test_init_default(self) -> None:
        """Test default initialization."""
        launcher = ContainerLauncher()

        assert launcher.image_name == "zerg-worker"
        assert launcher.network == "bridge"

    def test_init_custom(self) -> None:
        """Test custom initialization."""
        config = LauncherConfig(launcher_type=LauncherType.CONTAINER)
        launcher = ContainerLauncher(
            config=config,
            image_name="custom-worker",
            network="custom-network",
        )

        assert launcher.image_name == "custom-worker"
        assert launcher.network == "custom-network"


class TestContainerSpawn:
    """Tests for container spawning."""

    @patch("subprocess.run")
    @patch.object(ContainerLauncher, "_wait_ready", return_value=True)
    def test_spawn_success(self, mock_wait, mock_run, tmp_path: Path) -> None:
        """Test successful container spawn."""
        # Mock docker run to return container ID
        mock_run.return_value = MagicMock(returncode=0, stdout="container123abc\n")

        launcher = ContainerLauncher(image_name="test-image")

        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="zerg/test/worker-0",
        )

        assert result.success is True
        assert result.worker_id == 0
        assert result.handle is not None

    @patch("subprocess.run")
    def test_spawn_invalid_worker_id(self, mock_run, tmp_path: Path) -> None:
        """Test spawn with invalid worker ID."""
        launcher = ContainerLauncher()

        result = launcher.spawn(
            worker_id=-1,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test",
        )

        assert result.success is False
        assert "Invalid worker_id" in result.error

    @patch("subprocess.run")
    def test_spawn_docker_failure(self, mock_run, tmp_path: Path) -> None:
        """Test spawn when docker run fails."""
        mock_run.return_value = MagicMock(returncode=1, stderr="Error")

        launcher = ContainerLauncher()

        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test",
        )

        assert result.success is False

    @patch("subprocess.run")
    @patch.object(ContainerLauncher, "_verify_worker_process", return_value=True)
    @patch.object(ContainerLauncher, "_wait_ready", return_value=True)
    def test_spawn_validates_env(self, mock_wait, mock_verify, mock_run, tmp_path: Path) -> None:
        """Test spawn validates environment variables."""
        mock_run.return_value = MagicMock(returncode=0, stdout="container123\n")

        launcher = ContainerLauncher()

        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test",
            env={"LD_PRELOAD": "/evil.so", "ZERG_CUSTOM": "ok"},  # LD_PRELOAD should be blocked
        )

        # Find the docker run call (skip the docker rm -f call)
        docker_calls = [c for c in mock_run.call_args_list if "rm" not in str(c)]
        assert len(docker_calls) > 0
        cmd = docker_calls[0][0][0]
        cmd_str = " ".join(cmd)
        assert "LD_PRELOAD" not in cmd_str


class TestContainerMonitor:
    """Tests for container monitoring."""

    @patch("subprocess.run")
    def test_monitor_running(self, mock_run) -> None:
        """Test monitoring running container."""
        mock_run.return_value = MagicMock(returncode=0, stdout="true,0\n")

        launcher = ContainerLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, status=WorkerStatus.INITIALIZING)
        launcher._container_ids[0] = "container123"

        status = launcher.monitor(0)

        assert status == WorkerStatus.RUNNING

    @patch("subprocess.run")
    def test_monitor_stopped(self, mock_run) -> None:
        """Test monitoring stopped container."""
        mock_run.return_value = MagicMock(returncode=0, stdout="false,0\n")

        launcher = ContainerLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, status=WorkerStatus.RUNNING)
        launcher._container_ids[0] = "container123"

        status = launcher.monitor(0)

        assert status == WorkerStatus.STOPPED

    @patch("subprocess.run")
    def test_monitor_crashed(self, mock_run) -> None:
        """Test monitoring crashed container."""
        mock_run.return_value = MagicMock(returncode=0, stdout="false,1\n")

        launcher = ContainerLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, status=WorkerStatus.RUNNING)
        launcher._container_ids[0] = "container123"

        status = launcher.monitor(0)

        assert status == WorkerStatus.CRASHED

    @patch("subprocess.run")
    def test_monitor_checkpointing(self, mock_run) -> None:
        """Test monitoring checkpointing container."""
        mock_run.return_value = MagicMock(returncode=0, stdout="false,2\n")

        launcher = ContainerLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, status=WorkerStatus.RUNNING)
        launcher._container_ids[0] = "container123"

        status = launcher.monitor(0)

        assert status == WorkerStatus.CHECKPOINTING

    def test_monitor_nonexistent(self) -> None:
        """Test monitoring nonexistent worker."""
        launcher = ContainerLauncher()

        status = launcher.monitor(999)

        assert status == WorkerStatus.STOPPED


class TestContainerTerminate:
    """Tests for container termination."""

    @patch("subprocess.run")
    def test_terminate_graceful(self, mock_run) -> None:
        """Test graceful container termination."""
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, status=WorkerStatus.RUNNING)
        launcher._container_ids[0] = "container123"

        result = launcher.terminate(0)

        assert result is True
        # Should use docker stop
        call_args = mock_run.call_args_list[0][0][0]
        assert "stop" in call_args

    @patch("subprocess.run")
    def test_terminate_force(self, mock_run) -> None:
        """Test forced container termination."""
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, status=WorkerStatus.RUNNING)
        launcher._container_ids[0] = "container123"

        result = launcher.terminate(0, force=True)

        assert result is True
        # Should use docker kill
        call_args = mock_run.call_args_list[0][0][0]
        assert "kill" in call_args

    def test_terminate_nonexistent(self) -> None:
        """Test terminating nonexistent worker."""
        launcher = ContainerLauncher()

        result = launcher.terminate(999)

        assert result is False


class TestContainerOutput:
    """Tests for container output retrieval."""

    @patch("subprocess.run")
    def test_get_output(self, mock_run) -> None:
        """Test getting container output."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Worker started\nProcessing task\n",
            stderr="",
        )

        launcher = ContainerLauncher()
        launcher._container_ids[0] = "container123"

        output = launcher.get_output(0, tail=50)

        assert "Worker started" in output
        mock_run.assert_called_once()

    def test_get_output_nonexistent(self) -> None:
        """Test getting output from nonexistent worker."""
        launcher = ContainerLauncher()

        output = launcher.get_output(999)

        assert output == ""


class TestNetworkManagement:
    """Tests for Docker network management."""

    @patch("subprocess.run")
    def test_ensure_network_exists(self, mock_run) -> None:
        """Test ensuring network when it exists."""
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()

        result = launcher.ensure_network()

        assert result is True

    @patch("subprocess.run")
    def test_ensure_network_creates(self, mock_run) -> None:
        """Test ensuring network creates when missing."""
        mock_run.side_effect = [
            MagicMock(returncode=1),  # network inspect fails
            MagicMock(returncode=0),  # network create succeeds
        ]

        launcher = ContainerLauncher()

        result = launcher.ensure_network()

        assert result is True
        assert mock_run.call_count == 2


class TestImageCheck:
    """Tests for Docker image checking."""

    @patch("subprocess.run")
    def test_image_exists_true(self, mock_run) -> None:
        """Test image exists returns True."""
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher(image_name="test-image")

        assert launcher.image_exists() is True

    @patch("subprocess.run")
    def test_image_exists_false(self, mock_run) -> None:
        """Test image exists returns False when missing."""
        mock_run.return_value = MagicMock(returncode=1)

        launcher = ContainerLauncher(image_name="missing-image")

        assert launcher.image_exists() is False


class TestLauncherCommon:
    """Tests for common launcher functionality."""

    def test_get_handle(self) -> None:
        """Test getting worker handle."""
        launcher = ContainerLauncher()
        handle = WorkerHandle(worker_id=0, status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle

        result = launcher.get_handle(0)

        assert result is handle

    def test_get_all_workers(self) -> None:
        """Test getting all workers."""
        launcher = ContainerLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, status=WorkerStatus.RUNNING)
        launcher._workers[1] = WorkerHandle(worker_id=1, status=WorkerStatus.STOPPED)

        workers = launcher.get_all_workers()

        assert len(workers) == 2
        assert 0 in workers
        assert 1 in workers

    @patch("subprocess.run")
    def test_terminate_all(self, mock_run) -> None:
        """Test terminating all workers."""
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, status=WorkerStatus.RUNNING)
        launcher._workers[1] = WorkerHandle(worker_id=1, status=WorkerStatus.RUNNING)
        launcher._container_ids[0] = "container0"
        launcher._container_ids[1] = "container1"

        results = launcher.terminate_all()

        assert results[0] is True
        assert results[1] is True

    def test_get_status_summary(self) -> None:
        """Test getting status summary."""
        launcher = ContainerLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, status=WorkerStatus.RUNNING)
        launcher._workers[1] = WorkerHandle(worker_id=1, status=WorkerStatus.RUNNING)
        launcher._workers[2] = WorkerHandle(worker_id=2, status=WorkerStatus.STOPPED)

        summary = launcher.get_status_summary()

        assert summary["total"] == 3
        assert summary["alive"] == 2
        assert summary["by_status"]["running"] == 2
        assert summary["by_status"]["stopped"] == 1
