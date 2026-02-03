"""Plugin configuration models for ZERG."""

from pydantic import BaseModel, Field


class HookConfig(BaseModel):
    """Configuration for a lifecycle hook plugin."""

    event: str = Field(..., description="Lifecycle event name (from PluginHookEvent enum)")
    command: str = Field(..., description="Shell command to execute")
    timeout: int = Field(default=60, ge=1, le=600, description="Timeout in seconds")


class PluginGateConfig(BaseModel):
    """Configuration for a quality gate plugin."""

    name: str = Field(..., description="Unique gate name")
    command: str = Field(..., description="Shell command to execute")
    required: bool = Field(default=False, description="Whether gate failure blocks merge")
    timeout: int = Field(default=300, ge=1, le=3600, description="Timeout in seconds")


class LauncherPluginConfig(BaseModel):
    """Configuration for a launcher plugin."""

    name: str = Field(..., description="Launcher name (e.g., 'k8s', 'ssh')")
    entry_point: str = Field(
        ...,
        description="Python entry point (e.g., 'my_pkg.launchers:K8sLauncher')",
    )


class ContextEngineeringConfig(BaseModel):
    """Configuration for context engineering plugin."""

    enabled: bool = Field(default=True, description="Enable context engineering")
    command_splitting: bool = Field(default=True, description="Use split command files when available")
    security_rule_filtering: bool = Field(default=True, description="Filter security rules by task file extensions")
    task_context_budget_tokens: int = Field(
        default=4000, ge=500, le=20000, description="Max tokens for per-task context"
    )
    fallback_to_full: bool = Field(default=True, description="Fall back to full context on errors")


class PluginsConfig(BaseModel):
    """Complete plugin system configuration."""

    enabled: bool = Field(default=True, description="Whether plugin system is enabled")
    hooks: list[HookConfig] = Field(default_factory=list, description="Lifecycle hook plugins")
    quality_gates: list[PluginGateConfig] = Field(default_factory=list, description="Quality gate plugins")
    launchers: list[LauncherPluginConfig] = Field(default_factory=list, description="Launcher plugins")
    context_engineering: ContextEngineeringConfig = Field(
        default_factory=ContextEngineeringConfig,
        description="Context engineering plugin settings",
    )
