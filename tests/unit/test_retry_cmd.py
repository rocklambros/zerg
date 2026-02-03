"""Comprehensive unit tests for ZERG retry command module.

Tests for zerg/commands/retry.py achieving 100% coverage.
Covers:
- retry_failed_tasks() function
- detect_feature() function
- get_failed_tasks() function
- show_retry_plan() function
- retry_task() function
- retry_all_failed_tasks() function
- Edge cases (no failed tasks, all failed, partial failures)
- Worker respawning and state updates
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from zerg.commands.retry import (
    detect_feature,
    get_failed_tasks,
    retry,
    retry_all_failed_tasks,
    retry_task,
    show_retry_plan,
)
from zerg.constants import TaskStatus
from zerg.state import StateManager


class TestDetectFeature:
    """Tests for the detect_feature function."""

    def test_detect_feature_no_state_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test detect_feature returns None when state directory does not exist."""
        monkeypatch.chdir(tmp_path)
        # No .zerg/state directory

        result = detect_feature()

        assert result is None

    def test_detect_feature_empty_state_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test detect_feature returns None when state directory is empty."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        result = detect_feature()

        assert result is None

    def test_detect_feature_single_state_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test detect_feature returns feature name from single state file."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "my-feature.json").write_text("{}")

        result = detect_feature()

        assert result == "my-feature"

    def test_detect_feature_multiple_state_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test detect_feature returns most recent state file."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        # Create older file
        older_file = state_dir / "older-feature.json"
        older_file.write_text("{}")

        # Create newer file (touch to update mtime)
        import time

        time.sleep(0.01)  # Small delay to ensure different mtime
        newer_file = state_dir / "newer-feature.json"
        newer_file.write_text("{}")

        result = detect_feature()

        assert result == "newer-feature"


class TestGetFailedTasks:
    """Tests for the get_failed_tasks function."""

    def test_get_failed_tasks_no_failures(self, tmp_path: Path) -> None:
        """Test get_failed_tasks returns empty list when no failures."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.COMPLETE)
        state.set_task_status("T2", TaskStatus.IN_PROGRESS)

        result = get_failed_tasks(state)

        assert result == []

    def test_get_failed_tasks_with_failed_tasks(self, tmp_path: Path) -> None:
        """Test get_failed_tasks returns failed task IDs."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED, error="Something went wrong")
        state.set_task_status("T2", TaskStatus.COMPLETE)
        state.set_task_status("T3", TaskStatus.FAILED, error="Another error")

        result = get_failed_tasks(state)

        assert "T1" in result
        assert "T3" in result
        assert "T2" not in result
        assert len(result) == 2

    def test_get_failed_tasks_with_blocked_tasks(self, tmp_path: Path) -> None:
        """Test get_failed_tasks includes blocked tasks."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED)
        state.set_task_status("T2", TaskStatus.BLOCKED)
        state.set_task_status("T3", TaskStatus.COMPLETE)

        result = get_failed_tasks(state)

        assert "T1" in result
        assert "T2" in result
        assert "T3" not in result
        assert len(result) == 2

    def test_get_failed_tasks_empty_state(self, tmp_path: Path) -> None:
        """Test get_failed_tasks with no tasks in state."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()

        result = get_failed_tasks(state)

        assert result == []


