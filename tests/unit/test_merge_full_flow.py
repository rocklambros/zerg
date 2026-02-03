"""Unit tests for MergeCoordinator full_merge_flow and finalize operations.

Tests comprehensive merge workflow including:
- Full merge flow success path
- Gate failures (pre-merge and post-merge)
- Merge conflict handling
- Finalize merge to target branch
- MergeFlowResult structure validation
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from zerg.config import QualityGate, ZergConfig
from zerg.constants import GateResult
from zerg.exceptions import MergeConflictError
from zerg.merge import MergeCoordinator, MergeFlowResult
from zerg.types import GateRunResult


class TestMergeFlowResultDataclass:
    """Tests for MergeFlowResult dataclass structure and methods."""

    def test_merge_flow_result_creation_success(self):
        """MergeFlowResult should store success data correctly."""
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["worker-0", "worker-1"],
            target_branch="main",
            merge_commit="abc123def",
        )

        assert result.success is True
        assert result.level == 1
        assert result.source_branches == ["worker-0", "worker-1"]
        assert result.target_branch == "main"
        assert result.merge_commit == "abc123def"
        assert result.error is None
        assert result.gate_results == []
        assert isinstance(result.timestamp, datetime)

    def test_merge_flow_result_creation_failure(self):
        """MergeFlowResult should store failure data correctly."""
        result = MergeFlowResult(
            success=False,
            level=2,
            source_branches=["worker-0"],
            target_branch="develop",
            error="Pre-merge gates failed",
        )

        assert result.success is False
        assert result.level == 2
        assert result.error == "Pre-merge gates failed"
        assert result.merge_commit is None

    def test_merge_flow_result_with_gate_results(self):
        """MergeFlowResult should include gate results."""
        gate_result = GateRunResult(
            gate_name="lint",
            result=GateResult.PASS,
            command="ruff check .",
            exit_code=0,
            stdout="All checks passed",
            stderr="",
            duration_ms=500,
        )

        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["worker-0"],
            target_branch="main",
            merge_commit="abc123",
            gate_results=[gate_result],
        )

        assert len(result.gate_results) == 1
        assert result.gate_results[0].gate_name == "lint"
        assert result.gate_results[0].result == GateResult.PASS

    def test_merge_flow_result_to_dict(self):
        """MergeFlowResult.to_dict() should return proper dictionary."""
        gate_result = GateRunResult(
            gate_name="test",
            result=GateResult.FAIL,
            command="pytest",
            exit_code=1,
            duration_ms=1000,
        )

        result = MergeFlowResult(
            success=False,
            level=3,
            source_branches=["branch-1", "branch-2"],
            target_branch="main",
            gate_results=[gate_result],
            error="Tests failed",
        )

        result_dict = result.to_dict()

        assert result_dict["success"] is False
        assert result_dict["level"] == 3
        assert result_dict["source_branches"] == ["branch-1", "branch-2"]
        assert result_dict["target_branch"] == "main"
        assert result_dict["error"] == "Tests failed"
        assert result_dict["merge_commit"] is None
        assert len(result_dict["gate_results"]) == 1
        assert "timestamp" in result_dict
        # Timestamp should be ISO format string
        assert isinstance(result_dict["timestamp"], str)


class TestFullMergeFlowSuccess:
    """Tests for full_merge_flow success scenarios."""

    @pytest.fixture
    def mock_git_ops(self):
        """Create mock GitOps instance."""
        mock = MagicMock()
        mock.list_worker_branches.return_value = ["worker-0", "worker-1"]
        mock.create_staging_branch.return_value = "zerg/test-feature/staging"
        mock.checkout.return_value = None
        mock.merge.return_value = "merge_commit_sha"
        mock.branch_exists.return_value = True
        mock.delete_branch.return_value = None
        mock.abort_merge.return_value = None
        return mock

    @pytest.fixture
    def mock_gate_runner(self):
        """Create mock GateRunner that passes all gates."""
        mock = MagicMock()
        passed_result = GateRunResult(
            gate_name="lint",
            result=GateResult.PASS,
            command="echo pass",
            exit_code=0,
            duration_ms=100,
        )
        mock.run_all_gates.return_value = (True, [passed_result])
        mock.get_summary.return_value = {"passed": 1, "failed": 0}
        return mock

    @pytest.fixture
    def sample_config(self):
        """Create a sample configuration."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="lint", command="echo lint", required=True),
        ]
        return config

    def test_full_merge_flow_success_with_explicit_branches(
        self, mock_git_ops, mock_gate_runner, sample_config, tmp_path
    ):
        """Full merge flow should succeed with explicit worker branches."""
        with (
            patch("zerg.merge.GitOps", return_value=mock_git_ops),
            patch("zerg.merge.GateRunner", return_value=mock_gate_runner),
        ):
            coordinator = MergeCoordinator(
                feature="test-feature",
                config=sample_config,
                repo_path=tmp_path,
            )

            result = coordinator.full_merge_flow(
                level=1,
                worker_branches=["worker-0", "worker-1"],
                target_branch="main",
            )

            assert result.success is True
            assert result.level == 1
            assert result.source_branches == ["worker-0", "worker-1"]
            assert result.target_branch == "main"
            assert result.merge_commit is not None
            assert result.error is None

    def test_full_merge_flow_auto_detects_branches(self, mock_git_ops, mock_gate_runner, sample_config, tmp_path):
        """Full merge flow should auto-detect worker branches when not provided."""
        mock_git_ops.list_worker_branches.return_value = ["auto-worker-0", "auto-worker-1"]

        with (
            patch("zerg.merge.GitOps", return_value=mock_git_ops),
            patch("zerg.merge.GateRunner", return_value=mock_gate_runner),
        ):
            coordinator = MergeCoordinator(
                feature="test-feature",
                config=sample_config,
                repo_path=tmp_path,
            )

            result = coordinator.full_merge_flow(
                level=1,
                worker_branches=None,  # Auto-detect
                target_branch="main",
            )

            assert result.success is True
            assert result.source_branches == ["auto-worker-0", "auto-worker-1"]
            mock_git_ops.list_worker_branches.assert_called_once_with("test-feature")

    def test_full_merge_flow_skips_gates_when_requested(self, mock_git_ops, mock_gate_runner, sample_config, tmp_path):
        """Full merge flow should skip gates when skip_gates=True."""
        with (
            patch("zerg.merge.GitOps", return_value=mock_git_ops),
            patch("zerg.merge.GateRunner", return_value=mock_gate_runner),
        ):
            coordinator = MergeCoordinator(
                feature="test-feature",
                config=sample_config,
                repo_path=tmp_path,
            )

            result = coordinator.full_merge_flow(
                level=1,
                worker_branches=["worker-0"],
                target_branch="main",
                skip_gates=True,
            )

            assert result.success is True
            assert result.gate_results == []
            # Gate runner should not be called
            mock_gate_runner.run_all_gates.assert_not_called()

    def test_full_merge_flow_returns_empty_branches_error(
        self, mock_git_ops, mock_gate_runner, sample_config, tmp_path
    ):
        """Full merge flow should fail when no worker branches found."""
        mock_git_ops.list_worker_branches.return_value = []

        with (
            patch("zerg.merge.GitOps", return_value=mock_git_ops),
            patch("zerg.merge.GateRunner", return_value=mock_gate_runner),
        ):
            coordinator = MergeCoordinator(
                feature="test-feature",
                config=sample_config,
                repo_path=tmp_path,
            )

            result = coordinator.full_merge_flow(
                level=1,
                worker_branches=None,  # Will auto-detect to empty
                target_branch="main",
            )

            assert result.success is False
            assert result.error == "No worker branches found"
            assert result.source_branches == []


