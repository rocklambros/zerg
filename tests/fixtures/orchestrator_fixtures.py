"""Reusable pytest fixtures for orchestrator edge case testing.

This module provides comprehensive fixtures for testing:
- Merge timeout and retry scenarios
- Error recovery and pause/resume flows
- Worker crash and restart handling
- Container mode initialization
- Level completion edge cases
- Task failure and retry logic

Fixture Dependency Graph:
    orchestrator_with_mocks
         |
         +-- mock_orchestrator_deps (all mocked dependencies)
         |
         +-- orchestrator_factory (parameterized creation)

    merge_timeout_scenarios
         |
         +-- timeout_config, merge_timeout_result
         |
         +-- merge_retry_scenario

    error_recovery_scenarios
         |
         +-- recoverable_error_state
         |
         +-- paused_orchestrator_state

    worker_scenarios
         |
         +-- crashed_worker_scenario
         |
         +-- initialization_timeout_scenario

    container_mode_scenarios
         |
         +-- container_mode_config
         |
         +-- devcontainer_setup
"""

from __future__ import annotations

import json
from collections.abc import Callable, Generator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from zerg.config import (
    LoggingConfig,
    ProjectConfig,
    WorkersConfig,
    ZergConfig,
)
from zerg.constants import (
    LevelMergeStatus,
    TaskStatus,
    WorkerStatus,
)
from zerg.launcher_types import LauncherConfig, LauncherType, SpawnResult, WorkerHandle
from zerg.merge import MergeFlowResult
from zerg.types import WorkerState

# =============================================================================
# Mock Orchestrator Dependencies
# =============================================================================


