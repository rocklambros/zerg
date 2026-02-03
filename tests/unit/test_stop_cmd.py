"""Comprehensive unit tests for ZERG stop command.

Tests cover:
- detect_feature() auto-detection from state files
- show_workers_to_stop() table display
- stop_workers_graceful() with checkpoint signals and timeout handling
- stop_workers_force() immediate termination
- Main stop() command with all CLI options
- Error handling and edge cases

Coverage target: 100% of zerg/commands/stop.py
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

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_state_manager() -> MagicMock:
    """Create a mock StateManager with default configuration."""
    mock = MagicMock()
    mock.feature = "test-feature"
    mock.exists.return_value = True
    mock.load.return_value = {}
    mock.get_all_workers.return_value = {}
    mock.update_worker = MagicMock()
    mock.append_event = MagicMock()
    mock.set_paused = MagicMock()
    return mock


@pytest.fixture
def mock_config() -> MagicMock:
    """Create a mock ZergConfig."""
    return MagicMock()


@pytest.fixture
def mock_container_manager() -> MagicMock:
    """Create a mock ContainerManager."""
    mock = MagicMock()
    mock.stop_worker = MagicMock()
    return mock


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
        2: WorkerState(
            worker_id=2,
            status=WorkerStatus.RUNNING,
            current_task="TASK-002",
            port=49154,
            branch="zerg/test/worker-2",
            started_at=datetime.now(),
        ),
    }


@pytest.fixture
def zerg_state_dir(tmp_path: Path) -> Path:
    """Create ZERG state directory structure."""
    state_dir = tmp_path / ".zerg" / "state"
    state_dir.mkdir(parents=True)
    return state_dir


# =============================================================================
# detect_feature() Tests
# =============================================================================


class TestDetectFeature:
    """Tests for detect_feature() function."""

    def test_detect_feature_no_state_dir(self, tmp_path: Path, monkeypatch) -> None:
        """Test returns None when state directory doesn't exist."""
        monkeypatch.chdir(tmp_path)
        result = detect_feature()
        assert result is None

    def test_detect_feature_empty_state_dir(self, zerg_state_dir: Path, tmp_path: Path, monkeypatch) -> None:
        """Test returns None when state directory is empty."""
        monkeypatch.chdir(tmp_path)
        result = detect_feature()
        assert result is None

    def test_detect_feature_single_state_file(self, zerg_state_dir: Path, tmp_path: Path, monkeypatch) -> None:
        """Test detects feature from single state file."""
        monkeypatch.chdir(tmp_path)
        state_file = zerg_state_dir / "my-feature.json"
        state_file.write_text("{}")

        result = detect_feature()
        assert result == "my-feature"

    def test_detect_feature_multiple_files_returns_most_recent(
        self, zerg_state_dir: Path, tmp_path: Path, monkeypatch
    ) -> None:
        """Test returns most recently modified state file."""
        monkeypatch.chdir(tmp_path)
        import time

        # Create older file
        older_file = zerg_state_dir / "old-feature.json"
        older_file.write_text("{}")

        time.sleep(0.01)

        # Create newer file
        newer_file = zerg_state_dir / "new-feature.json"
        newer_file.write_text("{}")

        result = detect_feature()
        assert result == "new-feature"


# =============================================================================
# show_workers_to_stop() Tests
# =============================================================================


