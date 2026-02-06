"""Tests for GitRunner base class."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from zerg.exceptions import GitError
from zerg.git.base import GitRunner


class TestGitRunnerInit:
    """Tests for GitRunner initialization."""

    def test_init_valid_repo(self, tmp_repo: Path) -> None:
        runner = GitRunner(tmp_repo)
        assert runner.repo_path == tmp_repo
        assert runner.repo_path.is_absolute()

    def test_init_string_path(self, tmp_repo: Path) -> None:
        runner = GitRunner(str(tmp_repo))
        assert runner.repo_path == tmp_repo

    def test_init_invalid_repo(self, tmp_path: Path) -> None:
        with pytest.raises(GitError) as exc_info:
            GitRunner(tmp_path)
        assert "Not a git repository" in str(exc_info.value)


class TestGitRunnerRun:
    """Tests for GitRunner._run method."""

    def test_run_success(self, tmp_repo: Path) -> None:
        runner = GitRunner(tmp_repo)
        assert runner._run("status").returncode == 0

    def test_run_failure_raises(self, tmp_repo: Path) -> None:
        runner = GitRunner(tmp_repo)
        with pytest.raises(GitError) as exc_info:
            runner._run("checkout", "nonexistent-branch-xyz")
        assert exc_info.value.exit_code is not None

    def test_run_failure_no_check(self, tmp_repo: Path) -> None:
        runner = GitRunner(tmp_repo)
        result = runner._run("checkout", "nonexistent-branch-xyz", check=False)
        assert result.returncode != 0

    def test_run_timeout(self, tmp_repo: Path) -> None:
        runner = GitRunner(tmp_repo)
        with patch("zerg.git.base.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=1)
            with pytest.raises(GitError) as exc_info:
                runner._run("status", timeout=1)
            assert exc_info.value.exit_code == -1


class TestGitRunnerQueries:
    """Tests for GitRunner read-only query methods."""

    def test_current_branch_and_commit(self, tmp_repo: Path) -> None:
        runner = GitRunner(tmp_repo)
        branch = runner.current_branch()
        assert isinstance(branch, str) and len(branch) > 0
        commit = runner.current_commit()
        assert isinstance(commit, str) and len(commit) == 40

    def test_has_changes(self, tmp_repo: Path) -> None:
        runner = GitRunner(tmp_repo)
        assert runner.has_changes() is False
        (tmp_repo / "new-file.txt").write_text("content")
        assert runner.has_changes() is True
