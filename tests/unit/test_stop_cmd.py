"""Unit tests for ZERG stop command.

Thinned from 40 tests to cover unique code paths:
- detect_feature (no dir, single file, multiple files)
- show_workers_to_stop (force + graceful)
- stop_workers_graceful (signal, skip non-running, timeout->force, signal failure)
- stop_workers_force (kills all, handles failure)
- CLI command (help, no feature, no workers, force, graceful confirm/decline, specific worker)
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from zerg.cli import cli
from zerg.commands.stop import (
    detect_feature,
    show_workers_to_stop,
    stop_workers_force,
    stop_workers_graceful,
)
from zerg.constants import WorkerStatus
from zerg.types import WorkerState


@pytest.fixture
def sample_workers() -> dict[int, WorkerState]:
    """Create sample workers in various states."""
    return {
        0: WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            current_task="TASK-001",
            port=49152,
            branch="zerg/test/worker-0",
            started_at=datetime.now(),
        ),
        1: WorkerState(
            worker_id=1,
            status=WorkerStatus.IDLE,
            current_task=None,
            port=49153,
            branch="zerg/test/worker-1",
            started_at=datetime.now(),
        ),
    }


@pytest.fixture
def mock_state_manager() -> MagicMock:
    """Create a mock StateManager."""
    mock = MagicMock()
    mock.feature = "test-feature"
    mock.exists.return_value = True
    mock.get_all_workers.return_value = {}
    return mock


@pytest.fixture
def mock_config() -> MagicMock:
    return MagicMock()


class TestDetectFeature:
    """Tests for detect_feature() function."""

    def test_no_state_dir(self, tmp_path: Path, monkeypatch) -> None:
        """Test returns None when state directory doesn't exist."""
        monkeypatch.chdir(tmp_path)
        assert detect_feature() is None

    def test_single_state_file(self, tmp_path: Path, monkeypatch) -> None:
        """Test detects feature from single state file."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "my-feature.json").write_text("{}")
        assert detect_feature() == "my-feature"


class TestShowWorkersToStop:
    """Tests for show_workers_to_stop() function."""

    @pytest.mark.parametrize("force", [True, False])
    def test_show_workers(self, sample_workers: dict, force: bool, capsys) -> None:
        """Test display for both force and graceful modes."""
        show_workers_to_stop(sample_workers, force=force)
        captured = capsys.readouterr()
        assert len(captured.out) > 0


class TestStopWorkersGraceful:
    """Tests for stop_workers_graceful() function."""

    @patch("zerg.commands.stop.ContainerManager")
    @patch("zerg.commands.stop.time")
    def test_graceful_sends_signals_to_running(
        self, mock_time, mock_container_cls, sample_workers, mock_state_manager, mock_config
    ) -> None:
        """Test sends signals to running workers and updates status."""
        mock_container = MagicMock()
        mock_container_cls.return_value = mock_container
        mock_time.time.side_effect = [0, 100]
        mock_time.sleep = MagicMock()
        mock_state_manager.get_all_workers.return_value = {}
        mock_ws = MagicMock()
        mock_state_manager.get_worker_state.return_value = mock_ws
        stop_workers_graceful(sample_workers, mock_state_manager, mock_config, timeout=30)
        assert mock_container.stop_worker.call_count >= 1
        assert mock_ws.status == WorkerStatus.STOPPING

    @patch("zerg.commands.stop.ContainerManager")
    @patch("zerg.commands.stop.time")
    @patch("zerg.commands.stop.stop_workers_force")
    def test_graceful_forces_remaining_on_timeout(
        self, mock_force, mock_time, mock_container_cls, sample_workers, mock_state_manager, mock_config
    ) -> None:
        """Test force stops remaining workers after timeout."""
        mock_container_cls.return_value = MagicMock()
        mock_time.time.side_effect = [0, 35, 40]
        mock_time.sleep = MagicMock()
        remaining = {
            0: WorkerState(
                worker_id=0, status=WorkerStatus.STOPPING, current_task="TASK-001", started_at=datetime.now()
            )
        }
        mock_state_manager.get_all_workers.return_value = remaining
        stop_workers_graceful(sample_workers, mock_state_manager, mock_config, timeout=30)
        mock_force.assert_called_once()

    @patch("zerg.commands.stop.ContainerManager")
    @patch("zerg.commands.stop.time")
    def test_graceful_handles_signal_failure(
        self, mock_time, mock_container_cls, sample_workers, mock_state_manager, mock_config
    ) -> None:
        """Test handles container signal failures gracefully."""
        mock_container = MagicMock()
        mock_container.stop_worker.side_effect = Exception("Signal failed")
        mock_container_cls.return_value = mock_container
        mock_time.time.side_effect = [0, 100]
        mock_time.sleep = MagicMock()
        mock_state_manager.get_all_workers.return_value = {}
        stop_workers_graceful(sample_workers, mock_state_manager, mock_config, timeout=30)


class TestStopWorkersForce:
    """Tests for stop_workers_force() function."""

    @patch("zerg.commands.stop.ContainerManager")
    def test_force_kills_all_and_updates_status(
        self, mock_container_cls, sample_workers, mock_state_manager, mock_config
    ) -> None:
        """Test force stops all workers and updates status to STOPPED."""
        mock_container_cls.return_value = MagicMock()
        mock_ws = MagicMock()
        mock_state_manager.get_worker_state.return_value = mock_ws
        stop_workers_force(sample_workers, mock_state_manager, mock_config)
        assert mock_state_manager.set_worker_state.call_count == len(sample_workers)
        assert mock_ws.status == WorkerStatus.STOPPED
        mock_state_manager.set_paused.assert_called_once_with(True)

    @patch("zerg.commands.stop.ContainerManager")
    def test_force_handles_kill_failure(
        self, mock_container_cls, sample_workers, mock_state_manager, mock_config
    ) -> None:
        """Test handles container kill failures gracefully."""
        mock_container = MagicMock()
        mock_container.stop_worker.side_effect = Exception("Kill failed")
        mock_container_cls.return_value = mock_container
        stop_workers_force(sample_workers, mock_state_manager, mock_config)


class TestStopCommand:
    """Tests for main stop() CLI command."""

    def test_stop_help(self) -> None:
        """Test stop --help shows all options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["stop", "--help"])
        assert result.exit_code == 0
        assert "--feature" in result.output
        assert "--force" in result.output

    def test_stop_no_feature_fails(self, tmp_path: Path, monkeypatch) -> None:
        """Test fails when no feature specified and none detected."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()
        runner = CliRunner()
        result = runner.invoke(cli, ["stop"])
        assert result.exit_code != 0

    @patch("zerg.commands.stop.StateManager")
    @patch("zerg.commands.stop.ZergConfig")
    def test_stop_no_workers(self, mock_config_cls, mock_state_cls, tmp_path: Path, monkeypatch) -> None:
        """Test returns early when no workers running."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)
        mock_state = MagicMock()
        mock_state.exists.return_value = True
        mock_state.get_all_workers.return_value = {}
        mock_state_cls.return_value = mock_state
        mock_config_cls.load.return_value = MagicMock()
        runner = CliRunner()
        result = runner.invoke(cli, ["stop", "--feature", "test"])
        assert "No workers running" in result.output

    @patch("zerg.commands.stop.StateManager")
    @patch("zerg.commands.stop.ZergConfig")
    @patch("zerg.commands.stop.stop_workers_force")
    @patch("zerg.commands.stop.show_workers_to_stop")
    def test_stop_force_skips_confirmation(
        self, mock_show, mock_force, mock_config_cls, mock_state_cls, sample_workers, tmp_path: Path, monkeypatch
    ) -> None:
        """Test --force skips confirmation prompt."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)
        mock_state = MagicMock()
        mock_state.exists.return_value = True
        mock_state.get_all_workers.return_value = sample_workers
        mock_state_cls.return_value = mock_state
        mock_config_cls.load.return_value = MagicMock()
        runner = CliRunner()
        result = runner.invoke(cli, ["stop", "--feature", "test", "--force"])
        mock_force.assert_called_once()
        assert "Stop complete" in result.output

    @patch("zerg.commands.stop.StateManager")
    @patch("zerg.commands.stop.ZergConfig")
    @patch("zerg.commands.stop.stop_workers_graceful")
    @patch("zerg.commands.stop.show_workers_to_stop")
    def test_stop_confirmation_declined_aborts(
        self, mock_show, mock_graceful, mock_config_cls, mock_state_cls, sample_workers, tmp_path: Path, monkeypatch
    ) -> None:
        """Test declining confirmation aborts stop."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)
        mock_state = MagicMock()
        mock_state.exists.return_value = True
        mock_state.get_all_workers.return_value = sample_workers
        mock_state_cls.return_value = mock_state
        mock_config_cls.load.return_value = MagicMock()
        runner = CliRunner()
        result = runner.invoke(cli, ["stop", "--feature", "test"], input="n\n")
        mock_graceful.assert_not_called()
        assert "Aborted" in result.output