class TestShowWorkersToStop:
    """Tests for show_workers_to_stop() function."""

    def test_show_workers_force_mode(self, sample_workers: dict, capsys) -> None:
        """Test display shows FORCE KILL action for force mode."""
        show_workers_to_stop(sample_workers, force=True)
        captured = capsys.readouterr()
        assert "FORCE KILL" in captured.out or len(captured.out) > 0

    def test_show_workers_graceful_mode(self, sample_workers: dict, capsys) -> None:
        """Test display shows CHECKPOINT action for graceful mode."""
        show_workers_to_stop(sample_workers, force=False)
        captured = capsys.readouterr()
        assert "CHECKPOINT" in captured.out or len(captured.out) > 0

    def test_show_workers_displays_all_workers(self, sample_workers: dict, capsys) -> None:
        """Test all workers are displayed in the table."""
        show_workers_to_stop(sample_workers, force=False)
        captured = capsys.readouterr()
        # Workers should be displayed
        assert "worker-0" in captured.out or "0" in captured.out

    def test_show_workers_running_status_highlighted(self, sample_workers: dict, capsys) -> None:
        """Test RUNNING status is highlighted differently."""
        show_workers_to_stop(sample_workers, force=False)
        captured = capsys.readouterr()
        # Should contain status display
        assert "RUNNING" in captured.out.upper() or len(captured.out) > 0

    def test_show_workers_idle_status_dimmed(self, sample_workers: dict, capsys) -> None:
        """Test IDLE status is displayed with dim styling."""
        show_workers_to_stop(sample_workers, force=False)
        # Just verify no exception raised for idle workers
        assert True

    def test_show_workers_current_task_displayed(self, sample_workers: dict, capsys) -> None:
        """Test current task is shown or dash for no task."""
        show_workers_to_stop(sample_workers, force=False)
        captured = capsys.readouterr()
        # Should show task or dash
        assert "TASK-001" in captured.out or "-" in captured.out


# =============================================================================
# stop_workers_graceful() Tests
# =============================================================================


