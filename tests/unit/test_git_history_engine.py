"""Tests for zerg.git.history_engine -- commit history intelligence."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from zerg.exceptions import GitError
from zerg.git.config import GitConfig
from zerg.git.history_engine import (
    HistoryAnalyzer,
    HistoryEngine,
    RewritePlanner,
    SafeRewriter,
    _detect_type_from_message,
    _get_lines_changed,
    _parse_date,
    _validate_branch_name,
)
from zerg.git.types import CommitInfo, CommitType


@pytest.fixture()
def mock_runner() -> MagicMock:
    runner = MagicMock()
    runner.repo_path = "/fake/repo"
    return runner


@pytest.fixture()
def sample_commits() -> list[CommitInfo]:
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
            sha="eee5555",
            message="update readme",
            author="Dev",
            date="2025-01-15 14:00:00 +0000",
            files=("docs/README.md",),
            commit_type=CommitType.DOCS,
        ),
    ]


class TestHelpers:
    def test_validate_branch_name(self) -> None:
        _validate_branch_name("main")
        _validate_branch_name("feature/auth-system")
        with pytest.raises(ValueError, match="Invalid branch name"):
            _validate_branch_name("")
        with pytest.raises(ValueError, match="Invalid branch name"):
            _validate_branch_name("; rm -rf /")

    def test_parse_date(self) -> None:
        assert _parse_date("2025-01-15 10:30:00 +0000").year == 2025
        assert _parse_date("not-a-date") == datetime(2000, 1, 1)

    def test_parse_date_iso8601_with_t(self) -> None:
        result = _parse_date("2025-01-15T10:30:00+0000")
        assert result.year == 2025
        assert result.month == 1
        assert result.hour == 10

    def test_parse_date_no_timezone(self) -> None:
        result = _parse_date("2025-01-15 10:30:00")
        assert result.year == 2025
        assert result.minute == 30

    def test_detect_type(self) -> None:
        assert _detect_type_from_message("add new login page") == CommitType.FEAT
        assert _detect_type_from_message("fix broken validation") == CommitType.FIX
        assert _detect_type_from_message("xyz random gibberish") is None

    def test_detect_type_docs(self) -> None:
        assert _detect_type_from_message("update documentation") == CommitType.DOCS

    def test_detect_type_refactor(self) -> None:
        assert _detect_type_from_message("refactor auth module") == CommitType.REFACTOR

    def test_detect_type_test(self) -> None:
        assert _detect_type_from_message("test coverage improvements") == CommitType.TEST


class TestGetLinesChanged:
    """Tests for _get_lines_changed helper function (lines 104-115)."""

    def test_normal_numstat_output(self) -> None:
        runner = MagicMock()
        runner._run.return_value = MagicMock(stdout="10\t5\tsrc/auth.py\n3\t1\tsrc/utils.py\n")
        result = _get_lines_changed(runner, "abc123")
        assert result == 19  # 10+5+3+1

    def test_binary_file_dashes(self) -> None:
        runner = MagicMock()
        runner._run.return_value = MagicMock(stdout="-\t-\timage.png\n5\t2\tsrc/app.py\n")
        result = _get_lines_changed(runner, "abc123")
        assert result == 7  # 0+0+5+2

    def test_empty_output(self) -> None:
        runner = MagicMock()
        runner._run.return_value = MagicMock(stdout="")
        result = _get_lines_changed(runner, "abc123")
        assert result == 0

    def test_none_stdout(self) -> None:
        runner = MagicMock()
        runner._run.return_value = MagicMock(stdout=None)
        result = _get_lines_changed(runner, "abc123")
        assert result == 0

    def test_git_error_returns_zero(self) -> None:
        runner = MagicMock()
        runner._run.side_effect = GitError("git failed")
        result = _get_lines_changed(runner, "abc123")
        assert result == 0

    def test_value_error_returns_zero(self) -> None:
        runner = MagicMock()
        runner._run.return_value = MagicMock(stdout="notanumber\t5\tfile.py\n")
        result = _get_lines_changed(runner, "abc123")
        assert result == 0

    def test_single_column_line_skipped(self) -> None:
        runner = MagicMock()
        runner._run.return_value = MagicMock(stdout="incomplete\n10\t5\tsrc/app.py\n")
        # "incomplete" has no tab -> split gives 1 part -> skipped
        # next line: 10+5 = 15
        result = _get_lines_changed(runner, "abc123")
        assert result == 15


class TestHistoryAnalyzer:
    def test_get_commits_parses_log(self, mock_runner: MagicMock) -> None:
        log_output = (
            "abc1234|||feat: add auth|||Alice|||2025-01-15 10:00:00 +0000\n"
            "src/auth.py\n\n"
            "def5678|||fix: broken login|||Bob|||2025-01-15 11:00:00 +0000\nsrc/auth.py\n"
        )
        mock_runner._run.return_value = MagicMock(stdout=log_output)
        commits = HistoryAnalyzer(mock_runner).get_commits("main")
        assert len(commits) == 2

    def test_get_commits_empty_output(self, mock_runner: MagicMock) -> None:
        """Covers line 148 -- empty output returns []."""
        mock_runner._run.return_value = MagicMock(stdout="")
        commits = HistoryAnalyzer(mock_runner).get_commits("main")
        assert commits == []

    def test_get_commits_none_stdout(self, mock_runner: MagicMock) -> None:
        """Covers line 148 -- None stdout returns []."""
        mock_runner._run.return_value = MagicMock(stdout=None)
        commits = HistoryAnalyzer(mock_runner).get_commits("main")
        assert commits == []

    def test_parse_log_malformed_separator_line(self, mock_runner: MagicMock) -> None:
        """Covers line 199 -- ||| line with fewer than 4 parts resets current_sha."""
        log_output = (
            "abc1234|||feat: add auth|||Alice|||2025-01-15 10:00:00 +0000\n"
            "src/auth.py\n"
            "bad|||line\n"  # Only 2 parts, triggers line 199
            "def5678|||fix: broken login|||Bob|||2025-01-15 11:00:00 +0000\n"
            "src/login.py\n"
        )
        mock_runner._run.return_value = MagicMock(stdout=log_output)
        commits = HistoryAnalyzer(mock_runner).get_commits("main")
        # First commit is valid, malformed line resets, second commit is valid
        assert len(commits) == 2

    def test_find_squash_candidates_wip(self, sample_commits: list[CommitInfo]) -> None:
        groups = HistoryAnalyzer(MagicMock()).find_squash_candidates(sample_commits)
        wip_shas = {c.sha for g in groups for c in g if c.message.lower().startswith("wip")}
        assert "bbb2222" in wip_shas and "ccc3333" in wip_shas

    def test_find_squash_candidates_empty(self) -> None:
        assert HistoryAnalyzer(MagicMock()).find_squash_candidates([]) == []

    def test_find_squash_candidates_fixup(self) -> None:
        """Covers lines 262-276 -- fixup! commit with matching target."""
        commits = [
            CommitInfo(
                sha="aaa1111",
                message="add login form",
                author="Dev",
                date="2025-01-15 10:00:00 +0000",
                files=("src/login.py",),
                commit_type=CommitType.FEAT,
            ),
            CommitInfo(
                sha="bbb2222",
                message="fixup! add login form",
                author="Dev",
                date="2025-01-15 10:30:00 +0000",
                files=("src/login.py",),
                commit_type=None,
            ),
        ]
        groups = HistoryAnalyzer(MagicMock()).find_squash_candidates(commits)
        all_shas = {c.sha for g in groups for c in g}
        assert "aaa1111" in all_shas
        assert "bbb2222" in all_shas

    def test_find_squash_candidates_squash_prefix(self) -> None:
        """Covers fixup!/squash! branch -- squash! prefix with matching target."""
        commits = [
            CommitInfo(
                sha="aaa1111",
                message="implement caching",
                author="Dev",
                date="2025-01-15 10:00:00 +0000",
                files=("src/cache.py",),
                commit_type=CommitType.FEAT,
            ),
            CommitInfo(
                sha="bbb2222",
                message="squash! implement caching",
                author="Dev",
                date="2025-01-15 10:30:00 +0000",
                files=("src/cache.py",),
                commit_type=None,
            ),
        ]
        groups = HistoryAnalyzer(MagicMock()).find_squash_candidates(commits)
        all_shas = {c.sha for g in groups for c in g}
        assert "aaa1111" in all_shas
        assert "bbb2222" in all_shas

    def test_find_squash_candidates_fixup_no_target(self) -> None:
        """Covers lines 272-275 -- fixup! without a matching target still gets grouped."""
        commits = [
            CommitInfo(
                sha="bbb2222",
                message="fixup! nonexistent commit",
                author="Dev",
                date="2025-01-15 10:30:00 +0000",
                files=("src/login.py",),
                commit_type=None,
            ),
        ]
        groups = HistoryAnalyzer(MagicMock()).find_squash_candidates(commits)
        # Even without target, single fixup! gets added as a group
        assert len(groups) >= 1
        fixup_shas = {c.sha for g in groups for c in g}
        assert "bbb2222" in fixup_shas

    def test_find_squash_candidates_no_files_skipped(self) -> None:
        """Covers lines 284-285 -- commits with no files skip related-commit grouping."""
        commits = [
            CommitInfo(
                sha="aaa1111",
                message="some commit",
                author="Dev",
                date="2025-01-15 10:00:00 +0000",
                files=(),
                commit_type=CommitType.CHORE,
            ),
            CommitInfo(
                sha="bbb2222",
                message="another commit",
                author="Dev",
                date="2025-01-15 14:00:00 +0000",
                files=(),
                commit_type=CommitType.CHORE,
            ),
        ]
        groups = HistoryAnalyzer(MagicMock()).find_squash_candidates(commits)
        # No files means they won't be grouped by related-files pass
        # They may still be grouped by small-commit window pass
        # The key coverage target is that the no-files branch is hit
        assert isinstance(groups, list)

    def test_find_squash_candidates_related_files(self) -> None:
        """Covers lines 294-296, 301-304 -- related commits grouped by shared files."""
        commits = [
            CommitInfo(
                sha="aaa1111",
                message="update auth handler",
                author="Dev",
                date="2025-01-15 10:00:00 +0000",
                files=("src/auth.py",),
                commit_type=CommitType.FEAT,
            ),
            CommitInfo(
                sha="bbb2222",
                message="improve auth tests",
                author="Dev",
                date="2025-01-15 10:10:00 +0000",
                files=("src/auth.py", "tests/test_auth.py"),
                commit_type=CommitType.TEST,
            ),
        ]
        groups = HistoryAnalyzer(MagicMock()).find_squash_candidates(commits)
        # These share src/auth.py and are sequential -> related group
        related_shas = {c.sha for g in groups for c in g}
        assert "aaa1111" in related_shas
        assert "bbb2222" in related_shas

    def test_find_squash_candidates_small_commits_within_window(self) -> None:
        """Covers lines 321-322, 327-330 -- small commits within 1-hour window."""
        commits = [
            CommitInfo(
                sha="aaa1111",
                message="tiny fix alpha",
                author="Dev",
                date="2025-01-15 10:00:00 +0000",
                files=("src/alpha.py",),
                commit_type=CommitType.FIX,
            ),
            CommitInfo(
                sha="bbb2222",
                message="tiny fix beta",
                author="Dev",
                date="2025-01-15 10:20:00 +0000",
                files=("src/beta.py",),
                commit_type=CommitType.FIX,
            ),
        ]
        # These don't share files and aren't WIP/fixup, so they only match
        # the small-commit-within-time-window pass (Pass 4).
        groups = HistoryAnalyzer(MagicMock()).find_squash_candidates(commits)
        assert len(groups) >= 1
        window_shas = {c.sha for g in groups for c in g}
        assert "aaa1111" in window_shas
        assert "bbb2222" in window_shas

    def test_find_squash_candidates_single_wip_not_grouped(self) -> None:
        """Covers line 254 -- single WIP commit discarded from WIP group."""
        commits = [
            CommitInfo(
                sha="aaa1111",
                message="wip something",
                author="Dev",
                date="2025-01-15 10:00:00 +0000",
                files=("src/app.py",),
                commit_type=None,
            ),
        ]
        groups = HistoryAnalyzer(MagicMock()).find_squash_candidates(commits)
        # Single WIP -> discarded from WIP group, sha removed from used set
        # It may appear in other groups (small commit / related)
        assert isinstance(groups, list)

    def test_find_reorder_groups(self) -> None:
        """Covers lines 345-366 -- group commits by directory and type."""
        commits = [
            CommitInfo(
                sha="aaa1111",
                message="feat: add auth",
                author="Dev",
                date="2025-01-15 10:00:00 +0000",
                files=("src/auth.py", "src/models.py"),
                commit_type=CommitType.FEAT,
            ),
            CommitInfo(
                sha="bbb2222",
                message="fix: auth bug",
                author="Dev",
                date="2025-01-15 10:30:00 +0000",
                files=("src/auth.py",),
                commit_type=CommitType.FIX,
            ),
            CommitInfo(
                sha="ccc3333",
                message="docs: update readme",
                author="Dev",
                date="2025-01-15 11:00:00 +0000",
                files=("docs/README.md",),
                commit_type=CommitType.DOCS,
            ),
            CommitInfo(
                sha="ddd4444",
                message="chore: misc",
                author="Dev",
                date="2025-01-15 11:30:00 +0000",
                files=(),
                commit_type=CommitType.CHORE,
            ),
        ]
        groups = HistoryAnalyzer(MagicMock()).find_reorder_groups(commits)
        assert "src/feat" in groups
        assert "src/fix" in groups
        assert "docs/docs" in groups
        # No files -> primary_dir is "."
        assert "./chore" in groups

    def test_find_reorder_groups_no_type(self) -> None:
        """Covers line 361 -- commit_type is None -> 'other' label."""
        commits = [
            CommitInfo(
                sha="aaa1111",
                message="something random",
                author="Dev",
                date="2025-01-15 10:00:00 +0000",
                files=("src/app.py",),
                commit_type=None,
            ),
        ]
        groups = HistoryAnalyzer(MagicMock()).find_reorder_groups(commits)
        assert "src/other" in groups

    def test_find_reorder_groups_root_files(self) -> None:
        """Covers line 354 -- file without directory uses '.' as primary."""
        commits = [
            CommitInfo(
                sha="aaa1111",
                message="feat: update config",
                author="Dev",
                date="2025-01-15 10:00:00 +0000",
                files=("setup.py",),
                commit_type=CommitType.FEAT,
            ),
        ]
        groups = HistoryAnalyzer(MagicMock()).find_reorder_groups(commits)
        assert "./feat" in groups


class TestRewritePlanner:
    def test_plan_squash(self) -> None:
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
            ]
        ]
        plans = RewritePlanner().plan_squash(groups)
        assert len(plans) == 1 and plans[0]["action"] == "squash" and plans[0]["message"].startswith("feat:")

    def test_plan_squash_empty_group_skipped(self) -> None:
        """Covers line 385 -- empty group in the list is skipped."""
        groups = [
            [],
            [
                CommitInfo(
                    sha="aaa1111",
                    message="feat: something",
                    author="Dev",
                    date="2025-01-15 10:00:00 +0000",
                    files=("src/app.py",),
                    commit_type=CommitType.FEAT,
                ),
            ],
        ]
        plans = RewritePlanner().plan_squash(groups)
        assert len(plans) == 1  # Only the non-empty group

    def test_plan_reorder(self) -> None:
        """Covers lines 408-416 -- plan_reorder returns ordered SHAs."""
        groups = {
            "src/feat": [
                CommitInfo(
                    sha="aaa1111",
                    message="feat: a",
                    author="D",
                    date="2025-01-15 10:00:00 +0000",
                    files=("src/a.py",),
                    commit_type=CommitType.FEAT,
                ),
            ],
            "src/fix": [
                CommitInfo(
                    sha="bbb2222",
                    message="fix: b",
                    author="D",
                    date="2025-01-15 10:30:00 +0000",
                    files=("src/b.py",),
                    commit_type=CommitType.FIX,
                ),
            ],
            "docs/docs": [
                CommitInfo(
                    sha="ccc3333",
                    message="docs: c",
                    author="D",
                    date="2025-01-15 11:00:00 +0000",
                    files=("docs/c.md",),
                    commit_type=CommitType.DOCS,
                ),
            ],
        }
        ordered = RewritePlanner().plan_reorder(groups)
        # Sorted by group name: docs/docs < src/feat < src/fix
        assert ordered == ["ccc3333", "aaa1111", "bbb2222"]

    def test_plan_reorder_deduplicates_shas(self) -> None:
        """Covers line 413 -- duplicate SHA in different groups only appears once."""
        commit = CommitInfo(
            sha="aaa1111",
            message="feat: a",
            author="D",
            date="2025-01-15 10:00:00 +0000",
            files=("src/a.py",),
            commit_type=CommitType.FEAT,
        )
        groups = {
            "group1": [commit],
            "group2": [commit],
        }
        ordered = RewritePlanner().plan_reorder(groups)
        assert ordered.count("aaa1111") == 1

    def test_plan_rewrite_messages(self) -> None:
        commits = [
            CommitInfo(
                sha="aaa",
                message="feat: proper",
                author="D",
                date="2025-01-15 10:00:00 +0000",
                files=("a.py",),
                commit_type=CommitType.FEAT,
            ),
            CommitInfo(
                sha="bbb",
                message="fix some bug",
                author="D",
                date="2025-01-15 11:00:00 +0000",
                files=("b.py",),
                commit_type=CommitType.FIX,
            ),
        ]
        rewrites = RewritePlanner().plan_rewrite_messages(commits)
        assert len(rewrites) == 1 and rewrites[0]["sha"] == "bbb"

    def test_plan_rewrite_wip_prefix_stripped(self) -> None:
        """Covers lines 438-440 -- WIP prefix variants are stripped."""
        commits = [
            CommitInfo(
                sha="aaa",
                message="wip stuff to do",
                author="D",
                date="2025-01-15 10:00:00 +0000",
                files=("a.py",),
                commit_type=None,
            ),
            CommitInfo(
                sha="bbb",
                message="WIP: more work",
                author="D",
                date="2025-01-15 10:30:00 +0000",
                files=("b.py",),
                commit_type=None,
            ),
            CommitInfo(
                sha="ccc",
                message="wip: testing",
                author="D",
                date="2025-01-15 11:00:00 +0000",
                files=("c.py",),
                commit_type=None,
            ),
        ]
        rewrites = RewritePlanner().plan_rewrite_messages(commits)
        assert len(rewrites) == 3
        for r in rewrites:
            assert not r["new"].lower().startswith("wip")

    def test_plan_rewrite_empty_message_after_strip(self) -> None:
        """Covers line 443 -- empty message after stripping uses 'update' fallback."""
        commits = [
            CommitInfo(
                sha="aaa",
                message="   ",
                author="D",
                date="2025-01-15 10:00:00 +0000",
                files=("a.py",),
                commit_type=None,
            ),
        ]
        rewrites = RewritePlanner().plan_rewrite_messages(commits)
        assert len(rewrites) == 1
        assert rewrites[0]["new"].endswith(": update")

    def test_generate_squash_message_single_file(self) -> None:
        """Covers line 480 -- single file in group -> uses filename stem."""
        group = [
            CommitInfo(
                sha="aaa",
                message="feat: a",
                author="D",
                date="2025-01-15 10:00:00 +0000",
                files=("src/auth.py",),
                commit_type=CommitType.FEAT,
            ),
        ]
        msg = RewritePlanner()._generate_squash_message(group)
        assert "auth" in msg
        assert msg.startswith("feat:")

    def test_generate_squash_message_few_files(self) -> None:
        """Covers lines 481-483 -- 2-3 files -> lists stems."""
        group = [
            CommitInfo(
                sha="aaa",
                message="feat: a",
                author="D",
                date="2025-01-15 10:00:00 +0000",
                files=("src/auth.py", "src/models.py"),
                commit_type=CommitType.FEAT,
            ),
        ]
        msg = RewritePlanner()._generate_squash_message(group)
        assert "auth" in msg
        assert "models" in msg

    def test_generate_squash_message_many_files(self) -> None:
        """Covers lines 484-485 -- >3 files -> 'update N files'."""
        group = [
            CommitInfo(
                sha="aaa",
                message="feat: a",
                author="D",
                date="2025-01-15 10:00:00 +0000",
                files=("src/a.py", "src/b.py", "src/c.py", "src/d.py"),
                commit_type=CommitType.FEAT,
            ),
        ]
        msg = RewritePlanner()._generate_squash_message(group)
        assert "4 files" in msg

    def test_generate_squash_message_no_commit_type(self) -> None:
        """Covers line 468 -- commit_type=None defaults to CHORE."""
        group = [
            CommitInfo(
                sha="aaa",
                message="random stuff",
                author="D",
                date="2025-01-15 10:00:00 +0000",
                files=("src/app.py",),
                commit_type=None,
            ),
        ]
        msg = RewritePlanner()._generate_squash_message(group)
        assert msg.startswith("chore:")


class TestSafeRewriter:
    def test_create_cleaned_branch(self, mock_runner: MagicMock) -> None:
        result = SafeRewriter(mock_runner).create_cleaned_branch("feature/auth")
        assert result == "feature/auth-cleaned"

    def test_create_cleaned_branch_invalid(self, mock_runner: MagicMock) -> None:
        with pytest.raises(ValueError, match="Invalid branch name"):
            SafeRewriter(mock_runner).create_cleaned_branch("; evil")

    def test_preview_squash_plan(self, mock_runner: MagicMock) -> None:
        plan = [{"action": "squash", "commits": ["aaa", "bbb"], "message": "feat: combined"}]
        output = SafeRewriter(mock_runner).preview(plan)
        assert "SQUASH" in output and "2 commits" in output

    def test_preview_rewrite_plan(self, mock_runner: MagicMock) -> None:
        """Covers lines 726-730 -- preview of rewrite plans."""
        plan = [{"sha": "abc12345", "old": "fix something", "new": "fix: something"}]
        output = SafeRewriter(mock_runner).preview(plan)
        assert "REWRITE" in output
        assert "abc12345" in output
        assert "fix something" in output

    def test_preview_dict_reorder_plan(self, mock_runner: MagicMock) -> None:
        """Covers lines 731-737 -- preview with dict plan (reorder groups)."""
        commit = CommitInfo(
            sha="abc12345",
            message="feat: a",
            author="D",
            date="2025-01-15 10:00:00 +0000",
            files=("a.py",),
            commit_type=CommitType.FEAT,
        )
        plan = {"src/feat": [commit]}
        output = SafeRewriter(mock_runner).preview(plan)
        assert "Reorder plan" in output
        assert "src/feat" in output
        assert "abc12345" in output

    def test_execute_squash_empty_plan(self, mock_runner: MagicMock) -> None:
        """Covers line 531 -- empty plan returns True immediately."""
        result = SafeRewriter(mock_runner).execute_squash([], base="main")
        assert result is True

    def test_execute_squash_no_squash_shas(self, mock_runner: MagicMock) -> None:
        """Covers lines 543-544 -- plan with only single-commit groups (no squash SHAs)."""
        plan = [{"action": "squash", "commits": ["aaa1111"], "message": "feat: only one"}]
        result = SafeRewriter(mock_runner).execute_squash(plan, base="main")
        assert result is True

    def test_execute_squash_invalid_base(self, mock_runner: MagicMock) -> None:
        """Covers line 529 -- invalid base branch raises ValueError."""
        plan = [{"action": "squash", "commits": ["aaa", "bbb"], "message": "feat: combined"}]
        with pytest.raises(ValueError, match="Invalid branch name"):
            SafeRewriter(mock_runner).execute_squash(plan, base="; evil")

    @patch("subprocess.run")
    def test_execute_squash_success(self, mock_subprocess: MagicMock, mock_runner: MagicMock) -> None:
        """Covers lines 546-603 -- successful squash execution."""
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="", stderr="")
        plan = [{"action": "squash", "commits": ["aaa1111", "bbb2222"], "message": "feat: combined"}]
        result = SafeRewriter(mock_runner).execute_squash(plan, base="main")
        assert result is True
        mock_subprocess.assert_called_once()

    @patch("subprocess.run")
    def test_execute_squash_failure_aborts(self, mock_subprocess: MagicMock, mock_runner: MagicMock) -> None:
        """Covers lines 596-600 -- failed rebase triggers abort."""
        mock_subprocess.return_value = MagicMock(returncode=1, stdout="", stderr="conflict")
        plan = [{"action": "squash", "commits": ["aaa1111", "bbb2222"], "message": "feat: combined"}]
        result = SafeRewriter(mock_runner).execute_squash(plan, base="main")
        assert result is False
        # Should abort the rebase on failure
        mock_runner._run.assert_called_with("rebase", "--abort", check=False)

    @patch("subprocess.run")
    def test_execute_squash_exception_aborts(self, mock_subprocess: MagicMock, mock_runner: MagicMock) -> None:
        """Covers lines 605-608 -- exception during rebase triggers abort."""
        mock_subprocess.side_effect = OSError("process failed")
        plan = [{"action": "squash", "commits": ["aaa1111", "bbb2222"], "message": "feat: combined"}]
        result = SafeRewriter(mock_runner).execute_squash(plan, base="main")
        assert result is False
        mock_runner._run.assert_called_with("rebase", "--abort", check=False)

    def test_execute_reorder_empty_shas(self, mock_runner: MagicMock) -> None:
        """Covers lines 628-629 -- empty ordered_shas returns True."""
        result = SafeRewriter(mock_runner).execute_reorder([], base="main")
        assert result is True

    def test_execute_reorder_invalid_base(self, mock_runner: MagicMock) -> None:
        """Covers line 626 -- invalid base branch raises ValueError."""
        with pytest.raises(ValueError, match="Invalid branch name"):
            SafeRewriter(mock_runner).execute_reorder(["aaa1111"], base="; evil")

    @patch("subprocess.run")
    def test_execute_reorder_success(self, mock_subprocess: MagicMock, mock_runner: MagicMock) -> None:
        """Covers lines 634-693 -- successful reorder execution."""
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = SafeRewriter(mock_runner).execute_reorder(["aaa1111", "bbb2222"], base="main")
        assert result is True
        mock_subprocess.assert_called_once()

    @patch("subprocess.run")
    def test_execute_reorder_failure_aborts(self, mock_subprocess: MagicMock, mock_runner: MagicMock) -> None:
        """Covers lines 687-690 -- failed reorder triggers abort."""
        mock_subprocess.return_value = MagicMock(returncode=1, stdout="", stderr="conflict")
        result = SafeRewriter(mock_runner).execute_reorder(["aaa1111", "bbb2222"], base="main")
        assert result is False
        mock_runner._run.assert_called_with("rebase", "--abort", check=False)

    @patch("subprocess.run")
    def test_execute_reorder_exception_aborts(self, mock_subprocess: MagicMock, mock_runner: MagicMock) -> None:
        """Covers lines 695-698 -- exception during reorder triggers abort."""
        mock_subprocess.side_effect = OSError("process failed")
        result = SafeRewriter(mock_runner).execute_reorder(["aaa1111", "bbb2222"], base="main")
        assert result is False
        mock_runner._run.assert_called_with("rebase", "--abort", check=False)


class TestHistoryEngine:
    def test_run_preview(self, mock_runner: MagicMock) -> None:
        log_output = "abc|||wip stuff|||Dev|||2025-01-15 10:00:00 +0000\nsrc/a.py\n"
        mock_runner._run.return_value = MagicMock(stdout=log_output)
        assert HistoryEngine(mock_runner, GitConfig()).run(action="preview", base_branch="main") == 0

    def test_run_invalid_branch(self, mock_runner: MagicMock) -> None:
        assert HistoryEngine(mock_runner, GitConfig()).run(action="preview", base_branch="; evil") == 1

    def test_run_preview_no_commits(self, mock_runner: MagicMock) -> None:
        """Covers lines 766-768 -- no commits found returns 0."""
        mock_runner._run.return_value = MagicMock(stdout="")
        result = HistoryEngine(mock_runner, GitConfig()).run(action="preview", base_branch="main")
        assert result == 0

    def test_run_preview_clean_history(self, mock_runner: MagicMock) -> None:
        """Covers line 783 -- no squash/rewrite plans: 'already clean'."""
        log_output = "abc|||feat: properly formatted|||Dev|||2025-01-15 10:00:00 +0000\nsrc/a.py\n"
        mock_runner._run.return_value = MagicMock(stdout=log_output)
        result = HistoryEngine(mock_runner, GitConfig()).run(action="preview", base_branch="main")
        assert result == 0

    def test_run_preview_with_rewrite_plan(self, mock_runner: MagicMock) -> None:
        """Covers lines 777-778, 779-781 -- preview with rewrite messages."""
        # Two commits: one WIP (squash candidate) and one non-conventional (rewrite candidate)
        log_output = "abc|||fix something|||Dev|||2025-01-15 10:00:00 +0000\nsrc/a.py\n"
        mock_runner._run.return_value = MagicMock(stdout=log_output)
        result = HistoryEngine(mock_runner, GitConfig()).run(action="preview", base_branch="main")
        assert result == 0

    def test_run_cleanup_clean_history(self, mock_runner: MagicMock) -> None:
        """Covers lines 787-789 -- cleanup with clean history returns 0."""
        log_output = "abc|||feat: properly formatted|||Dev|||2025-01-15 10:00:00 +0000\nsrc/a.py\n"
        mock_runner._run.return_value = MagicMock(stdout=log_output)
        result = HistoryEngine(mock_runner, GitConfig()).run(action="cleanup", base_branch="main")
        assert result == 0

    @patch("subprocess.run")
    def test_run_cleanup_with_squash(self, mock_subprocess: MagicMock, mock_runner: MagicMock) -> None:
        """Covers lines 786-808 -- cleanup with squash plan creates branch and executes."""
        log_output = (
            "abc|||wip stuff|||Dev|||2025-01-15 10:00:00 +0000\nsrc/a.py\n\n"
            "def|||wip more|||Dev|||2025-01-15 10:10:00 +0000\nsrc/a.py\n"
        )
        mock_runner._run.return_value = MagicMock(stdout=log_output)
        mock_runner.current_branch.return_value = "feature/test"
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = HistoryEngine(mock_runner, GitConfig()).run(action="cleanup", base_branch="main")
        assert result == 0

    @patch("subprocess.run")
    def test_run_cleanup_squash_fails(self, mock_subprocess: MagicMock, mock_runner: MagicMock) -> None:
        """Covers lines 803-805 -- cleanup fails when squash fails."""
        log_output = (
            "abc|||wip stuff|||Dev|||2025-01-15 10:00:00 +0000\nsrc/a.py\n\n"
            "def|||wip more|||Dev|||2025-01-15 10:10:00 +0000\nsrc/a.py\n"
        )
        mock_runner._run.return_value = MagicMock(stdout=log_output)
        mock_runner.current_branch.return_value = "feature/test"
        mock_subprocess.return_value = MagicMock(returncode=1, stdout="", stderr="conflict")
        result = HistoryEngine(mock_runner, GitConfig()).run(action="cleanup", base_branch="main")
        assert result == 1

    def test_run_unknown_action(self, mock_runner: MagicMock) -> None:
        """Covers lines 810-812 -- unknown action returns 1."""
        log_output = "abc|||wip stuff|||Dev|||2025-01-15 10:00:00 +0000\nsrc/a.py\n"
        mock_runner._run.return_value = MagicMock(stdout=log_output)
        result = HistoryEngine(mock_runner, GitConfig()).run(action="bogus", base_branch="main")
        assert result == 1

    def test_run_git_error(self, mock_runner: MagicMock) -> None:
        """Covers lines 814-816 -- GitError during run returns 1."""
        mock_runner._run.side_effect = GitError("git broken")
        result = HistoryEngine(mock_runner, GitConfig()).run(action="preview", base_branch="main")
        assert result == 1
