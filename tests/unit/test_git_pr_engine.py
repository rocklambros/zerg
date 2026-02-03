"""Tests for zerg.git.pr_engine -- AI-powered PR creation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from zerg.git.config import GitConfig, GitPRConfig
from zerg.git.pr_engine import (
    ContextAssembler,
    PRContext,
    PRCreator,
    PREngine,
    PRGenerator,
    _parse_commit_type,
    _sanitize_pr_content,
)
from zerg.git.types import CommitInfo, CommitType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_runner(
    repo_path: Path | None = None,
    log_output: str = "",
    branch: str = "feat/test",
) -> MagicMock:
    """Build a mock GitRunner with controlled output."""
    runner = MagicMock()
    runner.repo_path = repo_path or Path("/fake/repo")

    def _run_side_effect(*args, **kwargs):
        result = MagicMock(spec=subprocess.CompletedProcess)
        result.returncode = 0
        joined = " ".join(args)
        if "log" in joined:
            result.stdout = log_output
        elif "rev-parse" in joined and "--abbrev-ref" in joined:
            result.stdout = branch
        else:
            result.stdout = ""
        return result

    runner._run.side_effect = _run_side_effect
    return runner


def _commit(
    sha: str = "abc1234",
    message: str = "feat: add login",
    author: str = "Test User",
    date: str = "2026-01-15 10:00:00 +0000",
    files: tuple[str, ...] = ("src/auth.py",),
    commit_type: CommitType | None = CommitType.FEAT,
) -> CommitInfo:
    """Convenience factory for CommitInfo."""
    return CommitInfo(
        sha=sha,
        message=message,
        author=author,
        date=date,
        files=files,
        commit_type=commit_type,
    )


def _context(
    commits: list[CommitInfo] | None = None,
    issues: list[dict] | None = None,
) -> PRContext:
    """Convenience factory for PRContext."""
    return PRContext(
        commits=commits or [],
        issues=issues or [],
    )


# ===========================================================================
# Utility functions
# ===========================================================================


class TestSanitizePRContent:
    """Tests for _sanitize_pr_content."""

    def test_strips_script_tags(self):
        assert "<script>" not in _sanitize_pr_content("<script>alert(1)</script>")

    def test_strips_iframe_tags(self):
        assert "<iframe>" not in _sanitize_pr_content("<iframe src='evil'></iframe>")

    def test_escapes_triple_backticks(self):
        result = _sanitize_pr_content("```injected```")
        assert "\\```" in result

    def test_passes_normal_text(self):
        text = "feat: add user authentication"
        assert _sanitize_pr_content(text) == text


class TestParseCommitType:
    """Tests for _parse_commit_type."""

    def test_feat(self):
        assert _parse_commit_type("feat: add login") == CommitType.FEAT

    def test_fix_with_scope(self):
        assert _parse_commit_type("fix(auth): resolve token issue") == CommitType.FIX

    def test_nonconventional_returns_none(self):
        assert _parse_commit_type("random commit message") is None

    def test_docs(self):
        assert _parse_commit_type("docs: update README") == CommitType.DOCS


# ===========================================================================
# ContextAssembler
# ===========================================================================


class TestContextAssembler:
    """Tests for ContextAssembler."""

    def test_assemble_diffs_only(self):
        """With context_depth='diffs', only commits are gathered."""
        log_out = "abc123|||feat: add auth|||Alice|||2026-01-15 10:00:00\n\nsrc/auth.py\n"
        runner = _make_runner(log_output=log_out)
        config = GitPRConfig(context_depth="diffs")
        assembler = ContextAssembler()

        ctx = assembler.assemble(runner, config, "main")

        assert len(ctx.commits) == 1
        assert ctx.commits[0].sha == "abc123"
        assert ctx.commits[0].message == "feat: add auth"
        assert ctx.issues == []
        assert ctx.specs == []

    @patch("zerg.git.pr_engine.subprocess.run")
    def test_assemble_with_issues(self, mock_run):
        """With context_depth='issues', commits and issues are gathered."""
        log_out = "abc123|||fix: patch bug|||Bob|||2026-01-15\n\nsrc/bug.py\n"
        runner = _make_runner(log_output=log_out)
        config = GitPRConfig(context_depth="issues")

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([{"number": 42, "title": "Bug report", "state": "OPEN"}]),
        )

        assembler = ContextAssembler()
        ctx = assembler.assemble(runner, config, "main")

        assert len(ctx.commits) == 1
        assert len(ctx.issues) == 1
        assert ctx.issues[0]["number"] == 42

    @patch("zerg.git.pr_engine.subprocess.run")
    def test_assemble_full_context(self, mock_run, tmp_path):
        """With context_depth='full', commits, issues, specs, and CLAUDE.md gathered."""
        log_out = "abc|||feat: full|||Dev|||2026-01-15\n\nsrc/app.py\n"
        runner = _make_runner(repo_path=tmp_path, log_output=log_out)

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([{"number": 1, "title": "Issue", "state": "OPEN"}]),
        )

        # Create CLAUDE.md
        (tmp_path / "CLAUDE.md").write_text("# Project\nInstructions here.")

        # Create .gsd/specs/
        specs_dir = tmp_path / ".gsd" / "specs"
        specs_dir.mkdir(parents=True)
        (specs_dir / "auth.md").write_text("Auth spec")
        (specs_dir / "api.md").write_text("API spec")

        assembler = ContextAssembler()
        config = GitPRConfig(context_depth="full")
        ctx = assembler.assemble(runner, config, "main")

        assert len(ctx.commits) == 1
        assert len(ctx.issues) == 1
        assert ctx.claude_md is not None
        assert "Project" in ctx.claude_md
        assert sorted(ctx.specs) == ["api.md", "auth.md"]

    @patch("zerg.git.pr_engine.subprocess.run", side_effect=FileNotFoundError)
    def test_gh_not_available_graceful(self, mock_run):
        """Missing gh CLI does not crash; issues are empty."""
        log_out = "abc|||feat: test|||Dev|||2026-01-15\n\nsrc/x.py\n"
        runner = _make_runner(log_output=log_out)
        config = GitPRConfig(context_depth="issues")

        assembler = ContextAssembler()
        ctx = assembler.assemble(runner, config, "main")

        assert len(ctx.commits) == 1
        assert ctx.issues == []


# ===========================================================================
# PRGenerator
# ===========================================================================


class TestPRGenerator:
    """Tests for PRGenerator."""

    def setup_method(self):
        self.generator = PRGenerator()

    def test_generate_title_single_feat_commit(self):
        """Single feat commit uses its message as title."""
        ctx = _context(commits=[_commit(message="feat: add authentication system")])
        config = GitPRConfig()

        result = self.generator.generate(ctx, config)

        assert result["title"] == "feat: add authentication system"

    def test_generate_title_multiple_commits_dominant_type(self):
        """Multiple commits use dominant type for title."""
        commits = [
            _commit(sha="a", message="feat: add login", commit_type=CommitType.FEAT),
            _commit(sha="b", message="feat: add signup", commit_type=CommitType.FEAT),
            _commit(sha="c", message="fix: typo", commit_type=CommitType.FIX),
        ]
        ctx = _context(commits=commits)
        config = GitPRConfig()

        result = self.generator.generate(ctx, config)

        assert result["title"].startswith("feat:")

    def test_generate_body_structure(self):
        """Generated body contains expected markdown sections."""
        ctx = _context(
            commits=[_commit(files=("src/auth.py", "tests/test_auth.py"))],
            issues=[{"number": 10, "title": "Auth needed", "state": "OPEN"}],
        )
        config = GitPRConfig()

        result = self.generator.generate(ctx, config)
        body = result["body"]

        assert "## Summary" in body
        assert "## Changes" in body
        assert "## Test Plan" in body
        assert "## Linked Issues" in body
        assert "#10" in body

    def test_auto_labels_feat(self):
        """Feat commits produce 'enhancement' label."""
        ctx = _context(commits=[_commit(commit_type=CommitType.FEAT)])
        config = GitPRConfig(auto_label=True)

        result = self.generator.generate(ctx, config)

        assert "enhancement" in result["labels"]

    def test_auto_labels_fix(self):
        """Fix commits produce 'bug' label."""
        ctx = _context(commits=[_commit(commit_type=CommitType.FIX)])
        config = GitPRConfig(auto_label=True)

        result = self.generator.generate(ctx, config)

        assert "bug" in result["labels"]

    def test_auto_labels_disabled(self):
        """With auto_label=False, no labels are generated."""
        ctx = _context(commits=[_commit(commit_type=CommitType.FEAT)])
        config = GitPRConfig(auto_label=False)

        result = self.generator.generate(ctx, config)

        assert result["labels"] == []

    def test_size_warning_triggered(self):
        """Size warning appears when file count exceeds threshold."""
        many_files = tuple(f"src/file_{i}.py" for i in range(500))
        ctx = _context(commits=[_commit(files=many_files)])
        config = GitPRConfig(size_warning_loc=400)

        result = self.generator.generate(ctx, config)

        assert "Warning" in result["body"]
        assert "500" in result["body"]

    def test_reviewer_from_commit_authors(self):
        """Reviewers are suggested from commit authors."""
        commits = [
            _commit(sha="a", author="Alice"),
            _commit(sha="b", author="Bob"),
            _commit(sha="c", author="Alice"),  # duplicate
        ]
        ctx = _context(commits=commits)
        config = GitPRConfig(reviewer_suggestion=True)

        result = self.generator.generate(ctx, config)

        assert "Alice" in result["reviewers"]
        assert "Bob" in result["reviewers"]
        # No duplicates
        assert len([r for r in result["reviewers"] if r == "Alice"]) == 1


# ===========================================================================
# PRCreator
# ===========================================================================


class TestPRCreator:
    """Tests for PRCreator."""

    @patch("zerg.git.pr_engine.subprocess.run")
    def test_create_success(self, mock_run):
        """Successful gh pr create returns url and number."""
        mock_run.return_value = MagicMock(
            stdout="https://github.com/owner/repo/pull/42\n",
            returncode=0,
        )
        runner = _make_runner()
        creator = PRCreator()

        result = creator.create(
            runner,
            {"title": "feat: test", "body": "body", "labels": [], "reviewers": []},
        )

        assert result["url"] == "https://github.com/owner/repo/pull/42"
        assert result["number"] == 42

    @patch("zerg.git.pr_engine.subprocess.run")
    def test_create_draft_mode(self, mock_run):
        """Draft flag is passed to gh pr create."""
        mock_run.return_value = MagicMock(
            stdout="https://github.com/owner/repo/pull/99\n",
            returncode=0,
        )
        runner = _make_runner()
        creator = PRCreator()

        creator.create(
            runner,
            {"title": "feat: draft", "body": "body", "labels": [], "reviewers": []},
            draft=True,
        )

        call_args = mock_run.call_args[0][0]
        assert "--draft" in call_args

    @patch("zerg.git.pr_engine.subprocess.run", side_effect=FileNotFoundError)
    def test_gh_not_available_saves_to_file(self, mock_run, tmp_path):
        """When gh is missing, PR body is saved to draft file."""
        runner = _make_runner(repo_path=tmp_path, branch="feat/my-feature")
        creator = PRCreator()

        result = creator.create(
            runner,
            {"title": "feat: offline", "body": "PR body here", "labels": [], "reviewers": []},
        )

        assert "path" in result
        draft_path = Path(result["path"])
        assert draft_path.exists()
        content = draft_path.read_text()
        assert "feat: offline" in content
        assert "PR body here" in content


# ===========================================================================
# PREngine
# ===========================================================================


class TestPREngine:
    """Tests for PREngine orchestration."""

    @patch("zerg.git.pr_engine.subprocess.run")
    def test_full_run_success(self, mock_subprocess):
        """Full run: assemble -> generate -> create returns 0."""
        log_out = "abc123|||feat: add feature|||Dev|||2026-01-15\n\nsrc/feature.py\n"
        runner = _make_runner(log_output=log_out)
        config = GitConfig()

        # Mock gh issue list (for context assembly)
        # and gh pr create (for PR creation)
        def subprocess_side_effect(cmd, **kwargs):
            result = MagicMock()
            if "issue" in cmd:
                result.returncode = 0
                result.stdout = json.dumps([])
            elif "pr" in cmd:
                result.returncode = 0
                result.stdout = "https://github.com/owner/repo/pull/1\n"
            else:
                result.returncode = 0
                result.stdout = ""
            return result

        mock_subprocess.side_effect = subprocess_side_effect

        engine = PREngine(runner, config)
        exit_code = engine.run(base_branch="main")

        assert exit_code == 0
        assert engine.result is not None
        assert "url" in engine.result

    def test_run_with_no_commits_returns_1(self):
        """No commits between base and HEAD returns exit code 1."""
        runner = _make_runner(log_output="")
        config = GitConfig()

        engine = PREngine(runner, config)
        exit_code = engine.run(base_branch="main")

        assert exit_code == 1

    @patch("zerg.git.pr_engine.subprocess.run")
    def test_run_with_explicit_reviewer(self, mock_subprocess):
        """Explicit reviewer is added to PR data."""
        log_out = "abc|||feat: test|||Dev|||2026-01-15\n\nsrc/x.py\n"
        runner = _make_runner(log_output=log_out)
        config = GitConfig()

        mock_subprocess.side_effect = lambda cmd, **kw: MagicMock(
            returncode=0,
            stdout="https://github.com/owner/repo/pull/5\n" if "pr" in cmd else json.dumps([]),
        )

        engine = PREngine(runner, config)
        exit_code = engine.run(base_branch="main", reviewer="alice")

        assert exit_code == 0
        # Verify reviewer was passed to gh pr create
        pr_create_calls = [c for c in mock_subprocess.call_args_list if "pr" in c[0][0]]
        assert pr_create_calls
        call_cmd = pr_create_calls[0][0][0]
        assert "--reviewer" in call_cmd
        assert "alice" in call_cmd
