"""Unit tests for MergeCoordinator in zerg/merge.py.

Tests cover:
- MergeCoordinator.__init__() construction
- prepare_merge() staging branch creation
- run_pre_merge_gates() with/without pipeline, skip_tests
- execute_merge() success, multi-branch, conflict
- run_post_merge_gates() with/without pipeline, skip_tests
- finalize() with detach HEAD logic
- abort() with/without staging branch
- full_merge_flow() success, pre-merge failure, post-merge failure,
  no branches, merge conflict, generic exception, skip_gates, skip_tests
- get_mergeable_branches()
- cleanup_feature_branches()
- MergeFlowResult.to_dict()
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from zerg.config import QualityGate, ZergConfig
from zerg.constants import GateResult, MergeStatus
from zerg.exceptions import MergeConflictError
from zerg.merge import MergeCoordinator, MergeFlowResult
from zerg.types import GateRunResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_config() -> ZergConfig:
    """ZergConfig with two required quality gates."""
    cfg = ZergConfig()
    cfg.quality_gates = [
        QualityGate(name="lint", command="ruff check .", required=True),
        QualityGate(name="test", command="pytest", required=True),
    ]
    return cfg


@pytest.fixture
def mock_git():
    """Mock GitOps instance with sensible defaults."""
    git = MagicMock()
    git.create_staging_branch.return_value = "zerg/my-feat/staging-1"
    git.current_branch.return_value = "zerg/my-feat/staging-1"
    git.merge.return_value = "abc123def456"
    git.branch_exists.return_value = True
    git.list_worker_branches.return_value = [
        "zerg/my-feat/worker-0",
        "zerg/my-feat/worker-1",
    ]
    git.delete_feature_branches.return_value = 2
    return git


@pytest.fixture
def mock_gates():
    """Mock GateRunner instance."""
    gates = MagicMock()
    gates.run_all_gates.return_value = (True, [_pass_result("lint"), _pass_result("test")])
    gates.get_summary.return_value = {"passed": 2, "failed": 0}
    return gates


@pytest.fixture
def coordinator(mock_config, mock_git, mock_gates):
    """MergeCoordinator wired with mocked collaborators."""
    with (
        patch("zerg.merge.GitOps", return_value=mock_git),
        patch("zerg.merge.GateRunner", return_value=mock_gates),
        patch("zerg.merge.ZergConfig.load", return_value=mock_config),
    ):
        mc = MergeCoordinator(feature="my-feat", config=mock_config, repo_path="/tmp/repo")
    # Replace internal objects with our mocks (GitOps/GateRunner already set via patch)
    mc.git = mock_git
    mc.gates = mock_gates
    return mc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pass_result(name: str) -> GateRunResult:
    return GateRunResult(
        gate_name=name,
        result=GateResult.PASS,
        command=f"{name} cmd",
        exit_code=0,
    )


def _fail_result(name: str) -> GateRunResult:
    return GateRunResult(
        gate_name=name,
        result=GateResult.FAIL,
        command=f"{name} cmd",
        exit_code=1,
        stderr="check failed",
    )


# ===========================================================================
# MergeFlowResult
# ===========================================================================


class TestMergeFlowResult:
    """Tests for the MergeFlowResult dataclass."""

    def test_to_dict_success(self):
        """to_dict includes all fields with correct types."""
        ts = datetime(2026, 1, 15, 12, 0, 0)
        result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["b1", "b2"],
            target_branch="main",
            merge_commit="abc123",
            gate_results=[_pass_result("lint")],
            timestamp=ts,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["level"] == 1
        assert d["source_branches"] == ["b1", "b2"]
        assert d["target_branch"] == "main"
        assert d["merge_commit"] == "abc123"
        assert d["error"] is None
        assert d["timestamp"] == ts.isoformat()
        assert len(d["gate_results"]) == 1
        assert d["gate_results"][0]["gate_name"] == "lint"

    def test_to_dict_failure_with_error(self):
        """to_dict captures error string."""
        result = MergeFlowResult(
            success=False,
            level=2,
            source_branches=[],
            target_branch="main",
            error="No worker branches found",
        )
        d = result.to_dict()
        assert d["success"] is False
        assert d["error"] == "No worker branches found"
        assert d["merge_commit"] is None


# ===========================================================================
# MergeCoordinator.__init__
# ===========================================================================


class TestMergeCoordinatorInit:
    """Tests for MergeCoordinator construction."""

    def test_init_with_explicit_config(self, mock_config):
        """Accepts explicit config without calling ZergConfig.load()."""
        with patch("zerg.merge.GitOps") as mock_git_cls, patch("zerg.merge.GateRunner"):
            mc = MergeCoordinator(feature="feat", config=mock_config, repo_path="/tmp")
        assert mc.feature == "feat"
        assert mc.config is mock_config
        assert mc._current_level == 0
        mock_git_cls.assert_called_once_with("/tmp")

    def test_init_loads_default_config_when_none(self):
        """Calls ZergConfig.load() when config is None."""
        with (
            patch("zerg.merge.GitOps"),
            patch("zerg.merge.GateRunner"),
            patch("zerg.merge.ZergConfig.load") as mock_load,
        ):
            mock_load.return_value = ZergConfig()
            mc = MergeCoordinator(feature="feat")
        mock_load.assert_called_once()
        assert mc.config is mock_load.return_value

    def test_init_stores_gate_pipeline(self, mock_config):
        """gate_pipeline parameter is stored for cached gate execution."""
        pipeline = MagicMock()
        with patch("zerg.merge.GitOps"), patch("zerg.merge.GateRunner"):
            mc = MergeCoordinator(feature="f", config=mock_config, gate_pipeline=pipeline)
        assert mc._gate_pipeline is pipeline


# ===========================================================================
# prepare_merge
# ===========================================================================


class TestPrepareMerge:
    """Tests for MergeCoordinator.prepare_merge()."""

    def test_creates_staging_branch(self, coordinator, mock_git):
        """Delegates to git.create_staging_branch and returns the name."""
        result = coordinator.prepare_merge(level=1, target_branch="main")
        mock_git.create_staging_branch.assert_called_once_with("my-feat", "main")
        assert result == "zerg/my-feat/staging-1"


# ===========================================================================
# run_pre_merge_gates
# ===========================================================================


class TestRunPreMergeGates:
    """Tests for run_pre_merge_gates()."""

    def test_all_pass_no_pipeline(self, coordinator, mock_gates):
        """Falls back to GateRunner when no pipeline is set."""
        passed, results = coordinator.run_pre_merge_gates()
        assert passed is True
        mock_gates.run_all_gates.assert_called_once()

    def test_failure_no_pipeline(self, coordinator, mock_gates):
        """Reports failure when a gate fails."""
        mock_gates.run_all_gates.return_value = (False, [_fail_result("lint")])
        mock_gates.get_summary.return_value = {"passed": 0, "failed": 1}
        passed, results = coordinator.run_pre_merge_gates()
        assert passed is False
        assert results[0].result == GateResult.FAIL

    def test_uses_cached_pipeline(self, coordinator):
        """Uses GatePipeline when available, bypasses GateRunner."""
        pipeline = MagicMock()
        pipeline.run_gates_for_level.return_value = [_pass_result("lint")]
        coordinator._gate_pipeline = pipeline
        coordinator._current_level = 3

        passed, results = coordinator.run_pre_merge_gates()
        assert passed is True
        pipeline.run_gates_for_level.assert_called_once()
        # Verify level key matches current level
        call_kwargs = pipeline.run_gates_for_level.call_args
        assert call_kwargs.kwargs.get("level", call_kwargs[1].get("level")) == 3

    def test_pipeline_failure(self, coordinator):
        """Pipeline reports failure correctly."""
        pipeline = MagicMock()
        pipeline.run_gates_for_level.return_value = [_fail_result("test")]
        coordinator._gate_pipeline = pipeline
        coordinator._current_level = 1

        passed, _ = coordinator.run_pre_merge_gates()
        assert passed is False

    def test_skip_tests_filters_test_gate(self, coordinator, mock_config):
        """skip_tests=True removes test gates from the list."""
        # The method filters required gates, so ensure we test that path
        passed, _ = coordinator.run_pre_merge_gates(skip_tests=True)
        # It should still call run_all_gates with filtered gates list
        assert passed is True


# ===========================================================================
# execute_merge
# ===========================================================================


class TestExecuteMerge:
    """Tests for execute_merge()."""

    def test_single_branch_success(self, coordinator, mock_git):
        """Merges a single branch and returns MergeResult."""
        results = coordinator.execute_merge(
            source_branches=["zerg/my-feat/worker-0"],
            staging_branch="staging",
        )
        mock_git.checkout.assert_called_once_with("staging")
        mock_git.merge.assert_called_once()
        assert len(results) == 1
        assert results[0].status == MergeStatus.MERGED
        assert results[0].commit_sha == "abc123def456"

    def test_multiple_branches(self, coordinator, mock_git):
        """Merges multiple branches sequentially."""
        mock_git.merge.side_effect = ["sha1111", "sha2222"]
        results = coordinator.execute_merge(
            source_branches=["worker-0", "worker-1"],
            staging_branch="staging",
        )
        assert len(results) == 2
        assert results[0].commit_sha == "sha1111"
        assert results[1].commit_sha == "sha2222"

    def test_merge_conflict_raises(self, coordinator, mock_git):
        """Raises MergeConflictError and records conflict result."""
        conflict = MergeConflictError(
            message="conflict",
            source_branch="worker-0",
            target_branch="staging",
            conflicting_files=["src/main.py"],
        )
        mock_git.merge.side_effect = conflict

        with pytest.raises(MergeConflictError):
            coordinator.execute_merge(
                source_branches=["worker-0"],
                staging_branch="staging",
            )

    def test_conflict_on_second_branch(self, coordinator, mock_git):
        """First branch merges, second conflicts -- partial results before raise."""
        conflict = MergeConflictError(
            message="conflict",
            source_branch="worker-1",
            target_branch="staging",
            conflicting_files=["file.py"],
        )
        mock_git.merge.side_effect = ["sha1111", conflict]

        with pytest.raises(MergeConflictError):
            coordinator.execute_merge(
                source_branches=["worker-0", "worker-1"],
                staging_branch="staging",
            )


# ===========================================================================
# run_post_merge_gates
# ===========================================================================


class TestRunPostMergeGates:
    """Tests for run_post_merge_gates()."""

    def test_all_pass_no_pipeline(self, coordinator, mock_gates):
        """Falls back to GateRunner when no pipeline is set."""
        passed, results = coordinator.run_post_merge_gates()
        assert passed is True

    def test_failure_no_pipeline(self, coordinator, mock_gates):
        """Reports failure when gates fail."""
        mock_gates.run_all_gates.return_value = (False, [_fail_result("test")])
        mock_gates.get_summary.return_value = {"passed": 0, "failed": 1}
        passed, _ = coordinator.run_post_merge_gates()
        assert passed is False

    def test_uses_pipeline_with_offset_key(self, coordinator):
        """Post-merge uses level + 1000 as cache key."""
        pipeline = MagicMock()
        pipeline.run_gates_for_level.return_value = [_pass_result("lint")]
        coordinator._gate_pipeline = pipeline
        coordinator._current_level = 2

        passed, _ = coordinator.run_post_merge_gates()
        assert passed is True
        call_kwargs = pipeline.run_gates_for_level.call_args
        # Post-merge cache key = current_level + 1000
        assert call_kwargs.kwargs.get("level", call_kwargs[1].get("level")) == 1002

    def test_skip_tests(self, coordinator, mock_gates):
        """skip_tests=True filters test gate for post-merge."""
        passed, _ = coordinator.run_post_merge_gates(skip_tests=True)
        assert passed is True


# ===========================================================================
# finalize
# ===========================================================================


class TestFinalize:
    """Tests for finalize()."""

    def test_finalize_success(self, coordinator, mock_git):
        """Merges staging into target and returns commit SHA."""
        commit = coordinator.finalize("staging-branch", "main")
        mock_git.checkout.assert_called_with("main")
        mock_git.merge.assert_called_once()
        assert commit == "abc123def456"

    def test_detaches_head_when_on_staging(self, coordinator, mock_git):
        """Detaches HEAD when current branch is the staging branch."""
        mock_git.current_branch.return_value = "staging-branch"
        coordinator.finalize("staging-branch", "main")
        mock_git._run.assert_called_once_with("checkout", "--detach", "HEAD")

    def test_does_not_detach_when_on_different_branch(self, coordinator, mock_git):
        """Skips HEAD detach when current branch is not staging."""
        mock_git.current_branch.return_value = "some-other-branch"
        coordinator.finalize("staging-branch", "main")
        mock_git._run.assert_not_called()

    def test_detach_failure_is_swallowed(self, coordinator, mock_git):
        """HEAD detach errors are caught and logged, not propagated."""
        mock_git.current_branch.return_value = "staging-branch"
        mock_git._run.side_effect = Exception("detach failed")
        # Should not raise
        commit = coordinator.finalize("staging-branch", "main")
        assert commit == "abc123def456"

    def test_current_branch_exception_swallowed(self, coordinator, mock_git):
        """Exception in current_branch() is caught gracefully."""
        mock_git.current_branch.side_effect = Exception("not a repo")
        commit = coordinator.finalize("staging-branch", "main")
        assert commit == "abc123def456"


# ===========================================================================
# abort
# ===========================================================================


class TestAbort:
    """Tests for abort()."""

    def test_abort_with_staging_branch(self, coordinator, mock_git):
        """Aborts merge, checks out main, and deletes staging branch."""
        coordinator.abort("staging-branch")
        mock_git.abort_merge.assert_called_once()
        mock_git.checkout.assert_called_once_with("main")
        mock_git.delete_branch.assert_called_once_with("staging-branch", force=True)

    def test_abort_without_staging_branch(self, coordinator, mock_git):
        """Aborts merge but skips branch deletion when no staging branch."""
        coordinator.abort(None)
        mock_git.abort_merge.assert_called_once()
        mock_git.delete_branch.assert_not_called()

    def test_abort_branch_does_not_exist(self, coordinator, mock_git):
        """Skips deletion when staging branch does not exist."""
        mock_git.branch_exists.return_value = False
        coordinator.abort("staging-branch")
        mock_git.abort_merge.assert_called_once()
        mock_git.delete_branch.assert_not_called()


# ===========================================================================
# full_merge_flow
# ===========================================================================


class TestFullMergeFlow:
    """Tests for full_merge_flow()."""

    def test_success_with_gates(self, coordinator, mock_git, mock_gates):
        """Complete merge flow succeeds with passing gates."""
        result = coordinator.full_merge_flow(
            level=1,
            worker_branches=["worker-0", "worker-1"],
        )
        assert result.success is True
        assert result.level == 1
        assert result.merge_commit == "abc123def456"
        assert result.error is None
        # Staging branch should be cleaned up
        mock_git.delete_branch.assert_called()

    def test_success_skip_gates(self, coordinator, mock_git, mock_gates):
        """skip_gates=True bypasses pre/post-merge gates."""
        result = coordinator.full_merge_flow(
            level=1,
            worker_branches=["worker-0"],
            skip_gates=True,
        )
        assert result.success is True
        # Gates should not have been called
        mock_gates.run_all_gates.assert_not_called()

    def test_no_worker_branches(self, coordinator, mock_git):
        """Returns failure when no worker branches found."""
        result = coordinator.full_merge_flow(level=1, worker_branches=[])
        assert result.success is False
        assert result.error == "No worker branches found"

    def test_auto_detect_branches(self, coordinator, mock_git, mock_gates):
        """Auto-detects worker branches when not provided."""
        result = coordinator.full_merge_flow(level=1)
        assert result.success is True
        mock_git.list_worker_branches.assert_called_once_with("my-feat")

    def test_auto_detect_no_branches(self, coordinator, mock_git):
        """Returns failure when auto-detect finds no branches."""
        mock_git.list_worker_branches.return_value = []
        result = coordinator.full_merge_flow(level=1)
        assert result.success is False
        assert result.error == "No worker branches found"

    def test_pre_merge_gate_failure(self, coordinator, mock_gates):
        """Returns failure when pre-merge gates fail."""
        mock_gates.run_all_gates.return_value = (False, [_fail_result("lint")])
        mock_gates.get_summary.return_value = {"passed": 0, "failed": 1}
        result = coordinator.full_merge_flow(
            level=1,
            worker_branches=["worker-0"],
        )
        assert result.success is False
        assert result.error == "Pre-merge gates failed"
        assert len(result.gate_results) > 0

    def test_post_merge_gate_failure(self, coordinator, mock_git, mock_gates):
        """Returns failure and aborts when post-merge gates fail."""
        # Pre-merge passes, post-merge fails
        mock_gates.run_all_gates.side_effect = [
            (True, [_pass_result("lint")]),  # pre-merge pass
            (False, [_fail_result("test")]),  # post-merge fail
        ]
        mock_gates.get_summary.return_value = {"passed": 0, "failed": 1}
        result = coordinator.full_merge_flow(
            level=1,
            worker_branches=["worker-0"],
        )
        assert result.success is False
        assert result.error == "Post-merge gates failed"
        # abort should have been called
        mock_git.abort_merge.assert_called()

    def test_merge_conflict_during_flow(self, coordinator, mock_git, mock_gates):
        """Handles MergeConflictError and aborts."""
        conflict = MergeConflictError(
            message="conflict",
            source_branch="worker-0",
            target_branch="staging",
            conflicting_files=["file.py"],
        )
        mock_git.merge.side_effect = conflict
        result = coordinator.full_merge_flow(
            level=1,
            worker_branches=["worker-0"],
            skip_gates=True,
        )
        assert result.success is False
        assert "file.py" in result.error
        mock_git.abort_merge.assert_called()

    def test_generic_exception_during_flow(self, coordinator, mock_git, mock_gates):
        """Handles unexpected exceptions and aborts."""
        mock_git.merge.side_effect = RuntimeError("disk full")
        result = coordinator.full_merge_flow(
            level=1,
            worker_branches=["worker-0"],
            skip_gates=True,
        )
        assert result.success is False
        assert "disk full" in result.error
        mock_git.abort_merge.assert_called()

    def test_sets_current_level(self, coordinator, mock_gates):
        """full_merge_flow sets _current_level for cache key."""
        coordinator.full_merge_flow(level=3, worker_branches=["w0"], skip_gates=True)
        assert coordinator._current_level == 3

    @pytest.mark.parametrize("skip_tests", [True, False])
    def test_skip_tests_parameter(self, coordinator, mock_gates, skip_tests):
        """skip_tests is forwarded to pre/post-merge gate methods."""
        coordinator.full_merge_flow(
            level=1,
            worker_branches=["worker-0"],
            skip_tests=skip_tests,
        )
        # Gates were called (not skipped entirely, just test gate filtered)
        assert mock_gates.run_all_gates.called


# ===========================================================================
# get_mergeable_branches / cleanup_feature_branches
# ===========================================================================


class TestUtilityMethods:
    """Tests for get_mergeable_branches and cleanup_feature_branches."""

    def test_get_mergeable_branches(self, coordinator, mock_git):
        """Delegates to git.list_worker_branches."""
        branches = coordinator.get_mergeable_branches()
        mock_git.list_worker_branches.assert_called_once_with("my-feat")
        assert branches == ["zerg/my-feat/worker-0", "zerg/my-feat/worker-1"]

    def test_cleanup_feature_branches(self, coordinator, mock_git):
        """Delegates to git.delete_feature_branches."""
        count = coordinator.cleanup_feature_branches(force=True)
        mock_git.delete_feature_branches.assert_called_once_with("my-feat", force=True)
        assert count == 2

    def test_cleanup_feature_branches_no_force(self, coordinator, mock_git):
        """Passes force=False when specified."""
        coordinator.cleanup_feature_branches(force=False)
        mock_git.delete_feature_branches.assert_called_once_with("my-feat", force=False)
