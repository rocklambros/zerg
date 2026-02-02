"""MCP routing telemetry for ZERG."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class RoutingEvent:
    """Single routing event."""

    task_id: str
    servers_recommended: list[str]
    servers_used: list[str] | None = None
    cost_estimate: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "task_id": self.task_id,
            "servers_recommended": self.servers_recommended,
            "servers_used": self.servers_used,
            "cost_estimate": self.cost_estimate,
            "timestamp": self.timestamp.isoformat(),
        }


class RoutingTelemetry:
    """Collect and report MCP routing telemetry."""

    def __init__(self) -> None:
        self._events: list[RoutingEvent] = []

    def record(self, event: RoutingEvent) -> None:
        """Record a routing event.

        Args:
            event: RoutingEvent to record.
        """
        self._events.append(event)

    def record_routing(
        self,
        task_id: str,
        servers_recommended: list[str],
        cost_estimate: float = 0.0,
    ) -> None:
        """Record a routing decision.

        Args:
            task_id: Task identifier.
            servers_recommended: List of recommended server names.
            cost_estimate: Estimated cost for this routing.
        """
        self._events.append(
            RoutingEvent(
                task_id=task_id,
                servers_recommended=servers_recommended,
                cost_estimate=cost_estimate,
            )
        )

    def record_usage(self, task_id: str, servers_used: list[str]) -> None:
        """Record which servers were actually used (post-execution).

        Finds the most recent unresolved event for the given task_id
        and sets its servers_used field.

        Args:
            task_id: Task identifier.
            servers_used: List of server names actually used.
        """
        for event in reversed(self._events):
            if event.task_id == task_id and event.servers_used is None:
                event.servers_used = servers_used
                return

    @property
    def events(self) -> list[RoutingEvent]:
        """Return a copy of all recorded events."""
        return self._events.copy()

    def get_summary(self) -> dict[str, Any]:
        """Get telemetry summary.

        Returns:
            Dictionary with total_routings, server_frequency,
            total_cost, and avg_cost.
        """
        if not self._events:
            return {"total_routings": 0, "server_frequency": {}, "total_cost": 0.0}

        server_freq: dict[str, int] = {}
        total_cost = 0.0

        for event in self._events:
            total_cost += event.cost_estimate
            for server in event.servers_recommended:
                server_freq[server] = server_freq.get(server, 0) + 1

        return {
            "total_routings": len(self._events),
            "server_frequency": server_freq,
            "total_cost": round(total_cost, 2),
            "avg_cost": round(total_cost / len(self._events), 2),
        }

    def clear(self) -> None:
        """Clear all recorded events."""
        self._events.clear()
