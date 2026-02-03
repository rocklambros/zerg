"""Unit tests for ZERG behavioral mode system."""

from __future__ import annotations

from click.testing import CliRunner

from zerg.cli import cli
from zerg.modes import BehavioralMode, ModeContext, ModeDetector


class TestBehavioralModeEnum:
    """Tests for BehavioralMode enum values and properties."""

    def test_enum_values(self) -> None:
        """Test all expected enum members exist with correct values."""
        assert BehavioralMode.PRECISION.value == "precision"
        assert BehavioralMode.SPEED.value == "speed"
        assert BehavioralMode.EXPLORATION.value == "exploration"
        assert BehavioralMode.REFACTOR.value == "refactor"
        assert BehavioralMode.DEBUG.value == "debug"

    def test_enum_member_count(self) -> None:
        """Test exactly 5 behavioral modes exist."""
        assert len(BehavioralMode) == 5

    def test_description_precision(self) -> None:
        """Test PRECISION mode description."""
        assert "thorough" in BehavioralMode.PRECISION.description.lower()

    def test_description_speed(self) -> None:
        """Test SPEED mode description."""
        assert "fast" in BehavioralMode.SPEED.description.lower()

    def test_description_exploration(self) -> None:
        """Test EXPLORATION mode description."""
        assert "discovery" in BehavioralMode.EXPLORATION.description.lower()

    def test_description_refactor(self) -> None:
        """Test REFACTOR mode description."""
        assert "transformation" in BehavioralMode.REFACTOR.description.lower()

    def test_description_debug(self) -> None:
        """Test DEBUG mode description."""
        assert "diagnostic" in BehavioralMode.DEBUG.description.lower()

    def test_all_modes_have_descriptions(self) -> None:
        """Test every mode has a non-empty description."""
        for mode in BehavioralMode:
            assert isinstance(mode.description, str)
            assert len(mode.description) > 0

    def test_verification_level_precision(self) -> None:
        """Test PRECISION verification level is full."""
        assert BehavioralMode.PRECISION.verification_level == "full"

    def test_verification_level_speed(self) -> None:
        """Test SPEED verification level is minimal."""
        assert BehavioralMode.SPEED.verification_level == "minimal"

    def test_verification_level_exploration(self) -> None:
        """Test EXPLORATION verification level is none."""
        assert BehavioralMode.EXPLORATION.verification_level == "none"

    def test_verification_level_refactor(self) -> None:
        """Test REFACTOR verification level is full."""
        assert BehavioralMode.REFACTOR.verification_level == "full"

    def test_verification_level_debug(self) -> None:
        """Test DEBUG verification level is verbose."""
        assert BehavioralMode.DEBUG.verification_level == "verbose"

    def test_all_modes_have_verification_levels(self) -> None:
        """Test every mode returns a non-empty verification level."""
        for mode in BehavioralMode:
            level = mode.verification_level
            assert isinstance(level, str)
            assert len(level) > 0


class TestModeContext:
    """Tests for ModeContext dataclass."""

    def test_creation_basic(self) -> None:
        """Test basic ModeContext creation."""
        ctx = ModeContext(
            mode=BehavioralMode.PRECISION,
            auto_detected=False,
            detection_reason="explicit",
        )
        assert ctx.mode == BehavioralMode.PRECISION
        assert ctx.auto_detected is False
        assert ctx.detection_reason == "explicit"
        assert ctx.depth_tier is None
        assert ctx.efficiency_zone is None

    def test_creation_with_optional_fields(self) -> None:
        """Test ModeContext creation with all fields."""
        ctx = ModeContext(
            mode=BehavioralMode.DEBUG,
            auto_detected=True,
            detection_reason="keyword match",
            depth_tier="think-hard",
            efficiency_zone="yellow",
        )
        assert ctx.depth_tier == "think-hard"
        assert ctx.efficiency_zone == "yellow"

    def test_to_dict_keys(self) -> None:
        """Test to_dict returns expected keys."""
        ctx = ModeContext(
            mode=BehavioralMode.SPEED,
            auto_detected=True,
            detection_reason="zone-based",
        )
        d = ctx.to_dict()
        expected_keys = {"mode", "auto_detected", "detection_reason", "depth_tier", "efficiency_zone"}
        assert set(d.keys()) == expected_keys

    def test_to_dict_values(self) -> None:
        """Test to_dict serializes values correctly."""
        ctx = ModeContext(
            mode=BehavioralMode.REFACTOR,
            auto_detected=True,
            detection_reason="keyword",
            depth_tier="standard",
            efficiency_zone="green",
        )
        d = ctx.to_dict()
        assert d["mode"] == "refactor"
        assert d["auto_detected"] is True
        assert d["detection_reason"] == "keyword"
        assert d["depth_tier"] == "standard"
        assert d["efficiency_zone"] == "green"

    def test_to_dict_none_optional_fields(self) -> None:
        """Test to_dict with None optional fields."""
        ctx = ModeContext(
            mode=BehavioralMode.PRECISION,
            auto_detected=False,
            detection_reason="default",
        )
        d = ctx.to_dict()
        assert d["depth_tier"] is None
        assert d["efficiency_zone"] is None


