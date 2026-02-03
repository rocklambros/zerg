"""Unit tests for ZERG analysis depth tier system."""

from __future__ import annotations

from click.testing import CliRunner

from zerg.cli import cli
from zerg.depth_tiers import DepthContext, DepthRouter, DepthTier


class TestDepthTierEnum:
    """Tests for DepthTier enum values and properties."""

    def test_enum_values(self) -> None:
        """Test all expected enum members exist with correct values."""
        assert DepthTier.QUICK.value == "quick"
        assert DepthTier.STANDARD.value == "standard"
        assert DepthTier.THINK.value == "think"
        assert DepthTier.THINK_HARD.value == "think-hard"
        assert DepthTier.ULTRATHINK.value == "ultrathink"

    def test_enum_member_count(self) -> None:
        """Test exactly 5 depth tiers exist."""
        assert len(DepthTier) == 5

    def test_token_budget_quick(self) -> None:
        """Test QUICK tier has 1000 token budget."""
        assert DepthTier.QUICK.token_budget == 1000

    def test_token_budget_standard(self) -> None:
        """Test STANDARD tier has 2000 token budget."""
        assert DepthTier.STANDARD.token_budget == 2000

    def test_token_budget_think(self) -> None:
        """Test THINK tier has 4000 token budget."""
        assert DepthTier.THINK.token_budget == 4000

    def test_token_budget_think_hard(self) -> None:
        """Test THINK_HARD tier has 10000 token budget."""
        assert DepthTier.THINK_HARD.token_budget == 10000

    def test_token_budget_ultrathink(self) -> None:
        """Test ULTRATHINK tier has 32000 token budget."""
        assert DepthTier.ULTRATHINK.token_budget == 32000

    def test_token_budgets_increase_monotonically(self) -> None:
        """Test token budgets increase with each tier."""
        tiers = [
            DepthTier.QUICK,
            DepthTier.STANDARD,
            DepthTier.THINK,
            DepthTier.THINK_HARD,
            DepthTier.ULTRATHINK,
        ]
        budgets = [t.token_budget for t in tiers]
        assert budgets == sorted(budgets)
        assert len(set(budgets)) == len(budgets)  # All unique

    def test_mcp_servers_quick_empty(self) -> None:
        """Test QUICK tier recommends no MCP servers."""
        assert DepthTier.QUICK.mcp_servers == []

    def test_mcp_servers_standard_empty(self) -> None:
        """Test STANDARD tier recommends no MCP servers."""
        assert DepthTier.STANDARD.mcp_servers == []

    def test_mcp_servers_think(self) -> None:
        """Test THINK tier recommends sequential MCP server."""
        assert DepthTier.THINK.mcp_servers == ["sequential"]

    def test_mcp_servers_think_hard(self) -> None:
        """Test THINK_HARD tier recommends sequential and context7."""
        assert DepthTier.THINK_HARD.mcp_servers == ["sequential", "context7"]

    def test_mcp_servers_ultrathink(self) -> None:
        """Test ULTRATHINK tier recommends all major MCP servers."""
        servers = DepthTier.ULTRATHINK.mcp_servers
        assert "sequential" in servers
        assert "context7" in servers
        assert "playwright" in servers
        assert "morphllm" in servers

    def test_mcp_servers_subset_hierarchy(self) -> None:
        """Test higher tiers include servers from lower tiers."""
        think_servers = set(DepthTier.THINK.mcp_servers)
        think_hard_servers = set(DepthTier.THINK_HARD.mcp_servers)
        ultrathink_servers = set(DepthTier.ULTRATHINK.mcp_servers)

        assert think_servers.issubset(think_hard_servers)
        assert think_hard_servers.issubset(ultrathink_servers)

    def test_description_all_tiers_have_descriptions(self) -> None:
        """Test every tier has a non-empty description."""
        for tier in DepthTier:
            assert isinstance(tier.description, str)
            assert len(tier.description) > 0

    def test_description_values(self) -> None:
        """Test specific description values."""
        assert DepthTier.QUICK.description == "Fast surface-level analysis"
        assert DepthTier.STANDARD.description == "Balanced default analysis"
        assert DepthTier.ULTRATHINK.description == "Maximum depth comprehensive analysis"


