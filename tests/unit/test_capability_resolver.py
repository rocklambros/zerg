"""Unit tests for CapabilityResolver and ResolvedCapabilities."""

from __future__ import annotations

import pytest

from zerg.capability_resolver import CapabilityResolver, ResolvedCapabilities
from zerg.config import ZergConfig

# ---------------------------------------------------------------------------
# ResolvedCapabilities dataclass tests
# ---------------------------------------------------------------------------


class TestResolvedCapabilitiesDefaults:
    """Verify ResolvedCapabilities default field values."""

    def test_defaults(self):
        rc = ResolvedCapabilities()
        assert rc.compact is True
        assert rc.loop_enabled is True
        assert rc.depth_tier == "standard"
        assert rc.mode == "precision"
        assert rc.tdd is False
        assert rc.rules_enabled is True
        assert rc.gates_enabled is True
        assert rc.token_budget == 2000
        assert rc.loop_iterations == 5
        assert rc.staleness_threshold == 300
        assert rc.mcp_hint == ""


class TestResolvedCapabilitiesToEnvVars:
    """Verify to_env_vars() key presence, value formatting, and conditional keys."""

    EXPECTED_KEYS = {
        "ZERG_ANALYSIS_DEPTH",
        "ZERG_TOKEN_BUDGET",
        "ZERG_COMPACT_MODE",
        "ZERG_BEHAVIORAL_MODE",
        "ZERG_TDD_MODE",
        "ZERG_RULES_ENABLED",
        "ZERG_LOOP_ENABLED",
        "ZERG_LOOP_ITERATIONS",
        "ZERG_VERIFICATION_GATES",
        "ZERG_STALENESS_THRESHOLD",
    }

    def test_to_env_vars_keys(self):
        """to_env_vars() returns all expected ZERG_* keys (no mcp_hint by default)."""
        env = ResolvedCapabilities().to_env_vars()
        assert set(env.keys()) == self.EXPECTED_KEYS

    def test_to_env_vars_values(self):
        """Boolean fields are stringified as '0'/'1'; int fields as str."""
        rc = ResolvedCapabilities(
            compact=True,
            tdd=False,
            rules_enabled=True,
            loop_enabled=False,
            gates_enabled=True,
            token_budget=4000,
            loop_iterations=10,
            staleness_threshold=600,
        )
        env = rc.to_env_vars()

        # Booleans -> "0" / "1"
        assert env["ZERG_COMPACT_MODE"] == "1"
        assert env["ZERG_TDD_MODE"] == "0"
        assert env["ZERG_RULES_ENABLED"] == "1"
        assert env["ZERG_LOOP_ENABLED"] == "0"
        assert env["ZERG_VERIFICATION_GATES"] == "1"

        # Ints -> str
        assert env["ZERG_TOKEN_BUDGET"] == "4000"
        assert env["ZERG_LOOP_ITERATIONS"] == "10"
        assert env["ZERG_STALENESS_THRESHOLD"] == "600"

    def test_to_env_vars_mcp_hint_omitted_when_empty(self):
        """ZERG_MCP_HINT is not present when mcp_hint is empty string."""
        env = ResolvedCapabilities(mcp_hint="").to_env_vars()
        assert "ZERG_MCP_HINT" not in env

    def test_to_env_vars_mcp_hint_included(self):
        """ZERG_MCP_HINT is present when mcp_hint is set."""
        env = ResolvedCapabilities(mcp_hint="sequential,context7").to_env_vars()
        assert "ZERG_MCP_HINT" in env
        assert env["ZERG_MCP_HINT"] == "sequential,context7"


# ---------------------------------------------------------------------------
# CapabilityResolver.resolve() tests
# ---------------------------------------------------------------------------


class TestCapabilityResolverResolve:
    """Verify CapabilityResolver.resolve() with various inputs."""

    @pytest.fixture
    def resolver(self):
        return CapabilityResolver()

    @pytest.fixture
    def default_config(self):
        return ZergConfig()

    def test_resolve_defaults(self, resolver, default_config):
        """resolve({}) produces sensible defaults."""
        rc = resolver.resolve(cli_flags={}, config=default_config)
        assert isinstance(rc, ResolvedCapabilities)
        assert rc.depth_tier == "standard"
        assert rc.compact is True
        assert rc.tdd is False

    def test_resolve_cli_depth_override(self, resolver, default_config):
        """CLI depth flag overrides task-graph auto-detection."""
        rc = resolver.resolve(cli_flags={"depth": "think"}, config=default_config)
        assert rc.depth_tier == "think"
        assert rc.token_budget == 4000

    def test_resolve_cli_tdd(self, resolver, default_config):
        """CLI tdd=True enables TDD mode."""
        rc = resolver.resolve(cli_flags={"tdd": True}, config=default_config)
        assert rc.tdd is True

    def test_resolve_compact_off(self, resolver, default_config):
        """CLI compact=False disables compact mode."""
        rc = resolver.resolve(cli_flags={"compact": False}, config=default_config)
        assert rc.compact is False

    def test_resolve_loop_off(self, resolver, default_config):
        """CLI loop=False disables improvement loops."""
        rc = resolver.resolve(cli_flags={"loop": False}, config=default_config, command="rush")
        assert rc.loop_enabled is False

    def test_resolve_iterations_override(self, resolver, default_config):
        """CLI iterations value overrides config default."""
        rc = resolver.resolve(cli_flags={"iterations": 10}, config=default_config)
        assert rc.loop_iterations == 10

    def test_resolve_deepest_wins_from_task_graph(self, resolver, default_config):
        """When no CLI depth flag, deepest task tier wins across task graph."""
        task_graph = {
            "tasks": [
                {
                    "id": "TASK-001",
                    "description": "simple change",
                    "files": {"create": ["a.py"]},
                },
                {
                    "id": "TASK-002",
                    "description": (
                        "complex architectural refactor spanning security, performance, and database migration layers"
                    ),
                    "files": {"modify": [f"src/module_{i}.py" for i in range(15)]},
                },
            ]
        }
        rc = resolver.resolve(
            cli_flags={},
            config=default_config,
            task_graph=task_graph,
        )
        # The second task is complex enough that the auto-router should
        # assign a tier deeper than "standard".  Exact tier depends on
        # DepthRouter heuristics, so we just verify it is not standard.
        assert rc.depth_tier != "standard" or rc.token_budget > 2000

    def test_resolve_with_config(self, resolver):
        """Config values (e.g. rules, verification) are picked up."""
        config = ZergConfig()
        rc = resolver.resolve(cli_flags={}, config=config)
        # ZergConfig defaults should flow through
        assert rc.rules_enabled == config.rules.enabled
        assert rc.gates_enabled == config.verification.require_before_completion
        assert rc.staleness_threshold == config.verification.staleness_threshold_seconds
