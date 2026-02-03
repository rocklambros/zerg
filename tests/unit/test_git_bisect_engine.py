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

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_commit(
    sha: str = "abc123",
    message: str = "feat: add feature",
    author: str = "Dev",
    date: str = "2025-01-15 10:00:00 +0000",
    files: tuple[str, ...] = ("src/main.py",),
    commit_type: CommitType | None = CommitType.FEAT,
) -> CommitInfo:
    return CommitInfo(
        sha=sha,
        message=message,
        author=author,
        date=date,
        files=files,
        commit_type=commit_type,
    )


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
def tester() -> SemanticTester:
    return SemanticTester()


@pytest.fixture()
def bisect_runner(
    mock_runner: MagicMock,
    ranker: CommitRanker,
    tester: SemanticTester,
) -> BisectRunner:
    return BisectRunner(mock_runner, ranker, tester)


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_detect_commit_type_conventional_prefix(self) -> None:
        assert _detect_commit_type_from_message("feat: add login") == CommitType.FEAT
        assert _detect_commit_type_from_message("fix(auth): resolve bug") == CommitType.FIX
        assert _detect_commit_type_from_message("docs: update readme") == CommitType.DOCS

    def test_detect_commit_type_pattern_fallback(self) -> None:
        result = _detect_commit_type_from_message("add new authentication flow")
        assert result == CommitType.FEAT

    def test_detect_commit_type_unknown(self) -> None:
        result = _detect_commit_type_from_message("random message")
        assert result is None

    def test_extract_file_hints(self) -> None:
        hints = _extract_file_hints_from_symptom("Error in src/main.py line 42")
        assert "src/main.py" in hints

    def test_extract_module_hints(self) -> None:
        hints = _extract_file_hints_from_symptom("ImportError in zerg.git.base module")
        assert "zerg/git/base" in hints

    def test_sanitize_text(self) -> None:
        assert "```" not in _sanitize_text("```python\ncode\n```")
        # Control characters removed
        assert "\x00" not in _sanitize_text("bad\x00text")


# ---------------------------------------------------------------------------
# CommitRanker tests
# ---------------------------------------------------------------------------


class TestCommitRanker:
    def test_get_commits_in_range_parses_log(self, ranker: CommitRanker, mock_runner: MagicMock) -> None:
        log_output = (
            "abc123|||feat: add feature|||Dev|||2025-01-15 10:00:00 +0000\n"
            "src/main.py\n"
            "src/utils.py\n"
            "\n"
            "def456|||fix: resolve bug|||Dev|||2025-01-16 10:00:00 +0000\n"
            "src/bug.py\n"
        )
        mock_runner._run.return_value = MagicMock(stdout=log_output)

        commits = ranker.get_commits_in_range("good", "bad")

        assert len(commits) == 2
        assert commits[0].sha == "abc123"
        assert commits[0].files == ("src/main.py", "src/utils.py")
        assert commits[0].commit_type == CommitType.FEAT
        assert commits[1].sha == "def456"
        assert commits[1].files == ("src/bug.py",)

    def test_get_commits_empty_output(self, ranker: CommitRanker, mock_runner: MagicMock) -> None:
        mock_runner._run.return_value = MagicMock(stdout="")
        commits = ranker.get_commits_in_range("good", "bad")
        assert commits == []

    def test_rank_scores_file_overlap_highest(self, ranker: CommitRanker) -> None:
        commit_with_overlap = _make_commit(
            sha="aaa", files=("src/main.py", "src/utils.py"), commit_type=CommitType.CHORE
        )
        commit_without_overlap = _make_commit(sha="bbb", files=("docs/readme.md",), commit_type=CommitType.CHORE)
        commits = [commit_without_overlap, commit_with_overlap]

        ranked = ranker.rank(commits, "test failure", failing_files=["src/main.py"])

        # The commit with file overlap should rank first
        assert ranked[0]["commit"].sha == "aaa"
        assert ranked[0]["score"] > ranked[1]["score"]

    def test_rank_scores_recency(self, ranker: CommitRanker) -> None:
        old_commit = _make_commit(sha="old", files=("a.py",), commit_type=CommitType.CHORE)
        new_commit = _make_commit(sha="new", files=("b.py",), commit_type=CommitType.CHORE)
        # Commits listed oldest first, newest last
        commits = [old_commit, new_commit]

        ranked = ranker.rank(commits, "something broke", failing_files=[])

        # new_commit has higher recency (index=1 of 2 = 1.0) vs old (index=0 of 2 = 0.5)
        new_entry = next(r for r in ranked if r["commit"].sha == "new")
        old_entry = next(r for r in ranked if r["commit"].sha == "old")
        assert new_entry["score"] >= old_entry["score"]

    def test_rank_with_no_failing_files(self, ranker: CommitRanker) -> None:
        commit = _make_commit(sha="aaa", files=("src/main.py",))
        ranked = ranker.rank(
            [commit],
            "error in src/main.py",
            failing_files=None,
        )
        assert len(ranked) == 1
        # Should still extract hints from symptom
        assert ranked[0]["score"] > 0

    def test_rank_empty_commits(self, ranker: CommitRanker) -> None:
        assert ranker.rank([], "symptom") == []

    def test_rank_high_risk_type_scores_higher(self, ranker: CommitRanker) -> None:
        feat_commit = _make_commit(sha="feat", commit_type=CommitType.FEAT, files=("a.py",))
        docs_commit = _make_commit(sha="docs", commit_type=CommitType.DOCS, files=("a.py",))
        commits = [feat_commit, docs_commit]

        ranked = ranker.rank(commits, "bug", failing_files=[])

        feat_entry = next(r for r in ranked if r["commit"].sha == "feat")
        docs_entry = next(r for r in ranked if r["commit"].sha == "docs")
        assert feat_entry["score"] > docs_entry["score"]


