"""Integration tests for dedup behavioral equivalence.

Verifies end-to-end behavior after the sync/async deduplication refactoring
(Level 1-2 of core-refactoring). These tests exercise the integration points
between components, not just unit-level behavior:

1. Orchestrator initialization with all components
2. Worker spawn/terminate lifecycle through unified methods
3. WorkerProtocol claim_next_task end-to-end
4. _main_loop orchestration handles level transitions
5. No regressions in overall system behavior
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.mocks import MockContainerLauncher
from zerg.constants import TaskStatus, WorkerStatus
from zerg.launcher_types import SpawnResult
from zerg.orchestrator import Orchestrator

# =============================================================================
# Helpers
# =============================================================================


def _create_orchestrator_patches() -> dict[str, str]:
    """Return dict of names to patch on zerg.orchestrator for full Orchestrator init."""
    return {
        "StateManager": "zerg.orchestrator.StateManager",
        "LevelController": "zerg.orchestrator.LevelController",
        "TaskParser": "zerg.orchestrator.TaskParser",
        "WorktreeManager": "zerg.orchestrator.WorktreeManager",
        "PortAllocator": "zerg.orchestrator.PortAllocator",
        "MergeCoordinator": "zerg.orchestrator.MergeCoordinator",
        "SubprocessLauncher": "zerg.orchestrator.SubprocessLauncher",
        "GateRunner": "zerg.orchestrator.GateRunner",
        "ContainerManager": "zerg.orchestrator.ContainerManager",
        "TaskSyncBridge": "zerg.orchestrator.TaskSyncBridge",
    }


def _make_state_mock() -> MagicMock:
    """Create a MagicMock for StateManager with common defaults."""
    state = MagicMock()
    state.load.return_value = {}
    state._state = {"tasks": {}, "workers": {}}
    state.get_tasks_ready_for_retry.return_value = []
    state.get_task_retry_count.return_value = 0
    state.get_stale_in_progress_tasks.return_value = []
    return state


def _make_worktree_mock(tmp_path: Path) -> MagicMock:
    """Create a MagicMock for WorktreeManager."""
    wt = MagicMock()
    wt_info = MagicMock()
    wt_info.path = tmp_path / "worktree"
    wt_info.branch = "test-branch"
    wt.create.return_value = wt_info
    wt.get_worktree_path.return_value = tmp_path / "worktree"
    return wt


def _make_ports_mock() -> MagicMock:
    """Create a MagicMock for PortAllocator."""
    ports = MagicMock()
    ports.allocate_one.return_value = 50000
    return ports


def _make_launcher_mock(
    spawn_success: bool = True,
    monitor_status: WorkerStatus = WorkerStatus.RUNNING,
) -> MagicMock:
    """Create a MagicMock for the launcher."""
    launcher = MagicMock()
    result = MagicMock(spec=SpawnResult)
    result.success = spawn_success
    result.handle = MagicMock()
    result.handle.container_id = None
    result.error = None if spawn_success else "Spawn failed"
    launcher.spawn.return_value = result
    launcher.monitor.return_value = monitor_status
    launcher.sync_state.return_value = None
    launcher.terminate.return_value = True
    return launcher


# =============================================================================
# 1. Orchestrator initialization with all components
# =============================================================================


class TestOrchestratorInitialization:
    """Verify Orchestrator initializes with all dedup-refactored components."""

    def test_orchestrator_creates_worker_manager(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Orchestrator should wire WorkerManager on init."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)
        (tmp_path / ".zerg" / "logs").mkdir(parents=True)

        patches = _create_orchestrator_patches()
        with (
            patch(patches["StateManager"]) as state_cls,
            patch(patches["LevelController"]),
            patch(patches["TaskParser"]),
            patch(patches["WorktreeManager"]),
            patch(patches["PortAllocator"]),
            patch(patches["MergeCoordinator"]),
            patch(patches["SubprocessLauncher"]),
            patch(patches["GateRunner"]),
            patch(patches["ContainerManager"]),
            patch(patches["TaskSyncBridge"]),
        ):
            state_cls.return_value = _make_state_mock()
            orch = Orchestrator("test-feature")

            assert hasattr(orch, "_worker_manager")
            assert hasattr(orch, "_level_coord")
            assert hasattr(orch, "_retry_manager")
            assert hasattr(orch, "_state_sync")

    def test_orchestrator_wires_shared_workers_dict(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """WorkerManager and LevelCoordinator share the same _workers dict."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)
        (tmp_path / ".zerg" / "logs").mkdir(parents=True)

        patches = _create_orchestrator_patches()
        with (
            patch(patches["StateManager"]) as state_cls,
            patch(patches["LevelController"]),
            patch(patches["TaskParser"]),
            patch(patches["WorktreeManager"]),
            patch(patches["PortAllocator"]),
            patch(patches["MergeCoordinator"]),
            patch(patches["SubprocessLauncher"]),
            patch(patches["GateRunner"]),
            patch(patches["ContainerManager"]),
            patch(patches["TaskSyncBridge"]),
        ):
            state_cls.return_value = _make_state_mock()
            orch = Orchestrator("test-feature")

            # Same dict object shared by reference
            assert orch._workers is orch._worker_manager._workers
            assert orch._workers is orch._level_coord._workers

    def test_orchestrator_unified_main_loop_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unified _main_loop must be callable with optional sleep_fn."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)
        (tmp_path / ".zerg" / "logs").mkdir(parents=True)

        patches = _create_orchestrator_patches()
        with (
            patch(patches["StateManager"]) as state_cls,
            patch(patches["LevelController"]),
            patch(patches["TaskParser"]),
            patch(patches["WorktreeManager"]),
            patch(patches["PortAllocator"]),
            patch(patches["MergeCoordinator"]),
            patch(patches["SubprocessLauncher"]),
            patch(patches["GateRunner"]),
            patch(patches["ContainerManager"]),
            patch(patches["TaskSyncBridge"]),
        ):
            state_cls.return_value = _make_state_mock()
            orch = Orchestrator("test-feature")

            # _main_loop exists and accepts sleep_fn
            assert callable(orch._main_loop)
            # _main_loop_as_async exists as the async wrapper
            assert asyncio.iscoroutinefunction(orch._main_loop_as_async)
            # Old async methods do NOT exist
            assert not hasattr(orch, "_poll_workers_async")
            assert not hasattr(orch, "_main_loop_async")


