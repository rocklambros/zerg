"""Unit tests for ZERG retry command module.

Thinned from 46 tests to cover unique code paths:
- detect_feature (no dir, single file)
- get_failed_tasks (no failures, with failures, with blocked)
- show_retry_plan (basic, with reset)
- retry_task (simple requeue, with reset, with worker, orchestrator success/fallback, exception)
- retry_all_failed_tasks (without reset, with reset, exception)
- CLI command (no args, no feature, single task, all-failed, abort, queue failure)
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

    def test_no_state_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test returns None when state directory does not exist."""
        monkeypatch.chdir(tmp_path)
        assert detect_feature() is None

    def test_single_state_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test returns feature name from single state file."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "my-feature.json").write_text("{}")
        assert detect_feature() == "my-feature"


class TestGetFailedTasks:
    """Tests for the get_failed_tasks function."""

    def test_no_failures(self, tmp_path: Path) -> None:
        """Test returns empty list when no failures."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.COMPLETE)
        assert get_failed_tasks(state) == []

    def test_with_failed_and_blocked(self, tmp_path: Path) -> None:
        """Test returns failed and blocked task IDs."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED, error="err")
        state.set_task_status("T2", TaskStatus.BLOCKED)
        state.set_task_status("T3", TaskStatus.COMPLETE)
        result = get_failed_tasks(state)
        assert "T1" in result
        assert "T2" in result
        assert "T3" not in result


class TestShowRetryPlan:
    """Tests for the show_retry_plan function."""

    def test_show_retry_plan_displays_tasks(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test show_retry_plan displays failed tasks."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED)
        show_retry_plan(state, ["T1"], reset=False, worker_id=None)
        captured = capsys.readouterr()
        assert "T1" in captured.out

    def test_show_retry_plan_with_reset(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test show_retry_plan shows RESET action."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED)
        show_retry_plan(state, ["T1"], reset=True, worker_id=None)
        captured = capsys.readouterr()
        assert "RESET" in captured.out


class TestRetryTask:
    """Tests for the retry_task function."""

    def test_simple_requeue(self, tmp_path: Path) -> None:
        """Test retry_task simple requeue without reset."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED, error="Error occurred")
        assert retry_task(state, "T1", reset=False, worker_id=None) is True
        assert state.get_task_status("T1") == TaskStatus.PENDING.value

    def test_with_reset_clears_retry_count(self, tmp_path: Path) -> None:
        """Test retry_task with reset clears retry count."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED)
        state.increment_task_retry("T1")
        state.increment_task_retry("T1")
        assert retry_task(state, "T1", reset=True, worker_id=None) is True
        assert state.get_task_retry_count("T1") == 0

    def test_with_worker_assignment(self, tmp_path: Path) -> None:
        """Test retry_task assigns to specific worker."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED)
        with patch.object(state, "claim_task", create=True) as mock_assign:
            assert retry_task(state, "T1", reset=False, worker_id=3) is True
            mock_assign.assert_called_once_with("T1", 3)

    def test_orchestrator_success(self, tmp_path: Path) -> None:
        """Test retry_task uses orchestrator when available."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED)
        mock_orch = MagicMock()
        mock_orch.retry_task.return_value = True
        assert retry_task(state, "T1", reset=False, worker_id=None, orchestrator=mock_orch) is True
        mock_orch.retry_task.assert_called_once_with("T1")

    def test_orchestrator_fallback(self, tmp_path: Path) -> None:
        """Test retry_task falls back when orchestrator fails."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        state.set_task_status("T1", TaskStatus.FAILED)
        mock_orch = MagicMock()
        mock_orch.retry_task.return_value = False
        assert retry_task(state, "T1", reset=False, worker_id=None, orchestrator=mock_orch) is True
        assert state.get_task_status("T1") == TaskStatus.PENDING.value

    def test_exception_handling(self, tmp_path: Path) -> None:
        """Test retry_task returns False on exception."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()
        with patch.object(state, "set_task_status", side_effect=Exception("DB error")):
            assert retry_task(state, "T1", reset=False, worker_id=None) is False


class TestRetryAllFailedTasks:
    """Tests for the retry_all_failed_tasks function."""

    def test_without_reset(self) -> None:
        """Test uses orchestrator without reset."""
        with patch("zerg.commands.retry.Orchestrator") as mock_orch_cls:
            mock_orch = MagicMock()
            mock_orch.retry_all_failed.return_value = ["T1", "T2"]
            mock_orch_cls.return_value = mock_orch
            count, retried = retry_all_failed_tasks("test-feature", reset=False)
            assert count == 2
            assert retried == ["T1", "T2"]

    def test_exception_handling(self) -> None:
        """Test handles exceptions gracefully."""
        with patch("zerg.commands.retry.Orchestrator") as mock_orch_cls:
            mock_orch_cls.side_effect = Exception("Connection failed")
            count, retried = retry_all_failed_tasks("test-feature", reset=False)
            assert count == 0
            assert retried == []


class TestRetryCommand:
    """Tests for the retry Click command."""

    def _make_state_data(self, tasks: dict | None = None, paused: bool = False) -> str:
        """Helper to create state JSON."""
        return json.dumps(
            {
                "feature": "test-feature",
                "started_at": datetime.now().isoformat(),
                "current_level": 1,
                "tasks": tasks or {"T1": {"status": "failed"}},
                "workers": {},
                "levels": {},
                "execution_log": [],
                "paused": paused,
                "error": None,
            }
        )

    def test_no_task_or_all_failed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test fails without task_id or --all-failed."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(retry, [])
        assert result.exit_code == 1

    def test_no_feature_detected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test fails when no feature can be detected."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(retry, ["TASK-001"])
        assert result.exit_code == 1
        assert "No active feature" in result.output

    def test_single_task_confirmed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test retry command for single task with confirmation."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "test-feature.json").write_text(self._make_state_data())
        runner = CliRunner()
        result = runner.invoke(retry, ["T1", "--feature", "test-feature"], input="y\n")
        assert "queued for retry" in result.output

    def test_aborted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test retry command when user aborts."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "test-feature.json").write_text(self._make_state_data())
        runner = CliRunner()
        result = runner.invoke(retry, ["T1", "--feature", "test-feature"], input="n\n")
        assert "Aborted" in result.output

    def test_all_failed_tasks(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test retry command with --all-failed flag."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)
        tasks = {"T1": {"status": "failed"}, "T2": {"status": "failed"}, "T3": {"status": "complete"}}
        (state_dir / "test-feature.json").write_text(self._make_state_data(tasks=tasks))
        runner = CliRunner()
        result = runner.invoke(retry, ["--all-failed", "--feature", "test-feature"], input="y\n")
        assert "T1" in result.output
        assert "queued for retry" in result.output

    def test_task_queue_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test retry command when task fails to queue."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "test-feature.json").write_text(self._make_state_data())
        runner = CliRunner()
        with patch("zerg.commands.retry.retry_task") as mock_retry:
            mock_retry.return_value = False
            result = runner.invoke(retry, ["T1", "--feature", "test-feature"], input="y\n")
        assert "failed to queue" in result.output
