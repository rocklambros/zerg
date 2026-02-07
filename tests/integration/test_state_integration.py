"""Integration tests for StateManager persistence.

Tests cover:
1. State save and load roundtrip
2. State recovery after crash
3. Concurrent state access handling
4. State migration between versions
5. State backup and restore
"""

import json
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from zerg.constants import LevelMergeStatus, TaskStatus, WorkerStatus
from zerg.exceptions import StateError
from zerg.state import StateManager
from zerg.types import WorkerState


class TestStateSaveLoadRoundtrip:
    """Test state save and load roundtrip with real filesystem operations."""

    def test_basic_roundtrip(self, tmp_path: Path) -> None:
        """Test basic save/load preserves state."""
        state_dir = tmp_path / "state"
        manager = StateManager("test-feature", state_dir=state_dir)
        manager.load()

        # Set up comprehensive state
        manager.set_current_level(3)
        manager.set_task_status("TASK-001", TaskStatus.COMPLETE, worker_id=0)
        manager.set_task_status("TASK-002", TaskStatus.IN_PROGRESS, worker_id=1)
        manager.set_task_status("TASK-003", TaskStatus.PENDING)
        manager.set_paused(True)
        manager.set_error("Test error message")
        manager.append_event("test_event", {"key": "value"})
        manager.set_level_status(1, "complete", merge_commit="abc123")
        manager.set_level_merge_status(2, LevelMergeStatus.MERGING)

        # Create new manager instance and verify state persisted
        manager2 = StateManager("test-feature", state_dir=state_dir)
        state = manager2.load()

        assert state["current_level"] == 3
        assert state["paused"] is True
        assert state["error"] == "Test error message"
        assert len(state["execution_log"]) == 1
        assert state["execution_log"][0]["event"] == "test_event"
        assert manager2.get_task_status("TASK-001") == TaskStatus.COMPLETE.value
        assert manager2.get_task_status("TASK-002") == TaskStatus.IN_PROGRESS.value
        assert manager2.get_task_status("TASK-003") == TaskStatus.PENDING.value
        assert manager2.get_level_merge_status(2) == LevelMergeStatus.MERGING

    def test_worker_state_roundtrip(self, tmp_path: Path) -> None:
        """Test worker state serialization roundtrip."""
        state_dir = tmp_path / "state"
        manager = StateManager("test-feature", state_dir=state_dir)
        manager.load()

        # Create worker states with all fields populated
        now = datetime.now()
        worker_state = WorkerState(
            worker_id=1,
            status=WorkerStatus.RUNNING,
            current_task="TASK-001",
            port=49152,
            container_id="container-abc",
            worktree_path="/path/to/worktree",
            branch="feature/test",
            health_check_at=now,
            started_at=now,
            ready_at=now,
            last_task_completed_at=now,
            tasks_completed=5,
            context_usage=0.75,
        )
        manager.set_worker_state(worker_state)

        # Load in new manager instance
        manager2 = StateManager("test-feature", state_dir=state_dir)
        manager2.load()
        loaded_worker = manager2.get_worker_state(1)

        assert loaded_worker is not None
        assert loaded_worker.worker_id == 1
        assert loaded_worker.status == WorkerStatus.RUNNING
        assert loaded_worker.current_task == "TASK-001"
        assert loaded_worker.port == 49152
        assert loaded_worker.container_id == "container-abc"
        assert loaded_worker.tasks_completed == 5
        assert loaded_worker.context_usage == 0.75


