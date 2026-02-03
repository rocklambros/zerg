"""Performance aggregator — main orchestrator for the ZERG performance analysis system."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from zerg.performance.adapters.base import BaseToolAdapter
from zerg.performance.catalog import STATIC_TOOLS, FactorCatalog
from zerg.performance.stack_detector import detect_stack
from zerg.performance.tool_registry import ToolRegistry
from zerg.performance.types import (
    CategoryScore,
    PerformanceFinding,
    PerformanceReport,
    Severity,
)

logger = logging.getLogger(__name__)

# Severity weights for scoring
SEVERITY_WEIGHTS: dict[Severity, int] = {
    Severity.CRITICAL: 25,
    Severity.HIGH: 10,
    Severity.MEDIUM: 5,
    Severity.LOW: 2,
    Severity.INFO: 0,
}


class PerformanceAuditor:
    """Main orchestrator that runs all tool adapters and produces a unified report."""

    def __init__(self, project_path: str = ".") -> None:
        self.project_path = project_path
        self.catalog = FactorCatalog.load()
        self.registry = ToolRegistry()
        self.stack = detect_stack(project_path)

    def run(self, files: list[str]) -> PerformanceReport:
        """Run full performance audit.

        Args:
            files: List of file paths to analyse.

        Returns:
            A complete ``PerformanceReport`` with scores, findings and metadata.
        """
        # 1. Check tool availability (parallel)
        tool_statuses = self.registry.check_availability()
        available_tools = {t.name for t in tool_statuses if t.available}

        # 2. Get static-only factors
        static_factors = self.catalog.filter_static_only()

        # 3. Select applicable adapters
        adapters = self._get_adapters(available_tools)

        # 4. Run adapters in parallel
        all_findings = self._run_adapters(adapters, files)

        # 5. Compute category scores
        categories = self._compute_category_scores(all_findings, static_factors)

        # 6. Compute overall score
        overall = self._compute_overall_score(categories)

        # 7. Count factors checked
        checked_factor_ids: set[int] = set()
        for adapter in adapters:
            checked_factor_ids.update(adapter.factors_covered)

        return PerformanceReport(
            overall_score=overall,
            categories=categories,
            tool_statuses=tool_statuses,
            findings=all_findings,
            factors_checked=len(checked_factor_ids),
            factors_total=len(static_factors),
            detected_stack=self.stack,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_adapters(self, available_tools: set[str]) -> list[BaseToolAdapter]:
        """Import and instantiate all applicable adapters."""
        from zerg.performance.adapters.cloc_adapter import ClocAdapter
        from zerg.performance.adapters.deptry_adapter import DeptryAdapter
        from zerg.performance.adapters.dive_adapter import DiveAdapter
        from zerg.performance.adapters.hadolint_adapter import HadolintAdapter
        from zerg.performance.adapters.jscpd_adapter import JscpdAdapter
        from zerg.performance.adapters.lizard_adapter import LizardAdapter
        from zerg.performance.adapters.pipdeptree_adapter import PipdeptreeAdapter
        from zerg.performance.adapters.radon_adapter import RadonAdapter
        from zerg.performance.adapters.semgrep_adapter import SemgrepAdapter
        from zerg.performance.adapters.trivy_adapter import TrivyAdapter
        from zerg.performance.adapters.vulture_adapter import VultureAdapter

        all_adapters: list[BaseToolAdapter] = [
            SemgrepAdapter(),
            RadonAdapter(),
            LizardAdapter(),
            VultureAdapter(),
            JscpdAdapter(),
            DeptryAdapter(),
            PipdeptreeAdapter(),
            DiveAdapter(),
            HadolintAdapter(),
            TrivyAdapter(),
            ClocAdapter(),
        ]

        # Filter to applicable + available
        return [a for a in all_adapters if a.tool_name in available_tools and a.is_applicable(self.stack)]

    def _run_adapters(self, adapters: list[BaseToolAdapter], files: list[str]) -> list[PerformanceFinding]:
        """Run all adapters in parallel."""
        all_findings: list[PerformanceFinding] = []

        if not adapters:
            return all_findings

        with ThreadPoolExecutor(max_workers=min(len(adapters), 8)) as executor:
            futures = {executor.submit(a.run, files, self.project_path, self.stack): a for a in adapters}
            for future in as_completed(futures):
                adapter = futures[future]
                try:
                    findings = future.result(timeout=300)
                    all_findings.extend(findings)
                    logger.info("Adapter %s: %d findings", adapter.name, len(findings))
                except Exception:
                    logger.warning("Adapter %s failed", adapter.name, exc_info=True)

        return all_findings

    def _compute_category_scores(
        self,
        findings: list[PerformanceFinding],
        static_factors: list,
    ) -> list[CategoryScore]:
        """Compute per-category scores."""
        # Group factors by category
        factors_by_cat = self.catalog.get_factors_by_category()

        # Group findings by category
        findings_by_cat: dict[str, list[PerformanceFinding]] = {}
        for f in findings:
            findings_by_cat.setdefault(f.category, []).append(f)

        static_set = set(STATIC_TOOLS)
        categories: list[CategoryScore] = []
        for cat_name, cat_factors in factors_by_cat.items():
            # Count how many factors in this category have static tools
            static_in_cat = [fac for fac in cat_factors if any(t in static_set for t in fac.cli_tools)]

            cat_findings = findings_by_cat.get(cat_name, [])
            factors_checked = len(static_in_cat)

            if factors_checked == 0:
                score = None
            else:
                penalty = sum(SEVERITY_WEIGHTS.get(f.severity, 0) for f in cat_findings)
                score = max(0.0, 100.0 - (penalty / max(1, factors_checked)) * 10)

            categories.append(
                CategoryScore(
                    category=cat_name,
                    score=score,
                    findings=cat_findings,
                    factors_checked=factors_checked,
                    factors_total=len(cat_factors),
                )
            )

        # Sort by score (None last, then ascending)
        categories.sort(
            key=lambda c: (
                c.score is None,
                c.score if c.score is not None else 999,
            )
        )

        return categories

    def _compute_overall_score(self, categories: list[CategoryScore]) -> float | None:
        """Compute weighted average overall score."""
        scored = [(c.score, c.factors_checked) for c in categories if c.score is not None]
        if not scored:
            return None
        total_weight = sum(w for _, w in scored)
        if total_weight == 0:
            return None
        return sum(s * w for s, w in scored) / total_weight
