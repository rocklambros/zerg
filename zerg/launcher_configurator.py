"""ZERG launcher configuration component.

Extracted from Orchestrator to handle launcher creation, auto-detection,
and container lifecycle management.
"""

import subprocess as sp
from datetime import datetime
from pathlib import Path

from zerg.config import ZergConfig
from zerg.constants import WorkerStatus
from zerg.launcher import (
    ContainerLauncher,
    LauncherConfig,
    LauncherType,
    SubprocessLauncher,
    WorkerLauncher,
    get_plugin_launcher,
)
from zerg.logging import get_logger
from zerg.plugins import PluginRegistry
from zerg.types import WorkerState

logger = get_logger("launcher_configurator")


class LauncherConfigurator:
    """Manages launcher creation, auto-detection, and container lifecycle.

    Encapsulates launcher-related logic previously embedded in Orchestrator,
    including launcher type detection, Docker image resolution, orphan
    container cleanup, and container health checking.
    """

    def __init__(
        self,
        config: ZergConfig,
        repo_path: Path,
        plugin_registry: PluginRegistry,
    ) -> None:
        """Initialize launcher configurator.

        Args:
            config: ZERG configuration
            repo_path: Path to git repository (resolved)
            plugin_registry: Plugin registry for custom launchers
        """
        self._config = config
        self._repo_path = repo_path
        self._plugin_registry = plugin_registry

    def create_launcher(self, mode: str | None = None) -> WorkerLauncher:
        """Create worker launcher based on config and mode.

        Args:
            mode: Launcher mode override (subprocess, container, auto)
                  If None, uses config setting

        Returns:
            Configured WorkerLauncher instance
        """
        # Check plugin registry first for custom launcher
        if mode and mode not in ("subprocess", "container", "auto"):
            plugin_launcher = get_plugin_launcher(mode, self._plugin_registry)
            if plugin_launcher is not None:
                logger.info(f"Using plugin launcher: {mode}")
                return plugin_launcher

        # Determine launcher type
        if mode == "subprocess":
            launcher_type = LauncherType.SUBPROCESS
        elif mode == "container":
            launcher_type = LauncherType.CONTAINER
        elif mode == "auto" or mode is None:
            # Auto-detect based on environment
            launcher_type = self._auto_detect_launcher_type()
        else:
            # Try plugin launcher for unrecognized mode
            plugin_launcher = get_plugin_launcher(mode, self._plugin_registry)
            if plugin_launcher is not None:
                logger.info(f"Using plugin launcher: {mode}")
                return plugin_launcher
            # Fall back to config setting if plugin not found
            launcher_type = self._config.get_launcher_type()

        config = LauncherConfig(
            launcher_type=launcher_type,
            timeout_seconds=self._config.workers.timeout_minutes * 60,
            log_dir=Path(self._config.logging.directory),
        )

        if launcher_type == LauncherType.CONTAINER:
            # Use ContainerLauncher with resource limits from config
            launcher = ContainerLauncher(
                config=config,
                image_name=self._get_worker_image_name(),
                memory_limit=self._config.resources.container_memory_limit,
                cpu_limit=self._config.resources.container_cpu_limit,
            )
            # Ensure network exists
            network_ok = launcher.ensure_network()
            if not network_ok:
                if mode == "container":
                    raise RuntimeError(
                        "Container mode explicitly requested but Docker network "
                        "creation failed. Check that Docker is running and accessible."
                    )
                # Auto-detected container mode: fall back gracefully
                logger.warning("Docker network setup failed, falling back to subprocess")
                return SubprocessLauncher(config)
            logger.info("Using ContainerLauncher")
            return launcher
        else:
            logger.info("Using SubprocessLauncher")
            return SubprocessLauncher(config)

    def _auto_detect_launcher_type(self) -> LauncherType:
        """Auto-detect whether to use container or subprocess launcher.

        Detection logic:
        1. Check if devcontainer.json exists
        2. Check if worker image is built
        3. Fall back to subprocess if containers not available

        Returns:
            Detected LauncherType
        """
        devcontainer_path = self._repo_path / ".devcontainer" / "devcontainer.json"

        # No devcontainer config = use subprocess
        if not devcontainer_path.exists():
            logger.debug("No devcontainer.json found, using subprocess mode")
            return LauncherType.SUBPROCESS

        # Check if image exists
        image_name = self._get_worker_image_name()

        try:
            import subprocess as _sp

            result = _sp.run(
                ["docker", "image", "inspect", image_name],
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                logger.debug(f"Found worker image {image_name}, using container mode")
                return LauncherType.CONTAINER
            else:
                logger.debug(f"Worker image {image_name} not found, using subprocess mode")
                return LauncherType.SUBPROCESS
        except Exception as e:
            logger.debug(f"Docker check failed ({e}), using subprocess mode")
            return LauncherType.SUBPROCESS

    def _get_worker_image_name(self) -> str:
        """Get the worker image name.

        Returns:
            Docker image name for workers
        """
        # Check config first
        if hasattr(self._config, "container_image"):
            return str(self._config.container_image)

        # Default to standard worker image
        return "zerg-worker"

    def _cleanup_orphan_containers(self) -> None:
        """Remove leftover zerg-worker containers from previous runs."""
        try:
            result = sp.run(
                ["docker", "ps", "-a", "--filter", "name=zerg-worker", "--format", "{{.ID}}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return
            for cid in result.stdout.strip().split("\n"):
                if cid:
                    sp.run(
                        ["docker", "rm", "-f", cid],
                        capture_output=True,
                        timeout=10,
                    )
                    logger.info(f"Removed orphan container {cid[:12]}")
        except (sp.TimeoutExpired, FileNotFoundError):
            pass  # Docker not available, skip

    def _check_container_health(
        self,
        workers: dict[int, WorkerState],
        launcher: WorkerLauncher,
    ) -> None:
        """Mark containers stuck beyond timeout as CRASHED.

        Args:
            workers: Dictionary of worker_id to WorkerState (owned by Orchestrator)
            launcher: The active WorkerLauncher instance (owned by Orchestrator)
        """
        try:
            is_container = isinstance(launcher, ContainerLauncher)
        except TypeError:
            return
        if not is_container:
            return
        timeout_seconds = self._config.workers.timeout_minutes * 60
        for worker_id, worker in list(workers.items()):
            if worker.status == WorkerStatus.RUNNING and worker.started_at:
                elapsed = (datetime.now() - worker.started_at).total_seconds()
                if elapsed > timeout_seconds:
                    logger.warning(
                        f"Worker {worker_id} exceeded timeout ({elapsed:.0f}s > {timeout_seconds}s), terminating"
                    )
                    launcher.terminate(worker_id)
                    worker.status = WorkerStatus.CRASHED
