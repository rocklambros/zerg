"""Tests for zerg.gates module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.command_executor import CommandValidationError
from zerg.config import QualityGate, ZergConfig
from zerg.constants import GateResult
from zerg.exceptions import GateFailureError, GateTimeoutError
from zerg.gates import GateRunner
from zerg.types import GateRunResult


class TestGateRunner:
    """Tests for GateRunner class."""

    def test_create_runner(self, sample_config: ZergConfig) -> None:
        """Test creating a GateRunner."""
        runner = GateRunner(sample_config)

        assert runner is not None
        assert runner.config == sample_config

    def test_create_runner_default_config(self) -> None:
        """Test creating a GateRunner with default config."""
        with patch.object(ZergConfig, "load") as mock_load:
            mock_load.return_value = ZergConfig()
            runner = GateRunner()

        assert runner is not None
        mock_load.assert_called_once()

    def test_run_gate_success(self, sample_config: ZergConfig, tmp_path: Path) -> None:
        """Test running a passing gate."""
        runner = GateRunner(sample_config)
        gate = QualityGate(name="test", command="echo success", required=True)

        result = runner.run_gate(gate, cwd=tmp_path)

        assert result.result == GateResult.PASS
        assert result.gate_name == "test"
        assert result.exit_code == 0

    def test_run_gate_failure(self, sample_config: ZergConfig, tmp_path: Path) -> None:
        """Test running a failing gate."""
        runner = GateRunner(sample_config)
        # Use 'false' command which is a real executable that returns exit code 1
        gate = QualityGate(name="test", command="false", required=True)

        result = runner.run_gate(gate, cwd=tmp_path)

        assert result.result == GateResult.FAIL
        assert result.exit_code == 1

    def test_run_gate_timeout(self, sample_config: ZergConfig, tmp_path: Path) -> None:
        """Test running a gate that times out."""
        runner = GateRunner(sample_config)
        gate = QualityGate(name="test", command="echo test", required=True, timeout=5)

        # Mock executor to return timeout result
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.exit_code = -1
        mock_result.stdout = ""
        mock_result.stderr = "Command timed out after 5s"

        with patch.object(runner, "_get_executor") as mock_get_executor:
            mock_executor = MagicMock()
            mock_executor.execute.return_value = mock_result
            mock_get_executor.return_value = mock_executor

            result = runner.run_gate(gate, cwd=tmp_path)

        assert result.result == GateResult.TIMEOUT

    def test_run_gate_command_validation_error(self, sample_config: ZergConfig, tmp_path: Path) -> None:
        """Test running a gate that fails command validation."""
        runner = GateRunner(sample_config)
        gate = QualityGate(name="test", command="echo test", required=True)

        with patch.object(runner, "_get_executor") as mock_get_executor:
            mock_executor = MagicMock()
            mock_executor.execute.side_effect = CommandValidationError("Dangerous command")
            mock_get_executor.return_value = mock_executor

            result = runner.run_gate(gate, cwd=tmp_path)

        assert result.result == GateResult.ERROR
        assert result.exit_code == -1
        assert "Command validation failed" in result.stderr

    def test_run_gate_general_exception(self, sample_config: ZergConfig, tmp_path: Path) -> None:
        """Test running a gate that throws an unexpected exception."""
        runner = GateRunner(sample_config)
        gate = QualityGate(name="test", command="echo test", required=True)

        with patch.object(runner, "_get_executor") as mock_get_executor:
            mock_executor = MagicMock()
            mock_executor.execute.side_effect = RuntimeError("Unexpected error")
            mock_get_executor.return_value = mock_executor

            result = runner.run_gate(gate, cwd=tmp_path)

        assert result.result == GateResult.ERROR
        assert result.exit_code == -1
        assert "Unexpected error" in result.stderr

    def test_run_gate_with_env(self, sample_config: ZergConfig, tmp_path: Path) -> None:
        """Test running a gate with custom environment variables."""
        runner = GateRunner(sample_config)
        gate = QualityGate(name="test", command="echo test", required=True)

        result = runner.run_gate(gate, cwd=tmp_path, env={"CUSTOM_VAR": "value"})

        assert result.result == GateResult.PASS

    def test_run_gate_default_cwd(self, sample_config: ZergConfig) -> None:
        """Test running a gate with default working directory."""
        runner = GateRunner(sample_config)
        gate = QualityGate(name="test", command="pwd", required=True)

        result = runner.run_gate(gate)

        assert result.result == GateResult.PASS

    def test_run_all_gates_success(self, sample_config: ZergConfig, tmp_path: Path) -> None:
        """Test running all gates successfully."""
        sample_config.quality_gates = [
            QualityGate(name="lint", command="echo lint", required=True),
            QualityGate(name="test", command="echo test", required=True),
        ]
        runner = GateRunner(sample_config)

        all_passed, results = runner.run_all_gates(cwd=tmp_path)

        assert all_passed is True
        assert len(results) == 2
        assert all(r.result == GateResult.PASS for r in results)

    def test_run_all_gates_stop_on_failure(self, sample_config: ZergConfig, tmp_path: Path) -> None:
        """Test running gates stops on first failure."""
        sample_config.quality_gates = [
            QualityGate(name="fail", command="false", required=True),
            QualityGate(name="skip", command="echo skip", required=True),
        ]
        runner = GateRunner(sample_config)

        all_passed, results = runner.run_all_gates(cwd=tmp_path, stop_on_failure=True)

        assert all_passed is False
        # Only first gate should have run
        assert len(results) == 1
        assert results[0].gate_name == "fail"

    def test_run_all_gates_optional_failure(self, sample_config: ZergConfig, tmp_path: Path) -> None:
        """Test optional gate failure doesn't stop execution."""
        sample_config.quality_gates = [
            QualityGate(name="optional", command="false", required=False),
            QualityGate(name="required", command="echo pass", required=True),
        ]
        runner = GateRunner(sample_config)

        all_passed, results = runner.run_all_gates(cwd=tmp_path, stop_on_failure=True)

        assert all_passed is True
        assert len(results) == 2

    def test_run_all_gates_continue_on_failure(self, sample_config: ZergConfig, tmp_path: Path) -> None:
        """Test running all gates continues on failure when stop_on_failure=False."""
        sample_config.quality_gates = [
            QualityGate(name="fail", command="false", required=True),
            QualityGate(name="pass", command="echo pass", required=True),
        ]
        runner = GateRunner(sample_config)

        all_passed, results = runner.run_all_gates(cwd=tmp_path, stop_on_failure=False)

        assert all_passed is False
        assert len(results) == 2

    def test_run_required_only(self, sample_config: ZergConfig, tmp_path: Path) -> None:
        """Test running only required gates."""
        sample_config.quality_gates = [
            QualityGate(name="required", command="echo required", required=True),
            QualityGate(name="optional", command="echo optional", required=False),
        ]
        runner = GateRunner(sample_config)

        all_passed, results = runner.run_all_gates(cwd=tmp_path, required_only=True)

        assert all_passed is True
        assert len(results) == 1
        assert results[0].gate_name == "required"

    def test_run_all_gates_no_gates(self, sample_config: ZergConfig) -> None:
        """Test running when no gates are configured."""
        sample_config.quality_gates = []
        runner = GateRunner(sample_config)

        all_passed, results = runner.run_all_gates()

        assert all_passed is True
        assert not results

    def test_run_all_gates_with_explicit_gates(self, sample_config: ZergConfig, tmp_path: Path) -> None:
        """Test running with explicitly provided gates list."""
        runner = GateRunner(sample_config)
        custom_gates = [
            QualityGate(name="custom1", command="echo custom1", required=True),
            QualityGate(name="custom2", command="echo custom2", required=True),
        ]

        all_passed, results = runner.run_all_gates(gates=custom_gates, cwd=tmp_path)

        assert all_passed is True
        assert len(results) == 2
        assert results[0].gate_name == "custom1"
        assert results[1].gate_name == "custom2"

    def test_run_gate_by_name(self, sample_config: ZergConfig, tmp_path: Path) -> None:
        """Test running a gate by name."""
        sample_config.quality_gates = [
            QualityGate(name="lint", command="echo lint", required=True),
        ]
        runner = GateRunner(sample_config)

        result = runner.run_gate_by_name("lint", cwd=tmp_path)

        assert result.gate_name == "lint"
        assert result.result == GateResult.PASS

    def test_run_gate_by_name_not_found(self, sample_config: ZergConfig) -> None:
        """Test running a gate by name that doesn't exist."""
        runner = GateRunner(sample_config)

        with pytest.raises(ValueError, match="Gate not found"):
            runner.run_gate_by_name("nonexistent")

    def test_check_result_pass(self, sample_config: ZergConfig) -> None:
        """Test check_result with passing result."""
        runner = GateRunner(sample_config)
        result = GateRunResult(
            gate_name="test",
            result=GateResult.PASS,
            command="echo test",
            exit_code=0,
            duration_ms=100,
        )

        assert runner.check_result(result) is True

    def test_check_result_skip(self, sample_config: ZergConfig) -> None:
        """Test check_result with skipped result."""
        runner = GateRunner(sample_config)
        result = GateRunResult(
            gate_name="test",
            result=GateResult.SKIP,
            command="echo test",
            exit_code=0,
            duration_ms=100,
        )

        assert runner.check_result(result) is True

    def test_check_result_failure_raises(self, sample_config: ZergConfig) -> None:
        """Test check_result raises on failure."""
        runner = GateRunner(sample_config)
        result = GateRunResult(
            gate_name="test",
            result=GateResult.FAIL,
            command="exit 1",
            exit_code=1,
            duration_ms=100,
        )

        with pytest.raises(GateFailureError):
            runner.check_result(result, raise_on_failure=True)

    def test_check_result_timeout_raises(self, sample_config: ZergConfig) -> None:
        """Test check_result raises on timeout."""
        runner = GateRunner(sample_config)
        result = GateRunResult(
            gate_name="test",
            result=GateResult.TIMEOUT,
            command="sleep 100",
            exit_code=-1,
            duration_ms=5000,
        )

        with pytest.raises(GateTimeoutError):
            runner.check_result(result, raise_on_failure=True)

    def test_check_result_error_raises(self, sample_config: ZergConfig) -> None:
        """Test check_result raises on error."""
        runner = GateRunner(sample_config)
        result = GateRunResult(
            gate_name="test",
            result=GateResult.ERROR,
            command="invalid",
            exit_code=-1,
            duration_ms=100,
        )

        with pytest.raises(GateFailureError):
            runner.check_result(result, raise_on_failure=True)

    def test_check_result_no_raise(self, sample_config: ZergConfig) -> None:
        """Test check_result without raising on failure."""
        runner = GateRunner(sample_config)
        result = GateRunResult(
            gate_name="test",
            result=GateResult.FAIL,
            command="exit 1",
            exit_code=1,
            duration_ms=100,
        )

        assert runner.check_result(result, raise_on_failure=False) is False

    def test_get_results(self, sample_config: ZergConfig, tmp_path: Path) -> None:
        """Test getting stored results."""
        runner = GateRunner(sample_config)
        gate = QualityGate(name="test", command="echo test", required=True)

        runner.run_gate(gate, cwd=tmp_path)
        results = runner.get_results()

        assert len(results) == 1

    def test_get_results_returns_copy(self, sample_config: ZergConfig, tmp_path: Path) -> None:
        """Test get_results returns a copy."""
        runner = GateRunner(sample_config)
        gate = QualityGate(name="test", command="echo test", required=True)

        runner.run_gate(gate, cwd=tmp_path)
        results = runner.get_results()
        results.clear()

        # Original should not be modified
        assert len(runner.get_results()) == 1

    def test_clear_results(self, sample_config: ZergConfig, tmp_path: Path) -> None:
        """Test clearing stored results."""
        runner = GateRunner(sample_config)
        gate = QualityGate(name="test", command="echo test", required=True)

        runner.run_gate(gate, cwd=tmp_path)
        runner.clear_results()
        results = runner.get_results()

        assert not results

    def test_get_summary(self, sample_config: ZergConfig, tmp_path: Path) -> None:
        """Test getting results summary."""
        sample_config.quality_gates = [
            QualityGate(name="pass", command="echo pass", required=True),
            QualityGate(name="fail", command="false", required=False),
        ]
        runner = GateRunner(sample_config)

        runner.run_all_gates(cwd=tmp_path, stop_on_failure=False)
        summary = runner.get_summary()

        assert summary["total"] == 2
        assert summary["passed"] == 1
        assert summary["failed"] == 1

    def test_get_summary_all_results_types(self, sample_config: ZergConfig) -> None:
        """Test get_summary counts all result types."""
        runner = GateRunner(sample_config)

        # Manually add results of each type
        runner._results = [
            GateRunResult(
                gate_name="pass",
                result=GateResult.PASS,
                command="echo",
                exit_code=0,
            ),
            GateRunResult(
                gate_name="fail",
                result=GateResult.FAIL,
                command="false",
                exit_code=1,
            ),
            GateRunResult(
                gate_name="timeout",
                result=GateResult.TIMEOUT,
                command="sleep",
                exit_code=-1,
            ),
            GateRunResult(
                gate_name="error",
                result=GateResult.ERROR,
                command="invalid",
                exit_code=-1,
            ),
            GateRunResult(
                gate_name="skip",
                result=GateResult.SKIP,
                command="skip",
                exit_code=0,
            ),
        ]

        summary = runner.get_summary()

        assert summary["total"] == 5
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["timeout"] == 1
        assert summary["error"] == 1
        assert summary["skipped"] == 1

    def test_get_summary_empty(self, sample_config: ZergConfig) -> None:
        """Test get_summary with no results."""
        runner = GateRunner(sample_config)

        summary = runner.get_summary()

        assert summary["total"] == 0
        assert summary["passed"] == 0
        assert summary["failed"] == 0
        assert summary["timeout"] == 0
        assert summary["error"] == 0
        assert summary["skipped"] == 0

    def test_run_gate_stores_result(self, sample_config: ZergConfig, tmp_path: Path) -> None:
        """Test that run_gate stores result in internal list."""
        runner = GateRunner(sample_config)
        gate = QualityGate(name="test", command="echo test", required=True)

        assert len(runner._results) == 0
        runner.run_gate(gate, cwd=tmp_path)
        assert len(runner._results) == 1

    def test_run_gate_records_duration(self, sample_config: ZergConfig, tmp_path: Path) -> None:
        """Test that run_gate records execution duration."""
        runner = GateRunner(sample_config)
        gate = QualityGate(name="test", command="echo test", required=True)

        result = runner.run_gate(gate, cwd=tmp_path)

        assert result.duration_ms >= 0

    def test_run_gate_uses_gate_timeout(self, sample_config: ZergConfig, tmp_path: Path) -> None:
        """Test that run_gate uses the timeout from gate config."""
        runner = GateRunner(sample_config)
        gate = QualityGate(name="test", command="echo test", required=True, timeout=60)

        with patch.object(runner, "_get_executor") as mock_get_executor:
            mock_executor = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.exit_code = 0
            mock_result.stdout = "test"
            mock_result.stderr = ""
            mock_executor.execute.return_value = mock_result
            mock_get_executor.return_value = mock_executor

            runner.run_gate(gate, cwd=tmp_path)

            mock_get_executor.assert_called_with(tmp_path, timeout=60)