@pytest.fixture
def mock_orchestrator_deps() -> Generator[dict[str, MagicMock], None, None]:
    """Create mocked orchestrator dependencies.

    Provides a complete set of mocked dependencies for isolated orchestrator
    testing. All dependencies return sensible defaults.

    Yields:
        Dictionary of mocked dependency objects
    """
    with (
        patch("zerg.orchestrator.StateManager") as state_mock,
        patch("zerg.orchestrator.LevelController") as levels_mock,
        patch("zerg.orchestrator.TaskParser") as parser_mock,
        patch("zerg.orchestrator.GateRunner") as gates_mock,
        patch("zerg.orchestrator.WorktreeManager") as worktree_mock,
        patch("zerg.orchestrator.ContainerManager") as container_mock,
        patch("zerg.orchestrator.PortAllocator") as ports_mock,
        patch("zerg.orchestrator.MergeCoordinator") as merge_mock,
        patch("zerg.orchestrator.SubprocessLauncher") as subprocess_launcher_mock,
        patch("zerg.orchestrator.ContainerLauncher") as container_launcher_mock,
        patch("zerg.orchestrator.TaskSyncBridge") as task_sync_mock,
        patch("zerg.orchestrator.MetricsCollector") as metrics_mock,
    ):
        # StateManager mock
        state = MagicMock()
        state.load.return_value = {}
        state.get_task_status.return_value = None
        state.get_task_retry_count.return_value = 0
        state.get_failed_tasks.return_value = []
        state._state = {"tasks": {}}
        state_mock.return_value = state

        # LevelController mock
        levels = MagicMock()
        levels.current_level = 1
        levels.is_level_complete.return_value = False
        levels.is_level_resolved.return_value = False
        levels.can_advance.return_value = False
        levels.get_pending_tasks_for_level.return_value = []
        levels.get_status.return_value = {
            "current_level": 1,
            "total_tasks": 10,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "in_progress_tasks": 0,
            "progress_percent": 0,
            "is_complete": False,
            "levels": {},
        }
        levels_mock.return_value = levels

        # TaskParser mock
        parser = MagicMock()
        parser.get_all_tasks.return_value = []
        parser.get_task.return_value = None
        parser.total_tasks = 0
        parser.levels = [1, 2]
        parser.get_tasks_for_level.return_value = []
        parser_mock.return_value = parser

        # GateRunner mock
        gates = MagicMock()
        gates.run_all_gates.return_value = (True, [])
        gates_mock.return_value = gates

        # WorktreeManager mock
        worktree = MagicMock()
        worktree_info = MagicMock()
        worktree_info.path = Path("/tmp/worktree")
        worktree_info.branch = "zerg/test/worker-0"
        worktree.create.return_value = worktree_info
        worktree.get_worktree_path.return_value = Path("/tmp/worktree")
        worktree_mock.return_value = worktree

        # ContainerManager mock
        container = MagicMock()
        container.get_status.return_value = WorkerStatus.RUNNING
        container_mock.return_value = container

        # PortAllocator mock
        ports = MagicMock()
        ports.allocate_one.return_value = 49152
        ports_mock.return_value = ports

        # MergeCoordinator mock
        merge = MagicMock()
        merge_result = MagicMock(spec=MergeFlowResult)
        merge_result.success = True
        merge_result.merge_commit = "abc123def456"
        merge_result.error = None
        merge.full_merge_flow.return_value = merge_result
        merge_mock.return_value = merge

        # SubprocessLauncher mock
        subprocess_launcher = MagicMock()
        spawn_result = MagicMock(spec=SpawnResult)
        spawn_result.success = True
        spawn_result.error = None
        spawn_result.handle = MagicMock(spec=WorkerHandle)
        spawn_result.handle.container_id = None
        subprocess_launcher.spawn.return_value = spawn_result
        subprocess_launcher.monitor.return_value = WorkerStatus.RUNNING
        subprocess_launcher.sync_state.return_value = {}
        subprocess_launcher_mock.return_value = subprocess_launcher

        # ContainerLauncher mock
        container_launcher = MagicMock()
        container_spawn = MagicMock(spec=SpawnResult)
        container_spawn.success = True
        container_spawn.error = None
        container_spawn.handle = MagicMock(spec=WorkerHandle)
        container_spawn.handle.container_id = "container-abc123"
        container_launcher.spawn.return_value = container_spawn
        container_launcher.monitor.return_value = WorkerStatus.RUNNING
        container_launcher.ensure_network.return_value = True
        container_launcher.sync_state.return_value = {}
        container_launcher_mock.return_value = container_launcher

        # TaskSyncBridge mock
        task_sync = MagicMock()
        task_sync.sync_state.return_value = None
        task_sync_mock.return_value = task_sync

        # MetricsCollector mock
        metrics = MagicMock()
        metrics_result = MagicMock()
        metrics_result.tasks_completed = 0
        metrics_result.tasks_total = 10
        metrics_result.total_duration_ms = 0
        metrics_result.to_dict.return_value = {}
        metrics.compute_feature_metrics.return_value = metrics_result
        metrics_mock.return_value = metrics

        yield {
            "state": state,
            "levels": levels,
            "parser": parser,
            "gates": gates,
            "worktree": worktree,
            "container": container,
            "ports": ports,
            "merge": merge,
            "subprocess_launcher": subprocess_launcher,
            "container_launcher": container_launcher,
            "task_sync": task_sync,
            "metrics": metrics,
            # Also expose the mock classes for patching verification
            "StateManager": state_mock,
            "LevelController": levels_mock,
            "TaskParser": parser_mock,
            "MergeCoordinator": merge_mock,
            "SubprocessLauncher": subprocess_launcher_mock,
            "ContainerLauncher": container_launcher_mock,
        }


# =============================================================================
# Merge Timeout and Retry Fixtures
# =============================================================================


@pytest.fixture
def merge_timeout_config() -> ZergConfig:
    """Create ZergConfig with short merge timeout for testing.

    Returns:
        ZergConfig with 1 second merge timeout and 2 retries
    """
    config = ZergConfig(
        project=ProjectConfig(name="timeout-test", description="Timeout testing"),
        workers=WorkersConfig(
            max_concurrent=3,
            timeout_minutes=30,
            retry_attempts=2,
        ),
    )
    # Add merge timeout attributes
    config.merge_timeout_seconds = 1  # type: ignore[attr-defined]
    config.merge_max_retries = 2  # type: ignore[attr-defined]
    return config


