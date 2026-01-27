# DC12-004: TestContainerLauncher

Create `tests/integration/test_container_launcher_checks.py` with 3 tests for launcher availability checks.

## Files Owned
- `tests/integration/test_container_launcher_checks.py`

## Dependencies
- DC12-001 (conftest_container.py must exist)

## Tests Required

1. `test_docker_available_check` - Verify docker_available() returns bool without error
2. `test_image_exists_check` - Verify image_exists() returns False for nonexistent image
3. `test_spawn_requires_image` - Verify spawn fails gracefully when image doesn't exist

## Implementation

```python
"""Integration tests for ContainerLauncher availability checks."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.launcher import ContainerLauncher, LauncherConfig


class TestContainerLauncher:
    """Test suite for ContainerLauncher availability and graceful failure."""

    def test_docker_available_check(self) -> None:
        """Docker availability check returns bool without raising.

        The check should never raise an exception, always returning
        True or False based on Docker availability.
        """
        result = ContainerLauncher.docker_available()

        assert isinstance(result, bool), f"Expected bool, got {type(result)}"

    @patch("subprocess.run")
    def test_image_exists_check(self, mock_run: MagicMock) -> None:
        """Image exists check returns False for nonexistent image.

        Mocks docker image inspect to return failure, verifying
        the launcher correctly reports the image doesn't exist.
        """
        # Mock docker image inspect to fail (image not found)
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: No such image: nonexistent-image-12345"
        )

        launcher = ContainerLauncher()
        result = launcher.image_exists("nonexistent-image-12345")

        assert result is False, "Expected False for nonexistent image"

    @patch("subprocess.run")
    def test_spawn_requires_image(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Spawn fails gracefully when image doesn't exist.

        When attempting to spawn with a nonexistent image,
        the launcher should return a failed SpawnResult rather
        than raising an exception.
        """
        # Mock all docker commands to fail (image not found scenario)
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: No such image"
        )

        launcher = ContainerLauncher(image_name="nonexistent-test-image")
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="main",
        )

        # Should fail gracefully, not raise
        assert result.success is False, "Expected spawn to fail for missing image"
```

## Verification Command
```bash
pytest tests/integration/test_container_launcher_checks.py -v
```

## Success Criteria
- All 3 tests pass
- No exceptions raised during availability checks
- Graceful failure when image doesn't exist
