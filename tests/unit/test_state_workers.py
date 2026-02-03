"""Tests for worker state edge cases in ZERG state management.

Covers edge cases for:
- get_worker_state with non-existent worker ID
- set_worker_state with None fields
- Worker state update preserves existing fields
- get_all_workers returns empty when no workers
- Worker state serialization roundtrip
"""

from datetime import datetime
from pathlib import Path

from zerg.constants import WorkerStatus
from zerg.state import StateManager
from zerg.types import WorkerState


class TestGetWorkerStateEdgeCases:
    """Tests for get_worker_state edge cases."""

    def test_get_worker_state_non_existent_worker_id_returns_none(self, tmp_path: Path) -> None:
        """Test get_worker_state returns None for non-existent worker ID."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        result = manager.get_worker_state(worker_id=999)

        assert result is None

    def test_get_worker_state_empty_workers_dict_returns_none(self, tmp_path: Path) -> None:
        """Test get_worker_state returns None when workers dict is empty."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        # Ensure workers dict is empty
        manager._state["workers"] = {}

        result = manager.get_worker_state(worker_id=1)

        assert result is None

    def test_get_worker_state_with_string_key_mismatch(self, tmp_path: Path) -> None:
        """Test get_worker_state handles string key conversion correctly."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        # Workers are stored with string keys
        manager._state["workers"] = {
            "1": {
                "worker_id": 1,
                "status": WorkerStatus.READY.value,
                "current_task": None,
                "port": 8080,
                "container_id": None,
                "worktree_path": None,
                "branch": None,
                "health_check_at": None,
                "started_at": None,
                "ready_at": None,
                "last_task_completed_at": None,
                "tasks_completed": 0,
                "context_usage": 0.0,
            }
        }
        manager.save()

        # Should find worker with int ID lookup
        result = manager.get_worker_state(worker_id=1)
        assert result is not None
        assert result.worker_id == 1

        # Should not find worker with different ID
        result_missing = manager.get_worker_state(worker_id=2)
        assert result_missing is None


class TestSetWorkerStateEdgeCases:
    """Tests for set_worker_state edge cases."""

    def test_set_worker_state_with_all_none_optional_fields(self, tmp_path: Path) -> None:
        """Test set_worker_state handles WorkerState with None optional fields."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        worker_state = WorkerState(
            worker_id=1,
            status=WorkerStatus.INITIALIZING,
            current_task=None,
            port=None,
            container_id=None,
            worktree_path=None,
            branch=None,
            health_check_at=None,
            started_at=None,
            ready_at=None,
            last_task_completed_at=None,
            tasks_completed=0,
            context_usage=0.0,
        )

        manager.set_worker_state(worker_state)

        # Verify state was saved
        retrieved = manager.get_worker_state(worker_id=1)
        assert retrieved is not None
        assert retrieved.worker_id == 1
        assert retrieved.status == WorkerStatus.INITIALIZING
        assert retrieved.current_task is None
        assert retrieved.port is None
        assert retrieved.container_id is None

    def test_set_worker_state_creates_workers_dict_if_missing(self, tmp_path: Path) -> None:
        """Test set_worker_state creates workers dict if it does not exist."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        # Remove workers key entirely
        del manager._state["workers"]

        worker_state = WorkerState(
            worker_id=1,
            status=WorkerStatus.READY,
        )

        manager.set_worker_state(worker_state)

        assert "workers" in manager._state
        assert "1" in manager._state["workers"]


class TestWorkerStateUpdatePreservation:
    """Tests for worker state update field preservation."""

    def test_update_worker_status_preserves_other_fields(self, tmp_path: Path) -> None:
        """Test updating worker status preserves existing fields."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # Set initial state with many fields populated
        initial_state = WorkerState(
            worker_id=1,
            status=WorkerStatus.INITIALIZING,
            current_task="TASK-001",
            port=8080,
            container_id="abc123",
            worktree_path="/tmp/worktree",
            branch="feature/test",
            started_at=datetime(2025, 1, 1, 10, 0, 0),
            tasks_completed=5,
            context_usage=0.35,
        )
        manager.set_worker_state(initial_state)

        # Update only status via new WorkerState
        updated_state = WorkerState(
            worker_id=1,
            status=WorkerStatus.RUNNING,
            current_task="TASK-002",
            port=8080,
            container_id="abc123",
            worktree_path="/tmp/worktree",
            branch="feature/test",
            started_at=datetime(2025, 1, 1, 10, 0, 0),
            tasks_completed=5,
            context_usage=0.40,
        )
        manager.set_worker_state(updated_state)

        # Verify all fields
        retrieved = manager.get_worker_state(worker_id=1)
        assert retrieved is not None
        assert retrieved.status == WorkerStatus.RUNNING
        assert retrieved.current_task == "TASK-002"
        assert retrieved.port == 8080
        assert retrieved.container_id == "abc123"
        assert retrieved.worktree_path == "/tmp/worktree"
        assert retrieved.branch == "feature/test"
        assert retrieved.tasks_completed == 5
        assert retrieved.context_usage == 0.40

    def test_set_worker_state_overwrites_completely(self, tmp_path: Path) -> None:
        """Test set_worker_state does full replacement, not merge."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # Set initial state with populated optional fields
        initial_state = WorkerState(
            worker_id=1,
            status=WorkerStatus.RUNNING,
            current_task="TASK-001",
            port=8080,
            container_id="container-xyz",
            tasks_completed=10,
        )
        manager.set_worker_state(initial_state)

        # Set new state with None for previously set fields
        new_state = WorkerState(
            worker_id=1,
            status=WorkerStatus.IDLE,
            current_task=None,
            port=None,
            container_id=None,
            tasks_completed=0,
        )
        manager.set_worker_state(new_state)

        # Verify the new state completely replaced the old
        retrieved = manager.get_worker_state(worker_id=1)
        assert retrieved is not None
        assert retrieved.status == WorkerStatus.IDLE
        assert retrieved.current_task is None
        assert retrieved.port is None
        assert retrieved.container_id is None
        assert retrieved.tasks_completed == 0


class TestGetAllWorkersEdgeCases:
    """Tests for get_all_workers edge cases."""

    def test_get_all_workers_returns_empty_dict_when_no_workers(self, tmp_path: Path) -> None:
        """Test get_all_workers returns empty dict when no workers exist."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        result = manager.get_all_workers()

        assert result == {}
        assert isinstance(result, dict)

    def test_get_all_workers_returns_empty_when_workers_key_missing(self, tmp_path: Path) -> None:
        """Test get_all_workers returns empty dict when workers key missing."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        # Remove the workers key
        manager._state.pop("workers", None)

        result = manager.get_all_workers()

        assert result == {}

    def test_get_all_workers_returns_correct_worker_states(self, tmp_path: Path) -> None:
        """Test get_all_workers returns all registered workers."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # Add multiple workers
        for i in range(3):
            worker_state = WorkerState(
                worker_id=i,
                status=WorkerStatus.READY,
                port=8080 + i,
            )
            manager.set_worker_state(worker_state)

        result = manager.get_all_workers()

        assert len(result) == 3
        assert 0 in result
        assert 1 in result
        assert 2 in result
        assert result[0].port == 8080
        assert result[1].port == 8081
        assert result[2].port == 8082

    def test_get_all_workers_converts_string_keys_to_int(self, tmp_path: Path) -> None:
        """Test get_all_workers converts string keys to integer keys."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        worker_state = WorkerState(
            worker_id=42,
            status=WorkerStatus.RUNNING,
        )
        manager.set_worker_state(worker_state)

        result = manager.get_all_workers()

        # Keys should be integers, not strings
        assert 42 in result
        assert "42" not in result
        assert isinstance(list(result.keys())[0], int)


class TestWorkerStateSerializationRoundtrip:
    """Tests for worker state serialization and deserialization roundtrip."""

    def test_basic_worker_state_roundtrip(self, tmp_path: Path) -> None:
        """Test basic worker state survives save/load cycle."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        original = WorkerState(
            worker_id=1,
            status=WorkerStatus.READY,
            current_task="TASK-001",
            port=8080,
        )
        manager.set_worker_state(original)

        # Create new manager to force reload from disk
        manager2 = StateManager("test-feature", state_dir=tmp_path)
        manager2.load()

        retrieved = manager2.get_worker_state(worker_id=1)

        assert retrieved is not None
        assert retrieved.worker_id == original.worker_id
        assert retrieved.status == original.status
        assert retrieved.current_task == original.current_task
        assert retrieved.port == original.port

    def test_worker_state_with_datetime_fields_roundtrip(self, tmp_path: Path) -> None:
        """Test worker state with datetime fields survives roundtrip."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        now = datetime.now()
        original = WorkerState(
            worker_id=1,
            status=WorkerStatus.RUNNING,
            health_check_at=now,
            started_at=now,
            ready_at=now,
            last_task_completed_at=now,
        )
        manager.set_worker_state(original)

        # Create new manager to force reload from disk
        manager2 = StateManager("test-feature", state_dir=tmp_path)
        manager2.load()

        retrieved = manager2.get_worker_state(worker_id=1)

        assert retrieved is not None
        # Datetime comparison - after serialization/deserialization
        assert retrieved.health_check_at is not None
        assert retrieved.started_at is not None
        assert retrieved.ready_at is not None
        assert retrieved.last_task_completed_at is not None
        # Compare as ISO strings to handle microsecond precision
        assert retrieved.health_check_at.isoformat() == now.isoformat()
        assert retrieved.started_at.isoformat() == now.isoformat()

    def test_worker_state_with_all_fields_roundtrip(self, tmp_path: Path) -> None:
        """Test worker state with all fields populated survives roundtrip."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        now = datetime.now()
        original = WorkerState(
            worker_id=7,
            status=WorkerStatus.CHECKPOINTING,
            current_task="TASK-XYZ-999",
            port=49152,
            container_id="sha256:abc123def456",
            worktree_path="/workspace/zerg-worktrees/worker-7",
            branch="zerg/test-feature/level-3/worker-7",
            health_check_at=now,
            started_at=now,
            ready_at=now,
            last_task_completed_at=now,
            tasks_completed=42,
            context_usage=0.85,
        )
        manager.set_worker_state(original)

        # Create new manager to force reload from disk
        manager2 = StateManager("test-feature", state_dir=tmp_path)
        manager2.load()

        retrieved = manager2.get_worker_state(worker_id=7)

        assert retrieved is not None
        assert retrieved.worker_id == 7
        assert retrieved.status == WorkerStatus.CHECKPOINTING
        assert retrieved.current_task == "TASK-XYZ-999"
        assert retrieved.port == 49152
        assert retrieved.container_id == "sha256:abc123def456"
        assert retrieved.worktree_path == "/workspace/zerg-worktrees/worker-7"
        assert retrieved.branch == "zerg/test-feature/level-3/worker-7"
        assert retrieved.tasks_completed == 42
        assert retrieved.context_usage == 0.85

    def test_multiple_workers_roundtrip(self, tmp_path: Path) -> None:
        """Test multiple workers survive roundtrip correctly."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        workers = [
            WorkerState(worker_id=0, status=WorkerStatus.READY, port=8000),
            WorkerState(worker_id=1, status=WorkerStatus.RUNNING, port=8001, current_task="TASK-A"),
            WorkerState(worker_id=2, status=WorkerStatus.IDLE, port=8002, tasks_completed=5),
        ]
        for w in workers:
            manager.set_worker_state(w)

        # Create new manager to force reload from disk
        manager2 = StateManager("test-feature", state_dir=tmp_path)
        manager2.load()

        all_workers = manager2.get_all_workers()

        assert len(all_workers) == 3
        assert all_workers[0].status == WorkerStatus.READY
        assert all_workers[1].current_task == "TASK-A"
        assert all_workers[2].tasks_completed == 5

    def test_worker_state_none_fields_roundtrip(self, tmp_path: Path) -> None:
        """Test worker state with None fields survives roundtrip."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        original = WorkerState(
            worker_id=1,
            status=WorkerStatus.STOPPED,
            current_task=None,
            port=None,
            container_id=None,
            worktree_path=None,
            branch=None,
            health_check_at=None,
            started_at=None,
            ready_at=None,
            last_task_completed_at=None,
        )
        manager.set_worker_state(original)

        # Create new manager to force reload from disk
        manager2 = StateManager("test-feature", state_dir=tmp_path)
        manager2.load()

        retrieved = manager2.get_worker_state(worker_id=1)

        assert retrieved is not None
        assert retrieved.status == WorkerStatus.STOPPED
        assert retrieved.current_task is None
        assert retrieved.port is None
        assert retrieved.container_id is None
        assert retrieved.worktree_path is None
        assert retrieved.branch is None
        assert retrieved.health_check_at is None
        assert retrieved.started_at is None
        assert retrieved.ready_at is None
        assert retrieved.last_task_completed_at is None
