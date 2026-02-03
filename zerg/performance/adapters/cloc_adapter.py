"""cloc adapter for code volume metrics."""

from __future__ import annotations

import json
import logging
import subprocess

from zerg.performance.adapters.base import BaseToolAdapter
from zerg.performance.types import DetectedStack, PerformanceFinding, Severity

logger = logging.getLogger(__name__)


class ClocAdapter(BaseToolAdapter):
    """Adapter for cloc (Count Lines of Code) analysis."""

    name: str = "cloc"
    tool_name: str = "cloc"
    # Factor 115 = Microservice fragmentation (Architecture — uses cloc for size metrics)
    factors_covered: list[int] = [115]

    def is_applicable(self, stack: DetectedStack) -> bool:
        """cloc supports all languages; always applicable."""
        return True

    def run(
        self,
        files: list[str],
        project_path: str,
        stack: DetectedStack,
    ) -> list[PerformanceFinding]:
        """Run cloc and return code volume findings."""
        try:
            result = subprocess.run(
                ["cloc", "--json", project_path],
                capture_output=True,
                text=True,
                timeout=180,
            )
            data = json.loads(result.stdout)
        except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
            logger.debug("cloc failed or produced unparseable output", exc_info=True)
            return []

        if not isinstance(data, dict):
            logger.debug("cloc output is not a JSON object")
            return []

        return self._analyze(data)

    def _analyze(self, data: dict[str, object]) -> list[PerformanceFinding]:
        """Analyze cloc JSON output for code volume metrics."""
        summary = data.get("SUM")
        if not isinstance(summary, dict):
            logger.debug("cloc output missing SUM section")
            return []

        code_lines = summary.get("code", 0)
        comment_lines = summary.get("comment", 0)
        n_files = summary.get("nFiles", 0)

        if not isinstance(code_lines, int | float):
            code_lines = 0
        if not isinstance(comment_lines, int | float):
            comment_lines = 0
        if not isinstance(n_files, int | float):
            n_files = 0

        findings: list[PerformanceFinding] = []

        # Comment ratio analysis
        total_meaningful = code_lines + comment_lines
        if total_meaningful > 0:
            comment_ratio = comment_lines / total_meaningful
            if comment_ratio < 0.05:
                findings.append(
                    PerformanceFinding(
                        factor_id=115,
                        factor_name="Code volume metrics",
                        category="Architecture",
                        severity=Severity.MEDIUM,
                        message=(
                            f"Low documentation ratio: {comment_ratio:.1%} comments "
                            f"({int(comment_lines)} comment lines / {int(total_meaningful)} total)"
                        ),
                        tool=self.name,
                        rule_id="low-comment-ratio",
                        suggestion=("Increase inline documentation, especially for public APIs and complex logic"),
                    )
                )

        # Large codebase info
        if code_lines > 100_000:
            findings.append(
                PerformanceFinding(
                    factor_id=115,
                    factor_name="Code volume metrics",
                    category="Architecture",
                    severity=Severity.INFO,
                    message=(f"Large codebase: {int(code_lines):,} lines of code across {int(n_files):,} files"),
                    tool=self.name,
                    rule_id="large-codebase",
                    suggestion="Consider modularization if the codebase continues to grow",
                )
            )

        return findings