class TestStateRecoveryAfterCrash:
    """Test state recovery scenarios simulating crashes."""

    def test_recovery_from_valid_state(self, tmp_path: Path) -> None:
        """Test recovery when state file is valid."""
        state_dir = tmp_path / "state"
        manager = StateManager("test-feature", state_dir=state_dir)
        manager.load()

        # Set up state simulating mid-execution
        manager.set_current_level(2)
        manager.set_task_status("TASK-001", TaskStatus.COMPLETE, worker_id=0)
        manager.set_task_status("TASK-002", TaskStatus.IN_PROGRESS, worker_id=1)
        manager.set_task_status("TASK-003", TaskStatus.PENDING)
        manager.set_level_status(1, "complete")
        manager.set_level_status(2, "running")

        # Simulate crash by creating new manager (without explicit shutdown)
        manager2 = StateManager("test-feature", state_dir=state_dir)
        state = manager2.load()

        # Verify recovery preserves in-progress state
        assert state["current_level"] == 2
        assert manager2.get_task_status("TASK-001") == TaskStatus.COMPLETE.value
        assert manager2.get_task_status("TASK-002") == TaskStatus.IN_PROGRESS.value
        assert manager2.get_task_status("TASK-003") == TaskStatus.PENDING.value

    @pytest.mark.parametrize(
        "file_content,description",
        [
            ("{invalid json content", "corrupted JSON"),
            ("", "empty file"),
            ('{"feature": "test", "current_level": 2, "tasks":', "truncated JSON"),
        ],
    )
    def test_recovery_from_corrupt_file(self, tmp_path: Path, file_content: str, description: str) -> None:
        """Test recovery when state file is corrupt ({description})."""
        state_dir = tmp_path / "state"
        state_dir.mkdir(parents=True, exist_ok=True)

        state_file = state_dir / "test-feature.json"
        state_file.write_text(file_content, encoding="utf-8")

        manager = StateManager("test-feature", state_dir=state_dir)

        with pytest.raises(StateError):
            manager.load()

    def test_recovery_from_missing_directory(self, tmp_path: Path) -> None:
        """Test state manager creates directory if missing."""
        state_dir = tmp_path / "nonexistent" / "nested" / "state"

        # Directory should not exist
        assert not state_dir.exists()

        manager = StateManager("test-feature", state_dir=state_dir)

        # Directory should be created
        assert state_dir.exists()

        # Should load fresh state
        state = manager.load()
        assert state["feature"] == "test-feature"
        assert state["current_level"] == 0


class TestConcurrentStateAccess:
    """Test concurrent state access handling.

    Note: StateManager uses threading.RLock for thread safety within a single
    instance but does not implement file-level locking for multi-process access.
    These tests verify the thread-safety guarantees provided.
    """

    def test_single_instance_concurrent_task_claims(self, tmp_path: Path) -> None:
        """Test multiple threads claiming tasks through a single shared manager instance."""
        state_dir = tmp_path / "state"
        manager = StateManager("test-feature", state_dir=state_dir)
        manager.load()

        # Set up pending tasks
        for i in range(10):
            manager.set_task_status(f"TASK-{i:03d}", TaskStatus.PENDING)

        results: dict[str, list[int]] = {f"TASK-{i:03d}": [] for i in range(10)}
        lock = threading.Lock()

        def worker_claim(worker_id: int) -> None:
            """Worker attempts to claim tasks using shared manager."""
            for task_id in list(results.keys()):
                if manager.claim_task(task_id, worker_id):
                    with lock:
                        results[task_id].append(worker_id)

        # Run concurrent claims from multiple threads using same manager instance
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker_claim, i) for i in range(5)]
            for future in as_completed(futures):
                future.result()

        # Each task should be claimed by at most one worker
        for task_id, claimers in results.items():
            assert len(claimers) <= 1, f"Task {task_id} claimed by multiple workers: {claimers}"

        # All tasks should be claimed (total claims = 10)
        total_claims = sum(len(v) for v in results.values())
        assert total_claims == 10

    def test_lock_prevents_corruption(self, tmp_path: Path) -> None:
        """Test that internal lock prevents state corruption during concurrent access."""
        state_dir = tmp_path / "state"
        manager = StateManager("test-feature", state_dir=state_dir)
        manager.load()

        errors: list[Exception] = []
        iterations = 100

        def read_write_cycle() -> None:
            """Perform read-write cycle on shared manager."""
            try:
                for _ in range(iterations):
                    # Read current level
                    _ = manager.get_current_level()
                    # Write new level
                    manager.set_current_level(manager.get_current_level() + 1)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=read_write_cycle) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should occur
        assert len(errors) == 0

        # State should be valid
        state = manager.load()
        assert isinstance(state["current_level"], int)


