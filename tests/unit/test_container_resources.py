"""Unit tests for container-execution resource limits and related features.

Tests cover:
- ResourcesConfig and ZergConfig defaults for container resource limits
- ContainerLauncher resource limit parameters and docker run flags
- Orchestrator passing config limits to ContainerLauncher
- Orphan container cleanup
- Container health check timeout detection
- Container log retrieval
- Docker image build command
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.config import ResourcesConfig, ZergConfig
from zerg.constants import WorkerStatus
from zerg.launcher import ContainerLauncher
from zerg.launcher_configurator import LauncherConfigurator
from zerg.plugins import PluginRegistry

# ---------------------------------------------------------------------------
# 1. Config tests: ResourcesConfig defaults and ZergConfig.load() defaults
# ---------------------------------------------------------------------------


class TestResourcesConfigDefaults:
    """Verify ResourcesConfig has correct container resource defaults."""

    def test_container_memory_limit_default(self) -> None:
        """ResourcesConfig should default container_memory_limit to '4g'."""
        config = ResourcesConfig()
        assert config.container_memory_limit == "4g"

    def test_container_cpu_limit_default(self) -> None:
        """ResourcesConfig should default container_cpu_limit to 2.0."""
        config = ResourcesConfig()
        assert config.container_cpu_limit == 2.0

    def test_custom_memory_limit(self) -> None:
        """ResourcesConfig should accept a custom memory limit."""
        config = ResourcesConfig(container_memory_limit="8g")
        assert config.container_memory_limit == "8g"

    def test_custom_cpu_limit(self) -> None:
        """ResourcesConfig should accept a custom CPU limit."""
        config = ResourcesConfig(container_cpu_limit=4.0)
        assert config.container_cpu_limit == 4.0


class TestZergConfigLoadDefaults:
    """Verify ZergConfig.load() returns correct resource defaults."""

    def test_load_returns_default_memory_limit(self, tmp_path: Path) -> None:
        """ZergConfig.load() with missing file returns default memory limit."""
        config = ZergConfig.load(config_path=tmp_path / "nonexistent.yaml")
        assert config.resources.container_memory_limit == "4g"

    def test_load_returns_default_cpu_limit(self, tmp_path: Path) -> None:
        """ZergConfig.load() with missing file returns default cpu limit."""
        config = ZergConfig.load(config_path=tmp_path / "nonexistent.yaml")
        assert config.resources.container_cpu_limit == 2.0


# ---------------------------------------------------------------------------
# 2. ContainerLauncher resource limits
# ---------------------------------------------------------------------------


class TestContainerLauncherInit:
    """Verify ContainerLauncher accepts and stores resource limit params."""

    def test_default_memory_limit(self) -> None:
        """ContainerLauncher defaults memory_limit to '4g'."""
        launcher = ContainerLauncher()
        assert launcher.memory_limit == "4g"

    def test_default_cpu_limit(self) -> None:
        """ContainerLauncher defaults cpu_limit to 2.0."""
        launcher = ContainerLauncher()
        assert launcher.cpu_limit == 2.0

    def test_custom_memory_limit(self) -> None:
        """ContainerLauncher accepts custom memory_limit."""
        launcher = ContainerLauncher(memory_limit="16g")
        assert launcher.memory_limit == "16g"

    def test_custom_cpu_limit(self) -> None:
        """ContainerLauncher accepts custom cpu_limit."""
        launcher = ContainerLauncher(cpu_limit=8.0)
        assert launcher.cpu_limit == 8.0

    def test_custom_image_name(self) -> None:
        """ContainerLauncher accepts custom image_name."""
        launcher = ContainerLauncher(image_name="my-worker")
        assert launcher.image_name == "my-worker"

    def test_custom_network(self) -> None:
        """ContainerLauncher accepts custom network."""
        launcher = ContainerLauncher(network="my-net")
        assert launcher.network == "my-net"


class TestContainerLauncherStartContainer:
    """Verify _start_container includes --memory and --cpus flags."""

    @patch("subprocess.run")
    def test_docker_run_includes_memory_flag(self, mock_run: MagicMock) -> None:
        """_start_container must pass --memory flag to docker run."""
        mock_run.return_value = MagicMock(returncode=0, stdout="abc123container\n", stderr="")

        launcher = ContainerLauncher(memory_limit="8g", cpu_limit=4.0)
        worktree_path = Path("/tmp/fake-worktrees/feature/worker-0")

        result = launcher._start_container(
            container_name="zerg-worker-0",
            worktree_path=worktree_path,
            env={"ZERG_WORKER_ID": "0"},
        )

        assert result is not None
        cmd = mock_run.call_args[0][0]
        assert "--memory" in cmd
        mem_idx = cmd.index("--memory")
        assert cmd[mem_idx + 1] == "8g"

    @patch("subprocess.run")
    def test_docker_run_includes_cpus_flag(self, mock_run: MagicMock) -> None:
        """_start_container must pass --cpus flag to docker run."""
        mock_run.return_value = MagicMock(returncode=0, stdout="abc123container\n", stderr="")

        launcher = ContainerLauncher(memory_limit="4g", cpu_limit=3.5)
        worktree_path = Path("/tmp/fake-worktrees/feature/worker-0")

        launcher._start_container(
            container_name="zerg-worker-0",
            worktree_path=worktree_path,
            env={"ZERG_WORKER_ID": "0"},
        )

        cmd = mock_run.call_args[0][0]
        assert "--cpus" in cmd
        cpus_idx = cmd.index("--cpus")
        assert cmd[cpus_idx + 1] == "3.5"

    @patch("subprocess.run")
    def test_docker_run_default_limits(self, mock_run: MagicMock) -> None:
        """_start_container with default limits passes '4g' and '2.0'."""
        mock_run.return_value = MagicMock(returncode=0, stdout="containerid\n", stderr="")

        launcher = ContainerLauncher()
        worktree_path = Path("/tmp/fake-worktrees/feature/worker-0")

        launcher._start_container(
            container_name="zerg-worker-0",
            worktree_path=worktree_path,
            env={},
        )

        cmd = mock_run.call_args[0][0]
        mem_idx = cmd.index("--memory")
        assert cmd[mem_idx + 1] == "4g"
        cpus_idx = cmd.index("--cpus")
        assert cmd[cpus_idx + 1] == "2.0"


# ---------------------------------------------------------------------------
# 3. Orchestrator passes limits from config to ContainerLauncher
# ---------------------------------------------------------------------------


class TestOrchestratorPassesLimits:
    """Verify Orchestrator._create_launcher passes config resource limits."""

    def test_create_launcher_container_mode(self) -> None:
        """_create_launcher in container mode passes memory and cpu limits."""
        from zerg.orchestrator import Orchestrator

        # Build a config with custom resource limits
        config = ZergConfig()
        config.resources.container_memory_limit = "16g"
        config.resources.container_cpu_limit = 8.0

        # Create a minimal orchestrator without running __init__
        orch = Orchestrator.__new__(Orchestrator)
        orch.config = config
        orch.repo_path = Path(".")
        orch._plugin_registry = PluginRegistry()
        orch._launcher_config = LauncherConfigurator(config, orch.repo_path, orch._plugin_registry)

        # Patch ContainerLauncher at the module level to capture constructor args
        with patch("zerg.orchestrator.ContainerLauncher") as mock_cl_cls:
            mock_launcher = MagicMock()
            mock_cl_cls.return_value = mock_launcher

            orch._create_launcher(mode="container")

        mock_cl_cls.assert_called_once()
        call_kwargs = mock_cl_cls.call_args[1]
        assert call_kwargs["memory_limit"] == "16g"
        assert call_kwargs["cpu_limit"] == 8.0

    def test_create_launcher_subprocess_mode(self) -> None:
        """_create_launcher in subprocess mode returns SubprocessLauncher."""
        from zerg.orchestrator import Orchestrator

        orch = Orchestrator.__new__(Orchestrator)
        orch.config = ZergConfig()
        orch.repo_path = Path(".")

        with patch("zerg.orchestrator.SubprocessLauncher") as mock_sp_cls:
            mock_launcher = MagicMock()
            mock_sp_cls.return_value = mock_launcher

            result = orch._create_launcher(mode="subprocess")

        mock_sp_cls.assert_called_once()
        assert result is mock_launcher


# ---------------------------------------------------------------------------
# 4. Orphan cleanup
# ---------------------------------------------------------------------------


class TestCleanupOrphanContainers:
    """Verify _cleanup_orphan_containers behaviour."""

    def _make_orchestrator(self):
        """Create a minimal Orchestrator for cleanup tests."""
        from zerg.orchestrator import Orchestrator

        orch = Orchestrator.__new__(Orchestrator)
        orch.config = ZergConfig()
        orch.launcher = MagicMock(spec=ContainerLauncher)
        orch._plugin_registry = PluginRegistry()
        orch._launcher_config = LauncherConfigurator(orch.config, Path("."), orch._plugin_registry)
        return orch

    @patch("zerg.launcher_configurator.sp.run")
    def test_cleanup_removes_found_containers(self, mock_run: MagicMock) -> None:
        """Should run docker rm -f for each container ID found."""
        # First call: docker ps returns two container IDs
        ps_result = MagicMock(returncode=0, stdout="aaa111\nbbb222")
        rm_result = MagicMock(returncode=0)
        mock_run.side_effect = [ps_result, rm_result, rm_result]

        orch = self._make_orchestrator()
        orch._cleanup_orphan_containers()

        assert mock_run.call_count == 3
        # Verify rm calls
        for rm_call in mock_run.call_args_list[1:]:
            cmd = rm_call[0][0]
            assert cmd[0] == "docker"
            assert cmd[1] == "rm"
            assert cmd[2] == "-f"

    @patch("zerg.launcher_configurator.sp.run")
    def test_cleanup_no_containers_found(self, mock_run: MagicMock) -> None:
        """Should handle empty ps output gracefully."""
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        orch = self._make_orchestrator()
        orch._cleanup_orphan_containers()

        # Only the ps call, no rm calls
        assert mock_run.call_count == 1

    @patch("zerg.launcher_configurator.sp.run")
    def test_cleanup_handles_file_not_found(self, mock_run: MagicMock) -> None:
        """Should handle FileNotFoundError (no Docker installed) gracefully."""
        mock_run.side_effect = FileNotFoundError("docker not found")

        orch = self._make_orchestrator()

        # Should not raise
        orch._cleanup_orphan_containers()

    @patch("zerg.launcher_configurator.sp.run")
    def test_cleanup_handles_timeout(self, mock_run: MagicMock) -> None:
        """Should handle TimeoutExpired gracefully."""
        mock_run.side_effect = subprocess.TimeoutExpired("docker", 10)

        orch = self._make_orchestrator()

        # Should not raise
        orch._cleanup_orphan_containers()

    @patch("zerg.launcher_configurator.sp.run")
    def test_cleanup_skips_on_nonzero_return(self, mock_run: MagicMock) -> None:
        """Should skip rm when docker ps returns non-zero."""
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        orch = self._make_orchestrator()
        orch._cleanup_orphan_containers()

        # Only the ps call, no rm
        assert mock_run.call_count == 1


# ---------------------------------------------------------------------------
# 5. Health check
# ---------------------------------------------------------------------------


class TestCheckContainerHealth:
    """Verify _check_container_health marks timed-out workers as CRASHED."""

    def _make_orchestrator(self):
        """Create a minimal Orchestrator for health check tests."""
        from zerg.orchestrator import Orchestrator

        orch = Orchestrator.__new__(Orchestrator)
        orch.config = ZergConfig()
        orch.launcher = MagicMock(spec=ContainerLauncher)
        orch.state = MagicMock()
        orch._workers = {}
        orch._plugin_registry = PluginRegistry()
        orch._launcher_config = LauncherConfigurator(orch.config, Path("."), orch._plugin_registry)
        return orch

    def test_marks_timed_out_worker_as_crashed(self) -> None:
        """Worker exceeding timeout should be marked CRASHED."""
        from zerg.types import WorkerState

        orch = self._make_orchestrator()
        orch.config.workers.timeout_minutes = 30

        worker = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            started_at=datetime.now() - timedelta(minutes=60),
        )
        orch._workers[0] = worker

        orch._check_container_health()

        assert worker.status == WorkerStatus.CRASHED
        orch.launcher.terminate.assert_called_once_with(0)
        orch.state.set_worker_state.assert_called_once_with(worker)

    def test_does_not_crash_worker_within_timeout(self) -> None:
        """Worker within timeout should not be marked CRASHED."""
        from zerg.types import WorkerState

        orch = self._make_orchestrator()
        orch.config.workers.timeout_minutes = 30

        worker = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            started_at=datetime.now() - timedelta(minutes=10),
        )
        orch._workers[0] = worker

        orch._check_container_health()

        assert worker.status == WorkerStatus.RUNNING
        orch.launcher.terminate.assert_not_called()

    def test_skips_non_running_workers(self) -> None:
        """Workers not in RUNNING status should be skipped."""
        from zerg.types import WorkerState

        orch = self._make_orchestrator()
        orch.config.workers.timeout_minutes = 1

        worker = WorkerState(
            worker_id=0,
            status=WorkerStatus.STOPPED,
            started_at=datetime.now() - timedelta(hours=2),
        )
        orch._workers[0] = worker

        orch._check_container_health()

        assert worker.status == WorkerStatus.STOPPED
        orch.launcher.terminate.assert_not_called()

    def test_skips_when_not_container_launcher(self) -> None:
        """Should do nothing when launcher is not ContainerLauncher."""
        from zerg.launcher import SubprocessLauncher
        from zerg.types import WorkerState

        orch = self._make_orchestrator()
        orch.launcher = MagicMock(spec=SubprocessLauncher)
        orch.config.workers.timeout_minutes = 1

        worker = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            started_at=datetime.now() - timedelta(hours=2),
        )
        orch._workers[0] = worker

        orch._check_container_health()

        # Status unchanged because launcher is not ContainerLauncher
        assert worker.status == WorkerStatus.RUNNING

    def test_skips_worker_without_started_at(self) -> None:
        """Workers without started_at should be skipped."""
        from zerg.types import WorkerState

        orch = self._make_orchestrator()
        orch.config.workers.timeout_minutes = 1

        worker = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            started_at=None,
        )
        orch._workers[0] = worker

        orch._check_container_health()

        assert worker.status == WorkerStatus.RUNNING
        orch.launcher.terminate.assert_not_called()


# ---------------------------------------------------------------------------
# 6. Container logs
# ---------------------------------------------------------------------------


class TestGetContainerLogs:
    """Verify _get_container_logs fetches docker logs correctly."""

    @patch("zerg.commands.logs.subprocess.run")
    def test_returns_stdout_on_success(self, mock_run: MagicMock) -> None:
        """Should return stdout when docker logs succeeds."""
        mock_run.return_value = MagicMock(returncode=0, stdout="line1\nline2\n", stderr="")

        from zerg.commands.logs import _get_container_logs

        result = _get_container_logs(3)

        assert result == "line1\nline2\n"
        cmd = mock_run.call_args[0][0]
        assert cmd == ["docker", "logs", "zerg-worker-3"]

    @patch("zerg.commands.logs.subprocess.run")
    def test_returns_none_on_nonzero_exit(self, mock_run: MagicMock) -> None:
        """Should return None when docker logs fails."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="no such container")

        from zerg.commands.logs import _get_container_logs

        result = _get_container_logs(5)

        assert result is None

    @patch("zerg.commands.logs.subprocess.run")
    def test_returns_none_on_timeout(self, mock_run: MagicMock) -> None:
        """Should return None when docker logs times out."""
        mock_run.side_effect = subprocess.TimeoutExpired("docker logs", 10)

        from zerg.commands.logs import _get_container_logs

        result = _get_container_logs(1)

        assert result is None

    @patch("zerg.commands.logs.subprocess.run")
    def test_returns_none_when_docker_unavailable(self, mock_run: MagicMock) -> None:
        """Should return None when Docker is not installed (FileNotFoundError)."""
        mock_run.side_effect = FileNotFoundError("docker not found")

        from zerg.commands.logs import _get_container_logs

        result = _get_container_logs(0)

        assert result is None

    @patch("zerg.commands.logs.subprocess.run")
    def test_passes_correct_timeout(self, mock_run: MagicMock) -> None:
        """Should pass timeout=10 to subprocess.run."""
        mock_run.return_value = MagicMock(returncode=0, stdout="logs")

        from zerg.commands.logs import _get_container_logs

        _get_container_logs(2)

        kwargs = mock_run.call_args[1]
        assert kwargs["timeout"] == 10

    @patch("zerg.commands.logs.subprocess.run")
    def test_container_name_format(self, mock_run: MagicMock) -> None:
        """Should use 'zerg-worker-{worker_id}' as container name."""
        mock_run.return_value = MagicMock(returncode=0, stdout="output")

        from zerg.commands.logs import _get_container_logs

        _get_container_logs(42)

        cmd = mock_run.call_args[0][0]
        assert cmd[2] == "zerg-worker-42"