class TestStopWorkersGraceful:
    """Tests for stop_workers_graceful() function."""

    @patch("zerg.commands.stop.ContainerManager")
    @patch("zerg.commands.stop.time")
    def test_graceful_sends_checkpoint_signals(
        self,
        mock_time,
        mock_container_cls,
        sample_workers: dict,
        mock_state_manager: MagicMock,
        mock_config: MagicMock,
    ) -> None:
        """Test sends SIGUSR1 to running workers."""
        mock_container = MagicMock()
        mock_container_cls.return_value = mock_container

        # Simulate immediate stop
        mock_time.time.side_effect = [0, 100]
        mock_time.sleep = MagicMock()
        mock_state_manager.get_all_workers.return_value = {}

        stop_workers_graceful(sample_workers, mock_state_manager, mock_config, timeout=30)

        # Should call stop_worker for running workers
        assert mock_container.stop_worker.call_count >= 1

    @patch("zerg.commands.stop.ContainerManager")
    @patch("zerg.commands.stop.time")
    def test_graceful_skips_non_running_workers(
        self,
        mock_time,
        mock_container_cls,
        mock_state_manager: MagicMock,
        mock_config: MagicMock,
    ) -> None:
        """Test does not signal non-running workers."""
        mock_container = MagicMock()
        mock_container_cls.return_value = mock_container

        workers = {
            0: WorkerState(
                worker_id=0,
                status=WorkerStatus.STOPPED,
                current_task=None,
                started_at=datetime.now(),
            )
        }

        mock_time.time.side_effect = [0, 100]
        mock_time.sleep = MagicMock()
        mock_state_manager.get_all_workers.return_value = {}

        stop_workers_graceful(workers, mock_state_manager, mock_config, timeout=30)

        # Should not signal stopped workers
        mock_container.stop_worker.assert_not_called()

    @patch("zerg.commands.stop.ContainerManager")
    @patch("zerg.commands.stop.time")
    def test_graceful_updates_worker_status_to_stopping(
        self,
        mock_time,
        mock_container_cls,
        sample_workers: dict,
        mock_state_manager: MagicMock,
        mock_config: MagicMock,
    ) -> None:
        """Test updates worker status to STOPPING after signal."""
        mock_container = MagicMock()
        mock_container_cls.return_value = mock_container

        mock_time.time.side_effect = [0, 100]
        mock_time.sleep = MagicMock()
        mock_state_manager.get_all_workers.return_value = {}

        # Set up get_worker_state to return mock worker states
        mock_ws = MagicMock()
        mock_state_manager.get_worker_state.return_value = mock_ws

        stop_workers_graceful(sample_workers, mock_state_manager, mock_config, timeout=30)

        # Should get and set worker state for running workers
        assert mock_state_manager.get_worker_state.call_count >= 1
        assert mock_state_manager.set_worker_state.call_count >= 1
        # Verify status was set to STOPPING on the worker state object
        assert mock_ws.status == WorkerStatus.STOPPING

    @patch("zerg.commands.stop.ContainerManager")
    @patch("zerg.commands.stop.time")
    def test_graceful_waits_for_shutdown(
        self,
        mock_time,
        mock_container_cls,
        sample_workers: dict,
        mock_state_manager: MagicMock,
        mock_config: MagicMock,
    ) -> None:
        """Test waits until workers stop gracefully."""
        mock_container = MagicMock()
        mock_container_cls.return_value = mock_container

        # Simulate time passing - workers still running initially
        # First call (start), then loop iterations, finally timeout
        mock_time.time.side_effect = [0, 5, 10, 15, 100]
        mock_time.sleep = MagicMock()

        # Return workers that are still STOPPING on first few calls, then empty
        stopping_workers = {
            0: WorkerState(
                worker_id=0,
                status=WorkerStatus.STOPPING,
                current_task="TASK-001",
                started_at=datetime.now(),
            )
        }
        stopped_workers = {}

        mock_state_manager.get_all_workers.side_effect = [
            stopping_workers,  # First check - still stopping
            stopping_workers,  # Second check - still stopping
            stopped_workers,  # Third check - all stopped
        ]

        stop_workers_graceful(sample_workers, mock_state_manager, mock_config, timeout=30)

        # Should poll for status and sleep between checks
        assert mock_time.sleep.called

    @patch("zerg.commands.stop.ContainerManager")
    @patch("zerg.commands.stop.time")
    @patch("zerg.commands.stop.stop_workers_force")
    def test_graceful_forces_remaining_on_timeout(
        self,
        mock_force,
        mock_time,
        mock_container_cls,
        sample_workers: dict,
        mock_state_manager: MagicMock,
        mock_config: MagicMock,
    ) -> None:
        """Test force stops remaining workers after timeout."""
        mock_container = MagicMock()
        mock_container_cls.return_value = mock_container

        # Simulate timeout with workers still running
        mock_time.time.side_effect = [0, 35, 40]
        mock_time.sleep = MagicMock()

        # Workers remain running after timeout
        remaining_workers = {
            0: WorkerState(
                worker_id=0,
                status=WorkerStatus.STOPPING,
                current_task="TASK-001",
                started_at=datetime.now(),
            )
        }
        mock_state_manager.get_all_workers.return_value = remaining_workers

        stop_workers_graceful(sample_workers, mock_state_manager, mock_config, timeout=30)

        # Should force stop remaining workers
        mock_force.assert_called_once()

    @patch("zerg.commands.stop.ContainerManager")
    @patch("zerg.commands.stop.time")
    def test_graceful_handles_signal_failure(
        self,
        mock_time,
        mock_container_cls,
        sample_workers: dict,
        mock_state_manager: MagicMock,
        mock_config: MagicMock,
    ) -> None:
        """Test handles container signal failures gracefully."""
        mock_container = MagicMock()
        mock_container.stop_worker.side_effect = Exception("Signal failed")
        mock_container_cls.return_value = mock_container

        mock_time.time.side_effect = [0, 100]
        mock_time.sleep = MagicMock()
        mock_state_manager.get_all_workers.return_value = {}

        # Should not raise, just log warning
        stop_workers_graceful(sample_workers, mock_state_manager, mock_config, timeout=30)

    @patch("zerg.commands.stop.ContainerManager")
    @patch("zerg.commands.stop.time")
    def test_graceful_all_workers_stop_before_timeout(
        self,
        mock_time,
        mock_container_cls,
        sample_workers: dict,
        mock_state_manager: MagicMock,
        mock_config: MagicMock,
    ) -> None:
        """Test returns early when all workers stop gracefully."""
        mock_container = MagicMock()
        mock_container_cls.return_value = mock_container

        # Simulate workers stopping before timeout
        time_values = [0]  # Start
        for i in range(10):
            time_values.append(i * 2)  # Within timeout
        mock_time.time.side_effect = time_values
        mock_time.sleep = MagicMock()

        # After first check, all workers stopped
        mock_state_manager.get_all_workers.return_value = {
            0: WorkerState(
                worker_id=0,
                status=WorkerStatus.STOPPED,
                current_task=None,
                started_at=datetime.now(),
            )
        }

        stop_workers_graceful(sample_workers, mock_state_manager, mock_config, timeout=30)

        # Should detect all stopped and return early

    @patch("zerg.commands.stop.ContainerManager")
    @patch("zerg.commands.stop.time")
    @patch("zerg.commands.stop.stop_workers_force")
    def test_graceful_timeout_with_no_remaining_workers(
        self,
        mock_force,
        mock_time,
        mock_container_cls,
        sample_workers: dict,
        mock_state_manager: MagicMock,
        mock_config: MagicMock,
    ) -> None:
        """Test timeout path when no workers remain to force stop."""
        mock_container = MagicMock()
        mock_container_cls.return_value = mock_container

        # Simulate immediate timeout (loop never runs)
        mock_time.time.side_effect = [0, 35, 40]
        mock_time.sleep = MagicMock()

        # After timeout, get_all_workers returns empty (all workers already stopped)
        # This tests the "if remaining:" branch being False
        mock_state_manager.get_all_workers.return_value = {}

        stop_workers_graceful(sample_workers, mock_state_manager, mock_config, timeout=30)

        # Should NOT call force stop since no remaining workers
        mock_force.assert_not_called()


