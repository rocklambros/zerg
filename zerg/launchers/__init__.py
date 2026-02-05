"""ZERG launchers package.

Re-exports launcher types, ABC, and concrete implementations.
Provides a factory function for plugin-based launcher discovery.
"""

from __future__ import annotations

from typing import Any

from zerg.launcher_types import LauncherConfig, LauncherType, SpawnResult, WorkerHandle
from zerg.logging import get_logger

logger = get_logger("launchers")

# Lazy imports for sub-modules that may not exist yet (created by parallel tasks).
# WorkerLauncher (base.py), SubprocessLauncher, ContainerLauncher are imported
# on first access so that this package is importable even before those modules land.

_WorkerLauncher: type | None = None
_SubprocessLauncher: type | None = None
_ContainerLauncher: type | None = None


def _load_worker_launcher() -> type:
    """Lazily import WorkerLauncher from launchers.base."""
    global _WorkerLauncher  # noqa: PLW0603
    if _WorkerLauncher is None:
        from zerg.launchers.base import WorkerLauncher as _WL

        _WorkerLauncher = _WL
    return _WorkerLauncher


def _load_subprocess_launcher() -> type:
    """Lazily import SubprocessLauncher."""
    global _SubprocessLauncher  # noqa: PLW0603
    if _SubprocessLauncher is None:
        from zerg.launchers.subprocess_launcher import (
            SubprocessLauncher as _SL,
        )

        _SubprocessLauncher = _SL
    return _SubprocessLauncher


def _load_container_launcher() -> type:
    """Lazily import ContainerLauncher."""
    global _ContainerLauncher  # noqa: PLW0603
    if _ContainerLauncher is None:
        from zerg.launchers.container_launcher import (
            ContainerLauncher as _CL,
        )

        _ContainerLauncher = _CL
    return _ContainerLauncher


def get_plugin_launcher(name: str, registry: Any) -> Any | None:
    """Look up a launcher from the plugin registry.

    Args:
        name: Launcher name to look up.
        registry: Plugin registry instance (PluginRegistry or None).

    Returns:
        WorkerLauncher instance from plugin, or None if not found/available.
    """
    if registry is None:
        return None
    plugin = registry.get_launcher(name)
    if plugin is None:
        return None
    try:
        launcher = plugin.create_launcher(None)
        return launcher
    except Exception as e:
        logger.warning(f"Plugin launcher '{name}' failed to create launcher instance: {e}")
        return None


def __getattr__(name: str) -> Any:
    """Module-level __getattr__ for lazy loading of launcher classes.

    This allows ``from zerg.launchers import WorkerLauncher`` to work even
    when the sub-modules are being created by parallel tasks and may not
    exist yet at package-import time.  If the sub-module is missing the
    import will raise ImportError at access time -- which is the correct
    behavior (fail at use, not at package init).
    """
    if name == "WorkerLauncher":
        return _load_worker_launcher()
    if name == "SubprocessLauncher":
        return _load_subprocess_launcher()
    if name == "ContainerLauncher":
        return _load_container_launcher()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Types (always available -- from launcher_types)
    "LauncherConfig",
    "LauncherType",
    "SpawnResult",
    "WorkerHandle",
    # ABC and concrete launchers (lazy-loaded from sub-modules)
    "WorkerLauncher",
    "SubprocessLauncher",
    "ContainerLauncher",
    # Factory
    "get_plugin_launcher",
]
