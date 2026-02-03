"""Tests for MergeFlowResult dataclass and to_dict() method."""

from datetime import datetime

from zerg.constants import GateResult
from zerg.merge import MergeFlowResult
from zerg.types import GateRunResult


class TestMergeFlowResultInitialization:
    """Test MergeFlowResult initialization with all fields."""

    def test_init_with_required_fields_only(self) -> None:
        """Test initialization with only required fields."""
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
        # Check defaults
        assert result.merge_commit is None
        assert result.gate_results == []
        assert result.error is None
        assert isinstance(result.timestamp, datetime)

    def test_init_with_all_fields(self) -> None:
        """Test initialization with all fields populated."""
        timestamp = datetime(2025, 1, 27, 12, 0, 0)
        gate_result = GateRunResult(
            gate_name="lint",
            result=GateResult.PASS,
            command="ruff check .",
            exit_code=0,
            stdout="All checks passed",
            stderr="",
            duration_ms=1500,
            timestamp=timestamp,
        )
        result = MergeFlowResult(
            success=True,
            level=2,
            source_branches=["feature/auth-1", "feature/auth-2", "feature/auth-3"],
            target_branch="develop",
            merge_commit="abc123def456",
            gate_results=[gate_result],
            error=None,
            timestamp=timestamp,
        )
        assert result.success is True
        assert result.level == 2
        assert result.source_branches == ["feature/auth-1", "feature/auth-2", "feature/auth-3"]
        assert result.target_branch == "develop"
        assert result.merge_commit == "abc123def456"
        assert len(result.gate_results) == 1
        assert result.gate_results[0].gate_name == "lint"
        assert result.error is None
        assert result.timestamp == timestamp

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

    def test_init_with_empty_source_branches(self) -> None:
        """Test initialization with empty source branches list."""
        result = MergeFlowResult(
            success=False,
            level=1,
            source_branches=[],
            target_branch="main",
            error="No worker branches found",
        )
        assert result.source_branches == []
        assert result.error == "No worker branches found"


class TestMergeFlowResultToDict:
    """Test to_dict() serialization method."""

    def test_to_dict_serializes_all_fields(self) -> None:
        """Test that to_dict() includes all fields in output."""
        timestamp = datetime(2025, 1, 27, 14, 30, 45)
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["branch-a", "branch-b"],
            target_branch="main",
            merge_commit="sha256hash",
            gate_results=[],
            error=None,
            timestamp=timestamp,
        )
        d = result.to_dict()

        assert "success" in d
        assert "level" in d
        assert "source_branches" in d
        assert "target_branch" in d
        assert "merge_commit" in d
        assert "gate_results" in d
        assert "error" in d
        assert "timestamp" in d

    def test_to_dict_correct_values(self) -> None:
        """Test that to_dict() produces correct values for each field."""
        timestamp = datetime(2025, 6, 15, 10, 20, 30)
        result = MergeFlowResult(
            success=True,
            level=4,
            source_branches=["worker-0", "worker-1", "worker-2"],
            target_branch="release",
            merge_commit="deadbeef1234",
            gate_results=[],
            error=None,
            timestamp=timestamp,
        )
        d = result.to_dict()

        assert d["success"] is True
        assert d["level"] == 4
        assert d["source_branches"] == ["worker-0", "worker-1", "worker-2"]
        assert d["target_branch"] == "release"
        assert d["merge_commit"] == "deadbeef1234"
        assert d["gate_results"] == []
        assert d["error"] is None

    def test_to_dict_preserves_source_branches_list_type(self) -> None:
        """Test that source_branches remains a list in dict output."""
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["a", "b", "c"],
            target_branch="main",
        )
        d = result.to_dict()
        assert isinstance(d["source_branches"], list)
        assert d["source_branches"] == ["a", "b", "c"]


