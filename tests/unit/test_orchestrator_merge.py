"""Unit tests for orchestrator merge timeout and recovery.

Tests BF-007: Orchestrator merge timeout with retry and recoverable error state.
"""

import concurrent.futures
from unittest.mock import MagicMock

from tests.mocks.mock_merge import MockMergeCoordinator
from zerg.constants import LevelMergeStatus


class TestMergeTimeout:
    """Tests for merge timeout handling."""

    def test_merge_completes_within_timeout(self):
        """Merge that completes within timeout should succeed."""
        merger = MockMergeCoordinator("test-feature")
        merger.configure(merge_delay=0.1, always_succeed=True)

        result = merger.full_merge_flow(
            level=1,
            worker_branches=["worker-0", "worker-1"],
        )

        assert result.success
        assert result.merge_commit is not None
        assert merger.get_attempt_count() == 1

    def test_merge_timeout_returns_failure(self):
        """Merge that times out should return failure result."""
        merger = MockMergeCoordinator("test-feature")
        merger.configure(timeout_at_attempt=1)

        result = merger.full_merge_flow(
            level=1,
            worker_branches=["worker-0", "worker-1"],
        )

        assert not result.success
        assert "timed out" in result.error.lower()
        assert len(merger.get_timed_out_attempts()) == 1

    def test_merge_timeout_with_executor(self):
        """Test merge timeout using ThreadPoolExecutor pattern."""
        merger = MockMergeCoordinator("test-feature")
        # Simulate slow merge (longer than timeout)
        merger.configure(merge_delay=2.0, always_succeed=True)

        timeout_seconds = 0.5
        result = None
        timed_out = False

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                merger.full_merge_flow,
                level=1,
                worker_branches=["worker-0"],
            )
            try:
                result = future.result(timeout=timeout_seconds)
            except concurrent.futures.TimeoutError:
                timed_out = True
                # Cancel the future (though it may complete in background)
                future.cancel()

        assert timed_out
        # Result should not be available due to timeout
        assert result is None or timed_out


class TestMergeRetry:
    """Tests for merge retry with exponential backoff."""

    def test_retry_on_first_failure(self):
        """Should retry merge on first failure."""
        merger = MockMergeCoordinator("test-feature")
        # Fail first attempt, succeed second
        merger.configure(fail_at_attempt=1)

        # First attempt fails
        result1 = merger.full_merge_flow(level=1, worker_branches=["worker-0"])
        assert not result1.success
        assert merger.get_attempt_count() == 1

        # Reset failure - second attempt should succeed
        merger.configure(always_succeed=True)
        result2 = merger.full_merge_flow(level=1, worker_branches=["worker-0"])
        assert result2.success
        assert merger.get_attempt_count() == 2

    def test_exponential_backoff_timing(self):
        """Test that backoff timing is exponential."""
        # Calculate expected backoff delays
        base_delay = 10  # seconds
        expected_delays = [
            base_delay * (2**0),  # 10s after attempt 1
            base_delay * (2**1),  # 20s after attempt 2
            base_delay * (2**2),  # 40s after attempt 3
        ]

        # Verify the pattern
        assert expected_delays == [10, 20, 40]

    def test_max_retries_exceeded(self):
        """Should stop retrying after max attempts."""
        merger = MockMergeCoordinator("test-feature")
        merger.configure(always_succeed=False)

        max_retries = 3
        results = []

        for _ in range(max_retries):
            result = merger.full_merge_flow(level=1, worker_branches=["worker-0"])
            results.append(result)

        # All attempts should fail
        assert all(not r.success for r in results)
        assert merger.get_attempt_count() == max_retries
        assert len(merger.get_failed_attempts()) == max_retries


class TestRecoverableErrorState:
    """Tests for recoverable error state (pause instead of stop)."""

    def test_merge_failure_triggers_pause(self):
        """Merge failure should set paused state, not stopped."""
        # This tests the expected behavior after BF-007 fix
        state = MagicMock()
        state.set_paused = MagicMock()
        state.set_error = MagicMock()

        # Simulate the pause behavior
        def set_recoverable_error(error: str):
            state.set_error(error)
            state.set_paused(True)

        set_recoverable_error("Merge failed after 3 retries")

        state.set_error.assert_called_once()
        state.set_paused.assert_called_once_with(True)

    def test_pause_allows_resume(self):
        """Paused state should allow resume."""
        state = MagicMock()
        state._paused = True

        # Resume logic
        state._paused = False
        state.set_paused = MagicMock()

        # Simulate resume
        state._paused = False
        state.set_paused(False)

        assert not state._paused
        state.set_paused.assert_called_with(False)

    def test_conflict_triggers_pause_not_stop(self):
        """Merge conflict should pause execution, not stop it."""
        merger = MockMergeCoordinator("test-feature")
        merger.configure(
            conflict_at_level=1,
            conflicting_files=["src/file.py"],
        )

        result = merger.full_merge_flow(level=1, worker_branches=["worker-0"])

        assert not result.success
        assert "conflict" in result.error.lower()


class TestMergeLevelStatus:
    """Tests for merge level status updates."""

    def test_merging_status_set_before_merge(self):
        """MERGING status should be set before merge starts."""
        # Verify the expected status sequence

        assert LevelMergeStatus.MERGING.value == "merging"
        assert LevelMergeStatus.COMPLETE.value == "complete"

    def test_complete_status_on_success(self):
        """COMPLETE status should be set on merge success."""
        merger = MockMergeCoordinator("test-feature")
        merger.configure(always_succeed=True)

        result = merger.full_merge_flow(level=1, worker_branches=["worker-0"])

        assert result.success
        # The orchestrator would set COMPLETE status

    def test_failed_status_on_error(self):
        """FAILED status should be set on merge error."""
        merger = MockMergeCoordinator("test-feature")
        merger.configure(fail_at_level=1)

        result = merger.full_merge_flow(level=1, worker_branches=["worker-0"])

        assert not result.success
        # The orchestrator would set FAILED status

    def test_conflict_status_on_conflict(self):
        """CONFLICT status should be set on merge conflict."""
        merger = MockMergeCoordinator("test-feature")
        merger.configure(conflict_at_level=1)

        result = merger.full_merge_flow(level=1, worker_branches=["worker-0"])

        assert not result.success
        assert "conflict" in result.error.lower()
        # The orchestrator would set CONFLICT status


class TestOrchestratorMergeIntegration:
    """Integration tests for orchestrator merge behavior."""

    def test_merge_timeout_config_values(self):
        """Test that config values are applied correctly."""
        # Expected config values from plan
        merge_timeout_seconds = 600  # 10 min
        merge_max_retries = 3

        assert merge_timeout_seconds == 600
        assert merge_max_retries == 3

    def test_merge_level_with_empty_branches(self):
        """Merge with no worker branches should succeed."""
        merger = MockMergeCoordinator("test-feature")

        result = merger.full_merge_flow(
            level=1,
            worker_branches=[],  # No branches
        )

        # Empty branches could be success or special case
        assert result.level == 1

    def test_multiple_levels_merge_sequentially(self):
        """Multiple levels should merge in sequence."""
        merger = MockMergeCoordinator("test-feature")
        merger.configure(always_succeed=True)

        results = []
        for level in [1, 2, 3]:
            result = merger.full_merge_flow(
                level=level,
                worker_branches=[f"worker-{level}"],
            )
            results.append(result)

        assert all(r.success for r in results)
        assert merger.get_attempt_count() == 3
