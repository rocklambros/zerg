"""Integration tests for ZERG merge flow."""

from pathlib import Path

import pytest

from zerg.config import QualityGate, ZergConfig
from zerg.constants import GateResult
from zerg.exceptions import GateFailureError, MergeConflictError
from zerg.gates import GateRunner
from zerg.git_ops import GitOps


class TestMergeFlowClean:
    """Tests for clean merge scenarios."""

    def test_clean_merge_from_feature_branch(self, tmp_repo: Path) -> None:
        """Test merging a feature branch with no conflicts."""
        ops = GitOps(tmp_repo)
        main_branch = ops.current_branch()

        # Create feature branch with changes
        ops.create_branch("feature/test")
        ops.checkout("feature/test")
        (tmp_repo / "feature.txt").write_text("feature content")
        ops.commit("Add feature", add_all=True)

        # Merge back to main
        ops.checkout(main_branch)
        merge_commit = ops.merge("feature/test", message="Merge feature/test")

        assert merge_commit is not None
        assert (tmp_repo / "feature.txt").exists()

    def test_clean_merge_multiple_branches(self, tmp_repo: Path) -> None:
        """Test merging multiple feature branches sequentially."""
        ops = GitOps(tmp_repo)
        main_branch = ops.current_branch()

        # Create and merge first feature
        ops.create_branch("feature/one")
        ops.checkout("feature/one")
        (tmp_repo / "one.txt").write_text("one")
        ops.commit("Add one", add_all=True)

        ops.checkout(main_branch)
        ops.merge("feature/one", message="Merge feature/one")

        # Create and merge second feature
        ops.create_branch("feature/two")
        ops.checkout("feature/two")
        (tmp_repo / "two.txt").write_text("two")
        ops.commit("Add two", add_all=True)

        ops.checkout(main_branch)
        ops.merge("feature/two", message="Merge feature/two")

        assert (tmp_repo / "one.txt").exists()
        assert (tmp_repo / "two.txt").exists()

    def test_staging_branch_workflow(self, tmp_repo: Path) -> None:
        """Test staging branch creation and merge workflow."""
        ops = GitOps(tmp_repo)
        main_branch = ops.current_branch()

        # Create staging branch
        staging = ops.create_staging_branch("myfeature", base=main_branch)
        assert staging == "zerg/myfeature/staging"
        assert ops.branch_exists(staging)

        # Create worker branches
        ops.create_branch("zerg/myfeature/worker-0", main_branch)
        ops.checkout("zerg/myfeature/worker-0")
        (tmp_repo / "worker0.txt").write_text("worker 0 work")
        ops.commit("Worker 0 changes", add_all=True)

        # Merge worker into staging
        ops.checkout(staging)
        ops.merge("zerg/myfeature/worker-0", message="Merge worker-0")

        assert (tmp_repo / "worker0.txt").exists()


class TestMergeFlowConflict:
    """Tests for merge conflict scenarios."""

    def test_merge_conflict_detected(self, tmp_repo: Path) -> None:
        """Test merge conflicts are properly detected."""
        ops = GitOps(tmp_repo)
        main_branch = ops.current_branch()

        # Create conflicting changes
        ops.create_branch("feature/conflict")
        ops.checkout("feature/conflict")
        (tmp_repo / "README.md").write_text("feature version")
        ops.commit("Feature change", add_all=True)

        ops.checkout(main_branch)
        (tmp_repo / "README.md").write_text("main version")
        ops.commit("Main change", add_all=True)

        # Merge should fail with conflict
        with pytest.raises(MergeConflictError) as exc_info:
            ops.merge("feature/conflict")

        assert "README.md" in exc_info.value.conflicting_files

    def test_merge_conflict_includes_file_list(self, tmp_repo: Path) -> None:
        """Test merge conflict exception includes all conflicting files."""
        ops = GitOps(tmp_repo)
        main_branch = ops.current_branch()

        # Create feature branch with changes
        ops.create_branch("feature/multi-conflict")
        ops.checkout("feature/multi-conflict")
        (tmp_repo / "README.md").write_text("feature readme")
        (tmp_repo / "config.txt").write_text("feature config")
        ops.commit("Feature changes", add_all=True)

        ops.checkout(main_branch)
        (tmp_repo / "config.txt").write_text("main config")
        ops.commit("Main config change", add_all=True)
        (tmp_repo / "README.md").write_text("main readme")
        ops.commit("Main readme change", add_all=True)

        with pytest.raises(MergeConflictError) as exc_info:
            ops.merge("feature/multi-conflict")

        # Should include both conflicting files
        assert len(exc_info.value.conflicting_files) >= 1


