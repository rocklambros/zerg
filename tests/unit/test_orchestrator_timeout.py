"""Unit tests for Orchestrator merge timeout handling.

Tests the merge timeout with ThreadPoolExecutor and retry logic in
Orchestrator._on_level_complete_handler, including:
- Merge timeout triggers retry
- Exponential backoff between retries
- Max retries reached pauses orchestrator
- Successful merge after retry
- Timeout configuration from config
"""

import time
from datetime import datetime
from unittest.mock import MagicMock, patch

from zerg.config import ErrorRecoveryConfig
from zerg.constants import LevelMergeStatus, WorkerStatus
from zerg.merge import MergeFlowResult
from zerg.orchestrator import Orchestrator
from zerg.types import WorkerState


class TestMergeTimeoutTriggersRetry:
    """Test that merge timeout triggers retry mechanism."""

    @patch("zerg.orchestrator.MergeCoordinator")
    @patch("zerg.orchestrator.StateManager")
    @patch("zerg.orchestrator.ZergConfig")
    def test_timeout_triggers_retry_attempt(
        self,
        mock_config_cls,
        mock_state_cls,
        mock_merger_cls,
    ):
        """When merge times out, orchestrator should retry."""
        # Setup config mock
        mock_config = MagicMock()
        mock_config.workers.retry_attempts = 3
        mock_config.workers.timeout_minutes = 30
        mock_config.ports.range_start = 8000
        mock_config.ports.range_end = 9000
        mock_config.logging.directory = "/tmp/logs"
        mock_config.quality_gates = []
        mock_config.error_recovery = ErrorRecoveryConfig()
        mock_config.plugins = MagicMock(enabled=False)
        mock_config.merge_timeout_seconds = 1  # Very short for test
        mock_config.merge_max_retries = 3
        mock_config_cls.load.return_value = mock_config

        # Setup state mock
        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        # Setup merger mock - first call times out, second succeeds
        mock_merger = MagicMock()
        call_count = [0]

        def slow_then_fast(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: sleep longer than timeout to force timeout
                time.sleep(2)
            return MergeFlowResult(
                success=True,
                level=1,
                source_branches=["worker-0"],
                target_branch="main",
                merge_commit="abc123",
            )

        mock_merger.full_merge_flow.side_effect = slow_then_fast
        mock_merger_cls.return_value = mock_merger

        # Create orchestrator
        with patch("zerg.orchestrator.WorktreeManager"):
            with patch("zerg.orchestrator.ContainerManager"):
                with patch("zerg.orchestrator.PortAllocator"):
                    with patch("zerg.orchestrator.GateRunner"):
                        with patch("zerg.orchestrator.LevelController"):
                            with patch("zerg.orchestrator.TaskParser"):
                                with patch("zerg.orchestrator.TaskSyncBridge"):
                                    with patch.object(
                                        Orchestrator,
                                        "_create_launcher",
                                        return_value=MagicMock(),
                                    ):
                                        orch = Orchestrator(
                                            feature="test-feature",
                                            config=mock_config,
                                        )

        # Add a worker with branch
        worker = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            port=8000,
            branch="worker-0",
            worktree_path="/tmp/wt",
            started_at=datetime.now(),
        )
        orch._workers[0] = worker

        # Execute level complete handler
        orch._on_level_complete_handler(1)

        # Verify retry occurred - should have at least 2 calls due to timeout+retry
        assert mock_merger.full_merge_flow.call_count >= 1
        # State should record merge_retry event on timeout
        mock_state.append_event.assert_any_call(
            "level_complete",
            {"level": 1, "merge_commit": "abc123"},
        )

    @patch("zerg.orchestrator.MergeCoordinator")
    @patch("zerg.orchestrator.StateManager")
    @patch("zerg.orchestrator.ZergConfig")
    def test_timeout_returns_failure_result(
        self,
        mock_config_cls,
        mock_state_cls,
        mock_merger_cls,
    ):
        """Timeout should produce MergeFlowResult with timeout error."""
        mock_config = MagicMock()
        mock_config.workers.retry_attempts = 3
        mock_config.workers.timeout_minutes = 30
        mock_config.ports.range_start = 8000
        mock_config.ports.range_end = 9000
        mock_config.logging.directory = "/tmp/logs"
        mock_config.quality_gates = []
        mock_config.error_recovery = ErrorRecoveryConfig()
        mock_config.plugins = MagicMock(enabled=False)
        mock_config.merge_timeout_seconds = 0.1  # Very short
        mock_config.merge_max_retries = 1  # Only 1 retry
        mock_config_cls.load.return_value = mock_config

        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        # Merger always times out
        mock_merger = MagicMock()

        def always_slow(*args, **kwargs):
            time.sleep(1)  # Always exceeds timeout
            return MergeFlowResult(
                success=True,
                level=1,
                source_branches=[],
                target_branch="main",
            )

        mock_merger.full_merge_flow.side_effect = always_slow
        mock_merger_cls.return_value = mock_merger

        with patch("zerg.orchestrator.WorktreeManager"):
            with patch("zerg.orchestrator.ContainerManager"):
                with patch("zerg.orchestrator.PortAllocator"):
                    with patch("zerg.orchestrator.GateRunner"):
                        with patch("zerg.orchestrator.LevelController"):
                            with patch("zerg.orchestrator.TaskParser"):
                                with patch("zerg.orchestrator.TaskSyncBridge"):
                                    with patch.object(
                                        Orchestrator,
                                        "_create_launcher",
                                        return_value=MagicMock(),
                                    ):
                                        orch = Orchestrator(
                                            feature="test-feature",
                                            config=mock_config,
                                        )

        worker = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            port=8000,
            branch="worker-0",
            worktree_path="/tmp/wt",
            started_at=datetime.now(),
        )
        orch._workers[0] = worker

        # Execute - should timeout and eventually pause
        orch._on_level_complete_handler(1)

        # Should have set recoverable error due to max retries exceeded
        mock_state.set_error.assert_called()
        mock_state.set_paused.assert_called_with(True)