class TestModeDetectorExplicit:
    """Tests for ModeDetector with explicit mode selection."""

    def test_explicit_mode_overrides_everything(self) -> None:
        """Test explicit mode ignores description, zone, and depth."""
        detector = ModeDetector()
        ctx = detector.detect(
            description="debug this broken code",
            explicit_mode=BehavioralMode.SPEED,
            depth_tier="ultrathink",
            efficiency_zone="red",
        )
        assert ctx.mode == BehavioralMode.SPEED
        assert ctx.auto_detected is False
        assert ctx.detection_reason == "explicit"

    def test_explicit_each_mode(self) -> None:
        """Test explicit mode works for every BehavioralMode value."""
        detector = ModeDetector()
        for mode in BehavioralMode:
            ctx = detector.detect(explicit_mode=mode)
            assert ctx.mode == mode
            assert ctx.auto_detected is False

    def test_explicit_mode_records_transition(self) -> None:
        """Test explicit mode records a transition."""
        detector = ModeDetector()
        detector.detect(explicit_mode=BehavioralMode.DEBUG)
        assert len(detector.transitions) == 1
        assert detector.transitions[0]["to"] == "debug"


class TestModeDetectorAutoDetectDisabled:
    """Tests for ModeDetector with auto_detect=False."""

    def test_auto_detect_disabled_returns_default(self) -> None:
        """Test disabled auto-detect always returns default mode."""
        detector = ModeDetector(auto_detect=False)
        ctx = detector.detect(description="debug this broken code")
        assert ctx.mode == BehavioralMode.PRECISION
        assert ctx.auto_detected is False
        assert ctx.detection_reason == "auto-detect disabled"

    def test_auto_detect_disabled_custom_default(self) -> None:
        """Test disabled auto-detect with custom default mode."""
        detector = ModeDetector(auto_detect=False, default_mode=BehavioralMode.SPEED)
        ctx = detector.detect(description="refactor the module")
        assert ctx.mode == BehavioralMode.SPEED

    def test_auto_detect_disabled_still_allows_explicit(self) -> None:
        """Test explicit mode still works when auto-detect is disabled."""
        detector = ModeDetector(auto_detect=False)
        ctx = detector.detect(explicit_mode=BehavioralMode.DEBUG)
        assert ctx.mode == BehavioralMode.DEBUG


