"""Integration tests for verification tiers wiring into verify.py."""

from unittest.mock import MagicMock, patch

from zerg.config import VerificationTiersConfig
from zerg.verify import VerificationExecutor


class TestVerificationTiersWiring:
    """Test that VerificationExecutor.verify_task_tiered() works with VerificationTiers."""

    def test_verify_task_tiered_returns_result(self) -> None:
        executor = VerificationExecutor(default_timeout=10)
        task = {
            "id": "TASK-001",
            "verification": {"command": "echo ok", "timeout_seconds": 10},
        }

        with patch("zerg.verification_tiers.CommandExecutor") as mock_cls:
            mock_exec = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.exit_code = 0
            mock_result.stdout = "ok"
            mock_result.stderr = ""
            mock_exec.execute.return_value = mock_result
            mock_cls.return_value = mock_exec

            result = executor.verify_task_tiered(task)

        assert result.task_id == "TASK-001"
        assert result.overall_pass is True
        assert len(result.tiers) == 1
        assert result.tiers[0].tier == 2  # fallback to task verification

    def test_verify_task_tiered_with_config(self) -> None:
        config = VerificationTiersConfig(
            tier1_command="lint",
            tier2_command="test",
        )
        executor = VerificationExecutor(default_timeout=10)
        task = {"id": "TASK-002"}

        with patch("zerg.verification_tiers.CommandExecutor") as mock_cls:
            mock_exec = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.exit_code = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_exec.execute.return_value = mock_result
            mock_cls.return_value = mock_exec

            result = executor.verify_task_tiered(task, config=config)

        assert result.overall_pass is True
        assert len(result.tiers) == 2

    def test_verify_task_tiered_records_results(self) -> None:
        executor = VerificationExecutor(default_timeout=10)
        task = {
            "id": "TASK-003",
            "verification": {"command": "pytest", "timeout_seconds": 10},
        }

        with patch("zerg.verification_tiers.CommandExecutor") as mock_cls:
            mock_exec = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.exit_code = 0
            mock_result.stdout = "passed"
            mock_result.stderr = ""
            mock_exec.execute.return_value = mock_result
            mock_cls.return_value = mock_exec

            executor.verify_task_tiered(task)

        # Should record results in standard results list
        results = executor.get_results()
        assert len(results) >= 1
        assert results[0].task_id == "TASK-003"

    def test_blocking_failure_stops_execution(self) -> None:
        config = VerificationTiersConfig(
            tier1_command="lint",
            tier2_command="test",
            tier3_command="quality",
        )
        executor = VerificationExecutor(default_timeout=10)

        call_count = 0

        def mock_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            result.success = False  # All fail
            result.exit_code = 1
            result.stdout = ""
            result.stderr = "error"
            return result

        with patch("zerg.verification_tiers.CommandExecutor") as mock_cls:
            mock_exec = MagicMock()
            mock_exec.execute.side_effect = mock_execute
            mock_cls.return_value = mock_exec

            result = executor.verify_task_tiered({"id": "T1"}, config=config)

        # Should stop after tier 1 failure
        assert result.overall_pass is False
        assert len(result.tiers) == 1
        assert call_count == 1
