"""Tests for ZERG containers module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.config import ZergConfig
from zerg.constants import WorkerStatus
from zerg.containers import ContainerInfo, ContainerManager
from zerg.exceptions import ContainerError


@pytest.fixture(autouse=True)
def mock_zerg_config():
    """Mock ZergConfig.load() for all container tests."""
    mock_config = MagicMock(spec=ZergConfig)
    mock_config.workers = MagicMock()
    mock_config.workers.max_workers = 5
    with patch.object(ZergConfig, "load", return_value=mock_config):
        yield mock_config


class TestContainerInfo:
    """Tests for ContainerInfo dataclass."""

    def test_creation(self) -> None:
        """Test creating container info."""
        info = ContainerInfo(
            container_id="abc123",
            name="zerg-worker-0",
            status="running",
            worker_id=0,
            port=49152,
            image="zerg-worker:latest",
        )

        assert info.container_id == "abc123"
        assert info.name == "zerg-worker-0"
        assert info.status == "running"
        assert info.worker_id == 0
        assert info.port == 49152
        assert info.image == "zerg-worker:latest"

    def test_creation_minimal(self) -> None:
        """Test creating container info with minimal fields."""
        info = ContainerInfo(
            container_id="abc123",
            name="zerg-worker-0",
            status="running",
            worker_id=0,
        )

        assert info.container_id == "abc123"
        assert info.port is None
        assert info.image is None


class TestContainerManager:
    """Tests for ContainerManager class."""

    @pytest.fixture
    def mock_docker(self):
        """Mock Docker commands."""
        with patch.object(ContainerManager, "_run_docker") as mock:
            mock.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="",
            )
            yield mock

    @pytest.fixture
    def mock_compose(self):
        """Mock Docker Compose commands."""
        with patch.object(ContainerManager, "_run_compose") as mock:
            mock.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="",
            )
            yield mock

    def test_init_default(self, mock_docker) -> None:
        """Test default initialization."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()

        assert manager.compose_file == Path(".devcontainer/docker-compose.yaml")

    def test_init_custom_compose_file(self, mock_docker) -> None:
        """Test initialization with custom compose file."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager(compose_file="/custom/docker-compose.yaml")

        assert manager.compose_file == Path("/custom/docker-compose.yaml")

    def test_init_with_custom_config(self) -> None:
        """Test initialization with custom config."""
        custom_config = MagicMock(spec=ZergConfig)
        custom_config.workers = MagicMock()
        custom_config.workers.max_workers = 10

        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager(config=custom_config)

        assert manager.config == custom_config


class TestCheckDocker:
    """Tests for _check_docker method."""

    def test_check_docker_success(self) -> None:
        """Test _check_docker when Docker is available."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            ContainerManager()
            # No exception should be raised

    def test_check_docker_not_running(self) -> None:
        """Test _check_docker when Docker daemon is not running."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            # Should log warning but not raise
            ContainerManager()

    def test_check_docker_timeout(self) -> None:
        """Test _check_docker when Docker command times out."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("docker info", 10)
            # Should log warning but not raise
            ContainerManager()

    def test_check_docker_not_found(self) -> None:
        """Test _check_docker when Docker is not installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("docker not found")
            # Should log warning but not raise
            ContainerManager()


class TestRunDocker:
    """Tests for _run_docker method."""

    def test_run_docker_success(self) -> None:
        """Test _run_docker with successful command."""
        with patch.object(ContainerManager, "_check_docker"), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="output",
                stderr="",
            )

            manager = ContainerManager()
            result = manager._run_docker("ps", "-a")

            assert result.returncode == 0
            mock_run.assert_called()

    def test_run_docker_called_process_error(self) -> None:
        """Test _run_docker with CalledProcessError."""
        with patch.object(ContainerManager, "_check_docker"), patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1,
                cmd=["docker", "ps"],
                stderr="error message",
            )

            manager = ContainerManager()

            with pytest.raises(ContainerError) as exc_info:
                manager._run_docker("ps", "-a")

            assert "Docker command failed" in str(exc_info.value)
            assert exc_info.value.details["exit_code"] == 1

    def test_run_docker_timeout(self) -> None:
        """Test _run_docker with timeout."""
        with patch.object(ContainerManager, "_check_docker"), patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("docker", 60)

            manager = ContainerManager()

            with pytest.raises(ContainerError) as exc_info:
                manager._run_docker("ps", "-a", timeout=60)

            assert "timed out" in str(exc_info.value)
            assert "60s" in str(exc_info.value)

    def test_run_docker_check_false(self) -> None:
        """Test _run_docker with check=False doesn't raise."""
        with patch.object(ContainerManager, "_check_docker"), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="error",
            )

            manager = ContainerManager()
            result = manager._run_docker("ps", "-a", check=False)

            assert result.returncode == 1


