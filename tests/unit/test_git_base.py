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
        """Test initialization with a valid git repository."""
        runner = GitRunner(tmp_repo)
        assert runner.repo_path == tmp_repo

    def test_init_string_path(self, tmp_repo: Path) -> None:
        """Test initialization with a string path resolves correctly."""
        runner = GitRunner(str(tmp_repo))
        assert runner.repo_path == tmp_repo

    def test_init_invalid_repo(self, tmp_path: Path) -> None:
        """Test initialization with non-repo raises GitError."""
        with pytest.raises(GitError) as exc_info:
            GitRunner(tmp_path)
        assert "Not a git repository" in str(exc_info.value)
        assert str(tmp_path) in str(exc_info.value.details)

    def test_init_worktree(self, tmp_repo: Path, tmp_path: Path) -> None:
        """Test initialization works with a git worktree."""
        worktree_path = tmp_path / "worktree"
        subprocess.run(
            ["git", "-C", str(tmp_repo), "worktree", "add", str(worktree_path), "HEAD"],
            capture_output=True,
            check=True,
        )
        runner = GitRunner(worktree_path)
        assert runner.repo_path == worktree_path

    def test_init_resolves_relative_path(self, tmp_repo: Path) -> None:
        """Test that repo_path is always resolved to absolute."""
        runner = GitRunner(tmp_repo)
        assert runner.repo_path.is_absolute()


class TestGitRunnerRun:
    """Tests for GitRunner._run method."""

    def test_run_success(self, tmp_repo: Path) -> None:
        """Test running a successful git command."""
        runner = GitRunner(tmp_repo)
        result = runner._run("status")
        assert result.returncode == 0

    def test_run_failure_raises(self, tmp_repo: Path) -> None:
        """Test that a failing command raises GitError with details."""
        runner = GitRunner(tmp_repo)
        with pytest.raises(GitError) as exc_info:
            runner._run("checkout", "nonexistent-branch-xyz")
        assert exc_info.value.exit_code is not None
        assert exc_info.value.command is not None
        assert "git" in exc_info.value.command

    def test_run_failure_no_check(self, tmp_repo: Path) -> None:
        """Test running a failing command with check=False returns result."""
        runner = GitRunner(tmp_repo)
        result = runner._run("checkout", "nonexistent-branch-xyz", check=False)
        assert result.returncode != 0

    def test_run_without_capture(self, tmp_repo: Path) -> None:
        """Test running command without capturing output."""
        runner = GitRunner(tmp_repo)
        result = runner._run("status", capture=False)
        assert result.returncode == 0

    def test_run_timeout(self, tmp_repo: Path) -> None:
        """Test that timeout produces GitError with exit_code -1."""
        runner = GitRunner(tmp_repo)
        with patch("zerg.git.base.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=1)
            with pytest.raises(GitError) as exc_info:
                runner._run("status", timeout=1)
            assert exc_info.value.exit_code == -1


class TestGitRunnerQueries:
    """Tests for GitRunner read-only query methods."""

    def test_current_branch(self, tmp_repo: Path) -> None:
        """Test getting current branch name."""
        runner = GitRunner(tmp_repo)
        branch = runner.current_branch()
        assert isinstance(branch, str)
        assert len(branch) > 0

    def test_current_commit(self, tmp_repo: Path) -> None:
        """Test getting current commit SHA is 40 chars."""
        runner = GitRunner(tmp_repo)
        commit = runner.current_commit()
        assert isinstance(commit, str)
        assert len(commit) == 40

    def test_has_changes_clean(self, tmp_repo: Path) -> None:
        """Test has_changes returns False for clean repo."""
        runner = GitRunner(tmp_repo)
        assert runner.has_changes() is False

    def test_has_changes_untracked(self, tmp_repo: Path) -> None:
        """Test has_changes returns True with untracked file."""
        runner = GitRunner(tmp_repo)
        (tmp_repo / "new-file.txt").write_text("content")
        assert runner.has_changes() is True

    def test_has_changes_modified(self, tmp_repo: Path) -> None:
        """Test has_changes returns True with modified file."""
        runner = GitRunner(tmp_repo)
        (tmp_repo / "README.md").write_text("modified")
        assert runner.has_changes() is True
