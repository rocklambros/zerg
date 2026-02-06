"""Unit tests for ZERG exceptions module."""

import pytest

from zerg.exceptions import (
    ConfigurationError,
    ContainerError,
    GateError,
    GateFailureError,
    GateTimeoutError,
    GitError,
    LevelError,
    MergeConflictError,
    OrchestratorError,
    StateError,
    TaskDependencyError,
    TaskError,
    TaskTimeoutError,
    TaskVerificationFailedError,
    ValidationError,
    WorkerCommunicationError,
    WorkerError,
    WorkerStartupError,
    WorktreeError,
    ZergError,
)


class TestZergError:
    """Tests for base ZergError."""

    @pytest.mark.smoke
    def test_basic_error(self) -> None:
        """Test basic error creation."""
        error = ZergError("Test error")
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.details == {}

    @pytest.mark.smoke
    def test_error_with_details(self) -> None:
        """Test error with details."""
        error = ZergError("Error", details={"key": "value"})
        assert error.details == {"key": "value"}
        assert "key" in str(error)

    @pytest.mark.smoke
    def test_error_is_exception(self) -> None:
        """Test error is an exception."""
        error = ZergError("Test")
        assert isinstance(error, Exception)

        with pytest.raises(ZergError):
            raise error


class TestConfigurationError:
    """Tests for ConfigurationError."""

    def test_configuration_error(self) -> None:
        """Test ConfigurationError creation."""
        error = ConfigurationError("Invalid config")
        assert isinstance(error, ZergError)
        assert "Invalid config" in str(error)


class TestTaskError:
    """Tests for TaskError and subclasses."""

    def test_task_error_basic(self) -> None:
        """Test basic TaskError."""
        error = TaskError("Task failed")
        assert error.task_id is None
        assert "Task failed" in str(error)

    def test_task_error_with_task_id(self) -> None:
        """Test TaskError with task ID."""
        error = TaskError("Failed", task_id="TASK-001")
        assert error.task_id == "TASK-001"


class TestTaskVerificationFailed:
    """Tests for TaskVerificationFailedError."""

    def test_verification_failed(self) -> None:
        """Test TaskVerificationFailedError creation."""
        error = TaskVerificationFailedError(
            message="Verification failed",
            task_id="TASK-001",
            command="pytest",
            exit_code=1,
            stdout="output",
            stderr="error",
        )
        assert error.task_id == "TASK-001"
        assert error.command == "pytest"
        assert error.exit_code == 1
        assert error.stdout == "output"
        assert error.stderr == "error"


class TestTaskDependencyError:
    """Tests for TaskDependencyError."""

    def test_dependency_error(self) -> None:
        """Test TaskDependencyError creation."""
        error = TaskDependencyError(
            message="Missing deps",
            task_id="TASK-002",
            missing_deps=["TASK-001"],
        )
        assert error.task_id == "TASK-002"
        assert error.missing_deps == ["TASK-001"]


class TestTaskTimeoutError:
    """Tests for TaskTimeoutError."""

    def test_timeout_error(self) -> None:
        """Test TaskTimeoutError creation."""
        error = TaskTimeoutError(
            message="Timeout",
            task_id="TASK-001",
            timeout_seconds=300,
        )
        assert error.task_id == "TASK-001"
        assert error.timeout_seconds == 300


class TestWorkerError:
    """Tests for WorkerError and subclasses."""

    def test_worker_error_basic(self) -> None:
        """Test basic WorkerError."""
        error = WorkerError("Worker failed")
        assert error.worker_id is None

    def test_worker_error_with_id(self) -> None:
        """Test WorkerError with worker ID."""
        error = WorkerError("Failed", worker_id=5)
        assert error.worker_id == 5

    def test_worker_startup_error(self) -> None:
        """Test WorkerStartupError."""
        error = WorkerStartupError("Startup failed", worker_id=1)
        assert isinstance(error, WorkerError)

    def test_worker_communication_error(self) -> None:
        """Test WorkerCommunicationError."""
        error = WorkerCommunicationError("Communication failed")
        assert isinstance(error, WorkerError)