class TestRunCompose:
    """Tests for _run_compose method."""

    def test_run_compose_success(self) -> None:
        """Test _run_compose with successful command."""
        with patch.object(ContainerManager, "_check_docker"), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="output",
                stderr="",
            )

            manager = ContainerManager()
            result = manager._run_compose("up", "-d")

            assert result.returncode == 0

    def test_run_compose_with_env(self) -> None:
        """Test _run_compose with environment variables."""
        with patch.object(ContainerManager, "_check_docker"), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            manager = ContainerManager()
            manager._run_compose("up", "-d", env={"CUSTOM_VAR": "value"})

            call_args = mock_run.call_args
            assert "CUSTOM_VAR" in call_args.kwargs["env"]

    def test_run_compose_called_process_error(self) -> None:
        """Test _run_compose with CalledProcessError."""
        with patch.object(ContainerManager, "_check_docker"), patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1,
                cmd=["docker", "compose", "up"],
                stderr="compose error",
            )

            manager = ContainerManager()

            with pytest.raises(ContainerError) as exc_info:
                manager._run_compose("up", "-d")

            assert "Compose command failed" in str(exc_info.value)

    def test_run_compose_timeout(self) -> None:
        """Test _run_compose with timeout."""
        with patch.object(ContainerManager, "_check_docker"), patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("docker compose", 120)

            manager = ContainerManager()

            with pytest.raises(ContainerError) as exc_info:
                manager._run_compose("up", "-d", timeout=120)

            assert "timed out" in str(exc_info.value)


class TestBuild:
    """Tests for container build."""

    def test_build(self) -> None:
        """Test building worker image."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_compose") as mock_compose,
        ):
            mock_compose.return_value = MagicMock(returncode=0)

            manager = ContainerManager()
            manager.build()

            mock_compose.assert_called_once()
            call_args = mock_compose.call_args[0]
            assert "build" in call_args

    def test_build_no_cache(self) -> None:
        """Test building with no cache."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_compose") as mock_compose,
        ):
            mock_compose.return_value = MagicMock(returncode=0)

            manager = ContainerManager()
            manager.build(no_cache=True)

            call_args = mock_compose.call_args[0]
            assert "--no-cache" in call_args


class TestStartWorker:
    """Tests for starting workers."""

    def test_start_worker(self) -> None:
        """Test starting a worker container."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
            patch.object(ContainerManager, "_run_compose") as mock_compose,
            patch("time.sleep"),
        ):
            # Mock docker ps to return container ID
            mock_docker.return_value = MagicMock(
                returncode=0,
                stdout="abc123def456",
                stderr="",
            )
            mock_compose.return_value = MagicMock(returncode=0)

            manager = ContainerManager()
            info = manager.start_worker(
                worker_id=0,
                feature="test-feature",
                port=49152,
                worktree_path="/tmp/worktree",
                branch="zerg/test/worker-0",
            )

            assert info.worker_id == 0
            assert info.port == 49152
            assert info.status == "running"
            mock_compose.assert_called()

    def test_start_worker_removes_existing(self) -> None:
        """Test starting worker removes existing container."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
            patch.object(ContainerManager, "_run_compose") as mock_compose,
            patch("time.sleep"),
        ):
            mock_docker.return_value = MagicMock(
                returncode=0,
                stdout="abc123",
                stderr="",
            )
            mock_compose.return_value = MagicMock(returncode=0)

            manager = ContainerManager()
            manager.start_worker(0, "test", 49152, "/tmp", "branch")

            # First call should be rm -f for existing container
            first_call = mock_docker.call_args_list[0]
            assert "rm" in first_call[0]
            assert "-f" in first_call[0]

    def test_start_worker_no_container_id_fallback(self) -> None:
        """Test start_worker falls back to alternate naming when container ID not found."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
            patch.object(ContainerManager, "_run_compose") as mock_compose,
            patch("time.sleep"),
        ):
            # First call returns empty (no container by name)
            # Second call returns container from --latest
            mock_docker.side_effect = [
                MagicMock(returncode=0, stdout="", stderr=""),  # rm -f
                MagicMock(returncode=0, stdout="", stderr=""),  # ps -q -f name=
                MagicMock(returncode=0, stdout="fallback123", stderr=""),  # ps -q --latest
            ]
            mock_compose.return_value = MagicMock(returncode=0)

            manager = ContainerManager()
            info = manager.start_worker(0, "test", 49152, "/tmp", "branch")

            assert info.container_id == "fallback123"

    def test_start_worker_no_container_id_unknown_fallback(self) -> None:
        """Test start_worker uses unknown fallback when no container found."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
            patch.object(ContainerManager, "_run_compose") as mock_compose,
            patch("time.sleep"),
        ):
            # Both lookups return empty
            mock_docker.side_effect = [
                MagicMock(returncode=0, stdout="", stderr=""),  # rm -f
                MagicMock(returncode=0, stdout="", stderr=""),  # ps -q -f name=
                MagicMock(returncode=0, stdout="", stderr=""),  # ps -q --latest
            ]
            mock_compose.return_value = MagicMock(returncode=0)

            manager = ContainerManager()
            info = manager.start_worker(0, "test", 49152, "/tmp", "branch")

            assert info.container_id == "unknown-0"


