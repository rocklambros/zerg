"""deptry adapter for Python dependency issue detection."""

from __future__ import annotations

import json
import logging
import subprocess

from zerg.performance.adapters.base import BaseToolAdapter
from zerg.performance.types import DetectedStack, PerformanceFinding, Severity

logger = logging.getLogger(__name__)

# deptry error codes -> severity and description
_ERROR_MAP: dict[str, tuple[Severity, str]] = {
    "DEP001": (Severity.HIGH, "Missing dependency"),
    "DEP002": (Severity.MEDIUM, "Unused dependency"),
    "DEP003": (Severity.LOW, "Transitive dependency used directly"),
    "DEP004": (Severity.LOW, "Misplaced dev dependency"),
}


class DeptryAdapter(BaseToolAdapter):
    """Adapter for deptry Python dependency issue detection."""

    name: str = "deptry"
    tool_name: str = "deptry"
    # Factor 79 = Dependency bloat (Dependencies)
    # Factor 120 = Dependency audit for bloat (AI Code Detection)
    factors_covered: list[int] = [79, 120]

    def is_applicable(self, stack: DetectedStack) -> bool:
        """deptry only works on Python projects."""
        return "python" in stack.languages

    def run(
        self,
        files: list[str],
        project_path: str,
        stack: DetectedStack,
    ) -> list[PerformanceFinding]:
        """Run deptry and return dependency findings."""
        try:
            result = subprocess.run(
                ["deptry", project_path, "--json-output", "-"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            # deptry writes JSON to the specified output; "-" means stdout
            data = json.loads(result.stdout)
        except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
            logger.debug("deptry failed or produced unparseable output", exc_info=True)
            return []

        if not isinstance(data, list):
            logger.debug("deptry output is not a JSON array")
            return []

        findings: list[PerformanceFinding] = []
        for violation in data:
            if not isinstance(violation, dict):
                continue

            error_code = violation.get("error_code", "")
            module = violation.get("module", "<unknown>")
            message = violation.get("message", "")

            severity_info = _ERROR_MAP.get(error_code)
            if severity_info is None:
                severity = Severity.LOW
                desc = "Dependency issue"
            else:
                severity, desc = severity_info

            findings.append(
                PerformanceFinding(
                    factor_id=79,
                    factor_name="Dependency bloat",
                    category="Dependencies",
                    severity=severity,
                    message=f"{desc}: {module} — {message}" if message else f"{desc}: {module}",
                    file="",
                    line=0,
                    tool=self.name,
                    rule_id=error_code,
                    suggestion=self._suggestion_for(error_code, module),
                )
            )
        return findings

    @staticmethod
    def _suggestion_for(error_code: str, module: str) -> str:
        """Return a human-readable suggestion based on the error code."""
        suggestions: dict[str, str] = {
            "DEP001": f"Add '{module}' to project dependencies",
            "DEP002": f"Remove unused dependency '{module}'",
            "DEP003": (f"Add '{module}' as a direct dependency instead of relying on transitive install"),
            "DEP004": f"Move '{module}' from dev to main dependencies (or vice versa)",
        }
        return suggestions.get(error_code, f"Review dependency '{module}'")
