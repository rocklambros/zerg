"""Tests for ZERG v2 Orchestrator."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Add .zerg to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator import MergeConflictError, Orchestrator
from worktree import WorktreeManager


class TestOrchestratorInit:
    """Tests for Orchestrator initialization."""

    def test_orchestrator_init(self):
        """Test Orchestrator instantiates correctly."""
        o = Orchestrator()
        assert o is not None

    def test_orchestrator_has_required_methods(self):
        """Test Orchestrator has start, stop, get_status methods."""
        from orchestrator import Orchestrator

        o = Orchestrator()
        assert hasattr(o, "start")
        assert hasattr(o, "stop")
        assert hasattr(o, "get_status")
        assert callable(o.start)
        assert callable(o.stop)
        assert callable(o.get_status)


class TestOrchestratorStatus:
    """Tests for Orchestrator status."""

    def test_get_status_idle(self):
        """Test status is IDLE when not running."""
        o = Orchestrator()
        status = o.get_status()
        assert status["state"] == "IDLE"

    def test_get_status_contains_worker_info(self):
        """Test status includes worker information."""
        o = Orchestrator()
        status = o.get_status()
        assert "workers" in status
        assert "active_workers" in status
        assert "completed_tasks" in status


class TestOrchestratorShutdown:
    """Tests for Orchestrator shutdown."""

    def test_graceful_shutdown(self):
        """Test graceful shutdown sets state to STOPPED."""
        o = Orchestrator()
        o.stop()
        assert o.get_status()["state"] == "STOPPED"

    def test_force_shutdown(self):
        """Test force shutdown sets state to STOPPED."""
        o = Orchestrator()
        o.stop(force=True)
        assert o.get_status()["state"] == "STOPPED"


class TestOrchestratorStart:
    """Tests for Orchestrator start."""

    def test_start_sets_running_state(self, tmp_path):
        """Test start transitions to RUNNING state."""
        # Create minimal task graph
        task_graph = {
            "feature": "test",
            "tasks": [],
            "levels": {},
        }
        graph_path = tmp_path / "task-graph.json"
        graph_path.write_text(json.dumps(task_graph))

        o = Orchestrator()
        o.start(str(graph_path), workers=1, dry_run=True)
        assert o.get_status()["state"] in ("RUNNING", "COMPLETE")


class TestOrchestratorLevelBarrier:
    """Tests for level barrier synchronization."""

    def test_level_ordering(self):
        """Test tasks are ordered by level."""
        o = Orchestrator()
        # Level ordering is enforced internally
        assert hasattr(o, "_current_level") or hasattr(o, "current_level")


class TestOrchestratorCheckpoint:
    """Tests for checkpoint and resume."""

    def test_checkpoint_save(self, tmp_path):
        """Test checkpoint saves state."""
        o = Orchestrator()
        o._state_path = str(tmp_path / "state.json")
        o.save_checkpoint()

        assert Path(o._state_path).exists()

    def test_checkpoint_load(self, tmp_path):
        """Test checkpoint loads state."""
        state_path = tmp_path / "state.json"
        state_data = {
            "state": "PAUSED",
            "current_level": 2,
            "completed_tasks": ["TASK-001"],
        }
        state_path.write_text(json.dumps(state_data))

        o = Orchestrator()
        o._state_path = str(state_path)
        o.load_checkpoint()

        assert o._state == "PAUSED" or o.get_status()["state"] == "PAUSED"


class TestOrchestratorWorktreeIntegration:
    """Tests for Orchestrator integration with WorktreeManager."""

    @pytest.fixture
    def git_repo(self, tmp_path):
        """Create a test git repo."""
        subprocess.run(
            ["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True,
        )
        # Create initial commit
        (tmp_path / "README.md").write_text("# Test Repo")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True
        )
        return tmp_path

    def test_orchestrator_has_worktree_manager(self):
        """Test Orchestrator has WorktreeManager instance."""
        o = Orchestrator()
        assert hasattr(o, "_worktree_manager")
        assert isinstance(o._worktree_manager, WorktreeManager)

    def test_orchestrator_has_spawn_worker_method(self):
        """Test Orchestrator has spawn_worker method."""
        o = Orchestrator()
        assert hasattr(o, "spawn_worker")
        assert callable(o.spawn_worker)

    def test_orchestrator_has_complete_level_method(self):
        """Test Orchestrator has complete_level method."""
        o = Orchestrator()
        assert hasattr(o, "complete_level")
        assert callable(o.complete_level)

    def test_orchestrator_has_get_level_workers_method(self):
        """Test Orchestrator has get_level_workers method."""
        o = Orchestrator()
        assert hasattr(o, "get_level_workers")
        assert callable(o.get_level_workers)

    def test_spawn_worker_creates_worktree(self, git_repo):
        """Test spawn_worker creates an isolated worktree."""
        o = Orchestrator()
        o._worktree_manager = WorktreeManager(git_repo)

        task = {"id": "TASK-001", "title": "Test task"}
        worker = o.spawn_worker("w1", task)

        assert worker.worktree is not None
        assert worker.worktree.path.exists()
        assert worker.worktree.branch == "zerg/worker-w1"
        assert worker.current_task == "TASK-001"

    def test_complete_level_with_no_workers(self):
        """Test complete_level succeeds with no workers."""
        o = Orchestrator()
        result = o.complete_level(0)
        assert result.success
        assert result.merged_count == 0


class TestMergeConflictError:
    """Tests for MergeConflictError exception."""

    def test_merge_conflict_error_creation(self):
        """Test MergeConflictError can be created."""
        err = MergeConflictError(["file1.py", "file2.py"])
        assert err.conflicts == ["file1.py", "file2.py"]
        assert "file1.py" in str(err)
        assert "file2.py" in str(err)

    def test_merge_conflict_error_empty_conflicts(self):
        """Test MergeConflictError with empty conflicts."""
        err = MergeConflictError([])
        assert err.conflicts == []