class TestStopWorker:
    """Tests for stopping workers."""

    def test_stop_worker(self) -> None:
        """Test stopping a worker."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(returncode=0, stdout="", stderr="")

            manager = ContainerManager()
            manager._containers[0] = ContainerInfo(
                container_id="abc123",
                name="zerg-worker-0",
                status="running",
                worker_id=0,
            )

            manager.stop_worker(0)

            assert 0 not in manager._containers

    def test_stop_worker_force(self) -> None:
        """Test force stopping a worker."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(returncode=0, stdout="", stderr="")

            manager = ContainerManager()
            manager._containers[0] = ContainerInfo(
                container_id="abc123",
                name="zerg-worker-0",
                status="running",
                worker_id=0,
            )

            manager.stop_worker(0, force=True)

            # Should use kill instead of stop
            first_call = mock_docker.call_args_list[0]
            assert "kill" in first_call[0]

    def test_stop_worker_not_found(self) -> None:
        """Test stopping non-existent worker."""
        with patch.object(ContainerManager, "_check_docker"), patch.object(ContainerManager, "_run_docker"):
            manager = ContainerManager()
            # Should not raise
            manager.stop_worker(99)

    def test_stop_worker_graceful(self) -> None:
        """Test graceful stop with custom timeout."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(returncode=0, stdout="", stderr="")

            manager = ContainerManager()
            manager._containers[0] = ContainerInfo(
                container_id="abc123",
                name="zerg-worker-0",
                status="running",
                worker_id=0,
            )

            manager.stop_worker(0, timeout=60)

            # First call should be stop with timeout
            first_call = mock_docker.call_args_list[0]
            assert "stop" in first_call[0]
            assert "60" in first_call[0]


class TestStopAll:
    """Tests for stopping all workers."""

    def test_stop_all(self) -> None:
        """Test stopping all workers."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="",
            )

            manager = ContainerManager()
            manager._containers = {
                0: ContainerInfo("a", "zerg-worker-0", "running", 0),
                1: ContainerInfo("b", "zerg-worker-1", "running", 1),
            }

            count = manager.stop_all()

            assert count >= 2
            assert len(manager._containers) == 0

    def test_stop_all_with_orphans(self) -> None:
        """Test stopping all workers including orphaned containers."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            # Return orphaned container IDs from docker ps
            mock_docker.return_value = MagicMock(
                returncode=0,
                stdout="orphan1\norphan2\n",
                stderr="",
            )

            manager = ContainerManager()
            manager._containers = {
                0: ContainerInfo("a", "zerg-worker-0", "running", 0),
            }

            count = manager.stop_all()

            # 1 tracked + 2 orphaned
            assert count == 3

    def test_stop_all_empty_orphans(self) -> None:
        """Test stopping all workers with empty orphan list."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="",
            )

            manager = ContainerManager()
            manager._containers = {}

            count = manager.stop_all()

            assert count == 0

    def test_stop_all_force(self) -> None:
        """Test force stopping all workers."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="",
            )

            manager = ContainerManager()
            manager._containers = {
                0: ContainerInfo("a", "zerg-worker-0", "running", 0),
            }

            manager.stop_all(force=True)

            # Should use kill
            assert any("kill" in str(call) for call in mock_docker.call_args_list)


class TestGetStatus:
    """Tests for getting worker status."""

    def test_get_status_running(self) -> None:
        """Test getting running status."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(
                returncode=0,
                stdout="running\n",
                stderr="",
            )

            manager = ContainerManager()
            manager._containers[0] = ContainerInfo(
                container_id="abc123",
                name="zerg-worker-0",
                status="running",
                worker_id=0,
            )

            status = manager.get_status(0)

            assert status == WorkerStatus.RUNNING

    def test_get_status_stopped(self) -> None:
        """Test getting stopped status."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(
                returncode=0,
                stdout="exited\n",
                stderr="",
            )

            manager = ContainerManager()
            manager._containers[0] = ContainerInfo(
                container_id="abc123",
                name="zerg-worker-0",
                status="running",
                worker_id=0,
            )

            status = manager.get_status(0)

            assert status == WorkerStatus.STOPPED

    def test_get_status_paused(self) -> None:
        """Test getting paused status (checkpointing)."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(
                returncode=0,
                stdout="paused\n",
                stderr="",
            )

            manager = ContainerManager()
            manager._containers[0] = ContainerInfo(
                container_id="abc123",
                name="zerg-worker-0",
                status="running",
                worker_id=0,
            )

            status = manager.get_status(0)

            assert status == WorkerStatus.CHECKPOINTING

    def test_get_status_dead(self) -> None:
        """Test getting dead status (crashed)."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(
                returncode=0,
                stdout="dead\n",
                stderr="",
            )

            manager = ContainerManager()
            manager._containers[0] = ContainerInfo(
                container_id="abc123",
                name="zerg-worker-0",
                status="running",
                worker_id=0,
            )

            status = manager.get_status(0)

            assert status == WorkerStatus.CRASHED

    def test_get_status_unknown(self) -> None:
        """Test getting unknown status defaults to STOPPED."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(
                returncode=0,
                stdout="unknown_status\n",
                stderr="",
            )

            manager = ContainerManager()
            manager._containers[0] = ContainerInfo(
                container_id="abc123",
                name="zerg-worker-0",
                status="running",
                worker_id=0,
            )

            status = manager.get_status(0)

            assert status == WorkerStatus.STOPPED

    def test_get_status_not_tracked(self) -> None:
        """Test getting status for untracked worker."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()

            status = manager.get_status(99)

            assert status == WorkerStatus.STOPPED


class TestGetLogs:
    """Tests for getting container logs."""

    def test_get_logs(self) -> None:
        """Test getting logs."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(
                returncode=0,
                stdout="Log line 1\nLog line 2\n",
                stderr="",
            )

            manager = ContainerManager()
            manager._containers[0] = ContainerInfo(
                container_id="abc123",
                name="zerg-worker-0",
                status="running",
                worker_id=0,
            )

            logs = manager.get_logs(0)

            assert "Log line 1" in logs
            assert "Log line 2" in logs

    def test_get_logs_with_stderr(self) -> None:
        """Test getting logs includes stderr."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(
                returncode=0,
                stdout="stdout output",
                stderr="stderr output",
            )

            manager = ContainerManager()
            manager._containers[0] = ContainerInfo(
                container_id="abc123",
                name="zerg-worker-0",
                status="running",
                worker_id=0,
            )

            logs = manager.get_logs(0)

            assert "stdout output" in logs
            assert "stderr output" in logs

    def test_get_logs_custom_tail(self) -> None:
        """Test getting logs with custom tail lines."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(
                returncode=0,
                stdout="output",
                stderr="",
            )

            manager = ContainerManager()
            manager._containers[0] = ContainerInfo(
                container_id="abc123",
                name="zerg-worker-0",
                status="running",
                worker_id=0,
            )

            manager.get_logs(0, tail=50)

            call_args = mock_docker.call_args[0]
            assert "--tail" in call_args
            assert "50" in call_args

    def test_get_logs_follow(self) -> None:
        """Test getting logs with follow option."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(
                returncode=0,
                stdout="streaming output",
                stderr="",
            )

            manager = ContainerManager()
            manager._containers[0] = ContainerInfo(
                container_id="abc123",
                name="zerg-worker-0",
                status="running",
                worker_id=0,
            )

            manager.get_logs(0, follow=True)

            call_args = mock_docker.call_args[0]
            assert "-f" in call_args

    def test_get_logs_not_found(self) -> None:
        """Test getting logs for non-existent worker."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()

            logs = manager.get_logs(99)

            assert logs == ""