class TestModeDetectorKeywords:
    """Tests for ModeDetector keyword detection."""

    def test_debug_keywords(self) -> None:
        """Test DEBUG mode keywords are detected."""
        detector = ModeDetector()
        for keyword in ["debug", "diagnose", "troubleshoot", "fix", "bug", "error", "failing", "broken"]:
            ctx = detector.detect(description=f"Need to {keyword} the system")
            assert ctx.mode == BehavioralMode.DEBUG, f"Keyword '{keyword}' should trigger DEBUG"
            assert ctx.auto_detected is True

    def test_refactor_keywords(self) -> None:
        """Test REFACTOR mode keywords are detected."""
        detector = ModeDetector()
        for keyword in ["refactor", "restructure", "reorganize", "clean up", "migrate", "rename", "extract", "move"]:
            ctx = detector.detect(description=f"Need to {keyword} the code")
            assert ctx.mode == BehavioralMode.REFACTOR, f"Keyword '{keyword}' should trigger REFACTOR"

    def test_exploration_keywords(self) -> None:
        """Test EXPLORATION mode keywords are detected."""
        detector = ModeDetector()
        for keyword in ["explore", "discover", "research", "investigate", "brainstorm", "analyze"]:
            ctx = detector.detect(description=f"Let's {keyword} the options")
            assert ctx.mode == BehavioralMode.EXPLORATION, f"Keyword '{keyword}' should trigger EXPLORATION"

    def test_speed_keywords(self) -> None:
        """Test SPEED mode keywords are detected."""
        detector = ModeDetector()
        for keyword in ["quick", "fast", "prototype", "spike", "poc", "draft"]:
            ctx = detector.detect(description=f"Make a {keyword} version")
            assert ctx.mode == BehavioralMode.SPEED, f"Keyword '{keyword}' should trigger SPEED"

    def test_keyword_case_insensitive(self) -> None:
        """Test keyword matching is case insensitive."""
        detector = ModeDetector()
        ctx = detector.detect(description="DEBUG THIS NOW")
        assert ctx.mode == BehavioralMode.DEBUG

    def test_keyword_partial_match(self) -> None:
        """Test keywords match as substrings."""
        detector = ModeDetector()
        ctx = detector.detect(description="debugging the application")
        assert ctx.mode == BehavioralMode.DEBUG

    def test_debug_takes_priority_over_refactor(self) -> None:
        """Test DEBUG keywords checked before REFACTOR."""
        detector = ModeDetector()
        # 'fix' is DEBUG, 'refactor' is REFACTOR; DEBUG checked first
        ctx = detector.detect(description="fix and refactor the module")
        assert ctx.mode == BehavioralMode.DEBUG

    def test_no_keyword_match_falls_through(self) -> None:
        """Test description with no keywords falls through to zone/depth/default."""
        detector = ModeDetector()
        ctx = detector.detect(description="implement a login form")
        assert ctx.mode == BehavioralMode.PRECISION  # default
        assert ctx.auto_detected is False


class TestModeDetectorZoneBased:
    """Tests for ModeDetector zone-based detection."""

    def test_red_zone_triggers_speed(self) -> None:
        """Test red efficiency zone triggers SPEED mode."""
        detector = ModeDetector()
        ctx = detector.detect(efficiency_zone="red")
        assert ctx.mode == BehavioralMode.SPEED
        assert ctx.auto_detected is True
        assert "red" in ctx.detection_reason

    def test_yellow_zone_does_not_trigger(self) -> None:
        """Test yellow zone alone does not trigger a specific mode."""
        detector = ModeDetector()
        ctx = detector.detect(efficiency_zone="yellow")
        # Falls through to depth or default
        assert ctx.mode == BehavioralMode.PRECISION

    def test_green_zone_does_not_trigger(self) -> None:
        """Test green zone alone does not trigger a specific mode."""
        detector = ModeDetector()
        ctx = detector.detect(efficiency_zone="green")
        assert ctx.mode == BehavioralMode.PRECISION

    def test_keywords_override_zone(self) -> None:
        """Test keywords take priority over zone-based detection."""
        detector = ModeDetector()
        ctx = detector.detect(
            description="refactor the auth module",
            efficiency_zone="red",
        )
        assert ctx.mode == BehavioralMode.REFACTOR


class TestModeDetectorDepthBased:
    """Tests for ModeDetector depth-based detection."""

    def test_ultrathink_triggers_precision(self) -> None:
        """Test ultrathink depth tier triggers PRECISION mode."""
        detector = ModeDetector()
        ctx = detector.detect(depth_tier="ultrathink")
        assert ctx.mode == BehavioralMode.PRECISION
        assert ctx.auto_detected is True
        assert "ultrathink" in ctx.detection_reason

    def test_think_hard_triggers_precision(self) -> None:
        """Test think-hard depth tier triggers PRECISION mode."""
        detector = ModeDetector()
        ctx = detector.detect(depth_tier="think-hard")
        assert ctx.mode == BehavioralMode.PRECISION
        assert ctx.auto_detected is True

    def test_standard_depth_does_not_trigger(self) -> None:
        """Test standard depth tier falls through to default."""
        detector = ModeDetector()
        ctx = detector.detect(depth_tier="standard")
        assert ctx.mode == BehavioralMode.PRECISION  # default
        assert ctx.auto_detected is False

    def test_think_depth_does_not_trigger(self) -> None:
        """Test think depth tier falls through to default."""
        detector = ModeDetector()
        ctx = detector.detect(depth_tier="think")
        assert ctx.mode == BehavioralMode.PRECISION
        assert ctx.auto_detected is False

    def test_zone_overrides_depth(self) -> None:
        """Test zone-based detection takes priority over depth-based."""
        detector = ModeDetector()
        ctx = detector.detect(depth_tier="ultrathink", efficiency_zone="red")
        # Red zone triggers speed, which is checked before depth
        assert ctx.mode == BehavioralMode.SPEED


