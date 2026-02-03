"""Comprehensive unit tests for ZERG git command.

Tests cover all code paths in zerg/commands/git_cmd.py for 100% coverage:
- Commit type detection
- Commit message generation
- Commit action with various scenarios
- Branch management
- Merge operations with different strategies
- Sync operations
- History display
- Interactive finish workflow
- Main CLI command entry point
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import click
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
    git_cmd,
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

    def test_detect_test_from_files(self) -> None:
        """Test detection of 'test' type from test files."""
        result = detect_commit_type("some diff", ["tests/test_feature.py"])
        assert result == "test"

    def test_detect_docs_from_md_files(self) -> None:
        """Test detection of 'docs' type from markdown files."""
        result = detect_commit_type("some diff", ["README.md"])
        assert result == "docs"

    def test_detect_docs_from_readme_in_filename(self) -> None:
        """Test detection of 'docs' type from README in filename."""
        result = detect_commit_type("some diff", ["readme.txt"])
        assert result == "docs"

    def test_detect_feat_from_add_keyword(self) -> None:
        """Test detection of 'feat' type from add keyword in diff."""
        result = detect_commit_type("add new feature", ["src/feature.py"])
        assert result == "feat"

    def test_detect_feat_from_implement_keyword(self) -> None:
        """Test detection of 'feat' from implement keyword."""
        result = detect_commit_type("implement auth system", ["src/auth.py"])
        assert result == "feat"

    def test_detect_feat_from_create_keyword(self) -> None:
        """Test detection of 'feat' from create keyword."""
        result = detect_commit_type("create user model", ["models/user.py"])
        assert result == "feat"

    def test_detect_feat_from_new_keyword(self) -> None:
        """Test detection of 'feat' from new keyword."""
        result = detect_commit_type("new endpoint", ["api/endpoint.py"])
        assert result == "feat"

    def test_detect_feat_from_feature_keyword(self) -> None:
        """Test detection of 'feat' from feature keyword."""
        result = detect_commit_type("feature implementation", ["src/app.py"])
        assert result == "feat"

    def test_detect_fix_from_fix_keyword(self) -> None:
        """Test detection of 'fix' type from fix keyword."""
        result = detect_commit_type("fix bug in parser", ["src/parser.py"])
        assert result == "fix"

    def test_detect_fix_from_bugfix_keyword(self) -> None:
        """Test detection of 'fix' from bugfix keyword."""
        result = detect_commit_type("bugfix for login", ["src/auth.py"])
        assert result == "fix"

    def test_detect_fix_from_resolve_keyword(self) -> None:
        """Test detection of 'fix' from resolve keyword."""
        result = detect_commit_type("resolve issue", ["src/main.py"])
        assert result == "fix"

    def test_detect_fix_from_correct_keyword(self) -> None:
        """Test detection of 'fix' from correct keyword."""
        result = detect_commit_type("correct calculation", ["src/math.py"])
        assert result == "fix"

    def test_detect_fix_from_patch_keyword(self) -> None:
        """Test detection of 'fix' from patch keyword."""
        result = detect_commit_type("patch vulnerability", ["src/security.py"])
        assert result == "fix"

    def test_detect_docs_from_doc_keyword(self) -> None:
        """Test detection of 'docs' from doc keyword in diff."""
        result = detect_commit_type("doc update", ["src/api.py"])
        assert result == "docs"

    def test_detect_docs_from_comment_keyword(self) -> None:
        """Test detection of 'docs' from comment keyword."""
        result = detect_commit_type("comment improvements", ["src/utils.py"])
        assert result == "docs"

    def test_detect_docs_from_documentation_keyword(self) -> None:
        """Test detection of 'docs' from documentation keyword."""
        result = detect_commit_type("documentation update", ["src/app.py"])
        assert result == "docs"

    def test_detect_style_from_format_keyword(self) -> None:
        """Test detection of 'style' from format keyword."""
        result = detect_commit_type("format code", ["src/main.py"])
        assert result == "style"

    def test_detect_style_from_lint_keyword(self) -> None:
        """Test detection of 'style' from lint keyword."""
        result = detect_commit_type("lint fixes", ["src/utils.py"])
        assert result == "style"

    def test_detect_style_from_whitespace_keyword(self) -> None:
        """Test detection of 'style' from whitespace keyword."""
        result = detect_commit_type("whitespace cleanup", ["src/file.py"])
        assert result == "style"

    def test_detect_style_from_prettier_keyword(self) -> None:
        """Test detection of 'style' from prettier keyword."""
        result = detect_commit_type("prettier run", ["src/app.js"])
        assert result == "style"

    def test_detect_refactor_from_refactor_keyword(self) -> None:
        """Test detection of 'refactor' from refactor keyword."""
        result = detect_commit_type("refactor module", ["src/module.py"])
        assert result == "refactor"

    def test_detect_refactor_from_restructure_keyword(self) -> None:
        """Test detection of 'refactor' from restructure keyword."""
        result = detect_commit_type("restructure code", ["src/app.py"])
        assert result == "refactor"

    def test_detect_refactor_from_reorganize_keyword(self) -> None:
        """Test detection of 'refactor' from reorganize keyword."""
        result = detect_commit_type("reorganize imports", ["src/main.py"])
        assert result == "refactor"

    def test_detect_refactor_from_cleanup_keyword(self) -> None:
        """Test detection of 'refactor' from cleanup keyword."""
        result = detect_commit_type("cleanup dead code", ["src/utils.py"])
        assert result == "refactor"

    def test_detect_test_from_spec_keyword(self) -> None:
        """Test detection of 'test' from spec keyword in diff."""
        result = detect_commit_type("spec update", ["src/main.py"])
        assert result == "test"

    def test_detect_test_from_coverage_keyword(self) -> None:
        """Test detection of 'test' from coverage keyword."""
        result = detect_commit_type("coverage improvement", ["src/main.py"])
        assert result == "test"

    def test_detect_chore_from_chore_keyword(self) -> None:
        """Test detection of 'chore' from chore keyword."""
        result = detect_commit_type("chore update", ["src/main.py"])
        assert result == "chore"

    def test_detect_chore_from_build_keyword(self) -> None:
        """Test detection of 'chore' from build keyword."""
        result = detect_commit_type("build config", ["Makefile"])
        assert result == "chore"

    def test_detect_chore_from_ci_keyword(self) -> None:
        """Test detection of 'chore' from ci keyword."""
        result = detect_commit_type("ci pipeline", [".github/workflows/ci.yml"])
        assert result == "chore"

    def test_detect_chore_from_deps_keyword(self) -> None:
        """Test detection of 'chore' from deps keyword."""
        result = detect_commit_type("deps update", ["requirements.txt"])
        assert result == "chore"

    def test_detect_chore_from_bump_keyword(self) -> None:
        """Test detection of 'chore' from bump keyword."""
        result = detect_commit_type("bump version", ["pyproject.toml"])
        assert result == "chore"

    def test_detect_chore_from_update_dep_keyword(self) -> None:
        """Test detection of 'chore' from 'update.*dep' pattern."""
        result = detect_commit_type("update dependencies", ["requirements.txt"])
        assert result == "chore"

    def test_detect_chore_default(self) -> None:
        """Test default to 'chore' when no patterns match."""
        result = detect_commit_type("random content", ["random.txt"])
        assert result == "chore"

    def test_file_patterns_take_priority_over_diff(self) -> None:
        """Test that file patterns take priority over diff content."""
        # File pattern (test) should win over diff content (feat)
        result = detect_commit_type("add new feature", ["tests/test_feature.py"])
        assert result == "test"


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

    def test_multiple_files_message(self) -> None:
        """Test message generation for 2-3 files."""
        result = generate_commit_message("changes", ["src/a.py", "src/b.py"])
        assert "a" in result and "b" in result
        assert ":" in result

    def test_three_files_message(self) -> None:
        """Test message generation for exactly 3 files."""
        result = generate_commit_message("changes", ["src/a.py", "src/b.py", "src/c.py"])
        assert ":" in result
        # Should contain all 3 stems
        assert "a" in result
        assert "b" in result
        assert "c" in result

    def test_many_files_with_directories(self) -> None:
        """Test message generation for 4+ files grouped by directory."""
        files = [
            "src/auth/login.py",
            "src/auth/logout.py",
            "src/core/main.py",
            "src/core/utils.py",
        ]
        result = generate_commit_message("changes", files)
        assert ":" in result
        # Should mention directories
        assert "auth" in result or "core" in result or "files" in result

    def test_many_files_root_level(self) -> None:
        """Test message generation for files at root level."""
        files = ["a.py", "b.py", "c.py", "d.py"]
        result = generate_commit_message("changes", files)
        assert "4 files" in result

    def test_commit_type_prefix(self) -> None:
        """Test that commit type is prefixed."""
        result = generate_commit_message("fix bug", ["src/bugfix.py"])
        assert result.startswith("fix:")


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

    def test_with_unstaged_changes_stages_all(self) -> None:
        """Test commit stages all when nothing staged."""
        mock_git = MagicMock()
        mock_git.has_changes.return_value = True

        # Status result
        status_mock = MagicMock()
        status_mock.stdout = " M src/file.py"

        # No staged files
        staged_mock = MagicMock()
        staged_mock.stdout = ""

        # Unstaged files exist
        unstaged_mock = MagicMock()
        unstaged_mock.stdout = "src/file.py"

        # Diff result
        diff_mock = MagicMock()
        diff_mock.stdout = "1 file changed"

        mock_git._run.side_effect = [status_mock, staged_mock, unstaged_mock, None, diff_mock]
        mock_git.commit.return_value = "abc123def456"

        with patch("zerg.commands.git_cmd.Prompt.ask", return_value="test: update"):
            result = action_commit(mock_git, push=False)

        assert result == 0
        mock_git._run.assert_any_call("add", "-A")
        mock_git.commit.assert_called_once_with("test: update")

    def test_with_staged_changes(self) -> None:
        """Test commit with already staged changes."""
        mock_git = MagicMock()
        mock_git.has_changes.return_value = True

        # Status result
        status_mock = MagicMock()
        status_mock.stdout = "M  src/file.py"

        # Staged files exist
        staged_mock = MagicMock()
        staged_mock.stdout = "src/file.py"

        # No unstaged files
        unstaged_mock = MagicMock()
        unstaged_mock.stdout = ""

        # Diff result
        diff_mock = MagicMock()
        diff_mock.stdout = "1 file changed"

        mock_git._run.side_effect = [status_mock, staged_mock, unstaged_mock, diff_mock]
        mock_git.commit.return_value = "abc123def456"

        with patch("zerg.commands.git_cmd.Prompt.ask", return_value="chore: update file"):
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

    def test_commit_failure(self) -> None:
        """Test commit failure handling."""
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
        mock_git.commit.side_effect = GitError("Commit failed")

        with patch("zerg.commands.git_cmd.Prompt.ask", return_value="chore: update"):
            result = action_commit(mock_git, push=False)

        assert result == 1


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

    def test_create_branch_already_exists(self) -> None:
        """Test creating branch that already exists."""
        mock_git = MagicMock()
        mock_git.branch_exists.return_value = True

        result = action_branch(mock_git, name="existing-branch", base="main")
        assert result == 1

    def test_create_branch_success_without_checkout(self) -> None:
        """Test creating branch successfully without checkout."""
        mock_git = MagicMock()
        mock_git.branch_exists.return_value = False

        with patch("zerg.commands.git_cmd.Confirm.ask", return_value=False):
            result = action_branch(mock_git, name="new-branch", base="main")

        assert result == 0
        mock_git.create_branch.assert_called_once_with("new-branch", "main")
        mock_git.checkout.assert_not_called()

    def test_create_branch_success_with_checkout(self) -> None:
        """Test creating branch and checking out."""
        mock_git = MagicMock()
        mock_git.branch_exists.return_value = False

        with patch("zerg.commands.git_cmd.Confirm.ask", return_value=True):
            result = action_branch(mock_git, name="new-branch", base="main")

        assert result == 0
        mock_git.create_branch.assert_called_once_with("new-branch", "main")
        mock_git.checkout.assert_called_once_with("new-branch")

    def test_create_branch_failure(self) -> None:
        """Test branch creation failure."""
        mock_git = MagicMock()
        mock_git.branch_exists.return_value = False
        mock_git.create_branch.side_effect = GitError("Failed to create branch")

        result = action_branch(mock_git, name="new-branch", base="main")
        assert result == 1


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

    def test_merge_branch_not_exists(self) -> None:
        """Test merge with non-existent branch."""
        mock_git = MagicMock()
        mock_git.branch_exists.return_value = False

        result = action_merge(mock_git, branch="nonexistent", strategy="merge", base="main")
        assert result == 1

    def test_merge_squash_strategy(self) -> None:
        """Test squash merge strategy."""
        mock_git = MagicMock()
        mock_git.branch_exists.return_value = True

        result = action_merge(mock_git, branch="feature", strategy="squash", base="main")
        assert result == 0
        mock_git._run.assert_called_once_with("merge", "--squash", "feature")

    def test_merge_rebase_strategy(self) -> None:
        """Test rebase merge strategy."""
        mock_git = MagicMock()
        mock_git.branch_exists.return_value = True

        result = action_merge(mock_git, branch="feature", strategy="rebase", base="main")
        assert result == 0
        mock_git.rebase.assert_called_once_with("feature")

    def test_merge_regular_strategy(self) -> None:
        """Test regular merge strategy."""
        mock_git = MagicMock()
        mock_git.branch_exists.return_value = True

        result = action_merge(mock_git, branch="feature", strategy="merge", base="main")
        assert result == 0
        mock_git.merge.assert_called_once_with("feature")

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

    def test_merge_git_error(self) -> None:
        """Test merge with git error (not conflict)."""
        mock_git = MagicMock()
        mock_git.branch_exists.return_value = True
        mock_git.merge.side_effect = GitError("Merge failed")

        result = action_merge(mock_git, branch="feature", strategy="merge", base="main")
        assert result == 1

    def test_rebase_conflict(self) -> None:
        """Test rebase with conflicts."""
        mock_git = MagicMock()
        mock_git.branch_exists.return_value = True
        mock_git.rebase.side_effect = MergeConflictError(
            "Rebase conflict",
            source_branch="feature",
            target_branch="main",
            conflicting_files=["src/file.py"],
        )

        result = action_merge(mock_git, branch="feature", strategy="rebase", base="main")
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

    def test_sync_on_feature_branch(self) -> None:
        """Test sync when on feature branch."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "feature"

        result = action_sync(mock_git, base="main")
        assert result == 0
        mock_git.fetch.assert_called_once()
        mock_git.rebase.assert_called_once_with("origin/main")

    def test_sync_pull_rebase_fails(self) -> None:
        """Test sync when pull --rebase fails (handled gracefully)."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "feature"
        mock_git._run.side_effect = GitError("Pull failed")

        # Should not fail overall
        result = action_sync(mock_git, base="main")
        assert result == 0

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

    def test_sync_rebase_git_error(self) -> None:
        """Test sync when rebase has git error (not conflict)."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "feature"
        mock_git.rebase.side_effect = GitError("Rebase failed")

        # Non-conflict git errors are ignored
        result = action_sync(mock_git, base="main")
        assert result == 0

    def test_sync_fetch_failure(self) -> None:
        """Test sync when fetch fails."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "main"
        mock_git.fetch.side_effect = GitError("Fetch failed")

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

    def test_history_with_since(self) -> None:
        """Test history with since option."""
        mock_git = MagicMock()
        log_result = MagicMock()
        log_result.stdout = "abc123 feat: add feature"
        mock_git._run.return_value = log_result

        result = action_history(mock_git, since="v1.0.0")
        assert result == 0
        # Verify args contain the since parameter
        call_args = mock_git._run.call_args
        assert "v1.0.0..HEAD" in call_args[0]

    def test_history_no_commits(self) -> None:
        """Test history with no commits found."""
        mock_git = MagicMock()
        log_result = MagicMock()
        log_result.stdout = ""
        mock_git._run.return_value = log_result

        result = action_history(mock_git, since=None)
        assert result == 0

    def test_history_single_word_commit(self) -> None:
        """Test history with single-word commit (no message after SHA)."""
        mock_git = MagicMock()
        log_result = MagicMock()
        log_result.stdout = "abc123\n"
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
            mock_confirm.side_effect = [True, True]  # push, delete branch
            mock_git._run.return_value = log_result

            result = action_finish(mock_git, base="main", push=False)

        assert result == 0
        mock_git.checkout.assert_any_call("main")
        mock_git.push.assert_called()
        mock_git.delete_branch.assert_called_with("feature", force=True)

    def test_finish_merge_with_conflict(self) -> None:
        """Test finish merge with conflict."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "feature"

        log_result = MagicMock()
        log_result.stdout = "abc123 feat: something"
        pull_result = MagicMock()
        pull_result.stdout = ""

        # Sequence: git log, pull --rebase, merge --squash (throws)
        mock_git._run.side_effect = [
            log_result,  # git log
            pull_result,  # git pull --rebase
            MergeConflictError(
                "Merge conflict",
                source_branch="feature",
                target_branch="main",
                conflicting_files=["src/file.py"],
            ),  # merge --squash
        ]

        with patch("zerg.commands.git_cmd.Prompt.ask", return_value="merge"):
            result = action_finish(mock_git, base="main", push=False)

        assert result == 1
        mock_git.checkout.assert_called_with("feature")  # Switch back to feature

    def test_finish_merge_pull_rebase_fails(self) -> None:
        """Test finish merge when pull --rebase fails (GitError caught, continues)."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "feature"

        log_result = MagicMock()
        log_result.stdout = "abc123 feat: something"
        merge_result = MagicMock()
        merge_result.stdout = ""
        diff_result = MagicMock()
        diff_result.stdout = ""

        # Sequence: git log, pull --rebase (throws GitError), merge --squash, diff --cached
        mock_git._run.side_effect = [
            log_result,  # git log
            GitError("Pull rebase failed"),  # git pull --rebase - caught and ignored
            merge_result,  # merge --squash
            diff_result,  # diff --cached --stat
        ]
        mock_git.commit.return_value = "merged123"

        with (
            patch("zerg.commands.git_cmd.Prompt.ask") as mock_prompt,
            patch("zerg.commands.git_cmd.Confirm.ask") as mock_confirm,
        ):
            mock_prompt.side_effect = ["merge", "feat: merge feature"]
            mock_confirm.side_effect = [False, False]  # no push, no delete

            result = action_finish(mock_git, base="main", push=False)

        # Should succeed despite pull --rebase failure
        assert result == 0
        mock_git.commit.assert_called_once()

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

    def test_finish_pr_choice_with_push_flag(self) -> None:
        """Test finish pr with push=True flag."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "feature"

        log_result = MagicMock()
        log_result.stdout = "abc123 feat: something"
        mock_git._run.return_value = log_result

        with patch("zerg.commands.git_cmd.Prompt.ask", return_value="pr"):
            result = action_finish(mock_git, base="main", push=True)

        assert result == 0
        mock_git.push.assert_called_with(set_upstream=True)

    def test_finish_keep_choice(self) -> None:
        """Test finish with keep choice."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "feature"

        log_result = MagicMock()
        log_result.stdout = "abc123 feat: something"
        mock_git._run.return_value = log_result

        with (
            patch("zerg.commands.git_cmd.Prompt.ask", return_value="keep"),
            patch("zerg.commands.git_cmd.Confirm.ask", return_value=True),
        ):
            result = action_finish(mock_git, base="main", push=False)

        assert result == 0
        mock_git.push.assert_called_with(set_upstream=True)

    def test_finish_keep_choice_with_push_flag(self) -> None:
        """Test finish keep with push=True flag."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "feature"

        log_result = MagicMock()
        log_result.stdout = "abc123 feat: something"
        mock_git._run.return_value = log_result

        with patch("zerg.commands.git_cmd.Prompt.ask", return_value="keep"):
            result = action_finish(mock_git, base="main", push=True)

        assert result == 0
        mock_git.push.assert_called_with(set_upstream=True)

    def test_finish_discard_choice_confirmed(self) -> None:
        """Test finish with discard choice confirmed."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "feature"

        log_result = MagicMock()
        log_result.stdout = "abc123 feat: something"
        mock_git._run.return_value = log_result

        with (
            patch("zerg.commands.git_cmd.Prompt.ask", return_value="discard"),
            patch("zerg.commands.git_cmd.Confirm.ask", return_value=True),
        ):
            result = action_finish(mock_git, base="main", push=False)

        assert result == 0
        mock_git.checkout.assert_called_with("main")
        mock_git.delete_branch.assert_called_with("feature", force=True)

    def test_finish_discard_choice_cancelled(self) -> None:
        """Test finish with discard choice cancelled."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "feature"

        log_result = MagicMock()
        log_result.stdout = "abc123 feat: something"
        mock_git._run.return_value = log_result

        with (
            patch("zerg.commands.git_cmd.Prompt.ask", return_value="discard"),
            patch("zerg.commands.git_cmd.Confirm.ask", return_value=False),
        ):
            result = action_finish(mock_git, base="main", push=False)

        assert result == 0
        mock_git.checkout.assert_not_called()
        mock_git.delete_branch.assert_not_called()

    def test_finish_no_log_output(self) -> None:
        """Test finish when no commits in branch."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "feature"

        log_result = MagicMock()
        log_result.stdout = ""
        mock_git._run.return_value = log_result

        with (
            patch("zerg.commands.git_cmd.Prompt.ask", return_value="keep"),
            patch("zerg.commands.git_cmd.Confirm.ask", return_value=False),
        ):
            result = action_finish(mock_git, base="main", push=False)

        assert result == 0

    def test_finish_merge_no_push_no_delete(self) -> None:
        """Test finish merge without pushing or deleting."""
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
            mock_confirm.side_effect = [False, False]  # no push, no delete

            result = action_finish(mock_git, base="main", push=False)

        assert result == 0
        mock_git.push.assert_not_called()


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

        # Mock subprocess calls for gh pr view and gh pr merge
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
        mock_git.checkout.assert_called_once_with("main")
        mock_git._run.assert_called_with("pull", "--rebase")
        mock_git.delete_branch.assert_called_once_with("feature/auth", force=True)

    def test_ship_already_on_base(self) -> None:
        """Test ship when already on base branch returns 0 with warning."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "main"

        result = action_ship(mock_git, base="main", draft=False, reviewer=None, no_merge=False)
        assert result == 0

    @patch("zerg.commands.git_cmd.action_commit", return_value=1)
    def test_ship_commit_fails(self, mock_commit: MagicMock) -> None:
        """Test ship aborts when commit fails."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "feature/auth"
        mock_git.has_changes.return_value = True

        result = action_ship(mock_git, base="main", draft=False, reviewer=None, no_merge=False)
        assert result == 1

    @patch("zerg.commands.git_cmd.action_pr", return_value=1)
    @patch("zerg.commands.git_cmd.action_commit", return_value=0)
    def test_ship_pr_fails(self, mock_commit: MagicMock, mock_pr: MagicMock) -> None:
        """Test ship aborts when PR creation fails."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "feature/auth"
        mock_git.has_changes.return_value = True

        result = action_ship(mock_git, base="main", draft=False, reviewer=None, no_merge=False)
        assert result == 1
        mock_commit.assert_called_once()
        mock_pr.assert_called_once()

    @patch("zerg.commands.git_cmd.action_pr", return_value=0)
    @patch("zerg.commands.git_cmd.action_commit", return_value=0)
    def test_ship_merge_falls_back_to_admin(self, mock_commit: MagicMock, mock_pr: MagicMock) -> None:
        """Test ship falls back to admin merge when regular merge is blocked."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "feature/auth"
        mock_git.has_changes.return_value = True

        pr_view_result = MagicMock()
        pr_view_result.stdout = "42\n"
        pr_view_result.returncode = 0

        # First merge fails (returncode != 0)
        merge_fail_result = MagicMock()
        merge_fail_result.returncode = 1

        # Admin merge succeeds
        admin_merge_result = MagicMock()
        admin_merge_result.returncode = 0

        with patch("subprocess.run") as mock_subprocess:
            mock_subprocess.side_effect = [pr_view_result, merge_fail_result, admin_merge_result]
            result = action_ship(mock_git, base="main", draft=False, reviewer=None, no_merge=False)

        assert result == 0
        # Should have called subprocess 3 times: pr view, merge, admin merge
        assert mock_subprocess.call_count == 3

    @patch("zerg.commands.git_cmd.action_pr", return_value=0)
    @patch("zerg.commands.git_cmd.action_commit", return_value=0)
    def test_ship_no_merge_flag(self, mock_commit: MagicMock, mock_pr: MagicMock) -> None:
        """Test ship stops after PR creation with --no-merge flag."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "feature/auth"
        mock_git.has_changes.return_value = True

        result = action_ship(mock_git, base="main", draft=False, reviewer=None, no_merge=True)

        assert result == 0
        mock_commit.assert_called_once()
        mock_pr.assert_called_once()
        # Should NOT have called checkout or delete_branch
        mock_git.checkout.assert_not_called()
        mock_git.delete_branch.assert_not_called()

    @patch("zerg.commands.git_cmd.action_pr", return_value=0)
    def test_ship_no_local_changes(self, mock_pr: MagicMock) -> None:
        """Test ship with no local changes still pushes and creates PR."""
        mock_git = MagicMock()
        mock_git.current_branch.return_value = "feature/auth"
        mock_git.has_changes.return_value = False

        pr_view_result = MagicMock()
        pr_view_result.stdout = "42\n"
        pr_view_result.returncode = 0

        merge_result = MagicMock()
        merge_result.returncode = 0

        with patch("subprocess.run") as mock_subprocess:
            mock_subprocess.side_effect = [pr_view_result, merge_result]
            result = action_ship(mock_git, base="main", draft=False, reviewer=None, no_merge=False)

        assert result == 0
        # Should have pushed without committing
        mock_git.push.assert_called_once_with(set_upstream=True)
        mock_pr.assert_called_once()


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

    def test_git_cmd_commit_action(self, tmp_repo: Path) -> None:
        """Test git command with commit action."""
        runner = CliRunner()

        with patch("zerg.commands.git_cmd.GitOps") as mock_git_cls:
            mock_git = MagicMock()
            mock_git_cls.return_value = mock_git
            mock_git.current_branch.return_value = "main"
            mock_git.has_changes.return_value = False

            result = runner.invoke(cli, ["git", "--action", "commit"])

        # Should exit 0 (no changes)
        assert result.exit_code == 0

    def test_git_cmd_branch_action(self, tmp_repo: Path) -> None:
        """Test git command with branch action."""
        runner = CliRunner()

        with patch("zerg.commands.git_cmd.GitOps") as mock_git_cls:
            mock_git = MagicMock()
            mock_git_cls.return_value = mock_git
            mock_git.current_branch.return_value = "main"
            mock_git.list_branches.return_value = [
                BranchInfo(name="main", commit="abc123", is_current=True),
            ]

            result = runner.invoke(cli, ["git", "--action", "branch"])

        assert result.exit_code == 0

    def test_git_cmd_merge_action(self, tmp_repo: Path) -> None:
        """Test git command with merge action without branch."""
        runner = CliRunner()

        with patch("zerg.commands.git_cmd.GitOps") as mock_git_cls:
            mock_git = MagicMock()
            mock_git_cls.return_value = mock_git
            mock_git.current_branch.return_value = "main"

            result = runner.invoke(cli, ["git", "--action", "merge"])

        # Should exit 1 (no branch specified)
        assert result.exit_code == 1

    def test_git_cmd_sync_action(self, tmp_repo: Path) -> None:
        """Test git command with sync action."""
        runner = CliRunner()

        with patch("zerg.commands.git_cmd.GitOps") as mock_git_cls:
            mock_git = MagicMock()
            mock_git_cls.return_value = mock_git
            mock_git.current_branch.return_value = "main"

            result = runner.invoke(cli, ["git", "--action", "sync"])

        assert result.exit_code == 0

    def test_git_cmd_history_action(self, tmp_repo: Path) -> None:
        """Test git command with history action."""
        runner = CliRunner()

        with patch("zerg.commands.git_cmd.GitOps") as mock_git_cls:
            mock_git = MagicMock()
            mock_git_cls.return_value = mock_git
            mock_git.current_branch.return_value = "main"
            log_result = MagicMock()
            log_result.stdout = "abc123 test commit"
            mock_git._run.return_value = log_result

            result = runner.invoke(cli, ["git", "--action", "history"])

        assert result.exit_code == 0

    def test_git_cmd_finish_action(self, tmp_repo: Path) -> None:
        """Test git command with finish action."""
        runner = CliRunner()

        with patch("zerg.commands.git_cmd.GitOps") as mock_git_cls:
            mock_git = MagicMock()
            mock_git_cls.return_value = mock_git
            mock_git.current_branch.return_value = "main"  # On base, nothing to finish

            result = runner.invoke(cli, ["git", "--action", "finish"])

        assert result.exit_code == 0

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

    def test_git_cmd_general_exception(self, tmp_repo: Path) -> None:
        """Test git command with general exception."""
        runner = CliRunner()

        with patch("zerg.commands.git_cmd.GitOps") as mock_git_cls:
            mock_git_cls.side_effect = Exception("Something went wrong")

            result = runner.invoke(cli, ["git", "--action", "commit"])

        assert result.exit_code == 1

    def test_git_cmd_unknown_action(self, tmp_repo: Path) -> None:
        """Test git command with unknown action (shouldn't happen due to click.Choice)."""
        runner = CliRunner()

        # Click validates choices, so invalid action should fail before reaching handler
        result = runner.invoke(cli, ["git", "--action", "invalid"])
        assert result.exit_code != 0

    def test_git_cmd_direct_invoke_unknown_action(self, tmp_repo: Path) -> None:
        """Test git_cmd with unknown action bypassing Click validation.

        This covers the defensive 'else' branch that Click normally prevents.
        """
        # Create a Click context to run the command in
        ctx = click.Context(git_cmd)

        # Bypass Click validation by invoking the function directly with context
        with (
            ctx.scope(),
            patch("zerg.commands.git_cmd.GitOps") as mock_git_cls,
        ):
            mock_git = MagicMock()
            mock_git_cls.return_value = mock_git
            mock_git.current_branch.return_value = "main"

            # Invoke function directly with invalid action
            with pytest.raises(SystemExit) as excinfo:
                ctx.invoke(
                    git_cmd,
                    action="unknown_action",  # Invalid action bypassing Click
                    push=False,
                    base="main",
                    name=None,
                    branch=None,
                    strategy="merge",
                    since=None,
                )

            assert excinfo.value.code == 1


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

    def test_patterns_are_valid_regex(self) -> None:
        """Test that all patterns are valid regex."""
        import re

        for _commit_type, patterns in COMMIT_TYPE_PATTERNS.items():
            for pattern in patterns:
                # Should not raise
                re.compile(pattern, re.IGNORECASE)
