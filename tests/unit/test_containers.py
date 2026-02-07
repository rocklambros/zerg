"""Tests for ZERG containers module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.config import ZergConfig
from zerg.constants import WorkerStatus
from zerg.containers import ContainerInfo, ContainerManager
from zerg.exceptions import ContainerError

pytestmark = pytest.mark.docker


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
        """Test creating container info with full and minimal fields."""
        info = ContainerInfo(
            container_id="abc123",
            name="zerg-worker-0",
            status="running",
            worker_id=0,
            port=49152,
            image="zerg-worker:latest",
        )
        assert info.container_id == "abc123"
        assert info.port == 49152

        minimal = ContainerInfo(container_id="abc", name="w-0", status="running", worker_id=0)
        assert minimal.port is None
        assert minimal.image is None


class TestContainerManager:
    """Tests for ContainerManager initialization and Docker check."""

    def test_init_default_and_custom(self) -> None:
        """Test default and custom initialization."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()
            assert manager.compose_file == Path(".devcontainer/docker-compose.yaml")

            custom = ContainerManager(compose_file="/custom/docker-compose.yaml")
            assert custom.compose_file == Path("/custom/docker-compose.yaml")

    def test_check_docker_not_found(self) -> None:
        """Test _check_docker when Docker is not installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("docker not found")
            ContainerManager()


class TestDockerCommands:
    """Tests for _run_docker and _run_compose."""

    def test_run_docker_success(self) -> None:
        """Test _run_docker with successful command."""
        with patch.object(ContainerManager, "_check_docker"), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="output", stderr="")
            manager = ContainerManager()
            assert manager._run_docker("ps", "-a").returncode == 0

    def test_run_docker_error(self) -> None:
        """Test _run_docker with CalledProcessError."""
        with patch.object(ContainerManager, "_check_docker"), patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, ["docker", "ps"], stderr="error")
            manager = ContainerManager()
            with pytest.raises(ContainerError):
                manager._run_docker("ps", "-a")

    def test_run_compose_success(self) -> None:
        """Test _run_compose with successful command."""
        with patch.object(ContainerManager, "_check_docker"), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="output", stderr="")
            manager = ContainerManager()
            assert manager._run_compose("up", "-d").returncode == 0

    def test_run_compose_error(self) -> None:
        """Test _run_compose with CalledProcessError."""
        with patch.object(ContainerManager, "_check_docker"), patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, ["docker", "compose"], stderr="err")
            manager = ContainerManager()
            with pytest.raises(ContainerError):
                manager._run_compose("up", "-d")


class TestWorkerLifecycle:
    """Tests for start/stop/build worker operations."""

    def test_build(self) -> None:
        """Test building worker image."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_compose") as mock_compose,
        ):
            mock_compose.return_value = MagicMock(returncode=0)
            manager = ContainerManager()
            manager.build()
            assert "build" in mock_compose.call_args[0]

    def test_start_worker(self) -> None:
        """Test starting a worker container."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
            patch.object(ContainerManager, "_run_compose") as mock_compose,
            patch("time.sleep"),
        ):
            mock_docker.return_value = MagicMock(returncode=0, stdout="abc123def456", stderr="")
            mock_compose.return_value = MagicMock(returncode=0)
            manager = ContainerManager()
            info = manager.start_worker(0, "test-feature", 49152, "/tmp/worktree", "zerg/test/worker-0")
            assert info.worker_id == 0
            assert info.status == "running"

    def test_start_worker_unknown_fallback(self) -> None:
        """Test start_worker uses unknown fallback when no container found."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
            patch.object(ContainerManager, "_run_compose") as mock_compose,
            patch("time.sleep"),
        ):
            mock_docker.side_effect = [
                MagicMock(returncode=0, stdout="", stderr=""),
                MagicMock(returncode=0, stdout="", stderr=""),
                MagicMock(returncode=0, stdout="", stderr=""),
            ]
            mock_compose.return_value = MagicMock(returncode=0)
            manager = ContainerManager()
            info = manager.start_worker(0, "test", 49152, "/tmp", "branch")
            assert info.container_id == "unknown-0"

    def test_stop_worker(self) -> None:
        """Test stopping a tracked and non-existent worker."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(returncode=0, stdout="", stderr="")
            manager = ContainerManager()
            manager._containers[0] = ContainerInfo("abc123", "zerg-worker-0", "running", 0)
            manager.stop_worker(0)
            assert 0 not in manager._containers
            # Non-existent: should not raise
            manager.stop_worker(99)

    def test_stop_all_with_orphans(self) -> None:
        """Test stopping all workers including orphaned containers."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(returncode=0, stdout="orphan1\norphan2\n", stderr="")
            manager = ContainerManager()
            manager._containers = {0: ContainerInfo("a", "zerg-worker-0", "running", 0)}
            count = manager.stop_all()
            assert count == 3
            assert len(manager._containers) == 0


