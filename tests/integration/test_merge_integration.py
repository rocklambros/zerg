"""Integration tests for complete merge workflow.

Tests the full merge flow end-to-end using MockMergeCoordinator,
covering gate pass/fail integration, conflict handling, staging branch
lifecycle, and merge result propagation.
"""

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

    def test_merge_flow_with_empty_branches(self, mock_merger: MockMergeCoordinator) -> None:
        """Test merge flow handles empty branch list."""
        mock_merger.configure(always_succeed=True)

        result = mock_merger.full_merge_flow(
            level=1,
            worker_branches=[],
            target_branch="main",
        )

        assert result.source_branches == []


class TestMergeWithGateIntegration:
    """Test merge flow with gate pass/fail integration."""

    def test_pre_merge_gate_pass_allows_merge(
        self, mock_merger: MockMergeCoordinator, worker_branches: list[str]
    ) -> None:
        """Test merge proceeds when pre-merge gates pass."""
        mock_merger.configure(
            always_succeed=True,
            pre_merge_gate_failure_levels=[],
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

    def test_gate_failure_at_specific_level(self, mock_merger: MockMergeCoordinator) -> None:
        """Test gate failure only at specific level."""
        mock_merger.configure(
            gate_failure_levels=[2],
        )

        result1 = mock_merger.full_merge_flow(
            level=1,
            worker_branches=["worker-0"],
        )
        assert result1.success is True

        result2 = mock_merger.full_merge_flow(
            level=2,
            worker_branches=["worker-0"],
        )
        assert result2.success is False
        assert "gates failed" in result2.error.lower()


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


class TestStagingBranchLifecycle:
    """Test staging branch creation and cleanup."""

    def test_staging_branch_created(self, mock_merger: MockMergeCoordinator) -> None:
        """Test staging branch name is generated correctly."""
        staging = mock_merger.prepare_merge(level=1, target_branch="main")

        assert staging == "zerg/test-feature/staging"

    def test_abort_cleans_up_staging(self, mock_merger: MockMergeCoordinator) -> None:
        """Test abort cleans up staging branch."""
        staging = mock_merger.prepare_merge(level=1)

        mock_merger.abort(staging_branch=staging)


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

    @pytest.mark.parametrize(
        "config_kwargs,check_attr,check_field",
        [
            ({"always_succeed": True}, "get_successful_attempts", "success"),
            ({"fail_at_attempt": 1}, "get_failed_attempts", "success"),
            ({"timeout_at_attempt": 1}, "get_timed_out_attempts", "timed_out"),
        ],
        ids=["successful", "failed", "timeout"],
    )
    def test_attempt_recorded(
        self, mock_merger: MockMergeCoordinator, config_kwargs: dict, check_attr: str, check_field: str
    ) -> None:
        """Test that attempts of various types are recorded."""
        mock_merger.configure(**config_kwargs)

        mock_merger.full_merge_flow(level=1, worker_branches=["w-0"])

        results = getattr(mock_merger, check_attr)()
        assert len(results) == 1

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


class TestHelperMethods:
    """Test helper methods on MockMergeCoordinator."""

    def test_get_mergeable_branches_default_empty(self, mock_merger: MockMergeCoordinator) -> None:
        """Test get_mergeable_branches returns empty by default."""
        branches = mock_merger.get_mergeable_branches()
        assert branches == []


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
