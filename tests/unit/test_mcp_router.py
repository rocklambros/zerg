"""Unit tests for ZERG MCP auto-routing system."""

from __future__ import annotations

from datetime import datetime

import pytest
from click.testing import CliRunner

from zerg.cli import cli
from zerg.mcp_router import (
    TASK_CAPABILITY_MAP,
    MCPRouter,
    MCPServer,
    RoutingDecision,
)
from zerg.mcp_telemetry import RoutingEvent, RoutingTelemetry


class TestMCPServerEnum:
    """Tests for MCPServer enum values and properties."""

    def test_all_servers_exist_with_capabilities_and_cost(self) -> None:
        """Test all 6 servers exist with capabilities and positive cost."""
        assert len(MCPServer) == 6
        for server in MCPServer:
            assert len(server.capabilities) > 0
            assert server.cost_weight > 0

    def test_cost_weight_ordering(self) -> None:
        """Test CONTEXT7 cheapest and PLAYWRIGHT most expensive."""
        assert MCPServer.CONTEXT7.cost_weight == 0.5
        assert MCPServer.SEQUENTIAL.cost_weight == 1.0
        assert MCPServer.PLAYWRIGHT.cost_weight == 2.0


class TestRoutingDecision:
    """Tests for RoutingDecision dataclass."""

    def test_creation_and_to_dict(self) -> None:
        """Test basic creation and serialization."""
        decision = RoutingDecision(
            recommended_servers=[MCPServer.SEQUENTIAL, MCPServer.CONTEXT7],
            reasoning=["reason1", "reason2"],
            cost_estimate=1.5,
            depth_tier="think",
        )
        assert decision.server_names == ["sequential", "context7"]
        d = decision.to_dict()
        assert d["servers"] == ["sequential", "context7"]
        assert d["cost_estimate"] == 1.5
        assert d["depth_tier"] == "think"

    def test_empty_servers(self) -> None:
        """Test with no servers recommended."""
        decision = RoutingDecision(recommended_servers=[], reasoning=["no servers needed"], cost_estimate=0.0)
        assert decision.server_names == []
        assert decision.to_dict()["servers"] == []


class TestMCPRouterInit:
    """Tests for MCPRouter initialization."""

    def test_default_all_servers_available(self) -> None:
        """Test default router has all servers available."""
        router = MCPRouter()
        assert len(router.available) == len(MCPServer)
        assert router.cost_aware is True
        assert router.max_servers == 3

    def test_limited_and_unknown_servers(self) -> None:
        """Test router with limited and unknown server names."""
        router = MCPRouter(available_servers=["sequential", "nonexistent"])
        assert len(router.available) == 1
        assert MCPServer.SEQUENTIAL in router.available


class TestMCPRouterRouting:
    """Tests for MCPRouter.route method."""

    def test_route_no_args_empty_decision(self) -> None:
        """Test route with no arguments returns empty recommendation."""
        router = MCPRouter()
        decision = router.route()
        assert decision.recommended_servers == []

    @pytest.mark.parametrize(
        "task_type,expected_server",
        [
            ("test", "playwright"),
            ("debug", "sequential"),
            ("ui", "magic"),
            ("document", "context7"),
        ],
    )
    def test_route_task_type(self, task_type: str, expected_server: str) -> None:
        """Test task type routing to expected servers."""
        router = MCPRouter()
        decision = router.route(task_type=task_type)
        assert expected_server in decision.server_names

    def test_route_unknown_task_type(self) -> None:
        """Test unknown task type returns empty."""
        router = MCPRouter()
        decision = router.route(task_type="unknown_type")
        assert decision.recommended_servers == []

    def test_route_description_keywords(self) -> None:
        """Test description keyword routing."""
        router = MCPRouter()
        assert "playwright" in router.route(task_description="Write integration test").server_names
        assert "sequential" in router.route(task_description="Debug the auth flow").server_names
        assert router.route(task_description="Add a constant").recommended_servers == []

    def test_route_file_extensions(self) -> None:
        """Test file extension routing."""
        router = MCPRouter()
        assert "magic" in router.route(file_extensions=[".tsx"]).server_names
        assert "playwright" in router.route(file_extensions=[".test.ts"]).server_names
        assert router.route(file_extensions=[".py"]).recommended_servers == []

    def test_route_depth_tiers(self) -> None:
        """Test depth tier routing."""
        router = MCPRouter()
        assert router.route(depth_tier="quick").recommended_servers == []
        assert "sequential" in router.route(depth_tier="think").server_names
        think_hard = router.route(depth_tier="think-hard")
        assert "sequential" in think_hard.server_names
        assert "context7" in think_hard.server_names
        assert think_hard.depth_tier == "think-hard"

    def test_route_combined_inputs(self) -> None:
        """Test routing with multiple inputs combines results."""
        router = MCPRouter()
        decision = router.route(
            task_description="debug the ui component",
            task_type="test",
            file_extensions=[".tsx"],
        )
        assert len(decision.recommended_servers) > 0

    def test_route_max_servers_limit(self) -> None:
        """Test max_servers limits output."""
        router = MCPRouter(max_servers=1, cost_aware=False)
        decision = router.route(task_description="debug test refactor analyze ui design review document security")
        assert len(decision.recommended_servers) <= 1

    def test_route_limited_available_servers(self) -> None:
        """Test routing with limited available servers only returns available ones."""
        router = MCPRouter(available_servers=["sequential"])
        decision = router.route(task_type="test")
        for s in decision.recommended_servers:
            assert s == MCPServer.SEQUENTIAL