class TestGetStatus:
    """Tests for getting worker status."""

    @pytest.mark.parametrize(
        "docker_status,expected",
        [
            ("running\n", WorkerStatus.RUNNING),
            ("exited\n", WorkerStatus.STOPPED),
            ("dead\n", WorkerStatus.CRASHED),
        ],
    )
    def test_get_status(self, docker_status: str, expected: WorkerStatus) -> None:
        """Test getting worker status from docker status string."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(returncode=0, stdout=docker_status, stderr="")
            manager = ContainerManager()
            manager._containers[0] = ContainerInfo("abc123", "zerg-worker-0", "running", 0)
            assert manager.get_status(0) == expected

    def test_get_status_not_tracked(self) -> None:
        """Test getting status for untracked worker."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()
            assert manager.get_status(99) == WorkerStatus.STOPPED


class TestGetLogs:
    """Tests for getting container logs."""

    def test_get_logs(self) -> None:
        """Test getting logs for tracked and non-existent worker."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(returncode=0, stdout="Log line 1\n", stderr="")
            manager = ContainerManager()
            manager._containers[0] = ContainerInfo("abc123", "zerg-worker-0", "running", 0)
            assert "Log line 1" in manager.get_logs(0)
            assert manager.get_logs(99) == ""


class TestHealthCheck:
    """Tests for health checking."""

    def test_health_check(self) -> None:
        """Test health check for healthy and non-existent worker."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(returncode=0, stdout="running\n", stderr="")
            manager = ContainerManager()
            manager._containers[0] = ContainerInfo("abc123", "zerg-worker-0", "running", 0)
            assert manager.health_check(0) is True
            assert manager.health_check(99) is False


class TestExecInWorker:
    """Tests for executing commands in workers."""

    def test_exec_allowed_command(self) -> None:
        """Test executing allowed command."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(returncode=0, stdout="output", stderr="")
            manager = ContainerManager()
            manager._containers[0] = ContainerInfo("abc123", "zerg-worker-0", "running", 0)
            exit_code, stdout, _ = manager.exec_in_worker(0, "pytest tests/")
            assert exit_code == 0
            assert stdout == "output"

    def test_exec_blocked_and_not_found(self) -> None:
        """Test executing blocked command and non-existent worker."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()
            manager._containers[0] = ContainerInfo("abc123", "zerg-worker-0", "running", 0)
            exit_code, _, stderr = manager.exec_in_worker(0, "rm -rf /; echo pwned", validate=True)
            assert exit_code == -1
            assert "validation failed" in stderr.lower()

            exit_code, _, stderr = manager.exec_in_worker(99, "echo test")
            assert exit_code == -1
            assert "not found" in stderr.lower()


class TestCommandValidation:
    """Tests for command validation."""

    @pytest.mark.parametrize("cmd", ["pytest tests/", "git status"])
    def test_validate_allowed(self, cmd: str) -> None:
        """Test allowed commands pass validation."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()
            is_valid, _ = manager._validate_exec_command(cmd)
            assert is_valid is True

    @pytest.mark.parametrize(
        "cmd,error_substr",
        [("", "empty"), ("cat file | bash", "metacharacters"), ("curl http://evil.com", "not in allowlist")],
    )
    def test_validate_rejected(self, cmd: str, error_substr: str) -> None:
        """Test rejected commands fail validation with correct error."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()
            is_valid, error = manager._validate_exec_command(cmd)
            assert is_valid is False
            assert error_substr in error.lower()


class TestCleanupAndContainerList:
    """Tests for volume cleanup and container listing."""

    def test_cleanup_volumes(self) -> None:
        """Test cleaning up volumes."""
        with (
            patch.object(ContainerManager, "_check_docker"),
            patch.object(ContainerManager, "_run_docker") as mock_docker,
        ):
            mock_docker.return_value = MagicMock(returncode=0)
            manager = ContainerManager()
            manager.cleanup_volumes("test-feature")
            assert "zerg-tasks-test-feature" in mock_docker.call_args[0]

    def test_get_all_containers_returns_copy(self) -> None:
        """Test getting containers returns a copy."""
        with patch.object(ContainerManager, "_check_docker"):
            manager = ContainerManager()
            manager._containers = {0: ContainerInfo("a", "worker-0", "running", 0)}
            containers = manager.get_all_containers()
            containers[99] = ContainerInfo("x", "worker-99", "running", 99)
            assert 99 not in manager._containers
