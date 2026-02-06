"""Tests for MergeFlowResult dataclass and to_dict() method."""

from datetime import datetime

import pytest

from zerg.constants import GateResult
from zerg.merge import MergeFlowResult
from zerg.types import GateRunResult


class TestMergeFlowResultInitialization:
    """Test MergeFlowResult initialization with all fields."""

    def test_init_with_required_fields_only(self) -> None:
        """Test initialization with only required fields and defaults."""
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["worker-1", "worker-2"],
            target_branch="main",
        )
        assert result.success is True
        assert result.level == 1
        assert result.source_branches == ["worker-1", "worker-2"]
        assert result.target_branch == "main"
        assert result.merge_commit is None
        assert result.gate_results == []
        assert result.error is None
        assert isinstance(result.timestamp, datetime)

    def test_init_with_failure_scenario(self) -> None:
        """Test initialization for a failed merge scenario."""
        result = MergeFlowResult(
            success=False,
            level=3,
            source_branches=["worker-1"],
            target_branch="main",
            merge_commit=None,
            gate_results=[],
            error="Merge conflict in src/auth.py",
        )
        assert result.success is False
        assert result.level == 3
        assert result.merge_commit is None
        assert result.error == "Merge conflict in src/auth.py"


class TestMergeFlowResultToDict:
    """Test to_dict() serialization method."""

    def test_to_dict_correct_values_and_types(self) -> None:
        """Test that to_dict() produces correct values and types for each field."""
        timestamp = datetime(2025, 6, 15, 10, 20, 30)
        gate = GateRunResult(
            gate_name="test",
            result=GateResult.PASS,
            command="echo test",
            exit_code=0,
        )
        result = MergeFlowResult(
            success=True,
            level=4,
            source_branches=["worker-0", "worker-1", "worker-2"],
            target_branch="release",
            merge_commit="deadbeef1234",
            gate_results=[gate],
            error=None,
            timestamp=timestamp,
        )
        d = result.to_dict()

        assert isinstance(d, dict)
        assert d["success"] is True
        assert isinstance(d["success"], bool)
        assert d["level"] == 4
        assert isinstance(d["level"], int)
        assert d["source_branches"] == ["worker-0", "worker-1", "worker-2"]
        assert isinstance(d["source_branches"], list)
        assert d["target_branch"] == "release"
        assert isinstance(d["target_branch"], str)
        assert d["merge_commit"] == "deadbeef1234"
        assert isinstance(d["gate_results"], list)
        assert isinstance(d["gate_results"][0], dict)
        assert d["error"] is None
        assert isinstance(d["timestamp"], str)


class TestGateResultsSerialization:
    """Test gate_results list serialization in to_dict()."""

    def test_single_gate_result_serialization(self) -> None:
        """Test serialization of a single gate result."""
        gate_timestamp = datetime(2025, 1, 27, 9, 0, 0)
        gate = GateRunResult(
            gate_name="pytest",
            result=GateResult.PASS,
            command="pytest tests/",
            exit_code=0,
            stdout="10 tests passed",
            stderr="",
            duration_ms=5000,
            timestamp=gate_timestamp,
        )
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["worker-1"],
            target_branch="main",
            gate_results=[gate],
        )
        d = result.to_dict()

        assert len(d["gate_results"]) == 1
        gate_dict = d["gate_results"][0]
        assert gate_dict["gate_name"] == "pytest"
        assert gate_dict["result"] == "pass"
        assert gate_dict["command"] == "pytest tests/"
        assert gate_dict["exit_code"] == 0
        assert gate_dict["stdout"] == "10 tests passed"
        assert gate_dict["stderr"] == ""
        assert gate_dict["duration_ms"] == 5000
        assert gate_dict["timestamp"] == "2025-01-27T09:00:00"

    @pytest.mark.parametrize(
        "gate_enum,expected_str",
        [
            (GateResult.PASS, "pass"),
            (GateResult.FAIL, "fail"),
            (GateResult.SKIP, "skip"),
            (GateResult.TIMEOUT, "timeout"),
            (GateResult.ERROR, "error"),
        ],
    )
    def test_gate_result_enum_serialization(self, gate_enum: GateResult, expected_str: str) -> None:
        """Test serialization of all GateResult enum values."""
        timestamp = datetime(2025, 1, 27, 12, 0, 0)
        gate = GateRunResult(
            gate_name="test-gate",
            result=gate_enum,
            command="test",
            exit_code=0,
            timestamp=timestamp,
        )
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=[],
            target_branch="main",
            gate_results=[gate],
            timestamp=timestamp,
        )
        d = result.to_dict()
        assert d["gate_results"][0]["result"] == expected_str