class TestHealthCheck:
    """Tests for health checking."""

    def test_health_check_healthy(self) -> None:
        """Test health check for healthy container."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(
                returncode=0,
                stdout="running\n",
                stderr="",
            )

            manager = ContainerManager()
            manager._containers[0] = ContainerInfo(
                container_id="abc123",
                name="zerg-worker-0",
                status="running",
                worker_id=0,
            )

            healthy = manager.health_check(0)

            assert healthy is True

    def test_health_check_unhealthy(self) -> None:
        """Test health check for unhealthy container."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(
                returncode=0,
                stdout="exited\n",
                stderr="",
            )

            manager = ContainerManager()
            manager._containers[0] = ContainerInfo(
                container_id="abc123",
                name="zerg-worker-0",
                status="running",
                worker_id=0,
            )

            healthy = manager.health_check(0)

            assert healthy is False

    def test_health_check_not_found(self) -> None:
        """Test health check for non-existent worker."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()

            healthy = manager.health_check(99)

            assert healthy is False


class TestExecInWorker:
    """Tests for executing commands in workers."""

    def test_exec_allowed_command(self) -> None:
        """Test executing allowed command."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(
                returncode=0,
                stdout="output",
                stderr="",
            )

            manager = ContainerManager()
            manager._containers[0] = ContainerInfo(
                container_id="abc123",
                name="zerg-worker-0",
                status="running",
                worker_id=0,
            )

            exit_code, stdout, stderr = manager.exec_in_worker(0, "pytest tests/")

            assert exit_code == 0
            assert stdout == "output"

    def test_exec_blocked_command(self) -> None:
        """Test executing blocked command."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()
            manager._containers[0] = ContainerInfo(
                container_id="abc123",
                name="zerg-worker-0",
                status="running",
                worker_id=0,
            )

            exit_code, stdout, stderr = manager.exec_in_worker(
                0,
                "rm -rf /; echo pwned",
                validate=True,
            )

            assert exit_code == -1
            assert "validation failed" in stderr.lower()

    def test_exec_shell_metacharacters_blocked(self) -> None:
        """Test shell metacharacters are blocked."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()
            manager._containers[0] = ContainerInfo(
                container_id="abc123",
                name="zerg-worker-0",
                status="running",
                worker_id=0,
            )

            exit_code, stdout, stderr = manager.exec_in_worker(
                0,
                "echo `whoami`",
                validate=True,
            )

            assert exit_code == -1
            assert "metacharacters" in stderr.lower()

    def test_exec_validation_disabled(self) -> None:
        """Test execution with validation disabled."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(
                returncode=0,
                stdout="output",
                stderr="",
            )

            manager = ContainerManager()
            manager._containers[0] = ContainerInfo(
                container_id="abc123",
                name="zerg-worker-0",
                status="running",
                worker_id=0,
            )

            exit_code, stdout, stderr = manager.exec_in_worker(
                0,
                "custom_command",
                validate=False,
            )

            assert exit_code == 0

    def test_exec_worker_not_found(self) -> None:
        """Test exec on non-existent worker."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()

            exit_code, stdout, stderr = manager.exec_in_worker(99, "echo test")

            assert exit_code == -1
            assert "not found" in stderr.lower()

    def test_exec_with_custom_timeout(self) -> None:
        """Test exec with custom timeout."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(
                returncode=0,
                stdout="output",
                stderr="",
            )

            manager = ContainerManager()
            manager._containers[0] = ContainerInfo(
                container_id="abc123",
                name="zerg-worker-0",
                status="running",
                worker_id=0,
            )

            manager.exec_in_worker(0, "pytest tests/", timeout=120)

            mock_docker.assert_called_with(
                "exec",
                "abc123",
                "sh",
                "-c",
                "pytest tests/",
                check=False,
                timeout=120,
            )


class TestCommandValidation:
    """Tests for command validation."""

    def test_validate_pytest(self) -> None:
        """Test pytest is allowed."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()

            is_valid, error = manager._validate_exec_command("pytest tests/")

            assert is_valid is True

    def test_validate_python_m_pytest(self) -> None:
        """Test python -m pytest is allowed."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()

            is_valid, error = manager._validate_exec_command("python -m pytest tests/")

            assert is_valid is True

    def test_validate_git_status(self) -> None:
        """Test git status is allowed."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()

            is_valid, error = manager._validate_exec_command("git status")

            assert is_valid is True

    def test_validate_git_diff(self) -> None:
        """Test git diff is allowed."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()

            is_valid, error = manager._validate_exec_command("git diff HEAD")

            assert is_valid is True

    def test_validate_git_log(self) -> None:
        """Test git log is allowed."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()

            is_valid, error = manager._validate_exec_command("git log --oneline")

            assert is_valid is True

    def test_validate_empty(self) -> None:
        """Test empty command rejected."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()

            is_valid, error = manager._validate_exec_command("")

            assert is_valid is False
            assert "empty" in error.lower()

    def test_validate_dangerous_pipe(self) -> None:
        """Test pipe is rejected."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()

            is_valid, error = manager._validate_exec_command("cat file | bash")

            assert is_valid is False
            assert "metacharacters" in error.lower()

    def test_validate_dangerous_semicolon(self) -> None:
        """Test semicolon is rejected."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()

            is_valid, error = manager._validate_exec_command("echo hi; rm -rf /")

            assert is_valid is False
            assert "metacharacters" in error.lower()

    def test_validate_dangerous_backtick(self) -> None:
        """Test backtick is rejected."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()

            is_valid, error = manager._validate_exec_command("echo `id`")

            assert is_valid is False
            assert "metacharacters" in error.lower()

    def test_validate_not_in_allowlist(self) -> None:
        """Test command not in allowlist is rejected."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()

            is_valid, error = manager._validate_exec_command("curl http://evil.com")

            assert is_valid is False
            assert "not in allowlist" in error.lower()

    def test_validate_ruff(self) -> None:
        """Test ruff is allowed."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()

            is_valid, error = manager._validate_exec_command("ruff check .")

            assert is_valid is True

    def test_validate_make(self) -> None:
        """Test make is allowed."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()

            is_valid, error = manager._validate_exec_command("make build")

            assert is_valid is True

    def test_validate_pwd(self) -> None:
        """Test pwd is allowed."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()

            is_valid, error = manager._validate_exec_command("pwd")

            assert is_valid is True

    def test_validate_ls(self) -> None:
        """Test ls is allowed."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()

            is_valid, error = manager._validate_exec_command("ls -la")

            assert is_valid is True

    def test_validate_empty_split_fallback(self) -> None:
        """Test command that splits to empty list."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()

            # A command of just whitespace
            is_valid, error = manager._validate_exec_command("   ")

            # Should handle empty command
            assert is_valid is False


