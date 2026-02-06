"""Tests for ZERG security module."""

import os
from pathlib import Path

import pytest

from zerg.security import (
    SECRET_PATTERNS,
    SENSITIVE_FILES,
    check_file_size,
    check_for_non_ascii_filenames,
    check_for_secrets,
    check_sensitive_files,
    install_hooks,
    run_security_scan,
    validate_commit_message,
)


class TestCheckForSecrets:
    """Tests for secret detection across different pattern categories."""

    @pytest.mark.parametrize(
        "content",
        [
            'password = "supersecret123"',
            'api_key = "abcdefghijklmnop1234567890"',
            'token = "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ123456789A"',
            'openai_key = "sk-aBcDeFgHiJkLmNoPqRsTuVwXyZaBcDeFgHiJkLmNoPqRsAbCd"',
            'aws_key = "AKIAIOSFODNN7EXAMPLE"',
            "-----BEGIN RSA PRIVATE KEY-----\nMIIEow...",
        ],
        ids=["password", "api_key", "github_token", "openai_key", "aws_key", "private_key"],
    )
    def test_detect_secret_types(self, content: str) -> None:
        """Each secret type should be detected."""
        findings = check_for_secrets(content)
        assert len(findings) >= 1

    def test_no_false_positives_short_values(self) -> None:
        """Short values should not trigger false positives."""
        findings = check_for_secrets('password = "abc"')
        assert len(findings) == 0

    def test_multiline_content(self) -> None:
        """Secrets in multiline content detected with correct line number."""
        content = 'line1 = "normal"\npassword = "secretpassword123"\nline3 = "also normal"'
        findings = check_for_secrets(content)
        assert len(findings) == 1

    def test_masked_output(self) -> None:
        """Found secrets should be masked/truncated in output."""
        content = 'password = "this_is_a_very_long_secret_that_should_be_truncated_at_fifty_characters"'
        findings = check_for_secrets(content)
        assert len(findings[0][2]) <= 53


class TestCheckSensitiveFiles:
    """Tests for sensitive file detection."""

    @pytest.mark.parametrize(
        "files,expected",
        [
            (["src/app.py", ".env", "README.md"], [".env"]),
            (["app.py", "credentials.json"], ["credentials.json"]),
            (["id_rsa", "id_ed25519", "known_hosts"], ["id_rsa", "id_ed25519"]),
            (["secrets/.env", "config/credentials.json"], None),  # 2 sensitive
        ],
        ids=["env", "credentials", "ssh_keys", "nested_paths"],
    )
    def test_detect_sensitive_files(self, files: list[str], expected: list[str] | None) -> None:
        sensitive = check_sensitive_files(files)
        if expected is not None:
            for exp in expected:
                assert exp in sensitive
        else:
            assert len(sensitive) == 2


class TestCheckNonAsciiFilenames:
    def test_ascii_and_non_ascii(self) -> None:
        non_ascii = check_for_non_ascii_filenames(["file.py", "test.js", "tëst.py", "文件.txt"])
        assert len(non_ascii) == 2
        assert "tëst.py" in non_ascii


class TestValidateCommitMessage:
    @pytest.mark.parametrize(
        "msg",
        [
            "feat: add new login feature",
            "fix: resolve auth bug",
            "feat(auth): add OAuth",
            "feat!: remove deprecated API",
        ],
        ids=["feat", "fix", "scoped", "breaking"],
    )
    def test_valid_messages(self, msg: str) -> None:
        is_valid, error = validate_commit_message(msg)
        assert is_valid is True

    @pytest.mark.parametrize(
        "msg,error_substr",
        [("", "empty"), ("fix", "short"), ("feat: " + "a" * 70, "long"), ("Added a new feature", "conventional")],
        ids=["empty", "too_short", "too_long", "invalid_format"],
    )
    def test_invalid_messages(self, msg: str, error_substr: str) -> None:
        is_valid, error = validate_commit_message(msg)
        assert is_valid is False
        assert error_substr in error.lower()


class TestCheckFileSize:
    def test_small_file_passes(self, tmp_path: Path) -> None:
        (tmp_path / "small.txt").write_text("hello")
        assert check_file_size(tmp_path / "small.txt") is True

    def test_large_file_fails(self, tmp_path: Path) -> None:
        large_file = tmp_path / "large.bin"
        large_file.write_bytes(b"x" * (6 * 1024 * 1024))
        assert check_file_size(large_file, max_size_mb=5.0) is False


class TestInstallHooks:
    def test_install_success(self, tmp_path: Path) -> None:
        git_hooks = tmp_path / ".git" / "hooks"
        git_hooks.mkdir(parents=True)
        zerg_hooks = tmp_path / ".zerg" / "hooks"
        zerg_hooks.mkdir(parents=True)
        (zerg_hooks / "pre-commit").write_text("#!/bin/bash\necho 'pre-commit'")
        assert install_hooks(tmp_path) is True
        assert os.access(git_hooks / "pre-commit", os.X_OK)

    def test_install_no_git_dir(self, tmp_path: Path) -> None:
        assert install_hooks(tmp_path) is False


class TestSecurityScan:
    def test_scan_clean_project(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("print('hello')")
        results = run_security_scan(tmp_path)
        assert results["passed"] is True

    def test_scan_finds_secrets(self, tmp_path: Path) -> None:
        (tmp_path / "config.py").write_text('api_key = "sk-aBcDeFgHiJkLmNoPqRsTuVwXyZaBcDeFgHiJkLmNoPq"')
        results = run_security_scan(tmp_path)
        assert results["passed"] is False
        assert len(results["secrets_found"]) > 0

    def test_scan_skips_git_dir(self, tmp_path: Path) -> None:
        """Scanning should skip .git directory."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text('password = "supersecretpassword123"')
        results = run_security_scan(tmp_path)
        assert len(results["secrets_found"]) == 0


class TestSecretPatterns:
    def test_patterns_are_compiled(self) -> None:
        for pattern in SECRET_PATTERNS:
            assert hasattr(pattern, "search")

    def test_sensitive_files_defined(self) -> None:
        assert ".env" in SENSITIVE_FILES
        assert "id_rsa" in SENSITIVE_FILES
