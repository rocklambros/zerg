"""Unit tests for performance analysis report formatters."""

from __future__ import annotations

import json
from io import StringIO

from rich.console import Console

from zerg.performance.formatters import (
    format_json,
    format_markdown,
    format_rich,
    format_sarif,
)
from zerg.performance.types import (
    CategoryScore,
    DetectedStack,
    PerformanceFinding,
    PerformanceReport,
    Severity,
    ToolStatus,
)


def _sample_report() -> PerformanceReport:
    finding = PerformanceFinding(
        factor_id=1,
        factor_name="Test factor",
        category="TestCat",
        severity=Severity.MEDIUM,
        message="A test finding",
        file="test.py",
        line=42,
        tool="test-tool",
        rule_id="TEST-001",
        suggestion="Fix the thing",
    )
    return PerformanceReport(
        overall_score=85.0,
        categories=[
            CategoryScore(category="TestCat", score=85.0, findings=[finding], factors_checked=5, factors_total=10),
        ],
        tool_statuses=[ToolStatus(name="test-tool", available=True, version="1.0", factors_covered=5)],
        findings=[finding],
        factors_checked=5,
        factors_total=10,
        detected_stack=DetectedStack(languages=["python"], frameworks=["flask"], has_docker=True),
    )


def _empty_report() -> PerformanceReport:
    return PerformanceReport(
        overall_score=None,
        categories=[],
        tool_statuses=[],
        findings=[],
        factors_checked=0,
        factors_total=0,
        detected_stack=DetectedStack(languages=[], frameworks=[]),
    )


class TestFormatJson:
    def test_valid_json(self) -> None:
        data = json.loads(format_json(_sample_report()))
        assert data["overall_score"] == 85.0
        assert len(data["findings"]) == 1

    def test_empty_report(self) -> None:
        data = json.loads(format_json(_empty_report()))
        assert data["overall_score"] is None
        assert data["findings"] == []


class TestFormatSarif:
    def test_valid_sarif_structure(self) -> None:
        data = json.loads(format_sarif(_sample_report()))
        assert data["version"] == "2.1.0"
        run = data["runs"][0]
        assert len(run["results"]) == 1
        assert run["results"][0]["ruleId"] == "PERF-1"

    def test_empty_report(self) -> None:
        data = json.loads(format_sarif(_empty_report()))
        assert data["runs"][0]["results"] == []


class TestFormatMarkdown:
    def test_contains_expected_sections(self) -> None:
        output = format_markdown(_sample_report())
        assert "# Performance Analysis Report" in output
        assert "85/100" in output
        assert "python" in output

    def test_empty_report(self) -> None:
        output = format_markdown(_empty_report())
        assert "N/A/100" in output
        assert "Total findings: 0" in output


class TestFormatRich:
    def test_does_not_crash(self) -> None:
        console = Console(file=StringIO(), force_terminal=True)
        format_rich(_sample_report(), console)
        assert len(console.file.getvalue()) > 0  # type: ignore[union-attr]

    def test_empty_report_does_not_crash(self) -> None:
        console = Console(file=StringIO(), force_terminal=True)
        format_rich(_empty_report(), console)
        assert len(console.file.getvalue()) > 0  # type: ignore[union-attr]
