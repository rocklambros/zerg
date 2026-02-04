"""Tests for ZERG step executor module."""

from pathlib import Path
from unittest.mock import MagicMock

from zerg.heartbeat import HeartbeatWriter
from zerg.step_executor import (
    Step,
    StepAction,
    StepExecutor,
    StepResult,
    StepState,
    StepVerify,
    TaskResult,
)


class TestStepAction:
    """Tests for StepAction enum."""

    def test_values(self) -> None:
        """Test StepAction enum values exist."""
        assert StepAction.WRITE_TEST.value == "write_test"
        assert StepAction.VERIFY_FAIL.value == "verify_fail"
        assert StepAction.IMPLEMENT.value == "implement"
        assert StepAction.VERIFY_PASS.value == "verify_pass"
        assert StepAction.FORMAT.value == "format"
        assert StepAction.COMMIT.value == "commit"


class TestStepVerify:
    """Tests for StepVerify enum."""

    def test_values(self) -> None:
        """Test StepVerify enum values exist."""
        assert StepVerify.EXIT_CODE.value == "exit_code"
        assert StepVerify.EXIT_CODE_NONZERO.value == "exit_code_nonzero"
        assert StepVerify.NONE.value == "none"


class TestStepState:
    """Tests for StepState enum."""

    def test_values(self) -> None:
        """Test StepState enum values exist."""
        assert StepState.PENDING.value == "pending"
        assert StepState.IN_PROGRESS.value == "in_progress"
        assert StepState.COMPLETED.value == "completed"
        assert StepState.FAILED.value == "failed"
        assert StepState.SKIPPED.value == "skipped"


class TestStepResult:
    """Tests for StepResult dataclass."""

    def test_creation(self) -> None:
        """Test StepResult creation."""
        result = StepResult(
            step_number=1,
            action="implement",
            state=StepState.COMPLETED,
            exit_code=0,
            stdout="Success",
            stderr="",
            duration_ms=100,
        )
        assert result.step_number == 1
        assert result.action == "implement"
        assert result.state == StepState.COMPLETED
        assert result.exit_code == 0

    def test_to_dict(self) -> None:
        """Test StepResult serialization."""
        result = StepResult(
            step_number=2,
            action="verify_pass",
            state=StepState.FAILED,
            exit_code=1,
            error_message="Test failed",
        )
        d = result.to_dict()
        assert d["step_number"] == 2
        assert d["action"] == "verify_pass"
        assert d["state"] == "failed"
        assert d["exit_code"] == 1
        assert d["error_message"] == "Test failed"


class TestTaskResult:
    """Tests for TaskResult dataclass."""

    def test_success_result(self) -> None:
        """Test successful TaskResult."""
        result = TaskResult(
            task_id="TASK-001",
            success=True,
            total_duration_ms=500,
        )
        assert result.task_id == "TASK-001"
        assert result.success is True
        assert result.failed_step is None

    def test_failure_result(self) -> None:
        """Test failed TaskResult."""
        result = TaskResult(
            task_id="TASK-002",
            success=False,
            failed_step=3,
            error_message="Step 3 failed",
        )
        assert result.success is False
        assert result.failed_step == 3

    def test_to_dict(self) -> None:
        """Test TaskResult serialization."""
        step_result = StepResult(
            step_number=1,
            action="implement",
            state=StepState.COMPLETED,
        )
        result = TaskResult(
            task_id="TASK-003",
            success=True,
            step_results=[step_result],
            total_duration_ms=1000,
        )
        d = result.to_dict()
        assert d["task_id"] == "TASK-003"
        assert d["success"] is True
        assert len(d["step_results"]) == 1
        assert d["total_duration_ms"] == 1000


