"""MCP server auto-routing for ZERG."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from zerg.mcp_telemetry import RoutingEvent, RoutingTelemetry

logger = logging.getLogger(__name__)


class MCPServer(Enum):
    """Known MCP servers with capabilities."""

    SEQUENTIAL = "sequential"
    CONTEXT7 = "context7"
    PLAYWRIGHT = "playwright"
    MORPHLLM = "morphllm"
    MAGIC = "magic"
    SERENA = "serena"

    @property
    def capabilities(self) -> list[str]:
        """Capabilities provided by this MCP server."""
        caps: dict[MCPServer, list[str]] = {
            MCPServer.SEQUENTIAL: ["analysis", "debugging", "architecture", "planning"],
            MCPServer.CONTEXT7: ["documentation", "library-lookup", "framework-patterns"],
            MCPServer.PLAYWRIGHT: ["browser-testing", "e2e", "visual-testing", "accessibility"],
            MCPServer.MORPHLLM: ["bulk-edit", "pattern-transform", "style-enforcement"],
            MCPServer.MAGIC: ["ui-component", "design-system", "frontend"],
            MCPServer.SERENA: ["symbol-ops", "project-memory", "lsp", "large-codebase"],
        }
        return caps[self]

    @property
    def cost_weight(self) -> float:
        """Relative cost weight (1.0 = baseline)."""
        weights: dict[MCPServer, float] = {
            MCPServer.SEQUENTIAL: 1.0,
            MCPServer.CONTEXT7: 0.5,
            MCPServer.PLAYWRIGHT: 2.0,
            MCPServer.MORPHLLM: 1.5,
            MCPServer.MAGIC: 1.5,
            MCPServer.SERENA: 1.0,
        }
        return weights[self]


@dataclass
class RoutingDecision:
    """Result of MCP routing decision."""

    recommended_servers: list[MCPServer]
    reasoning: list[str]
    cost_estimate: float
    depth_tier: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "servers": [s.value for s in self.recommended_servers],
            "reasoning": self.reasoning,
            "cost_estimate": self.cost_estimate,
            "depth_tier": self.depth_tier,
        }

    @property
    def server_names(self) -> list[str]:
        """List of recommended server name strings."""
        return [s.value for s in self.recommended_servers]


# Task type keywords -> required capabilities
TASK_CAPABILITY_MAP: dict[str, list[str]] = {
    "test": ["browser-testing", "e2e"],
    "debug": ["analysis", "debugging"],
    "refactor": ["bulk-edit", "pattern-transform", "symbol-ops"],
    "analyze": ["analysis", "architecture"],
    "document": ["documentation", "library-lookup"],
    "ui": ["ui-component", "design-system", "frontend"],
    "design": ["architecture", "planning"],
    "review": ["analysis", "architecture"],
    "security": ["analysis"],
}


class MCPRouter:
    """Route tasks to appropriate MCP servers based on task analysis."""

    def __init__(
        self,
        available_servers: list[str] | None = None,
        cost_aware: bool = True,
        max_servers: int = 3,
        telemetry_enabled: bool = False,
    ) -> None:
        """Initialize MCP router.

        Args:
            available_servers: List of available server names.
                If None, all known servers are available.
            cost_aware: Enable cost-based optimization.
            max_servers: Maximum number of servers to recommend.
            telemetry_enabled: Enable routing telemetry collection.
        """
        self.cost_aware = cost_aware
        self.max_servers = max_servers
        self._telemetry: RoutingTelemetry | None = RoutingTelemetry() if telemetry_enabled else None

        if available_servers is not None:
            self.available: list[MCPServer] = []
            for name in available_servers:
                try:
                    self.available.append(MCPServer(name))
                except ValueError:
                    logger.debug("Unknown MCP server name: %s", name)
        else:
            self.available = list(MCPServer)

    def route(
        self,
        task_description: str | None = None,
        task_type: str | None = None,
        file_extensions: list[str] | None = None,
        depth_tier: str | None = None,
    ) -> RoutingDecision:
        """Determine which MCP servers to use for a task.

        Args:
            task_description: Natural language task description.
            task_type: Task type hint (test, debug, refactor, etc.)
            file_extensions: File extensions involved (.py, .ts, etc.)
            depth_tier: Analysis depth tier from depth tiers system.

        Returns:
            RoutingDecision with recommended servers and reasoning.
        """
        needed_capabilities: set[str] = set()
        reasoning: list[str] = []

        # Gather capabilities from task type
        if task_type and task_type in TASK_CAPABILITY_MAP:
            caps = TASK_CAPABILITY_MAP[task_type]
            needed_capabilities.update(caps)
            reasoning.append(f"task type '{task_type}' needs: {', '.join(caps)}")

        # Gather from description keywords
        if task_description:
            desc_lower = task_description.lower()
            for keyword, caps in TASK_CAPABILITY_MAP.items():
                if keyword in desc_lower:
                    needed_capabilities.update(caps)
                    reasoning.append(f"keyword '{keyword}' in description")

        # File extension hints
        if file_extensions:
            for ext in file_extensions:
                if ext in (".tsx", ".jsx", ".css", ".html"):
                    needed_capabilities.add("ui-component")
                    needed_capabilities.add("frontend")
                    reasoning.append(f"extension {ext} -> frontend capabilities")
                if ext in (".test.ts", ".test.js", ".spec.ts", ".spec.js"):
                    needed_capabilities.add("browser-testing")
                    reasoning.append(f"extension {ext} -> testing capabilities")

        # Depth tier influence
        if depth_tier:
            from zerg.depth_tiers import DepthTier

            try:
                tier = DepthTier(depth_tier)
                tier_servers = tier.mcp_servers
                for server_name in tier_servers:
                    try:
                        server = MCPServer(server_name)
                        needed_capabilities.update(server.capabilities)
                        reasoning.append(f"depth tier '{depth_tier}' recommends {server_name}")
                    except ValueError:
                        pass
            except ValueError:
                logger.debug("Unknown depth tier: %s", depth_tier)

        # Match capabilities to servers
        matched = self._match_servers(needed_capabilities)

        # Apply cost awareness
        if self.cost_aware and len(matched) > self.max_servers:
            matched = self._cost_optimize(matched)
            reasoning.append(f"cost-optimized to {len(matched)} servers")

        # Limit to max
        matched = matched[: self.max_servers]

        cost = sum(s.cost_weight for s in matched)

        if not matched:
            reasoning.append("no specific MCP servers needed")

        decision = RoutingDecision(
            recommended_servers=matched,
            reasoning=reasoning,
            cost_estimate=cost,
            depth_tier=depth_tier,
        )

        if self._telemetry is not None:
            task_id = task_type or task_description or "unknown"
            event = RoutingEvent(
                task_id=task_id,
                servers_recommended=decision.server_names,
                cost_estimate=decision.cost_estimate,
            )
            self._telemetry.record(event)

        return decision

    @property
    def telemetry(self) -> RoutingTelemetry | None:
        """Access the telemetry instance, or None if telemetry is disabled."""
        return self._telemetry

    def _match_servers(self, needed: set[str]) -> list[MCPServer]:
        """Match needed capabilities to available servers.

        Args:
            needed: Set of capability strings required.

        Returns:
            List of matching servers sorted by relevance (most overlap first).
        """
        if not needed:
            return []

        scored: list[tuple[MCPServer, int]] = []
        for server in self.available:
            overlap = len(set(server.capabilities) & needed)
            if overlap > 0:
                scored.append((server, overlap))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in scored]

    def _cost_optimize(self, servers: list[MCPServer]) -> list[MCPServer]:
        """Sort by capability/cost ratio and trim to max_servers.

        Args:
            servers: List of candidate servers.

        Returns:
            Cost-optimized list trimmed to max_servers.
        """
        optimized = sorted(
            servers,
            key=lambda s: len(s.capabilities) / s.cost_weight,
            reverse=True,
        )
        return optimized[: self.max_servers]

    def get_env_hint(self, decision: RoutingDecision) -> dict[str, str]:
        """Get environment variable hint for worker.

        Args:
            decision: Routing decision to encode.

        Returns:
            Dict with ZERG_MCP_HINT env var, or empty dict.
        """
        if decision.recommended_servers:
            return {"ZERG_MCP_HINT": ",".join(decision.server_names)}
        return {}