@pytest.fixture
def merge_timeout_result() -> MergeFlowResult:
    """Create a merge result indicating timeout.

    Returns:
        MergeFlowResult with timeout error
    """
    return MergeFlowResult(
        success=False,
        level=1,
        source_branches=["zerg/test/worker-0", "zerg/test/worker-1"],
        target_branch="main",
        error="Merge timed out",
    )


@pytest.fixture
def merge_conflict_result() -> MergeFlowResult:
    """Create a merge result indicating conflict.

    Returns:
        MergeFlowResult with conflict error
    """
    return MergeFlowResult(
        success=False,
        level=1,
        source_branches=["zerg/test/worker-0"],
        target_branch="main",
        error="CONFLICT (content): Merge conflict in src/state.py",
    )


@pytest.fixture
def merge_success_result() -> MergeFlowResult:
    """Create a successful merge result.

    Returns:
        MergeFlowResult indicating success
    """
    return MergeFlowResult(
        success=True,
        level=1,
        source_branches=["zerg/test/worker-0", "zerg/test/worker-1"],
        target_branch="main",
        merge_commit="abc123def456789",
    )


@pytest.fixture
def merge_retry_scenario(
    mock_orchestrator_deps: dict[str, MagicMock],
) -> dict[str, Any]:
    """Create a scenario where merge fails then succeeds.

    Configures mocks to simulate:
    1. First merge attempt times out
    2. Second merge attempt succeeds

    Args:
        mock_orchestrator_deps: Mocked dependencies

    Returns:
        Dictionary with scenario configuration and expected results
    """
    fail_result = MergeFlowResult(
        success=False,
        level=1,
        source_branches=["zerg/test/worker-0"],
        target_branch="main",
        error="Merge timed out",
    )

    success_result = MergeFlowResult(
        success=True,
        level=1,
        source_branches=["zerg/test/worker-0"],
        target_branch="main",
        merge_commit="retry123",
    )

    # Configure merge mock to fail first, then succeed
    mock_orchestrator_deps["merge"].full_merge_flow.side_effect = [
        fail_result,
        success_result,
    ]

    return {
        "fail_result": fail_result,
        "success_result": success_result,
        "expected_attempts": 2,
        "expected_final_success": True,
    }


# =============================================================================
# Error Recovery Fixtures
# =============================================================================


@pytest.fixture
def recoverable_error_config() -> ZergConfig:
    """Create ZergConfig for testing recoverable errors.

    Returns:
        ZergConfig with standard recovery settings
    """
    return ZergConfig(
        project=ProjectConfig(name="recovery-test", description="Recovery testing"),
        workers=WorkersConfig(
            max_concurrent=3,
            timeout_minutes=30,
            retry_attempts=3,
        ),
    )


@pytest.fixture
def paused_orchestrator_state() -> dict[str, Any]:
    """Create state representing a paused orchestrator.

    Returns:
        Dictionary simulating paused state after recoverable error
    """
    return {
        "feature": "test-feature",
        "current_level": 2,
        "paused": True,
        "error": "Level 2 merge failed after 3 attempts",
        "tasks": {
            "TASK-001": {"status": "complete"},
            "TASK-002": {"status": "complete"},
            "TASK-003": {"status": "in_progress"},
        },
        "workers": {
            "0": {"status": "idle"},
            "1": {"status": "running", "current_task": "TASK-003"},
        },
        "events": [
            {"event": "rush_started", "data": {"workers": 2}},
            {"event": "level_started", "data": {"level": 1}},
            {"event": "level_complete", "data": {"level": 1}},
            {"event": "level_started", "data": {"level": 2}},
            {"event": "recoverable_error", "data": {"error": "Merge failed"}},
        ],
    }


