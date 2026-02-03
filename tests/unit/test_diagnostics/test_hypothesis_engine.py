"""Tests for zerg.diagnostics.hypothesis_engine."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from zerg.diagnostics.hypothesis_engine import (
    BayesianScorer,
    HypothesisChainer,
    HypothesisEngine,
    HypothesisGenerator,
    HypothesisTestRunner,
)
from zerg.diagnostics.knowledge_base import KnownPattern
from zerg.diagnostics.types import (
    ErrorCategory,
    ErrorFingerprint,
    Evidence,
    ScoredHypothesis,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_fingerprint():
    return ErrorFingerprint(
        hash="abc123",
        language="python",
        error_type="ValueError",
        message_template="invalid literal",
        file="test.py",
        line=42,
    )


@pytest.fixture
def sample_evidence():
    return [Evidence(description="Error at test.py:42", source="code", confidence=0.8)]


@pytest.fixture
def scorer():
    return BayesianScorer()


@pytest.fixture
def generator():
    return HypothesisGenerator()


@pytest.fixture
def runner():
    return HypothesisTestRunner()


@pytest.fixture
def chainer():
    return HypothesisChainer()


@pytest.fixture
def engine():
    return HypothesisEngine()


# ---------------------------------------------------------------------------
# TestBayesianScorer
# ---------------------------------------------------------------------------


class TestBayesianScorer:
    """Tests for BayesianScorer."""

    def test_posterior_no_evidence(self, scorer):
        result = scorer.compute_posterior(0.5, [], [])
        assert result == 0.5

    def test_posterior_positive_evidence(self, scorer):
        ev_for = [Evidence(description="match", source="code", confidence=0.8)]
        result = scorer.compute_posterior(0.5, ev_for, [])
        assert result > 0.5

    def test_posterior_negative_evidence(self, scorer):
        ev_against = [Evidence(description="mismatch", source="code", confidence=0.8)]
        result = scorer.compute_posterior(0.5, [], ev_against)
        assert result < 0.5

    def test_posterior_mixed_evidence(self, scorer):
        ev_for = [Evidence(description="match", source="code", confidence=0.9)]
        ev_against = [Evidence(description="mismatch", source="code", confidence=0.3)]
        result = scorer.compute_posterior(0.5, ev_for, ev_against)
        # Positive evidence is stronger here, so result should be > 0.5
        assert result > 0.5

    def test_posterior_clamped_high(self, scorer):
        strong_evidence = [Evidence(description=f"ev{i}", source="code", confidence=0.99) for i in range(20)]
        result = scorer.compute_posterior(0.9, strong_evidence, [])
        assert result <= 0.99

    def test_posterior_clamped_low(self, scorer):
        strong_neg = [Evidence(description=f"ev{i}", source="code", confidence=0.99) for i in range(20)]
        result = scorer.compute_posterior(0.1, [], strong_neg)
        assert result >= 0.01

    def test_rank_descending(self, scorer):
        hypotheses = [
            ScoredHypothesis(
                description="low",
                category=ErrorCategory.UNKNOWN,
                prior_probability=0.1,
                posterior_probability=0.2,
            ),
            ScoredHypothesis(
                description="high",
                category=ErrorCategory.UNKNOWN,
                prior_probability=0.1,
                posterior_probability=0.9,
            ),
            ScoredHypothesis(
                description="mid",
                category=ErrorCategory.UNKNOWN,
                prior_probability=0.1,
                posterior_probability=0.5,
            ),
        ]
        ranked = scorer.rank(hypotheses)
        assert ranked[0].description == "high"
        assert ranked[1].description == "mid"
        assert ranked[2].description == "low"

    def test_rank_empty(self, scorer):
        assert scorer.rank([]) == []


# ---------------------------------------------------------------------------
# TestHypothesisGenerator
# ---------------------------------------------------------------------------


class TestHypothesisGenerator:
    """Tests for HypothesisGenerator."""

    def test_generate_from_fingerprint(self, generator, sample_fingerprint, sample_evidence):
        results = generator.generate(sample_fingerprint, sample_evidence)
        # Should have at least the location hypothesis
        assert len(results) >= 1
        location_hyp = results[0]
        assert "test.py:42" in location_hyp.description
        assert location_hyp.category == ErrorCategory.CODE_ERROR

    def test_generate_from_kb(self, generator, sample_fingerprint, sample_evidence):
        pattern = KnownPattern(
            name="TestPattern",
            category="python",
            symptoms=["ValueError"],
            prior_probability=0.7,
            common_causes=["bad input"],
            fix_templates=["validate input first"],
        )
        kb_matches = [(pattern, 0.8)]
        results = generator.generate(sample_fingerprint, sample_evidence, kb_matches=kb_matches)
        # Should have location + KB + evidence-based hypotheses
        kb_hyps = [h for h in results if "Known pattern" in h.description]
        assert len(kb_hyps) >= 1

    def test_generate_max_10(self, generator):
        fp = ErrorFingerprint(
            hash="x",
            language="python",
            error_type="ValueError",
            message_template="err",
            file="f.py",
            line=1,
        )
        # Create many evidence items to generate many hypotheses
        evidence = [Evidence(description=f"evidence_{i}", source="code", confidence=0.6) for i in range(20)]
        patterns = [
            (
                KnownPattern(
                    name=f"Pat{i}",
                    category="python",
                    symptoms=[],
                    prior_probability=0.5,
                    common_causes=[f"cause{i}"],
                    fix_templates=[f"fix{i}"],
                ),
                0.5,
            )
            for i in range(15)
        ]
        results = generator.generate(fp, evidence, kb_matches=patterns)
        assert len(results) <= 10

    def test_generate_empty(self, generator):
        fp = ErrorFingerprint(
            hash="empty",
            language="python",
            error_type="Unknown",
            message_template="",
            file="",
            line=0,
        )
        results = generator.generate(fp, [])
        # No file/line, no KB, no evidence -> empty or minimal
        assert len(results) == 0

    def test_generate_sets_fix(self, generator, sample_fingerprint, sample_evidence):
        pattern = KnownPattern(
            name="FixPattern",
            category="python",
            symptoms=[],
            prior_probability=0.6,
            common_causes=["root cause"],
            fix_templates=["apply the fix"],
        )
        results = generator.generate(sample_fingerprint, sample_evidence, kb_matches=[(pattern, 0.7)])
        kb_hyps = [h for h in results if "Known pattern" in h.description]
        assert len(kb_hyps) >= 1
        assert kb_hyps[0].suggested_fix == "apply the fix"


# ---------------------------------------------------------------------------
# TestHypothesisTestRunner
# ---------------------------------------------------------------------------


class TestHypothesisTestRunner:
    """Tests for HypothesisTestRunner."""

    def _make_hypothesis(self, test_command: str = "", **kwargs) -> ScoredHypothesis:
        defaults = dict(
            description="test hyp",
            category=ErrorCategory.CODE_ERROR,
            prior_probability=0.5,
            posterior_probability=0.5,
            test_command=test_command,
        )
        defaults.update(kwargs)
        return ScoredHypothesis(**defaults)

    def test_can_test_safe_command(self, runner):
        h = self._make_hypothesis(test_command="python -c 'print(1)'")
        assert runner.can_test(h) is True

    def test_can_test_unsafe_command(self, runner):
        h = self._make_hypothesis(test_command="rm -rf /")
        assert runner.can_test(h) is False

    def test_can_test_empty_command(self, runner):
        h = self._make_hypothesis(test_command="")
        assert runner.can_test(h) is False

    def test_can_test_git_command(self, runner):
        h = self._make_hypothesis(test_command="git status")
        assert runner.can_test(h) is True

    @patch("zerg.diagnostics.hypothesis_engine.subprocess.run")
    def test_test_success(self, mock_run, runner):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        h = self._make_hypothesis(test_command="python -c 'print(1)'")
        original_posterior = h.posterior_probability

        result = runner.test(h)

        assert result.test_result == "PASSED"
        assert result.posterior_probability > original_posterior
        mock_run.assert_called_once()

    @patch("zerg.diagnostics.hypothesis_engine.subprocess.run")
    def test_test_failure(self, mock_run, runner):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        h = self._make_hypothesis(test_command="python -c 'raise Exception()'")
        original_posterior = h.posterior_probability

        result = runner.test(h)

        assert result.test_result == "FAILED"
        assert result.posterior_probability < original_posterior
        mock_run.assert_called_once()

    @patch("zerg.diagnostics.hypothesis_engine.subprocess.run")
    def test_test_timeout(self, mock_run, runner):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="python", timeout=30)
        h = self._make_hypothesis(test_command="python -c 'import time; time.sleep(999)'")

        result = runner.test(h)

        assert result.test_result is not None
        assert "ERROR" in result.test_result
        mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# TestHypothesisChainer
# ---------------------------------------------------------------------------


class TestHypothesisChainer:
    """Tests for HypothesisChainer."""

    def _make_hypothesis(
        self, category: ErrorCategory, posterior: float = 0.5, test_result: str | None = None
    ) -> ScoredHypothesis:
        return ScoredHypothesis(
            description=f"{category.value} hypothesis",
            category=category,
            prior_probability=0.5,
            posterior_probability=posterior,
            test_result=test_result,
        )

    def test_chain_boost_same_category(self, chainer):
        confirmed = self._make_hypothesis(ErrorCategory.CODE_ERROR, posterior=0.8, test_result="PASSED")
        candidate = self._make_hypothesis(ErrorCategory.CODE_ERROR, posterior=0.5)
        candidates = [confirmed, candidate]

        result = chainer.chain(confirmed, candidates)

        boosted = [h for h in result if h is candidate][0]
        assert boosted.posterior_probability > 0.5

    def test_chain_suppress_contradictory(self, chainer):
        confirmed = self._make_hypothesis(ErrorCategory.CODE_ERROR, posterior=0.8, test_result="PASSED")
        candidate = self._make_hypothesis(ErrorCategory.INFRASTRUCTURE, posterior=0.5)
        candidates = [confirmed, candidate]

        result = chainer.chain(confirmed, candidates)

        suppressed = [h for h in result if h is candidate][0]
        assert suppressed.posterior_probability < 0.5

    def test_chain_empty(self, chainer):
        confirmed = self._make_hypothesis(ErrorCategory.CODE_ERROR, posterior=0.8, test_result="PASSED")
        result = chainer.chain(confirmed, [])
        assert result == []


# ---------------------------------------------------------------------------
# TestHypothesisEngine
# ---------------------------------------------------------------------------


class TestHypothesisEngine:
    """Tests for HypothesisEngine."""

    def test_analyze_produces_scored(self, engine, sample_fingerprint, sample_evidence):
        results = engine.analyze(sample_fingerprint, sample_evidence)
        assert isinstance(results, list)
        assert len(results) >= 1
        for h in results:
            assert isinstance(h, ScoredHypothesis)
            assert 0.01 <= h.posterior_probability <= 0.99

    @patch("zerg.diagnostics.hypothesis_engine.subprocess.run")
    def test_auto_test_mocked(self, mock_run, engine, sample_fingerprint, sample_evidence):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        hypotheses = engine.analyze(sample_fingerprint, sample_evidence)
        # Give one a test command so auto_test exercises subprocess
        hypotheses[0].test_command = "python -c 'print(1)'"

        result = engine.auto_test(hypotheses)

        assert isinstance(result, list)
        # The hypothesis with test_command should have been tested
        tested = [h for h in result if h.test_result is not None]
        assert len(tested) >= 1

    def test_get_top_hypothesis(self, engine):
        hypotheses = [
            ScoredHypothesis(
                description="low",
                category=ErrorCategory.UNKNOWN,
                prior_probability=0.1,
                posterior_probability=0.2,
            ),
            ScoredHypothesis(
                description="high",
                category=ErrorCategory.UNKNOWN,
                prior_probability=0.1,
                posterior_probability=0.9,
            ),
        ]
        top = engine.get_top_hypothesis(hypotheses)
        assert top is not None
        assert top.description == "high"

    def test_get_top_hypothesis_empty(self, engine):
        assert engine.get_top_hypothesis([]) is None
