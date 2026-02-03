"""Unit tests for ZERG pre-flight checker."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.preflight import CheckResult, PreflightChecker, PreflightReport


class TestPreflightReport:
    """Tests for PreflightReport dataclass."""

    def test_empty_report_passes(self) -> None:
        report = PreflightReport()
        assert report.passed
        assert report.errors == []
        assert report.warnings == []

    def test_report_with_error_fails(self) -> None:
        report = PreflightReport(
            checks=[
                CheckResult(name="test", passed=False, message="fail", severity="error"),
            ]
        )
        assert not report.passed
        assert len(report.errors) == 1

    def test_report_with_warning_still_passes(self) -> None:
        report = PreflightReport(
            checks=[
                CheckResult(name="test", passed=False, message="warn", severity="warning"),
            ]
        )
        assert report.passed
        assert len(report.warnings) == 1

    def test_str_representation(self) -> None:
        report = PreflightReport(
            checks=[
                CheckResult(name="disk", passed=True, message="ok"),
                CheckResult(name="auth", passed=False, message="no key"),
            ]
        )
        s = str(report)
        assert "PASS" in s
        assert "FAIL" in s


class TestCheckDiskSpace:
    """Tests for disk space check."""

    def test_sufficient_disk_space(self) -> None:
        checker = PreflightChecker(min_disk_gb=0.001)
        result = checker.check_disk_space()
        assert result.passed
        assert "GB free" in result.message

    def test_insufficient_disk_space(self) -> None:
        checker = PreflightChecker(min_disk_gb=999999)
        result = checker.check_disk_space()
        assert not result.passed
        assert "need" in result.message


class TestCheckGitRepo:
    """Tests for git repository check."""

    def test_git_repo_exists(self) -> None:
        checker = PreflightChecker(repo_path=".")
        result = checker.check_git_repo()
        assert result.passed

    def test_no_git_repo(self, tmp_path: Path) -> None:
        checker = PreflightChecker(repo_path=str(tmp_path))
        result = checker.check_git_repo()
        assert not result.passed


class TestCheckAuth:
    """Tests for authentication check."""

    def test_api_key_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        checker = PreflightChecker()
        result = checker.check_auth()
        assert result.passed
        assert "ANTHROPIC_API_KEY" in result.message

    def test_claude_dir_exists(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        checker = PreflightChecker()
        result = checker.check_auth()
        assert result.passed
        assert "OAuth" in result.message

    def test_no_auth(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        checker = PreflightChecker()
        result = checker.check_auth()
        assert not result.passed


class TestCheckPorts:
    """Tests for port availability check."""

    def test_ports_available(self) -> None:
        # Use a high port range unlikely to be in use
        checker = PreflightChecker(
            worker_count=1,
            port_range_start=49152,
            port_range_end=49252,
        )
        result = checker.check_ports()
        assert result.passed

    def test_insufficient_ports(self) -> None:
        # Request impossibly many ports from a tiny range
        checker = PreflightChecker(
            worker_count=1000,
            port_range_start=49152,
            port_range_end=49153,
        )
        result = checker.check_ports()
        assert not result.passed


class TestCheckDocker:
    """Tests for Docker checks."""

    @patch("zerg.preflight.subprocess.run")
    def test_docker_available(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        checker = PreflightChecker()
        result = checker.check_docker_available()
        assert result.passed

    @patch("zerg.preflight.subprocess.run")
    def test_docker_not_available(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1)
        checker = PreflightChecker()
        result = checker.check_docker_available()
        assert not result.passed

    @patch("zerg.preflight.subprocess.run", side_effect=FileNotFoundError)
    def test_docker_not_installed(self, mock_run: MagicMock) -> None:
        checker = PreflightChecker()
        result = checker.check_docker_available()
        assert not result.passed
        assert "not found" in result.message

    @patch("zerg.preflight.subprocess.run")
    def test_docker_image_found(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        checker = PreflightChecker(docker_image="test:latest")
        result = checker.check_docker_image()
        assert result.passed

    @patch("zerg.preflight.subprocess.run")
    def test_docker_image_missing(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1)
        checker = PreflightChecker(docker_image="missing:latest")
        result = checker.check_docker_image()
        assert not result.passed


class TestCheckWorktree:
    """Tests for git worktree check."""

    @patch("zerg.preflight.subprocess.run")
    def test_worktree_supported(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        checker = PreflightChecker(repo_path=".")
        result = checker.check_worktree_feasibility()
        assert result.passed

    def test_worktree_no_git(self, tmp_path: Path) -> None:
        checker = PreflightChecker(repo_path=str(tmp_path))
        result = checker.check_worktree_feasibility()
        assert not result.passed
        assert result.severity == "warning"


class TestRunAll:
    """Tests for run_all orchestration."""

    @patch("zerg.preflight.subprocess.run")
    def test_run_all_container_mode(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        checker = PreflightChecker(mode="container", worker_count=1)
        report = checker.run_all()
        # Should include docker checks
        check_names = [c.name for c in report.checks]
        assert "Docker daemon" in check_names
        assert "Docker image" in check_names
        assert "Authentication" in check_names

    def test_run_all_subprocess_mode(self) -> None:
        checker = PreflightChecker(mode="subprocess", worker_count=1)
        report = checker.run_all()
        check_names = [c.name for c in report.checks]
        # Should NOT include docker checks
        assert "Docker daemon" not in check_names
        assert "Docker image" not in check_names
