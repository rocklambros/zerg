"""Tests for zerg.types module."""

from datetime import datetime

import pytest

from zerg.constants import GateResult, Level, MergeStatus, WorkerStatus
from zerg.types import (
    GateRunResult,
    LevelStatus,
    MergeResult,
    OrchestratorState,
    Task,
    TaskGraph,
    WorkerAssignmentEntry,
    WorkerAssignments,
    WorkerState,
)


class TestTask:
    """Tests for Task TypedDict."""

    @pytest.mark.smoke
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

    @pytest.mark.smoke
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

    @pytest.mark.smoke
    def test_required_fields(self, sample_task_graph: TaskGraph) -> None:
        """Test that required fields are present."""
        assert "feature" in sample_task_graph
        assert "tasks" in sample_task_graph
        assert "levels" in sample_task_graph

    @pytest.mark.smoke
    def test_tasks_list(self, sample_task_graph: TaskGraph) -> None:
        """Test tasks is a list."""
        tasks = sample_task_graph.get("tasks", [])
        assert isinstance(tasks, list)
        assert tasks

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

        # With some failed tasks: is_complete is False, is_resolved is True
        status = LevelStatus(
            level=Level.FOUNDATION,
            name="foundation",
            total_tasks=5,
            completed_tasks=3,
            failed_tasks=2,
            status="complete",
        )
        assert not status.is_complete
        assert status.is_resolved

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

    def test_level_status_progress_zero_tasks(self) -> None:
        """Test LevelStatus progress with zero total tasks returns 100%."""
        status = LevelStatus(
            level=Level.FOUNDATION,
            name="foundation",
            total_tasks=0,
            completed_tasks=0,
            status="complete",
        )

        assert status.progress_percent == 100.0

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

    def test_level_status_from_dict(self) -> None:
        """Test LevelStatus deserialization."""
        now = datetime.now()
        data = {
            "level": 2,
            "name": "core",
            "total_tasks": 10,
            "completed_tasks": 5,
            "failed_tasks": 1,
            "in_progress_tasks": 2,
            "status": "running",
            "started_at": now.isoformat(),
            "completed_at": None,
            "merge_commit": "abc123",
        }

        status = LevelStatus.from_dict(data)

        assert status.level == Level.CORE
        assert status.name == "core"
        assert status.total_tasks == 10
        assert status.completed_tasks == 5
        assert status.failed_tasks == 1
        assert status.in_progress_tasks == 2
        assert status.status == "running"
        assert status.started_at is not None
        assert status.completed_at is None
        assert status.merge_commit == "abc123"


class TestGateRunResult:
    """Tests for GateRunResult dataclass."""

    def test_create_gate_run_result(self) -> None:
        """Test creating a GateRunResult."""
        result = GateRunResult(
            gate_name="lint",
            result=GateResult.PASS,
            command="ruff check .",
            exit_code=0,
            stdout="All checks passed",
            stderr="",
            duration_ms=1500,
        )

        assert result.gate_name == "lint"
        assert result.result == GateResult.PASS
        assert result.command == "ruff check ."
        assert result.exit_code == 0

    def test_gate_run_result_to_dict(self) -> None:
        """Test GateRunResult serialization."""
        now = datetime.now()
        result = GateRunResult(
            gate_name="test",
            result=GateResult.FAIL,
            command="pytest",
            exit_code=1,
            stdout="1 failed",
            stderr="Error details",
            duration_ms=5000,
            timestamp=now,
        )

        result_dict = result.to_dict()

        assert result_dict["gate_name"] == "test"
        assert result_dict["result"] == "fail"
        assert result_dict["command"] == "pytest"
        assert result_dict["exit_code"] == 1
        assert result_dict["stdout"] == "1 failed"
        assert result_dict["stderr"] == "Error details"
        assert result_dict["duration_ms"] == 5000
        assert result_dict["timestamp"] == now.isoformat()


class TestMergeResult:
    """Tests for MergeResult dataclass."""

    def test_create_merge_result(self) -> None:
        """Test creating a MergeResult."""
        result = MergeResult(
            source_branch="feature/auth",
            target_branch="main",
            status=MergeStatus.MERGED,
            commit_sha="abc123def456",
        )

        assert result.source_branch == "feature/auth"
        assert result.target_branch == "main"
        assert result.status == MergeStatus.MERGED
        assert result.commit_sha == "abc123def456"

    def test_merge_result_with_conflicts(self) -> None:
        """Test MergeResult with conflict details."""
        result = MergeResult(
            source_branch="feature/auth",
            target_branch="main",
            status=MergeStatus.CONFLICT,
            conflicting_files=["src/auth.py", "tests/test_auth.py"],
            error_message="Merge conflict in src/auth.py",
        )

        assert result.status == MergeStatus.CONFLICT
        assert len(result.conflicting_files) == 2
        assert result.error_message is not None

    def test_merge_result_to_dict(self) -> None:
        """Test MergeResult serialization."""
        now = datetime.now()
        result = MergeResult(
            source_branch="feature/api",
            target_branch="develop",
            status=MergeStatus.MERGED,
            commit_sha="def789",
            conflicting_files=[],
            error_message=None,
            timestamp=now,
        )

        result_dict = result.to_dict()

        assert result_dict["source_branch"] == "feature/api"
        assert result_dict["target_branch"] == "develop"
        assert result_dict["status"] == "merged"
        assert result_dict["commit_sha"] == "def789"
        assert result_dict["conflicting_files"] == []
        assert result_dict["error_message"] is None
        assert result_dict["timestamp"] == now.isoformat()