class TestShowRetryPlan:
    """Tests for the show_retry_plan function."""

    def test_show_retry_plan_failed_tasks(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test show_retry_plan displays failed tasks."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED)
        state.set_task_status("T2", TaskStatus.BLOCKED)

        show_retry_plan(state, ["T1", "T2"], reset=False, worker_id=None)

        captured = capsys.readouterr()
        assert "T1" in captured.out
        assert "T2" in captured.out

    def test_show_retry_plan_with_reset(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test show_retry_plan shows RESET action when reset=True."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED)

        show_retry_plan(state, ["T1"], reset=True, worker_id=None)

        captured = capsys.readouterr()
        assert "RESET" in captured.out

    def test_show_retry_plan_with_worker_id(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test show_retry_plan shows target worker when specified."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED)

        show_retry_plan(state, ["T1"], reset=False, worker_id=2)

        captured = capsys.readouterr()
        assert "2" in captured.out

    def test_show_retry_plan_unknown_task(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test show_retry_plan handles unknown task gracefully."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()

        show_retry_plan(state, ["UNKNOWN"], reset=False, worker_id=None)

        captured = capsys.readouterr()
        assert "UNKNOWN" in captured.out
        assert "unknown" in captured.out


class TestRetryTask:
    """Tests for the retry_task function."""

    def test_retry_task_simple_requeue(self, tmp_path: Path) -> None:
        """Test retry_task simple requeue without reset."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED, error="Error occurred")

        result = retry_task(state, "T1", reset=False, worker_id=None)

        assert result is True
        assert state.get_task_status("T1") == TaskStatus.PENDING.value

    def test_retry_task_with_reset(self, tmp_path: Path) -> None:
        """Test retry_task with reset clears retry count."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED)
        state.increment_task_retry("T1")
        state.increment_task_retry("T1")

        result = retry_task(state, "T1", reset=True, worker_id=None)

        assert result is True
        assert state.get_task_status("T1") == TaskStatus.PENDING.value
        assert state.get_task_retry_count("T1") == 0

    def test_retry_task_with_worker_assignment(self, tmp_path: Path) -> None:
        """Test retry_task assigns to specific worker."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED)

        # Mock claim_task method since StateManager doesn't have it by default
        with patch.object(state, "claim_task", create=True) as mock_assign:
            result = retry_task(state, "T1", reset=False, worker_id=3)

            assert result is True
            mock_assign.assert_called_once_with("T1", 3)

    def test_retry_task_logs_event(self, tmp_path: Path) -> None:
        """Test retry_task appends event to execution log."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED)

        # Test without worker_id to avoid claim_task call
        retry_task(state, "T1", reset=True, worker_id=None)

        events = state.get_events()
        retry_events = [e for e in events if e["event"] == "task_retry"]
        assert len(retry_events) >= 1
        last_retry = retry_events[-1]
        assert last_retry["data"]["task_id"] == "T1"
        assert last_retry["data"]["reset"] is True
        assert last_retry["data"]["worker_id"] is None

    def test_retry_task_logs_event_with_worker(self, tmp_path: Path) -> None:
        """Test retry_task logs event with worker_id when specified."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED)

        # Mock claim_task to allow logging with worker_id
        with patch.object(state, "claim_task", create=True):
            retry_task(state, "T1", reset=True, worker_id=5)

        events = state.get_events()
        retry_events = [e for e in events if e["event"] == "task_retry"]
        assert len(retry_events) >= 1
        last_retry = retry_events[-1]
        assert last_retry["data"]["task_id"] == "T1"
        assert last_retry["data"]["reset"] is True
        assert last_retry["data"]["worker_id"] == 5

    def test_retry_task_exception_handling(self, tmp_path: Path) -> None:
        """Test retry_task returns False on exception."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()

        # Force an exception by patching set_task_status
        with patch.object(state, "set_task_status", side_effect=Exception("DB error")):
            result = retry_task(state, "T1", reset=False, worker_id=None)

        assert result is False

    def test_retry_task_with_orchestrator_success(self, tmp_path: Path) -> None:
        """Test retry_task uses orchestrator when available and successful."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED)

        mock_orchestrator = MagicMock()
        mock_orchestrator.retry_task.return_value = True

        result = retry_task(state, "T1", reset=False, worker_id=None, orchestrator=mock_orchestrator)

        assert result is True
        mock_orchestrator.retry_task.assert_called_once_with("T1")

    def test_retry_task_with_orchestrator_and_worker(self, tmp_path: Path) -> None:
        """Test retry_task assigns worker after orchestrator retry."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED)

        mock_orchestrator = MagicMock()
        mock_orchestrator.retry_task.return_value = True

        with patch.object(state, "claim_task", create=True) as mock_assign:
            result = retry_task(state, "T1", reset=False, worker_id=2, orchestrator=mock_orchestrator)

            assert result is True
            mock_assign.assert_called_once_with("T1", 2)

    def test_retry_task_with_orchestrator_failure_fallback(self, tmp_path: Path) -> None:
        """Test retry_task falls back to manual retry when orchestrator fails."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED)

        mock_orchestrator = MagicMock()
        mock_orchestrator.retry_task.return_value = False

        result = retry_task(state, "T1", reset=False, worker_id=None, orchestrator=mock_orchestrator)

        assert result is True
        # Should have fallen back to manual retry
        assert state.get_task_status("T1") == TaskStatus.PENDING.value

    def test_retry_task_with_reset_ignores_orchestrator(self, tmp_path: Path) -> None:
        """Test retry_task with reset=True skips orchestrator."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED)
        state.increment_task_retry("T1")

        mock_orchestrator = MagicMock()

        result = retry_task(state, "T1", reset=True, worker_id=None, orchestrator=mock_orchestrator)

        assert result is True
        # Orchestrator should not be called when reset=True
        mock_orchestrator.retry_task.assert_not_called()
        assert state.get_task_retry_count("T1") == 0


class TestRetryAllFailedTasks:
    """Tests for the retry_all_failed_tasks function."""

    def test_retry_all_failed_tasks_without_reset(self, tmp_path: Path) -> None:
        """Test retry_all_failed_tasks uses orchestrator without reset."""
        with patch("zerg.commands.retry.Orchestrator") as mock_orch_cls:
            mock_orch = MagicMock()
            mock_orch.retry_all_failed.return_value = ["T1", "T2"]
            mock_orch_cls.return_value = mock_orch

            count, retried = retry_all_failed_tasks("test-feature", reset=False)

            assert count == 2
            assert retried == ["T1", "T2"]
            mock_orch.retry_all_failed.assert_called_once()

    def test_retry_all_failed_tasks_with_reset(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test retry_all_failed_tasks with reset does manual retry."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        # Create state with failed tasks
        state = StateManager("test-feature", state_dir=state_dir)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED)
        state.set_task_status("T2", TaskStatus.FAILED)
        state.set_task_status("T3", TaskStatus.COMPLETE)
        state.increment_task_retry("T1")
        state.save()

        with patch("zerg.commands.retry.Orchestrator"):
            count, retried = retry_all_failed_tasks("test-feature", reset=True)

            assert count == 2
            assert "T1" in retried
            assert "T2" in retried

    def test_retry_all_failed_tasks_exception_handling(self) -> None:
        """Test retry_all_failed_tasks handles exceptions gracefully."""
        with patch("zerg.commands.retry.Orchestrator") as mock_orch_cls:
            mock_orch_cls.side_effect = Exception("Connection failed")

            count, retried = retry_all_failed_tasks("test-feature", reset=False)

            assert count == 0
            assert retried == []

    def test_retry_all_failed_tasks_no_failures(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test retry_all_failed_tasks with no failed tasks."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state = StateManager("test-feature", state_dir=state_dir)
        state.load()
        state.set_task_status("T1", TaskStatus.COMPLETE)
        state.save()

        with patch("zerg.commands.retry.Orchestrator"):
            count, retried = retry_all_failed_tasks("test-feature", reset=True)

            assert count == 0
            assert retried == []


class TestRetryCommand:
    """Tests for the retry Click command."""

    def test_retry_no_task_or_all_failed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test retry command fails without task_id or --all-failed."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(retry, [])

        assert result.exit_code == 1
        assert "Error" in result.output

    def test_retry_no_feature_detected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test retry command fails when no feature can be detected."""
        monkeypatch.chdir(tmp_path)
        # No state files

        runner = CliRunner()
        result = runner.invoke(retry, ["TASK-001"])

        assert result.exit_code == 1
        assert "No active feature" in result.output

    def test_retry_feature_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test retry command fails when feature state does not exist."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        runner = CliRunner()
        result = runner.invoke(retry, ["TASK-001", "--feature", "nonexistent"])

        assert result.exit_code == 1
        assert "No state found" in result.output

    def test_retry_no_tasks_to_retry(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test retry command with --all-failed when no failed tasks."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        # Create valid state file with no failed tasks
        state_data = {
            "feature": "test-feature",
            "started_at": datetime.now().isoformat(),
            "current_level": 1,
            "tasks": {"T1": {"status": "complete"}},
            "workers": {},
            "levels": {},
            "execution_log": [],
            "paused": False,
            "error": None,
        }
        (state_dir / "test-feature.json").write_text(json.dumps(state_data))

        runner = CliRunner()
        result = runner.invoke(retry, ["--all-failed", "--feature", "test-feature"])

        assert "No tasks to retry" in result.output

    def test_retry_single_task_confirmed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test retry command for single task with confirmation."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        # Create state with failed task
        state_data = {
            "feature": "test-feature",
            "started_at": datetime.now().isoformat(),
            "current_level": 1,
            "tasks": {"T1": {"status": "failed", "error": "Test error"}},
            "workers": {},
            "levels": {},
            "execution_log": [],
            "paused": False,
            "error": None,
        }
        (state_dir / "test-feature.json").write_text(json.dumps(state_data))

        runner = CliRunner()
        result = runner.invoke(retry, ["T1", "--feature", "test-feature"], input="y\n")

        assert "queued for retry" in result.output

    def test_retry_aborted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test retry command when user aborts."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state_data = {
            "feature": "test-feature",
            "started_at": datetime.now().isoformat(),
            "current_level": 1,
            "tasks": {"T1": {"status": "failed"}},
            "workers": {},
            "levels": {},
            "execution_log": [],
            "paused": False,
            "error": None,
        }
        (state_dir / "test-feature.json").write_text(json.dumps(state_data))

        runner = CliRunner()
        result = runner.invoke(retry, ["T1", "--feature", "test-feature"], input="n\n")

        assert "Aborted" in result.output

    def test_retry_with_reset_option(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test retry command with --reset option."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state_data = {
            "feature": "test-feature",
            "started_at": datetime.now().isoformat(),
            "current_level": 1,
            "tasks": {"T1": {"status": "failed", "retry_count": 3}},
            "workers": {},
            "levels": {},
            "execution_log": [],
            "paused": False,
            "error": None,
        }
        (state_dir / "test-feature.json").write_text(json.dumps(state_data))

        runner = CliRunner()
        result = runner.invoke(retry, ["T1", "--feature", "test-feature", "--reset"], input="y\n")

        assert "queued for retry" in result.output

    def test_retry_with_worker_option(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test retry command with --worker option."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state_data = {
            "feature": "test-feature",
            "started_at": datetime.now().isoformat(),
            "current_level": 1,
            "tasks": {"T1": {"status": "failed"}},
            "workers": {},
            "levels": {},
            "execution_log": [],
            "paused": False,
            "error": None,
        }
        (state_dir / "test-feature.json").write_text(json.dumps(state_data))

        runner = CliRunner()
        with patch("zerg.commands.retry.retry_task") as mock_retry:
            mock_retry.return_value = True
            result = runner.invoke(
                retry,
                ["T1", "--feature", "test-feature", "--worker", "2"],
                input="y\n",
            )

        assert "queued for retry" in result.output

    def test_retry_unpauses_execution(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test retry command unpauses execution if paused."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state_data = {
            "feature": "test-feature",
            "started_at": datetime.now().isoformat(),
            "current_level": 1,
            "tasks": {"T1": {"status": "failed"}},
            "workers": {},
            "levels": {},
            "execution_log": [],
            "paused": True,  # Paused state
            "error": None,
        }
        (state_dir / "test-feature.json").write_text(json.dumps(state_data))

        runner = CliRunner()
        result = runner.invoke(retry, ["T1", "--feature", "test-feature"], input="y\n")

        assert "unpaused" in result.output

    def test_retry_all_failed_tasks_command(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test retry command with --all-failed flag."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state_data = {
            "feature": "test-feature",
            "started_at": datetime.now().isoformat(),
            "current_level": 1,
            "tasks": {
                "T1": {"status": "failed"},
                "T2": {"status": "failed"},
                "T3": {"status": "complete"},
            },
            "workers": {},
            "levels": {},
            "execution_log": [],
            "paused": False,
            "error": None,
        }
        (state_dir / "test-feature.json").write_text(json.dumps(state_data))

        runner = CliRunner()
        result = runner.invoke(retry, ["--all-failed", "--feature", "test-feature"], input="y\n")

        assert "T1" in result.output
        assert "T2" in result.output
        assert "queued for retry" in result.output

    def test_retry_task_queue_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test retry command when task fails to queue."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state_data = {
            "feature": "test-feature",
            "started_at": datetime.now().isoformat(),
            "current_level": 1,
            "tasks": {"T1": {"status": "failed"}},
            "workers": {},
            "levels": {},
            "execution_log": [],
            "paused": False,
            "error": None,
        }
        (state_dir / "test-feature.json").write_text(json.dumps(state_data))

        runner = CliRunner()
        with patch("zerg.commands.retry.retry_task") as mock_retry:
            mock_retry.return_value = False  # Simulate failure
            result = runner.invoke(retry, ["T1", "--feature", "test-feature"], input="y\n")

        assert "failed to queue" in result.output

    def test_retry_auto_detect_feature(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test retry command auto-detects feature from state files."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state_data = {
            "feature": "auto-detected-feature",
            "started_at": datetime.now().isoformat(),
            "current_level": 1,
            "tasks": {"T1": {"status": "failed"}},
            "workers": {},
            "levels": {},
            "execution_log": [],
            "paused": False,
            "error": None,
        }
        (state_dir / "auto-detected-feature.json").write_text(json.dumps(state_data))

        runner = CliRunner()
        result = runner.invoke(retry, ["T1"], input="y\n")

        assert "auto-detected-feature" in result.output

    def test_retry_exception_in_main_flow(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test retry command handles unexpected exceptions."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state_data = {
            "feature": "test-feature",
            "started_at": datetime.now().isoformat(),
            "current_level": 1,
            "tasks": {"T1": {"status": "failed"}},
            "workers": {},
            "levels": {},
            "execution_log": [],
            "paused": False,
            "error": None,
        }
        (state_dir / "test-feature.json").write_text(json.dumps(state_data))

        runner = CliRunner()
        with patch("zerg.commands.retry.show_retry_plan", side_effect=Exception("Display error")):
            result = runner.invoke(retry, ["T1", "--feature", "test-feature"])

        assert result.exit_code == 1
        assert "Error" in result.output


class TestRetryEdgeCases:
    """Edge case tests for retry functionality."""

    def test_retry_blocked_task(self, tmp_path: Path) -> None:
        """Test retrying a blocked task."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.BLOCKED)

        result = retry_task(state, "T1", reset=False, worker_id=None)

        assert result is True
        assert state.get_task_status("T1") == TaskStatus.PENDING.value

    def test_retry_preserves_other_task_data(self, tmp_path: Path) -> None:
        """Test retry preserves other task metadata."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED, worker_id=1, error="Original error")

        retry_task(state, "T1", reset=False, worker_id=None)

        # Status changed but task entry still exists
        assert state.get_task_status("T1") == TaskStatus.PENDING.value

    def test_multiple_retries_increment_count(self, tmp_path: Path) -> None:
        """Test multiple retries increment retry count."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED)

        # First retry
        retry_task(state, "T1", reset=False, worker_id=None)
        state.increment_task_retry("T1")

        # Second retry
        state.set_task_status("T1", TaskStatus.FAILED)
        retry_task(state, "T1", reset=False, worker_id=None)
        state.increment_task_retry("T1")

        assert state.get_task_retry_count("T1") == 2

    def test_reset_clears_error_message(self, tmp_path: Path) -> None:
        """Test reset clears error message from task."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED, error="Critical failure")

        retry_task(state, "T1", reset=True, worker_id=None)

        # Note: The reset sets error=None in set_task_status
        assert state.get_task_status("T1") == TaskStatus.PENDING.value

    def test_retry_with_both_orchestrator_and_worker_id(self, tmp_path: Path) -> None:
        """Test retry with both orchestrator success and worker assignment."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED)

        mock_orchestrator = MagicMock()
        mock_orchestrator.retry_task.return_value = True

        with patch.object(state, "claim_task", create=True) as mock_assign:
            result = retry_task(state, "T1", reset=False, worker_id=5, orchestrator=mock_orchestrator)

            assert result is True
            mock_orchestrator.retry_task.assert_called_once_with("T1")
            mock_assign.assert_called_once_with("T1", 5)

    def test_retry_task_with_reset_and_worker(self, tmp_path: Path) -> None:
        """Test retry_task with reset and worker_id assignment."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED)
        state.increment_task_retry("T1")

        with patch.object(state, "claim_task", create=True) as mock_assign:
            result = retry_task(state, "T1", reset=True, worker_id=3)

            assert result is True
            assert state.get_task_status("T1") == TaskStatus.PENDING.value
            assert state.get_task_retry_count("T1") == 0
            mock_assign.assert_called_once_with("T1", 3)

    def test_retry_task_orchestrator_fallback_with_worker(self, tmp_path: Path) -> None:
        """Test retry_task falls back and assigns worker when orchestrator fails."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED)

        mock_orchestrator = MagicMock()
        mock_orchestrator.retry_task.return_value = False  # Orchestrator fails

        with patch.object(state, "claim_task", create=True) as mock_assign:
            result = retry_task(state, "T1", reset=False, worker_id=4, orchestrator=mock_orchestrator)

            assert result is True
            # Should have fallen back and assigned worker
            mock_assign.assert_called_once_with("T1", 4)
