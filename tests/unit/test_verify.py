"""Tests for ZERG verification executor module."""

from datetime import datetime
from pathlib import Path

import pytest

from zerg.exceptions import TaskTimeoutError, TaskVerificationFailedError
from zerg.verify import VerificationExecutionResult, VerificationExecutor


class TestVerificationExecutionResult:
    """Tests for VerificationExecutionResult dataclass."""

    def test_creation(self) -> None:
        """Test result creation."""
        result = VerificationExecutionResult(
            task_id="TASK-001",
            success=True,
            exit_code=0,
            stdout="output",
            stderr="",
            duration_ms=100,
            command="echo test",
        )

        assert result.task_id == "TASK-001"
        assert result.success is True
        assert result.exit_code == 0
        assert result.stdout == "output"
        assert result.duration_ms == 100
        assert isinstance(result.timestamp, datetime)

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        result = VerificationExecutionResult(
            task_id="TASK-001",
            success=True,
            exit_code=0,
            stdout="output",
            stderr="error",
            duration_ms=100,
            command="pytest",
        )

        data = result.to_dict()

        assert data["task_id"] == "TASK-001"
        assert data["success"] is True
        assert data["exit_code"] == 0
        assert data["stdout"] == "output"
        assert data["stderr"] == "error"
        assert data["duration_ms"] == 100
        assert data["command"] == "pytest"
        assert "timestamp" in data


class TestVerificationExecutor:
    """Tests for VerificationExecutor class."""

    def test_init_default(self) -> None:
        """Test default initialization."""
        executor = VerificationExecutor()
        assert executor.default_timeout == 30

    def test_init_custom_timeout(self) -> None:
        """Test initialization with custom timeout."""
        executor = VerificationExecutor(default_timeout=60)
        assert executor.default_timeout == 60

    def test_verify_success(self, tmp_path: Path) -> None:
        """Test successful verification."""
        executor = VerificationExecutor()

        result = executor.verify("echo hello", "TASK-001", cwd=tmp_path)

        assert result.success is True
        assert result.exit_code == 0
        assert "hello" in result.stdout
        assert result.task_id == "TASK-001"

    def test_verify_failure(self, tmp_path: Path) -> None:
        """Test failed verification."""
        executor = VerificationExecutor()

        result = executor.verify("python -c 'exit(1)'", "TASK-001", cwd=tmp_path)

        assert result.success is False
        assert result.exit_code == 1

    def test_verify_with_timeout(self, tmp_path: Path) -> None:
        """Test verification with custom timeout."""
        executor = VerificationExecutor(default_timeout=30)

        # Quick command should succeed
        result = executor.verify("echo fast", "TASK-001", timeout=5, cwd=tmp_path)

        assert result.success is True

    def test_verify_invalid_command(self, tmp_path: Path) -> None:
        """Test verification with invalid command (dangerous patterns)."""
        executor = VerificationExecutor()

        # Commands with shell metacharacters should be blocked
        result = executor.verify("echo test; rm -rf /", "TASK-001", cwd=tmp_path)

        assert result.success is False
        assert "validation" in result.stderr.lower()

    def test_verify_stores_results(self, tmp_path: Path) -> None:
        """Test that results are stored."""
        executor = VerificationExecutor()

        executor.verify("echo one", "TASK-001", cwd=tmp_path)
        executor.verify("echo two", "TASK-002", cwd=tmp_path)

        results = executor.get_results()
        assert len(results) == 2

    def test_get_results_for_task(self, tmp_path: Path) -> None:
        """Test getting results for specific task."""
        executor = VerificationExecutor()

        executor.verify("echo one", "TASK-001", cwd=tmp_path)
        executor.verify("echo two", "TASK-002", cwd=tmp_path)
        executor.verify("echo three", "TASK-001", cwd=tmp_path)

        task_results = executor.get_results_for_task("TASK-001")
        assert len(task_results) == 2

    def test_clear_results(self, tmp_path: Path) -> None:
        """Test clearing results."""
        executor = VerificationExecutor()

        executor.verify("echo test", "TASK-001", cwd=tmp_path)
        assert len(executor.get_results()) == 1

        executor.clear_results()
        assert len(executor.get_results()) == 0


class TestVerifyTask:
    """Tests for verify_task method."""

    def test_verify_task_with_spec(self, tmp_path: Path) -> None:
        """Test verifying task with verification spec."""
        executor = VerificationExecutor()

        task = {
            "id": "TASK-001",
            "verification": {
                "command": "echo success",
                "timeout_seconds": 10,
            },
        }

        result = executor.verify_task(task, cwd=tmp_path)

        assert result.success is True
        assert result.task_id == "TASK-001"

    def test_verify_task_no_spec(self, tmp_path: Path) -> None:
        """Test verifying task without verification spec."""
        executor = VerificationExecutor()

        task = {"id": "TASK-001"}

        result = executor.verify_task(task, cwd=tmp_path)

        # No verification = auto pass
        assert result.success is True
        assert result.exit_code == 0
        assert "No verification" in result.stdout


