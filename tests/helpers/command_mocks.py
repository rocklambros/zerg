"""Reusable mock utilities for testing ZERG commands.

This module provides configurable mock objects and fixtures for testing
ZERG orchestration, launching, git operations, filesystem, and subprocess
execution without requiring actual processes or system resources.

Example usage:
    def test_orchestrator_level_execution(mock_orchestrator):
        orch = mock_orchestrator(feature="test-feature", worker_count=3)
        orch.execute_level(1)
        assert orch.levels[1].status == "complete"

    def test_worker_spawn(mock_launcher):
        launcher = mock_launcher(spawn_delay=0.1)
        result = launcher.spawn(worker_id=0, feature="test", ...)
        assert result.success

    def test_git_merge(mock_git_ops):
        git = mock_git_ops(has_conflicts=False)
        commit = git.merge("feature-branch")
        assert commit.startswith("abc123")
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from zerg.constants import (
    GateResult,
    Level,
    LevelMergeStatus,
    WorkerStatus,
)
from zerg.merge import MergeFlowResult
from zerg.types import (
    GateRunResult,
    LevelStatus,
    WorkerState,
)

# =============================================================================
# MockOrchestrator - Simulates level execution and state management
# =============================================================================


@dataclass
class MockLevelExecution:
    """Tracks execution state for a single level."""

    level: int
    tasks: list[str]
    status: str = "pending"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    merge_commit: str | None = None
    merge_status: LevelMergeStatus = LevelMergeStatus.PENDING


@dataclass
class MockOrchestratorState:
    """Simulated orchestrator state for testing.

    Attributes:
        feature: Feature name being orchestrated
        current_level: Currently executing level
        levels: Level execution tracking
        workers: Worker state mapping
        events: Event log for verification
        paused: Whether execution is paused
        error: Current error state
    """

    feature: str
    current_level: int = 1
    levels: dict[int, MockLevelExecution] = field(default_factory=dict)
    workers: dict[int, WorkerState] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    paused: bool = False
    error: str | None = None
    running: bool = False


class MockOrchestrator:
    """Configurable mock orchestrator for testing command interactions.

    Simulates level execution, worker management, and state transitions
    without spawning actual processes or containers.

    Example:
        orch = MockOrchestrator("test-feature")
        orch.configure(worker_count=3, fail_at_level=2)
        orch.start_level(1)
        assert orch.state.current_level == 1
        orch.complete_level(1)
        assert orch.state.levels[1].status == "complete"
    """

    def __init__(
        self,
        feature: str,
        worker_count: int = 5,
        task_graph: dict[int, list[str]] | None = None,
    ) -> None:
        """Initialize mock orchestrator.

        Args:
            feature: Feature name
            worker_count: Number of simulated workers
            task_graph: Mapping of level -> task IDs (auto-generated if None)
        """
        self.feature = feature
        self.worker_count = worker_count
        self.state = MockOrchestratorState(feature=feature)

        # Default task graph: 3 levels with 2-3 tasks each
        self._task_graph = task_graph or {
            1: ["TASK-001", "TASK-002"],
            2: ["TASK-003", "TASK-004", "TASK-005"],
            3: ["TASK-006"],
        }

        # Configure behavior
        self._fail_at_level: int | None = None
        self._conflict_at_level: int | None = None
        self._gate_failures: set[int] = set()
        self._level_callbacks: list[Callable[[int], None]] = []
        self._task_callbacks: list[Callable[[str], None]] = []

        # Initialize levels
        for level, tasks in self._task_graph.items():
            self.state.levels[level] = MockLevelExecution(
                level=level,
                tasks=tasks,
            )

    def configure(
        self,
        fail_at_level: int | None = None,
        conflict_at_level: int | None = None,
        gate_failure_levels: list[int] | None = None,
    ) -> MockOrchestrator:
        """Configure mock behavior.

        Args:
            fail_at_level: Level number to simulate failure at
            conflict_at_level: Level to simulate merge conflict at
            gate_failure_levels: Levels where gates should fail

        Returns:
            Self for chaining
        """
        self._fail_at_level = fail_at_level
        self._conflict_at_level = conflict_at_level
        self._gate_failures = set(gate_failure_levels or [])
        return self

    def start(self, start_level: int = 1) -> None:
        """Start orchestration simulation.

        Args:
            start_level: Level to start at
        """
        self.state.running = True
        self.state.current_level = start_level
        self._append_event(
            "rush_started",
            {
                "workers": self.worker_count,
                "total_tasks": sum(len(t) for t in self._task_graph.values()),
            },
        )

    def stop(self, force: bool = False) -> None:
        """Stop orchestration.

        Args:
            force: Force stop without cleanup
        """
        self.state.running = False
        self._append_event("rush_stopped", {"force": force})

    def start_level(self, level: int) -> list[str]:
        """Start a level.

        Args:
            level: Level number to start

        Returns:
            List of task IDs in the level
        """
        if level not in self.state.levels:
            raise ValueError(f"Level {level} not found")

        level_exec = self.state.levels[level]
        level_exec.status = "running"
        level_exec.started_at = datetime.now()
        self.state.current_level = level

        self._append_event(
            "level_started",
            {
                "level": level,
                "tasks": len(level_exec.tasks),
            },
        )

        return level_exec.tasks

    def complete_level(self, level: int, merge_commit: str = "abc123def") -> bool:
        """Complete a level with merge.

        Args:
            level: Level number
            merge_commit: Simulated merge commit SHA

        Returns:
            True if level completed successfully
        """
        if level not in self.state.levels:
            raise ValueError(f"Level {level} not found")

        level_exec = self.state.levels[level]

        # Check for configured failures
        if level == self._fail_at_level:
            level_exec.status = "failed"
            level_exec.merge_status = LevelMergeStatus.FAILED
            self.state.error = f"Simulated failure at level {level}"
            self._append_event("level_failed", {"level": level})
            return False

        if level == self._conflict_at_level:
            level_exec.status = "conflict"
            level_exec.merge_status = LevelMergeStatus.CONFLICT
            self.state.paused = True
            self._append_event("merge_conflict", {"level": level})
            return False

        if level in self._gate_failures:
            level_exec.status = "gate_failed"
            level_exec.merge_status = LevelMergeStatus.FAILED
            self._append_event("gate_failed", {"level": level})
            return False

        # Success path
        level_exec.status = "complete"
        level_exec.completed_at = datetime.now()
        level_exec.merge_commit = merge_commit
        level_exec.merge_status = LevelMergeStatus.COMPLETE

        self._append_event(
            "level_complete",
            {
                "level": level,
                "merge_commit": merge_commit,
            },
        )

        for callback in self._level_callbacks:
            callback(level)

        return True

    def execute_level(self, level: int) -> bool:
        """Execute a complete level cycle.

        Simulates starting a level, running tasks, and completing merge.

        Args:
            level: Level to execute

        Returns:
            True if level completed successfully
        """
        self.start_level(level)
        return self.complete_level(level)

    def advance_to_next_level(self) -> int | None:
        """Advance to the next level if possible.

        Returns:
            Next level number or None if complete
        """
        current = self.state.current_level
        next_level = current + 1

        if next_level not in self.state.levels:
            return None

        self.state.current_level = next_level
        return next_level

    def status(self) -> dict[str, Any]:
        """Get current orchestration status.

        Returns:
            Status dictionary matching Orchestrator.status() format
        """
        total_tasks = sum(len(lvl.tasks) for lvl in self.state.levels.values())
        completed_tasks = sum(len(lvl.tasks) for lvl in self.state.levels.values() if lvl.status == "complete")

        return {
            "feature": self.feature,
            "running": self.state.running,
            "current_level": self.state.current_level,
            "progress": {
                "total": total_tasks,
                "completed": completed_tasks,
                "failed": 0,
                "in_progress": 0,
                "percent": (completed_tasks / total_tasks * 100) if total_tasks else 0,
            },
            "workers": {
                wid: {
                    "status": w.status.value,
                    "current_task": w.current_task,
                    "tasks_completed": w.tasks_completed,
                }
                for wid, w in self.state.workers.items()
            },
            "levels": {
                lvl: {
                    "status": exec_.status,
                    "tasks": len(exec_.tasks),
                    "merge_commit": exec_.merge_commit,
                }
                for lvl, exec_ in self.state.levels.items()
            },
            "is_complete": all(lvl.status == "complete" for lvl in self.state.levels.values()),
        }

    def on_level_complete(self, callback: Callable[[int], None]) -> None:
        """Register level completion callback.

        Args:
            callback: Function to call with level number
        """
        self._level_callbacks.append(callback)

    def on_task_complete(self, callback: Callable[[str], None]) -> None:
        """Register task completion callback.

        Args:
            callback: Function to call with task ID
        """
        self._task_callbacks.append(callback)

    def _append_event(self, event: str, data: dict[str, Any]) -> None:
        """Add event to log.

        Args:
            event: Event type
            data: Event data
        """
        self.state.events.append(
            {
                "timestamp": datetime.now().isoformat(),
                "event": event,
                "data": data,
            }
        )

    def get_events(self, event_type: str | None = None) -> list[dict[str, Any]]:
        """Get events from log.

        Args:
            event_type: Filter by event type

        Returns:
            List of events
        """
        if event_type is None:
            return self.state.events
        return [e for e in self.state.events if e["event"] == event_type]


# =============================================================================
# MockLauncher - Simulates worker spawning without actual processes
# =============================================================================


@dataclass
class MockWorkerHandle:
    """Mock handle for a simulated worker."""

    worker_id: int
    pid: int | None = None
    container_id: str | None = None
    status: WorkerStatus = WorkerStatus.INITIALIZING
    started_at: datetime = field(default_factory=datetime.now)
    exit_code: int | None = None

    def is_alive(self) -> bool:
        """Check if worker is considered alive."""
        return self.status in (
            WorkerStatus.INITIALIZING,
            WorkerStatus.READY,
            WorkerStatus.RUNNING,
            WorkerStatus.IDLE,
            WorkerStatus.CHECKPOINTING,
        )


@dataclass
class MockSpawnResult:
    """Result of mock spawn operation."""

    success: bool
    worker_id: int
    handle: MockWorkerHandle | None = None
    error: str | None = None


class MockLauncher:
    """Simulates worker spawning without creating actual processes.

    Tracks spawn/terminate operations and allows configuring failure scenarios.

    Example:
        launcher = MockLauncher()
        launcher.configure(fail_spawn_ids={2})  # Worker 2 will fail to spawn

        result = launcher.spawn(worker_id=0, feature="test", ...)
        assert result.success

        result = launcher.spawn(worker_id=2, feature="test", ...)
        assert not result.success
    """

    def __init__(self, use_containers: bool = False) -> None:
        """Initialize mock launcher.

        Args:
            use_containers: Simulate container mode (vs subprocess)
        """
        self.use_containers = use_containers
        self._workers: dict[int, MockWorkerHandle] = {}
        self._spawn_count = 0
        self._terminate_count = 0

        # Configurable behavior
        self._fail_spawn_ids: set[int] = set()
        self._crash_worker_ids: set[int] = set()
        self._checkpoint_worker_ids: set[int] = set()
        self._spawn_delay: float = 0.0

    def configure(
        self,
        fail_spawn_ids: set[int] | None = None,
        crash_worker_ids: set[int] | None = None,
        checkpoint_worker_ids: set[int] | None = None,
        spawn_delay: float = 0.0,
    ) -> MockLauncher:
        """Configure mock behavior.

        Args:
            fail_spawn_ids: Worker IDs that should fail to spawn
            crash_worker_ids: Worker IDs that should crash after starting
            checkpoint_worker_ids: Worker IDs that should checkpoint
            spawn_delay: Simulated spawn delay in seconds

        Returns:
            Self for chaining
        """
        self._fail_spawn_ids = fail_spawn_ids or set()
        self._crash_worker_ids = crash_worker_ids or set()
        self._checkpoint_worker_ids = checkpoint_worker_ids or set()
        self._spawn_delay = spawn_delay
        return self

    def spawn(
        self,
        worker_id: int,
        feature: str,
        worktree_path: Path,
        branch: str,
        env: dict[str, str] | None = None,
    ) -> MockSpawnResult:
        """Simulate spawning a worker.

        Args:
            worker_id: Worker identifier
            feature: Feature name
            worktree_path: Path to worktree
            branch: Git branch
            env: Environment variables

        Returns:
            MockSpawnResult with handle or error
        """
        self._spawn_count += 1

        if worker_id in self._fail_spawn_ids:
            return MockSpawnResult(
                success=False,
                worker_id=worker_id,
                error=f"Simulated spawn failure for worker {worker_id}",
            )

        # Create handle
        handle = MockWorkerHandle(
            worker_id=worker_id,
            pid=10000 + worker_id if not self.use_containers else None,
            container_id=f"mock-container-{worker_id}" if self.use_containers else None,
            status=WorkerStatus.RUNNING,
        )

        self._workers[worker_id] = handle

        return MockSpawnResult(
            success=True,
            worker_id=worker_id,
            handle=handle,
        )

    def monitor(self, worker_id: int) -> WorkerStatus:
        """Check simulated worker status.

        Args:
            worker_id: Worker to check

        Returns:
            Current worker status
        """
        handle = self._workers.get(worker_id)
        if not handle:
            return WorkerStatus.STOPPED

        # Check for configured status overrides
        if worker_id in self._crash_worker_ids:
            handle.status = WorkerStatus.CRASHED
            handle.exit_code = 1

        if worker_id in self._checkpoint_worker_ids:
            handle.status = WorkerStatus.CHECKPOINTING
            handle.exit_code = 2

        return handle.status

    def terminate(self, worker_id: int, force: bool = False) -> bool:
        """Simulate terminating a worker.

        Args:
            worker_id: Worker to terminate
            force: Force termination

        Returns:
            True if termination succeeded
        """
        handle = self._workers.get(worker_id)
        if not handle:
            return False

        self._terminate_count += 1
        handle.status = WorkerStatus.STOPPED
        handle.exit_code = 0

        return True

    def get_output(self, worker_id: int, tail: int = 100) -> str:
        """Get simulated worker output.

        Args:
            worker_id: Worker to get output from
            tail: Number of lines

        Returns:
            Simulated output string
        """
        if worker_id not in self._workers:
            return ""
        return f"[Mock output for worker {worker_id}]\nSimulated log lines..."

    def get_handle(self, worker_id: int) -> MockWorkerHandle | None:
        """Get worker handle.

        Args:
            worker_id: Worker identifier

        Returns:
            MockWorkerHandle or None
        """
        return self._workers.get(worker_id)

    def get_all_workers(self) -> dict[int, MockWorkerHandle]:
        """Get all worker handles.

        Returns:
            Dictionary of worker_id to handle
        """
        return self._workers.copy()

    def terminate_all(self, force: bool = False) -> dict[int, bool]:
        """Terminate all workers.

        Args:
            force: Force termination

        Returns:
            Dictionary of worker_id to success
        """
        results = {}
        for worker_id in list(self._workers.keys()):
            results[worker_id] = self.terminate(worker_id, force=force)
        return results

    def get_spawn_count(self) -> int:
        """Get total spawn attempts."""
        return self._spawn_count

    def get_terminate_count(self) -> int:
        """Get total terminate calls."""
        return self._terminate_count


# =============================================================================
# MockGitOps - Simulates git operations
# =============================================================================


@dataclass
class MockBranchInfo:
    """Mock branch information."""

    name: str
    commit: str
    is_current: bool = False


class MockGitOps:
    """Simulates git operations without actual repository access.

    Tracks branch operations, commits, and merges in memory.

    Example:
        git = MockGitOps()
        git.configure(has_conflicts=False)

        git.create_branch("feature-branch", "main")
        commit = git.merge("feature-branch")
        assert commit is not None
    """

    def __init__(self, repo_path: str | Path = ".") -> None:
        """Initialize mock git operations.

        Args:
            repo_path: Simulated repository path
        """
        self.repo_path = Path(repo_path)
        self._current_branch = "main"
        self._branches: dict[str, str] = {"main": "initial123"}
        self._commits: list[str] = ["initial123"]
        self._changes_staged = False
        self._stash: list[str] = []

        # Configurable behavior
        self._has_conflicts = False
        self._conflicting_files: list[str] = []
        self._fail_checkout: set[str] = set()
        self._fail_merge: set[str] = set()

    def configure(
        self,
        has_conflicts: bool = False,
        conflicting_files: list[str] | None = None,
        fail_checkout_branches: list[str] | None = None,
        fail_merge_branches: list[str] | None = None,
    ) -> MockGitOps:
        """Configure mock behavior.

        Args:
            has_conflicts: Whether merges should have conflicts
            conflicting_files: Files that conflict
            fail_checkout_branches: Branches that fail checkout
            fail_merge_branches: Branches that fail merge

        Returns:
            Self for chaining
        """
        self._has_conflicts = has_conflicts
        self._conflicting_files = conflicting_files or []
        self._fail_checkout = set(fail_checkout_branches or [])
        self._fail_merge = set(fail_merge_branches or [])
        return self

    def current_branch(self) -> str:
        """Get current branch name."""
        return self._current_branch

    def current_commit(self) -> str:
        """Get current commit SHA."""
        return self._branches.get(self._current_branch, "unknown")

    def branch_exists(self, branch: str) -> bool:
        """Check if branch exists."""
        return branch in self._branches

    def create_branch(self, branch: str, base: str = "HEAD") -> str:
        """Create a new branch.

        Args:
            branch: Branch name
            base: Base ref

        Returns:
            Commit SHA
        """
        base_commit = self._branches.get(
            base if base != "HEAD" else self._current_branch,
            "unknown",
        )
        self._branches[branch] = base_commit
        return base_commit

    def delete_branch(self, branch: str, force: bool = False) -> None:
        """Delete a branch.

        Args:
            branch: Branch name
            force: Force delete
        """
        if branch in self._branches and branch != self._current_branch:
            del self._branches[branch]

    def checkout(self, ref: str) -> None:
        """Checkout a branch or commit.

        Args:
            ref: Branch or commit

        Raises:
            RuntimeError: If checkout fails
        """
        if ref in self._fail_checkout:
            raise RuntimeError(f"Simulated checkout failure for {ref}")

        if ref in self._branches:
            self._current_branch = ref

    def get_commit(self, ref: str = "HEAD") -> str:
        """Get commit SHA for ref."""
        if ref == "HEAD":
            ref = self._current_branch
        return self._branches.get(ref, "unknown")

    def has_changes(self) -> bool:
        """Check for uncommitted changes."""
        return self._changes_staged

    def has_conflicts(self) -> bool:
        """Check for merge conflicts."""
        return self._has_conflicts and len(self._conflicting_files) > 0

    def get_conflicting_files(self) -> list[str]:
        """Get list of conflicting files."""
        return self._conflicting_files if self._has_conflicts else []

    def commit(
        self,
        message: str,
        add_all: bool = False,
        allow_empty: bool = False,
    ) -> str:
        """Create a commit.

        Args:
            message: Commit message
            add_all: Stage all changes
            allow_empty: Allow empty commit

        Returns:
            Commit SHA
        """
        new_commit = f"commit{len(self._commits):04d}"
        self._commits.append(new_commit)
        self._branches[self._current_branch] = new_commit
        self._changes_staged = False
        return new_commit

    def merge(
        self,
        branch: str,
        message: str | None = None,
        no_ff: bool = True,
    ) -> str:
        """Merge a branch.

        Args:
            branch: Branch to merge
            message: Merge message
            no_ff: No fast-forward

        Returns:
            Merge commit SHA

        Raises:
            RuntimeError: If merge fails or has conflicts
        """
        if branch in self._fail_merge:
            raise RuntimeError(f"Simulated merge failure for {branch}")

        if self._has_conflicts:
            from zerg.exceptions import MergeConflictError

            raise MergeConflictError(
                f"Merge conflict: {branch}",
                source_branch=branch,
                target_branch=self._current_branch,
                conflicting_files=self._conflicting_files,
            )

        return self.commit(message or f"Merge {branch}")

    def abort_merge(self) -> None:
        """Abort merge."""
        self._has_conflicts = False
        self._conflicting_files = []

    def rebase(self, onto: str) -> None:
        """Rebase current branch.

        Args:
            onto: Branch to rebase onto
        """
        if self._has_conflicts:
            from zerg.exceptions import MergeConflictError

            raise MergeConflictError(
                f"Rebase conflict onto {onto}",
                source_branch=self._current_branch,
                target_branch=onto,
                conflicting_files=self._conflicting_files,
            )

    def abort_rebase(self) -> None:
        """Abort rebase."""
        pass

    def create_staging_branch(self, feature: str, base: str = "main") -> str:
        """Create staging branch.

        Args:
            feature: Feature name
            base: Base branch

        Returns:
            Staging branch name
        """
        staging = f"zerg/{feature}/staging"
        self.create_branch(staging, base)
        return staging

    def list_branches(self, pattern: str | None = None) -> list[MockBranchInfo]:
        """List branches.

        Args:
            pattern: Filter pattern

        Returns:
            List of branch info
        """
        result = []
        for name, commit in self._branches.items():
            if pattern is None or name.startswith(pattern.replace("*", "")):
                result.append(
                    MockBranchInfo(
                        name=name,
                        commit=commit,
                        is_current=(name == self._current_branch),
                    )
                )
        return result

    def list_worker_branches(self, feature: str) -> list[str]:
        """List worker branches for feature.

        Args:
            feature: Feature name

        Returns:
            List of branch names
        """
        prefix = f"zerg/{feature}/worker-"
        return [b for b in self._branches if b.startswith(prefix)]

    def delete_feature_branches(self, feature: str, force: bool = True) -> int:
        """Delete all feature branches.

        Args:
            feature: Feature name
            force: Force delete

        Returns:
            Number deleted
        """
        prefix = f"zerg/{feature}/"
        to_delete = [b for b in self._branches if b.startswith(prefix)]
        for branch in to_delete:
            self.delete_branch(branch, force)
        return len(to_delete)

    def stash(self, message: str | None = None) -> bool:
        """Stash changes."""
        if not self._changes_staged:
            return False
        self._stash.append(message or "stash")
        self._changes_staged = False
        return True

    def stash_pop(self) -> None:
        """Pop stash."""
        if self._stash:
            self._stash.pop()
            self._changes_staged = True

    def add_branch(self, name: str, commit: str | None = None) -> None:
        """Helper to add a branch for testing.

        Args:
            name: Branch name
            commit: Optional specific commit SHA
        """
        self._branches[name] = commit or f"commit_{name}"

    def simulate_changes(self) -> None:
        """Helper to simulate staged changes."""
        self._changes_staged = True


# =============================================================================
# MockFilesystem - Simulates file operations
# =============================================================================


class MockFilesystem:
    """Simulates file system operations in memory.

    Tracks file creates, reads, writes, and directory operations.

    Example:
        fs = MockFilesystem()
        fs.write("/path/to/file.txt", "content")
        assert fs.exists("/path/to/file.txt")
        assert fs.read("/path/to/file.txt") == "content"
    """

    def __init__(self, base_path: Path | None = None) -> None:
        """Initialize mock filesystem.

        Args:
            base_path: Optional base path for relative operations
        """
        self.base_path = base_path or Path("/mock")
        self._files: dict[str, str] = {}
        self._directories: set[str] = {str(self.base_path)}
        self._read_count: dict[str, int] = {}
        self._write_count: dict[str, int] = {}

    def _resolve(self, path: str | Path) -> str:
        """Resolve path to absolute string."""
        p = Path(path)
        if not p.is_absolute():
            p = self.base_path / p
        return str(p)

    def exists(self, path: str | Path) -> bool:
        """Check if path exists.

        Args:
            path: Path to check

        Returns:
            True if exists as file or directory
        """
        resolved = self._resolve(path)
        return resolved in self._files or resolved in self._directories

    def is_file(self, path: str | Path) -> bool:
        """Check if path is a file."""
        return self._resolve(path) in self._files

    def is_dir(self, path: str | Path) -> bool:
        """Check if path is a directory."""
        return self._resolve(path) in self._directories

    def read(self, path: str | Path) -> str:
        """Read file content.

        Args:
            path: Path to read

        Returns:
            File content

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        resolved = self._resolve(path)
        if resolved not in self._files:
            raise FileNotFoundError(f"No such file: {path}")

        self._read_count[resolved] = self._read_count.get(resolved, 0) + 1
        return self._files[resolved]

    def write(self, path: str | Path, content: str) -> None:
        """Write content to file.

        Args:
            path: Path to write
            content: Content to write
        """
        resolved = self._resolve(path)
        parent = str(Path(resolved).parent)

        # Auto-create parent directories
        self._ensure_dir(parent)

        self._files[resolved] = content
        self._write_count[resolved] = self._write_count.get(resolved, 0) + 1

    def mkdir(self, path: str | Path, parents: bool = False) -> None:
        """Create directory.

        Args:
            path: Directory path
            parents: Create parent directories

        Raises:
            FileExistsError: If exists and not a directory
        """
        resolved = self._resolve(path)

        if resolved in self._files:
            raise FileExistsError(f"File exists: {path}")

        if parents:
            self._ensure_dir(resolved)
        else:
            parent = str(Path(resolved).parent)
            if parent not in self._directories:
                raise FileNotFoundError(f"No such directory: {parent}")
            self._directories.add(resolved)

    def _ensure_dir(self, path: str) -> None:
        """Ensure directory exists, creating parents as needed."""
        parts = Path(path).parts
        current = ""
        for part in parts:
            current = str(Path(current) / part) if current else part
            if current.startswith("/"):
                self._directories.add(current)
            else:
                self._directories.add("/" + current)

    def remove(self, path: str | Path) -> None:
        """Remove file.

        Args:
            path: Path to remove

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        resolved = self._resolve(path)
        if resolved not in self._files:
            raise FileNotFoundError(f"No such file: {path}")
        del self._files[resolved]

    def rmdir(self, path: str | Path) -> None:
        """Remove directory.

        Args:
            path: Directory to remove

        Raises:
            OSError: If not empty
        """
        resolved = self._resolve(path)
        if resolved not in self._directories:
            raise FileNotFoundError(f"No such directory: {path}")

        # Check if empty
        for f in self._files:
            if f.startswith(resolved + "/"):
                raise OSError(f"Directory not empty: {path}")
        for d in self._directories:
            if d.startswith(resolved + "/"):
                raise OSError(f"Directory not empty: {path}")

        self._directories.remove(resolved)

    def listdir(self, path: str | Path) -> list[str]:
        """List directory contents.

        Args:
            path: Directory path

        Returns:
            List of names in directory
        """
        resolved = self._resolve(path)
        if resolved not in self._directories:
            raise FileNotFoundError(f"No such directory: {path}")

        prefix = resolved + "/"
        names = set()

        for f in self._files:
            if f.startswith(prefix):
                rel = f[len(prefix) :]
                if "/" in rel:
                    names.add(rel.split("/")[0])
                else:
                    names.add(rel)

        for d in self._directories:
            if d.startswith(prefix):
                rel = d[len(prefix) :]
                if "/" in rel:
                    names.add(rel.split("/")[0])
                elif rel:
                    names.add(rel)

        return sorted(names)

    def get_read_count(self, path: str | Path) -> int:
        """Get number of times file was read."""
        return self._read_count.get(self._resolve(path), 0)

    def get_write_count(self, path: str | Path) -> int:
        """Get number of times file was written."""
        return self._write_count.get(self._resolve(path), 0)

    def clear(self) -> None:
        """Clear all files and directories."""
        self._files.clear()
        self._directories.clear()
        self._directories.add(str(self.base_path))
        self._read_count.clear()
        self._write_count.clear()


# =============================================================================
# MockSubprocess - Captures command execution
# =============================================================================


@dataclass
class CapturedCommand:
    """Record of a captured command execution."""

    args: list[str]
    kwargs: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


class MockSubprocess:
    """Captures and simulates subprocess execution.

    Records all command executions without running actual processes.
    Can be configured to return specific outputs for command patterns.

    Example:
        mock_sp = MockSubprocess()
        mock_sp.register_output(["git", "status"], stdout="On branch main")
        mock_sp.register_output(["pytest"], returncode=1, stderr="Test failed")

        # Use in test
        result = mock_sp.run(["git", "status"])
        assert "On branch main" in result.stdout
    """

    def __init__(self) -> None:
        """Initialize mock subprocess."""
        self._commands: list[CapturedCommand] = []
        self._outputs: dict[tuple[str, ...], dict[str, Any]] = {}
        self._default_returncode = 0
        self._default_stdout = ""
        self._default_stderr = ""

    def register_output(
        self,
        cmd_pattern: list[str],
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
    ) -> MockSubprocess:
        """Register expected output for a command pattern.

        Args:
            cmd_pattern: Command prefix to match
            returncode: Return code
            stdout: Standard output
            stderr: Standard error

        Returns:
            Self for chaining
        """
        key = tuple(cmd_pattern)
        self._outputs[key] = {
            "returncode": returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
        return self

    def set_defaults(
        self,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
    ) -> MockSubprocess:
        """Set default outputs for unregistered commands.

        Args:
            returncode: Default return code
            stdout: Default stdout
            stderr: Default stderr

        Returns:
            Self for chaining
        """
        self._default_returncode = returncode
        self._default_stdout = stdout
        self._default_stderr = stderr
        return self

    def run(
        self,
        args: list[str],
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
        timeout: float | None = None,
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> MagicMock:
        """Simulate subprocess.run.

        Args:
            args: Command arguments
            capture_output: Capture stdout/stderr
            text: Text mode
            check: Raise on non-zero exit
            timeout: Timeout (not enforced)
            cwd: Working directory
            env: Environment
            **kwargs: Additional arguments

        Returns:
            Mock CompletedProcess-like object

        Raises:
            subprocess.CalledProcessError: If check=True and returncode != 0
        """
        import subprocess

        # Find matching output
        output = self._find_output(args)

        captured = CapturedCommand(
            args=args,
            kwargs={
                "capture_output": capture_output,
                "text": text,
                "check": check,
                "timeout": timeout,
                "cwd": str(cwd) if cwd else None,
                "env": env,
                **kwargs,
            },
            returncode=output["returncode"],
            stdout=output["stdout"],
            stderr=output["stderr"],
        )
        self._commands.append(captured)

        # Create result
        result = MagicMock()
        result.returncode = output["returncode"]
        result.stdout = output["stdout"]
        result.stderr = output["stderr"]
        result.args = args

        if check and output["returncode"] != 0:
            raise subprocess.CalledProcessError(
                output["returncode"],
                args,
                output["stdout"],
                output["stderr"],
            )

        return result

    def _find_output(self, args: list[str]) -> dict[str, Any]:
        """Find registered output for command.

        Args:
            args: Command arguments

        Returns:
            Output configuration
        """
        # Try exact matches first, then prefix matches
        for key in sorted(self._outputs.keys(), key=len, reverse=True):
            if args[: len(key)] == list(key):
                return self._outputs[key]

        return {
            "returncode": self._default_returncode,
            "stdout": self._default_stdout,
            "stderr": self._default_stderr,
        }

    def get_commands(
        self,
        filter_cmd: str | None = None,
    ) -> list[CapturedCommand]:
        """Get captured commands.

        Args:
            filter_cmd: Filter by command name (first arg)

        Returns:
            List of captured commands
        """
        if filter_cmd is None:
            return self._commands.copy()
        return [c for c in self._commands if c.args and c.args[0] == filter_cmd]

    def get_last_command(self) -> CapturedCommand | None:
        """Get most recent command."""
        return self._commands[-1] if self._commands else None

    def was_called_with(self, *args: str) -> bool:
        """Check if a command was called with given arguments.

        Args:
            *args: Arguments to check

        Returns:
            True if matching command was executed
        """
        args_list = list(args)
        return any(cmd.args[: len(args_list)] == args_list for cmd in self._commands)

    def call_count(self, cmd: str | None = None) -> int:
        """Get number of command executions.

        Args:
            cmd: Filter by command name

        Returns:
            Number of executions
        """
        if cmd is None:
            return len(self._commands)
        return len([c for c in self._commands if c.args and c.args[0] == cmd])

    def clear(self) -> None:
        """Clear captured commands."""
        self._commands.clear()


# =============================================================================
# Pytest Fixtures
# =============================================================================


@pytest.fixture
def mock_orchestrator() -> Callable[..., MockOrchestrator]:
    """Factory fixture for creating MockOrchestrator instances.

    Example:
        def test_example(mock_orchestrator):
            orch = mock_orchestrator("test-feature", worker_count=3)
            orch.configure(fail_at_level=2)
            ...
    """

    def factory(
        feature: str = "test-feature",
        worker_count: int = 5,
        task_graph: dict[int, list[str]] | None = None,
    ) -> MockOrchestrator:
        return MockOrchestrator(feature, worker_count, task_graph)

    return factory


@pytest.fixture
def mock_launcher() -> Callable[..., MockLauncher]:
    """Factory fixture for creating MockLauncher instances.

    Example:
        def test_example(mock_launcher):
            launcher = mock_launcher(use_containers=True)
            launcher.configure(fail_spawn_ids={2})
            ...
    """

    def factory(use_containers: bool = False) -> MockLauncher:
        return MockLauncher(use_containers)

    return factory


@pytest.fixture
def mock_git_ops() -> Callable[..., MockGitOps]:
    """Factory fixture for creating MockGitOps instances.

    Example:
        def test_example(mock_git_ops):
            git = mock_git_ops()
            git.configure(has_conflicts=True, conflicting_files=["src/file.py"])
            ...
    """

    def factory(repo_path: str | Path = ".") -> MockGitOps:
        return MockGitOps(repo_path)

    return factory


@pytest.fixture
def mock_filesystem() -> Callable[..., MockFilesystem]:
    """Factory fixture for creating MockFilesystem instances.

    Example:
        def test_example(mock_filesystem):
            fs = mock_filesystem(Path("/project"))
            fs.write("config.yaml", "key: value")
            ...
    """

    def factory(base_path: Path | None = None) -> MockFilesystem:
        return MockFilesystem(base_path)

    return factory


@pytest.fixture
def mock_subprocess() -> MockSubprocess:
    """Fixture providing a MockSubprocess instance.

    Example:
        def test_example(mock_subprocess):
            mock_subprocess.register_output(["git", "status"], stdout="clean")
            result = mock_subprocess.run(["git", "status"])
            assert "clean" in result.stdout
    """
    return MockSubprocess()


# =============================================================================
# Context Managers for Temporary State
# =============================================================================


@contextlib.contextmanager
def temporary_orchestrator_state(
    feature: str = "test",
    levels: dict[int, str] | None = None,
) -> Generator[MockOrchestratorState, None, None]:
    """Context manager for temporary orchestrator state.

    Creates and yields a MockOrchestratorState that is automatically
    cleaned up when the context exits.

    Example:
        with temporary_orchestrator_state("feature", {1: "complete"}) as state:
            assert state.levels[1].status == "complete"
            # state is cleaned up after this block

    Args:
        feature: Feature name
        levels: Optional level status mapping

    Yields:
        MockOrchestratorState instance
    """
    state = MockOrchestratorState(feature=feature)

    if levels:
        for level, status in levels.items():
            state.levels[level] = MockLevelExecution(
                level=level,
                tasks=[f"TASK-{level:03d}"],
                status=status,
            )

    try:
        yield state
    finally:
        # Cleanup
        state.levels.clear()
        state.workers.clear()
        state.events.clear()


@contextlib.contextmanager
def temporary_git_state(
    branches: list[str] | None = None,
    current_branch: str = "main",
) -> Generator[MockGitOps, None, None]:
    """Context manager for temporary git state.

    Creates a MockGitOps with preconfigured branches that is
    automatically reset when the context exits.

    Example:
        branches = ["main", "zerg/test/worker-0"]
        with temporary_git_state(branches, "main") as git:
            git.checkout("zerg/test/worker-0")
            ...

    Args:
        branches: List of branch names to create
        current_branch: Branch to check out initially

    Yields:
        Configured MockGitOps instance
    """
    git = MockGitOps()

    if branches:
        for branch in branches:
            if branch != "main":
                git.add_branch(branch)

    git._current_branch = current_branch

    try:
        yield git
    finally:
        git._branches = {"main": "initial123"}
        git._current_branch = "main"


@contextlib.contextmanager
def temporary_filesystem(
    files: dict[str, str] | None = None,
    base_path: Path | None = None,
) -> Generator[MockFilesystem, None, None]:
    """Context manager for temporary filesystem state.

    Creates a MockFilesystem with preconfigured files that is
    automatically cleared when the context exits.

    Example:
        files = {"config.yaml": "key: value", "src/main.py": "print(1)"}
        with temporary_filesystem(files) as fs:
            content = fs.read("config.yaml")
            ...

    Args:
        files: Dictionary of path -> content to create
        base_path: Base path for the filesystem

    Yields:
        Configured MockFilesystem instance
    """
    fs = MockFilesystem(base_path)

    if files:
        for path, content in files.items():
            fs.write(path, content)

    try:
        yield fs
    finally:
        fs.clear()


# =============================================================================
# Helper Functions for Common Test Scenarios
# =============================================================================


def create_sample_task_graph(
    num_levels: int = 3,
    tasks_per_level: int = 2,
) -> dict[int, list[str]]:
    """Create a sample task graph for testing.

    Args:
        num_levels: Number of levels
        tasks_per_level: Tasks per level

    Returns:
        Dictionary mapping level -> task IDs
    """
    graph = {}
    task_num = 1

    for level in range(1, num_levels + 1):
        tasks = []
        for _ in range(tasks_per_level):
            tasks.append(f"TASK-{task_num:03d}")
            task_num += 1
        graph[level] = tasks

    return graph


def create_worker_states(
    count: int,
    status: WorkerStatus = WorkerStatus.RUNNING,
    feature: str = "test",
) -> dict[int, WorkerState]:
    """Create sample worker states for testing.

    Args:
        count: Number of workers
        status: Status for all workers
        feature: Feature name

    Returns:
        Dictionary of worker_id -> WorkerState
    """
    workers = {}
    for i in range(count):
        workers[i] = WorkerState(
            worker_id=i,
            status=status,
            port=49152 + i,
            branch=f"zerg/{feature}/worker-{i}",
            started_at=datetime.now(),
        )
    return workers


def create_level_statuses(
    levels: list[int],
    status: str = "pending",
) -> dict[int, LevelStatus]:
    """Create sample level statuses for testing.

    Args:
        levels: List of level numbers
        status: Status for all levels

    Returns:
        Dictionary of level -> LevelStatus
    """
    statuses = {}
    for level in levels:
        statuses[level] = LevelStatus(
            level=Level(level) if level <= 5 else Level.QUALITY,
            name=f"level-{level}",
            total_tasks=2,
            status=status,
        )
    return statuses


def assert_events_contain(
    events: list[dict[str, Any]],
    event_type: str,
    data_match: dict[str, Any] | None = None,
) -> None:
    """Assert that events contain a specific event type and data.

    Args:
        events: List of event dictionaries
        event_type: Expected event type
        data_match: Optional data fields to match

    Raises:
        AssertionError: If event not found
    """
    matching = [e for e in events if e.get("event") == event_type]

    if not matching:
        raise AssertionError(f"Event '{event_type}' not found in events: {[e.get('event') for e in events]}")

    if data_match:
        for event in matching:
            event_data = event.get("data", {})
            if all(event_data.get(k) == v for k, v in data_match.items()):
                return

        raise AssertionError(
            f"Event '{event_type}' found but data doesn't match. "
            f"Expected: {data_match}, Found: {[e.get('data') for e in matching]}"
        )


def create_mock_merge_result(
    success: bool = True,
    level: int = 1,
    commit: str = "abc123def",
    error: str | None = None,
) -> MergeFlowResult:
    """Create a mock MergeFlowResult for testing.

    Args:
        success: Whether merge succeeded
        level: Level number
        commit: Merge commit SHA
        error: Error message if failed

    Returns:
        MergeFlowResult instance
    """
    return MergeFlowResult(
        success=success,
        level=level,
        source_branches=["zerg/test/worker-0", "zerg/test/worker-1"],
        target_branch="main",
        merge_commit=commit if success else None,
        error=error,
    )


def create_mock_gate_result(
    gate_name: str = "test",
    passed: bool = True,
    command: str = "pytest",
) -> GateRunResult:
    """Create a mock GateRunResult for testing.

    Args:
        gate_name: Gate name
        passed: Whether gate passed
        command: Gate command

    Returns:
        GateRunResult instance
    """
    return GateRunResult(
        gate_name=gate_name,
        result=GateResult.PASS if passed else GateResult.FAIL,
        command=command,
        exit_code=0 if passed else 1,
        stdout="Tests passed" if passed else "Tests failed",
        stderr="" if passed else "1 test failed",
        duration_ms=1000,
    )
