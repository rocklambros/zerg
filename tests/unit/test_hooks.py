"""Tests for ZERG pre-commit hooks.

Tests are organized by check category:
- TestSecrets: Advanced secrets detection
- TestShellInjection: Shell injection patterns
- TestCodeInjection: Code injection (eval/exec/pickle)
- TestHardcodedUrls: Hardcoded URL detection
- TestRuffLint: Ruff integration
- TestDebugger: Debugger statement detection
- TestMergeMarkers: Merge conflict marker detection
- TestZergBranch: ZERG branch naming validation
- TestNoPrint: Print statement detection
"""

import re
import subprocess
from pathlib import Path
from typing import ClassVar

import pytest

# =============================================================================
# Pattern Definitions (mirroring hook patterns for testability)
# =============================================================================

# Security Patterns
PATTERNS = {
    # AWS Access Key
    "aws_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    # GitHub PAT (classic and fine-grained)
    "github_pat": re.compile(r"(ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9]{20,}_[a-zA-Z0-9]{40,})"),
    # OpenAI API Key
    "openai_key": re.compile(r"sk-[a-zA-Z0-9]{48}"),
    # Anthropic API Key
    "anthropic_key": re.compile(r"sk-ant-[a-zA-Z0-9\-]{90,}"),
    # Private Key Headers
    "private_key": re.compile(r"-----BEGIN (RSA|DSA|EC|OPENSSH|PGP) PRIVATE KEY-----"),
    # Generic secrets (password=, secret=, etc.)
    "generic_secret": re.compile(
        r"(password|secret|api_key|apikey|access_token|auth_token)" r"\s*[=:]\s*['\"][^'\"]{8,}['\"]",
        re.IGNORECASE,
    ),
    # Shell Injection
    "shell_injection": re.compile(r"(shell\s*=\s*True|os\.system\s*\(|os\.popen\s*\()"),
    # Code Injection (eval/exec not in comments)
    "code_injection": re.compile(r"^[^#]*\b(eval|exec)\s*\("),
    # Pickle (unsafe deserialization)
    "pickle_load": re.compile(r"pickle\.(load|loads)\s*\("),
    # Debugger statements
    "debugger": re.compile(r"(breakpoint\s*\(\)|pdb\.set_trace\s*\(\)|import\s+i?pdb)"),
    # Merge conflict markers
    "merge_conflict": re.compile(r"^(<{7}|={7}|>{7})"),
    # Print statements (not in comments)
    "print_stmt": re.compile(r"^[^#]*\bprint\s*\("),
    # Hardcoded localhost
    "localhost": re.compile(r"(localhost|127\.0\.0\.1|0\.0\.0\.0):[0-9]+"),
}

# ZERG branch naming pattern
ZERG_BRANCH_PATTERN = re.compile(r"^zerg/[a-z0-9-]+/worker-[0-9]+$")


# =============================================================================
# Base Test Class
# =============================================================================


class TestHooksBase:
    """Base class for hook tests with common utilities."""

    # Path to fixtures directory
    FIXTURES_DIR: ClassVar[Path] = Path(__file__).parent.parent / "fixtures" / "hook_samples"

    @classmethod
    def read_fixture(cls, subdir: str, filename: str) -> str:
        """Read a test fixture file.

        Args:
            subdir: Subdirectory within hook_samples
            filename: Fixture filename

        Returns:
            File content as string
        """
        fixture_path = cls.FIXTURES_DIR / subdir / filename
        return fixture_path.read_text()

    @staticmethod
    def matches_pattern(content: str, pattern_name: str) -> list[str]:
        """Check if content matches a pattern.

        Args:
            content: Text content to check
            pattern_name: Name of pattern in PATTERNS dict

        Returns:
            List of matched strings
        """
        pattern = PATTERNS[pattern_name]
        matches = []
        for line in content.split("\n"):
            found = pattern.findall(line)
            if found:
                # Handle groups
                for match in found:
                    if isinstance(match, tuple):
                        matches.append(match[0])
                    else:
                        matches.append(match)
        return matches

    @staticmethod
    def check_branch_name(branch: str) -> bool:
        """Check if branch name follows ZERG convention.

        Args:
            branch: Branch name to check

        Returns:
            True if branch name is valid
        """
        return bool(ZERG_BRANCH_PATTERN.match(branch))


# =============================================================================
# Security Tests
# =============================================================================


class TestSecrets(TestHooksBase):
    """Tests for secrets detection patterns."""

    @pytest.mark.parametrize(
        "pattern_name,fixture_file",
        [
            ("aws_key", "aws_key.py"),
            ("github_pat", "github_pat.py"),
            ("openai_key", "openai_key.py"),
            ("private_key", "private_key.py"),
        ],
        ids=["aws", "github-pat", "openai", "private-key"],
    )
    def test_secret_detection_from_fixture(self, pattern_name: str, fixture_file: str) -> None:
        """Should detect secret patterns in fixture files."""
        content = self.read_fixture("secrets", fixture_file)
        matches = self.matches_pattern(content, pattern_name)
        assert len(matches) > 0, f"Should detect {pattern_name}"

    def test_generic_secret_detection(self) -> None:
        """Should detect generic secret patterns (password=, api_key=, etc.)."""
        for content in [
            "password = 'mysecretpassword123'",
            "api_key: 'super_secret_api_key_here'",
        ]:
            matches = self.matches_pattern(content, "generic_secret")
            assert len(matches) > 0, f"Should detect secret in: {content}"

    def test_clean_code_no_secrets(self) -> None:
        """Clean code should not trigger secret detection."""
        content = self.read_fixture("clean", "safe_code.py")
        for pattern_name in ["aws_key", "github_pat", "openai_key", "private_key"]:
            assert len(self.matches_pattern(content, pattern_name)) == 0


