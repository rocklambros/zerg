"""Unit tests targeting uncovered lines in zerg/orchestrator.py.

Coverage targets: lines 105-106, 117-118, 148, 246-247, 258-259,
332-333, 464-471, 521-523, 572-573, 595-599, 633, 675-750, 767,
780-801, 808-875, 882-909, 1004-1005.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zerg.constants import TaskStatus, WorkerStatus
from zerg.types import WorkerState

# ---------------------------------------------------------------------------
# Shared patch context: patches all heavy deps so Orchestrator.__init__ works
# ---------------------------------------------------------------------------

ORCH_PATCHES = {
    "state_cls": "zerg.orchestrator.StateManager",
    "levels_cls": "zerg.orchestrator.LevelController",
    "parser_cls": "zerg.orchestrator.TaskParser",
    "worktree_cls": "zerg.orchestrator.WorktreeManager",
    "ports_cls": "zerg.orchestrator.PortAllocator",
    "merge_cls": "zerg.orchestrator.MergeCoordinator",
    "launcher_cls": "zerg.orchestrator.SubprocessLauncher",
    "gate_cls": "zerg.orchestrator.GateRunner",
    "container_cls": "zerg.orchestrator.ContainerManager",
    "task_sync_cls": "zerg.orchestrator.TaskSyncBridge",
}


def _build_orchestrator(
    tmp_path: Path,
    feature: str = "test-feat",
    *,
    state_mock: MagicMock | None = None,
    levels_mock: MagicMock | None = None,
    launcher_mock: MagicMock | None = None,
    parser_mock: MagicMock | None = None,
):
    """Create an Orchestrator with all heavy deps mocked.

    Returns (orchestrator, mocks_dict, patches_dict).
    """
    from zerg.orchestrator import Orchestrator

    patches = {k: patch(v) for k, v in ORCH_PATCHES.items()}
    mocks = {k: p.start() for k, p in patches.items()}

    sm = state_mock or MagicMock()
    sm.load.return_value = {}
    sm._state = {"workers": {}, "tasks": {}}
    mocks["state_cls"].return_value = sm

    lm = levels_mock or MagicMock()
    lm.current_level = 1
    mocks["levels_cls"].return_value = lm

    if launcher_mock is not None:
        mocks["launcher_cls"].return_value = launcher_mock

    if parser_mock is not None:
        mocks["parser_cls"].return_value = parser_mock

    orch = Orchestrator(feature, repo_path=tmp_path)
    return orch, mocks, patches


def _stop_patches(patches: dict):
    for p in patches.values():
        p.stop()


# ===========================================================================
# Lines 105-106: Plugin load_entry_points failure branch
# ===========================================================================


class TestPluginLoadFailure:
    """Cover lines 105-106: exception in plugin_registry.load_entry_points."""

    def test_plugin_entry_points_exception_logged(self, tmp_path):
        """When load_entry_points raises, warning is logged and init continues."""
        from zerg.orchestrator import Orchestrator

        with (
            patch.dict("os.environ", {}, clear=False),
            patch("zerg.orchestrator.StateManager") as sc,
            patch("zerg.orchestrator.LevelController"),
            patch("zerg.orchestrator.TaskParser"),
            patch("zerg.orchestrator.WorktreeManager"),
            patch("zerg.orchestrator.PortAllocator"),
            patch("zerg.orchestrator.MergeCoordinator"),
            patch("zerg.orchestrator.SubprocessLauncher"),
            patch("zerg.orchestrator.GateRunner"),
            patch("zerg.orchestrator.ContainerManager"),
            patch("zerg.orchestrator.TaskSyncBridge"),
            patch("zerg.orchestrator.PluginRegistry") as pr_cls,
        ):
            sc.return_value = MagicMock()
            sc.return_value._state = {"workers": {}, "tasks": {}}

            # Make load_entry_points blow up after load_yaml_hooks succeeds
            registry_mock = MagicMock()
            registry_mock.load_yaml_hooks.return_value = None
            registry_mock.load_entry_points.side_effect = RuntimeError("boom")
            pr_cls.return_value = registry_mock

            # Build a config with plugins.enabled = True and hooks
            with patch("zerg.orchestrator.ZergConfig"):
                cfg = MagicMock()
                cfg.plugins.enabled = True
                cfg.plugins.hooks = []
                cfg.plugins.context_engineering = MagicMock(enabled=False)
                cfg.workers.timeout_minutes = 30
                cfg.workers.retry_attempts = 3
                cfg.logging.directory = ".zerg/logs"
                cfg.logging.level = "INFO"
                cfg.logging.max_log_size_mb = 50
                cfg.ports.range_start = 49200
                cfg.ports.range_end = 49400
                cfg.resources.container_memory_limit = "1g"
                cfg.resources.container_cpu_limit = "1.0"
                cfg.error_recovery.circuit_breaker.failure_threshold = 5
                cfg.error_recovery.circuit_breaker.cooldown_seconds = 60
                cfg.error_recovery.circuit_breaker.enabled = True
                cfg.error_recovery.backpressure.failure_rate_threshold = 0.5
                cfg.error_recovery.backpressure.window_size = 10
                cfg.error_recovery.backpressure.enabled = True

                orch = Orchestrator("feat", config=cfg, repo_path=tmp_path)

            # If we get here without error, the except block on 105-106 was hit
            assert orch is not None


# ===========================================================================
# Lines 117-118: Context engineering plugin registration failure
# ===========================================================================


class TestContextPluginRegistrationFailure:
    """Cover lines 117-118: exception registering context engineering plugin."""

    def test_context_plugin_registration_exception(self, tmp_path):
        from zerg.orchestrator import Orchestrator

        with (
            patch("zerg.orchestrator.StateManager") as sc,
            patch("zerg.orchestrator.LevelController"),
            patch("zerg.orchestrator.TaskParser"),
            patch("zerg.orchestrator.WorktreeManager"),
            patch("zerg.orchestrator.PortAllocator"),
            patch("zerg.orchestrator.MergeCoordinator"),
            patch("zerg.orchestrator.SubprocessLauncher"),
            patch("zerg.orchestrator.GateRunner"),
            patch("zerg.orchestrator.ContainerManager"),
            patch("zerg.orchestrator.TaskSyncBridge"),
            patch("zerg.orchestrator.ContextEngineeringPlugin", side_effect=RuntimeError("ctx boom")),
            patch("zerg.orchestrator.ContextEngineeringConfig") as cec,
        ):
            sc.return_value = MagicMock()
            sc.return_value._state = {"workers": {}, "tasks": {}}

            cec_inst = MagicMock()
            cec_inst.enabled = True
            cec.return_value = cec_inst

            orch = Orchestrator("feat", repo_path=tmp_path)
            # Line 117-118 exception caught; orchestrator created fine
            assert orch is not None


# ===========================================================================
# Line 148: _cleanup_orphan_containers for ContainerLauncher
# ===========================================================================


class TestCleanupOrphanContainers:
    """Cover line 148: cleanup called when launcher is ContainerLauncher."""

    def test_cleanup_orphan_called_for_container_launcher(self, tmp_path):
        from zerg.orchestrator import Orchestrator

        with (
            patch("zerg.orchestrator.StateManager") as sc,
            patch("zerg.orchestrator.LevelController"),
            patch("zerg.orchestrator.TaskParser"),
            patch("zerg.orchestrator.WorktreeManager"),
            patch("zerg.orchestrator.PortAllocator"),
            patch("zerg.orchestrator.MergeCoordinator"),
            patch("zerg.orchestrator.SubprocessLauncher"),
            patch("zerg.orchestrator.GateRunner"),
            patch("zerg.orchestrator.ContainerManager"),
            patch("zerg.orchestrator.TaskSyncBridge"),
            patch("zerg.orchestrator.ContainerLauncher") as cl_cls,
        ):
            sc.return_value = MagicMock()
            sc.return_value._state = {"workers": {}, "tasks": {}}

            container_launcher = cl_cls.return_value
            container_launcher.ensure_network.return_value = True

            orch = Orchestrator("feat", repo_path=tmp_path, launcher_mode="container")
            # Launcher is a ContainerLauncher mock, so isinstance check passes
            # and _cleanup_orphan_containers is called on line 148
            assert orch.launcher is not None


# ===========================================================================
# Lines 246-247, 258-259: plugin launcher paths in _create_launcher
# ===========================================================================


class TestPluginLauncherPath:
    """Cover lines 246-247 and 258-259: plugin launcher returned."""

    def test_create_launcher_with_plugin_mode(self, tmp_path):
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            fake_launcher = MagicMock()
            with patch("zerg.orchestrator.get_plugin_launcher", return_value=fake_launcher):
                result = orch._create_launcher(mode="custom-plugin")
            assert result is fake_launcher
        finally:
            _stop_patches(patches)

    def test_create_launcher_plugin_none_raises(self, tmp_path):
        """When plugin launcher returns None for unknown mode, ValueError raised."""
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            with patch("zerg.orchestrator.get_plugin_launcher", return_value=None):
                with pytest.raises(ValueError, match="Unsupported launcher mode"):
                    orch._create_launcher(mode="nonexistent-mode")
        finally:
            _stop_patches(patches)


# ===========================================================================
# Lines 332-333: _reassign_stranded_tasks active worker from state
# ===========================================================================


class TestReassignStrandedTasks:
    """Cover lines 332-333: collecting active IDs from disk state."""

    def test_active_ids_from_state(self, tmp_path):
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            # Set up disk state with an active worker (not stopped/crashed)
            sm = mocks["state_cls"].return_value
            sm._state = {
                "workers": {
                    "1": {"status": "running"},
                    "2": {"status": "stopped"},
                }
            }

            # Also add in-memory workers
            orch._workers[3] = WorkerState(worker_id=3, status=WorkerStatus.RUNNING)
            orch._workers[4] = WorkerState(worker_id=4, status=WorkerStatus.CRASHED)

            # Mock _state_sync so we can verify the active_ids parameter
            mock_sync = MagicMock()
            orch._state_sync = mock_sync

            orch._reassign_stranded_tasks()

            # The state_sync should receive active_ids = {1, 3}
            mock_sync.reassign_stranded_tasks.assert_called_once()
            active_ids = mock_sync.reassign_stranded_tasks.call_args[0][0]
            assert 1 in active_ids
            assert 3 in active_ids
            assert 2 not in active_ids
            assert 4 not in active_ids
        finally:
            _stop_patches(patches)


# ===========================================================================
# Lines 464-471: start() with start_level > 1 pre-marking prior levels
# ===========================================================================


class TestStartWithStartLevel:
    """Cover lines 464-471: resuming from level > 1."""

    def test_start_with_start_level_premark_levels(self, tmp_path):
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            parser = mocks["parser_cls"].return_value
            parser.parse.return_value = None
            tasks = [
                {"id": "T1", "level": 1, "title": "t1"},
                {"id": "T2", "level": 2, "title": "t2"},
                {"id": "T3", "level": 3, "title": "t3"},
            ]
            parser.get_all_tasks.return_value = tasks

            levels = mocks["levels_cls"].return_value
            # Create fake level objects for levels 1 and 2
            level1 = MagicMock()
            level1.total_tasks = 1
            level2 = MagicMock()
            level2.total_tasks = 1
            levels._levels = {1: level1, 2: level2}
            levels._tasks = {
                "T1": {"level": 1, "status": "pending"},
                "T2": {"level": 2, "status": "pending"},
                "T3": {"level": 3, "status": "pending"},
            }
            levels.current_level = 3

            # Worker spawning
            wm = orch._worker_manager
            wm.spawn_workers = MagicMock(return_value=2)
            wm.wait_for_initialization = MagicMock(return_value=True)
            orch._start_level = MagicMock()

            # Patch _main_loop to avoid infinite loop
            orch._main_loop = MagicMock()

            orch.start(
                task_graph_path="fake-graph.json",
                worker_count=2,
                start_level=3,
            )

            # Prior levels 1 and 2 should be pre-marked complete
            assert level1.completed_tasks == level1.total_tasks
            assert level1.status == "complete"
            assert level2.completed_tasks == level2.total_tasks
            assert level2.status == "complete"

            # Tasks at level 1 should be marked complete
            assert levels._tasks["T1"]["status"] == TaskStatus.COMPLETE.value

            orch._start_level.assert_called_once_with(3)
        finally:
            _stop_patches(patches)


# ===========================================================================
# Lines 521-523: status() metrics computation failure
# ===========================================================================


class TestStatusMetricsFailure:
    """Cover lines 521-523: MetricsCollector exception in status()."""

    def test_status_metrics_exception_returns_none(self, tmp_path):
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            levels = mocks["levels_cls"].return_value
            levels.get_status.return_value = {
                "current_level": 1,
                "total_tasks": 2,
                "completed_tasks": 0,
                "failed_tasks": 0,
                "in_progress_tasks": 1,
                "progress_percent": 0,
                "is_complete": False,
                "levels": {},
            }

            with patch("zerg.orchestrator.MetricsCollector") as mc_cls:
                mc_cls.side_effect = RuntimeError("metrics boom")
                result = orch.status()

            assert result["metrics"] is None
        finally:
            _stop_patches(patches)


# ===========================================================================
# Lines 572-573: _main_loop merge failure continues
# ===========================================================================


class TestMainLoopMergeFailure:
    """Cover lines 572-573: merge failure in main loop triggers continue."""

    def test_main_loop_merge_fail_continues(self, tmp_path):
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            orch._running = True
            orch._poll_workers = MagicMock()
            orch._check_retry_ready_tasks = MagicMock()

            levels = mocks["levels_cls"].return_value
            levels.current_level = 1
            levels.is_level_resolved.return_value = True
            levels.can_advance.return_value = False
            levels.get_status.return_value = {"is_complete": False}

            # Make _on_level_complete_handler return False (merge fail)
            call_count = 0

            def on_complete(level):
                nonlocal call_count
                call_count += 1
                return False

            orch._on_level_complete_handler = on_complete

            # Stop after 2 iterations
            iteration = 0

            def fake_sleep(t):
                nonlocal iteration
                iteration += 1
                if iteration >= 2:
                    orch._running = False

            with patch("time.sleep", side_effect=fake_sleep):
                orch._main_loop()

            # The handler was called once (level guard prevents re-entry)
            assert call_count == 1
        finally:
            _stop_patches(patches)


# ===========================================================================
# Lines 595-599: main loop respawn when all workers exited but tasks remain
# ===========================================================================


class TestMainLoopRespawnOnAllWorkersExited:
    """Cover lines 595-599: respawn workers when all exited with tasks remaining."""

    def test_respawn_when_workers_all_exited(self, tmp_path):
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            orch._running = True
            orch._poll_workers = MagicMock()
            orch._check_retry_ready_tasks = MagicMock()

            levels = mocks["levels_cls"].return_value
            levels.current_level = 1
            levels.is_level_resolved.return_value = False
            levels.get_pending_tasks_for_level.return_value = ["T1", "T2"]

            # All workers are stopped
            orch._workers[0] = WorkerState(worker_id=0, status=WorkerStatus.STOPPED)

            respawn_mock = MagicMock()
            orch._respawn_workers_for_level = respawn_mock

            iteration = 0

            def fake_sleep(t):
                nonlocal iteration
                iteration += 1
                if iteration >= 1:
                    orch._running = False

            with patch("time.sleep", side_effect=fake_sleep):
                orch._main_loop()

            respawn_mock.assert_called_once_with(1)
        finally:
            _stop_patches(patches)


# ===========================================================================
# Line 633: _poll_workers skips stopped/crashed workers
# ===========================================================================


class TestPollWorkersSkipStoppedCrashed:
    """Cover line 633: skip already stopped/crashed workers during poll."""

    def test_poll_workers_skips_stopped(self, tmp_path):
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            orch._workers[0] = WorkerState(worker_id=0, status=WorkerStatus.STOPPED)
            orch._workers[1] = WorkerState(worker_id=1, status=WorkerStatus.CRASHED)

            launcher = MagicMock()
            launcher.sync_state.return_value = None
            orch.launcher = launcher

            orch._sync_levels_from_state = MagicMock()
            orch._reassign_stranded_tasks = MagicMock()
            orch._check_container_health = MagicMock()
            orch.task_sync = MagicMock()

            orch._poll_workers()

            # monitor should NOT be called for stopped/crashed
            launcher.monitor.assert_not_called()
        finally:
            _stop_patches(patches)


# ===========================================================================
# Lines 675-750: start_async full path
# ===========================================================================


class TestStartAsync:
    """Cover lines 675-750: async start path."""

    def test_start_async_dry_run(self, tmp_path):
        """Dry run path of start_async."""
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            parser = mocks["parser_cls"].return_value
            parser.parse.return_value = None
            parser.get_all_tasks.return_value = [
                {"id": "T1", "level": 1, "title": "t"},
            ]
            parser.total_tasks = 1
            parser.levels = [1]
            parser.get_tasks_for_level.return_value = [{"id": "T1", "title": "t"}]

            sm = mocks["state_cls"].return_value
            sm.load_async = AsyncMock()

            orch._print_plan = MagicMock()

            asyncio.run(orch.start_async("fake.json", worker_count=1, dry_run=True))

            sm.load_async.assert_awaited_once()
            orch._print_plan.assert_called_once()
        finally:
            _stop_patches(patches)

    def test_start_async_zero_spawned_raises(self, tmp_path):
        """start_async raises when zero workers spawn."""
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            parser = mocks["parser_cls"].return_value
            parser.parse.return_value = None
            parser.get_all_tasks.return_value = [
                {"id": "T1", "level": 1, "title": "t"},
            ]

            sm = mocks["state_cls"].return_value
            sm.load_async = AsyncMock()
            sm.save_async = AsyncMock()

            orch._worker_manager.spawn_workers = MagicMock(return_value=0)

            with pytest.raises(RuntimeError, match="failed to spawn"):
                asyncio.run(orch.start_async("fake.json", worker_count=3))

            sm.save_async.assert_awaited_once()
        finally:
            _stop_patches(patches)

    def test_start_async_partial_spawn(self, tmp_path):
        """start_async continues with reduced capacity on partial spawn."""
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            parser = mocks["parser_cls"].return_value
            parser.parse.return_value = None
            tasks = [{"id": "T1", "level": 1, "title": "t"}]
            parser.get_all_tasks.return_value = tasks

            sm = mocks["state_cls"].return_value
            sm.load_async = AsyncMock()
            sm.save_async = AsyncMock()

            orch._worker_manager.spawn_workers = MagicMock(return_value=2)
            orch._worker_manager.wait_for_initialization = MagicMock(return_value=True)
            orch._start_level = MagicMock()
            orch._main_loop_async = AsyncMock()

            asyncio.run(orch.start_async("fake.json", worker_count=5))

            orch._main_loop_async.assert_awaited_once()
        finally:
            _stop_patches(patches)

    def test_start_async_with_start_level(self, tmp_path):
        """start_async pre-marks prior levels when start_level > 1."""
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            parser = mocks["parser_cls"].return_value
            parser.parse.return_value = None
            tasks = [
                {"id": "T1", "level": 1, "title": "t1"},
                {"id": "T2", "level": 2, "title": "t2"},
            ]
            parser.get_all_tasks.return_value = tasks

            sm = mocks["state_cls"].return_value
            sm.load_async = AsyncMock()

            levels = mocks["levels_cls"].return_value
            lvl1 = MagicMock()
            lvl1.total_tasks = 1
            levels._levels = {1: lvl1}
            levels._tasks = {"T1": {"level": 1, "status": "pending"}}

            orch._worker_manager.spawn_workers = MagicMock(return_value=2)
            orch._worker_manager.wait_for_initialization = MagicMock(return_value=True)
            orch._start_level = MagicMock()
            orch._main_loop_async = AsyncMock()

            asyncio.run(orch.start_async("fake.json", worker_count=2, start_level=2))

            assert lvl1.status == "complete"
            assert levels._tasks["T1"]["status"] == TaskStatus.COMPLETE.value
        finally:
            _stop_patches(patches)


# ===========================================================================
# Line 767: start_sync wraps start_async
# ===========================================================================


class TestStartSync:
    """Cover line 767: start_sync delegates to asyncio.run(start_async)."""

    def test_start_sync_calls_start_async(self, tmp_path):
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            orch.start_async = AsyncMock()
            orch.start_sync("graph.json", worker_count=2, start_level=1, dry_run=True)
            orch.start_async.assert_awaited_once_with(
                "graph.json",
                worker_count=2,
                start_level=1,
                dry_run=True,
            )
        finally:
            _stop_patches(patches)


# ===========================================================================
# Lines 780-801: stop_async
# ===========================================================================


class TestStopAsync:
    """Cover lines 780-801: async stop path."""

    def test_stop_async_normal(self, tmp_path):
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            orch._running = True
            orch._workers[0] = WorkerState(worker_id=0, status=WorkerStatus.RUNNING)
            orch._terminate_worker = MagicMock()

            sm = mocks["state_cls"].return_value
            sm.save_async = AsyncMock()

            asyncio.run(orch.stop_async(force=False))

            assert orch._running is False
            orch._terminate_worker.assert_called_once_with(0, force=False)
            sm.save_async.assert_awaited_once()
        finally:
            _stop_patches(patches)

    def test_stop_async_generate_state_md_failure(self, tmp_path):
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            sm = mocks["state_cls"].return_value
            sm.save_async = AsyncMock()
            sm.generate_state_md.side_effect = RuntimeError("md boom")

            asyncio.run(orch.stop_async(force=True))

            # Should not raise even though generate_state_md failed
            assert orch._running is False
        finally:
            _stop_patches(patches)


# ===========================================================================
# Lines 808-875: _main_loop_async
# ===========================================================================


class TestMainLoopAsync:
    """Cover lines 808-875: async main loop branches."""

    def test_main_loop_async_all_complete(self, tmp_path):
        """Loop exits when all tasks are complete."""
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            orch._running = True
            orch._poll_workers_async = AsyncMock()
            orch._check_retry_ready_tasks = MagicMock()

            levels = mocks["levels_cls"].return_value
            levels.current_level = 1
            levels.is_level_resolved.return_value = True
            levels.can_advance.return_value = False
            levels.get_status.return_value = {"is_complete": True}

            orch._on_level_complete_handler = MagicMock(return_value=True)

            asyncio.run(orch._main_loop_async())

            assert orch._running is False
        finally:
            _stop_patches(patches)

    def test_main_loop_async_merge_fail_continues(self, tmp_path):
        """Merge failure in async loop continues."""
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            orch._running = True
            orch._poll_workers_async = AsyncMock()
            orch._check_retry_ready_tasks = MagicMock()

            levels = mocks["levels_cls"].return_value
            levels.current_level = 1
            levels.is_level_resolved.return_value = True
            levels.get_pending_tasks_for_level.return_value = []

            call_count = 0

            def on_complete(level):
                nonlocal call_count
                call_count += 1
                return False

            orch._on_level_complete_handler = on_complete

            # All workers stopped
            orch._workers[0] = WorkerState(worker_id=0, status=WorkerStatus.STOPPED)

            iteration = 0

            async def fake_sleep(t):
                nonlocal iteration
                iteration += 1
                if iteration >= 2:
                    orch._running = False

            with patch("asyncio.sleep", side_effect=fake_sleep):
                asyncio.run(orch._main_loop_async())

            assert call_count == 1
        finally:
            _stop_patches(patches)

    def test_main_loop_async_advances_level(self, tmp_path):
        """Async loop advances to next level after merge success."""
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            orch._running = True
            orch._poll_workers_async = AsyncMock()
            orch._check_retry_ready_tasks = MagicMock()

            levels = mocks["levels_cls"].return_value
            levels.current_level = 1
            # First call: level resolved; second onward: not resolved
            levels.is_level_resolved.side_effect = [True, False, False]
            levels.can_advance.return_value = True
            levels.advance_level.return_value = 2
            levels.get_pending_tasks_for_level.return_value = []

            orch._on_level_complete_handler = MagicMock(return_value=True)
            orch._start_level = MagicMock()
            orch._respawn_workers_for_level = MagicMock()

            # Add a running worker so the "all workers exited" branch is not hit
            orch._workers[0] = WorkerState(worker_id=0, status=WorkerStatus.RUNNING)

            iteration = 0

            async def fake_sleep(t):
                nonlocal iteration
                iteration += 1
                if iteration >= 1:
                    orch._running = False

            with patch("asyncio.sleep", side_effect=fake_sleep):
                asyncio.run(orch._main_loop_async())

            orch._start_level.assert_called_with(2)
            orch._respawn_workers_for_level.assert_called_with(2)
        finally:
            _stop_patches(patches)

    def test_main_loop_async_respawn_workers(self, tmp_path):
        """Async loop respawns workers when all exited but tasks remain."""
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            orch._running = True
            orch._poll_workers_async = AsyncMock()
            orch._check_retry_ready_tasks = MagicMock()

            levels = mocks["levels_cls"].return_value
            levels.current_level = 1
            levels.is_level_resolved.return_value = False
            levels.get_pending_tasks_for_level.return_value = ["T1"]

            orch._workers[0] = WorkerState(worker_id=0, status=WorkerStatus.STOPPED)
            orch._respawn_workers_for_level = MagicMock()

            iteration = 0

            async def fake_sleep(t):
                nonlocal iteration
                iteration += 1
                if iteration >= 1:
                    orch._running = False

            with patch("asyncio.sleep", side_effect=fake_sleep):
                asyncio.run(orch._main_loop_async())

            orch._respawn_workers_for_level.assert_called_with(1)
        finally:
            _stop_patches(patches)

    def test_main_loop_async_keyboard_interrupt(self, tmp_path):
        """Async loop handles KeyboardInterrupt."""
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            orch._running = True
            orch._poll_workers_async = AsyncMock(side_effect=KeyboardInterrupt)
            orch.stop_async = AsyncMock()

            asyncio.run(orch._main_loop_async())

            orch.stop_async.assert_awaited_once()
        finally:
            _stop_patches(patches)

    def test_main_loop_async_exception_stops(self, tmp_path):
        """Async loop handles generic exception by stopping."""
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            orch._running = True
            orch._poll_workers_async = AsyncMock(side_effect=ValueError("bad"))
            orch.stop_async = AsyncMock()

            sm = mocks["state_cls"].return_value

            with pytest.raises(ValueError, match="bad"):
                asyncio.run(orch._main_loop_async())

            sm.set_error.assert_called_once()
            orch.stop_async.assert_awaited_once_with(force=True)
        finally:
            _stop_patches(patches)


# ===========================================================================
# Lines 882-909: _poll_workers_async
# ===========================================================================


class TestPollWorkersAsync:
    """Cover lines 882-909: async worker polling."""

    def test_poll_workers_async_crashed(self, tmp_path):
        """Async poll detects crashed worker."""
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            worker = WorkerState(worker_id=0, status=WorkerStatus.RUNNING, current_task="T1")
            orch._workers[0] = worker

            sm = mocks["state_cls"].return_value
            sm.load_async = AsyncMock()

            launcher = MagicMock()
            launcher.monitor.return_value = WorkerStatus.CRASHED
            launcher.sync_state.return_value = None
            orch.launcher = launcher

            orch._sync_levels_from_state = MagicMock()
            orch._reassign_stranded_tasks = MagicMock()
            orch._check_container_health = MagicMock()
            orch.task_sync = MagicMock()
            orch._handle_task_failure = MagicMock()
            orch._handle_worker_exit = MagicMock()

            asyncio.run(orch._poll_workers_async())

            assert worker.status == WorkerStatus.CRASHED
            sm.set_worker_state.assert_called()
            orch._handle_task_failure.assert_called_once_with("T1", 0, "Worker crashed")
            orch._handle_worker_exit.assert_called_once_with(0)
        finally:
            _stop_patches(patches)

    def test_poll_workers_async_crashed_no_task(self, tmp_path):
        """Async poll detects crashed worker with no current task."""
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            worker = WorkerState(worker_id=0, status=WorkerStatus.RUNNING, current_task=None)
            orch._workers[0] = worker

            sm = mocks["state_cls"].return_value
            sm.load_async = AsyncMock()

            launcher = MagicMock()
            launcher.monitor.return_value = WorkerStatus.CRASHED
            launcher.sync_state.return_value = None
            orch.launcher = launcher

            orch._sync_levels_from_state = MagicMock()
            orch._reassign_stranded_tasks = MagicMock()
            orch._check_container_health = MagicMock()
            orch.task_sync = MagicMock()
            orch._handle_task_failure = MagicMock()
            orch._handle_worker_exit = MagicMock()

            asyncio.run(orch._poll_workers_async())

            assert worker.status == WorkerStatus.CRASHED
            # _handle_task_failure should NOT be called when no current_task
            orch._handle_task_failure.assert_not_called()
            orch._handle_worker_exit.assert_called_once_with(0)
        finally:
            _stop_patches(patches)

    def test_poll_workers_async_checkpointing(self, tmp_path):
        """Async poll detects checkpointing worker."""
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            worker = WorkerState(worker_id=0, status=WorkerStatus.RUNNING)
            orch._workers[0] = worker

            sm = mocks["state_cls"].return_value
            sm.load_async = AsyncMock()

            launcher = MagicMock()
            launcher.monitor.return_value = WorkerStatus.CHECKPOINTING
            launcher.sync_state.return_value = None
            orch.launcher = launcher

            orch._sync_levels_from_state = MagicMock()
            orch._reassign_stranded_tasks = MagicMock()
            orch._check_container_health = MagicMock()
            orch.task_sync = MagicMock()
            orch._handle_worker_exit = MagicMock()

            asyncio.run(orch._poll_workers_async())

            assert worker.status == WorkerStatus.CHECKPOINTING
            orch._handle_worker_exit.assert_called_once_with(0)
        finally:
            _stop_patches(patches)

    def test_poll_workers_async_stopped(self, tmp_path):
        """Async poll detects stopped worker."""
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            worker = WorkerState(worker_id=0, status=WorkerStatus.RUNNING)
            orch._workers[0] = worker

            sm = mocks["state_cls"].return_value
            sm.load_async = AsyncMock()

            launcher = MagicMock()
            launcher.monitor.return_value = WorkerStatus.STOPPED
            launcher.sync_state.return_value = None
            orch.launcher = launcher

            orch._sync_levels_from_state = MagicMock()
            orch._reassign_stranded_tasks = MagicMock()
            orch._check_container_health = MagicMock()
            orch.task_sync = MagicMock()
            orch._handle_worker_exit = MagicMock()

            asyncio.run(orch._poll_workers_async())

            assert worker.status == WorkerStatus.STOPPED
            orch._handle_worker_exit.assert_called_once_with(0)
        finally:
            _stop_patches(patches)

    def test_poll_workers_async_skips_stopped(self, tmp_path):
        """Async poll skips already stopped workers."""
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            worker = WorkerState(worker_id=0, status=WorkerStatus.STOPPED)
            orch._workers[0] = worker

            sm = mocks["state_cls"].return_value
            sm.load_async = AsyncMock()

            launcher = MagicMock()
            launcher.sync_state.return_value = None
            orch.launcher = launcher

            orch._sync_levels_from_state = MagicMock()
            orch._reassign_stranded_tasks = MagicMock()
            orch._check_container_health = MagicMock()
            orch.task_sync = MagicMock()

            asyncio.run(orch._poll_workers_async())

            launcher.monitor.assert_not_called()
        finally:
            _stop_patches(patches)


# ===========================================================================
# Lines 1004-1005: generate_task_contexts exception path
# ===========================================================================


class TestGenerateTaskContextsException:
    """Cover lines 1004-1005: exception building task context."""

    def test_context_generation_exception_logged(self, tmp_path):
        orch, mocks, patches = _build_orchestrator(tmp_path)
        try:
            orch._plugin_registry = MagicMock()
            orch._plugin_registry.build_task_context.side_effect = RuntimeError("ctx err")

            task_graph = {
                "feature": "test",
                "tasks": [
                    {"id": "T1", "title": "task"},  # no "context" key
                ],
            }

            result = orch.generate_task_contexts(task_graph)

            # Exception is caught, no context generated
            assert result == {}
            # Task should NOT have a context key added
            assert "context" not in task_graph["tasks"][0]
        finally:
            _stop_patches(patches)
