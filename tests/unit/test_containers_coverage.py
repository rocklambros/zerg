"""Tests for async methods in zerg/containers.py (COV-007).

Covers uncovered lines 458-478, 496-521, 529-540, 555-570, 581-598, 609-625, 649-659.
"""

from unittest.mock import AsyncMock, MagicMock, patch

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


@pytest.fixture
def manager():
    """Create a ContainerManager with mocked _check_docker."""
    with patch.object(ContainerManager, "_check_docker"):
        mgr = ContainerManager()
    return mgr


@pytest.fixture
def manager_with_worker(manager):
    """Manager with a single tracked worker container."""
    manager._containers[0] = ContainerInfo(
        container_id="abc123",
        name="zerg-worker-0",
        status="running",
        worker_id=0,
        port=49152,
    )
    return manager


def _make_mock_process(returncode=0, stdout=b"", stderr=b""):
    """Create a mock asyncio subprocess process."""
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = returncode
    proc.kill = MagicMock()
    proc.wait = AsyncMock()
    return proc


# ---------------------------------------------------------------------------
# Lines 458-478: _run_docker_async
# ---------------------------------------------------------------------------
class TestRunDockerAsync:
    """Tests for _run_docker_async (lines 458-478)."""

    @pytest.mark.asyncio
    async def test_run_docker_async_success(self, manager) -> None:
        """Test successful async docker command returns (returncode, stdout, stderr)."""
        proc = _make_mock_process(returncode=0, stdout=b"container_id\n", stderr=b"")

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            returncode, stdout, stderr = await manager._run_docker_async("ps", "-a")

        assert returncode == 0
        assert stdout == "container_id\n"
        assert stderr == ""

    @pytest.mark.asyncio
    async def test_run_docker_async_nonzero_return(self, manager) -> None:
        """Test async docker command with non-zero returncode."""
        proc = _make_mock_process(returncode=1, stdout=b"", stderr=b"error msg")

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            returncode, stdout, stderr = await manager._run_docker_async("inspect", "bad")

        assert returncode == 1
        assert stderr == "error msg"

    @pytest.mark.asyncio
    async def test_run_docker_async_none_returncode(self, manager) -> None:
        """Test async docker command with None returncode falls back to 0."""
        proc = _make_mock_process(returncode=None, stdout=b"ok", stderr=b"")

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            returncode, stdout, stderr = await manager._run_docker_async("info")

        assert returncode == 0

    @pytest.mark.asyncio
    async def test_run_docker_async_timeout(self, manager) -> None:
        """Test async docker command timeout kills process and returns error."""
        proc = AsyncMock()
        proc.communicate = AsyncMock(side_effect=TimeoutError())
        proc.kill = MagicMock()
        proc.wait = AsyncMock()
        proc.returncode = None

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            returncode, stdout, stderr = await manager._run_docker_async("pull", "large-image", timeout=5)

        assert returncode == 1
        assert stdout == ""
        assert "timeout after 5s" in stderr
        proc.kill.assert_called_once()
        proc.wait.assert_awaited_once()