# ---------------------------------------------------------------------------
# SemanticTester tests
# ---------------------------------------------------------------------------


class TestSemanticTester:
    @patch("zerg.git.bisect_engine.subprocess.run")
    def test_run_test_success(self, mock_run: MagicMock, tester: SemanticTester) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["pytest"], returncode=0, stdout="all passed", stderr=""
        )
        result = tester.run_test("pytest -x")
        assert result["passed"] is True
        assert result["exit_code"] == 0
        assert result["stdout"] == "all passed"

    @patch("zerg.git.bisect_engine.subprocess.run")
    def test_run_test_failure(self, mock_run: MagicMock, tester: SemanticTester) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["pytest"], returncode=1, stdout="FAILED test_foo", stderr=""
        )
        result = tester.run_test("pytest -x")
        assert result["passed"] is False
        assert result["exit_code"] == 1

    @patch("zerg.git.bisect_engine.subprocess.run")
    def test_run_test_timeout(self, mock_run: MagicMock, tester: SemanticTester) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="pytest", timeout=5)
        result = tester.run_test("pytest -x", timeout=5)
        assert result["passed"] is False
        assert result["exit_code"] == -1

    def test_analyze_output_pass(self, tester: SemanticTester) -> None:
        result = {"exit_code": 0, "stdout": "5 passed", "stderr": ""}
        analysis = tester.analyze_output(result)
        assert analysis["status"] == "pass"
        assert analysis["failing_tests"] == []

    def test_analyze_output_failed_pattern(self, tester: SemanticTester) -> None:
        result = {
            "exit_code": 1,
            "stdout": "FAILED tests/test_foo.py::test_bar\n1 failed",
            "stderr": "",
        }
        analysis = tester.analyze_output(result)
        assert analysis["status"] == "fail"
        assert "tests/test_foo.py::test_bar" in analysis["failing_tests"]

    def test_analyze_output_error_pattern(self, tester: SemanticTester) -> None:
        result = {
            "exit_code": 2,
            "stdout": "",
            "stderr": "ERROR: ImportError in conftest\nError: cannot import module",
        }
        analysis = tester.analyze_output(result)
        assert analysis["status"] == "error"
        assert analysis["error_message"] != ""


# ---------------------------------------------------------------------------
# BisectRunner tests
# ---------------------------------------------------------------------------