class TestOrchestratorState:
    """Tests for OrchestratorState dataclass."""

    def test_create_orchestrator_state(self) -> None:
        """Test creating an OrchestratorState."""
        now = datetime.now()
        state = OrchestratorState(
            feature="user-auth",
            started_at=now,
            current_level=2,
        )

        assert state.feature == "user-auth"
        assert state.started_at == now
        assert state.current_level == 2
        assert state.workers == {}
        assert state.levels == {}

    def test_orchestrator_state_to_dict(self) -> None:
        """Test OrchestratorState serialization."""
        now = datetime.now()
        worker = WorkerState(
            worker_id=1,
            status=WorkerStatus.RUNNING,
            port=49152,
        )
        level = LevelStatus(
            level=Level.FOUNDATION,
            name="foundation",
            total_tasks=3,
            completed_tasks=1,
            status="running",
        )

        state = OrchestratorState(
            feature="api-endpoints",
            started_at=now,
            current_level=1,
            workers={1: worker},
            levels={1: level},
            execution_log=[{"timestamp": now.isoformat(), "event": "started", "data": {}}],
            paused=False,
            error=None,
        )

        state_dict = state.to_dict()

        assert state_dict["feature"] == "api-endpoints"
        assert state_dict["started_at"] == now.isoformat()
        assert state_dict["current_level"] == 1
        assert 1 in state_dict["workers"]
        assert state_dict["workers"][1]["worker_id"] == 1
        assert 1 in state_dict["levels"]
        assert state_dict["levels"][1]["name"] == "foundation"
        assert len(state_dict["execution_log"]) == 1
        assert state_dict["paused"] is False
        assert state_dict["error"] is None


class TestWorkerAssignmentEntry:
    """Tests for WorkerAssignmentEntry dataclass."""

    def test_create_worker_assignment_entry(self) -> None:
        """Test creating a WorkerAssignmentEntry."""
        entry = WorkerAssignmentEntry(
            task_id="TASK-001",
            worker_id=2,
            level=1,
            estimated_minutes=15,
        )

        assert entry.task_id == "TASK-001"
        assert entry.worker_id == 2
        assert entry.level == 1
        assert entry.estimated_minutes == 15

    def test_worker_assignment_entry_to_dict(self) -> None:
        """Test WorkerAssignmentEntry serialization."""
        entry = WorkerAssignmentEntry(
            task_id="TASK-002",
            worker_id=3,
            level=2,
            estimated_minutes=30,
        )

        entry_dict = entry.to_dict()

        assert entry_dict["task_id"] == "TASK-002"
        assert entry_dict["worker_id"] == 3
        assert entry_dict["level"] == 2
        assert entry_dict["estimated_minutes"] == 30


class TestWorkerAssignments:
    """Tests for WorkerAssignments dataclass."""

    def test_create_worker_assignments(self) -> None:
        """Test creating a WorkerAssignments."""
        assignments = WorkerAssignments(
            feature="user-auth",
            worker_count=3,
        )

        assert assignments.feature == "user-auth"
        assert assignments.worker_count == 3
        assert not assignments.assignments  # Empty list by default

    def test_get_worker_tasks(self) -> None:
        """Test getting all tasks for a worker."""
        entry1 = WorkerAssignmentEntry("TASK-001", 1, 1, 10)
        entry2 = WorkerAssignmentEntry("TASK-002", 1, 1, 15)
        entry3 = WorkerAssignmentEntry("TASK-003", 2, 1, 20)

        assignments = WorkerAssignments(
            feature="feature",
            worker_count=2,
            assignments=[entry1, entry2, entry3],
        )

        worker1_tasks = assignments.get_worker_tasks(1)
        worker2_tasks = assignments.get_worker_tasks(2)

        assert worker1_tasks == ["TASK-001", "TASK-002"]
        assert worker2_tasks == ["TASK-003"]

    def test_get_worker_tasks_no_assignments(self) -> None:
        """Test getting tasks for worker with no assignments."""
        assignments = WorkerAssignments(
            feature="feature",
            worker_count=2,
            assignments=[],
        )

        tasks = assignments.get_worker_tasks(1)

        assert not tasks

    def test_get_task_worker(self) -> None:
        """Test getting the worker assigned to a task."""
        entry1 = WorkerAssignmentEntry("TASK-001", 1, 1, 10)
        entry2 = WorkerAssignmentEntry("TASK-002", 2, 1, 15)

        assignments = WorkerAssignments(
            feature="feature",
            worker_count=2,
            assignments=[entry1, entry2],
        )

        assert assignments.get_task_worker("TASK-001") == 1
        assert assignments.get_task_worker("TASK-002") == 2

    def test_get_task_worker_not_found(self) -> None:
        """Test getting worker for unassigned task returns None."""
        entry = WorkerAssignmentEntry("TASK-001", 1, 1, 10)

        assignments = WorkerAssignments(
            feature="feature",
            worker_count=1,
            assignments=[entry],
        )

        result = assignments.get_task_worker("TASK-999")

        assert result is None

    def test_worker_assignments_to_dict(self) -> None:
        """Test WorkerAssignments serialization."""
        now = datetime.now()
        entry = WorkerAssignmentEntry("TASK-001", 1, 1, 10)

        assignments = WorkerAssignments(
            feature="api-feature",
            worker_count=3,
            assignments=[entry],
            generated_at=now,
        )

        assignments_dict = assignments.to_dict()

        assert assignments_dict["feature"] == "api-feature"
        assert assignments_dict["worker_count"] == 3
        assert len(assignments_dict["assignments"]) == 1
        assert assignments_dict["assignments"][0]["task_id"] == "TASK-001"
        assert assignments_dict["generated_at"] == now.isoformat()
