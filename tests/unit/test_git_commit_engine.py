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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_runner(numstat: str = "", diff_names: str = "") -> MagicMock:
    """Build a mock GitRunner whose _run returns controlled output."""
    runner = MagicMock()

    def _run_side_effect(*args, **kwargs):
        result = MagicMock(spec=subprocess.CompletedProcess)
        joined = " ".join(args)
        if "--numstat" in joined:
            result.stdout = numstat
        elif "--name-only" in joined:
            result.stdout = diff_names
        elif "--stat" in joined:
            result.stdout = ""
        elif "add" in joined:
            result.stdout = ""
        elif "commit" in joined:
            result.stdout = ""
        else:
            result.stdout = ""
        result.returncode = 0
        return result

    runner._run.side_effect = _run_side_effect
    return runner


def _diff(
    files: list[str] | None = None,
    insertions: int = 0,
    deletions: int = 0,
    by_extension: dict[str, list[str]] | None = None,
    by_directory: dict[str, list[str]] | None = None,
) -> DiffAnalysis:
    """Convenience factory for DiffAnalysis."""
    return DiffAnalysis(
        files_changed=files or [],
        insertions=insertions,
        deletions=deletions,
        by_extension=by_extension or {},
        by_directory=by_directory or {},
    )


# ===========================================================================
# DiffAnalyzer
# ===========================================================================


class TestDiffAnalyzer:
    """Tests for DiffAnalyzer."""

    def test_analyze_staged_parses_numstat(self):
        """Numstat output is correctly parsed into DiffAnalysis fields."""
        numstat = "10\t2\tsrc/foo.py\n5\t0\tsrc/bar.py\n"
        runner = _make_runner(numstat=numstat)
        analyzer = DiffAnalyzer()

        result = analyzer.analyze_staged(runner)

        assert result.files_changed == ["src/foo.py", "src/bar.py"]
        assert result.insertions == 15
        assert result.deletions == 2
        assert ".py" in result.by_extension
        assert len(result.by_extension[".py"]) == 2
        assert "src" in result.by_directory

    def test_analyze_staged_empty_diff(self):
        """Empty diff produces empty DiffAnalysis."""
        runner = _make_runner(numstat="")
        analyzer = DiffAnalyzer()

        result = analyzer.analyze_staged(runner)

        assert result.files_changed == []
        assert result.insertions == 0
        assert result.deletions == 0

    def test_analyze_unstaged_delegates_correctly(self):
        """Unstaged analysis calls _run without --cached."""
        numstat = "3\t1\tREADME.md\n"
        runner = _make_runner(numstat=numstat)
        analyzer = DiffAnalyzer()

        result = analyzer.analyze_unstaged(runner)

        assert result.files_changed == ["README.md"]
        # Verify --cached was NOT in the numstat call for unstaged
        calls = runner._run.call_args_list
        numstat_calls = [c for c in calls if "--numstat" in c.args]
        assert numstat_calls
        assert "--cached" not in numstat_calls[-1].args

    def test_analyze_binary_files(self):
        """Binary files (shown as - -) are handled gracefully."""
        numstat = "-\t-\timages/logo.png\n5\t0\tsrc/app.py\n"
        runner = _make_runner(numstat=numstat)
        analyzer = DiffAnalyzer()

        result = analyzer.analyze_staged(runner)

        assert len(result.files_changed) == 2
        assert result.insertions == 5
        assert result.deletions == 0

    def test_analyze_groups_by_directory(self):
        """Files are grouped by their top-level directory."""
        numstat = "1\t0\tlib/a.py\n2\t0\tlib/b.py\n3\t0\ttests/test_a.py\n"
        runner = _make_runner(numstat=numstat)
        analyzer = DiffAnalyzer()

        result = analyzer.analyze_staged(runner)

        assert "lib" in result.by_directory
        assert "tests" in result.by_directory
        assert len(result.by_directory["lib"]) == 2
        assert len(result.by_directory["tests"]) == 1


# ===========================================================================
# CommitMessageGenerator
# ===========================================================================


