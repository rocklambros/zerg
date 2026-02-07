"""Unit tests for container-execution resource limits — thinned Phase 4/5."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.config import ResourcesConfig, ZergConfig
from zerg.constants import WorkerStatus
from zerg.launcher_configurator import LauncherConfigurator
from zerg.launchers import ContainerLauncher
from zerg.plugins import PluginRegistry

pytestmark = pytest.mark.docker


class TestResourcesConfigDefaults:
    def test_defaults_and_custom(self) -> None:
        default = ResourcesConfig()
        assert default.container_memory_limit == "4g"
        assert default.container_cpu_limit == 2.0
        custom = ResourcesConfig(container_memory_limit="8g", container_cpu_limit=4.0)
        assert custom.container_memory_limit == "8g"


class TestContainerLauncherInit:
    def test_defaults(self) -> None:
        launcher = ContainerLauncher()
        assert launcher.memory_limit == "4g"
        assert launcher.cpu_limit == 2.0

    def test_custom_limits(self) -> None:
        launcher = ContainerLauncher(memory_limit="16g", cpu_limit=8.0, image_name="my-worker")
        assert launcher.memory_limit == "16g"
        assert launcher.image_name == "my-worker"


class TestContainerLauncherStartContainer:
    @patch("subprocess.run")
    def test_docker_run_includes_resource_flags(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="containerid\n", stderr="")
        launcher = ContainerLauncher(memory_limit="8g", cpu_limit=3.5)
        launcher._start_container(
            container_name="zerg-worker-0",
            worktree_path=Path("/tmp/fake-worktrees/feature/worker-0"),
            env={"ZERG_WORKER_ID": "0"},
        )
        cmd = mock_run.call_args[0][0]
        mem_idx = cmd.index("--memory")
        assert cmd[mem_idx + 1] == "8g"
        cpus_idx = cmd.index("--cpus")
        assert cmd[cpus_idx + 1] == "3.5"


class TestOrchestratorPassesLimits:
    def test_create_launcher_container_mode(self) -> None:
        from zerg.orchestrator import Orchestrator

        config = ZergConfig()
        config.resources.container_memory_limit = "16g"
        config.resources.container_cpu_limit = 8.0
        orch = Orchestrator.__new__(Orchestrator)
        orch.config = config
        orch.repo_path = Path(".")
        orch._plugin_registry = PluginRegistry()
        orch._launcher_config = LauncherConfigurator(config, orch.repo_path, orch._plugin_registry)
        with patch("zerg.orchestrator.ContainerLauncher") as mock_cl_cls:
            mock_cl_cls.return_value = MagicMock()
            orch._create_launcher(mode="container")
        call_kwargs = mock_cl_cls.call_args[1]
        assert call_kwargs["memory_limit"] == "16g"
        assert call_kwargs["cpu_limit"] == 8.0


class TestCleanupOrphanContainers:
    def _make_orchestrator(self):
        from zerg.orchestrator import Orchestrator

        orch = Orchestrator.__new__(Orchestrator)
        orch.config = ZergConfig()
        orch.launcher = MagicMock(spec=ContainerLauncher)
        orch._plugin_registry = PluginRegistry()
        orch._launcher_config = LauncherConfigurator(orch.config, Path("."), orch._plugin_registry)
        return orch

    @patch("zerg.launcher_configurator.sp.run")
    def test_cleanup_removes_found_containers(self, mock_run: MagicMock) -> None:
        ps_result = MagicMock(returncode=0, stdout="aaa111\nbbb222")
        rm_result = MagicMock(returncode=0)
        mock_run.side_effect = [ps_result, rm_result, rm_result]
        self._make_orchestrator()._cleanup_orphan_containers()
        assert mock_run.call_count == 3

    @patch("zerg.launcher_configurator.sp.run")
    def test_cleanup_no_containers_found(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        self._make_orchestrator()._cleanup_orphan_containers()
        assert mock_run.call_count == 1


class TestCheckContainerHealth:
    def _make_orchestrator(self):
        from zerg.orchestrator import Orchestrator
        from zerg.worker_registry import WorkerRegistry

        orch = Orchestrator.__new__(Orchestrator)
        orch.config = ZergConfig()
        orch.launcher = MagicMock(spec=ContainerLauncher)
        orch.state = MagicMock()
        orch.registry = WorkerRegistry()
        orch._plugin_registry = PluginRegistry()
        orch._launcher_config = LauncherConfigurator(orch.config, Path("."), orch._plugin_registry)
        return orch

    def test_marks_timed_out_worker_as_crashed(self) -> None:
        from zerg.types import WorkerState

        orch = self._make_orchestrator()
        orch.config.workers.timeout_minutes = 30
        worker = WorkerState(
            worker_id=0, status=WorkerStatus.RUNNING, started_at=datetime.now() - timedelta(minutes=60)
        )
        orch.registry.register(0, worker)
        orch._check_container_health()
        assert worker.status == WorkerStatus.CRASHED

    def test_does_not_crash_worker_within_timeout(self) -> None:
        from zerg.types import WorkerState

        orch = self._make_orchestrator()
        orch.config.workers.timeout_minutes = 30
        worker = WorkerState(
            worker_id=0, status=WorkerStatus.RUNNING, started_at=datetime.now() - timedelta(minutes=10)
        )
        orch.registry.register(0, worker)
        orch._check_container_health()
        assert worker.status == WorkerStatus.RUNNING


class TestGetContainerLogs:
    @patch("zerg.commands.logs.subprocess.run")
    def test_returns_stdout_on_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="line1\nline2\n", stderr="")
        from zerg.commands.logs import _get_container_logs

        assert _get_container_logs(3) == "line1\nline2\n"

    @patch("zerg.commands.logs.subprocess.run")
    def test_returns_none_on_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="no such container")
        from zerg.commands.logs import _get_container_logs

        assert _get_container_logs(5) is None


class TestBuildDockerImage:
    @patch("zerg.commands.build.subprocess.run")
    @patch("zerg.commands.build.Path")
    def test_runs_docker_build(self, mock_path_cls: MagicMock, mock_run: MagicMock) -> None:
        mock_dockerfile = MagicMock()
        mock_dockerfile.exists.return_value = True
        mock_dockerfile.__str__ = lambda self: ".devcontainer/Dockerfile"
        mock_path_cls.return_value = mock_dockerfile
        mock_run.side_effect = [MagicMock(returncode=0), MagicMock(returncode=0, stdout="123456789\n")]
        from zerg.commands.build import _build_docker_image

        _build_docker_image()
        cmd = mock_run.call_args_list[0][0][0]
        assert "docker" in cmd and "build" in cmd

    @patch("zerg.commands.build.Path")
    def test_handles_missing_dockerfile(self, mock_path_cls: MagicMock) -> None:
        mock_dockerfile = MagicMock()
        mock_dockerfile.exists.return_value = False
        mock_path_cls.return_value = mock_dockerfile
        from zerg.commands.build import _build_docker_image

        with pytest.raises(SystemExit):
            _build_docker_image()
