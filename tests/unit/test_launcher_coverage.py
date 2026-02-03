"""Coverage tests for uncovered paths in zerg/launcher.py.

COV-005: Targets lines 219, 231, 244, 257, 360, 377, 391-405, 465,
716-807, 821-839, 854-892, 1100-1105, 1318-1327, 1518-1622,
1641-1713, 1727-1783.
"""

import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.mocks.mock_launcher import MockContainerLauncher
from zerg.constants import WorkerStatus
from zerg.launcher import (
    ContainerLauncher,
    LauncherConfig,
    SubprocessLauncher,
    WorkerHandle,
    WorkerLauncher,
)


# ---------------------------------------------------------------------------
# Helper: run coroutine in tests
# ---------------------------------------------------------------------------
def run_async(coro):
    """Run an async coroutine synchronously for testing."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Abstract method pass statements (lines 219, 231, 244, 257)
# These are abstract methods with `pass` bodies. They are covered by
# calling subclass implementations. The MockContainerLauncher already
# covers spawn/monitor/terminate via the existing test suite.
# We add a direct test that the ABC cannot be instantiated.
# ---------------------------------------------------------------------------
class TestAbstractLauncherCoverage:
    """Verify abstract methods on WorkerLauncher."""

    def test_cannot_instantiate_abstract_launcher(self) -> None:
        """WorkerLauncher is abstract and cannot be directly instantiated."""
        with pytest.raises(TypeError):
            WorkerLauncher()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# WorkerLauncher.spawn_async (line 360)
# WorkerLauncher.terminate_async (line 377)
# WorkerLauncher.wait_all_async (lines 391-405)
# ---------------------------------------------------------------------------
class TestWorkerLauncherAsyncMethods:
    """Cover base-class async helpers that delegate to sync methods."""

    def test_spawn_async_delegates_to_sync(self) -> None:
        """spawn_async should call self.spawn via asyncio.to_thread."""
        launcher = MockContainerLauncher()
        launcher.configure()

        result = run_async(
            launcher.spawn_async(
                worker_id=0,
                feature="test-feat",
                worktree_path=Path("/workspace"),
                branch="test-branch",
            )
        )

        assert result.success
        assert result.handle is not None
        assert result.handle.worker_id == 0

    def test_terminate_async_delegates_to_sync(self) -> None:
        """terminate_async should call self.terminate via asyncio.to_thread."""
        launcher = MockContainerLauncher()
        launcher.configure()

        launcher.spawn(
            worker_id=0,
            feature="test-feat",
            worktree_path=Path("/workspace"),
            branch="test-branch",
        )

        result = run_async(launcher.terminate_async(0))
        assert result is True

    def test_terminate_async_unknown_worker(self) -> None:
        """terminate_async returns False for unknown worker."""
        launcher = MockContainerLauncher()

        result = run_async(launcher.terminate_async(999))
        assert result is False

    def test_wait_all_async_returns_final_statuses(self) -> None:
        """wait_all_async should poll until workers finish."""
        launcher = MockContainerLauncher()
        launcher.configure(container_crash_workers={0})

        launcher.spawn(
            worker_id=0,
            feature="test",
            worktree_path=Path("/workspace"),
            branch="branch",
        )

        # Worker 0 is configured to crash, so monitor returns CRASHED
        results = run_async(launcher.wait_all_async([0]))

        assert 0 in results
        assert results[0] == WorkerStatus.CRASHED

    def test_wait_all_async_multiple_workers(self) -> None:
        """wait_all_async handles multiple workers."""
        launcher = MockContainerLauncher()
        launcher.configure(container_crash_workers={1})

        for wid in range(2):
            launcher.spawn(
                worker_id=wid,
                feature="test",
                worktree_path=Path(f"/workspace-{wid}"),
                branch=f"branch-{wid}",
            )

        # Make worker 0 stopped by terminating it first
        launcher.terminate(0)

        results = run_async(launcher.wait_all_async([0, 1]))

        assert 0 in results
        assert 1 in results
        # Worker 0 was terminated -> STOPPED; worker 1 configured to crash -> CRASHED
        assert results[0] == WorkerStatus.STOPPED
        assert results[1] == WorkerStatus.CRASHED


# ---------------------------------------------------------------------------
# SubprocessLauncher.spawn with CLAUDE_CODE_TASK_LIST_ID (line 465)
# ---------------------------------------------------------------------------
class TestSubprocessLauncherTaskListId:
    """Cover CLAUDE_CODE_TASK_LIST_ID injection in subprocess spawn."""

    def test_task_list_id_injected_when_set(self, tmp_path: Path) -> None:
        """CLAUDE_CODE_TASK_LIST_ID should propagate to worker env."""
        launcher = SubprocessLauncher()

        with (
            patch("subprocess.Popen") as mock_popen,
            patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": "my-feature"}),
        ):
            mock_process = MagicMock()
            mock_process.pid = 99999
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process

            result = launcher.spawn(
                worker_id=0,
                feature="test",
                worktree_path=tmp_path,
                branch="test-branch",
            )

            assert result.success
            # Check the env passed to Popen includes the task list ID
            call_kwargs = mock_popen.call_args
            env_passed = call_kwargs[1].get("env") or call_kwargs.kwargs.get("env")
            assert env_passed["CLAUDE_CODE_TASK_LIST_ID"] == "my-feature"


# ---------------------------------------------------------------------------
# SubprocessLauncher.spawn_async (lines 716-807)
# ---------------------------------------------------------------------------
class TestSubprocessLauncherSpawnAsync:
    """Cover SubprocessLauncher.spawn_async native async implementation."""

    def test_spawn_async_success(self, tmp_path: Path) -> None:
        """spawn_async should create an async subprocess."""
        launcher = SubprocessLauncher()

        mock_process = AsyncMock()
        mock_process.pid = 54321

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = run_async(
                launcher.spawn_async(
                    worker_id=0,
                    feature="async-feat",
                    worktree_path=tmp_path,
                    branch="async-branch",
                )
            )

        assert result.success
        assert result.handle is not None
        assert result.handle.pid == 54321
        assert result.handle.status == WorkerStatus.INITIALIZING

    def test_spawn_async_with_log_dir(self, tmp_path: Path) -> None:
        """spawn_async should handle log_dir configuration."""
        log_dir = tmp_path / "logs"
        config = LauncherConfig(log_dir=log_dir)
        launcher = SubprocessLauncher(config=config)

        mock_process = AsyncMock()
        mock_process.pid = 54322

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = run_async(
                launcher.spawn_async(
                    worker_id=0,
                    feature="log-feat",
                    worktree_path=tmp_path,
                    branch="log-branch",
                )
            )

        assert result.success
        assert log_dir.exists()

    def test_spawn_async_with_invalid_worker_id_and_log_dir(self, tmp_path: Path) -> None:
        """spawn_async should reject negative worker_id when log_dir is set."""
        log_dir = tmp_path / "logs"
        config = LauncherConfig(log_dir=log_dir)
        launcher = SubprocessLauncher(config=config)

        result = run_async(
            launcher.spawn_async(
                worker_id=-1,
                feature="bad",
                worktree_path=tmp_path,
                branch="bad-branch",
            )
        )

        assert not result.success
        assert "Invalid worker_id" in result.error

    def test_spawn_async_failure(self, tmp_path: Path) -> None:
        """spawn_async should return error on subprocess failure."""
        launcher = SubprocessLauncher()

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=OSError("exec failed"),
        ):
            result = run_async(
                launcher.spawn_async(
                    worker_id=0,
                    feature="fail-feat",
                    worktree_path=tmp_path,
                    branch="fail-branch",
                )
            )

        assert not result.success
        assert "exec failed" in result.error

    def test_spawn_async_with_task_list_id(self, tmp_path: Path) -> None:
        """spawn_async propagates CLAUDE_CODE_TASK_LIST_ID."""
        launcher = SubprocessLauncher()

        mock_process = AsyncMock()
        mock_process.pid = 54323

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec,
            patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": "async-list"}),
        ):
            result = run_async(
                launcher.spawn_async(
                    worker_id=0,
                    feature="task-feat",
                    worktree_path=tmp_path,
                    branch="task-branch",
                )
            )

        assert result.success
        # Verify env was passed with the task list ID
        call_kwargs = mock_exec.call_args
        env_arg = call_kwargs.kwargs.get("env")
        assert env_arg["CLAUDE_CODE_TASK_LIST_ID"] == "async-list"

    def test_spawn_async_with_config_env_vars(self, tmp_path: Path) -> None:
        """spawn_async validates and injects config env vars."""
        config = LauncherConfig(env_vars={"ZERG_DEBUG": "true"})
        launcher = SubprocessLauncher(config=config)

        mock_process = AsyncMock()
        mock_process.pid = 54324

        with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
            result = run_async(
                launcher.spawn_async(
                    worker_id=0,
                    feature="cfg-feat",
                    worktree_path=tmp_path,
                    branch="cfg-branch",
                    env={"ZERG_CUSTOM": "val"},
                )
            )

        assert result.success
        env_arg = mock_exec.call_args.kwargs.get("env")
        assert env_arg["ZERG_DEBUG"] == "true"
        assert env_arg["ZERG_CUSTOM"] == "val"


# ---------------------------------------------------------------------------
# SubprocessLauncher.wait_async (lines 821-839)
# ---------------------------------------------------------------------------
class TestSubprocessLauncherWaitAsync:
    """Cover SubprocessLauncher.wait_async."""

    def test_wait_async_with_async_process_exit_0(self, tmp_path: Path) -> None:
        """wait_async returns STOPPED for exit code 0."""
        launcher = SubprocessLauncher()

        mock_process = AsyncMock()
        mock_process.pid = 11111
        mock_process.returncode = 0
        mock_process.wait = AsyncMock()

        # Directly set up internal state
        handle = WorkerHandle(worker_id=0, pid=11111, status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._async_processes = {0: mock_process}

        status = run_async(launcher.wait_async(0))
        assert status == WorkerStatus.STOPPED
        assert handle.exit_code == 0

    def test_wait_async_with_async_process_exit_2(self) -> None:
        """wait_async returns CHECKPOINTING for exit code 2."""
        launcher = SubprocessLauncher()

        mock_process = AsyncMock()
        mock_process.pid = 11112
        mock_process.returncode = 2
        mock_process.wait = AsyncMock()

        handle = WorkerHandle(worker_id=0, pid=11112, status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._async_processes = {0: mock_process}

        status = run_async(launcher.wait_async(0))
        assert status == WorkerStatus.CHECKPOINTING

    def test_wait_async_with_async_process_exit_3(self) -> None:
        """wait_async returns BLOCKED for exit code 3."""
        launcher = SubprocessLauncher()

        mock_process = AsyncMock()
        mock_process.pid = 11113
        mock_process.returncode = 3
        mock_process.wait = AsyncMock()

        handle = WorkerHandle(worker_id=0, pid=11113, status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._async_processes = {0: mock_process}

        status = run_async(launcher.wait_async(0))
        assert status == WorkerStatus.BLOCKED

    def test_wait_async_with_async_process_crash(self) -> None:
        """wait_async returns CRASHED for non-zero non-special exit codes."""
        launcher = SubprocessLauncher()

        mock_process = AsyncMock()
        mock_process.pid = 11114
        mock_process.returncode = 137
        mock_process.wait = AsyncMock()

        handle = WorkerHandle(worker_id=0, pid=11114, status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._async_processes = {0: mock_process}

        status = run_async(launcher.wait_async(0))
        assert status == WorkerStatus.CRASHED

    def test_wait_async_no_handle_falls_back_to_monitor(self) -> None:
        """wait_async with async process but no handle falls back to monitor."""
        launcher = SubprocessLauncher()

        mock_process = AsyncMock()
        mock_process.pid = 11115
        mock_process.returncode = 0
        mock_process.wait = AsyncMock()

        # No handle in _workers, but process exists
        launcher._async_processes = {0: mock_process}

        status = run_async(launcher.wait_async(0))
        # Falls through to monitor which returns STOPPED for unknown
        assert status == WorkerStatus.STOPPED

    def test_wait_async_no_async_process_falls_back(self) -> None:
        """wait_async without async process falls back to sync monitor."""
        launcher = SubprocessLauncher()
        # No _async_processes attribute at all
        status = run_async(launcher.wait_async(0))
        assert status == WorkerStatus.STOPPED


# ---------------------------------------------------------------------------
# SubprocessLauncher.terminate_async (lines 854-892)
# ---------------------------------------------------------------------------
class TestSubprocessLauncherTerminateAsync:
    """Cover SubprocessLauncher.terminate_async."""

    def test_terminate_async_graceful(self) -> None:
        """terminate_async should gracefully stop async process."""
        launcher = SubprocessLauncher()

        mock_process = AsyncMock()
        mock_process.pid = 22222
        mock_process.returncode = 0
        mock_process.terminate = MagicMock()
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock()

        handle = WorkerHandle(worker_id=0, pid=22222, status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._async_processes = {0: mock_process}

        result = run_async(launcher.terminate_async(0, force=False))
        assert result is True
        mock_process.terminate.assert_called_once()
        # Worker should be cleaned up
        assert 0 not in launcher._workers
        assert 0 not in launcher._async_processes

    def test_terminate_async_force_kill(self) -> None:
        """terminate_async with force=True uses kill."""
        launcher = SubprocessLauncher()

        mock_process = AsyncMock()
        mock_process.pid = 22223
        mock_process.returncode = -9
        mock_process.kill = MagicMock()
        mock_process.terminate = MagicMock()
        mock_process.wait = AsyncMock()

        handle = WorkerHandle(worker_id=0, pid=22223, status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._async_processes = {0: mock_process}

        result = run_async(launcher.terminate_async(0, force=True))
        assert result is True
        mock_process.kill.assert_called_once()

    def test_terminate_async_no_handle_returns_false(self) -> None:
        """terminate_async returns False if handle missing."""
        launcher = SubprocessLauncher()

        mock_process = AsyncMock()
        launcher._async_processes = {0: mock_process}
        # No handle in _workers

        result = run_async(launcher.terminate_async(0))
        assert result is False

    def test_terminate_async_timeout_then_kill(self) -> None:
        """terminate_async should kill process on wait timeout."""
        launcher = SubprocessLauncher()

        mock_process = AsyncMock()
        mock_process.pid = 22224
        mock_process.returncode = -9
        mock_process.terminate = MagicMock()
        mock_process.kill = MagicMock()

        # First wait raises TimeoutError, second succeeds
        async def wait_with_timeout():
            raise TimeoutError("timed out")

        mock_process.wait = AsyncMock(side_effect=[TimeoutError("timed out"), None])

        handle = WorkerHandle(worker_id=0, pid=22224, status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._async_processes = {0: mock_process}

        # Patch asyncio.wait_for to raise TimeoutError

        async def mock_wait_for(coro, timeout):
            # Consume the coroutine to avoid warning
            try:
                await coro
            except Exception:
                pass
            raise TimeoutError("timed out")

        with patch("asyncio.wait_for", side_effect=mock_wait_for):
            result = run_async(launcher.terminate_async(0, force=False))

        assert result is True
        mock_process.kill.assert_called()

    def test_terminate_async_exception_returns_false(self) -> None:
        """terminate_async returns False on unexpected exception."""
        launcher = SubprocessLauncher()

        mock_process = MagicMock()
        mock_process.pid = 22225
        mock_process.terminate = MagicMock(side_effect=RuntimeError("unexpected"))

        handle = WorkerHandle(worker_id=0, pid=22225, status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._async_processes = {0: mock_process}

        result = run_async(launcher.terminate_async(0, force=False))
        assert result is False
        # Cleanup should still happen in finally block
        assert 0 not in launcher._async_processes

    def test_terminate_async_fallback_to_sync(self) -> None:
        """terminate_async falls back to sync terminate when no async process."""
        launcher = SubprocessLauncher()

        mock_process = MagicMock()
        mock_process.pid = 22226
        mock_process.poll.return_value = None
        mock_process.returncode = 0
        mock_process.terminate = MagicMock()
        mock_process.wait = MagicMock()

        handle = WorkerHandle(worker_id=0, pid=22226, status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._processes[0] = mock_process
        # No _async_processes -> falls back to sync

        result = run_async(launcher.terminate_async(0, force=False))
        assert result is True


# ---------------------------------------------------------------------------
# ContainerLauncher._start_container git mount logic (lines 1100-1105)
# ---------------------------------------------------------------------------
class TestContainerStartContainerGitMount:
    """Cover the git worktree mount logic in _start_container."""

    def test_start_container_mounts_git_worktree(self, tmp_path: Path) -> None:
        """_start_container should mount .git and worktree dirs when they exist."""
        launcher = ContainerLauncher()

        # Set up directory structure simulating a git worktree
        main_repo = tmp_path / "repo"
        worktree_dir = main_repo / ".zerg-worktrees" / "feat" / "worker-0"
        worktree_dir.mkdir(parents=True)
        (main_repo / ".zerg" / "state").mkdir(parents=True)
        (main_repo / ".git" / "worktrees" / "worker-0").mkdir(parents=True)
        # Create ~/.claude mock
        claude_dir = tmp_path / "home" / ".claude"
        claude_dir.mkdir(parents=True)
        claude_json = tmp_path / "home" / ".claude.json"
        claude_json.write_text("{}")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "container123abc"
        mock_result.stderr = ""

        with (
            patch("subprocess.run", return_value=mock_result),
            patch("os.getuid", return_value=1000),
            patch("os.getgid", return_value=1000),
            patch("pathlib.Path.home", return_value=tmp_path / "home"),
        ):
            env = {"ZERG_WORKER_ID": "0", "ZERG_FEATURE": "test"}
            container_id = launcher._start_container(
                container_name="zerg-worker-0",
                worktree_path=worktree_dir,
                env=env,
            )

        assert container_id == "container123abc"
        # Verify git worktree env vars were added
        assert env["ZERG_GIT_WORKTREE_DIR"] == "/workspace/.git-worktree"
        assert env["ZERG_GIT_MAIN_DIR"] == "/repo/.git"

    def test_start_container_no_git_dirs_skips_mount(self, tmp_path: Path) -> None:
        """_start_container should skip git mount when dirs don't exist."""
        launcher = ContainerLauncher()

        # Worktree path without proper git dirs
        worktree_dir = tmp_path / "a" / "b" / "c" / "worker-0"
        worktree_dir.mkdir(parents=True)
        (tmp_path / "a" / ".zerg" / "state").mkdir(parents=True)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "container456"
        mock_result.stderr = ""

        with (
            patch("subprocess.run", return_value=mock_result),
            patch("os.getuid", return_value=1000),
            patch("os.getgid", return_value=1000),
            patch("pathlib.Path.home", return_value=tmp_path / "nonexistent-home"),
        ):
            env = {"ZERG_WORKER_ID": "0"}
            container_id = launcher._start_container(
                container_name="zerg-worker-0",
                worktree_path=worktree_dir,
                env=env,
            )

        assert container_id == "container456"
        # Git env vars should NOT be set
        assert "ZERG_GIT_WORKTREE_DIR" not in env


