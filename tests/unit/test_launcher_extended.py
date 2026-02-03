"""Extended unit tests for launcher module (TC-023).

Tests edge cases and security validation for launcher components.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from zerg.constants import WorkerStatus
from zerg.launcher import (
    ALLOWED_ENV_VARS,
    DANGEROUS_ENV_VARS,
    ContainerLauncher,
    LauncherConfig,
    LauncherType,
    SpawnResult,
    SubprocessLauncher,
    WorkerHandle,
    validate_env_vars,
)


class TestValidateEnvVars:
    """Tests for environment variable validation."""

    def test_validate_allowed_var(self) -> None:
        """Test allowed variables pass validation."""
        env = {"ZERG_WORKER_ID": "1"}

        result = validate_env_vars(env)

        assert "ZERG_WORKER_ID" in result
        assert result["ZERG_WORKER_ID"] == "1"

    def test_validate_zerg_prefixed(self) -> None:
        """Test ZERG_ prefixed variables pass."""
        env = {"ZERG_CUSTOM_VAR": "value"}

        result = validate_env_vars(env)

        assert "ZERG_CUSTOM_VAR" in result

    def test_validate_blocks_dangerous(self) -> None:
        """Test dangerous variables are blocked."""
        env = {"PATH": "/malicious/path"}

        result = validate_env_vars(env)

        assert "PATH" not in result

    def test_validate_blocks_ld_preload(self) -> None:
        """Test LD_PRELOAD is blocked."""
        env = {"LD_PRELOAD": "/malicious.so"}

        result = validate_env_vars(env)

        assert "LD_PRELOAD" not in result

    def test_validate_blocks_shell_metacharacters(self) -> None:
        """Test values with shell metacharacters are blocked."""
        env = {"ZERG_TEST": "value; rm -rf /"}

        result = validate_env_vars(env)

        assert "ZERG_TEST" not in result

    def test_validate_blocks_pipe(self) -> None:
        """Test values with pipe are blocked."""
        env = {"ZERG_TEST": "value | evil"}

        result = validate_env_vars(env)

        assert "ZERG_TEST" not in result

    def test_validate_blocks_backtick(self) -> None:
        """Test values with backtick are blocked."""
        env = {"ZERG_TEST": "`evil`"}

        result = validate_env_vars(env)

        assert "ZERG_TEST" not in result

    def test_validate_blocks_dollar_sign(self) -> None:
        """Test values with $ are blocked."""
        env = {"ZERG_TEST": "$HOME"}

        result = validate_env_vars(env)

        assert "ZERG_TEST" not in result

    def test_validate_blocks_subshell(self) -> None:
        """Test values with subshell are blocked."""
        env = {"ZERG_TEST": "$(evil)"}

        result = validate_env_vars(env)

        assert "ZERG_TEST" not in result

    def test_validate_unlisted_skipped(self) -> None:
        """Test unlisted variables are skipped."""
        env = {"RANDOM_VAR": "value"}

        result = validate_env_vars(env)

        assert "RANDOM_VAR" not in result

    def test_validate_multiple_vars(self) -> None:
        """Test validating multiple variables."""
        env = {
            "ZERG_WORKER_ID": "1",
            "PATH": "/bad",
            "ANTHROPIC_API_KEY": "sk-xxx",
            "ZERG_DEBUG": "true",
        }

        result = validate_env_vars(env)

        assert "ZERG_WORKER_ID" in result
        assert "PATH" not in result
        assert "ANTHROPIC_API_KEY" in result
        assert "ZERG_DEBUG" in result

    def test_validate_empty_dict(self) -> None:
        """Test validating empty dict."""
        result = validate_env_vars({})

        assert result == {}


class TestLauncherConfig:
    """Tests for LauncherConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration."""
        config = LauncherConfig()

        assert config.launcher_type == LauncherType.SUBPROCESS
        assert config.timeout_seconds == 3600
        assert config.env_vars == {}
        assert config.working_dir is None
        assert config.log_dir is None

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = LauncherConfig(
            launcher_type=LauncherType.CONTAINER,
            timeout_seconds=1800,
            env_vars={"TEST": "value"},
            working_dir=Path("/tmp"),
        )

        assert config.launcher_type == LauncherType.CONTAINER
        assert config.timeout_seconds == 1800
        assert config.env_vars == {"TEST": "value"}
        assert config.working_dir == Path("/tmp")


class TestSpawnResult:
    """Tests for SpawnResult dataclass."""

    def test_success_result(self) -> None:
        """Test successful spawn result."""
        handle = MagicMock()
        result = SpawnResult(success=True, worker_id=1, handle=handle)

        assert result.success is True
        assert result.worker_id == 1
        assert result.handle is handle
        assert result.error is None

    def test_failure_result(self) -> None:
        """Test failed spawn result."""
        result = SpawnResult(success=False, worker_id=1, error="Failed to start")

        assert result.success is False
        assert result.error == "Failed to start"
        assert result.handle is None


class TestWorkerHandle:
    """Tests for WorkerHandle dataclass."""

    def test_handle_creation(self) -> None:
        """Test creating a worker handle."""
        handle = WorkerHandle(worker_id=1, pid=12345)

        assert handle.worker_id == 1
        assert handle.pid == 12345
        assert handle.status == WorkerStatus.INITIALIZING

    def test_handle_with_container(self) -> None:
        """Test handle with container ID."""
        handle = WorkerHandle(worker_id=1, container_id="abc123")

        assert handle.container_id == "abc123"
        assert handle.pid is None

    def test_is_alive_running_states(self) -> None:
        """Test is_alive returns True for running states."""
        alive_states = [
            WorkerStatus.INITIALIZING,
            WorkerStatus.READY,
            WorkerStatus.RUNNING,
            WorkerStatus.IDLE,
            WorkerStatus.CHECKPOINTING,
        ]

        for status in alive_states:
            handle = WorkerHandle(worker_id=1, status=status)
            assert handle.is_alive() is True, f"Expected alive for {status}"

    def test_is_alive_dead_states(self) -> None:
        """Test is_alive returns False for dead states."""
        dead_states = [
            WorkerStatus.STOPPING,
            WorkerStatus.STOPPED,
            WorkerStatus.CRASHED,
            WorkerStatus.BLOCKED,
        ]

        for status in dead_states:
            handle = WorkerHandle(worker_id=1, status=status)
            assert handle.is_alive() is False, f"Expected not alive for {status}"

    def test_handle_started_at(self) -> None:
        """Test handle has started_at timestamp."""
        handle = WorkerHandle(worker_id=1)

        assert handle.started_at is not None
        assert isinstance(handle.started_at, datetime)


class TestSubprocessLauncher:
    """Tests for SubprocessLauncher."""

    def test_init_with_default_config(self) -> None:
        """Test initialization with default config."""
        launcher = SubprocessLauncher()

        assert launcher.config is not None
        assert launcher.config.launcher_type == LauncherType.SUBPROCESS

    def test_init_with_custom_config(self) -> None:
        """Test initialization with custom config."""
        config = LauncherConfig(timeout_seconds=1800)
        launcher = SubprocessLauncher(config=config)

        assert launcher.config.timeout_seconds == 1800

    def test_spawn_creates_handle(self, tmp_path: Path) -> None:
        """Test spawn creates worker handle."""
        launcher = SubprocessLauncher()

        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process

            result = launcher.spawn(
                worker_id=0,
                feature="test",
                worktree_path=tmp_path,
                branch="test-branch",
            )

            assert result.success is True
            assert result.handle is not None
            assert result.handle.worker_id == 0

    def test_spawn_failure(self, tmp_path: Path) -> None:
        """Test spawn failure handling."""
        launcher = SubprocessLauncher()

        with patch("subprocess.Popen") as mock_popen:
            mock_popen.side_effect = OSError("Failed to start")

            result = launcher.spawn(
                worker_id=0,
                feature="test",
                worktree_path=tmp_path,
                branch="test-branch",
            )

            assert result.success is False
            assert "Failed" in result.error

    def test_monitor_running(self) -> None:
        """Test monitoring running worker."""
        launcher = SubprocessLauncher()
        handle = WorkerHandle(worker_id=0, pid=12345, status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle

        # Mock the process in _processes dict
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Still running
        launcher._processes[0] = mock_process

        status = launcher.monitor(0)

        assert status == WorkerStatus.RUNNING

    def test_monitor_unknown_worker(self) -> None:
        """Test monitoring unknown worker."""
        launcher = SubprocessLauncher()

        status = launcher.monitor(999)

        assert status == WorkerStatus.STOPPED

    def test_terminate_worker(self) -> None:
        """Test terminating a worker."""
        launcher = SubprocessLauncher()

        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process

            launcher.spawn(
                worker_id=0,
                feature="test",
                worktree_path=Path("/tmp"),
                branch="test-branch",
            )

            result = launcher.terminate(0)

            assert result is True
            mock_process.terminate.assert_called()

    def test_terminate_unknown_worker(self) -> None:
        """Test terminating unknown worker."""
        launcher = SubprocessLauncher()

        result = launcher.terminate(999)

        assert result is False

    def test_get_handle(self) -> None:
        """Test getting worker handle."""
        launcher = SubprocessLauncher()
        handle = WorkerHandle(worker_id=0, pid=12345)
        launcher._workers[0] = handle

        result = launcher.get_handle(0)

        assert result is handle

    def test_get_handle_unknown(self) -> None:
        """Test getting unknown handle."""
        launcher = SubprocessLauncher()

        result = launcher.get_handle(999)

        assert result is None

    def test_get_all_workers(self) -> None:
        """Test getting all workers."""
        launcher = SubprocessLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0)
        launcher._workers[1] = WorkerHandle(worker_id=1)

        result = launcher.get_all_workers()

        assert len(result) == 2
        assert 0 in result
        assert 1 in result


class TestContainerLauncher:
    """Tests for ContainerLauncher."""

    def test_init_with_defaults(self) -> None:
        """Test initialization with defaults."""
        launcher = ContainerLauncher()

        assert launcher.image_name == "zerg-worker"
        assert launcher.network == "bridge"

    def test_init_with_custom_image(self) -> None:
        """Test initialization with custom image."""
        launcher = ContainerLauncher(image_name="custom-image")

        assert launcher.image_name == "custom-image"

    def test_init_with_custom_network(self) -> None:
        """Test initialization with custom network."""
        launcher = ContainerLauncher(network="custom-network")

        assert launcher.network == "custom-network"

    def test_constants_defined(self) -> None:
        """Test class constants are defined."""
        assert ContainerLauncher.DEFAULT_NETWORK == "bridge"
        assert ContainerLauncher.CONTAINER_PREFIX == "zerg-worker"

    def test_ensure_network_exists(self) -> None:
        """Test ensure_network when network exists."""
        launcher = ContainerLauncher()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = launcher.ensure_network()

            assert result is True

    def test_image_exists_true(self) -> None:
        """Test image_exists returns True."""
        launcher = ContainerLauncher()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="sha256:abc")

            result = launcher.image_exists()

            assert result is True

    def test_image_exists_false(self) -> None:
        """Test image_exists returns False."""
        launcher = ContainerLauncher()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")

            result = launcher.image_exists()

            assert result is False


class TestLauncherType:
    """Tests for LauncherType enum."""

    def test_subprocess_type(self) -> None:
        """Test subprocess launcher type."""
        assert LauncherType.SUBPROCESS.value == "subprocess"

    def test_container_type(self) -> None:
        """Test container launcher type."""
        assert LauncherType.CONTAINER.value == "container"


class TestAllowedEnvVars:
    """Tests for environment variable constants."""

    def test_anthropic_key_allowed(self) -> None:
        """Test ANTHROPIC_API_KEY is in allowed list."""
        assert "ANTHROPIC_API_KEY" in ALLOWED_ENV_VARS

    def test_zerg_vars_allowed(self) -> None:
        """Test ZERG vars are in allowed list."""
        assert "ZERG_WORKER_ID" in ALLOWED_ENV_VARS
        assert "ZERG_FEATURE" in ALLOWED_ENV_VARS

    def test_path_dangerous(self) -> None:
        """Test PATH is in dangerous list."""
        assert "PATH" in DANGEROUS_ENV_VARS

    def test_ld_preload_dangerous(self) -> None:
        """Test LD_PRELOAD is in dangerous list."""
        assert "LD_PRELOAD" in DANGEROUS_ENV_VARS

    def test_home_dangerous(self) -> None:
        """Test HOME is in dangerous list."""
        assert "HOME" in DANGEROUS_ENV_VARS


class TestLauncherStatusSummary:
    """Tests for launcher status summary."""

    def test_get_status_summary_empty(self) -> None:
        """Test status summary with no workers."""
        launcher = SubprocessLauncher()

        summary = launcher.get_status_summary()

        assert summary["total"] == 0
        assert summary["alive"] == 0

    def test_get_status_summary_with_workers(self) -> None:
        """Test status summary with workers."""
        launcher = SubprocessLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, status=WorkerStatus.RUNNING)
        launcher._workers[1] = WorkerHandle(worker_id=1, status=WorkerStatus.STOPPED)

        summary = launcher.get_status_summary()

        assert summary["total"] == 2


class TestTerminateAll:
    """Tests for terminate_all method."""

    def test_terminate_all_empty(self) -> None:
        """Test terminate_all with no workers."""
        launcher = SubprocessLauncher()

        result = launcher.terminate_all()

        assert result == {}

    def test_terminate_all_with_workers(self) -> None:
        """Test terminate_all with workers."""
        launcher = SubprocessLauncher()

        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process

            launcher.spawn(
                worker_id=0,
                feature="test",
                worktree_path=Path("/tmp"),
                branch="test-branch",
            )
            launcher.spawn(
                worker_id=1,
                feature="test",
                worktree_path=Path("/tmp"),
                branch="test-branch",
            )

            result = launcher.terminate_all()

            assert 0 in result
            assert 1 in result
