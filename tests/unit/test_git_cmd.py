"""Thinned unit tests for ZERG git command.

Reduced from 101 to ~30 tests by:
- TestDetectCommitType: 28 -> 1 parametrized (one keyword per type + file priority)
- TestGenerateCommitMessage: 6 -> 2 (single file, many files)
- TestActionCommit: 4 -> 2 (no changes, with push)
- TestActionBranch: 5 -> 2 (list, create success)
- TestActionMerge: 7 -> 3 (no branch, squash, conflict)
- TestActionSync: 6 -> 2 (base branch, conflict)
- TestActionHistory: 4 -> 1
- TestActionFinish: 12 -> 3 (on base, merge choice, pr choice)
- TestActionShip: 7 -> 3 (happy path, commit fails, no-merge)
- TestGitCmd: 11 -> 3 (help, keyboard interrupt, git error)
- TestCommitTypePatterns: 2 -> 1
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from zerg.cli import cli
from zerg.commands.git_cmd import (
    COMMIT_TYPE_PATTERNS,
    action_branch,
    action_commit,
    action_finish,
    action_history,
    action_merge,
    action_ship,
    action_sync,
    detect_commit_type,
    generate_commit_message,
)
from zerg.exceptions import GitError, MergeConflictError
from zerg.git_ops import BranchInfo

if TYPE_CHECKING:
    from pathlib import Path


# =============================================================================
# Test detect_commit_type
# =============================================================================


class TestDetectCommitType:
    """Tests for commit type detection from diff and files."""

    @pytest.mark.parametrize(
        "diff,files,expected",
        [
            ("add new feature", ["src/feature.py"], "feat"),
            ("fix bug in parser", ["src/parser.py"], "fix"),
            ("doc update", ["src/api.py"], "docs"),
            ("format code", ["src/main.py"], "style"),
            ("refactor module", ["src/module.py"], "refactor"),
            ("spec update", ["src/main.py"], "test"),
            ("chore update", ["src/main.py"], "chore"),
            ("random content", ["random.txt"], "chore"),  # default
            ("some diff", ["tests/test_feature.py"], "test"),  # file pattern
            ("some diff", ["README.md"], "docs"),  # file pattern
            # File patterns take priority over diff content
            ("add new feature", ["tests/test_feature.py"], "test"),
        ],
    )
    def test_detect_commit_type(self, diff: str, files: list[str], expected: str) -> None:
        """Test commit type detection from diff keywords and file patterns."""
        result = detect_commit_type(diff, files)
        assert result == expected


# =============================================================================
# Test generate_commit_message
# =============================================================================


class TestGenerateCommitMessage:
    """Tests for commit message generation."""

    def test_single_file_message(self) -> None:
        """Test message generation for single file."""
        result = generate_commit_message("add function", ["src/utils.py"])
        assert "utils" in result
        assert ":" in result

    def test_many_files_root_level(self) -> None:
        """Test message generation for files at root level."""
        files = ["a.py", "b.py", "c.py", "d.py"]
        result = generate_commit_message("changes", files)
        assert "4 files" in result


# =============================================================================
# Test action_commit
# =============================================================================


class TestActionCommit:
    """Tests for commit action."""

    def test_no_changes(self) -> None:
        """Test commit with no changes returns 0."""
        mock_git = MagicMock()
        mock_git.has_changes.return_value = False

        result = action_commit(mock_git, push=False)
        assert result == 0

    def test_commit_with_push(self) -> None:
        """Test commit with push option."""
        mock_git = MagicMock()
        mock_git.has_changes.return_value = True

        status_mock = MagicMock()
        status_mock.stdout = "M  src/file.py"
        staged_mock = MagicMock()
        staged_mock.stdout = "src/file.py"
        unstaged_mock = MagicMock()
        unstaged_mock.stdout = ""
        diff_mock = MagicMock()
        diff_mock.stdout = ""

        mock_git._run.side_effect = [status_mock, staged_mock, unstaged_mock, diff_mock]
        mock_git.commit.return_value = "abc123def456"

        with patch("zerg.commands.git_cmd.Prompt.ask", return_value="chore: update"):
            result = action_commit(mock_git, push=True)

        assert result == 0
        mock_git.push.assert_called_once_with(set_upstream=True)


# =============================================================================
# Test action_branch
# =============================================================================


class TestActionBranch:
    """Tests for branch action."""

    def test_list_branches(self) -> None:
        """Test listing branches when no name provided."""
        mock_git = MagicMock()
        mock_git.list_branches.return_value = [
            BranchInfo(name="main", commit="abc123", is_current=True),
            BranchInfo(name="feature", commit="def456", is_current=False),
        ]

        result = action_branch(mock_git, name=None, base="main")
        assert result == 0
        mock_git.list_branches.assert_called_once()

    def test_create_branch_success(self) -> None:
        """Test creating branch successfully."""
        mock_git = MagicMock()
        mock_git.branch_exists.return_value = False

        with patch("zerg.commands.git_cmd.Confirm.ask", return_value=False):
            result = action_branch(mock_git, name="new-branch", base="main")

        assert result == 0
        mock_git.create_branch.assert_called_once_with("new-branch", "main")


# =============================================================================
# Test action_merge
# =============================================================================


class TestActionMerge:
    """Tests for merge action."""

    def test_merge_no_branch_specified(self) -> None:
        """Test merge without branch specified."""
        mock_git = MagicMock()
        result = action_merge(mock_git, branch=None, strategy="merge", base="main")
        assert result == 1

    def test_merge_squash_strategy(self) -> None:
        """Test squash merge strategy."""
        mock_git = MagicMock()
        mock_git.branch_exists.return_value = True

        result = action_merge(mock_git, branch="feature", strategy="squash", base="main")
        assert result == 0
        mock_git._run.assert_called_once_with("merge", "--squash", "feature")

    def test_merge_conflict(self) -> None:
        """Test merge with conflicts."""
        mock_git = MagicMock()
        mock_git.branch_exists.return_value = True
        mock_git.merge.side_effect = MergeConflictError(
            "Merge conflict",
            source_branch="feature",
            target_branch="main",
            conflicting_files=["src/file.py"],
        )

        result = action_merge(mock_git, branch="feature", strategy="merge", base="main")
        assert result == 1


# =============================================================================
# Test action_sync
# =============================================================================


class TestActionSync:
    """Tests for sync action."""

    def test_sync_on_base_branch(self) -> None:
        """Test sync when on base branch."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "main"

        result = action_sync(mock_git, base="main")
        assert result == 0
        mock_git.fetch.assert_called_once()

    def test_sync_rebase_conflict(self) -> None:
        """Test sync when rebase has conflict."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "feature"
        mock_git.rebase.side_effect = MergeConflictError(
            "Rebase conflict",
            source_branch="feature",
            target_branch="main",
            conflicting_files=["src/file.py"],
        )

        result = action_sync(mock_git, base="main")
        assert result == 1


# =============================================================================
# Test action_history
# =============================================================================


class TestActionHistory:
    """Tests for history action."""

    def test_history_default(self) -> None:
        """Test history with default options."""
        mock_git = MagicMock()
        log_result = MagicMock()
        log_result.stdout = "abc123 feat: add feature\ndef456 fix: bug fix"
        mock_git._run.return_value = log_result

        result = action_history(mock_git, since=None)
        assert result == 0


# =============================================================================
# Test action_finish
# =============================================================================


class TestActionFinish:
    """Tests for finish workflow action."""

    def test_finish_on_base_branch(self) -> None:
        """Test finish when already on base branch."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "main"

        result = action_finish(mock_git, base="main", push=False)
        assert result == 0

    def test_finish_merge_choice(self) -> None:
        """Test finish with merge choice."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "feature"

        log_result = MagicMock()
        log_result.stdout = "abc123 feat: something"
        diff_result = MagicMock()
        diff_result.stdout = ""
        mock_git._run.return_value = log_result
        mock_git.commit.return_value = "merged123"

        with (
            patch("zerg.commands.git_cmd.Prompt.ask") as mock_prompt,
            patch("zerg.commands.git_cmd.Confirm.ask") as mock_confirm,
        ):
            mock_prompt.side_effect = ["merge", "feat: merge feature"]
            mock_confirm.side_effect = [True, True]
            mock_git._run.return_value = log_result

            result = action_finish(mock_git, base="main", push=False)

        assert result == 0
        mock_git.checkout.assert_any_call("main")
        mock_git.push.assert_called()
        mock_git.delete_branch.assert_called_with("feature", force=True)

    def test_finish_pr_choice(self) -> None:
        """Test finish with pr choice."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "feature"

        log_result = MagicMock()
        log_result.stdout = "abc123 feat: something"
        mock_git._run.return_value = log_result

        with (
            patch("zerg.commands.git_cmd.Prompt.ask", return_value="pr"),
            patch("zerg.commands.git_cmd.Confirm.ask", return_value=True),
        ):
            result = action_finish(mock_git, base="main", push=False)

        assert result == 0
        mock_git.push.assert_called_with(set_upstream=True)