class TestFullMergeFlowGateFailures:
    """Tests for full_merge_flow with gate failures."""

    @pytest.fixture
    def mock_git_ops(self):
        """Create mock GitOps instance."""
        mock = MagicMock()
        mock.create_staging_branch.return_value = "zerg/test-feature/staging"
        mock.checkout.return_value = None
        mock.merge.return_value = "merge_commit_sha"
        mock.branch_exists.return_value = True
        mock.delete_branch.return_value = None
        mock.abort_merge.return_value = None
        return mock

    @pytest.fixture
    def sample_config(self):
        """Create a sample configuration."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="lint", command="ruff check", required=True),
            QualityGate(name="test", command="pytest", required=True),
        ]
        return config

    def test_full_merge_flow_fails_on_pre_merge_gate_failure(self, mock_git_ops, sample_config, tmp_path):
        """Full merge flow should fail when pre-merge gates fail."""
        mock_gate_runner = MagicMock()
        failed_result = GateRunResult(
            gate_name="lint",
            result=GateResult.FAIL,
            command="ruff check",
            exit_code=1,
            stdout="",
            stderr="Lint errors found",
            duration_ms=200,
        )
        mock_gate_runner.run_all_gates.return_value = (False, [failed_result])
        mock_gate_runner.get_summary.return_value = {"passed": 0, "failed": 1}

        with (
            patch("zerg.merge.GitOps", return_value=mock_git_ops),
            patch("zerg.merge.GateRunner", return_value=mock_gate_runner),
        ):
            coordinator = MergeCoordinator(
                feature="test-feature",
                config=sample_config,
                repo_path=tmp_path,
            )

            result = coordinator.full_merge_flow(
                level=1,
                worker_branches=["worker-0"],
                target_branch="main",
            )

            assert result.success is False
            assert result.error == "Pre-merge gates failed"
            assert len(result.gate_results) == 1
            assert result.gate_results[0].result == GateResult.FAIL
            # Should not have attempted merge
            mock_git_ops.merge.assert_not_called()

    def test_full_merge_flow_fails_on_post_merge_gate_failure(self, mock_git_ops, sample_config, tmp_path):
        """Full merge flow should fail when post-merge gates fail."""
        mock_gate_runner = MagicMock()

        # Pre-merge passes
        pre_merge_result = GateRunResult(
            gate_name="lint",
            result=GateResult.PASS,
            command="ruff check",
            exit_code=0,
            duration_ms=100,
        )

        # Post-merge fails
        post_merge_result = GateRunResult(
            gate_name="test",
            result=GateResult.FAIL,
            command="pytest",
            exit_code=1,
            stdout="",
            stderr="Test failures",
            duration_ms=500,
        )

        # First call (pre-merge) passes, second call (post-merge) fails
        mock_gate_runner.run_all_gates.side_effect = [
            (True, [pre_merge_result]),
            (False, [post_merge_result]),
        ]
        mock_gate_runner.get_summary.return_value = {"passed": 1, "failed": 1}

        with (
            patch("zerg.merge.GitOps", return_value=mock_git_ops),
            patch("zerg.merge.GateRunner", return_value=mock_gate_runner),
        ):
            coordinator = MergeCoordinator(
                feature="test-feature",
                config=sample_config,
                repo_path=tmp_path,
            )

            result = coordinator.full_merge_flow(
                level=1,
                worker_branches=["worker-0"],
                target_branch="main",
            )

            assert result.success is False
            assert result.error == "Post-merge gates failed"
            assert len(result.gate_results) == 2
            # Abort should have been called to clean up
            mock_git_ops.abort_merge.assert_called()

    def test_full_merge_flow_gate_results_accumulate(self, mock_git_ops, sample_config, tmp_path):
        """Gate results from both pre and post merge should accumulate."""
        mock_gate_runner = MagicMock()

        pre_merge_result = GateRunResult(
            gate_name="lint",
            result=GateResult.PASS,
            command="ruff",
            exit_code=0,
            duration_ms=100,
        )

        post_merge_result = GateRunResult(
            gate_name="test",
            result=GateResult.PASS,
            command="pytest",
            exit_code=0,
            duration_ms=500,
        )

        mock_gate_runner.run_all_gates.side_effect = [
            (True, [pre_merge_result]),
            (True, [post_merge_result]),
        ]
        mock_gate_runner.get_summary.return_value = {"passed": 2, "failed": 0}

        with (
            patch("zerg.merge.GitOps", return_value=mock_git_ops),
            patch("zerg.merge.GateRunner", return_value=mock_gate_runner),
        ):
            coordinator = MergeCoordinator(
                feature="test-feature",
                config=sample_config,
                repo_path=tmp_path,
            )

            result = coordinator.full_merge_flow(
                level=1,
                worker_branches=["worker-0"],
                target_branch="main",
            )

            assert result.success is True
            assert len(result.gate_results) == 2
            assert result.gate_results[0].gate_name == "lint"
            assert result.gate_results[1].gate_name == "test"


class TestFullMergeFlowMergeConflicts:
    """Tests for full_merge_flow with merge conflicts."""

    @pytest.fixture
    def mock_git_ops_with_conflict(self):
        """Create mock GitOps that raises MergeConflictError."""
        mock = MagicMock()
        mock.create_staging_branch.return_value = "zerg/test-feature/staging"
        mock.checkout.return_value = None
        mock.branch_exists.return_value = True
        mock.delete_branch.return_value = None
        mock.abort_merge.return_value = None

        # First merge succeeds, second causes conflict
        conflict = MergeConflictError(
            message="Merge conflict detected",
            source_branch="worker-1",
            target_branch="zerg/test-feature/staging",
            conflicting_files=["src/models.py", "src/utils.py"],
        )
        mock.merge.side_effect = ["first_merge_sha", conflict]
        return mock

    @pytest.fixture
    def mock_gate_runner(self):
        """Create mock GateRunner that passes all gates."""
        mock = MagicMock()
        passed_result = GateRunResult(
            gate_name="lint",
            result=GateResult.PASS,
            command="echo pass",
            exit_code=0,
            duration_ms=100,
        )
        mock.run_all_gates.return_value = (True, [passed_result])
        mock.get_summary.return_value = {"passed": 1, "failed": 0}
        return mock

    @pytest.fixture
    def sample_config(self):
        """Create a sample configuration."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="lint", command="echo lint", required=True),
        ]
        return config

    def test_full_merge_flow_handles_merge_conflict(
        self, mock_git_ops_with_conflict, mock_gate_runner, sample_config, tmp_path
    ):
        """Full merge flow should handle merge conflicts gracefully."""
        with (
            patch("zerg.merge.GitOps", return_value=mock_git_ops_with_conflict),
            patch("zerg.merge.GateRunner", return_value=mock_gate_runner),
        ):
            coordinator = MergeCoordinator(
                feature="test-feature",
                config=sample_config,
                repo_path=tmp_path,
            )

            result = coordinator.full_merge_flow(
                level=1,
                worker_branches=["worker-0", "worker-1"],
                target_branch="main",
            )

            assert result.success is False
            assert "conflict" in result.error.lower()
            assert "src/models.py" in result.error or "src/utils.py" in result.error
            # Abort should be called to clean up
            mock_git_ops_with_conflict.abort_merge.assert_called()

    def test_full_merge_flow_conflict_returns_correct_level(
        self, mock_git_ops_with_conflict, mock_gate_runner, sample_config, tmp_path
    ):
        """MergeFlowResult should have correct level on conflict."""
        with (
            patch("zerg.merge.GitOps", return_value=mock_git_ops_with_conflict),
            patch("zerg.merge.GateRunner", return_value=mock_gate_runner),
        ):
            coordinator = MergeCoordinator(
                feature="test-feature",
                config=sample_config,
                repo_path=tmp_path,
            )

            result = coordinator.full_merge_flow(
                level=3,
                worker_branches=["worker-0", "worker-1"],
                target_branch="main",
            )

            assert result.level == 3
            assert result.source_branches == ["worker-0", "worker-1"]
            assert result.target_branch == "main"

    def test_full_merge_flow_single_branch_conflict(self, sample_config, tmp_path):
        """Full merge flow should handle conflict on single branch merge."""
        mock_git_ops = MagicMock()
        mock_git_ops.create_staging_branch.return_value = "zerg/test-feature/staging"
        mock_git_ops.checkout.return_value = None
        mock_git_ops.branch_exists.return_value = True
        mock_git_ops.abort_merge.return_value = None

        conflict = MergeConflictError(
            message="Conflict in single branch",
            source_branch="worker-0",
            target_branch="staging",
            conflicting_files=["config.yaml"],
        )
        mock_git_ops.merge.side_effect = conflict

        mock_gate_runner = MagicMock()
        mock_gate_runner.run_all_gates.return_value = (True, [])
        mock_gate_runner.get_summary.return_value = {"passed": 0, "failed": 0}

        with (
            patch("zerg.merge.GitOps", return_value=mock_git_ops),
            patch("zerg.merge.GateRunner", return_value=mock_gate_runner),
        ):
            coordinator = MergeCoordinator(
                feature="test-feature",
                config=sample_config,
                repo_path=tmp_path,
            )

            result = coordinator.full_merge_flow(
                level=1,
                worker_branches=["worker-0"],
                target_branch="main",
            )

            assert result.success is False
            assert "conflict" in result.error.lower()