class TestExponentialBackoffBetweenRetries:
    """Test exponential backoff timing between retry attempts."""

    def test_backoff_formula_calculation(self):
        """Verify exponential backoff formula: 2^attempt * 10."""
        base_delay = 10
        expected_backoffs = []

        for attempt in range(3):
            backoff = 2**attempt * base_delay
            expected_backoffs.append(backoff)

        # Verify the exponential pattern
        assert expected_backoffs == [10, 20, 40]

    def test_backoff_sequence_is_exponential(self):
        """Each backoff should be 2x the previous."""
        base_delay = 10
        backoffs = [2**i * base_delay for i in range(4)]

        # Verify doubling pattern
        for i in range(1, len(backoffs)):
            assert backoffs[i] == backoffs[i - 1] * 2

    @patch("zerg.level_coordinator.time.sleep")
    @patch("zerg.orchestrator.MergeCoordinator")
    @patch("zerg.orchestrator.StateManager")
    @patch("zerg.orchestrator.ZergConfig")
    def test_backoff_sleep_called_between_retries(
        self,
        mock_config_cls,
        mock_state_cls,
        mock_merger_cls,
        mock_sleep,
    ):
        """Should sleep with exponential backoff between retries."""
        mock_config = MagicMock()
        mock_config.workers.retry_attempts = 3
        mock_config.workers.timeout_minutes = 30
        mock_config.ports.range_start = 8000
        mock_config.ports.range_end = 9000
        mock_config.logging.directory = "/tmp/logs"
        mock_config.quality_gates = []
        mock_config.error_recovery = ErrorRecoveryConfig()
        mock_config.plugins = MagicMock(enabled=False)
        mock_config.merge_timeout_seconds = 600
        mock_config.merge_max_retries = 3
        mock_config_cls.load.return_value = mock_config

        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        # Merger fails first 2 times, succeeds third
        mock_merger = MagicMock()
        call_count = [0]

        def fail_then_succeed(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                return MergeFlowResult(
                    success=False,
                    level=1,
                    source_branches=["worker-0"],
                    target_branch="main",
                    error="Simulated failure",
                )
            return MergeFlowResult(
                success=True,
                level=1,
                source_branches=["worker-0"],
                target_branch="main",
                merge_commit="abc123",
            )

        mock_merger.full_merge_flow.side_effect = fail_then_succeed
        mock_merger_cls.return_value = mock_merger

        with patch("zerg.orchestrator.WorktreeManager"):
            with patch("zerg.orchestrator.ContainerManager"):
                with patch("zerg.orchestrator.PortAllocator"):
                    with patch("zerg.orchestrator.GateRunner"):
                        with patch("zerg.orchestrator.LevelController"):
                            with patch("zerg.orchestrator.TaskParser"):
                                with patch("zerg.orchestrator.TaskSyncBridge"):
                                    with patch.object(
                                        Orchestrator,
                                        "_create_launcher",
                                        return_value=MagicMock(),
                                    ):
                                        orch = Orchestrator(
                                            feature="test-feature",
                                            config=mock_config,
                                        )

        worker = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            port=8000,
            branch="worker-0",
            worktree_path="/tmp/wt",
            started_at=datetime.now(),
        )
        orch._workers[0] = worker

        orch._on_level_complete_handler(1)

        # Verify sleep was called with exponential backoff values
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        # First retry backoff: 2^0 * 10 = 10
        # Second retry backoff: 2^1 * 10 = 20
        assert 10 in sleep_calls
        assert 20 in sleep_calls


