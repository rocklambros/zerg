"""Bayesian hypothesis ranking and testing engine for ZERG diagnostics."""

from __future__ import annotations

import subprocess

from zerg.diagnostics.knowledge_base import KnownPattern, PatternMatcher
from zerg.diagnostics.types import (
    ErrorCategory,
    ErrorFingerprint,
    Evidence,
    ScoredHypothesis,
)
from zerg.logging import get_logger

logger = get_logger("diagnostics.hypothesis_engine")

__all__ = [
    "BayesianScorer",
    "HypothesisChainer",
    "HypothesisEngine",
    "HypothesisGenerator",
    "HypothesisTestRunner",
]


class BayesianScorer:
    """Simplified Bayesian scoring for diagnostic hypotheses."""

    def compute_posterior(
        self,
        prior: float,
        evidence_for: list[Evidence],
        evidence_against: list[Evidence],
    ) -> float:
        """Compute posterior probability from prior and evidence.

        Simplified Bayesian update: start with prior, multiply by
        (1 + confidence * 0.5) for each positive evidence and by
        (1 - confidence * 0.5) for each negative evidence.
        Result is clamped to [0.01, 0.99].
        """
        posterior = prior
        for ev in evidence_for:
            posterior *= 1.0 + ev.confidence * 0.5
        for ev in evidence_against:
            posterior *= 1.0 - ev.confidence * 0.5
        return max(0.01, min(0.99, posterior))

    def rank(self, hypotheses: list[ScoredHypothesis]) -> list[ScoredHypothesis]:
        """Return hypotheses sorted by posterior_probability descending."""
        return sorted(hypotheses, key=lambda h: h.posterior_probability, reverse=True)


class HypothesisGenerator:
    """Generate diagnostic hypotheses from error fingerprints and evidence."""

    def __init__(self) -> None:
        self._matcher = PatternMatcher()

    def generate(
        self,
        fingerprint: ErrorFingerprint,
        evidence: list[Evidence],
        kb_matches: list[tuple[KnownPattern, float]] | None = None,
    ) -> list[ScoredHypothesis]:
        """Generate hypotheses from fingerprint, evidence, and KB matches.

        Sources:
        - Fingerprint location (if file+line known): prior 0.3
        - Knowledge base matches: prior from KB match score
        - Evidence patterns: prior 0.1
        Returns at most 10 hypotheses.
        """
        hypotheses: list[ScoredHypothesis] = []
        seen_descriptions: set[str] = set()

        # a) Fingerprint location hypothesis
        if fingerprint.file and fingerprint.line > 0:
            desc = f"Error at {fingerprint.file}:{fingerprint.line} ({fingerprint.error_type})"
            if desc not in seen_descriptions:
                seen_descriptions.add(desc)
                hypotheses.append(
                    ScoredHypothesis(
                        description=desc,
                        category=self._category_from_error_type(fingerprint.error_type),
                        prior_probability=0.3,
                        evidence_for=[e for e in evidence if e.confidence >= 0.5],
                        evidence_against=[e for e in evidence if e.confidence < 0.3],
                    )
                )

        # b) Knowledge base matches
        if kb_matches:
            for pattern, score in kb_matches:
                cause = pattern.common_causes[0] if pattern.common_causes else "unknown cause"
                desc = f"Known pattern: {pattern.name} - {cause}"
                if desc not in seen_descriptions:
                    seen_descriptions.add(desc)
                    fix = pattern.fix_templates[0] if pattern.fix_templates else ""
                    hypotheses.append(
                        ScoredHypothesis(
                            description=desc,
                            category=self._category_from_pattern(pattern.category),
                            prior_probability=min(score, 0.99),
                            evidence_for=[e for e in evidence if e.confidence >= 0.5],
                            evidence_against=[],
                            suggested_fix=fix,
                        )
                    )

        # c) Evidence-based hypotheses
        for ev in evidence:
            desc = f"Evidence-based: {ev.description}"
            if desc not in seen_descriptions:
                seen_descriptions.add(desc)
                hypotheses.append(
                    ScoredHypothesis(
                        description=desc,
                        category=ErrorCategory.UNKNOWN,
                        prior_probability=0.1,
                        evidence_for=[ev] if ev.confidence >= 0.5 else [],
                        evidence_against=[ev] if ev.confidence < 0.3 else [],
                    )
                )

        return hypotheses[:10]

    def _category_from_error_type(self, error_type: str) -> ErrorCategory:
        """Map error type string to ErrorCategory."""
        mapping: dict[str, ErrorCategory] = {
            "ImportError": ErrorCategory.DEPENDENCY,
            "ModuleNotFoundError": ErrorCategory.DEPENDENCY,
            "SyntaxError": ErrorCategory.CODE_ERROR,
            "TypeError": ErrorCategory.CODE_ERROR,
            "ValueError": ErrorCategory.CODE_ERROR,
            "KeyError": ErrorCategory.CODE_ERROR,
            "AttributeError": ErrorCategory.CODE_ERROR,
            "FileNotFoundError": ErrorCategory.INFRASTRUCTURE,
            "PermissionError": ErrorCategory.INFRASTRUCTURE,
            "ConnectionError": ErrorCategory.INFRASTRUCTURE,
            "TimeoutError": ErrorCategory.INFRASTRUCTURE,
            "OSError": ErrorCategory.INFRASTRUCTURE,
        }
        return mapping.get(error_type, ErrorCategory.UNKNOWN)

    def _category_from_pattern(self, category: str) -> ErrorCategory:
        """Map pattern category string to ErrorCategory."""
        mapping: dict[str, ErrorCategory] = {
            "python": ErrorCategory.CODE_ERROR,
            "zerg": ErrorCategory.WORKER_FAILURE,
            "general": ErrorCategory.UNKNOWN,
        }
        return mapping.get(category, ErrorCategory.UNKNOWN)


