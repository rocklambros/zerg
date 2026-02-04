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
    context_threshold_percent: int = Field(default=int(DEFAULT_CONTEXT_THRESHOLD * 100), ge=50, le=90)
    launcher_type: str = Field(default="subprocess", pattern="^(subprocess|container)$")
    backoff_strategy: str = Field(default="exponential", pattern="^(exponential|linear|fixed)$")
    backoff_base_seconds: int = Field(default=30, ge=1, le=600)
    backoff_max_seconds: int = Field(default=300, ge=1, le=3600)
    task_list_id: str | None = Field(
        default=None,
        description="Override CLAUDE_CODE_TASK_LIST_ID (default: feature name)",
    )

    # Resilience: Spawn retry configuration (FR-1)
    spawn_retry_attempts: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Number of retry attempts for worker spawn failures",
    )
    spawn_backoff_strategy: str = Field(
        default="exponential",
        pattern="^(exponential|linear|fixed)$",
        description="Backoff strategy for spawn retries: exponential, linear, or fixed",
    )
    spawn_backoff_base_seconds: int = Field(
        default=2,
        ge=1,
        le=60,
        description="Base delay in seconds for spawn retry backoff",
    )
    spawn_backoff_max_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Maximum delay in seconds for spawn retry backoff",
    )

    # Resilience: Task timeout configuration (FR-2)
    task_stale_timeout_seconds: int = Field(
        default=600,
        ge=60,
        le=3600,
        description="Timeout in seconds before a stale in_progress task is auto-failed",
    )

    # Resilience: Heartbeat configuration (FR-3)
    heartbeat_interval_seconds: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Interval in seconds between worker heartbeats",
    )
    heartbeat_stale_threshold: int = Field(
        default=120,
        ge=30,
        le=600,
        description="Threshold in seconds before a worker is considered stale (no heartbeat)",
    )

    # Resilience: Auto-respawn configuration (FR-6)
    auto_respawn: bool = Field(
        default=True,
        description="Automatically respawn workers that crash to maintain target count",
    )
    max_respawn_attempts: int = Field(
        default=5,
        ge=0,
        le=20,
        description="Maximum respawn attempts per worker before giving up",
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


class ResilienceConfig(BaseModel):
    """Resilience configuration for auto-recovery and fault tolerance.

    This config acts as a master toggle for resilience features.
    Individual feature settings are in WorkersConfig for consistency
    with existing configuration patterns.
    """

    enabled: bool = Field(
        default=True,
        description="Master toggle for all resilience features",
    )


class EfficiencyConfig(BaseModel):
    """Token efficiency configuration."""

    auto_compact_threshold: float = Field(default=0.75, ge=0.5, le=1.0)
    symbol_system: bool = True
    abbreviations: bool = True


class RulesConfig(BaseModel):
    """Engineering rules configuration."""

    enabled: bool = True
    base_rules: bool = True
    custom_rules: bool = True
    disabled_rules: list[str] = Field(default_factory=list)
    inject_into_workers: bool = True


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


class LoopConfig(BaseModel):
    """Iterative improvement loop configuration."""

    max_iterations: int = Field(default=5, ge=1, le=10)
    plateau_threshold: int = Field(default=2, ge=1, le=5)
    rollback_on_regression: bool = True
    convergence_threshold: float = Field(default=0.02, ge=0.001, le=0.5)


class VerificationConfig(BaseModel):
    """Verification gate configuration."""

    require_before_completion: bool = True
    staleness_threshold_seconds: int = Field(default=300, ge=10, le=3600)
    store_artifacts: bool = True
    artifact_dir: str = ".zerg/artifacts"


class ModeConfig(BaseModel):
    """Behavioral mode configuration."""

    auto_detect: bool = True
    default_mode: str = Field(
        default="precision",
        pattern="^(precision|speed|exploration|refactor|debug)$",
    )
    log_transitions: bool = True


class MCPRoutingConfig(BaseModel):
    """MCP auto-routing configuration."""

    auto_detect: bool = True
    available_servers: list[str] = Field(
        default_factory=lambda: [
            "sequential",
            "context7",
            "playwright",
            "morphllm",
            "magic",
            "serena",
        ]
    )
    cost_aware: bool = True
    telemetry: bool = True
    max_servers: int = Field(default=3, ge=1, le=6)


class TDDConfig(BaseModel):
    """TDD enforcement configuration."""

    enabled: bool = False
    enforce_red_green: bool = True
    anti_patterns: list[str] = Field(default_factory=lambda: ["mock_heavy", "testing_impl", "no_assertions"])


class HeartbeatConfig(BaseModel):
    """Heartbeat health monitoring configuration."""

    interval_seconds: int = Field(default=15, ge=5, le=300)
    stall_timeout_seconds: int = Field(default=120, ge=30, le=600)
    max_restarts: int = Field(default=2, ge=0, le=5)


class EscalationConfig(BaseModel):
    """Escalation handling configuration."""

    auto_interrupt: bool = Field(default=True)
    poll_interval_seconds: int = Field(default=5, ge=1, le=60)


class VerificationTiersConfig(BaseModel):
    """Three-tier verification configuration."""

    tier1_blocking: bool = Field(default=True)
    tier1_command: str | None = Field(default=None)
    tier2_blocking: bool = Field(default=True)
    tier2_command: str | None = Field(default=None)
    tier3_blocking: bool = Field(default=False)
    tier3_command: str | None = Field(default=None)


class RepoMapConfig(BaseModel):
    """Repository symbol map configuration."""

    enabled: bool = Field(default=True)
    languages: list[str] = Field(default_factory=lambda: ["python", "javascript", "typescript"])
    max_tokens_per_module: int = Field(default=3000, ge=500, le=10000)
    context_budget_percent: int = Field(default=15, ge=5, le=30)


class TokenMetricsConfig(BaseModel):
    """Token usage tracking configuration."""

    enabled: bool = True
    api_counting: bool = False
    cache_enabled: bool = True
    cache_ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    fallback_chars_per_token: float = Field(default=4.0, ge=1.0, le=10.0)


class PlanningConfig(BaseModel):
    """Planning and detail level configuration for bite-sized task planning.

    Controls how detailed task plans are generated, including TDD steps,
    code snippets, and adaptive detail based on developer familiarity.
    """

    default_detail: str = Field(
        default="standard",
        pattern="^(standard|medium|high)$",
        description="Default detail level: standard (no steps), medium (TDD steps), high (with snippets)",
    )
    include_code_snippets: bool = Field(
        default=False,
        description="Include code snippets in task steps (requires high detail level)",
    )
    include_test_first: bool = Field(
        default=True,
        description="Generate test-first (TDD) step sequences",
    )
    step_verification: bool = Field(
        default=True,
        description="Enable step-level exit code verification during execution",
    )
    adaptive_detail: bool = Field(
        default=True,
        description="Automatically reduce detail level based on familiarity and success rates",
    )
    adaptive_familiarity_threshold: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Number of times a file must be modified before reducing detail",
    )
    adaptive_success_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Success rate threshold for reducing detail in a directory",
    )


