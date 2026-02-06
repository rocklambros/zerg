"""Tests for LauncherConfigurator component."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from zerg.config import ZergConfig
from zerg.constants import WorkerStatus
from zerg.launcher_configurator import LauncherConfigurator
from zerg.launcher_types import LauncherType
from zerg.launchers import ContainerLauncher, SubprocessLauncher
from zerg.plugins import PluginRegistry
from zerg.types import WorkerState


@pytest.fixture
def mock_config():
    config = MagicMock(spec=ZergConfig)
    config.workers = MagicMock()
    config.workers.timeout_minutes = 30
    config.logging = MagicMock()
    config.logging.directory = ".zerg/logs"
    config.resources = MagicMock()
    config.resources.container_memory_limit = "2g"
    config.resources.container_cpu_limit = "2.0"
    config.get_launcher_type.return_value = LauncherType.SUBPROCESS
    # No container_image attribute by default
    del config.container_image
    return config


@pytest.fixture
def mock_plugin_registry():
    return MagicMock(spec=PluginRegistry)


@pytest.fixture
def configurator(tmp_path, mock_config, mock_plugin_registry):
    return LauncherConfigurator(
        config=mock_config,
        repo_path=tmp_path,
        plugin_registry=mock_plugin_registry,
    )


class TestCreateLauncher:
    """Tests for create_launcher method."""

    def test_create_launcher_default_returns_subprocess(self, configurator):
        """Default (mode=None) auto-detects; no devcontainer -> subprocess."""
        launcher = configurator.create_launcher()
        assert isinstance(launcher, SubprocessLauncher)

    def test_create_launcher_subprocess_mode(self, configurator):
        """Explicit subprocess mode returns SubprocessLauncher."""
        launcher = configurator.create_launcher(mode="subprocess")
        assert isinstance(launcher, SubprocessLauncher)

    @patch("zerg.launcher_configurator.ContainerLauncher")
    def test_create_launcher_container_raises_on_docker_failure(self, mock_container_cls, configurator):
        """Container mode raises RuntimeError when Docker network fails."""
        mock_instance = MagicMock()
        mock_instance.ensure_network.return_value = False
        mock_container_cls.return_value = mock_instance

        with pytest.raises(RuntimeError, match="Container mode explicitly requested"):
            configurator.create_launcher(mode="container")

    @patch("zerg.launcher_configurator.ContainerLauncher")
    def test_create_launcher_container_success(self, mock_container_cls, configurator):
        """Container mode returns ContainerLauncher when Docker works."""
        mock_instance = MagicMock(spec=ContainerLauncher)
        mock_instance.ensure_network.return_value = True
        mock_container_cls.return_value = mock_instance

        launcher = configurator.create_launcher(mode="container")
        assert launcher is mock_instance

    def test_create_launcher_auto_returns_subprocess(self, tmp_path, mock_config, mock_plugin_registry):
        """Auto mode always returns SubprocessLauncher (task mode default)."""
        # Even with devcontainer, auto returns subprocess
        (tmp_path / ".devcontainer").mkdir()
        (tmp_path / ".devcontainer" / "devcontainer.json").write_text("{}")

        cfg = LauncherConfigurator(mock_config, tmp_path, mock_plugin_registry)
        launcher = cfg.create_launcher(mode="auto")

        assert isinstance(launcher, SubprocessLauncher)


class TestAutoDetect:
    """Tests for _auto_detect_launcher_type."""

    def test_auto_detect_always_returns_subprocess(self, configurator):
        """Auto-detect always returns SUBPROCESS (task mode is implicit default)."""
        result = configurator._auto_detect_launcher_type()
        assert result == LauncherType.SUBPROCESS

    def test_auto_detect_ignores_devcontainer(self, tmp_path, mock_config, mock_plugin_registry):
        """devcontainer.json presence is ignored; still returns SUBPROCESS."""
        (tmp_path / ".devcontainer").mkdir()
        (tmp_path / ".devcontainer" / "devcontainer.json").write_text("{}")

        cfg = LauncherConfigurator(mock_config, tmp_path, mock_plugin_registry)
        result = cfg._auto_detect_launcher_type()

        assert result == LauncherType.SUBPROCESS


class TestGetWorkerImageName:
    """Tests for _get_worker_image_name."""

    def test_default_image_name(self, configurator):
        """Default image name is 'zerg-worker'."""
        assert configurator._get_worker_image_name() == "zerg-worker"

    def test_custom_image_from_config(self, tmp_path, mock_plugin_registry):
        """Config with container_image attribute returns custom name."""
        config = MagicMock(spec=ZergConfig)
        config.container_image = "my-custom-image:v2"
        config.workers = MagicMock()
        config.workers.timeout_minutes = 30
        config.logging = MagicMock()
        config.logging.directory = ".zerg/logs"

        cfg = LauncherConfigurator(config, tmp_path, mock_plugin_registry)
        assert cfg._get_worker_image_name() == "my-custom-image:v2"


class TestCheckContainerHealth:
    """Tests for _check_container_health."""

    def test_marks_timed_out_workers_crashed(self, configurator, mock_config):
        """Workers exceeding timeout are marked CRASHED."""
        mock_config.workers.timeout_minutes = 1  # 60 seconds

        worker = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            port=49152,
            started_at=datetime.now() - timedelta(seconds=120),  # Over timeout
        )
        workers = {0: worker}

        launcher = MagicMock(spec=ContainerLauncher)

        configurator._check_container_health(workers, launcher)

        assert worker.status == WorkerStatus.CRASHED
        launcher.terminate.assert_called_once_with(0)

    def test_skips_non_container_launcher(self, configurator):
        """Non-container launcher is skipped."""
        workers = {0: MagicMock()}
        launcher = MagicMock(spec=SubprocessLauncher)

        # Should not raise or modify anything
        configurator._check_container_health(workers, launcher)
