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
    """Tests for advanced secrets detection."""

    def test_aws_key_detection(self) -> None:
        """Should detect AWS access key patterns."""
        content = self.read_fixture("secrets", "aws_key.py")
        matches = self.matches_pattern(content, "aws_key")
        assert len(matches) > 0, "Should detect AWS access key"
        assert any("AKIA" in m for m in matches)

    def test_github_pat_classic_detection(self) -> None:
        """Should detect GitHub classic PAT patterns."""
        content = self.read_fixture("secrets", "github_pat.py")
        matches = self.matches_pattern(content, "github_pat")
        assert len(matches) > 0, "Should detect GitHub PAT"
        assert any("ghp_" in m for m in matches)

    def test_github_pat_finegrained_detection(self) -> None:
        """Should detect GitHub fine-grained PAT patterns."""
        content = "token = 'github_pat_11ABCDEFGHIJKLMNOPQRS_abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ12345'"
        matches = self.matches_pattern(content, "github_pat")
        assert len(matches) > 0, "Should detect fine-grained PAT"

    def test_openai_key_detection(self) -> None:
        """Should detect OpenAI API key patterns."""
        content = self.read_fixture("secrets", "openai_key.py")
        matches = self.matches_pattern(content, "openai_key")
        assert len(matches) > 0, "Should detect OpenAI key"
        assert any("sk-" in m for m in matches)

    def test_anthropic_key_detection(self) -> None:
        """Should detect Anthropic API key patterns."""
        content = "api_key = 'sk-ant-api03-" + "x" * 90 + "'"
        matches = self.matches_pattern(content, "anthropic_key")
        assert len(matches) > 0, "Should detect Anthropic key"

    def test_private_key_detection(self) -> None:
        """Should detect private key headers."""
        content = self.read_fixture("secrets", "private_key.py")
        matches = self.matches_pattern(content, "private_key")
        assert len(matches) > 0, "Should detect private key"

    def test_generic_secret_detection(self) -> None:
        """Should detect generic secret patterns."""
        test_cases = [
            "password = 'mysecretpassword123'",
            "api_key: 'super_secret_api_key_here'",
            "SECRET = 'very-secret-value-123'",
        ]
        for content in test_cases:
            matches = self.matches_pattern(content, "generic_secret")
            assert len(matches) > 0, f"Should detect secret in: {content}"

    def test_clean_code_no_secrets(self) -> None:
        """Clean code should not trigger secret detection."""
        content = self.read_fixture("clean", "safe_code.py")
        for pattern_name in ["aws_key", "github_pat", "openai_key", "private_key"]:
            matches = self.matches_pattern(content, pattern_name)
            assert len(matches) == 0, f"Clean code triggered {pattern_name}"


class TestShellInjection(TestHooksBase):
    """Tests for shell injection detection."""

    def test_shell_true_detection(self) -> None:
        """Should detect subprocess shell=True."""
        content = self.read_fixture("injection", "shell_true.py")
        matches = self.matches_pattern(content, "shell_injection")
        assert len(matches) > 0, "Should detect shell=True"

    def test_os_system_detection(self) -> None:
        """Should detect os.system() calls."""
        content = self.read_fixture("injection", "os_system.py")
        matches = self.matches_pattern(content, "shell_injection")
        assert len(matches) > 0, "Should detect os.system"

    def test_os_popen_detection(self) -> None:
        """Should detect os.popen() calls."""
        content = "result = os.popen('ls -la').read()"
        matches = self.matches_pattern(content, "shell_injection")
        assert len(matches) > 0, "Should detect os.popen"

    def test_safe_subprocess_allowed(self) -> None:
        """Safe subprocess usage should be allowed."""
        content = "subprocess.run(['ls', '-la'], capture_output=True)"
        matches = self.matches_pattern(content, "shell_injection")
        assert len(matches) == 0, "Safe subprocess should not trigger"


class TestCodeInjection(TestHooksBase):
    """Tests for code injection detection (eval/exec/pickle)."""

    def test_eval_detection(self) -> None:
        """Should detect eval() calls."""
        content = self.read_fixture("injection", "eval_exec.py")
        matches = self.matches_pattern(content, "code_injection")
        assert len(matches) > 0, "Should detect eval"

    def test_exec_detection(self) -> None:
        """Should detect exec() calls."""
        content = "exec(user_code)"
        matches = self.matches_pattern(content, "code_injection")
        assert len(matches) > 0, "Should detect exec"

    def test_commented_eval_allowed(self) -> None:
        """Commented eval should not trigger."""
        content = "# eval(something)  # this is a comment"
        matches = self.matches_pattern(content, "code_injection")
        assert len(matches) == 0, "Commented eval should not trigger"

    def test_pickle_load_detection(self) -> None:
        """Should detect pickle.load() calls."""
        content = self.read_fixture("injection", "pickle_load.py")
        matches = self.matches_pattern(content, "pickle_load")
        assert len(matches) > 0, "Should detect pickle.load"

    def test_pickle_loads_detection(self) -> None:
        """Should detect pickle.loads() calls."""
        content = "data = pickle.loads(raw_data)"
        matches = self.matches_pattern(content, "pickle_load")
        assert len(matches) > 0, "Should detect pickle.loads"


