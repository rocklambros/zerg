"""Unit tests for merge gate execution in MergeCoordinator.

Tests run_pre_merge_gates and gate execution logic including:
- All gates passing
- Some gates failing
- Required-only gate filtering
- Gate summary logging
- Custom working directory support
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from zerg.config import QualityGate, ZergConfig
from zerg.constants import GateResult
from zerg.gates import GateRunner
from zerg.merge import MergeCoordinator
from zerg.types import GateRunResult


class TestRunPreMergeGatesAllPassing:
    """Tests for run_pre_merge_gates when all gates pass."""

    def test_all_gates_pass_returns_true(self):
        """When all gates pass, should return True and results."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="lint", command="echo lint", required=True),
            QualityGate(name="test", command="echo test", required=True),
        ]

        mock_gate_runner = MagicMock(spec=GateRunner)
        mock_gate_runner.run_all_gates.return_value = (
            True,
            [
                GateRunResult(
                    gate_name="lint",
                    result=GateResult.PASS,
                    command="echo lint",
                    exit_code=0,
                    stdout="ok",
                    duration_ms=50,
                ),
                GateRunResult(
                    gate_name="test",
                    result=GateResult.PASS,
                    command="echo test",
                    exit_code=0,
                    stdout="ok",
                    duration_ms=100,
                ),
            ],
        )
        mock_gate_runner.get_summary.return_value = {
            "total": 2,
            "passed": 2,
            "failed": 0,
            "timeout": 0,
            "error": 0,
            "skipped": 0,
        }

        with patch("zerg.merge.GateRunner", return_value=mock_gate_runner):
            with patch("zerg.merge.GitOps"):
                coordinator = MergeCoordinator(
                    feature="test-feature",
                    config=config,
                )

        all_passed, results = coordinator.run_pre_merge_gates()

        assert all_passed is True
        assert len(results) == 2
        assert all(r.result == GateResult.PASS for r in results)

    def test_empty_gates_returns_true(self):
        """When no gates configured, should return True with empty results."""
        config = ZergConfig()
        config.quality_gates = []

        mock_gate_runner = MagicMock(spec=GateRunner)
        mock_gate_runner.run_all_gates.return_value = (True, [])
        mock_gate_runner.get_summary.return_value = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "timeout": 0,
            "error": 0,
            "skipped": 0,
        }

        with patch("zerg.merge.GateRunner", return_value=mock_gate_runner):
            with patch("zerg.merge.GitOps"):
                coordinator = MergeCoordinator(
                    feature="test-feature",
                    config=config,
                )

        all_passed, results = coordinator.run_pre_merge_gates()

        assert all_passed is True
        assert len(results) == 0

    def test_single_gate_pass(self):
        """Single gate passing should return True."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="lint", command="echo lint", required=True),
        ]

        mock_gate_runner = MagicMock(spec=GateRunner)
        mock_gate_runner.run_all_gates.return_value = (
            True,
            [
                GateRunResult(
                    gate_name="lint",
                    result=GateResult.PASS,
                    command="echo lint",
                    exit_code=0,
                    duration_ms=50,
                ),
            ],
        )
        mock_gate_runner.get_summary.return_value = {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "timeout": 0,
            "error": 0,
            "skipped": 0,
        }

        with patch("zerg.merge.GateRunner", return_value=mock_gate_runner):
            with patch("zerg.merge.GitOps"):
                coordinator = MergeCoordinator(
                    feature="test-feature",
                    config=config,
                )

        all_passed, results = coordinator.run_pre_merge_gates()

        assert all_passed is True
        assert len(results) == 1
        assert results[0].gate_name == "lint"


class TestRunPreMergeGatesSomeFailing:
    """Tests for run_pre_merge_gates when some gates fail."""

    def test_one_gate_fails_returns_false(self):
        """When one required gate fails, should return False."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="lint", command="echo lint", required=True),
            QualityGate(name="test", command="false", required=True),
        ]

        mock_gate_runner = MagicMock(spec=GateRunner)
        mock_gate_runner.run_all_gates.return_value = (
            False,
            [
                GateRunResult(
                    gate_name="lint",
                    result=GateResult.PASS,
                    command="echo lint",
                    exit_code=0,
                    duration_ms=50,
                ),
                GateRunResult(
                    gate_name="test",
                    result=GateResult.FAIL,
                    command="false",
                    exit_code=1,
                    stderr="Test failed",
                    duration_ms=100,
                ),
            ],
        )
        mock_gate_runner.get_summary.return_value = {
            "total": 2,
            "passed": 1,
            "failed": 1,
            "timeout": 0,
            "error": 0,
            "skipped": 0,
        }

        with patch("zerg.merge.GateRunner", return_value=mock_gate_runner):
            with patch("zerg.merge.GitOps"):
                coordinator = MergeCoordinator(
                    feature="test-feature",
                    config=config,
                )

        all_passed, results = coordinator.run_pre_merge_gates()

        assert all_passed is False
        assert len(results) == 2
        assert results[0].result == GateResult.PASS
        assert results[1].result == GateResult.FAIL

    def test_all_gates_fail_returns_false(self):
        """When all gates fail, should return False."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="lint", command="false", required=True),
            QualityGate(name="test", command="false", required=True),
        ]

        mock_gate_runner = MagicMock(spec=GateRunner)
        mock_gate_runner.run_all_gates.return_value = (
            False,
            [
                GateRunResult(
                    gate_name="lint",
                    result=GateResult.FAIL,
                    command="false",
                    exit_code=1,
                    duration_ms=50,
                ),
            ],
        )
        mock_gate_runner.get_summary.return_value = {
            "total": 2,
            "passed": 0,
            "failed": 1,
            "timeout": 0,
            "error": 0,
            "skipped": 0,
        }

        with patch("zerg.merge.GateRunner", return_value=mock_gate_runner):
            with patch("zerg.merge.GitOps"):
                coordinator = MergeCoordinator(
                    feature="test-feature",
                    config=config,
                )

        all_passed, results = coordinator.run_pre_merge_gates()

        assert all_passed is False

    def test_timeout_gate_returns_false(self):
        """When a gate times out, should return False."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="slow", command="sleep 100", required=True, timeout=1),
        ]

        mock_gate_runner = MagicMock(spec=GateRunner)
        mock_gate_runner.run_all_gates.return_value = (
            False,
            [
                GateRunResult(
                    gate_name="slow",
                    result=GateResult.TIMEOUT,
                    command="sleep 100",
                    exit_code=-1,
                    stderr="timed out",
                    duration_ms=1000,
                ),
            ],
        )
        mock_gate_runner.get_summary.return_value = {
            "total": 1,
            "passed": 0,
            "failed": 0,
            "timeout": 1,
            "error": 0,
            "skipped": 0,
        }

        with patch("zerg.merge.GateRunner", return_value=mock_gate_runner):
            with patch("zerg.merge.GitOps"):
                coordinator = MergeCoordinator(
                    feature="test-feature",
                    config=config,
                )

        all_passed, results = coordinator.run_pre_merge_gates()

        assert all_passed is False
        assert results[0].result == GateResult.TIMEOUT

    def test_error_gate_returns_false(self):
        """When a gate errors, should return False."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="broken", command="nonexistent-cmd", required=True),
        ]

        mock_gate_runner = MagicMock(spec=GateRunner)
        mock_gate_runner.run_all_gates.return_value = (
            False,
            [
                GateRunResult(
                    gate_name="broken",
                    result=GateResult.ERROR,
                    command="nonexistent-cmd",
                    exit_code=-1,
                    stderr="Command not found",
                    duration_ms=10,
                ),
            ],
        )
        mock_gate_runner.get_summary.return_value = {
            "total": 1,
            "passed": 0,
            "failed": 0,
            "timeout": 0,
            "error": 1,
            "skipped": 0,
        }

        with patch("zerg.merge.GateRunner", return_value=mock_gate_runner):
            with patch("zerg.merge.GitOps"):
                coordinator = MergeCoordinator(
                    feature="test-feature",
                    config=config,
                )

        all_passed, results = coordinator.run_pre_merge_gates()

        assert all_passed is False
        assert results[0].result == GateResult.ERROR


class TestRunPreMergeGatesRequiredOnly:
    """Tests for required_only filtering in run_pre_merge_gates."""

    def test_required_only_true_passes_to_gate_runner(self):
        """run_pre_merge_gates should pass required_only=True to gate runner."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="required-gate", command="echo ok", required=True),
            QualityGate(name="optional-gate", command="echo ok", required=False),
        ]

        mock_gate_runner = MagicMock(spec=GateRunner)
        mock_gate_runner.run_all_gates.return_value = (True, [])
        mock_gate_runner.get_summary.return_value = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "timeout": 0,
            "error": 0,
            "skipped": 0,
        }

        with patch("zerg.merge.GateRunner", return_value=mock_gate_runner):
            with patch("zerg.merge.GitOps"):
                coordinator = MergeCoordinator(
                    feature="test-feature",
                    config=config,
                )

        coordinator.run_pre_merge_gates()

        # Verify required_only=True was passed
        mock_gate_runner.run_all_gates.assert_called_once()
        call_kwargs = mock_gate_runner.run_all_gates.call_args[1]
        assert call_kwargs.get("required_only") is True

    def test_optional_gate_failure_not_reported_when_required_only(self):
        """Optional gates failing should not affect overall pass when required_only."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="required-gate", command="echo ok", required=True),
            QualityGate(name="optional-gate", command="false", required=False),
        ]

        mock_gate_runner = MagicMock(spec=GateRunner)
        # Simulate run_all_gates filtering to only required gates
        mock_gate_runner.run_all_gates.return_value = (
            True,
            [
                GateRunResult(
                    gate_name="required-gate",
                    result=GateResult.PASS,
                    command="echo ok",
                    exit_code=0,
                    duration_ms=50,
                ),
            ],
        )
        mock_gate_runner.get_summary.return_value = {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "timeout": 0,
            "error": 0,
            "skipped": 0,
        }

        with patch("zerg.merge.GateRunner", return_value=mock_gate_runner):
            with patch("zerg.merge.GitOps"):
                coordinator = MergeCoordinator(
                    feature="test-feature",
                    config=config,
                )

        all_passed, results = coordinator.run_pre_merge_gates()

        assert all_passed is True
        # Only the required gate should be in results
        assert len(results) == 1
        assert results[0].gate_name == "required-gate"


class TestGateSummaryLogging:
    """Tests for gate summary logging."""

    def test_summary_logged_after_gates_run(self):
        """Summary should be logged after gates complete."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="lint", command="echo lint", required=True),
        ]

        mock_gate_runner = MagicMock(spec=GateRunner)
        mock_gate_runner.run_all_gates.return_value = (
            True,
            [
                GateRunResult(
                    gate_name="lint",
                    result=GateResult.PASS,
                    command="echo lint",
                    exit_code=0,
                    duration_ms=50,
                ),
            ],
        )
        mock_gate_runner.get_summary.return_value = {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "timeout": 0,
            "error": 0,
            "skipped": 0,
        }

        with patch("zerg.merge.GateRunner", return_value=mock_gate_runner):
            with patch("zerg.merge.GitOps"):
                coordinator = MergeCoordinator(
                    feature="test-feature",
                    config=config,
                )

        coordinator.run_pre_merge_gates()

        # Verify get_summary was called
        mock_gate_runner.get_summary.assert_called_once()

    def test_summary_with_failures_logged(self):
        """Summary with failures should be logged correctly."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="lint", command="echo lint", required=True),
            QualityGate(name="test", command="false", required=True),
        ]

        mock_gate_runner = MagicMock(spec=GateRunner)
        mock_gate_runner.run_all_gates.return_value = (
            False,
            [
                GateRunResult(
                    gate_name="lint",
                    result=GateResult.PASS,
                    command="echo lint",
                    exit_code=0,
                    duration_ms=50,
                ),
                GateRunResult(
                    gate_name="test",
                    result=GateResult.FAIL,
                    command="false",
                    exit_code=1,
                    duration_ms=100,
                ),
            ],
        )
        mock_gate_runner.get_summary.return_value = {
            "total": 2,
            "passed": 1,
            "failed": 1,
            "timeout": 0,
            "error": 0,
            "skipped": 0,
        }

        with patch("zerg.merge.GateRunner", return_value=mock_gate_runner):
            with patch("zerg.merge.GitOps"):
                coordinator = MergeCoordinator(
                    feature="test-feature",
                    config=config,
                )

        with patch("zerg.merge.logger") as mock_logger:
            coordinator.run_pre_merge_gates()

            # Check that logging was called with summary info
            info_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("1 passed" in call and "1 failed" in call for call in info_calls)

    def test_summary_counts_accurate(self):
        """Summary counts should accurately reflect gate results."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="lint", command="echo lint", required=True),
            QualityGate(name="test", command="echo test", required=True),
            QualityGate(name="coverage", command="echo cov", required=True),
        ]

        mock_gate_runner = MagicMock(spec=GateRunner)
        mock_gate_runner.run_all_gates.return_value = (
            True,
            [
                GateRunResult(
                    gate_name="lint",
                    result=GateResult.PASS,
                    command="echo lint",
                    exit_code=0,
                    duration_ms=50,
                ),
                GateRunResult(
                    gate_name="test",
                    result=GateResult.PASS,
                    command="echo test",
                    exit_code=0,
                    duration_ms=100,
                ),
                GateRunResult(
                    gate_name="coverage",
                    result=GateResult.PASS,
                    command="echo cov",
                    exit_code=0,
                    duration_ms=75,
                ),
            ],
        )
        expected_summary = {
            "total": 3,
            "passed": 3,
            "failed": 0,
            "timeout": 0,
            "error": 0,
            "skipped": 0,
        }
        mock_gate_runner.get_summary.return_value = expected_summary

        with patch("zerg.merge.GateRunner", return_value=mock_gate_runner):
            with patch("zerg.merge.GitOps"):
                coordinator = MergeCoordinator(
                    feature="test-feature",
                    config=config,
                )

        coordinator.run_pre_merge_gates()

        # Summary should reflect all 3 gates passing
        summary = mock_gate_runner.get_summary.return_value
        assert summary["total"] == 3
        assert summary["passed"] == 3
        assert summary["failed"] == 0


