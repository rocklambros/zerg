"""ZERG plugin system configuration models."""

from pydantic import BaseModel, Field


class HookConfig(BaseModel):
    """Configuration for a lifecycle hook."""

    event: str
    command: str
    timeout: int = Field(default=60, ge=1, le=3600)


class PluginGateConfig(BaseModel):
    """Configuration for a plugin-provided quality gate."""

    name: str
    command: str
    required: bool = False
    timeout: int = Field(default=300, ge=1, le=3600)


class LauncherPluginConfig(BaseModel):
    """Configuration for a launcher plugin."""

    name: str
    entry_point: str


class PluginsConfig(BaseModel):
    """Top-level plugin system configuration."""

    enabled: bool = True
    hooks: list[HookConfig] = Field(default_factory=list)
    quality_gates: list[PluginGateConfig] = Field(default_factory=list)
    launchers: list[LauncherPluginConfig] = Field(default_factory=list)