@pytest.fixture
def intervention_required_state() -> dict[str, Any]:
    """Create state requiring manual intervention.

    Returns:
        Dictionary simulating conflict state requiring intervention
    """
    return {
        "feature": "test-feature",
        "current_level": 1,
        "paused": True,
        "error": None,
        "level_merge_status": {
            "1": {
                "status": LevelMergeStatus.CONFLICT.value,
                "details": {
                    "error": "CONFLICT in state.py",
                    "conflicting_files": ["src/state.py"],
                },
            },
        },
        "tasks": {
            "TASK-001": {"status": "complete"},
            "TASK-002": {"status": "complete"},
        },
        "events": [
            {"event": "paused_for_intervention", "data": {"reason": "Merge conflict"}},
        ],
    }


# =============================================================================
# Worker Scenario Fixtures
# =============================================================================


@pytest.fixture
def crashed_worker_state() -> WorkerState:
    """Create a worker that has crashed.

    Returns:
        WorkerState representing a crashed worker
    """
    return WorkerState(
        worker_id=0,
        status=WorkerStatus.CRASHED,
        current_task="TASK-001",
        port=49152,
        container_id="container-crashed",
        worktree_path="/tmp/zerg-worktrees/test/worker-0",
        branch="zerg/test/worker-0",
        started_at=datetime.now() - timedelta(minutes=10),
        tasks_completed=2,
        context_usage=0.85,
    )


@pytest.fixture
def checkpointing_worker_state() -> WorkerState:
    """Create a worker that is checkpointing.

    Returns:
        WorkerState representing a checkpointing worker
    """
    return WorkerState(
        worker_id=1,
        status=WorkerStatus.CHECKPOINTING,
        current_task="TASK-002",
        port=49153,
        container_id="container-checkpoint",
        worktree_path="/tmp/zerg-worktrees/test/worker-1",
        branch="zerg/test/worker-1",
        started_at=datetime.now() - timedelta(minutes=15),
        tasks_completed=3,
        context_usage=0.78,
    )


@pytest.fixture
def blocked_worker_state() -> WorkerState:
    """Create a worker that is blocked.

    Returns:
        WorkerState representing a blocked worker
    """
    return WorkerState(
        worker_id=2,
        status=WorkerStatus.BLOCKED,
        current_task="TASK-003",
        port=49154,
        container_id="container-blocked",
        worktree_path="/tmp/zerg-worktrees/test/worker-2",
        branch="zerg/test/worker-2",
        started_at=datetime.now() - timedelta(minutes=5),
        tasks_completed=1,
        context_usage=0.45,
    )


@pytest.fixture
def initialization_timeout_scenario(
    mock_orchestrator_deps: dict[str, MagicMock],
) -> dict[str, Any]:
    """Create scenario where worker initialization times out.

    Args:
        mock_orchestrator_deps: Mocked dependencies

    Returns:
        Scenario configuration
    """
    # Configure launcher to return INITIALIZING status continuously
    mock_orchestrator_deps["subprocess_launcher"].monitor.return_value = (
        WorkerStatus.INITIALIZING
    )

    return {
        "timeout_seconds": 2,
        "check_interval": 0.5,
        "expected_timeout": True,
    }


@pytest.fixture
def worker_crash_scenario(
    mock_orchestrator_deps: dict[str, MagicMock],
) -> dict[str, Any]:
    """Create scenario where worker crashes during execution.

    Args:
        mock_orchestrator_deps: Mocked dependencies

    Returns:
        Scenario configuration with crash simulation
    """
    # Configure launcher to report crash after first check
    mock_orchestrator_deps["subprocess_launcher"].monitor.side_effect = [
        WorkerStatus.RUNNING,
        WorkerStatus.RUNNING,
        WorkerStatus.CRASHED,
    ]

    return {
        "crash_after_polls": 3,
        "current_task": "TASK-001",
        "expected_retry": True,
    }


# =============================================================================
# Container Mode Fixtures
# =============================================================================