class TestGateResultsSerialization:
    """Test gate_results list serialization in to_dict()."""

    def test_empty_gate_results_serializes_to_empty_list(self) -> None:
        """Test that empty gate_results becomes empty list in dict."""
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["worker-1"],
            target_branch="main",
            gate_results=[],
        )
        d = result.to_dict()
        assert d["gate_results"] == []
        assert isinstance(d["gate_results"], list)

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

    def test_multiple_gate_results_serialization(self) -> None:
        """Test serialization of multiple gate results."""
        timestamp1 = datetime(2025, 1, 27, 10, 0, 0)
        timestamp2 = datetime(2025, 1, 27, 10, 1, 0)
        timestamp3 = datetime(2025, 1, 27, 10, 2, 0)

        gates = [
            GateRunResult(
                gate_name="lint",
                result=GateResult.PASS,
                command="ruff check .",
                exit_code=0,
                stdout="",
                stderr="",
                duration_ms=1000,
                timestamp=timestamp1,
            ),
            GateRunResult(
                gate_name="typecheck",
                result=GateResult.PASS,
                command="mypy .",
                exit_code=0,
                stdout="Success: no issues found",
                stderr="",
                duration_ms=3000,
                timestamp=timestamp2,
            ),
            GateRunResult(
                gate_name="security",
                result=GateResult.FAIL,
                command="bandit -r src/",
                exit_code=1,
                stdout="",
                stderr="High severity issue found",
                duration_ms=2000,
                timestamp=timestamp3,
            ),
        ]
        result = MergeFlowResult(
            success=False,
            level=2,
            source_branches=["worker-1", "worker-2"],
            target_branch="main",
            gate_results=gates,
            error="Quality gates failed",
        )
        d = result.to_dict()

        assert len(d["gate_results"]) == 3
        assert d["gate_results"][0]["gate_name"] == "lint"
        assert d["gate_results"][0]["result"] == "pass"
        assert d["gate_results"][1]["gate_name"] == "typecheck"
        assert d["gate_results"][1]["result"] == "pass"
        assert d["gate_results"][2]["gate_name"] == "security"
        assert d["gate_results"][2]["result"] == "fail"
        assert d["gate_results"][2]["stderr"] == "High severity issue found"

    def test_gate_result_all_statuses(self) -> None:
        """Test serialization of all GateResult enum values."""
        statuses = [
            (GateResult.PASS, "pass"),
            (GateResult.FAIL, "fail"),
            (GateResult.SKIP, "skip"),
            (GateResult.TIMEOUT, "timeout"),
            (GateResult.ERROR, "error"),
        ]
        timestamp = datetime(2025, 1, 27, 12, 0, 0)

        for gate_result_enum, expected_string in statuses:
            gate = GateRunResult(
                gate_name="test-gate",
                result=gate_result_enum,
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
            assert d["gate_results"][0]["result"] == expected_string


class TestTimestampIsoFormatConversion:
    """Test timestamp ISO format conversion in to_dict()."""

    def test_timestamp_basic_iso_format(self) -> None:
        """Test basic ISO format conversion of timestamp."""
        timestamp = datetime(2025, 1, 27, 15, 45, 30)
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["worker-1"],
            target_branch="main",
            timestamp=timestamp,
        )
        d = result.to_dict()
        assert d["timestamp"] == "2025-01-27T15:45:30"

    def test_timestamp_with_microseconds(self) -> None:
        """Test ISO format conversion preserves microseconds."""
        timestamp = datetime(2025, 3, 10, 8, 30, 15, 123456)
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["worker-1"],
            target_branch="main",
            timestamp=timestamp,
        )
        d = result.to_dict()
        assert d["timestamp"] == "2025-03-10T08:30:15.123456"

    def test_timestamp_midnight(self) -> None:
        """Test ISO format for midnight timestamp."""
        timestamp = datetime(2025, 12, 31, 0, 0, 0)
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=[],
            target_branch="main",
            timestamp=timestamp,
        )
        d = result.to_dict()
        assert d["timestamp"] == "2025-12-31T00:00:00"

    def test_timestamp_end_of_day(self) -> None:
        """Test ISO format for end of day timestamp."""
        timestamp = datetime(2025, 7, 4, 23, 59, 59)
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=[],
            target_branch="main",
            timestamp=timestamp,
        )
        d = result.to_dict()
        assert d["timestamp"] == "2025-07-04T23:59:59"

    def test_timestamp_can_be_parsed_back(self) -> None:
        """Test that serialized timestamp can be parsed back to datetime."""
        original_timestamp = datetime(2025, 5, 20, 14, 22, 33)
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=[],
            target_branch="main",
            timestamp=original_timestamp,
        )
        d = result.to_dict()
        parsed_timestamp = datetime.fromisoformat(d["timestamp"])
        assert parsed_timestamp == original_timestamp

    def test_default_timestamp_is_current_time(self) -> None:
        """Test that default timestamp is approximately current time."""
        before = datetime.now()
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=[],
            target_branch="main",
        )
        after = datetime.now()

        # Timestamp should be between before and after
        assert before <= result.timestamp <= after

        # And should serialize to ISO format
        d = result.to_dict()
        parsed = datetime.fromisoformat(d["timestamp"])
        assert before <= parsed <= after


