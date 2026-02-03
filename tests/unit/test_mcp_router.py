"""Unit tests for ZERG MCP auto-routing system."""

from __future__ import annotations

from datetime import datetime

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

    def test_enum_values(self) -> None:
        """Test all expected enum members exist with correct values."""
        assert MCPServer.SEQUENTIAL.value == "sequential"
        assert MCPServer.CONTEXT7.value == "context7"
        assert MCPServer.PLAYWRIGHT.value == "playwright"
        assert MCPServer.MORPHLLM.value == "morphllm"
        assert MCPServer.MAGIC.value == "magic"
        assert MCPServer.SERENA.value == "serena"

    def test_enum_member_count(self) -> None:
        """Test exactly 6 MCP servers exist."""
        assert len(MCPServer) == 6

    def test_capabilities_sequential(self) -> None:
        """Test SEQUENTIAL capabilities."""
        caps = MCPServer.SEQUENTIAL.capabilities
        assert "analysis" in caps
        assert "debugging" in caps
        assert "architecture" in caps
        assert "planning" in caps

    def test_capabilities_context7(self) -> None:
        """Test CONTEXT7 capabilities."""
        caps = MCPServer.CONTEXT7.capabilities
        assert "documentation" in caps
        assert "library-lookup" in caps
        assert "framework-patterns" in caps

    def test_capabilities_playwright(self) -> None:
        """Test PLAYWRIGHT capabilities."""
        caps = MCPServer.PLAYWRIGHT.capabilities
        assert "browser-testing" in caps
        assert "e2e" in caps

    def test_capabilities_morphllm(self) -> None:
        """Test MORPHLLM capabilities."""
        caps = MCPServer.MORPHLLM.capabilities
        assert "bulk-edit" in caps
        assert "pattern-transform" in caps

    def test_capabilities_magic(self) -> None:
        """Test MAGIC capabilities."""
        caps = MCPServer.MAGIC.capabilities
        assert "ui-component" in caps
        assert "frontend" in caps

    def test_capabilities_serena(self) -> None:
        """Test SERENA capabilities."""
        caps = MCPServer.SERENA.capabilities
        assert "symbol-ops" in caps
        assert "lsp" in caps

    def test_all_servers_have_capabilities(self) -> None:
        """Test every server has at least one capability."""
        for server in MCPServer:
            assert len(server.capabilities) > 0, f"{server} has no capabilities"

    def test_cost_weight_baseline(self) -> None:
        """Test SEQUENTIAL is baseline cost weight 1.0."""
        assert MCPServer.SEQUENTIAL.cost_weight == 1.0

    def test_cost_weight_context7_cheapest(self) -> None:
        """Test CONTEXT7 has lowest cost weight."""
        assert MCPServer.CONTEXT7.cost_weight == 0.5

    def test_cost_weight_playwright_most_expensive(self) -> None:
        """Test PLAYWRIGHT has highest cost weight."""
        assert MCPServer.PLAYWRIGHT.cost_weight == 2.0

    def test_all_servers_have_positive_cost(self) -> None:
        """Test every server has positive cost weight."""
        for server in MCPServer:
            assert server.cost_weight > 0, f"{server} has non-positive cost"


class TestRoutingDecision:
    """Tests for RoutingDecision dataclass."""

    def test_creation(self) -> None:
        """Test basic RoutingDecision creation."""
        decision = RoutingDecision(
            recommended_servers=[MCPServer.SEQUENTIAL],
            reasoning=["test reason"],
            cost_estimate=1.0,
        )
        assert len(decision.recommended_servers) == 1
        assert decision.cost_estimate == 1.0
        assert decision.depth_tier is None

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        decision = RoutingDecision(
            recommended_servers=[MCPServer.SEQUENTIAL, MCPServer.CONTEXT7],
            reasoning=["reason1", "reason2"],
            cost_estimate=1.5,
            depth_tier="think",
        )
        d = decision.to_dict()

        assert d["servers"] == ["sequential", "context7"]
        assert d["reasoning"] == ["reason1", "reason2"]
        assert d["cost_estimate"] == 1.5
        assert d["depth_tier"] == "think"

    def test_server_names_property(self) -> None:
        """Test server_names returns string names."""
        decision = RoutingDecision(
            recommended_servers=[MCPServer.PLAYWRIGHT, MCPServer.MAGIC],
            reasoning=[],
            cost_estimate=3.5,
        )
        assert decision.server_names == ["playwright", "magic"]

    def test_server_names_empty(self) -> None:
        """Test server_names with no servers."""
        decision = RoutingDecision(
            recommended_servers=[],
            reasoning=["no servers needed"],
            cost_estimate=0.0,
        )
        assert decision.server_names == []

    def test_to_dict_empty_servers(self) -> None:
        """Test to_dict with empty server list."""
        decision = RoutingDecision(recommended_servers=[], reasoning=[], cost_estimate=0.0)
        d = decision.to_dict()
        assert d["servers"] == []


