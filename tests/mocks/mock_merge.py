"""Mock MergeCoordinator with timeout and failure simulation.

Provides MockMergeCoordinator for testing orchestrator merge handling
with configurable timeout, retry, and failure scenarios.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from zerg.merge import MergeFlowResult


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

        # Results to return
        self._custom_results: dict[int, MergeFlowResult] = {}

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
    ) -> MockMergeCoordinator:
        """Configure mock behavior.

        Args:
            merge_delay: Simulated merge duration in seconds
            fail_at_attempt: Attempt number to fail at (1-indexed)
            fail_at_level: Level number to fail at
            conflict_at_level: Level to simulate conflict at
            timeout_at_attempt: Attempt to simulate timeout at
            always_succeed: Default success behavior
            gate_failure_levels: Levels where gates fail
            conflicting_files: Files that conflict

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
            self._record_attempt(level, worker_branches or [], target_branch,
                               duration_ms, result.success, result.error, False)
            return result

        # Check for timeout simulation
        if self._timeout_at_attempt == self._attempt_count:
            self._record_attempt(level, worker_branches or [], target_branch,
                               duration_ms, False, "Merge timed out", True)
            return MergeFlowResult(
                success=False,
                level=level,
                source_branches=worker_branches or [],
                target_branch=target_branch,
                error="Merge timed out",
            )

        # Check for attempt-based failure
        if self._fail_at_attempt == self._attempt_count:
            self._record_attempt(level, worker_branches or [], target_branch,
                               duration_ms, False, "Simulated failure at attempt", False)
            return MergeFlowResult(
                success=False,
                level=level,
                source_branches=worker_branches or [],
                target_branch=target_branch,
                error=f"Simulated failure at attempt {self._attempt_count}",
            )

        # Check for level-based failure
        if self._fail_at_level == level:
            self._record_attempt(level, worker_branches or [], target_branch,
                               duration_ms, False, "Simulated failure at level", False)
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
            self._record_attempt(level, worker_branches or [], target_branch,
                               duration_ms, False, error, False)
            return MergeFlowResult(
                success=False,
                level=level,
                source_branches=worker_branches or [],
                target_branch=target_branch,
                error=error,
            )

        # Check for gate failures
        if level in self._gate_failure_levels:
            self._record_attempt(level, worker_branches or [], target_branch,
                               duration_ms, False, "Post-merge gates failed", False)
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
            self._record_attempt(level, worker_branches or [], target_branch,
                               duration_ms, True, None, False)
            return MergeFlowResult(
                success=True,
                level=level,
                source_branches=worker_branches or [],
                target_branch=target_branch,
                merge_commit=merge_commit,
            )

        # Explicit failure
        self._record_attempt(level, worker_branches or [], target_branch,
                           duration_ms, False, "Merge failed", False)
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
        self._attempts.append(MergeAttempt(
            level=level,
            worker_branches=worker_branches,
            target_branch=target_branch,
            duration_ms=duration_ms,
            success=success,
            error=error,
            timed_out=timed_out,
        ))

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

    # Additional methods to match MergeCoordinator interface

    def prepare_merge(self, level: int, target_branch: str = "main") -> str:
        """Mock prepare_merge - returns staging branch name.

        Args:
            level: Level being merged
            target_branch: Target branch

        Returns:
            Staging branch name
        """
        return f"zerg/{self.feature}/staging"

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
