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
from zerg.git.types import RescueSnapshot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_git(*args: str, cwd: Path) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _make_commit(repo: Path, filename: str = "file.txt", msg: str = "commit") -> str:
    """Create a file and commit it, returning the commit SHA."""
    (repo / filename).write_text(f"content-{filename}\n")
    _run_git("add", "-A", cwd=repo)
    _run_git("commit", "-q", "-m", msg, cwd=repo)
    return _run_git("rev-parse", "HEAD", cwd=repo)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


class TestValidation:
    """Tests for name and path validation helpers."""

    def test_validate_name_accepts_valid(self) -> None:
        _validate_name("main", "branch")
        _validate_name("feature/foo-bar", "branch")
        _validate_name("zerg-snapshot-20260201T120000", "tag")
        _validate_name("v1.2.3", "tag")

    def test_validate_name_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="Invalid"):
            _validate_name("", "branch")

    def test_validate_name_rejects_special_chars(self) -> None:
        with pytest.raises(ValueError, match="Invalid"):
            _validate_name("branch;rm -rf /", "branch")

    def test_validate_name_rejects_leading_dot(self) -> None:
        with pytest.raises(ValueError, match="Invalid"):
            _validate_name(".hidden", "branch")

    def test_validate_path_within_project(self, tmp_path: Path) -> None:
        valid = tmp_path / "subdir" / "file.log"
        result = _validate_path_within_project(valid, tmp_path)
        assert result.is_relative_to(tmp_path)

    def test_validate_path_rejects_escape(self, tmp_path: Path) -> None:
        escaped = tmp_path / ".." / "outside" / "file.log"
        with pytest.raises(ValueError, match="outside project root"):
            _validate_path_within_project(escaped, tmp_path)


# ---------------------------------------------------------------------------
# OperationLogger
# ---------------------------------------------------------------------------


class TestOperationLogger:
    """Tests for OperationLogger JSON-lines logging."""

    def test_log_and_read(self, tmp_path: Path) -> None:
        log_path = tmp_path / ".zerg" / "git-ops.log"
        logger = OperationLogger(log_path, project_root=tmp_path)

        logger.log_operation("merge", "main", "abc123", "Merged feature")
        logger.log_operation("snapshot", "dev", "def456", "Pre-deploy snapshot")

        entries = logger.get_recent(10)
        assert len(entries) == 2
        assert entries[0]["operation"] == "merge"
        assert entries[1]["branch"] == "dev"
        assert "timestamp" in entries[0]

    def test_get_recent_limits_count(self, tmp_path: Path) -> None:
        log_path = tmp_path / "ops.log"
        logger = OperationLogger(log_path)

        for i in range(10):
            logger.log_operation("op", "main", f"sha{i}", f"desc {i}")

        recent = logger.get_recent(3)
        assert len(recent) == 3
        assert recent[-1]["commit"] == "sha9"

    def test_get_recent_empty_file(self, tmp_path: Path) -> None:
        log_path = tmp_path / "empty.log"
        logger = OperationLogger(log_path)
        assert logger.get_recent() == []

    def test_get_recent_skips_malformed_lines(self, tmp_path: Path) -> None:
        log_path = tmp_path / "bad.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text('{"valid": true}\nnot json\n{"also": "valid"}\n')

        logger = OperationLogger(log_path)
        entries = logger.get_recent()
        assert len(entries) == 2

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        log_path = tmp_path / "deep" / "nested" / "ops.log"
        logger = OperationLogger(log_path)
        logger.log_operation("test", "main", "abc", "test")
        assert log_path.exists()


# ---------------------------------------------------------------------------
# SnapshotManager
# ---------------------------------------------------------------------------


class TestSnapshotManager:
    """Tests for SnapshotManager tag-based snapshots."""

    def test_create_snapshot(self, tmp_repo: Path) -> None:
        runner = GitRunner(tmp_repo)
        config = GitRescueConfig(max_snapshots=5)
        mgr = SnapshotManager(runner, config)

        snap = mgr.create_snapshot("merge", "Before merge")
        assert snap.tag.startswith("zerg-snapshot-")
        assert snap.branch == "main" or snap.branch == "master"
        assert len(snap.commit) == 40
        assert snap.operation == "merge"

        # Tag should exist in git
        tags = _run_git("tag", "--list", "zerg-snapshot-*", cwd=tmp_repo)
        assert snap.tag in tags

    def test_list_snapshots(self, tmp_repo: Path) -> None:
        runner = GitRunner(tmp_repo)
        config = GitRescueConfig(max_snapshots=10)
        mgr = SnapshotManager(runner, config)

        mgr.create_snapshot("op1", "first")
        time.sleep(1.1)  # ensure distinct timestamps
        mgr.create_snapshot("op2", "second")

        snapshots = mgr.list_snapshots()
        assert len(snapshots) == 2
        assert all(isinstance(s, RescueSnapshot) for s in snapshots)
        # Sorted by timestamp
        assert snapshots[0].timestamp <= snapshots[1].timestamp

    def test_list_snapshots_empty(self, tmp_repo: Path) -> None:
        runner = GitRunner(tmp_repo)
        config = GitRescueConfig()
        mgr = SnapshotManager(runner, config)
        assert mgr.list_snapshots() == []

    def test_restore_snapshot(self, tmp_repo: Path) -> None:
        runner = GitRunner(tmp_repo)
        config = GitRescueConfig()
        mgr = SnapshotManager(runner, config)

        original_commit = runner.current_commit()
        snap = mgr.create_snapshot("test", "test snapshot")
        _make_commit(tmp_repo, "new_file.txt", "diverge")

        mgr.restore_snapshot(snap.tag)
        # HEAD should now point at snapshot commit
        head = _run_git("rev-parse", "HEAD", cwd=tmp_repo)
        assert head == original_commit

    def test_restore_invalid_tag_rejected(self, tmp_repo: Path) -> None:
        runner = GitRunner(tmp_repo)
        config = GitRescueConfig()
        mgr = SnapshotManager(runner, config)

        with pytest.raises(ValueError, match="Not a zerg snapshot"):
            mgr.restore_snapshot("some-other-tag")

    def test_restore_malicious_tag_rejected(self, tmp_repo: Path) -> None:
        runner = GitRunner(tmp_repo)
        config = GitRescueConfig()
        mgr = SnapshotManager(runner, config)

        with pytest.raises(ValueError, match="Invalid"):
            mgr.restore_snapshot("; rm -rf /")

    def test_prune_snapshots(self, tmp_repo: Path) -> None:
        runner = GitRunner(tmp_repo)
        config = GitRescueConfig(max_snapshots=2)
        mgr = SnapshotManager(runner, config)

        # Create 4 snapshots with distinct timestamps
        for i in range(4):
            _make_commit(tmp_repo, f"file{i}.txt", f"commit {i}")
            mgr.create_snapshot(f"op{i}", f"snap {i}")
            time.sleep(1.1)

        assert len(mgr.list_snapshots()) == 4
        deleted = mgr.prune_snapshots()
        assert deleted == 2
        remaining = mgr.list_snapshots()
        assert len(remaining) == 2

    def test_prune_noop_when_under_limit(self, tmp_repo: Path) -> None:
        runner = GitRunner(tmp_repo)
        config = GitRescueConfig(max_snapshots=10)
        mgr = SnapshotManager(runner, config)

        mgr.create_snapshot("op", "snap")
        assert mgr.prune_snapshots() == 0