class TestTimestampSerialization:
    """Test timestamp ISO format conversion in to_dict()."""

    @pytest.mark.parametrize(
        "ts,expected",
        [
            (datetime(2025, 1, 27, 15, 45, 30), "2025-01-27T15:45:30"),
            (datetime(2025, 3, 10, 8, 30, 15, 123456), "2025-03-10T08:30:15.123456"),
            (datetime(2025, 12, 31, 0, 0, 0), "2025-12-31T00:00:00"),
            (datetime(2025, 7, 4, 23, 59, 59), "2025-07-04T23:59:59"),
        ],
    )
    def test_timestamp_iso_format(self, ts: datetime, expected: str) -> None:
        """Test various timestamp ISO format conversions."""
        result = MergeFlowResult(success=True, level=1, source_branches=[], target_branch="main", timestamp=ts)
        d = result.to_dict()
        assert d["timestamp"] == expected

    def test_default_timestamp_is_current_time(self) -> None:
        """Test that default timestamp is approximately current time."""
        before = datetime.now()
        result = MergeFlowResult(success=True, level=1, source_branches=[], target_branch="main")
        after = datetime.now()
        assert before <= result.timestamp <= after
        d = result.to_dict()
        assert before <= datetime.fromisoformat(d["timestamp"]) <= after


class TestOptionalFieldSerialization:
    """Test handling of None and present values for optional fields."""

    @pytest.mark.parametrize(
        "merge_commit,error",
        [
            (None, None),
            ("abc123", None),
            (None, "Merge conflict detected"),
        ],
    )
    def test_optional_field_combinations(self, merge_commit, error) -> None:
        """Test to_dict with various optional field combinations."""
        result = MergeFlowResult(
            success=merge_commit is not None,
            level=1,
            source_branches=["worker-1"],
            target_branch="main",
            merge_commit=merge_commit,
            error=error,
        )
        d = result.to_dict()
        assert d["merge_commit"] == merge_commit
        assert d["error"] == error
        assert "merge_commit" in d
        assert "error" in d


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_large_number_of_source_branches(self) -> None:
        """Test with many source branches."""
        branches = [f"worker-{i}" for i in range(100)]
        result = MergeFlowResult(success=True, level=1, source_branches=branches, target_branch="main")
        d = result.to_dict()
        assert len(d["source_branches"]) == 100
        assert d["source_branches"][0] == "worker-0"
        assert d["source_branches"][99] == "worker-99"

    def test_special_characters_in_branch_names(self) -> None:
        """Test branch names with special characters."""
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["feature/auth-v2.0", "bugfix/issue#123", "release_1.2.3"],
            target_branch="main",
        )
        d = result.to_dict()
        assert d["source_branches"] == ["feature/auth-v2.0", "bugfix/issue#123", "release_1.2.3"]

    @pytest.mark.parametrize("level", [0, -1])
    def test_boundary_levels(self, level: int) -> None:
        """Test with boundary level values."""
        result = MergeFlowResult(success=True, level=level, source_branches=[], target_branch="main")
        d = result.to_dict()
        assert d["level"] == level