class TestFinalizeMerge:
    """Tests for finalize merge operation."""

    @pytest.fixture
    def mock_git_ops(self):
        """Create mock GitOps instance."""
        mock = MagicMock()
        mock.checkout.return_value = None
        mock.merge.return_value = "final_merge_commit_sha"
        return mock

    @pytest.fixture
    def sample_config(self):
        """Create a sample configuration."""
        return ZergConfig()

    def test_finalize_merges_staging_to_target(self, mock_git_ops, sample_config, tmp_path):
        """Finalize should merge staging branch into target branch."""
        with patch("zerg.merge.GitOps", return_value=mock_git_ops), patch("zerg.merge.GateRunner"):
            coordinator = MergeCoordinator(
                feature="test-feature",
                config=sample_config,
                repo_path=tmp_path,
            )

            commit = coordinator.finalize(
                staging_branch="zerg/test-feature/staging",
                target_branch="main",
            )

            assert commit == "final_merge_commit_sha"
            mock_git_ops.checkout.assert_called_with("main")
            mock_git_ops.merge.assert_called_once()
            call_args = mock_git_ops.merge.call_args
            assert call_args[0][0] == "zerg/test-feature/staging"

    def test_finalize_uses_correct_commit_message(self, mock_git_ops, sample_config, tmp_path):
        """Finalize should use ZERG-specific commit message."""
        with patch("zerg.merge.GitOps", return_value=mock_git_ops), patch("zerg.merge.GateRunner"):
            coordinator = MergeCoordinator(
                feature="test-feature",
                config=sample_config,
                repo_path=tmp_path,
            )

            coordinator.finalize(
                staging_branch="zerg/test-feature/staging",
                target_branch="main",
            )

            call_args = mock_git_ops.merge.call_args
            message = call_args[1]["message"]
            assert "ZERG" in message
            assert "staging" in message.lower()

    def test_finalize_to_different_target_branches(self, mock_git_ops, sample_config, tmp_path):
        """Finalize should work with different target branches."""
        with patch("zerg.merge.GitOps", return_value=mock_git_ops), patch("zerg.merge.GateRunner"):
            coordinator = MergeCoordinator(
                feature="test-feature",
                config=sample_config,
                repo_path=tmp_path,
            )

            # Test with develop branch
            coordinator.finalize(
                staging_branch="zerg/test-feature/staging",
                target_branch="develop",
            )

            mock_git_ops.checkout.assert_called_with("develop")