# ---------------------------------------------------------------------------
# 7. Build --docker
# ---------------------------------------------------------------------------


class TestBuildDockerImage:
    """Verify _build_docker_image runs docker build correctly."""

    @patch("zerg.commands.build.subprocess.run")
    @patch("zerg.commands.build.Path")
    def test_runs_docker_build(self, mock_path_cls: MagicMock, mock_run: MagicMock) -> None:
        """Should run docker build with correct arguments."""
        # Make Dockerfile exist
        mock_dockerfile = MagicMock()
        mock_dockerfile.exists.return_value = True
        mock_dockerfile.__str__ = lambda self: ".devcontainer/Dockerfile"
        mock_path_cls.return_value = mock_dockerfile

        # First call: docker build (succeeds)
        # Second call: docker image inspect (for size display)
        mock_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=0, stdout="123456789\n"),
        ]

        from zerg.commands.build import _build_docker_image

        _build_docker_image()

        build_call = mock_run.call_args_list[0]
        cmd = build_call[0][0]
        assert "docker" in cmd
        assert "build" in cmd
        assert "-t" in cmd
        assert "zerg-worker" in cmd

    @patch("zerg.commands.build.Path")
    def test_handles_missing_dockerfile(self, mock_path_cls: MagicMock) -> None:
        """Should raise SystemExit when Dockerfile is missing."""
        mock_dockerfile = MagicMock()
        mock_dockerfile.exists.return_value = False
        mock_path_cls.return_value = mock_dockerfile

        from zerg.commands.build import _build_docker_image

        with pytest.raises(SystemExit):
            _build_docker_image()

    @patch("zerg.commands.build.subprocess.run")
    @patch("zerg.commands.build.Path")
    def test_handles_docker_not_found(self, mock_path_cls: MagicMock, mock_run: MagicMock) -> None:
        """Should raise SystemExit when Docker is not installed."""
        mock_dockerfile = MagicMock()
        mock_dockerfile.exists.return_value = True
        mock_dockerfile.__str__ = lambda self: ".devcontainer/Dockerfile"
        mock_path_cls.return_value = mock_dockerfile

        mock_run.side_effect = FileNotFoundError("docker not found")

        from zerg.commands.build import _build_docker_image

        with pytest.raises(SystemExit):
            _build_docker_image()

    @patch("zerg.commands.build.subprocess.run")
    @patch("zerg.commands.build.Path")
    def test_handles_build_failure(self, mock_path_cls: MagicMock, mock_run: MagicMock) -> None:
        """Should raise SystemExit when docker build fails."""
        mock_dockerfile = MagicMock()
        mock_dockerfile.exists.return_value = True
        mock_dockerfile.__str__ = lambda self: ".devcontainer/Dockerfile"
        mock_path_cls.return_value = mock_dockerfile

        mock_run.return_value = MagicMock(returncode=1)

        from zerg.commands.build import _build_docker_image

        with pytest.raises(SystemExit):
            _build_docker_image()

    @patch("zerg.commands.build.subprocess.run")
    @patch("zerg.commands.build.Path")
    def test_handles_build_timeout(self, mock_path_cls: MagicMock, mock_run: MagicMock) -> None:
        """Should raise SystemExit when docker build times out."""
        mock_dockerfile = MagicMock()
        mock_dockerfile.exists.return_value = True
        mock_dockerfile.__str__ = lambda self: ".devcontainer/Dockerfile"
        mock_path_cls.return_value = mock_dockerfile

        mock_run.side_effect = subprocess.TimeoutExpired("docker build", 600)

        from zerg.commands.build import _build_docker_image

        with pytest.raises(SystemExit):
            _build_docker_image()
