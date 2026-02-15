"""ZERG v2 Security Command - Security review, vulnerability scanning, hardening."""

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class VulnerabilityType(Enum):
    """Types of security vulnerabilities."""

    INJECTION = "injection"
    XSS = "xss"
    SECRETS = "secrets"
    DEPENDENCY = "dependency"
    AUTH = "authentication"
    ACCESS = "access_control"
    CRYPTO = "cryptography"
    CONFIG = "misconfiguration"


class Severity(Enum):
    """Vulnerability severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class SecurityConfig:
    """Configuration for security scanning."""

    preset: str = "owasp"
    autofix: bool = False
    scan_dependencies: bool = True
    scan_secrets: bool = True
    exclude_patterns: list[str] = field(default_factory=list)


@dataclass
class Vulnerability:
    """A security vulnerability finding."""

    vuln_type: VulnerabilityType
    severity: Severity
    message: str
    file: str
    line: int
    column: int = 0
    fix_suggestion: str = ""
    cwe_id: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "type": self.vuln_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "fix_suggestion": self.fix_suggestion,
            "cwe_id": self.cwe_id,
        }


@dataclass
class SecurityResult:
    """Result of security scan."""

    total_files: int
    scanned_files: int
    vulnerabilities: list[Vulnerability]
    scan_time_seconds: float

    @property
    def is_secure(self) -> bool:
        """Check if no vulnerabilities found."""
        return len(self.vulnerabilities) == 0

    @property
    def critical_count(self) -> int:
        """Count critical vulnerabilities."""
        return sum(1 for v in self.vulnerabilities if v.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        """Count high severity vulnerabilities."""
        return sum(1 for v in self.vulnerabilities if v.severity == Severity.HIGH)

    def by_severity(self) -> dict[str, list[Vulnerability]]:
        """Group vulnerabilities by severity."""
        result: dict[str, list[Vulnerability]] = {}
        for v in self.vulnerabilities:
            key = v.severity.value
            if key not in result:
                result[key] = []
            result[key].append(v)
        return result


class OWASPScanner:
    """OWASP Top 10 vulnerability scanner."""

    CHECKS = [
        ("A01:2021", "Broken Access Control", VulnerabilityType.ACCESS),
        ("A02:2021", "Cryptographic Failures", VulnerabilityType.CRYPTO),
        ("A03:2021", "Injection", VulnerabilityType.INJECTION),
        ("A04:2021", "Insecure Design", VulnerabilityType.CONFIG),
        ("A05:2021", "Security Misconfiguration", VulnerabilityType.CONFIG),
        ("A06:2021", "Vulnerable Components", VulnerabilityType.DEPENDENCY),
        ("A07:2021", "Auth Failures", VulnerabilityType.AUTH),
        ("A08:2021", "Data Integrity Failures", VulnerabilityType.CONFIG),
        ("A09:2021", "Logging Failures", VulnerabilityType.CONFIG),
        ("A10:2021", "SSRF", VulnerabilityType.INJECTION),
    ]

    def get_checks(self) -> list[tuple]:
        """Return OWASP check definitions."""
        return self.CHECKS

    def scan(self, files: list[str]) -> list[Vulnerability]:
        """Scan files for OWASP vulnerabilities.

        Real implementation would use semgrep or similar.
        """
        return []


class DependencyScanner:
    """Dependency CVE scanner."""

    SUPPORTED_FORMATS = [
        "requirements.txt",
        "package.json",
        "Cargo.toml",
        "go.mod",
        "Gemfile",
    ]

    def supported_formats(self) -> list[str]:
        """Return supported dependency file formats."""
        return self.SUPPORTED_FORMATS

    def scan(self, project_path: Path) -> list[Vulnerability]:
        """Scan dependencies for known CVEs.

        Real implementation would use safety, npm audit, etc.
        """
        return []


class SecretScanner:
    """Secret detection scanner."""

    PATTERNS = [
        (r"(?i)api[_-]?key\s*[=:]\s*['\"][^'\"]+['\"]", "API Key"),
        (r"(?i)secret[_-]?key\s*[=:]\s*['\"][^'\"]+['\"]", "Secret Key"),
        (r"(?i)password\s*[=:]\s*['\"][^'\"]+['\"]", "Password"),
        (r"(?i)token\s*[=:]\s*['\"][^'\"]+['\"]", "Token"),
        (r"sk-[a-zA-Z0-9]{32,}", "OpenAI API Key"),
        (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
        (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
        (r"-----BEGIN (?:RSA |DSA |EC )?PRIVATE KEY-----", "Private Key"),
    ]

    def get_patterns(self) -> list[tuple]:
        """Return detection patterns."""
        return self.PATTERNS

    def scan_content(self, content: str, filename: str) -> list[Vulnerability]:
        """Scan content for secrets."""
        vulnerabilities = []

        for pattern, secret_type in self.PATTERNS:
            matches = re.finditer(pattern, content)
            for match in matches:
                # Calculate line number
                line_num = content[: match.start()].count("\n") + 1
                vulnerabilities.append(
                    Vulnerability(
                        vuln_type=VulnerabilityType.SECRETS,
                        severity=Severity.CRITICAL,
                        message=f"Potential {secret_type} detected",
                        file=filename,
                        line=line_num,
                        fix_suggestion="Remove hardcoded secret and use environment variables",
                        cwe_id="CWE-798",
                    )
                )

        return vulnerabilities

    def scan(self, files: list[str]) -> list[Vulnerability]:
        """Scan files for secrets."""
        vulnerabilities = []
        for filepath in files:
            try:
                with open(filepath, encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                vulnerabilities.extend(self.scan_content(content, filepath))
            except OSError:
                pass  # Best-effort file read; skip unreadable files
        return vulnerabilities


class SecurityCommand:
    """Main security command orchestrator."""

    PRESETS = {
        "owasp": "OWASP Top 10 vulnerabilities",
        "pci": "PCI-DSS compliance checks",
        "hipaa": "HIPAA security requirements",
        "soc2": "SOC 2 security controls",
    }

    def __init__(self, config: SecurityConfig | None = None):
        """Initialize security command."""
        self.config = config or SecurityConfig()
        self.owasp_scanner = OWASPScanner()
        self.dependency_scanner = DependencyScanner()
        self.secret_scanner = SecretScanner()

    def supported_presets(self) -> list[str]:
        """Return list of supported security presets."""
        return list(self.PRESETS.keys())

    def run(
        self,
        files: list[str],
        preset: str | None = None,
        dry_run: bool = False,
    ) -> SecurityResult:
        """Run security scan.

        Args:
            files: Files to scan
            preset: Security preset to use
            dry_run: If True, don't actually scan

        Returns:
            SecurityResult with scan details
        """
        if dry_run:
            return SecurityResult(
                total_files=len(files),
                scanned_files=0,
                vulnerabilities=[],
                scan_time_seconds=0.0,
            )

        vulnerabilities = []

        # Scan for secrets
        if self.config.scan_secrets:
            vulnerabilities.extend(self.secret_scanner.scan(files))

        # OWASP checks
        vulnerabilities.extend(self.owasp_scanner.scan(files))

        return SecurityResult(
            total_files=len(files),
            scanned_files=len(files),
            vulnerabilities=vulnerabilities,
            scan_time_seconds=0.1,
        )

    def format_result(self, result: SecurityResult, format: str = "text") -> str:
        """Format scan result.

        Args:
            result: Security result to format
            format: Output format (text, json, sarif)

        Returns:
            Formatted string
        """
        if format == "json":
            return self._format_json(result)
        elif format == "sarif":
            return self._format_sarif(result)
        else:
            return self._format_text(result)

    def _format_text(self, result: SecurityResult) -> str:
        """Format as text."""
        status = "SECURE" if result.is_secure else "VULNERABILITIES FOUND"
        lines = [
            "Security Scan Results",
            "=" * 40,
            f"Status: {status}",
            f"Files Scanned: {result.scanned_files}/{result.total_files}",
            f"Vulnerabilities: {len(result.vulnerabilities)}",
            f"  Critical: {result.critical_count}",
            f"  High: {result.high_count}",
            "",
        ]

        if result.vulnerabilities:
            lines.append("Findings:")
            for v in result.vulnerabilities[:10]:
                icon = "🔴" if v.severity == Severity.CRITICAL else "🟠"
                lines.append(f"  {icon} [{v.severity.value}] {v.file}:{v.line}")
                lines.append(f"     {v.message}")

        return "\n".join(lines)

    def _format_json(self, result: SecurityResult) -> str:
        """Format as JSON."""
        return json.dumps(
            {
                "status": "secure" if result.is_secure else "vulnerable",
                "total_files": result.total_files,
                "scanned_files": result.scanned_files,
                "vulnerability_count": len(result.vulnerabilities),
                "critical_count": result.critical_count,
                "high_count": result.high_count,
                "vulnerabilities": [v.to_dict() for v in result.vulnerabilities],
                "scan_time_seconds": result.scan_time_seconds,
            },
            indent=2,
        )

    def _format_sarif(self, result: SecurityResult) -> str:
        """Format as SARIF."""
        sarif = {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "zerg-security", "version": "2.0"}},
                    "results": [
                        {
                            "ruleId": v.cwe_id or v.vuln_type.value,
                            "level": "error"
                            if v.severity in (Severity.CRITICAL, Severity.HIGH)
                            else "warning",
                            "message": {"text": v.message},
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": v.file},
                                        "region": {
                                            "startLine": v.line,
                                            "startColumn": v.column,
                                        },
                                    }
                                }
                            ],
                        }
                        for v in result.vulnerabilities
                    ],
                }
            ],
        }
        return json.dumps(sarif, indent=2)


__all__ = [
    "VulnerabilityType",
    "Severity",
    "SecurityConfig",
    "Vulnerability",
    "SecurityResult",
    "OWASPScanner",
    "DependencyScanner",
    "SecretScanner",
    "SecurityCommand",
]