class TestMCPRouterGetEnvHint:
    """Tests for MCPRouter.get_env_hint."""

    def test_env_hint_with_servers(self) -> None:
        """Test env hint contains comma-separated servers."""
        decision = RoutingDecision(
            recommended_servers=[MCPServer.SEQUENTIAL, MCPServer.CONTEXT7],
            reasoning=[],
            cost_estimate=1.5,
        )
        router = MCPRouter()
        hint = router.get_env_hint(decision)
        assert hint["ZERG_MCP_HINT"] == "sequential,context7"

    def test_env_hint_empty_when_no_servers(self) -> None:
        """Test env hint is empty when no servers recommended."""
        decision = RoutingDecision(recommended_servers=[], reasoning=[], cost_estimate=0.0)
        router = MCPRouter()
        assert router.get_env_hint(decision) == {}


class TestRoutingTelemetry:
    """Tests for RoutingTelemetry collection."""

    def test_record_routing_and_summary(self) -> None:
        """Test recording events and getting summary."""
        tel = RoutingTelemetry()
        assert len(tel.events) == 0

        tel.record_routing("t1", ["sequential", "context7"], cost_estimate=1.5)
        tel.record_routing("t2", ["sequential"], cost_estimate=1.0)
        tel.record_routing("t3", ["playwright"], cost_estimate=2.0)

        summary = tel.get_summary()
        assert summary["total_routings"] == 3
        assert summary["server_frequency"]["sequential"] == 2
        assert summary["total_cost"] == 4.5

    def test_record_usage_updates_event(self) -> None:
        """Test record_usage updates the most recent matching event."""
        tel = RoutingTelemetry()
        tel.record_routing("t1", ["sequential"])
        tel.record_routing("t1", ["context7"])
        tel.record_usage("t1", ["context7"])
        assert tel.events[0].servers_used is None
        assert tel.events[1].servers_used == ["context7"]

    def test_record_usage_no_match(self) -> None:
        """Test record_usage with non-existent task_id is no-op."""
        tel = RoutingTelemetry()
        tel.record_routing("t1", ["sequential"])
        tel.record_usage("nonexistent", ["sequential"])
        assert tel.events[0].servers_used is None


class TestRoutingEvent:
    """Tests for RoutingEvent dataclass."""

    def test_creation_and_serialization(self) -> None:
        """Test event creation and to_dict."""
        event = RoutingEvent(
            task_id="task-1",
            servers_recommended=["sequential", "context7"],
            servers_used=["sequential"],
            cost_estimate=1.5,
        )
        assert event.task_id == "task-1"
        assert isinstance(event.timestamp, datetime)
        d = event.to_dict()
        assert d["servers_recommended"] == ["sequential", "context7"]
        assert d["servers_used"] == ["sequential"]
        datetime.fromisoformat(d["timestamp"])


class TestTaskCapabilityMap:
    """Tests for TASK_CAPABILITY_MAP constant."""

    def test_expected_task_types_present(self) -> None:
        """Test expected task types are defined with capabilities."""
        expected = ["test", "debug", "refactor", "analyze", "document", "ui", "design", "review", "security"]
        for task_type in expected:
            assert task_type in TASK_CAPABILITY_MAP
            assert len(TASK_CAPABILITY_MAP[task_type]) > 0


class TestCliMCPFlags:
    """Tests for CLI --mcp/--no-mcp flag integration."""

    def test_cli_mcp_flags_accepted(self) -> None:
        """Test CLI accepts --mcp and --no-mcp flags."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "--mcp" in result.output
