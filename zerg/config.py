"""ZERG configuration management using Pydantic."""

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field

from zerg.constants import (
    DEFAULT_CONTEXT_THRESHOLD,
    DEFAULT_PORT_RANGE_END,
    DEFAULT_PORT_RANGE_START,
    DEFAULT_PORTS_PER_WORKER,
    DEFAULT_RETRY_ATTEMPTS,
    DEFAULT_TIMEOUT_MINUTES,
    DEFAULT_WORKERS,
)
from zerg.git.config import GitConfig
from zerg.launcher import LauncherType
from zerg.plugin_config import PluginsConfig


class ProjectConfig(BaseModel):
    """Project identification configuration."""

    name: str = "zerg"
    description: str = "Parallel Claude Code execution system"


class WorkersConfig(BaseModel):
    """Worker configuration settings."""

    max_concurrent: int = Field(default=DEFAULT_WORKERS, ge=1, le=10)
    timeout_minutes: int = Field(default=DEFAULT_TIMEOUT_MINUTES, ge=1, le=120)
    retry_attempts: int = Field(default=DEFAULT_RETRY_ATTEMPTS, ge=0, le=10)
    context_threshold_percent: int = Field(
        default=int(DEFAULT_CONTEXT_THRESHOLD * 100), ge=50, le=90
    )
    launcher_type: str = Field(default="subprocess", pattern="^(subprocess|container)$")
    backoff_strategy: str = Field(
        default="exponential", pattern="^(exponential|linear|fixed)$"
    )
    backoff_base_seconds: int = Field(default=30, ge=1, le=600)
    backoff_max_seconds: int = Field(default=300, ge=1, le=3600)
    task_list_id: str | None = Field(
        default=None,
        description="Override CLAUDE_CODE_TASK_LIST_ID (default: feature name)",
    )


class PortsConfig(BaseModel):
    """Port allocation configuration."""

    range_start: int = Field(default=DEFAULT_PORT_RANGE_START, ge=1024, le=65535)
    range_end: int = Field(default=DEFAULT_PORT_RANGE_END, ge=1024, le=65535)
    ports_per_worker: int = Field(default=DEFAULT_PORTS_PER_WORKER, ge=1, le=100)


class QualityGate(BaseModel):
    """Single quality gate configuration."""

    name: str
    command: str
    required: bool = False
    timeout: int = Field(default=300, ge=1, le=3600)
    coverage_threshold: int | None = None


class ResourcesConfig(BaseModel):
    """Resource limits per worker."""

    cpu_cores: int = Field(default=2, ge=1, le=32)
    memory_gb: int = Field(default=4, ge=1, le=64)
    disk_gb: int = Field(default=10, ge=1, le=500)
    container_memory_limit: str = Field(default="4g")
    container_cpu_limit: float = Field(default=2.0, ge=0.1, le=32.0)


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field(default="info", pattern="^(debug|info|warn|error)$")
    directory: str = ".zerg/logs"
    retain_days: int = Field(default=7, ge=1, le=365)
    ephemeral_retain_on_success: bool = False
    ephemeral_retain_on_failure: bool = True
    max_log_size_mb: int = Field(default=50, ge=1, le=1000)
    structured_output: bool = True


class SecurityConfig(BaseModel):
    """Security configuration."""

    level: str = Field(default="standard", pattern="^(minimal|standard|strict)$")
    pre_commit_hooks: bool = True
    audit_logging: bool = True
    container_readonly: bool = True


class CircuitBreakerConfig(BaseModel):
    """Circuit breaker configuration."""

    enabled: bool = True
    failure_threshold: int = Field(default=3, ge=1, le=20)
    cooldown_seconds: int = Field(default=60, ge=5, le=600)


class BackpressureConfig(BaseModel):
    """Backpressure controller configuration."""

    enabled: bool = True
    failure_rate_threshold: float = Field(default=0.5, ge=0.1, le=1.0)
    window_size: int = Field(default=10, ge=3, le=100)


class ErrorRecoveryConfig(BaseModel):
    """Error recovery configuration."""

    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)
    backpressure: BackpressureConfig = Field(default_factory=BackpressureConfig)


class ZergConfig(BaseModel):
    """Complete ZERG configuration."""

    project: ProjectConfig = Field(default_factory=ProjectConfig)
    workers: WorkersConfig = Field(default_factory=WorkersConfig)
    ports: PortsConfig = Field(default_factory=PortsConfig)
    quality_gates: list[QualityGate] = Field(default_factory=list)
    mcp_servers: list[str] = Field(default_factory=lambda: ["filesystem", "github", "fetch"])
    resources: ResourcesConfig = Field(default_factory=ResourcesConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    plugins: PluginsConfig = Field(default_factory=PluginsConfig)
    error_recovery: ErrorRecoveryConfig = Field(default_factory=ErrorRecoveryConfig)
    git: GitConfig = Field(default_factory=GitConfig)

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> "ZergConfig":
        """Load configuration from YAML file.

        Args:
            config_path: Path to config file. Defaults to .zerg/config.yaml

        Returns:
            ZergConfig instance
        """
        config_path = Path(".zerg/config.yaml") if config_path is None else Path(config_path)

        if not config_path.exists():
            return cls()

        with open(config_path) as f:
            data = yaml.safe_load(f) or {}

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ZergConfig":
        """Create configuration from dictionary.

        Args:
            data: Configuration dictionary

        Returns:
            ZergConfig instance
        """
        return cls(**data)

    def save(self, config_path: str | Path | None = None) -> None:
        """Save configuration to YAML file.

        Args:
            config_path: Path to save config. Defaults to .zerg/config.yaml
        """
        config_path = Path(".zerg/config.yaml") if config_path is None else Path(config_path)

        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Configuration as dictionary
        """
        return self.model_dump()

    @property
    def context_threshold(self) -> float:
        """Get context threshold as a float (0.0 to 1.0)."""
        return self.workers.context_threshold_percent / 100.0

    def get_gate(self, name: str) -> QualityGate | None:
        """Get a quality gate by name.

        Args:
            name: Gate name

        Returns:
            QualityGate or None if not found
        """
        for gate in self.quality_gates:
            if gate.name == name:
                return gate
        return None

    def get_required_gates(self) -> list[QualityGate]:
        """Get all required quality gates.

        Returns:
            List of required QualityGate instances
        """
        return [g for g in self.quality_gates if g.required]

    def get_launcher_type(self) -> LauncherType:
        """Get the configured launcher type.

        Returns:
            LauncherType enum value
        """
        return LauncherType(self.workers.launcher_type)