class TestBisectRunner:
    def test_run_predictive_finds_culprit(self, bisect_runner: BisectRunner, mock_runner: MagicMock) -> None:
        _make_commit(
            sha="culprit123",
            files=("src/broken.py",),
            commit_type=CommitType.FEAT,
        )
        log_output = "culprit123|||feat: add feature|||Dev|||2025-01-15 10:00:00 +0000\nsrc/broken.py\n"
        mock_runner._run.return_value = MagicMock(stdout=log_output)

        # Mock the tester to return failure
        with patch.object(bisect_runner._tester, "run_test") as mock_test:
            mock_test.return_value = {
                "exit_code": 1,
                "stdout": "FAILED",
                "stderr": "",
                "passed": False,
            }
            result = bisect_runner.run_predictive("good", "bad", "broken feature", "pytest -x")

        assert result is not None
        assert result["culprit"].sha == "culprit123"
        assert result["score"] > 0

    def test_run_predictive_low_confidence_returns_none(
        self, bisect_runner: BisectRunner, mock_runner: MagicMock
    ) -> None:
        mock_runner._run.return_value = MagicMock(stdout="")

        result = bisect_runner.run_predictive("good", "bad", "unknown issue", "pytest -x")
        assert result is None

    def test_run_git_bisect(self, bisect_runner: BisectRunner, mock_runner: MagicMock) -> None:
        sha = "a1b2c3d4e5" * 4  # 40 hex chars
        bisect_output = f"{sha} is the first bad commit\ncommit message: feat: add broken thing\n"
        mock_runner._run.return_value = MagicMock(stdout=bisect_output, returncode=0)

        result = bisect_runner.run_git_bisect("good", "bad", "pytest -x")

        assert result is not None
        assert result["culprit_sha"] == sha

    def test_run_git_bisect_no_match(self, bisect_runner: BisectRunner, mock_runner: MagicMock) -> None:
        mock_runner._run.return_value = MagicMock(stdout="no result", returncode=1)

        result = bisect_runner.run_git_bisect("good", "bad", "pytest -x")
        assert result is None

    def test_run_orchestration_uses_predictive_first(self, bisect_runner: BisectRunner) -> None:
        predictive_result = {
            "culprit": _make_commit(sha="found_it"),
            "score": 0.95,
            "test_result": {"passed": False, "exit_code": 1, "stdout": "", "stderr": ""},
        }
        with patch.object(bisect_runner, "run_predictive", return_value=predictive_result):
            result = bisect_runner.run("good", "bad", "symptom", "pytest -x")

        assert result["method"] == "predictive"
        assert result["culprit"].sha == "found_it"

    def test_run_orchestration_falls_back_to_git_bisect(self, bisect_runner: BisectRunner) -> None:
        with (
            patch.object(bisect_runner, "run_predictive", return_value=None),
            patch.object(
                bisect_runner,
                "run_git_bisect",
                return_value={"culprit_sha": "abc" * 13 + "a", "message": "bad commit"},
            ),
        ):
            result = bisect_runner.run("good", "bad", "symptom", "pytest -x")

        assert result["method"] == "git_bisect"

    def test_run_orchestration_both_fail(self, bisect_runner: BisectRunner) -> None:
        with (
            patch.object(bisect_runner, "run_predictive", return_value=None),
            patch.object(bisect_runner, "run_git_bisect", return_value=None),
        ):
            result = bisect_runner.run("good", "bad", "symptom", "pytest -x")

        assert result["method"] == "failed"


# ---------------------------------------------------------------------------
# RootCauseAnalyzer tests
# ---------------------------------------------------------------------------


class TestRootCauseAnalyzer:
    def test_analyze_produces_report(self, mock_runner: MagicMock) -> None:
        mock_runner._run.return_value = MagicMock(stdout=" src/main.py | 10 +++++++---\n 1 file changed")
        culprit = _make_commit(
            sha="abc123",
            message="refactor: restructure module",
            commit_type=CommitType.REFACTOR,
            files=("src/main.py",),
        )
        analyzer = RootCauseAnalyzer()
        report = analyzer.analyze(mock_runner, culprit, "tests failing")

        assert report["commit"] is culprit
        assert "src/main.py" in report["diff_summary"]
        assert "Refactoring" in report["likely_cause"]
        assert "Review changes in" in report["suggestion"]

    def test_analyze_feat_cause(self, mock_runner: MagicMock) -> None:
        mock_runner._run.return_value = MagicMock(stdout="diff output")
        culprit = _make_commit(commit_type=CommitType.FEAT)
        analyzer = RootCauseAnalyzer()
        report = analyzer.analyze(mock_runner, culprit, "regression")
        assert "regression" in report["likely_cause"] or "feature" in report["likely_cause"].lower()

    def test_analyze_no_files(self, mock_runner: MagicMock) -> None:
        mock_runner._run.return_value = MagicMock(stdout="")
        culprit = _make_commit(files=(), commit_type=None)
        analyzer = RootCauseAnalyzer()
        report = analyzer.analyze(mock_runner, culprit, "crash")
        assert "Review full diff" in report["suggestion"]


