"""Tests for zerg.performance.types module."""

from __future__ import annotations

import pytest

from zerg.performance.types import (
    CategoryScore,
    DetectedStack,
    PerformanceFinding,
    PerformanceReport,
    Severity,
    ToolStatus,
)


class TestSeverityWeight:
    """Tests for Severity.weight() classmethod."""

    def test_critical_weight(self) -> None:
        assert Severity.weight(Severity.CRITICAL) == 25

    def test_high_weight(self) -> None:
        assert Severity.weight(Severity.HIGH) == 10

    def test_medium_weight(self) -> None:
        assert Severity.weight(Severity.MEDIUM) == 5

    def test_low_weight(self) -> None:
        assert Severity.weight(Severity.LOW) == 2

    def test_info_weight(self) -> None:
        assert Severity.weight(Severity.INFO) == 0


class TestPerformanceFinding:
    """Tests for PerformanceFinding dataclass."""

    def test_creation_with_all_fields(self) -> None:
        finding = PerformanceFinding(
            factor_id=42,
            factor_name="N+1 Query",
            category="Database",
            severity=Severity.HIGH,
            message="Detected N+1 query pattern",
            file="app/models.py",
            line=55,
            tool="semgrep",
            rule_id="python.perf.n-plus-one",
            suggestion="Use select_related or prefetch_related",
        )
        assert finding.factor_id == 42
        assert finding.factor_name == "N+1 Query"
        assert finding.category == "Database"
        assert finding.severity == Severity.HIGH
        assert finding.message == "Detected N+1 query pattern"
        assert finding.file == "app/models.py"
        assert finding.line == 55
        assert finding.tool == "semgrep"
        assert finding.rule_id == "python.perf.n-plus-one"
        assert finding.suggestion == "Use select_related or prefetch_related"

    def test_creation_with_defaults(self) -> None:
        finding = PerformanceFinding(
            factor_id=1,
            factor_name="Test",
            category="CPU",
            severity=Severity.LOW,
            message="Test message",
        )
        assert finding.file == ""
        assert finding.line == 0
        assert finding.tool == ""
        assert finding.rule_id == ""
        assert finding.suggestion == ""

    def test_to_dict(self) -> None:
        finding = PerformanceFinding(
            factor_id=1,
            factor_name="Test",
            category="CPU",
            severity=Severity.MEDIUM,
            message="msg",
        )
        d = finding.to_dict()
        assert d["severity"] == "medium"
        assert d["factor_id"] == 1
        assert isinstance(d, dict)


class TestPerformanceReport:
    """Tests for PerformanceReport dataclass."""

    @pytest.fixture()
    def sample_report(self) -> PerformanceReport:
        findings = [
            PerformanceFinding(
                factor_id=1,
                factor_name="Low issue",
                category="CPU",
                severity=Severity.LOW,
                message="low",
            ),
            PerformanceFinding(
                factor_id=2,
                factor_name="Critical issue",
                category="CPU",
                severity=Severity.CRITICAL,
                message="critical",
            ),
            PerformanceFinding(
                factor_id=3,
                factor_name="High issue",
                category="Memory",
                severity=Severity.HIGH,
                message="high",
            ),
            PerformanceFinding(
                factor_id=4,
                factor_name="Medium issue",
                category="IO",
                severity=Severity.MEDIUM,
                message="medium",
            ),
            PerformanceFinding(
                factor_id=5,
                factor_name="Info issue",
                category="CPU",
                severity=Severity.INFO,
                message="info",
            ),
        ]
        return PerformanceReport(
            overall_score=72.5,
            categories=[
                CategoryScore(
                    category="CPU",
                    score=80.0,
                    findings=findings[:1],
                    factors_checked=5,
                    factors_total=10,
                ),
            ],
            tool_statuses=[ToolStatus(name="semgrep", available=True, version="1.0")],
            findings=findings,
            factors_checked=10,
            factors_total=50,
            detected_stack=DetectedStack(
                languages=["python"],
                frameworks=["django"],
                has_docker=True,
                has_kubernetes=False,
            ),
        )

    def test_to_dict_serializes_nested(self, sample_report: PerformanceReport) -> None:
        d = sample_report.to_dict()
        assert isinstance(d, dict)
        assert isinstance(d["categories"], list)
        assert isinstance(d["categories"][0], dict)
        assert isinstance(d["tool_statuses"][0], dict)
        assert isinstance(d["findings"][0], dict)
        assert isinstance(d["detected_stack"], dict)
        assert d["overall_score"] == 72.5
        assert d["detected_stack"]["languages"] == ["python"]

    def test_top_issues_limit(self, sample_report: PerformanceReport) -> None:
        top3 = sample_report.top_issues(limit=3)
        assert len(top3) == 3
        # First should be CRITICAL (weight 25)
        assert top3[0].startswith("[CRITICAL]")
        # Second should be HIGH (weight 10)
        assert top3[1].startswith("[HIGH]")
        # Third should be MEDIUM (weight 5)
        assert top3[2].startswith("[MEDIUM]")

    def test_top_issues_empty_findings(self) -> None:
        report = PerformanceReport(
            overall_score=None,
            categories=[],
            tool_statuses=[],
            findings=[],
            factors_checked=0,
            factors_total=0,
            detected_stack=DetectedStack(languages=[], frameworks=[]),
        )
        assert report.top_issues(limit=3) == []


class TestCategoryScore:
    """Tests for CategoryScore dataclass."""

    def test_score_none(self) -> None:
        cs = CategoryScore(
            category="CPU",
            score=None,
            findings=[],
            factors_checked=0,
            factors_total=10,
        )
        assert cs.score is None
        d = cs.to_dict()
        assert d["score"] is None


class TestDetectedStack:
    """Tests for DetectedStack dataclass."""

    def test_creation(self) -> None:
        stack = DetectedStack(
            languages=["python", "go"],
            frameworks=["django"],
            has_docker=True,
            has_kubernetes=True,
        )
        assert stack.languages == ["python", "go"]
        assert stack.frameworks == ["django"]
        assert stack.has_docker is True
        assert stack.has_kubernetes is True

    def test_defaults(self) -> None:
        stack = DetectedStack(languages=[], frameworks=[])
        assert stack.has_docker is False
        assert stack.has_kubernetes is False
