"""Tests for zerg.gates module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.config import QualityGate, ZergConfig
from zerg.constants import GateResult
from zerg.exceptions import GateFailure, GateTimeoutError
from zerg.gates import GateRunner
from zerg.types import GateRunResult


class TestGateRunner:
    """Tests for GateRunner class."""

    def test_create_runner(self, sample_config: ZergConfig) -> None:
        """Test creating a GateRunner."""
        runner = GateRunner(sample_config)

        assert runner is not None
        assert runner.config == sample_config

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
        gate = QualityGate(name="test", command="exit 1", required=True)

        result = runner.run_gate(gate, cwd=tmp_path)

        assert result.result == GateResult.FAIL
        assert result.exit_code == 1

    @patch("subprocess.run")
    def test_run_gate_timeout(
        self,
        mock_run: MagicMock,
        sample_config: ZergConfig,
        tmp_path: Path,
    ) -> None:
        """Test running a gate that times out."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 5)

        runner = GateRunner(sample_config)
        gate = QualityGate(name="test", command="sleep 100", required=True, timeout=5)

        result = runner.run_gate(gate, cwd=tmp_path)

        assert result.result == GateResult.TIMEOUT

    def test_run_all_gates_success(
        self, sample_config: ZergConfig, tmp_path: Path
    ) -> None:
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

    def test_run_all_gates_stop_on_failure(
        self, sample_config: ZergConfig, tmp_path: Path
    ) -> None:
        """Test running gates stops on first failure."""
        sample_config.quality_gates = [
            QualityGate(name="fail", command="exit 1", required=True),
            QualityGate(name="skip", command="echo skip", required=True),
        ]
        runner = GateRunner(sample_config)

        all_passed, results = runner.run_all_gates(cwd=tmp_path, stop_on_failure=True)

        assert all_passed is False
        # Only first gate should have run
        assert len(results) == 1
        assert results[0].gate_name == "fail"

    def test_run_all_gates_optional_failure(
        self, sample_config: ZergConfig, tmp_path: Path
    ) -> None:
        """Test optional gate failure doesn't stop execution."""
        sample_config.quality_gates = [
            QualityGate(name="optional", command="exit 1", required=False),
            QualityGate(name="required", command="echo pass", required=True),
        ]
        runner = GateRunner(sample_config)

        all_passed, results = runner.run_all_gates(cwd=tmp_path, stop_on_failure=True)

        assert all_passed is True
        assert len(results) == 2

    def test_run_required_only(
        self, sample_config: ZergConfig, tmp_path: Path
    ) -> None:
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

    def test_run_gate_by_name(
        self, sample_config: ZergConfig, tmp_path: Path
    ) -> None:
        """Test running a gate by name."""
        sample_config.quality_gates = [
            QualityGate(name="lint", command="echo lint", required=True),
        ]
        runner = GateRunner(sample_config)

        result = runner.run_gate_by_name("lint", cwd=tmp_path)

        assert result.gate_name == "lint"
        assert result.result == GateResult.PASS

    def test_run_gate_by_name_not_found(
        self, sample_config: ZergConfig
    ) -> None:
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

        with pytest.raises(GateFailure):
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

    def test_clear_results(self, sample_config: ZergConfig, tmp_path: Path) -> None:
        """Test clearing stored results."""
        runner = GateRunner(sample_config)
        gate = QualityGate(name="test", command="echo test", required=True)

        runner.run_gate(gate, cwd=tmp_path)
        runner.clear_results()
        results = runner.get_results()

        assert len(results) == 0

    def test_get_summary(self, sample_config: ZergConfig, tmp_path: Path) -> None:
        """Test getting results summary."""
        sample_config.quality_gates = [
            QualityGate(name="pass", command="echo pass", required=True),
            QualityGate(name="fail", command="exit 1", required=False),
        ]
        runner = GateRunner(sample_config)

        runner.run_all_gates(cwd=tmp_path, stop_on_failure=False)
        summary = runner.get_summary()

        assert summary["total"] == 2
        assert summary["passed"] == 1
        assert summary["failed"] == 1