class TestMergeFlowGateFailure:
    """Tests for merge gate failure scenarios."""

    def test_gate_failure_before_merge(self, tmp_repo: Path, sample_config: ZergConfig) -> None:
        """Test quality gate failure before merge."""
        sample_config.quality_gates = [
            QualityGate(name="fail", command="exit 1", required=True),
        ]

        runner = GateRunner(sample_config)
        all_passed, results = runner.run_all_gates(cwd=tmp_repo)

        assert all_passed is False
        assert results[0].result == GateResult.FAIL

    def test_optional_gate_failure_allows_merge(self, tmp_repo: Path, sample_config: ZergConfig) -> None:
        """Test optional gate failure does not block merge."""
        sample_config.quality_gates = [
            QualityGate(name="lint", command="exit 1", required=False),
            QualityGate(name="test", command="echo pass", required=True),
        ]

        runner = GateRunner(sample_config)
        all_passed, results = runner.run_all_gates(cwd=tmp_repo, stop_on_failure=False)

        # All passed because lint is optional
        assert all_passed is True

    def test_required_gate_failure_blocks_merge(self, tmp_repo: Path, sample_config: ZergConfig) -> None:
        """Test required gate failure blocks merge."""
        sample_config.quality_gates = [
            QualityGate(name="test", command="exit 1", required=True),
        ]

        runner = GateRunner(sample_config)
        result = runner.run_gate_by_name("test", cwd=tmp_repo)

        # Check result raises on failure
        with pytest.raises(GateFailureError):
            runner.check_result(result, raise_on_failure=True)

    def test_gate_run_order(self, tmp_repo: Path, sample_config: ZergConfig) -> None:
        """Test gates run in correct order."""
        sample_config.quality_gates = [
            QualityGate(name="first", command="echo first", required=True),
            QualityGate(name="second", command="echo second", required=True),
            QualityGate(name="third", command="echo third", required=True),
        ]

        runner = GateRunner(sample_config)
        all_passed, results = runner.run_all_gates(cwd=tmp_repo)

        assert all_passed is True
        assert [r.gate_name for r in results] == ["first", "second", "third"]


class TestMergeFlowIntegration:
    """Integration tests combining merge and gate flows."""

    def test_full_merge_workflow(self, tmp_repo: Path, sample_config: ZergConfig) -> None:
        """Test complete merge workflow with gates."""
        ops = GitOps(tmp_repo)
        main_branch = ops.current_branch()

        # Create feature branch
        ops.create_branch("feature/integration")
        ops.checkout("feature/integration")
        (tmp_repo / "integration.txt").write_text("integration test")
        ops.commit("Add integration file", add_all=True)

        # Run quality gates
        sample_config.quality_gates = [
            QualityGate(name="lint", command="echo lint", required=True),
        ]
        runner = GateRunner(sample_config)
        all_passed, _ = runner.run_all_gates(cwd=tmp_repo)
        assert all_passed is True

        # Merge if gates pass
        ops.checkout(main_branch)
        merge_commit = ops.merge("feature/integration", message="Merge after gates")

        assert merge_commit is not None
        assert (tmp_repo / "integration.txt").exists()

    def test_cleanup_after_merge(self, tmp_repo: Path) -> None:
        """Test branch cleanup after successful merge."""
        ops = GitOps(tmp_repo)
        main_branch = ops.current_branch()

        # Create and merge feature
        ops.create_branch("zerg/cleanup/worker-0")
        ops.checkout("zerg/cleanup/worker-0")
        (tmp_repo / "cleanup.txt").write_text("cleanup test")
        ops.commit("Worker changes", add_all=True)

        ops.checkout(main_branch)
        ops.merge("zerg/cleanup/worker-0", message="Merge worker")

        # Cleanup branches
        count = ops.delete_feature_branches("cleanup")
        assert count >= 1
        assert not ops.branch_exists("zerg/cleanup/worker-0")
