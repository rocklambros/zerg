"""Unit tests for ZERG analysis depth tier system."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from zerg.cli import cli
from zerg.depth_tiers import DepthContext, DepthRouter, DepthTier


class TestDepthTierEnum:
    """Tests for DepthTier enum values and properties."""

    def test_all_tiers_exist_with_properties(self) -> None:
        """Test all 5 tiers exist with budgets, servers, and descriptions."""
        assert len(DepthTier) == 5
        for tier in DepthTier:
            assert tier.token_budget > 0
            assert isinstance(tier.mcp_servers, list)
            assert len(tier.description) > 0

    def test_token_budgets_increase_monotonically(self) -> None:
        """Test token budgets increase with each tier."""
        tiers = [DepthTier.QUICK, DepthTier.STANDARD, DepthTier.THINK, DepthTier.THINK_HARD, DepthTier.ULTRATHINK]
        budgets = [t.token_budget for t in tiers]
        assert budgets == sorted(budgets)
        assert len(set(budgets)) == len(budgets)

    def test_mcp_servers_subset_hierarchy(self) -> None:
        """Test higher tiers include servers from lower tiers."""
        assert DepthTier.QUICK.mcp_servers == []
        assert DepthTier.THINK.mcp_servers == ["sequential"]
        think_hard = set(DepthTier.THINK_HARD.mcp_servers)
        ultrathink = set(DepthTier.ULTRATHINK.mcp_servers)
        assert {"sequential"}.issubset(think_hard)
        assert think_hard.issubset(ultrathink)


class TestDepthContext:
    """Tests for DepthContext dataclass."""

    @pytest.mark.parametrize(
        "tier,expected_budget,expected_env",
        [
            (DepthTier.QUICK, 1000, "quick"),
            (DepthTier.THINK, 4000, "think"),
            (DepthTier.ULTRATHINK, 32000, "ultrathink"),
        ],
    )
    def test_from_tier(self, tier: DepthTier, expected_budget: int, expected_env: str) -> None:
        """Test creating context from tier."""
        ctx = DepthContext.from_tier(tier)
        assert ctx.tier == tier
        assert ctx.token_budget == expected_budget
        assert ctx.env_value == expected_env

    def test_from_tier_preserves_mcp_list(self) -> None:
        """Test that from_tier creates independent mcp list copies."""
        ctx1 = DepthContext.from_tier(DepthTier.THINK)
        ctx2 = DepthContext.from_tier(DepthTier.THINK)
        ctx1.recommended_mcp.append("extra")
        assert "extra" not in ctx2.recommended_mcp


class TestDepthRouter:
    """Tests for DepthRouter routing logic."""

    def test_default_and_explicit_tier(self) -> None:
        """Test defaults to STANDARD and explicit tier overrides all."""
        router = DepthRouter()
        assert router.route().tier == DepthTier.STANDARD

        ctx = router.route(description="modernize everything", explicit_tier=DepthTier.QUICK, file_count=100)
        assert ctx.tier == DepthTier.QUICK

    @pytest.mark.parametrize(
        "keyword,expected_tier",
        [
            ("analyze", DepthTier.THINK),
            ("architect", DepthTier.THINK_HARD),
            ("modernize", DepthTier.ULTRATHINK),
        ],
    )
    def test_route_description_keywords(self, keyword: str, expected_tier: DepthTier) -> None:
        """Test keyword detection triggers correct tier."""
        router = DepthRouter()
        ctx = router.route(description=f"Please {keyword} this code")
        assert ctx.tier == expected_tier

    def test_route_highest_priority_wins(self) -> None:
        """Test that highest tier keyword wins when multiple match."""
        router = DepthRouter()
        ctx = router.route(description="critical analyze the system")
        assert ctx.tier == DepthTier.ULTRATHINK

    def test_route_scope_escalation(self) -> None:
        """Test scope escalation with file/directory counts."""
        router = DepthRouter()
        assert router.route(file_count=5, directory_count=1).tier == DepthTier.STANDARD
        assert router.route(file_count=10).tier == DepthTier.THINK
        assert router.route(file_count=25).tier == DepthTier.THINK_HARD
        assert router.route(directory_count=6).tier == DepthTier.THINK_HARD

    def test_route_scope_does_not_downgrade(self) -> None:
        """Test scope escalation never downgrades a keyword-detected tier."""
        router = DepthRouter()
        ctx = router.route(description="critical issue", file_count=1, directory_count=1)
        assert ctx.tier == DepthTier.ULTRATHINK

    def test_route_boundary_values(self) -> None:
        """Test boundary: exact thresholds do not trigger next tier."""
        router = DepthRouter()
        assert router.route(file_count=7).tier == DepthTier.STANDARD
        assert router.route(file_count=20).tier == DepthTier.THINK
        assert router.route(directory_count=2).tier == DepthTier.STANDARD
        assert router.route(directory_count=5).tier == DepthTier.THINK


class TestDepthRouterGetEnvVars:
    """Tests for DepthRouter.get_env_vars method."""

    def test_get_env_vars_all_tiers(self) -> None:
        """Test env vars match tier value for every tier."""
        router = DepthRouter()
        for tier in DepthTier:
            ctx = DepthContext.from_tier(tier)
            env_vars = router.get_env_vars(ctx)
            assert env_vars["ZERG_ANALYSIS_DEPTH"] == tier.value


class TestCliDepthFlags:
    """Tests for CLI depth flag integration."""

    def test_cli_help_shows_depth_flags(self) -> None:
        """Test CLI help includes depth flag options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "--quick" in result.output
        assert "--think" in result.output
        assert "--ultrathink" in result.output

    def test_cli_mutually_exclusive_depth_flags(self) -> None:
        """Test multiple depth flags produce a usage error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--quick", "--think", "status"])
        assert result.exit_code != 0
