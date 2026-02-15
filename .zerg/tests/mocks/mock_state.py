"""Mock StateManager for testing state.py functionality.

Provides comprehensive simulation of worker state, task state, level state,
and event tracking capabilities for testing edge cases.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class MockTaskStatus(Enum):
    """Task execution status mirror for mocking."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    BLOCKED = "blocked"


class MockLevelStatus(Enum):
    """Level execution status for mocking."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class MockEvent:
    """Represents a state event for tracking."""

    event_type: str
    entity_id: str
    timestamp: datetime
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize event to dictionary."""
        return {
            "event_type": self.event_type,
            "entity_id": self.entity_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }


@dataclass
class MockWorkerState:
    """Mock worker state with configurable behavior."""

    id: str
    status: str = "idle"
    current_task: str | None = None
    tasks_completed: int = 0
    error: str | None = None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "status": self.status,
            "current_task": self.current_task,
            "tasks_completed": self.tasks_completed,
            "error": self.error,
        }


@dataclass
class MockTaskState:
    """Mock task state with configurable behavior."""

    id: str
    status: MockTaskStatus = MockTaskStatus.PENDING
    worker_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    level: int = 1

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "status": self.status.value,
            "worker_id": self.worker_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "level": self.level,
        }


@dataclass
class MockLevelState:
    """Mock level state for testing."""

    level: int
    status: MockLevelStatus = MockLevelStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    tasks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "level": self.level,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "tasks": self.tasks,
        }


class StateError(Exception):
    """Exception for state-related errors."""

    pass


