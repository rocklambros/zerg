"""Tests for zerg.git.rescue -- triple-layer undo/recovery system."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.exceptions import GitError
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

    def test_get_recent_skips_blank_lines_and_malformed_json(self, tmp_path: Path) -> None:
        """Cover lines 128, 131-133: blank lines skipped, malformed JSON logged and skipped."""
        log_path = tmp_path / "ops.log"
        log_path.write_text(
            '{"operation":"merge","branch":"main","commit":"abc","description":"ok"}\n'
            "\n"
            "NOT VALID JSON\n"
            '{"operation":"snap","branch":"dev","commit":"def","description":"ok2"}\n'
        )
        op_logger = OperationLogger(log_path)
        entries = op_logger.get_recent(10)
        assert len(entries) == 2
        assert entries[0]["operation"] == "merge"
        assert entries[1]["operation"] == "snap"


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

    def test_list_snapshots_giterror_on_resolve(self, tmp_repo: Path) -> None:
        """Cover lines 214-216: GitError when resolving a snapshot tag is caught and skipped."""
        runner = GitRunner(tmp_repo)
        mgr = SnapshotManager(runner, GitRescueConfig(max_snapshots=10))
        # Create a real snapshot so there's a tag
        mgr.create_snapshot("test", "snapshot")
        # Patch _run to raise GitError only on "rev-list" calls (tag resolve)
        original_run = runner._run

        def _patched_run(*args, **kwargs):
            if args and args[0] == "rev-list":
                raise GitError("could not resolve")
            return original_run(*args, **kwargs)

        with patch.object(runner, "_run", side_effect=_patched_run):
            snapshots = mgr.list_snapshots()
        # The tag exists but resolving it fails, so it's skipped
        assert snapshots == []

    def test_prune_no_delete_when_under_max(self, tmp_repo: Path) -> None:
        """Cover line 245: early return 0 when snapshots <= max_snapshots."""
        mgr = SnapshotManager(GitRunner(tmp_repo), GitRescueConfig(max_snapshots=10))
        mgr.create_snapshot("test", "snapshot")
        deleted = mgr.prune_snapshots()
        assert deleted == 0

    def test_prune_giterror_on_tag_delete(self, tmp_repo: Path) -> None:
        """Cover lines 254-255: GitError during tag deletion is caught, continues."""
        runner = GitRunner(tmp_repo)
        mgr = SnapshotManager(runner, GitRescueConfig(max_snapshots=1))
        # Create 3 snapshots to have 2 to delete
        for i in range(3):
            _make_commit(tmp_repo, f"prune{i}.txt", f"commit {i}")
            mgr.create_snapshot(f"op{i}", f"snap {i}")
            time.sleep(1.1)
        # Patch _run to fail on "tag -d" calls
        original_run = runner._run

        def _patched_run(*args, **kwargs):
            if len(args) >= 2 and args[0] == "tag" and args[1] == "-d":
                raise GitError("failed to delete tag")
            return original_run(*args, **kwargs)

        with patch.object(runner, "_run", side_effect=_patched_run):
            deleted = mgr.prune_snapshots()
        # Both deletes failed
        assert deleted == 0


class TestRescueEngine:
    def _make_engine(self, repo: Path) -> RescueEngine:
        return RescueEngine(GitRunner(repo), GitConfig())

    def test_auto_snapshot(self, tmp_repo: Path) -> None:
        snap = self._make_engine(tmp_repo).auto_snapshot("merge")
        assert snap is not None and snap.tag.startswith("zerg-snapshot-")

    def test_auto_snapshot_disabled(self, tmp_repo: Path) -> None:
        """Cover line 293: auto_snapshot returns None when disabled."""
        config = GitConfig(rescue=GitRescueConfig(auto_snapshot=False))
        engine = RescueEngine(GitRunner(tmp_repo), config)
        assert engine.auto_snapshot("merge") is None

    def test_undo_last(self, tmp_repo: Path) -> None:
        engine = self._make_engine(tmp_repo)
        original = _run_git("rev-parse", "HEAD", cwd=tmp_repo)
        engine.auto_snapshot("change")
        _make_commit(tmp_repo, "after.txt", "after snapshot")
        assert engine.undo_last() is True
        assert _run_git("rev-parse", "HEAD", cwd=tmp_repo) == original

    def test_undo_no_snapshots(self, tmp_repo: Path) -> None:
        assert self._make_engine(tmp_repo).undo_last() is False

    def test_undo_last_giterror(self, tmp_repo: Path) -> None:
        """Cover lines 345-347: undo_last returns False when reset raises GitError."""
        engine = self._make_engine(tmp_repo)
        engine.auto_snapshot("change")
        _make_commit(tmp_repo, "after.txt", "after snapshot")
        # Patch _run to raise GitError on "reset" calls
        original_run = engine._runner._run

        def _patched_run(*args, **kwargs):
            if args and args[0] == "reset":
                raise GitError("reset failed")
            return original_run(*args, **kwargs)

        with patch.object(engine._runner, "_run", side_effect=_patched_run):
            result = engine.undo_last()
        assert result is False

    def test_restore_success(self, tmp_repo: Path) -> None:
        """Cover lines 358-367: restore method succeeds and logs operation."""
        engine = self._make_engine(tmp_repo)
        snap = engine.auto_snapshot("test")
        _make_commit(tmp_repo, "new.txt", "diverge")
        assert engine.restore(snap.tag) is True
        # Check the operation was logged
        ops = engine.list_operations()
        restore_ops = [o for o in ops if o["operation"] == "restore"]
        assert len(restore_ops) == 1
        assert snap.tag in restore_ops[0]["description"]

    def test_restore_invalid_tag(self, tmp_repo: Path) -> None:
        """Cover lines 368-370: restore returns False on ValueError (invalid tag)."""
        engine = self._make_engine(tmp_repo)
        result = engine.restore("not-a-zerg-tag")
        assert result is False

    def test_restore_giterror(self, tmp_repo: Path) -> None:
        """Cover lines 368-370: restore returns False on GitError."""
        engine = self._make_engine(tmp_repo)
        snap = engine.auto_snapshot("test")
        # Patch checkout to fail
        original_run = engine._runner._run

        def _patched_run(*args, **kwargs):
            if args and args[0] == "checkout":
                raise GitError("checkout failed")
            return original_run(*args, **kwargs)

        with patch.object(engine._runner, "_run", side_effect=_patched_run):
            result = engine.restore(snap.tag)
        assert result is False

    def test_recover_branch_success(self, tmp_repo: Path) -> None:
        """Cover lines 384-416: recover_branch finds branch in reflog and recreates it."""
        # Create and delete a branch
        _run_git("checkout", "-b", "feature-recover", cwd=tmp_repo)
        _make_commit(tmp_repo, "feat.txt", "feature work")
        _run_git("checkout", "main", cwd=tmp_repo)
        _run_git("branch", "-D", "feature-recover", cwd=tmp_repo)

        engine = self._make_engine(tmp_repo)
        result = engine.recover_branch("feature-recover")
        assert result is True
        # Branch should be recreated
        branches = _run_git("branch", cwd=tmp_repo)
        assert "feature-recover" in branches

    def test_recover_branch_not_found(self, tmp_repo: Path) -> None:
        """Cover lines 404-406: recover_branch returns False when branch not in reflog."""
        engine = self._make_engine(tmp_repo)
        result = engine.recover_branch("nonexistent-branch-xyz")
        assert result is False

    def test_recover_branch_giterror(self, tmp_repo: Path) -> None:
        """Cover lines 417-419: recover_branch returns False on GitError."""
        engine = self._make_engine(tmp_repo)
        # Patch _run to raise on "branch" creation
        original_run = engine._runner._run

        def _patched_run(*args, **kwargs):
            if args and args[0] == "reflog":
                # Return a fake reflog that mentions "test-branch"
                mock_result = MagicMock()
                mock_result.stdout = (
                    "abc1234567890123456789012345678901234567 checkout: moving from test-branch to main\n"
                )
                return mock_result
            if args and args[0] == "branch":
                raise GitError("branch creation failed")
            return original_run(*args, **kwargs)

        with patch.object(engine._runner, "_run", side_effect=_patched_run):
            result = engine.recover_branch("test-branch")
        assert result is False

    def test_recover_branch_invalid_name(self, tmp_repo: Path) -> None:
        """Cover line 384: recover_branch raises ValueError for invalid branch names."""
        engine = self._make_engine(tmp_repo)
        with pytest.raises(ValueError, match="Invalid branch"):
            engine.recover_branch(";rm -rf /")

    def test_run_dispatch(self, tmp_repo: Path) -> None:
        engine = self._make_engine(tmp_repo)
        engine.auto_snapshot("test")
        assert engine.run("list") == 0
        assert engine.run("invalid-action") == 1

    def test_run_undo(self, tmp_repo: Path) -> None:
        """Cover line 440: run('undo') dispatches to undo_last."""
        engine = self._make_engine(tmp_repo)
        engine.auto_snapshot("test")
        _make_commit(tmp_repo, "after.txt", "after snapshot")
        assert engine.run("undo") == 0

    def test_run_undo_fails(self, tmp_repo: Path) -> None:
        """Cover line 440: run('undo') returns 1 when no snapshots."""
        engine = self._make_engine(tmp_repo)
        assert engine.run("undo") == 1

    def test_run_restore(self, tmp_repo: Path) -> None:
        """Cover lines 443-447: run('restore') with valid and missing tag."""
        engine = self._make_engine(tmp_repo)
        snap = engine.auto_snapshot("test")
        assert engine.run("restore", snapshot_tag=snap.tag) == 0

    def test_run_restore_missing_tag(self, tmp_repo: Path) -> None:
        """Cover lines 444-446: run('restore') returns 1 when tag is empty."""
        engine = self._make_engine(tmp_repo)
        assert engine.run("restore") == 1
        assert engine.run("restore", snapshot_tag="") == 1

    def test_run_recover_branch(self, tmp_repo: Path) -> None:
        """Cover lines 450-454: run('recover-branch') dispatches correctly."""
        _run_git("checkout", "-b", "feature-run-recover", cwd=tmp_repo)
        _make_commit(tmp_repo, "feat.txt", "feature work")
        _run_git("checkout", "main", cwd=tmp_repo)
        _run_git("branch", "-D", "feature-run-recover", cwd=tmp_repo)

        engine = self._make_engine(tmp_repo)
        assert engine.run("recover-branch", branch_name="feature-run-recover") == 0

    def test_run_recover_branch_missing_name(self, tmp_repo: Path) -> None:
        """Cover lines 451-453: run('recover-branch') returns 1 when name is empty."""
        engine = self._make_engine(tmp_repo)
        assert engine.run("recover-branch") == 1
        assert engine.run("recover-branch", branch_name="") == 1
