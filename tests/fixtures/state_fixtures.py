"""Reusable pytest fixtures for testing state and orchestrator functionality.

This module provides comprehensive fixtures for testing:
- Task graphs with multiple levels
- ZergState objects in various configurations
- Worker states (idle, running, completed, failed)
- Level completion scenarios
- Feature configurations

Fixture Dependency Graph:
    sample_task_graph
         |
         +-- sample_task_graph_file (writes to disk)
         |
         +-- task_graph_factory (parameterized creation)

    sample_zerg_state
         |
         +-- depends on: sample_task_graph
         |
         +-- zerg_state_factory (custom creation)

    worker_state_fixtures
         |
         +-- idle_worker, running_worker, completed_worker, failed_worker
         |
         +-- worker_state_factory (parameterized creation)

    level_completion_scenarios
         |
         +-- depends on: sample_task_graph
         |
         +-- level_pending, level_in_progress, level_complete, level_failed

    feature_config_fixtures
         |
         +-- minimal_config, standard_config, production_config
         |
         +-- config_factory (parameterized creation)
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

from zerg.config import (
    LoggingConfig,
    PortsConfig,
    ProjectConfig,
    QualityGate,
    ResourcesConfig,
    SecurityConfig,
    WorkersConfig,
    ZergConfig,
)
from zerg.constants import (
    Level,
    LevelMergeStatus,
    MergeStatus,
    WorkerStatus,
)
from zerg.types import (
    GateRunResult,
    LevelSpec,
    LevelStatus,
    MergeResult,
    OrchestratorState,
    Task,
    TaskGraph,
    VerificationResult,
    WorkerAssignmentEntry,
    WorkerAssignments,
    WorkerState,
)

# =============================================================================
# Task Graph Fixtures
# =============================================================================


@pytest.fixture
def sample_task_level_1() -> list[Task]:
    """Create Level 1 (Foundation) tasks.

    Returns:
        List of foundation-level tasks with no dependencies
    """
    return [
        {
            "id": "L1-001",
            "title": "Create core module structure",
            "description": "Set up the base module with __init__.py and constants",
            "level": 1,
            "dependencies": [],
            "files": {
                "create": ["src/core/__init__.py", "src/core/constants.py"],
                "modify": [],
                "read": [],
            },
            "verification": {
                "command": "python -c 'import src.core'",
                "timeout_seconds": 30,
            },
            "estimate_minutes": 10,
            "status": "pending",
            "critical_path": True,
        },
        {
            "id": "L1-002",
            "title": "Define data models",
            "description": "Create TypedDict and dataclass definitions",
            "level": 1,
            "dependencies": [],
            "files": {
                "create": ["src/core/types.py"],
                "modify": [],
                "read": ["src/core/constants.py"],
            },
            "verification": {
                "command": "python -c 'from src.core.types import *'",
                "timeout_seconds": 30,
            },
            "estimate_minutes": 15,
            "status": "pending",
            "critical_path": True,
        },
        {
            "id": "L1-003",
            "title": "Set up configuration loader",
            "description": "YAML configuration with Pydantic validation",
            "level": 1,
            "dependencies": [],
            "files": {
                "create": ["src/core/config.py"],
                "modify": [],
                "read": [],
            },
            "verification": {
                "command": "python -c 'from src.core.config import Config'",
                "timeout_seconds": 30,
            },
            "estimate_minutes": 20,
            "status": "pending",
            "critical_path": False,
        },
    ]


@pytest.fixture
def sample_task_level_2() -> list[Task]:
    """Create Level 2 (Core) tasks.

    Returns:
        List of core-level tasks depending on Level 1
    """
    return [
        {
            "id": "L2-001",
            "title": "Implement state manager",
            "description": "File-based state persistence with locking",
            "level": 2,
            "dependencies": ["L1-001", "L1-002"],
            "files": {
                "create": ["src/core/state.py"],
                "modify": ["src/core/__init__.py"],
                "read": ["src/core/types.py"],
            },
            "verification": {
                "command": "pytest tests/unit/test_state.py -v",
                "timeout_seconds": 60,
            },
            "estimate_minutes": 25,
            "status": "pending",
            "critical_path": True,
        },
        {
            "id": "L2-002",
            "title": "Build task parser",
            "description": "Parse task-graph.json with validation",
            "level": 2,
            "dependencies": ["L1-001", "L1-002"],
            "files": {
                "create": ["src/core/parser.py"],
                "modify": ["src/core/__init__.py"],
                "read": ["src/core/types.py"],
            },
            "verification": {
                "command": "pytest tests/unit/test_parser.py -v",
                "timeout_seconds": 60,
            },
            "estimate_minutes": 20,
            "status": "pending",
            "critical_path": True,
        },
    ]


@pytest.fixture
def sample_task_level_3() -> list[Task]:
    """Create Level 3 (Integration) tasks.

    Returns:
        List of integration-level tasks depending on Level 2
    """
    return [
        {
            "id": "L3-001",
            "title": "Orchestrator core",
            "description": "Main coordination engine integrating state and parser",
            "level": 3,
            "dependencies": ["L2-001", "L2-002"],
            "files": {
                "create": ["src/core/orchestrator.py"],
                "modify": ["src/core/__init__.py"],
                "read": ["src/core/state.py", "src/core/parser.py"],
            },
            "verification": {
                "command": "pytest tests/unit/test_orchestrator.py -v",
                "timeout_seconds": 120,
            },
            "estimate_minutes": 45,
            "status": "pending",
            "critical_path": True,
        },
        {
            "id": "L3-002",
            "title": "Worker launcher",
            "description": "Subprocess and container worker spawning",
            "level": 3,
            "dependencies": ["L2-001"],
            "files": {
                "create": ["src/core/launcher.py"],
                "modify": ["src/core/__init__.py"],
                "read": ["src/core/state.py", "src/core/config.py"],
            },
            "verification": {
                "command": "pytest tests/unit/test_launcher.py -v",
                "timeout_seconds": 120,
            },
            "estimate_minutes": 35,
            "status": "pending",
            "critical_path": False,
        },
    ]


@pytest.fixture
def sample_task_graph(
    sample_task_level_1: list[Task],
    sample_task_level_2: list[Task],
    sample_task_level_3: list[Task],
) -> TaskGraph:
    """Create a complete task graph with 3 levels.

    This fixture combines tasks from all three levels into a complete
    TaskGraph structure suitable for testing orchestration workflows.

    Args:
        sample_task_level_1: Level 1 foundation tasks
        sample_task_level_2: Level 2 core tasks
        sample_task_level_3: Level 3 integration tasks

    Returns:
        Complete TaskGraph with all tasks and level specifications
    """
    all_tasks = sample_task_level_1 + sample_task_level_2 + sample_task_level_3

    return {
        "schema": "1.0",
        "feature": "test-feature",
        "version": "1.0.0",
        "generated": datetime.now().isoformat(),
        "total_tasks": len(all_tasks),
        "estimated_duration_minutes": 170,
        "max_parallelization": 3,
        "critical_path": ["L1-001", "L1-002", "L2-001", "L2-002", "L3-001"],
        "critical_path_minutes": 115,
        "tasks": all_tasks,
        "levels": {
            "1": {
                "name": "foundation",
                "tasks": ["L1-001", "L1-002", "L1-003"],
                "parallel": True,
                "estimated_minutes": 45,
                "depends_on_levels": [],
            },
            "2": {
                "name": "core",
                "tasks": ["L2-001", "L2-002"],
                "parallel": True,
                "estimated_minutes": 45,
                "depends_on_levels": [1],
            },
            "3": {
                "name": "integration",
                "tasks": ["L3-001", "L3-002"],
                "parallel": True,
                "estimated_minutes": 80,
                "depends_on_levels": [2],
            },
        },
    }


@pytest.fixture
def sample_task_graph_file(tmp_path: Path, sample_task_graph: TaskGraph) -> Path:
    """Write sample task graph to a JSON file.

    Args:
        tmp_path: Pytest temporary directory
        sample_task_graph: Task graph fixture

    Returns:
        Path to the created task-graph.json file
    """
    file_path = tmp_path / ".gsd" / "specs" / "test-feature" / "task-graph.json"
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w") as f:
        json.dump(sample_task_graph, f, indent=2)

    return file_path


@pytest.fixture
def task_graph_factory() -> Callable[..., TaskGraph]:
    """Factory fixture for creating custom task graphs.

    Returns:
        Callable that creates TaskGraph instances with custom parameters
    """

    def _create_task_graph(
        feature: str = "custom-feature",
        num_levels: int = 3,
        tasks_per_level: int = 2,
        with_critical_path: bool = True,
    ) -> TaskGraph:
        """Create a custom task graph.

        Args:
            feature: Feature name
            num_levels: Number of levels to generate
            tasks_per_level: Tasks in each level
            with_critical_path: Whether to mark critical path

        Returns:
            Generated TaskGraph
        """
        tasks: list[Task] = []
        levels: dict[str, LevelSpec] = {}
        critical_path: list[str] = []

        for level in range(1, num_levels + 1):
            level_tasks: list[str] = []
            dependencies = (
                [f"L{level - 1}-{i:03d}" for i in range(1, tasks_per_level + 1)]
                if level > 1
                else []
            )

            for task_num in range(1, tasks_per_level + 1):
                task_id = f"L{level}-{task_num:03d}"
                level_tasks.append(task_id)

                if with_critical_path and task_num == 1:
                    critical_path.append(task_id)

                tasks.append(
                    {
                        "id": task_id,
                        "title": f"Task {task_id}",
                        "description": f"Auto-generated task for level {level}",
                        "level": level,
                        "dependencies": dependencies[:1] if dependencies else [],
                        "files": {
                            "create": [f"src/level{level}/task{task_num}.py"],
                            "modify": [],
                            "read": [],
                        },
                        "verification": {
                            "command": f"python -c 'print(\"{task_id}\")'",
                            "timeout_seconds": 30,
                        },
                        "estimate_minutes": 15,
                        "status": "pending",
                        "critical_path": task_num == 1,
                    }
                )

            levels[str(level)] = {
                "name": f"level-{level}",
                "tasks": level_tasks,
                "parallel": True,
                "estimated_minutes": tasks_per_level * 15,
                "depends_on_levels": [level - 1] if level > 1 else [],
            }

        return {
            "schema": "1.0",
            "feature": feature,
            "version": "1.0.0",
            "generated": datetime.now().isoformat(),
            "total_tasks": len(tasks),
            "estimated_duration_minutes": num_levels * tasks_per_level * 15,
            "max_parallelization": tasks_per_level,
            "critical_path": critical_path,
            "critical_path_minutes": num_levels * 15,
            "tasks": tasks,
            "levels": levels,
        }

    return _create_task_graph


# =============================================================================
# ZergState / OrchestratorState Fixtures
# =============================================================================


@pytest.fixture
def sample_zerg_state(sample_task_graph: TaskGraph) -> OrchestratorState:
    """Create a pre-configured OrchestratorState.

    This state represents an orchestration that has just started,
    with workers initialized but no tasks yet in progress.

    Args:
        sample_task_graph: Task graph fixture for task initialization

    Returns:
        OrchestratorState with initial configuration
    """
    workers = {
        0: WorkerState(
            worker_id=0,
            status=WorkerStatus.READY,
            port=49152,
            worktree_path="/tmp/zerg-worktrees/test-feature/worker-0",
            branch="zerg/test-feature/worker-0",
            started_at=datetime.now(),
            tasks_completed=0,
            context_usage=0.0,
        ),
        1: WorkerState(
            worker_id=1,
            status=WorkerStatus.READY,
            port=49153,
            worktree_path="/tmp/zerg-worktrees/test-feature/worker-1",
            branch="zerg/test-feature/worker-1",
            started_at=datetime.now(),
            tasks_completed=0,
            context_usage=0.0,
        ),
        2: WorkerState(
            worker_id=2,
            status=WorkerStatus.READY,
            port=49154,
            worktree_path="/tmp/zerg-worktrees/test-feature/worker-2",
            branch="zerg/test-feature/worker-2",
            started_at=datetime.now(),
            tasks_completed=0,
            context_usage=0.0,
        ),
    }

    levels = {
        1: LevelStatus(
            level=Level.FOUNDATION,
            name="foundation",
            total_tasks=3,
            status="pending",
        ),
        2: LevelStatus(
            level=Level.CORE,
            name="core",
            total_tasks=2,
            status="pending",
        ),
        3: LevelStatus(
            level=Level.INTEGRATION,
            name="integration",
            total_tasks=2,
            status="pending",
        ),
    }

    return OrchestratorState(
        feature="test-feature",
        started_at=datetime.now(),
        current_level=1,
        workers=workers,
        levels=levels,
        execution_log=[
            {
                "timestamp": datetime.now().isoformat(),
                "event": "rush_started",
                "data": {"workers": 3, "total_tasks": 7},
            }
        ],
        paused=False,
        error=None,
    )


@pytest.fixture
def zerg_state_in_progress(sample_zerg_state: OrchestratorState) -> OrchestratorState:
    """Create an OrchestratorState with tasks in progress.

    Modifies the sample state to show Level 1 partially complete with
    some workers actively executing tasks.

    Args:
        sample_zerg_state: Base state fixture

    Returns:
        OrchestratorState with in-progress execution
    """
    state = sample_zerg_state

    # Update workers to show active work
    state.workers[0].status = WorkerStatus.RUNNING
    state.workers[0].current_task = "L1-001"
    state.workers[0].context_usage = 0.15

    state.workers[1].status = WorkerStatus.RUNNING
    state.workers[1].current_task = "L1-002"
    state.workers[1].context_usage = 0.22

    state.workers[2].status = WorkerStatus.IDLE
    state.workers[2].tasks_completed = 1

    # Update level status
    state.levels[1].status = "running"
    state.levels[1].in_progress_tasks = 2
    state.levels[1].completed_tasks = 1
    state.levels[1].started_at = datetime.now() - timedelta(minutes=5)

    # Add execution events
    state.execution_log.extend(
        [
            {
                "timestamp": (datetime.now() - timedelta(minutes=5)).isoformat(),
                "event": "level_started",
                "data": {"level": 1, "tasks": 3},
            },
            {
                "timestamp": (datetime.now() - timedelta(minutes=4)).isoformat(),
                "event": "task_started",
                "data": {"task_id": "L1-003", "worker_id": 2},
            },
            {
                "timestamp": (datetime.now() - timedelta(minutes=1)).isoformat(),
                "event": "task_complete",
                "data": {"task_id": "L1-003", "worker_id": 2},
            },
        ]
    )

    return state


@pytest.fixture
def zerg_state_level_complete(sample_zerg_state: OrchestratorState) -> OrchestratorState:
    """Create an OrchestratorState with Level 1 complete.

    Shows the state after Level 1 has finished and merged,
    ready to begin Level 2.

    Args:
        sample_zerg_state: Base state fixture

    Returns:
        OrchestratorState after Level 1 completion
    """
    state = sample_zerg_state

    # All workers idle after Level 1
    for worker in state.workers.values():
        worker.status = WorkerStatus.IDLE
        worker.current_task = None
        worker.tasks_completed = 1

    # Level 1 complete
    state.levels[1].status = "complete"
    state.levels[1].completed_tasks = 3
    state.levels[1].started_at = datetime.now() - timedelta(minutes=15)
    state.levels[1].completed_at = datetime.now()
    state.levels[1].merge_commit = "abc123def456"

    # Ready for Level 2
    state.current_level = 2
    state.levels[2].status = "pending"

    return state


@pytest.fixture
def zerg_state_factory() -> Callable[..., OrchestratorState]:
    """Factory fixture for creating custom OrchestratorState instances.

    Returns:
        Callable that creates OrchestratorState with custom configuration
    """

    def _create_state(
        feature: str = "custom-feature",
        num_workers: int = 3,
        current_level: int = 1,
        paused: bool = False,
        error: str | None = None,
        total_levels: int = 3,
    ) -> OrchestratorState:
        """Create a custom OrchestratorState.

        Args:
            feature: Feature name
            num_workers: Number of workers to create
            current_level: Current execution level
            paused: Whether execution is paused
            error: Error message if any
            total_levels: Total number of levels

        Returns:
            Custom OrchestratorState instance
        """
        workers = {}
        for i in range(num_workers):
            workers[i] = WorkerState(
                worker_id=i,
                status=WorkerStatus.READY,
                port=49152 + i,
                worktree_path=f"/tmp/zerg-worktrees/{feature}/worker-{i}",
                branch=f"zerg/{feature}/worker-{i}",
                started_at=datetime.now(),
            )

        levels = {}
        level_names = ["foundation", "core", "integration", "commands", "quality"]
        level_enums = [Level.FOUNDATION, Level.CORE, Level.INTEGRATION, Level.COMMANDS, Level.QUALITY]

        for lvl in range(1, min(total_levels + 1, 6)):
            levels[lvl] = LevelStatus(
                level=level_enums[lvl - 1],
                name=level_names[lvl - 1],
                total_tasks=2,
                status="complete" if lvl < current_level else "pending",
            )

        return OrchestratorState(
            feature=feature,
            started_at=datetime.now(),
            current_level=current_level,
            workers=workers,
            levels=levels,
            execution_log=[],
            paused=paused,
            error=error,
        )

    return _create_state


# =============================================================================
# Worker State Fixtures
# =============================================================================


@pytest.fixture
def idle_worker() -> WorkerState:
    """Create a worker in IDLE state.

    Returns:
        WorkerState that is idle and ready for task assignment
    """
    return WorkerState(
        worker_id=0,
        status=WorkerStatus.IDLE,
        current_task=None,
        port=49152,
        container_id=None,
        worktree_path="/tmp/zerg-worktrees/test/worker-0",
        branch="zerg/test/worker-0",
        health_check_at=datetime.now(),
        started_at=datetime.now() - timedelta(minutes=10),
        tasks_completed=2,
        context_usage=0.45,
    )


@pytest.fixture
def running_worker() -> WorkerState:
    """Create a worker in RUNNING state.

    Returns:
        WorkerState that is actively executing a task
    """
    return WorkerState(
        worker_id=1,
        status=WorkerStatus.RUNNING,
        current_task="L1-001",
        port=49153,
        container_id="container-abc123",
        worktree_path="/tmp/zerg-worktrees/test/worker-1",
        branch="zerg/test/worker-1",
        health_check_at=datetime.now(),
        started_at=datetime.now() - timedelta(minutes=5),
        tasks_completed=0,
        context_usage=0.25,
    )


@pytest.fixture
def completed_worker() -> WorkerState:
    """Create a worker that has completed all assigned tasks.

    Returns:
        WorkerState that finished successfully
    """
    return WorkerState(
        worker_id=2,
        status=WorkerStatus.STOPPED,
        current_task=None,
        port=49154,
        container_id=None,
        worktree_path="/tmp/zerg-worktrees/test/worker-2",
        branch="zerg/test/worker-2",
        health_check_at=datetime.now() - timedelta(minutes=2),
        started_at=datetime.now() - timedelta(minutes=30),
        tasks_completed=5,
        context_usage=0.68,
    )


@pytest.fixture
def failed_worker() -> WorkerState:
    """Create a worker in CRASHED state.

    Returns:
        WorkerState that crashed during execution
    """
    return WorkerState(
        worker_id=3,
        status=WorkerStatus.CRASHED,
        current_task="L2-001",
        port=49155,
        container_id="container-xyz789",
        worktree_path="/tmp/zerg-worktrees/test/worker-3",
        branch="zerg/test/worker-3",
        health_check_at=datetime.now() - timedelta(minutes=5),
        started_at=datetime.now() - timedelta(minutes=15),
        tasks_completed=1,
        context_usage=0.92,
    )


@pytest.fixture
def checkpointing_worker() -> WorkerState:
    """Create a worker in CHECKPOINTING state.

    Returns:
        WorkerState that is saving checkpoint due to high context
    """
    return WorkerState(
        worker_id=4,
        status=WorkerStatus.CHECKPOINTING,
        current_task="L1-002",
        port=49156,
        container_id="container-chk001",
        worktree_path="/tmp/zerg-worktrees/test/worker-4",
        branch="zerg/test/worker-4",
        health_check_at=datetime.now(),
        started_at=datetime.now() - timedelta(minutes=20),
        tasks_completed=3,
        context_usage=0.78,
    )


@pytest.fixture(
    params=[
        ("idle", WorkerStatus.IDLE),
        ("ready", WorkerStatus.READY),
        ("running", WorkerStatus.RUNNING),
        ("checkpointing", WorkerStatus.CHECKPOINTING),
        ("stopped", WorkerStatus.STOPPED),
        ("crashed", WorkerStatus.CRASHED),
        ("blocked", WorkerStatus.BLOCKED),
    ]
)
def parametrized_worker_status(request: pytest.FixtureRequest) -> tuple[str, WorkerStatus]:
    """Parametrized fixture for testing all worker statuses.

    Args:
        request: Pytest fixture request

    Returns:
        Tuple of (status_name, WorkerStatus enum)
    """
    return request.param


@pytest.fixture
def worker_state_factory() -> Callable[..., WorkerState]:
    """Factory fixture for creating custom WorkerState instances.

    Returns:
        Callable that creates WorkerState with custom configuration
    """

    def _create_worker(
        worker_id: int = 0,
        status: WorkerStatus = WorkerStatus.READY,
        current_task: str | None = None,
        port: int | None = None,
        container_id: str | None = None,
        tasks_completed: int = 0,
        context_usage: float = 0.0,
    ) -> WorkerState:
        """Create a custom WorkerState.

        Args:
            worker_id: Worker identifier
            status: Worker status
            current_task: Current task being executed
            port: Allocated port number
            container_id: Docker container ID
            tasks_completed: Number of completed tasks
            context_usage: Context window usage (0.0 to 1.0)

        Returns:
            Custom WorkerState instance
        """
        return WorkerState(
            worker_id=worker_id,
            status=status,
            current_task=current_task,
            port=port or (49152 + worker_id),
            container_id=container_id,
            worktree_path=f"/tmp/zerg-worktrees/test/worker-{worker_id}",
            branch=f"zerg/test/worker-{worker_id}",
            health_check_at=datetime.now(),
            started_at=datetime.now(),
            tasks_completed=tasks_completed,
            context_usage=context_usage,
        )

    return _create_worker


# =============================================================================
# Level Completion Scenario Fixtures
# =============================================================================


@pytest.fixture
def level_pending() -> LevelStatus:
    """Create a LevelStatus in pending state.

    Returns:
        LevelStatus that hasn't started yet
    """
    return LevelStatus(
        level=Level.FOUNDATION,
        name="foundation",
        total_tasks=3,
        completed_tasks=0,
        failed_tasks=0,
        in_progress_tasks=0,
        status="pending",
        started_at=None,
        completed_at=None,
        merge_commit=None,
    )


@pytest.fixture
def level_in_progress() -> LevelStatus:
    """Create a LevelStatus in progress.

    Returns:
        LevelStatus with tasks actively executing
    """
    return LevelStatus(
        level=Level.CORE,
        name="core",
        total_tasks=4,
        completed_tasks=1,
        failed_tasks=0,
        in_progress_tasks=2,
        status="running",
        started_at=datetime.now() - timedelta(minutes=10),
        completed_at=None,
        merge_commit=None,
    )


@pytest.fixture
def level_complete() -> LevelStatus:
    """Create a LevelStatus that completed successfully.

    Returns:
        LevelStatus with all tasks completed and merged
    """
    return LevelStatus(
        level=Level.INTEGRATION,
        name="integration",
        total_tasks=3,
        completed_tasks=3,
        failed_tasks=0,
        in_progress_tasks=0,
        status="complete",
        started_at=datetime.now() - timedelta(minutes=30),
        completed_at=datetime.now(),
        merge_commit="abc123def456789",
    )


@pytest.fixture
def level_failed() -> LevelStatus:
    """Create a LevelStatus with failed tasks.

    Returns:
        LevelStatus where some tasks failed
    """
    return LevelStatus(
        level=Level.COMMANDS,
        name="commands",
        total_tasks=5,
        completed_tasks=3,
        failed_tasks=2,
        in_progress_tasks=0,
        status="failed",
        started_at=datetime.now() - timedelta(minutes=45),
        completed_at=None,
        merge_commit=None,
    )


@pytest.fixture
def level_merge_conflict() -> tuple[LevelStatus, dict[str, Any]]:
    """Create a LevelStatus with merge conflict.

    Returns:
        Tuple of (LevelStatus, conflict_details)
    """
    level = LevelStatus(
        level=Level.CORE,
        name="core",
        total_tasks=2,
        completed_tasks=2,
        failed_tasks=0,
        in_progress_tasks=0,
        status="merge_conflict",
        started_at=datetime.now() - timedelta(minutes=20),
        completed_at=None,
        merge_commit=None,
    )

    conflict_details = {
        "merge_status": LevelMergeStatus.CONFLICT.value,
        "conflicting_files": ["src/core/state.py", "src/core/config.py"],
        "worker_branches": ["zerg/test/worker-0", "zerg/test/worker-1"],
        "error": "CONFLICT (content): Merge conflict in src/core/state.py",
    }

    return level, conflict_details


@pytest.fixture
def all_levels_complete() -> dict[int, LevelStatus]:
    """Create a complete set of finished levels.

    Returns:
        Dictionary mapping level numbers to completed LevelStatus instances
    """
    base_time = datetime.now() - timedelta(hours=2)
    levels = {
        1: LevelStatus(
            level=Level.FOUNDATION,
            name="foundation",
            total_tasks=3,
            completed_tasks=3,
            status="complete",
            started_at=base_time,
            completed_at=base_time + timedelta(minutes=20),
            merge_commit="aaa111",
        ),
        2: LevelStatus(
            level=Level.CORE,
            name="core",
            total_tasks=4,
            completed_tasks=4,
            status="complete",
            started_at=base_time + timedelta(minutes=25),
            completed_at=base_time + timedelta(minutes=55),
            merge_commit="bbb222",
        ),
        3: LevelStatus(
            level=Level.INTEGRATION,
            name="integration",
            total_tasks=3,
            completed_tasks=3,
            status="complete",
            started_at=base_time + timedelta(minutes=60),
            completed_at=base_time + timedelta(minutes=90),
            merge_commit="ccc333",
        ),
    }
    return levels


# =============================================================================
# Feature Configuration Fixtures
# =============================================================================


@pytest.fixture
def minimal_config() -> ZergConfig:
    """Create a minimal ZergConfig with defaults.

    Returns:
        ZergConfig with minimal settings
    """
    return ZergConfig(
        project=ProjectConfig(name="minimal", description="Minimal config"),
        workers=WorkersConfig(max_concurrent=2, timeout_minutes=15),
        quality_gates=[],
    )


@pytest.fixture
def standard_config() -> ZergConfig:
    """Create a standard ZergConfig for typical usage.

    Returns:
        ZergConfig with standard development settings
    """
    return ZergConfig(
        project=ProjectConfig(name="standard", description="Standard config"),
        workers=WorkersConfig(
            max_concurrent=5,
            timeout_minutes=30,
            retry_attempts=3,
            context_threshold_percent=70,
        ),
        quality_gates=[
            QualityGate(name="lint", command="ruff check .", required=True),
            QualityGate(name="typecheck", command="mypy .", required=False),
            QualityGate(name="test", command="pytest -v", required=True, timeout=600),
        ],
        mcp_servers=["filesystem", "github", "fetch"],
    )


@pytest.fixture
def production_config() -> ZergConfig:
    """Create a production-grade ZergConfig.

    Returns:
        ZergConfig with strict production settings
    """
    return ZergConfig(
        project=ProjectConfig(
            name="production",
            description="Production deployment configuration",
        ),
        workers=WorkersConfig(
            max_concurrent=10,
            timeout_minutes=60,
            retry_attempts=5,
            context_threshold_percent=65,
            launcher_type="container",
        ),
        ports=PortsConfig(
            range_start=50000,
            range_end=60000,
            ports_per_worker=20,
        ),
        quality_gates=[
            QualityGate(name="lint", command="ruff check . --strict", required=True),
            QualityGate(name="typecheck", command="mypy . --strict", required=True),
            QualityGate(name="test", command="pytest --cov=src --cov-fail-under=90", required=True, timeout=900),
            QualityGate(name="security", command="bandit -r src", required=True),
        ],
        resources=ResourcesConfig(
            cpu_cores=4,
            memory_gb=8,
            disk_gb=50,
        ),
        logging=LoggingConfig(
            level="debug",
            directory="/var/log/zerg",
            retain_days=30,
        ),
        security=SecurityConfig(
            level="strict",
            pre_commit_hooks=True,
            audit_logging=True,
            container_readonly=True,
        ),
    )


@pytest.fixture
def config_yaml_file(tmp_path: Path, standard_config: ZergConfig) -> Path:
    """Write a standard config to a YAML file.

    Args:
        tmp_path: Pytest temporary directory
        standard_config: Standard config fixture

    Returns:
        Path to the created config.yaml file
    """
    config_path = tmp_path / ".zerg" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    config_dict = standard_config.to_dict()
    with open(config_path, "w") as f:
        yaml.dump(config_dict, f, default_flow_style=False)

    return config_path


@pytest.fixture
def config_factory() -> Callable[..., ZergConfig]:
    """Factory fixture for creating custom ZergConfig instances.

    Returns:
        Callable that creates ZergConfig with custom configuration
    """

    def _create_config(
        name: str = "custom",
        max_workers: int = 5,
        timeout_minutes: int = 30,
        gates: list[tuple[str, str, bool]] | None = None,
        launcher_type: str = "subprocess",
    ) -> ZergConfig:
        """Create a custom ZergConfig.

        Args:
            name: Project name
            max_workers: Maximum concurrent workers
            timeout_minutes: Worker timeout
            gates: List of (name, command, required) tuples for quality gates
            launcher_type: Worker launcher type

        Returns:
            Custom ZergConfig instance
        """
        quality_gates = []
        if gates:
            for gate_name, command, required in gates:
                quality_gates.append(
                    QualityGate(name=gate_name, command=command, required=required)
                )

        return ZergConfig(
            project=ProjectConfig(name=name, description=f"{name} configuration"),
            workers=WorkersConfig(
                max_concurrent=max_workers,
                timeout_minutes=timeout_minutes,
                launcher_type=launcher_type,
            ),
            quality_gates=quality_gates,
        )

    return _create_config


# =============================================================================
# Additional Type Fixtures
# =============================================================================


@pytest.fixture
def sample_verification_result() -> VerificationResult:
    """Create a successful verification result.

    Returns:
        VerificationResult indicating success
    """
    return {
        "success": True,
        "exit_code": 0,
        "stdout": "All tests passed!",
        "stderr": "",
        "duration_ms": 1234,
        "timestamp": datetime.now().isoformat(),
    }


@pytest.fixture
def failed_verification_result() -> VerificationResult:
    """Create a failed verification result.

    Returns:
        VerificationResult indicating failure
    """
    return {
        "success": False,
        "exit_code": 1,
        "stdout": "",
        "stderr": "AssertionError: Expected 5, got 4",
        "duration_ms": 567,
        "timestamp": datetime.now().isoformat(),
    }


@pytest.fixture
def sample_merge_result() -> MergeResult:
    """Create a successful merge result.

    Returns:
        MergeResult indicating successful merge
    """
    return MergeResult(
        source_branch="zerg/test-feature/worker-0",
        target_branch="main",
        status=MergeStatus.MERGED,
        commit_sha="abc123def456789012345678901234567890abcd",
        conflicting_files=[],
        error_message=None,
        timestamp=datetime.now(),
    )


@pytest.fixture
def conflict_merge_result() -> MergeResult:
    """Create a merge result with conflicts.

    Returns:
        MergeResult indicating merge conflict
    """
    return MergeResult(
        source_branch="zerg/test-feature/worker-1",
        target_branch="main",
        status=MergeStatus.CONFLICT,
        commit_sha=None,
        conflicting_files=["src/core/state.py", "src/core/parser.py"],
        error_message="CONFLICT (content): Merge conflict in src/core/state.py",
        timestamp=datetime.now(),
    )


@pytest.fixture
def sample_worker_assignments() -> WorkerAssignments:
    """Create sample worker assignments.

    Returns:
        WorkerAssignments for a 3-worker, 7-task scenario
    """
    assignments = [
        WorkerAssignmentEntry(task_id="L1-001", worker_id=0, level=1, estimated_minutes=10),
        WorkerAssignmentEntry(task_id="L1-002", worker_id=1, level=1, estimated_minutes=15),
        WorkerAssignmentEntry(task_id="L1-003", worker_id=2, level=1, estimated_minutes=20),
        WorkerAssignmentEntry(task_id="L2-001", worker_id=0, level=2, estimated_minutes=25),
        WorkerAssignmentEntry(task_id="L2-002", worker_id=1, level=2, estimated_minutes=20),
        WorkerAssignmentEntry(task_id="L3-001", worker_id=0, level=3, estimated_minutes=45),
        WorkerAssignmentEntry(task_id="L3-002", worker_id=2, level=3, estimated_minutes=35),
    ]

    return WorkerAssignments(
        feature="test-feature",
        worker_count=3,
        assignments=assignments,
        generated_at=datetime.now(),
    )


@pytest.fixture
def sample_gate_run_result() -> GateRunResult:
    """Create a successful gate run result.

    Returns:
        GateRunResult for a passing quality gate
    """
    from zerg.constants import GateResult

    return GateRunResult(
        gate_name="test",
        result=GateResult.PASS,
        command="pytest -v",
        exit_code=0,
        stdout="5 passed in 2.34s",
        stderr="",
        duration_ms=2340,
        timestamp=datetime.now(),
    )


# =============================================================================
# Exported fixtures for import verification
# =============================================================================

__all__ = [
    # Task graph fixtures
    "sample_task_level_1",
    "sample_task_level_2",
    "sample_task_level_3",
    "sample_task_graph",
    "sample_task_graph_file",
    "task_graph_factory",
    # State fixtures
    "sample_zerg_state",
    "zerg_state_in_progress",
    "zerg_state_level_complete",
    "zerg_state_factory",
    # Worker fixtures
    "idle_worker",
    "running_worker",
    "completed_worker",
    "failed_worker",
    "checkpointing_worker",
    "parametrized_worker_status",
    "worker_state_factory",
    # Level fixtures
    "level_pending",
    "level_in_progress",
    "level_complete",
    "level_failed",
    "level_merge_conflict",
    "all_levels_complete",
    # Config fixtures
    "minimal_config",
    "standard_config",
    "production_config",
    "config_yaml_file",
    "config_factory",
    # Additional type fixtures
    "sample_verification_result",
    "failed_verification_result",
    "sample_merge_result",
    "conflict_merge_result",
    "sample_worker_assignments",
    "sample_gate_run_result",
]
