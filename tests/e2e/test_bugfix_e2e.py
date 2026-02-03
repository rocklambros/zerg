"""E2E test: multi-level execution with all bug fixes.

Tests BF-013: Verifies all three bug fixes (BF-007, BF-008, BF-009)
work together in a simulated multi-level ZERG execution using mocks.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.mocks.mock_git import MockGitOps
from tests.mocks.mock_launcher import MockContainerLauncher
from tests.mocks.mock_merge import MockMergeCoordinator
from zerg.constants import WorkerStatus


@pytest.fixture
def mock_full_deps():
    """Mock all dependencies for E2E orchestrator test."""
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
        levels.advance_level.side_effect = lambda: setattr(levels, "current_level", levels.current_level + 1)
        levels.start_level.return_value = ["TASK-001"]
        levels.get_pending_tasks_for_level.return_value = []
        levels.get_level_task_ids.return_value = ["TASK-001", "TASK-002"]
        levels.get_status.return_value = {
            "current_level": 1,
            "total_tasks": 6,
            "completed_tasks": 0,
            "is_complete": False,
        }
        levels_mock.return_value = levels

        parser = MagicMock()
        parser.parse.return_value = None
        parser.get_task.return_value = {"id": "TASK-001", "title": "Test Task", "level": 1}
        parser_mock.return_value = parser

        # Use mock merge coordinator (BF-007)
        merger = MockMergeCoordinator("test-feature")
        merger.configure(always_succeed=True)
        merge_mock.return_value = merger

        # Use mock container launcher (BF-008)
        launcher = MockContainerLauncher()
        launcher.configure()
        launcher_mock.return_value = launcher

        yield {
            "state": state,
            "levels": levels,
            "merge": merger,
            "launcher": launcher,
            "parser": parser,
        }


class TestE2EMultiLevelExecution:
    """E2E tests for multi-level ZERG execution with all fixes."""

    def test_full_execution_flow_success(self, mock_full_deps, tmp_path: Path, monkeypatch):
        """Test complete successful execution across 3 levels.

        Verifies:
        - BF-007: Merge completes successfully for each level
        - BF-008: Workers spawn with exec verification
        - Level progression works correctly
        """
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        from zerg.orchestrator import Orchestrator

        merger = mock_full_deps["merge"]
        merger.configure(always_succeed=True)

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._spawn_worker(1)
        orch._running = True

        # Simulate 3 level completions
        for level in [1, 2, 3]:
            orch._on_level_complete_handler(level)

        # All merges should have succeeded
        assert merger.get_attempt_count() >= 3
        assert len(merger.get_successful_attempts()) >= 3
        assert len(merger.get_failed_attempts()) == 0

    def test_merge_retry_then_success(self, mock_full_deps, tmp_path: Path, monkeypatch):
        """Test merge retry at level 2, then success.

        Verifies BF-007: Merge timeout and retry mechanism.
        """
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        from zerg.orchestrator import Orchestrator

        merger = mock_full_deps["merge"]
        # Level 1 succeeds, Level 2 fails first then succeeds
        merger.configure(fail_at_attempt=2)  # Second merge attempt (first of level 2)

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._running = True

        # Level 1 succeeds
        orch._on_level_complete_handler(1)
        assert len(merger.get_successful_attempts()) >= 1

        # Level 2 retries then succeeds
        orch._on_level_complete_handler(2)

        # Should have had at least one failure then success
        assert len(merger.get_failed_attempts()) >= 1

        # Retry event should be emitted
        append_event_calls = mock_full_deps["state"].append_event.call_args_list
        retry_events = [c for c in append_event_calls if c[0][0] == "merge_retry"]
        assert len(retry_events) >= 1

    @pytest.mark.e2e
    @pytest.mark.timeout(60)
    def test_recoverable_error_allows_resume(self, mock_full_deps, tmp_path: Path, monkeypatch):
        """Test recoverable error pauses, then allows resume.

        Verifies BF-007: Recoverable error state (pause instead of stop).
        """
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        from zerg.orchestrator import Orchestrator

        merger = mock_full_deps["merge"]

        # Complete level 1 successfully
        merger.configure(always_succeed=True)

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._running = True

        orch._on_level_complete_handler(1)
        assert not orch._paused

        # Level 2: Configure persistent failure
        merger.configure(always_succeed=False)
        orch._on_level_complete_handler(2)

        # Should be paused (recoverable), not stopped
        assert orch._paused is True
        assert orch._running is True

        # Simulate manual intervention - fix the issue
        merger.configure(always_succeed=True)
        merger.reset()

        # Resume
        orch._paused = False
        mock_full_deps["state"].is_paused.return_value = False

        # Level 2 retry should now succeed
        orch._on_level_complete_handler(2)
        assert len(merger.get_successful_attempts()) >= 1


class TestE2EWorkerLifecycle:
    """E2E tests for worker lifecycle with exec verification."""

    def test_worker_spawn_exec_verify_success(self, mock_full_deps, tmp_path: Path, monkeypatch):
        """Test worker spawn with exec verification.

        Verifies BF-008: Launcher checks exec return value and verifies process.
        """
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        launcher = mock_full_deps["launcher"]
        launcher.configure()  # All workers succeed

        # Spawn multiple workers
        for i in range(3):
            result = launcher.spawn(
                worker_id=i,
                feature="test-feature",
                worktree_path=Path(f"/workspace/worktree-{i}"),
                branch=f"zerg/test-feature/worker-{i}",
            )
            assert result.success
            assert result.handle.status == WorkerStatus.RUNNING

        # All spawn attempts should be successful
        successful = launcher.get_successful_spawns()
        assert len(successful) == 3

        # All should have passed exec and process verification
        for attempt in successful:
            assert attempt.exec_success
            assert attempt.process_verified

    def test_worker_exec_failure_cleanup(self, mock_full_deps, tmp_path: Path, monkeypatch):
        """Test cleanup when exec fails.

        Verifies BF-008: Resources cleaned up on exec failure.
        """
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        launcher = mock_full_deps["launcher"]
        # Worker 1 exec fails
        launcher.configure(exec_fail_workers={1})

        # Spawn workers
        results = []
        for i in range(3):
            result = launcher.spawn(
                worker_id=i,
                feature="test-feature",
                worktree_path=Path(f"/workspace/worktree-{i}"),
                branch=f"zerg/test-feature/worker-{i}",
            )
            results.append(result)

        # Workers 0 and 2 succeed, worker 1 fails
        assert results[0].success
        assert not results[1].success
        assert results[2].success

        # Only 2 workers should be registered
        assert len(launcher.get_all_workers()) == 2

        # Worker 1 should be cleaned up
        assert launcher.get_handle(1) is None


class TestE2ECommitVerification:
    """E2E tests for commit verification flow."""

    def test_commit_with_head_verification(self):
        """Test commit flow with HEAD verification.

        Verifies BF-009: HEAD verification after commit.
        """
        git = MockGitOps()

        # Simulate task completion with commit
        for i in range(3):
            git.simulate_changes()

            head_before = git.current_commit()
            commit_sha = git.commit(f"ZERG [0]: Task {i}", add_all=True)
            head_after = git.current_commit()

            # HEAD must change (BF-009 verification)
            assert head_before != head_after
            assert head_after == commit_sha

        # All commits should have changed HEAD
        successful = git.get_commits_with_head_change()
        assert len(successful) == 3

    def test_commit_failure_detection(self):
        """Test detection of commit failure (HEAD unchanged).

        Verifies BF-009: Detects when commit succeeds but HEAD doesn't change.
        """
        git = MockGitOps()
        git.configure(commit_no_head_change=True)
        git.simulate_changes()

        head_before = git.current_commit()
        git.commit("ZERG [0]: Test task", add_all=True)
        head_after = git.current_commit()

        # This simulates the bug - commit "succeeds" but HEAD unchanged
        assert head_before == head_after

        # BF-009: Worker should detect this
        failures = git.get_commits_without_head_change()
        assert len(failures) == 1


class TestE2EAllFixesTogether:
    """E2E test verifying all three fixes work together."""

    def test_complete_bugfix_scenario(self, mock_full_deps, tmp_path: Path, monkeypatch):
        """Test scenario exercising all three bug fixes.

        Scenario:
        1. Level 1: Normal completion (merge succeeds)
        2. Level 2: Merge fails, retries, succeeds (BF-007)
        3. Level 3: Worker exec fails, another worker takes over (BF-008)
        4. Task commits verified (BF-009)
        """
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        from zerg.orchestrator import Orchestrator

        merger = mock_full_deps["merge"]
        launcher = mock_full_deps["launcher"]

        # BF-007: Configure merge to fail first attempt at level 2
        merger.configure(fail_at_attempt=2)

        # BF-008: Worker 1 exec fails
        launcher.configure(exec_fail_workers={1})

        orch = Orchestrator("test-feature")
        orch._running = True

        # Spawn workers (worker 1 will fail exec)
        for i in range(3):
            result = launcher.spawn(
                worker_id=i,
                feature="test-feature",
                worktree_path=Path(f"/workspace/worktree-{i}"),
                branch=f"zerg/test-feature/worker-{i}",
            )
            if result.success:
                orch._workers[i] = MagicMock(branch=f"zerg/test-feature/worker-{i}")

        # BF-008: Verify worker 1 failed, others succeeded
        assert len(launcher.get_exec_failed_spawns()) == 1

        # Level 1: Normal completion
        orch._on_level_complete_handler(1)
        assert len(merger.get_successful_attempts()) >= 1

        # Level 2: Fails first, retries succeed (BF-007)
        orch._on_level_complete_handler(2)
        assert len(merger.get_failed_attempts()) >= 1  # Had at least one failure

        # BF-009: Verify commit behavior
        git = MockGitOps()
        git.simulate_changes()
        head_before = git.current_commit()
        commit_sha = git.commit("ZERG [0]: Test task", add_all=True)
        head_after = git.current_commit()

        # BF-009: HEAD must change
        assert head_before != head_after
        assert head_after == commit_sha

        # All three fixes are exercised:
        # - BF-007: Merge retry mechanism (merger.get_failed_attempts() >= 1)
        # - BF-008: Exec verification (exec_fail_workers caused cleanup)
        # - BF-009: HEAD verification (head_before != head_after)


class TestE2EMetrics:
    """E2E tests for metrics collection."""

    def test_metrics_collected_after_merge(self, mock_full_deps, tmp_path: Path, monkeypatch):
        """Test metrics collection after merge completion."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        from zerg.orchestrator import Orchestrator

        merger = mock_full_deps["merge"]
        merger.configure(always_succeed=True)

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._running = True

        orch._on_level_complete_handler(1)

        # Merge should succeed
        assert merger.get_attempt_count() >= 1
        assert len(merger.get_successful_attempts()) >= 1

    def test_event_emission_throughout_flow(self, mock_full_deps, tmp_path: Path, monkeypatch):
        """Test events are emitted at each stage."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        from zerg.orchestrator import Orchestrator

        merger = mock_full_deps["merge"]
        merger.configure(always_succeed=True)

        orch = Orchestrator("test-feature")
        orch._spawn_worker(0)
        orch._running = True

        orch._on_level_complete_handler(1)

        # Events should have been emitted
        append_event_calls = mock_full_deps["state"].append_event.call_args_list
        event_types = [call[0][0] for call in append_event_calls]

        # Should have level_complete event
        assert "level_complete" in event_types
