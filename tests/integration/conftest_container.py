"""Shared fixtures for container integration tests."""

import subprocess
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def docker_available() -> bool:
    """Check if Docker is available on the system.

    Returns:
        True if Docker is available and responding, False otherwise.
    """
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


@pytest.fixture
def mock_docker_run() -> Generator[MagicMock, None, None]:
    """Fixture to mock Docker subprocess calls.

    Yields:
        MagicMock configured for successful Docker operations.
    """
    with patch("subprocess.run") as mock:
        mock.return_value = MagicMock(returncode=0, stdout="", stderr="")
        yield mock


@pytest.fixture
def multi_lang_project(tmp_path: Path) -> Path:
    """Create a multi-language project for testing.

    Creates marker files for Python and JavaScript detection.

    Args:
        tmp_path: Pytest temporary path fixture.

    Returns:
        Path to the project directory.
    """
    (tmp_path / "requirements.txt").write_text("pytest>=7.0\nclick>=8.0\n")
    (tmp_path / "package.json").write_text('{"name": "test-project", "version": "1.0.0"}')
    return tmp_path


@pytest.fixture
def go_rust_project(tmp_path: Path) -> Path:
    """Create a Go and Rust project for testing.

    Args:
        tmp_path: Pytest temporary path fixture.

    Returns:
        Path to the project directory.
    """
    (tmp_path / "go.mod").write_text("module example.com/test\n\ngo 1.22\n")
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"\nversion = "0.1.0"\n')
    return tmp_path


@pytest.fixture
def devcontainer_output_dir(tmp_path: Path) -> Path:
    """Create .devcontainer output directory.

    Args:
        tmp_path: Pytest temporary path fixture.

    Returns:
        Path to the .devcontainer directory.
    """
    devcontainer_dir = tmp_path / ".devcontainer"
    devcontainer_dir.mkdir()
    return devcontainer_dir