class TestGateRunnerIntegration:
    """Integration tests for GateRunner."""

    def test_full_workflow(self, sample_config: ZergConfig, tmp_path: Path) -> None:
        """Test a complete gate running workflow."""
        sample_config.quality_gates = [
            QualityGate(name="lint", command="echo linting", required=True, timeout=30),
            QualityGate(name="test", command="echo testing", required=True, timeout=60),
            QualityGate(name="coverage", command="echo coverage", required=False),
        ]

        runner = GateRunner(sample_config)

        # Run all gates
        all_passed, results = runner.run_all_gates(cwd=tmp_path)

        assert all_passed is True
        assert len(results) == 3

        # Check summary
        summary = runner.get_summary()
        assert summary["total"] == 3
        assert summary["passed"] == 3

        # Get all results
        all_results = runner.get_results()
        assert len(all_results) == 3

        # Clear and verify
        runner.clear_results()
        assert len(runner.get_results()) == 0
        assert runner.get_summary()["total"] == 0


class TestGateResultTracking:
    """Tests for gate result tracking behavior."""

    def test_results_accumulate(self, sample_config: ZergConfig, tmp_path: Path) -> None:
        """Test that results accumulate across multiple gate runs."""
        runner = GateRunner(sample_config)
        gate = QualityGate(name="test", command="echo test", required=True)

        runner.run_gate(gate, cwd=tmp_path)
        runner.run_gate(gate, cwd=tmp_path)
        runner.run_gate(gate, cwd=tmp_path)

        assert len(runner.get_results()) == 3

    def test_results_cleared_properly(self, sample_config: ZergConfig, tmp_path: Path) -> None:
        """Test that clear_results properly clears all results."""
        runner = GateRunner(sample_config)
        gate = QualityGate(name="test", command="echo test", required=True)

        runner.run_gate(gate, cwd=tmp_path)
        runner.run_gate(gate, cwd=tmp_path)
        assert len(runner.get_results()) == 2

        runner.clear_results()
        assert len(runner.get_results()) == 0

        runner.run_gate(gate, cwd=tmp_path)
        assert len(runner.get_results()) == 1
