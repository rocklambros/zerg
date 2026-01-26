"""Tests for ZERG v2 Worker Runner with TDD Protocol."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestTDDResult:
    """Tests for TDDResult dataclass."""

    def test_tdd_result_creation(self):
        """Test TDDResult can be created."""
        from worker_runner import TDDResult

        result = TDDResult(
            test_written=True,
            test_failed_initially=True,
            implementation_written=True,
            test_passed_finally=True,
            refactored=False,
        )
        assert result.test_written is True
        assert result.test_passed_finally is True

    def test_tdd_result_is_complete(self):
        """Test TDDResult.is_complete property."""
        from worker_runner import TDDResult

        complete = TDDResult(
            test_written=True,
            test_failed_initially=True,
            implementation_written=True,
            test_passed_finally=True,
            refactored=False,
        )
        assert complete.is_complete is True

        incomplete = TDDResult(
            test_written=True,
            test_failed_initially=False,  # Test didn't fail - bad TDD
            implementation_written=True,
            test_passed_finally=True,
            refactored=False,
        )
        assert incomplete.is_complete is False


class TestVerificationResult:
    """Tests for VerificationResult dataclass."""

    def test_verification_result_creation(self):
        """Test VerificationResult can be created."""
        from worker_runner import VerificationResult

        result = VerificationResult(
            command="pytest tests/",
            exit_code=0,
            output="All tests passed",
            passed=True,
        )
        assert result.passed is True
        assert result.exit_code == 0

    def test_verification_result_failed(self):
        """Test VerificationResult for failed verification."""
        from worker_runner import VerificationResult

        result = VerificationResult(
            command="pytest tests/",
            exit_code=1,
            output="1 failed",
            passed=False,
        )
        assert result.passed is False


class TestTaskSpec:
    """Tests for TaskSpec dataclass."""

    def test_task_spec_creation(self):
        """Test TaskSpec can be created."""
        from worker_runner import TaskSpec

        spec = TaskSpec(
            task_id="TASK-001",
            title="Implement feature",
            files_create=["src/feature.py"],
            files_modify=[],
            verification_command="pytest tests/",
        )
        assert spec.task_id == "TASK-001"
        assert spec.verification_command == "pytest tests/"


class TestTDDEnforcer:
    """Tests for TDD enforcement."""

    def test_tdd_enforcer_creation(self):
        """Test TDDEnforcer can be created."""
        from worker_runner import TaskSpec, TDDEnforcer

        spec = TaskSpec(
            task_id="TASK-001",
            title="Test",
            files_create=[],
            files_modify=[],
            verification_command="echo ok",
        )
        enforcer = TDDEnforcer(spec)
        assert enforcer.spec == spec

    def test_tdd_step_test_written(self):
        """Test recording test written step."""
        from worker_runner import TaskSpec, TDDEnforcer

        spec = TaskSpec(
            task_id="TASK-001",
            title="Test",
            files_create=[],
            files_modify=[],
            verification_command="echo ok",
        )
        enforcer = TDDEnforcer(spec)
        enforcer.record_test_written()
        assert enforcer.result.test_written is True

    def test_tdd_step_test_failed(self):
        """Test recording initial test failure step."""
        from worker_runner import TaskSpec, TDDEnforcer

        spec = TaskSpec(
            task_id="TASK-001",
            title="Test",
            files_create=[],
            files_modify=[],
            verification_command="echo ok",
        )
        enforcer = TDDEnforcer(spec)
        enforcer.record_test_written()
        enforcer.record_test_failed_initially()
        assert enforcer.result.test_failed_initially is True

    def test_tdd_complete_flow(self):
        """Test complete TDD flow."""
        from worker_runner import TaskSpec, TDDEnforcer

        spec = TaskSpec(
            task_id="TASK-001",
            title="Test",
            files_create=[],
            files_modify=[],
            verification_command="echo ok",
        )
        enforcer = TDDEnforcer(spec)
        enforcer.record_test_written()
        enforcer.record_test_failed_initially()
        enforcer.record_implementation_written()
        enforcer.record_test_passed()

        assert enforcer.result.is_complete is True


class TestVerificationEnforcer:
    """Tests for verification enforcement."""

    def test_verification_enforcer_creation(self):
        """Test VerificationEnforcer can be created."""
        from worker_runner import TaskSpec, VerificationEnforcer

        spec = TaskSpec(
            task_id="TASK-001",
            title="Test",
            files_create=[],
            files_modify=[],
            verification_command="echo ok",
        )
        enforcer = VerificationEnforcer(spec)
        assert enforcer.spec == spec

    @patch("subprocess.run")
    def test_run_verification(self, mock_run):
        """Test running verification command."""
        from worker_runner import TaskSpec, VerificationEnforcer

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="All tests passed",
            stderr="",
        )

        spec = TaskSpec(
            task_id="TASK-001",
            title="Test",
            files_create=[],
            files_modify=[],
            verification_command="pytest tests/",
        )
        enforcer = VerificationEnforcer(spec)
        result = enforcer.run()

        assert result.passed is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_verification_timeout(self, mock_run):
        """Test verification timeout handling."""
        import subprocess

        from worker_runner import TaskSpec, VerificationEnforcer

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=60)

        spec = TaskSpec(
            task_id="TASK-001",
            title="Test",
            files_create=[],
            files_modify=[],
            verification_command="slow_test",
            verification_timeout=60,
        )
        enforcer = VerificationEnforcer(spec)
        result = enforcer.run()

        assert result.passed is False
        assert "timeout" in result.output.lower()


class TestForbiddenPhrases:
    """Tests for forbidden phrase detection."""

    def test_detect_forbidden_phrases(self):
        """Test detecting forbidden phrases."""
        from worker_runner import check_forbidden_phrases

        forbidden = [
            "should work now",
            "probably passes",
            "seems correct",
            "looks good",
        ]

        for phrase in forbidden:
            result = check_forbidden_phrases(phrase)
            assert result is not None, f"Should detect: {phrase}"

    def test_allow_valid_phrases(self):
        """Test allowing valid phrases."""
        from worker_runner import check_forbidden_phrases

        valid = [
            "tests pass",
            "verification successful",
            "all checks complete",
        ]

        for phrase in valid:
            result = check_forbidden_phrases(phrase)
            assert result is None, f"Should allow: {phrase}"


class TestWorkerRunner:
    """Tests for WorkerRunner class."""

    def test_worker_runner_creation(self):
        """Test WorkerRunner can be created."""
        from worker_runner import TaskSpec, WorkerRunner

        spec = TaskSpec(
            task_id="TASK-001",
            title="Test",
            files_create=[],
            files_modify=[],
            verification_command="echo ok",
        )
        runner = WorkerRunner(spec)
        assert runner.spec == spec

    def test_worker_runner_has_tdd_enforcer(self):
        """Test WorkerRunner has TDD enforcer."""
        from worker_runner import TaskSpec, WorkerRunner

        spec = TaskSpec(
            task_id="TASK-001",
            title="Test",
            files_create=[],
            files_modify=[],
            verification_command="echo ok",
        )
        runner = WorkerRunner(spec)
        assert runner.tdd_enforcer is not None

    def test_worker_runner_has_verification_enforcer(self):
        """Test WorkerRunner has verification enforcer."""
        from worker_runner import TaskSpec, WorkerRunner

        spec = TaskSpec(
            task_id="TASK-001",
            title="Test",
            files_create=[],
            files_modify=[],
            verification_command="echo ok",
        )
        runner = WorkerRunner(spec)
        assert runner.verification_enforcer is not None


class TestSelfReviewChecklist:
    """Tests for self-review checklist."""

    def test_checklist_items(self):
        """Test checklist has required items."""
        from worker_runner import get_self_review_checklist

        checklist = get_self_review_checklist()
        assert len(checklist) > 0

        # Should have key checks
        keywords = ["test", "verification", "lint", "commit"]
        for keyword in keywords:
            found = any(keyword.lower() in item.lower() for item in checklist)
            assert found, f"Checklist should include {keyword}"


class TestClaudeInvocationResult:
    """Tests for ClaudeInvocationResult dataclass."""

    def test_claude_result_creation(self):
        """Test ClaudeInvocationResult can be created."""
        from worker_runner import ClaudeInvocationResult

        result = ClaudeInvocationResult(
            success=True,
            exit_code=0,
            stdout="Output",
            stderr="",
            duration_ms=1000,
            task_id="TASK-001",
        )
        assert result.success is True
        assert result.exit_code == 0

    def test_claude_result_to_dict(self):
        """Test ClaudeInvocationResult.to_dict()."""
        from worker_runner import ClaudeInvocationResult

        result = ClaudeInvocationResult(
            success=True,
            exit_code=0,
            stdout="Output",
            stderr="",
            duration_ms=1000,
            task_id="TASK-001",
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["task_id"] == "TASK-001"
        assert "timestamp" in d

    def test_claude_result_truncates_long_output(self):
        """Test that long output is truncated."""
        from worker_runner import ClaudeInvocationResult

        long_output = "x" * 5000
        result = ClaudeInvocationResult(
            success=True,
            exit_code=0,
            stdout=long_output,
            stderr=long_output,
            duration_ms=1000,
            task_id="TASK-001",
        )
        d = result.to_dict()
        assert len(d["stdout"]) == 2000
        assert len(d["stderr"]) == 2000


class TestWorkerRunResult:
    """Tests for WorkerRunResult dataclass."""

    def test_worker_run_result_creation(self):
        """Test WorkerRunResult can be created."""
        from worker_runner import WorkerRunResult

        result = WorkerRunResult(
            task_id="TASK-001",
            success=True,
            tdd_complete=True,
            verification_passed=True,
        )
        assert result.success is True
        assert result.task_id == "TASK-001"

    def test_worker_run_result_to_dict(self):
        """Test WorkerRunResult.to_dict()."""
        from worker_runner import WorkerRunResult

        result = WorkerRunResult(
            task_id="TASK-001",
            success=True,
            tdd_complete=True,
            verification_passed=True,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["tdd_complete"] is True
        assert d["verification_passed"] is True
        assert "started_at" in d


class TestWorkerRunnerRun:
    """Tests for WorkerRunner.run() method (L4-001)."""

    @patch("worker_runner.subprocess.run")
    def test_run_success(self, mock_subprocess):
        """Test successful task execution."""
        from worker_runner import TaskSpec, WorkerRunner

        # Mock Claude Code success
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="Done",
            stderr="",
        )

        spec = TaskSpec(
            task_id="TASK-001",
            title="Test Task",
            files_create=["new.py"],
            files_modify=[],
            verification_command="echo ok",
        )
        runner = WorkerRunner(spec)
        result = runner.run()

        assert result.success is True
        assert result.verification_passed is True
        assert result.tdd_complete is True
        assert result.claude_result is not None
        assert result.completed_at is not None

    @patch("worker_runner.subprocess.run")
    def test_run_claude_failure(self, mock_subprocess):
        """Test task execution when Claude Code fails."""
        from worker_runner import TaskSpec, WorkerRunner

        # Mock Claude Code failure
        mock_subprocess.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error",
        )

        spec = TaskSpec(
            task_id="TASK-001",
            title="Test Task",
            files_create=[],
            files_modify=[],
            verification_command="echo ok",
        )
        runner = WorkerRunner(spec)
        result = runner.run()

        assert result.success is False
        assert result.error is not None
        assert "Claude Code failed" in result.error

    @patch("worker_runner.subprocess.run")
    def test_run_verification_failure(self, mock_subprocess):
        """Test task execution when verification fails."""
        from worker_runner import TaskSpec, WorkerRunner

        # First call: Claude Code success, Second call: verification fail
        mock_subprocess.side_effect = [
            MagicMock(returncode=0, stdout="Done", stderr=""),  # Claude
            MagicMock(returncode=1, stdout="", stderr="Test failed"),  # Verify
        ]

        spec = TaskSpec(
            task_id="TASK-001",
            title="Test Task",
            files_create=[],
            files_modify=[],
            verification_command="pytest",
        )
        runner = WorkerRunner(spec)
        result = runner.run()

        assert result.success is False
        assert result.verification_passed is False

    def test_build_prompt(self):
        """Test prompt building from task spec."""
        from worker_runner import TaskSpec, WorkerRunner

        spec = TaskSpec(
            task_id="TASK-001",
            title="Implement Feature",
            files_create=["src/feature.py"],
            files_modify=["src/main.py"],
            verification_command="pytest tests/",
            acceptance_criteria=["Must pass tests", "Must be documented"],
        )
        runner = WorkerRunner(spec)
        prompt = runner._build_prompt()

        assert "# Task: Implement Feature" in prompt
        assert "## Files" in prompt
        assert "Create: src/feature.py" in prompt
        assert "Modify: src/main.py" in prompt
        assert "## Verification" in prompt
        assert "pytest tests/" in prompt
        assert "## Acceptance Criteria" in prompt
        assert "Must pass tests" in prompt

    @patch("worker_runner.subprocess.run")
    def test_verify_with_retry_success_first_try(self, mock_subprocess):
        """Test verification with retry succeeds first try."""
        from worker_runner import TaskSpec, WorkerRunner

        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="Pass",
            stderr="",
        )

        spec = TaskSpec(
            task_id="TASK-001",
            title="Test",
            files_create=[],
            files_modify=[],
            verification_command="echo ok",
        )
        runner = WorkerRunner(spec)
        result = runner.verify_with_retry(max_retries=2)

        assert result.passed is True
        assert mock_subprocess.call_count == 1

    @patch("worker_runner.subprocess.run")
    def test_verify_with_retry_success_on_retry(self, mock_subprocess):
        """Test verification with retry succeeds on second try."""
        from worker_runner import TaskSpec, WorkerRunner

        # First call fails, second succeeds
        mock_subprocess.side_effect = [
            MagicMock(returncode=1, stdout="", stderr="Fail"),
            MagicMock(returncode=0, stdout="Pass", stderr=""),
        ]

        spec = TaskSpec(
            task_id="TASK-001",
            title="Test",
            files_create=[],
            files_modify=[],
            verification_command="pytest",
        )
        runner = WorkerRunner(spec)
        result = runner.verify_with_retry(max_retries=2)

        assert result.passed is True
        assert mock_subprocess.call_count == 2
