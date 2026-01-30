"""Tests for TaskRetryManager component."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.config import ZergConfig
from zerg.constants import TaskStatus
from zerg.levels import LevelController
from zerg.state import StateManager
from zerg.task_retry_manager import TaskRetryManager


@pytest.fixture
def mock_config():
    config = MagicMock(spec=ZergConfig)
    config.workers = MagicMock()
    config.workers.retry_attempts = 3
    config.workers.backoff_strategy = "exponential"
    config.workers.backoff_base_seconds = 30
    config.workers.backoff_max_seconds = 300
    return config


@pytest.fixture
def mock_state():
    state = MagicMock(spec=StateManager)
    state.get_task_retry_count.return_value = 0
    state.increment_task_retry.return_value = 1
    state.get_tasks_ready_for_retry.return_value = []
    state.get_failed_tasks.return_value = []
    state.get_task_status.return_value = TaskStatus.FAILED.value
    return state


@pytest.fixture
def mock_levels():
    return MagicMock(spec=LevelController)


@pytest.fixture
def retry_manager(mock_config, mock_state, mock_levels, tmp_path):
    return TaskRetryManager(
        config=mock_config,
        state=mock_state,
        levels=mock_levels,
        repo_path=tmp_path,
    )


class TestHandleTaskFailure:
    """Tests for handle_task_failure."""

    def test_retries_when_under_limit(self, retry_manager, mock_state):
        """Task is scheduled for retry when under max attempts."""
        mock_state.get_task_retry_count.return_value = 0

        result = retry_manager.handle_task_failure("TASK-001", 0, "some error")

        assert result is True
        mock_state.increment_task_retry.assert_called_once()
        mock_state.set_task_status.assert_called_with("TASK-001", "waiting_retry")

    def test_marks_failed_when_over_limit(self, retry_manager, mock_state, mock_levels):
        """Task is permanently failed when retry limit reached."""
        mock_state.get_task_retry_count.return_value = 3  # At limit

        result = retry_manager.handle_task_failure("TASK-001", 0, "persistent error")

        assert result is False
        mock_levels.mark_task_failed.assert_called_once_with("TASK-001", "persistent error")
        mock_state.set_task_status.assert_called_once()
        # Check it was set to FAILED
        call_args = mock_state.set_task_status.call_args
        assert call_args[0][1] == TaskStatus.FAILED

    def test_emits_structured_log_on_retry(self, mock_config, mock_state, mock_levels, tmp_path):
        """Structured writer emits warning on retry."""
        writer = MagicMock()
        manager = TaskRetryManager(
            config=mock_config, state=mock_state, levels=mock_levels,
            repo_path=tmp_path, structured_writer=writer,
        )
        mock_state.get_task_retry_count.return_value = 0

        manager.handle_task_failure("TASK-001", 0, "err")

        writer.emit.assert_called_once()


class TestRetryTask:
    """Tests for retry_task."""

    def test_resets_failed_task_to_pending(self, retry_manager, mock_state):
        """Failed task is reset to pending."""
        mock_state.get_task_status.return_value = TaskStatus.FAILED.value

        result = retry_manager.retry_task("TASK-001")

        assert result is True
        mock_state.reset_task_retry.assert_called_with("TASK-001")
        mock_state.set_task_status.assert_called_with("TASK-001", TaskStatus.PENDING)

    def test_rejects_non_failed_tasks(self, retry_manager, mock_state):
        """Non-failed tasks cannot be retried."""
        mock_state.get_task_status.return_value = "running"

        result = retry_manager.retry_task("TASK-001")

        assert result is False
        mock_state.reset_task_retry.assert_not_called()

    def test_accepts_string_failed_status(self, retry_manager, mock_state):
        """String 'failed' is also accepted."""
        mock_state.get_task_status.return_value = "failed"

        result = retry_manager.retry_task("TASK-001")

        assert result is True


class TestRetryAllFailed:
    """Tests for retry_all_failed."""

    def test_processes_all_failed_tasks(self, retry_manager, mock_state):
        """All failed tasks are queued for retry."""
        mock_state.get_failed_tasks.return_value = [
            {"task_id": "TASK-001"},
            {"task_id": "TASK-002"},
        ]
        mock_state.get_task_status.return_value = TaskStatus.FAILED.value

        retried = retry_manager.retry_all_failed()

        assert len(retried) == 2
        assert "TASK-001" in retried
        assert "TASK-002" in retried


class TestCheckRetryReadyTasks:
    """Tests for check_retry_ready_tasks."""

    def test_requeues_ready_tasks(self, retry_manager, mock_state):
        """Tasks whose backoff elapsed are requeued as PENDING."""
        mock_state.get_tasks_ready_for_retry.return_value = ["TASK-001", "TASK-002"]

        retry_manager.check_retry_ready_tasks()

        assert mock_state.set_task_status.call_count == 2
        mock_state.set_task_status.assert_any_call("TASK-001", TaskStatus.PENDING)
        mock_state.set_task_status.assert_any_call("TASK-002", TaskStatus.PENDING)


class TestVerifyWithRetry:
    """Tests for verify_with_retry."""

    @patch("zerg.verify.VerificationExecutor")
    def test_succeeds_on_first_attempt(self, mock_verifier_cls, retry_manager):
        """Verification passes on first try."""
        success_result = MagicMock()
        success_result.success = True
        verifier = MagicMock()
        verifier.verify.return_value = success_result
        mock_verifier_cls.return_value = verifier

        result = retry_manager.verify_with_retry("TASK-001", "echo ok")

        assert result is True
        assert verifier.verify.call_count == 1

    @patch("time.sleep")
    @patch("zerg.verify.VerificationExecutor")
    def test_fails_after_max_retries(self, mock_verifier_cls, mock_sleep, retry_manager):
        """Verification fails after exhausting retries."""
        fail_result = MagicMock()
        fail_result.success = False
        verifier = MagicMock()
        verifier.verify.return_value = fail_result
        mock_verifier_cls.return_value = verifier

        result = retry_manager.verify_with_retry("TASK-001", "false", max_retries=2)

        assert result is False
        # 1 initial + 2 retries = 3 attempts
        assert verifier.verify.call_count == 3
