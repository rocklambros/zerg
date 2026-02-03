"""Comprehensive unit tests for launcher module to achieve 100% coverage.

Tests all launcher components including:
- SubprocessLauncher: spawn, monitor, terminate, wait methods
- ContainerLauncher: spawn, monitor, terminate, container management
- Environment variable validation and security
- Edge cases and error handling
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

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
    get_plugin_launcher,
    validate_env_vars,
)

# =============================================================================
# validate_env_vars Tests
# =============================================================================


class TestValidateEnvVars:
    """Tests for environment variable validation."""

    def test_allowed_env_var_passes(self) -> None:
        """Test that allowed environment variables pass validation."""
        env = {"ZERG_WORKER_ID": "1", "ANTHROPIC_API_KEY": "sk-test"}
        result = validate_env_vars(env)
        assert "ZERG_WORKER_ID" in result
        assert "ANTHROPIC_API_KEY" in result

    def test_zerg_prefixed_var_passes(self) -> None:
        """Test ZERG_ prefixed variables are allowed."""
        env = {"ZERG_CUSTOM_VAR": "value", "ZERG_ANOTHER": "test"}
        result = validate_env_vars(env)
        assert "ZERG_CUSTOM_VAR" in result
        assert "ZERG_ANOTHER" in result

    def test_dangerous_var_blocked(self) -> None:
        """Test dangerous environment variables are blocked."""
        for dangerous in ["PATH", "LD_PRELOAD", "HOME", "DYLD_INSERT_LIBRARIES"]:
            env = {dangerous: "/malicious"}
            result = validate_env_vars(env)
            assert dangerous not in result

    def test_shell_metacharacters_blocked(self) -> None:
        """Test values with shell metacharacters are blocked."""
        metachar_values = [
            "value; rm -rf /",
            "value | evil",
            "value & background",
            "`evil`",
            "$HOME",
            "$(evil)",
            "value < file",
            "value > file",
        ]
        for val in metachar_values:
            env = {"ZERG_TEST": val}
            result = validate_env_vars(env)
            assert "ZERG_TEST" not in result

    def test_unlisted_var_skipped(self) -> None:
        """Test unlisted variables are skipped."""
        env = {"RANDOM_UNKNOWN_VAR": "value"}
        result = validate_env_vars(env)
        assert "RANDOM_UNKNOWN_VAR" not in result

    def test_empty_dict_returns_empty(self) -> None:
        """Test empty input returns empty output."""
        assert validate_env_vars({}) == {}

    def test_mixed_vars_filtered_correctly(self) -> None:
        """Test mixed allowed/blocked vars are correctly filtered."""
        env = {
            "ZERG_WORKER_ID": "1",  # allowed
            "PATH": "/bad",  # dangerous
            "ANTHROPIC_API_KEY": "sk-xxx",  # allowed
            "ZERG_BAD": "value; rm",  # blocked due to metachar
            "UNKNOWN": "val",  # unlisted
        }
        result = validate_env_vars(env)
        assert result == {"ZERG_WORKER_ID": "1", "ANTHROPIC_API_KEY": "sk-xxx"}


class TestAllowedEnvVarsConstant:
    """Tests for ALLOWED_ENV_VARS constant."""

    def test_contains_zerg_vars(self) -> None:
        """Test ZERG-specific vars are in allowed list."""
        zerg_vars = [
            "ZERG_WORKER_ID",
            "ZERG_FEATURE",
            "ZERG_WORKTREE",
            "ZERG_BRANCH",
            "ZERG_TASK_ID",
            "ZERG_SPEC_DIR",
        ]
        for var in zerg_vars:
            assert var in ALLOWED_ENV_VARS

    def test_contains_api_keys(self) -> None:
        """Test API key vars are in allowed list."""
        assert "ANTHROPIC_API_KEY" in ALLOWED_ENV_VARS
        assert "OPENAI_API_KEY" in ALLOWED_ENV_VARS


class TestDangerousEnvVarsConstant:
    """Tests for DANGEROUS_ENV_VARS constant."""

    def test_contains_path_vars(self) -> None:
        """Test PATH-related vars are dangerous."""
        assert "PATH" in DANGEROUS_ENV_VARS
        assert "PYTHONPATH" in DANGEROUS_ENV_VARS
        assert "NODE_PATH" in DANGEROUS_ENV_VARS

    def test_contains_library_loading_vars(self) -> None:
        """Test library loading vars are dangerous."""
        assert "LD_PRELOAD" in DANGEROUS_ENV_VARS
        assert "LD_LIBRARY_PATH" in DANGEROUS_ENV_VARS
        assert "DYLD_INSERT_LIBRARIES" in DANGEROUS_ENV_VARS


# =============================================================================
# LauncherType Tests
# =============================================================================


class TestLauncherType:
    """Tests for LauncherType enum."""

    def test_subprocess_value(self) -> None:
        """Test subprocess type value."""
        assert LauncherType.SUBPROCESS.value == "subprocess"

    def test_container_value(self) -> None:
        """Test container type value."""
        assert LauncherType.CONTAINER.value == "container"


# =============================================================================
# LauncherConfig Tests
# =============================================================================


class TestLauncherConfig:
    """Tests for LauncherConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = LauncherConfig()
        assert config.launcher_type == LauncherType.SUBPROCESS
        assert config.timeout_seconds == 3600
        assert config.env_vars == {}
        assert config.working_dir is None
        assert config.log_dir is None

    def test_custom_values(self, tmp_path: Path) -> None:
        """Test custom configuration values."""
        config = LauncherConfig(
            launcher_type=LauncherType.CONTAINER,
            timeout_seconds=1800,
            env_vars={"KEY": "value"},
            working_dir=tmp_path,
            log_dir=tmp_path / "logs",
        )
        assert config.launcher_type == LauncherType.CONTAINER
        assert config.timeout_seconds == 1800
        assert config.env_vars == {"KEY": "value"}
        assert config.working_dir == tmp_path
        assert config.log_dir == tmp_path / "logs"


# =============================================================================
# SpawnResult Tests
# =============================================================================


class TestSpawnResult:
    """Tests for SpawnResult dataclass."""

    def test_success_result(self) -> None:
        """Test successful spawn result."""
        handle = WorkerHandle(worker_id=0, pid=12345)
        result = SpawnResult(success=True, worker_id=0, handle=handle)
        assert result.success is True
        assert result.worker_id == 0
        assert result.handle is handle
        assert result.error is None

    def test_failure_result(self) -> None:
        """Test failed spawn result."""
        result = SpawnResult(success=False, worker_id=0, error="Spawn failed")
        assert result.success is False
        assert result.handle is None
        assert result.error == "Spawn failed"


# =============================================================================
# WorkerHandle Tests
# =============================================================================


