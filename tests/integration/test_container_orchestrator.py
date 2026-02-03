"""Integration tests for Orchestrator launcher mode selection."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from zerg.config import ZergConfig
from zerg.launcher import SubprocessLauncher
from zerg.orchestrator import Orchestrator


class TestOrchestratorModeSelection:
    """Test suite for orchestrator launcher mode auto-detection."""

    @patch("zerg.orchestrator.TaskParser")
    @patch("zerg.orchestrator.StateManager")
    @patch("zerg.orchestrator.WorktreeManager")
    @patch("zerg.orchestrator.ContainerManager")
    @patch("zerg.orchestrator.PortAllocator")
    @patch("zerg.orchestrator.GateRunner")
    @patch("zerg.orchestrator.LevelController")
    @patch("zerg.orchestrator.MergeCoordinator")
    @patch("zerg.orchestrator.TaskSyncBridge")
    def test_auto_detect_without_devcontainer(
        self,
        mock_sync: MagicMock,
        mock_merger: MagicMock,
        mock_levels: MagicMock,
        mock_gates: MagicMock,
        mock_ports: MagicMock,
        mock_containers: MagicMock,
        mock_worktrees: MagicMock,
        mock_state: MagicMock,
        mock_parser: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Auto-detect uses SubprocessLauncher without devcontainer.

        When no .devcontainer/devcontainer.json exists, the orchestrator
        should fall back to SubprocessLauncher for worker execution.
        """
        # Create minimal repo structure WITHOUT .devcontainer
        (tmp_path / ".git").mkdir()
        (tmp_path / ".zerg").mkdir()

        config = ZergConfig()
        orch = Orchestrator(
            feature="test",
            config=config,
            repo_path=tmp_path,
            launcher_mode="auto",
        )

        # Should use SubprocessLauncher when devcontainer is missing
        assert isinstance(orch.launcher, SubprocessLauncher), f"Expected SubprocessLauncher, got {type(orch.launcher)}"

    @patch("zerg.orchestrator.TaskParser")
    @patch("zerg.orchestrator.StateManager")
    @patch("zerg.orchestrator.WorktreeManager")
    @patch("zerg.orchestrator.ContainerManager")
    @patch("zerg.orchestrator.PortAllocator")
    @patch("zerg.orchestrator.GateRunner")
    @patch("zerg.orchestrator.LevelController")
    @patch("zerg.orchestrator.MergeCoordinator")
    @patch("zerg.orchestrator.TaskSyncBridge")
    def test_subprocess_mode_explicit(
        self,
        mock_sync: MagicMock,
        mock_merger: MagicMock,
        mock_levels: MagicMock,
        mock_gates: MagicMock,
        mock_ports: MagicMock,
        mock_containers: MagicMock,
        mock_worktrees: MagicMock,
        mock_state: MagicMock,
        mock_parser: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Explicit subprocess mode uses SubprocessLauncher.

        When launcher_mode="subprocess" is specified, the orchestrator
        should use SubprocessLauncher regardless of devcontainer presence.
        """
        # Create structure with devcontainer
        (tmp_path / ".git").mkdir()
        (tmp_path / ".zerg").mkdir()
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        (devcontainer_dir / "devcontainer.json").write_text('{"name": "test"}')

        config = ZergConfig()
        orch = Orchestrator(
            feature="test",
            config=config,
            repo_path=tmp_path,
            launcher_mode="subprocess",  # Explicit subprocess mode
        )

        # Should use SubprocessLauncher when explicitly requested
        assert isinstance(orch.launcher, SubprocessLauncher), f"Expected SubprocessLauncher, got {type(orch.launcher)}"