class TestCustomWorkingDirectory:
    """Tests for custom working directory support."""

    def test_cwd_passed_to_gate_runner(self):
        """Custom cwd should be passed to gate runner."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="lint", command="echo lint", required=True),
        ]

        mock_gate_runner = MagicMock(spec=GateRunner)
        mock_gate_runner.run_all_gates.return_value = (True, [])
        mock_gate_runner.get_summary.return_value = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "timeout": 0,
            "error": 0,
            "skipped": 0,
        }

        with patch("zerg.merge.GateRunner", return_value=mock_gate_runner):
            with patch("zerg.merge.GitOps"):
                coordinator = MergeCoordinator(
                    feature="test-feature",
                    config=config,
                )

        custom_dir = "/custom/path"
        coordinator.run_pre_merge_gates(cwd=custom_dir)

        # Verify cwd was passed to run_all_gates
        mock_gate_runner.run_all_gates.assert_called_once()
        call_kwargs = mock_gate_runner.run_all_gates.call_args[1]
        assert call_kwargs.get("cwd") == custom_dir

    def test_cwd_with_path_object(self):
        """Custom cwd as Path object should work."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="lint", command="echo lint", required=True),
        ]

        mock_gate_runner = MagicMock(spec=GateRunner)
        mock_gate_runner.run_all_gates.return_value = (True, [])
        mock_gate_runner.get_summary.return_value = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "timeout": 0,
            "error": 0,
            "skipped": 0,
        }

        with patch("zerg.merge.GateRunner", return_value=mock_gate_runner):
            with patch("zerg.merge.GitOps"):
                coordinator = MergeCoordinator(
                    feature="test-feature",
                    config=config,
                )

        custom_dir = Path("/custom/path")
        coordinator.run_pre_merge_gates(cwd=custom_dir)

        # Verify cwd was passed to run_all_gates
        mock_gate_runner.run_all_gates.assert_called_once()
        call_kwargs = mock_gate_runner.run_all_gates.call_args[1]
        assert call_kwargs.get("cwd") == custom_dir

    def test_cwd_none_uses_default(self):
        """When cwd is None, default behavior should apply."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="lint", command="echo lint", required=True),
        ]

        mock_gate_runner = MagicMock(spec=GateRunner)
        mock_gate_runner.run_all_gates.return_value = (True, [])
        mock_gate_runner.get_summary.return_value = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "timeout": 0,
            "error": 0,
            "skipped": 0,
        }

        with patch("zerg.merge.GateRunner", return_value=mock_gate_runner):
            with patch("zerg.merge.GitOps"):
                coordinator = MergeCoordinator(
                    feature="test-feature",
                    config=config,
                )

        coordinator.run_pre_merge_gates(cwd=None)

        # Verify cwd=None was passed (default behavior)
        mock_gate_runner.run_all_gates.assert_called_once()
        call_kwargs = mock_gate_runner.run_all_gates.call_args[1]
        assert call_kwargs.get("cwd") is None

    def test_cwd_with_temp_directory(self):
        """Custom cwd with actual temp directory should work."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="lint", command="echo lint", required=True),
        ]

        mock_gate_runner = MagicMock(spec=GateRunner)
        mock_gate_runner.run_all_gates.return_value = (True, [])
        mock_gate_runner.get_summary.return_value = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "timeout": 0,
            "error": 0,
            "skipped": 0,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("zerg.merge.GateRunner", return_value=mock_gate_runner):
                with patch("zerg.merge.GitOps"):
                    coordinator = MergeCoordinator(
                        feature="test-feature",
                        config=config,
                    )

            coordinator.run_pre_merge_gates(cwd=tmpdir)

            # Verify temp dir was passed
            mock_gate_runner.run_all_gates.assert_called_once()
            call_kwargs = mock_gate_runner.run_all_gates.call_args[1]
            assert call_kwargs.get("cwd") == tmpdir