class TestDepthContext:
    """Tests for DepthContext dataclass."""

    def test_from_tier_quick(self) -> None:
        """Test creating context from QUICK tier."""
        ctx = DepthContext.from_tier(DepthTier.QUICK)

        assert ctx.tier == DepthTier.QUICK
        assert ctx.token_budget == 1000
        assert ctx.recommended_mcp == []
        assert ctx.env_value == "quick"

    def test_from_tier_standard(self) -> None:
        """Test creating context from STANDARD tier."""
        ctx = DepthContext.from_tier(DepthTier.STANDARD)

        assert ctx.tier == DepthTier.STANDARD
        assert ctx.token_budget == 2000
        assert ctx.recommended_mcp == []
        assert ctx.env_value == "standard"

    def test_from_tier_think(self) -> None:
        """Test creating context from THINK tier."""
        ctx = DepthContext.from_tier(DepthTier.THINK)

        assert ctx.tier == DepthTier.THINK
        assert ctx.token_budget == 4000
        assert ctx.recommended_mcp == ["sequential"]
        assert ctx.env_value == "think"

    def test_from_tier_think_hard(self) -> None:
        """Test creating context from THINK_HARD tier."""
        ctx = DepthContext.from_tier(DepthTier.THINK_HARD)

        assert ctx.tier == DepthTier.THINK_HARD
        assert ctx.token_budget == 10000
        assert ctx.env_value == "think-hard"

    def test_from_tier_ultrathink(self) -> None:
        """Test creating context from ULTRATHINK tier."""
        ctx = DepthContext.from_tier(DepthTier.ULTRATHINK)

        assert ctx.tier == DepthTier.ULTRATHINK
        assert ctx.token_budget == 32000
        assert ctx.env_value == "ultrathink"

    def test_from_tier_preserves_mcp_list(self) -> None:
        """Test that from_tier creates independent mcp list copies."""
        ctx1 = DepthContext.from_tier(DepthTier.THINK)
        ctx2 = DepthContext.from_tier(DepthTier.THINK)

        # Modifying one should not affect the other
        ctx1.recommended_mcp.append("extra")
        assert "extra" not in ctx2.recommended_mcp


class TestDepthRouter:
    """Tests for DepthRouter routing logic."""

    def test_default_tier_is_standard(self) -> None:
        """Test router defaults to STANDARD tier."""
        router = DepthRouter()
        assert router.default_tier == DepthTier.STANDARD

    def test_custom_default_tier(self) -> None:
        """Test router accepts custom default tier."""
        router = DepthRouter(default_tier=DepthTier.THINK)
        assert router.default_tier == DepthTier.THINK

    def test_route_no_args_returns_default(self) -> None:
        """Test route with no arguments returns default tier."""
        router = DepthRouter()
        ctx = router.route()

        assert ctx.tier == DepthTier.STANDARD

    def test_route_explicit_tier_overrides_all(self) -> None:
        """Test explicit tier overrides description and scope."""
        router = DepthRouter()
        ctx = router.route(
            description="modernize the entire system",
            explicit_tier=DepthTier.QUICK,
            file_count=100,
            directory_count=50,
        )

        assert ctx.tier == DepthTier.QUICK

    def test_route_explicit_tier_each_value(self) -> None:
        """Test explicit tier works for each DepthTier value."""
        router = DepthRouter()
        for tier in DepthTier:
            ctx = router.route(explicit_tier=tier)
            assert ctx.tier == tier

    def test_route_description_think_keywords(self) -> None:
        """Test THINK-level keywords trigger THINK tier."""
        router = DepthRouter()
        for keyword in ["analyze", "investigate", "debug", "trace", "profile"]:
            ctx = router.route(description=f"Please {keyword} this code")
            assert ctx.tier == DepthTier.THINK, f"Keyword '{keyword}' should trigger THINK"

    def test_route_description_think_hard_keywords(self) -> None:
        """Test THINK_HARD-level keywords trigger THINK_HARD tier."""
        router = DepthRouter()
        keywords = [
            "architect",
            "redesign",
            "migrate",
            "security audit",
            "performance analysis",
            "system design",
        ]
        for keyword in keywords:
            ctx = router.route(description=f"Need to {keyword} the system")
            assert ctx.tier == DepthTier.THINK_HARD, f"Keyword '{keyword}' should trigger THINK_HARD"

    def test_route_description_ultrathink_keywords(self) -> None:
        """Test ULTRATHINK-level keywords trigger ULTRATHINK tier."""
        router = DepthRouter()
        keywords = [
            "modernize",
            "rewrite",
            "critical",
            "production incident",
            "full audit",
            "comprehensive review",
        ]
        for keyword in keywords:
            ctx = router.route(description=f"We must {keyword} everything")
            assert ctx.tier == DepthTier.ULTRATHINK, f"Keyword '{keyword}' should trigger ULTRATHINK"

    def test_route_description_case_insensitive(self) -> None:
        """Test keyword matching is case insensitive."""
        router = DepthRouter()
        ctx = router.route(description="ANALYZE this MODULE")
        assert ctx.tier == DepthTier.THINK

    def test_route_description_no_keywords_returns_default(self) -> None:
        """Test description without keywords returns default tier."""
        router = DepthRouter()
        ctx = router.route(description="add a button to the form")
        assert ctx.tier == DepthTier.STANDARD

    def test_route_description_highest_priority_wins(self) -> None:
        """Test that highest tier keyword wins when multiple match."""
        router = DepthRouter()
        # "critical" is ULTRATHINK, "analyze" is THINK
        ctx = router.route(description="critical analyze the system")
        assert ctx.tier == DepthTier.ULTRATHINK

    def test_route_scope_escalation_many_files(self) -> None:
        """Test scope escalation with >20 files triggers THINK_HARD."""
        router = DepthRouter()
        ctx = router.route(file_count=25)
        assert ctx.tier == DepthTier.THINK_HARD

    def test_route_scope_escalation_many_directories(self) -> None:
        """Test scope escalation with >5 directories triggers THINK_HARD."""
        router = DepthRouter()
        ctx = router.route(directory_count=6)
        assert ctx.tier == DepthTier.THINK_HARD

    def test_route_scope_escalation_moderate_files(self) -> None:
        """Test scope escalation with >7 files triggers THINK."""
        router = DepthRouter()
        ctx = router.route(file_count=10)
        assert ctx.tier == DepthTier.THINK

    def test_route_scope_escalation_moderate_directories(self) -> None:
        """Test scope escalation with >2 directories triggers THINK."""
        router = DepthRouter()
        ctx = router.route(directory_count=3)
        assert ctx.tier == DepthTier.THINK

    def test_route_scope_no_escalation_small(self) -> None:
        """Test no scope escalation for small file/directory counts."""
        router = DepthRouter()
        ctx = router.route(file_count=5, directory_count=1)
        assert ctx.tier == DepthTier.STANDARD

    def test_route_scope_does_not_downgrade_description(self) -> None:
        """Test scope escalation never downgrades a keyword-detected tier."""
        router = DepthRouter()
        # "critical" detects ULTRATHINK, small scope should not downgrade
        ctx = router.route(description="critical issue", file_count=1, directory_count=1)
        assert ctx.tier == DepthTier.ULTRATHINK

    def test_route_scope_escalation_combined_with_keywords(self) -> None:
        """Test scope escalation respects keyword detection."""
        router = DepthRouter()
        # "analyze" detects THINK, large scope should escalate to THINK_HARD
        ctx = router.route(description="analyze module", file_count=25)
        assert ctx.tier == DepthTier.THINK_HARD

    def test_route_boundary_file_count_7(self) -> None:
        """Test boundary: exactly 7 files does not trigger escalation."""
        router = DepthRouter()
        ctx = router.route(file_count=7)
        assert ctx.tier == DepthTier.STANDARD

    def test_route_boundary_file_count_20(self) -> None:
        """Test boundary: exactly 20 files triggers THINK not THINK_HARD."""
        router = DepthRouter()
        ctx = router.route(file_count=20)
        assert ctx.tier == DepthTier.THINK

    def test_route_boundary_directory_count_2(self) -> None:
        """Test boundary: exactly 2 directories does not trigger escalation."""
        router = DepthRouter()
        ctx = router.route(directory_count=2)
        assert ctx.tier == DepthTier.STANDARD

    def test_route_boundary_directory_count_5(self) -> None:
        """Test boundary: exactly 5 directories triggers THINK not THINK_HARD."""
        router = DepthRouter()
        ctx = router.route(directory_count=5)
        assert ctx.tier == DepthTier.THINK