class TestStateMigration:
    """Test state migration between versions."""

    def test_load_v1_state_format(self, tmp_path: Path) -> None:
        """Test loading state from older format (missing new fields)."""
        state_dir = tmp_path / "state"
        state_dir.mkdir(parents=True, exist_ok=True)

        # Create V1 state (missing newer fields like merge_status, metrics)
        v1_state: dict[str, Any] = {
            "feature": "test-feature",
            "started_at": "2026-01-25T10:00:00",
            "current_level": 1,
            "tasks": {
                "TASK-001": {"status": "complete", "worker_id": 0},
                "TASK-002": {"status": "pending"},
            },
            "workers": {},
            "execution_log": [],
            "paused": False,
            "error": None,
            # Note: No "levels" or "metrics" field
        }

        state_file = state_dir / "test-feature.json"
        with open(state_file, "w") as f:
            json.dump(v1_state, f)

        # Load with current manager
        manager = StateManager("test-feature", state_dir=state_dir)
        state = manager.load()

        # Should load without error
        assert state["feature"] == "test-feature"
        assert state["current_level"] == 1
        assert manager.get_task_status("TASK-001") == "complete"
        assert manager.get_task_status("TASK-002") == "pending"

        # Optional fields should be accessible with defaults
        assert manager.get_level_status(1) is None
        assert manager.get_metrics() is None

    def test_state_with_extra_fields(self, tmp_path: Path) -> None:
        """Test loading state with unknown fields (forward compatibility)."""
        state_dir = tmp_path / "state"
        state_dir.mkdir(parents=True, exist_ok=True)

        # Create state with extra fields that current code doesnt know about
        future_state: dict[str, Any] = {
            "feature": "test-feature",
            "started_at": "2026-01-25T10:00:00",
            "current_level": 2,
            "tasks": {},
            "workers": {},
            "levels": {},
            "execution_log": [],
            "metrics": None,
            "paused": False,
            "error": None,
            # Extra fields from a future version
            "future_field_1": "some value",
            "future_field_2": {"nested": "data"},
            "new_feature_config": [1, 2, 3],
        }

        state_file = state_dir / "test-feature.json"
        with open(state_file, "w") as f:
            json.dump(future_state, f)

        # Should load without error
        manager = StateManager("test-feature", state_dir=state_dir)
        state = manager.load()

        assert state["current_level"] == 2
        # Extra fields are preserved in state dict
        assert state.get("future_field_1") == "some value"


class TestStateBackupRestore:
    """Test state backup and restore functionality."""

    def test_manual_backup_and_restore(self, tmp_path: Path) -> None:
        """Test manual backup and restore of state files."""
        state_dir = tmp_path / "state"
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Create and populate state
        manager = StateManager("test-feature", state_dir=state_dir)
        manager.load()
        manager.set_current_level(3)
        manager.set_task_status("TASK-001", TaskStatus.COMPLETE, worker_id=0)
        manager.set_task_status("TASK-002", TaskStatus.IN_PROGRESS, worker_id=1)
        manager.append_event("important_event", {"data": "critical"})

        # Manual backup (copy state file)
        state_file = state_dir / "test-feature.json"
        backup_file = backup_dir / "test-feature.json.bak"
        shutil.copy2(state_file, backup_file)

        # Simulate disaster (corrupt or delete state)
        state_file.write_text("corrupted data", encoding="utf-8")

        # Verify state is corrupted
        with pytest.raises(StateError):
            StateManager("test-feature", state_dir=state_dir).load()

        # Restore from backup
        shutil.copy2(backup_file, state_file)

        # Verify restoration
        restored_manager = StateManager("test-feature", state_dir=state_dir)
        state = restored_manager.load()

        assert state["current_level"] == 3
        assert restored_manager.get_task_status("TASK-001") == TaskStatus.COMPLETE.value
        assert restored_manager.get_task_status("TASK-002") == TaskStatus.IN_PROGRESS.value
        assert len(state["execution_log"]) == 1
        assert state["execution_log"][0]["event"] == "important_event"

    def test_delete_and_recreate(self, tmp_path: Path) -> None:
        """Test deleting state and recreating fresh."""
        state_dir = tmp_path / "state"
        manager = StateManager("test-feature", state_dir=state_dir)
        manager.load()

        # Populate state
        manager.set_current_level(5)
        manager.set_task_status("TASK-001", TaskStatus.FAILED, error="fatal error")

        # Verify it exists
        assert manager.exists()

        # Delete state
        manager.delete()
        assert not manager.exists()

        # Create fresh manager - should start with initial state
        fresh_manager = StateManager("test-feature", state_dir=state_dir)
        state = fresh_manager.load()

        assert state["current_level"] == 0
        assert state["tasks"] == {}
        assert state["error"] is None


