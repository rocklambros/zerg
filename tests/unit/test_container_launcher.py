"""Unit tests for ContainerLauncher.

Targets uncovered lines for >=80% coverage:
- spawn validation, env injection, git mounts
- _start_container_impl error paths
- _wait_ready / _verify_worker_process exception branches
- monitor alive-check and exit code branches
- terminate timeout / force-kill failures
- get_output, ensure_network, image_exists
- spawn_async, _start_container_async, terminate_async
"""

from __future__ import annotations

import asyncio
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zerg.constants import WorkerStatus
from zerg.launcher_types import LauncherConfig, WorkerHandle
from zerg.launchers.container_launcher import ContainerLauncher

pytestmark = pytest.mark.docker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _launcher(**kwargs) -> ContainerLauncher:
    """Create a ContainerLauncher with sensible test defaults."""
    defaults = {"image_name": "test-image", "memory_limit": "4g", "cpu_limit": 2.0}
    defaults.update(kwargs)
    return ContainerLauncher(**defaults)


def _fake_worktree(tmp_path: Path) -> Path:
    """Create a fake worktree path with expected parent structure.

    ContainerLauncher derives the main repo as worktree.parent.parent.parent,
    so we need: repo/.zerg-worktrees/feature/worker-0
    """
    repo = tmp_path / "repo"
    wt = repo / ".zerg-worktrees" / "feature" / "worker-0"
    wt.mkdir(parents=True)
    # Create .zerg/state in the repo
    (repo / ".zerg" / "state").mkdir(parents=True)
    return wt


# ===========================================================================
# _build_container_cmd tests
# ===========================================================================


class TestBuildContainerCmd:
    """Tests for docker command construction."""

    def test_basic_command_structure(self, tmp_path: Path) -> None:
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()
        env: dict[str, str] = {"ZERG_WORKER_ID": "0"}

        cmd = launcher._build_container_cmd("zerg-worker-0", wt, env)

        assert cmd[0] == "docker"
        assert cmd[1] == "run"
        assert "-d" in cmd
        assert "--name" in cmd
        assert cmd[cmd.index("--name") + 1] == "zerg-worker-0"

    def test_resource_limits_in_command(self, tmp_path: Path) -> None:
        wt = _fake_worktree(tmp_path)
        launcher = _launcher(memory_limit="8g", cpu_limit=4.0)
        env: dict[str, str] = {}

        cmd = launcher._build_container_cmd("w0", wt, env)

        mem_idx = cmd.index("--memory")
        assert cmd[mem_idx + 1] == "8g"
        cpus_idx = cmd.index("--cpus")
        assert cmd[cpus_idx + 1] == "4.0"

    def test_workspace_volume_mount(self, tmp_path: Path) -> None:
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()
        env: dict[str, str] = {}

        cmd = launcher._build_container_cmd("w0", wt, env)

        # Find volume mounts
        volume_args = [cmd[i + 1] for i, v in enumerate(cmd) if v == "-v"]
        workspace_mount = [v for v in volume_args if ":/workspace" in v and "state" not in v]
        assert len(workspace_mount) >= 1
        assert str(wt.absolute()) in workspace_mount[0]

    def test_state_dir_volume_mount(self, tmp_path: Path) -> None:
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()
        env: dict[str, str] = {}

        cmd = launcher._build_container_cmd("w0", wt, env)

        volume_args = [cmd[i + 1] for i, v in enumerate(cmd) if v == "-v"]
        state_mount = [v for v in volume_args if "state" in v]
        assert len(state_mount) >= 1

    def test_git_worktree_mounts_when_dirs_exist(self, tmp_path: Path) -> None:
        """Lines 249-254: git dir and worktree metadata mounts."""
        wt = _fake_worktree(tmp_path)
        repo = wt.parent.parent.parent
        # Create .git dir and worktrees metadata
        git_dir = repo / ".git"
        git_dir.mkdir(parents=True)
        worktree_meta = git_dir / "worktrees" / "worker-0"
        worktree_meta.mkdir(parents=True)

        env: dict[str, str] = {}
        launcher = _launcher()
        cmd = launcher._build_container_cmd("w0", wt, env)

        volume_args = [cmd[i + 1] for i, v in enumerate(cmd) if v == "-v"]
        git_mounts = [v for v in volume_args if "/repo/.git" in v]
        assert len(git_mounts) >= 1, "Expected .git mount"
        # Also check env vars were added
        assert env.get("ZERG_GIT_WORKTREE_DIR") == "/workspace/.git-worktree"
        assert env.get("ZERG_GIT_MAIN_DIR") == "/repo/.git"

    def test_claude_config_mount(self, tmp_path: Path) -> None:
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()
        env: dict[str, str] = {}

        with patch("zerg.launchers.container_launcher.Path.home", return_value=tmp_path):
            # Create .claude dir
            claude_dir = tmp_path / ".claude"
            claude_dir.mkdir()
            cmd = launcher._build_container_cmd("w0", wt, env)

        volume_args = [cmd[i + 1] for i, v in enumerate(cmd) if v == "-v"]
        claude_mounts = [v for v in volume_args if ".claude" in v and ".claude.json" not in v]
        assert len(claude_mounts) >= 1

    def test_claude_json_mount(self, tmp_path: Path) -> None:
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()
        env: dict[str, str] = {}

        with patch("zerg.launchers.container_launcher.Path.home", return_value=tmp_path):
            # Create .claude.json file
            (tmp_path / ".claude.json").write_text("{}")
            cmd = launcher._build_container_cmd("w0", wt, env)

        volume_args = [cmd[i + 1] for i, v in enumerate(cmd) if v == "-v"]
        json_mounts = [v for v in volume_args if ".claude.json" in v]
        assert len(json_mounts) >= 1

    def test_env_vars_in_command(self, tmp_path: Path) -> None:
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()
        env = {"ZERG_WORKER_ID": "5", "ZERG_FEATURE": "test"}

        cmd = launcher._build_container_cmd("w0", wt, env)

        # Collect -e flags
        env_args = [cmd[i + 1] for i, v in enumerate(cmd) if v == "-e"]
        env_keys = [a.split("=")[0] for a in env_args]
        assert "ZERG_WORKER_ID" in env_keys
        assert "ZERG_FEATURE" in env_keys

    def test_network_in_command(self, tmp_path: Path) -> None:
        wt = _fake_worktree(tmp_path)
        launcher = _launcher(network="my-net")
        env: dict[str, str] = {}

        cmd = launcher._build_container_cmd("w0", wt, env)

        net_idx = cmd.index("--network")
        assert cmd[net_idx + 1] == "my-net"

    def test_entry_script_in_command(self, tmp_path: Path) -> None:
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()
        env: dict[str, str] = {}

        cmd = launcher._build_container_cmd("w0", wt, env)

        # Last args should contain the entry script reference
        bash_cmd = cmd[-1]
        assert "worker_entry.sh" in bash_cmd


