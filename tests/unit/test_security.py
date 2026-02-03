"""Tests for ZERG security module."""

import os
from pathlib import Path

from zerg.security import (
    SECRET_PATTERNS,
    SENSITIVE_FILES,
    check_file_size,
    check_for_non_ascii_filenames,
    check_for_secrets,
    check_sensitive_files,
    get_large_files,
    install_hooks,
    run_security_scan,
    uninstall_hooks,
    validate_commit_message,
)


class TestCheckForSecrets:
    """Tests for secret detection."""

    def test_detect_password(self) -> None:
        """Test detecting password patterns."""
        content = 'password = "supersecret123"'

        findings = check_for_secrets(content)

        assert len(findings) == 1
        assert findings[0][0] == 1  # Line 1

    def test_detect_api_key(self) -> None:
        """Test detecting API key patterns."""
        content = 'api_key = "abcdefghijklmnop1234567890"'

        findings = check_for_secrets(content)

        assert len(findings) >= 1

    def test_detect_github_token(self) -> None:
        """Test detecting GitHub token."""
        content = 'token = "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ123456789A"'

        findings = check_for_secrets(content)

        assert len(findings) >= 1

    def test_detect_openai_key(self) -> None:
        """Test detecting OpenAI API key."""
        # OpenAI keys: sk- followed by exactly 48 characters (total 51 chars)
        # Pattern: sk-[A-Za-z0-9]{48}
        content = 'openai_key = "sk-aBcDeFgHiJkLmNoPqRsTuVwXyZaBcDeFgHiJkLmNoPqRsAbCd"'

        findings = check_for_secrets(content)

        # The sk- pattern requires exactly 48 alphanumeric chars after sk-
        assert len(findings) >= 1

    def test_detect_aws_key(self) -> None:
        """Test detecting AWS access key."""
        content = 'aws_key = "AKIAIOSFODNN7EXAMPLE"'

        findings = check_for_secrets(content)

        assert len(findings) >= 1

    def test_detect_private_key(self) -> None:
        """Test detecting private key header."""
        content = "-----BEGIN RSA PRIVATE KEY-----\nMIIEow..."

        findings = check_for_secrets(content)

        assert len(findings) >= 1

    def test_no_false_positives_short_values(self) -> None:
        """Test short values don't trigger false positives."""
        content = 'password = "abc"'  # Too short

        findings = check_for_secrets(content)

        assert len(findings) == 0

    def test_multiline_content(self) -> None:
        """Test checking multiline content."""
        content = """
line1 = "normal"
password = "secretpassword123"
line3 = "also normal"
"""

        findings = check_for_secrets(content)

        assert len(findings) == 1
        assert findings[0][0] == 3  # Line 3 (second non-empty)

    def test_masked_output(self) -> None:
        """Test that found secrets are masked in output."""
        content = 'password = "this_is_a_very_long_secret_that_should_be_truncated_at_fifty_characters"'

        findings = check_for_secrets(content)

        # The matched text should be truncated
        assert len(findings[0][2]) <= 53  # 50 + "..."


class TestCheckNonAsciiFilenames:
    """Tests for non-ASCII filename detection."""

    def test_ascii_filenames(self) -> None:
        """Test ASCII filenames pass."""
        files = ["file.py", "test/file.js", "path/to/file.txt"]

        non_ascii = check_for_non_ascii_filenames(files)

        assert len(non_ascii) == 0

    def test_non_ascii_detected(self) -> None:
        """Test non-ASCII characters detected."""
        files = ["file.py", "tëst.py", "文件.txt"]

        non_ascii = check_for_non_ascii_filenames(files)

        assert len(non_ascii) == 2
        assert "tëst.py" in non_ascii
        assert "文件.txt" in non_ascii