# ---------------------------------------------------------------------------
# ContainerLauncher.monitor - health file check (lines 1318-1327)
# ---------------------------------------------------------------------------
class TestContainerMonitorHealthCheck:
    """Cover the health file check in ContainerLauncher.monitor."""

    def test_monitor_health_file_absent_after_grace_period(self) -> None:
        """Monitor returns STOPPED when health marker file is absent after 60s."""
        launcher = ContainerLauncher()

        # Set up a worker with started_at > 60 seconds ago
        handle = WorkerHandle(
            worker_id=0,
            container_id="health-test-123",
            status=WorkerStatus.RUNNING,
            started_at=datetime.now() - timedelta(seconds=120),
        )
        launcher._workers[0] = handle
        launcher._container_ids[0] = "health-test-123"

        # First call: docker inspect returns running
        inspect_result = MagicMock()
        inspect_result.returncode = 0
        inspect_result.stdout = "true,0"

        # Second call: health file check fails (absent)
        alive_result = MagicMock()
        alive_result.returncode = 1

        with patch("subprocess.run", side_effect=[inspect_result, alive_result]):
            status = launcher.monitor(0)

        assert status == WorkerStatus.STOPPED

    def test_monitor_health_file_present_after_grace_period(self) -> None:
        """Monitor returns RUNNING when health marker file is present after 60s."""
        launcher = ContainerLauncher()

        handle = WorkerHandle(
            worker_id=0,
            container_id="health-ok-123",
            status=WorkerStatus.RUNNING,
            started_at=datetime.now() - timedelta(seconds=120),
        )
        launcher._workers[0] = handle
        launcher._container_ids[0] = "health-ok-123"

        inspect_result = MagicMock()
        inspect_result.returncode = 0
        inspect_result.stdout = "true,0"

        alive_result = MagicMock()
        alive_result.returncode = 0  # File exists

        with patch("subprocess.run", side_effect=[inspect_result, alive_result]):
            status = launcher.monitor(0)

        assert status == WorkerStatus.RUNNING

    def test_monitor_within_grace_period_skips_health_check(self) -> None:
        """Monitor skips health check within the 60s grace period."""
        launcher = ContainerLauncher()

        handle = WorkerHandle(
            worker_id=0,
            container_id="young-123",
            status=WorkerStatus.RUNNING,
            started_at=datetime.now() - timedelta(seconds=10),
        )
        launcher._workers[0] = handle
        launcher._container_ids[0] = "young-123"

        inspect_result = MagicMock()
        inspect_result.returncode = 0
        inspect_result.stdout = "true,0"

        with patch("subprocess.run", return_value=inspect_result) as mock_run:
            status = launcher.monitor(0)

        assert status == WorkerStatus.RUNNING
        # Only one subprocess call (inspect), no health check
        assert mock_run.call_count == 1


