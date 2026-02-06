"""Tests for zerg.git.rescue -- triple-layer undo/recovery system."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from zerg.git.base import GitRunner
from zerg.git.config import GitConfig, GitRescueConfig
from zerg.git.rescue import (
    OperationLogger,
    RescueEngine,
    SnapshotManager,
    _validate_name,
    _validate_path_within_project,
)


def _run_git(*args: str, cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _make_commit(repo: Path, filename: str = "file.txt", msg: str = "commit") -> str:
    (repo / filename).write_text(f"content-{filename}\n")
    _run_git("add", "-A", cwd=repo)
    _run_git("commit", "-q", "-m", msg, cwd=repo)
    return _run_git("rev-parse", "HEAD", cwd=repo)


class TestValidation:
    def test_validate_name(self) -> None:
        _validate_name("main", "branch")
        _validate_name("feature/foo-bar", "branch")
        with pytest.raises(ValueError, match="Invalid"):
            _validate_name("", "branch")
        with pytest.raises(ValueError, match="Invalid"):
            _validate_name("branch;rm -rf /", "branch")

    def test_validate_path(self, tmp_path: Path) -> None:
        result = _validate_path_within_project(tmp_path / "sub" / "f.log", tmp_path)
        assert result.is_relative_to(tmp_path)
        with pytest.raises(ValueError, match="outside project root"):
            _validate_path_within_project(tmp_path / ".." / "outside" / "f.log", tmp_path)


class TestOperationLogger:
    def test_log_and_read(self, tmp_path: Path) -> None:
        logger = OperationLogger(tmp_path / ".zerg" / "git-ops.log", project_root=tmp_path)
        logger.log_operation("merge", "main", "abc123", "Merged feature")
        logger.log_operation("snapshot", "dev", "def456", "Pre-deploy")
        entries = logger.get_recent(10)
        assert len(entries) == 2 and entries[0]["operation"] == "merge"

    def test_get_recent_empty(self, tmp_path: Path) -> None:
        assert OperationLogger(tmp_path / "empty.log").get_recent() == []


class TestSnapshotManager:
    def test_create_and_list(self, tmp_repo: Path) -> None:
        mgr = SnapshotManager(GitRunner(tmp_repo), GitRescueConfig(max_snapshots=5))
        snap = mgr.create_snapshot("merge", "Before merge")
        assert snap.tag.startswith("zerg-snapshot-") and len(snap.commit) == 40
        assert len(mgr.list_snapshots()) == 1

    def test_restore_snapshot(self, tmp_repo: Path) -> None:
        runner = GitRunner(tmp_repo)
        mgr = SnapshotManager(runner, GitRescueConfig())
        original = runner.current_commit()
        snap = mgr.create_snapshot("test", "snapshot")
        _make_commit(tmp_repo, "new.txt", "diverge")
        mgr.restore_snapshot(snap.tag)
        assert _run_git("rev-parse", "HEAD", cwd=tmp_repo) == original

    def test_restore_invalid_tag(self, tmp_repo: Path) -> None:
        mgr = SnapshotManager(GitRunner(tmp_repo), GitRescueConfig())
        with pytest.raises(ValueError, match="Not a zerg snapshot"):
            mgr.restore_snapshot("some-other-tag")

    def test_prune(self, tmp_repo: Path) -> None:
        mgr = SnapshotManager(GitRunner(tmp_repo), GitRescueConfig(max_snapshots=2))
        for i in range(4):
            _make_commit(tmp_repo, f"file{i}.txt", f"commit {i}")
            mgr.create_snapshot(f"op{i}", f"snap {i}")
            time.sleep(1.1)
        assert mgr.prune_snapshots() == 2 and len(mgr.list_snapshots()) == 2


class TestRescueEngine:
    def _make_engine(self, repo: Path) -> RescueEngine:
        return RescueEngine(GitRunner(repo), GitConfig())

    def test_auto_snapshot(self, tmp_repo: Path) -> None:
        snap = self._make_engine(tmp_repo).auto_snapshot("merge")
        assert snap is not None and snap.tag.startswith("zerg-snapshot-")

    def test_undo_last(self, tmp_repo: Path) -> None:
        engine = self._make_engine(tmp_repo)
        original = _run_git("rev-parse", "HEAD", cwd=tmp_repo)
        engine.auto_snapshot("change")
        _make_commit(tmp_repo, "after.txt", "after snapshot")
        assert engine.undo_last() is True
        assert _run_git("rev-parse", "HEAD", cwd=tmp_repo) == original

    def test_undo_no_snapshots(self, tmp_repo: Path) -> None:
        assert self._make_engine(tmp_repo).undo_last() is False

    def test_run_dispatch(self, tmp_repo: Path) -> None:
        engine = self._make_engine(tmp_repo)
        engine.auto_snapshot("test")
        assert engine.run("list") == 0
        assert engine.run("invalid-action") == 1
