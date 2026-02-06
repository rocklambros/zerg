"""Tests for zerg.git.bisect_engine module."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.git.bisect_engine import (
    BisectEngine,
    BisectRunner,
    CommitRanker,
    RootCauseAnalyzer,
    SemanticTester,
    _detect_commit_type_from_message,
    _extract_file_hints_from_symptom,
    _sanitize_text,
)
from zerg.git.config import GitConfig
from zerg.git.types import CommitInfo, CommitType


def _make_commit(
    sha: str = "abc123",
    message: str = "feat: add feature",
    author: str = "Dev",
    date: str = "2025-01-15 10:00:00 +0000",
    files: tuple[str, ...] = ("src/main.py",),
    commit_type: CommitType | None = CommitType.FEAT,
) -> CommitInfo:
    return CommitInfo(sha=sha, message=message, author=author, date=date, files=files, commit_type=commit_type)


@pytest.fixture()
def mock_runner() -> MagicMock:
    runner = MagicMock()
    runner.repo_path = Path("/tmp/test-repo")
    runner.current_branch.return_value = "main"
    runner.current_commit.return_value = "deadbeef" * 5
    return runner


@pytest.fixture()
def ranker(mock_runner: MagicMock) -> CommitRanker:
    return CommitRanker(mock_runner)


@pytest.fixture()
def bisect_runner(mock_runner: MagicMock, ranker: CommitRanker) -> BisectRunner:
    tester = SemanticTester()
    return BisectRunner(mock_runner, ranker, tester)


class TestHelpers:
    def test_detect_commit_type(self) -> None:
        assert _detect_commit_type_from_message("feat: add login") == CommitType.FEAT
        assert _detect_commit_type_from_message("fix(auth): resolve bug") == CommitType.FIX
        assert _detect_commit_type_from_message("random message") is None

    def test_extract_file_hints(self) -> None:
        assert "src/main.py" in _extract_file_hints_from_symptom("Error in src/main.py line 42")

    def test_sanitize_text(self) -> None:
        assert "```" not in _sanitize_text("```python\ncode\n```")


class TestCommitRanker:
    def test_get_commits_in_range(self, ranker: CommitRanker, mock_runner: MagicMock) -> None:
        log_output = (
            "abc123|||feat: add feature|||Dev|||2025-01-15 10:00:00 +0000\n"
            "src/main.py\n\n"
            "def456|||fix: resolve bug|||Dev|||2025-01-16 10:00:00 +0000\nsrc/bug.py\n"
        )
        mock_runner._run.return_value = MagicMock(stdout=log_output)
        commits = ranker.get_commits_in_range("good", "bad")
        assert len(commits) == 2
        assert commits[0].sha == "abc123"

    def test_rank_scores_file_overlap_highest(self, ranker: CommitRanker) -> None:
        with_overlap = _make_commit(sha="aaa", files=("src/main.py",), commit_type=CommitType.CHORE)
        without_overlap = _make_commit(sha="bbb", files=("docs/readme.md",), commit_type=CommitType.CHORE)
        ranked = ranker.rank([without_overlap, with_overlap], "test failure", failing_files=["src/main.py"])
        assert ranked[0]["commit"].sha == "aaa"

    def test_rank_empty(self, ranker: CommitRanker) -> None:
        assert ranker.rank([], "symptom") == []


class TestSemanticTester:
    @patch("zerg.git.bisect_engine.subprocess.run")
    def test_run_test_pass_and_fail(self, mock_run: MagicMock) -> None:
        tester = SemanticTester()
        mock_run.return_value = subprocess.CompletedProcess(args=["pytest"], returncode=0, stdout="passed", stderr="")
        assert tester.run_test("pytest -x")["passed"] is True

        mock_run.return_value = subprocess.CompletedProcess(args=["pytest"], returncode=1, stdout="FAILED", stderr="")
        assert tester.run_test("pytest -x")["passed"] is False

    def test_analyze_output(self) -> None:
        tester = SemanticTester()
        assert tester.analyze_output({"exit_code": 0, "stdout": "5 passed", "stderr": ""})["status"] == "pass"
        result = tester.analyze_output({"exit_code": 1, "stdout": "FAILED tests/test_foo.py::test_bar", "stderr": ""})
        assert result["status"] == "fail"


class TestBisectRunner:
    def test_run_predictive_finds_culprit(self, bisect_runner: BisectRunner, mock_runner: MagicMock) -> None:
        log_output = "culprit123|||feat: add feature|||Dev|||2025-01-15 10:00:00 +0000\nsrc/broken.py\n"
        mock_runner._run.return_value = MagicMock(stdout=log_output)
        with patch.object(bisect_runner._tester, "run_test") as mock_test:
            mock_test.return_value = {"exit_code": 1, "stdout": "FAILED", "stderr": "", "passed": False}
            result = bisect_runner.run_predictive("good", "bad", "broken feature", "pytest -x")
        assert result is not None and result["culprit"].sha == "culprit123"

    def test_run_orchestration(self, bisect_runner: BisectRunner) -> None:
        predictive_result = {
            "culprit": _make_commit(sha="found_it"),
            "score": 0.95,
            "test_result": {"passed": False, "exit_code": 1, "stdout": "", "stderr": ""},
        }
        with patch.object(bisect_runner, "run_predictive", return_value=predictive_result):
            result = bisect_runner.run("good", "bad", "symptom", "pytest -x")
        assert result["method"] == "predictive"

    def test_run_both_fail(self, bisect_runner: BisectRunner) -> None:
        with (
            patch.object(bisect_runner, "run_predictive", return_value=None),
            patch.object(bisect_runner, "run_git_bisect", return_value=None),
        ):
            assert bisect_runner.run("good", "bad", "symptom", "pytest -x")["method"] == "failed"


class TestRootCauseAnalyzer:
    def test_analyze_produces_report(self, mock_runner: MagicMock) -> None:
        mock_runner._run.return_value = MagicMock(stdout=" src/main.py | 10 +++++++---\n")
        culprit = _make_commit(sha="abc123", commit_type=CommitType.REFACTOR, files=("src/main.py",))
        report = RootCauseAnalyzer().analyze(mock_runner, culprit, "tests failing")
        assert report["commit"] is culprit
        assert "src/main.py" in report["diff_summary"]


class TestBisectEngine:
    def test_full_run(self, mock_runner: MagicMock, tmp_path: Path) -> None:
        mock_runner.repo_path = tmp_path
        culprit = _make_commit(sha="c" * 40, files=("src/main.py",))
        engine = BisectEngine(mock_runner, GitConfig())
        with (
            patch.object(
                engine._bisect_runner,
                "run",
                return_value={
                    "method": "predictive",
                    "culprit": culprit,
                    "score": 0.95,
                    "test_result": {"passed": False},
                },
            ),
            patch.object(
                engine._analyzer,
                "analyze",
                return_value={
                    "commit": culprit,
                    "diff_summary": "1 file",
                    "likely_cause": "regression",
                    "suggestion": "Review",
                },
            ),
        ):
            assert engine.run(symptom="broken", test_cmd="pytest -x", good="g", bad="b") == 0