class TestNoneValuesForOptionalFields:
    """Test handling of None values for optional fields."""

    def test_merge_commit_none(self) -> None:
        """Test that None merge_commit serializes correctly."""
        result = MergeFlowResult(
            success=False,
            level=1,
            source_branches=["worker-1"],
            target_branch="main",
            merge_commit=None,
        )
        d = result.to_dict()
        assert d["merge_commit"] is None
        assert "merge_commit" in d

    def test_error_none(self) -> None:
        """Test that None error serializes correctly."""
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["worker-1"],
            target_branch="main",
            error=None,
        )
        d = result.to_dict()
        assert d["error"] is None
        assert "error" in d

    def test_both_optional_fields_none(self) -> None:
        """Test serialization when both optional fields are None."""
        timestamp = datetime(2025, 1, 27, 16, 0, 0)
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["worker-1", "worker-2"],
            target_branch="main",
            merge_commit=None,
            error=None,
            timestamp=timestamp,
        )
        d = result.to_dict()
        assert d["merge_commit"] is None
        assert d["error"] is None
        # Verify other fields are still present and correct
        assert d["success"] is True
        assert d["level"] == 1
        assert d["source_branches"] == ["worker-1", "worker-2"]
        assert d["target_branch"] == "main"
        assert d["gate_results"] == []
        assert d["timestamp"] == "2025-01-27T16:00:00"

    def test_merge_commit_present_error_none(self) -> None:
        """Test successful merge with commit but no error."""
        result = MergeFlowResult(
            success=True,
            level=2,
            source_branches=["worker-1"],
            target_branch="main",
            merge_commit="abc123",
            error=None,
        )
        d = result.to_dict()
        assert d["merge_commit"] == "abc123"
        assert d["error"] is None

    def test_error_present_merge_commit_none(self) -> None:
        """Test failed merge with error but no commit."""
        result = MergeFlowResult(
            success=False,
            level=2,
            source_branches=["worker-1"],
            target_branch="main",
            merge_commit=None,
            error="Merge conflict detected",
        )
        d = result.to_dict()
        assert d["merge_commit"] is None
        assert d["error"] == "Merge conflict detected"

    def test_default_values_for_optional_fields(self) -> None:
        """Test that default values for optional fields work correctly."""
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["worker-1"],
            target_branch="main",
        )
        # merge_commit and error should default to None
        assert result.merge_commit is None
        assert result.error is None
        # gate_results should default to empty list
        assert result.gate_results == []

        d = result.to_dict()
        assert d["merge_commit"] is None
        assert d["error"] is None
        assert d["gate_results"] == []


