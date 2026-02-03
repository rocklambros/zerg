"""Pytest fixtures for ZERG E2E testing."""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from zerg.containers import ContainerManager

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
def sample_e2e_task_graph() -> dict:
    """Provide a sample task graph with 4 tasks across 2 levels.

    Level 1 (parallel):
        L1-001 - create src/hello.py
        L1-002 - create src/utils.py
    Level 2 (depends on L1):
        L2-001 - create tests/test_hello.py (depends on L1-001)
        L2-002 - create README.md (depends on L1-001, L1-002)

    Returns:
        Dict with 'tasks' key containing list of task dictionaries.
    """
    return {
        "tasks": [
            {
                "id": "L1-001",
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
                    "command": 'python -c "import src.hello"',
                    "timeout_seconds": 30,
                },
            },
            {
                "id": "L1-002",
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
                    "command": 'python -c "import src.utils"',
                    "timeout_seconds": 30,
                },
            },
            {
                "id": "L2-001",
                "title": "Create hello tests",
                "description": "Write tests for the hello module.",
                "phase": "testing",
                "level": 2,
                "dependencies": ["L1-001"],
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
                "id": "L2-002",
                "title": "Create README",
                "description": "Generate project README with usage instructions.",
                "phase": "documentation",
                "level": 2,
                "dependencies": ["L1-001", "L1-002"],
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
    }


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


# ---------------------------------------------------------------------------
# Docker E2E fixtures
# ---------------------------------------------------------------------------


def _docker_available() -> bool:
    """Check if Docker daemon is running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-skip @pytest.mark.docker tests when Docker is unavailable."""
    if _docker_available():
        return
    skip_docker = pytest.mark.skip(reason="Docker daemon not available")
    for item in items:
        if "docker" in item.keywords:
            item.add_marker(skip_docker)


@pytest.fixture(scope="session")
def docker_image() -> str:  # type: ignore[misc]
    """Build a minimal test image with bash and git.

    Yields the image tag. Removes the image on teardown.
    """
    tag = "zerg-test:session"
    subprocess.run(
        [
            "docker",
            "build",
            "-t",
            tag,
            "-f",
            "-",
            ".",
        ],
        input=("FROM python:3.12-alpine\nRUN apk add --no-cache bash git\n"),
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    yield tag
    subprocess.run(
        ["docker", "rmi", "-f", tag],
        capture_output=True,
        timeout=30,
    )


@pytest.fixture
def docker_container(docker_image: str) -> tuple[str, str]:  # type: ignore[misc]
    """Run a labelled container kept alive with tail -f /dev/null.

    Returns (container_id, container_name). Removes container on teardown.
    """
    name = f"zerg-test-{uuid.uuid4().hex[:8]}"
    result = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            name,
            "--label",
            "zerg-test=true",
            docker_image,
            "tail",
            "-f",
            "/dev/null",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    container_id = result.stdout.strip()
    yield container_id, name
    subprocess.run(
        ["docker", "rm", "-f", container_id],
        capture_output=True,
        timeout=30,
    )


@pytest.fixture
def container_manager_real(
    docker_container: tuple[str, str],
) -> ContainerManager:
    """Real ContainerManager with a test container injected.

    Patches _check_docker to no-op and injects the test container
    as worker_id=0 in _containers.
    """
    from zerg.containers import ContainerInfo, ContainerManager

    container_id, container_name = docker_container

    # Bypass _check_docker during __init__
    original_check = ContainerManager._check_docker
    ContainerManager._check_docker = lambda self: None  # type: ignore[assignment]
    try:
        mgr = ContainerManager()
    finally:
        ContainerManager._check_docker = original_check  # type: ignore[assignment]

    mgr._containers[0] = ContainerInfo(
        container_id=container_id,
        name=container_name,
        status="running",
        worker_id=0,
    )
    return mgr


@pytest.fixture
def tmp_worktree(tmp_path: Path) -> Path:
    """Create a temporary git repo with a stub worker_entry.sh.

    The entry script writes /tmp/.zerg-alive and execs sleep 300.
    Returns the repo path.
    """
    repo = tmp_path / "worktree"
    repo.mkdir()

    # Initialise a git repo
    git_env = os.environ.copy()
    git_env["GIT_AUTHOR_NAME"] = "ZERG Test"
    git_env["GIT_AUTHOR_EMAIL"] = "test@zerg.dev"
    git_env["GIT_COMMITTER_NAME"] = "ZERG Test"
    git_env["GIT_COMMITTER_EMAIL"] = "test@zerg.dev"

    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)

    # Create .zerg directory and worker_entry.sh
    zerg_dir = repo / ".zerg"
    zerg_dir.mkdir()
    entry = zerg_dir / "worker_entry.sh"
    entry.write_text(
        "#!/usr/bin/env bash\n"
        "touch /tmp/.zerg-alive\n"
        "# Create a script named worker_main so pgrep -f finds it\n"
        "printf '#!/bin/sh\\nsleep 300\\n' > /tmp/worker_main\n"
        "chmod +x /tmp/worker_main\n"
        "exec /tmp/worker_main\n"
    )
    entry.chmod(0o755)

    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=repo,
        capture_output=True,
        check=True,
        env=git_env,
    )

    return repo


@pytest.fixture(scope="session", autouse=True)
def docker_cleanup_safety_net() -> None:  # type: ignore[misc]
    """Safety net: remove all containers labelled zerg-test=true on teardown."""
    yield None
    result = subprocess.run(
        ["docker", "ps", "-a", "-q", "--filter", "label=zerg-test=true"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    for cid in result.stdout.strip().splitlines():
        if cid:
            subprocess.run(
                ["docker", "rm", "-f", cid],
                capture_output=True,
                timeout=15,
            )