class TestWorktreeError:
    """Tests for WorktreeError."""

    def test_worktree_error(self) -> None:
        """Test WorktreeError creation."""
        error = WorktreeError("Worktree failed", worktree_path="/path/to/worktree")
        assert error.worktree_path == "/path/to/worktree"


class TestGitError:
    """Tests for GitError and MergeConflictError."""

    def test_git_error_basic(self) -> None:
        """Test basic GitError."""
        error = GitError("Git failed")
        assert error.command is None
        assert error.exit_code is None

    def test_git_error_with_command(self) -> None:
        """Test GitError with command details."""
        error = GitError("Failed", command="git merge", exit_code=1)
        assert error.command == "git merge"
        assert error.exit_code == 1


class TestMergeConflict:
    """Tests for MergeConflictError."""

    def test_merge_conflict(self) -> None:
        """Test MergeConflictError creation."""
        error = MergeConflictError(
            message="Conflict",
            source_branch="feature",
            target_branch="main",
            conflicting_files=["a.py", "b.py"],
        )
        assert error.source_branch == "feature"
        assert error.target_branch == "main"
        assert error.conflicting_files == ["a.py", "b.py"]

    def test_merge_conflict_no_files(self) -> None:
        """Test MergeConflictError without file list."""
        error = MergeConflictError(
            message="Conflict",
            source_branch="feature",
            target_branch="main",
        )
        assert error.conflicting_files == []


class TestGateError:
    """Tests for GateError and subclasses."""

    def test_gate_error_basic(self) -> None:
        """Test basic GateError."""
        error = GateError("Gate failed")
        assert error.gate_name is None

    def test_gate_error_with_name(self) -> None:
        """Test GateError with gate name."""
        error = GateError("Failed", gate_name="lint")
        assert error.gate_name == "lint"


class TestGateFailure:
    """Tests for GateFailureError."""

    def test_gate_failure(self) -> None:
        """Test GateFailureError creation."""
        error = GateFailureError(
            message="Lint failed",
            gate_name="lint",
            command="ruff check .",
            exit_code=1,
            stdout="errors",
            stderr="",
        )
        assert error.gate_name == "lint"
        assert error.command == "ruff check ."
        assert error.exit_code == 1


class TestGateTimeoutError:
    """Tests for GateTimeoutError."""

    def test_gate_timeout(self) -> None:
        """Test GateTimeoutError creation."""
        error = GateTimeoutError(
            message="Timeout",
            gate_name="test",
            timeout_seconds=60,
        )
        assert error.gate_name == "test"
        assert error.timeout_seconds == 60


class TestContainerError:
    """Tests for ContainerError."""

    def test_container_error(self) -> None:
        """Test ContainerError creation."""
        error = ContainerError("Container failed", container_id="abc123")
        assert error.container_id == "abc123"


class TestValidationError:
    """Tests for ValidationError."""

    def test_validation_error(self) -> None:
        """Test ValidationError creation."""
        error = ValidationError("Invalid", field="task_id")
        assert error.field == "task_id"


class TestStateError:
    """Tests for StateError."""

    def test_state_error(self) -> None:
        """Test StateError creation."""
        error = StateError("State corrupted")
        assert isinstance(error, ZergError)


class TestLevelError:
    """Tests for LevelError."""

    def test_level_error(self) -> None:
        """Test LevelError creation."""
        error = LevelError("Level failed", level=2)
        assert error.level == 2


class TestOrchestratorError:
    """Tests for OrchestratorError."""

    def test_orchestrator_error(self) -> None:
        """Test OrchestratorError creation."""
        error = OrchestratorError("Orchestration failed")
        assert isinstance(error, ZergError)