# ---------------------------------------------------------------------------
# ContainerLauncher.spawn_async (lines 1518-1622)
# ---------------------------------------------------------------------------
class TestContainerLauncherSpawnAsync:
    """Cover ContainerLauncher.spawn_async."""

    def test_spawn_async_success(self, tmp_path: Path) -> None:
        """spawn_async should create container and return success."""
        launcher = ContainerLauncher()

        # Mock docker rm
        rm_proc = AsyncMock()
        rm_proc.communicate = AsyncMock(return_value=(b"", b""))

        with (
            patch.object(launcher, "_start_container_async", new_callable=AsyncMock, return_value="async-cid-123"),
            patch.object(launcher, "_wait_ready", return_value=True),
            patch.object(launcher, "_verify_worker_process", return_value=True),
            patch("asyncio.create_subprocess_exec", return_value=rm_proc),
            patch.dict(os.environ, {}, clear=False),
        ):
            result = run_async(
                launcher.spawn_async(
                    worker_id=0,
                    feature="async-test",
                    worktree_path=tmp_path,
                    branch="async-branch",
                )
            )

        assert result.success
        assert result.handle is not None
        assert result.handle.container_id == "async-cid-123"
        assert result.handle.status == WorkerStatus.RUNNING

    def test_spawn_async_invalid_worker_id(self, tmp_path: Path) -> None:
        """spawn_async rejects negative worker_id."""
        launcher = ContainerLauncher()

        result = run_async(
            launcher.spawn_async(
                worker_id=-5,
                feature="bad",
                worktree_path=tmp_path,
                branch="bad-branch",
            )
        )

        assert not result.success
        assert "Invalid worker_id" in result.error

    def test_spawn_async_container_start_failure(self, tmp_path: Path) -> None:
        """spawn_async returns error when container fails to start."""
        launcher = ContainerLauncher()

        rm_proc = AsyncMock()
        rm_proc.communicate = AsyncMock(return_value=(b"", b""))

        with (
            patch.object(launcher, "_start_container_async", new_callable=AsyncMock, return_value=None),
            patch("asyncio.create_subprocess_exec", return_value=rm_proc),
            patch.dict(os.environ, {}, clear=False),
        ):
            result = run_async(
                launcher.spawn_async(
                    worker_id=0,
                    feature="fail",
                    worktree_path=tmp_path,
                    branch="fail-branch",
                )
            )

        assert not result.success
        assert "Failed to start container" in result.error

    def test_spawn_async_ready_timeout(self, tmp_path: Path) -> None:
        """spawn_async returns error when container not ready."""
        launcher = ContainerLauncher()

        rm_proc = AsyncMock()
        rm_proc.communicate = AsyncMock(return_value=(b"", b""))

        with (
            patch.object(launcher, "_start_container_async", new_callable=AsyncMock, return_value="cid-ready-fail"),
            patch.object(launcher, "_wait_ready", return_value=False),
            patch("asyncio.create_subprocess_exec", return_value=rm_proc),
            patch.dict(os.environ, {}, clear=False),
        ):
            result = run_async(
                launcher.spawn_async(
                    worker_id=0,
                    feature="test",
                    worktree_path=tmp_path,
                    branch="branch",
                )
            )

        assert not result.success
        assert "ready" in result.error.lower()

    def test_spawn_async_verify_process_failure(self, tmp_path: Path) -> None:
        """spawn_async returns error when worker process fails to start."""
        launcher = ContainerLauncher()

        rm_proc = AsyncMock()
        rm_proc.communicate = AsyncMock(return_value=(b"", b""))

        with (
            patch.object(launcher, "_start_container_async", new_callable=AsyncMock, return_value="cid-proc-fail"),
            patch.object(launcher, "_wait_ready", return_value=True),
            patch.object(launcher, "_verify_worker_process", return_value=False),
            patch.object(launcher, "_cleanup_failed_container"),
            patch("asyncio.create_subprocess_exec", return_value=rm_proc),
            patch.dict(os.environ, {}, clear=False),
        ):
            result = run_async(
                launcher.spawn_async(
                    worker_id=0,
                    feature="test",
                    worktree_path=tmp_path,
                    branch="branch",
                )
            )

        assert not result.success
        assert "process" in result.error.lower()

    def test_spawn_async_with_task_list_id(self, tmp_path: Path) -> None:
        """spawn_async propagates CLAUDE_CODE_TASK_LIST_ID."""
        launcher = ContainerLauncher()

        rm_proc = AsyncMock()
        rm_proc.communicate = AsyncMock(return_value=(b"", b""))

        with (
            patch.object(
                launcher, "_start_container_async", new_callable=AsyncMock, return_value="cid-task"
            ) as mock_start,
            patch.object(launcher, "_wait_ready", return_value=True),
            patch.object(launcher, "_verify_worker_process", return_value=True),
            patch("asyncio.create_subprocess_exec", return_value=rm_proc),
            patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": "container-list"}),
        ):
            result = run_async(
                launcher.spawn_async(
                    worker_id=0,
                    feature="task-test",
                    worktree_path=tmp_path,
                    branch="task-branch",
                )
            )

        assert result.success
        # Verify the task list ID was in the env passed to _start_container_async
        call_kwargs = mock_start.call_args
        env_arg = call_kwargs.kwargs.get("env") or call_kwargs[1].get("env")
        assert env_arg["CLAUDE_CODE_TASK_LIST_ID"] == "container-list"

    def test_spawn_async_with_env_file_api_key(self, tmp_path: Path) -> None:
        """spawn_async reads ANTHROPIC_API_KEY from .env file."""
        launcher = ContainerLauncher()

        rm_proc = AsyncMock()
        rm_proc.communicate = AsyncMock(return_value=(b"", b""))

        # Create a .env file
        Path(".env")

        with (
            patch.object(launcher, "_start_container_async", new_callable=AsyncMock, return_value="cid-env"),
            patch.object(launcher, "_wait_ready", return_value=True),
            patch.object(launcher, "_verify_worker_process", return_value=True),
            patch("asyncio.create_subprocess_exec", return_value=rm_proc),
            patch.dict(os.environ, {}, clear=False),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value="ANTHROPIC_API_KEY=sk-test-key-123\n"),
        ):
            # Remove ANTHROPIC_API_KEY from env to force .env file read
            env_backup = os.environ.pop("ANTHROPIC_API_KEY", None)
            try:
                result = run_async(
                    launcher.spawn_async(
                        worker_id=0,
                        feature="env-test",
                        worktree_path=tmp_path,
                        branch="env-branch",
                    )
                )
            finally:
                if env_backup:
                    os.environ["ANTHROPIC_API_KEY"] = env_backup

        assert result.success

    def test_spawn_async_exception_handling(self, tmp_path: Path) -> None:
        """spawn_async should handle unexpected exceptions."""
        launcher = ContainerLauncher()

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=RuntimeError("docker broken"),
        ):
            result = run_async(
                launcher.spawn_async(
                    worker_id=0,
                    feature="err",
                    worktree_path=tmp_path,
                    branch="err-branch",
                )
            )

        assert not result.success
        assert "docker broken" in result.error


