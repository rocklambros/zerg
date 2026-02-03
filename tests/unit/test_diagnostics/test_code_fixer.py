"""Tests for zerg.diagnostics.code_fixer module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from zerg.diagnostics.code_fixer import (
    CodeAwareFixer,
    DependencyAnalyzer,
    FixSuggestionGenerator,
    GitContextAnalyzer,
)
from zerg.diagnostics.recovery import RecoveryStep
from zerg.diagnostics.types import ErrorFingerprint, Evidence


# ---------------------------------------------------------------------------
# TestDependencyAnalyzer
# ---------------------------------------------------------------------------
class TestDependencyAnalyzer:
    """Tests for DependencyAnalyzer."""

    def test_analyze_imports_valid_file(self, tmp_path: Path) -> None:
        """Temp .py file with known imports returns the correct module names."""
        py_file = tmp_path / "sample.py"
        py_file.write_text("import os\nfrom pathlib import Path\n")

        analyzer = DependencyAnalyzer()
        result = analyzer.analyze_imports(str(py_file))

        assert "os" in result
        assert "pathlib" in result

    def test_analyze_imports_nonexistent(self) -> None:
        """Non-existent file returns empty list."""
        analyzer = DependencyAnalyzer()
        result = analyzer.analyze_imports("/no/such/file.py")
        assert result == []

    def test_find_missing_deps_import_error(self) -> None:
        """ImportError message yields the missing module name."""
        analyzer = DependencyAnalyzer()
        result = analyzer.find_missing_deps("ImportError: No module named 'foo'")
        assert result == ["foo"]

    def test_find_missing_deps_module_not_found(self) -> None:
        """ModuleNotFoundError message yields the missing module name."""
        analyzer = DependencyAnalyzer()
        result = analyzer.find_missing_deps("ModuleNotFoundError: No module named 'bar'")
        assert result == ["bar"]

    def test_find_missing_deps_no_match(self) -> None:
        """Unrelated error text returns empty list."""
        analyzer = DependencyAnalyzer()
        result = analyzer.find_missing_deps("TypeError: bad type")
        assert result == []

    def test_trace_import_chain(self, tmp_path: Path) -> None:
        """Files importing a module are discovered by trace_import_chain."""
        # Create two .py files: one imports 'mymod', one does not
        (tmp_path / "a.py").write_text("import mymod\n")
        (tmp_path / "b.py").write_text("import os\n")

        analyzer = DependencyAnalyzer()
        result = analyzer.trace_import_chain("mymod", tmp_path)

        assert len(result) == 1
        assert "a.py" in result[0]


# ---------------------------------------------------------------------------
# TestGitContextAnalyzer
# ---------------------------------------------------------------------------
class TestGitContextAnalyzer:
    """Tests for GitContextAnalyzer — all subprocess calls mocked."""

    def test_get_recent_changes(self) -> None:
        """Mocked git log output returns list of dicts with expected keys."""
        git_output = (
            "abc1234|Alice|2025-01-01T00:00:00+00:00|Initial commit\ndef5678|Bob|2025-01-02T00:00:00+00:00|Add feature"
        )
        mock_result = MagicMock(stdout=git_output, returncode=0)

        analyzer = GitContextAnalyzer()
        with patch("subprocess.run", return_value=mock_result):
            changes = analyzer.get_recent_changes("some_file.py")

        assert len(changes) == 2
        assert changes[0]["hash"] == "abc1234"
        assert changes[0]["author"] == "Alice"
        assert changes[0]["date"] == "2025-01-01T00:00:00+00:00"
        assert changes[0]["message"] == "Initial commit"
        assert changes[1]["author"] == "Bob"

    def test_get_recent_changes_failure(self) -> None:
        """Subprocess failure returns empty list."""
        mock_result = MagicMock(stdout="", returncode=1)

        analyzer = GitContextAnalyzer()
        with patch("subprocess.run", return_value=mock_result):
            changes = analyzer.get_recent_changes("some_file.py")

        assert changes == []

    def test_get_blame_context(self) -> None:
        """Mocked git blame porcelain output returns expected entries."""
        blame_output = (
            "abc12345678901234567890123456789012345678 10 10 1\n"
            "author Alice\n"
            "author-mail <alice@example.com>\n"
            "author-time 1700000000\n"
            "author-tz +0000\n"
            "committer Alice\n"
            "summary Some commit\n"
            "filename file.py\n"
            "\tprint('hello')\n"
        )
        mock_result = MagicMock(stdout=blame_output, returncode=0)

        analyzer = GitContextAnalyzer()
        with patch("subprocess.run", return_value=mock_result):
            blame = analyzer.get_blame_context("file.py", 10)

        assert len(blame) >= 1
        entry = blame[0]
        assert "line" in entry
        assert "hash" in entry
        assert "author" in entry
        assert "content" in entry
        assert entry["author"] == "Alice"
        assert entry["content"] == "print('hello')"

    def test_suggest_bisect(self) -> None:
        """suggest_bisect returns a string containing 'git bisect'."""
        analyzer = GitContextAnalyzer()
        result = analyzer.suggest_bisect()
        assert "git bisect" in result


# ---------------------------------------------------------------------------
# TestFixSuggestionGenerator
# ---------------------------------------------------------------------------
class TestFixSuggestionGenerator:
    """Tests for FixSuggestionGenerator."""

    def _make_fingerprint(self, **kwargs) -> ErrorFingerprint:
        """Helper to create an ErrorFingerprint with sensible defaults."""
        defaults = {
            "hash": "abc123",
            "language": "python",
            "error_type": "Error",
            "message_template": "something went wrong",
            "file": "",
            "line": 0,
        }
        defaults.update(kwargs)
        return ErrorFingerprint(**defaults)

    def test_suggest_code_error(self) -> None:
        """CODE_ERROR-type fingerprint mentions code review."""
        gen = FixSuggestionGenerator()
        fp = self._make_fingerprint(
            error_type="TypeError",
            message_template="bad type",
            file="main.py",
            line=42,
        )
        suggestions = gen.suggest(fp, [])
        assert any("review" in s.lower() or "Review" in s for s in suggestions)

    def test_suggest_dependency(self) -> None:
        """DEPENDENCY-type fingerprint mentions pip install."""
        gen = FixSuggestionGenerator()
        fp = self._make_fingerprint(
            error_type="ImportError",
            message_template="No module named foo",
        )
        suggestions = gen.suggest(fp, [])
        assert any("pip install" in s.lower() for s in suggestions)

    def test_suggest_default(self) -> None:
        """Generic error returns at least one suggestion."""
        gen = FixSuggestionGenerator()
        fp = self._make_fingerprint(
            error_type="RuntimeError",
            message_template="unknown issue",
        )
        suggestions = gen.suggest(fp, [])
        assert len(suggestions) >= 1

    def test_generate_recovery_steps(self) -> None:
        """Recovery steps returns list of RecoveryStep with expected fields."""
        gen = FixSuggestionGenerator()
        fp = self._make_fingerprint(
            error_type="TypeError",
            message_template="bad type",
            file="main.py",
            line=10,
        )
        steps = gen.generate_recovery_steps(fp, [])
        assert len(steps) >= 1
        assert all(isinstance(s, RecoveryStep) for s in steps)
        for s in steps:
            assert s.description
            assert s.command
            assert s.risk in ("safe", "moderate", "destructive")


# ---------------------------------------------------------------------------
# TestCodeAwareFixer
# ---------------------------------------------------------------------------
class TestCodeAwareFixer:
    """Tests for the CodeAwareFixer facade."""

    def test_analyze_full_flow(self, tmp_path: Path) -> None:
        """Full analyze() returns dict with expected top-level keys."""
        # Create a real python file for dependency analysis
        py_file = tmp_path / "buggy.py"
        py_file.write_text("import os\n")

        fp = ErrorFingerprint(
            hash="abc123",
            language="python",
            error_type="TypeError",
            message_template="bad arg",
            file="buggy.py",
            line=1,
        )
        evidence: list[Evidence] = []

        # Mock git subprocess calls
        mock_result = MagicMock(stdout="", returncode=1)
        fixer = CodeAwareFixer()
        with patch("subprocess.run", return_value=mock_result):
            result = fixer.analyze(fp, evidence, project_root=tmp_path)

        assert "dependencies" in result
        assert "git_context" in result
        assert "suggestions" in result
        assert "recovery_steps" in result
        # dependencies sub-keys
        assert "imports" in result["dependencies"]
        assert "missing" in result["dependencies"]
