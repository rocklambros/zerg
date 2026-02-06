"""Unit tests for ZERG behavioral mode system — thinned to essentials."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from zerg.cli import cli
from zerg.modes import BehavioralMode, ModeContext, ModeDetector

# ── BehavioralMode Enum ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "mode,value,desc_fragment,verify_level",
    [
        (BehavioralMode.PRECISION, "precision", "thorough", "full"),
        (BehavioralMode.SPEED, "speed", "fast", "minimal"),
        (BehavioralMode.EXPLORATION, "exploration", "discovery", "none"),
        (BehavioralMode.REFACTOR, "refactor", "transformation", "full"),
        (BehavioralMode.DEBUG, "debug", "diagnostic", "verbose"),
    ],
)
def test_behavioral_mode_properties(mode, value, desc_fragment, verify_level) -> None:
    assert mode.value == value
    assert desc_fragment in mode.description.lower()
    assert mode.verification_level == verify_level


def test_behavioral_mode_count() -> None:
    assert len(BehavioralMode) == 5


# ── ModeContext ─────────────────────────────────────────────────────


class TestModeContext:
    def test_creation_and_defaults(self) -> None:
        ctx = ModeContext(
            mode=BehavioralMode.PRECISION,
            auto_detected=False,
            detection_reason="explicit",
        )
        assert ctx.mode == BehavioralMode.PRECISION
        assert ctx.depth_tier is None
        assert ctx.efficiency_zone is None

    def test_to_dict_full(self) -> None:
        ctx = ModeContext(
            mode=BehavioralMode.REFACTOR,
            auto_detected=True,
            detection_reason="keyword",
            depth_tier="standard",
            efficiency_zone="green",
        )
        d = ctx.to_dict()
        assert d["mode"] == "refactor"
        assert d["depth_tier"] == "standard"
        assert d["efficiency_zone"] == "green"
        assert set(d.keys()) == {"mode", "auto_detected", "detection_reason", "depth_tier", "efficiency_zone"}


# ── ModeDetector: Explicit ──────────────────────────────────────────


class TestModeDetectorExplicit:
    def test_explicit_overrides_everything(self) -> None:
        detector = ModeDetector()
        ctx = detector.detect(
            description="debug this broken code",
            explicit_mode=BehavioralMode.SPEED,
            depth_tier="ultrathink",
            efficiency_zone="red",
        )
        assert ctx.mode == BehavioralMode.SPEED
        assert ctx.auto_detected is False
        assert len(detector.transitions) == 1
        # Passthrough: depth_tier and efficiency_zone are preserved
        assert ctx.depth_tier == "ultrathink"
        assert ctx.efficiency_zone == "red"


# ── ModeDetector: Auto-detect Disabled ──────────────────────────────


class TestModeDetectorAutoDetectDisabled:
    def test_returns_default_but_allows_explicit(self) -> None:
        detector = ModeDetector(auto_detect=False)
        ctx = detector.detect(description="debug this broken code")
        assert ctx.mode == BehavioralMode.PRECISION
        assert ctx.detection_reason == "auto-detect disabled"
        ctx2 = detector.detect(explicit_mode=BehavioralMode.DEBUG)
        assert ctx2.mode == BehavioralMode.DEBUG


# ── ModeDetector: Keywords ──────────────────────────────────────────


class TestModeDetectorKeywords:
    @pytest.mark.parametrize(
        "keyword,expected_mode",
        [
            ("debug", BehavioralMode.DEBUG),
            ("fix", BehavioralMode.DEBUG),
            ("refactor", BehavioralMode.REFACTOR),
            ("explore", BehavioralMode.EXPLORATION),
            ("quick", BehavioralMode.SPEED),
        ],
    )
    def test_keyword_detection(self, keyword, expected_mode) -> None:
        detector = ModeDetector()
        ctx = detector.detect(description=f"Need to {keyword} the system")
        assert ctx.mode == expected_mode
        assert ctx.auto_detected is True

    def test_debug_priority_over_refactor(self) -> None:
        detector = ModeDetector()
        ctx = detector.detect(description="fix and refactor the module")
        assert ctx.mode == BehavioralMode.DEBUG


# ── ModeDetector: Zone-Based ────────────────────────────────────────


class TestModeDetectorZoneBased:
    def test_red_zone_triggers_speed(self) -> None:
        detector = ModeDetector()
        ctx = detector.detect(efficiency_zone="red")
        assert ctx.mode == BehavioralMode.SPEED
        assert ctx.auto_detected is True

    def test_yellow_green_no_trigger(self) -> None:
        detector = ModeDetector()
        for zone in ["yellow", "green"]:
            ctx = detector.detect(efficiency_zone=zone)
            assert ctx.mode == BehavioralMode.PRECISION


# ── ModeDetector: Depth-Based ───────────────────────────────────────


class TestModeDetectorDepthBased:
    @pytest.mark.parametrize("tier", ["ultrathink", "think-hard"])
    def test_deep_tiers_trigger_precision(self, tier) -> None:
        detector = ModeDetector()
        ctx = detector.detect(depth_tier=tier)
        assert ctx.mode == BehavioralMode.PRECISION
        assert ctx.auto_detected is True

    def test_standard_does_not_trigger(self) -> None:
        detector = ModeDetector()
        ctx = detector.detect(depth_tier="standard")
        assert ctx.auto_detected is False


# ── ModeDetector: Default ───────────────────────────────────────────


class TestModeDetectorDefault:
    def test_no_input_returns_default(self) -> None:
        detector = ModeDetector()
        ctx = detector.detect()
        assert ctx.mode == BehavioralMode.PRECISION
        assert ctx.detection_reason == "default"


# ── ModeDetector: Transitions ───────────────────────────────────────


class TestModeDetectorTransitions:
    def test_transition_recorded_and_returns_copy(self) -> None:
        detector = ModeDetector()
        detector.detect(explicit_mode=BehavioralMode.DEBUG)
        assert len(detector.transitions) == 1
        t = detector.transitions[0]
        assert t["from"] == "none" and t["to"] == "debug"
        detector.transitions.append({"fake": "entry"})
        assert len(detector.transitions) == 1  # copy

    def test_from_previous_mode(self) -> None:
        detector = ModeDetector()
        detector.detect(explicit_mode=BehavioralMode.SPEED)
        detector.detect(explicit_mode=BehavioralMode.DEBUG)
        assert detector.transitions[1]["from"] == "speed"

    def test_disabled_logging_and_current_mode(self) -> None:
        detector = ModeDetector(log_transitions=False)
        assert detector.current_mode is None
        detector.detect(explicit_mode=BehavioralMode.DEBUG)
        assert len(detector.transitions) == 0
        assert detector.current_mode == BehavioralMode.DEBUG


# ── ModeDetector: Priority Chain ────────────────────────────────────


class TestModeDetectorPriority:
    def test_full_priority_chain(self) -> None:
        detector = ModeDetector()
        ctx = detector.detect(
            description="debug broken code",
            explicit_mode=BehavioralMode.EXPLORATION,
            depth_tier="ultrathink",
            efficiency_zone="red",
        )
        assert ctx.mode == BehavioralMode.EXPLORATION  # explicit wins

    def test_keywords_over_zone(self) -> None:
        detector = ModeDetector()
        ctx = detector.detect(description="explore the architecture", efficiency_zone="red")
        assert ctx.mode == BehavioralMode.EXPLORATION


# ── CLI --mode Flag ─────────────────────────────────────────────────


class TestCliModeFlag:
    def test_mode_flag_accepted(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--mode", "speed", "--help"])
        assert result.exit_code == 0
        assert "--mode" in result.output

    def test_invalid_mode_rejected(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--mode", "invalid", "status"])
        assert result.exit_code != 0