class RushConfig(BaseModel):
    """Rush execution configuration."""

    defer_merge_to_ship: bool = Field(
        default=True,
        description="Defer merging to main until /zerg:git ship is called",
    )
    gates_at_ship_only: bool = Field(
        default=True,
        description="Run quality gates only at ship time, not after each level",
    )


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
    resilience: ResilienceConfig = Field(default_factory=ResilienceConfig)
    plugins: PluginsConfig = Field(default_factory=PluginsConfig)
    efficiency: EfficiencyConfig = Field(default_factory=EfficiencyConfig)
    rules: RulesConfig = Field(default_factory=RulesConfig)
    error_recovery: ErrorRecoveryConfig = Field(default_factory=ErrorRecoveryConfig)
    git: GitConfig = Field(default_factory=GitConfig)
    improvement_loops: LoopConfig = Field(default_factory=LoopConfig)
    behavioral_modes: ModeConfig = Field(default_factory=ModeConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    mcp_routing: MCPRoutingConfig = Field(default_factory=MCPRoutingConfig)
    tdd: TDDConfig = Field(default_factory=TDDConfig)
    heartbeat: HeartbeatConfig = Field(default_factory=HeartbeatConfig)
    escalation: EscalationConfig = Field(default_factory=EscalationConfig)
    verification_tiers: VerificationTiersConfig = Field(default_factory=VerificationTiersConfig)
    repo_map: RepoMapConfig = Field(default_factory=RepoMapConfig)
    token_metrics: TokenMetricsConfig = Field(default_factory=TokenMetricsConfig)
    planning: PlanningConfig = Field(default_factory=PlanningConfig)
    rush: RushConfig = Field(default_factory=RushConfig)

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