# ---------------------------------------------------------------------------
# ContainerLauncher._start_container_async (lines 1641-1713)
# ---------------------------------------------------------------------------
class TestContainerStartContainerAsync:
    """Cover ContainerLauncher._start_container_async."""

    def test_start_container_async_success(self, tmp_path: Path) -> None:
        """_start_container_async returns container ID on success."""
        launcher = ContainerLauncher()

        worktree_dir = tmp_path / "repo" / ".zerg-worktrees" / "feat" / "worker-0"
        worktree_dir.mkdir(parents=True)
        (tmp_path / "repo" / ".zerg" / "state").mkdir(parents=True)

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"async-cid-789\n", b""))

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
            patch("asyncio.wait_for", return_value=(b"async-cid-789\n", b"")),
            patch("os.getuid", return_value=1000),
            patch("os.getgid", return_value=1000),
            patch("pathlib.Path.home", return_value=tmp_path / "nonexistent-home"),
        ):
            # We need to handle wait_for properly
            async def run_test():
                return await launcher._start_container_async(
                    container_name="zerg-worker-0",
                    worktree_path=worktree_dir,
                    env={"ZERG_WORKER_ID": "0"},
                )

            # Patch wait_for to actually await the coroutine and return result
            async def fake_wait_for(coro, timeout):
                return await coro

            with patch("asyncio.wait_for", side_effect=fake_wait_for):
                container_id = run_async(run_test())

        assert container_id == "async-cid-789"

    def test_start_container_async_docker_failure(self, tmp_path: Path) -> None:
        """_start_container_async returns None on docker failure."""
        launcher = ContainerLauncher()

        worktree_dir = tmp_path / "repo" / ".zerg-worktrees" / "feat" / "worker-0"
        worktree_dir.mkdir(parents=True)
        (tmp_path / "repo" / ".zerg" / "state").mkdir(parents=True)

        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error starting\n"))

        async def fake_wait_for(coro, timeout):
            return await coro

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
            patch("asyncio.wait_for", side_effect=fake_wait_for),
            patch("os.getuid", return_value=1000),
            patch("os.getgid", return_value=1000),
            patch("pathlib.Path.home", return_value=tmp_path / "nonexistent-home"),
        ):
            container_id = run_async(
                launcher._start_container_async(
                    container_name="zerg-worker-0",
                    worktree_path=worktree_dir,
                    env={"ZERG_WORKER_ID": "0"},
                )
            )

        assert container_id is None

    def test_start_container_async_timeout(self, tmp_path: Path) -> None:
        """_start_container_async returns None on timeout."""
        launcher = ContainerLauncher()

        worktree_dir = tmp_path / "repo" / ".zerg-worktrees" / "feat" / "worker-0"
        worktree_dir.mkdir(parents=True)
        (tmp_path / "repo" / ".zerg" / "state").mkdir(parents=True)

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock()

        async def timeout_wait_for(coro, timeout):
            raise TimeoutError("timed out")

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
            patch("asyncio.wait_for", side_effect=timeout_wait_for),
            patch("os.getuid", return_value=1000),
            patch("os.getgid", return_value=1000),
            patch("pathlib.Path.home", return_value=tmp_path / "nonexistent-home"),
        ):
            container_id = run_async(
                launcher._start_container_async(
                    container_name="zerg-worker-0",
                    worktree_path=worktree_dir,
                    env={"ZERG_WORKER_ID": "0"},
                )
            )

        assert container_id is None

    def test_start_container_async_exception(self, tmp_path: Path) -> None:
        """_start_container_async returns None on unexpected exception."""
        launcher = ContainerLauncher()

        worktree_dir = tmp_path / "repo" / ".zerg-worktrees" / "feat" / "worker-0"
        worktree_dir.mkdir(parents=True)
        (tmp_path / "repo" / ".zerg" / "state").mkdir(parents=True)

        with (
            patch("asyncio.create_subprocess_exec", side_effect=RuntimeError("broken")),
            patch("os.getuid", return_value=1000),
            patch("os.getgid", return_value=1000),
            patch("pathlib.Path.home", return_value=tmp_path / "nonexistent-home"),
        ):
            container_id = run_async(
                launcher._start_container_async(
                    container_name="zerg-worker-0",
                    worktree_path=worktree_dir,
                    env={"ZERG_WORKER_ID": "0"},
                )
            )

        assert container_id is None

    def test_start_container_async_with_git_and_claude_mounts(self, tmp_path: Path) -> None:
        """_start_container_async mounts git worktree and claude config when present."""
        launcher = ContainerLauncher()

        main_repo = tmp_path / "repo"
        worktree_dir = main_repo / ".zerg-worktrees" / "feat" / "worker-0"
        worktree_dir.mkdir(parents=True)
        (main_repo / ".zerg" / "state").mkdir(parents=True)
        (main_repo / ".git" / "worktrees" / "worker-0").mkdir(parents=True)

        home_dir = tmp_path / "home"
        (home_dir / ".claude").mkdir(parents=True)
        (home_dir / ".claude.json").write_text("{}")

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"mounted-cid\n", b""))

        async def fake_wait_for(coro, timeout):
            return await coro

        with (
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc),
            patch("asyncio.wait_for", side_effect=fake_wait_for),
            patch("os.getuid", return_value=1000),
            patch("os.getgid", return_value=1000),
            patch("pathlib.Path.home", return_value=home_dir),
        ):
            env = {"ZERG_WORKER_ID": "0"}
            container_id = run_async(
                launcher._start_container_async(
                    container_name="zerg-worker-0",
                    worktree_path=worktree_dir,
                    env=env,
                )
            )

        assert container_id == "mounted-cid"
        assert env.get("ZERG_GIT_WORKTREE_DIR") == "/workspace/.git-worktree"
        assert env.get("ZERG_GIT_MAIN_DIR") == "/repo/.git"


