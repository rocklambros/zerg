"""Radon adapter for cyclomatic complexity and maintainability index analysis."""

from __future__ import annotations

import json
import logging
import subprocess

from zerg.performance.adapters.base import BaseToolAdapter
from zerg.performance.types import DetectedStack, PerformanceFinding, Severity

logger = logging.getLogger(__name__)

# Radon rank -> severity mapping (C and worse are noteworthy)
_RANK_SEVERITY: dict[str, Severity] = {
    "C": Severity.MEDIUM,
    "D": Severity.HIGH,
    "E": Severity.CRITICAL,
    "F": Severity.CRITICAL,
}


class RadonAdapter(BaseToolAdapter):
    """Adapter for radon cyclomatic-complexity and maintainability-index analysis."""

    name: str = "radon"
    tool_name: str = "radon"
    # Factor IDs: 1 = Algorithm complexity (CPU/Compute),
    # plus maintainability-related factors from Code-Level Patterns
    factors_covered: list[int] = [1, 28, 29]

    def is_applicable(self, stack: DetectedStack) -> bool:
        """Radon only works on Python source code."""
        return "python" in stack.languages

    def run(
        self,
        files: list[str],
        project_path: str,
        stack: DetectedStack,
    ) -> list[PerformanceFinding]:
        """Run radon cc and radon mi, return combined findings."""
        findings: list[PerformanceFinding] = []
        findings.extend(self._run_cyclomatic_complexity(project_path))
        findings.extend(self._run_maintainability_index(project_path))
        return findings

    # ------------------------------------------------------------------
    # Cyclomatic complexity (radon cc)
    # ------------------------------------------------------------------

    def _run_cyclomatic_complexity(self, project_path: str) -> list[PerformanceFinding]:
        """Run ``radon cc -j -a`` and return findings for ranks C-F."""
        try:
            result = subprocess.run(
                ["radon", "cc", "-j", "-a", project_path],
                capture_output=True,
                text=True,
                timeout=120,
            )
            data = json.loads(result.stdout)
        except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
            logger.debug("radon cc failed or produced unparseable output", exc_info=True)
            return []

        findings: list[PerformanceFinding] = []
        for filepath, blocks in data.items():
            if not isinstance(blocks, list):
                continue
            for block in blocks:
                rank = block.get("rank", "A")
                severity = _RANK_SEVERITY.get(rank)
                if severity is None:
                    continue
                name = block.get("name", "<unknown>")
                complexity = block.get("complexity", "?")
                block_type = block.get("type", "block")
                findings.append(
                    PerformanceFinding(
                        factor_id=1,
                        factor_name="Algorithm complexity",
                        category="CPU / Compute",
                        severity=severity,
                        message=(f"{block_type} '{name}' has cyclomatic complexity {complexity} (rank {rank})"),
                        file=filepath,
                        line=block.get("lineno", 0),
                        tool=self.name,
                        rule_id=f"cc-rank-{rank}",
                        suggestion=f"Refactor '{name}' to reduce cyclomatic complexity",
                    )
                )
        return findings

    # ------------------------------------------------------------------
    # Maintainability index (radon mi)
    # ------------------------------------------------------------------

    def _run_maintainability_index(self, project_path: str) -> list[PerformanceFinding]:
        """Run ``radon mi -j`` and return findings for ranks C-F."""
        try:
            result = subprocess.run(
                ["radon", "mi", "-j", project_path],
                capture_output=True,
                text=True,
                timeout=120,
            )
            data = json.loads(result.stdout)
        except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
            logger.debug("radon mi failed or produced unparseable output", exc_info=True)
            return []

        findings: list[PerformanceFinding] = []
        for filepath, info in data.items():
            if not isinstance(info, dict):
                continue
            rank = info.get("rank", "A")
            severity = _RANK_SEVERITY.get(rank)
            if severity is None:
                continue
            mi_score = info.get("mi", 0.0)
            findings.append(
                PerformanceFinding(
                    factor_id=28,
                    factor_name="Maintainability index",
                    category="Code-Level Patterns",
                    severity=severity,
                    message=(f"File has maintainability index {mi_score:.1f} (rank {rank})"),
                    file=filepath,
                    line=0,
                    tool=self.name,
                    rule_id=f"mi-rank-{rank}",
                    suggestion="Improve code structure to raise maintainability index",
                )
            )
        return findings