class TestModeDetectorDefault:
    """Tests for ModeDetector default fallback behavior."""

    def test_no_input_returns_default(self) -> None:
        """Test detect with no input returns default mode."""
        detector = ModeDetector()
        ctx = detector.detect()
        assert ctx.mode == BehavioralMode.PRECISION
        assert ctx.auto_detected is False
        assert ctx.detection_reason == "default"

    def test_custom_default_mode(self) -> None:
        """Test custom default mode is returned when no signals match."""
        detector = ModeDetector(default_mode=BehavioralMode.EXPLORATION)
        ctx = detector.detect()
        assert ctx.mode == BehavioralMode.EXPLORATION

    def test_none_description_returns_default(self) -> None:
        """Test None description falls through to default."""
        detector = ModeDetector()
        ctx = detector.detect(description=None)
        assert ctx.mode == BehavioralMode.PRECISION

    def test_empty_description_returns_default(self) -> None:
        """Test empty description falls through to default."""
        detector = ModeDetector()
        ctx = detector.detect(description="")
        assert ctx.mode == BehavioralMode.PRECISION


class TestModeDetectorTransitions:
    """Tests for ModeDetector transition logging."""

    def test_no_transitions_initially(self) -> None:
        """Test transitions list is empty before any detection."""
        detector = ModeDetector()
        assert detector.transitions == []

    def test_transition_recorded_on_explicit(self) -> None:
        """Test transition is recorded for explicit mode."""
        detector = ModeDetector()
        detector.detect(explicit_mode=BehavioralMode.DEBUG)
        assert len(detector.transitions) == 1
        t = detector.transitions[0]
        assert t["from"] == "none"
        assert t["to"] == "debug"
        assert t["reason"] == "explicit"
        assert t["auto"] is False

    def test_transition_recorded_on_keyword(self) -> None:
        """Test transition is recorded for keyword detection."""
        detector = ModeDetector()
        detector.detect(description="debug the issue")
        assert len(detector.transitions) == 1
        assert detector.transitions[0]["auto"] is True

    def test_transition_from_previous_mode(self) -> None:
        """Test second transition records previous mode in 'from' field."""
        detector = ModeDetector()
        detector.detect(explicit_mode=BehavioralMode.SPEED)
        detector.detect(explicit_mode=BehavioralMode.DEBUG)
        assert len(detector.transitions) == 2
        assert detector.transitions[1]["from"] == "speed"
        assert detector.transitions[1]["to"] == "debug"

    def test_multiple_transitions_tracked(self) -> None:
        """Test multiple transitions are all recorded."""
        detector = ModeDetector()
        detector.detect(explicit_mode=BehavioralMode.SPEED)
        detector.detect(explicit_mode=BehavioralMode.DEBUG)
        detector.detect(explicit_mode=BehavioralMode.REFACTOR)
        assert len(detector.transitions) == 3

    def test_transitions_not_logged_when_disabled(self) -> None:
        """Test transitions not recorded when log_transitions=False."""
        detector = ModeDetector(log_transitions=False)
        detector.detect(explicit_mode=BehavioralMode.DEBUG)
        assert len(detector.transitions) == 0

    def test_current_mode_tracks_with_logging_disabled(self) -> None:
        """Test current_mode still updates even when logging disabled."""
        detector = ModeDetector(log_transitions=False)
        detector.detect(explicit_mode=BehavioralMode.DEBUG)
        assert detector.current_mode == BehavioralMode.DEBUG

    def test_transitions_returns_copy(self) -> None:
        """Test transitions property returns a copy, not the internal list."""
        detector = ModeDetector()
        detector.detect(explicit_mode=BehavioralMode.SPEED)
        transitions = detector.transitions
        transitions.append({"fake": "entry"})
        assert len(detector.transitions) == 1

    def test_default_fallback_does_not_record_transition(self) -> None:
        """Test default fallback does not record a transition."""
        detector = ModeDetector()
        detector.detect()
        assert len(detector.transitions) == 0

    def test_auto_detect_disabled_does_not_record_transition(self) -> None:
        """Test auto-detect disabled does not record a transition."""
        detector = ModeDetector(auto_detect=False)
        detector.detect(description="debug something")
        assert len(detector.transitions) == 0