class TestFullMergeFlowWithFinalize:
    """Tests for complete merge flow including finalize step."""

    @pytest.fixture
    def mock_git_ops(self):
        """Create mock GitOps with full behavior."""
        mock = MagicMock()
        mock.create_staging_branch.return_value = "zerg/test-feature/staging"
        mock.checkout.return_value = None
        mock.merge.return_value = "merge_commit_sha"
        mock.branch_exists.return_value = True
        mock.delete_branch.return_value = None
        mock.abort_merge.return_value = None
        return mock

    @pytest.fixture
    def mock_gate_runner(self):
        """Create mock GateRunner that passes all gates."""
        mock = MagicMock()
        mock.run_all_gates.return_value = (True, [])
        mock.get_summary.return_value = {"passed": 0, "failed": 0}
        return mock

    @pytest.fixture
    def sample_config(self):
        """Create a sample configuration with no gates."""
        config = ZergConfig()
        config.quality_gates = []
        return config

    def test_full_flow_pushes_to_target_branch(self, mock_git_ops, mock_gate_runner, sample_config, tmp_path):
        """Full merge flow should push changes to target branch."""
        with (
            patch("zerg.merge.GitOps", return_value=mock_git_ops),
            patch("zerg.merge.GateRunner", return_value=mock_gate_runner),
        ):
            coordinator = MergeCoordinator(
                feature="test-feature",
                config=sample_config,
                repo_path=tmp_path,
            )

            result = coordinator.full_merge_flow(
                level=1,
                worker_branches=["worker-0"],
                target_branch="main",
            )

            assert result.success is True
            # Verify finalize was performed (checkout target, merge staging)
            checkout_calls = mock_git_ops.checkout.call_args_list
            # Last checkout should be to target branch for finalize
            assert any("main" in str(call) for call in checkout_calls)

    def test_full_flow_cleans_up_staging_branch(self, mock_git_ops, mock_gate_runner, sample_config, tmp_path):
        """Full merge flow should clean up staging branch after success."""
        with (
            patch("zerg.merge.GitOps", return_value=mock_git_ops),
            patch("zerg.merge.GateRunner", return_value=mock_gate_runner),
        ):
            coordinator = MergeCoordinator(
                feature="test-feature",
                config=sample_config,
                repo_path=tmp_path,
            )

            result = coordinator.full_merge_flow(
                level=1,
                worker_branches=["worker-0"],
                target_branch="main",
            )

            assert result.success is True
            # Staging branch should be deleted
            mock_git_ops.delete_branch.assert_called()

    def test_full_flow_returns_merge_commit(self, mock_git_ops, mock_gate_runner, sample_config, tmp_path):
        """Full merge flow should return the final merge commit SHA."""
        mock_git_ops.merge.return_value = "final_sha_12345"

        with (
            patch("zerg.merge.GitOps", return_value=mock_git_ops),
            patch("zerg.merge.GateRunner", return_value=mock_gate_runner),
        ):
            coordinator = MergeCoordinator(
                feature="test-feature",
                config=sample_config,
                repo_path=tmp_path,
            )

            result = coordinator.full_merge_flow(
                level=1,
                worker_branches=["worker-0"],
                target_branch="main",
            )

            assert result.success is True
            assert result.merge_commit == "final_sha_12345"


