"""Tests for zerg.diagnostics.hypothesis_engine."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from zerg.diagnostics.hypothesis_engine import (
    BayesianScorer,
    HypothesisChainer,
    HypothesisEngine,
    HypothesisGenerator,
    HypothesisTestRunner,
)
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
    def test_posterior_positive_evidence(self, scorer):
        ev_for = [Evidence(description="match", source="code", confidence=0.8)]
        result = scorer.compute_posterior(0.5, ev_for, [])
        assert result > 0.5

    def test_posterior_negative_evidence(self, scorer):
        ev_against = [Evidence(description="mismatch", source="code", confidence=0.8)]
        result = scorer.compute_posterior(0.5, [], ev_against)
        assert result < 0.5

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
        assert ranked[2].description == "low"


# ---------------------------------------------------------------------------
# TestHypothesisGenerator
# ---------------------------------------------------------------------------


class TestHypothesisGenerator:
    def test_generate_from_fingerprint(self, generator, sample_fingerprint, sample_evidence):
        results = generator.generate(sample_fingerprint, sample_evidence)
        assert len(results) >= 1
        assert "test.py:42" in results[0].description
        assert results[0].category == ErrorCategory.CODE_ERROR

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
        assert len(results) == 0


# ---------------------------------------------------------------------------
# TestHypothesisTestRunner
# ---------------------------------------------------------------------------


class TestHypothesisTestRunner:
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

    @pytest.mark.parametrize(
        "command,expected",
        [
            ("echo 'test'", True),
            ("rm -rf /", False),
            ("", False),
            ("git status", True),
        ],
    )
    def test_can_test(self, runner, command, expected):
        h = self._make_hypothesis(test_command=command)
        assert runner.can_test(h) is expected

    def test_test_success(self, runner):
        h = self._make_hypothesis(test_command="echo 'test'")
        original_posterior = h.posterior_probability
        result = runner.test(h)
        assert result.test_result == "PASSED"
        assert result.posterior_probability > original_posterior

    def test_test_failure(self, runner):
        h = self._make_hypothesis(test_command="false")
        original_posterior = h.posterior_probability
        result = runner.test(h)
        assert result.test_result == "FAILED"
        assert result.posterior_probability < original_posterior

    def test_test_timeout(self, runner):
        with patch.object(runner._executor, "execute") as mock_execute:
            mock_execute.side_effect = subprocess.TimeoutExpired(cmd="echo", timeout=30)
            h = self._make_hypothesis(test_command="echo 'test'")
            result = runner.test(h)
            assert result.test_result is not None
            assert "ERROR" in result.test_result or "timeout" in result.test_result.lower()


# ---------------------------------------------------------------------------
# TestHypothesisChainer
# ---------------------------------------------------------------------------


class TestHypothesisChainer:
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
        result = chainer.chain(confirmed, [confirmed, candidate])
        boosted = [h for h in result if h is candidate][0]
        assert boosted.posterior_probability > 0.5

    def test_chain_suppress_contradictory(self, chainer):
        confirmed = self._make_hypothesis(ErrorCategory.CODE_ERROR, posterior=0.8, test_result="PASSED")
        candidate = self._make_hypothesis(ErrorCategory.INFRASTRUCTURE, posterior=0.5)
        result = chainer.chain(confirmed, [confirmed, candidate])
        suppressed = [h for h in result if h is candidate][0]
        assert suppressed.posterior_probability < 0.5


# ---------------------------------------------------------------------------
# TestHypothesisEngine
# ---------------------------------------------------------------------------


class TestHypothesisEngine:
    def test_analyze_produces_scored(self, engine, sample_fingerprint, sample_evidence):
        results = engine.analyze(sample_fingerprint, sample_evidence)
        assert isinstance(results, list)
        assert len(results) >= 1
        for h in results:
            assert isinstance(h, ScoredHypothesis)
            assert 0.01 <= h.posterior_probability <= 0.99

    def test_get_top_hypothesis_empty(self, engine):
        assert engine.get_top_hypothesis([]) is None
