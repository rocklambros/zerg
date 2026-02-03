"""Vulture adapter for dead-code detection in Python projects."""

from __future__ import annotations

import logging
import re
import subprocess

from zerg.performance.adapters.base import BaseToolAdapter
from zerg.performance.types import DetectedStack, PerformanceFinding, Severity

logger = logging.getLogger(__name__)

# Regex for vulture output lines:
#   path/to/file.py:42: unused function 'foo' (60% confidence)
_VULTURE_LINE_RE = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+):\s+unused\s+(?P<type>\S+)\s+'(?P<name>[^']+)'"
    r"\s+\((?P<confidence>\d+)%\s+confidence\)",
)


class VultureAdapter(BaseToolAdapter):
    """Adapter for vulture dead-code detection."""

    name: str = "vulture"
    tool_name: str = "vulture"
    # Factor IDs: 30 = Dead code, 31 = Code volume
    factors_covered: list[int] = [30, 31]

    def is_applicable(self, stack: DetectedStack) -> bool:
        """Vulture only works on Python source code."""
        return "python" in stack.languages

    def run(
        self,
        files: list[str],
        project_path: str,
        stack: DetectedStack,
    ) -> list[PerformanceFinding]:
        """Run ``vulture --min-confidence 80`` and return findings."""
        try:
            result = subprocess.run(
                [
                    "vulture",
                    project_path,
                    "--min-confidence",
                    "80",
                    "--exclude",
                    "tests/,.zerg/tests/",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            # vulture exits with code 1 when it finds dead code — that is normal
            output = result.stdout
        except (subprocess.SubprocessError, OSError):
            logger.debug("vulture failed to execute", exc_info=True)
            return []

        return self._parse_output(output)

    # ------------------------------------------------------------------
    # Output parsing
    # ------------------------------------------------------------------

    def _parse_output(self, output: str) -> list[PerformanceFinding]:
        """Parse vulture text output into findings."""
        findings: list[PerformanceFinding] = []

        for line in output.splitlines():
            match = _VULTURE_LINE_RE.match(line.strip())
            if not match:
                continue

            filepath = match.group("file")
            lineno = int(match.group("line"))
            unused_type = match.group("type")
            name = match.group("name")
            confidence = int(match.group("confidence"))

            severity = self._confidence_to_severity(confidence)

            findings.append(
                PerformanceFinding(
                    factor_id=30,
                    factor_name="Dead code",
                    category="Code-Level Patterns",
                    severity=severity,
                    message=(f"Unused {unused_type} '{name}' ({confidence}% confidence)"),
                    file=filepath,
                    line=lineno,
                    tool=self.name,
                    rule_id=f"dead-{unused_type}",
                    suggestion=f"Remove unused {unused_type} '{name}' or mark as used",
                )
            )

        return findings

    @staticmethod
    def _confidence_to_severity(confidence: int) -> Severity:
        """Map vulture confidence percentage to severity."""
        if confidence >= 100:
            return Severity.HIGH
        if confidence >= 90:
            return Severity.MEDIUM
        return Severity.LOW