class TestStepExecutor:
    """Tests for StepExecutor class."""

    def test_execute_classic_mode_empty_steps(self) -> None:
        """Test execution with empty steps (classic mode)."""
        executor = StepExecutor(task_id="TASK-001")
        result = executor.execute(steps=None)

        assert result.success is True
        assert result.task_id == "TASK-001"
        assert result.failed_step is None
        assert len(result.step_results) == 0

    def test_execute_classic_mode_no_steps(self) -> None:
        """Test execution with empty list (classic mode)."""
        executor = StepExecutor(task_id="TASK-002")
        result = executor.execute(steps=[])

        assert result.success is True
        assert result.failed_step is None

    def test_execute_single_step_success(self) -> None:
        """Test successful execution of single step."""
        steps: list[Step] = [
            {
                "step": 1,
                "action": "implement",
                "run": "echo 'success'",
                "verify": "exit_code",
            }
        ]
        executor = StepExecutor(task_id="TASK-003")
        result = executor.execute(steps)

        assert result.success is True
        assert len(result.step_results) == 1
        assert result.step_results[0].state == StepState.COMPLETED
        assert result.step_results[0].exit_code == 0

    def test_execute_single_step_failure(self) -> None:
        """Test failed execution of single step."""
        steps: list[Step] = [
            {
                "step": 1,
                "action": "verify_pass",
                "run": "exit 1",
                "verify": "exit_code",
            }
        ]
        executor = StepExecutor(task_id="TASK-004")
        result = executor.execute(steps)

        assert result.success is False
        assert result.failed_step == 1
        assert len(result.step_results) == 1
        assert result.step_results[0].state == StepState.FAILED

    def test_execute_multiple_steps_success(self) -> None:
        """Test successful execution of multiple steps."""
        steps: list[Step] = [
            {"step": 1, "action": "write_test", "run": "echo 'test written'", "verify": "exit_code"},
            {"step": 2, "action": "verify_fail", "run": "exit 1", "verify": "exit_code_nonzero"},
            {"step": 3, "action": "implement", "run": "echo 'implemented'", "verify": "exit_code"},
            {"step": 4, "action": "verify_pass", "run": "echo 'tests pass'", "verify": "exit_code"},
        ]
        executor = StepExecutor(task_id="TASK-005")
        result = executor.execute(steps)

        assert result.success is True
        assert len(result.step_results) == 4
        for sr in result.step_results:
            assert sr.state == StepState.COMPLETED

    def test_execute_multiple_steps_failure_middle(self) -> None:
        """Test failure in middle step."""
        steps: list[Step] = [
            {"step": 1, "action": "write_test", "run": "echo 'done'", "verify": "exit_code"},
            {"step": 2, "action": "implement", "run": "exit 1", "verify": "exit_code"},
            {"step": 3, "action": "verify_pass", "run": "echo 'pass'", "verify": "exit_code"},
        ]
        executor = StepExecutor(task_id="TASK-006")
        result = executor.execute(steps)

        assert result.success is False
        assert result.failed_step == 2
        assert len(result.step_results) == 2  # Only executed 2 steps
        assert result.step_results[0].state == StepState.COMPLETED
        assert result.step_results[1].state == StepState.FAILED

    def test_verify_exit_code_nonzero(self) -> None:
        """Test exit_code_nonzero verification mode."""
        steps: list[Step] = [
            {
                "step": 1,
                "action": "verify_fail",
                "run": "exit 1",
                "verify": "exit_code_nonzero",
            }
        ]
        executor = StepExecutor(task_id="TASK-007")
        result = executor.execute(steps)

        assert result.success is True
        assert result.step_results[0].exit_code == 1

    def test_verify_exit_code_nonzero_fails_on_zero(self) -> None:
        """Test exit_code_nonzero fails when exit code is 0."""
        steps: list[Step] = [
            {
                "step": 1,
                "action": "verify_fail",
                "run": "exit 0",
                "verify": "exit_code_nonzero",
            }
        ]
        executor = StepExecutor(task_id="TASK-008")
        result = executor.execute(steps)

        assert result.success is False
        assert "non-zero" in (result.error_message or "").lower()

    def test_verify_none_always_passes(self) -> None:
        """Test verify=none always passes."""
        steps: list[Step] = [
            {"step": 1, "action": "format", "run": "exit 42", "verify": "none"},
        ]
        executor = StepExecutor(task_id="TASK-009")
        result = executor.execute(steps)

        assert result.success is True
        assert result.step_results[0].exit_code == 42

    def test_step_without_command(self) -> None:
        """Test step with no run command."""
        steps: list[Step] = [
            {"step": 1, "action": "write_test", "run": "", "verify": "exit_code"},
        ]
        executor = StepExecutor(task_id="TASK-010")
        result = executor.execute(steps)

        assert result.success is True
        assert result.step_results[0].state == StepState.COMPLETED

    def test_heartbeat_updates(self, tmp_path: Path) -> None:
        """Test heartbeat is updated during execution."""
        writer = HeartbeatWriter(worker_id=1, state_dir=tmp_path)

        steps: list[Step] = [
            {"step": 1, "action": "implement", "run": "echo 'done'", "verify": "exit_code"},
            {"step": 2, "action": "verify", "run": "echo 'verified'", "verify": "exit_code"},
        ]
        executor = StepExecutor(task_id="TASK-011", heartbeat_writer=writer)
        result = executor.execute(steps)

        assert result.success is True

        # Verify heartbeat file was created
        heartbeat_path = tmp_path / "heartbeat-1.json"
        assert heartbeat_path.exists()

    def test_heartbeat_updates_with_mock(self) -> None:
        """Test heartbeat write calls with mock."""
        mock_writer = MagicMock(spec=HeartbeatWriter)

        steps: list[Step] = [
            {"step": 1, "action": "implement", "run": "echo 'done'", "verify": "exit_code"},
        ]
        executor = StepExecutor(task_id="TASK-012", heartbeat_writer=mock_writer)
        executor.execute(steps)

        # Should have been called at least once
        assert mock_writer.write.called

        # Check that step progress was included
        calls = mock_writer.write.call_args_list
        for call in calls:
            _, kwargs = call
            assert "current_step" in kwargs
            assert "total_steps" in kwargs
            assert "step_states" in kwargs

    def test_working_directory(self, tmp_path: Path) -> None:
        """Test execution uses specified working directory."""
        # Create a file in tmp_path
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        steps: list[Step] = [
            {"step": 1, "action": "check", "run": "ls test.txt", "verify": "exit_code"},
        ]
        executor = StepExecutor(task_id="TASK-013", working_dir=str(tmp_path))
        result = executor.execute(steps)

        assert result.success is True

    def test_command_timeout(self) -> None:
        """Test command timeout handling."""
        steps: list[Step] = [
            {"step": 1, "action": "slow", "run": "sleep 10", "verify": "exit_code"},
        ]
        executor = StepExecutor(task_id="TASK-014", default_timeout=1)
        result = executor.execute(steps)

        assert result.success is False
        assert "timed out" in (result.error_message or "").lower()
        assert result.step_results[0].state == StepState.FAILED

    def test_step_number_from_step_field(self) -> None:
        """Test step number is taken from step field."""
        steps: list[Step] = [
            {"step": 5, "action": "test", "run": "echo 'ok'", "verify": "exit_code"},
        ]
        executor = StepExecutor(task_id="TASK-015")
        result = executor.execute(steps)

        assert result.step_results[0].step_number == 5

    def test_step_number_defaults_to_index(self) -> None:
        """Test step number defaults to 1-based index if not provided."""
        steps: list[Step] = [
            {"action": "test", "run": "echo 'ok'", "verify": "exit_code"},
        ]
        executor = StepExecutor(task_id="TASK-016")
        result = executor.execute(steps)

        assert result.step_results[0].step_number == 1

    def test_output_truncation(self) -> None:
        """Test long output is truncated."""
        # Generate long output
        steps: list[Step] = [
            {
                "step": 1,
                "action": "verbose",
                "run": "python -c \"print('x' * 20000)\"",
                "verify": "exit_code",
            },
        ]
        executor = StepExecutor(task_id="TASK-017")
        result = executor.execute(steps)

        assert result.success is True
        # Output should be truncated to 10000 chars
        assert len(result.step_results[0].stdout) <= 10000

    def test_unknown_verify_mode_treated_as_exit_code(self) -> None:
        """Test unknown verify mode defaults to exit_code behavior."""
        steps: list[Step] = [
            {"step": 1, "action": "test", "run": "exit 0", "verify": "unknown_mode"},
        ]
        executor = StepExecutor(task_id="TASK-018")
        result = executor.execute(steps)

        assert result.success is True  # exit 0 passes for exit_code

    def test_execution_error_handling(self) -> None:
        """Test handling of execution errors."""
        # Simulate execution error with invalid command
        steps: list[Step] = [
            {
                "step": 1,
                "action": "bad",
                "run": "/nonexistent/command/path",
                "verify": "exit_code",
            },
        ]
        executor = StepExecutor(task_id="TASK-019")
        result = executor.execute(steps)

        # Should fail (command not found)
        assert result.success is False
        assert result.step_results[0].state == StepState.FAILED

    def test_total_duration_tracked(self) -> None:
        """Test total duration is tracked."""
        steps: list[Step] = [
            {"step": 1, "action": "test", "run": "echo 'done'", "verify": "exit_code"},
        ]
        executor = StepExecutor(task_id="TASK-020")
        result = executor.execute(steps)

        assert result.total_duration_ms >= 0

    def test_step_states_tracking(self) -> None:
        """Test step states are properly tracked."""
        mock_writer = MagicMock(spec=HeartbeatWriter)

        steps: list[Step] = [
            {"step": 1, "action": "first", "run": "echo '1'", "verify": "exit_code"},
            {"step": 2, "action": "second", "run": "exit 1", "verify": "exit_code"},
            {"step": 3, "action": "third", "run": "echo '3'", "verify": "exit_code"},
        ]
        executor = StepExecutor(task_id="TASK-021", heartbeat_writer=mock_writer)
        result = executor.execute(steps)

        assert result.success is False
        assert result.failed_step == 2

        # Check that step states were updated
        calls = mock_writer.write.call_args_list
        # Last call should have: completed, failed, skipped
        last_call = calls[-1]
        _, kwargs = last_call
        step_states = kwargs.get("step_states", [])
        assert len(step_states) == 3
        # After failure at step 2:
        # - Step 1: completed
        # - Step 2: failed
        # - Step 3: skipped

    def test_heartbeat_failure_does_not_abort_execution(self, tmp_path: Path) -> None:
        """Test that heartbeat write failure doesn't abort task execution."""
        mock_writer = MagicMock(spec=HeartbeatWriter)
        mock_writer.write.side_effect = OSError("Heartbeat write failed")

        steps: list[Step] = [
            {"step": 1, "action": "test", "run": "echo 'done'", "verify": "exit_code"},
        ]
        executor = StepExecutor(task_id="TASK-022", heartbeat_writer=mock_writer)
        result = executor.execute(steps)

        # Should still succeed despite heartbeat failure
        assert result.success is True


