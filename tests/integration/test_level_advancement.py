"""Integration test: level advancement after merge (mocked).

Tests BF-010: Verifies orchestrator level advancement behavior after
merge operations using mocked merge coordinator.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.mocks.mock_merge import MockMergeCoordinator


@pytest.fixture
def mock_orchestrator_deps():
    """Mock orchestrator dependencies matching unit test pattern."""
    with (
        patch("zerg.orchestrator.StateManager") as state_mock,
        patch("zerg.orchestrator.LevelController") as levels_mock,
        patch("zerg.orchestrator.TaskParser") as parser_mock,
        patch("zerg.orchestrator.GateRunner"),
        patch("zerg.orchestrator.WorktreeManager"),
        patch("zerg.orchestrator.ContainerManager"),
        patch("zerg.orchestrator.PortAllocator"),
        patch("zerg.orchestrator.MergeCoordinator") as merge_mock,
        patch("zerg.orchestrator.SubprocessLauncher") as launcher_mock,
        patch("time.sleep"),
    ):
        state = MagicMock()
        state.load.return_value = {}
        state.get_task_status.return_value = None
        state.get_task_retry_count.return_value = 0
        state.get_failed_tasks.return_value = []
        state_mock.return_value = state

        levels = MagicMock()
        levels.current_level = 1
        levels.is_level_complete.return_value = False
        levels.is_level_resolved.return_value = False
        levels.can_advance.return_value = True
        levels.advance_level.return_value = 2
        levels.start_level.return_value = ["TASK-001"]
        levels.get_pending_tasks_for_level.return_value = []
        levels.get_level_task_ids.return_value = ["TASK-001"]
        levels.get_status.return_value = {
            "current_level": 1,
            "total_tasks": 10,
            "completed_tasks": 5,
            "is_complete": False,
        }
        levels_mock.return_value = levels

        parser = MagicMock()
        parser.parse.return_value = None
        parser.get_task.return_value = {"id": "TASK-001", "title": "Test", "level": 1}
        parser_mock.return_value = parser

        # Use our mock merge coordinator
        merger = MockMergeCoordinator("test-feature")
        merger.configure(always_succeed=True)
        merge_mock.return_value = merger

        launcher = MagicMock()
        launcher.spawn.return_value = MagicMock(success=True, worker_id=0, handle=MagicMock())
        launcher_mock.return_value = launcher

        yield {
            "state": state,
            "levels": levels,
            "merge": merger,
            "launcher": launcher,
        }


class TestLevelAdvancementAfterMerge:
    """Integration tests for level advancement after merge."""

    def test_successful_merge_advances_level(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch):
        """Successful merge should allow level advancement."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        from zerg.orchestrator import Orchestrator

        merger = mock_orchestrator_deps["merge"]
        merger.configure(always_succeed=True)

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._running = True

        # Complete level 1
        orch._on_level_complete_handler(1)

        # Merge should have been called
        assert merger.get_attempt_count() >= 1
        assert len(merger.get_successful_attempts()) >= 1

        # State should reflect completion
        mock_orchestrator_deps["state"].set_level_status.assert_called()

    def test_merge_failure_with_retry_eventually_succeeds(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch):
        """Merge failure with retry should eventually succeed."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        from zerg.orchestrator import Orchestrator

        merger = mock_orchestrator_deps["merge"]
        # Fail first attempt, succeed on retry
        merger.configure(fail_at_attempt=1)

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._running = True

        # Complete level 1
        orch._on_level_complete_handler(1)

        # Should have attempted multiple times
        assert merger.get_attempt_count() >= 2
        # At least one should be a retry (after the first failure)
        assert len(merger.get_failed_attempts()) >= 1

    def test_merge_conflict_pauses_execution(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch):
        """Merge conflict should pause execution for intervention."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        from zerg.orchestrator import Orchestrator

        merger = mock_orchestrator_deps["merge"]
        merger.configure(conflict_at_level=1, conflicting_files=["src/file.py"])

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._running = True

        orch._on_level_complete_handler(1)

        # Should be paused
        assert orch._paused is True

    def test_recoverable_error_pauses_not_stops(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch):
        """Recoverable merge error should pause, not stop."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        from zerg.orchestrator import Orchestrator

        merger = mock_orchestrator_deps["merge"]
        # Configure to always fail (simulating max retries exceeded)
        merger.configure(always_succeed=False)

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._running = True

        orch._on_level_complete_handler(1)

        # BF-007: Should be paused, not stopped
        assert orch._paused is True
        # Should still be "running" (not stopped)
        assert orch._running is True
        mock_orchestrator_deps["state"].set_paused.assert_called_with(True)


class TestMultiLevelAdvancement:
    """Tests for multi-level advancement scenarios."""

    def test_sequential_level_completion(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch):
        """Multiple levels should complete in sequence."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        from zerg.orchestrator import Orchestrator

        merger = mock_orchestrator_deps["merge"]
        merger.configure(always_succeed=True)

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._running = True

        # Complete levels 1, 2, 3
        for level in [1, 2, 3]:
            orch._on_level_complete_handler(level)

        # All three levels should have merged
        assert merger.get_attempt_count() >= 3

    def test_merge_failure_at_level_2_allows_retry(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch):
        """Failure at level 2 should still allow retry."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        from zerg.orchestrator import Orchestrator

        merger = mock_orchestrator_deps["merge"]
        # Fail at level 2
        merger.configure(fail_at_level=2)

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._running = True

        # Level 1 succeeds
        orch._on_level_complete_handler(1)
        assert len(merger.get_successful_attempts()) >= 1

        # Level 2 fails and pauses
        orch._on_level_complete_handler(2)
        assert orch._paused is True


class TestMergeRetryEvents:
    """Tests for merge retry event emission."""

    def test_retry_events_emitted(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch):
        """Retry attempts should emit events."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        from zerg.orchestrator import Orchestrator

        merger = mock_orchestrator_deps["merge"]
        # Fail first attempt to trigger retry
        merger.configure(fail_at_attempt=1)

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._running = True

        orch._on_level_complete_handler(1)

        # Check that merge_retry event was emitted
        append_event_calls = mock_orchestrator_deps["state"].append_event.call_args_list
        retry_events = [call for call in append_event_calls if call[0][0] == "merge_retry"]
        assert len(retry_events) >= 1

    def test_recoverable_error_event_emitted(self, mock_orchestrator_deps, tmp_path: Path, monkeypatch):
        """Recoverable error should emit event."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        from zerg.orchestrator import Orchestrator

        merger = mock_orchestrator_deps["merge"]
        merger.configure(always_succeed=False)

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._running = True

        orch._on_level_complete_handler(1)

        # Check that recoverable_error event was emitted
        append_event_calls = mock_orchestrator_deps["state"].append_event.call_args_list
        error_events = [call for call in append_event_calls if call[0][0] == "recoverable_error"]
        assert len(error_events) >= 1