class TestModeDetectorCurrentMode:
    """Tests for ModeDetector.current_mode property."""

    def test_current_mode_none_initially(self) -> None:
        """Test current_mode is None before any detection."""
        detector = ModeDetector()
        assert detector.current_mode is None

    def test_current_mode_updates_after_detect(self) -> None:
        """Test current_mode updates after detection with transition."""
        detector = ModeDetector()
        detector.detect(explicit_mode=BehavioralMode.REFACTOR)
        assert detector.current_mode == BehavioralMode.REFACTOR

    def test_current_mode_updates_on_keyword_detect(self) -> None:
        """Test current_mode updates after keyword-based detection."""
        detector = ModeDetector()
        detector.detect(description="debug this")
        assert detector.current_mode == BehavioralMode.DEBUG


class TestModeDetectorPriority:
    """Tests for detection priority order."""

    def test_explicit_over_keywords(self) -> None:
        """Test explicit mode beats keyword detection."""
        detector = ModeDetector()
        ctx = detector.detect(
            description="debug the module",
            explicit_mode=BehavioralMode.SPEED,
        )
        assert ctx.mode == BehavioralMode.SPEED

    def test_keywords_over_zone(self) -> None:
        """Test keyword detection beats zone-based detection."""
        detector = ModeDetector()
        ctx = detector.detect(
            description="explore the architecture",
            efficiency_zone="red",
        )
        assert ctx.mode == BehavioralMode.EXPLORATION

    def test_zone_over_depth(self) -> None:
        """Test zone-based detection beats depth-based detection."""
        detector = ModeDetector()
        ctx = detector.detect(
            efficiency_zone="red",
            depth_tier="ultrathink",
        )
        assert ctx.mode == BehavioralMode.SPEED

    def test_depth_over_default(self) -> None:
        """Test depth-based detection beats default."""
        detector = ModeDetector()
        ctx = detector.detect(depth_tier="ultrathink")
        assert ctx.mode == BehavioralMode.PRECISION
        assert ctx.auto_detected is True

    def test_full_priority_chain(self) -> None:
        """Test complete priority chain: explicit > keywords > zone > depth > default."""
        detector = ModeDetector()

        # All signals present, explicit wins
        ctx = detector.detect(
            description="debug broken code",
            explicit_mode=BehavioralMode.EXPLORATION,
            depth_tier="ultrathink",
            efficiency_zone="red",
        )
        assert ctx.mode == BehavioralMode.EXPLORATION


class TestModeDetectorContextPassthrough:
    """Tests for depth_tier and efficiency_zone passthrough in ModeContext."""

    def test_depth_tier_passed_through(self) -> None:
        """Test depth_tier is included in returned context."""
        detector = ModeDetector()
        ctx = detector.detect(depth_tier="think-hard")
        assert ctx.depth_tier == "think-hard"

    def test_efficiency_zone_passed_through(self) -> None:
        """Test efficiency_zone is included in returned context."""
        detector = ModeDetector()
        ctx = detector.detect(efficiency_zone="yellow")
        assert ctx.efficiency_zone == "yellow"

    def test_both_passed_through_on_explicit(self) -> None:
        """Test both fields passed through when using explicit mode."""
        detector = ModeDetector()
        ctx = detector.detect(
            explicit_mode=BehavioralMode.DEBUG,
            depth_tier="standard",
            efficiency_zone="green",
        )
        assert ctx.depth_tier == "standard"
        assert ctx.efficiency_zone == "green"


class TestCliModeFlag:
    """Tests for CLI --mode flag integration."""

    def test_cli_help_shows_mode_flag(self) -> None:
        """Test CLI help includes --mode option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "--mode" in result.output

    def test_cli_mode_choices_shown(self) -> None:
        """Test CLI help shows mode choices."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert "precision" in result.output
        assert "speed" in result.output
        assert "debug" in result.output

    def test_cli_mode_flag_accepted(self) -> None:
        """Test CLI accepts --mode flag without error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--mode", "speed", "--help"])
        assert result.exit_code == 0

    def test_cli_invalid_mode_rejected(self) -> None:
        """Test CLI rejects invalid mode values."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--mode", "invalid", "status"])
        assert result.exit_code != 0
