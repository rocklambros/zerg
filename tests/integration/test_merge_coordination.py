"""Integration tests for ZERG merge coordination (TC-012).

Tests the MergeCoordinator with mocked git operations.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.config import QualityGate, ZergConfig
from zerg.constants import MergeStatus
from zerg.exceptions import MergeConflictError
from zerg.merge import MergeCoordinator, MergeFlowResult


@pytest.fixture
def sample_config() -> ZergConfig:
    """Create sample configuration."""
    config = ZergConfig()
    config.quality_gates = [
        QualityGate(name="lint", command="echo lint", required=True),
        QualityGate(name="test", command="echo test", required=True),
    ]
    return config


@pytest.fixture
def mock_git_ops():
    """Mock GitOps for testing."""
    with patch("zerg.merge.GitOps") as git_mock:
        git = MagicMock()
        git.create_staging_branch.return_value = "zerg/test-feature/staging-1"
        git.branch_exists.return_value = True
        git.list_worker_branches.return_value = ["zerg/test-feature/worker-0", "zerg/test-feature/worker-1"]
        git.merge.return_value = "abc123def456"
        git.checkout.return_value = None
        git.abort_merge.return_value = None
        git.delete_branch.return_value = None
        git.delete_feature_branches.return_value = 2
        git_mock.return_value = git
        yield git


@pytest.fixture
def mock_gates():
    """Mock GateRunner for testing."""
    with patch("zerg.merge.GateRunner") as gates_mock:
        gates = MagicMock()
        gates.run_all_gates.return_value = (True, [])
        gates.get_summary.return_value = {"passed": 2, "failed": 0}
        gates_mock.return_value = gates
        yield gates


class TestMergeCoordinatorInit:
    """Tests for MergeCoordinator initialization."""

    def test_init(self, mock_git_ops, mock_gates, sample_config, tmp_path: Path) -> None:
        """Test coordinator initialization."""
        coordinator = MergeCoordinator("test-feature", sample_config, tmp_path)

        assert coordinator.feature == "test-feature"
        assert coordinator.repo_path == tmp_path

    def test_init_default_config(self, mock_git_ops, mock_gates, tmp_path: Path) -> None:
        """Test initialization with default config."""
        with patch.object(ZergConfig, "load") as load_mock:
            load_mock.return_value = ZergConfig()

            coordinator = MergeCoordinator("test-feature", repo_path=tmp_path)

            assert coordinator.config is not None


class TestPrepareMerge:
    """Tests for merge preparation."""

    def test_prepare_merge_creates_staging(self, mock_git_ops, mock_gates, sample_config, tmp_path: Path) -> None:
        """Test prepare_merge creates staging branch."""
        coordinator = MergeCoordinator("test-feature", sample_config, tmp_path)

        staging = coordinator.prepare_merge(level=1)

        assert staging == "zerg/test-feature/staging-1"
        mock_git_ops.create_staging_branch.assert_called_with("test-feature", "main")

    def test_prepare_merge_custom_target(self, mock_git_ops, mock_gates, sample_config, tmp_path: Path) -> None:
        """Test prepare_merge with custom target branch."""
        coordinator = MergeCoordinator("test-feature", sample_config, tmp_path)

        coordinator.prepare_merge(level=1, target_branch="develop")

        mock_git_ops.create_staging_branch.assert_called_with("test-feature", "develop")


class TestPreMergeGates:
    """Tests for pre-merge quality gates."""

    def test_run_pre_merge_gates_pass(self, mock_git_ops, mock_gates, sample_config, tmp_path: Path) -> None:
        """Test pre-merge gates passing."""
        coordinator = MergeCoordinator("test-feature", sample_config, tmp_path)

        passed, results = coordinator.run_pre_merge_gates()

        assert passed is True
        mock_gates.run_all_gates.assert_called()

    def test_run_pre_merge_gates_fail(self, mock_git_ops, mock_gates, sample_config, tmp_path: Path) -> None:
        """Test pre-merge gates failing."""
        mock_gates.run_all_gates.return_value = (False, [])

        coordinator = MergeCoordinator("test-feature", sample_config, tmp_path)

        passed, results = coordinator.run_pre_merge_gates()

        assert passed is False

    def test_run_pre_merge_gates_with_cwd(self, mock_git_ops, mock_gates, sample_config, tmp_path: Path) -> None:
        """Test pre-merge gates with custom cwd."""
        coordinator = MergeCoordinator("test-feature", sample_config, tmp_path)

        coordinator.run_pre_merge_gates(cwd=tmp_path / "subdir")

        mock_gates.run_all_gates.assert_called_with(
            gates=sample_config.quality_gates,
            cwd=tmp_path / "subdir",
            required_only=True,
        )


class TestExecuteMerge:
    """Tests for merge execution."""

    def test_execute_merge_success(self, mock_git_ops, mock_gates, sample_config, tmp_path: Path) -> None:
        """Test successful merge execution."""
        coordinator = MergeCoordinator("test-feature", sample_config, tmp_path)
        source_branches = ["zerg/test/worker-0", "zerg/test/worker-1"]

        results = coordinator.execute_merge(source_branches, "staging")

        assert len(results) == 2
        assert all(r.status == MergeStatus.MERGED for r in results)

    def test_execute_merge_checkouts_staging(self, mock_git_ops, mock_gates, sample_config, tmp_path: Path) -> None:
        """Test merge checks out staging branch."""
        coordinator = MergeCoordinator("test-feature", sample_config, tmp_path)

        coordinator.execute_merge(["branch1"], "staging")

        mock_git_ops.checkout.assert_called_with("staging")

    def test_execute_merge_conflict_raises(self, mock_git_ops, mock_gates, sample_config, tmp_path: Path) -> None:
        """Test merge conflict raises exception."""
        mock_git_ops.merge.side_effect = MergeConflictError(
            "Merge conflict",
            source_branch="worker-0",
            target_branch="staging",
            conflicting_files=["src/auth.py"],
        )

        coordinator = MergeCoordinator("test-feature", sample_config, tmp_path)

        with pytest.raises(MergeConflictError):
            coordinator.execute_merge(["worker-0"], "staging")


class TestPostMergeGates:
    """Tests for post-merge quality gates."""

    def test_run_post_merge_gates(self, mock_git_ops, mock_gates, sample_config, tmp_path: Path) -> None:
        """Test running post-merge gates."""
        coordinator = MergeCoordinator("test-feature", sample_config, tmp_path)

        passed, results = coordinator.run_post_merge_gates()

        assert passed is True
        mock_gates.run_all_gates.assert_called()


class TestFinalize:
    """Tests for merge finalization."""

    def test_finalize_merges_to_target(self, mock_git_ops, mock_gates, sample_config, tmp_path: Path) -> None:
        """Test finalize merges staging to target."""
        coordinator = MergeCoordinator("test-feature", sample_config, tmp_path)

        commit = coordinator.finalize("staging", "main")

        mock_git_ops.checkout.assert_called_with("main")
        mock_git_ops.merge.assert_called_with(
            "staging",
            message="ZERG: Complete level merge from staging",
        )
        assert commit == "abc123def456"


class TestAbort:
    """Tests for aborting merge."""

    def test_abort_calls_git_abort(self, mock_git_ops, mock_gates, sample_config, tmp_path: Path) -> None:
        """Test abort calls git abort."""
        coordinator = MergeCoordinator("test-feature", sample_config, tmp_path)

        coordinator.abort()

        mock_git_ops.abort_merge.assert_called()

    def test_abort_deletes_staging_branch(self, mock_git_ops, mock_gates, sample_config, tmp_path: Path) -> None:
        """Test abort deletes staging branch."""
        coordinator = MergeCoordinator("test-feature", sample_config, tmp_path)

        coordinator.abort(staging_branch="staging")

        mock_git_ops.delete_branch.assert_called_with("staging", force=True)


class TestFullMergeFlow:
    """Tests for complete merge flow."""

    def test_full_merge_flow_success(self, mock_git_ops, mock_gates, sample_config, tmp_path: Path) -> None:
        """Test successful full merge flow."""
        coordinator = MergeCoordinator("test-feature", sample_config, tmp_path)

        result = coordinator.full_merge_flow(
            level=1,
            worker_branches=["worker-0", "worker-1"],
            target_branch="main",
        )

        assert result.success is True
        assert result.level == 1
        assert result.merge_commit == "abc123def456"

    def test_full_merge_flow_no_branches(self, mock_git_ops, mock_gates, sample_config, tmp_path: Path) -> None:
        """Test merge flow with no branches."""
        mock_git_ops.list_worker_branches.return_value = []

        coordinator = MergeCoordinator("test-feature", sample_config, tmp_path)

        result = coordinator.full_merge_flow(level=1)

        assert result.success is False
        assert "No worker branches" in result.error

    def test_full_merge_flow_auto_detect_branches(
        self, mock_git_ops, mock_gates, sample_config, tmp_path: Path
    ) -> None:
        """Test merge flow auto-detects branches."""
        coordinator = MergeCoordinator("test-feature", sample_config, tmp_path)

        coordinator.full_merge_flow(level=1)

        mock_git_ops.list_worker_branches.assert_called_with("test-feature")

    def test_full_merge_flow_pre_gates_fail(self, mock_git_ops, mock_gates, sample_config, tmp_path: Path) -> None:
        """Test merge flow fails on pre-merge gates."""
        mock_gates.run_all_gates.return_value = (False, [])

        coordinator = MergeCoordinator("test-feature", sample_config, tmp_path)

        result = coordinator.full_merge_flow(
            level=1,
            worker_branches=["worker-0"],
        )

        assert result.success is False
        assert "Pre-merge gates failed" in result.error

    def test_full_merge_flow_post_gates_fail(self, mock_git_ops, mock_gates, sample_config, tmp_path: Path) -> None:
        """Test merge flow fails on post-merge gates."""
        # First call (pre-merge) passes, second (post-merge) fails
        mock_gates.run_all_gates.side_effect = [(True, []), (False, [])]

        coordinator = MergeCoordinator("test-feature", sample_config, tmp_path)

        result = coordinator.full_merge_flow(
            level=1,
            worker_branches=["worker-0"],
        )

        assert result.success is False
        assert "Post-merge gates failed" in result.error
        mock_git_ops.abort_merge.assert_called()

    def test_full_merge_flow_conflict(self, mock_git_ops, mock_gates, sample_config, tmp_path: Path) -> None:
        """Test merge flow handles conflict."""
        mock_git_ops.merge.side_effect = MergeConflictError(
            "Conflict",
            source_branch="worker-0",
            target_branch="staging",
            conflicting_files=["src/auth.py"],
        )

        coordinator = MergeCoordinator("test-feature", sample_config, tmp_path)

        result = coordinator.full_merge_flow(
            level=1,
            worker_branches=["worker-0"],
        )

        assert result.success is False
        assert "conflict" in result.error.lower()

    def test_full_merge_flow_skip_gates(self, mock_git_ops, mock_gates, sample_config, tmp_path: Path) -> None:
        """Test merge flow with gates skipped."""
        coordinator = MergeCoordinator("test-feature", sample_config, tmp_path)

        result = coordinator.full_merge_flow(
            level=1,
            worker_branches=["worker-0"],
            skip_gates=True,
        )

        assert result.success is True
        mock_gates.run_all_gates.assert_not_called()

    def test_full_merge_flow_cleans_staging(self, mock_git_ops, mock_gates, sample_config, tmp_path: Path) -> None:
        """Test successful merge cleans up staging branch."""
        coordinator = MergeCoordinator("test-feature", sample_config, tmp_path)

        coordinator.full_merge_flow(
            level=1,
            worker_branches=["worker-0"],
        )

        # Staging branch should be deleted
        mock_git_ops.delete_branch.assert_called()


class TestMergeFlowResult:
    """Tests for MergeFlowResult dataclass."""

    def test_to_dict(self) -> None:
        """Test converting result to dictionary."""
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["worker-0", "worker-1"],
            target_branch="main",
            merge_commit="abc123",
        )

        data = result.to_dict()

        assert data["success"] is True
        assert data["level"] == 1
        assert data["source_branches"] == ["worker-0", "worker-1"]
        assert data["target_branch"] == "main"
        assert data["merge_commit"] == "abc123"
        assert "timestamp" in data


class TestHelperMethods:
    """Tests for helper methods."""

    def test_get_mergeable_branches(self, mock_git_ops, mock_gates, sample_config, tmp_path: Path) -> None:
        """Test getting mergeable branches."""
        mock_git_ops.list_worker_branches.return_value = ["worker-0", "worker-1"]

        coordinator = MergeCoordinator("test-feature", sample_config, tmp_path)

        branches = coordinator.get_mergeable_branches()

        assert branches == ["worker-0", "worker-1"]

    def test_cleanup_feature_branches(self, mock_git_ops, mock_gates, sample_config, tmp_path: Path) -> None:
        """Test cleaning up feature branches."""
        mock_git_ops.delete_feature_branches.return_value = 3

        coordinator = MergeCoordinator("test-feature", sample_config, tmp_path)

        count = coordinator.cleanup_feature_branches()

        assert count == 3
        mock_git_ops.delete_feature_branches.assert_called_with("test-feature", force=True)