# ===========================================================================
# _start_container_impl tests
# ===========================================================================


class TestStartContainerImpl:
    """Tests for async container start core logic."""

    def test_success_returns_container_id(self, tmp_path: Path) -> None:
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()

        async def run_fn(cmd):
            return 0, "abc123\n", ""

        result = asyncio.run(launcher._start_container_impl("w0", wt, {}, run_fn))
        assert result == "abc123"

    def test_nonzero_returncode_returns_none(self, tmp_path: Path) -> None:
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()

        async def run_fn(cmd):
            return 1, "", "error msg"

        result = asyncio.run(launcher._start_container_impl("w0", wt, {}, run_fn))
        assert result is None

    def test_timeout_returns_none(self, tmp_path: Path) -> None:
        """Lines 332-334: TimeoutExpired branch."""
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()

        async def run_fn(cmd):
            raise TimeoutError("timed out")

        result = asyncio.run(launcher._start_container_impl("w0", wt, {}, run_fn))
        assert result is None

    def test_subprocess_timeout_returns_none(self, tmp_path: Path) -> None:
        """Lines 332-334: subprocess.TimeoutExpired branch."""
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()

        async def run_fn(cmd):
            raise subprocess.TimeoutExpired(cmd="docker", timeout=60)

        result = asyncio.run(launcher._start_container_impl("w0", wt, {}, run_fn))
        assert result is None

    def test_generic_exception_returns_none(self, tmp_path: Path) -> None:
        """Lines 335-337: Generic exception branch."""
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()

        async def run_fn(cmd):
            raise RuntimeError("docker not found")

        result = asyncio.run(launcher._start_container_impl("w0", wt, {}, run_fn))
        assert result is None


# ===========================================================================
# spawn tests
# ===========================================================================


