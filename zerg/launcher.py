"""Backward compatibility — imports redirect to zerg.launchers package.

This module re-exports all public names that were previously defined here.
All real implementation now lives in:
  - zerg.launcher_types (LauncherConfig, LauncherType, SpawnResult, WorkerHandle)
  - zerg.env_validator (ALLOWED_ENV_VARS, DANGEROUS_ENV_VARS, validate_env_vars, ...)
  - zerg.launchers.base (WorkerLauncher ABC)
  - zerg.launchers.subprocess_launcher (SubprocessLauncher)
  - zerg.launchers.container_launcher (ContainerLauncher)
  - zerg.launchers (get_plugin_launcher factory)

TASK-022 will update all callers to import from the new paths directly,
after which this file will be deleted.
"""

from zerg.env_validator import (
    ALLOWED_ENV_VARS,
    CONTAINER_HEALTH_FILE,
    CONTAINER_HOME_DIR,
    DANGEROUS_ENV_VARS,
    validate_env_vars,
)
from zerg.launcher_types import LauncherConfig, LauncherType, SpawnResult, WorkerHandle
from zerg.launchers import get_plugin_launcher
from zerg.launchers.base import WorkerLauncher
from zerg.launchers.container_launcher import ContainerLauncher
from zerg.launchers.subprocess_launcher import SubprocessLauncher

__all__ = [
    # Launcher ABC and concrete implementations
    "WorkerLauncher",
    "SubprocessLauncher",
    "ContainerLauncher",
    # Data types
    "LauncherConfig",
    "LauncherType",
    "SpawnResult",
    "WorkerHandle",
    # Environment validation
    "ALLOWED_ENV_VARS",
    "DANGEROUS_ENV_VARS",
    "CONTAINER_HOME_DIR",
    "CONTAINER_HEALTH_FILE",
    "validate_env_vars",
    # Factory
    "get_plugin_launcher",
]
