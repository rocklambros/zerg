"""ZERG exception hierarchy."""

from typing import Any


class ZergError(Exception):
    """Base exception for all ZERG errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class ConfigurationError(ZergError):
    """Error in ZERG configuration."""

    pass


class TaskError(ZergError):
    """Base error for task-related issues."""

    def __init__(self, message: str, task_id: str | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details)
        self.task_id = task_id


class TaskVerificationFailedError(TaskError):
    """Task verification command failed."""

    def __init__(
        self,
        message: str,
        task_id: str,
        command: str,
        exit_code: int,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        super().__init__(message, task_id, {"command": command, "exit_code": exit_code})
        self.command = command
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr


class TaskDependencyError(TaskError):
    """Task has unresolved dependencies."""

    def __init__(self, message: str, task_id: str, missing_deps: list[str]) -> None:
        super().__init__(message, task_id, {"missing_dependencies": missing_deps})
        self.missing_deps = missing_deps


class TaskTimeoutError(TaskError):
    """Task execution timed out."""

    def __init__(self, message: str, task_id: str, timeout_seconds: int) -> None:
        super().__init__(message, task_id, {"timeout_seconds": timeout_seconds})
        self.timeout_seconds = timeout_seconds


class WorkerError(ZergError):
    """Base error for worker-related issues."""

    def __init__(self, message: str, worker_id: int | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details)
        self.worker_id = worker_id


class WorkerStartupError(WorkerError):
    """Worker failed to start."""

    pass


class WorkerCommunicationError(WorkerError):
    """Failed to communicate with worker."""

    pass


class WorktreeError(ZergError):
    """Error in worktree operations."""

    def __init__(self, message: str, worktree_path: str | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details)
        self.worktree_path = worktree_path


class GitError(ZergError):
    """Error in git operations."""

    def __init__(
        self,
        message: str,
        command: str | None = None,
        exit_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.command = command
        self.exit_code = exit_code


class MergeConflictError(GitError):
    """Merge conflict detected during branch merge."""

    def __init__(
        self,
        message: str,
        source_branch: str,
        target_branch: str,
        conflicting_files: list[str] | None = None,
    ) -> None:
        super().__init__(
            message,
            details={
                "source_branch": source_branch,
                "target_branch": target_branch,
                "conflicting_files": conflicting_files or [],
            },
        )
        self.source_branch = source_branch
        self.target_branch = target_branch
        self.conflicting_files = conflicting_files or []


class GateError(ZergError):
    """Base error for quality gate issues."""

    def __init__(self, message: str, gate_name: str | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details)
        self.gate_name = gate_name


class GateFailureError(GateError):
    """Quality gate check failed."""

    def __init__(
        self,
        message: str,
        gate_name: str,
        command: str,
        exit_code: int,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        super().__init__(message, gate_name, {"command": command, "exit_code": exit_code, "stdout": stdout})
        self.command = command
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr


class GateTimeoutError(GateError):
    """Quality gate timed out."""

    def __init__(self, message: str, gate_name: str, timeout_seconds: int) -> None:
        super().__init__(message, gate_name, {"timeout_seconds": timeout_seconds})
        self.timeout_seconds = timeout_seconds


class ContainerError(ZergError):
    """Error in container operations."""

    def __init__(
        self,
        message: str,
        container_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.container_id = container_id


class ValidationError(ZergError):
    """Error in data validation."""

    def __init__(self, message: str, field: str | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details)
        self.field = field


class StateError(ZergError):
    """Error in state management."""

    pass


class LevelError(ZergError):
    """Error in level management."""

    def __init__(self, message: str, level: int | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details)
        self.level = level


class OrchestratorError(ZergError):
    """Error in orchestrator operations."""

    pass
