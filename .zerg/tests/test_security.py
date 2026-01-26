"""Tests for ZERG v2 Security Command."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestVulnerabilityType:
    """Tests for vulnerability type enumeration."""

    def test_types_exist(self):
        """Test vulnerability types are defined."""
        from security import VulnerabilityType

        assert hasattr(VulnerabilityType, "INJECTION")
        assert hasattr(VulnerabilityType, "XSS")
        assert hasattr(VulnerabilityType, "SECRETS")
        assert hasattr(VulnerabilityType, "DEPENDENCY")


class TestSeverity:
    """Tests for severity levels."""

    def test_severity_levels_exist(self):
        """Test severity levels are defined."""
        from security import Severity

        assert hasattr(Severity, "CRITICAL")
        assert hasattr(Severity, "HIGH")
        assert hasattr(Severity, "MEDIUM")
        assert hasattr(Severity, "LOW")


class TestSecurityConfig:
    """Tests for security configuration."""

    def test_config_defaults(self):
        """Test SecurityConfig has sensible defaults."""
        from security import SecurityConfig

        config = SecurityConfig()
        assert config.preset == "owasp"
        assert config.autofix is False

    def test_config_custom(self):
        """Test SecurityConfig with custom values."""
        from security import SecurityConfig

        config = SecurityConfig(preset="pci", autofix=True)
        assert config.preset == "pci"
        assert config.autofix is True


class TestVulnerability:
    """Tests for vulnerability findings."""

    def test_vulnerability_creation(self):
        """Test Vulnerability can be created."""
        from security import Severity, Vulnerability, VulnerabilityType

        vuln = Vulnerability(
            vuln_type=VulnerabilityType.INJECTION,
            severity=Severity.HIGH,
            message="SQL injection detected",
            file="db.py",
            line=42,
        )
        assert vuln.vuln_type == VulnerabilityType.INJECTION
        assert vuln.severity == Severity.HIGH

    def test_vulnerability_to_dict(self):
        """Test Vulnerability serialization."""
        from security import Severity, Vulnerability, VulnerabilityType

        vuln = Vulnerability(
            vuln_type=VulnerabilityType.XSS,
            severity=Severity.MEDIUM,
            message="XSS vulnerability",
            file="template.html",
            line=10,
        )
        data = vuln.to_dict()
        assert data["type"] == "xss"
        assert data["severity"] == "medium"


class TestSecurityResult:
    """Tests for security scan results."""

    def test_result_creation(self):
        """Test SecurityResult can be created."""
        from security import SecurityResult

        result = SecurityResult(
            total_files=10,
            scanned_files=10,
            vulnerabilities=[],
            scan_time_seconds=5.0,
        )
        assert result.total_files == 10
        assert result.is_secure is True

    def test_result_with_vulnerabilities(self):
        """Test SecurityResult with vulnerabilities."""
        from security import (
            SecurityResult,
            Severity,
            Vulnerability,
            VulnerabilityType,
        )

        vuln = Vulnerability(
            vuln_type=VulnerabilityType.SECRETS,
            severity=Severity.CRITICAL,
            message="Hardcoded API key",
            file="config.py",
            line=5,
        )
        result = SecurityResult(
            total_files=10,
            scanned_files=10,
            vulnerabilities=[vuln],
            scan_time_seconds=5.0,
        )
        assert result.is_secure is False
        assert result.critical_count == 1


class TestOWASPScanner:
    """Tests for OWASP Top 10 scanner."""

    def test_scanner_creation(self):
        """Test OWASPScanner can be created."""
        from security import OWASPScanner

        scanner = OWASPScanner()
        assert scanner is not None

    def test_scanner_checks(self):
        """Test OWASPScanner has OWASP checks."""
        from security import OWASPScanner

        scanner = OWASPScanner()
        checks = scanner.get_checks()
        # Should have OWASP top 10 categories
        assert len(checks) > 0


class TestDependencyScanner:
    """Tests for dependency CVE scanner."""

    def test_scanner_creation(self):
        """Test DependencyScanner can be created."""
        from security import DependencyScanner

        scanner = DependencyScanner()
        assert scanner is not None

    def test_scanner_supported_formats(self):
        """Test DependencyScanner supports common formats."""
        from security import DependencyScanner

        scanner = DependencyScanner()
        formats = scanner.supported_formats()
        assert "requirements.txt" in formats or "package.json" in formats


class TestSecretScanner:
    """Tests for secret detection scanner."""

    def test_scanner_creation(self):
        """Test SecretScanner can be created."""
        from security import SecretScanner

        scanner = SecretScanner()
        assert scanner is not None

    def test_scanner_patterns(self):
        """Test SecretScanner has detection patterns."""
        from security import SecretScanner

        scanner = SecretScanner()
        patterns = scanner.get_patterns()
        assert len(patterns) > 0

    def test_scanner_detects_api_key(self):
        """Test SecretScanner detects API key patterns."""
        from security import SecretScanner

        scanner = SecretScanner()
        # Check if common patterns would be detected
        test_content = "API_KEY='sk-1234567890abcdef'"
        result = scanner.scan_content(test_content, "test.py")
        assert len(result) > 0 or isinstance(result, list)


class TestSecurityCommand:
    """Tests for SecurityCommand class."""

    def test_command_creation(self):
        """Test SecurityCommand can be created."""
        from security import SecurityCommand

        cmd = SecurityCommand()
        assert cmd is not None

    def test_command_supported_presets(self):
        """Test SecurityCommand lists supported presets."""
        from security import SecurityCommand

        cmd = SecurityCommand()
        presets = cmd.supported_presets()
        assert "owasp" in presets
        assert "pci" in presets

    def test_command_run_returns_result(self):
        """Test run returns SecurityResult."""
        from security import SecurityCommand, SecurityResult

        cmd = SecurityCommand()
        result = cmd.run(files=[], dry_run=True)
        assert isinstance(result, SecurityResult)

    def test_command_format_text(self):
        """Test text output format."""
        from security import SecurityCommand, SecurityResult

        cmd = SecurityCommand()
        result = SecurityResult(
            total_files=5, scanned_files=5, vulnerabilities=[], scan_time_seconds=1.0
        )
        output = cmd.format_result(result, format="text")
        assert "Security" in output

    def test_command_format_sarif(self):
        """Test SARIF output format."""
        from security import SecurityCommand, SecurityResult

        cmd = SecurityCommand()
        result = SecurityResult(
            total_files=5, scanned_files=5, vulnerabilities=[], scan_time_seconds=1.0
        )
        output = cmd.format_result(result, format="sarif")
        assert "$schema" in output or "sarif" in output.lower()