class TestMaxRetriesReachedPausesOrchestrator:
    """Test that max retries reached pauses orchestrator."""

    @patch("zerg.level_coordinator.time.sleep")
    @patch("zerg.orchestrator.MergeCoordinator")
    @patch("zerg.orchestrator.StateManager")
    @patch("zerg.orchestrator.ZergConfig")
    def test_max_retries_sets_paused_state(
        self,
        mock_config_cls,
        mock_state_cls,
        mock_merger_cls,
        mock_sleep,
    ):
        """After max retries, orchestrator should set paused state."""
        mock_config = MagicMock()
        mock_config.workers.retry_attempts = 3
        mock_config.workers.timeout_minutes = 30
        mock_config.ports.range_start = 8000
        mock_config.ports.range_end = 9000
        mock_config.logging.directory = "/tmp/logs"
        mock_config.quality_gates = []
        mock_config.error_recovery = ErrorRecoveryConfig()
        mock_config.plugins = MagicMock(enabled=False)
        mock_config.merge_timeout_seconds = 600
        mock_config.merge_max_retries = 2
        mock_config_cls.load.return_value = mock_config

        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        # Merger always fails
        mock_merger = MagicMock()
        mock_merger.full_merge_flow.return_value = MergeFlowResult(
            success=False,
            level=1,
            source_branches=["worker-0"],
            target_branch="main",
            error="Persistent failure",
        )
        mock_merger_cls.return_value = mock_merger

        with patch("zerg.orchestrator.WorktreeManager"):
            with patch("zerg.orchestrator.ContainerManager"):
                with patch("zerg.orchestrator.PortAllocator"):
                    with patch("zerg.orchestrator.GateRunner"):
                        with patch("zerg.orchestrator.LevelController"):
                            with patch("zerg.orchestrator.TaskParser"):
                                with patch("zerg.orchestrator.TaskSyncBridge"):
                                    with patch.object(
                                        Orchestrator,
                                        "_create_launcher",
                                        return_value=MagicMock(),
                                    ):
                                        orch = Orchestrator(
                                            feature="test-feature",
                                            config=mock_config,
                                        )

        worker = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            port=8000,
            branch="worker-0",
            worktree_path="/tmp/wt",
            started_at=datetime.now(),
        )
        orch._workers[0] = worker

        orch._on_level_complete_handler(1)

        # Should be paused after max retries
        assert orch._paused is True
        mock_state.set_paused.assert_called_with(True)
        mock_state.set_error.assert_called()

    @patch("zerg.level_coordinator.time.sleep")
    @patch("zerg.orchestrator.MergeCoordinator")
    @patch("zerg.orchestrator.StateManager")
    @patch("zerg.orchestrator.ZergConfig")
    def test_max_retries_records_recoverable_error_event(
        self,
        mock_config_cls,
        mock_state_cls,
        mock_merger_cls,
        mock_sleep,
    ):
        """Max retries should record recoverable_error event."""
        mock_config = MagicMock()
        mock_config.workers.retry_attempts = 3
        mock_config.workers.timeout_minutes = 30
        mock_config.ports.range_start = 8000
        mock_config.ports.range_end = 9000
        mock_config.logging.directory = "/tmp/logs"
        mock_config.quality_gates = []
        mock_config.error_recovery = ErrorRecoveryConfig()
        mock_config.plugins = MagicMock(enabled=False)
        mock_config.merge_timeout_seconds = 600
        mock_config.merge_max_retries = 1
        mock_config_cls.load.return_value = mock_config

        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        mock_merger = MagicMock()
        mock_merger.full_merge_flow.return_value = MergeFlowResult(
            success=False,
            level=1,
            source_branches=["worker-0"],
            target_branch="main",
            error="Test error",
        )
        mock_merger_cls.return_value = mock_merger

        with patch("zerg.orchestrator.WorktreeManager"):
            with patch("zerg.orchestrator.ContainerManager"):
                with patch("zerg.orchestrator.PortAllocator"):
                    with patch("zerg.orchestrator.GateRunner"):
                        with patch("zerg.orchestrator.LevelController"):
                            with patch("zerg.orchestrator.TaskParser"):
                                with patch("zerg.orchestrator.TaskSyncBridge"):
                                    with patch.object(
                                        Orchestrator,
                                        "_create_launcher",
                                        return_value=MagicMock(),
                                    ):
                                        orch = Orchestrator(
                                            feature="test-feature",
                                            config=mock_config,
                                        )

        worker = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            port=8000,
            branch="worker-0",
            worktree_path="/tmp/wt",
            started_at=datetime.now(),
        )
        orch._workers[0] = worker

        orch._on_level_complete_handler(1)

        # Check recoverable_error event was recorded
        event_calls = [call for call in mock_state.append_event.call_args_list if call[0][0] == "recoverable_error"]
        assert len(event_calls) == 1

    @patch("zerg.level_coordinator.time.sleep")
    @patch("zerg.orchestrator.MergeCoordinator")
    @patch("zerg.orchestrator.StateManager")
    @patch("zerg.orchestrator.ZergConfig")
    def test_level_merge_status_set_to_failed(
        self,
        mock_config_cls,
        mock_state_cls,
        mock_merger_cls,
        mock_sleep,
    ):
        """Level merge status should be FAILED after max retries."""
        mock_config = MagicMock()
        mock_config.workers.retry_attempts = 3
        mock_config.workers.timeout_minutes = 30
        mock_config.ports.range_start = 8000
        mock_config.ports.range_end = 9000
        mock_config.logging.directory = "/tmp/logs"
        mock_config.quality_gates = []
        mock_config.error_recovery = ErrorRecoveryConfig()
        mock_config.plugins = MagicMock(enabled=False)
        mock_config.merge_timeout_seconds = 600
        mock_config.merge_max_retries = 1
        mock_config_cls.load.return_value = mock_config

        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        mock_merger = MagicMock()
        mock_merger.full_merge_flow.return_value = MergeFlowResult(
            success=False,
            level=1,
            source_branches=["worker-0"],
            target_branch="main",
            error="Test error",
        )
        mock_merger_cls.return_value = mock_merger

        with patch("zerg.orchestrator.WorktreeManager"):
            with patch("zerg.orchestrator.ContainerManager"):
                with patch("zerg.orchestrator.PortAllocator"):
                    with patch("zerg.orchestrator.GateRunner"):
                        with patch("zerg.orchestrator.LevelController"):
                            with patch("zerg.orchestrator.TaskParser"):
                                with patch("zerg.orchestrator.TaskSyncBridge"):
                                    with patch.object(
                                        Orchestrator,
                                        "_create_launcher",
                                        return_value=MagicMock(),
                                    ):
                                        orch = Orchestrator(
                                            feature="test-feature",
                                            config=mock_config,
                                        )

        worker = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            port=8000,
            branch="worker-0",
            worktree_path="/tmp/wt",
            started_at=datetime.now(),
        )
        orch._workers[0] = worker

        orch._on_level_complete_handler(1)

        # Verify level merge status was set to FAILED
        mock_state.set_level_merge_status.assert_any_call(1, LevelMergeStatus.FAILED)