@pytest.fixture
def container_mode_config() -> ZergConfig:
    """Create ZergConfig for container mode testing.

    Returns:
        ZergConfig configured for container launcher
    """
    return ZergConfig(
        project=ProjectConfig(name="container-test", description="Container testing"),
        workers=WorkersConfig(
            max_concurrent=5,
            timeout_minutes=60,
            launcher_type="container",
        ),
        logging=LoggingConfig(
            level="debug",
            directory="/tmp/zerg-logs",
        ),
    )


@pytest.fixture
def devcontainer_setup(tmp_path: Path) -> Path:
    """Create devcontainer configuration for container mode testing.

    Args:
        tmp_path: Pytest temporary directory

    Returns:
        Path to the repo with devcontainer setup
    """
    # Create .devcontainer directory and config
    devcontainer_dir = tmp_path / ".devcontainer"
    devcontainer_dir.mkdir(parents=True)

    devcontainer_json = {
        "name": "ZERG Worker",
        "image": "zerg-worker:latest",
        "features": {},
        "mounts": [],
        "postCreateCommand": "echo 'Container ready'",
    }

    (devcontainer_dir / "devcontainer.json").write_text(
        json.dumps(devcontainer_json, indent=2)
    )

    # Create .zerg directory
    (tmp_path / ".zerg").mkdir()
    (tmp_path / ".zerg" / "state").mkdir()

    return tmp_path


@pytest.fixture
def container_launcher_config() -> LauncherConfig:
    """Create LauncherConfig for container mode.

    Returns:
        LauncherConfig configured for containers
    """
    return LauncherConfig(
        launcher_type=LauncherType.CONTAINER,
        timeout_seconds=3600,
        log_dir=Path("/tmp/zerg-logs"),
    )


@pytest.fixture
def subprocess_launcher_config() -> LauncherConfig:
    """Create LauncherConfig for subprocess mode.

    Returns:
        LauncherConfig configured for subprocesses
    """
    return LauncherConfig(
        launcher_type=LauncherType.SUBPROCESS,
        timeout_seconds=1800,
        log_dir=Path("/tmp/zerg-logs"),
    )


# =============================================================================
# Task Retry Fixtures
# =============================================================================


@pytest.fixture
def task_at_retry_limit() -> dict[str, Any]:
    """Create state for a task at retry limit.

    Returns:
        Dictionary representing task that has exhausted retries
    """
    return {
        "task_id": "TASK-001",
        "status": TaskStatus.FAILED.value,
        "retry_count": 3,
        "max_retries": 3,
        "error": "Verification failed after 3 attempts",
        "history": [
            {"attempt": 1, "error": "Test failed"},
            {"attempt": 2, "error": "Test failed"},
            {"attempt": 3, "error": "Test failed"},
        ],
    }


@pytest.fixture
def task_for_retry() -> dict[str, Any]:
    """Create state for a task ready to retry.

    Returns:
        Dictionary representing failed task with retries remaining
    """
    return {
        "task_id": "TASK-002",
        "status": TaskStatus.FAILED.value,
        "retry_count": 1,
        "max_retries": 3,
        "error": "Verification failed on first attempt",
        "history": [
            {"attempt": 1, "error": "Test failed"},
        ],
    }


@pytest.fixture
def multiple_failed_tasks() -> list[dict[str, Any]]:
    """Create state with multiple failed tasks.

    Returns:
        List of failed task states
    """
    return [
        {
            "task_id": "TASK-001",
            "status": TaskStatus.FAILED.value,
            "retry_count": 1,
            "worker_id": 0,
        },
        {
            "task_id": "TASK-003",
            "status": TaskStatus.FAILED.value,
            "retry_count": 2,
            "worker_id": 1,
        },
        {
            "task_id": "TASK-005",
            "status": TaskStatus.FAILED.value,
            "retry_count": 0,
            "worker_id": 2,
        },
    ]


# =============================================================================
# Level Completion Edge Case Fixtures
# =============================================================================


@pytest.fixture
def level_with_no_workers() -> dict[str, Any]:
    """Create state with level complete but no active workers.

    Returns:
        State representing empty worker scenario
    """
    return {
        "level": 1,
        "tasks_complete": 3,
        "tasks_total": 3,
        "workers": {},
        "branches": [],
    }


