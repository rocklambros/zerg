"""Analysis depth tier system for ZERG."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DepthTier(Enum):
    """Analysis depth levels controlling reasoning intensity."""

    QUICK = "quick"  # Fast, surface-level analysis
    STANDARD = "standard"  # Default balanced analysis
    THINK = "think"  # Structured analysis (~4K tokens)
    THINK_HARD = "think-hard"  # Deep analysis (~10K tokens)
    ULTRATHINK = "ultrathink"  # Maximum depth (~32K tokens)

    @property
    def token_budget(self) -> int:
        """Approximate token budget for this depth tier."""
        budgets = {
            DepthTier.QUICK: 1000,
            DepthTier.STANDARD: 2000,
            DepthTier.THINK: 4000,
            DepthTier.THINK_HARD: 10000,
            DepthTier.ULTRATHINK: 32000,
        }
        return budgets[self]

    @property
    def mcp_servers(self) -> list[str]:
        """Recommended MCP servers for this depth tier."""
        servers: dict[DepthTier, list[str]] = {
            DepthTier.QUICK: [],
            DepthTier.STANDARD: [],
            DepthTier.THINK: ["sequential"],
            DepthTier.THINK_HARD: ["sequential", "context7"],
            DepthTier.ULTRATHINK: ["sequential", "context7", "playwright", "morphllm"],
        }
        return servers[self]

    @property
    def description(self) -> str:
        """Human-readable description of this depth tier."""
        descriptions = {
            DepthTier.QUICK: "Fast surface-level analysis",
            DepthTier.STANDARD: "Balanced default analysis",
            DepthTier.THINK: "Structured multi-step analysis",
            DepthTier.THINK_HARD: "Deep architectural analysis",
            DepthTier.ULTRATHINK: "Maximum depth comprehensive analysis",
        }
        return descriptions[self]


@dataclass
class DepthContext:
    """Context information for depth-aware operations."""

    tier: DepthTier
    token_budget: int
    recommended_mcp: list[str]
    env_value: str  # Value to pass via ZERG_ANALYSIS_DEPTH env var

    @classmethod
    def from_tier(cls, tier: DepthTier) -> DepthContext:
        """Create context from a depth tier."""
        return cls(
            tier=tier,
            token_budget=tier.token_budget,
            recommended_mcp=tier.mcp_servers,
            env_value=tier.value,
        )


class DepthRouter:
    """Routes analysis requests to appropriate depth tier."""

    # Keywords that suggest higher analysis depth
    DEPTH_KEYWORDS: dict[DepthTier, list[str]] = {
        DepthTier.THINK: [
            "analyze",
            "investigate",
            "debug",
            "trace",
            "profile",
        ],
        DepthTier.THINK_HARD: [
            "architect",
            "redesign",
            "migrate",
            "security audit",
            "performance analysis",
            "system design",
        ],
        DepthTier.ULTRATHINK: [
            "modernize",
            "rewrite",
            "critical",
            "production incident",
            "full audit",
            "comprehensive review",
        ],
    }

    def __init__(self, default_tier: DepthTier = DepthTier.STANDARD) -> None:
        """Initialize depth router.

        Args:
            default_tier: Default depth tier when none specified.
        """
        self.default_tier = default_tier

    def route(
        self,
        description: str | None = None,
        explicit_tier: DepthTier | None = None,
        file_count: int = 0,
        directory_count: int = 0,
    ) -> DepthContext:
        """Determine appropriate depth tier for a task.

        Args:
            description: Task description for keyword matching.
            explicit_tier: Explicitly requested tier (overrides auto-detection).
            file_count: Number of files involved.
            directory_count: Number of directories involved.

        Returns:
            DepthContext for the selected tier.
        """
        if explicit_tier is not None:
            return DepthContext.from_tier(explicit_tier)

        tier = self._detect_from_description(description) if description else self.default_tier

        # Escalate based on scope
        if directory_count > 5 or file_count > 20:
            tier = max(tier, DepthTier.THINK_HARD, key=lambda t: t.token_budget)
        elif directory_count > 2 or file_count > 7:
            tier = max(tier, DepthTier.THINK, key=lambda t: t.token_budget)

        return DepthContext.from_tier(tier)

    def _detect_from_description(self, description: str) -> DepthTier:
        """Detect depth tier from task description keywords.

        Args:
            description: Task description text.

        Returns:
            Detected DepthTier.
        """
        desc_lower = description.lower()

        # Check from highest to lowest priority
        for tier in [DepthTier.ULTRATHINK, DepthTier.THINK_HARD, DepthTier.THINK]:
            keywords = self.DEPTH_KEYWORDS.get(tier, [])
            if any(kw in desc_lower for kw in keywords):
                return tier

        return self.default_tier

    def get_mode_hint(self, context: DepthContext) -> str | None:
        """Suggest a behavioral mode based on depth tier.

        Args:
            context: Current depth context.

        Returns:
            Suggested mode name or None.
        """
        if context.tier in (DepthTier.ULTRATHINK, DepthTier.THINK_HARD):
            return "precision"
        if context.tier == DepthTier.QUICK:
            return "speed"
        return None

    def get_env_vars(self, context: DepthContext) -> dict[str, str]:
        """Get environment variables for a depth context.

        Args:
            context: Depth context to export.

        Returns:
            Dict of environment variable name to value.
        """
        return {"ZERG_ANALYSIS_DEPTH": context.env_value}