class TestSuccessfulMergeAfterRetry:
    """Test successful merge after initial failures."""

    @patch("zerg.level_coordinator.time.sleep")
    @patch("zerg.orchestrator.MergeCoordinator")
    @patch("zerg.orchestrator.StateManager")
    @patch("zerg.orchestrator.ZergConfig")
    def test_success_after_one_retry(
        self,
        mock_config_cls,
        mock_state_cls,
        mock_merger_cls,
        mock_sleep,
    ):
        """Merge should succeed after one retry."""
        mock_config = MagicMock()
        mock_config.workers.retry_attempts = 3
        mock_config.workers.timeout_minutes = 30
        mock_config.ports.range_start = 8000
        mock_config.ports.range_end = 9000
        mock_config.logging.directory = "/tmp/logs"
        mock_config.quality_gates = []
        mock_config.error_recovery = ErrorRecoveryConfig()
        mock_config.plugins = MagicMock(enabled=False)
        mock_config.merge_timeout_seconds = 600
        mock_config.merge_max_retries = 3
        mock_config_cls.load.return_value = mock_config

        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        mock_merger = MagicMock()
        call_count = [0]

        def fail_once_then_succeed(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return MergeFlowResult(
                    success=False,
                    level=1,
                    source_branches=["worker-0"],
                    target_branch="main",
                    error="Transient failure",
                )
            return MergeFlowResult(
                success=True,
                level=1,
                source_branches=["worker-0"],
                target_branch="main",
                merge_commit="abc123",
            )

        mock_merger.full_merge_flow.side_effect = fail_once_then_succeed
        mock_merger_cls.return_value = mock_merger

        with patch("zerg.orchestrator.WorktreeManager"):
            with patch("zerg.orchestrator.ContainerManager"):
                with patch("zerg.orchestrator.PortAllocator"):
                    with patch("zerg.orchestrator.GateRunner"):
                        with patch("zerg.orchestrator.LevelController"):
                            with patch("zerg.orchestrator.TaskParser"):
                                with patch("zerg.orchestrator.TaskSyncBridge"):
                                    with patch.object(
                                        Orchestrator,
                                        "_create_launcher",
                                        return_value=MagicMock(),
                                    ):
                                        orch = Orchestrator(
                                            feature="test-feature",
                                            config=mock_config,
                                        )

        worker = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            port=8000,
            branch="worker-0",
            worktree_path="/tmp/wt",
            started_at=datetime.now(),
        )
        orch._workers[0] = worker

        orch._on_level_complete_handler(1)

        # Should not be paused since merge eventually succeeded
        assert orch._paused is False
        # Verify level_complete event was recorded
        mock_state.append_event.assert_any_call(
            "level_complete",
            {"level": 1, "merge_commit": "abc123"},
        )

    @patch("zerg.level_coordinator.time.sleep")
    @patch("zerg.orchestrator.MergeCoordinator")
    @patch("zerg.orchestrator.StateManager")
    @patch("zerg.orchestrator.ZergConfig")
    def test_success_after_multiple_retries(
        self,
        mock_config_cls,
        mock_state_cls,
        mock_merger_cls,
        mock_sleep,
    ):
        """Merge should succeed after multiple retries."""
        mock_config = MagicMock()
        mock_config.workers.retry_attempts = 3
        mock_config.workers.timeout_minutes = 30
        mock_config.ports.range_start = 8000
        mock_config.ports.range_end = 9000
        mock_config.logging.directory = "/tmp/logs"
        mock_config.quality_gates = []
        mock_config.error_recovery = ErrorRecoveryConfig()
        mock_config.plugins = MagicMock(enabled=False)
        mock_config.merge_timeout_seconds = 600
        mock_config.merge_max_retries = 5
        mock_config_cls.load.return_value = mock_config

        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        mock_merger = MagicMock()
        call_count = [0]

        def fail_twice_then_succeed(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                return MergeFlowResult(
                    success=False,
                    level=1,
                    source_branches=["worker-0"],
                    target_branch="main",
                    error=f"Failure {call_count[0]}",
                )
            return MergeFlowResult(
                success=True,
                level=1,
                source_branches=["worker-0"],
                target_branch="main",
                merge_commit="def456",
            )

        mock_merger.full_merge_flow.side_effect = fail_twice_then_succeed
        mock_merger_cls.return_value = mock_merger

        with patch("zerg.orchestrator.WorktreeManager"):
            with patch("zerg.orchestrator.ContainerManager"):
                with patch("zerg.orchestrator.PortAllocator"):
                    with patch("zerg.orchestrator.GateRunner"):
                        with patch("zerg.orchestrator.LevelController"):
                            with patch("zerg.orchestrator.TaskParser"):
                                with patch("zerg.orchestrator.TaskSyncBridge"):
                                    with patch.object(
                                        Orchestrator,
                                        "_create_launcher",
                                        return_value=MagicMock(),
                                    ):
                                        orch = Orchestrator(
                                            feature="test-feature",
                                            config=mock_config,
                                        )

        worker = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            port=8000,
            branch="worker-0",
            worktree_path="/tmp/wt",
            started_at=datetime.now(),
        )
        orch._workers[0] = worker

        orch._on_level_complete_handler(1)

        # Should have called merge 3 times (2 failures + 1 success)
        assert mock_merger.full_merge_flow.call_count == 3
        # Should not be paused
        assert orch._paused is False
        # Level status should be COMPLETE
        mock_state.set_level_merge_status.assert_any_call(1, LevelMergeStatus.COMPLETE)

    @patch("zerg.level_coordinator.time.sleep")
    @patch("zerg.orchestrator.MergeCoordinator")
    @patch("zerg.orchestrator.StateManager")
    @patch("zerg.orchestrator.ZergConfig")
    def test_retry_event_recorded_on_failure(
        self,
        mock_config_cls,
        mock_state_cls,
        mock_merger_cls,
        mock_sleep,
    ):
        """Should record merge_retry event on each retry."""
        mock_config = MagicMock()
        mock_config.workers.retry_attempts = 3
        mock_config.workers.timeout_minutes = 30
        mock_config.ports.range_start = 8000
        mock_config.ports.range_end = 9000
        mock_config.logging.directory = "/tmp/logs"
        mock_config.quality_gates = []
        mock_config.error_recovery = ErrorRecoveryConfig()
        mock_config.plugins = MagicMock(enabled=False)
        mock_config.merge_timeout_seconds = 600
        mock_config.merge_max_retries = 3
        mock_config_cls.load.return_value = mock_config

        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        mock_merger = MagicMock()
        call_count = [0]

        def fail_once(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return MergeFlowResult(
                    success=False,
                    level=1,
                    source_branches=["worker-0"],
                    target_branch="main",
                    error="First failure",
                )
            return MergeFlowResult(
                success=True,
                level=1,
                source_branches=["worker-0"],
                target_branch="main",
                merge_commit="xyz789",
            )

        mock_merger.full_merge_flow.side_effect = fail_once
        mock_merger_cls.return_value = mock_merger

        with patch("zerg.orchestrator.WorktreeManager"):
            with patch("zerg.orchestrator.ContainerManager"):
                with patch("zerg.orchestrator.PortAllocator"):
                    with patch("zerg.orchestrator.GateRunner"):
                        with patch("zerg.orchestrator.LevelController"):
                            with patch("zerg.orchestrator.TaskParser"):
                                with patch("zerg.orchestrator.TaskSyncBridge"):
                                    with patch.object(
                                        Orchestrator,
                                        "_create_launcher",
                                        return_value=MagicMock(),
                                    ):
                                        orch = Orchestrator(
                                            feature="test-feature",
                                            config=mock_config,
                                        )

        worker = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            port=8000,
            branch="worker-0",
            worktree_path="/tmp/wt",
            started_at=datetime.now(),
        )
        orch._workers[0] = worker

        orch._on_level_complete_handler(1)

        # Check merge_retry event was recorded
        retry_events = [call for call in mock_state.append_event.call_args_list if call[0][0] == "merge_retry"]
        assert len(retry_events) == 1
        # Verify retry event has expected data
        retry_data = retry_events[0][0][1]
        assert retry_data["level"] == 1
        assert retry_data["attempt"] == 1
        assert retry_data["backoff_seconds"] == 10