class TestCheckSensitiveFiles:
    """Tests for sensitive file detection."""

    def test_env_file_detected(self) -> None:
        """Test .env file is detected."""
        files = ["src/app.py", ".env", "README.md"]

        sensitive = check_sensitive_files(files)

        assert ".env" in sensitive

    def test_credentials_file_detected(self) -> None:
        """Test credentials files detected."""
        files = ["app.py", "credentials.json", "config.yaml"]

        sensitive = check_sensitive_files(files)

        assert "credentials.json" in sensitive

    def test_ssh_keys_detected(self) -> None:
        """Test SSH key files detected."""
        files = ["id_rsa", "id_ed25519", "known_hosts"]

        sensitive = check_sensitive_files(files)

        assert "id_rsa" in sensitive
        assert "id_ed25519" in sensitive

    def test_path_extraction(self) -> None:
        """Test only filename is checked, not path."""
        files = ["secrets/.env", "config/credentials.json"]

        sensitive = check_sensitive_files(files)

        assert len(sensitive) == 2


class TestValidateCommitMessage:
    """Tests for commit message validation."""

    def test_valid_feat_message(self) -> None:
        """Test valid feat message."""
        is_valid, error = validate_commit_message("feat: add new login feature")

        assert is_valid is True
        assert error is None

    def test_valid_fix_message(self) -> None:
        """Test valid fix message."""
        is_valid, error = validate_commit_message("fix: resolve authentication bug")

        assert is_valid is True
        assert error is None

    def test_valid_with_scope(self) -> None:
        """Test valid message with scope."""
        is_valid, error = validate_commit_message("feat(auth): add OAuth support")

        assert is_valid is True

    def test_valid_breaking_change(self) -> None:
        """Test valid breaking change message."""
        is_valid, error = validate_commit_message("feat!: remove deprecated API")

        assert is_valid is True

    def test_empty_message(self) -> None:
        """Test empty message fails."""
        is_valid, error = validate_commit_message("")

        assert is_valid is False
        assert "empty" in error.lower()

    def test_too_short(self) -> None:
        """Test too short message fails."""
        is_valid, error = validate_commit_message("fix")

        assert is_valid is False
        assert "short" in error.lower()

    def test_too_long(self) -> None:
        """Test too long first line fails."""
        long_message = "feat: " + "a" * 70

        is_valid, error = validate_commit_message(long_message)

        assert is_valid is False
        assert "long" in error.lower()

    def test_invalid_format(self) -> None:
        """Test invalid format fails."""
        is_valid, error = validate_commit_message("Added a new feature")

        assert is_valid is False
        assert "conventional" in error.lower()

    def test_merge_commit_allowed(self) -> None:
        """Test merge commits are allowed."""
        is_valid, error = validate_commit_message("Merge branch 'feature' into main")

        assert is_valid is True


class TestCheckFileSize:
    """Tests for file size checking."""

    def test_small_file_passes(self, tmp_path: Path) -> None:
        """Test small file passes check."""
        small_file = tmp_path / "small.txt"
        small_file.write_text("hello")

        assert check_file_size(small_file) is True

    def test_large_file_fails(self, tmp_path: Path) -> None:
        """Test large file fails check."""
        large_file = tmp_path / "large.bin"
        large_file.write_bytes(b"x" * (6 * 1024 * 1024))  # 6MB

        assert check_file_size(large_file, max_size_mb=5.0) is False

    def test_nonexistent_file_passes(self) -> None:
        """Test nonexistent file passes (no error)."""
        assert check_file_size("/nonexistent/file.txt") is True

    def test_custom_size_limit(self, tmp_path: Path) -> None:
        """Test custom size limit."""
        file = tmp_path / "medium.bin"
        file.write_bytes(b"x" * (2 * 1024 * 1024))  # 2MB

        assert check_file_size(file, max_size_mb=1.0) is False
        assert check_file_size(file, max_size_mb=5.0) is True


class TestGetLargeFiles:
    """Tests for getting large files."""

    def test_get_large_files(self, tmp_path: Path) -> None:
        """Test getting list of large files."""
        small = tmp_path / "small.txt"
        small.write_text("hello")

        large = tmp_path / "large.bin"
        large.write_bytes(b"x" * (6 * 1024 * 1024))

        large_files = get_large_files([str(small), str(large)], max_size_mb=5.0)

        assert len(large_files) == 1
        assert large_files[0][0] == str(large)
        assert large_files[0][1] > 5.0

    def test_get_large_files_empty(self, tmp_path: Path) -> None:
        """Test no large files."""
        small = tmp_path / "small.txt"
        small.write_text("hello")

        large_files = get_large_files([str(small)], max_size_mb=5.0)

        assert len(large_files) == 0