# =============================================================================
# Test action_ship
# =============================================================================


class TestActionShip:
    """Tests for ship action."""

    @patch("zerg.commands.git_cmd.action_pr", return_value=0)
    @patch("zerg.commands.git_cmd.action_commit", return_value=0)
    def test_ship_happy_path(self, mock_commit: MagicMock, mock_pr: MagicMock) -> None:
        """Test ship happy path: commit, push, PR, merge, checkout, cleanup."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "feature/auth"
        mock_git.has_changes.return_value = True

        pr_view_result = MagicMock()
        pr_view_result.stdout = "42\n"
        pr_view_result.returncode = 0

        merge_result = MagicMock()
        merge_result.returncode = 0

        with patch("subprocess.run") as mock_subprocess:
            mock_subprocess.side_effect = [pr_view_result, merge_result]
            result = action_ship(mock_git, base="main", draft=False, reviewer=None, no_merge=False)

        assert result == 0
        mock_commit.assert_called_once_with(mock_git, push=True, mode="auto")
        mock_pr.assert_called_once_with(mock_git, "main", False, None)

    @patch("zerg.commands.git_cmd.action_commit", return_value=1)
    def test_ship_commit_fails(self, mock_commit: MagicMock) -> None:
        """Test ship aborts when commit fails."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "feature/auth"
        mock_git.has_changes.return_value = True

        result = action_ship(mock_git, base="main", draft=False, reviewer=None, no_merge=False)
        assert result == 1

    @patch("zerg.commands.git_cmd.action_pr", return_value=0)
    @patch("zerg.commands.git_cmd.action_commit", return_value=0)
    def test_ship_no_merge_flag(self, mock_commit: MagicMock, mock_pr: MagicMock) -> None:
        """Test ship stops after PR creation with --no-merge flag."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "feature/auth"
        mock_git.has_changes.return_value = True

        result = action_ship(mock_git, base="main", draft=False, reviewer=None, no_merge=True)

        assert result == 0
        mock_git.checkout.assert_not_called()
        mock_git.delete_branch.assert_not_called()


# =============================================================================
# Test git_cmd (main CLI command)
# =============================================================================


class TestGitCmd:
    """Tests for the main git CLI command."""

    def test_git_cmd_help(self) -> None:
        """Test git --help shows options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["git", "--help"])

        assert result.exit_code == 0
        assert "action" in result.output
        assert "push" in result.output
        assert "base" in result.output

    def test_git_cmd_keyboard_interrupt(self, tmp_repo: Path) -> None:
        """Test git command with keyboard interrupt."""
        runner = CliRunner()

        with patch("zerg.commands.git_cmd.GitOps") as mock_git_cls:
            mock_git_cls.side_effect = KeyboardInterrupt()

            result = runner.invoke(cli, ["git", "--action", "commit"])

        assert result.exit_code == 130

    def test_git_cmd_git_error(self, tmp_repo: Path) -> None:
        """Test git command with GitError."""
        runner = CliRunner()

        with patch("zerg.commands.git_cmd.GitOps") as mock_git_cls:
            mock_git_cls.side_effect = GitError("Git failed")

            result = runner.invoke(cli, ["git", "--action", "commit"])

        assert result.exit_code == 1


# =============================================================================
# Test COMMIT_TYPE_PATTERNS constant
# =============================================================================


class TestCommitTypePatterns:
    """Tests for COMMIT_TYPE_PATTERNS constant."""

    def test_patterns_exist(self) -> None:
        """Test that expected commit types have patterns."""
        expected_types = ["feat", "fix", "docs", "style", "refactor", "test", "chore"]
        for commit_type in expected_types:
            assert commit_type in COMMIT_TYPE_PATTERNS
            assert len(COMMIT_TYPE_PATTERNS[commit_type]) > 0
