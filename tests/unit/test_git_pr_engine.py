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


def _make_runner(repo_path=None, log_output="", branch="feat/test") -> MagicMock:
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
    sha="abc1234", message="feat: add login", author="Test User", files=("src/auth.py",), commit_type=CommitType.FEAT
) -> CommitInfo:
    return CommitInfo(
        sha=sha, message=message, author=author, date="2026-01-15 10:00:00 +0000", files=files, commit_type=commit_type
    )


def _context(commits=None, issues=None) -> PRContext:
    return PRContext(commits=commits or [], issues=issues or [])


class TestUtilities:
    def test_sanitize_pr_content(self):
        assert "<script>" not in _sanitize_pr_content("<script>alert(1)</script>")
        assert _sanitize_pr_content("normal text") == "normal text"

    def test_parse_commit_type(self):
        assert _parse_commit_type("feat: add login") == CommitType.FEAT
        assert _parse_commit_type("fix(auth): bug") == CommitType.FIX
        assert _parse_commit_type("random message") is None


class TestContextAssembler:
    def test_assemble_diffs_only(self):
        log_out = "abc123|||feat: add auth|||Alice|||2026-01-15 10:00:00\n\nsrc/auth.py\n"
        runner = _make_runner(log_output=log_out)
        ctx = ContextAssembler().assemble(runner, GitPRConfig(context_depth="diffs"), "main")
        assert len(ctx.commits) == 1 and ctx.issues == []

    @patch("zerg.git.pr_engine.subprocess.run", side_effect=FileNotFoundError)
    def test_gh_not_available(self, mock_run):
        log_out = "abc|||feat: test|||Dev|||2026-01-15\n\nsrc/x.py\n"
        ctx = ContextAssembler().assemble(_make_runner(log_output=log_out), GitPRConfig(context_depth="issues"), "main")
        assert len(ctx.commits) == 1 and ctx.issues == []


class TestPRGenerator:
    def test_generate_title_and_body(self):
        ctx = _context(
            commits=[_commit(files=("src/auth.py", "tests/test_auth.py"))],
            issues=[{"number": 10, "title": "Auth needed", "state": "OPEN"}],
        )
        result = PRGenerator().generate(ctx, GitPRConfig())
        assert result["title"] == "feat: add login"
        assert "## Summary" in result["body"] and "#10" in result["body"]

    def test_auto_labels(self):
        ctx = _context(commits=[_commit(commit_type=CommitType.FEAT)])
        assert "enhancement" in PRGenerator().generate(ctx, GitPRConfig(auto_label=True))["labels"]
        assert PRGenerator().generate(ctx, GitPRConfig(auto_label=False))["labels"] == []


class TestPRCreator:
    @patch("zerg.git.pr_engine.subprocess.run")
    def test_create_success(self, mock_run):
        mock_run.return_value = MagicMock(stdout="https://github.com/owner/repo/pull/42\n", returncode=0)
        result = PRCreator().create(_make_runner(), {"title": "feat: test", "body": "b", "labels": [], "reviewers": []})
        assert result["url"] == "https://github.com/owner/repo/pull/42" and result["number"] == 42

    @patch("zerg.git.pr_engine.subprocess.run", side_effect=FileNotFoundError)
    def test_gh_not_available_saves_draft(self, mock_run, tmp_path):
        runner = _make_runner(repo_path=tmp_path, branch="feat/my-feature")
        result = PRCreator().create(runner, {"title": "feat: off", "body": "body", "labels": [], "reviewers": []})
        assert "path" in result and Path(result["path"]).exists()


class TestPREngine:
    @patch("zerg.git.pr_engine.subprocess.run")
    def test_full_run(self, mock_subprocess):
        log_out = "abc123|||feat: add feature|||Dev|||2026-01-15\n\nsrc/feature.py\n"

        def side_effect(cmd, **kwargs):
            r = MagicMock()
            r.returncode = 0
            r.stdout = "https://github.com/o/r/pull/1\n" if "pr" in cmd else json.dumps([])
            return r

        mock_subprocess.side_effect = side_effect
        engine = PREngine(_make_runner(log_output=log_out), GitConfig())
        assert engine.run(base_branch="main") == 0 and "url" in engine.result

    def test_no_commits_returns_1(self):
        engine = PREngine(_make_runner(log_output=""), GitConfig())
        assert engine.run(base_branch="main") == 1
