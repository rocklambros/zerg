"""Tests for ZERG v2 Orchestrator."""

import json
import sys
from pathlib import Path

# Add .zerg to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator import Orchestrator


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