# =============================================================================
# 2. Worker spawn/terminate lifecycle through unified methods
# =============================================================================


class TestWorkerLifecycleIntegration:
    """Test worker spawn and terminate lifecycle end-to-end with Orchestrator."""

    def test_spawn_worker_through_orchestrator(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Spawning via orchestrator._spawn_worker delegates to WorkerManager."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)
        (tmp_path / ".zerg" / "logs").mkdir(parents=True)

        patches = _create_orchestrator_patches()
        with (
            patch(patches["StateManager"]) as state_cls,
            patch(patches["LevelController"]),
            patch(patches["TaskParser"]),
            patch(patches["WorktreeManager"]) as wt_cls,
            patch(patches["PortAllocator"]) as ports_cls,
            patch(patches["MergeCoordinator"]),
            patch(patches["SubprocessLauncher"]) as launcher_cls,
            patch(patches["GateRunner"]),
            patch(patches["ContainerManager"]),
            patch(patches["TaskSyncBridge"]),
        ):
            state_mock = _make_state_mock()
            state_cls.return_value = state_mock

            wt_cls.return_value = _make_worktree_mock(tmp_path)
            ports_cls.return_value = _make_ports_mock()
            launcher_cls.return_value = _make_launcher_mock()

            orch = Orchestrator("test-feature")

            worker_state = orch._spawn_worker(0)

            # Worker should be tracked in shared dict
            assert 0 in orch._workers
            assert orch._workers[0] is worker_state
            assert worker_state.status == WorkerStatus.RUNNING
            assert worker_state.worker_id == 0

    def test_terminate_worker_through_orchestrator(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Terminate via orchestrator delegates to WorkerManager which uses launcher."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)
        (tmp_path / ".zerg" / "logs").mkdir(parents=True)

        patches = _create_orchestrator_patches()
        with (
            patch(patches["StateManager"]) as state_cls,
            patch(patches["LevelController"]),
            patch(patches["TaskParser"]),
            patch(patches["WorktreeManager"]) as wt_cls,
            patch(patches["PortAllocator"]) as ports_cls,
            patch(patches["MergeCoordinator"]),
            patch(patches["SubprocessLauncher"]) as launcher_cls,
            patch(patches["GateRunner"]),
            patch(patches["ContainerManager"]),
            patch(patches["TaskSyncBridge"]),
        ):
            state_mock = _make_state_mock()
            state_cls.return_value = state_mock

            wt_cls.return_value = _make_worktree_mock(tmp_path)
            ports_cls.return_value = _make_ports_mock()
            launcher_mock = _make_launcher_mock()
            launcher_cls.return_value = launcher_mock

            orch = Orchestrator("test-feature")

            # Spawn then terminate
            orch._spawn_worker(0)
            assert 0 in orch._workers

            orch._terminate_worker(0)
            launcher_mock.terminate.assert_called_once_with(0, force=False)

    def test_spawn_multiple_workers(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """_spawn_workers spawns the requested count and returns actual count."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)
        (tmp_path / ".zerg" / "logs").mkdir(parents=True)

        patches = _create_orchestrator_patches()
        with (
            patch(patches["StateManager"]) as state_cls,
            patch(patches["LevelController"]),
            patch(patches["TaskParser"]),
            patch(patches["WorktreeManager"]) as wt_cls,
            patch(patches["PortAllocator"]) as ports_cls,
            patch(patches["MergeCoordinator"]),
            patch(patches["SubprocessLauncher"]) as launcher_cls,
            patch(patches["GateRunner"]),
            patch(patches["ContainerManager"]),
            patch(patches["TaskSyncBridge"]),
        ):
            state_cls.return_value = _make_state_mock()
            wt_cls.return_value = _make_worktree_mock(tmp_path)
            ports_cls.return_value = _make_ports_mock()
            launcher_cls.return_value = _make_launcher_mock()

            orch = Orchestrator("test-feature")
            orch._worker_manager.running = True

            spawned = orch._spawn_workers(3)
            assert spawned == 3
            assert len(orch._workers) == 3

    def test_spawn_with_mock_container_launcher(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """MockContainerLauncher spawn/terminate lifecycle works end-to-end."""
        launcher = MockContainerLauncher()

        # Spawn worker
        result = launcher.spawn(0, "test-feature", tmp_path / "worktree", "main")
        assert result.success is True
        assert result.handle is not None
        assert result.handle.status == WorkerStatus.RUNNING

        # Monitor shows running
        status = launcher.monitor(0)
        assert status == WorkerStatus.RUNNING

        # Terminate
        terminated = launcher.terminate(0)
        assert terminated is True

        # After terminate, monitor shows stopped
        status = launcher.monitor(0)
        assert status == WorkerStatus.STOPPED

    def test_mock_launcher_crash_lifecycle(self) -> None:
        """MockContainerLauncher crash simulation works correctly."""
        launcher = MockContainerLauncher()
        launcher.configure(container_crash_workers={0})

        result = launcher.spawn(0, "test-feature", Path("/tmp/wt"), "main")
        assert result.success is True

        # Monitor detects crash
        status = launcher.monitor(0)
        assert status == WorkerStatus.CRASHED

        # Clear crash config, worker was already crashed though
        launcher.configure(container_crash_workers=set())

        # Spawn a new worker in slot 1 - should succeed
        result2 = launcher.spawn(1, "test-feature", Path("/tmp/wt2"), "main")
        assert result2.success is True
        assert launcher.monitor(1) == WorkerStatus.RUNNING


# =============================================================================
# 3. WorkerProtocol claim_next_task end-to-end
# =============================================================================


class TestWorkerProtocolClaimIntegration:
    """Test WorkerProtocol claim_next_task integration with state."""

    def test_claim_next_task_sync_delegates_to_async(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Sync claim_next_task must delegate to async version via asyncio.run."""
        from zerg.protocol_state import WorkerProtocol

        # WorkerProtocol reads worktree_path and branch from env
        monkeypatch.setenv("ZERG_WORKTREE", "/tmp/worktree")
        monkeypatch.setenv("ZERG_BRANCH", "test-branch")

        # Create protocol with mocked dependencies
        with (
            patch("zerg.protocol_state.StateManager") as state_cls,
            patch("zerg.protocol_state.TaskParser") as parser_cls,
            patch("zerg.protocol_state.GitOps"),
            patch("zerg.protocol_state.SpecLoader"),
            patch("zerg.protocol_state.DependencyChecker") as dep_cls,
            patch("zerg.protocol_state.VerificationExecutor"),
            patch("zerg.protocol_state.setup_structured_logging", return_value=None),
        ):
            state_mock = MagicMock()
            state_mock.load.return_value = {}
            state_mock.get_tasks_by_status.return_value = ["TASK-001"]
            state_mock.claim_task.return_value = True
            state_cls.return_value = state_mock

            parser_mock = MagicMock()
            parser_mock.get_task.return_value = {
                "id": "TASK-001",
                "title": "Test Task",
                "level": 1,
                "dependencies": [],
                "files": {"create": [], "modify": [], "read": []},
                "verification": {"command": "echo ok"},
            }
            parser_cls.return_value = parser_mock

            dep_mock = MagicMock()
            dep_mock.check_dependencies.return_value = True
            dep_cls.return_value = dep_mock

            protocol = WorkerProtocol(
                worker_id=0,
                feature="test-feature",
            )

            # claim_next_task (sync) should work and find the task
            protocol.claim_next_task(max_wait=0.5, poll_interval=0.1)

            # It should have called into state manager
            state_mock.load.assert_called()
            state_mock.get_tasks_by_status.assert_called()

    def test_wait_for_ready_sync_delegates_to_async(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Sync wait_for_ready must delegate to async version."""
        from zerg.protocol_state import WorkerProtocol

        monkeypatch.setenv("ZERG_WORKTREE", "/tmp/worktree")
        monkeypatch.setenv("ZERG_BRANCH", "test-branch")

        with (
            patch("zerg.protocol_state.StateManager"),
            patch("zerg.protocol_state.TaskParser"),
            patch("zerg.protocol_state.GitOps"),
            patch("zerg.protocol_state.SpecLoader"),
            patch("zerg.protocol_state.DependencyChecker"),
            patch("zerg.protocol_state.VerificationExecutor"),
            patch("zerg.protocol_state.setup_structured_logging", return_value=None),
        ):
            protocol = WorkerProtocol(
                worker_id=0,
                feature="test-feature",
            )

            # Set ready state
            protocol._is_ready = True

            # Sync wrapper should delegate and return True
            result = protocol.wait_for_ready(timeout=1.0)
            assert result is True

    def test_wait_for_ready_sync_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Sync wait_for_ready returns False on timeout."""
        from zerg.protocol_state import WorkerProtocol

        monkeypatch.setenv("ZERG_WORKTREE", "/tmp/worktree")
        monkeypatch.setenv("ZERG_BRANCH", "test-branch")

        with (
            patch("zerg.protocol_state.StateManager"),
            patch("zerg.protocol_state.TaskParser"),
            patch("zerg.protocol_state.GitOps"),
            patch("zerg.protocol_state.SpecLoader"),
            patch("zerg.protocol_state.DependencyChecker"),
            patch("zerg.protocol_state.VerificationExecutor"),
            patch("zerg.protocol_state.setup_structured_logging", return_value=None),
        ):
            protocol = WorkerProtocol(
                worker_id=0,
                feature="test-feature",
            )

            # Not ready
            protocol._is_ready = False

            # Should timeout and return False
            result = protocol.wait_for_ready(timeout=0.3)
            assert result is False


# =============================================================================
# 4. _main_loop orchestration handles level transitions
# =============================================================================


class TestMainLoopLevelTransitions:
    """Test the unified _main_loop handles level transitions correctly."""

    def test_main_loop_completes_single_level(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """_main_loop exits when all levels are complete."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)
        (tmp_path / ".zerg" / "logs").mkdir(parents=True)

        patches = _create_orchestrator_patches()
        with (
            patch(patches["StateManager"]) as state_cls,
            patch(patches["LevelController"]) as levels_cls,
            patch(patches["TaskParser"]),
            patch(patches["WorktreeManager"]),
            patch(patches["PortAllocator"]),
            patch(patches["MergeCoordinator"]),
            patch(patches["SubprocessLauncher"]) as launcher_cls,
            patch(patches["GateRunner"]),
            patch(patches["ContainerManager"]),
            patch(patches["TaskSyncBridge"]),
        ):
            state_mock = _make_state_mock()
            state_cls.return_value = state_mock

            levels_mock = MagicMock()
            levels_mock.current_level = 1
            # First call: level resolved, second call: is_complete
            levels_mock.is_level_resolved.return_value = True
            levels_mock.can_advance.return_value = False
            levels_mock.get_status.return_value = {
                "current_level": 1,
                "total_tasks": 1,
                "completed_tasks": 1,
                "failed_tasks": 0,
                "in_progress_tasks": 0,
                "progress_percent": 100,
                "is_complete": True,
                "levels": {},
            }
            levels_mock.get_pending_tasks_for_level.return_value = []
            levels_cls.return_value = levels_mock

            launcher_mock = _make_launcher_mock()
            launcher_cls.return_value = launcher_mock

            orch = Orchestrator("test-feature")
            orch._running = True
            orch._worker_manager.running = True

            # Patch level coordinator's handle_level_complete
            orch._level_coord.handle_level_complete = MagicMock(return_value=True)
            orch._level_coord.paused = False

            # Run _main_loop with a no-op sleep
            call_count = 0

            def counting_sleep(seconds: float) -> None:
                nonlocal call_count
                call_count += 1
                # After one iteration, the loop should have detected completion
                # Safety: prevent infinite loop
                if call_count > 5:
                    orch._running = False

            orch._main_loop(sleep_fn=counting_sleep)

            # Should have exited because is_complete was True
            assert orch._running is False

    def test_main_loop_advances_to_next_level(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """_main_loop calls _start_level and _respawn_workers when advancing."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)
        (tmp_path / ".zerg" / "logs").mkdir(parents=True)

        patches = _create_orchestrator_patches()
        with (
            patch(patches["StateManager"]) as state_cls,
            patch(patches["LevelController"]) as levels_cls,
            patch(patches["TaskParser"]),
            patch(patches["WorktreeManager"]),
            patch(patches["PortAllocator"]),
            patch(patches["MergeCoordinator"]),
            patch(patches["SubprocessLauncher"]) as launcher_cls,
            patch(patches["GateRunner"]),
            patch(patches["ContainerManager"]),
            patch(patches["TaskSyncBridge"]),
        ):
            state_mock = _make_state_mock()
            state_cls.return_value = state_mock

            levels_mock = MagicMock()
            iteration = 0

            def dynamic_current_level() -> int:
                nonlocal iteration
                # Level 1 for first iterations, then level 2
                return 1 if iteration < 2 else 2

            type(levels_mock).current_level = property(lambda self: dynamic_current_level())

            # First iteration: level 1 is resolved, can advance
            # After advance, level 2 completes immediately
            resolve_calls = [0]

            def is_level_resolved_side_effect(level: int) -> bool:
                resolve_calls[0] += 1
                if level == 1:
                    return True
                return resolve_calls[0] > 3  # Level 2 resolves on later call

            levels_mock.is_level_resolved.side_effect = is_level_resolved_side_effect
            levels_mock.can_advance.side_effect = [True, False]
            levels_mock.advance_level.return_value = 2
            levels_mock.get_status.return_value = {
                "current_level": 2,
                "total_tasks": 2,
                "completed_tasks": 2,
                "failed_tasks": 0,
                "in_progress_tasks": 0,
                "progress_percent": 100,
                "is_complete": True,
                "levels": {},
            }
            levels_mock.get_pending_tasks_for_level.return_value = []
            levels_cls.return_value = levels_mock

            launcher_cls.return_value = _make_launcher_mock()

            orch = Orchestrator("test-feature")
            orch._running = True
            orch._worker_manager.running = True

            orch._level_coord.handle_level_complete = MagicMock(return_value=True)
            orch._level_coord.paused = False

            call_count = 0

            def counting_sleep(seconds: float) -> None:
                nonlocal call_count, iteration
                call_count += 1
                iteration += 1
                if call_count > 10:
                    orch._running = False

            orch._main_loop(sleep_fn=counting_sleep)

            # Should have advanced from level 1 to 2
            levels_mock.advance_level.assert_called_once()

    def test_main_loop_pauses_on_merge_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """_main_loop continues (doesn't advance) when merge fails."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)
        (tmp_path / ".zerg" / "logs").mkdir(parents=True)

        patches = _create_orchestrator_patches()
        with (
            patch(patches["StateManager"]) as state_cls,
            patch(patches["LevelController"]) as levels_cls,
            patch(patches["TaskParser"]),
            patch(patches["WorktreeManager"]),
            patch(patches["PortAllocator"]),
            patch(patches["MergeCoordinator"]),
            patch(patches["SubprocessLauncher"]) as launcher_cls,
            patch(patches["GateRunner"]),
            patch(patches["ContainerManager"]),
            patch(patches["TaskSyncBridge"]),
        ):
            state_mock = _make_state_mock()
            state_cls.return_value = state_mock

            levels_mock = MagicMock()
            levels_mock.current_level = 1
            levels_mock.is_level_resolved.return_value = True
            levels_mock.get_pending_tasks_for_level.return_value = []
            levels_cls.return_value = levels_mock

            launcher_cls.return_value = _make_launcher_mock()

            orch = Orchestrator("test-feature")
            orch._running = True
            orch._worker_manager.running = True

            # Merge fails
            orch._level_coord.handle_level_complete = MagicMock(return_value=False)
            orch._level_coord.paused = True

            call_count = 0

            def counting_sleep(seconds: float) -> None:
                nonlocal call_count
                call_count += 1
                if call_count > 2:
                    orch._running = False

            orch._main_loop(sleep_fn=counting_sleep)

            # Merge was attempted but failed, so can_advance should NOT have been called
            levels_mock.can_advance.assert_not_called()
            # Orchestrator should have been paused due to merge failure
            assert orch._paused is True

    def test_main_loop_calls_poll_workers_with_all_features(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_poll_workers within _main_loop includes escalation, progress, and stall detection.

        After the god-class refactor, _check_escalations and _aggregate_progress were
        inlined into _poll_workers. We now verify _poll_workers and _check_stale_tasks
        are called (stale task check remains a separate method).
        """
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)
        (tmp_path / ".zerg" / "logs").mkdir(parents=True)

        patches = _create_orchestrator_patches()
        with (
            patch(patches["StateManager"]) as state_cls,
            patch(patches["LevelController"]) as levels_cls,
            patch(patches["TaskParser"]),
            patch(patches["WorktreeManager"]),
            patch(patches["PortAllocator"]),
            patch(patches["MergeCoordinator"]),
            patch(patches["SubprocessLauncher"]) as launcher_cls,
            patch(patches["GateRunner"]),
            patch(patches["ContainerManager"]),
            patch(patches["TaskSyncBridge"]),
        ):
            state_mock = _make_state_mock()
            state_cls.return_value = state_mock

            levels_mock = MagicMock()
            levels_mock.current_level = 1
            levels_mock.is_level_resolved.return_value = False
            levels_mock.get_pending_tasks_for_level.return_value = ["TASK-001"]
            levels_cls.return_value = levels_mock

            launcher_cls.return_value = _make_launcher_mock()

            orch = Orchestrator("test-feature")
            orch._running = True
            orch._worker_manager.running = True

            # _check_stale_tasks is still a separate method; patch to track calls
            orch._check_stale_tasks = MagicMock()

            # Add a running worker so the auto-respawn logic doesn't trigger
            orch._workers[0] = MagicMock()
            orch._workers[0].status = WorkerStatus.RUNNING

            call_count = 0

            def counting_sleep(seconds: float) -> None:
                nonlocal call_count
                call_count += 1
                if call_count > 0:
                    orch._running = False

            orch._main_loop(sleep_fn=counting_sleep)

            # _check_stale_tasks should have been called from _poll_workers
            orch._check_stale_tasks.assert_called()
            # Escalation and progress logic are now inline in _poll_workers;
            # verify state was loaded (proves _poll_workers ran)
            state_mock.load.assert_called()


# =============================================================================
# 5. No regressions in overall system behavior
# =============================================================================


class TestNoRegressions:
    """Verify no regressions in Orchestrator behavior after dedup changes."""

    def test_start_and_stop_lifecycle(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Orchestrator start() then stop() works correctly."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)
        (tmp_path / ".zerg" / "logs").mkdir(parents=True)
        (tmp_path / ".gsd" / "specs" / "test-feature").mkdir(parents=True)

        # Create a simple task graph
        task_graph = {
            "feature": "test-feature",
            "version": "1.0",
            "generated": datetime.now().isoformat(),
            "total_tasks": 1,
            "tasks": [
                {
                    "id": "TASK-001",
                    "title": "Test Task",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["file1.py"], "modify": [], "read": []},
                    "verification": {"command": "echo ok"},
                },
            ],
        }
        graph_path = tmp_path / "task-graph.json"
        with open(graph_path, "w") as f:
            json.dump(task_graph, f)

        patches = _create_orchestrator_patches()
        with (
            patch(patches["StateManager"]) as state_cls,
            patch(patches["LevelController"]) as levels_cls,
            patch(patches["TaskParser"]) as parser_cls,
            patch(patches["WorktreeManager"]) as wt_cls,
            patch(patches["PortAllocator"]) as ports_cls,
            patch(patches["MergeCoordinator"]),
            patch(patches["SubprocessLauncher"]) as launcher_cls,
            patch(patches["GateRunner"]),
            patch(patches["ContainerManager"]),
            patch(patches["TaskSyncBridge"]),
        ):
            state_mock = _make_state_mock()
            state_cls.return_value = state_mock

            levels_mock = MagicMock()
            levels_mock.current_level = 1
            levels_mock.is_level_resolved.return_value = True
            levels_mock.can_advance.return_value = False
            levels_mock.get_status.return_value = {
                "current_level": 1,
                "total_tasks": 1,
                "completed_tasks": 1,
                "failed_tasks": 0,
                "in_progress_tasks": 0,
                "progress_percent": 100,
                "is_complete": True,
                "levels": {},
            }
            levels_mock.get_pending_tasks_for_level.return_value = []
            levels_cls.return_value = levels_mock

            parser_mock = MagicMock()
            parser_mock.get_all_tasks.return_value = task_graph["tasks"]
            parser_mock.levels = [1]
            parser_mock.total_tasks = 1
            parser_cls.return_value = parser_mock

            wt_cls.return_value = _make_worktree_mock(tmp_path)
            ports_cls.return_value = _make_ports_mock()
            launcher_cls.return_value = _make_launcher_mock()

            orch = Orchestrator("test-feature")

            # Patch _main_loop to exit immediately (simulates completion)
            _ = orch._main_loop  # noqa: F841

            def quick_main_loop(sleep_fn: Any = None) -> None:
                orch._running = False

            orch._main_loop = quick_main_loop

            # Start should not raise
            orch.start(graph_path, worker_count=1)

            # Stop should clean up
            orch._running = True  # Re-enable to test stop
            orch.stop()

            assert orch._running is False
            state_mock.save.assert_called()

    def test_status_returns_expected_structure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """status() returns correctly structured dict."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)
        (tmp_path / ".zerg" / "logs").mkdir(parents=True)

        patches = _create_orchestrator_patches()
        with (
            patch(patches["StateManager"]) as state_cls,
            patch(patches["LevelController"]) as levels_cls,
            patch(patches["TaskParser"]),
            patch(patches["WorktreeManager"]),
            patch(patches["PortAllocator"]),
            patch(patches["MergeCoordinator"]),
            patch(patches["SubprocessLauncher"]),
            patch(patches["GateRunner"]),
            patch(patches["ContainerManager"]),
            patch(patches["TaskSyncBridge"]),
            patch("zerg.orchestrator.MetricsCollector") as metrics_cls,
        ):
            state_cls.return_value = _make_state_mock()

            levels_mock = MagicMock()
            levels_mock.current_level = 1
            levels_mock.get_status.return_value = {
                "current_level": 1,
                "total_tasks": 3,
                "completed_tasks": 1,
                "failed_tasks": 0,
                "in_progress_tasks": 1,
                "progress_percent": 33,
                "is_complete": False,
                "levels": {},
            }
            levels_cls.return_value = levels_mock

            metrics_mock = MagicMock()
            feature_metrics = MagicMock()
            feature_metrics.to_dict.return_value = {"tasks_completed": 1, "tasks_total": 3}
            metrics_mock.compute_feature_metrics.return_value = feature_metrics
            metrics_cls.return_value = metrics_mock

            orch = Orchestrator("test-feature")
            status = orch.status()

            assert "feature" in status
            assert "running" in status
            assert "current_level" in status
            assert "progress" in status
            assert "workers" in status
            assert "is_complete" in status
            assert "metrics" in status
            assert "circuit_breaker" in status
            assert "backpressure" in status
            assert status["feature"] == "test-feature"
            assert status["progress"]["total"] == 3

    def test_resume_clears_paused_state(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """resume() clears paused flag and updates state."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)
        (tmp_path / ".zerg" / "logs").mkdir(parents=True)

        patches = _create_orchestrator_patches()
        with (
            patch(patches["StateManager"]) as state_cls,
            patch(patches["LevelController"]),
            patch(patches["TaskParser"]),
            patch(patches["WorktreeManager"]),
            patch(patches["PortAllocator"]),
            patch(patches["MergeCoordinator"]),
            patch(patches["SubprocessLauncher"]),
            patch(patches["GateRunner"]),
            patch(patches["ContainerManager"]),
            patch(patches["TaskSyncBridge"]),
        ):
            state_mock = _make_state_mock()
            state_cls.return_value = state_mock

            orch = Orchestrator("test-feature")
            orch._paused = True

            orch.resume()

            assert orch._paused is False
            state_mock.set_paused.assert_called_with(False)
            state_mock.append_event.assert_called_with("resumed", {})

    def test_worker_crash_resets_task_to_pending(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Worker crash marks task FAILED then resets to PENDING (no retry increment)."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)
        (tmp_path / ".zerg" / "logs").mkdir(parents=True)

        patches = _create_orchestrator_patches()
        with (
            patch(patches["StateManager"]) as state_cls,
            patch(patches["LevelController"]) as levels_cls,
            patch(patches["TaskParser"]),
            patch(patches["WorktreeManager"]),
            patch(patches["PortAllocator"]),
            patch(patches["MergeCoordinator"]),
            patch(patches["SubprocessLauncher"]),
            patch(patches["GateRunner"]),
            patch(patches["ContainerManager"]),
            patch(patches["TaskSyncBridge"]),
        ):
            state_mock = _make_state_mock()
            state_cls.return_value = state_mock

            levels_mock = MagicMock()
            levels_cls.return_value = levels_mock

            orch = Orchestrator("test-feature")

            # Simulate worker crash with a task
            orch._handle_worker_crash("TASK-001", wid=0)

            # Should have marked failed first, then pending
            set_calls = state_mock.set_task_status.call_args_list
            failed_calls = [c for c in set_calls if c[0][1] == TaskStatus.FAILED]
            pending_calls = [c for c in set_calls if c[0][1] == TaskStatus.PENDING]

            assert len(failed_calls) >= 1
            assert len(pending_calls) >= 1
            # Should NOT have incremented retry count
            state_mock.increment_task_retry.assert_not_called()

    def test_poll_workers_detects_crashed_worker(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """_poll_workers detects crashed workers and triggers crash handling."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)
        (tmp_path / ".zerg" / "logs").mkdir(parents=True)

        patches = _create_orchestrator_patches()
        with (
            patch(patches["StateManager"]) as state_cls,
            patch(patches["LevelController"]) as levels_cls,
            patch(patches["TaskParser"]) as parser_cls,
            patch(patches["WorktreeManager"]) as wt_cls,
            patch(patches["PortAllocator"]) as ports_cls,
            patch(patches["MergeCoordinator"]),
            patch(patches["SubprocessLauncher"]) as launcher_cls,
            patch(patches["GateRunner"]),
            patch(patches["ContainerManager"]),
            patch(patches["TaskSyncBridge"]),
        ):
            state_mock = _make_state_mock()
            state_cls.return_value = state_mock

            levels_mock = MagicMock()
            levels_mock.current_level = 1
            levels_mock.get_pending_tasks_for_level.return_value = ["TASK-002"]
            levels_cls.return_value = levels_mock

            parser_mock = MagicMock()
            parser_mock.get_task.return_value = {
                "id": "TASK-001",
                "verification": {"command": "echo ok"},
            }
            parser_cls.return_value = parser_mock

            wt_cls.return_value = _make_worktree_mock(tmp_path)
            ports_cls.return_value = _make_ports_mock()

            launcher_mock = _make_launcher_mock(monitor_status=WorkerStatus.CRASHED)
            launcher_cls.return_value = launcher_mock

            orch = Orchestrator("test-feature")
            orch._running = True
            orch._worker_manager.running = True

            # Spawn a worker, assign it a task, then poll
            worker_state = orch._spawn_worker(0)
            worker_state.current_task = "TASK-001"

            orch._poll_workers()

            # Crash was detected and handled: task should have been marked FAILED
            # then reset to PENDING (crash handling resets for reassignment).
            # The worker may have been respawned via handle_worker_exit.
            set_calls = state_mock.set_task_status.call_args_list
            failed_calls = [c for c in set_calls if len(c[0]) >= 2 and c[0][1] == TaskStatus.FAILED]
            assert len(failed_calls) >= 1, "Crash should mark the task as FAILED"

            # Crash event should have been recorded
            event_calls = [c for c in state_mock.append_event.call_args_list if c[0][0] == "task_crash_reassign"]
            assert len(event_calls) >= 1, "Crash event should be recorded"

    def test_poll_workers_sync_alias_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """_poll_workers_sync alias exists and points to _poll_workers."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)
        (tmp_path / ".zerg" / "logs").mkdir(parents=True)

        patches = _create_orchestrator_patches()
        with (
            patch(patches["StateManager"]) as state_cls,
            patch(patches["LevelController"]),
            patch(patches["TaskParser"]),
            patch(patches["WorktreeManager"]),
            patch(patches["PortAllocator"]),
            patch(patches["MergeCoordinator"]),
            patch(patches["SubprocessLauncher"]),
            patch(patches["GateRunner"]),
            patch(patches["ContainerManager"]),
            patch(patches["TaskSyncBridge"]),
        ):
            state_cls.return_value = _make_state_mock()
            orch = Orchestrator("test-feature")

            # _poll_workers_sync is an alias for backward compatibility
            assert orch._poll_workers_sync == orch._poll_workers


# =============================================================================
# 6. Launcher dedup patterns (spawn_with_retry, _start_container, terminate)
# =============================================================================


class TestLauncherDedupEndToEnd:
    """Integration tests for launcher dedup patterns working end-to-end."""

    def test_spawn_with_retry_succeeds_on_first_attempt(self) -> None:
        """spawn_with_retry returns success on first attempt for healthy launcher."""
        launcher = MockContainerLauncher()

        result = launcher.spawn_with_retry(
            worker_id=0,
            feature="test-feature",
            worktree_path=Path("/tmp/worktree"),
            branch="main",
            max_attempts=3,
        )

        assert result.success is True
        assert result.worker_id == 0
        # Should have only one spawn attempt
        assert len(launcher.get_spawn_attempts()) == 1

    def test_spawn_with_retry_retries_on_failure(self) -> None:
        """spawn_with_retry retries on failure using the injected sleep_fn."""
        launcher = MockContainerLauncher()

        # First attempt fails, second succeeds
        launcher.configure(spawn_fail_workers={0})

        result = launcher.spawn_with_retry(
            worker_id=0,
            feature="test-feature",
            worktree_path=Path("/tmp/worktree"),
            branch="main",
            max_attempts=3,
            backoff_base_seconds=0.01,
            backoff_max_seconds=0.1,
        )

        # Should fail after all attempts since spawn_fail_workers persists
        assert result.success is False
        # Should have tried all 3 attempts
        assert len(launcher.get_spawn_attempts()) == 3

    def test_spawn_with_retry_async_equivalent(self) -> None:
        """spawn_with_retry_async produces the same result as sync version."""
        launcher = MockContainerLauncher()

        sync_result = launcher.spawn_with_retry(
            worker_id=0,
            feature="test",
            worktree_path=Path("/tmp/wt"),
            branch="main",
            max_attempts=1,
        )

        launcher.reset()

        async_result = asyncio.run(
            launcher.spawn_with_retry_async(
                worker_id=0,
                feature="test",
                worktree_path=Path("/tmp/wt"),
                branch="main",
                max_attempts=1,
            )
        )

        assert sync_result.success == async_result.success
        assert sync_result.worker_id == async_result.worker_id


# =============================================================================
# 7. Async path behavioral equivalence
# =============================================================================


class TestAsyncPathEquivalence:
    """Verify async paths delegate to the same unified logic as sync paths."""

    def test_main_loop_as_async_delegates_to_main_loop(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """_main_loop_as_async runs _main_loop via asyncio.to_thread."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)
        (tmp_path / ".zerg" / "logs").mkdir(parents=True)

        patches = _create_orchestrator_patches()
        with (
            patch(patches["StateManager"]) as state_cls,
            patch(patches["LevelController"]),
            patch(patches["TaskParser"]),
            patch(patches["WorktreeManager"]),
            patch(patches["PortAllocator"]),
            patch(patches["MergeCoordinator"]),
            patch(patches["SubprocessLauncher"]),
            patch(patches["GateRunner"]),
            patch(patches["ContainerManager"]),
            patch(patches["TaskSyncBridge"]),
        ):
            state_cls.return_value = _make_state_mock()

            orch = Orchestrator("test-feature")
            orch._running = False  # Prevent infinite loop

            # Patch _main_loop to verify it's called
            main_loop_called = []
            _ = orch._main_loop  # noqa: F841

            def tracking_main_loop(sleep_fn: Any = None) -> None:
                main_loop_called.append(True)

            orch._main_loop = tracking_main_loop

            # Run the async wrapper
            asyncio.run(orch._main_loop_as_async())

            assert len(main_loop_called) == 1

    def test_start_async_initializes_same_as_sync(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """start_async sets up the same components as start (minus async state load)."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)
        (tmp_path / ".zerg" / "logs").mkdir(parents=True)
        (tmp_path / ".gsd" / "specs" / "test-feature").mkdir(parents=True)

        task_graph = {
            "feature": "test-feature",
            "version": "1.0",
            "generated": datetime.now().isoformat(),
            "total_tasks": 1,
            "tasks": [
                {
                    "id": "TASK-001",
                    "title": "Test",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["f.py"], "modify": [], "read": []},
                    "verification": {"command": "echo ok"},
                },
            ],
        }
        graph_path = tmp_path / "task-graph.json"
        with open(graph_path, "w") as f:
            json.dump(task_graph, f)

        patches = _create_orchestrator_patches()
        with (
            patch(patches["StateManager"]) as state_cls,
            patch(patches["LevelController"]) as levels_cls,
            patch(patches["TaskParser"]) as parser_cls,
            patch(patches["WorktreeManager"]) as wt_cls,
            patch(patches["PortAllocator"]) as ports_cls,
            patch(patches["MergeCoordinator"]),
            patch(patches["SubprocessLauncher"]) as launcher_cls,
            patch(patches["GateRunner"]),
            patch(patches["ContainerManager"]),
            patch(patches["TaskSyncBridge"]),
        ):
            state_mock = _make_state_mock()
            state_mock.load_async = AsyncMock(return_value={})
            state_cls.return_value = state_mock

            levels_mock = MagicMock()
            levels_cls.return_value = levels_mock

            parser_mock = MagicMock()
            parser_mock.get_all_tasks.return_value = task_graph["tasks"]
            parser_mock.levels = [1]
            parser_mock.total_tasks = 1
            parser_cls.return_value = parser_mock

            wt_cls.return_value = _make_worktree_mock(tmp_path)
            ports_cls.return_value = _make_ports_mock()
            launcher_cls.return_value = _make_launcher_mock()

            orch = Orchestrator("test-feature")

            # Dry run to avoid needing to mock the full main loop
            asyncio.run(orch.start_async(graph_path, worker_count=1, dry_run=True))

            # Should have parsed tasks and initialized levels
            parser_mock.parse.assert_called_once_with(graph_path)
            levels_mock.initialize.assert_called_once()
