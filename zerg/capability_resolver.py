"""Cross-cutting capability resolution for ZERG.

Resolves CLI flags, config, and task graph analysis into a unified
ResolvedCapabilities that gets passed as env vars to workers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from zerg.config import ZergConfig
from zerg.depth_tiers import DepthRouter, DepthTier
from zerg.mcp_router import MCPRouter
from zerg.modes import BehavioralMode, ModeDetector

logger = logging.getLogger(__name__)

# Commands where loops apply (code-touching commands)
LOOP_COMMANDS = frozenset(
    {
        "rush",
        "refactor",
        "test",
        "security",
        "build",
        "review",
        "analyze",
    }
)


@dataclass
class ResolvedCapabilities:
    """Resolved cross-cutting capabilities ready for worker injection."""

    # Depth
    depth_tier: str = "standard"
    token_budget: int = 2000

    # Compact/efficiency
    compact: bool = True

    # Behavioral mode
    mode: str = "precision"

    # MCP routing
    mcp_hint: str = ""

    # TDD
    tdd: bool = False

    # Rules
    rules_enabled: bool = True

    # Loops
    loop_enabled: bool = True
    loop_iterations: int = 5

    # Verification gates
    gates_enabled: bool = True
    staleness_threshold: int = 300

    def to_env_vars(self) -> dict[str, str]:
        """Convert to flat ZERG_* env var dict for worker injection."""
        env: dict[str, str] = {
            "ZERG_ANALYSIS_DEPTH": self.depth_tier,
            "ZERG_TOKEN_BUDGET": str(self.token_budget),
            "ZERG_COMPACT_MODE": "1" if self.compact else "0",
            "ZERG_BEHAVIORAL_MODE": self.mode,
            "ZERG_TDD_MODE": "1" if self.tdd else "0",
            "ZERG_RULES_ENABLED": "1" if self.rules_enabled else "0",
            "ZERG_LOOP_ENABLED": "1" if self.loop_enabled else "0",
            "ZERG_LOOP_ITERATIONS": str(self.loop_iterations),
            "ZERG_VERIFICATION_GATES": "1" if self.gates_enabled else "0",
            "ZERG_STALENESS_THRESHOLD": str(self.staleness_threshold),
        }
        if self.mcp_hint:
            env["ZERG_MCP_HINT"] = self.mcp_hint
        return env

    def to_dict(self) -> dict[str, Any]:
        """Serialize for logging/status output."""
        return {
            "depth_tier": self.depth_tier,
            "token_budget": self.token_budget,
            "compact": self.compact,
            "mode": self.mode,
            "mcp_hint": self.mcp_hint,
            "tdd": self.tdd,
            "rules_enabled": self.rules_enabled,
            "loop_enabled": self.loop_enabled,
            "loop_iterations": self.loop_iterations,
            "gates_enabled": self.gates_enabled,
        }


class CapabilityResolver:
    """Resolves CLI flags + config + task graph into ResolvedCapabilities.

    Design decisions:
    - Depth: scan all tasks, auto-detect per task via DepthRouter, take max.
      CLI flag overrides.
    - Compact/Loop: ON by default for code-touching commands.
    - Mode: auto-detected from resolved depth, can be CLI-overridden.
    - MCP: routed based on resolved depth tier.
    """

    def __init__(self) -> None:
        self._depth_router = DepthRouter()
        self._mode_detector = ModeDetector()
        self._mcp_router = MCPRouter()

    def resolve(
        self,
        cli_flags: dict[str, Any],
        config: ZergConfig,
        task_graph: dict[str, Any] | None = None,
        command: str | None = None,
    ) -> ResolvedCapabilities:
        """Resolve all capabilities from CLI flags, config, and task graph.

        Args:
            cli_flags: ctx.obj dict from Click (depth, compact, mode, tdd, etc.)
            config: ZergConfig instance
            task_graph: Parsed task-graph.json dict (optional)
            command: Active command name (e.g. "rush") for loop applicability

        Returns:
            ResolvedCapabilities ready for worker injection
        """
        # --- Depth resolution: deepest wins globally ---
        depth_tier = self._resolve_depth(cli_flags, task_graph)

        # --- Compact/efficiency ---
        compact = cli_flags.get("compact", True)

        # --- Behavioral mode ---
        mode = self._resolve_mode(cli_flags, config, depth_tier)

        # --- MCP routing ---
        mcp_hint = self._resolve_mcp(config, depth_tier)

        # --- TDD ---
        tdd = cli_flags.get("tdd", False) or config.tdd.enabled

        # --- Rules ---
        rules_enabled = config.rules.enabled

        # --- Loops ---
        is_code_command = command in LOOP_COMMANDS if command else True
        loop_enabled = cli_flags.get("loop", True) and is_code_command
        loop_iterations = cli_flags.get("iterations") or config.improvement_loops.max_iterations

        # --- Verification gates ---
        gates_enabled = config.verification.require_before_completion
        staleness_threshold = config.verification.staleness_threshold_seconds

        resolved = ResolvedCapabilities(
            depth_tier=depth_tier,
            token_budget=DepthTier(depth_tier).token_budget,
            compact=compact,
            mode=mode,
            mcp_hint=mcp_hint,
            tdd=tdd,
            rules_enabled=rules_enabled,
            loop_enabled=loop_enabled,
            loop_iterations=loop_iterations,
            gates_enabled=gates_enabled,
            staleness_threshold=staleness_threshold,
        )

        logger.info("Resolved capabilities: %s", resolved.to_dict())
        return resolved

    def _resolve_depth(
        self,
        cli_flags: dict[str, Any],
        task_graph: dict[str, Any] | None,
    ) -> str:
        """Resolve depth tier. CLI flag overrides, otherwise deepest task wins."""
        cli_depth = cli_flags.get("depth", "standard")
        if cli_depth != "standard":
            # CLI explicitly set a depth flag
            # Normalize think_hard -> think-hard for DepthTier enum
            return cli_depth.replace("_", "-")

        if not task_graph:
            return "standard"

        # Scan all tasks, auto-detect depth per task, take max
        tasks = task_graph.get("tasks", [])
        if not tasks:
            return "standard"

        max_tier = DepthTier.STANDARD
        for task in tasks:
            description = task.get("description", "")
            files = task.get("files", {})
            file_count = sum(len(v) for v in files.values() if isinstance(v, list))
            ctx = self._depth_router.route(
                description=description,
                file_count=file_count,
            )
            if ctx.tier.token_budget > max_tier.token_budget:
                max_tier = ctx.tier

        return max_tier.value

    def _resolve_mode(
        self,
        cli_flags: dict[str, Any],
        config: ZergConfig,
        depth_tier: str,
    ) -> str:
        """Resolve behavioral mode."""
        cli_mode = cli_flags.get("mode")
        explicit = BehavioralMode(cli_mode) if cli_mode else None

        mode_ctx = self._mode_detector.detect(
            explicit_mode=explicit,
            depth_tier=depth_tier,
        )
        return mode_ctx.mode.value

    def _resolve_mcp(self, config: ZergConfig, depth_tier: str) -> str:
        """Resolve MCP server hint from depth tier."""
        decision = self._mcp_router.route(depth_tier=depth_tier)
        if decision.recommended_servers:
            return ",".join(decision.server_names)
        return ""