# ---------------------------------------------------------------------------
# Lines 496-521: _run_compose_async
# ---------------------------------------------------------------------------
class TestRunComposeAsync:
    """Tests for _run_compose_async (lines 496-521)."""

    @pytest.mark.asyncio
    async def test_run_compose_async_success(self, manager) -> None:
        """Test successful async compose command."""
        proc = _make_mock_process(returncode=0, stdout=b"done\n", stderr=b"")

        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            returncode, stdout, stderr = await manager._run_compose_async("up", "-d")

        assert returncode == 0
        assert stdout == "done\n"
        # Verify compose-style command structure
        call_args = mock_exec.call_args[0]
        assert call_args[0] == "docker"
        assert call_args[1] == "compose"
        assert "-f" in call_args

    @pytest.mark.asyncio
    async def test_run_compose_async_with_env(self, manager) -> None:
        """Test async compose command passes env vars."""
        proc = _make_mock_process(returncode=0, stdout=b"", stderr=b"")

        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            await manager._run_compose_async("up", "-d", env={"ZERG_WORKER_ID": "1"})

        call_kwargs = mock_exec.call_args[1]
        assert "ZERG_WORKER_ID" in call_kwargs["env"]
        assert call_kwargs["env"]["ZERG_WORKER_ID"] == "1"

    @pytest.mark.asyncio
    async def test_run_compose_async_without_env(self, manager) -> None:
        """Test async compose command without extra env uses os.environ."""
        proc = _make_mock_process(returncode=0, stdout=b"", stderr=b"")

        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            await manager._run_compose_async("build")

        call_kwargs = mock_exec.call_args[1]
        # Should still have env from os.environ
        assert "env" in call_kwargs

    @pytest.mark.asyncio
    async def test_run_compose_async_nonzero_return(self, manager) -> None:
        """Test async compose command with failure returncode."""
        proc = _make_mock_process(returncode=2, stdout=b"", stderr=b"build failed")

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            returncode, stdout, stderr = await manager._run_compose_async("build")

        assert returncode == 2
        assert stderr == "build failed"

    @pytest.mark.asyncio
    async def test_run_compose_async_none_returncode(self, manager) -> None:
        """Test async compose command with None returncode defaults to 0."""
        proc = _make_mock_process(returncode=None, stdout=b"ok", stderr=b"")

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            returncode, _, _ = await manager._run_compose_async("ps")

        assert returncode == 0

    @pytest.mark.asyncio
    async def test_run_compose_async_timeout(self, manager) -> None:
        """Test async compose command timeout kills process."""
        proc = AsyncMock()
        proc.communicate = AsyncMock(side_effect=TimeoutError())
        proc.kill = MagicMock()
        proc.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            returncode, stdout, stderr = await manager._run_compose_async("build", timeout=10)

        assert returncode == 1
        assert "timeout after 10s" in stderr
        proc.kill.assert_called_once()


# ---------------------------------------------------------------------------
# Lines 529-540: build_async
# ---------------------------------------------------------------------------
class TestBuildAsync:
    """Tests for build_async (lines 529-540)."""

    @pytest.mark.asyncio
    async def test_build_async_success(self, manager) -> None:
        """Test async build succeeds."""
        with patch.object(manager, "_run_compose_async", new_callable=AsyncMock) as mock_compose:
            mock_compose.return_value = (0, "", "")
            await manager.build_async()

        mock_compose.assert_awaited_once()
        call_args = mock_compose.call_args
        assert "build" in call_args[0]
        assert call_args[1]["timeout"] == 300

    @pytest.mark.asyncio
    async def test_build_async_no_cache(self, manager) -> None:
        """Test async build with no_cache appends --no-cache arg."""
        with patch.object(manager, "_run_compose_async", new_callable=AsyncMock) as mock_compose:
            mock_compose.return_value = (0, "", "")
            await manager.build_async(no_cache=True)

        call_args = mock_compose.call_args[0]
        assert "build" in call_args
        assert "--no-cache" in call_args

    @pytest.mark.asyncio
    async def test_build_async_failure_raises_container_error(self, manager) -> None:
        """Test async build raises ContainerError on non-zero exit."""
        with patch.object(manager, "_run_compose_async", new_callable=AsyncMock) as mock_compose:
            mock_compose.return_value = (1, "", "build error details")

            with pytest.raises(ContainerError) as exc_info:
                await manager.build_async()

        assert "Compose build failed" in str(exc_info.value)
        assert exc_info.value.details["exit_code"] == 1


# ---------------------------------------------------------------------------
# Lines 555-570: stop_worker_async
# ---------------------------------------------------------------------------
class TestStopWorkerAsync:
    """Tests for stop_worker_async (lines 555-570)."""

    @pytest.mark.asyncio
    async def test_stop_worker_async_graceful(self, manager_with_worker) -> None:
        """Test async graceful stop calls docker stop then rm."""
        calls = []

        async def track_calls(*args, **kwargs):
            calls.append(args)
            return (0, "", "")

        with patch.object(manager_with_worker, "_run_docker_async", side_effect=track_calls):
            await manager_with_worker.stop_worker_async(0, timeout=30)

        assert 0 not in manager_with_worker._containers
        # First call: stop, second call: rm
        assert "stop" in calls[0]
        assert "-t" in calls[0]
        assert "30" in calls[0]
        assert "rm" in calls[1]

    @pytest.mark.asyncio
    async def test_stop_worker_async_force(self, manager_with_worker) -> None:
        """Test async force stop calls docker kill then rm."""
        calls = []

        async def track_calls(*args, **kwargs):
            calls.append(args)
            return (0, "", "")

        with patch.object(manager_with_worker, "_run_docker_async", side_effect=track_calls):
            await manager_with_worker.stop_worker_async(0, force=True)

        assert 0 not in manager_with_worker._containers
        assert "kill" in calls[0]
        assert "rm" in calls[1]

    @pytest.mark.asyncio
    async def test_stop_worker_async_not_found(self, manager) -> None:
        """Test async stop for non-existent worker returns early."""
        with patch.object(manager, "_run_docker_async", new_callable=AsyncMock) as mock_docker:
            await manager.stop_worker_async(99)

        # Should not call docker at all
        mock_docker.assert_not_awaited()


