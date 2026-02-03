"""Tests for pre-review context assembly."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

from zerg.git.base import GitRunner
from zerg.git.config import GitConfig
from zerg.git.prereview import (
    ContextPreparer,
    DomainFilter,
    PreReviewEngine,
    ReviewReporter,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_git(*args: str, cwd: Path) -> None:
    """Run git command safely."""
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)


def _make_runner(stdout: str = "", returncode: int = 0) -> MagicMock:
    """Create a mock GitRunner whose _run returns controlled output."""
    runner = MagicMock(spec=GitRunner)
    result = MagicMock()
    result.stdout = stdout
    result.returncode = returncode
    runner._run.return_value = result
    runner.repo_path = Path("/fake/repo")
    runner.current_branch.return_value = "feat/test"
    return runner


# ===========================================================================
# TestContextPreparer
# ===========================================================================


class TestContextPreparer:
    """Tests for ContextPreparer."""

    def test_get_changed_files_returns_list(self) -> None:
        runner = _make_runner("src/app.py\nREADME.md\n")
        preparer = ContextPreparer(runner)

        files = preparer.get_changed_files("main")

        assert files == ["src/app.py", "README.md"]
        runner._run.assert_called_once_with("diff", "--name-only", "main..HEAD")

    def test_get_changed_files_empty(self) -> None:
        runner = _make_runner("")
        preparer = ContextPreparer(runner)

        files = preparer.get_changed_files("main")

        assert files == []

    def test_get_file_hunks_within_budget(self) -> None:
        diff_text = "@@ -1,3 +1,4 @@\n+new line\n context\n"
        runner = _make_runner(diff_text)
        preparer = ContextPreparer(runner)

        hunks = preparer.get_file_hunks("app.py", "main", budget_chars=2000)

        assert hunks == diff_text
        runner._run.assert_called_once_with("diff", "main..HEAD", "--", "app.py")

    def test_get_file_hunks_truncates_over_budget(self) -> None:
        diff_text = "x" * 3000
        runner = _make_runner(diff_text)
        preparer = ContextPreparer(runner)

        hunks = preparer.get_file_hunks("app.py", "main", budget_chars=100)

        assert len(hunks) < len(diff_text)
        assert hunks.endswith("... [truncated]")

    def test_prepare_context_distributes_budget(self) -> None:
        runner = _make_runner()
        # First call: changed files. Subsequent calls: hunks per file.
        runner._run.side_effect = [
            MagicMock(stdout="a.py\nb.js\n"),
            MagicMock(stdout="diff a"),
            MagicMock(stdout="diff b"),
        ]
        preparer = ContextPreparer(runner)

        ctx = preparer.prepare_context("main", budget_chars=4000)

        assert ctx["total_files"] == 2
        assert len(ctx["files"]) == 2
        assert ctx["files"][0]["path"] == "a.py"
        assert ctx["files"][0]["extension"] == ".py"
        assert ctx["files"][1]["extension"] == ".js"

    def test_prepare_context_no_changes(self) -> None:
        runner = _make_runner("")
        preparer = ContextPreparer(runner)

        ctx = preparer.prepare_context("main")

        assert ctx == {"files": [], "total_files": 0, "truncated": False}


# ===========================================================================
# TestDomainFilter
# ===========================================================================


class TestDomainFilter:
    """Tests for DomainFilter."""

    def test_get_domains_for_py(self) -> None:
        df = DomainFilter(rules_dir=Path("/nonexistent"))
        domains = df.get_domains_for_extension(".py")

        assert "python" in domains
        assert "owasp" in domains

    def test_get_domains_for_js(self) -> None:
        df = DomainFilter(rules_dir=Path("/nonexistent"))
        domains = df.get_domains_for_extension(".js")

        assert "javascript" in domains
        assert "owasp" in domains

    def test_get_domains_for_ts(self) -> None:
        df = DomainFilter(rules_dir=Path("/nonexistent"))
        domains = df.get_domains_for_extension(".ts")

        assert "javascript" in domains
        assert "owasp" in domains

    def test_get_domains_for_dockerfile(self) -> None:
        df = DomainFilter(rules_dir=Path("/nonexistent"))
        domains = df.get_domains_for_filename("Dockerfile")

        assert "docker" in domains
        assert "owasp" in domains

    def test_always_includes_owasp(self) -> None:
        df = DomainFilter(rules_dir=Path("/nonexistent"))
        # Unknown extension should still get owasp
        domains = df.get_domains_for_extension(".rs")

        assert domains == ["owasp"]

    def test_get_rules_summary_reads_files(self, tmp_path: Path) -> None:
        """Create a mock rules directory and verify extraction."""
        core_dir = tmp_path / "_core"
        core_dir.mkdir()
        (core_dir / "owasp-2025.md").write_text(
            "# OWASP\n\n## Quick Reference\n\n"
            "| Rule | Level |\n|------|-------|\n| A01 | strict |\n\n"
            "## Version History\nv1.0\n"
        )

        df = DomainFilter(rules_dir=tmp_path)
        summary = df.get_rules_summary(["owasp"])

        assert "Quick Reference" in summary
        assert "A01" in summary

    def test_get_rules_summary_truncates(self, tmp_path: Path) -> None:
        core_dir = tmp_path / "_core"
        core_dir.mkdir()
        # Create a large reference section
        big_table = "| Rule | Level |\n" + "| A01 | strict |\n" * 200
        (core_dir / "owasp.md").write_text(f"# Rules\n\n## Quick Reference\n\n{big_table}\n\n## End\n")

        df = DomainFilter(rules_dir=tmp_path)
        summary = df.get_rules_summary(["owasp"], budget_chars=200)

        assert len(summary) <= 250  # some slack for header + truncation marker

    def test_filter_for_files_combines_domains(self) -> None:
        df = DomainFilter(rules_dir=Path("/nonexistent"))
        result = df.filter_for_files(["app.py", "index.js", "README.md"])

        assert "python" in result["domains"]
        assert "javascript" in result["domains"]
        assert "owasp" in result["domains"]
        assert "app.py" in result["per_file_domains"]
        assert "python" in result["per_file_domains"]["app.py"]


# ===========================================================================
# TestReviewReporter
# ===========================================================================


class TestReviewReporter:
    """Tests for ReviewReporter."""

    def test_generate_report_structure(self, tmp_path: Path) -> None:
        reporter = ReviewReporter(tmp_path)
        context = {
            "files": [
                {"path": "app.py", "hunks": "+new line", "extension": ".py"},
            ],
            "total_files": 1,
            "truncated": False,
        }
        rules = {
            "domains": {"python", "owasp"},
            "rules_summary": "Security rules here.",
            "per_file_domains": {"app.py": ["python", "owasp"]},
        }

        report = reporter.generate_report(context, rules, "feat/auth")

        assert "# Pre-Review Context: feat/auth" in report
        assert "## Changed Files (1)" in report
        assert "app.py" in report
        assert "```diff" in report
        assert "+new line" in report
        assert "## Security Rules Summary" in report
        assert "## Review Instructions" in report

    def test_save_report_creates_file(self, tmp_path: Path) -> None:
        reporter = ReviewReporter(tmp_path)
        report_path = reporter.save_report("# Report", "feat/test")

        assert report_path.exists()
        assert report_path.read_text() == "# Report"
        assert ".zerg/review-reports" in str(report_path)
        assert "feat_test" in report_path.name

    def test_save_report_path_within_project(self, tmp_path: Path) -> None:
        reporter = ReviewReporter(tmp_path)
        report_path = reporter.save_report("content", "my-branch")

        assert report_path.resolve().is_relative_to(tmp_path.resolve())


# ===========================================================================
# TestPreReviewEngine
# ===========================================================================


class TestPreReviewEngine:
    """Tests for PreReviewEngine."""

    def test_full_run_success(self, tmp_path: Path) -> None:
        runner = _make_runner()
        runner.repo_path = tmp_path
        runner.current_branch.return_value = "feat/review"

        # Sequence: changed files, then one hunk per file
        runner._run.side_effect = [
            MagicMock(stdout="src/app.py\n"),
            MagicMock(stdout="+added line\n"),
        ]

        config = GitConfig()
        engine = PreReviewEngine(runner, config)
        result = engine.run("main")

        assert result == 0
        reports = list((tmp_path / ".zerg" / "review-reports").glob("*.md"))
        assert len(reports) == 1
        content = reports[0].read_text()
        assert "src/app.py" in content

    def test_run_with_focus_filter(self, tmp_path: Path) -> None:
        runner = _make_runner()
        runner.repo_path = tmp_path
        runner.current_branch.return_value = "feat/secure"

        runner._run.side_effect = [
            MagicMock(stdout="app.py\nindex.js\n"),
            MagicMock(stdout="diff py"),
            MagicMock(stdout="diff js"),
        ]

        config = GitConfig()
        engine = PreReviewEngine(runner, config)
        result = engine.run("main", focus="python")

        assert result == 0
        reports = list((tmp_path / ".zerg" / "review-reports").glob("*.md"))
        assert len(reports) == 1

    def test_run_no_changes_returns_1(self) -> None:
        runner = _make_runner("")
        runner.repo_path = Path("/fake/repo")

        config = GitConfig()
        engine = PreReviewEngine(runner, config)
        result = engine.run("main")

        assert result == 1