class TestMCPRouterInit:
    """Tests for MCPRouter initialization."""

    def test_default_all_servers_available(self) -> None:
        """Test default router has all servers available."""
        router = MCPRouter()
        assert len(router.available) == len(MCPServer)

    def test_limited_available_servers(self) -> None:
        """Test router with limited server list."""
        router = MCPRouter(available_servers=["sequential", "context7"])
        assert len(router.available) == 2
        assert MCPServer.SEQUENTIAL in router.available
        assert MCPServer.CONTEXT7 in router.available

    def test_unknown_server_names_ignored(self) -> None:
        """Test unknown server names are silently ignored."""
        router = MCPRouter(available_servers=["sequential", "nonexistent"])
        assert len(router.available) == 1
        assert MCPServer.SEQUENTIAL in router.available

    def test_empty_available_servers(self) -> None:
        """Test router with empty server list."""
        router = MCPRouter(available_servers=[])
        assert len(router.available) == 0

    def test_cost_aware_default(self) -> None:
        """Test cost_aware defaults to True."""
        router = MCPRouter()
        assert router.cost_aware is True

    def test_max_servers_default(self) -> None:
        """Test max_servers defaults to 3."""
        router = MCPRouter()
        assert router.max_servers == 3


class TestMCPRouterRouting:
    """Tests for MCPRouter.route method."""

    def test_route_no_args_empty_decision(self) -> None:
        """Test route with no arguments returns empty recommendation."""
        router = MCPRouter()
        decision = router.route()
        assert decision.recommended_servers == []
        assert "no specific MCP servers needed" in decision.reasoning

    def test_route_task_type_test(self) -> None:
        """Test task type 'test' routes to playwright."""
        router = MCPRouter()
        decision = router.route(task_type="test")
        server_names = decision.server_names
        assert "playwright" in server_names

    def test_route_task_type_debug(self) -> None:
        """Test task type 'debug' routes to sequential."""
        router = MCPRouter()
        decision = router.route(task_type="debug")
        server_names = decision.server_names
        assert "sequential" in server_names

    def test_route_task_type_refactor(self) -> None:
        """Test task type 'refactor' routes to morphllm and serena."""
        router = MCPRouter()
        decision = router.route(task_type="refactor")
        server_names = decision.server_names
        assert "morphllm" in server_names or "serena" in server_names

    def test_route_task_type_ui(self) -> None:
        """Test task type 'ui' routes to magic."""
        router = MCPRouter()
        decision = router.route(task_type="ui")
        server_names = decision.server_names
        assert "magic" in server_names

    def test_route_task_type_document(self) -> None:
        """Test task type 'document' routes to context7."""
        router = MCPRouter()
        decision = router.route(task_type="document")
        server_names = decision.server_names
        assert "context7" in server_names

    def test_route_unknown_task_type(self) -> None:
        """Test unknown task type returns empty."""
        router = MCPRouter()
        decision = router.route(task_type="unknown_type")
        assert decision.recommended_servers == []

    def test_route_description_keyword_test(self) -> None:
        """Test description with 'test' keyword routes to playwright."""
        router = MCPRouter()
        decision = router.route(task_description="Write integration test for login")
        assert "playwright" in decision.server_names

    def test_route_description_keyword_debug(self) -> None:
        """Test description with 'debug' keyword routes to sequential."""
        router = MCPRouter()
        decision = router.route(task_description="Debug the authentication flow")
        assert "sequential" in decision.server_names

    def test_route_description_keyword_ui(self) -> None:
        """Test description with 'ui' keyword routes to magic."""
        router = MCPRouter()
        decision = router.route(task_description="Build the UI dashboard")
        assert "magic" in decision.server_names

    def test_route_description_no_keywords(self) -> None:
        """Test description without keywords returns empty."""
        router = MCPRouter()
        decision = router.route(task_description="Add a constant value")
        assert decision.recommended_servers == []

    def test_route_file_extensions_tsx(self) -> None:
        """Test .tsx extension routes to frontend servers."""
        router = MCPRouter()
        decision = router.route(file_extensions=[".tsx"])
        assert "magic" in decision.server_names

    def test_route_file_extensions_jsx(self) -> None:
        """Test .jsx extension routes to frontend servers."""
        router = MCPRouter()
        decision = router.route(file_extensions=[".jsx"])
        assert "magic" in decision.server_names

    def test_route_file_extensions_css(self) -> None:
        """Test .css extension routes to frontend servers."""
        router = MCPRouter()
        decision = router.route(file_extensions=[".css"])
        assert "magic" in decision.server_names

    def test_route_file_extensions_test_ts(self) -> None:
        """Test .test.ts extension routes to testing servers."""
        router = MCPRouter()
        decision = router.route(file_extensions=[".test.ts"])
        assert "playwright" in decision.server_names

    def test_route_file_extensions_py_no_match(self) -> None:
        """Test .py extension alone does not trigger routing."""
        router = MCPRouter()
        decision = router.route(file_extensions=[".py"])
        assert decision.recommended_servers == []

    def test_route_depth_tier_think(self) -> None:
        """Test depth tier 'think' adds sequential."""
        router = MCPRouter()
        decision = router.route(depth_tier="think")
        assert "sequential" in decision.server_names

    def test_route_depth_tier_think_hard(self) -> None:
        """Test depth tier 'think-hard' adds sequential and context7."""
        router = MCPRouter()
        decision = router.route(depth_tier="think-hard")
        names = decision.server_names
        assert "sequential" in names
        assert "context7" in names

    def test_route_depth_tier_invalid(self) -> None:
        """Test invalid depth tier is handled gracefully."""
        router = MCPRouter()
        decision = router.route(depth_tier="invalid-tier")
        # Should not crash; may return empty or based on other inputs
        assert isinstance(decision, RoutingDecision)

    def test_route_depth_tier_quick_no_servers(self) -> None:
        """Test depth tier 'quick' adds no servers."""
        router = MCPRouter()
        decision = router.route(depth_tier="quick")
        assert decision.recommended_servers == []

    def test_route_combined_inputs(self) -> None:
        """Test routing with multiple inputs combines results."""
        router = MCPRouter()
        decision = router.route(
            task_description="debug the ui component",
            task_type="test",
            file_extensions=[".tsx"],
        )
        # Should have multiple servers from combined signals
        assert len(decision.recommended_servers) > 0

    def test_route_cost_estimate_calculated(self) -> None:
        """Test cost estimate is sum of server weights."""
        router = MCPRouter(cost_aware=False, max_servers=10)
        decision = router.route(task_type="debug")
        if decision.recommended_servers:
            expected_cost = sum(s.cost_weight for s in decision.recommended_servers)
            assert decision.cost_estimate == expected_cost

    def test_route_max_servers_limit(self) -> None:
        """Test max_servers limits output."""
        router = MCPRouter(max_servers=1, cost_aware=False)
        decision = router.route(task_description="debug test refactor analyze ui design review document security")
        assert len(decision.recommended_servers) <= 1

    def test_route_max_servers_custom(self) -> None:
        """Test custom max_servers value."""
        router = MCPRouter(max_servers=2)
        decision = router.route(task_description="debug test refactor analyze ui design review document")
        assert len(decision.recommended_servers) <= 2

    def test_route_cost_aware_optimization(self) -> None:
        """Test cost-aware mode optimizes server selection."""
        router = MCPRouter(cost_aware=True, max_servers=2)
        decision = router.route(task_description="debug test refactor analyze ui design review document")
        assert len(decision.recommended_servers) <= 2

    def test_route_limited_available_servers(self) -> None:
        """Test routing with limited available servers only returns available ones."""
        router = MCPRouter(available_servers=["sequential"])
        decision = router.route(task_type="test")
        # Playwright is not available, so should not appear
        for s in decision.recommended_servers:
            assert s == MCPServer.SEQUENTIAL

    def test_route_reasoning_populated(self) -> None:
        """Test reasoning list is populated with explanations."""
        router = MCPRouter()
        decision = router.route(task_type="debug")
        assert len(decision.reasoning) > 0
        assert any("debug" in r for r in decision.reasoning)

    def test_route_depth_tier_stored(self) -> None:
        """Test depth_tier is stored in decision."""
        router = MCPRouter()
        decision = router.route(depth_tier="think")
        assert decision.depth_tier == "think"