class TestShellInjection(TestHooksBase):
    """Tests for shell injection detection."""

    def test_shell_injection_from_fixtures(self) -> None:
        """Should detect dangerous shell patterns from fixture files."""
        for fixture in ("shell_true.py",):
            content = self.read_fixture("injection", fixture)
            assert len(self.matches_pattern(content, "shell_injection")) > 0

    def test_safe_subprocess_allowed(self) -> None:
        """Safe subprocess usage should not trigger."""
        content = "subprocess.run(['ls', '-la'], capture_output=True)"
        assert len(self.matches_pattern(content, "shell_injection")) == 0


class TestCodeInjection(TestHooksBase):
    """Tests for code injection detection via fixtures."""

    def test_injection_from_fixture(self) -> None:
        """Should detect dangerous code patterns from fixture."""
        content = self.read_fixture("injection", "eval_exec.py")
        assert len(self.matches_pattern(content, "code_injection")) > 0

    def test_deserialization_from_fixture(self) -> None:
        """Should detect unsafe deserialization from fixture."""
        content = self.read_fixture("injection", "pickle_load.py")
        assert len(self.matches_pattern(content, "pickle_load")) > 0


class TestHardcodedUrls(TestHooksBase):
    """Tests for hardcoded URL detection."""

    @pytest.mark.parametrize(
        "content",
        ["http://localhost:8080/api", "127.0.0.1:5432", "0.0.0.0:3000"],
        ids=["localhost", "loopback", "wildcard"],
    )
    def test_localhost_variants(self, content: str) -> None:
        """Should detect localhost/loopback addresses with port."""
        assert len(self.matches_pattern(content, "localhost")) > 0


# =============================================================================
# Quality Tests
# =============================================================================


class TestRuffLint(TestHooksBase):
    """Tests for ruff lint integration."""

    def test_ruff_available(self) -> None:
        """Ruff should be available in environment."""
        result = subprocess.run(
            ["ruff", "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, "Ruff should be installed"


class TestDebugger(TestHooksBase):
    """Tests for debugger statement detection."""

    @pytest.mark.parametrize(
        "content",
        ["import pdb; pdb.set_trace()", "import pdb", "import ipdb"],
        ids=["pdb-trace", "import-pdb", "import-ipdb"],
    )
    def test_debugger_detection(self, content: str) -> None:
        """Should detect debugger statements."""
        matches = self.matches_pattern(content, "debugger")
        assert len(matches) > 0


class TestMergeMarkers(TestHooksBase):
    """Tests for merge conflict marker detection."""

    @pytest.mark.parametrize(
        "content",
        ["<<<<<<<", "=======", ">>>>>>> feature-branch"],
        ids=["left", "equals", "right"],
    )
    def test_marker_detection(self, content: str) -> None:
        """Should detect all merge conflict marker types."""
        matches = self.matches_pattern(content, "merge_conflict")
        assert len(matches) > 0

    def test_partial_markers_allowed(self) -> None:
        """Partial markers (less than 7) should be allowed."""
        content = "x = '<<<<<'"  # Only 5 angles
        matches = self.matches_pattern(content, "merge_conflict")
        assert len(matches) == 0, "Partial markers should not trigger"


# =============================================================================
# ZERG-Specific Tests
# =============================================================================


class TestZergBranch(TestHooksBase):
    """Tests for ZERG branch naming validation."""

    def test_valid_branch_names(self) -> None:
        """Valid ZERG branch names should pass."""
        valid_branches = [
            "zerg/auth-feature/worker-1",
            "zerg/user-auth/worker-5",
            "zerg/api-v2/worker-10",
            "zerg/fix-123/worker-0",
        ]
        for branch in valid_branches:
            assert self.check_branch_name(branch), f"Should accept: {branch}"

    def test_invalid_branch_names(self) -> None:
        """Invalid branch names (including main/master) should fail."""
        invalid_branches = [
            "main",
            "master",
            "feature/auth",
            "zerg/auth",  # Missing worker suffix
            "zerg/Auth/worker-1",  # Uppercase
            "zerg/auth_feature/worker-1",  # Underscore
            "zerg/auth/Worker-1",  # Uppercase Worker
        ]
        for branch in invalid_branches:
            assert not self.check_branch_name(branch), f"Should reject: {branch}"


class TestNoPrint(TestHooksBase):
    """Tests for print statement detection."""

    def test_print_detection(self) -> None:
        """Should detect print() statements from fixture."""
        content = self.read_fixture("quality", "print_stmt.py")
        matches = self.matches_pattern(content, "print_stmt")
        assert len(matches) > 0, "Should detect print"

    def test_commented_print_allowed(self) -> None:
        """Commented print should not trigger."""
        content = "# print('debug')  # commented out"
        matches = self.matches_pattern(content, "print_stmt")
        assert len(matches) == 0, "Commented print should not trigger"


# =============================================================================
# Integration Helpers
# =============================================================================


class TestHookPatternIntegrity:
    """Meta-tests to verify pattern definitions are complete."""

    def test_all_patterns_defined_and_compiled(self) -> None:
        """All expected patterns should be defined and compiled."""
        expected_patterns = [
            "aws_key",
            "github_pat",
            "openai_key",
            "anthropic_key",
            "private_key",
            "generic_secret",
            "shell_injection",
            "code_injection",
            "pickle_load",
            "debugger",
            "merge_conflict",
            "print_stmt",
            "localhost",
        ]
        for pattern_name in expected_patterns:
            assert pattern_name in PATTERNS, f"Missing pattern: {pattern_name}"
            assert hasattr(PATTERNS[pattern_name], "match"), f"{pattern_name} is not compiled"
