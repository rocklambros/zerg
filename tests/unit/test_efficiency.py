"""Unit tests for ZERG token efficiency module — thinned to essentials."""

from __future__ import annotations

import pytest

from zerg.efficiency import (
    ABBREVIATIONS,
    SYMBOLS,
    CompactFormatter,
    EfficiencyZone,
    ZoneDetector,
)

# ── EfficiencyZone Enum ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "zone,value,threshold,desc_fragment",
    [
        (EfficiencyZone.GREEN, "green", 0.0, "Full capabilities"),
        (EfficiencyZone.YELLOW, "yellow", 75.0, "Efficiency mode"),
        (EfficiencyZone.RED, "red", 85.0, "Essential operations"),
    ],
)
def test_efficiency_zone_properties(zone, value, threshold, desc_fragment) -> None:
    assert zone.value == value
    assert zone.threshold == threshold
    assert desc_fragment in zone.description


# ── ZoneDetector ────────────────────────────────────────────────────


class TestZoneDetector:
    @pytest.mark.parametrize(
        "usage,expected",
        [
            (0.0, EfficiencyZone.GREEN),
            (74.9, EfficiencyZone.GREEN),
            (75.0, EfficiencyZone.YELLOW),
            (84.9, EfficiencyZone.YELLOW),
            (85.0, EfficiencyZone.RED),
            (100.0, EfficiencyZone.RED),
        ],
    )
    def test_detect_zones(self, usage, expected) -> None:
        assert ZoneDetector().detect(usage) == expected

    def test_custom_thresholds(self) -> None:
        d = ZoneDetector(yellow_threshold=50.0, red_threshold=80.0)
        assert d.detect(49.9) == EfficiencyZone.GREEN
        assert d.detect(50.0) == EfficiencyZone.YELLOW
        assert d.detect(80.0) == EfficiencyZone.RED

    def test_should_compact(self) -> None:
        d = ZoneDetector()
        assert d.should_compact(0.0, force_compact=True) is True
        assert d.should_compact(50.0) is False
        assert d.should_compact(80.0) is True
        assert d.should_compact(90.0) is True


# ── CompactFormatter ────────────────────────────────────────────────


class TestCompactFormatter:
    def test_format_status(self) -> None:
        f = CompactFormatter()
        result = f.format_status("completed")
        assert result.endswith("completed") and len(result) > len("completed")
        assert CompactFormatter(use_symbols=False).format_status("completed") == "completed"
        assert f.format_status("unknown_status") == "unknown_status"

    def test_abbreviate(self) -> None:
        f = CompactFormatter()
        assert f.abbreviate("configuration") == "cfg"
        assert f.abbreviate("foobar") == "foobar"
        assert CompactFormatter(use_abbreviations=False).abbreviate("configuration") == "configuration"
        result = f.abbreviate("check configuration and performance")
        assert "cfg" in result and "perf" in result

    def test_compact_summary(self) -> None:
        f = CompactFormatter()
        result = f.compact_summary({"name": "test", "count": 5, "enabled": True})
        assert "name=test" in result and "enabled=Y" in result
        assert "active=N" in f.compact_summary({"active": False})
        assert "cfg=" in f.compact_summary({"configuration": "done"})

    def test_compact_list(self) -> None:
        f = CompactFormatter()
        result = f.compact_list(["configuration", "performance", "testing"])
        assert "cfg" in result and " | " in result
        assert f.compact_list(["a", "b", "c"], separator=", ") == "a, b, c"


# ── Constants ───────────────────────────────────────────────────────


class TestConstants:
    def test_symbols_coverage(self) -> None:
        for category in [
            ["completed", "failed", "warning", "in_progress", "pending", "critical"],
            ["performance", "analysis", "security", "deployment", "architecture"],
            ["leads_to", "transforms", "rollback", "therefore", "because", "sequence"],
        ]:
            for key in category:
                assert key in SYMBOLS and isinstance(SYMBOLS[key], str) and len(SYMBOLS[key]) > 0

    def test_abbreviations(self) -> None:
        expected = {"configuration": "cfg", "implementation": "impl", "architecture": "arch"}
        for full, abbrev in expected.items():
            assert ABBREVIATIONS[full] == abbrev
        for full, abbrev in ABBREVIATIONS.items():
            assert len(abbrev) < len(full)


# ── ContextTracker Integration ──────────────────────────────────────


class TestContextTrackerGetZone:
    def test_get_zone_returns_valid(self) -> None:
        from zerg.context_tracker import ContextTracker

        tracker = ContextTracker(threshold_percent=70.0)
        assert tracker.get_zone() == "green"
        tracker2 = ContextTracker()
        assert tracker2.get_zone() in {"green", "yellow", "red"}