class TestMCPRouterGetEnvHint:
    """Tests for MCPRouter.get_env_hint."""

    def test_env_hint_with_servers(self) -> None:
        """Test env hint contains ZERG_MCP_HINT."""
        router = MCPRouter()
        decision = router.route(task_type="debug")
        hint = router.get_env_hint(decision)
        if decision.recommended_servers:
            assert "ZERG_MCP_HINT" in hint
            assert "sequential" in hint["ZERG_MCP_HINT"]

    def test_env_hint_empty_when_no_servers(self) -> None:
        """Test env hint is empty when no servers recommended."""
        decision = RoutingDecision(recommended_servers=[], reasoning=[], cost_estimate=0.0)
        router = MCPRouter()
        hint = router.get_env_hint(decision)
        assert hint == {}

    def test_env_hint_comma_separated(self) -> None:
        """Test multiple servers are comma-separated."""
        decision = RoutingDecision(
            recommended_servers=[MCPServer.SEQUENTIAL, MCPServer.CONTEXT7],
            reasoning=[],
            cost_estimate=1.5,
        )
        router = MCPRouter()
        hint = router.get_env_hint(decision)
        assert hint["ZERG_MCP_HINT"] == "sequential,context7"


class TestRoutingEvent:
    """Tests for RoutingEvent dataclass."""

    def test_creation(self) -> None:
        """Test basic event creation."""
        event = RoutingEvent(
            task_id="task-1",
            servers_recommended=["sequential"],
            cost_estimate=1.0,
        )
        assert event.task_id == "task-1"
        assert event.servers_used is None
        assert isinstance(event.timestamp, datetime)

    def test_to_dict(self) -> None:
        """Test event serialization."""
        event = RoutingEvent(
            task_id="task-2",
            servers_recommended=["sequential", "context7"],
            servers_used=["sequential"],
            cost_estimate=1.5,
        )
        d = event.to_dict()
        assert d["task_id"] == "task-2"
        assert d["servers_recommended"] == ["sequential", "context7"]
        assert d["servers_used"] == ["sequential"]
        assert d["cost_estimate"] == 1.5
        assert "timestamp" in d

    def test_to_dict_timestamp_iso_format(self) -> None:
        """Test timestamp is serialized as ISO format string."""
        event = RoutingEvent(task_id="task-3", servers_recommended=[], cost_estimate=0.0)
        d = event.to_dict()
        # Should be parseable as datetime
        datetime.fromisoformat(d["timestamp"])