# ---------------------------------------------------------------------------
# Lines 581-598: stop_all_async
# ---------------------------------------------------------------------------
class TestStopAllAsync:
    """Tests for stop_all_async (lines 581-598)."""

    @pytest.mark.asyncio
    async def test_stop_all_async_with_tracked(self, manager) -> None:
        """Test async stop all stops tracked workers and orphans."""
        manager._containers = {
            0: ContainerInfo("a", "zerg-worker-0", "running", 0),
            1: ContainerInfo("b", "zerg-worker-1", "running", 1),
        }

        async def mock_run_docker(*args, **kwargs):
            # For ps -q -f name=zerg-worker- return orphan ID
            if "ps" in args and "-f" in args:
                return (0, "orphan123\n", "")
            return (0, "", "")

        with (
            patch.object(manager, "stop_worker_async", new_callable=AsyncMock) as mock_stop,
            patch.object(manager, "_run_docker_async", side_effect=mock_run_docker),
        ):
            count = await manager.stop_all_async()

        # 2 tracked + 1 orphan
        assert mock_stop.await_count == 2
        assert count >= 3

    @pytest.mark.asyncio
    async def test_stop_all_async_no_workers(self, manager) -> None:
        """Test async stop all with no tracked workers still checks orphans."""

        async def mock_run_docker(*args, **kwargs):
            return (0, "", "")

        with patch.object(manager, "_run_docker_async", side_effect=mock_run_docker):
            count = await manager.stop_all_async()

        assert count == 0

    @pytest.mark.asyncio
    async def test_stop_all_async_force(self, manager) -> None:
        """Test async force stop all passes force flag."""
        manager._containers = {
            0: ContainerInfo("a", "zerg-worker-0", "running", 0),
        }

        async def mock_run_docker(*args, **kwargs):
            return (0, "", "")

        with (
            patch.object(manager, "stop_worker_async", new_callable=AsyncMock) as mock_stop,
            patch.object(manager, "_run_docker_async", side_effect=mock_run_docker),
        ):
            await manager.stop_all_async(force=True)

        mock_stop.assert_awaited_once_with(0, force=True)

    @pytest.mark.asyncio
    async def test_stop_all_async_with_orphan_containers(self, manager) -> None:
        """Test async stop all cleans up orphaned containers."""

        async def mock_run_docker(*args, **kwargs):
            if "ps" in args:
                return (0, "orphan1\norphan2\n", "")
            return (0, "", "")

        rm_calls = []
        original_mock = mock_run_docker

        async def tracking_mock(*args, **kwargs):
            if "rm" in args:
                rm_calls.append(args)
            return await original_mock(*args, **kwargs)

        with patch.object(manager, "_run_docker_async", side_effect=tracking_mock):
            count = await manager.stop_all_async()

        assert count == 2  # 2 orphans
        assert len(rm_calls) == 2