class TestInstallHooks:
    """Tests for git hooks installation."""

    def test_install_no_git_dir(self, tmp_path: Path) -> None:
        """Test install fails without .git directory."""
        result = install_hooks(tmp_path)

        assert result is False

    def test_install_no_zerg_hooks(self, tmp_path: Path) -> None:
        """Test install fails without .zerg/hooks directory."""
        (tmp_path / ".git" / "hooks").mkdir(parents=True)

        result = install_hooks(tmp_path)

        assert result is False

    def test_install_success(self, tmp_path: Path) -> None:
        """Test successful hook installation."""
        git_hooks = tmp_path / ".git" / "hooks"
        git_hooks.mkdir(parents=True)

        zerg_hooks = tmp_path / ".zerg" / "hooks"
        zerg_hooks.mkdir(parents=True)

        # Create a sample hook
        hook = zerg_hooks / "pre-commit"
        hook.write_text("#!/bin/bash\necho 'pre-commit'")

        result = install_hooks(tmp_path)

        assert result is True
        installed_hook = git_hooks / "pre-commit"
        assert installed_hook.exists()
        assert os.access(installed_hook, os.X_OK)


class TestUninstallHooks:
    """Tests for git hooks uninstallation."""

    def test_uninstall_hooks(self, tmp_path: Path) -> None:
        """Test hook uninstallation."""
        git_hooks = tmp_path / ".git" / "hooks"
        git_hooks.mkdir(parents=True)

        zerg_hooks = tmp_path / ".zerg" / "hooks"
        zerg_hooks.mkdir(parents=True)

        # Create hooks
        (zerg_hooks / "pre-commit").write_text("#!/bin/bash")
        (git_hooks / "pre-commit").write_text("#!/bin/bash")

        result = uninstall_hooks(tmp_path)

        assert result is True
        assert not (git_hooks / "pre-commit").exists()


class TestSecurityScan:
    """Tests for full security scan."""

    def test_scan_clean_project(self, tmp_path: Path) -> None:
        """Test scanning clean project."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("print('hello')")

        results = run_security_scan(tmp_path)

        assert results["passed"] is True
        assert len(results["secrets_found"]) == 0
        assert len(results["sensitive_files"]) == 0

    def test_scan_finds_secrets(self, tmp_path: Path) -> None:
        """Test scanning finds secrets."""
        (tmp_path / "config.py").write_text('api_key = "sk-aBcDeFgHiJkLmNoPqRsTuVwXyZaBcDeFgHiJkLmNoPq"')

        results = run_security_scan(tmp_path)

        assert results["passed"] is False
        assert len(results["secrets_found"]) > 0

    def test_scan_finds_sensitive_files(self, tmp_path: Path) -> None:
        """Test scanning finds sensitive files."""
        (tmp_path / ".env").write_text("SECRET=value")

        results = run_security_scan(tmp_path)

        assert results["passed"] is False
        assert len(results["sensitive_files"]) > 0

    def test_scan_skips_git_dir(self, tmp_path: Path) -> None:
        """Test scanning skips .git directory."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text('password = "supersecretpassword123"')

        results = run_security_scan(tmp_path)

        # .git should be skipped, so no secrets found
        assert len(results["secrets_found"]) == 0

    def test_scan_skips_node_modules(self, tmp_path: Path) -> None:
        """Test scanning skips node_modules."""
        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()
        (node_modules / "pkg.js").write_text('api_key = "verylongsecretapikey12345678901234567890"')

        results = run_security_scan(tmp_path)

        assert len(results["secrets_found"]) == 0


class TestSecretPatterns:
    """Tests for secret pattern definitions."""

    def test_patterns_are_compiled(self) -> None:
        """Test that patterns are compiled regex objects."""
        for pattern in SECRET_PATTERNS:
            assert hasattr(pattern, "search")
            assert hasattr(pattern, "match")

    def test_sensitive_files_defined(self) -> None:
        """Test sensitive files list is populated."""
        assert ".env" in SENSITIVE_FILES
        assert "credentials.json" in SENSITIVE_FILES
        assert "id_rsa" in SENSITIVE_FILES