class TestCleanupVolumes:
    """Tests for volume cleanup."""

    def test_cleanup_volumes(self) -> None:
        """Test cleaning up volumes."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(returncode=0)

            manager = ContainerManager()
            manager.cleanup_volumes("test-feature")

            mock_docker.assert_called_once()
            call_args = mock_docker.call_args[0]
            assert "volume" in call_args
            assert "rm" in call_args
            assert "zerg-tasks-test-feature" in call_args


class TestGetAllContainers:
    """Tests for getting all containers."""

    def test_get_all_containers(self) -> None:
        """Test getting all tracked containers."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()
            manager._containers = {
                0: ContainerInfo("a", "worker-0", "running", 0),
                1: ContainerInfo("b", "worker-1", "running", 1),
            }

            containers = manager.get_all_containers()

            assert len(containers) == 2
            assert 0 in containers
            assert 1 in containers

    def test_get_all_containers_returns_copy(self) -> None:
        """Test getting containers returns a copy."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()
            manager._containers = {
                0: ContainerInfo("a", "worker-0", "running", 0),
            }

            containers = manager.get_all_containers()
            containers[99] = ContainerInfo("x", "worker-99", "running", 99)

            # Original should not be modified
            assert 99 not in manager._containers

    def test_get_all_containers_empty(self) -> None:
        """Test getting containers when none exist."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()

            containers = manager.get_all_containers()

            assert len(containers) == 0
            assert containers == {}
