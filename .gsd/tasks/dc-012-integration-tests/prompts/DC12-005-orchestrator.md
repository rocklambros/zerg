# DC12-005: TestOrchestratorModeSelection

Create `tests/integration/test_container_orchestrator.py` with 2 tests for orchestrator mode selection.

## Files Owned
- `tests/integration/test_container_orchestrator.py`

## Dependencies
- DC12-001 (conftest_container.py must exist)

## Tests Required

1. `test_auto_detect_without_devcontainer` - Uses SubprocessLauncher when no devcontainer exists
2. `test_container_mode_available_check` - Returns (bool, str) tuple for availability check

## Implementation

```python
"""Integration tests for Orchestrator launcher mode selection."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from zerg.orchestrator import Orchestrator
from zerg.launcher import SubprocessLauncher
from zerg.config import ZergConfig


class TestOrchestratorModeSelection:
    """Test suite for orchestrator launcher mode auto-detection."""

    @patch("zerg.orchestrator.TaskGraph")
    def test_auto_detect_without_devcontainer(
        self, mock_task_graph: MagicMock, tmp_path: Path
    ) -> None:
        """Auto-detect uses SubprocessLauncher without devcontainer.

        When no .devcontainer/devcontainer.json exists, the orchestrator
        should fall back to SubprocessLauncher for worker execution.
        """
        # Create minimal repo structure WITHOUT .devcontainer
        (tmp_path / ".git").mkdir()
        (tmp_path / ".zerg").mkdir()

        # Create minimal task graph file
        specs_dir = tmp_path / ".gsd" / "specs" / "test"
        specs_dir.mkdir(parents=True)

        # Mock TaskGraph to avoid file loading
        mock_task_graph.return_value.levels = []
        mock_task_graph.return_value.tasks = {}
        mock_task_graph.return_value.get_level_tasks.return_value = []

        config = ZergConfig(max_workers=2)
        orch = Orchestrator(
            feature="test",
            config=config,
            repo_path=tmp_path,
            launcher_mode="auto",
        )

        # Should use SubprocessLauncher when devcontainer is missing
        assert isinstance(orch.launcher, SubprocessLauncher), \
            f"Expected SubprocessLauncher, got {type(orch.launcher)}"
        assert orch.get_launcher_mode() == "subprocess"

    @patch("zerg.orchestrator.TaskGraph")
    def test_container_mode_available_check(
        self, mock_task_graph: MagicMock, tmp_path: Path
    ) -> None:
        """Container mode availability returns (bool, str) tuple.

        The container_mode_available() method should return a tuple
        with availability status and a reason string.
        """
        # Create minimal structure
        (tmp_path / ".git").mkdir()
        (tmp_path / ".zerg").mkdir()

        specs_dir = tmp_path / ".gsd" / "specs" / "test"
        specs_dir.mkdir(parents=True)

        mock_task_graph.return_value.levels = []
        mock_task_graph.return_value.tasks = {}
        mock_task_graph.return_value.get_level_tasks.return_value = []

        config = ZergConfig(max_workers=2)
        orch = Orchestrator(
            feature="test",
            config=config,
            repo_path=tmp_path,
        )

        available, reason = orch.container_mode_available()

        assert isinstance(available, bool), f"Expected bool, got {type(available)}"
        assert isinstance(reason, str), f"Expected str, got {type(reason)}"
```

## Verification Command
```bash
pytest tests/integration/test_container_orchestrator.py -v
```

## Success Criteria
- Both tests pass
- SubprocessLauncher used when no devcontainer present
- container_mode_available() returns proper tuple type