class TestFullMergeFlowErrorHandling:
    """Tests for error handling in full_merge_flow."""

    @pytest.fixture
    def sample_config(self):
        """Create a sample configuration."""
        config = ZergConfig()
        config.quality_gates = []
        return config

    def test_full_flow_handles_generic_exception(self, sample_config, tmp_path):
        """Full merge flow should handle unexpected exceptions."""
        mock_git_ops = MagicMock()
        mock_git_ops.create_staging_branch.side_effect = Exception("Unexpected git error")
        mock_git_ops.abort_merge.return_value = None

        mock_gate_runner = MagicMock()

        with (
            patch("zerg.merge.GitOps", return_value=mock_git_ops),
            patch("zerg.merge.GateRunner", return_value=mock_gate_runner),
        ):
            coordinator = MergeCoordinator(
                feature="test-feature",
                config=sample_config,
                repo_path=tmp_path,
            )

            result = coordinator.full_merge_flow(
                level=1,
                worker_branches=["worker-0"],
                target_branch="main",
            )

            assert result.success is False
            assert "Unexpected git error" in result.error

    def test_full_flow_aborts_on_failure(self, sample_config, tmp_path):
        """Full merge flow should abort and clean up on failure."""
        mock_git_ops = MagicMock()
        mock_git_ops.create_staging_branch.return_value = "zerg/test-feature/staging"
        mock_git_ops.checkout.return_value = None
        mock_git_ops.merge.side_effect = Exception("Merge failed unexpectedly")
        mock_git_ops.abort_merge.return_value = None
        mock_git_ops.branch_exists.return_value = True
        mock_git_ops.delete_branch.return_value = None

        mock_gate_runner = MagicMock()
        mock_gate_runner.run_all_gates.return_value = (True, [])
        mock_gate_runner.get_summary.return_value = {"passed": 0, "failed": 0}

        with (
            patch("zerg.merge.GitOps", return_value=mock_git_ops),
            patch("zerg.merge.GateRunner", return_value=mock_gate_runner),
        ):
            coordinator = MergeCoordinator(
                feature="test-feature",
                config=sample_config,
                repo_path=tmp_path,
            )

            result = coordinator.full_merge_flow(
                level=1,
                worker_branches=["worker-0"],
                target_branch="main",
            )

            assert result.success is False
            mock_git_ops.abort_merge.assert_called()


