"""jscpd adapter for copy-paste / code duplication detection."""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from pathlib import Path

from zerg.performance.adapters.base import BaseToolAdapter
from zerg.performance.types import DetectedStack, PerformanceFinding, Severity

logger = logging.getLogger(__name__)


class JscpdAdapter(BaseToolAdapter):
    """Adapter for jscpd copy-paste detection across multiple languages."""

    name: str = "jscpd"
    tool_name: str = "jscpd"
    # Factor 84 = Copy-paste with variations (Code Volume)
    factors_covered: list[int] = [84]

    def is_applicable(self, stack: DetectedStack) -> bool:
        """jscpd supports many languages; always applicable."""
        return True

    def run(
        self,
        files: list[str],
        project_path: str,
        stack: DetectedStack,
    ) -> list[PerformanceFinding]:
        """Run jscpd and return duplication findings."""
        tmpdir = tempfile.mkdtemp(prefix="jscpd-")
        try:
            return self._execute(project_path, tmpdir)
        finally:
            # Best-effort cleanup of temp directory
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)

    def _execute(self, project_path: str, output_dir: str) -> list[PerformanceFinding]:
        """Execute jscpd and parse the JSON report."""
        try:
            subprocess.run(
                [
                    "jscpd",
                    project_path,
                    "--reporters",
                    "json",
                    "--output",
                    output_dir,
                    "--ignore",
                    "htmlcov/**",
                    "--ignore",
                    ".claude/commands/**",
                    "--ignore",
                    ".zerg/**",
                    "--ignore",
                    ".gsd/**",
                ],
                capture_output=True,
                text=True,
                timeout=180,
            )
        except (subprocess.SubprocessError, OSError):
            logger.debug("jscpd execution failed", exc_info=True)
            return []

        report_path = Path(output_dir) / "jscpd-report.json"
        if not report_path.exists():
            logger.debug("jscpd report not found at %s", report_path)
            return []

        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.debug("Failed to parse jscpd report", exc_info=True)
            return []

        return self._parse_duplicates(data)

    def _parse_duplicates(self, data: dict[str, object]) -> list[PerformanceFinding]:
        """Parse the jscpd JSON report and map to findings."""
        duplicates = data.get("duplicates", [])
        if not isinstance(duplicates, list):
            return []

        findings: list[PerformanceFinding] = []
        for dup in duplicates:
            if not isinstance(dup, dict):
                continue

            lines = dup.get("lines", 0)
            if not isinstance(lines, int) or lines < 10:
                continue

            severity = self._severity_for_lines(lines)

            first_file = dup.get("firstFile", {})
            second_file = dup.get("secondFile", {})
            first_name = first_file.get("name", "<unknown>") if isinstance(first_file, dict) else "<unknown>"
            second_name = second_file.get("name", "<unknown>") if isinstance(second_file, dict) else "<unknown>"
            start_line = first_file.get("startLoc", {}).get("line", 0) if isinstance(first_file, dict) else 0
            if not isinstance(start_line, int):
                start_line = 0

            tokens = dup.get("tokens", 0)

            findings.append(
                PerformanceFinding(
                    factor_id=84,
                    factor_name="Copy-paste with variations",
                    category="Code Volume",
                    severity=severity,
                    message=(
                        f"Duplicated block ({lines} lines, {tokens} tokens) between {first_name} and {second_name}"
                    ),
                    file=first_name,
                    line=start_line,
                    tool=self.name,
                    rule_id="duplication",
                    suggestion="Extract duplicated code into a shared function or module",
                )
            )
        return findings

    @staticmethod
    def _severity_for_lines(lines: int) -> Severity:
        """Map duplicated line count to severity."""
        if lines > 50:
            return Severity.HIGH
        if lines > 20:
            return Severity.MEDIUM
        return Severity.LOW