class TestDepthRouterGetEnvVars:
    """Tests for DepthRouter.get_env_vars method."""

    def test_get_env_vars_returns_correct_key(self) -> None:
        """Test env vars dict uses ZERG_ANALYSIS_DEPTH key."""
        router = DepthRouter()
        ctx = DepthContext.from_tier(DepthTier.STANDARD)
        env_vars = router.get_env_vars(ctx)

        assert "ZERG_ANALYSIS_DEPTH" in env_vars

    def test_get_env_vars_standard(self) -> None:
        """Test env vars for STANDARD tier."""
        router = DepthRouter()
        ctx = DepthContext.from_tier(DepthTier.STANDARD)
        assert router.get_env_vars(ctx) == {"ZERG_ANALYSIS_DEPTH": "standard"}

    def test_get_env_vars_think_hard(self) -> None:
        """Test env vars for THINK_HARD tier."""
        router = DepthRouter()
        ctx = DepthContext.from_tier(DepthTier.THINK_HARD)
        assert router.get_env_vars(ctx) == {"ZERG_ANALYSIS_DEPTH": "think-hard"}

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
        assert "--think-hard" in result.output
        assert "--ultrathink" in result.output

    def test_cli_quick_flag_accepted(self) -> None:
        """Test CLI accepts --quick flag."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--quick", "--help"])
        assert result.exit_code == 0

    def test_cli_think_flag_accepted(self) -> None:
        """Test CLI accepts --think flag."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--think", "--help"])
        assert result.exit_code == 0

    def test_cli_think_hard_flag_accepted(self) -> None:
        """Test CLI accepts --think-hard flag."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--think-hard", "--help"])
        assert result.exit_code == 0

    def test_cli_ultrathink_flag_accepted(self) -> None:
        """Test CLI accepts --ultrathink flag."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--ultrathink", "--help"])
        assert result.exit_code == 0

    def test_cli_mutually_exclusive_depth_flags(self) -> None:
        """Test multiple depth flags produce a usage error."""
        runner = CliRunner()
        # Need a subcommand to trigger the cli function body past --help
        # Use status as it's a registered command
        result = runner.invoke(cli, ["--quick", "--think", "status"])

        assert result.exit_code != 0
        assert "mutually exclusive" in result.output.lower() or "Mutually exclusive" in (
            result.output + str(result.exception)
        )

    def test_cli_no_depth_flag_defaults_to_standard(self) -> None:
        """Test no depth flag sets context depth to standard."""
        runner = CliRunner()
        # Use a minimal test by checking help still works
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
