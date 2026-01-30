"""Lizard adapter for cyclomatic complexity and code-size analysis (multi-language)."""

from __future__ import annotations

import csv
import io
import logging
import subprocess

from zerg.performance.adapters.base import BaseToolAdapter
from zerg.performance.types import DetectedStack, PerformanceFinding, Severity

logger = logging.getLogger(__name__)


class LizardAdapter(BaseToolAdapter):
    """Adapter for lizard complexity / code-size analyser (supports many languages)."""

    name: str = "lizard"
    tool_name: str = "lizard"
    # Factor IDs: 1 = Algorithm complexity, 29 = Function size
    factors_covered: list[int] = [1, 29]

    def is_applicable(self, stack: DetectedStack) -> bool:
        """Lizard supports many languages — always applicable."""
        return True

    def run(
        self,
        files: list[str],
        project_path: str,
        stack: DetectedStack,
    ) -> list[PerformanceFinding]:
        """Run ``lizard --csv`` and return findings based on thresholds."""
        try:
            result = subprocess.run(
                ["lizard", project_path, "--csv"],
                capture_output=True,
                text=True,
                timeout=180,
            )
            output = result.stdout
        except (subprocess.SubprocessError, OSError):
            logger.debug("lizard failed to execute", exc_info=True)
            return []

        return self._parse_csv(output)

    # ------------------------------------------------------------------
    # CSV parsing
    # ------------------------------------------------------------------

    def _parse_csv(self, output: str) -> list[PerformanceFinding]:
        """Parse lizard CSV output and flag functions exceeding thresholds."""
        findings: list[PerformanceFinding] = []
        reader = csv.reader(io.StringIO(output))

        for row in reader:
            # lizard CSV columns (0-indexed):
            #   0: NLOC, 1: CCN, 2: token, 3: PARAM, 4: length,
            #   5: location (file:line), 6: function name, ...
            if len(row) < 7:
                continue
            try:
                nloc = int(row[0])
                ccn = int(row[1])
                params = int(row[3])
            except (ValueError, IndexError):
                continue

            location = row[5]
            func_name = row[6] if len(row) > 6 else "<unknown>"
            file, line = self._parse_location(location)

            # --- Cyclomatic complexity thresholds ---
            if ccn > 40:
                findings.append(self._ccn_finding(func_name, ccn, Severity.CRITICAL, file, line))
            elif ccn > 25:
                findings.append(self._ccn_finding(func_name, ccn, Severity.HIGH, file, line))
            elif ccn > 15:
                findings.append(self._ccn_finding(func_name, ccn, Severity.MEDIUM, file, line))

            # --- Function size (NLOC) thresholds ---
            if nloc > 200:
                findings.append(self._nloc_finding(func_name, nloc, Severity.HIGH, file, line))
            elif nloc > 100:
                findings.append(self._nloc_finding(func_name, nloc, Severity.MEDIUM, file, line))

            # --- Parameter count threshold ---
            if params > 5:
                findings.append(self._params_finding(func_name, params, file, line))

        return findings

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_location(location: str) -> tuple[str, int]:
        """Extract file path and line number from lizard location string."""
        # Format: "path/to/file@line"  or  "path/to/file:line"
        for sep in ("@", ":"):
            if sep in location:
                parts = location.rsplit(sep, 1)
                try:
                    return parts[0], int(parts[1])
                except (ValueError, IndexError):
                    return location, 0
        return location, 0

    def _ccn_finding(
        self,
        func: str,
        ccn: int,
        severity: Severity,
        file: str,
        line: int,
    ) -> PerformanceFinding:
        return PerformanceFinding(
            factor_id=1,
            factor_name="Algorithm complexity",
            category="CPU / Compute",
            severity=severity,
            message=f"Function '{func}' has cyclomatic complexity {ccn}",
            file=file,
            line=line,
            tool=self.name,
            rule_id=f"ccn-{severity.value}",
            suggestion=f"Refactor '{func}' to reduce cyclomatic complexity below 15",
        )

    def _nloc_finding(
        self,
        func: str,
        nloc: int,
        severity: Severity,
        file: str,
        line: int,
    ) -> PerformanceFinding:
        return PerformanceFinding(
            factor_id=29,
            factor_name="Function size",
            category="Code-Level Patterns",
            severity=severity,
            message=f"Function '{func}' has {nloc} lines of code",
            file=file,
            line=line,
            tool=self.name,
            rule_id=f"nloc-{severity.value}",
            suggestion=f"Break '{func}' into smaller functions (target < 50 NLOC)",
        )

    def _params_finding(
        self,
        func: str,
        params: int,
        file: str,
        line: int,
    ) -> PerformanceFinding:
        return PerformanceFinding(
            factor_id=29,
            factor_name="Function size",
            category="Code-Level Patterns",
            severity=Severity.LOW,
            message=f"Function '{func}' has {params} parameters",
            file=file,
            line=line,
            tool=self.name,
            rule_id="params-excessive",
            suggestion=f"Reduce parameters for '{func}' (consider a config object or dataclass)",
        )
