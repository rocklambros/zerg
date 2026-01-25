"""Tests for zerg.types module."""

from zerg.constants import Level, WorkerStatus
from zerg.types import (
    LevelStatus,
    Task,
    TaskGraph,
    WorkerState,
)


class TestTask:
    """Tests for Task TypedDict."""

    def test_required_fields(self, sample_task: Task) -> None:
        """Test that required fields are present."""
        assert "id" in sample_task
        assert "title" in sample_task
        assert "level" in sample_task

    def test_optional_fields(self, sample_task: Task) -> None:
        """Test optional fields."""
        assert "description" in sample_task
        assert "dependencies" in sample_task
        assert "files" in sample_task
        assert "verification" in sample_task

    def test_files_structure(self, sample_task: Task) -> None:
        """Test files structure."""
        files = sample_task.get("files", {})
        assert "create" in files
        assert "modify" in files
        assert "read" in files
        assert isinstance(files["create"], list)

    def test_verification_structure(self, sample_task: Task) -> None:
        """Test verification structure."""
        verification = sample_task.get("verification", {})
        assert "command" in verification
        assert "timeout_seconds" in verification


class TestTaskGraph:
    """Tests for TaskGraph TypedDict."""

    def test_required_fields(self, sample_task_graph: TaskGraph) -> None:
        """Test that required fields are present."""
        assert "feature" in sample_task_graph
        assert "tasks" in sample_task_graph
        assert "levels" in sample_task_graph

    def test_tasks_list(self, sample_task_graph: TaskGraph) -> None:
        """Test tasks is a list."""
        tasks = sample_task_graph.get("tasks", [])
        assert isinstance(tasks, list)
        assert len(tasks) > 0

    def test_levels_dict(self, sample_task_graph: TaskGraph) -> None:
        """Test levels is a dict."""
        levels = sample_task_graph.get("levels", {})
        assert isinstance(levels, dict)
        assert "1" in levels

    def test_level_structure(self, sample_task_graph: TaskGraph) -> None:
        """Test level structure."""
        levels = sample_task_graph.get("levels", {})
        level_1 = levels.get("1", {})

        assert "name" in level_1
        assert "tasks" in level_1
        assert "parallel" in level_1

    def test_metadata_fields(self, sample_task_graph: TaskGraph) -> None:
        """Test metadata fields."""
        assert sample_task_graph.get("version") == "1.0"
        assert sample_task_graph.get("total_tasks") == 5
        assert sample_task_graph.get("max_parallelization") == 3


class TestWorkerState:
    """Tests for WorkerState dataclass."""

    def test_create_worker_state(self) -> None:
        """Test creating a WorkerState."""
        state = WorkerState(
            worker_id=1,
            status=WorkerStatus.RUNNING,
            port=49152,
        )

        assert state.worker_id == 1
        assert state.status == WorkerStatus.RUNNING
        assert state.port == 49152

    def test_worker_state_defaults(self) -> None:
        """Test WorkerState default values."""
        state = WorkerState(
            worker_id=0,
            status=WorkerStatus.IDLE,
        )

        assert state.current_task is None
        assert state.context_usage == 0.0
        assert state.port is None

    def test_worker_state_to_dict(self) -> None:
        """Test WorkerState serialization."""
        state = WorkerState(
            worker_id=2,
            status=WorkerStatus.RUNNING,
            port=49154,
            current_task="TASK-001",
            context_usage=0.45,
        )

        state_dict = state.to_dict()

        assert state_dict["worker_id"] == 2
        assert state_dict["status"] == "running"
        assert state_dict["port"] == 49154
        assert state_dict["current_task"] == "TASK-001"
        assert state_dict["context_usage"] == 0.45

    def test_worker_state_from_dict(self) -> None:
        """Test WorkerState deserialization."""
        data = {
            "worker_id": 3,
            "status": "idle",
            "current_task": None,
            "port": 49155,
        }

        state = WorkerState.from_dict(data)

        assert state.worker_id == 3
        assert state.status == WorkerStatus.IDLE
        assert state.port == 49155


class TestLevelStatus:
    """Tests for LevelStatus dataclass."""

    def test_create_level_status(self) -> None:
        """Test creating a LevelStatus."""
        status = LevelStatus(
            level=Level.FOUNDATION,
            name="foundation",
            total_tasks=5,
            completed_tasks=3,
            status="running",
        )

        assert status.level == Level.FOUNDATION
        assert status.name == "foundation"
        assert status.total_tasks == 5
        assert status.completed_tasks == 3

    def test_level_status_is_complete(self) -> None:
        """Test LevelStatus completion check."""
        # Not complete
        status = LevelStatus(
            level=Level.FOUNDATION,
            name="foundation",
            total_tasks=5,
            completed_tasks=3,
            status="running",
        )
        assert not status.is_complete

        # Complete
        status = LevelStatus(
            level=Level.FOUNDATION,
            name="foundation",
            total_tasks=5,
            completed_tasks=5,
            status="complete",
        )
        assert status.is_complete

    def test_level_status_progress(self) -> None:
        """Test LevelStatus progress calculation."""
        status = LevelStatus(
            level=Level.FOUNDATION,
            name="foundation",
            total_tasks=10,
            completed_tasks=6,
            status="running",
        )

        assert status.progress_percent == 60.0

    def test_level_status_to_dict(self) -> None:
        """Test LevelStatus serialization."""
        status = LevelStatus(
            level=Level.CORE,
            name="core",
            total_tasks=8,
            completed_tasks=4,
            status="running",
        )

        status_dict = status.to_dict()

        assert status_dict["level"] == 2
        assert status_dict["name"] == "core"
        assert status_dict["total_tasks"] == 8