# ---------------------------------------------------------------------------
# Lines 609-625: get_status_async
# ---------------------------------------------------------------------------
class TestGetStatusAsync:
    """Tests for get_status_async (lines 609-625)."""

    @pytest.mark.asyncio
    async def test_get_status_async_running(self, manager_with_worker) -> None:
        """Test async status returns RUNNING for running container."""
        with patch.object(
            manager_with_worker,
            "_run_docker_async",
            new_callable=AsyncMock,
            return_value=(0, "running\n", ""),
        ):
            status = await manager_with_worker.get_status_async(0)

        assert status == WorkerStatus.RUNNING

    @pytest.mark.asyncio
    async def test_get_status_async_paused(self, manager_with_worker) -> None:
        """Test async status returns CHECKPOINTING for paused container."""
        with patch.object(
            manager_with_worker,
            "_run_docker_async",
            new_callable=AsyncMock,
            return_value=(0, "paused\n", ""),
        ):
            status = await manager_with_worker.get_status_async(0)

        assert status == WorkerStatus.CHECKPOINTING

    @pytest.mark.asyncio
    async def test_get_status_async_exited(self, manager_with_worker) -> None:
        """Test async status returns STOPPED for exited container."""
        with patch.object(
            manager_with_worker,
            "_run_docker_async",
            new_callable=AsyncMock,
            return_value=(0, "exited\n", ""),
        ):
            status = await manager_with_worker.get_status_async(0)

        assert status == WorkerStatus.STOPPED

    @pytest.mark.asyncio
    async def test_get_status_async_dead(self, manager_with_worker) -> None:
        """Test async status returns CRASHED for dead container."""
        with patch.object(
            manager_with_worker,
            "_run_docker_async",
            new_callable=AsyncMock,
            return_value=(0, "dead\n", ""),
        ):
            status = await manager_with_worker.get_status_async(0)

        assert status == WorkerStatus.CRASHED

    @pytest.mark.asyncio
    async def test_get_status_async_unknown_defaults_stopped(self, manager_with_worker) -> None:
        """Test async status returns STOPPED for unknown docker status."""
        with patch.object(
            manager_with_worker,
            "_run_docker_async",
            new_callable=AsyncMock,
            return_value=(0, "restarting\n", ""),
        ):
            status = await manager_with_worker.get_status_async(0)

        assert status == WorkerStatus.STOPPED

    @pytest.mark.asyncio
    async def test_get_status_async_not_tracked(self, manager) -> None:
        """Test async status returns STOPPED for untracked worker."""
        status = await manager.get_status_async(99)
        assert status == WorkerStatus.STOPPED


# ---------------------------------------------------------------------------
# Lines 649-659: exec_in_worker_async
# ---------------------------------------------------------------------------
class TestExecInWorkerAsync:
    """Tests for exec_in_worker_async (lines 649-659)."""

    @pytest.mark.asyncio
    async def test_exec_async_allowed_command(self, manager_with_worker) -> None:
        """Test async exec with allowed command succeeds."""
        with patch.object(
            manager_with_worker,
            "_run_docker_async",
            new_callable=AsyncMock,
            return_value=(0, "test output\n", ""),
        ):
            exit_code, stdout, stderr = await manager_with_worker.exec_in_worker_async(0, "pytest tests/")

        assert exit_code == 0
        assert stdout == "test output\n"

    @pytest.mark.asyncio
    async def test_exec_async_blocked_command(self, manager_with_worker) -> None:
        """Test async exec blocks dangerous commands."""
        exit_code, stdout, stderr = await manager_with_worker.exec_in_worker_async(0, "rm -rf /; echo pwned")

        assert exit_code == -1
        assert "validation failed" in stderr.lower()

    @pytest.mark.asyncio
    async def test_exec_async_worker_not_found(self, manager) -> None:
        """Test async exec on non-existent worker returns error."""
        exit_code, stdout, stderr = await manager.exec_in_worker_async(99, "pytest tests/")

        assert exit_code == -1
        assert "not found" in stderr.lower()

    @pytest.mark.asyncio
    async def test_exec_async_validation_disabled(self, manager_with_worker) -> None:
        """Test async exec with validation disabled allows any command."""
        with patch.object(
            manager_with_worker,
            "_run_docker_async",
            new_callable=AsyncMock,
            return_value=(0, "output", ""),
        ):
            exit_code, stdout, stderr = await manager_with_worker.exec_in_worker_async(
                0, "custom_forbidden_cmd", validate=False
            )

        assert exit_code == 0
        assert stdout == "output"

    @pytest.mark.asyncio
    async def test_exec_async_passes_timeout(self, manager_with_worker) -> None:
        """Test async exec passes timeout to _run_docker_async."""
        with patch.object(
            manager_with_worker,
            "_run_docker_async",
            new_callable=AsyncMock,
            return_value=(0, "", ""),
        ) as mock_docker:
            await manager_with_worker.exec_in_worker_async(0, "pytest tests/", timeout=120)

        mock_docker.assert_awaited_once_with(
            "exec",
            "abc123",
            "sh",
            "-c",
            "pytest tests/",
            timeout=120,
        )

    @pytest.mark.asyncio
    async def test_exec_async_metacharacter_blocked(self, manager_with_worker) -> None:
        """Test async exec blocks shell metacharacters."""
        exit_code, stdout, stderr = await manager_with_worker.exec_in_worker_async(0, "echo `whoami`")

        assert exit_code == -1
        assert "metacharacters" in stderr.lower()
