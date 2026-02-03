"""Unit tests for TaskSyncBridge."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from zerg.constants import TaskStatus
from zerg.state import StateManager
from zerg.task_sync import ClaudeTask, TaskSyncBridge, load_design_manifest


class TestClaudeTask:
    """Tests for ClaudeTask dataclass."""

    def test_create_claude_task(self) -> None:
        """Test ClaudeTask creation with defaults."""
        task = ClaudeTask(
            task_id="L0-001",
            subject="Create auth service",
            description="Implement authentication",
            status="pending",
            level=0,
            feature="auth",
        )
        assert task.task_id == "L0-001"
        assert task.subject == "Create auth service"
        assert task.status == "pending"
        assert task.level == 0
        assert task.worker_id is None
        assert task.active_form is None

    def test_claude_task_with_worker(self) -> None:
        """Test ClaudeTask with worker assignment."""
        task = ClaudeTask(
            task_id="L1-002",
            subject="Test task",
            description="",
            status="in_progress",
            level=1,
            feature="test",
            worker_id=3,
            active_form="Testing",
        )
        assert task.worker_id == 3
        assert task.active_form == "Testing"

    def test_claude_task_to_dict(self) -> None:
        """Test conversion to dictionary."""
        now = datetime.now()
        task = ClaudeTask(
            task_id="L0-001",
            subject="Subject",
            description="Desc",
            status="pending",
            level=0,
            feature="feat",
            created_at=now,
            updated_at=now,
        )
        d = task.to_dict()

        assert d["task_id"] == "L0-001"
        assert d["subject"] == "Subject"
        assert d["status"] == "pending"
        assert d["level"] == 0
        assert d["feature"] == "feat"
        assert d["created_at"] == now.isoformat()


class TestDesignManifestLoading:
    """Tests for load_design_manifest function."""

    def test_load_design_manifest_exists(self, tmp_path: Path) -> None:
        """Test loading a manifest file that exists."""
        manifest = {
            "tasks": [
                {"id": "L0-001", "title": "Create types", "description": "Define types"},
                {"id": "L0-002", "title": "Create utils", "description": "Add utilities"},
            ]
        }
        manifest_path = tmp_path / "design-tasks-manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        result = load_design_manifest(tmp_path)

        assert result is not None
        assert len(result) == 2
        assert result[0]["id"] == "L0-001"
        assert result[0]["title"] == "Create types"
        assert result[1]["id"] == "L0-002"
        assert result[1]["title"] == "Create utils"

    def test_load_design_manifest_missing(self, tmp_path: Path) -> None:
        """Test loading manifest from a directory without the file."""
        nonexistent = tmp_path / "no-such-dir"

        result = load_design_manifest(nonexistent)

        assert result is None


class TestTaskSyncBridge:
    """Tests for TaskSyncBridge class."""

    @pytest.fixture
    def temp_state_dir(self, tmp_path: Path) -> Path:
        """Create temp directory for state files."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        return state_dir

    @pytest.fixture
    def state_manager(self, temp_state_dir: Path) -> StateManager:
        """Create StateManager with temp directory."""
        return StateManager("test-feature", state_dir=temp_state_dir)

    @pytest.fixture
    def bridge(self, state_manager: StateManager) -> TaskSyncBridge:
        """Create TaskSyncBridge with test state manager."""
        return TaskSyncBridge("test-feature", state_manager=state_manager)

    def test_init(self) -> None:
        """Test bridge initialization."""
        bridge = TaskSyncBridge("my-feature")
        assert bridge.feature == "my-feature"
        assert bridge._synced_tasks == {}

    def test_init_with_state_manager(self, state_manager: StateManager) -> None:
        """Test bridge initialization with provided state manager."""
        bridge = TaskSyncBridge("test", state_manager=state_manager)
        assert bridge.state is state_manager

    def test_create_level_tasks(self, bridge: TaskSyncBridge) -> None:
        """Test creating Claude tasks for a level."""
        tasks = [
            {"id": "L0-001", "title": "Create types", "description": "Define types"},
            {"id": "L0-002", "title": "Create utils", "description": "Add utilities"},
        ]

        created = bridge.create_level_tasks(level=0, tasks=tasks)

        assert len(created) == 2
        assert created[0].task_id == "L0-001"
        assert "[L0]" in created[0].subject
        assert created[0].status == "pending"
        assert created[0].level == 0

        # Check internal tracking
        assert "L0-001" in bridge._synced_tasks
        assert "L0-002" in bridge._synced_tasks

    def test_create_level_tasks_active_form(self, bridge: TaskSyncBridge) -> None:
        """Test that active_form is set during creation."""
        tasks = [{"id": "L1-001", "title": "Build API", "description": ""}]
        created = bridge.create_level_tasks(level=1, tasks=tasks)

        assert created[0].active_form == "Executing Build API"

    def test_sync_state_updates_status(self, bridge: TaskSyncBridge, state_manager: StateManager) -> None:
        """Test sync_state updates task statuses from ZERG state."""
        # Create tasks
        bridge.create_level_tasks(0, [{"id": "L0-001", "title": "Task 1"}])

        # Update ZERG state
        state_manager.load()
        state_manager.set_task_status("L0-001", TaskStatus.IN_PROGRESS, worker_id=2)

        # Sync
        updated = bridge.sync_state()

        assert updated == 1
        task = bridge.get_task("L0-001")
        assert task is not None
        assert task.status == "in_progress"
        assert task.worker_id == 2

    def test_sync_state_no_updates(self, bridge: TaskSyncBridge) -> None:
        """Test sync_state returns 0 when no changes."""
        # Create task in pending status
        bridge.create_level_tasks(0, [{"id": "L0-001", "title": "Task 1"}])

        # Sync with matching state (default pending)
        updated = bridge.sync_state({"tasks": {"L0-001": {"status": "pending"}}})

        assert updated == 0

    def test_sync_state_skips_untracked(self, bridge: TaskSyncBridge) -> None:
        """Test sync_state skips tasks not in synced_tasks."""
        state = {"tasks": {"unknown-task": {"status": "in_progress"}}}
        updated = bridge.sync_state(state)

        assert updated == 0
        assert bridge.get_task("unknown-task") is None

    def test_get_task_list(self, bridge: TaskSyncBridge) -> None:
        """Test get_task_list returns all tasks."""
        bridge.create_level_tasks(
            0,
            [
                {"id": "L0-001", "title": "T1"},
                {"id": "L0-002", "title": "T2"},
            ],
        )

        task_list = bridge.get_task_list()

        assert len(task_list) == 2
        assert all(isinstance(t, dict) for t in task_list)
        task_ids = [t["task_id"] for t in task_list]
        assert "L0-001" in task_ids
        assert "L0-002" in task_ids

    def test_get_level_summary(self, bridge: TaskSyncBridge) -> None:
        """Test get_level_summary returns correct counts."""
        bridge.create_level_tasks(
            0,
            [
                {"id": "L0-001", "title": "T1"},
                {"id": "L0-002", "title": "T2"},
                {"id": "L0-003", "title": "T3"},
            ],
        )
        bridge._synced_tasks["L0-002"].status = "in_progress"
        bridge._synced_tasks["L0-003"].status = "completed"

        summary = bridge.get_level_summary(0)

        assert summary["level"] == 0
        assert summary["total"] == 3
        assert summary["pending"] == 1
        assert summary["in_progress"] == 1
        assert summary["completed"] == 1

    def test_get_level_summary_empty(self, bridge: TaskSyncBridge) -> None:
        """Test get_level_summary for nonexistent level."""
        summary = bridge.get_level_summary(99)

        assert summary["level"] == 99
        assert summary["total"] == 0

    def test_is_level_complete_true(self, bridge: TaskSyncBridge) -> None:
        """Test is_level_complete returns True when all done."""
        bridge.create_level_tasks(
            0,
            [
                {"id": "L0-001", "title": "T1"},
                {"id": "L0-002", "title": "T2"},
            ],
        )
        bridge._synced_tasks["L0-001"].status = "completed"
        bridge._synced_tasks["L0-002"].status = "completed"

        assert bridge.is_level_complete(0) is True

    def test_is_level_complete_false(self, bridge: TaskSyncBridge) -> None:
        """Test is_level_complete returns False when tasks pending."""
        bridge.create_level_tasks(
            0,
            [
                {"id": "L0-001", "title": "T1"},
                {"id": "L0-002", "title": "T2"},
            ],
        )
        bridge._synced_tasks["L0-001"].status = "completed"
        # L0-002 still pending

        assert bridge.is_level_complete(0) is False

    def test_is_level_complete_empty(self, bridge: TaskSyncBridge) -> None:
        """Test is_level_complete returns True for empty level."""
        assert bridge.is_level_complete(99) is True

    def test_get_task(self, bridge: TaskSyncBridge) -> None:
        """Test get_task retrieves correct task."""
        bridge.create_level_tasks(0, [{"id": "L0-001", "title": "Find me"}])

        task = bridge.get_task("L0-001")

        assert task is not None
        assert task.task_id == "L0-001"

    def test_get_task_not_found(self, bridge: TaskSyncBridge) -> None:
        """Test get_task returns None for unknown task."""
        assert bridge.get_task("unknown") is None

    def test_update_task_status(self, bridge: TaskSyncBridge) -> None:
        """Test manual task status update."""
        bridge.create_level_tasks(0, [{"id": "L0-001", "title": "T1"}])

        result = bridge.update_task_status("L0-001", "in_progress", worker_id=5)

        assert result is True
        task = bridge.get_task("L0-001")
        assert task is not None
        assert task.status == "in_progress"
        assert task.worker_id == 5

    def test_update_task_status_not_found(self, bridge: TaskSyncBridge) -> None:
        """Test update returns False for unknown task."""
        result = bridge.update_task_status("unknown", "completed")
        assert result is False

    def test_clear(self, bridge: TaskSyncBridge) -> None:
        """Test clearing all synced tasks."""
        bridge.create_level_tasks(
            0,
            [
                {"id": "L0-001", "title": "T1"},
                {"id": "L0-002", "title": "T2"},
            ],
        )

        bridge.clear()

        assert len(bridge._synced_tasks) == 0
        assert bridge.get_task("L0-001") is None


class TestTaskSyncBridgeStatusMapping:
    """Tests for status mapping between ZERG and Claude Tasks."""

    def test_status_map_pending(self) -> None:
        """Test pending status maps correctly."""
        assert TaskSyncBridge.STATUS_MAP[TaskStatus.PENDING.value] == "pending"
        assert TaskSyncBridge.STATUS_MAP[TaskStatus.TODO.value] == "pending"

    def test_status_map_in_progress(self) -> None:
        """Test in_progress status maps correctly."""
        assert TaskSyncBridge.STATUS_MAP[TaskStatus.IN_PROGRESS.value] == "in_progress"
        assert TaskSyncBridge.STATUS_MAP[TaskStatus.CLAIMED.value] == "in_progress"
        assert TaskSyncBridge.STATUS_MAP[TaskStatus.PAUSED.value] == "in_progress"
        assert TaskSyncBridge.STATUS_MAP[TaskStatus.BLOCKED.value] == "in_progress"

    def test_status_map_completed(self) -> None:
        """Test completed status maps correctly."""
        assert TaskSyncBridge.STATUS_MAP[TaskStatus.COMPLETE.value] == "completed"
        assert TaskSyncBridge.STATUS_MAP[TaskStatus.FAILED.value] == "completed"