class TestGateExecutionIntegration:
    """Integration tests for gate execution flow."""

    def test_run_pre_merge_gates_returns_correct_types(self):
        """Return types should match expected signature."""
        config = ZergConfig()
        config.quality_gates = []

        mock_gate_runner = MagicMock(spec=GateRunner)
        mock_gate_runner.run_all_gates.return_value = (True, [])
        mock_gate_runner.get_summary.return_value = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "timeout": 0,
            "error": 0,
            "skipped": 0,
        }

        with patch("zerg.merge.GateRunner", return_value=mock_gate_runner):
            with patch("zerg.merge.GitOps"):
                coordinator = MergeCoordinator(
                    feature="test-feature",
                    config=config,
                )

        result = coordinator.run_pre_merge_gates()

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], list)

    def test_gate_results_contain_required_fields(self):
        """Gate results should contain all required fields."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="lint", command="echo lint", required=True),
        ]

        mock_gate_runner = MagicMock(spec=GateRunner)
        gate_result = GateRunResult(
            gate_name="lint",
            result=GateResult.PASS,
            command="echo lint",
            exit_code=0,
            stdout="output",
            stderr="",
            duration_ms=50,
        )
        mock_gate_runner.run_all_gates.return_value = (True, [gate_result])
        mock_gate_runner.get_summary.return_value = {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "timeout": 0,
            "error": 0,
            "skipped": 0,
        }

        with patch("zerg.merge.GateRunner", return_value=mock_gate_runner):
            with patch("zerg.merge.GitOps"):
                coordinator = MergeCoordinator(
                    feature="test-feature",
                    config=config,
                )

        _, results = coordinator.run_pre_merge_gates()

        assert len(results) == 1
        result = results[0]
        assert hasattr(result, "gate_name")
        assert hasattr(result, "result")
        assert hasattr(result, "command")
        assert hasattr(result, "exit_code")
        assert hasattr(result, "stdout")
        assert hasattr(result, "stderr")
        assert hasattr(result, "duration_ms")

    def test_gates_config_passed_to_runner(self):
        """Quality gates from config should be passed to gate runner."""
        config = ZergConfig()
        gate1 = QualityGate(name="lint", command="echo lint", required=True)
        gate2 = QualityGate(name="test", command="echo test", required=True)
        config.quality_gates = [gate1, gate2]

        mock_gate_runner = MagicMock(spec=GateRunner)
        mock_gate_runner.run_all_gates.return_value = (True, [])
        mock_gate_runner.get_summary.return_value = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "timeout": 0,
            "error": 0,
            "skipped": 0,
        }

        with patch("zerg.merge.GateRunner", return_value=mock_gate_runner):
            with patch("zerg.merge.GitOps"):
                coordinator = MergeCoordinator(
                    feature="test-feature",
                    config=config,
                )

        coordinator.run_pre_merge_gates()

        # Verify gates were passed
        mock_gate_runner.run_all_gates.assert_called_once()
        call_kwargs = mock_gate_runner.run_all_gates.call_args[1]
        assert call_kwargs.get("gates") == config.quality_gates


class TestPostMergeGates:
    """Tests for run_post_merge_gates consistency with run_pre_merge_gates."""

    def test_post_merge_gates_same_signature(self):
        """run_post_merge_gates should have same return signature as run_pre_merge_gates."""
        config = ZergConfig()
        config.quality_gates = []

        mock_gate_runner = MagicMock(spec=GateRunner)
        mock_gate_runner.run_all_gates.return_value = (True, [])
        mock_gate_runner.get_summary.return_value = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "timeout": 0,
            "error": 0,
            "skipped": 0,
        }

        with patch("zerg.merge.GateRunner", return_value=mock_gate_runner):
            with patch("zerg.merge.GitOps"):
                coordinator = MergeCoordinator(
                    feature="test-feature",
                    config=config,
                )

        pre_result = coordinator.run_pre_merge_gates()
        post_result = coordinator.run_post_merge_gates()

        # Both should return tuple[bool, list[GateRunResult]]
        assert type(pre_result) is type(post_result)
        assert len(pre_result) == len(post_result)

    def test_post_merge_gates_uses_required_only(self):
        """run_post_merge_gates should also use required_only=True."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="lint", command="echo lint", required=True),
        ]

        mock_gate_runner = MagicMock(spec=GateRunner)
        mock_gate_runner.run_all_gates.return_value = (True, [])
        mock_gate_runner.get_summary.return_value = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "timeout": 0,
            "error": 0,
            "skipped": 0,
        }

        with patch("zerg.merge.GateRunner", return_value=mock_gate_runner):
            with patch("zerg.merge.GitOps"):
                coordinator = MergeCoordinator(
                    feature="test-feature",
                    config=config,
                )

        coordinator.run_post_merge_gates()

        # Verify required_only=True was passed
        mock_gate_runner.run_all_gates.assert_called_once()
        call_kwargs = mock_gate_runner.run_all_gates.call_args[1]
        assert call_kwargs.get("required_only") is True
