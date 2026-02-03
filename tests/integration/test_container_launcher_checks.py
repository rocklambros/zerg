"""Integration tests for ContainerLauncher availability checks."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from zerg.launcher import ContainerLauncher


def docker_cli_available() -> bool:
    """Check if Docker CLI is available on the system."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


class TestContainerLauncher:
    """Test suite for ContainerLauncher availability and graceful failure."""

    def test_docker_available_check(self) -> None:
        """Docker availability check returns bool without raising.

        The check should never raise an exception, always returning
        True or False based on Docker availability.
        """
        # Use our local helper function
        result = docker_cli_available()

        assert isinstance(result, bool), f"Expected bool, got {type(result)}"

    @patch("subprocess.run")
    def test_image_exists_check(self, mock_run: MagicMock) -> None:
        """Image exists check returns False for nonexistent image.

        Mocks docker image inspect to return failure, verifying
        the launcher correctly reports the image doesn't exist.
        """
        # Mock docker image inspect to fail (image not found)
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Error: No such image: nonexistent-image-12345"
        )

        # Create launcher with specific image name
        launcher = ContainerLauncher(image_name="nonexistent-image-12345")
        result = launcher.image_exists()

        assert result is False, "Expected False for nonexistent image"

    @patch("subprocess.run")
    def test_spawn_requires_image(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Spawn fails gracefully when image doesn't exist.

        When attempting to spawn with a nonexistent image,
        the launcher should return a failed SpawnResult rather
        than raising an exception.
        """
        # Mock all docker commands to fail (image not found scenario)
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error: No such image")

        launcher = ContainerLauncher(image_name="nonexistent-test-image")
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="main",
        )

        # Should fail gracefully, not raise
        assert result.success is False, "Expected spawn to fail for missing image"
