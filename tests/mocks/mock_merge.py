"""Mock MergeCoordinator with full merge flow simulation.

Provides MockMergeCoordinator for testing orchestrator merge handling
with configurable timeout, retry, failure scenarios, and complete
merge flow simulation including gates, execute, and finalize.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from zerg.constants import GateResult, MergeStatus
from zerg.merge import MergeFlowResult
from zerg.types import GateRunResult, MergeResult


@dataclass
class MergeAttempt:
    """Record of a merge attempt."""

    level: int
    worker_branches: list[str]
    target_branch: str
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: int = 0
    success: bool = False
    error: str | None = None
    timed_out: bool = False


class MockMergeCoordinator:
    """Mock MergeCoordinator with timeout and failure simulation.

    Simulates merge operations with configurable delays, timeouts, and
    failure scenarios for testing orchestrator merge handling.

    Example:
        merger = MockMergeCoordinator("test-feature")
        merger.configure(
            merge_delay=5.0,  # Simulate 5 second merge
            fail_at_attempt=2,  # Fail on second attempt
        )

        result = merger.full_merge_flow(level=1, worker_branches=[...])
        assert result.success  # First attempt succeeds

        result = merger.full_merge_flow(level=2, worker_branches=[...])
        assert not result.success  # Second attempt fails
    """

    def __init__(
        self,
        feature: str,
        config: Any = None,
        repo_path: str | Path = ".",
    ) -> None:
        """Initialize mock merge coordinator.

        Args:
            feature: Feature name
            config: ZergConfig (ignored in mock)
            repo_path: Repository path (ignored in mock)
        """
        self.feature = feature
        self.config = config
        self.repo_path = Path(repo_path)

        # Attempt tracking
        self._attempts: list[MergeAttempt] = []
        self._attempt_count = 0

        # Configurable behavior
        self._merge_delay: float = 0.0
        self._fail_at_attempt: int | None = None
        self._fail_at_level: int | None = None
        self._conflict_at_level: int | None = None
        self._timeout_at_attempt: int | None = None
        self._always_succeed: bool = True
        self._gate_failure_levels: set[int] = set()
        self._conflicting_files: list[str] = []
        self._pre_merge_gate_failure_levels: set[int] = set()
        self._post_merge_gate_failure_levels: set[int] = set()
        self._execute_merge_conflict_branches: set[str] = set()
        self._finalize_fails: bool = False
        self._gate_delay: float = 0.0

        # Results to return
        self._custom_results: dict[int, MergeFlowResult] = {}

        # Gate results tracking
        self._gate_runs: list[GateRunResult] = []
        self._merge_results: list[MergeResult] = []

        # Current level being processed (for gate methods)
        self._current_level: int = 0

    def configure(
        self,
        merge_delay: float = 0.0,
        fail_at_attempt: int | None = None,
        fail_at_level: int | None = None,
        conflict_at_level: int | None = None,
        timeout_at_attempt: int | None = None,
        always_succeed: bool = True,
        gate_failure_levels: list[int] | None = None,
        conflicting_files: list[str] | None = None,
        pre_merge_gate_failure_levels: list[int] | None = None,
        post_merge_gate_failure_levels: list[int] | None = None,
        execute_merge_conflict_branches: list[str] | None = None,
        finalize_fails: bool = False,
        gate_delay: float = 0.0,
    ) -> MockMergeCoordinator:
        """Configure mock behavior.

        Args:
            merge_delay: Simulated merge duration in seconds
            fail_at_attempt: Attempt number to fail at (1-indexed)
            fail_at_level: Level number to fail at
            conflict_at_level: Level to simulate conflict at
            timeout_at_attempt: Attempt to simulate timeout at
            always_succeed: Default success behavior
            gate_failure_levels: Levels where gates fail (legacy, applies to both)
            conflicting_files: Files that conflict
            pre_merge_gate_failure_levels: Levels where pre-merge gates fail
            post_merge_gate_failure_levels: Levels where post-merge gates fail
            execute_merge_conflict_branches: Branches that cause conflicts in execute_merge
            finalize_fails: Whether finalize operation fails
            gate_delay: Simulated gate execution delay in seconds

        Returns:
            Self for chaining
        """
        self._merge_delay = merge_delay
        self._fail_at_attempt = fail_at_attempt
        self._fail_at_level = fail_at_level
        self._conflict_at_level = conflict_at_level
        self._timeout_at_attempt = timeout_at_attempt
        self._always_succeed = always_succeed
        self._gate_failure_levels = set(gate_failure_levels or [])
        self._conflicting_files = conflicting_files or []
        self._pre_merge_gate_failure_levels = set(pre_merge_gate_failure_levels or [])
        self._post_merge_gate_failure_levels = set(post_merge_gate_failure_levels or [])
        self._execute_merge_conflict_branches = set(execute_merge_conflict_branches or [])
        self._finalize_fails = finalize_fails
        self._gate_delay = gate_delay
        return self

    def set_result(self, level: int, result: MergeFlowResult) -> None:
        """Set a custom result for a specific level.

        Args:
            level: Level number
            result: Result to return for that level
        """
        self._custom_results[level] = result

    def full_merge_flow(
        self,
        level: int,
        worker_branches: list[str] | None = None,
        target_branch: str = "main",
        skip_gates: bool = False,
    ) -> MergeFlowResult:
        """Execute mock merge flow.

        Args:
            level: Level being merged
            worker_branches: Branches to merge
            target_branch: Target branch
            skip_gates: Skip gates

        Returns:
            MergeFlowResult based on configuration
        """
        self._attempt_count += 1
        start_time = time.time()

        # Apply configured delay
        if self._merge_delay > 0:
            time.sleep(self._merge_delay)

        duration_ms = int((time.time() - start_time) * 1000)

        # Check for custom result
        if level in self._custom_results:
            result = self._custom_results[level]
            self._record_attempt(
                level, worker_branches or [], target_branch, duration_ms, result.success, result.error, False
            )
            return result

        # Check for timeout simulation
        if self._timeout_at_attempt == self._attempt_count:
            self._record_attempt(
                level, worker_branches or [], target_branch, duration_ms, False, "Merge timed out", True
            )
            return MergeFlowResult(
                success=False,
                level=level,
                source_branches=worker_branches or [],
                target_branch=target_branch,
                error="Merge timed out",
            )

        # Check for attempt-based failure
        if self._fail_at_attempt == self._attempt_count:
            self._record_attempt(
                level, worker_branches or [], target_branch, duration_ms, False, "Simulated failure at attempt", False
            )
            return MergeFlowResult(
                success=False,
                level=level,
                source_branches=worker_branches or [],
                target_branch=target_branch,
                error=f"Simulated failure at attempt {self._attempt_count}",
            )

        # Check for level-based failure
        if self._fail_at_level == level:
            self._record_attempt(
                level, worker_branches or [], target_branch, duration_ms, False, "Simulated failure at level", False
            )
            return MergeFlowResult(
                success=False,
                level=level,
                source_branches=worker_branches or [],
                target_branch=target_branch,
                error=f"Simulated failure at level {level}",
            )

        # Check for conflict simulation
        if self._conflict_at_level == level:
            error = f"Merge conflict: {self._conflicting_files or ['file.py']}"
            self._record_attempt(level, worker_branches or [], target_branch, duration_ms, False, error, False)
            return MergeFlowResult(
                success=False,
                level=level,
                source_branches=worker_branches or [],
                target_branch=target_branch,
                error=error,
            )

        # Check for gate failures
        if level in self._gate_failure_levels:
            self._record_attempt(
                level, worker_branches or [], target_branch, duration_ms, False, "Post-merge gates failed", False
            )
            return MergeFlowResult(
                success=False,
                level=level,
                source_branches=worker_branches or [],
                target_branch=target_branch,
                error="Post-merge gates failed",
            )

        # Default success case
        if self._always_succeed:
            merge_commit = f"merge{self._attempt_count:04d}"
            self._record_attempt(level, worker_branches or [], target_branch, duration_ms, True, None, False)
            return MergeFlowResult(
                success=True,
                level=level,
                source_branches=worker_branches or [],
                target_branch=target_branch,
                merge_commit=merge_commit,
            )

        # Explicit failure
        self._record_attempt(level, worker_branches or [], target_branch, duration_ms, False, "Merge failed", False)
        return MergeFlowResult(
            success=False,
            level=level,
            source_branches=worker_branches or [],
            target_branch=target_branch,
            error="Merge failed",
        )

    def _record_attempt(
        self,
        level: int,
        worker_branches: list[str],
        target_branch: str,
        duration_ms: int,
        success: bool,
        error: str | None,
        timed_out: bool,
    ) -> None:
        """Record a merge attempt.

        Args:
            level: Level being merged
            worker_branches: Branches involved
            target_branch: Target branch
            duration_ms: Duration in milliseconds
            success: Whether attempt succeeded
            error: Error message if failed
            timed_out: Whether attempt timed out
        """
        self._attempts.append(
            MergeAttempt(
                level=level,
                worker_branches=worker_branches,
                target_branch=target_branch,
                duration_ms=duration_ms,
                success=success,
                error=error,
                timed_out=timed_out,
            )
        )

    def get_attempts(self) -> list[MergeAttempt]:
        """Get all recorded merge attempts.

        Returns:
            List of MergeAttempt records
        """
        return self._attempts.copy()

    def get_attempt_count(self) -> int:
        """Get total number of merge attempts.

        Returns:
            Number of attempts
        """
        return self._attempt_count

    def get_successful_attempts(self) -> list[MergeAttempt]:
        """Get successful merge attempts.

        Returns:
            List of successful MergeAttempt records
        """
        return [a for a in self._attempts if a.success]

    def get_failed_attempts(self) -> list[MergeAttempt]:
        """Get failed merge attempts.

        Returns:
            List of failed MergeAttempt records
        """
        return [a for a in self._attempts if not a.success]

    def get_timed_out_attempts(self) -> list[MergeAttempt]:
        """Get timed out merge attempts.

        Returns:
            List of timed out MergeAttempt records
        """
        return [a for a in self._attempts if a.timed_out]

    def reset(self) -> None:
        """Reset mock state."""
        self._attempts.clear()
        self._attempt_count = 0
        self._custom_results.clear()
        self._gate_runs.clear()
        self._merge_results.clear()
        self._current_level = 0

    def get_gate_runs(self) -> list[GateRunResult]:
        """Get all gate execution results.

        Returns:
            List of GateRunResult records
        """
        return self._gate_runs.copy()

    def get_pre_merge_gate_runs(self) -> list[GateRunResult]:
        """Get pre-merge gate execution results.

        Returns:
            List of pre-merge GateRunResult records
        """
        return [g for g in self._gate_runs if g.gate_name == "pre_merge_check"]

    def get_post_merge_gate_runs(self) -> list[GateRunResult]:
        """Get post-merge gate execution results.

        Returns:
            List of post-merge GateRunResult records
        """
        return [g for g in self._gate_runs if g.gate_name == "post_merge_check"]

    def get_merge_results(self) -> list[MergeResult]:
        """Get all merge operation results.

        Returns:
            List of MergeResult records
        """
        return self._merge_results.copy()

    def get_successful_merges(self) -> list[MergeResult]:
        """Get successful merge results.

        Returns:
            List of successful MergeResult records
        """
        return [m for m in self._merge_results if m.status == MergeStatus.MERGED]

    def get_conflict_merges(self) -> list[MergeResult]:
        """Get merge results that had conflicts.

        Returns:
            List of conflicting MergeResult records
        """
        return [m for m in self._merge_results if m.status == MergeStatus.CONFLICT]

    def set_current_level(self, level: int) -> None:
        """Set the current level for gate operations.

        Args:
            level: Current level number
        """
        self._current_level = level

    # Additional methods to match MergeCoordinator interface

    def prepare_merge(self, level: int, target_branch: str = "main") -> str:
        """Mock prepare_merge - returns staging branch name.

        Args:
            level: Level being merged
            target_branch: Target branch

        Returns:
            Staging branch name
        """
        self._current_level = level
        return f"zerg/{self.feature}/staging"

    def run_pre_merge_gates(
        self,
        cwd: str | Path | None = None,
    ) -> tuple[bool, list[GateRunResult]]:
        """Run mock pre-merge quality gates.

        Args:
            cwd: Working directory (ignored in mock)

        Returns:
            Tuple of (all_passed, results)
        """
        # Apply configured delay
        if self._gate_delay > 0:
            time.sleep(self._gate_delay)

        # Check for pre-merge gate failure at current level
        level = self._current_level
        should_fail = level in self._pre_merge_gate_failure_levels or level in self._gate_failure_levels

        result = GateRunResult(
            gate_name="pre_merge_check",
            result=GateResult.FAIL if should_fail else GateResult.PASS,
            command="pytest tests/",
            exit_code=1 if should_fail else 0,
            stdout="" if should_fail else "All tests passed",
            stderr="Test failures detected" if should_fail else "",
            duration_ms=int(self._gate_delay * 1000) if self._gate_delay else 100,
        )

        self._gate_runs.append(result)
        return (not should_fail, [result])

    def run_post_merge_gates(
        self,
        cwd: str | Path | None = None,
    ) -> tuple[bool, list[GateRunResult]]:
        """Run mock post-merge quality gates.

        Args:
            cwd: Working directory (ignored in mock)

        Returns:
            Tuple of (all_passed, results)
        """
        # Apply configured delay
        if self._gate_delay > 0:
            time.sleep(self._gate_delay)

        # Check for post-merge gate failure at current level
        level = self._current_level
        should_fail = level in self._post_merge_gate_failure_levels

        result = GateRunResult(
            gate_name="post_merge_check",
            result=GateResult.FAIL if should_fail else GateResult.PASS,
            command="pytest tests/ --integration",
            exit_code=1 if should_fail else 0,
            stdout="" if should_fail else "Integration tests passed",
            stderr="Integration test failures" if should_fail else "",
            duration_ms=int(self._gate_delay * 1000) if self._gate_delay else 100,
        )

        self._gate_runs.append(result)
        return (not should_fail, [result])

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
            MergeConflictError simulation via return value with CONFLICT status
        """
        from zerg.exceptions import MergeConflictError

        results = []

        for branch in source_branches:
            # Check for conflict simulation
            if branch in self._execute_merge_conflict_branches or self._conflict_at_level == self._current_level:
                conflict_files = self._conflicting_files or [f"{branch}_file.py"]
                result = MergeResult(
                    source_branch=branch,
                    target_branch=staging_branch,
                    status=MergeStatus.CONFLICT,
                    conflicting_files=conflict_files,
                    error_message=f"Merge conflict in {conflict_files}",
                )
                results.append(result)
                self._merge_results.append(result)
                raise MergeConflictError(
                    f"Merge conflict: {branch}",
                    source_branch=branch,
                    target_branch=staging_branch,
                    conflicting_files=conflict_files,
                )

            # Successful merge
            commit = f"merge_{branch}_{self._attempt_count:04d}"
            result = MergeResult(
                source_branch=branch,
                target_branch=staging_branch,
                status=MergeStatus.MERGED,
                commit_sha=commit,
            )
            results.append(result)
            self._merge_results.append(result)

        return results

    def finalize(
        self,
        staging_branch: str,
        target_branch: str,
    ) -> str:
        """Finalize merge by merging staging into target.

        Args:
            staging_branch: Staging branch with merged changes
            target_branch: Final target branch

        Returns:
            Merge commit SHA

        Raises:
            Exception: If finalize_fails is configured
        """
        if self._finalize_fails:
            raise Exception("Simulated finalize failure")

        commit = f"final_{self._attempt_count:04d}"
        return commit

    def abort(self, staging_branch: str | None = None) -> None:
        """Mock abort - no-op.

        Args:
            staging_branch: Branch to clean up
        """
        pass

    def get_mergeable_branches(self) -> list[str]:
        """Mock get_mergeable_branches.

        Returns:
            Empty list (override with set_result for specific behavior)
        """
        return []

    def cleanup_feature_branches(self, force: bool = True) -> int:
        """Mock cleanup_feature_branches.

        Args:
            force: Force delete

        Returns:
            0 (no branches deleted in mock)
        """
        return 0