class TestToDictOutputTypes:
    """Test that to_dict() returns correct Python types."""

    def test_output_is_dict(self) -> None:
        """Test that to_dict() returns a dict."""
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=[],
            target_branch="main",
        )
        d = result.to_dict()
        assert isinstance(d, dict)

    def test_success_is_bool(self) -> None:
        """Test that success field is boolean in dict."""
        for success_val in [True, False]:
            result = MergeFlowResult(
                success=success_val,
                level=1,
                source_branches=[],
                target_branch="main",
            )
            d = result.to_dict()
            assert isinstance(d["success"], bool)
            assert d["success"] is success_val

    def test_level_is_int(self) -> None:
        """Test that level field is int in dict."""
        result = MergeFlowResult(
            success=True,
            level=5,
            source_branches=[],
            target_branch="main",
        )
        d = result.to_dict()
        assert isinstance(d["level"], int)
        assert d["level"] == 5

    def test_source_branches_is_list(self) -> None:
        """Test that source_branches field is list in dict."""
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["a", "b"],
            target_branch="main",
        )
        d = result.to_dict()
        assert isinstance(d["source_branches"], list)

    def test_target_branch_is_str(self) -> None:
        """Test that target_branch field is str in dict."""
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=[],
            target_branch="develop",
        )
        d = result.to_dict()
        assert isinstance(d["target_branch"], str)

    def test_gate_results_is_list_of_dicts(self) -> None:
        """Test that gate_results is list of dicts in output."""
        gate = GateRunResult(
            gate_name="test",
            result=GateResult.PASS,
            command="echo test",
            exit_code=0,
        )
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=[],
            target_branch="main",
            gate_results=[gate],
        )
        d = result.to_dict()
        assert isinstance(d["gate_results"], list)
        assert len(d["gate_results"]) == 1
        assert isinstance(d["gate_results"][0], dict)

    def test_timestamp_is_str(self) -> None:
        """Test that timestamp field is str (ISO format) in dict."""
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=[],
            target_branch="main",
        )
        d = result.to_dict()
        assert isinstance(d["timestamp"], str)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_large_number_of_source_branches(self) -> None:
        """Test with many source branches."""
        branches = [f"worker-{i}" for i in range(100)]
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=branches,
            target_branch="main",
        )
        d = result.to_dict()
        assert len(d["source_branches"]) == 100
        assert d["source_branches"][0] == "worker-0"
        assert d["source_branches"][99] == "worker-99"

    def test_large_number_of_gate_results(self) -> None:
        """Test with many gate results."""
        timestamp = datetime(2025, 1, 27, 12, 0, 0)
        gates = [
            GateRunResult(
                gate_name=f"gate-{i}",
                result=GateResult.PASS,
                command=f"command-{i}",
                exit_code=0,
                timestamp=timestamp,
            )
            for i in range(50)
        ]
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["worker-1"],
            target_branch="main",
            gate_results=gates,
            timestamp=timestamp,
        )
        d = result.to_dict()
        assert len(d["gate_results"]) == 50
        assert d["gate_results"][0]["gate_name"] == "gate-0"
        assert d["gate_results"][49]["gate_name"] == "gate-49"

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

    def test_unicode_in_error_message(self) -> None:
        """Test error message with unicode characters."""
        result = MergeFlowResult(
            success=False,
            level=1,
            source_branches=[],
            target_branch="main",
            error="Merge failed: conflict in file.py - \u2718 \u26a0\ufe0f",
        )
        d = result.to_dict()
        assert "\u2718" in d["error"]
        assert "\u26a0\ufe0f" in d["error"]

    def test_very_long_commit_sha(self) -> None:
        """Test with full length git SHA."""
        full_sha = "a" * 40
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["worker-1"],
            target_branch="main",
            merge_commit=full_sha,
        )
        d = result.to_dict()
        assert d["merge_commit"] == full_sha
        assert len(d["merge_commit"]) == 40

    def test_level_zero(self) -> None:
        """Test with level 0 (edge case)."""
        result = MergeFlowResult(
            success=True,
            level=0,
            source_branches=[],
            target_branch="main",
        )
        d = result.to_dict()
        assert d["level"] == 0

    def test_negative_level(self) -> None:
        """Test with negative level (edge case for error scenarios)."""
        result = MergeFlowResult(
            success=False,
            level=-1,
            source_branches=[],
            target_branch="main",
            error="Invalid level",
        )
        d = result.to_dict()
        assert d["level"] == -1

    def test_empty_string_error(self) -> None:
        """Test with empty string error (distinct from None)."""
        result = MergeFlowResult(
            success=False,
            level=1,
            source_branches=[],
            target_branch="main",
            error="",
        )
        d = result.to_dict()
        assert d["error"] == ""
        assert d["error"] is not None

    def test_empty_string_merge_commit(self) -> None:
        """Test with empty string merge_commit (distinct from None)."""
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=[],
            target_branch="main",
            merge_commit="",
        )
        d = result.to_dict()
        assert d["merge_commit"] == ""
        assert d["merge_commit"] is not None
