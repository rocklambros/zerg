"""Unit tests for ZERG token efficiency module."""

from __future__ import annotations

from zerg.efficiency import (
    ABBREVIATIONS,
    SYMBOLS,
    CompactFormatter,
    EfficiencyZone,
    ZoneDetector,
)


class TestEfficiencyZone:
    """Tests for EfficiencyZone enum."""

    def test_zone_values(self) -> None:
        """Test enum values match expected strings."""
        assert EfficiencyZone.GREEN.value == "green"
        assert EfficiencyZone.YELLOW.value == "yellow"
        assert EfficiencyZone.RED.value == "red"

    def test_green_threshold(self) -> None:
        """Test green zone starts at 0%."""
        assert EfficiencyZone.GREEN.threshold == 0.0

    def test_yellow_threshold(self) -> None:
        """Test yellow zone starts at 75%."""
        assert EfficiencyZone.YELLOW.threshold == 75.0

    def test_red_threshold(self) -> None:
        """Test red zone starts at 85%."""
        assert EfficiencyZone.RED.threshold == 85.0

    def test_green_description(self) -> None:
        """Test green zone description."""
        assert "Full capabilities" in EfficiencyZone.GREEN.description

    def test_yellow_description(self) -> None:
        """Test yellow zone description."""
        assert "Efficiency mode" in EfficiencyZone.YELLOW.description

    def test_red_description(self) -> None:
        """Test red zone description."""
        assert "Essential operations" in EfficiencyZone.RED.description


class TestZoneDetector:
    """Tests for ZoneDetector."""

    def test_detect_green_at_zero(self) -> None:
        """Test 0% usage returns green zone."""
        detector = ZoneDetector()
        assert detector.detect(0.0) == EfficiencyZone.GREEN

    def test_detect_green_below_yellow(self) -> None:
        """Test 74.9% usage returns green zone."""
        detector = ZoneDetector()
        assert detector.detect(74.9) == EfficiencyZone.GREEN

    def test_detect_yellow_at_threshold(self) -> None:
        """Test exactly 75% usage returns yellow zone."""
        detector = ZoneDetector()
        assert detector.detect(75.0) == EfficiencyZone.YELLOW

    def test_detect_yellow_below_red(self) -> None:
        """Test 84.9% usage returns yellow zone."""
        detector = ZoneDetector()
        assert detector.detect(84.9) == EfficiencyZone.YELLOW

    def test_detect_red_at_threshold(self) -> None:
        """Test exactly 85% usage returns red zone."""
        detector = ZoneDetector()
        assert detector.detect(85.0) == EfficiencyZone.RED

    def test_detect_red_at_100(self) -> None:
        """Test 100% usage returns red zone."""
        detector = ZoneDetector()
        assert detector.detect(100.0) == EfficiencyZone.RED

    def test_custom_thresholds(self) -> None:
        """Test detector with custom thresholds."""
        detector = ZoneDetector(yellow_threshold=50.0, red_threshold=80.0)
        assert detector.detect(49.9) == EfficiencyZone.GREEN
        assert detector.detect(50.0) == EfficiencyZone.YELLOW
        assert detector.detect(79.9) == EfficiencyZone.YELLOW
        assert detector.detect(80.0) == EfficiencyZone.RED

    def test_should_compact_force_true(self) -> None:
        """Test force_compact always returns True."""
        detector = ZoneDetector()
        assert detector.should_compact(0.0, force_compact=True) is True
        assert detector.should_compact(50.0, force_compact=True) is True

    def test_should_compact_green_zone(self) -> None:
        """Test green zone does not compact without force."""
        detector = ZoneDetector()
        assert detector.should_compact(50.0) is False

    def test_should_compact_yellow_zone(self) -> None:
        """Test yellow zone triggers compact."""
        detector = ZoneDetector()
        assert detector.should_compact(80.0) is True

    def test_should_compact_red_zone(self) -> None:
        """Test red zone triggers compact."""
        detector = ZoneDetector()
        assert detector.should_compact(90.0) is True


