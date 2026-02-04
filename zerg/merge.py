"""Merge coordination for ZERG level completion."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zerg.config import ZergConfig
from zerg.constants import GateResult, MergeStatus
from zerg.exceptions import MergeConflictError
from zerg.gates import GateRunner
from zerg.git_ops import GitOps
from zerg.logging import get_logger
from zerg.types import GateRunResult, MergeResult

if TYPE_CHECKING:
    from zerg.level_coordinator import GatePipeline

logger = get_logger("merge")


@dataclass
class MergeFlowResult:
    """Result of a complete merge flow."""

    success: bool
    level: int
    source_branches: list[str]
    target_branch: str
    merge_commit: str | None = None
    gate_results: list[GateRunResult] = field(default_factory=list)
    error: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "level": self.level,
            "source_branches": self.source_branches,
            "target_branch": self.target_branch,
            "merge_commit": self.merge_commit,
            "gate_results": [g.to_dict() for g in self.gate_results],
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


class MergeCoordinator:
    """Coordinate branch merging and quality gates."""

    def __init__(
        self,
        feature: str,
        config: ZergConfig | None = None,
        repo_path: str | Path = ".",
        gate_pipeline: GatePipeline | None = None,
    ) -> None:
        """Initialize merge coordinator.

        Args:
            feature: Feature name
            config: ZERG configuration
            repo_path: Path to git repository
            gate_pipeline: Optional GatePipeline for cached gate execution
        """
        self.feature = feature
        self.config = config or ZergConfig.load()
        self.repo_path = Path(repo_path).resolve()
        self.git = GitOps(repo_path)
        self.gates = GateRunner(self.config)
        self._gate_pipeline = gate_pipeline
        self._current_level: int = 0  # Track level for cache key

    def prepare_merge(self, level: int, target_branch: str = "main") -> str:
        """Prepare for merge by creating staging branch.

        Args:
            level: Level being merged
            target_branch: Target branch for merge

        Returns:
            Staging branch name
        """
        staging_branch = self.git.create_staging_branch(self.feature, target_branch)
        logger.info(f"Created staging branch {staging_branch} from {target_branch}")
        return staging_branch

    def run_pre_merge_gates(
        self,
        cwd: str | Path | None = None,
        skip_tests: bool = False,
    ) -> tuple[bool, list[GateRunResult]]:
        """Run pre-merge quality gates.

        Uses cached results from GatePipeline if available, falling back to
        direct GateRunner execution otherwise.

        Args:
            cwd: Working directory
            skip_tests: Skip test gates (run lint only for faster iteration)

        Returns:
            Tuple of (all_passed, results)
        """
        logger.info("Running pre-merge gates")

        gates = list(self.config.quality_gates)
        if skip_tests:
            gates = [g for g in gates if g.name != "test"]
            logger.info("Skipping test gate (--skip-tests mode)")

        # Filter to required gates only
        required_gates = [g for g in gates if g.required]

        # Use cached pipeline if available (FR-perf: avoid duplicate gate runs)
        if self._gate_pipeline:
            logger.info("Using cached gate pipeline for pre-merge gates")
            results = self._gate_pipeline.run_gates_for_level(
                level=self._current_level,
                gates=required_gates,
                cwd=cwd,
            )
            all_passed = all(r.result == GateResult.PASS for r in results)
            passed_count = sum(1 for r in results if r.result == GateResult.PASS)
            failed_count = len(results) - passed_count
            logger.info(f"Pre-merge gates: {passed_count} passed, {failed_count} failed")
            return all_passed, results

        # Fallback to uncached execution
        all_passed, results = self.gates.run_all_gates(
            gates=required_gates,
            cwd=cwd,
            required_only=True,
        )

        summary = self.gates.get_summary()
        logger.info(f"Pre-merge gates: {summary['passed']} passed, {summary['failed']} failed")

        return all_passed, results

    def execute_merge(
        self,
        source_branches: list[str],
        staging_branch: str,
    ) -> list[MergeResult]:
        """Merge source branches into staging branch.

        Args:
            source_branches: Worker branches to merge
            staging_branch: Target staging branch

        Returns:
            List of MergeResult for each merge

        Raises:
            MergeConflictError: If any merge has conflicts
        """
        results = []

        # Checkout staging branch
        self.git.checkout(staging_branch)

        for branch in source_branches:
            logger.info(f"Merging {branch} into {staging_branch}")

            try:
                commit = self.git.merge(
                    branch,
                    message=f"Merge {branch} into {staging_branch}",
                )
                results.append(
                    MergeResult(
                        source_branch=branch,
                        target_branch=staging_branch,
                        status=MergeStatus.MERGED,
                        commit_sha=commit,
                    )
                )
                logger.info(f"Merged {branch}: {commit[:8]}")

            except MergeConflictError as e:
                results.append(
                    MergeResult(
                        source_branch=branch,
                        target_branch=staging_branch,
                        status=MergeStatus.CONFLICT,
                        conflicting_files=e.conflicting_files,
                        error_message=str(e),
                    )
                )
                raise

        return results

    def run_post_merge_gates(
        self,
        cwd: str | Path | None = None,
        skip_tests: bool = False,
    ) -> tuple[bool, list[GateRunResult]]:
        """Run post-merge quality gates.

        Uses cached results from GatePipeline if available. For post-merge,
        we use a different cache key (level + 1000) to distinguish from
        pre-merge gates while still benefiting from staleness checking.

        Args:
            cwd: Working directory
            skip_tests: Skip test gates (run lint only for faster iteration)

        Returns:
            Tuple of (all_passed, results)
        """
        logger.info("Running post-merge gates")

        gates = list(self.config.quality_gates)
        if skip_tests:
            gates = [g for g in gates if g.name != "test"]
            logger.info("Skipping test gate (--skip-tests mode)")

        # Filter to required gates only
        required_gates = [g for g in gates if g.required]

        # Use cached pipeline if available (FR-perf: avoid duplicate gate runs)
        # Post-merge uses level + 1000 as cache key to distinguish from pre-merge
        if self._gate_pipeline:
            logger.info("Using cached gate pipeline for post-merge gates")
            results = self._gate_pipeline.run_gates_for_level(
                level=self._current_level + 1000,  # Distinct cache key for post-merge
                gates=required_gates,
                cwd=cwd,
            )
            all_passed = all(r.result == GateResult.PASS for r in results)
            passed_count = sum(1 for r in results if r.result == GateResult.PASS)
            failed_count = len(results) - passed_count
            logger.info(f"Post-merge gates: {passed_count} passed, {failed_count} failed")
            return all_passed, results

        # Fallback to uncached execution
        all_passed, results = self.gates.run_all_gates(
            gates=required_gates,
            cwd=cwd,
            required_only=True,
        )

        summary = self.gates.get_summary()
        logger.info(f"Post-merge gates: {summary['passed']} passed, {summary['failed']} failed")

        return all_passed, results

    def finalize(
        self,
        staging_branch: str,
        target_branch: str,
    ) -> str:
        """Finalize merge by merging staging into target.

        Uses detached HEAD checkout to prevent 'branch used by worktree'
        errors when deleting the staging branch afterward.

        Args:
            staging_branch: Staging branch with merged changes
            target_branch: Final target branch

        Returns:
            Merge commit SHA
        """
        logger.info(f"Finalizing: merging {staging_branch} into {target_branch}")

        # Detach HEAD first to release any branch lock from current worktree
        # This prevents "cannot delete branch used by worktree" errors
        try:
            current = self.git.current_branch()
            if current == staging_branch:
                # Detach HEAD to release staging branch lock
                self.git._run("checkout", "--detach", "HEAD")
                logger.debug(f"Detached HEAD from {staging_branch}")
        except Exception as e:
            logger.debug(f"Could not detach HEAD (may already be detached): {e}")

        self.git.checkout(target_branch)
        commit = self.git.merge(
            staging_branch,
            message=f"ZERG: Complete level merge from {staging_branch}",
        )

        logger.info(f"Finalized merge: {commit[:8]}")
        return commit

    def abort(self, staging_branch: str | None = None) -> None:
        """Abort merge and cleanup.

        Args:
            staging_branch: Staging branch to delete
        """
        logger.info("Aborting merge")

        # Abort any in-progress merge
        self.git.abort_merge()

        # Delete staging branch
        if staging_branch and self.git.branch_exists(staging_branch):
            self.git.checkout("main")  # Switch to main first
            self.git.delete_branch(staging_branch, force=True)

    def full_merge_flow(
        self,
        level: int,
        worker_branches: list[str] | None = None,
        target_branch: str = "main",
        skip_gates: bool = False,
        skip_tests: bool = False,
    ) -> MergeFlowResult:
        """Execute complete merge flow for a level.

        Args:
            level: Level being merged
            worker_branches: Branches to merge (auto-detect if None)
            target_branch: Final target branch
            skip_gates: Skip quality gates entirely
            skip_tests: Skip test gates (run lint only for faster iteration)

        Returns:
            MergeFlowResult with outcome
        """
        logger.info(f"Starting full merge flow for level {level}")

        # Set current level for cache key (FR-perf)
        self._current_level = level

        # Auto-detect worker branches if not provided
        if worker_branches is None:
            worker_branches = self.git.list_worker_branches(self.feature)

        if not worker_branches:
            return MergeFlowResult(
                success=False,
                level=level,
                source_branches=[],
                target_branch=target_branch,
                error="No worker branches found",
            )

        staging_branch = None
        gate_results: list[GateRunResult] = []

        try:
            # Step 1: Create staging branch
            staging_branch = self.prepare_merge(level, target_branch)

            # Step 2: Run pre-merge gates
            if not skip_gates:
                passed, results = self.run_pre_merge_gates(skip_tests=skip_tests)
                gate_results.extend(results)
                if not passed:
                    return MergeFlowResult(
                        success=False,
                        level=level,
                        source_branches=worker_branches,
                        target_branch=target_branch,
                        gate_results=gate_results,
                        error="Pre-merge gates failed",
                    )

            # Step 3: Merge all worker branches
            self.execute_merge(worker_branches, staging_branch)

            # Step 4: Run post-merge gates
            if not skip_gates:
                passed, results = self.run_post_merge_gates(skip_tests=skip_tests)
                gate_results.extend(results)
                if not passed:
                    self.abort(staging_branch)
                    return MergeFlowResult(
                        success=False,
                        level=level,
                        source_branches=worker_branches,
                        target_branch=target_branch,
                        gate_results=gate_results,
                        error="Post-merge gates failed",
                    )

            # Step 5: Finalize merge
            commit = self.finalize(staging_branch, target_branch)

            # Cleanup staging branch
            self.git.delete_branch(staging_branch, force=True)

            return MergeFlowResult(
                success=True,
                level=level,
                source_branches=worker_branches,
                target_branch=target_branch,
                merge_commit=commit,
                gate_results=gate_results,
            )

        except MergeConflictError as e:
            self.abort(staging_branch)
            return MergeFlowResult(
                success=False,
                level=level,
                source_branches=worker_branches,
                target_branch=target_branch,
                gate_results=gate_results,
                error=f"Merge conflict: {e.conflicting_files}",
            )

        except Exception as e:
            self.abort(staging_branch)
            return MergeFlowResult(
                success=False,
                level=level,
                source_branches=worker_branches,
                target_branch=target_branch,
                gate_results=gate_results,
                error=str(e),
            )

    def get_mergeable_branches(self) -> list[str]:
        """Get branches that are ready to merge.

        Returns:
            List of branch names
        """
        return self.git.list_worker_branches(self.feature)

    def cleanup_feature_branches(self, force: bool = True) -> int:
        """Delete all branches for the feature.

        Args:
            force: Force delete

        Returns:
            Number of branches deleted
        """
        return self.git.delete_feature_branches(self.feature, force=force)