# ---------------------------------------------------------------------------
# ContainerLauncher.terminate_async (lines 1727-1783)
# ---------------------------------------------------------------------------
class TestContainerLauncherTerminateAsync:
    """Cover ContainerLauncher.terminate_async."""

    def test_terminate_async_graceful_success(self) -> None:
        """terminate_async should gracefully stop container."""
        launcher = ContainerLauncher()

        handle = WorkerHandle(worker_id=0, container_id="term-cid-1", status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._container_ids[0] = "term-cid-1"

        # Mock docker stop and docker rm
        stop_proc = AsyncMock()
        stop_proc.returncode = 0
        stop_proc.communicate = AsyncMock(return_value=(b"", b""))

        rm_proc = AsyncMock()
        rm_proc.returncode = 0
        rm_proc.communicate = AsyncMock(return_value=(b"", b""))

        call_count = 0

        async def mock_create_subprocess(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return stop_proc  # docker stop
            return rm_proc  # docker rm

        async def fake_wait_for(coro, timeout):
            return await coro

        with (
            patch("asyncio.create_subprocess_exec", side_effect=mock_create_subprocess),
            patch("asyncio.wait_for", side_effect=fake_wait_for),
        ):
            result = run_async(launcher.terminate_async(0, force=False))

        assert result is True
        assert 0 not in launcher._workers
        assert 0 not in launcher._container_ids

    def test_terminate_async_force_kill(self) -> None:
        """terminate_async with force uses docker kill."""
        launcher = ContainerLauncher()

        handle = WorkerHandle(worker_id=0, container_id="term-cid-2", status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._container_ids[0] = "term-cid-2"

        kill_proc = AsyncMock()
        kill_proc.returncode = 0
        kill_proc.communicate = AsyncMock(return_value=(b"", b""))

        rm_proc = AsyncMock()
        rm_proc.returncode = 0
        rm_proc.communicate = AsyncMock(return_value=(b"", b""))

        call_count = 0

        async def mock_create_subprocess(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Check that "kill" is in args
                assert "kill" in args
                return kill_proc
            return rm_proc

        async def fake_wait_for(coro, timeout):
            return await coro

        with (
            patch("asyncio.create_subprocess_exec", side_effect=mock_create_subprocess),
            patch("asyncio.wait_for", side_effect=fake_wait_for),
        ):
            result = run_async(launcher.terminate_async(0, force=True))

        assert result is True

    def test_terminate_async_unknown_worker(self) -> None:
        """terminate_async returns False for unknown worker."""
        launcher = ContainerLauncher()

        result = run_async(launcher.terminate_async(999))
        assert result is False

    def test_terminate_async_stop_fails(self) -> None:
        """terminate_async returns False when docker stop fails."""
        launcher = ContainerLauncher()

        handle = WorkerHandle(worker_id=0, container_id="term-cid-3", status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._container_ids[0] = "term-cid-3"

        stop_proc = AsyncMock()
        stop_proc.returncode = 1
        stop_proc.communicate = AsyncMock(return_value=(b"", b"error stopping\n"))

        async def fake_wait_for(coro, timeout):
            return await coro

        with (
            patch("asyncio.create_subprocess_exec", return_value=stop_proc),
            patch("asyncio.wait_for", side_effect=fake_wait_for),
        ):
            result = run_async(launcher.terminate_async(0))

        assert result is False

    def test_terminate_async_timeout_forces_kill(self) -> None:
        """terminate_async forces kill on timeout."""
        launcher = ContainerLauncher()

        handle = WorkerHandle(worker_id=0, container_id="term-cid-4", status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._container_ids[0] = "term-cid-4"

        stop_proc = AsyncMock()
        stop_proc.communicate = AsyncMock()

        kill_proc = AsyncMock()
        kill_proc.communicate = AsyncMock(return_value=(b"", b""))

        call_count = 0

        async def mock_create_subprocess(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return stop_proc  # docker stop
            return kill_proc  # docker kill after timeout

        async def timeout_wait_for(coro, timeout):
            # Consume the coroutine
            try:
                await coro
            except Exception:
                pass
            raise TimeoutError("timed out")

        with (
            patch("asyncio.create_subprocess_exec", side_effect=mock_create_subprocess),
            patch("asyncio.wait_for", side_effect=timeout_wait_for),
        ):
            result = run_async(launcher.terminate_async(0))

        assert result is True
        assert handle.status == WorkerStatus.STOPPED

    def test_terminate_async_exception(self) -> None:
        """terminate_async returns False on unexpected exception."""
        launcher = ContainerLauncher()

        handle = WorkerHandle(worker_id=0, container_id="term-cid-5", status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._container_ids[0] = "term-cid-5"

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=RuntimeError("unexpected docker error"),
        ):
            result = run_async(launcher.terminate_async(0))

        assert result is False
        # Cleanup should happen in finally
        assert 0 not in launcher._container_ids
        assert 0 not in launcher._workers