# ---------------------------------------------------------------------------
# BisectEngine integration tests
# ---------------------------------------------------------------------------


class TestBisectEngine:
    def test_full_run(self, mock_runner: MagicMock, tmp_path: Path) -> None:
        mock_runner.repo_path = tmp_path
        config = GitConfig()

        culprit = _make_commit(sha="c" * 40, files=("src/main.py",))

        engine = BisectEngine(mock_runner, config)

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
                    "diff_summary": "1 file changed",
                    "likely_cause": "feature regression",
                    "suggestion": "Review changes in src/main.py",
                },
            ),
        ):
            exit_code = engine.run(
                symptom="tests broken",
                test_cmd="pytest -x",
                good="good_sha",
                bad="bad_sha",
            )

        assert exit_code == 0
        # Verify report was saved
        report_dir = tmp_path / ".zerg" / "bisect-reports"
        assert report_dir.exists()
        reports = list(report_dir.glob("*.md"))
        assert len(reports) == 1
        content = reports[0].read_text()
        assert "tests broken" in content

    def test_run_with_no_test_cmd_auto_detect(self, mock_runner: MagicMock, tmp_path: Path) -> None:
        mock_runner.repo_path = tmp_path
        # Create a pyproject.toml with pytest config
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.pytest.ini_options]\naddopts = '-v'\n")

        config = GitConfig()
        engine = BisectEngine(mock_runner, config)

        with patch.object(
            engine._bisect_runner,
            "run",
            return_value={"method": "failed", "culprit": None, "message": "no culprit"},
        ):
            exit_code = engine.run(
                symptom="tests broken",
                good="good_sha",
                bad="bad_sha",
            )

        # Should have auto-detected pytest and proceeded (method=failed -> exit 1)
        assert exit_code == 1

    def test_run_no_good_ref_defaults(self, mock_runner: MagicMock, tmp_path: Path) -> None:
        mock_runner.repo_path = tmp_path
        config = GitConfig()
        engine = BisectEngine(mock_runner, config)

        # Mock _find_good_default
        with (
            patch.object(engine, "_find_good_default", return_value="v1.0.0"),
            patch.object(
                engine._bisect_runner,
                "run",
                return_value={
                    "method": "predictive",
                    "culprit": _make_commit(sha="d" * 40),
                    "score": 0.9,
                    "test_result": {"passed": False},
                },
            ),
            patch.object(
                engine._analyzer,
                "analyze",
                return_value={
                    "commit": _make_commit(sha="d" * 40),
                    "diff_summary": "",
                    "likely_cause": "cause",
                    "suggestion": "suggestion",
                },
            ),
        ):
            exit_code = engine.run(
                symptom="crash",
                test_cmd="pytest -x",
            )

        assert exit_code == 0

    def test_run_no_test_cmd_no_detection_fails(self, mock_runner: MagicMock, tmp_path: Path) -> None:
        mock_runner.repo_path = tmp_path
        config = GitConfig()
        engine = BisectEngine(mock_runner, config)

        exit_code = engine.run(
            symptom="crash",
            good="good_sha",
            bad="bad_sha",
        )
        assert exit_code == 1

    def test_find_good_default_tag(self, mock_runner: MagicMock, tmp_path: Path) -> None:
        mock_runner.repo_path = tmp_path
        mock_runner._run.return_value = MagicMock(stdout="v1.2.3\n", returncode=0)
        config = GitConfig()
        engine = BisectEngine(mock_runner, config)
        assert engine._find_good_default() == "v1.2.3"

    def test_find_good_default_first_commit(self, mock_runner: MagicMock, tmp_path: Path) -> None:
        mock_runner.repo_path = tmp_path

        def side_effect(*args, **kwargs):
            if "describe" in args:
                result = MagicMock(stdout="", returncode=128)
                return result
            if "rev-list" in args:
                return MagicMock(stdout="first_commit_sha\n")
            return MagicMock(stdout="", returncode=0)

        mock_runner._run.side_effect = side_effect
        config = GitConfig()
        engine = BisectEngine(mock_runner, config)
        assert engine._find_good_default() == "first_commit_sha"