class MockStateManager:
    """Mock StateManager with full state simulation capabilities.

    Supports:
    - Worker state management (get/set, invalid IDs)
    - Task state management (status transitions, missing tasks)
    - Level state management (status transitions)
    - Event tracking (filtering, history truncation)
    - Configurable error injection for edge case testing
    - Load/save simulation with optional failures
    """

    def __init__(
        self,
        feature: str = "test-feature",
        *,
        load_should_fail: bool = False,
        save_should_fail: bool = False,
        max_event_history: int = 100,
    ):
        """Initialize MockStateManager.

        Args:
            feature: Feature name for this execution
            load_should_fail: If True, load() raises StateError
            save_should_fail: If True, save() raises StateError
            max_event_history: Maximum events to keep in history
        """
        self.feature = feature
        self.started_at = datetime.now()
        self.current_level = 0

        # State storage
        self._workers: dict[str, MockWorkerState] = {}
        self._tasks: dict[str, MockTaskState] = {}
        self._levels: dict[int, MockLevelState] = {}
        self._events: list[MockEvent] = []
        self._checkpoints: list[dict] = []

        # Configurable behavior
        self._load_should_fail = load_should_fail
        self._save_should_fail = save_should_fail
        self._max_event_history = max_event_history

        # Tracking for test assertions
        self.save_called = False
        self.load_called = False
        self.save_call_count = 0
        self.load_call_count = 0

    # --- Worker State Methods ---

    def get_worker_state(self, worker_id: str) -> MockWorkerState | None:
        """Get worker state by ID.

        Args:
            worker_id: Worker identifier

        Returns:
            Worker state or None if not found
        """
        return self._workers.get(worker_id)

    def set_worker_state(
        self,
        worker_id: str,
        state: MockWorkerState | None = None,
        *,
        status: str | None = None,
        current_task: str | None = None,
        tasks_completed: int | None = None,
        error: str | None = None,
    ) -> MockWorkerState:
        """Set or update worker state.

        Args:
            worker_id: Worker identifier
            state: Complete state to set (overrides individual fields)
            status: Worker status to set
            current_task: Current task ID
            tasks_completed: Number of completed tasks
            error: Error message if any

        Returns:
            Updated worker state
        """
        if state is not None:
            self._workers[worker_id] = state
            self._record_event("worker_state_set", worker_id, {"state": state.to_dict()})
            return state

        existing = self._workers.get(worker_id)
        if existing is None:
            existing = MockWorkerState(id=worker_id)
            self._workers[worker_id] = existing

        if status is not None:
            existing.status = status
        if current_task is not None:
            existing.current_task = current_task
        if tasks_completed is not None:
            existing.tasks_completed = tasks_completed
        if error is not None:
            existing.error = error

        self._record_event("worker_state_updated", worker_id, existing.to_dict())
        return existing

    def remove_worker(self, worker_id: str) -> bool:
        """Remove worker state.

        Args:
            worker_id: Worker identifier

        Returns:
            True if worker was removed, False if not found
        """
        if worker_id in self._workers:
            del self._workers[worker_id]
            self._record_event("worker_removed", worker_id, {})
            return True
        return False

    def get_all_workers(self) -> dict[str, MockWorkerState]:
        """Get all worker states."""
        return self._workers.copy()

    def get_active_workers(self) -> list[MockWorkerState]:
        """Get workers with non-idle status."""
        return [w for w in self._workers.values() if w.status != "idle"]

    # --- Task State Methods ---

    def get_task_status(self, task_id: str) -> MockTaskStatus | None:
        """Get task status by ID.

        Args:
            task_id: Task identifier

        Returns:
            Task status or None if task not found
        """
        task = self._tasks.get(task_id)
        return task.status if task else None

    def get_task_state(self, task_id: str) -> MockTaskState | None:
        """Get complete task state by ID.

        Args:
            task_id: Task identifier

        Returns:
            Task state or None if not found
        """
        return self._tasks.get(task_id)

    def set_task_state(
        self,
        task_id: str,
        state: MockTaskState | None = None,
        *,
        status: MockTaskStatus | None = None,
        worker_id: str | None = None,
        error: str | None = None,
        level: int | None = None,
    ) -> MockTaskState:
        """Set or update task state.

        Args:
            task_id: Task identifier
            state: Complete state to set
            status: Task status to set
            worker_id: Assigned worker ID
            error: Error message if any
            level: Task level

        Returns:
            Updated task state
        """
        if state is not None:
            self._tasks[task_id] = state
            self._record_event("task_state_set", task_id, {"state": state.to_dict()})
            return state

        existing = self._tasks.get(task_id)
        if existing is None:
            existing = MockTaskState(id=task_id)
            self._tasks[task_id] = existing

        old_status = existing.status

        if status is not None:
            existing.status = status
            # Auto-set timestamps on status transitions
            if status == MockTaskStatus.RUNNING and existing.started_at is None:
                existing.started_at = datetime.now()
            elif status in (MockTaskStatus.COMPLETE, MockTaskStatus.FAILED):
                existing.completed_at = datetime.now()

        if worker_id is not None:
            existing.worker_id = worker_id
        if error is not None:
            existing.error = error
        if level is not None:
            existing.level = level

        self._record_event(
            "task_state_updated",
            task_id,
            {
                "old_status": old_status.value,
                "new_status": existing.status.value,
                **existing.to_dict(),
            },
        )
        return existing

    def transition_task_status(
        self, task_id: str, new_status: MockTaskStatus
    ) -> tuple[bool, str]:
        """Transition task status with validation.

        Args:
            task_id: Task identifier
            new_status: Target status

        Returns:
            Tuple of (success, message)
        """
        task = self._tasks.get(task_id)
        if task is None:
            return False, f"Task {task_id} not found"

        # Define valid transitions
        valid_transitions = {
            MockTaskStatus.PENDING: {MockTaskStatus.RUNNING, MockTaskStatus.BLOCKED},
            MockTaskStatus.RUNNING: {
                MockTaskStatus.COMPLETE,
                MockTaskStatus.FAILED,
                MockTaskStatus.BLOCKED,
            },
            MockTaskStatus.BLOCKED: {MockTaskStatus.PENDING, MockTaskStatus.FAILED},
            MockTaskStatus.COMPLETE: set(),  # Terminal state
            MockTaskStatus.FAILED: {MockTaskStatus.PENDING},  # Can retry
        }

        allowed = valid_transitions.get(task.status, set())
        if new_status not in allowed:
            return (
                False,
                f"Invalid transition: {task.status.value} -> {new_status.value}",
            )

        self.set_task_state(task_id, status=new_status)
        return True, f"Transitioned to {new_status.value}"

    def get_tasks_by_status(self, status: MockTaskStatus) -> list[MockTaskState]:
        """Get all tasks with given status."""
        return [t for t in self._tasks.values() if t.status == status]

    def get_tasks_by_level(self, level: int) -> list[MockTaskState]:
        """Get all tasks at given level."""
        return [t for t in self._tasks.values() if t.level == level]

    def get_all_tasks(self) -> dict[str, MockTaskState]:
        """Get all task states."""
        return self._tasks.copy()

    # --- Level State Methods ---

    def get_level_state(self, level: int) -> MockLevelState | None:
        """Get level state by number.

        Args:
            level: Level number

        Returns:
            Level state or None if not found
        """
        return self._levels.get(level)

    def set_level_state(
        self,
        level: int,
        state: MockLevelState | None = None,
        *,
        status: MockLevelStatus | None = None,
        tasks: list[str] | None = None,
    ) -> MockLevelState:
        """Set or update level state.

        Args:
            level: Level number
            state: Complete state to set
            status: Level status to set
            tasks: Task IDs in this level

        Returns:
            Updated level state
        """
        if state is not None:
            self._levels[level] = state
            self._record_event("level_state_set", str(level), {"state": state.to_dict()})
            return state

        existing = self._levels.get(level)
        if existing is None:
            existing = MockLevelState(level=level)
            self._levels[level] = existing

        old_status = existing.status

        if status is not None:
            existing.status = status
            # Auto-set timestamps on status transitions
            if status == MockLevelStatus.IN_PROGRESS and existing.started_at is None:
                existing.started_at = datetime.now()
            elif status in (MockLevelStatus.COMPLETE, MockLevelStatus.FAILED):
                existing.completed_at = datetime.now()

        if tasks is not None:
            existing.tasks = tasks

        self._record_event(
            "level_state_updated",
            str(level),
            {
                "old_status": old_status.value,
                "new_status": existing.status.value,
                **existing.to_dict(),
            },
        )
        return existing

    def transition_level_status(
        self, level: int, new_status: MockLevelStatus
    ) -> tuple[bool, str]:
        """Transition level status with validation.

        Args:
            level: Level number
            new_status: Target status

        Returns:
            Tuple of (success, message)
        """
        level_state = self._levels.get(level)
        if level_state is None:
            return False, f"Level {level} not found"

        # Define valid transitions
        valid_transitions = {
            MockLevelStatus.PENDING: {MockLevelStatus.IN_PROGRESS},
            MockLevelStatus.IN_PROGRESS: {MockLevelStatus.COMPLETE, MockLevelStatus.FAILED},
            MockLevelStatus.COMPLETE: set(),  # Terminal state
            MockLevelStatus.FAILED: {MockLevelStatus.PENDING},  # Can retry
        }

        allowed = valid_transitions.get(level_state.status, set())
        if new_status not in allowed:
            return (
                False,
                f"Invalid transition: {level_state.status.value} -> {new_status.value}",
            )

        self.set_level_state(level, status=new_status)
        return True, f"Transitioned to {new_status.value}"

    def is_level_complete(self, level: int) -> bool:
        """Check if all tasks in level are complete."""
        level_state = self._levels.get(level)
        if level_state is None:
            return False

        for task_id in level_state.tasks:
            task = self._tasks.get(task_id)
            if task is None or task.status != MockTaskStatus.COMPLETE:
                return False
        return True

    def get_current_level(self) -> int:
        """Get current execution level."""
        return self.current_level

    def advance_level(self) -> int:
        """Advance to next level.

        Returns:
            New current level
        """
        self.current_level += 1
        self._record_event(
            "level_advanced", str(self.current_level), {"new_level": self.current_level}
        )
        return self.current_level

    # --- Event Tracking Methods ---

    def _record_event(
        self, event_type: str, entity_id: str, data: dict | None = None
    ) -> MockEvent:
        """Record a state event.

        Args:
            event_type: Type of event
            entity_id: ID of affected entity
            data: Additional event data

        Returns:
            Created event
        """
        event = MockEvent(
            event_type=event_type,
            entity_id=entity_id,
            timestamp=datetime.now(),
            data=data or {},
        )
        self._events.append(event)

        # Truncate history if needed
        if len(self._events) > self._max_event_history:
            self._events = self._events[-self._max_event_history :]

        return event

    def get_events(
        self,
        *,
        event_type: str | None = None,
        entity_id: str | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[MockEvent]:
        """Get events with optional filtering.

        Args:
            event_type: Filter by event type
            entity_id: Filter by entity ID
            since: Filter events after this time
            limit: Maximum events to return

        Returns:
            List of matching events
        """
        result = self._events.copy()

        if event_type is not None:
            result = [e for e in result if e.event_type == event_type]

        if entity_id is not None:
            result = [e for e in result if e.entity_id == entity_id]

        if since is not None:
            result = [e for e in result if e.timestamp > since]

        if limit is not None:
            result = result[-limit:]

        return result

    def get_event_history(self) -> list[MockEvent]:
        """Get full event history."""
        return self._events.copy()

    def clear_events(self) -> int:
        """Clear all events.

        Returns:
            Number of events cleared
        """
        count = len(self._events)
        self._events = []
        return count

    def truncate_event_history(self, keep_last: int) -> int:
        """Truncate event history to keep only recent events.

        Args:
            keep_last: Number of events to keep

        Returns:
            Number of events removed
        """
        if keep_last >= len(self._events):
            return 0

        removed = len(self._events) - keep_last
        self._events = self._events[-keep_last:]
        return removed

    # --- Checkpoint Methods ---

    def create_checkpoint(
        self,
        task_id: str,
        worker_id: str,
        *,
        files_created: list[str] | None = None,
        files_modified: list[str] | None = None,
        current_step: int = 0,
        state_data: dict | None = None,
    ) -> dict:
        """Create a checkpoint for a task.

        Args:
            task_id: Task identifier
            worker_id: Worker identifier
            files_created: List of created files
            files_modified: List of modified files
            current_step: Current step number
            state_data: Additional state data

        Returns:
            Checkpoint dictionary
        """
        checkpoint = {
            "task_id": task_id,
            "worker_id": worker_id,
            "timestamp": datetime.now().isoformat(),
            "files_created": files_created or [],
            "files_modified": files_modified or [],
            "current_step": current_step,
            "state_data": state_data or {},
        }
        self._checkpoints.append(checkpoint)
        self._record_event("checkpoint_created", task_id, checkpoint)
        return checkpoint

    def get_checkpoints(self, task_id: str | None = None) -> list[dict]:
        """Get checkpoints, optionally filtered by task.

        Args:
            task_id: Optional task ID filter

        Returns:
            List of checkpoint dictionaries
        """
        if task_id is None:
            return self._checkpoints.copy()
        return [cp for cp in self._checkpoints if cp["task_id"] == task_id]

    # --- Persistence Methods ---

    def save(self, path: str | None = None) -> None:
        """Save state to disk (simulated).

        Args:
            path: Optional path (ignored in mock)

        Raises:
            StateError: If configured to fail
        """
        self.save_called = True
        self.save_call_count += 1

        if self._save_should_fail:
            raise StateError("Simulated save failure")

        self._record_event("state_saved", self.feature, {"path": path})

    def load(self, path: str | None = None) -> bool:
        """Load state from disk (simulated).

        Args:
            path: Optional path (ignored in mock)

        Returns:
            True if load succeeded

        Raises:
            StateError: If configured to fail
        """
        self.load_called = True
        self.load_call_count += 1

        if self._load_should_fail:
            raise StateError("Simulated load failure")

        self._record_event("state_loaded", self.feature, {"path": path})
        return True

    # --- State Export/Import ---

    def to_dict(self) -> dict:
        """Export full state to dictionary.

        Returns:
            Complete state dictionary
        """
        return {
            "feature": self.feature,
            "started_at": self.started_at.isoformat(),
            "current_level": self.current_level,
            "workers": {k: v.to_dict() for k, v in self._workers.items()},
            "tasks": {k: v.to_dict() for k, v in self._tasks.items()},
            "levels": {k: v.to_dict() for k, v in self._levels.items()},
            "events": [e.to_dict() for e in self._events],
            "checkpoints": self._checkpoints,
        }

    def reset(self) -> None:
        """Reset all state to initial values."""
        self._workers = {}
        self._tasks = {}
        self._levels = {}
        self._events = []
        self._checkpoints = []
        self.current_level = 0
        self.save_called = False
        self.load_called = False
        self.save_call_count = 0
        self.load_call_count = 0

    # --- Test Helpers ---

    def setup_workers(self, count: int, status: str = "idle") -> list[str]:
        """Helper to set up multiple workers.

        Args:
            count: Number of workers to create
            status: Initial status for all workers

        Returns:
            List of worker IDs
        """
        worker_ids = []
        for i in range(count):
            worker_id = f"worker-{i + 1}"
            self.set_worker_state(worker_id, status=status)
            worker_ids.append(worker_id)
        return worker_ids

    def setup_tasks(
        self, task_ids: list[str], level: int = 1, status: MockTaskStatus = MockTaskStatus.PENDING
    ) -> list[str]:
        """Helper to set up multiple tasks.

        Args:
            task_ids: List of task IDs to create
            level: Level for all tasks
            status: Initial status for all tasks

        Returns:
            List of task IDs
        """
        for task_id in task_ids:
            self.set_task_state(task_id, status=status, level=level)
        return task_ids

    def setup_level(self, level: int, task_ids: list[str]) -> MockLevelState:
        """Helper to set up a level with tasks.

        Args:
            level: Level number
            task_ids: Task IDs in this level

        Returns:
            Level state
        """
        # Ensure tasks exist
        self.setup_tasks(task_ids, level=level)

        # Create level
        return self.set_level_state(level, tasks=task_ids)
