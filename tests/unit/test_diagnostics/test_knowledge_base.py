"""Tests for zerg.diagnostics.knowledge_base module."""

from __future__ import annotations

from zerg.diagnostics.knowledge_base import (
    KNOWN_PATTERNS,
    KnownPattern,
    PatternMatcher,
)

# ---------------------------------------------------------------------------
# KNOWN_PATTERNS collection
# ---------------------------------------------------------------------------


class TestKnownPatterns:
    """Tests for the KNOWN_PATTERNS list."""

    def test_pattern_count(self) -> None:
        assert len(KNOWN_PATTERNS) >= 25

    def test_pattern_fields(self) -> None:
        for pattern in KNOWN_PATTERNS:
            assert pattern.name, f"Pattern missing name: {pattern}"
            assert pattern.category, f"Pattern {pattern.name} missing category"
            assert len(pattern.symptoms) >= 3, f"Pattern {pattern.name} has <3 symptoms"
            assert 0 < pattern.prior_probability < 1, f"Pattern {pattern.name} prior out of (0,1)"
            assert len(pattern.common_causes) >= 2, f"Pattern {pattern.name} has <2 common_causes"
            assert len(pattern.fix_templates) >= 1, f"Pattern {pattern.name} has <1 fix_templates"

    def test_pattern_to_dict(self) -> None:
        p = KNOWN_PATTERNS[0]
        d = p.to_dict()
        expected_keys = {
            "name",
            "category",
            "symptoms",
            "prior_probability",
            "common_causes",
            "fix_templates",
            "related_patterns",
        }
        assert set(d.keys()) == expected_keys


# ---------------------------------------------------------------------------
# PatternMatcher.match
# ---------------------------------------------------------------------------


class TestPatternMatcherMatch:
    """Tests for PatternMatcher.match()."""

    def test_match_import_error(self) -> None:
        matcher = PatternMatcher()
        results = matcher.match("ImportError: No module named foo")
        assert len(results) > 0
        scores = [score for _, score in results]
        assert all(s > 0 for s in scores)

    def test_match_value_error(self) -> None:
        matcher = PatternMatcher()
        results = matcher.match("ValueError: invalid literal for int()")
        assert len(results) > 0

    def test_match_worker_crash(self) -> None:
        matcher = PatternMatcher()
        results = matcher.match("worker crashed unexpectedly")
        assert len(results) > 0

    def test_match_unknown(self) -> None:
        matcher = PatternMatcher()
        results = matcher.match("xyzzy gibberish zzz999")
        # Should return empty or only very low-score matches
        for _, score in results:
            assert score <= 1.0

    def test_match_scores_bounded(self) -> None:
        matcher = PatternMatcher()
        for text in [
            "ImportError: No module named os",
            "worker timed out",
            "MemoryError",
            "CONFLICT Merge conflict in file.py",
        ]:
            results = matcher.match(text)
            for _, score in results:
                assert 0 < score <= 1.0


# ---------------------------------------------------------------------------
# PatternMatcher.get_prior
# ---------------------------------------------------------------------------


class TestPatternMatcherGetPrior:
    """Tests for PatternMatcher.get_prior()."""

    def test_get_prior_valid_category(self) -> None:
        matcher = PatternMatcher()
        prior = matcher.get_prior("python")
        assert isinstance(prior, float)
        assert 0 < prior < 1

    def test_get_prior_unknown_category(self) -> None:
        matcher = PatternMatcher()
        prior = matcher.get_prior("nonexistent_category_xyz")
        assert prior == 0.0


# ---------------------------------------------------------------------------
# PatternMatcher.get_related
# ---------------------------------------------------------------------------


class TestPatternMatcherGetRelated:
    """Tests for PatternMatcher.get_related()."""

    def test_get_related_returns_known_patterns(self) -> None:
        matcher = PatternMatcher()
        related = matcher.get_related("import_error")
        assert len(related) > 0
        for item in related:
            assert isinstance(item, KnownPattern)

    def test_get_related_unknown_pattern(self) -> None:
        matcher = PatternMatcher()
        related = matcher.get_related("totally_unknown_xyz")
        assert related == []