class HypothesisTestRunner:
    """Run test commands to validate hypotheses."""

    SAFE_PREFIXES: list[str] = [
        "python",
        "pip",
        "git",
        "ls",
        "cat",
        "zerg",
        "docker",
        "node",
        "npm",
        "which",
        "echo",
        "test",
    ]

    def can_test(self, hypothesis: ScoredHypothesis) -> bool:
        """Check if hypothesis has a testable, safe command."""
        cmd = hypothesis.test_command.strip()
        if not cmd:
            return False
        return any(cmd.startswith(prefix) for prefix in self.SAFE_PREFIXES)

    def test(self, hypothesis: ScoredHypothesis, timeout: int = 30) -> ScoredHypothesis:
        """Run the hypothesis test command and update scoring.

        On success (rc=0): test_result='PASSED', posterior boosted 1.5x.
        On failure (rc!=0): test_result='FAILED', posterior reduced 0.5x.
        On timeout/error: test_result='ERROR: ...'.
        Posterior is clamped to [0.01, 0.99].
        """
        if not self.can_test(hypothesis):
            return hypothesis

        try:
            result = subprocess.run(  # noqa: S602
                hypothesis.test_command,
                shell=True,
                capture_output=True,
                timeout=timeout,
                text=True,
            )
            if result.returncode == 0:
                hypothesis.test_result = "PASSED"
                hypothesis.posterior_probability = min(0.99, hypothesis.posterior_probability * 1.5)
            else:
                hypothesis.test_result = "FAILED"
                hypothesis.posterior_probability = max(0.01, hypothesis.posterior_probability * 0.5)
        except subprocess.TimeoutExpired:
            hypothesis.test_result = f"ERROR: timeout after {timeout}s"
        except Exception as exc:  # noqa: BLE001
            hypothesis.test_result = f"ERROR: {exc}"

        hypothesis.posterior_probability = max(0.01, min(0.99, hypothesis.posterior_probability))
        return hypothesis


class HypothesisChainer:
    """Chain hypothesis results to update related hypotheses."""

    _CONTRADICTORY_PAIRS: list[tuple[ErrorCategory, ErrorCategory]] = [
        (ErrorCategory.CODE_ERROR, ErrorCategory.INFRASTRUCTURE),
        (ErrorCategory.DEPENDENCY, ErrorCategory.CONFIGURATION),
    ]

    def chain(
        self,
        confirmed: ScoredHypothesis,
        candidates: list[ScoredHypothesis],
    ) -> list[ScoredHypothesis]:
        """Update candidate posteriors based on a confirmed hypothesis.

        When a hypothesis is confirmed (test_result='PASSED'):
        - Boost same-category hypotheses by 1.2x
        - Suppress contradictory-category hypotheses by 0.7x
        Posteriors are clamped to [0.01, 0.99].
        """
        if confirmed.test_result != "PASSED":
            return candidates

        contradictory_categories = self._get_contradictory(confirmed.category)

        for h in candidates:
            if h is confirmed:
                continue
            if h.category == confirmed.category:
                h.posterior_probability = min(0.99, h.posterior_probability * 1.2)
            elif h.category in contradictory_categories:
                h.posterior_probability = max(0.01, h.posterior_probability * 0.7)

        return candidates

    def _get_contradictory(self, category: ErrorCategory) -> set[ErrorCategory]:
        """Return categories that contradict the given category."""
        result: set[ErrorCategory] = set()
        for a, b in self._CONTRADICTORY_PAIRS:
            if category == a:
                result.add(b)
            elif category == b:
                result.add(a)
        return result


class HypothesisEngine:
    """Facade combining generation, scoring, testing, and chaining."""

    def __init__(self) -> None:
        self._scorer = BayesianScorer()
        self._generator = HypothesisGenerator()
        self._test_runner = HypothesisTestRunner()
        self._chainer = HypothesisChainer()

    def analyze(
        self,
        fingerprint: ErrorFingerprint,
        evidence: list[Evidence],
    ) -> list[ScoredHypothesis]:
        """Generate, score, and rank hypotheses for a given error."""
        hypotheses = self._generator.generate(fingerprint, evidence)
        for h in hypotheses:
            h.posterior_probability = self._scorer.compute_posterior(
                h.prior_probability, h.evidence_for, h.evidence_against
            )
        return self._scorer.rank(hypotheses)

    def auto_test(
        self,
        hypotheses: list[ScoredHypothesis],
        max_tests: int = 3,
    ) -> list[ScoredHypothesis]:
        """Test top N testable hypotheses, chain results, re-rank."""
        tested = 0
        for h in hypotheses:
            if tested >= max_tests:
                break
            if self._test_runner.can_test(h):
                self._test_runner.test(h)
                if h.test_result == "PASSED":
                    self._chainer.chain(h, hypotheses)
                tested += 1
        return self._scorer.rank(hypotheses)

    def get_top_hypothesis(self, hypotheses: list[ScoredHypothesis]) -> ScoredHypothesis | None:
        """Return the hypothesis with the highest posterior, or None."""
        if not hypotheses:
            return None
        return max(hypotheses, key=lambda h: h.posterior_probability)