class TestCommitMessageGenerator:
    """Tests for CommitMessageGenerator."""

    def setup_method(self):
        self.gen = CommitMessageGenerator(GitCommitConfig())

    def test_detect_test_files(self):
        """Files in tests/ or prefixed test_ detected as TEST."""
        diff = _diff(
            files=["tests/test_foo.py", "tests/test_bar.py"],
            by_directory={"tests": ["tests/test_foo.py", "tests/test_bar.py"]},
        )
        assert self.gen.detect_commit_type(diff) == CommitType.TEST

    def test_detect_doc_files(self):
        """Markdown files detected as DOCS."""
        diff = _diff(
            files=["README.md", "CHANGELOG.md"],
            by_extension={".md": ["README.md", "CHANGELOG.md"]},
            by_directory={".": ["README.md", "CHANGELOG.md"]},
        )
        assert self.gen.detect_commit_type(diff) == CommitType.DOCS

    def test_detect_feat_from_filename(self):
        """File names containing 'feature' trigger FEAT."""
        diff = _diff(
            files=["src/feature_payment.py"],
            by_directory={"src": ["src/feature_payment.py"]},
        )
        assert self.gen.detect_commit_type(diff) == CommitType.FEAT

    def test_detect_fix_from_filename(self):
        """File names containing 'fix ' pattern trigger FIX."""
        diff = _diff(
            files=["src/fix login.py"],
            by_directory={"src": ["src/fix login.py"]},
        )
        assert self.gen.detect_commit_type(diff) == CommitType.FIX

    def test_detect_fallback_chore(self):
        """Unknown patterns fall back to CHORE."""
        diff = _diff(
            files=["src/utils.py"],
            by_directory={"src": ["src/utils.py"]},
        )
        assert self.gen.detect_commit_type(diff) == CommitType.CHORE

    def test_detect_empty_diff_returns_chore(self):
        """Empty diff returns CHORE."""
        assert self.gen.detect_commit_type(_diff()) == CommitType.CHORE

    def test_generate_single_file(self):
        """Single file produces 'type: update <stem>' message."""
        diff = _diff(
            files=["tests/test_auth.py"],
            by_directory={"tests": ["tests/test_auth.py"]},
        )
        msg = self.gen.generate(diff)
        assert msg.startswith("test")
        assert "test_auth" in msg

    def test_generate_with_scope(self):
        """When all files share one directory, scope is included."""
        diff = _diff(
            files=["lib/parser.py", "lib/lexer.py"],
            by_directory={"lib": ["lib/parser.py", "lib/lexer.py"]},
            by_extension={".py": ["lib/parser.py", "lib/lexer.py"]},
        )
        msg = self.gen.generate(diff)
        assert "(lib)" in msg

    def test_suggest_returns_three_candidates(self):
        """Suggest mode always returns exactly 3 messages."""
        diff = _diff(
            files=["src/main.py"],
            by_directory={"src": ["src/main.py"]},
        )
        candidates = self.gen.suggest(diff)
        assert len(candidates) == 3
        assert all(isinstance(c, str) for c in candidates)

    def test_generate_multiple_files_summary(self):
        """Multiple files produce a grouped summary."""
        diff = _diff(
            files=["src/a.py", "src/b.py", "src/c.py", "src/d.py"],
            by_directory={"src": ["src/a.py", "src/b.py", "src/c.py", "src/d.py"]},
        )
        msg = self.gen.generate(diff)
        assert "src" in msg


# ===========================================================================
# StagingSuggester
# ===========================================================================


class TestStagingSuggester:
    """Tests for StagingSuggester."""

    def test_suggest_related_same_directory(self):
        """Unstaged files in same directory as staged files are suggested."""
        runner = _make_runner(diff_names="src/helper.py\nsrc/utils.py\nlib/other.css\n")
        suggester = StagingSuggester()

        related = suggester.suggest_related(runner, staged_files=["src/main.py"])

        assert "src/helper.py" in related
        assert "src/utils.py" in related
        assert "lib/other.css" not in related

    def test_suggest_related_same_extension(self):
        """Unstaged files with same extension as staged files are suggested."""
        runner = _make_runner(diff_names="lib/other.py\nstatic/style.css\n")
        suggester = StagingSuggester()

        related = suggester.suggest_related(runner, staged_files=["src/main.py"])

        assert "lib/other.py" in related
        assert "static/style.css" not in related

    def test_suggest_no_staged_files(self):
        """Empty staged list returns empty suggestions."""
        runner = _make_runner(diff_names="src/foo.py\n")
        suggester = StagingSuggester()

        assert suggester.suggest_related(runner, staged_files=[]) == []

    def test_suggest_no_unstaged_files(self):
        """No unstaged files returns empty suggestions."""
        runner = _make_runner(diff_names="")
        suggester = StagingSuggester()

        assert suggester.suggest_related(runner, staged_files=["src/main.py"]) == []