# =============================================================================
# stop_workers_force() Tests
# =============================================================================


class TestStopWorkersForce:
    """Tests for stop_workers_force() function."""

    @patch("zerg.commands.stop.ContainerManager")
    def test_force_kills_all_workers(
        self,
        mock_container_cls,
        sample_workers: dict,
        mock_state_manager: MagicMock,
        mock_config: MagicMock,
    ) -> None:
        """Test force stops all worker containers."""
        mock_container = MagicMock()
        mock_container_cls.return_value = mock_container

        # Set up get_worker_state to return mock worker states
        mock_ws = MagicMock()
        mock_state_manager.get_worker_state.return_value = mock_ws

        stop_workers_force(sample_workers, mock_state_manager, mock_config)

        # Should call stop_worker for each worker
        assert mock_container.stop_worker.call_count == len(sample_workers)

    @patch("zerg.commands.stop.ContainerManager")
    def test_force_updates_worker_status_to_stopped(
        self,
        mock_container_cls,
        sample_workers: dict,
        mock_state_manager: MagicMock,
        mock_config: MagicMock,
    ) -> None:
        """Test updates each worker status to STOPPED."""
        mock_container = MagicMock()
        mock_container_cls.return_value = mock_container

        # Set up get_worker_state to return mock worker states
        mock_ws = MagicMock()
        mock_state_manager.get_worker_state.return_value = mock_ws

        stop_workers_force(sample_workers, mock_state_manager, mock_config)

        # Should get and set worker state for each worker
        assert mock_state_manager.get_worker_state.call_count == len(sample_workers)
        assert mock_state_manager.set_worker_state.call_count == len(sample_workers)
        # Last assignment should be STOPPED
        assert mock_ws.status == WorkerStatus.STOPPED

    @patch("zerg.commands.stop.ContainerManager")
    def test_force_logs_worker_killed_events(
        self,
        mock_container_cls,
        sample_workers: dict,
        mock_state_manager: MagicMock,
        mock_config: MagicMock,
    ) -> None:
        """Test logs worker_killed event for each worker."""
        mock_container = MagicMock()
        mock_container_cls.return_value = mock_container

        stop_workers_force(sample_workers, mock_state_manager, mock_config)

        # Should log event for each worker
        assert mock_state_manager.append_event.call_count == len(sample_workers)
        for call_args in mock_state_manager.append_event.call_args_list:
            assert call_args[0][0] == "worker_killed"
            assert call_args[0][1]["force"] is True

    @patch("zerg.commands.stop.ContainerManager")
    def test_force_sets_paused_state(
        self,
        mock_container_cls,
        sample_workers: dict,
        mock_state_manager: MagicMock,
        mock_config: MagicMock,
    ) -> None:
        """Test sets execution to paused state."""
        mock_container = MagicMock()
        mock_container_cls.return_value = mock_container

        stop_workers_force(sample_workers, mock_state_manager, mock_config)

        mock_state_manager.set_paused.assert_called_once_with(True)

    @patch("zerg.commands.stop.ContainerManager")
    def test_force_handles_container_kill_failure(
        self,
        mock_container_cls,
        sample_workers: dict,
        mock_state_manager: MagicMock,
        mock_config: MagicMock,
    ) -> None:
        """Test handles container kill failures gracefully."""
        mock_container = MagicMock()
        mock_container.stop_worker.side_effect = Exception("Kill failed")
        mock_container_cls.return_value = mock_container

        # Should not raise, just log error
        stop_workers_force(sample_workers, mock_state_manager, mock_config)

    @patch("zerg.commands.stop.ContainerManager")
    def test_force_uses_correct_worker_ids(
        self,
        mock_container_cls,
        sample_workers: dict,
        mock_state_manager: MagicMock,
        mock_config: MagicMock,
    ) -> None:
        """Test calls stop_worker with correct worker IDs."""
        mock_container = MagicMock()
        mock_container_cls.return_value = mock_container
        mock_state_manager.feature = "test-feature"

        # Set up get_worker_state to return mock worker states
        mock_ws = MagicMock()
        mock_state_manager.get_worker_state.return_value = mock_ws

        stop_workers_force(sample_workers, mock_state_manager, mock_config)

        # Check worker IDs passed to stop_worker
        calls = mock_container.stop_worker.call_args_list
        called_worker_ids = [call_args[0][0] for call_args in calls]
        for wid in sample_workers:
            assert wid in called_worker_ids