class TestStateMdGeneration:
    """Test STATE.md generation functionality."""

    def test_generate_state_md(self, tmp_path: Path) -> None:
        """Test STATE.md file generation."""
        state_dir = tmp_path / "state"
        gsd_dir = tmp_path / ".gsd"
        gsd_dir.mkdir(parents=True, exist_ok=True)

        manager = StateManager("test-feature", state_dir=state_dir)
        manager.load()

        # Set up comprehensive state
        manager.set_current_level(2)
        manager.set_task_status("TASK-001", TaskStatus.COMPLETE, worker_id=0)
        manager.set_task_status("TASK-002", TaskStatus.IN_PROGRESS, worker_id=1)
        manager.set_task_status("TASK-003", TaskStatus.FAILED, worker_id=2, error="Verification failed")
        manager.increment_task_retry("TASK-003")
        manager.set_level_status(1, "complete", merge_commit="abc1234567890")
        manager.set_level_status(2, "running")
        manager.append_event("level_started", {"level": 2})

        # Generate STATE.md
        state_md_path = manager.generate_state_md(gsd_dir=gsd_dir)

        assert state_md_path.exists()
        content = state_md_path.read_text(encoding="utf-8")

        # Verify content
        assert "# ZERG State: test-feature" in content
        assert "**Level:** 2" in content
        assert "TASK-001" in content
        assert "complete" in content
        assert "TASK-003" in content
        assert "Blockers" in content
        assert "Verification failed" in content


class TestCrossProcessStateVisibility:
    """Test that separate StateManager instances see each other's writes after load()."""

    def test_cross_process_state_visibility(self, tmp_path: Path) -> None:
        """Two StateManager instances on same file see each other's writes."""
        state_dir = tmp_path / "state"

        # Instance A (simulating worker process)
        manager_a = StateManager("test-feature", state_dir=state_dir)
        manager_a.load()

        # Instance B (simulating orchestrator process)
        manager_b = StateManager("test-feature", state_dir=state_dir)
        manager_b.load()

        # Worker (A) writes its own WorkerState
        worker_state = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            current_task="TASK-001",
            branch="zerg/test/worker-0",
            worktree_path="/tmp/wt",
            started_at=datetime.now(),
            tasks_completed=2,
            context_usage=0.35,
        )
        manager_a.set_worker_state(worker_state)

        # Orchestrator (B) hasn't reloaded yet -- stale in-memory state
        stale_worker = manager_b.get_worker_state(0)
        assert stale_worker is None, "Before load(), B should not see A's write"

        # Orchestrator (B) reloads from disk
        manager_b.load()
        fresh_worker = manager_b.get_worker_state(0)

        assert fresh_worker is not None
        assert fresh_worker.status == WorkerStatus.RUNNING
        assert fresh_worker.current_task == "TASK-001"
        assert fresh_worker.tasks_completed == 2
        assert fresh_worker.context_usage == 0.35