@pytest.fixture
def level_merge_in_progress_state() -> dict[str, Any]:
    """Create state during merge process.

    Returns:
        State during active merge
    """
    return {
        "level": 1,
        "merge_status": LevelMergeStatus.MERGING.value,
        "started_at": datetime.now().isoformat(),
        "tasks": ["TASK-001", "TASK-002"],
        "worker_branches": ["zerg/test/worker-0", "zerg/test/worker-1"],
    }


@pytest.fixture
def level_rebasing_state() -> dict[str, Any]:
    """Create state during worker rebase phase.

    Returns:
        State during rebase after merge
    """
    return {
        "level": 1,
        "merge_status": LevelMergeStatus.REBASING.value,
        "merge_commit": "abc123",
        "workers_to_rebase": [0, 1, 2],
        "rebased_workers": [0],
    }


# =============================================================================
# Orchestrator Factory Fixtures
# =============================================================================


@pytest.fixture
def orchestrator_factory(
    mock_orchestrator_deps: dict[str, MagicMock],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., Any]:
    """Factory fixture for creating configured Orchestrator instances.

    Args:
        mock_orchestrator_deps: Mocked dependencies
        tmp_path: Temporary directory
        monkeypatch: Pytest monkeypatch fixture

    Returns:
        Callable that creates Orchestrator instances
    """
    from zerg.orchestrator import Orchestrator

    def _create_orchestrator(
        feature: str = "test-feature",
        launcher_mode: str | None = None,
        config: ZergConfig | None = None,
    ) -> Orchestrator:
        """Create an Orchestrator with mocked dependencies.

        Args:
            feature: Feature name
            launcher_mode: Launcher mode (subprocess, container, auto)
            config: Optional ZergConfig override

        Returns:
            Configured Orchestrator instance
        """
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir(exist_ok=True)

        return Orchestrator(
            feature=feature,
            config=config,
            repo_path=tmp_path,
            launcher_mode=launcher_mode,
        )

    return _create_orchestrator


# =============================================================================
# Verification Fixtures
# =============================================================================


@pytest.fixture
def verification_success_scenario() -> dict[str, Any]:
    """Create scenario for successful verification.

    Returns:
        Verification scenario data
    """
    return {
        "task_id": "TASK-001",
        "command": "python -c 'print(1)'",
        "timeout": 60,
        "expected_success": True,
        "expected_retries": 0,
    }


@pytest.fixture
def verification_retry_scenario() -> dict[str, Any]:
    """Create scenario for verification with retries.

    Returns:
        Verification scenario data
    """
    return {
        "task_id": "TASK-002",
        "command": "pytest test_flaky.py",
        "timeout": 120,
        "fail_count": 2,
        "max_retries": 3,
        "expected_success": True,
        "expected_retries": 2,
    }


# =============================================================================
# Exported fixtures for import verification
# =============================================================================

__all__ = [
    # Mock dependencies
    "mock_orchestrator_deps",
    # Merge scenarios
    "merge_timeout_config",
    "merge_timeout_result",
    "merge_conflict_result",
    "merge_success_result",
    "merge_retry_scenario",
    # Error recovery
    "recoverable_error_config",
    "paused_orchestrator_state",
    "intervention_required_state",
    # Worker scenarios
    "crashed_worker_state",
    "checkpointing_worker_state",
    "blocked_worker_state",
    "initialization_timeout_scenario",
    "worker_crash_scenario",
    # Container mode
    "container_mode_config",
    "devcontainer_setup",
    "container_launcher_config",
    "subprocess_launcher_config",
    # Task retry
    "task_at_retry_limit",
    "task_for_retry",
    "multiple_failed_tasks",
    # Level completion
    "level_with_no_workers",
    "level_merge_in_progress_state",
    "level_rebasing_state",
    # Factories
    "orchestrator_factory",
    # Verification
    "verification_success_scenario",
    "verification_retry_scenario",
]
