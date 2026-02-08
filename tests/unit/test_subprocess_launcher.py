"""Unit tests for SubprocessLauncher.

Covers: spawn, monitor, terminate, get_output, wait_for_ready, wait_all,
spawn_async, wait_async, terminate_async, heartbeat_monitor property,
error handling, edge cases.

Target: >= 80% line coverage for zerg/launchers/subprocess_launcher.py.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from zerg.constants import WorkerStatus
from zerg.launcher_types import LauncherConfig, WorkerHandle
from zerg.launchers.subprocess_launcher import SubprocessLauncher

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def launcher() -> SubprocessLauncher:
    """Return a default SubprocessLauncher."""
    return SubprocessLauncher()


@pytest.fixture()
def launcher_with_log_dir(tmp_path: Path) -> SubprocessLauncher:
    """Return a launcher configured with a log directory."""
    config = LauncherConfig(log_dir=tmp_path / "logs")
    return SubprocessLauncher(config=config)


@pytest.fixture()
def worktree(tmp_path: Path) -> Path:
    """Create a minimal worktree directory."""
    wt = tmp_path / "worktree"
    wt.mkdir()
    return wt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_process(pid: int = 12345, poll_return: int | None = None) -> MagicMock:
    """Create a mock subprocess.Popen instance.

    Note: We intentionally avoid spec=subprocess.Popen because when Popen
    is patched at module level, the spec target becomes a Mock itself,
    causing InvalidSpecError in Python 3.13+.
    """
    proc = MagicMock()
    proc.pid = pid
    proc.poll.return_value = poll_return
    proc.returncode = poll_return
    proc.wait.return_value = poll_return
    return proc


# ===========================================================================
# SubprocessLauncher.__init__
# ===========================================================================


class TestInit:
    """Initialization tests."""

    def test_default_config(self) -> None:
        launcher = SubprocessLauncher()
        assert launcher.config is not None
        assert launcher._processes == {}
        assert launcher._output_buffers == {}
        assert launcher._heartbeat_monitor is None

    def test_custom_config(self, tmp_path: Path) -> None:
        config = LauncherConfig(log_dir=tmp_path)
        launcher = SubprocessLauncher(config=config)
        assert launcher.config.log_dir == tmp_path


# ===========================================================================
# heartbeat_monitor property
# ===========================================================================


class TestHeartbeatMonitorProperty:
    """Tests for the lazy-singleton HeartbeatMonitor."""

    def test_creates_instance_on_first_access(self, launcher: SubprocessLauncher) -> None:
        assert launcher._heartbeat_monitor is None
        hb = launcher.heartbeat_monitor
        assert hb is not None
        assert launcher._heartbeat_monitor is hb

    def test_returns_same_instance(self, launcher: SubprocessLauncher) -> None:
        first = launcher.heartbeat_monitor
        second = launcher.heartbeat_monitor
        assert first is second


# ===========================================================================
# spawn()
# ===========================================================================


class TestSpawn:
    """Tests for synchronous spawn."""

    @patch("zerg.launchers.subprocess_launcher.subprocess.Popen")
    def test_spawn_success(self, mock_popen: MagicMock, launcher: SubprocessLauncher, worktree: Path) -> None:
        mock_proc = _make_mock_process(pid=9999)
        mock_popen.return_value = mock_proc

        result = launcher.spawn(1, "test-feature", worktree, "branch-1")

        assert result.success is True
        assert result.worker_id == 1
        assert result.handle is not None
        assert result.handle.pid == 9999
        assert result.handle.status == WorkerStatus.INITIALIZING
        assert 1 in launcher._workers
        assert 1 in launcher._processes
        assert 1 in launcher._output_buffers

    @patch("zerg.launchers.subprocess_launcher.subprocess.Popen")
    def test_spawn_sets_zerg_env_vars(
        self, mock_popen: MagicMock, launcher: SubprocessLauncher, worktree: Path
    ) -> None:
        mock_popen.return_value = _make_mock_process()

        launcher.spawn(7, "my-feature", worktree, "br-7")

        call_kwargs = mock_popen.call_args[1]
        env = call_kwargs["env"]
        assert env["ZERG_WORKER_ID"] == "7"
        assert env["ZERG_FEATURE"] == "my-feature"
        assert env["ZERG_BRANCH"] == "br-7"

    @patch("zerg.launchers.subprocess_launcher.subprocess.Popen")
    def test_spawn_with_task_list_id(self, mock_popen: MagicMock, launcher: SubprocessLauncher, worktree: Path) -> None:
        """Line 98-99: CLAUDE_CODE_TASK_LIST_ID forwarding."""
        mock_popen.return_value = _make_mock_process()

        with patch.dict("os.environ", {"CLAUDE_CODE_TASK_LIST_ID": "test-list-123"}):
            launcher.spawn(1, "feat", worktree, "br")

        env = mock_popen.call_args[1]["env"]
        assert env["CLAUDE_CODE_TASK_LIST_ID"] == "test-list-123"

    @patch("zerg.launchers.subprocess_launcher.subprocess.Popen")
    def test_spawn_with_config_env_vars(self, mock_popen: MagicMock, worktree: Path) -> None:
        """Lines 105-107: validate and apply config env_vars."""
        config = LauncherConfig(env_vars={"ZERG_DEBUG": "1"})
        launcher = SubprocessLauncher(config=config)
        mock_popen.return_value = _make_mock_process()

        launcher.spawn(1, "feat", worktree, "br")

        env = mock_popen.call_args[1]["env"]
        assert env["ZERG_DEBUG"] == "1"

    @patch("zerg.launchers.subprocess_launcher.subprocess.Popen")
    def test_spawn_with_extra_env(self, mock_popen: MagicMock, launcher: SubprocessLauncher, worktree: Path) -> None:
        """Lines 109-111: validate and apply caller-supplied env."""
        mock_popen.return_value = _make_mock_process()

        launcher.spawn(1, "feat", worktree, "br", env={"ZERG_LOG_LEVEL": "DEBUG"})

        env = mock_popen.call_args[1]["env"]
        assert env["ZERG_LOG_LEVEL"] == "DEBUG"

    @patch("zerg.launchers.subprocess_launcher.subprocess.Popen")
    def test_spawn_with_log_dir(
        self, mock_popen: MagicMock, launcher_with_log_dir: SubprocessLauncher, worktree: Path
    ) -> None:
        """Lines 134-143: log file creation when log_dir configured."""
        mock_popen.return_value = _make_mock_process()

        result = launcher_with_log_dir.spawn(2, "feat", worktree, "br")

        assert result.success is True
        # The log directory should have been created
        assert launcher_with_log_dir.config.log_dir.exists()

    @patch("zerg.launchers.subprocess_launcher.subprocess.Popen")
    def test_spawn_invalid_worker_id_with_log_dir(
        self, mock_popen: MagicMock, launcher_with_log_dir: SubprocessLauncher, worktree: Path
    ) -> None:
        """Line 136-137: negative worker_id raises ValueError when log_dir set."""
        result = launcher_with_log_dir.spawn(-1, "feat", worktree, "br")

        assert result.success is False
        assert "Invalid worker_id" in (result.error or "")

    @patch("zerg.launchers.subprocess_launcher.subprocess.Popen")
    def test_spawn_popen_failure(self, mock_popen: MagicMock, launcher: SubprocessLauncher, worktree: Path) -> None:
        """Lines 169-171: OSError during Popen."""
        mock_popen.side_effect = OSError("No such file")

        result = launcher.spawn(1, "feat", worktree, "br")

        assert result.success is False
        assert "No such file" in (result.error or "")

    @patch("zerg.launchers.subprocess_launcher.subprocess.Popen")
    def test_spawn_uses_working_dir(self, mock_popen: MagicMock, worktree: Path) -> None:
        """Line 129: uses config.working_dir when set."""
        custom_dir = worktree / "custom"
        custom_dir.mkdir()
        config = LauncherConfig(working_dir=custom_dir)
        launcher = SubprocessLauncher(config=config)
        mock_popen.return_value = _make_mock_process()

        launcher.spawn(1, "feat", worktree, "br")

        call_kwargs = mock_popen.call_args[1]
        assert call_kwargs["cwd"] == custom_dir


# ===========================================================================
# monitor()
# ===========================================================================


class TestMonitor:
    """Tests for worker status monitoring."""

    def test_monitor_unknown_worker(self, launcher: SubprocessLauncher) -> None:
        """Line 186: returns STOPPED for unknown worker_id."""
        assert launcher.monitor(999) == WorkerStatus.STOPPED

    def test_monitor_running_process_transitions_from_initializing(self, launcher: SubprocessLauncher) -> None:
        """Lines 191-194: INITIALIZING -> RUNNING when process still alive."""
        proc = _make_mock_process(poll_return=None)
        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.INITIALIZING)
        launcher._workers[1] = handle
        launcher._processes[1] = proc

        with patch.object(type(launcher), "heartbeat_monitor", new_callable=PropertyMock) as mock_hb_prop:
            mock_monitor = MagicMock()
            mock_monitor.read.return_value = None
            mock_hb_prop.return_value = mock_monitor

            status = launcher.monitor(1)

        assert status == WorkerStatus.RUNNING
        assert handle.status == WorkerStatus.RUNNING

    def test_monitor_stale_heartbeat(self, launcher: SubprocessLauncher) -> None:
        """Lines 197-200: RUNNING -> STALLED when heartbeat is stale."""
        proc = _make_mock_process(poll_return=None)
        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.RUNNING)
        launcher._workers[1] = handle
        launcher._processes[1] = proc

        mock_hb = MagicMock()
        mock_hb.is_stale.return_value = True

        with patch.object(type(launcher), "heartbeat_monitor", new_callable=PropertyMock) as mock_hb_prop:
            mock_monitor = MagicMock()
            mock_monitor.read.return_value = mock_hb
            mock_hb_prop.return_value = mock_monitor

            status = launcher.monitor(1)

        assert status == WorkerStatus.STALLED

    def test_monitor_exit_code_0(self, launcher: SubprocessLauncher) -> None:
        """Lines 206-207: exit code 0 -> STOPPED."""
        proc = _make_mock_process(poll_return=0)
        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.RUNNING)
        launcher._workers[1] = handle
        launcher._processes[1] = proc

        status = launcher.monitor(1)
        assert status == WorkerStatus.STOPPED
        assert handle.exit_code == 0

    def test_monitor_exit_code_2_checkpoint(self, launcher: SubprocessLauncher) -> None:
        """Lines 208-209: exit code 2 -> CHECKPOINTING."""
        proc = _make_mock_process(poll_return=2)
        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.RUNNING)
        launcher._workers[1] = handle
        launcher._processes[1] = proc

        status = launcher.monitor(1)
        assert status == WorkerStatus.CHECKPOINTING

    def test_monitor_exit_code_3_blocked(self, launcher: SubprocessLauncher) -> None:
        """Lines 210-211: exit code 3 -> BLOCKED."""
        proc = _make_mock_process(poll_return=3)
        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.RUNNING)
        launcher._workers[1] = handle
        launcher._processes[1] = proc

        status = launcher.monitor(1)
        assert status == WorkerStatus.BLOCKED

    def test_monitor_exit_code_4_escalation(self, launcher: SubprocessLauncher) -> None:
        """Lines 212-213: exit code 4 -> STOPPED."""
        proc = _make_mock_process(poll_return=4)
        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.RUNNING)
        launcher._workers[1] = handle
        launcher._processes[1] = proc

        status = launcher.monitor(1)
        assert status == WorkerStatus.STOPPED

    def test_monitor_exit_code_other_crashed(self, launcher: SubprocessLauncher) -> None:
        """Lines 214-215: exit code != 0/2/3/4 -> CRASHED."""
        proc = _make_mock_process(poll_return=1)
        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.RUNNING)
        launcher._workers[1] = handle
        launcher._processes[1] = proc

        status = launcher.monitor(1)
        assert status == WorkerStatus.CRASHED


# ===========================================================================
# terminate()
# ===========================================================================


class TestTerminate:
    """Tests for worker termination."""

    def test_terminate_unknown_worker(self, launcher: SubprocessLauncher) -> None:
        """Line 232-233: returns False for unknown worker."""
        assert launcher.terminate(999) is False

    def test_terminate_graceful(self, launcher: SubprocessLauncher) -> None:
        """Lines 238-239: graceful terminate calls process.terminate()."""
        proc = _make_mock_process(poll_return=0)
        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.RUNNING)
        launcher._workers[1] = handle
        launcher._processes[1] = proc

        result = launcher.terminate(1, force=False)

        assert result is True
        proc.terminate.assert_called_once()
        proc.kill.assert_not_called()
        assert 1 not in launcher._processes
        assert 1 not in launcher._workers

    def test_terminate_force(self, launcher: SubprocessLauncher) -> None:
        """Lines 236-237: force=True calls process.kill()."""
        proc = _make_mock_process(poll_return=0)
        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.RUNNING)
        launcher._workers[1] = handle
        launcher._processes[1] = proc

        result = launcher.terminate(1, force=True)

        assert result is True
        proc.kill.assert_called_once()

    def test_terminate_timeout_escalates_to_kill(self, launcher: SubprocessLauncher) -> None:
        """Lines 243-246: TimeoutExpired during wait -> escalate to kill."""
        proc = _make_mock_process()
        proc.wait.side_effect = [subprocess.TimeoutExpired("cmd", 10), 0]
        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.RUNNING)
        launcher._workers[1] = handle
        launcher._processes[1] = proc

        result = launcher.terminate(1, force=False)

        assert result is True
        proc.terminate.assert_called_once()
        proc.kill.assert_called_once()

    def test_terminate_os_error(self, launcher: SubprocessLauncher) -> None:
        """Lines 254-256: OSError during termination returns False."""
        proc = _make_mock_process()
        proc.terminate.side_effect = OSError("Permission denied")
        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.RUNNING)
        launcher._workers[1] = handle
        launcher._processes[1] = proc

        result = launcher.terminate(1, force=False)

        assert result is False
        # Cleanup still happens in finally
        assert 1 not in launcher._processes
        assert 1 not in launcher._workers

    def test_terminate_updates_handle_status(self, launcher: SubprocessLauncher) -> None:
        """Line 248-249: sets STOPPED and exit_code on handle."""
        proc = _make_mock_process(poll_return=0)
        proc.returncode = 0
        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.RUNNING)
        launcher._workers[1] = handle
        launcher._processes[1] = proc

        launcher.terminate(1)

        # Handle gets cleaned up from _workers but we can verify the status was set
        # by checking proc.wait was called (status assignment happens before cleanup)
        proc.wait.assert_called()


# ===========================================================================
# get_output()
# ===========================================================================


class TestGetOutput:
    """Tests for output retrieval."""

    def test_get_output_from_log_file(self, launcher_with_log_dir: SubprocessLauncher) -> None:
        """Lines 277-281: reads from log file when log_dir configured."""
        log_dir = launcher_with_log_dir.config.log_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "worker-1.stdout.log"
        log_file.write_text("line1\nline2\nline3\n")

        output = launcher_with_log_dir.get_output(1, tail=2)
        lines = output.strip().split("\n")
        assert len(lines) == 2
        assert "line2" in output
        assert "line3" in output

    def test_get_output_from_buffer(self, launcher: SubprocessLauncher) -> None:
        """Lines 283-285: falls back to buffer when no log_dir."""
        launcher._output_buffers[1] = ["alpha", "beta", "gamma"]

        output = launcher.get_output(1, tail=2)
        assert output == "beta\ngamma"

    def test_get_output_empty_buffer(self, launcher: SubprocessLauncher) -> None:
        """Returns empty string for unknown worker."""
        output = launcher.get_output(999)
        assert output == ""


# ===========================================================================
# wait_for_ready()
# ===========================================================================


class TestWaitForReady:
    """Tests for wait_for_ready."""

    def test_wait_for_ready_immediately_running(self, launcher: SubprocessLauncher) -> None:
        """Lines 300-302: returns True when already RUNNING."""
        proc = _make_mock_process(poll_return=None)
        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.RUNNING)
        launcher._workers[1] = handle
        launcher._processes[1] = proc

        with patch.object(type(launcher), "heartbeat_monitor", new_callable=PropertyMock) as mock_hb_prop:
            mock_monitor = MagicMock()
            mock_monitor.read.return_value = None
            mock_hb_prop.return_value = mock_monitor

            result = launcher.wait_for_ready(1, timeout=1.0)

        assert result is True

    def test_wait_for_ready_crashed(self, launcher: SubprocessLauncher) -> None:
        """Lines 303-304: returns False when CRASHED."""
        proc = _make_mock_process(poll_return=1)
        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.RUNNING)
        launcher._workers[1] = handle
        launcher._processes[1] = proc

        result = launcher.wait_for_ready(1, timeout=1.0)
        assert result is False

    @patch("zerg.launchers.subprocess_launcher.time.sleep")
    def test_wait_for_ready_timeout(self, mock_sleep: MagicMock, launcher: SubprocessLauncher) -> None:
        """Lines 305-306: returns False on timeout."""
        # monitor always returns INITIALIZING (process never becomes ready)
        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.INITIALIZING)
        launcher._workers[1] = handle

        # No process means monitor returns STOPPED
        # Instead, mock monitor to return INITIALIZING
        with patch.object(launcher, "monitor", return_value=WorkerStatus.INITIALIZING):
            result = launcher.wait_for_ready(1, timeout=0.01)

        assert result is False


# ===========================================================================
# wait_all()
# ===========================================================================


class TestWaitAll:
    """Tests for wait_all."""

    @patch("zerg.launchers.subprocess_launcher.time.sleep")
    def test_wait_all_workers_done(self, mock_sleep: MagicMock, launcher: SubprocessLauncher) -> None:
        """Lines 318-336: returns final statuses when all workers exit."""
        proc = _make_mock_process(poll_return=0)
        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.RUNNING)
        launcher._workers[1] = handle
        launcher._processes[1] = proc

        statuses = launcher.wait_all(timeout=5.0)

        assert statuses[1] == WorkerStatus.STOPPED

    @patch("zerg.launchers.subprocess_launcher.time.sleep")
    def test_wait_all_timeout(self, mock_sleep: MagicMock, launcher: SubprocessLauncher) -> None:
        """Lines 331-332: exits loop on timeout."""
        proc = _make_mock_process(poll_return=None)
        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.RUNNING)
        launcher._workers[1] = handle
        launcher._processes[1] = proc

        # heartbeat_monitor check during monitor()
        with patch.object(type(launcher), "heartbeat_monitor", new_callable=PropertyMock) as mock_hb_prop:
            mock_monitor = MagicMock()
            mock_monitor.read.return_value = None
            mock_hb_prop.return_value = mock_monitor

            statuses = launcher.wait_all(timeout=0.01)

        assert 1 in statuses
        # Worker is still running, so status should be RUNNING
        assert statuses[1] == WorkerStatus.RUNNING

    def test_wait_all_empty(self, launcher: SubprocessLauncher) -> None:
        """No workers means immediate return."""
        statuses = launcher.wait_all(timeout=1.0)
        assert statuses == {}


# ===========================================================================
# spawn_async()
# ===========================================================================


class TestSpawnAsync:
    """Tests for async spawn."""

    @pytest.mark.asyncio
    async def test_spawn_async_success(self, launcher: SubprocessLauncher, worktree: Path) -> None:
        """Lines 361-456: async spawn creates process and handle."""
        mock_proc = AsyncMock()
        mock_proc.pid = 5555

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await launcher.spawn_async(1, "feat", worktree, "br-1")

        assert result.success is True
        assert result.handle is not None
        assert result.handle.pid == 5555
        assert result.handle.status == WorkerStatus.INITIALIZING
        assert 1 in launcher._workers
        assert hasattr(launcher, "_async_processes")
        assert 1 in launcher._async_processes

    @pytest.mark.asyncio
    async def test_spawn_async_with_task_list_id(self, launcher: SubprocessLauncher, worktree: Path) -> None:
        """Lines 380-382: CLAUDE_CODE_TASK_LIST_ID forwarded in async spawn."""
        mock_proc = AsyncMock()
        mock_proc.pid = 1111

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
            patch.dict("os.environ", {"CLAUDE_CODE_TASK_LIST_ID": "async-list"}),
        ):
            result = await launcher.spawn_async(1, "feat", worktree, "br")

        assert result.success is True

    @pytest.mark.asyncio
    async def test_spawn_async_with_config_env_vars(self, worktree: Path) -> None:
        """Lines 389-391: config env_vars validated in async spawn."""
        config = LauncherConfig(env_vars={"ZERG_DEBUG": "true"})
        launcher = SubprocessLauncher(config=config)
        mock_proc = AsyncMock()
        mock_proc.pid = 2222

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await launcher.spawn_async(1, "feat", worktree, "br")

        assert result.success is True

    @pytest.mark.asyncio
    async def test_spawn_async_with_extra_env(self, launcher: SubprocessLauncher, worktree: Path) -> None:
        """Lines 393-395: caller env validated in async spawn."""
        mock_proc = AsyncMock()
        mock_proc.pid = 3333

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await launcher.spawn_async(1, "feat", worktree, "br", env={"ZERG_LOG_LEVEL": "INFO"})

        assert result.success is True

    @pytest.mark.asyncio
    async def test_spawn_async_with_log_dir(self, launcher_with_log_dir: SubprocessLauncher, worktree: Path) -> None:
        """Lines 420-429: log files created for async spawn."""
        mock_proc = AsyncMock()
        mock_proc.pid = 4444

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await launcher_with_log_dir.spawn_async(2, "feat", worktree, "br")

        assert result.success is True
        assert launcher_with_log_dir.config.log_dir.exists()

    @pytest.mark.asyncio
    async def test_spawn_async_invalid_worker_id_with_log_dir(
        self, launcher_with_log_dir: SubprocessLauncher, worktree: Path
    ) -> None:
        """Lines 421-422: negative worker_id raises ValueError in async spawn."""
        result = await launcher_with_log_dir.spawn_async(-1, "feat", worktree, "br")

        assert result.success is False
        assert "Invalid worker_id" in (result.error or "")

    @pytest.mark.asyncio
    async def test_spawn_async_os_error(self, launcher: SubprocessLauncher, worktree: Path) -> None:
        """Lines 458-460: OSError handled in async spawn."""
        with patch("asyncio.create_subprocess_exec", side_effect=OSError("exec failed")):
            result = await launcher.spawn_async(1, "feat", worktree, "br")

        assert result.success is False
        assert "exec failed" in (result.error or "")


# ===========================================================================
# wait_async()
# ===========================================================================


class TestWaitAsync:
    """Tests for async wait."""

    @pytest.mark.asyncio
    async def test_wait_async_with_async_process(self, launcher: SubprocessLauncher) -> None:
        """Lines 474-490: waits on async process handle."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.wait = AsyncMock()

        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.RUNNING)
        launcher._workers[1] = handle
        launcher._async_processes = {1: mock_proc}

        status = await launcher.wait_async(1)

        assert status == WorkerStatus.STOPPED
        assert handle.exit_code == 0

    @pytest.mark.asyncio
    async def test_wait_async_checkpoint_exit(self, launcher: SubprocessLauncher) -> None:
        """Lines 484-485: exit code 2 -> CHECKPOINTING."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 2
        mock_proc.wait = AsyncMock()

        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.RUNNING)
        launcher._workers[1] = handle
        launcher._async_processes = {1: mock_proc}

        status = await launcher.wait_async(1)
        assert status == WorkerStatus.CHECKPOINTING

    @pytest.mark.asyncio
    async def test_wait_async_blocked_exit(self, launcher: SubprocessLauncher) -> None:
        """Lines 486-487: exit code 3 -> BLOCKED."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 3
        mock_proc.wait = AsyncMock()

        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.RUNNING)
        launcher._workers[1] = handle
        launcher._async_processes = {1: mock_proc}

        status = await launcher.wait_async(1)
        assert status == WorkerStatus.BLOCKED

    @pytest.mark.asyncio
    async def test_wait_async_crashed_exit(self, launcher: SubprocessLauncher) -> None:
        """Lines 488-489: other exit code -> CRASHED."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.wait = AsyncMock()

        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.RUNNING)
        launcher._workers[1] = handle
        launcher._async_processes = {1: mock_proc}

        status = await launcher.wait_async(1)
        assert status == WorkerStatus.CRASHED

    @pytest.mark.asyncio
    async def test_wait_async_fallback_to_monitor(self, launcher: SubprocessLauncher) -> None:
        """Line 492: falls back to sync monitor when no async process."""
        proc = _make_mock_process(poll_return=0)
        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.RUNNING)
        launcher._workers[1] = handle
        launcher._processes[1] = proc

        status = await launcher.wait_async(1)
        assert status == WorkerStatus.STOPPED


# ===========================================================================
# terminate_async()
# ===========================================================================


class TestTerminateAsync:
    """Tests for async terminate."""

    @pytest.mark.asyncio
    async def test_terminate_async_graceful(self, launcher: SubprocessLauncher) -> None:
        """Lines 507-530: async graceful termination."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.wait = AsyncMock()
        mock_proc.terminate = MagicMock()
        mock_proc.kill = MagicMock()

        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.RUNNING)
        launcher._workers[1] = handle
        launcher._async_processes = {1: mock_proc}

        result = await launcher.terminate_async(1, force=False)

        assert result is True
        mock_proc.terminate.assert_called_once()
        assert 1 not in launcher._async_processes
        assert 1 not in launcher._workers

    @pytest.mark.asyncio
    async def test_terminate_async_force(self, launcher: SubprocessLauncher) -> None:
        """Lines 515-516: force kill in async."""
        mock_proc = AsyncMock()
        mock_proc.returncode = -9
        mock_proc.wait = AsyncMock()
        mock_proc.terminate = MagicMock()
        mock_proc.kill = MagicMock()

        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.RUNNING)
        launcher._workers[1] = handle
        launcher._async_processes = {1: mock_proc}

        result = await launcher.terminate_async(1, force=True)

        assert result is True
        mock_proc.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_terminate_async_timeout_escalation(self, launcher: SubprocessLauncher) -> None:
        """Lines 520-524: TimeoutError escalates to kill."""
        mock_proc = AsyncMock()
        mock_proc.returncode = -9
        mock_proc.terminate = MagicMock()
        mock_proc.kill = MagicMock()

        # First wait raises TimeoutError, second succeeds
        mock_proc.wait = AsyncMock()

        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.RUNNING)
        launcher._workers[1] = handle
        launcher._async_processes = {1: mock_proc}

        with patch("asyncio.wait_for", side_effect=TimeoutError):
            result = await launcher.terminate_async(1, force=False)

        assert result is True
        mock_proc.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_terminate_async_no_handle(self, launcher: SubprocessLauncher) -> None:
        """Lines 511-512: returns False when no handle exists."""
        mock_proc = AsyncMock()
        launcher._async_processes = {1: mock_proc}
        # No handle in _workers

        result = await launcher.terminate_async(1)
        assert result is False

    @pytest.mark.asyncio
    async def test_terminate_async_os_error(self, launcher: SubprocessLauncher) -> None:
        """Lines 532-534: OSError during async terminate."""
        mock_proc = AsyncMock()
        mock_proc.terminate = MagicMock(side_effect=OSError("Not found"))
        mock_proc.wait = AsyncMock()

        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.RUNNING)
        launcher._workers[1] = handle
        launcher._async_processes = {1: mock_proc}

        result = await launcher.terminate_async(1, force=False)

        assert result is False
        # Cleanup still happens in finally block
        assert 1 not in launcher._async_processes
        assert 1 not in launcher._workers

    @pytest.mark.asyncio
    async def test_terminate_async_fallback_to_sync(self, launcher: SubprocessLauncher) -> None:
        """Line 542: falls back to sync terminate when no async process."""
        proc = _make_mock_process(poll_return=0)
        handle = WorkerHandle(worker_id=1, pid=123, status=WorkerStatus.RUNNING)
        launcher._workers[1] = handle
        launcher._processes[1] = proc

        result = await launcher.terminate_async(1, force=False)

        assert result is True
