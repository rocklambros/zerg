"""Unit tests for launcher module — thinned to essentials.

Covers: env validation, launcher types/config, subprocess+container launchers,
plugin launcher, spawn_with_retry (sync + async).
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from zerg.constants import WorkerStatus
from zerg.env_validator import validate_env_vars
from zerg.launcher_types import LauncherConfig, LauncherType, SpawnResult, WorkerHandle
from zerg.launchers import ContainerLauncher, SubprocessLauncher, get_plugin_launcher

# =============================================================================
# validate_env_vars
# =============================================================================


class TestValidateEnvVars:
    """Tests for environment variable validation."""

    def test_allowed_var_passes(self) -> None:
        env = {"ZERG_WORKER_ID": "1", "ANTHROPIC_API_KEY": "sk-test"}
        result = validate_env_vars(env)
        assert "ZERG_WORKER_ID" in result
        assert "ANTHROPIC_API_KEY" in result

    def test_mixed_vars_filtered_correctly(self) -> None:
        """Covers: dangerous blocked, metachar blocked, unknown skipped, allowed passed."""
        env = {
            "ZERG_WORKER_ID": "1",
            "PATH": "/bad",
            "ANTHROPIC_API_KEY": "sk-xxx",
            "ZERG_BAD": "value; rm",
            "UNKNOWN": "val",
        }
        result = validate_env_vars(env)
        assert result == {"ZERG_WORKER_ID": "1", "ANTHROPIC_API_KEY": "sk-xxx"}


# =============================================================================
# LauncherType / LauncherConfig / SpawnResult / WorkerHandle
# =============================================================================


class TestLauncherType:
    """Tests for LauncherType enum."""

    @pytest.mark.smoke
    def test_subprocess_value(self) -> None:
        assert LauncherType.SUBPROCESS.value == "subprocess"

    @pytest.mark.smoke
    def test_container_value(self) -> None:
        assert LauncherType.CONTAINER.value == "container"


class TestLauncherConfig:
    """Tests for LauncherConfig dataclass."""

    @pytest.mark.smoke
    def test_default_values(self) -> None:
        config = LauncherConfig()
        assert config.launcher_type == LauncherType.SUBPROCESS
        assert config.timeout_seconds == 3600
        assert config.env_vars == {}
        assert config.working_dir is None

    def test_custom_values(self, tmp_path: Path) -> None:
        config = LauncherConfig(
            launcher_type=LauncherType.CONTAINER,
            timeout_seconds=1800,
            env_vars={"KEY": "value"},
            working_dir=tmp_path,
        )
        assert config.launcher_type == LauncherType.CONTAINER
        assert config.timeout_seconds == 1800


class TestSpawnResult:
    """Tests for SpawnResult dataclass."""

    def test_success_and_failure(self) -> None:
        ok = SpawnResult(success=True, worker_id=0, handle=WorkerHandle(worker_id=0, pid=1))
        assert ok.success is True and ok.error is None
        fail = SpawnResult(success=False, worker_id=0, error="Spawn failed")
        assert fail.success is False and fail.handle is None


class TestWorkerHandle:
    """Tests for WorkerHandle dataclass."""

    def test_default_values(self) -> None:
        h = WorkerHandle(worker_id=0)
        assert h.pid is None
        assert h.status == WorkerStatus.INITIALIZING
        assert isinstance(h.started_at, datetime)

    def test_is_alive_states(self) -> None:
        """Spot-check representative alive and dead states."""
        assert WorkerHandle(worker_id=0, status=WorkerStatus.RUNNING).is_alive() is True
        assert WorkerHandle(worker_id=0, status=WorkerStatus.READY).is_alive() is True
        assert WorkerHandle(worker_id=0, status=WorkerStatus.STOPPED).is_alive() is False
        assert WorkerHandle(worker_id=0, status=WorkerStatus.CRASHED).is_alive() is False


# =============================================================================
# SubprocessLauncher
# =============================================================================


class TestSubprocessLauncherSpawn:
    """Tests for SubprocessLauncher spawn."""

    @patch("subprocess.Popen")
    def test_spawn_success(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        result = launcher.spawn(worker_id=0, feature="test-feature", worktree_path=tmp_path, branch="b")

        assert result.success is True
        assert result.handle.pid == 12345
        env = mock_popen.call_args[1]["env"]
        assert env["ZERG_WORKER_ID"] == "0"

    @patch("subprocess.Popen")
    def test_spawn_failure(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        mock_popen.side_effect = OSError("Failed to spawn")
        launcher = SubprocessLauncher()
        result = launcher.spawn(worker_id=0, feature="test", worktree_path=tmp_path, branch="b")
        assert result.success is False

    @patch("subprocess.Popen")
    def test_spawn_invalid_worker_id(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        config = LauncherConfig(log_dir=tmp_path / "logs")
        launcher = SubprocessLauncher(config=config)
        result = launcher.spawn(worker_id=-1, feature="test", worktree_path=tmp_path, branch="b")
        assert result.success is False
        assert "Invalid worker_id" in result.error


class TestSubprocessLauncherMonitor:
    """Tests for SubprocessLauncher.monitor."""

    def test_monitor_unknown_worker(self) -> None:
        launcher = SubprocessLauncher()
        assert launcher.monitor(999) == WorkerStatus.STOPPED

    @pytest.mark.parametrize(
        "poll_return,expected",
        [(None, WorkerStatus.RUNNING), (0, WorkerStatus.STOPPED), (1, WorkerStatus.CRASHED)],
    )
    @patch("subprocess.Popen")
    def test_monitor_exit_codes(self, mock_popen, tmp_path, poll_return, expected) -> None:
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = poll_return
        mock_popen.return_value = mock_process
        launcher = SubprocessLauncher()
        launcher.spawn(worker_id=0, feature="test", worktree_path=tmp_path, branch="b")
        assert launcher.monitor(0) == expected


class TestSubprocessLauncherHeartbeatMonitor:
    """Tests for SubprocessLauncher.heartbeat_monitor singleton (FR-4)."""

    def test_heartbeat_monitor_singleton_and_type(self) -> None:
        from zerg.heartbeat import HeartbeatMonitor

        launcher = SubprocessLauncher()
        assert launcher._heartbeat_monitor is None
        m1 = launcher.heartbeat_monitor
        assert m1 is launcher.heartbeat_monitor
        assert isinstance(m1, HeartbeatMonitor)


class TestSubprocessLauncherTerminate:
    """Tests for SubprocessLauncher.terminate."""

    def test_terminate_unknown(self) -> None:
        launcher = SubprocessLauncher()
        assert launcher.terminate(999) is False

    @patch("subprocess.Popen")
    def test_terminate_graceful(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        launcher = SubprocessLauncher()
        launcher.spawn(worker_id=0, feature="test", worktree_path=tmp_path, branch="b")
        assert launcher.terminate(0) is True
        mock_process.terminate.assert_called_once()

    @patch("subprocess.Popen")
    def test_terminate_exception(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.terminate.side_effect = OSError("Failed")
        mock_popen.return_value = mock_process
        launcher = SubprocessLauncher()
        launcher.spawn(worker_id=0, feature="test", worktree_path=tmp_path, branch="b")
        assert launcher.terminate(0) is False


class TestSubprocessLauncherGetOutput:
    """Tests for SubprocessLauncher.get_output."""

    def test_get_output_from_log_file(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "worker-0.stdout.log").write_text("line1\nline2\nline3\nline4\n")
        config = LauncherConfig(log_dir=log_dir)
        launcher = SubprocessLauncher(config=config)
        output = launcher.get_output(0, tail=2)
        assert "line3" in output
        assert "line1" not in output

    def test_get_output_no_data(self) -> None:
        launcher = SubprocessLauncher()
        assert launcher.get_output(999) == ""


class TestSubprocessLauncherWait:
    """Tests for wait_for_ready and wait_all."""

    @patch("subprocess.Popen")
    @patch("time.sleep")
    def test_wait_for_ready_running(self, mock_sleep, mock_popen, tmp_path) -> None:
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process
        launcher = SubprocessLauncher()
        launcher.spawn(worker_id=0, feature="test", worktree_path=tmp_path, branch="b")
        assert launcher.wait_for_ready(0, timeout=1.0) is True

    def test_wait_for_ready_timeout(self) -> None:
        launcher = SubprocessLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, status=WorkerStatus.BLOCKED)
        launcher._processes[0] = MagicMock(poll=MagicMock(return_value=None))
        launcher.monitor = lambda wid: WorkerStatus.BLOCKED  # type: ignore[method-assign]
        with patch("time.sleep"):
            assert launcher.wait_for_ready(0, timeout=0.01) is False


# =============================================================================
# WorkerLauncher base class
# =============================================================================


class TestWorkerLauncherBase:
    """Tests for WorkerLauncher abstract base class methods."""

    def test_get_handle(self) -> None:
        launcher = SubprocessLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, pid=12345)
        assert launcher.get_handle(0) is not None
        assert launcher.get_handle(999) is None

    def test_get_status_summary(self) -> None:
        launcher = SubprocessLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, status=WorkerStatus.RUNNING)
        launcher._workers[1] = WorkerHandle(worker_id=1, status=WorkerStatus.STOPPED)
        summary = launcher.get_status_summary()
        assert summary["total"] == 2
        assert summary["alive"] == 1


# =============================================================================
# ContainerLauncher
# =============================================================================


class TestContainerLauncherInit:
    """Tests for ContainerLauncher initialization."""

    def test_init_defaults_and_custom(self) -> None:
        default = ContainerLauncher()
        assert default.image_name == "zerg-worker"
        assert default.network == "bridge"
        custom = ContainerLauncher(image_name="custom", network="custom-net")
        assert custom.image_name == "custom"
        assert custom.network == "custom-net"


class TestContainerLauncherSpawn:
    """Tests for ContainerLauncher.spawn."""

    @patch("subprocess.run")
    @patch.object(ContainerLauncher, "_verify_worker_process")
    @patch.object(ContainerLauncher, "_run_worker_entry")
    @patch.object(ContainerLauncher, "_wait_ready")
    @patch.object(ContainerLauncher, "_start_container")
    def test_spawn_success(self, mock_start, mock_wait, mock_exec, mock_verify, mock_run, tmp_path):
        mock_start.return_value = "container-abc123"
        mock_wait.return_value = True
        mock_exec.return_value = True
        mock_verify.return_value = True
        mock_run.return_value = MagicMock(returncode=0)
        launcher = ContainerLauncher()
        result = launcher.spawn(worker_id=0, feature="test", worktree_path=tmp_path, branch="b")
        assert result.success is True
        assert result.handle.container_id == "container-abc123"

    @patch("subprocess.run")
    @patch.object(ContainerLauncher, "_start_container")
    def test_spawn_failure(self, mock_start, mock_run, tmp_path):
        mock_start.return_value = None
        mock_run.return_value = MagicMock(returncode=0)
        launcher = ContainerLauncher()
        result = launcher.spawn(worker_id=0, feature="test", worktree_path=tmp_path, branch="b")
        assert result.success is False


class TestContainerLauncherStartContainer:
    """Tests for ContainerLauncher._start_container."""

    @patch("subprocess.run")
    def test_start_success(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="container-id\n", stderr="")
        launcher = ContainerLauncher()
        assert launcher._start_container("name", tmp_path, {}) == "container-id"

    @patch("subprocess.run")
    def test_start_failure(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error")
        launcher = ContainerLauncher()
        assert launcher._start_container("name", tmp_path, {}) is None


class TestContainerLauncherMonitor:
    """Tests for ContainerLauncher.monitor."""

    def test_monitor_unknown(self) -> None:
        launcher = ContainerLauncher()
        assert launcher.monitor(999) == WorkerStatus.STOPPED

    @pytest.mark.parametrize(
        "stdout,expected",
        [("true,0\n", WorkerStatus.RUNNING), ("false,0\n", WorkerStatus.STOPPED), ("false,1\n", WorkerStatus.CRASHED)],
    )
    @patch("subprocess.run")
    def test_monitor_states(self, mock_run, stdout, expected):
        mock_run.return_value = MagicMock(returncode=0, stdout=stdout, stderr="")
        launcher = ContainerLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, container_id="c")
        launcher._container_ids[0] = "c"
        assert launcher.monitor(0) == expected

    @patch("subprocess.run")
    def test_monitor_cooldown_caching(self, mock_run) -> None:
        """FR-1: cached status within cooldown, docker called after expiry."""
        launcher = ContainerLauncher()
        # Within cooldown - should NOT call docker
        launcher._workers[0] = WorkerHandle(
            worker_id=0, container_id="c", status=WorkerStatus.RUNNING, health_check_at=datetime.now()
        )
        launcher._container_ids[0] = "c"
        assert launcher.monitor(0) == WorkerStatus.RUNNING
        mock_run.assert_not_called()

        # After cooldown - SHOULD call docker
        mock_run.return_value = MagicMock(returncode=0, stdout="true,0\n", stderr="")
        launcher._workers[0].health_check_at = datetime.now() - timedelta(seconds=15)
        launcher.monitor(0)
        mock_run.assert_called()


class TestContainerLauncherTerminate:
    """Tests for ContainerLauncher.terminate."""

    def test_terminate_unknown(self) -> None:
        assert ContainerLauncher().terminate(999) is False

    @patch("subprocess.run")
    def test_terminate_success(self, mock_run) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        launcher = ContainerLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, container_id="c")
        launcher._container_ids[0] = "c"
        assert launcher.terminate(0) is True
        assert 0 not in launcher._container_ids

    @patch("subprocess.run")
    def test_terminate_failure(self, mock_run) -> None:
        mock_run.side_effect = Exception("Docker error")
        launcher = ContainerLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, container_id="c")
        launcher._container_ids[0] = "c"
        assert launcher.terminate(0) is False


class TestContainerLauncherNetwork:
    """Tests for ensure_network and image_exists."""

    @patch("subprocess.run")
    def test_ensure_network_exists(self, mock_run) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        assert ContainerLauncher().ensure_network() is True

    @patch("subprocess.run")
    def test_ensure_network_creates(self, mock_run) -> None:
        mock_run.side_effect = [MagicMock(returncode=1), MagicMock(returncode=0)]
        assert ContainerLauncher().ensure_network() is True

    @patch("subprocess.run")
    def test_image_exists_true(self, mock_run) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        assert ContainerLauncher().image_exists() is True

    @patch("subprocess.run")
    def test_image_exists_false(self, mock_run) -> None:
        mock_run.return_value = MagicMock(returncode=1)
        assert ContainerLauncher().image_exists() is False


# =============================================================================
# Plugin Launcher
# =============================================================================


class TestGetPluginLauncher:
    """Tests for get_plugin_launcher."""

    def test_none_registry(self) -> None:
        assert get_plugin_launcher("test", None) is None

    def test_success_and_exception(self) -> None:
        from zerg.plugins import LauncherPlugin, PluginRegistry

        class GoodPlugin(LauncherPlugin):
            @property
            def name(self) -> str:
                return "good"

            def create_launcher(self, config: Any) -> Any:
                return SubprocessLauncher()

        class BadPlugin(LauncherPlugin):
            @property
            def name(self) -> str:
                return "bad"

            def create_launcher(self, config: Any) -> Any:
                raise RuntimeError("Failed")

        registry = PluginRegistry()
        registry.register_launcher(GoodPlugin())
        registry.register_launcher(BadPlugin())
        assert isinstance(get_plugin_launcher("good", registry), SubprocessLauncher)
        assert get_plugin_launcher("bad", registry) is None


# =============================================================================
# spawn_with_retry (FR-1)
# =============================================================================


class TestSpawnWithRetry:
    """Tests for spawn_with_retry with exponential backoff."""

    @patch.object(SubprocessLauncher, "spawn")
    @patch("zerg.launchers.base.time.sleep")
    def test_success_first_attempt(self, mock_sleep, mock_spawn, tmp_path):
        mock_spawn.return_value = SpawnResult(
            success=True,
            worker_id=0,
            handle=WorkerHandle(worker_id=0, pid=12345, status=WorkerStatus.RUNNING),
        )
        launcher = SubprocessLauncher()
        result = launcher.spawn_with_retry(worker_id=0, feature="f", worktree_path=tmp_path, branch="b")
        assert result.success is True
        mock_sleep.assert_not_called()

    @patch.object(SubprocessLauncher, "spawn")
    @patch("zerg.launchers.base.time.sleep")
    def test_all_attempts_fail(self, mock_sleep, mock_spawn, tmp_path):
        mock_spawn.return_value = SpawnResult(success=False, worker_id=0, error="persistent")
        launcher = SubprocessLauncher()
        result = launcher.spawn_with_retry(worker_id=0, feature="f", worktree_path=tmp_path, branch="b", max_attempts=3)
        assert result.success is False
        assert mock_spawn.call_count == 3

    @pytest.mark.asyncio
    @patch.object(SubprocessLauncher, "spawn_async")
    @patch("zerg.launchers.base.asyncio.sleep")
    async def test_async_retry_success(self, mock_sleep, mock_spawn_async, tmp_path):
        mock_spawn_async.return_value = SpawnResult(
            success=True,
            worker_id=0,
            handle=WorkerHandle(worker_id=0, pid=12345, status=WorkerStatus.RUNNING),
        )
        launcher = SubprocessLauncher()
        result = await launcher.spawn_with_retry_async(worker_id=0, feature="f", worktree_path=tmp_path, branch="b")
        assert result.success is True