class TestStepExecutorEdgeCases:
    """Edge case tests for StepExecutor."""

    def test_empty_action_defaults_to_unknown(self) -> None:
        """Test missing action field defaults to unknown."""
        steps: list[Step] = [
            {"step": 1, "run": "echo 'ok'", "verify": "exit_code"},
        ]
        executor = StepExecutor(task_id="TASK-100")
        result = executor.execute(steps)

        assert result.success is True
        assert result.step_results[0].action == "unknown"

    def test_missing_verify_defaults_to_exit_code(self) -> None:
        """Test missing verify field defaults to exit_code."""
        steps: list[Step] = [
            {"step": 1, "action": "test", "run": "exit 0"},  # No verify field
        ]
        executor = StepExecutor(task_id="TASK-101")
        result = executor.execute(steps)

        assert result.success is True

    def test_all_tdd_actions(self) -> None:
        """Test full TDD cycle with all action types."""
        steps: list[Step] = [
            {"step": 1, "action": "write_test", "run": "echo 'test'", "verify": "exit_code"},
            {"step": 2, "action": "verify_fail", "run": "exit 1", "verify": "exit_code_nonzero"},
            {"step": 3, "action": "implement", "run": "echo 'impl'", "verify": "exit_code"},
            {"step": 4, "action": "verify_pass", "run": "echo 'pass'", "verify": "exit_code"},
            {"step": 5, "action": "format", "run": "echo 'formatted'", "verify": "none"},
            {"step": 6, "action": "commit", "run": "echo 'committed'", "verify": "exit_code"},
        ]
        executor = StepExecutor(task_id="TASK-102")
        result = executor.execute(steps)

        assert result.success is True
        assert len(result.step_results) == 6

    def test_stderr_included_in_error_message(self) -> None:
        """Test stderr is included in error message on failure."""
        steps: list[Step] = [
            {
                "step": 1,
                "action": "fail",
                "run": "echo 'error details' >&2; exit 1",
                "verify": "exit_code",
            },
        ]
        executor = StepExecutor(task_id="TASK-103")
        result = executor.execute(steps)

        assert result.success is False
        assert "error details" in (result.error_message or "")

    def test_step_results_contain_stdout(self) -> None:
        """Test step results contain stdout."""
        steps: list[Step] = [
            {"step": 1, "action": "test", "run": "echo 'output'", "verify": "exit_code"},
        ]
        executor = StepExecutor(task_id="TASK-104")
        result = executor.execute(steps)

        assert "output" in result.step_results[0].stdout

    def test_step_results_contain_stderr(self) -> None:
        """Test step results contain stderr."""
        steps: list[Step] = [
            {
                "step": 1,
                "action": "test",
                "run": "echo 'stderr message' >&2",
                "verify": "exit_code",
            },
        ]
        executor = StepExecutor(task_id="TASK-105")
        result = executor.execute(steps)

        assert "stderr message" in result.step_results[0].stderr