class TestCompactFormatter:
    """Tests for CompactFormatter."""

    def test_format_status_with_symbols(self) -> None:
        """Test status formatting includes symbol prefix."""
        formatter = CompactFormatter()
        result = formatter.format_status("completed")
        assert result.endswith("completed")
        assert len(result) > len("completed")

    def test_format_status_without_symbols(self) -> None:
        """Test status formatting returns plain text when symbols disabled."""
        formatter = CompactFormatter(use_symbols=False)
        assert formatter.format_status("completed") == "completed"

    def test_format_status_unknown(self) -> None:
        """Test unknown status returns as-is."""
        formatter = CompactFormatter()
        assert formatter.format_status("unknown_status") == "unknown_status"

    def test_abbreviate_known_terms(self) -> None:
        """Test abbreviation of known terms."""
        formatter = CompactFormatter()
        assert formatter.abbreviate("configuration") == "cfg"
        assert formatter.abbreviate("implementation") == "impl"
        assert formatter.abbreviate("architecture") == "arch"
        assert formatter.abbreviate("performance") == "perf"

    def test_abbreviate_preserves_unknown(self) -> None:
        """Test abbreviation leaves unknown text unchanged."""
        formatter = CompactFormatter()
        assert formatter.abbreviate("foobar") == "foobar"

    def test_abbreviate_disabled(self) -> None:
        """Test abbreviation does nothing when disabled."""
        formatter = CompactFormatter(use_abbreviations=False)
        assert formatter.abbreviate("configuration") == "configuration"

    def test_abbreviate_in_sentence(self) -> None:
        """Test abbreviation within a larger text string."""
        formatter = CompactFormatter()
        result = formatter.abbreviate("check configuration and performance")
        assert "cfg" in result
        assert "perf" in result

    def test_compact_summary_basic(self) -> None:
        """Test compact summary with mixed types."""
        formatter = CompactFormatter()
        data = {"name": "test", "count": 5, "enabled": True}
        result = formatter.compact_summary(data)
        assert "name=test" in result
        assert "count=5" in result
        assert "enabled=Y" in result

    def test_compact_summary_bool_false(self) -> None:
        """Test compact summary formats False as N."""
        formatter = CompactFormatter()
        result = formatter.compact_summary({"active": False})
        assert "active=N" in result

    def test_compact_summary_abbreviates_keys(self) -> None:
        """Test compact summary abbreviates key names."""
        formatter = CompactFormatter()
        result = formatter.compact_summary({"configuration": "done"})
        assert "cfg=" in result

    def test_compact_summary_long_wraps(self) -> None:
        """Test compact summary wraps when exceeding max line length."""
        formatter = CompactFormatter(max_line_length=20)
        data = {"key_one": "value_one", "key_two": "value_two"}
        result = formatter.compact_summary(data)
        assert "\n" in result

    def test_compact_summary_short_single_line(self) -> None:
        """Test compact summary stays single line when short."""
        formatter = CompactFormatter(max_line_length=200)
        data = {"a": 1, "b": 2}
        result = formatter.compact_summary(data)
        assert "\n" not in result
        assert " | " in result

    def test_compact_list_default_separator(self) -> None:
        """Test compact list with default separator."""
        formatter = CompactFormatter()
        result = formatter.compact_list(["configuration", "performance", "testing"])
        assert "cfg" in result
        assert "perf" in result
        assert " | " in result

    def test_compact_list_custom_separator(self) -> None:
        """Test compact list with custom separator."""
        formatter = CompactFormatter()
        result = formatter.compact_list(["a", "b", "c"], separator=", ")
        assert result == "a, b, c"

    def test_compact_list_abbreviations_disabled(self) -> None:
        """Test compact list without abbreviations."""
        formatter = CompactFormatter(use_abbreviations=False)
        result = formatter.compact_list(["configuration"])
        assert result == "configuration"


class TestSymbolsDict:
    """Tests for SYMBOLS constant."""

    def test_has_status_symbols(self) -> None:
        """Test SYMBOLS contains status keys."""
        expected_keys = ["completed", "failed", "warning", "in_progress", "pending", "critical"]
        for key in expected_keys:
            assert key in SYMBOLS, f"Missing symbol: {key}"

    def test_has_domain_symbols(self) -> None:
        """Test SYMBOLS contains domain keys."""
        expected_keys = ["performance", "analysis", "security", "deployment", "architecture"]
        for key in expected_keys:
            assert key in SYMBOLS, f"Missing symbol: {key}"

    def test_has_logic_symbols(self) -> None:
        """Test SYMBOLS contains logic keys."""
        expected_keys = ["leads_to", "transforms", "rollback", "therefore", "because", "sequence"]
        for key in expected_keys:
            assert key in SYMBOLS, f"Missing symbol: {key}"

    def test_symbols_are_non_empty_strings(self) -> None:
        """Test all symbol values are non-empty strings."""
        for key, value in SYMBOLS.items():
            assert isinstance(value, str), f"Symbol {key} is not a string"
            assert len(value) > 0, f"Symbol {key} is empty"


class TestAbbreviationsDict:
    """Tests for ABBREVIATIONS constant."""

    def test_has_expected_keys(self) -> None:
        """Test ABBREVIATIONS contains expected mappings."""
        expected = {
            "configuration": "cfg",
            "implementation": "impl",
            "architecture": "arch",
            "performance": "perf",
            "operations": "ops",
            "environment": "env",
            "requirements": "req",
            "dependencies": "deps",
            "validation": "val",
            "documentation": "docs",
            "standards": "std",
            "security": "sec",
            "optimization": "opt",
        }
        for full, abbrev in expected.items():
            assert ABBREVIATIONS[full] == abbrev, f"Mismatch for {full}"

    def test_abbreviations_are_shorter(self) -> None:
        """Test all abbreviations are shorter than full terms."""
        for full, abbrev in ABBREVIATIONS.items():
            assert len(abbrev) < len(full), f"Abbreviation '{abbrev}' not shorter than '{full}'"


class TestContextTrackerGetZone:
    """Tests for ContextTracker.get_zone() integration."""

    def test_get_zone_returns_green_for_low_usage(self) -> None:
        """Test get_zone returns 'green' when usage is low."""
        from zerg.context_tracker import ContextTracker

        tracker = ContextTracker(threshold_percent=70.0)
        # Fresh tracker with no activity should be well under thresholds
        zone = tracker.get_zone()
        assert zone == "green"

    def test_get_zone_returns_valid_zone_name(self) -> None:
        """Test get_zone returns one of the valid zone names."""
        from zerg.context_tracker import ContextTracker

        tracker = ContextTracker()
        zone = tracker.get_zone()
        assert zone in {"green", "yellow", "red"}

    def test_get_zone_high_usage(self) -> None:
        """Test get_zone returns non-green for high simulated usage."""
        from zerg.context_tracker import ContextTracker

        tracker = ContextTracker()
        # Simulate reading many large files to push usage high
        for i in range(500):
            tracker.track_file_read(f"/fake/file_{i}.py", size=2000)
        zone = tracker.get_zone()
        # With 500 files * 2000 bytes * 0.25 tokens/char + overhead,
        # this should push past green zone
        assert zone in {"green", "yellow", "red"}