class TestWorkerHandle:
    """Tests for WorkerHandle dataclass."""

    def test_default_values(self) -> None:
        """Test default values for WorkerHandle."""
        handle = WorkerHandle(worker_id=0)
        assert handle.worker_id == 0
        assert handle.pid is None
        assert handle.container_id is None
        assert handle.status == WorkerStatus.INITIALIZING
        assert handle.exit_code is None
        assert isinstance(handle.started_at, datetime)

    def test_with_pid(self) -> None:
        """Test WorkerHandle with PID."""
        handle = WorkerHandle(worker_id=1, pid=12345)
        assert handle.pid == 12345

    def test_with_container_id(self) -> None:
        """Test WorkerHandle with container ID."""
        handle = WorkerHandle(worker_id=1, container_id="abc123")
        assert handle.container_id == "abc123"

    def test_is_alive_alive_states(self) -> None:
        """Test is_alive returns True for alive states."""
        alive_states = [
            WorkerStatus.INITIALIZING,
            WorkerStatus.READY,
            WorkerStatus.RUNNING,
            WorkerStatus.IDLE,
            WorkerStatus.CHECKPOINTING,
        ]
        for status in alive_states:
            handle = WorkerHandle(worker_id=0, status=status)
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
            handle = WorkerHandle(worker_id=0, status=status)
            assert handle.is_alive() is False, f"Expected not alive for {status}"


# =============================================================================
# SubprocessLauncher Tests
# =============================================================================


class TestSubprocessLauncherInit:
    """Tests for SubprocessLauncher initialization."""

    def test_init_default_config(self) -> None:
        """Test initialization with default config."""
        launcher = SubprocessLauncher()
        assert launcher.config is not None
        assert launcher.config.launcher_type == LauncherType.SUBPROCESS
        assert launcher._workers == {}
        assert launcher._processes == {}
        assert launcher._output_buffers == {}

    def test_init_custom_config(self) -> None:
        """Test initialization with custom config."""
        config = LauncherConfig(timeout_seconds=1800)
        launcher = SubprocessLauncher(config=config)
        assert launcher.config.timeout_seconds == 1800


