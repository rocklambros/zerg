"""Unit tests for MCP telemetry wiring into MCPRouter."""

from __future__ import annotations

from datetime import datetime

from zerg.mcp_router import MCPRouter
from zerg.mcp_telemetry import RoutingEvent, RoutingTelemetry

# ---------------------------------------------------------------------------
# RoutingEvent tests
# ---------------------------------------------------------------------------


def test_routing_event_creation_all_fields() -> None:
    """Test RoutingEvent creation with all fields explicitly set."""
    ts = datetime(2026, 1, 15, 12, 0, 0)
    event = RoutingEvent(
        task_id="task-42",
        servers_recommended=["sequential", "context7"],
        servers_used=["sequential"],
        cost_estimate=1.5,
        timestamp=ts,
    )
    assert event.task_id == "task-42"
    assert event.servers_recommended == ["sequential", "context7"]
    assert event.servers_used == ["sequential"]
    assert event.cost_estimate == 1.5
    assert event.timestamp == ts


def test_routing_event_defaults() -> None:
    """Test RoutingEvent defaults for optional fields."""
    event = RoutingEvent(task_id="t1", servers_recommended=["magic"])
    assert event.servers_used is None
    assert event.cost_estimate == 0.0
    assert isinstance(event.timestamp, datetime)


def test_routing_event_to_dict_roundtrip() -> None:
    """Test RoutingEvent to_dict contains all expected keys."""
    event = RoutingEvent(
        task_id="t1",
        servers_recommended=["sequential"],
        servers_used=["sequential"],
        cost_estimate=1.0,
    )
    d = event.to_dict()
    assert set(d.keys()) == {
        "task_id",
        "servers_recommended",
        "servers_used",
        "cost_estimate",
        "timestamp",
    }
    # Timestamp should be ISO-parseable
    datetime.fromisoformat(d["timestamp"])


# ---------------------------------------------------------------------------
# RoutingTelemetry tests
# ---------------------------------------------------------------------------


def test_telemetry_record_stores_events() -> None:
    """Test that record() stores events in order."""
    tel = RoutingTelemetry()
    e1 = RoutingEvent(task_id="a", servers_recommended=["sequential"])
    e2 = RoutingEvent(task_id="b", servers_recommended=["context7"])
    tel.record(e1)
    tel.record(e2)

    assert len(tel.events) == 2
    assert tel.events[0].task_id == "a"
    assert tel.events[1].task_id == "b"


def test_telemetry_summary_empty() -> None:
    """Test get_summary on a fresh RoutingTelemetry instance."""
    tel = RoutingTelemetry()
    summary = tel.get_summary()
    assert summary["total_routings"] == 0
    assert summary["server_frequency"] == {}
    assert summary["total_cost"] == 0.0
    assert "avg_cost" not in summary  # avg_cost absent when no events


def test_telemetry_summary_with_events() -> None:
    """Test get_summary calculates correct stats."""
    tel = RoutingTelemetry()
    tel.record_routing("t1", ["sequential", "context7"], cost_estimate=1.5)
    tel.record_routing("t2", ["sequential"], cost_estimate=1.0)

    summary = tel.get_summary()
    assert summary["total_routings"] == 2
    assert summary["server_frequency"]["sequential"] == 2
    assert summary["server_frequency"]["context7"] == 1
    assert summary["total_cost"] == 2.5
    assert summary["avg_cost"] == 1.25


def test_telemetry_clear_removes_all() -> None:
    """Test clear() empties the event list."""
    tel = RoutingTelemetry()
    tel.record_routing("t1", ["sequential"])
    tel.clear()
    assert len(tel.events) == 0


def test_telemetry_record_usage_updates_event() -> None:
    """Test record_usage links actual usage to existing event."""
    tel = RoutingTelemetry()
    tel.record_routing("t1", ["sequential", "context7"])
    tel.record_usage("t1", ["sequential"])
    assert tel.events[0].servers_used == ["sequential"]


# ---------------------------------------------------------------------------
# MCPRouter telemetry integration tests
# ---------------------------------------------------------------------------


def test_router_telemetry_enabled_records_events() -> None:
    """Test MCPRouter with telemetry enabled records events after route()."""
    router = MCPRouter(telemetry_enabled=True)
    router.route(task_type="debug")
    router.route(task_type="test")

    assert router.telemetry is not None
    assert len(router.telemetry.events) == 2
    # First event should correspond to debug routing
    assert router.telemetry.events[0].task_id == "debug"
    assert "sequential" in router.telemetry.events[0].servers_recommended


def test_router_telemetry_enabled_captures_cost() -> None:
    """Test telemetry events capture cost_estimate from routing decisions."""
    router = MCPRouter(telemetry_enabled=True)
    decision = router.route(task_type="debug")

    event = router.telemetry.events[0]
    assert event.cost_estimate == decision.cost_estimate


def test_router_telemetry_enabled_captures_server_names() -> None:
    """Test telemetry events capture recommended server names as strings."""
    router = MCPRouter(telemetry_enabled=True)
    decision = router.route(task_type="ui")

    event = router.telemetry.events[0]
    assert event.servers_recommended == decision.server_names


def test_router_telemetry_disabled_no_error() -> None:
    """Test MCPRouter with telemetry disabled does not error on route()."""
    router = MCPRouter(telemetry_enabled=False)
    decision = router.route(task_type="debug")

    assert router.telemetry is None
    # Routing still works correctly
    assert "sequential" in decision.server_names


def test_router_telemetry_default_disabled() -> None:
    """Test telemetry is disabled by default."""
    router = MCPRouter()
    assert router.telemetry is None


def test_router_telemetry_no_args_route() -> None:
    """Test telemetry records event even for empty routing (no task args)."""
    router = MCPRouter(telemetry_enabled=True)
    router.route()

    assert len(router.telemetry.events) == 1
    assert router.telemetry.events[0].task_id == "unknown"


def test_router_telemetry_uses_task_type_as_id() -> None:
    """Test task_id is derived from task_type when provided."""
    router = MCPRouter(telemetry_enabled=True)
    router.route(task_type="refactor")
    assert router.telemetry.events[0].task_id == "refactor"


def test_router_telemetry_uses_description_as_id_fallback() -> None:
    """Test task_id falls back to task_description when task_type is absent."""
    router = MCPRouter(telemetry_enabled=True)
    router.route(task_description="Fix the login bug")
    assert router.telemetry.events[0].task_id == "Fix the login bug"


def test_router_telemetry_summary_after_multiple_routes() -> None:
    """Test telemetry summary aggregates across multiple route() calls."""
    router = MCPRouter(telemetry_enabled=True)
    router.route(task_type="debug")
    router.route(task_type="test")
    router.route(task_type="document")

    summary = router.telemetry.get_summary()
    assert summary["total_routings"] == 3
    assert summary["total_cost"] > 0