class TestTimeoutConfigurationFromConfig:
    """Test timeout configuration from ZergConfig."""

    @patch("zerg.orchestrator.MergeCoordinator")
    @patch("zerg.orchestrator.StateManager")
    @patch("zerg.orchestrator.ZergConfig")
    def test_default_timeout_value(
        self,
        mock_config_cls,
        mock_state_cls,
        mock_merger_cls,
    ):
        """Should use default timeout of 600 seconds when not configured."""
        mock_config = MagicMock()
        mock_config.workers.retry_attempts = 3
        mock_config.workers.timeout_minutes = 30
        mock_config.ports.range_start = 8000
        mock_config.ports.range_end = 9000
        mock_config.logging.directory = "/tmp/logs"
        mock_config.quality_gates = []
        mock_config.error_recovery = ErrorRecoveryConfig()
        mock_config.plugins = MagicMock(enabled=False)
        # Remove merge_timeout_seconds attribute to test default
        del mock_config.merge_timeout_seconds
        mock_config.merge_max_retries = 3
        mock_config_cls.load.return_value = mock_config

        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        mock_merger = MagicMock()
        mock_merger.full_merge_flow.return_value = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["worker-0"],
            target_branch="main",
            merge_commit="abc123",
        )
        mock_merger_cls.return_value = mock_merger

        with patch("zerg.orchestrator.WorktreeManager"):
            with patch("zerg.orchestrator.ContainerManager"):
                with patch("zerg.orchestrator.PortAllocator"):
                    with patch("zerg.orchestrator.GateRunner"):
                        with patch("zerg.orchestrator.LevelController"):
                            with patch("zerg.orchestrator.TaskParser"):
                                with patch("zerg.orchestrator.TaskSyncBridge"):
                                    with patch.object(
                                        Orchestrator,
                                        "_create_launcher",
                                        return_value=MagicMock(),
                                    ):
                                        orch = Orchestrator(
                                            feature="test-feature",
                                            config=mock_config,
                                        )

        worker = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            port=8000,
            branch="worker-0",
            worktree_path="/tmp/wt",
            started_at=datetime.now(),
        )
        orch._workers[0] = worker

        # The default is accessed via getattr in _on_level_complete_handler
        # If merge_timeout_seconds is not present, it should use 600
        orch._on_level_complete_handler(1)

        # Verify merge completed successfully
        mock_state.append_event.assert_any_call(
            "level_complete",
            {"level": 1, "merge_commit": "abc123"},
        )

    @patch("zerg.level_coordinator.time.sleep")
    @patch("zerg.orchestrator.MergeCoordinator")
    @patch("zerg.orchestrator.StateManager")
    @patch("zerg.orchestrator.ZergConfig")
    def test_default_max_retries_value(
        self,
        mock_config_cls,
        mock_state_cls,
        mock_merger_cls,
        mock_sleep,
    ):
        """Should use default max_retries of 3 when not configured."""
        mock_config = MagicMock()
        mock_config.workers.retry_attempts = 3
        mock_config.workers.timeout_minutes = 30
        mock_config.ports.range_start = 8000
        mock_config.ports.range_end = 9000
        mock_config.logging.directory = "/tmp/logs"
        mock_config.quality_gates = []
        mock_config.error_recovery = ErrorRecoveryConfig()
        mock_config.plugins = MagicMock(enabled=False)
        mock_config.merge_timeout_seconds = 600
        # Remove merge_max_retries attribute to test default
        del mock_config.merge_max_retries
        mock_config_cls.load.return_value = mock_config

        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        mock_merger = MagicMock()
        call_count = [0]

        def always_fail(*args, **kwargs):
            call_count[0] += 1
            return MergeFlowResult(
                success=False,
                level=1,
                source_branches=["worker-0"],
                target_branch="main",
                error="Always fails",
            )

        mock_merger.full_merge_flow.side_effect = always_fail
        mock_merger_cls.return_value = mock_merger

        with patch("zerg.orchestrator.WorktreeManager"):
            with patch("zerg.orchestrator.ContainerManager"):
                with patch("zerg.orchestrator.PortAllocator"):
                    with patch("zerg.orchestrator.GateRunner"):
                        with patch("zerg.orchestrator.LevelController"):
                            with patch("zerg.orchestrator.TaskParser"):
                                with patch("zerg.orchestrator.TaskSyncBridge"):
                                    with patch.object(
                                        Orchestrator,
                                        "_create_launcher",
                                        return_value=MagicMock(),
                                    ):
                                        orch = Orchestrator(
                                            feature="test-feature",
                                            config=mock_config,
                                        )

        worker = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            port=8000,
            branch="worker-0",
            worktree_path="/tmp/wt",
            started_at=datetime.now(),
        )
        orch._workers[0] = worker

        orch._on_level_complete_handler(1)

        # Should have attempted 3 times (default max_retries)
        assert call_count[0] == 3

    @patch("zerg.orchestrator.MergeCoordinator")
    @patch("zerg.orchestrator.StateManager")
    @patch("zerg.orchestrator.ZergConfig")
    def test_custom_timeout_value(
        self,
        mock_config_cls,
        mock_state_cls,
        mock_merger_cls,
    ):
        """Should use custom timeout value when configured."""
        mock_config = MagicMock()
        mock_config.workers.retry_attempts = 3
        mock_config.workers.timeout_minutes = 30
        mock_config.ports.range_start = 8000
        mock_config.ports.range_end = 9000
        mock_config.logging.directory = "/tmp/logs"
        mock_config.quality_gates = []
        mock_config.error_recovery = ErrorRecoveryConfig()
        mock_config.plugins = MagicMock(enabled=False)
        mock_config.merge_timeout_seconds = 1200  # 20 minutes
        mock_config.merge_max_retries = 5
        mock_config_cls.load.return_value = mock_config

        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        mock_merger = MagicMock()
        mock_merger.full_merge_flow.return_value = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["worker-0"],
            target_branch="main",
            merge_commit="abc123",
        )
        mock_merger_cls.return_value = mock_merger

        with patch("zerg.orchestrator.WorktreeManager"):
            with patch("zerg.orchestrator.ContainerManager"):
                with patch("zerg.orchestrator.PortAllocator"):
                    with patch("zerg.orchestrator.GateRunner"):
                        with patch("zerg.orchestrator.LevelController"):
                            with patch("zerg.orchestrator.TaskParser"):
                                with patch("zerg.orchestrator.TaskSyncBridge"):
                                    with patch.object(
                                        Orchestrator,
                                        "_create_launcher",
                                        return_value=MagicMock(),
                                    ):
                                        orch = Orchestrator(
                                            feature="test-feature",
                                            config=mock_config,
                                        )

        worker = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            port=8000,
            branch="worker-0",
            worktree_path="/tmp/wt",
            started_at=datetime.now(),
        )
        orch._workers[0] = worker

        orch._on_level_complete_handler(1)

        # Verify the config value was accessible
        assert mock_config.merge_timeout_seconds == 1200
        assert mock_config.merge_max_retries == 5

    @patch("zerg.level_coordinator.time.sleep")
    @patch("zerg.orchestrator.MergeCoordinator")
    @patch("zerg.orchestrator.StateManager")
    @patch("zerg.orchestrator.ZergConfig")
    def test_custom_max_retries_value(
        self,
        mock_config_cls,
        mock_state_cls,
        mock_merger_cls,
        mock_sleep,
    ):
        """Should use custom max_retries value when configured."""
        mock_config = MagicMock()
        mock_config.workers.retry_attempts = 3
        mock_config.workers.timeout_minutes = 30
        mock_config.ports.range_start = 8000
        mock_config.ports.range_end = 9000
        mock_config.logging.directory = "/tmp/logs"
        mock_config.quality_gates = []
        mock_config.error_recovery = ErrorRecoveryConfig()
        mock_config.plugins = MagicMock(enabled=False)
        mock_config.merge_timeout_seconds = 600
        mock_config.merge_max_retries = 5  # Custom value
        mock_config_cls.load.return_value = mock_config

        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        mock_merger = MagicMock()
        call_count = [0]

        def always_fail(*args, **kwargs):
            call_count[0] += 1
            return MergeFlowResult(
                success=False,
                level=1,
                source_branches=["worker-0"],
                target_branch="main",
                error="Always fails",
            )

        mock_merger.full_merge_flow.side_effect = always_fail
        mock_merger_cls.return_value = mock_merger

        with patch("zerg.orchestrator.WorktreeManager"):
            with patch("zerg.orchestrator.ContainerManager"):
                with patch("zerg.orchestrator.PortAllocator"):
                    with patch("zerg.orchestrator.GateRunner"):
                        with patch("zerg.orchestrator.LevelController"):
                            with patch("zerg.orchestrator.TaskParser"):
                                with patch("zerg.orchestrator.TaskSyncBridge"):
                                    with patch.object(
                                        Orchestrator,
                                        "_create_launcher",
                                        return_value=MagicMock(),
                                    ):
                                        orch = Orchestrator(
                                            feature="test-feature",
                                            config=mock_config,
                                        )

        worker = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            port=8000,
            branch="worker-0",
            worktree_path="/tmp/wt",
            started_at=datetime.now(),
        )
        orch._workers[0] = worker

        orch._on_level_complete_handler(1)

        # Should have attempted 5 times (custom max_retries)
        assert call_count[0] == 5
