"""Tests for ZERG verification tiers module."""

from unittest.mock import MagicMock, patch

from zerg.config import VerificationTiersConfig
from zerg.verification_tiers import (
    TieredVerificationResult,
    TierResult,
    VerificationTiers,
)


class TestTierResult:
    """Tests for TierResult dataclass."""

    def test_creation(self) -> None:
        result = TierResult(
            tier=1,
            name="syntax",
            success=True,
            blocking=True,
            command="python -m py_compile file.py",
            stdout="",
            stderr="",
            duration_ms=50,
        )
        assert result.tier == 1
        assert result.success is True
        assert result.blocking is True

    def test_to_dict(self) -> None:
        result = TierResult(
            tier=2,
            name="correctness",
            success=False,
            blocking=True,
            command="pytest",
            stdout="out",
            stderr="err",
            duration_ms=1000,
        )
        d = result.to_dict()
        assert d["tier"] == 2
        assert d["success"] is False
        assert d["duration_ms"] == 1000


class TestTieredVerificationResult:
    """Tests for TieredVerificationResult."""

    def test_overall_pass_all_blocking_pass(self) -> None:
        result = TieredVerificationResult(
            task_id="T1",
            tiers=[
                TierResult(1, "syntax", True, True, "", "", "", 0),
                TierResult(2, "correctness", True, True, "", "", "", 0),
                TierResult(3, "quality", False, False, "", "", "", 0),
            ],
        )
        assert result.overall_pass is True
        assert result.overall_quality is False

    def test_overall_pass_blocking_fails(self) -> None:
        result = TieredVerificationResult(
            task_id="T1",
            tiers=[
                TierResult(1, "syntax", False, True, "", "", "", 0),
            ],
        )
        assert result.overall_pass is False

    def test_overall_quality_all_pass(self) -> None:
        result = TieredVerificationResult(
            task_id="T1",
            tiers=[
                TierResult(1, "syntax", True, True, "", "", "", 0),
                TierResult(2, "correctness", True, True, "", "", "", 0),
                TierResult(3, "quality", True, False, "", "", "", 0),
            ],
        )
        assert result.overall_quality is True

    def test_empty_tiers(self) -> None:
        result = TieredVerificationResult(task_id="T1")
        assert result.overall_pass is True  # vacuously true
        assert result.overall_quality is True

    def test_to_dict(self) -> None:
        result = TieredVerificationResult(
            task_id="T1",
            tiers=[TierResult(1, "syntax", True, True, "cmd", "", "", 50)],
        )
        d = result.to_dict()
        assert d["task_id"] == "T1"
        assert d["overall_pass"] is True
        assert len(d["tiers"]) == 1


class TestVerificationTiers:
    """Tests for VerificationTiers executor."""

    def test_execute_no_commands(self) -> None:
        config = VerificationTiersConfig()
        vt = VerificationTiers(config=config)
        task = {"id": "T1"}
        result = vt.execute(task)
        assert result.task_id == "T1"
        assert result.overall_pass is True  # no tiers to fail
        assert len(result.tiers) == 0

    def test_execute_falls_back_to_task_verification(self) -> None:
        config = VerificationTiersConfig()
        vt = VerificationTiers(config=config)
        task = {
            "id": "T1",
            "verification": {"command": "echo ok", "timeout_seconds": 10},
        }

        with patch("zerg.verification_tiers.CommandExecutor") as mock_cls:
            mock_executor = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.exit_code = 0
            mock_result.stdout = "ok"
            mock_result.stderr = ""
            mock_executor.execute.return_value = mock_result
            mock_cls.return_value = mock_executor

            result = vt.execute(task)

        assert len(result.tiers) == 1
        assert result.tiers[0].tier == 2
        assert result.tiers[0].name == "correctness"
        assert result.tiers[0].success is True

    def test_execute_stops_on_blocking_failure(self) -> None:
        config = VerificationTiersConfig(
            tier1_command="lint",
            tier2_command="test",
            tier3_command="quality",
        )
        vt = VerificationTiers(config=config)

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            mock_result.success = call_count > 1  # First call fails
            mock_result.exit_code = 0 if mock_result.success else 1
            mock_result.stdout = ""
            mock_result.stderr = "lint error" if call_count == 1 else ""
            return mock_result

        with patch("zerg.verification_tiers.CommandExecutor") as mock_cls:
            mock_executor = MagicMock()
            mock_executor.execute.side_effect = side_effect
            mock_cls.return_value = mock_executor

            result = vt.execute({"id": "T1"})

        # Should stop after tier 1 failure (blocking)
        assert len(result.tiers) == 1
        assert result.tiers[0].tier == 1
        assert result.tiers[0].success is False
        assert result.overall_pass is False

    def test_resolve_tier_commands_with_all_configured(self) -> None:
        config = VerificationTiersConfig(
            tier1_command="lint",
            tier2_command="test",
            tier3_command="quality",
        )
        vt = VerificationTiers(config=config)
        commands = vt._resolve_tier_commands("fallback")
        assert commands == {1: "lint", 2: "test", 3: "quality"}

    def test_resolve_tier_commands_fallback(self) -> None:
        config = VerificationTiersConfig()
        vt = VerificationTiers(config=config)
        commands = vt._resolve_tier_commands("pytest tests/")
        assert commands == {2: "pytest tests/"}