class TestSpawn:
    """Tests for the sync spawn method."""

    def test_invalid_worker_id_negative(self, tmp_path: Path) -> None:
        """Line 93: Invalid worker_id raises error, caught by spawn."""
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()

        result = launcher.spawn(-1, "feat", wt, "branch-x")
        assert not result.success
        assert "Invalid worker_id" in (result.error or "")

    def test_invalid_worker_id_string(self, tmp_path: Path) -> None:
        """Line 93: Non-int worker_id."""
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()

        result = launcher.spawn("abc", "feat", wt, "branch-x")  # type: ignore[arg-type]
        assert not result.success

    @patch("subprocess.run")
    def test_spawn_container_start_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Spawn returns failure when container start fails."""
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()
        # First call: docker rm (cleanup)
        # Second call: docker run (fails)
        mock_run.side_effect = [
            MagicMock(returncode=0),  # rm -f
            MagicMock(returncode=1, stdout="", stderr="image not found"),  # docker run
        ]

        with patch.dict("os.environ", {}, clear=True):
            result = launcher.spawn(0, "feat", wt, "branch-x")

        assert not result.success
        assert result.error == "Failed to start container"

    @patch("subprocess.run")
    def test_spawn_wait_ready_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Spawn returns failure when container doesn't become ready."""
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()

        # Mock docker rm and docker run to succeed
        mock_run.side_effect = [
            MagicMock(returncode=0),  # rm -f
            MagicMock(returncode=0, stdout="containerXYZ\n", stderr=""),  # docker run
        ]

        # Mock _wait_ready to return False directly (avoids polling loop)
        with patch.dict("os.environ", {}, clear=True), patch.object(launcher, "_wait_ready", return_value=False):
            result = launcher.spawn(0, "feat", wt, "branch-x")

        assert not result.success
        assert "ready" in (result.error or "").lower()

    @patch("subprocess.run")
    def test_spawn_env_vars_from_config_and_extra(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Lines 133-137: config.env_vars and extra env both validated."""
        wt = _fake_worktree(tmp_path)
        config = LauncherConfig(env_vars={"ZERG_DEBUG": "1"})
        launcher = ContainerLauncher(config=config, image_name="test-image")

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            cmd = args[0]
            if "rm" in cmd:
                return MagicMock(returncode=0)
            if "run" in cmd:
                return MagicMock(returncode=0, stdout="cid123\n", stderr="")
            if "inspect" in cmd:
                return MagicMock(returncode=0, stdout="true\n", stderr="")
            if "pgrep" in cmd:
                return MagicMock(returncode=0)
            return MagicMock(returncode=0)

        mock_run.side_effect = side_effect

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            launcher.spawn(
                0,
                "feat",
                wt,
                "branch-x",
                env={"ZERG_LOG_LEVEL": "debug"},
            )

        # Verify the docker run command included the env vars
        docker_run_calls = [c for c in mock_run.call_args_list if len(c[0]) > 0 and "run" in c[0][0]]
        assert len(docker_run_calls) >= 1
        run_cmd = docker_run_calls[0][0][0]
        cmd_str = " ".join(run_cmd)
        assert "ZERG_DEBUG=1" in cmd_str
        assert "ZERG_LOG_LEVEL=debug" in cmd_str

    @patch("subprocess.run")
    def test_spawn_reads_api_key_from_env_file(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """API key read from .env file when not in environment."""
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()

        def side_effect(*args, **kwargs):
            cmd = args[0]
            if "rm" in cmd:
                return MagicMock(returncode=0)
            if "run" in cmd:
                return MagicMock(returncode=0, stdout="cid\n", stderr="")
            if "inspect" in cmd:
                return MagicMock(returncode=0, stdout="true\n", stderr="")
            if "pgrep" in cmd:
                return MagicMock(returncode=0)
            return MagicMock(returncode=0)

        mock_run.side_effect = side_effect

        env_file = tmp_path / ".env"
        env_file.write_text("ANTHROPIC_API_KEY=sk-test-12345\n")

        import os

        orig_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            with patch.dict("os.environ", {}, clear=True):
                launcher.spawn(0, "feat", wt, "branch-x")
        finally:
            os.chdir(orig_cwd)

        # Verify API key ended up in the docker run command
        docker_run_calls = [c for c in mock_run.call_args_list if len(c[0]) > 0 and "run" in c[0][0]]
        if docker_run_calls:
            run_cmd = docker_run_calls[0][0][0]
            cmd_str = " ".join(run_cmd)
            assert "ANTHROPIC_API_KEY=sk-test-12345" in cmd_str

    @patch("subprocess.run")
    def test_spawn_includes_task_list_id(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """CLAUDE_CODE_TASK_LIST_ID propagated when present."""
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()

        def side_effect(*args, **kwargs):
            cmd = args[0]
            if "rm" in cmd:
                return MagicMock(returncode=0)
            if "run" in cmd:
                return MagicMock(returncode=0, stdout="cid\n", stderr="")
            if "inspect" in cmd:
                return MagicMock(returncode=0, stdout="true\n", stderr="")
            if "pgrep" in cmd:
                return MagicMock(returncode=0)
            return MagicMock(returncode=0)

        mock_run.side_effect = side_effect

        with patch.dict("os.environ", {"CLAUDE_CODE_TASK_LIST_ID": "my-list"}, clear=True):
            launcher.spawn(0, "feat", wt, "branch-x")

        docker_run_calls = [c for c in mock_run.call_args_list if len(c[0]) > 0 and "run" in c[0][0]]
        if docker_run_calls:
            run_cmd = docker_run_calls[0][0][0]
            cmd_str = " ".join(run_cmd)
            assert "CLAUDE_CODE_TASK_LIST_ID=my-list" in cmd_str


# ===========================================================================
# _wait_ready tests
# ===========================================================================


class TestWaitReady:
    """Tests for container readiness polling."""

    @patch("subprocess.run")
    @patch("time.sleep")
    def test_ready_immediately(self, mock_sleep: MagicMock, mock_run: MagicMock) -> None:
        launcher = _launcher()
        mock_run.return_value = MagicMock(returncode=0, stdout="true\n")

        assert launcher._wait_ready("abc123", timeout=5) is True

    @patch("subprocess.run")
    @patch("time.sleep")
    def test_not_ready_timeout(self, mock_sleep: MagicMock, mock_run: MagicMock) -> None:
        launcher = _launcher()
        mock_run.return_value = MagicMock(returncode=0, stdout="false\n")

        # Use a very short timeout
        with patch("time.time", side_effect=[0.0, 0.0, 1.0, 2.0]):
            result = launcher._wait_ready("abc123", timeout=1.5)

        assert result is False

    @patch("subprocess.run")
    @patch("time.sleep")
    def test_exception_during_readiness_check(self, mock_sleep: MagicMock, mock_run: MagicMock) -> None:
        """Lines 397-399: SubprocessError during polling retries."""
        launcher = _launcher()
        mock_run.side_effect = subprocess.SubprocessError("connection refused")

        with patch("time.time", side_effect=[0.0, 0.0, 1.0, 2.0]):
            result = launcher._wait_ready("abc123", timeout=1.5)

        assert result is False

    @patch("subprocess.run")
    @patch("time.sleep")
    def test_os_error_during_readiness_check(self, mock_sleep: MagicMock, mock_run: MagicMock) -> None:
        """Lines 397-399: OSError during polling retries."""
        launcher = _launcher()
        mock_run.side_effect = OSError("docker not found")

        with patch("time.time", side_effect=[0.0, 0.0, 1.0, 2.0]):
            result = launcher._wait_ready("abc123", timeout=1.5)

        assert result is False


# ===========================================================================
# _verify_worker_process tests
# ===========================================================================


class TestVerifyWorkerProcess:
    """Tests for worker process verification."""

    @patch("subprocess.run")
    def test_process_found(self, mock_run: MagicMock) -> None:
        launcher = _launcher()
        mock_run.return_value = MagicMock(returncode=0)

        assert launcher._verify_worker_process("cid123", timeout=2.0) is True

    @patch("subprocess.run")
    def test_process_not_found(self, mock_run: MagicMock) -> None:
        launcher = _launcher()
        mock_run.return_value = MagicMock(returncode=1)

        with patch("time.sleep"), patch("time.time", side_effect=[0.0, 0.0, 1.0, 2.0]):
            result = launcher._verify_worker_process("cid123", timeout=1.5)

        assert result is False

    @patch("subprocess.run")
    def test_exception_during_process_check(self, mock_run: MagicMock) -> None:
        """Lines 461-462: SubprocessError during pgrep retries."""
        launcher = _launcher()
        mock_run.side_effect = subprocess.SubprocessError("exec failed")

        with patch("time.sleep"), patch("time.time", side_effect=[0.0, 0.0, 1.0, 2.0]):
            result = launcher._verify_worker_process("cid123", timeout=1.5)

        assert result is False

    @patch("subprocess.run")
    def test_os_error_during_process_check(self, mock_run: MagicMock) -> None:
        """Lines 461-462: OSError during pgrep retries."""
        launcher = _launcher()
        mock_run.side_effect = OSError("no such file")

        with patch("time.sleep"), patch("time.time", side_effect=[0.0, 0.0, 1.0, 2.0]):
            result = launcher._verify_worker_process("cid123", timeout=1.5)

        assert result is False


# ===========================================================================
# _cleanup_failed_container tests
# ===========================================================================


class TestCleanupFailedContainer:
    @patch("subprocess.run")
    def test_cleanup_removes_tracking(self, mock_run: MagicMock) -> None:
        launcher = _launcher()
        mock_run.return_value = MagicMock(returncode=0)
        launcher._container_ids[0] = "cid"
        launcher._workers[0] = MagicMock()

        launcher._cleanup_failed_container("cid", 0)

        assert 0 not in launcher._container_ids
        assert 0 not in launcher._workers

    @patch("subprocess.run")
    def test_cleanup_handles_exception(self, mock_run: MagicMock) -> None:
        launcher = _launcher()
        mock_run.side_effect = OSError("docker error")
        launcher._container_ids[0] = "cid"
        launcher._workers[0] = MagicMock()

        # Should not raise
        launcher._cleanup_failed_container("cid", 0)
        # Tracking still cleaned
        assert 0 not in launcher._container_ids


# ===========================================================================
# monitor tests
# ===========================================================================


class TestMonitor:
    """Tests for container status monitoring."""

    def test_unknown_worker_returns_stopped(self) -> None:
        launcher = _launcher()
        assert launcher.monitor(999) == WorkerStatus.STOPPED

    @patch("subprocess.run")
    def test_container_running(self, mock_run: MagicMock) -> None:
        launcher = _launcher()
        handle = WorkerHandle(worker_id=0, container_id="cid", status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._container_ids[0] = "cid"

        mock_run.return_value = MagicMock(returncode=0, stdout="true,0\n")
        status = launcher.monitor(0)
        assert status == WorkerStatus.RUNNING

    @patch("subprocess.run")
    def test_container_exited_code_0(self, mock_run: MagicMock) -> None:
        launcher = _launcher()
        handle = WorkerHandle(worker_id=0, container_id="cid", status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._container_ids[0] = "cid"

        mock_run.return_value = MagicMock(returncode=0, stdout="false,0\n")
        status = launcher.monitor(0)
        assert status == WorkerStatus.STOPPED

    @patch("subprocess.run")
    def test_container_exited_code_2_checkpointing(self, mock_run: MagicMock) -> None:
        """Lines 557: Exit code 2 -> CHECKPOINTING."""
        launcher = _launcher()
        handle = WorkerHandle(worker_id=0, container_id="cid", status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._container_ids[0] = "cid"

        mock_run.return_value = MagicMock(returncode=0, stdout="false,2\n")
        status = launcher.monitor(0)
        assert status == WorkerStatus.CHECKPOINTING

    @patch("subprocess.run")
    def test_container_exited_code_3_blocked(self, mock_run: MagicMock) -> None:
        """Lines 558-559: Exit code 3 -> BLOCKED."""
        launcher = _launcher()
        handle = WorkerHandle(worker_id=0, container_id="cid", status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._container_ids[0] = "cid"

        mock_run.return_value = MagicMock(returncode=0, stdout="false,3\n")
        status = launcher.monitor(0)
        assert status == WorkerStatus.BLOCKED

    @patch("subprocess.run")
    def test_container_exited_other_code_crashed(self, mock_run: MagicMock) -> None:
        launcher = _launcher()
        handle = WorkerHandle(worker_id=0, container_id="cid", status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._container_ids[0] = "cid"

        mock_run.return_value = MagicMock(returncode=0, stdout="false,137\n")
        status = launcher.monitor(0)
        assert status == WorkerStatus.CRASHED

    @patch("subprocess.run")
    def test_inspect_failure_returns_stopped(self, mock_run: MagicMock) -> None:
        launcher = _launcher()
        handle = WorkerHandle(worker_id=0, container_id="cid", status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._container_ids[0] = "cid"

        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="not found")
        status = launcher.monitor(0)
        assert status == WorkerStatus.STOPPED

    @patch("subprocess.run")
    def test_monitor_alive_check_marker_absent(self, mock_run: MagicMock) -> None:
        """Lines 538-546: Alive check finds marker file absent -> STOPPED."""
        launcher = _launcher()
        started = datetime.now() - timedelta(seconds=120)
        handle = WorkerHandle(
            worker_id=0,
            container_id="cid",
            status=WorkerStatus.RUNNING,
        )
        handle.started_at = started
        launcher._workers[0] = handle
        launcher._container_ids[0] = "cid"

        def side_effect(*args, **kwargs):
            cmd = args[0]
            if "inspect" in cmd:
                return MagicMock(returncode=0, stdout="true,0\n")
            if "test" in cmd:
                # marker file absent
                return MagicMock(returncode=1)
            return MagicMock(returncode=0)

        mock_run.side_effect = side_effect
        status = launcher.monitor(0)
        assert status == WorkerStatus.STOPPED

    @patch("subprocess.run")
    def test_monitor_alive_check_marker_present(self, mock_run: MagicMock) -> None:
        """Alive check finds marker file present -> remains RUNNING."""
        launcher = _launcher()
        started = datetime.now() - timedelta(seconds=120)
        handle = WorkerHandle(
            worker_id=0,
            container_id="cid",
            status=WorkerStatus.RUNNING,
        )
        handle.started_at = started
        launcher._workers[0] = handle
        launcher._container_ids[0] = "cid"

        def side_effect(*args, **kwargs):
            cmd = args[0]
            if "inspect" in cmd:
                return MagicMock(returncode=0, stdout="true,0\n")
            if "test" in cmd:
                return MagicMock(returncode=0)  # marker present
            return MagicMock(returncode=0)

        mock_run.side_effect = side_effect
        status = launcher.monitor(0)
        assert status == WorkerStatus.RUNNING

    @patch("subprocess.run")
    def test_monitor_cooldown_skips_docker_call(self, mock_run: MagicMock) -> None:
        """FR-1: Recent health check skips docker call."""
        launcher = _launcher()
        handle = WorkerHandle(worker_id=0, container_id="cid", status=WorkerStatus.RUNNING)
        handle.health_check_at = datetime.now()  # just checked
        launcher._workers[0] = handle
        launcher._container_ids[0] = "cid"

        status = launcher.monitor(0)
        assert status == WorkerStatus.RUNNING
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_monitor_initializing_becomes_running(self, mock_run: MagicMock) -> None:
        launcher = _launcher()
        handle = WorkerHandle(worker_id=0, container_id="cid", status=WorkerStatus.INITIALIZING)
        launcher._workers[0] = handle
        launcher._container_ids[0] = "cid"

        mock_run.return_value = MagicMock(returncode=0, stdout="true,0\n")
        status = launcher.monitor(0)
        assert status == WorkerStatus.RUNNING

    @patch("subprocess.run")
    def test_monitor_exception_returns_current_status(self, mock_run: MagicMock) -> None:
        """Lines 565-567: Exception during monitor returns current status."""
        launcher = _launcher()
        handle = WorkerHandle(worker_id=0, container_id="cid", status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._container_ids[0] = "cid"

        mock_run.side_effect = subprocess.SubprocessError("docker down")
        status = launcher.monitor(0)
        assert status == WorkerStatus.RUNNING


# ===========================================================================
# terminate tests
# ===========================================================================


class TestTerminate:
    """Tests for container termination."""

    @patch("subprocess.run")
    def test_terminate_success(self, mock_run: MagicMock) -> None:
        launcher = _launcher()
        handle = WorkerHandle(worker_id=0, container_id="cid", status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._container_ids[0] = "cid"

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = launcher.terminate(0)
        assert result is True
        assert 0 not in launcher._container_ids

    @patch("subprocess.run")
    def test_terminate_force(self, mock_run: MagicMock) -> None:
        launcher = _launcher()
        handle = WorkerHandle(worker_id=0, container_id="cid", status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._container_ids[0] = "cid"

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = launcher.terminate(0, force=True)
        assert result is True

        # First call should use "kill" not "stop"
        first_cmd = mock_run.call_args_list[0][0][0]
        assert "kill" in first_cmd

    def test_terminate_unknown_worker(self) -> None:
        launcher = _launcher()
        result = launcher.terminate(999)
        assert result is False

    @patch("subprocess.run")
    def test_terminate_stop_failure(self, mock_run: MagicMock) -> None:
        launcher = _launcher()
        handle = WorkerHandle(worker_id=0, container_id="cid", status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._container_ids[0] = "cid"

        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        result = launcher.terminate(0)
        assert result is False


# ===========================================================================
# _terminate_impl timeout / force-kill tests
# ===========================================================================


class TestTerminateImplTimeout:
    """Tests for terminate timeout and force-kill failure paths."""

    def test_timeout_triggers_force_kill_success(self) -> None:
        """Lines 617-624: Timeout leads to force kill."""
        launcher = _launcher()
        handle = WorkerHandle(worker_id=0, container_id="cid", status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._container_ids[0] = "cid"

        call_count = 0

        async def run_fn(cmd, timeout):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("docker stop timed out")
            # force kill succeeds
            return 0, "", ""

        result = asyncio.run(launcher._terminate_impl(0, force=False, run_fn=run_fn))
        assert result is True

    def test_timeout_force_kill_also_fails(self) -> None:
        """Lines 621-622: Force kill also fails after timeout."""
        launcher = _launcher()
        handle = WorkerHandle(worker_id=0, container_id="cid", status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._container_ids[0] = "cid"

        call_count = 0

        async def run_fn(cmd, timeout):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("docker stop timed out")
            # force kill also fails
            raise OSError("docker kill failed too")

        result = asyncio.run(launcher._terminate_impl(0, force=False, run_fn=run_fn))
        # Still returns True because cleanup proceeds
        assert result is True
        assert 0 not in launcher._container_ids

    def test_generic_exception_returns_false(self) -> None:
        """Lines 626-628: Generic exception during terminate."""
        launcher = _launcher()
        handle = WorkerHandle(worker_id=0, container_id="cid", status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._container_ids[0] = "cid"

        async def run_fn(cmd, timeout):
            raise RuntimeError("unexpected")

        result = asyncio.run(launcher._terminate_impl(0, force=False, run_fn=run_fn))
        assert result is False
        # Finally block still cleans up
        assert 0 not in launcher._container_ids


# ===========================================================================
# get_output tests
# ===========================================================================


class TestGetOutput:
    """Tests for container log retrieval."""

    def test_unknown_worker_returns_empty(self) -> None:
        """Lines 679-682: No container_id returns empty."""
        launcher = _launcher()
        assert launcher.get_output(999) == ""

    @patch("subprocess.run")
    def test_success_returns_combined_output(self, mock_run: MagicMock) -> None:
        """Lines 684-691: Successful log retrieval."""
        launcher = _launcher()
        launcher._container_ids[0] = "cid"

        mock_run.return_value = MagicMock(returncode=0, stdout="stdout-line\n", stderr="stderr-line\n")
        output = launcher.get_output(0, tail=50)
        assert "stdout-line" in output
        assert "stderr-line" in output

        # Verify tail parameter
        cmd = mock_run.call_args[0][0]
        assert "--tail" in cmd
        assert "50" in cmd

    @patch("subprocess.run")
    def test_exception_returns_empty(self, mock_run: MagicMock) -> None:
        """Lines 692-694: SubprocessError returns empty."""
        launcher = _launcher()
        launcher._container_ids[0] = "cid"
        mock_run.side_effect = subprocess.SubprocessError("logs failed")

        assert launcher.get_output(0) == ""

    @patch("subprocess.run")
    def test_os_error_returns_empty(self, mock_run: MagicMock) -> None:
        """Lines 692-694: OSError returns empty."""
        launcher = _launcher()
        launcher._container_ids[0] = "cid"
        mock_run.side_effect = OSError("no docker")

        assert launcher.get_output(0) == ""


# ===========================================================================
# ensure_network tests
# ===========================================================================


class TestEnsureNetwork:
    """Tests for Docker network management."""

    @patch("subprocess.run")
    def test_network_already_exists(self, mock_run: MagicMock) -> None:
        launcher = _launcher()
        mock_run.return_value = MagicMock(returncode=0)
        assert launcher.ensure_network() is True
        # Only one call (inspect), no create
        assert mock_run.call_count == 1

    @patch("subprocess.run")
    def test_network_created_successfully(self, mock_run: MagicMock) -> None:
        launcher = _launcher()
        mock_run.side_effect = [
            MagicMock(returncode=1),  # inspect fails
            MagicMock(returncode=0),  # create succeeds
        ]
        assert launcher.ensure_network() is True

    @patch("subprocess.run")
    def test_network_create_failure(self, mock_run: MagicMock) -> None:
        """Lines 726-727: Network creation fails."""
        launcher = _launcher()
        mock_run.side_effect = [
            MagicMock(returncode=1),  # inspect fails
            MagicMock(returncode=1, stderr="permission denied"),  # create fails
        ]
        assert launcher.ensure_network() is False

    @patch("subprocess.run")
    def test_network_exception(self, mock_run: MagicMock) -> None:
        """Lines 729-731: Exception during network operations."""
        launcher = _launcher()
        mock_run.side_effect = subprocess.SubprocessError("docker error")
        assert launcher.ensure_network() is False


# ===========================================================================
# image_exists tests
# ===========================================================================


class TestImageExists:
    """Tests for Docker image existence check."""

    @patch("subprocess.run")
    def test_image_exists(self, mock_run: MagicMock) -> None:
        launcher = _launcher()
        mock_run.return_value = MagicMock(returncode=0)
        assert launcher.image_exists() is True

    @patch("subprocess.run")
    def test_image_not_exists(self, mock_run: MagicMock) -> None:
        launcher = _launcher()
        mock_run.return_value = MagicMock(returncode=1)
        assert launcher.image_exists() is False

    @patch("subprocess.run")
    def test_image_check_exception(self, mock_run: MagicMock) -> None:
        """Lines 746-748: Exception returns False."""
        launcher = _launcher()
        mock_run.side_effect = subprocess.SubprocessError("docker error")
        assert launcher.image_exists() is False

    @patch("subprocess.run")
    def test_image_check_os_error(self, mock_run: MagicMock) -> None:
        """Lines 746-748: OSError returns False."""
        launcher = _launcher()
        mock_run.side_effect = OSError("no docker binary")
        assert launcher.image_exists() is False


# ===========================================================================
# spawn_async tests
# ===========================================================================


class TestSpawnAsync:
    """Tests for async spawn method (lines 773-879)."""

    def test_invalid_worker_id_async(self, tmp_path: Path) -> None:
        """Lines 775-776: Invalid worker_id in async spawn."""
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()

        result = asyncio.run(launcher.spawn_async(-1, "feat", wt, "branch"))
        assert not result.success
        assert "Invalid worker_id" in (result.error or "")

    def test_container_start_failure_async(self, tmp_path: Path) -> None:
        """Lines 834-839: Container start failure in async path."""
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()

        async def _test():
            with (
                patch.object(launcher, "_start_container_async", return_value=None),
                patch("asyncio.create_subprocess_exec") as mock_proc,
            ):
                mock_p = AsyncMock()
                mock_p.communicate.return_value = (b"", b"")
                mock_proc.return_value = mock_p
                with patch.dict("os.environ", {}, clear=True):
                    return await launcher.spawn_async(0, "feat", wt, "branch")

        result = asyncio.run(_test())
        assert not result.success
        assert "Failed to start container" in (result.error or "")

    def test_wait_ready_failure_async(self, tmp_path: Path) -> None:
        """Lines 854-859: Wait ready failure in async path."""
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()

        async def _test():
            with (
                patch.object(launcher, "_start_container_async", return_value="cid123"),
                patch("asyncio.create_subprocess_exec") as mock_proc,
                patch("asyncio.to_thread", side_effect=[False]),
            ):
                mock_p = AsyncMock()
                mock_p.communicate.return_value = (b"", b"")
                mock_proc.return_value = mock_p
                with patch.dict("os.environ", {}, clear=True):
                    return await launcher.spawn_async(0, "feat", wt, "branch")

        result = asyncio.run(_test())
        assert not result.success
        assert "ready" in (result.error or "").lower()

    def test_verify_worker_failure_async(self, tmp_path: Path) -> None:
        """Lines 862-870: Worker process verification failure in async path."""
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()

        async def _test():
            # to_thread is called for: wait_ready (True), verify (False), cleanup
            with (
                patch.object(launcher, "_start_container_async", return_value="cid123"),
                patch("asyncio.create_subprocess_exec") as mock_proc,
                patch("asyncio.to_thread", side_effect=[True, False, None]),
            ):
                mock_p = AsyncMock()
                mock_p.communicate.return_value = (b"", b"")
                mock_proc.return_value = mock_p
                with patch.dict("os.environ", {}, clear=True):
                    return await launcher.spawn_async(0, "feat", wt, "branch")

        result = asyncio.run(_test())
        assert not result.success
        assert "Worker process failed" in (result.error or "")

    def test_spawn_async_success(self, tmp_path: Path) -> None:
        """Lines 872-875: Successful async spawn."""
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()

        async def _test():
            with (
                patch.object(launcher, "_start_container_async", return_value="cid123"),
                patch("asyncio.create_subprocess_exec") as mock_proc,
                patch("asyncio.to_thread", side_effect=[True, True]),
            ):
                mock_p = AsyncMock()
                mock_p.communicate.return_value = (b"", b"")
                mock_proc.return_value = mock_p
                with patch.dict("os.environ", {}, clear=True):
                    return await launcher.spawn_async(0, "feat", wt, "branch")

        result = asyncio.run(_test())
        assert result.success
        assert result.handle is not None
        assert result.handle.status == WorkerStatus.RUNNING

    def test_spawn_async_exception(self, tmp_path: Path) -> None:
        """Lines 877-879: Generic exception in async spawn."""
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()

        async def _test():
            with patch("asyncio.create_subprocess_exec", side_effect=RuntimeError("boom")):
                with patch.dict("os.environ", {}, clear=True):
                    return await launcher.spawn_async(0, "feat", wt, "branch")

        result = asyncio.run(_test())
        assert not result.success
        assert "boom" in (result.error or "")


# ===========================================================================
# _start_container_async tests
# ===========================================================================


class TestStartContainerAsync:
    """Tests for async container start wrapper (lines 901-915)."""

    def test_async_start_success(self, tmp_path: Path) -> None:
        """Lines 901-908: Async run function returns container id."""
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()

        async def _test():
            with patch.object(launcher, "_build_container_cmd", return_value=["docker", "run"]):
                with patch("asyncio.create_subprocess_exec") as mock_proc:
                    mock_p = AsyncMock()
                    mock_p.communicate.return_value = (b"cid-abc\n", b"")
                    mock_p.returncode = 0
                    mock_proc.return_value = mock_p
                    with patch("asyncio.wait_for", return_value=(b"cid-abc\n", b"")):
                        return await launcher._start_container_async("w0", wt, {})

        result = asyncio.run(_test())
        assert result == "cid-abc"

    def test_async_start_failure(self, tmp_path: Path) -> None:
        wt = _fake_worktree(tmp_path)
        launcher = _launcher()

        async def _test():
            with patch.object(launcher, "_build_container_cmd", return_value=["docker", "run"]):
                with patch("asyncio.create_subprocess_exec") as mock_proc:
                    mock_p = AsyncMock()
                    mock_p.communicate.return_value = (b"", b"error\n")
                    mock_p.returncode = 1
                    mock_proc.return_value = mock_p
                    with patch("asyncio.wait_for", return_value=(b"", b"error\n")):
                        return await launcher._start_container_async("w0", wt, {})

        result = asyncio.run(_test())
        assert result is None


# ===========================================================================
# terminate_async tests
# ===========================================================================


class TestTerminateAsync:
    """Tests for async terminate (lines 917-944)."""

    def test_terminate_async_success(self) -> None:
        """Lines 931-938: Successful async termination."""
        launcher = _launcher()
        handle = WorkerHandle(worker_id=0, container_id="cid", status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._container_ids[0] = "cid"

        async def _test():
            with patch("asyncio.create_subprocess_exec") as mock_proc:
                mock_p = AsyncMock()
                mock_p.communicate.return_value = (b"", b"")
                mock_p.returncode = 0
                mock_proc.return_value = mock_p
                with patch("asyncio.wait_for", return_value=(b"", b"")):
                    return await launcher.terminate_async(0, force=False)

        result = asyncio.run(_test())
        assert result is True

    def test_terminate_async_force(self) -> None:
        launcher = _launcher()
        handle = WorkerHandle(worker_id=0, container_id="cid", status=WorkerStatus.RUNNING)
        launcher._workers[0] = handle
        launcher._container_ids[0] = "cid"

        async def _test():
            with patch("asyncio.create_subprocess_exec") as mock_proc:
                mock_p = AsyncMock()
                mock_p.communicate.return_value = (b"", b"")
                mock_p.returncode = 0
                mock_proc.return_value = mock_p
                with patch("asyncio.wait_for", return_value=(b"", b"")):
                    return await launcher.terminate_async(0, force=True)

        result = asyncio.run(_test())
        assert result is True

    def test_terminate_async_no_worker(self) -> None:
        launcher = _launcher()

        result = asyncio.run(launcher.terminate_async(999))
        assert result is False


# ===========================================================================
# _run_worker_entry tests
# ===========================================================================


class TestRunWorkerEntry:
    """Tests for worker entry script execution."""

    @patch("subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        launcher = _launcher()
        mock_run.return_value = MagicMock(returncode=0)
        assert launcher._run_worker_entry("cid") is True

    @patch("subprocess.run")
    def test_failure(self, mock_run: MagicMock) -> None:
        launcher = _launcher()
        mock_run.return_value = MagicMock(returncode=1)
        assert launcher._run_worker_entry("cid") is False

    @patch("subprocess.run")
    def test_exception(self, mock_run: MagicMock) -> None:
        launcher = _launcher()
        mock_run.side_effect = subprocess.SubprocessError("exec failed")
        assert launcher._run_worker_entry("cid") is False


# ===========================================================================
# Init / defaults tests
# ===========================================================================


class TestInit:
    def test_default_network(self) -> None:
        launcher = ContainerLauncher()
        assert launcher.network == "bridge"

    def test_custom_network(self) -> None:
        launcher = ContainerLauncher(network="custom-net")
        assert launcher.network == "custom-net"

    def test_container_ids_initialized(self) -> None:
        launcher = ContainerLauncher()
        assert launcher._container_ids == {}
