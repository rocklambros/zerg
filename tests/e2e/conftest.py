"""Pytest fixtures for ZERG E2E testing."""

import os
import subprocess
from pathlib import Path

import pytest

from tests.e2e.harness import E2EHarness, E2EResult  # noqa: F401
from tests.e2e.mock_worker import MockWorker


@pytest.fixture
def e2e_harness(tmp_path: Path) -> E2EHarness:
    """Create an E2EHarness in mock mode with repo already initialized.

    Returns:
        E2EHarness with setup_repo() already called.
    """
    harness = E2EHarness(tmp_path, feature="test-feature", mode="mock")
    harness.setup_repo()
    return harness


@pytest.fixture
def mock_worker() -> MockWorker:
    """Create a MockWorker instance with no pre-configured failures.

    Returns:
        MockWorker that succeeds on all tasks.
    """
    return MockWorker()


@pytest.fixture
def sample_e2e_task_graph() -> list[dict]:
    """Provide a sample task graph with 4 tasks across 2 levels.

    Level 1 (parallel):
        T1.1 - create src/hello.py
        T1.2 - create src/utils.py
    Level 2 (depends on L1):
        T2.1 - create tests/test_hello.py (depends on T1.1)
        T2.2 - create README.md (depends on T1.1, T1.2)

    Returns:
        List of task dictionaries in task-graph format.
    """
    return [
        {
            "id": "T1.1",
            "title": "Create hello module",
            "description": "Create the main hello module with greeting function.",
            "phase": "implementation",
            "level": 1,
            "dependencies": [],
            "files": {
                "create": ["src/hello.py"],
                "modify": [],
                "read": [],
            },
            "verification": {
                "command": "python -c \"import src.hello\"",
                "timeout_seconds": 30,
            },
        },
        {
            "id": "T1.2",
            "title": "Create utils module",
            "description": "Create utility helpers used across the project.",
            "phase": "implementation",
            "level": 1,
            "dependencies": [],
            "files": {
                "create": ["src/utils.py"],
                "modify": [],
                "read": [],
            },
            "verification": {
                "command": "python -c \"import src.utils\"",
                "timeout_seconds": 30,
            },
        },
        {
            "id": "T2.1",
            "title": "Create hello tests",
            "description": "Write tests for the hello module.",
            "phase": "testing",
            "level": 2,
            "dependencies": ["T1.1"],
            "files": {
                "create": ["tests/test_hello.py"],
                "modify": [],
                "read": [],
            },
            "verification": {
                "command": "python -m pytest tests/test_hello.py",
                "timeout_seconds": 60,
            },
        },
        {
            "id": "T2.2",
            "title": "Create README",
            "description": "Generate project README with usage instructions.",
            "phase": "documentation",
            "level": 2,
            "dependencies": ["T1.1", "T1.2"],
            "files": {
                "create": ["README.md"],
                "modify": [],
                "read": [],
            },
            "verification": {
                "command": "test -f README.md",
                "timeout_seconds": 10,
            },
        },
    ]


@pytest.fixture
def e2e_repo(tmp_path: Path) -> Path:
    """Create a minimal git repository with ZERG directory structure.

    Initializes a git repo at tmp_path/e2e_repo with .zerg/ and .gsd/
    directories and an initial commit.

    Returns:
        Path to the initialized repository.
    """
    repo_path = tmp_path / "e2e_repo"
    repo_path.mkdir()

    (repo_path / ".zerg").mkdir()
    (repo_path / ".gsd").mkdir()

    git_env = os.environ.copy()
    git_env["GIT_AUTHOR_NAME"] = "ZERG Test"
    git_env["GIT_AUTHOR_EMAIL"] = "test@zerg.dev"
    git_env["GIT_COMMITTER_NAME"] = "ZERG Test"
    git_env["GIT_COMMITTER_EMAIL"] = "test@zerg.dev"

    subprocess.run(
        ["git", "init"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "add", "-A"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "E2E test repo"],
        cwd=repo_path,
        capture_output=True,
        check=True,
        env=git_env,
    )

    return repo_path
