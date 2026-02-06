"""Tests for zerg.git.commit_engine -- smart commit engine."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock

from zerg.git.commit_engine import (
    CommitEngine,
    CommitMessageGenerator,
    DiffAnalyzer,
    PreCommitValidator,
    StagingSuggester,
)
from zerg.git.config import GitCommitConfig, GitConfig
from zerg.git.types import CommitType, DiffAnalysis


def _make_runner(numstat: str = "", diff_names: str = "") -> MagicMock:
    runner = MagicMock()

    def _run_side_effect(*args, **kwargs):
        result = MagicMock(spec=subprocess.CompletedProcess)
        joined = " ".join(args)
        if "--numstat" in joined:
            result.stdout = numstat
        elif "--name-only" in joined:
            result.stdout = diff_names
        else:
            result.stdout = ""
        result.returncode = 0
        return result

    runner._run.side_effect = _run_side_effect
    return runner


def _diff(files=None, insertions=0, deletions=0, by_extension=None, by_directory=None) -> DiffAnalysis:
    return DiffAnalysis(
        files_changed=files or [],
        insertions=insertions,
        deletions=deletions,
        by_extension=by_extension or {},
        by_directory=by_directory or {},
    )


class TestDiffAnalyzer:
    def test_analyze_staged_parses_numstat(self):
        runner = _make_runner(numstat="10\t2\tsrc/foo.py\n5\t0\tsrc/bar.py\n")
        result = DiffAnalyzer().analyze_staged(runner)
        assert result.files_changed == ["src/foo.py", "src/bar.py"]
        assert result.insertions == 15 and result.deletions == 2

    def test_analyze_staged_empty(self):
        result = DiffAnalyzer().analyze_staged(_make_runner(numstat=""))
        assert result.files_changed == [] and result.insertions == 0

    def test_analyze_binary_files(self):
        runner = _make_runner(numstat="-\t-\timages/logo.png\n5\t0\tsrc/app.py\n")
        result = DiffAnalyzer().analyze_staged(runner)
        assert len(result.files_changed) == 2


class TestCommitMessageGenerator:
    def setup_method(self):
        self.gen = CommitMessageGenerator(GitCommitConfig())

    def test_detect_commit_types(self):
        assert (
            self.gen.detect_commit_type(
                _diff(files=["tests/test_foo.py"], by_directory={"tests": ["tests/test_foo.py"]})
            )
            == CommitType.TEST
        )
        assert (
            self.gen.detect_commit_type(
                _diff(files=["README.md"], by_extension={".md": ["README.md"]}, by_directory={".": ["README.md"]})
            )
            == CommitType.DOCS
        )
        assert self.gen.detect_commit_type(_diff()) == CommitType.CHORE

    def test_generate_single_file(self):
        diff = _diff(files=["tests/test_auth.py"], by_directory={"tests": ["tests/test_auth.py"]})
        msg = self.gen.generate(diff)
        assert msg.startswith("test") and "test_auth" in msg

    def test_suggest_returns_three(self):
        diff = _diff(files=["src/main.py"], by_directory={"src": ["src/main.py"]})
        assert len(self.gen.suggest(diff)) == 3


class TestStagingSuggester:
    def test_suggest_related(self):
        runner = _make_runner(diff_names="src/helper.py\nlib/other.css\n")
        related = StagingSuggester().suggest_related(runner, staged_files=["src/main.py"])
        assert "src/helper.py" in related and "lib/other.css" not in related

    def test_suggest_no_staged(self):
        runner = _make_runner(diff_names="src/foo.py\n")
        assert StagingSuggester().suggest_related(runner, staged_files=[]) == []


class TestPreCommitValidator:
    def test_valid_message(self):
        assert PreCommitValidator().validate("feat: add user authentication") == []

    def test_invalid_messages(self):
        v = PreCommitValidator()
        assert any("empty" in i.lower() for i in v.validate(""))
        assert any("short" in i.lower() for i in v.validate("fix: x"))
        assert any("wip" in i.lower() for i in v.validate("WIP: working on auth system"))


class TestCommitEngine:
    def _make_engine(self, mode="confirm", numstat=""):
        runner = _make_runner(numstat=numstat)
        return CommitEngine(runner, GitConfig(commit=GitCommitConfig(mode=mode))), runner

    def test_confirm_mode_no_staged(self):
        engine, _ = self._make_engine(mode="confirm", numstat="")
        assert engine.run() == 1

    def test_confirm_mode_with_staged(self):
        engine, _ = self._make_engine(mode="confirm", numstat="10\t2\tsrc/auth.py\n")
        assert engine.run() == 0 and engine.message is not None

    def test_suggest_mode(self):
        engine, _ = self._make_engine(mode="suggest", numstat="5\t0\tsrc/main.py\n")
        assert engine.run() == 0 and len(engine.suggestions) == 3

    def test_auto_mode_commits(self):
        engine, runner = self._make_engine(mode="auto", numstat="3\t1\tsrc/app.py\n")
        assert engine.run() == 0
        assert any("commit" in c.args for c in runner._run.call_args_list)