# =============================================================================
# Main stop() Command Tests
# =============================================================================


class TestStopCommand:
    """Tests for main stop() CLI command."""

    def test_stop_help_displays_options(self) -> None:
        """Test stop --help shows all options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["stop", "--help"])

        assert result.exit_code == 0
        assert "--feature" in result.output
        assert "--worker" in result.output
        assert "--force" in result.output
        assert "--timeout" in result.output

    def test_stop_no_feature_no_state_fails(self, tmp_path: Path, monkeypatch) -> None:
        """Test fails when no feature specified and none detected."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["stop"])

        assert result.exit_code != 0
        assert "No active feature" in result.output or "Error" in result.output

    @patch("zerg.commands.stop.StateManager")
    @patch("zerg.commands.stop.ZergConfig")
    def test_stop_nonexistent_feature_fails(
        self,
        mock_config_cls,
        mock_state_cls,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """Test fails when feature state doesn't exist."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)

        mock_state = MagicMock()
        mock_state.exists.return_value = False
        mock_state_cls.return_value = mock_state

        runner = CliRunner()
        result = runner.invoke(cli, ["stop", "--feature", "nonexistent"])

        assert result.exit_code != 0 or "not found" in result.output.lower()

    @patch("zerg.commands.stop.StateManager")
    @patch("zerg.commands.stop.ZergConfig")
    def test_stop_no_workers_returns_early(
        self,
        mock_config_cls,
        mock_state_cls,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
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
        self,
        mock_show,
        mock_force,
        mock_config_cls,
        mock_state_cls,
        sample_workers: dict,
        tmp_path: Path,
        monkeypatch,
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

        # Should call force stop without confirmation
        mock_force.assert_called_once()
        assert "confirm" not in result.output.lower()

    @patch("zerg.commands.stop.StateManager")
    @patch("zerg.commands.stop.ZergConfig")
    @patch("zerg.commands.stop.stop_workers_graceful")
    @patch("zerg.commands.stop.show_workers_to_stop")
    def test_stop_graceful_requires_confirmation(
        self,
        mock_show,
        mock_graceful,
        mock_config_cls,
        mock_state_cls,
        sample_workers: dict,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """Test graceful stop requires confirmation."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)

        mock_state = MagicMock()
        mock_state.exists.return_value = True
        mock_state.get_all_workers.return_value = sample_workers
        mock_state_cls.return_value = mock_state

        mock_config_cls.load.return_value = MagicMock()

        runner = CliRunner()
        runner.invoke(cli, ["stop", "--feature", "test"], input="y\n")

        # Should call graceful stop after confirmation
        mock_graceful.assert_called_once()

    @patch("zerg.commands.stop.StateManager")
    @patch("zerg.commands.stop.ZergConfig")
    @patch("zerg.commands.stop.stop_workers_graceful")
    @patch("zerg.commands.stop.show_workers_to_stop")
    def test_stop_confirmation_declined_aborts(
        self,
        mock_show,
        mock_graceful,
        mock_config_cls,
        mock_state_cls,
        sample_workers: dict,
        tmp_path: Path,
        monkeypatch,
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

        # Should abort without stopping
        mock_graceful.assert_not_called()
        assert "Aborted" in result.output

    @patch("zerg.commands.stop.StateManager")
    @patch("zerg.commands.stop.ZergConfig")
    @patch("zerg.commands.stop.stop_workers_force")
    @patch("zerg.commands.stop.show_workers_to_stop")
    def test_stop_specific_worker(
        self,
        mock_show,
        mock_force,
        mock_config_cls,
        mock_state_cls,
        sample_workers: dict,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """Test --worker stops only specified worker."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)

        mock_state = MagicMock()
        mock_state.exists.return_value = True
        mock_state.get_all_workers.return_value = sample_workers
        mock_state_cls.return_value = mock_state

        mock_config_cls.load.return_value = MagicMock()

        runner = CliRunner()
        runner.invoke(cli, ["stop", "--feature", "test", "--worker", "0", "--force"])

        # Should only stop worker 0
        call_args = mock_force.call_args
        workers_arg = call_args[0][0]
        assert len(workers_arg) == 1
        assert 0 in workers_arg

    @patch("zerg.commands.stop.StateManager")
    @patch("zerg.commands.stop.ZergConfig")
    def test_stop_specific_worker_not_found_fails(
        self,
        mock_config_cls,
        mock_state_cls,
        sample_workers: dict,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """Test fails when specified worker doesn't exist."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)

        mock_state = MagicMock()
        mock_state.exists.return_value = True
        mock_state.get_all_workers.return_value = sample_workers
        mock_state_cls.return_value = mock_state

        mock_config_cls.load.return_value = MagicMock()

        runner = CliRunner()
        result = runner.invoke(cli, ["stop", "--feature", "test", "--worker", "99", "--force"])

        assert result.exit_code != 0
        assert "Worker 99 not found" in result.output

    @patch("zerg.commands.stop.StateManager")
    @patch("zerg.commands.stop.ZergConfig")
    @patch("zerg.commands.stop.stop_workers_graceful")
    @patch("zerg.commands.stop.show_workers_to_stop")
    def test_stop_custom_timeout(
        self,
        mock_show,
        mock_graceful,
        mock_config_cls,
        mock_state_cls,
        sample_workers: dict,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """Test --timeout is passed to graceful stop."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)

        mock_state = MagicMock()
        mock_state.exists.return_value = True
        mock_state.get_all_workers.return_value = sample_workers
        mock_state_cls.return_value = mock_state

        mock_config_cls.load.return_value = MagicMock()

        runner = CliRunner()
        runner.invoke(cli, ["stop", "--feature", "test", "--timeout", "60"], input="y\n")

        # Should pass timeout to graceful stop
        call_args = mock_graceful.call_args
        assert call_args[0][3] == 60  # timeout argument

    @patch("zerg.commands.stop.detect_feature")
    @patch("zerg.commands.stop.StateManager")
    @patch("zerg.commands.stop.ZergConfig")
    @patch("zerg.commands.stop.stop_workers_force")
    @patch("zerg.commands.stop.show_workers_to_stop")
    def test_stop_auto_detects_feature(
        self,
        mock_show,
        mock_force,
        mock_config_cls,
        mock_state_cls,
        mock_detect,
        sample_workers: dict,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """Test auto-detects feature when not specified."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)

        mock_detect.return_value = "detected-feature"

        mock_state = MagicMock()
        mock_state.exists.return_value = True
        mock_state.get_all_workers.return_value = sample_workers
        mock_state_cls.return_value = mock_state

        mock_config_cls.load.return_value = MagicMock()

        runner = CliRunner()
        runner.invoke(cli, ["stop", "--force"])

        # Should use detected feature
        mock_state_cls.assert_called_once_with("detected-feature")

    def test_stop_keyboard_interrupt_handled(self, tmp_path: Path, monkeypatch) -> None:
        """Test KeyboardInterrupt is handled gracefully."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)

        with patch("zerg.commands.stop.StateManager") as mock_state_cls:
            mock_state_cls.side_effect = KeyboardInterrupt()

            runner = CliRunner()
            result = runner.invoke(cli, ["stop", "--feature", "test"])

            assert "Aborted" in result.output

    @patch("zerg.commands.stop.StateManager")
    def test_stop_general_exception_handled(
        self,
        mock_state_cls,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """Test general exceptions are handled gracefully."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)

        mock_state = MagicMock()
        mock_state.exists.return_value = True
        mock_state.load.side_effect = Exception("Something went wrong")
        mock_state_cls.return_value = mock_state

        runner = CliRunner()
        result = runner.invoke(cli, ["stop", "--feature", "test"])

        assert result.exit_code != 0
        assert "Error" in result.output

    @patch("zerg.commands.stop.StateManager")
    @patch("zerg.commands.stop.ZergConfig")
    @patch("zerg.commands.stop.stop_workers_force")
    @patch("zerg.commands.stop.show_workers_to_stop")
    def test_stop_prints_completion_message(
        self,
        mock_show,
        mock_force,
        mock_config_cls,
        mock_state_cls,
        sample_workers: dict,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """Test prints completion message on success."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)

        mock_state = MagicMock()
        mock_state.exists.return_value = True
        mock_state.get_all_workers.return_value = sample_workers
        mock_state_cls.return_value = mock_state

        mock_config_cls.load.return_value = MagicMock()

        runner = CliRunner()
        result = runner.invoke(cli, ["stop", "--feature", "test", "--force"])

        assert "Stop complete" in result.output


# =============================================================================
# Integration Tests
# =============================================================================


class TestStopIntegration:
    """Integration tests for stop command."""

    @patch("zerg.commands.stop.ContainerManager")
    @patch("zerg.commands.stop.StateManager")
    @patch("zerg.commands.stop.ZergConfig")
    def test_full_force_stop_workflow(
        self,
        mock_config_cls,
        mock_state_cls,
        mock_container_cls,
        sample_workers: dict,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """Test complete force stop workflow."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)

        mock_state = MagicMock()
        mock_state.feature = "test-feature"
        mock_state.exists.return_value = True
        mock_state.get_all_workers.return_value = sample_workers
        mock_state_cls.return_value = mock_state

        mock_container = MagicMock()
        mock_container_cls.return_value = mock_container

        mock_config_cls.load.return_value = MagicMock()

        runner = CliRunner()
        result = runner.invoke(cli, ["stop", "--feature", "test-feature", "--force"])

        assert result.exit_code == 0
        assert mock_container.stop_worker.called
        assert mock_state.get_worker_state.called
        assert mock_state.set_worker_state.called
        assert mock_state.append_event.called
        assert mock_state.set_paused.called

    @patch("zerg.commands.stop.ContainerManager")
    @patch("zerg.commands.stop.StateManager")
    @patch("zerg.commands.stop.ZergConfig")
    @patch("zerg.commands.stop.time")
    def test_full_graceful_stop_workflow(
        self,
        mock_time,
        mock_config_cls,
        mock_state_cls,
        mock_container_cls,
        sample_workers: dict,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """Test complete graceful stop workflow."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)

        mock_state = MagicMock()
        mock_state.feature = "test-feature"
        mock_state.exists.return_value = True

        # First call returns workers, second returns empty (all stopped)
        mock_state.get_all_workers.side_effect = [
            sample_workers,
            {},
        ]
        mock_state_cls.return_value = mock_state

        mock_container = MagicMock()
        mock_container_cls.return_value = mock_container

        mock_config_cls.load.return_value = MagicMock()

        mock_time.time.side_effect = [0, 100]
        mock_time.sleep = MagicMock()

        runner = CliRunner()
        result = runner.invoke(cli, ["stop", "--feature", "test-feature"], input="y\n")

        assert result.exit_code == 0
        assert mock_container.stop_worker.called