class TestRoutingTelemetry:
    """Tests for RoutingTelemetry collection."""

    def test_empty_telemetry(self) -> None:
        """Test fresh telemetry has no events."""
        tel = RoutingTelemetry()
        assert len(tel.events) == 0

    def test_record_event(self) -> None:
        """Test recording a single event."""
        tel = RoutingTelemetry()
        event = RoutingEvent(task_id="t1", servers_recommended=["sequential"], cost_estimate=1.0)
        tel.record(event)
        assert len(tel.events) == 1

    def test_record_routing(self) -> None:
        """Test record_routing convenience method."""
        tel = RoutingTelemetry()
        tel.record_routing("t1", ["sequential", "context7"], cost_estimate=1.5)
        assert len(tel.events) == 1
        assert tel.events[0].task_id == "t1"
        assert tel.events[0].servers_recommended == ["sequential", "context7"]

    def test_record_usage(self) -> None:
        """Test recording actual server usage."""
        tel = RoutingTelemetry()
        tel.record_routing("t1", ["sequential", "context7"])
        tel.record_usage("t1", ["sequential"])
        assert tel.events[0].servers_used == ["sequential"]

    def test_record_usage_updates_most_recent(self) -> None:
        """Test record_usage updates the most recent matching event."""
        tel = RoutingTelemetry()
        tel.record_routing("t1", ["sequential"])
        tel.record_routing("t1", ["context7"])
        tel.record_usage("t1", ["context7"])
        # First event should still be None
        assert tel.events[0].servers_used is None
        # Second event should be updated
        assert tel.events[1].servers_used == ["context7"]

    def test_record_usage_no_match(self) -> None:
        """Test record_usage with non-existent task_id is no-op."""
        tel = RoutingTelemetry()
        tel.record_routing("t1", ["sequential"])
        tel.record_usage("nonexistent", ["sequential"])
        # Original event unchanged
        assert tel.events[0].servers_used is None

    def test_get_summary_empty(self) -> None:
        """Test summary for empty telemetry."""
        tel = RoutingTelemetry()
        summary = tel.get_summary()
        assert summary["total_routings"] == 0
        assert summary["server_frequency"] == {}
        assert summary["total_cost"] == 0.0

    def test_get_summary_with_events(self) -> None:
        """Test summary with multiple events."""
        tel = RoutingTelemetry()
        tel.record_routing("t1", ["sequential", "context7"], cost_estimate=1.5)
        tel.record_routing("t2", ["sequential"], cost_estimate=1.0)
        tel.record_routing("t3", ["playwright"], cost_estimate=2.0)

        summary = tel.get_summary()
        assert summary["total_routings"] == 3
        assert summary["server_frequency"]["sequential"] == 2
        assert summary["server_frequency"]["context7"] == 1
        assert summary["server_frequency"]["playwright"] == 1
        assert summary["total_cost"] == 4.5
        assert summary["avg_cost"] == 1.5

    def test_clear(self) -> None:
        """Test clearing all events."""
        tel = RoutingTelemetry()
        tel.record_routing("t1", ["sequential"])
        tel.record_routing("t2", ["context7"])
        tel.clear()
        assert len(tel.events) == 0
        assert tel.get_summary()["total_routings"] == 0

    def test_events_returns_copy(self) -> None:
        """Test events property returns a copy."""
        tel = RoutingTelemetry()
        tel.record_routing("t1", ["sequential"])
        events = tel.events
        events.append(RoutingEvent(task_id="t2", servers_recommended=[], cost_estimate=0.0))
        # Original should be unchanged
        assert len(tel.events) == 1


class TestTaskCapabilityMap:
    """Tests for TASK_CAPABILITY_MAP constant."""

    def test_all_task_types_have_capabilities(self) -> None:
        """Test every task type maps to at least one capability."""
        for task_type, caps in TASK_CAPABILITY_MAP.items():
            assert len(caps) > 0, f"Task type '{task_type}' has no capabilities"

    def test_expected_task_types_present(self) -> None:
        """Test expected task types are defined."""
        expected = ["test", "debug", "refactor", "analyze", "document", "ui", "design", "review", "security"]
        for task_type in expected:
            assert task_type in TASK_CAPABILITY_MAP


class TestCliMCPFlags:
    """Tests for CLI --mcp/--no-mcp flag integration."""

    def test_cli_help_shows_mcp_flag(self) -> None:
        """Test CLI help includes --mcp/--no-mcp option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "--mcp" in result.output

    def test_cli_mcp_flag_accepted(self) -> None:
        """Test CLI accepts --mcp flag."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--mcp", "--help"])
        assert result.exit_code == 0

    def test_cli_no_mcp_flag_accepted(self) -> None:
        """Test CLI accepts --no-mcp flag."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--no-mcp", "--help"])
        assert result.exit_code == 0