class TestHardcodedUrls(TestHooksBase):
    """Tests for hardcoded URL detection."""

    def test_localhost_detection(self) -> None:
        """Should detect localhost with port."""
        content = "api_url = 'http://localhost:8080/api'"
        matches = self.matches_pattern(content, "localhost")
        assert len(matches) > 0, "Should detect localhost"

    def test_127_0_0_1_detection(self) -> None:
        """Should detect 127.0.0.1 with port."""
        content = "db_host = '127.0.0.1:5432'"
        matches = self.matches_pattern(content, "localhost")
        assert len(matches) > 0, "Should detect 127.0.0.1"

    def test_0_0_0_0_detection(self) -> None:
        """Should detect 0.0.0.0 with port."""
        content = "server.bind('0.0.0.0:3000')"
        matches = self.matches_pattern(content, "localhost")
        assert len(matches) > 0, "Should detect 0.0.0.0"

    def test_test_files_exempt(self) -> None:
        """Test files should be exempt from URL detection.

        Note: This tests the pattern behavior; actual exemption
        is handled at the hook level by excluding test directories.
        """
        # The pattern itself matches, but the hook skips test files
        content = "localhost:8080"
        matches = self.matches_pattern(content, "localhost")
        # Pattern matches, but hook would skip test files
        assert len(matches) > 0


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

    def test_ruff_check_clean_file(self, tmp_path: Path) -> None:
        """Ruff should pass on clean Python file."""
        clean_file = tmp_path / "clean.py"
        clean_file.write_text('"""Clean module."""\n\n\ndef main() -> None:\n    pass\n')

        result = subprocess.run(
            ["ruff", "check", str(clean_file)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Ruff should pass: {result.stdout}"

    def test_ruff_check_staged_only_flag(self) -> None:
        """Ruff supports checking specific files (for staged-only mode)."""
        # Verify ruff can check specific files
        result = subprocess.run(
            ["ruff", "check", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        # Ruff accepts file paths as arguments


class TestDebugger(TestHooksBase):
    """Tests for debugger statement detection."""

    def test_breakpoint_detection(self) -> None:
        """Should detect breakpoint() calls."""
        content = self.read_fixture("quality", "debugger.py")
        matches = self.matches_pattern(content, "debugger")
        assert len(matches) > 0, "Should detect breakpoint"

    def test_pdb_set_trace_detection(self) -> None:
        """Should detect pdb.set_trace() calls."""
        content = "import pdb; pdb.set_trace()"
        matches = self.matches_pattern(content, "debugger")
        assert len(matches) > 0, "Should detect pdb.set_trace"

    def test_import_pdb_detection(self) -> None:
        """Should detect import pdb statements."""
        content = "import pdb"
        matches = self.matches_pattern(content, "debugger")
        assert len(matches) > 0, "Should detect import pdb"

    def test_import_ipdb_detection(self) -> None:
        """Should detect import ipdb statements."""
        content = "import ipdb"
        matches = self.matches_pattern(content, "debugger")
        assert len(matches) > 0, "Should detect import ipdb"


class TestMergeMarkers(TestHooksBase):
    """Tests for merge conflict marker detection."""

    def test_left_marker_detection(self) -> None:
        """Should detect <<<<<<< markers."""
        content = self.read_fixture("quality", "merge_conflict.py")
        matches = self.matches_pattern(content, "merge_conflict")
        assert len(matches) > 0, "Should detect merge markers"

    def test_equals_marker_detection(self) -> None:
        """Should detect ======= markers."""
        content = "======="
        matches = self.matches_pattern(content, "merge_conflict")
        assert len(matches) > 0, "Should detect equals marker"

    def test_right_marker_detection(self) -> None:
        """Should detect >>>>>>> markers."""
        content = ">>>>>>> feature-branch"
        matches = self.matches_pattern(content, "merge_conflict")
        assert len(matches) > 0, "Should detect right marker"

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
        """Invalid branch names should fail."""
        invalid_branches = [
            "main",
            "feature/auth",
            "zerg/auth",  # Missing worker suffix
            "zerg/Auth/worker-1",  # Uppercase
            "zerg/auth_feature/worker-1",  # Underscore
            "zerg/auth/Worker-1",  # Uppercase Worker
        ]
        for branch in invalid_branches:
            assert not self.check_branch_name(branch), f"Should reject: {branch}"

    def test_main_branch_exempt(self) -> None:
        """Main branch should be exempt from ZERG naming.

        Note: This is handled at hook level, not pattern level.
        """
        # The pattern won't match main, which is correct
        assert not self.check_branch_name("main")
        assert not self.check_branch_name("master")


class TestNoPrint(TestHooksBase):
    """Tests for print statement detection."""

    def test_print_detection(self) -> None:
        """Should detect print() statements."""
        content = self.read_fixture("quality", "print_stmt.py")
        matches = self.matches_pattern(content, "print_stmt")
        assert len(matches) > 0, "Should detect print"

    def test_print_with_args_detection(self) -> None:
        """Should detect print() with arguments."""
        content = "print('hello', 'world', sep=', ')"
        matches = self.matches_pattern(content, "print_stmt")
        assert len(matches) > 0, "Should detect print with args"

    def test_commented_print_allowed(self) -> None:
        """Commented print should not trigger."""
        content = "# print('debug')  # commented out"
        matches = self.matches_pattern(content, "print_stmt")
        assert len(matches) == 0, "Commented print should not trigger"

    def test_test_files_exempt(self) -> None:
        """Test files should be exempt from print detection.

        Note: Actual exemption handled at hook level.
        """
        # Pattern matches, but hook would skip test files
        content = "print('test output')"
        matches = self.matches_pattern(content, "print_stmt")
        assert len(matches) > 0  # Pattern matches


# =============================================================================
# Integration Helpers
# =============================================================================


class TestHookPatternIntegrity:
    """Meta-tests to verify pattern definitions are complete."""

    def test_all_patterns_defined(self) -> None:
        """All expected patterns should be defined."""
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

    def test_patterns_are_compiled_regex(self) -> None:
        """All patterns should be compiled regex objects."""
        for name, pattern in PATTERNS.items():
            assert hasattr(pattern, "match"), f"{name} is not a compiled regex"
