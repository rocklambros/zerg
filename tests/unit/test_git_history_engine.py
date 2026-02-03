"""Tests for zerg.git.history_engine -- commit history intelligence."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from zerg.git.config import GitConfig
from zerg.git.history_engine import (
    HistoryAnalyzer,
    HistoryEngine,
    RewritePlanner,
    SafeRewriter,
    _detect_type_from_message,
    _parse_date,
    _validate_branch_name,
)
from zerg.git.types import CommitInfo, CommitType

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_runner() -> MagicMock:
    """Create a mock GitRunner with repo_path."""
    runner = MagicMock()
    runner.repo_path = "/fake/repo"
    return runner


@pytest.fixture()
def sample_commits() -> list[CommitInfo]:
    """Create a list of sample commits for testing."""
    return [
        CommitInfo(
            sha="aaa1111",
            message="feat: add user auth",
            author="Dev",
            date="2025-01-15 10:00:00 +0000",
            files=("src/auth.py", "src/models.py"),
            commit_type=CommitType.FEAT,
        ),
        CommitInfo(
            sha="bbb2222",
            message="wip trying stuff",
            author="Dev",
            date="2025-01-15 10:30:00 +0000",
            files=("src/auth.py",),
            commit_type=None,
        ),
        CommitInfo(
            sha="ccc3333",
            message="WIP more changes",
            author="Dev",
            date="2025-01-15 10:45:00 +0000",
            files=("src/utils.py",),
            commit_type=None,
        ),
        CommitInfo(
            sha="ddd4444",
            message="fixup! feat: add user auth",
            author="Dev",
            date="2025-01-15 11:00:00 +0000",
            files=("src/auth.py",),
            commit_type=CommitType.FIX,
        ),
        CommitInfo(
            sha="eee5555",
            message="update readme",
            author="Dev",
            date="2025-01-15 14:00:00 +0000",
            files=("docs/README.md",),
            commit_type=CommitType.DOCS,
        ),
    ]


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHelpers:
    """Tests for module-level helper functions."""

    def test_validate_branch_name_valid(self) -> None:
        _validate_branch_name("main")
        _validate_branch_name("feature/auth-system")
        _validate_branch_name("release/v1.2.3")

    def test_validate_branch_name_invalid(self) -> None:
        with pytest.raises(ValueError, match="Invalid branch name"):
            _validate_branch_name("")

        with pytest.raises(ValueError, match="Invalid branch name"):
            _validate_branch_name("../escape")

        with pytest.raises(ValueError, match="Invalid branch name"):
            _validate_branch_name("; rm -rf /")

    def test_parse_date_iso(self) -> None:
        result = _parse_date("2025-01-15 10:30:00 +0000")
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15

    def test_parse_date_fallback(self) -> None:
        result = _parse_date("not-a-date")
        assert result == datetime(2000, 1, 1)

    def test_detect_type_feat(self) -> None:
        assert _detect_type_from_message("add new login page") == CommitType.FEAT

    def test_detect_type_fix(self) -> None:
        assert _detect_type_from_message("fix broken validation") == CommitType.FIX

    def test_detect_type_none(self) -> None:
        assert _detect_type_from_message("xyz random gibberish") is None


# ---------------------------------------------------------------------------
# HistoryAnalyzer tests
# ---------------------------------------------------------------------------


class TestHistoryAnalyzer:
    """Tests for HistoryAnalyzer."""

    def test_get_commits_parses_log(self, mock_runner: MagicMock) -> None:
        """get_commits should parse git log output into CommitInfo objects."""
        log_output = (
            "abc1234|||feat: add auth|||Alice|||2025-01-15 10:00:00 +0000\n"
            "src/auth.py\n"
            "src/models.py\n"
            "\n"
            "def5678|||fix: broken login|||Bob|||2025-01-15 11:00:00 +0000\n"
            "src/auth.py\n"
        )
        mock_runner._run.return_value = MagicMock(stdout=log_output)

        analyzer = HistoryAnalyzer(mock_runner)
        commits = analyzer.get_commits("main")

        assert len(commits) == 2
        # Oldest first (reversed from git log)
        assert commits[0].sha == "def5678"
        assert commits[0].message == "fix: broken login"
        assert commits[0].files == ("src/auth.py",)
        assert commits[1].sha == "abc1234"
        assert commits[1].files == ("src/auth.py", "src/models.py")

    def test_get_commits_empty(self, mock_runner: MagicMock) -> None:
        """get_commits returns empty list when no commits found."""
        mock_runner._run.return_value = MagicMock(stdout="")
        analyzer = HistoryAnalyzer(mock_runner)
        assert analyzer.get_commits("main") == []

    def test_get_commits_validates_branch(self, mock_runner: MagicMock) -> None:
        """get_commits rejects invalid branch names."""
        analyzer = HistoryAnalyzer(mock_runner)
        with pytest.raises(ValueError, match="Invalid branch name"):
            analyzer.get_commits("; rm -rf /")

    def test_find_squash_candidates_wip(self, sample_commits: list[CommitInfo]) -> None:
        """find_squash_candidates groups WIP commits together."""
        analyzer = HistoryAnalyzer(MagicMock())
        groups = analyzer.find_squash_candidates(sample_commits)

        # Should find at least one WIP group
        wip_groups = [g for g in groups if any(c.message.lower().startswith("wip") for c in g)]
        assert len(wip_groups) >= 1
        wip_shas = {c.sha for g in wip_groups for c in g}
        assert "bbb2222" in wip_shas
        assert "ccc3333" in wip_shas

    def test_find_squash_candidates_fixup(self) -> None:
        """find_squash_candidates pairs fixup! commits with targets."""
        commits = [
            CommitInfo(
                sha="aaa1111",
                message="feat: add auth",
                author="Dev",
                date="2025-01-15 10:00:00 +0000",
                files=("src/auth.py",),
                commit_type=CommitType.FEAT,
            ),
            CommitInfo(
                sha="bbb2222",
                message="fixup! feat: add auth",
                author="Dev",
                date="2025-01-15 10:30:00 +0000",
                files=("src/auth.py",),
                commit_type=CommitType.FIX,
            ),
        ]
        analyzer = HistoryAnalyzer(MagicMock())
        groups = analyzer.find_squash_candidates(commits)

        fixup_groups = [g for g in groups if any("fixup!" in c.message for c in g)]
        assert len(fixup_groups) >= 1
        assert len(fixup_groups[0]) == 2

    def test_find_squash_candidates_related_files(self) -> None:
        """find_squash_candidates groups commits touching same files."""
        commits = [
            CommitInfo(
                sha="aaa1111",
                message="feat: step 1",
                author="Dev",
                date="2025-01-15 10:00:00 +0000",
                files=("src/core.py", "src/utils.py"),
                commit_type=CommitType.FEAT,
            ),
            CommitInfo(
                sha="bbb2222",
                message="feat: step 2",
                author="Dev",
                date="2025-01-15 10:30:00 +0000",
                files=("src/core.py",),
                commit_type=CommitType.FEAT,
            ),
        ]
        analyzer = HistoryAnalyzer(MagicMock())
        groups = analyzer.find_squash_candidates(commits)

        # These share src/core.py so they should be grouped
        assert len(groups) >= 1
        related = [g for g in groups if len(g) == 2]
        assert len(related) >= 1

    def test_find_reorder_groups_by_directory(self, sample_commits: list[CommitInfo]) -> None:
        """find_reorder_groups groups commits by primary directory."""
        analyzer = HistoryAnalyzer(MagicMock())
        groups = analyzer.find_reorder_groups(sample_commits)

        # Should have groups for 'src' and 'docs' directories
        group_prefixes = {k.split("/")[0] for k in groups}
        assert "src" in group_prefixes
        assert "docs" in group_prefixes

    def test_find_squash_candidates_empty(self) -> None:
        """find_squash_candidates returns empty for empty input."""
        analyzer = HistoryAnalyzer(MagicMock())
        assert analyzer.find_squash_candidates([]) == []


# ---------------------------------------------------------------------------
# RewritePlanner tests
# ---------------------------------------------------------------------------


class TestRewritePlanner:
    """Tests for RewritePlanner."""

    def test_plan_squash_generates_messages(self) -> None:
        """plan_squash generates conventional commit messages."""
        groups = [
            [
                CommitInfo(
                    sha="aaa1111",
                    message="feat: add login",
                    author="Dev",
                    date="2025-01-15 10:00:00 +0000",
                    files=("src/auth.py",),
                    commit_type=CommitType.FEAT,
                ),
                CommitInfo(
                    sha="bbb2222",
                    message="wip login fixes",
                    author="Dev",
                    date="2025-01-15 10:30:00 +0000",
                    files=("src/auth.py",),
                    commit_type=None,
                ),
            ],
        ]
        planner = RewritePlanner()
        plans = planner.plan_squash(groups)

        assert len(plans) == 1
        assert plans[0]["action"] == "squash"
        assert plans[0]["commits"] == ["aaa1111", "bbb2222"]
        # Message should use conventional format
        assert plans[0]["message"].startswith("feat:")

    def test_plan_reorder_returns_ordered_shas(self) -> None:
        """plan_reorder returns SHAs ordered by group name."""
        groups = {
            "src/feat": [
                CommitInfo(
                    sha="aaa1111",
                    message="feat: add",
                    author="Dev",
                    date="2025-01-15 10:00:00 +0000",
                    files=("src/a.py",),
                    commit_type=CommitType.FEAT,
                ),
            ],
            "docs/docs": [
                CommitInfo(
                    sha="bbb2222",
                    message="docs: update",
                    author="Dev",
                    date="2025-01-15 11:00:00 +0000",
                    files=("docs/README.md",),
                    commit_type=CommitType.DOCS,
                ),
            ],
        }
        planner = RewritePlanner()
        ordered = planner.plan_reorder(groups)

        assert len(ordered) == 2
        # 'docs/docs' sorts before 'src/feat'
        assert ordered[0] == "bbb2222"
        assert ordered[1] == "aaa1111"

    def test_plan_rewrite_messages_detects_non_conventional(self) -> None:
        """plan_rewrite_messages flags non-conventional messages."""
        commits = [
            CommitInfo(
                sha="aaa1111",
                message="feat: proper message",
                author="Dev",
                date="2025-01-15 10:00:00 +0000",
                files=("src/a.py",),
                commit_type=CommitType.FEAT,
            ),
            CommitInfo(
                sha="bbb2222",
                message="fix some bug in auth",
                author="Dev",
                date="2025-01-15 11:00:00 +0000",
                files=("src/auth.py",),
                commit_type=CommitType.FIX,
            ),
        ]
        planner = RewritePlanner()
        rewrites = planner.plan_rewrite_messages(commits)

        # Only bbb2222 should be flagged (non-conventional)
        assert len(rewrites) == 1
        assert rewrites[0]["sha"] == "bbb2222"
        assert rewrites[0]["old"] == "fix some bug in auth"
        assert rewrites[0]["new"].startswith("fix:")

    def test_plan_squash_empty_groups(self) -> None:
        """plan_squash returns empty for empty input."""
        planner = RewritePlanner()
        assert planner.plan_squash([]) == []


# ---------------------------------------------------------------------------
# SafeRewriter tests
# ---------------------------------------------------------------------------


class TestSafeRewriter:
    """Tests for SafeRewriter."""

    def test_create_cleaned_branch(self, mock_runner: MagicMock) -> None:
        """create_cleaned_branch creates the -cleaned branch."""
        rewriter = SafeRewriter(mock_runner)
        result = rewriter.create_cleaned_branch("feature/auth")

        assert result == "feature/auth-cleaned"
        mock_runner._run.assert_called_once_with("checkout", "-b", "feature/auth-cleaned")

    def test_create_cleaned_branch_invalid_name(self, mock_runner: MagicMock) -> None:
        """create_cleaned_branch rejects invalid names."""
        rewriter = SafeRewriter(mock_runner)
        with pytest.raises(ValueError, match="Invalid branch name"):
            rewriter.create_cleaned_branch("; evil")

    def test_preview_squash_plan(self, mock_runner: MagicMock) -> None:
        """preview returns readable text for squash plans."""
        plan = [
            {
                "action": "squash",
                "commits": ["aaa1111", "bbb2222"],
                "message": "feat: combined",
            }
        ]
        rewriter = SafeRewriter(mock_runner)
        output = rewriter.preview(plan)

        assert "SQUASH" in output
        assert "2 commits" in output
        assert "aaa1111" in output
        assert "feat: combined" in output

    def test_preview_rewrite_plan(self, mock_runner: MagicMock) -> None:
        """preview returns readable text for rewrite plans."""
        plan = [
            {
                "sha": "aaa1111",
                "old": "wip stuff",
                "new": "chore: update stuff",
            }
        ]
        rewriter = SafeRewriter(mock_runner)
        output = rewriter.preview(plan)

        assert "REWRITE" in output
        assert "wip stuff" in output
        assert "chore: update stuff" in output

    @patch("subprocess.run")
    def test_execute_squash_calls_rebase(self, mock_subprocess: MagicMock, mock_runner: MagicMock) -> None:
        """execute_squash runs git rebase -i with GIT_SEQUENCE_EDITOR."""
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="", stderr="")

        plan = [
            {
                "action": "squash",
                "commits": ["aaa1111", "bbb2222"],
                "message": "feat: combined",
            }
        ]

        rewriter = SafeRewriter(mock_runner)
        result = rewriter.execute_squash(plan, base="main")

        assert result is True
        # Verify subprocess.run was called with rebase -i
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args
        cmd = call_args[0][0]
        assert "rebase" in cmd
        assert "-i" in cmd
        # Verify GIT_SEQUENCE_EDITOR was set in env
        env = call_args[1].get("env", {})
        assert "GIT_SEQUENCE_EDITOR" in env

    @patch("subprocess.run")
    def test_execute_squash_failure_aborts(self, mock_subprocess: MagicMock, mock_runner: MagicMock) -> None:
        """execute_squash aborts rebase on failure."""
        mock_subprocess.return_value = MagicMock(returncode=1, stdout="", stderr="conflict")

        plan = [
            {
                "action": "squash",
                "commits": ["aaa1111", "bbb2222"],
                "message": "feat: combined",
            }
        ]

        rewriter = SafeRewriter(mock_runner)
        result = rewriter.execute_squash(plan, base="main")

        assert result is False
        # Verify rebase --abort was called
        mock_runner._run.assert_called_with("rebase", "--abort", check=False)

    def test_execute_squash_empty_plan(self, mock_runner: MagicMock) -> None:
        """execute_squash returns True for empty plan."""
        rewriter = SafeRewriter(mock_runner)
        assert rewriter.execute_squash([], base="main") is True


# ---------------------------------------------------------------------------
# HistoryEngine tests
# ---------------------------------------------------------------------------


class TestHistoryEngine:
    """Tests for HistoryEngine orchestration."""

    def test_run_preview_only(self, mock_runner: MagicMock) -> None:
        """run with preview action shows plan without executing."""
        log_output = (
            "abc1234|||wip stuff|||Dev|||2025-01-15 10:00:00 +0000\n"
            "src/a.py\n"
            "\n"
            "def5678|||WIP more|||Dev|||2025-01-15 10:30:00 +0000\n"
            "src/b.py\n"
        )
        mock_runner._run.return_value = MagicMock(stdout=log_output)

        config = GitConfig()
        engine = HistoryEngine(mock_runner, config)
        result = engine.run(action="preview", base_branch="main")

        assert result == 0
        # Preview should NOT create a branch
        calls = [str(c) for c in mock_runner._run.call_args_list]
        assert not any("checkout" in c for c in calls)

    def test_run_cleanup_no_commits(self, mock_runner: MagicMock) -> None:
        """run cleanup with no commits returns success."""
        mock_runner._run.return_value = MagicMock(stdout="")

        config = GitConfig()
        engine = HistoryEngine(mock_runner, config)
        result = engine.run(action="cleanup", base_branch="main")

        assert result == 0

    @patch.object(SafeRewriter, "execute_squash", return_value=True)
    @patch.object(SafeRewriter, "create_cleaned_branch", return_value="feat-cleaned")
    def test_run_cleanup_with_squash(
        self,
        mock_create: MagicMock,
        mock_squash: MagicMock,
        mock_runner: MagicMock,
    ) -> None:
        """run cleanup creates branch and executes squash."""
        log_output = (
            "abc1234|||wip stuff|||Dev|||2025-01-15 10:00:00 +0000\n"
            "src/a.py\n"
            "\n"
            "def5678|||WIP more|||Dev|||2025-01-15 10:30:00 +0000\n"
            "src/b.py\n"
        )
        mock_runner._run.return_value = MagicMock(stdout=log_output)
        mock_runner.current_branch.return_value = "feat"

        config = GitConfig()
        engine = HistoryEngine(mock_runner, config)
        result = engine.run(action="cleanup", base_branch="main")

        assert result == 0
        mock_create.assert_called_once_with("feat")
        mock_squash.assert_called_once()

    def test_run_unknown_action(self, mock_runner: MagicMock) -> None:
        """run with unknown action returns failure."""
        mock_runner._run.return_value = MagicMock(stdout="abc|||msg|||Dev|||2025-01-15 10:00:00 +0000\nf.py\n")

        config = GitConfig()
        engine = HistoryEngine(mock_runner, config)
        result = engine.run(action="invalid", base_branch="main")

        assert result == 1

    def test_run_invalid_branch(self, mock_runner: MagicMock) -> None:
        """run with invalid branch name returns failure."""
        config = GitConfig()
        engine = HistoryEngine(mock_runner, config)
        result = engine.run(action="preview", base_branch="; evil")

        assert result == 1
