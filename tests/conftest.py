"""Pytest configuration and fixtures for ZERG tests."""

import json
import os
import subprocess
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from zerg.config import QualityGate, ZergConfig
from zerg.repo_map import invalidate_cache as invalidate_repo_map_cache
from zerg.types import Task, TaskGraph


@pytest.fixture(autouse=True)
def reset_caches() -> Generator[None, None, None]:
    """Reset singleton/module-level caches between tests.

    This autouse fixture ensures that caching added in performance-core
    doesn't persist state across tests, which could cause test isolation issues.

    Caches reset:
    - ZergConfig singleton (TASK-001)
    - RepoMap TTL cache (TASK-004)
    """
    # Clear caches before test
    ZergConfig.invalidate_cache()
    invalidate_repo_map_cache()
    yield
    # Clear caches after test
    ZergConfig.invalidate_cache()
    invalidate_repo_map_cache()


def _run_git(*args: str, cwd: Path | None = None) -> None:
    """Run git command safely without shell=True."""
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        check=True,
    )


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary git repository.

    Yields:
        Path to the temporary repository
    """
    orig_dir = os.getcwd()
    os.chdir(tmp_path)

    # Use subprocess.run with argument list - no shell=True
    _run_git("init", "-q", "-b", "main", cwd=tmp_path)
    _run_git("config", "user.email", "test@test.com", cwd=tmp_path)
    _run_git("config", "user.name", "Test", cwd=tmp_path)

    # Create initial commit
    (tmp_path / "README.md").write_text("# Test Repo")
    _run_git("add", "-A", cwd=tmp_path)
    _run_git("commit", "-q", "-m", "Initial commit", cwd=tmp_path)

    yield tmp_path

    os.chdir(orig_dir)


@pytest.fixture
def sample_config() -> ZergConfig:
    """Create a sample ZERG configuration.

    Returns:
        Sample ZergConfig instance
    """
    config = ZergConfig()
    config.quality_gates = [
        QualityGate(name="lint", command="echo lint", required=True),
        QualityGate(name="test", command="echo test", required=True),
    ]
    return config


@pytest.fixture
def sample_task() -> Task:
    """Create a sample task.

    Returns:
        Sample Task TypedDict
    """
    return {
        "id": "TASK-001",
        "title": "Test Task",
        "description": "A test task for unit testing",
        "level": 1,
        "dependencies": [],
        "files": {
            "create": ["src/test.py"],
            "modify": [],
            "read": [],
        },
        "verification": {
            "command": "python -c 'print(1)'",
            "timeout_seconds": 60,
        },
        "estimate_minutes": 15,
    }


@pytest.fixture
def sample_task_graph(sample_task: Task) -> TaskGraph:
    """Create a sample task graph.

    Args:
        sample_task: Sample task fixture

    Returns:
        Sample TaskGraph TypedDict
    """
    return {
        "feature": "test-feature",
        "version": "1.0",
        "generated": "2026-01-25T10:00:00Z",
        "total_tasks": 5,
        "estimated_duration_minutes": 60,
        "max_parallelization": 3,
        "tasks": [
            sample_task,
            {
                "id": "TASK-002",
                "title": "Second Task",
                "level": 1,
                "dependencies": [],
            },
            {
                "id": "TASK-003",
                "title": "Third Task",
                "level": 2,
                "dependencies": ["TASK-001", "TASK-002"],
            },
        ],
        "levels": {
            "1": {
                "name": "foundation",
                "tasks": ["TASK-001", "TASK-002"],
                "parallel": True,
                "estimated_minutes": 30,
            },
            "2": {
                "name": "core",
                "tasks": ["TASK-003"],
                "parallel": True,
                "estimated_minutes": 30,
                "depends_on_levels": [1],
            },
        },
    }


@pytest.fixture
def task_graph_file(tmp_path: Path, sample_task_graph: TaskGraph) -> Path:
    """Create a task graph JSON file.

    Args:
        tmp_path: Temporary directory
        sample_task_graph: Sample task graph

    Returns:
        Path to the task graph file
    """
    file_path = tmp_path / "task-graph.json"
    with open(file_path, "w") as f:
        json.dump(sample_task_graph, f)
    return file_path


@pytest.fixture
def mock_container_manager() -> MagicMock:
    """Create a mock container manager.

    Returns:
        Mock ContainerManager
    """
    mock = MagicMock()
    mock.start_container.return_value = "container-123"
    mock.stop_container.return_value = True
    mock.is_running.return_value = True
    mock.get_logs.return_value = "Mock container logs"
    return mock


@pytest.fixture
def zerg_dirs(tmp_path: Path) -> Path:
    """Create ZERG directory structure.

    Args:
        tmp_path: Temporary directory

    Returns:
        Path to the temporary directory with ZERG structure
    """
    dirs = [
        ".zerg",
        ".zerg/state",
        ".zerg/logs",
        ".zerg/worktrees",
        ".gsd",
        ".gsd/specs",
        ".gsd/tasks",
    ]

    for dir_path in dirs:
        (tmp_path / dir_path).mkdir(parents=True, exist_ok=True)

    return tmp_path


@pytest.fixture
def feature_state(zerg_dirs: Path) -> Path:
    """Create a feature state file.

    Args:
        zerg_dirs: ZERG directory structure

    Returns:
        Path to the state file
    """
    state = {
        "feature": "test-feature",
        "current_level": 1,
        "paused": False,
        "error": None,
        "tasks": {
            "TASK-001": {"status": "pending"},
            "TASK-002": {"status": "pending"},
        },
        "workers": {},
        "events": [],
    }

    state_file = zerg_dirs / ".zerg/state/test-feature.json"
    with open(state_file, "w") as f:
        json.dump(state, f)

    return state_file