class TestVerifyWithRetry:
    """Tests for verify_with_retry method."""

    def test_verify_with_retry_success_first_try(self, tmp_path: Path) -> None:
        """Test retry succeeds on first try."""
        executor = VerificationExecutor()

        result = executor.verify_with_retry(
            "echo success",
            "TASK-001",
            max_retries=3,
            cwd=tmp_path,
        )

        assert result.success is True

    def test_verify_with_retry_fails_all(self, tmp_path: Path) -> None:
        """Test retry exhausts all attempts."""
        executor = VerificationExecutor()

        result = executor.verify_with_retry(
            "python -c 'exit(1)'",
            "TASK-001",
            max_retries=2,
            retry_delay=0.1,
            cwd=tmp_path,
        )

        assert result.success is False
        # Should have 2 results (initial + 1 retry)
        task_results = executor.get_results_for_task("TASK-001")
        assert len(task_results) == 2


class TestCheckResult:
    """Tests for check_result method."""

    def test_check_result_success(self) -> None:
        """Test checking successful result."""
        executor = VerificationExecutor()

        result = VerificationExecutionResult(
            task_id="TASK-001",
            success=True,
            exit_code=0,
            stdout="",
            stderr="",
            duration_ms=100,
            command="test",
        )

        assert executor.check_result(result) is True

    def test_check_result_failure_no_raise(self) -> None:
        """Test checking failed result without raising."""
        executor = VerificationExecutor()

        result = VerificationExecutionResult(
            task_id="TASK-001",
            success=False,
            exit_code=1,
            stdout="",
            stderr="error",
            duration_ms=100,
            command="test",
        )

        assert executor.check_result(result, raise_on_failure=False) is False

    def test_check_result_failure_raises(self) -> None:
        """Test checking failed result raises exception."""
        executor = VerificationExecutor()

        result = VerificationExecutionResult(
            task_id="TASK-001",
            success=False,
            exit_code=1,
            stdout="",
            stderr="some error",
            duration_ms=100,
            command="pytest test/",
        )

        with pytest.raises(TaskVerificationFailedError) as exc_info:
            executor.check_result(result, raise_on_failure=True)

        assert exc_info.value.task_id == "TASK-001"

    def test_check_result_timeout_raises(self) -> None:
        """Test checking timeout result raises timeout exception."""
        executor = VerificationExecutor()

        result = VerificationExecutionResult(
            task_id="TASK-001",
            success=False,
            exit_code=-1,
            stdout="",
            stderr="Command timed out after 30s",
            duration_ms=30000,
            command="sleep 60",
        )

        with pytest.raises(TaskTimeoutError) as exc_info:
            executor.check_result(result, raise_on_failure=True)

        assert exc_info.value.task_id == "TASK-001"


class TestGetSummary:
    """Tests for get_summary method."""

    def test_get_summary_empty(self) -> None:
        """Test summary with no results."""
        executor = VerificationExecutor()

        summary = executor.get_summary()

        assert summary["total"] == 0
        assert summary["passed"] == 0
        assert summary["failed"] == 0
        assert summary["pass_rate"] == 0

    def test_get_summary_mixed(self, tmp_path: Path) -> None:
        """Test summary with mixed results."""
        executor = VerificationExecutor()

        executor.verify("echo success", "TASK-001", cwd=tmp_path)
        executor.verify("echo another", "TASK-002", cwd=tmp_path)
        executor.verify("python -c 'exit(1)'", "TASK-003", cwd=tmp_path)

        summary = executor.get_summary()

        assert summary["total"] == 3
        assert summary["passed"] == 2
        assert summary["failed"] == 1
        assert summary["pass_rate"] == pytest.approx(66.67, rel=0.1)


class TestWithEnvironment:
    """Tests for verification with environment variables."""

    def test_verify_with_env(self, tmp_path: Path) -> None:
        """Test verification with custom environment."""
        executor = VerificationExecutor()

        # Create a script that reads env var (avoid semicolons in command)
        script = tmp_path / "test_env.py"
        script.write_text('import os\nprint(os.environ.get("ZERG_TEST_VAR", ""))')

        result = executor.verify(
            f"python {script}",
            "TASK-001",
            env={"ZERG_TEST_VAR": "hello"},
            cwd=tmp_path,
        )

        assert result.success is True
        assert "hello" in result.stdout