# ---------------------------------------------------------------------------
# RescueEngine
# ---------------------------------------------------------------------------


class TestRescueEngine:
    """Tests for RescueEngine high-level operations."""

    def _make_engine(self, repo: Path) -> RescueEngine:
        runner = GitRunner(repo)
        config = GitConfig()
        return RescueEngine(runner, config)

    def test_auto_snapshot_creates_when_enabled(self, tmp_repo: Path) -> None:
        engine = self._make_engine(tmp_repo)
        snap = engine.auto_snapshot("merge")
        assert snap is not None
        assert snap.tag.startswith("zerg-snapshot-")

    def test_auto_snapshot_skips_when_disabled(self, tmp_repo: Path) -> None:
        runner = GitRunner(tmp_repo)
        config = GitConfig(rescue=GitRescueConfig(auto_snapshot=False))
        engine = RescueEngine(runner, config)
        assert engine.auto_snapshot("merge") is None

    def test_list_operations_after_auto_snapshot(self, tmp_repo: Path) -> None:
        engine = self._make_engine(tmp_repo)
        engine.auto_snapshot("deploy")
        ops = engine.list_operations()
        assert len(ops) == 1
        assert ops[0]["operation"] == "snapshot"

    def test_undo_last(self, tmp_repo: Path) -> None:
        engine = self._make_engine(tmp_repo)
        original = _run_git("rev-parse", "HEAD", cwd=tmp_repo)

        engine.auto_snapshot("change")
        _make_commit(tmp_repo, "after.txt", "after snapshot")

        result = engine.undo_last()
        assert result is True
        current = _run_git("rev-parse", "HEAD", cwd=tmp_repo)
        assert current == original

    def test_undo_last_no_snapshots(self, tmp_repo: Path) -> None:
        engine = self._make_engine(tmp_repo)
        assert engine.undo_last() is False

    def test_recover_branch(self, tmp_repo: Path) -> None:
        GitRunner(tmp_repo)
        engine = self._make_engine(tmp_repo)

        # Create and delete a branch
        _run_git("checkout", "-b", "feature/recover-me", cwd=tmp_repo)
        _make_commit(tmp_repo, "feature.txt", "feature work")
        _run_git("checkout", "main", cwd=tmp_repo)
        _run_git("branch", "-D", "feature/recover-me", cwd=tmp_repo)

        result = engine.recover_branch("feature/recover-me")
        assert result is True

        # Branch should exist again
        branches = _run_git("branch", "--list", "feature/recover-me", cwd=tmp_repo)
        assert "feature/recover-me" in branches

    def test_recover_branch_not_found(self, tmp_repo: Path) -> None:
        engine = self._make_engine(tmp_repo)
        assert engine.recover_branch("nonexistent-branch-xyz") is False

    def test_run_dispatch_list(self, tmp_repo: Path) -> None:
        engine = self._make_engine(tmp_repo)
        engine.auto_snapshot("test")
        assert engine.run("list") == 0

    def test_run_dispatch_undo(self, tmp_repo: Path) -> None:
        engine = self._make_engine(tmp_repo)
        engine.auto_snapshot("test")
        _make_commit(tmp_repo, "x.txt", "x")
        assert engine.run("undo") == 0

    def test_run_dispatch_unknown(self, tmp_repo: Path) -> None:
        engine = self._make_engine(tmp_repo)
        assert engine.run("invalid-action") == 1

    def test_run_restore_missing_tag(self, tmp_repo: Path) -> None:
        engine = self._make_engine(tmp_repo)
        assert engine.run("restore") == 1

    def test_run_recover_branch_missing_name(self, tmp_repo: Path) -> None:
        engine = self._make_engine(tmp_repo)
        assert engine.run("recover-branch") == 1
