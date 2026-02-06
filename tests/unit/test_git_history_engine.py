"""Tests for zerg.git.history_engine -- commit history intelligence."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

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

    def test_detect_type(self) -> None:
        assert _detect_type_from_message("add new login page") == CommitType.FEAT
        assert _detect_type_from_message("fix broken validation") == CommitType.FIX
        assert _detect_type_from_message("xyz random gibberish") is None


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

    def test_find_squash_candidates_wip(self, sample_commits: list[CommitInfo]) -> None:
        groups = HistoryAnalyzer(MagicMock()).find_squash_candidates(sample_commits)
        wip_shas = {c.sha for g in groups for c in g if c.message.lower().startswith("wip")}
        assert "bbb2222" in wip_shas and "ccc3333" in wip_shas

    def test_find_squash_candidates_empty(self) -> None:
        assert HistoryAnalyzer(MagicMock()).find_squash_candidates([]) == []


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


class TestHistoryEngine:
    def test_run_preview(self, mock_runner: MagicMock) -> None:
        log_output = "abc|||wip stuff|||Dev|||2025-01-15 10:00:00 +0000\nsrc/a.py\n"
        mock_runner._run.return_value = MagicMock(stdout=log_output)
        assert HistoryEngine(mock_runner, GitConfig()).run(action="preview", base_branch="main") == 0

    def test_run_invalid_branch(self, mock_runner: MagicMock) -> None:
        assert HistoryEngine(mock_runner, GitConfig()).run(action="preview", base_branch="; evil") == 1