class TestMergeFlowResultValues:
    """Tests for MergeFlowResult field values in various scenarios."""

    @pytest.fixture
    def mock_git_ops(self):
        """Create mock GitOps instance."""
        mock = MagicMock()
        mock.create_staging_branch.return_value = "zerg/feature/staging"
        mock.checkout.return_value = None
        mock.merge.return_value = "commit123"
        mock.branch_exists.return_value = True
        mock.delete_branch.return_value = None
        mock.abort_merge.return_value = None
        return mock

    @pytest.fixture
    def mock_gate_runner(self):
        """Create mock GateRunner."""
        mock = MagicMock()
        mock.run_all_gates.return_value = (True, [])
        mock.get_summary.return_value = {"passed": 0, "failed": 0}
        return mock

    @pytest.fixture
    def sample_config(self):
        """Create sample config."""
        config = ZergConfig()
        config.quality_gates = []
        return config

    def test_result_contains_all_source_branches(self, mock_git_ops, mock_gate_runner, sample_config, tmp_path):
        """MergeFlowResult should contain all source branches."""
        branches = ["worker-0", "worker-1", "worker-2", "worker-3"]

        with (
            patch("zerg.merge.GitOps", return_value=mock_git_ops),
            patch("zerg.merge.GateRunner", return_value=mock_gate_runner),
        ):
            coordinator = MergeCoordinator(
                feature="feature",
                config=sample_config,
                repo_path=tmp_path,
            )

            result = coordinator.full_merge_flow(
                level=1,
                worker_branches=branches,
                target_branch="main",
            )

            assert result.source_branches == branches
            assert len(result.source_branches) == 4

    def test_result_timestamp_is_recent(self, mock_git_ops, mock_gate_runner, sample_config, tmp_path):
        """MergeFlowResult timestamp should be recent."""
        before = datetime.now()

        with (
            patch("zerg.merge.GitOps", return_value=mock_git_ops),
            patch("zerg.merge.GateRunner", return_value=mock_gate_runner),
        ):
            coordinator = MergeCoordinator(
                feature="feature",
                config=sample_config,
                repo_path=tmp_path,
            )

            result = coordinator.full_merge_flow(
                level=1,
                worker_branches=["worker-0"],
                target_branch="main",
            )

        after = datetime.now()

        assert before <= result.timestamp <= after

    def test_result_level_matches_input(self, mock_git_ops, mock_gate_runner, sample_config, tmp_path):
        """MergeFlowResult level should match input level."""
        with (
            patch("zerg.merge.GitOps", return_value=mock_git_ops),
            patch("zerg.merge.GateRunner", return_value=mock_gate_runner),
        ):
            coordinator = MergeCoordinator(
                feature="feature",
                config=sample_config,
                repo_path=tmp_path,
            )

            for level in [1, 2, 3, 5, 10]:
                result = coordinator.full_merge_flow(
                    level=level,
                    worker_branches=["worker-0"],
                    target_branch="main",
                )

                assert result.level == level

    def test_result_target_branch_matches_input(self, mock_git_ops, mock_gate_runner, sample_config, tmp_path):
        """MergeFlowResult target_branch should match input."""
        with (
            patch("zerg.merge.GitOps", return_value=mock_git_ops),
            patch("zerg.merge.GateRunner", return_value=mock_gate_runner),
        ):
            coordinator = MergeCoordinator(
                feature="feature",
                config=sample_config,
                repo_path=tmp_path,
            )

            for target in ["main", "develop", "release/v1.0"]:
                result = coordinator.full_merge_flow(
                    level=1,
                    worker_branches=["worker-0"],
                    target_branch=target,
                )

                assert result.target_branch == target
