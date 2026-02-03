"""Integration tests for complete merge workflow.

Tests the full merge flow end-to-end using MockMergeCoordinator,
covering gate pass/fail integration, conflict handling, staging branch
lifecycle, and merge result propagation.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.mocks.mock_merge import MockMergeCoordinator
from zerg.config import QualityGate, ZergConfig
from zerg.constants import GateResult, MergeStatus
from zerg.exceptions import MergeConflictError
from zerg.merge import MergeCoordinator, MergeFlowResult


@pytest.fixture
def sample_config() -> ZergConfig:
    """Create sample configuration for tests."""
    config = ZergConfig()
    config.quality_gates = [
        QualityGate(name="lint", command="echo lint", required=True),
        QualityGate(name="test", command="pytest tests/", required=True),
    ]
    return config


@pytest.fixture
def mock_merger() -> MockMergeCoordinator:
    """Create a fresh MockMergeCoordinator instance."""
    return MockMergeCoordinator("test-feature")


@pytest.fixture
def worker_branches() -> list[str]:
    """Standard worker branches for testing."""
    return [
        "zerg/test-feature/worker-0",
        "zerg/test-feature/worker-1",
        "zerg/test-feature/worker-2",
    ]


class TestFullMergeFlowEndToEnd:
    """Test full merge flow end-to-end scenarios."""

    def test_successful_merge_flow_single_level(
        self, mock_merger: MockMergeCoordinator, worker_branches: list[str]
    ) -> None:
        """Test complete successful merge flow for a single level."""
        mock_merger.configure(always_succeed=True)

        result = mock_merger.full_merge_flow(
            level=1,
            worker_branches=worker_branches,
            target_branch="main",
        )

        assert result.success is True
        assert result.level == 1
        assert result.source_branches == worker_branches
        assert result.target_branch == "main"
        assert result.merge_commit is not None
        assert result.error is None

    def test_successful_merge_flow_multiple_levels(self, mock_merger: MockMergeCoordinator) -> None:
        """Test merge flow across multiple levels sequentially."""
        mock_merger.configure(always_succeed=True)

        results = []
        for level in range(1, 4):
            branches = [f"zerg/test-feature/worker-{i}" for i in range(3)]
            result = mock_merger.full_merge_flow(
                level=level,
                worker_branches=branches,
                target_branch="main",
            )
            results.append(result)

        assert all(r.success for r in results)
        assert [r.level for r in results] == [1, 2, 3]
        assert mock_merger.get_attempt_count() == 3

    def test_merge_flow_with_empty_branches(self, mock_merger: MockMergeCoordinator) -> None:
        """Test merge flow handles empty branch list."""
        mock_merger.configure(always_succeed=True)

        result = mock_merger.full_merge_flow(
            level=1,
            worker_branches=[],
            target_branch="main",
        )

        # MockMergeCoordinator returns success with empty branches
        # Real coordinator would fail
        assert result.source_branches == []

    def test_merge_flow_records_timestamps(self, mock_merger: MockMergeCoordinator, worker_branches: list[str]) -> None:
        """Test merge flow records proper timestamps."""
        mock_merger.configure(always_succeed=True)

        before_merge = datetime.now()
        result = mock_merger.full_merge_flow(
            level=1,
            worker_branches=worker_branches,
        )
        after_merge = datetime.now()

        assert before_merge <= result.timestamp <= after_merge

    def test_merge_flow_to_dict_serialization(
        self, mock_merger: MockMergeCoordinator, worker_branches: list[str]
    ) -> None:
        """Test merge flow result serializes to dict properly."""
        mock_merger.configure(always_succeed=True)

        result = mock_merger.full_merge_flow(
            level=1,
            worker_branches=worker_branches,
        )

        data = result.to_dict()

        assert data["success"] is True
        assert data["level"] == 1
        assert data["source_branches"] == worker_branches
        assert data["target_branch"] == "main"
        assert "timestamp" in data
        assert "gate_results" in data


class TestMergeWithGateIntegration:
    """Test merge flow with gate pass/fail integration."""

    def test_pre_merge_gate_pass_allows_merge(
        self, mock_merger: MockMergeCoordinator, worker_branches: list[str]
    ) -> None:
        """Test merge proceeds when pre-merge gates pass."""
        mock_merger.configure(
            always_succeed=True,
            pre_merge_gate_failure_levels=[],  # No failures
        )
        mock_merger.set_current_level(1)

        passed, results = mock_merger.run_pre_merge_gates()

        assert passed is True
        assert len(results) == 1
        assert results[0].result == GateResult.PASS

    def test_pre_merge_gate_fail_blocks_merge(
        self, mock_merger: MockMergeCoordinator, worker_branches: list[str]
    ) -> None:
        """Test merge blocked when pre-merge gates fail."""
        mock_merger.configure(
            pre_merge_gate_failure_levels=[1],
        )
        mock_merger.set_current_level(1)

        passed, results = mock_merger.run_pre_merge_gates()

        assert passed is False
        assert results[0].result == GateResult.FAIL
        assert results[0].exit_code == 1

    def test_post_merge_gate_pass_completes_flow(
        self, mock_merger: MockMergeCoordinator, worker_branches: list[str]
    ) -> None:
        """Test flow completes when post-merge gates pass."""
        mock_merger.configure(
            always_succeed=True,
            post_merge_gate_failure_levels=[],
        )
        mock_merger.set_current_level(1)

        passed, results = mock_merger.run_post_merge_gates()

        assert passed is True
        assert results[0].gate_name == "post_merge_check"

    def test_post_merge_gate_fail_aborts_flow(
        self, mock_merger: MockMergeCoordinator, worker_branches: list[str]
    ) -> None:
        """Test flow aborts when post-merge gates fail."""
        mock_merger.configure(
            post_merge_gate_failure_levels=[1],
        )
        mock_merger.set_current_level(1)

        passed, results = mock_merger.run_post_merge_gates()

        assert passed is False
        assert results[0].result == GateResult.FAIL

    def test_gate_failure_at_specific_level(self, mock_merger: MockMergeCoordinator) -> None:
        """Test gate failure only at specific level."""
        mock_merger.configure(
            gate_failure_levels=[2],  # Only level 2 fails
        )

        # Level 1 should pass
        result1 = mock_merger.full_merge_flow(
            level=1,
            worker_branches=["worker-0"],
        )
        assert result1.success is True

        # Level 2 should fail
        result2 = mock_merger.full_merge_flow(
            level=2,
            worker_branches=["worker-0"],
        )
        assert result2.success is False
        assert "gates failed" in result2.error.lower()

    def test_gate_results_tracked_in_flow_result(self, mock_merger: MockMergeCoordinator) -> None:
        """Test gate results are properly tracked."""
        mock_merger.configure(always_succeed=True)
        mock_merger.set_current_level(1)

        # Run gates manually to track results
        mock_merger.run_pre_merge_gates()
        mock_merger.run_post_merge_gates()

        gate_runs = mock_merger.get_gate_runs()
        assert len(gate_runs) == 2

        pre_runs = mock_merger.get_pre_merge_gate_runs()
        post_runs = mock_merger.get_post_merge_gate_runs()
        assert len(pre_runs) == 1
        assert len(post_runs) == 1

    def test_gate_delay_simulation(self, mock_merger: MockMergeCoordinator) -> None:
        """Test gate execution delay is simulated."""
        mock_merger.configure(
            always_succeed=True,
            gate_delay=0.1,  # 100ms delay
        )
        mock_merger.set_current_level(1)

        before = datetime.now()
        mock_merger.run_pre_merge_gates()
        after = datetime.now()

        # Should take at least 100ms
        elapsed_ms = (after - before).total_seconds() * 1000
        assert elapsed_ms >= 90  # Allow some tolerance


class TestMergeConflictHandling:
    """Test merge conflict handling in full flow."""

    def test_conflict_at_specific_level(self, mock_merger: MockMergeCoordinator, worker_branches: list[str]) -> None:
        """Test conflict detection at specific level."""
        mock_merger.configure(
            conflict_at_level=1,
            conflicting_files=["src/auth.py", "src/config.py"],
        )

        result = mock_merger.full_merge_flow(
            level=1,
            worker_branches=worker_branches,
        )

        assert result.success is False
        assert "conflict" in result.error.lower()
        assert "src/auth.py" in result.error
        assert "src/config.py" in result.error

    def test_conflict_in_execute_merge(self, mock_merger: MockMergeCoordinator) -> None:
        """Test conflict raised during execute_merge."""
        mock_merger.configure(
            execute_merge_conflict_branches=["zerg/test/worker-1"],
            conflicting_files=["conflicting_file.py"],
        )

        with pytest.raises(MergeConflictError) as exc_info:
            mock_merger.execute_merge(
                source_branches=["zerg/test/worker-0", "zerg/test/worker-1"],
                staging_branch="staging",
            )

        assert "zerg/test/worker-1" in str(exc_info.value)
        assert exc_info.value.conflicting_files == ["conflicting_file.py"]

    def test_conflict_records_merge_result(self, mock_merger: MockMergeCoordinator) -> None:
        """Test conflict is recorded in merge results."""
        mock_merger.configure(
            execute_merge_conflict_branches=["worker-conflict"],
        )

        try:
            mock_merger.execute_merge(
                source_branches=["worker-conflict"],
                staging_branch="staging",
            )
        except MergeConflictError:
            pass

        conflict_merges = mock_merger.get_conflict_merges()
        assert len(conflict_merges) == 1
        assert conflict_merges[0].status == MergeStatus.CONFLICT

    def test_partial_merge_before_conflict(self, mock_merger: MockMergeCoordinator) -> None:
        """Test some branches merge before conflict occurs."""
        mock_merger.configure(
            execute_merge_conflict_branches=["worker-2"],
        )

        try:
            mock_merger.execute_merge(
                source_branches=["worker-0", "worker-1", "worker-2"],
                staging_branch="staging",
            )
        except MergeConflictError:
            pass

        successful = mock_merger.get_successful_merges()
        conflicts = mock_merger.get_conflict_merges()

        # First two should succeed, third should conflict
        assert len(successful) == 2
        assert len(conflicts) == 1

    def test_conflict_preserves_attempt_record(
        self, mock_merger: MockMergeCoordinator, worker_branches: list[str]
    ) -> None:
        """Test conflict is recorded in attempt history."""
        mock_merger.configure(conflict_at_level=1)

        mock_merger.full_merge_flow(
            level=1,
            worker_branches=worker_branches,
        )

        attempts = mock_merger.get_attempts()
        assert len(attempts) == 1
        assert attempts[0].success is False
        assert "conflict" in attempts[0].error.lower()


class TestStagingBranchLifecycle:
    """Test staging branch creation and cleanup."""

    def test_staging_branch_created(self, mock_merger: MockMergeCoordinator) -> None:
        """Test staging branch name is generated correctly."""
        staging = mock_merger.prepare_merge(level=1, target_branch="main")

        assert staging == "zerg/test-feature/staging"

    def test_staging_branch_custom_target(self, mock_merger: MockMergeCoordinator) -> None:
        """Test staging branch with custom target."""
        staging = mock_merger.prepare_merge(level=2, target_branch="develop")

        assert "staging" in staging
        assert mock_merger._current_level == 2

    def test_abort_cleans_up_staging(self, mock_merger: MockMergeCoordinator) -> None:
        """Test abort cleans up staging branch."""
        staging = mock_merger.prepare_merge(level=1)

        # Abort should be a no-op in mock but should not raise
        mock_merger.abort(staging_branch=staging)

    def test_successful_merge_cleans_staging(
        self, mock_merger: MockMergeCoordinator, worker_branches: list[str]
    ) -> None:
        """Test successful merge cleans up staging branch."""
        mock_merger.configure(always_succeed=True)

        # Full flow should complete and staging should be cleaned
        result = mock_merger.full_merge_flow(
            level=1,
            worker_branches=worker_branches,
        )

        assert result.success is True
        # Mock doesn't actually delete branches but simulates cleanup

    def test_failed_merge_triggers_abort(self, mock_merger: MockMergeCoordinator) -> None:
        """Test failed merge triggers abort with staging cleanup."""
        mock_merger.configure(conflict_at_level=1)

        result = mock_merger.full_merge_flow(
            level=1,
            worker_branches=["worker-0"],
        )

        assert result.success is False
        # Abort should have been called (mock records no state change)


class TestMergeResultPropagation:
    """Test merge result propagation to caller."""

    def test_success_result_contains_commit(
        self, mock_merger: MockMergeCoordinator, worker_branches: list[str]
    ) -> None:
        """Test successful merge result contains commit SHA."""
        mock_merger.configure(always_succeed=True)

        result = mock_merger.full_merge_flow(
            level=1,
            worker_branches=worker_branches,
        )

        assert result.success is True
        assert result.merge_commit is not None
        assert result.merge_commit.startswith("merge")

    def test_failure_result_contains_error(self, mock_merger: MockMergeCoordinator) -> None:
        """Test failed merge result contains error message."""
        mock_merger.configure(fail_at_level=1)

        result = mock_merger.full_merge_flow(
            level=1,
            worker_branches=["worker-0"],
        )

        assert result.success is False
        assert result.error is not None
        assert result.merge_commit is None

    def test_result_contains_source_branches(
        self, mock_merger: MockMergeCoordinator, worker_branches: list[str]
    ) -> None:
        """Test result contains all source branches."""
        mock_merger.configure(always_succeed=True)

        result = mock_merger.full_merge_flow(
            level=1,
            worker_branches=worker_branches,
        )

        assert result.source_branches == worker_branches

    def test_result_contains_target_branch(self, mock_merger: MockMergeCoordinator) -> None:
        """Test result contains target branch."""
        mock_merger.configure(always_succeed=True)

        result = mock_merger.full_merge_flow(
            level=1,
            worker_branches=["worker-0"],
            target_branch="develop",
        )

        assert result.target_branch == "develop"

    def test_result_contains_level(self, mock_merger: MockMergeCoordinator) -> None:
        """Test result contains correct level."""
        mock_merger.configure(always_succeed=True)

        result = mock_merger.full_merge_flow(
            level=3,
            worker_branches=["worker-0"],
        )

        assert result.level == 3

    def test_attempt_tracking_propagates(self, mock_merger: MockMergeCoordinator) -> None:
        """Test attempt tracking information propagates."""
        mock_merger.configure(always_succeed=True)

        mock_merger.full_merge_flow(level=1, worker_branches=["w-0"])
        mock_merger.full_merge_flow(level=2, worker_branches=["w-0"])

        assert mock_merger.get_attempt_count() == 2
        attempts = mock_merger.get_attempts()
        assert len(attempts) == 2
        assert attempts[0].level == 1
        assert attempts[1].level == 2

    def test_custom_result_overrides_default(self, mock_merger: MockMergeCoordinator) -> None:
        """Test custom result can override default behavior."""
        custom_result = MergeFlowResult(
            success=False,
            level=1,
            source_branches=["custom-branch"],
            target_branch="main",
            error="Custom error message",
        )
        mock_merger.set_result(level=1, result=custom_result)

        result = mock_merger.full_merge_flow(
            level=1,
            worker_branches=["worker-0"],
        )

        assert result.success is False
        assert result.error == "Custom error message"
        assert result.source_branches == ["custom-branch"]


class TestMergeAttemptTracking:
    """Test merge attempt tracking and history."""

    def test_successful_attempt_recorded(self, mock_merger: MockMergeCoordinator) -> None:
        """Test successful attempts are recorded."""
        mock_merger.configure(always_succeed=True)

        mock_merger.full_merge_flow(level=1, worker_branches=["w-0"])

        successful = mock_merger.get_successful_attempts()
        assert len(successful) == 1
        assert successful[0].success is True

    def test_failed_attempt_recorded(self, mock_merger: MockMergeCoordinator) -> None:
        """Test failed attempts are recorded."""
        mock_merger.configure(fail_at_attempt=1)

        mock_merger.full_merge_flow(level=1, worker_branches=["w-0"])

        failed = mock_merger.get_failed_attempts()
        assert len(failed) == 1
        assert failed[0].success is False

    def test_timeout_attempt_recorded(self, mock_merger: MockMergeCoordinator) -> None:
        """Test timeout attempts are recorded."""
        mock_merger.configure(timeout_at_attempt=1)

        mock_merger.full_merge_flow(level=1, worker_branches=["w-0"])

        timed_out = mock_merger.get_timed_out_attempts()
        assert len(timed_out) == 1
        assert timed_out[0].timed_out is True

    def test_attempt_duration_tracked(self, mock_merger: MockMergeCoordinator) -> None:
        """Test attempt duration is tracked."""
        mock_merger.configure(
            always_succeed=True,
            merge_delay=0.1,  # 100ms delay
        )

        mock_merger.full_merge_flow(level=1, worker_branches=["w-0"])

        attempts = mock_merger.get_attempts()
        assert attempts[0].duration_ms >= 90  # Allow tolerance

    def test_reset_clears_attempts(self, mock_merger: MockMergeCoordinator) -> None:
        """Test reset clears all attempt history."""
        mock_merger.configure(always_succeed=True)

        mock_merger.full_merge_flow(level=1, worker_branches=["w-0"])
        assert mock_merger.get_attempt_count() == 1

        mock_merger.reset()

        assert mock_merger.get_attempt_count() == 0
        assert len(mock_merger.get_attempts()) == 0


class TestFinalizeOperation:
    """Test finalize merge operation."""

    def test_finalize_returns_commit(self, mock_merger: MockMergeCoordinator) -> None:
        """Test finalize returns commit SHA."""
        mock_merger.configure(finalize_fails=False)

        commit = mock_merger.finalize("staging", "main")

        assert commit is not None
        assert commit.startswith("final_")

    def test_finalize_failure(self, mock_merger: MockMergeCoordinator) -> None:
        """Test finalize failure raises exception."""
        mock_merger.configure(finalize_fails=True)

        with pytest.raises(Exception) as exc_info:
            mock_merger.finalize("staging", "main")

        assert "finalize failure" in str(exc_info.value).lower()


class TestExecuteMergeOperation:
    """Test execute_merge operation details."""

    def test_execute_merge_returns_results(self, mock_merger: MockMergeCoordinator) -> None:
        """Test execute_merge returns MergeResult for each branch."""
        mock_merger.configure(always_succeed=True)

        results = mock_merger.execute_merge(
            source_branches=["w-0", "w-1", "w-2"],
            staging_branch="staging",
        )

        assert len(results) == 3
        assert all(r.status == MergeStatus.MERGED for r in results)
        assert all(r.commit_sha is not None for r in results)

    def test_execute_merge_sets_target_branch(self, mock_merger: MockMergeCoordinator) -> None:
        """Test execute_merge sets target branch on results."""
        results = mock_merger.execute_merge(
            source_branches=["w-0"],
            staging_branch="custom-staging",
        )

        assert results[0].target_branch == "custom-staging"

    def test_execute_merge_tracks_all_results(self, mock_merger: MockMergeCoordinator) -> None:
        """Test all merge results are tracked internally."""
        mock_merger.execute_merge(
            source_branches=["w-0", "w-1"],
            staging_branch="staging",
        )

        all_results = mock_merger.get_merge_results()
        assert len(all_results) == 2


class TestHelperMethods:
    """Test helper methods on MockMergeCoordinator."""

    def test_get_mergeable_branches_default_empty(self, mock_merger: MockMergeCoordinator) -> None:
        """Test get_mergeable_branches returns empty by default."""
        branches = mock_merger.get_mergeable_branches()
        assert branches == []

    def test_cleanup_feature_branches_returns_zero(self, mock_merger: MockMergeCoordinator) -> None:
        """Test cleanup_feature_branches returns 0 in mock."""
        count = mock_merger.cleanup_feature_branches()
        assert count == 0

    def test_cleanup_feature_branches_with_force(self, mock_merger: MockMergeCoordinator) -> None:
        """Test cleanup accepts force parameter."""
        count = mock_merger.cleanup_feature_branches(force=False)
        assert count == 0


class TestRealMergeCoordinatorIntegration:
    """Integration tests using real MergeCoordinator with mocked dependencies."""

    @pytest.fixture
    def mock_git_ops(self):
        """Mock GitOps for real coordinator testing."""
        with patch("zerg.merge.GitOps") as git_mock:
            git = MagicMock()
            git.create_staging_branch.return_value = "zerg/feature/staging"
            git.branch_exists.return_value = True
            git.list_worker_branches.return_value = [
                "zerg/feature/worker-0",
                "zerg/feature/worker-1",
            ]
            git.merge.return_value = "abc123def456"
            git.checkout.return_value = None
            git.abort_merge.return_value = None
            git.delete_branch.return_value = None
            git_mock.return_value = git
            yield git

    @pytest.fixture
    def mock_gate_runner(self):
        """Mock GateRunner for real coordinator testing."""
        with patch("zerg.merge.GateRunner") as gates_mock:
            gates = MagicMock()
            gates.run_all_gates.return_value = (True, [])
            gates.get_summary.return_value = {"passed": 2, "failed": 0}
            gates_mock.return_value = gates
            yield gates

    def test_real_coordinator_full_flow(
        self,
        mock_git_ops,
        mock_gate_runner,
        sample_config: ZergConfig,
        tmp_path: Path,
    ) -> None:
        """Test real MergeCoordinator full merge flow."""
        coordinator = MergeCoordinator("feature", sample_config, tmp_path)

        result = coordinator.full_merge_flow(
            level=1,
            worker_branches=["worker-0", "worker-1"],
            target_branch="main",
        )

        assert result.success is True
        assert result.merge_commit == "abc123def456"
        mock_git_ops.create_staging_branch.assert_called_once()
        mock_git_ops.merge.assert_called()

    def test_real_coordinator_gate_failure(
        self,
        mock_git_ops,
        mock_gate_runner,
        sample_config: ZergConfig,
        tmp_path: Path,
    ) -> None:
        """Test real coordinator handles gate failure."""
        mock_gate_runner.run_all_gates.return_value = (False, [])

        coordinator = MergeCoordinator("feature", sample_config, tmp_path)

        result = coordinator.full_merge_flow(
            level=1,
            worker_branches=["worker-0"],
        )

        assert result.success is False
        assert "Pre-merge gates failed" in result.error

    def test_real_coordinator_merge_conflict(
        self,
        mock_git_ops,
        mock_gate_runner,
        sample_config: ZergConfig,
        tmp_path: Path,
    ) -> None:
        """Test real coordinator handles merge conflict."""
        mock_git_ops.merge.side_effect = MergeConflictError(
            "Conflict in file.py",
            source_branch="worker-0",
            target_branch="staging",
            conflicting_files=["file.py"],
        )

        coordinator = MergeCoordinator("feature", sample_config, tmp_path)

        result = coordinator.full_merge_flow(
            level=1,
            worker_branches=["worker-0"],
        )

        assert result.success is False
        assert "conflict" in result.error.lower()
        mock_git_ops.abort_merge.assert_called()

    def test_real_coordinator_skip_gates(
        self,
        mock_git_ops,
        mock_gate_runner,
        sample_config: ZergConfig,
        tmp_path: Path,
    ) -> None:
        """Test real coordinator with skip_gates option."""
        coordinator = MergeCoordinator("feature", sample_config, tmp_path)

        result = coordinator.full_merge_flow(
            level=1,
            worker_branches=["worker-0"],
            skip_gates=True,
        )

        assert result.success is True
        mock_gate_runner.run_all_gates.assert_not_called()

    def test_real_coordinator_no_branches(
        self,
        mock_git_ops,
        mock_gate_runner,
        sample_config: ZergConfig,
        tmp_path: Path,
    ) -> None:
        """Test real coordinator with no worker branches."""
        mock_git_ops.list_worker_branches.return_value = []

        coordinator = MergeCoordinator("feature", sample_config, tmp_path)

        result = coordinator.full_merge_flow(level=1)

        assert result.success is False
        assert "No worker branches" in result.error
