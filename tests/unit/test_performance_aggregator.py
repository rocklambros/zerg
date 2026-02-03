"""Unit tests for performance aggregator (PerformanceAuditor)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from zerg.performance.aggregator import PerformanceAuditor
from zerg.performance.types import (
    DetectedStack,
    PerformanceFinding,
    Severity,
    ToolStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeAdapter:
    """A fake adapter that returns predetermined findings."""

    def __init__(
        self,
        name: str,
        tool_name: str,
        findings: list[PerformanceFinding],
        factors: list[int] | None = None,
    ) -> None:
        self.name = name
        self.tool_name = tool_name
        self._findings = findings
        self.factors_covered = factors or []

    def run(
        self,
        files: list[str],
        project_path: str,
        stack: DetectedStack,
    ) -> list[PerformanceFinding]:
        return self._findings

    def is_applicable(self, stack: DetectedStack) -> bool:
        return True


def _make_finding(
    category: str = "TestCat",
    severity: Severity = Severity.MEDIUM,
    factor_id: int = 1,
) -> PerformanceFinding:
    return PerformanceFinding(
        factor_id=factor_id,
        factor_name="Test factor",
        category=category,
        severity=severity,
        message="test finding",
        file="test.py",
        line=1,
        tool="fake",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPerformanceAuditor:
    """Tests for the PerformanceAuditor orchestrator."""

    @patch("zerg.performance.aggregator.detect_stack")
    @patch("zerg.performance.aggregator.ToolRegistry")
    @patch("zerg.performance.aggregator.FactorCatalog.load")
    def test_no_tools_available(
        self,
        mock_catalog_load: MagicMock,
        mock_registry_cls: MagicMock,
        mock_detect: MagicMock,
    ) -> None:
        """When no tools are available, report has no findings and overall_score=None."""
        mock_detect.return_value = DetectedStack(languages=["python"], frameworks=[])

        mock_registry = MagicMock()
        mock_registry.check_availability.return_value = [
            ToolStatus(name="semgrep", available=False),
            ToolStatus(name="radon", available=False),
        ]
        mock_registry_cls.return_value = mock_registry

        mock_catalog = MagicMock()
        mock_catalog.filter_static_only.return_value = []
        mock_catalog.get_factors_by_category.return_value = {}
        mock_catalog_load.return_value = mock_catalog

        auditor = PerformanceAuditor(".")
        report = auditor.run([])

        assert report.findings == []
        assert report.overall_score is None
        assert report.factors_checked == 0

    @patch("zerg.performance.aggregator.detect_stack")
    @patch("zerg.performance.aggregator.ToolRegistry")
    @patch("zerg.performance.aggregator.FactorCatalog.load")
    def test_synthetic_findings_scoring(
        self,
        mock_catalog_load: MagicMock,
        mock_registry_cls: MagicMock,
        mock_detect: MagicMock,
    ) -> None:
        """Verify scoring math with synthetic findings.

        1 CRITICAL finding in a category with 5 static factors:
        penalty = 25, score = max(0, 100 - (25/5)*10) = 50.0
        """
        mock_detect.return_value = DetectedStack(languages=["python"], frameworks=[])

        mock_registry = MagicMock()
        mock_registry.check_availability.return_value = [
            ToolStatus(name="fake", available=True),
        ]
        mock_registry_cls.return_value = mock_registry

        critical_finding = _make_finding(category="TestCat", severity=Severity.CRITICAL, factor_id=1)

        # Create mock catalog with 5 static factors in TestCat
        # cli_tools must contain a name from STATIC_TOOLS for counting
        mock_factor = MagicMock()
        mock_factor.cli_tools = ["semgrep"]
        mock_catalog = MagicMock()
        mock_catalog.filter_static_only.return_value = [mock_factor] * 5
        mock_catalog.get_factors_by_category.return_value = {
            "TestCat": [mock_factor] * 5,
        }
        mock_catalog_load.return_value = mock_catalog

        auditor = PerformanceAuditor(".")

        fake_adapter = FakeAdapter(
            name="fake",
            tool_name="fake",
            findings=[critical_finding],
            factors=[1],
        )

        with patch.object(auditor, "_get_adapters", return_value=[fake_adapter]):
            report = auditor.run(["test.py"])

        assert len(report.findings) == 1

        # Find the TestCat category score
        test_cat = next(c for c in report.categories if c.category == "TestCat")
        assert test_cat.factors_checked == 5
        assert test_cat.score == pytest.approx(50.0)

    @patch("zerg.performance.aggregator.detect_stack")
    @patch("zerg.performance.aggregator.ToolRegistry")
    @patch("zerg.performance.aggregator.FactorCatalog.load")
    def test_low_finding_scoring(
        self,
        mock_catalog_load: MagicMock,
        mock_registry_cls: MagicMock,
        mock_detect: MagicMock,
    ) -> None:
        """1 LOW finding in a category with 10 factors:
        penalty = 2, score = max(0, 100 - (2/10)*10) = 98.0
        """
        mock_detect.return_value = DetectedStack(languages=["python"], frameworks=[])

        mock_registry = MagicMock()
        mock_registry.check_availability.return_value = [
            ToolStatus(name="fake", available=True),
        ]
        mock_registry_cls.return_value = mock_registry

        low_finding = _make_finding(category="BigCat", severity=Severity.LOW, factor_id=2)

        mock_factor = MagicMock()
        mock_factor.cli_tools = ["semgrep"]
        mock_catalog = MagicMock()
        mock_catalog.filter_static_only.return_value = [mock_factor] * 10
        mock_catalog.get_factors_by_category.return_value = {
            "BigCat": [mock_factor] * 10,
        }
        mock_catalog_load.return_value = mock_catalog

        auditor = PerformanceAuditor(".")

        fake_adapter = FakeAdapter(
            name="fake",
            tool_name="fake",
            findings=[low_finding],
            factors=[2],
        )

        with patch.object(auditor, "_get_adapters", return_value=[fake_adapter]):
            report = auditor.run(["test.py"])

        big_cat = next(c for c in report.categories if c.category == "BigCat")
        assert big_cat.factors_checked == 10
        assert big_cat.score == pytest.approx(98.0)

    @patch("zerg.performance.aggregator.detect_stack")
    @patch("zerg.performance.aggregator.ToolRegistry")
    @patch("zerg.performance.aggregator.FactorCatalog.load")
    def test_overall_score_weighted_average(
        self,
        mock_catalog_load: MagicMock,
        mock_registry_cls: MagicMock,
        mock_detect: MagicMock,
    ) -> None:
        """Overall score should be a weighted average of category scores."""
        mock_detect.return_value = DetectedStack(languages=["python"], frameworks=[])

        mock_registry = MagicMock()
        mock_registry.check_availability.return_value = [
            ToolStatus(name="fake", available=True),
        ]
        mock_registry_cls.return_value = mock_registry

        # Cat A: 1 CRITICAL, 5 factors -> score 50, weight 5
        # Cat B: 1 LOW, 10 factors -> score 98, weight 10
        finding_a = _make_finding(category="CatA", severity=Severity.CRITICAL, factor_id=1)
        finding_b = _make_finding(category="CatB", severity=Severity.LOW, factor_id=2)

        mock_factor = MagicMock()
        mock_factor.cli_tools = ["semgrep"]
        mock_catalog = MagicMock()
        mock_catalog.filter_static_only.return_value = [mock_factor] * 15
        mock_catalog.get_factors_by_category.return_value = {
            "CatA": [mock_factor] * 5,
            "CatB": [mock_factor] * 10,
        }
        mock_catalog_load.return_value = mock_catalog

        auditor = PerformanceAuditor(".")

        fake_adapter = FakeAdapter(
            name="fake",
            tool_name="fake",
            findings=[finding_a, finding_b],
            factors=[1, 2],
        )

        with patch.object(auditor, "_get_adapters", return_value=[fake_adapter]):
            report = auditor.run(["test.py"])

        # Weighted average: (50*5 + 98*10) / (5+10) = (250 + 980)/15 = 82.0
        assert report.overall_score is not None
        assert report.overall_score == pytest.approx(82.0)

    @patch("zerg.performance.aggregator.detect_stack")
    @patch("zerg.performance.aggregator.ToolRegistry")
    @patch("zerg.performance.aggregator.FactorCatalog.load")
    def test_empty_files(
        self,
        mock_catalog_load: MagicMock,
        mock_registry_cls: MagicMock,
        mock_detect: MagicMock,
    ) -> None:
        """run([]) should not crash."""
        mock_detect.return_value = DetectedStack(languages=[], frameworks=[])

        mock_registry = MagicMock()
        mock_registry.check_availability.return_value = []
        mock_registry_cls.return_value = mock_registry

        mock_catalog = MagicMock()
        mock_catalog.filter_static_only.return_value = []
        mock_catalog.get_factors_by_category.return_value = {}
        mock_catalog_load.return_value = mock_catalog

        auditor = PerformanceAuditor(".")
        report = auditor.run([])

        assert report is not None
        assert report.findings == []
        assert report.overall_score is None