# ===========================================================================
# PreCommitValidator
# ===========================================================================


class TestPreCommitValidator:
    """Tests for PreCommitValidator."""

    def setup_method(self):
        self.validator = PreCommitValidator()

    def test_valid_message(self):
        """A well-formed message passes with no issues."""
        assert self.validator.validate("feat: add user authentication") == []

    def test_empty_message(self):
        """Empty message is flagged."""
        issues = self.validator.validate("")
        assert any("empty" in i.lower() for i in issues)

    def test_whitespace_only_message(self):
        """Whitespace-only message treated as empty."""
        issues = self.validator.validate("   \n  ")
        assert any("empty" in i.lower() for i in issues)

    def test_too_short_message(self):
        """Message under 10 chars is flagged."""
        issues = self.validator.validate("fix: x")
        assert any("short" in i.lower() for i in issues)

    def test_first_line_too_long(self):
        """First line over 72 chars is flagged."""
        long_msg = "feat: " + "a" * 70
        issues = self.validator.validate(long_msg)
        assert any("long" in i.lower() for i in issues)

    def test_wip_marker(self):
        """WIP marker in message is flagged."""
        issues = self.validator.validate("WIP: working on auth system")
        assert any("wip" in i.lower() for i in issues)

    def test_fixup_prefix(self):
        """fixup! prefix is flagged."""
        issues = self.validator.validate("fixup! feat: add login")
        assert any("fixup" in i.lower() for i in issues)


# ===========================================================================
# CommitEngine
# ===========================================================================


class TestCommitEngine:
    """Tests for CommitEngine orchestration."""

    def _make_engine(self, mode: str = "confirm", numstat: str = "") -> tuple[CommitEngine, MagicMock]:
        runner = _make_runner(numstat=numstat)
        config = GitConfig(commit=GitCommitConfig(mode=mode))
        engine = CommitEngine(runner, config)
        return engine, runner

    def test_confirm_mode_no_staged(self):
        """Confirm mode returns 1 when nothing is staged."""
        engine, _ = self._make_engine(mode="confirm", numstat="")
        assert engine.run() == 1

    def test_confirm_mode_with_staged(self):
        """Confirm mode generates message and returns 0."""
        engine, _ = self._make_engine(
            mode="confirm",
            numstat="10\t2\tsrc/auth.py\n",
        )
        assert engine.run() == 0
        assert engine.message is not None
        assert "auth" in engine.message

    def test_suggest_mode_returns_candidates(self):
        """Suggest mode populates suggestions list."""
        engine, _ = self._make_engine(
            mode="suggest",
            numstat="5\t0\tsrc/main.py\n",
        )
        assert engine.run() == 0
        assert engine.suggestions is not None
        assert len(engine.suggestions) == 3

    def test_auto_mode_commits(self):
        """Auto mode stages, generates message, and calls git commit."""
        engine, runner = self._make_engine(
            mode="auto",
            numstat="3\t1\tsrc/app.py\n",
        )
        result = engine.run()
        assert result == 0

        # Verify commit was called
        commit_calls = [c for c in runner._run.call_args_list if "commit" in c.args]
        assert len(commit_calls) == 1

    def test_mode_override(self):
        """Explicit mode parameter overrides config."""
        engine, _ = self._make_engine(
            mode="confirm",
            numstat="2\t0\tsrc/x.py\n",
        )
        # Override to suggest
        assert engine.run(mode="suggest") == 0
        assert engine.suggestions is not None

    def test_auto_mode_no_changes(self):
        """Auto mode returns 1 when no files changed after staging."""
        engine, _ = self._make_engine(mode="auto", numstat="")
        assert engine.run() == 1