class TestSubprocessLauncherSpawn:
    """Tests for SubprocessLauncher.spawn method."""

    @patch("subprocess.Popen")
    def test_spawn_success(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test successful worker spawn."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="zerg/test/worker-0",
        )

        assert result.success is True
        assert result.worker_id == 0
        assert result.handle is not None
        assert result.handle.pid == 12345
        assert result.handle.status == WorkerStatus.INITIALIZING

        # Verify command
        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert sys.executable in cmd[0]
        assert "-m" in cmd
        assert "zerg.worker_main" in cmd

        # Verify environment
        env = call_args[1]["env"]
        assert env["ZERG_WORKER_ID"] == "0"
        assert env["ZERG_FEATURE"] == "test-feature"

    @patch("subprocess.Popen")
    def test_spawn_with_config_env_vars(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test spawn applies config env vars."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        config = LauncherConfig(env_vars={"ZERG_DEBUG": "true"})
        launcher = SubprocessLauncher(config=config)
        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is True
        env = mock_popen.call_args[1]["env"]
        assert env["ZERG_DEBUG"] == "true"

    @patch("subprocess.Popen")
    def test_spawn_with_additional_env(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test spawn applies additional env vars."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
            env={"ZERG_CUSTOM": "value"},
        )

        assert result.success is True
        env = mock_popen.call_args[1]["env"]
        assert env["ZERG_CUSTOM"] == "value"

    @patch("subprocess.Popen")
    def test_spawn_with_log_dir(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test spawn creates log files when log_dir is set."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        log_dir = tmp_path / "logs"
        config = LauncherConfig(log_dir=log_dir)
        launcher = SubprocessLauncher(config=config)

        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is True
        assert log_dir.exists()

    @patch("subprocess.Popen")
    def test_spawn_invalid_worker_id(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test spawn with invalid worker ID."""
        log_dir = tmp_path / "logs"
        config = LauncherConfig(log_dir=log_dir)
        launcher = SubprocessLauncher(config=config)

        result = launcher.spawn(
            worker_id=-1,  # Invalid
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False
        assert "Invalid worker_id" in result.error

    @patch("subprocess.Popen")
    def test_spawn_failure(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test spawn failure handling."""
        mock_popen.side_effect = OSError("Failed to spawn")

        launcher = SubprocessLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False
        assert "Failed to spawn" in result.error

    @patch("subprocess.Popen")
    def test_spawn_uses_working_dir(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test spawn uses config working_dir."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        work_dir = tmp_path / "work"
        work_dir.mkdir()
        config = LauncherConfig(working_dir=work_dir)
        launcher = SubprocessLauncher(config=config)

        launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        call_args = mock_popen.call_args
        assert call_args[1]["cwd"] == work_dir


class TestSubprocessLauncherMonitor:
    """Tests for SubprocessLauncher.monitor method."""

    def test_monitor_unknown_worker(self) -> None:
        """Test monitoring unknown worker returns STOPPED."""
        launcher = SubprocessLauncher()
        status = launcher.monitor(999)
        assert status == WorkerStatus.STOPPED

    @patch("subprocess.Popen")
    def test_monitor_running_worker(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test monitoring running worker."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None  # Still running
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        status = launcher.monitor(0)
        assert status == WorkerStatus.RUNNING

    @patch("subprocess.Popen")
    def test_monitor_exited_success(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test monitoring worker that exited with code 0."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = 0
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        status = launcher.monitor(0)
        assert status == WorkerStatus.STOPPED

    @patch("subprocess.Popen")
    def test_monitor_checkpoint_exit(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test monitoring worker that exited with checkpoint code (2)."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = 2  # Checkpoint
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        status = launcher.monitor(0)
        assert status == WorkerStatus.CHECKPOINTING

    @patch("subprocess.Popen")
    def test_monitor_blocked_exit(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test monitoring worker that exited with blocked code (3)."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = 3  # Blocked
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        status = launcher.monitor(0)
        assert status == WorkerStatus.BLOCKED

    @patch("subprocess.Popen")
    def test_monitor_crashed_exit(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test monitoring worker that crashed (exit code 1)."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = 1  # Error
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        status = launcher.monitor(0)
        assert status == WorkerStatus.CRASHED


class TestSubprocessLauncherTerminate:
    """Tests for SubprocessLauncher.terminate method."""

    def test_terminate_unknown_worker(self) -> None:
        """Test terminating unknown worker returns False."""
        launcher = SubprocessLauncher()
        result = launcher.terminate(999)
        assert result is False

    @patch("subprocess.Popen")
    def test_terminate_graceful(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test graceful termination."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        result = launcher.terminate(0)

        assert result is True
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called()

    @patch("subprocess.Popen")
    def test_terminate_force(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test forced termination."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        result = launcher.terminate(0, force=True)

        assert result is True
        mock_process.kill.assert_called_once()

    @patch("subprocess.Popen")
    def test_terminate_timeout_then_kill(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test termination with timeout triggers kill."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = 0
        mock_process.wait.side_effect = [
            subprocess.TimeoutExpired("cmd", 10),
            None,  # Second wait succeeds
        ]
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        result = launcher.terminate(0)

        assert result is True
        mock_process.kill.assert_called_once()

    @patch("subprocess.Popen")
    def test_terminate_exception(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test termination failure handling."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.terminate.side_effect = OSError("Failed")
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        result = launcher.terminate(0)

        assert result is False


class TestSubprocessLauncherGetOutput:
    """Tests for SubprocessLauncher.get_output method."""

    def test_get_output_from_log_file(self, tmp_path: Path) -> None:
        """Test getting output from log file."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        log_file = log_dir / "worker-0.stdout.log"
        log_file.write_text("line1\nline2\nline3\nline4\n")

        config = LauncherConfig(log_dir=log_dir)
        launcher = SubprocessLauncher(config=config)

        output = launcher.get_output(0, tail=2)

        assert "line3" in output
        assert "line4" in output
        assert "line1" not in output

    def test_get_output_from_buffer(self) -> None:
        """Test getting output from buffer when no log file."""
        launcher = SubprocessLauncher()
        launcher._output_buffers[0] = ["line1", "line2", "line3"]

        output = launcher.get_output(0, tail=2)

        assert "line2" in output
        assert "line3" in output

    def test_get_output_no_data(self) -> None:
        """Test getting output when no data available."""
        launcher = SubprocessLauncher()
        output = launcher.get_output(999)
        assert output == ""


class TestSubprocessLauncherWaitForReady:
    """Tests for SubprocessLauncher.wait_for_ready method."""

    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_wait_for_ready_becomes_running(self, mock_sleep: MagicMock, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test wait_for_ready returns True when worker becomes running."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        # First poll: None (still initializing), then None (running)
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        result = launcher.wait_for_ready(0, timeout=1.0)

        assert result is True

    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_wait_for_ready_crashes(self, mock_sleep: MagicMock, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test wait_for_ready returns False when worker crashes."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = 1  # Crashed immediately
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        result = launcher.wait_for_ready(0, timeout=1.0)

        assert result is False

    def test_wait_for_ready_timeout_path(self) -> None:
        """Test wait_for_ready timeout path by directly testing the loop.

        This tests the timeout return path (line 509-510) by simulating
        a worker that stays in BLOCKED state without transitioning.
        """
        launcher = SubprocessLauncher()

        # Manually set up a worker in BLOCKED state
        # BLOCKED is not in the success states (RUNNING, READY)
        # and not in the failure states (CRASHED, STOPPED)
        # so it will loop until timeout
        handle = WorkerHandle(worker_id=0, status=WorkerStatus.BLOCKED)
        launcher._workers[0] = handle

        # Create a mock process that always reports non-terminal state
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Still running
        launcher._processes[0] = mock_process

        # Override monitor to always return BLOCKED
        def fake_monitor(worker_id: int) -> WorkerStatus:
            return WorkerStatus.BLOCKED

        launcher.monitor = fake_monitor  # type: ignore[method-assign]

        # Use a very short timeout
        with patch("time.sleep"):
            result = launcher.wait_for_ready(0, timeout=0.01)

        assert result is False


class TestSubprocessLauncherWaitAll:
    """Tests for SubprocessLauncher.wait_all method."""

    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_wait_all_all_stopped(self, mock_sleep: MagicMock, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test wait_all returns when all workers stopped."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = 0  # All stopped
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )
        launcher.spawn(
            worker_id=1,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch-1",
        )

        result = launcher.wait_all()

        assert 0 in result
        assert 1 in result
        assert result[0] == WorkerStatus.STOPPED
        assert result[1] == WorkerStatus.STOPPED

    @patch("subprocess.Popen")
    @patch("time.time")
    @patch("time.sleep")
    def test_wait_all_timeout(
        self,
        mock_sleep: MagicMock,
        mock_time: MagicMock,
        mock_popen: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test wait_all returns on timeout."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None  # Still running
        mock_popen.return_value = mock_process

        # Simulate timeout
        mock_time.side_effect = [0, 0, 15]  # Start, check, timeout

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        result = launcher.wait_all(timeout=10.0)

        assert 0 in result
        assert result[0] == WorkerStatus.RUNNING


# =============================================================================
# WorkerLauncher Base Class Tests
# =============================================================================


class TestWorkerLauncherBase:
    """Tests for WorkerLauncher abstract base class methods."""

    def test_get_handle_found(self) -> None:
        """Test get_handle returns handle when found."""
        launcher = SubprocessLauncher()
        handle = WorkerHandle(worker_id=0, pid=12345)
        launcher._workers[0] = handle

        result = launcher.get_handle(0)

        assert result is handle

    def test_get_handle_not_found(self) -> None:
        """Test get_handle returns None when not found."""
        launcher = SubprocessLauncher()
        result = launcher.get_handle(999)
        assert result is None

    def test_get_all_workers(self) -> None:
        """Test get_all_workers returns copy of workers dict."""
        launcher = SubprocessLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0)
        launcher._workers[1] = WorkerHandle(worker_id=1)

        result = launcher.get_all_workers()

        assert len(result) == 2
        assert 0 in result
        assert 1 in result
        # Verify it's a copy
        result[999] = WorkerHandle(worker_id=999)
        assert 999 not in launcher._workers

    @patch("subprocess.Popen")
    def test_terminate_all(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test terminate_all terminates all workers."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        for i in range(3):
            launcher.spawn(
                worker_id=i,
                feature="test",
                worktree_path=tmp_path,
                branch=f"test-branch-{i}",
            )

        results = launcher.terminate_all()

        assert len(results) == 3
        assert all(r is True for r in results.values())

    def test_terminate_all_empty(self) -> None:
        """Test terminate_all with no workers."""
        launcher = SubprocessLauncher()
        results = launcher.terminate_all()
        assert results == {}

    def test_get_status_summary_empty(self) -> None:
        """Test get_status_summary with no workers."""
        launcher = SubprocessLauncher()
        summary = launcher.get_status_summary()
        assert summary["total"] == 0
        assert summary["alive"] == 0
        assert summary["by_status"] == {}

    def test_get_status_summary_mixed(self) -> None:
        """Test get_status_summary with mixed worker states."""
        launcher = SubprocessLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, status=WorkerStatus.RUNNING)
        launcher._workers[1] = WorkerHandle(worker_id=1, status=WorkerStatus.RUNNING)
        launcher._workers[2] = WorkerHandle(worker_id=2, status=WorkerStatus.STOPPED)
        launcher._workers[3] = WorkerHandle(worker_id=3, status=WorkerStatus.CRASHED)

        summary = launcher.get_status_summary()

        assert summary["total"] == 4
        assert summary["alive"] == 2
        assert summary["by_status"]["running"] == 2
        assert summary["by_status"]["stopped"] == 1
        assert summary["by_status"]["crashed"] == 1


# =============================================================================
# ContainerLauncher Tests
# =============================================================================


class TestContainerLauncherInit:
    """Tests for ContainerLauncher initialization."""

    def test_init_defaults(self) -> None:
        """Test initialization with default values."""
        launcher = ContainerLauncher()
        assert launcher.image_name == "zerg-worker"
        assert launcher.network == "bridge"
        assert launcher._container_ids == {}

    def test_init_custom_image(self) -> None:
        """Test initialization with custom image."""
        launcher = ContainerLauncher(image_name="custom-image")
        assert launcher.image_name == "custom-image"

    def test_init_custom_network(self) -> None:
        """Test initialization with custom network."""
        launcher = ContainerLauncher(network="custom-network")
        assert launcher.network == "custom-network"

    def test_class_constants(self) -> None:
        """Test class constants are defined."""
        assert ContainerLauncher.DEFAULT_NETWORK == "bridge"
        assert ContainerLauncher.CONTAINER_PREFIX == "zerg-worker"
        assert ContainerLauncher.WORKER_ENTRY_SCRIPT == ".zerg/worker_entry.sh"


class TestContainerLauncherSpawn:
    """Tests for ContainerLauncher.spawn method."""

    @patch("subprocess.run")
    @patch.object(ContainerLauncher, "_verify_worker_process")
    @patch.object(ContainerLauncher, "_exec_worker_entry")
    @patch.object(ContainerLauncher, "_wait_ready")
    @patch.object(ContainerLauncher, "_start_container")
    def test_spawn_success(
        self,
        mock_start: MagicMock,
        mock_wait: MagicMock,
        mock_exec: MagicMock,
        mock_verify: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test successful container spawn."""
        mock_start.return_value = "container-abc123"
        mock_wait.return_value = True
        mock_exec.return_value = True
        mock_verify.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is True
        assert result.handle is not None
        assert result.handle.container_id == "container-abc123"
        assert result.handle.status == WorkerStatus.RUNNING

    @patch("subprocess.run")
    @patch.object(ContainerLauncher, "_start_container")
    def test_spawn_container_start_fails(self, mock_start: MagicMock, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test spawn failure when container start fails."""
        mock_start.return_value = None
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False
        assert "Failed to start container" in result.error

    @patch("subprocess.run")
    @patch.object(ContainerLauncher, "_wait_ready")
    @patch.object(ContainerLauncher, "_start_container")
    def test_spawn_container_not_ready(
        self, mock_start: MagicMock, mock_wait: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test spawn failure when container doesn't become ready."""
        mock_start.return_value = "container-abc123"
        mock_wait.return_value = False
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False
        assert "failed to become ready" in result.error

    @patch("subprocess.run")
    @patch.object(ContainerLauncher, "_start_container")
    def test_spawn_invalid_worker_id(self, mock_start: MagicMock, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test spawn with invalid worker ID."""
        mock_run.return_value = MagicMock(returncode=0)
        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=-1,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False
        assert "Invalid worker_id" in result.error
        mock_start.assert_not_called()

    @patch("subprocess.run")
    @patch.object(ContainerLauncher, "_exec_worker_entry")
    @patch.object(ContainerLauncher, "_wait_ready")
    @patch.object(ContainerLauncher, "_start_container")
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test-key"})
    def test_spawn_with_api_key(
        self,
        mock_start: MagicMock,
        mock_wait: MagicMock,
        mock_exec: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test spawn includes API key from environment."""
        mock_start.return_value = "container-abc123"
        mock_wait.return_value = True
        mock_exec.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        # Verify API key was passed to container
        call_env = mock_start.call_args[1]["env"]
        assert "ANTHROPIC_API_KEY" in call_env

    @patch("subprocess.run")
    @patch.object(ContainerLauncher, "_exec_worker_entry")
    @patch.object(ContainerLauncher, "_wait_ready")
    @patch.object(ContainerLauncher, "_start_container")
    def test_spawn_with_config_env_vars(
        self,
        mock_start: MagicMock,
        mock_wait: MagicMock,
        mock_exec: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test spawn applies config env vars."""
        mock_start.return_value = "container-abc123"
        mock_wait.return_value = True
        mock_exec.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        config = LauncherConfig(env_vars={"ZERG_DEBUG": "true"})
        launcher = ContainerLauncher(config=config)
        launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        # Verify config env var was passed
        call_env = mock_start.call_args[1]["env"]
        assert call_env.get("ZERG_DEBUG") == "true"

    @patch("subprocess.run")
    @patch.object(ContainerLauncher, "_exec_worker_entry")
    @patch.object(ContainerLauncher, "_wait_ready")
    @patch.object(ContainerLauncher, "_start_container")
    def test_spawn_with_additional_env(
        self,
        mock_start: MagicMock,
        mock_wait: MagicMock,
        mock_exec: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test spawn applies caller-provided env vars."""
        mock_start.return_value = "container-abc123"
        mock_wait.return_value = True
        mock_exec.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
            env={"ZERG_CUSTOM": "value"},
        )

        # Verify additional env var was passed
        call_env = mock_start.call_args[1]["env"]
        assert call_env.get("ZERG_CUSTOM") == "value"

    @patch("subprocess.run")
    @patch.object(ContainerLauncher, "_start_container")
    def test_spawn_exception_handling(self, mock_start: MagicMock, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test spawn handles exceptions."""
        mock_start.side_effect = Exception("Docker error")
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert result.success is False
        assert "Docker error" in result.error


class TestContainerLauncherStartContainer:
    """Tests for ContainerLauncher._start_container method."""

    @patch("subprocess.run")
    def test_start_container_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test successful container start."""
        mock_run.return_value = MagicMock(returncode=0, stdout="container-id-abc123\n", stderr="")

        launcher = ContainerLauncher()
        result = launcher._start_container(
            container_name="zerg-worker-0",
            worktree_path=tmp_path,
            env={"ZERG_WORKER_ID": "0"},
        )

        assert result == "container-id-abc123"
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_start_container_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test container start failure."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error starting container")

        launcher = ContainerLauncher()
        result = launcher._start_container(
            container_name="zerg-worker-0",
            worktree_path=tmp_path,
            env={},
        )

        assert result is None

    @patch("subprocess.run")
    def test_start_container_timeout(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test container start timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("docker", 60)

        launcher = ContainerLauncher()
        result = launcher._start_container(
            container_name="zerg-worker-0",
            worktree_path=tmp_path,
            env={},
        )

        assert result is None

    @patch("subprocess.run")
    def test_start_container_exception(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test container start exception."""
        mock_run.side_effect = Exception("Docker error")

        launcher = ContainerLauncher()
        result = launcher._start_container(
            container_name="zerg-worker-0",
            worktree_path=tmp_path,
            env={},
        )

        assert result is None


class TestContainerLauncherWaitReady:
    """Tests for ContainerLauncher._wait_ready method."""

    @patch("subprocess.run")
    @patch("time.sleep")
    def test_wait_ready_success(self, mock_sleep: MagicMock, mock_run: MagicMock) -> None:
        """Test wait_ready returns True when container running."""
        mock_run.return_value = MagicMock(returncode=0, stdout="true\n", stderr="")

        launcher = ContainerLauncher()
        result = launcher._wait_ready("container-abc", timeout=5)

        assert result is True

    @patch("subprocess.run")
    @patch("time.time")
    @patch("time.sleep")
    def test_wait_ready_timeout(self, mock_sleep: MagicMock, mock_time: MagicMock, mock_run: MagicMock) -> None:
        """Test wait_ready returns False on timeout."""
        mock_run.return_value = MagicMock(returncode=0, stdout="false\n", stderr="")
        mock_time.side_effect = [0, 0, 35]  # Exceeds timeout

        launcher = ContainerLauncher()
        result = launcher._wait_ready("container-abc", timeout=30)

        assert result is False

    @patch("subprocess.run")
    @patch("time.time")
    @patch("time.sleep")
    def test_wait_ready_exception_handling(
        self, mock_sleep: MagicMock, mock_time: MagicMock, mock_run: MagicMock
    ) -> None:
        """Test wait_ready handles exceptions."""
        mock_run.side_effect = subprocess.TimeoutExpired("docker", 10)
        mock_time.side_effect = [0, 0, 35]

        launcher = ContainerLauncher()
        result = launcher._wait_ready("container-abc", timeout=30)

        assert result is False


class TestContainerLauncherExecWorkerEntry:
    """Tests for ContainerLauncher._exec_worker_entry method."""

    @patch("subprocess.run")
    def test_exec_worker_entry_success(self, mock_run: MagicMock) -> None:
        """Test successful exec of worker entry script."""
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        result = launcher._exec_worker_entry("container-abc")

        assert result is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_exec_worker_entry_failure(self, mock_run: MagicMock) -> None:
        """Test failed exec of worker entry script."""
        mock_run.return_value = MagicMock(returncode=1)

        launcher = ContainerLauncher()
        result = launcher._exec_worker_entry("container-abc")

        assert result is False

    @patch("subprocess.run")
    def test_exec_worker_entry_exception(self, mock_run: MagicMock) -> None:
        """Test exec worker entry handles exceptions."""
        mock_run.side_effect = Exception("Docker exec error")

        launcher = ContainerLauncher()
        result = launcher._exec_worker_entry("container-abc")

        assert result is False


class TestContainerLauncherMonitor:
    """Tests for ContainerLauncher.monitor method."""

    def test_monitor_unknown_worker(self) -> None:
        """Test monitoring unknown worker returns STOPPED."""
        launcher = ContainerLauncher()
        status = launcher.monitor(999)
        assert status == WorkerStatus.STOPPED

    @patch("subprocess.run")
    def test_monitor_running_container(self, mock_run: MagicMock) -> None:
        """Test monitoring running container."""
        mock_run.return_value = MagicMock(returncode=0, stdout="true,0\n", stderr="")

        launcher = ContainerLauncher()
        handle = WorkerHandle(worker_id=0, container_id="container-abc")
        launcher._workers[0] = handle
        launcher._container_ids[0] = "container-abc"

        status = launcher.monitor(0)

        assert status == WorkerStatus.RUNNING

    @patch("subprocess.run")
    def test_monitor_exited_success(self, mock_run: MagicMock) -> None:
        """Test monitoring container that exited with code 0."""
        mock_run.return_value = MagicMock(returncode=0, stdout="false,0\n", stderr="")

        launcher = ContainerLauncher()
        handle = WorkerHandle(worker_id=0, container_id="container-abc")
        launcher._workers[0] = handle
        launcher._container_ids[0] = "container-abc"

        status = launcher.monitor(0)

        assert status == WorkerStatus.STOPPED

    @patch("subprocess.run")
    def test_monitor_checkpoint_exit(self, mock_run: MagicMock) -> None:
        """Test monitoring container with checkpoint exit code (2)."""
        mock_run.return_value = MagicMock(returncode=0, stdout="false,2\n", stderr="")

        launcher = ContainerLauncher()
        handle = WorkerHandle(worker_id=0, container_id="container-abc")
        launcher._workers[0] = handle
        launcher._container_ids[0] = "container-abc"

        status = launcher.monitor(0)

        assert status == WorkerStatus.CHECKPOINTING

    @patch("subprocess.run")
    def test_monitor_blocked_exit(self, mock_run: MagicMock) -> None:
        """Test monitoring container with blocked exit code (3)."""
        mock_run.return_value = MagicMock(returncode=0, stdout="false,3\n", stderr="")

        launcher = ContainerLauncher()
        handle = WorkerHandle(worker_id=0, container_id="container-abc")
        launcher._workers[0] = handle
        launcher._container_ids[0] = "container-abc"

        status = launcher.monitor(0)

        assert status == WorkerStatus.BLOCKED

    @patch("subprocess.run")
    def test_monitor_crashed_exit(self, mock_run: MagicMock) -> None:
        """Test monitoring container with crash exit code."""
        mock_run.return_value = MagicMock(returncode=0, stdout="false,1\n", stderr="")

        launcher = ContainerLauncher()
        handle = WorkerHandle(worker_id=0, container_id="container-abc")
        launcher._workers[0] = handle
        launcher._container_ids[0] = "container-abc"

        status = launcher.monitor(0)

        assert status == WorkerStatus.CRASHED

    @patch("subprocess.run")
    def test_monitor_docker_inspect_fails(self, mock_run: MagicMock) -> None:
        """Test monitoring when docker inspect fails."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error")

        launcher = ContainerLauncher()
        handle = WorkerHandle(worker_id=0, container_id="container-abc")
        launcher._workers[0] = handle
        launcher._container_ids[0] = "container-abc"

        status = launcher.monitor(0)

        assert status == WorkerStatus.STOPPED

    @patch("subprocess.run")
    def test_monitor_exception_handling(self, mock_run: MagicMock) -> None:
        """Test monitor handles exceptions."""
        mock_run.side_effect = Exception("Docker error")

        launcher = ContainerLauncher()
        handle = WorkerHandle(worker_id=0, container_id="container-abc", status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._container_ids[0] = "container-abc"

        status = launcher.monitor(0)

        # Should return current status on exception
        assert status == WorkerStatus.RUNNING


class TestContainerLauncherTerminate:
    """Tests for ContainerLauncher.terminate method."""

    def test_terminate_unknown_worker(self) -> None:
        """Test terminating unknown worker."""
        launcher = ContainerLauncher()
        result = launcher.terminate(999)
        assert result is False

    @patch("subprocess.run")
    def test_terminate_graceful(self, mock_run: MagicMock) -> None:
        """Test graceful termination."""
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        handle = WorkerHandle(worker_id=0, container_id="container-abc")
        launcher._workers[0] = handle
        launcher._container_ids[0] = "container-abc"

        result = launcher.terminate(0)

        assert result is True
        assert handle.status == WorkerStatus.STOPPED
        # Verify docker stop was called
        calls = mock_run.call_args_list
        assert any("stop" in str(c) for c in calls)

    @patch("subprocess.run")
    def test_terminate_force(self, mock_run: MagicMock) -> None:
        """Test forced termination."""
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        handle = WorkerHandle(worker_id=0, container_id="container-abc")
        launcher._workers[0] = handle
        launcher._container_ids[0] = "container-abc"

        result = launcher.terminate(0, force=True)

        assert result is True
        # Verify docker kill was called
        calls = mock_run.call_args_list
        assert any("kill" in str(c) for c in calls)

    @patch("subprocess.run")
    def test_terminate_failure(self, mock_run: MagicMock) -> None:
        """Test terminate failure."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Container not found")

        launcher = ContainerLauncher()
        handle = WorkerHandle(worker_id=0, container_id="container-abc")
        launcher._workers[0] = handle
        launcher._container_ids[0] = "container-abc"

        result = launcher.terminate(0)

        assert result is False

    @patch("subprocess.run")
    def test_terminate_timeout_then_kill(self, mock_run: MagicMock) -> None:
        """Test terminate timeout triggers kill."""
        # First call (stop) times out, second call (kill) succeeds
        mock_run.side_effect = [
            subprocess.TimeoutExpired("docker stop", 30),
            MagicMock(returncode=0),  # docker kill
        ]

        launcher = ContainerLauncher()
        handle = WorkerHandle(worker_id=0, container_id="container-abc")
        launcher._workers[0] = handle
        launcher._container_ids[0] = "container-abc"

        result = launcher.terminate(0)

        assert result is True
        assert handle.status == WorkerStatus.STOPPED

    @patch("subprocess.run")
    def test_terminate_exception(self, mock_run: MagicMock) -> None:
        """Test terminate handles exception."""
        mock_run.side_effect = Exception("Docker error")

        launcher = ContainerLauncher()
        handle = WorkerHandle(worker_id=0, container_id="container-abc")
        launcher._workers[0] = handle
        launcher._container_ids[0] = "container-abc"

        result = launcher.terminate(0)

        assert result is False

    @patch("subprocess.run")
    def test_terminate_cleans_up_container_id(self, mock_run: MagicMock) -> None:
        """Test terminate cleans up container ID reference."""
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        handle = WorkerHandle(worker_id=0, container_id="container-abc")
        launcher._workers[0] = handle
        launcher._container_ids[0] = "container-abc"

        launcher.terminate(0)

        assert 0 not in launcher._container_ids


class TestContainerLauncherGetOutput:
    """Tests for ContainerLauncher.get_output method."""

    @patch("subprocess.run")
    def test_get_output_success(self, mock_run: MagicMock) -> None:
        """Test getting container output."""
        mock_run.return_value = MagicMock(returncode=0, stdout="line1\nline2\n", stderr="error line\n")

        launcher = ContainerLauncher()
        launcher._container_ids[0] = "container-abc"

        output = launcher.get_output(0, tail=100)

        assert "line1" in output
        assert "line2" in output
        assert "error line" in output

    def test_get_output_unknown_worker(self) -> None:
        """Test getting output for unknown worker."""
        launcher = ContainerLauncher()
        output = launcher.get_output(999)
        assert output == ""

    @patch("subprocess.run")
    def test_get_output_exception(self, mock_run: MagicMock) -> None:
        """Test get_output handles exception."""
        mock_run.side_effect = Exception("Docker logs error")

        launcher = ContainerLauncher()
        launcher._container_ids[0] = "container-abc"

        output = launcher.get_output(0)

        assert output == ""


class TestContainerLauncherEnsureNetwork:
    """Tests for ContainerLauncher.ensure_network method."""

    @patch("subprocess.run")
    def test_ensure_network_exists(self, mock_run: MagicMock) -> None:
        """Test ensure_network when network already exists."""
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        result = launcher.ensure_network()

        assert result is True
        # Should only call inspect, not create
        assert mock_run.call_count == 1

    @patch("subprocess.run")
    def test_ensure_network_creates(self, mock_run: MagicMock) -> None:
        """Test ensure_network creates network when missing."""
        # First call (inspect) fails, second call (create) succeeds
        mock_run.side_effect = [
            MagicMock(returncode=1),  # inspect fails
            MagicMock(returncode=0),  # create succeeds
        ]

        launcher = ContainerLauncher()
        result = launcher.ensure_network()

        assert result is True
        assert mock_run.call_count == 2

    @patch("subprocess.run")
    def test_ensure_network_create_fails(self, mock_run: MagicMock) -> None:
        """Test ensure_network when create fails."""
        mock_run.side_effect = [
            MagicMock(returncode=1),  # inspect fails
            MagicMock(returncode=1, stderr="Network create error"),  # create fails
        ]

        launcher = ContainerLauncher()
        result = launcher.ensure_network()

        assert result is False

    @patch("subprocess.run")
    def test_ensure_network_exception(self, mock_run: MagicMock) -> None:
        """Test ensure_network handles exception."""
        mock_run.side_effect = Exception("Docker network error")

        launcher = ContainerLauncher()
        result = launcher.ensure_network()

        assert result is False


class TestContainerLauncherImageExists:
    """Tests for ContainerLauncher.image_exists method."""

    @patch("subprocess.run")
    def test_image_exists_true(self, mock_run: MagicMock) -> None:
        """Test image_exists returns True when image found."""
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        result = launcher.image_exists()

        assert result is True

    @patch("subprocess.run")
    def test_image_exists_false(self, mock_run: MagicMock) -> None:
        """Test image_exists returns False when image not found."""
        mock_run.return_value = MagicMock(returncode=1)

        launcher = ContainerLauncher()
        result = launcher.image_exists()

        assert result is False

    @patch("subprocess.run")
    def test_image_exists_exception(self, mock_run: MagicMock) -> None:
        """Test image_exists handles exception."""
        mock_run.side_effect = Exception("Docker error")

        launcher = ContainerLauncher()
        result = launcher.image_exists()

        assert result is False


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


class TestLauncherEdgeCases:
    """Edge case tests for launcher components."""

    @patch("subprocess.Popen")
    def test_spawn_stores_worker_correctly(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test spawn correctly stores worker references."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        assert 0 in launcher._workers
        assert 0 in launcher._processes
        assert 0 in launcher._output_buffers

    @patch("subprocess.Popen")
    def test_multiple_workers_tracked_independently(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test multiple workers are tracked independently."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()

        # Spawn multiple workers
        for i in range(3):
            launcher.spawn(
                worker_id=i,
                feature="test",
                worktree_path=tmp_path,
                branch=f"test-branch-{i}",
            )

        # All workers should be tracked
        assert len(launcher._workers) == 3
        for i in range(3):
            assert launcher._workers[i].worker_id == i

    def test_worker_handle_ready_state_is_alive(self) -> None:
        """Test worker in READY state is considered alive."""
        handle = WorkerHandle(worker_id=0, status=WorkerStatus.READY)
        assert handle.is_alive() is True

    def test_worker_handle_idle_state_is_alive(self) -> None:
        """Test worker in IDLE state is considered alive."""
        handle = WorkerHandle(worker_id=0, status=WorkerStatus.IDLE)
        assert handle.is_alive() is True


# =============================================================================
# Plugin Launcher Integration Tests
# =============================================================================


class TestGetPluginLauncher:
    """Tests for get_plugin_launcher function."""

    def test_get_plugin_launcher_none_registry(self) -> None:
        """Test get_plugin_launcher returns None when registry is None."""
        result = get_plugin_launcher("test-launcher", None)
        assert result is None

    def test_get_plugin_launcher_not_found(self) -> None:
        """Test get_plugin_launcher returns None when launcher not in registry."""
        from zerg.plugins import PluginRegistry

        registry = PluginRegistry()
        result = get_plugin_launcher("nonexistent", registry)
        assert result is None

    def test_get_plugin_launcher_success(self) -> None:
        """Test get_plugin_launcher returns launcher from registry."""
        from zerg.plugins import LauncherPlugin, PluginRegistry

        # Create a test launcher plugin
        class TestLauncherPlugin(LauncherPlugin):
            @property
            def name(self) -> str:
                return "test-launcher"

            def create_launcher(self, config: Any) -> Any:
                return SubprocessLauncher()

        registry = PluginRegistry()
        plugin = TestLauncherPlugin()
        registry.register_launcher(plugin)

        result = get_plugin_launcher("test-launcher", registry)

        assert result is not None
        assert isinstance(result, SubprocessLauncher)

    def test_get_plugin_launcher_exception(self) -> None:
        """Test get_plugin_launcher returns None when create_launcher raises."""
        from zerg.plugins import LauncherPlugin, PluginRegistry

        # Create a test launcher plugin that fails
        class FailingLauncherPlugin(LauncherPlugin):
            @property
            def name(self) -> str:
                return "failing-launcher"

            def create_launcher(self, config: Any) -> Any:
                raise RuntimeError("Failed to create launcher")

        registry = PluginRegistry()
        plugin = FailingLauncherPlugin()
        registry.register_launcher(plugin)

        result = get_plugin_launcher("failing-launcher", registry)

        assert result is None


# =============================================================================
# spawn_with_retry Tests (FR-1: Spawn Retry with Exponential Backoff)
# =============================================================================


class TestSpawnWithRetry:
    """Tests for spawn_with_retry method with exponential backoff."""

    @patch.object(SubprocessLauncher, "spawn")
    @patch("zerg.launcher.time.sleep")
    def test_spawn_with_retry_success_first_attempt(
        self, mock_sleep: MagicMock, mock_spawn: MagicMock, tmp_path: Path
    ) -> None:
        """Test spawn_with_retry succeeds on first attempt (no retries needed)."""
        mock_spawn.return_value = SpawnResult(
            success=True,
            worker_id=0,
            handle=WorkerHandle(worker_id=0, pid=12345, status=WorkerStatus.RUNNING),
        )

        launcher = SubprocessLauncher()
        result = launcher.spawn_with_retry(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="main",
        )

        assert result.success is True
        assert result.worker_id == 0
        assert mock_spawn.call_count == 1
        mock_sleep.assert_not_called()  # No retry delay needed

    @patch.object(SubprocessLauncher, "spawn")
    @patch("zerg.launcher.time.sleep")
    def test_spawn_with_retry_success_after_failures(
        self, mock_sleep: MagicMock, mock_spawn: MagicMock, tmp_path: Path
    ) -> None:
        """Test spawn_with_retry succeeds after initial failures."""
        # Fail twice, then succeed on third attempt
        mock_spawn.side_effect = [
            SpawnResult(success=False, worker_id=0, error="Docker not ready"),
            SpawnResult(success=False, worker_id=0, error="Network timeout"),
            SpawnResult(
                success=True,
                worker_id=0,
                handle=WorkerHandle(worker_id=0, pid=12345, status=WorkerStatus.RUNNING),
            ),
        ]

        launcher = SubprocessLauncher()
        result = launcher.spawn_with_retry(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="main",
            max_attempts=3,
            backoff_base_seconds=2.0,
            backoff_max_seconds=30.0,
        )

        assert result.success is True
        assert result.worker_id == 0
        assert mock_spawn.call_count == 3
        assert mock_sleep.call_count == 2  # Sleep between retry 1->2 and 2->3

    @patch.object(SubprocessLauncher, "spawn")
    @patch("zerg.launcher.time.sleep")
    def test_spawn_with_retry_all_attempts_fail(
        self, mock_sleep: MagicMock, mock_spawn: MagicMock, tmp_path: Path
    ) -> None:
        """Test spawn_with_retry fails after exhausting all attempts."""
        mock_spawn.return_value = SpawnResult(success=False, worker_id=0, error="Persistent failure")

        launcher = SubprocessLauncher()
        result = launcher.spawn_with_retry(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="main",
            max_attempts=3,
        )

        assert result.success is False
        assert result.worker_id == 0
        assert "Persistent failure" in str(result.error)
        assert mock_spawn.call_count == 3
        assert mock_sleep.call_count == 2  # Sleep between attempts

    @patch.object(SubprocessLauncher, "spawn")
    @patch("zerg.launcher.time.sleep")
    def test_spawn_with_retry_respects_max_attempts(
        self, mock_sleep: MagicMock, mock_spawn: MagicMock, tmp_path: Path
    ) -> None:
        """Test spawn_with_retry stops at max_attempts."""
        mock_spawn.return_value = SpawnResult(success=False, worker_id=0, error="Failure")

        launcher = SubprocessLauncher()
        result = launcher.spawn_with_retry(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="main",
            max_attempts=5,
        )

        assert result.success is False
        assert mock_spawn.call_count == 5

    @patch.object(SubprocessLauncher, "spawn")
    @patch("zerg.launcher.time.sleep")
    def test_spawn_with_retry_no_retries_when_max_attempts_is_one(
        self, mock_sleep: MagicMock, mock_spawn: MagicMock, tmp_path: Path
    ) -> None:
        """Test spawn_with_retry with max_attempts=1 does not retry."""
        mock_spawn.return_value = SpawnResult(success=False, worker_id=0, error="Immediate failure")

        launcher = SubprocessLauncher()
        result = launcher.spawn_with_retry(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="main",
            max_attempts=1,
        )

        assert result.success is False
        assert mock_spawn.call_count == 1
        mock_sleep.assert_not_called()

    @patch.object(SubprocessLauncher, "spawn")
    @patch("zerg.launcher.time.sleep")
    def test_spawn_with_retry_exponential_backoff(
        self, mock_sleep: MagicMock, mock_spawn: MagicMock, tmp_path: Path
    ) -> None:
        """Test spawn_with_retry uses exponential backoff."""
        mock_spawn.return_value = SpawnResult(success=False, worker_id=0, error="Failure")

        launcher = SubprocessLauncher()
        launcher.spawn_with_retry(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="main",
            max_attempts=4,
            backoff_strategy="exponential",
            backoff_base_seconds=2.0,
            backoff_max_seconds=30.0,
        )

        # With exponential backoff and base=2:
        # attempt 1 fails -> sleep ~4s (2 * 2^1 = 4, with jitter)
        # attempt 2 fails -> sleep ~8s (2 * 2^2 = 8, with jitter)
        # attempt 3 fails -> sleep ~16s (2 * 2^3 = 16, with jitter)
        # attempt 4 fails -> no more sleep
        assert mock_sleep.call_count == 3
        # Check delays are increasing (exponential pattern)
        delays = [call.args[0] for call in mock_sleep.call_args_list]
        # Allow for jitter variation (+/- 10%)
        assert delays[0] < delays[1] < delays[2]

    @patch.object(SubprocessLauncher, "spawn")
    @patch("zerg.launcher.time.sleep")
    def test_spawn_with_retry_passes_env_to_spawn(
        self, mock_sleep: MagicMock, mock_spawn: MagicMock, tmp_path: Path
    ) -> None:
        """Test spawn_with_retry passes env variables to underlying spawn."""
        mock_spawn.return_value = SpawnResult(
            success=True,
            worker_id=0,
            handle=WorkerHandle(worker_id=0, pid=12345, status=WorkerStatus.RUNNING),
        )

        launcher = SubprocessLauncher()
        env = {"CUSTOM_VAR": "value"}
        result = launcher.spawn_with_retry(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="main",
            env=env,
        )

        assert result.success is True
        mock_spawn.assert_called_once()
        call_args = mock_spawn.call_args
        assert call_args[0] == (0, "test-feature", tmp_path, "main", env)


class TestSpawnWithRetryAsync:
    """Tests for async spawn_with_retry_async method."""

    @pytest.mark.asyncio
    @patch.object(SubprocessLauncher, "spawn_async")
    @patch("zerg.launcher.asyncio.sleep")
    async def test_spawn_with_retry_async_success_first_attempt(
        self, mock_sleep: MagicMock, mock_spawn_async: MagicMock, tmp_path: Path
    ) -> None:
        """Test async spawn_with_retry succeeds on first attempt."""
        mock_spawn_async.return_value = SpawnResult(
            success=True,
            worker_id=0,
            handle=WorkerHandle(worker_id=0, pid=12345, status=WorkerStatus.RUNNING),
        )

        launcher = SubprocessLauncher()
        result = await launcher.spawn_with_retry_async(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="main",
        )

        assert result.success is True
        assert mock_spawn_async.call_count == 1
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(SubprocessLauncher, "spawn_async")
    @patch("zerg.launcher.asyncio.sleep")
    async def test_spawn_with_retry_async_retries_on_failure(
        self, mock_sleep: MagicMock, mock_spawn_async: MagicMock, tmp_path: Path
    ) -> None:
        """Test async spawn_with_retry retries on failure with async sleep."""
        mock_spawn_async.side_effect = [
            SpawnResult(success=False, worker_id=0, error="Transient error"),
            SpawnResult(
                success=True,
                worker_id=0,
                handle=WorkerHandle(worker_id=0, pid=12345, status=WorkerStatus.RUNNING),
            ),
        ]
        # asyncio.sleep needs to be a coroutine
        mock_sleep.return_value = None

        launcher = SubprocessLauncher()
        result = await launcher.spawn_with_retry_async(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="main",
            max_attempts=3,
        )

        assert result.success is True
        assert mock_spawn_async.call_count == 2
        assert mock_sleep.call_count == 1  # Only one retry needed

    @pytest.mark.asyncio
    @patch.object(SubprocessLauncher, "spawn_async")
    @patch("zerg.launcher.asyncio.sleep")
    async def test_spawn_with_retry_async_all_attempts_fail(
        self, mock_sleep: MagicMock, mock_spawn_async: MagicMock, tmp_path: Path
    ) -> None:
        """Test async spawn_with_retry fails after all attempts exhausted."""
        mock_spawn_async.return_value = SpawnResult(success=False, worker_id=0, error="Persistent async failure")
        mock_sleep.return_value = None

        launcher = SubprocessLauncher()
        result = await launcher.spawn_with_retry_async(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="main",
            max_attempts=3,
        )

        assert result.success is False
        assert "Persistent async failure" in str(result.error)
        assert mock_spawn_async.call_count == 3


class TestContainerLauncherSpawnWithRetry:
    """Tests for spawn_with_retry in ContainerLauncher."""

    @patch.object(ContainerLauncher, "spawn")
    @patch("zerg.launcher.time.sleep")
    def test_container_spawn_with_retry_success(
        self, mock_sleep: MagicMock, mock_spawn: MagicMock, tmp_path: Path
    ) -> None:
        """Test ContainerLauncher spawn_with_retry works correctly."""
        mock_spawn.return_value = SpawnResult(
            success=True,
            worker_id=0,
            handle=WorkerHandle(
                worker_id=0,
                container_id="abc123",
                status=WorkerStatus.RUNNING,
            ),
        )

        launcher = ContainerLauncher(image_name="test-image:latest")
        result = launcher.spawn_with_retry(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="main",
        )

        assert result.success is True
        assert result.handle.container_id == "abc123"
        mock_spawn.assert_called_once()

    @patch.object(ContainerLauncher, "spawn")
    @patch("zerg.launcher.time.sleep")
    def test_container_spawn_with_retry_recovers_from_docker_error(
        self, mock_sleep: MagicMock, mock_spawn: MagicMock, tmp_path: Path
    ) -> None:
        """Test ContainerLauncher spawn_with_retry recovers from Docker errors."""
        mock_spawn.side_effect = [
            SpawnResult(success=False, worker_id=0, error="Docker daemon not responding"),
            SpawnResult(
                success=True,
                worker_id=0,
                handle=WorkerHandle(
                    worker_id=0,
                    container_id="recovered123",
                    status=WorkerStatus.RUNNING,
                ),
            ),
        ]

        launcher = ContainerLauncher(image_name="test-image:latest")
        result = launcher.spawn_with_retry(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="main",
            max_attempts=3,
        )

        assert result.success is True
        assert result.handle.container_id == "recovered123"
        assert mock_spawn.call_count == 2
        assert mock_sleep.call_count == 1
