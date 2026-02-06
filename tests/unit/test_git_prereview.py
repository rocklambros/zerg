"""Tests for pre-review context assembly."""

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


def _make_runner(stdout: str = "", returncode: int = 0) -> MagicMock:
    runner = MagicMock(spec=GitRunner)
    result = MagicMock()
    result.stdout = stdout
    result.returncode = returncode
    runner._run.return_value = result
    runner.repo_path = Path("/fake/repo")
    runner.current_branch.return_value = "feat/test"
    return runner


class TestContextPreparer:
    def test_get_changed_files(self) -> None:
        runner = _make_runner("src/app.py\nREADME.md\n")
        files = ContextPreparer(runner).get_changed_files("main")
        assert files == ["src/app.py", "README.md"]

    def test_prepare_context(self) -> None:
        runner = _make_runner()
        runner._run.side_effect = [
            MagicMock(stdout="a.py\nb.js\n"),
            MagicMock(stdout="diff a"),
            MagicMock(stdout="diff b"),
        ]
        ctx = ContextPreparer(runner).prepare_context("main", budget_chars=4000)
        assert ctx["total_files"] == 2 and len(ctx["files"]) == 2

    def test_prepare_context_no_changes(self) -> None:
        ctx = ContextPreparer(_make_runner("")).prepare_context("main")
        assert ctx == {"files": [], "total_files": 0, "truncated": False}


class TestDomainFilter:
    def test_get_domains_for_extensions(self) -> None:
        df = DomainFilter(rules_dir=Path("/nonexistent"))
        assert "python" in df.get_domains_for_extension(".py")
        assert "javascript" in df.get_domains_for_extension(".js")
        assert df.get_domains_for_extension(".rs") == ["owasp"]

    def test_filter_for_files_combines(self) -> None:
        df = DomainFilter(rules_dir=Path("/nonexistent"))
        result = df.filter_for_files(["app.py", "index.js"])
        assert "python" in result["domains"] and "javascript" in result["domains"]

    def test_get_rules_summary(self, tmp_path: Path) -> None:
        core_dir = tmp_path / "_core"
        core_dir.mkdir()
        (core_dir / "owasp-2025.md").write_text(
            "# OWASP\n\n## Quick Reference\n\n| Rule | Level |\n|------|-------|\n| A01 | strict |\n\n## Version\nv1\n"
        )
        summary = DomainFilter(rules_dir=tmp_path).get_rules_summary(["owasp"])
        assert "Quick Reference" in summary


class TestReviewReporter:
    def test_generate_and_save(self, tmp_path: Path) -> None:
        reporter = ReviewReporter(tmp_path)
        context = {
            "files": [{"path": "app.py", "hunks": "+new", "extension": ".py"}],
            "total_files": 1,
            "truncated": False,
        }
        rules = {"domains": {"python"}, "rules_summary": "Rules.", "per_file_domains": {"app.py": ["python"]}}
        report = reporter.generate_report(context, rules, "feat/auth")
        assert "# Pre-Review Context: feat/auth" in report
        path = reporter.save_report("# Report", "feat/test")
        assert path.exists()


class TestPreReviewEngine:
    def test_full_run(self, tmp_path: Path) -> None:
        runner = _make_runner()
        runner.repo_path = tmp_path
        runner.current_branch.return_value = "feat/review"
        runner._run.side_effect = [MagicMock(stdout="src/app.py\n"), MagicMock(stdout="+added\n")]
        assert PreReviewEngine(runner, GitConfig()).run("main") == 0

    def test_no_changes(self) -> None:
        runner = _make_runner("")
        runner.repo_path = Path("/fake/repo")
        assert PreReviewEngine(runner, GitConfig()).run("main") == 1
