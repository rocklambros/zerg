"""Trivy adapter for vulnerability, secret, and misconfiguration scanning."""

from __future__ import annotations

import json
import logging
import subprocess

from zerg.performance.adapters.base import BaseToolAdapter
from zerg.performance.types import DetectedStack, PerformanceFinding, Severity

logger = logging.getLogger(__name__)

# trivy vulnerability severity -> Severity mapping
_VULN_SEVERITY: dict[str, Severity] = {
    "CRITICAL": Severity.CRITICAL,
    "HIGH": Severity.HIGH,
    "MEDIUM": Severity.MEDIUM,
    "LOW": Severity.LOW,
    "UNKNOWN": Severity.INFO,
}

# trivy misconfiguration severity -> Severity mapping
_MISCONFIG_SEVERITY: dict[str, Severity] = {
    "CRITICAL": Severity.CRITICAL,
    "HIGH": Severity.HIGH,
    "MEDIUM": Severity.MEDIUM,
    "LOW": Severity.LOW,
}


class TrivyAdapter(BaseToolAdapter):
    """Adapter for trivy filesystem scanning (vulnerabilities, secrets, misconfigs)."""

    name: str = "trivy"
    tool_name: str = "trivy"
    # Factor IDs: Security Patterns and Container Runtime categories
    factors_covered: list[int] = [22, 23, 24]

    def is_applicable(self, stack: DetectedStack) -> bool:
        """Trivy scans any filesystem — always applicable."""
        return True

    def run(
        self,
        files: list[str],
        project_path: str,
        stack: DetectedStack,
    ) -> list[PerformanceFinding]:
        """Run ``trivy fs`` on the project and return findings."""
        try:
            result = subprocess.run(
                [
                    "trivy",
                    "fs",
                    "--format",
                    "json",
                    "--scanners",
                    "vuln,secret,misconfig",
                    project_path,
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )
            data = json.loads(result.stdout)
        except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
            logger.debug("trivy scan failed or produced unparseable output", exc_info=True)
            return []

        findings: list[PerformanceFinding] = []

        results = data.get("Results", [])
        if not isinstance(results, list):
            return findings

        for entry in results:
            if not isinstance(entry, dict):
                continue
            target = entry.get("Target", "")
            findings.extend(self._parse_vulnerabilities(entry, target))
            findings.extend(self._parse_secrets(entry, target))
            findings.extend(self._parse_misconfigurations(entry, target))

        return findings

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------

    def _parse_vulnerabilities(self, entry: dict, target: str) -> list[PerformanceFinding]:
        """Extract vulnerability findings from a single result entry."""
        vulns = entry.get("Vulnerabilities")
        if not isinstance(vulns, list):
            return []

        findings: list[PerformanceFinding] = []
        for vuln in vulns:
            if not isinstance(vuln, dict):
                continue
            sev_str = vuln.get("Severity", "UNKNOWN")
            severity = _VULN_SEVERITY.get(sev_str, Severity.INFO)
            vuln_id = vuln.get("VulnerabilityID", "")
            pkg = vuln.get("PkgName", "")
            installed = vuln.get("InstalledVersion", "")
            fixed = vuln.get("FixedVersion", "")
            title = vuln.get("Title", vuln_id)

            suggestion = f"Upgrade {pkg} from {installed}" if pkg else ""
            if fixed:
                suggestion += f" to {fixed}"

            findings.append(
                PerformanceFinding(
                    factor_id=22,
                    factor_name="Dependency vulnerabilities",
                    category="Security Patterns",
                    severity=severity,
                    message=f"{vuln_id}: {title} in {pkg}@{installed}" if pkg else title,
                    file=target,
                    line=0,
                    tool=self.name,
                    rule_id=vuln_id,
                    suggestion=suggestion,
                )
            )
        return findings

    def _parse_secrets(self, entry: dict, target: str) -> list[PerformanceFinding]:
        """Extract secret findings from a single result entry."""
        secrets = entry.get("Secrets")
        if not isinstance(secrets, list):
            return []

        findings: list[PerformanceFinding] = []
        for secret in secrets:
            if not isinstance(secret, dict):
                continue
            rule_id = secret.get("RuleID", "")
            title = secret.get("Title", "Exposed secret")
            match_str = secret.get("Match", "")
            start_line = secret.get("StartLine", 0)

            findings.append(
                PerformanceFinding(
                    factor_id=23,
                    factor_name="Exposed secrets",
                    category="Security Patterns",
                    severity=Severity.HIGH,
                    message=f"{title}: {match_str}" if match_str else title,
                    file=target,
                    line=start_line,
                    tool=self.name,
                    rule_id=rule_id,
                    suggestion="Remove the exposed secret and rotate credentials",
                )
            )
        return findings

    def _parse_misconfigurations(self, entry: dict, target: str) -> list[PerformanceFinding]:
        """Extract misconfiguration findings from a single result entry."""
        misconfigs = entry.get("Misconfigurations")
        if not isinstance(misconfigs, list):
            return []

        findings: list[PerformanceFinding] = []
        for mc in misconfigs:
            if not isinstance(mc, dict):
                continue
            sev_str = mc.get("Severity", "MEDIUM")
            severity = _MISCONFIG_SEVERITY.get(sev_str, Severity.MEDIUM)
            mc_id = mc.get("ID", "")
            title = mc.get("Title", "")
            description = mc.get("Description", "")
            resolution = mc.get("Resolution", "")

            findings.append(
                PerformanceFinding(
                    factor_id=24,
                    factor_name="Infrastructure misconfiguration",
                    category="Container Runtime",
                    severity=severity,
                    message=f"{mc_id}: {title}" if mc_id else title,
                    file=target,
                    line=0,
                    tool=self.name,
                    rule_id=mc_id,
                    suggestion=resolution or description,
                )
            )
        return findings
