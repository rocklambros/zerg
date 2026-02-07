"""Integration tests for WorkerRegistry wiring into the orchestrator ecosystem.

Verifies that the WorkerRegistry is properly created by the Orchestrator and
shared with all consuming components (WorkerManager, LevelCoordinator,
LauncherConfigurator) as the single source of truth for worker state.

Tests cover:
1. Orchestrator creates registry and passes to consumers
2. WorkerManager register propagates to shared registry
3. Concurrent access from multiple components is thread-safe
4. Full orchestrator init succeeds with WorkerRegistry
"""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

from zerg.constants import WorkerStatus
from zerg.orchestrator import Orchestrator
from zerg.types import WorkerState
from zerg.worker_registry import WorkerRegistry

# =============================================================================
# Helpers
# =============================================================================


def _patch_orchestrator_deps():
    """Context manager that patches all Orchestrator external dependencies.

    Returns a context manager yielding a dict of mock instances keyed by name.
    """
    return _OrchestratorDepsPatcher()


class _OrchestratorDepsPatcher:
    """Patches all Orchestrator dependencies for isolated testing."""

    def __enter__(self) -> dict[str, MagicMock]:
        self._patches = [
            patch("zerg.orchestrator.StateManager"),
            patch("zerg.orchestrator.LevelController"),
            patch("zerg.orchestrator.TaskParser"),
            patch("zerg.orchestrator.WorktreeManager"),
            patch("zerg.orchestrator.PortAllocator"),
            patch("zerg.orchestrator.MergeCoordinator"),
            patch("zerg.orchestrator.SubprocessLauncher"),
            patch("zerg.orchestrator.GateRunner"),
            patch("zerg.orchestrator.ContainerManager"),
            patch("zerg.orchestrator.TaskSyncBridge"),
            patch("zerg.orchestrator.MetricsCollector"),
        ]
        mocks = [p.start() for p in self._patches]

        # StateManager needs .load() to return a dict
        state_mock = mocks[0].return_value
        state_mock.load.return_value = {}
        state_mock._state = {"tasks": {}}

        # LevelController defaults
        levels_mock = mocks[1].return_value
        levels_mock.current_level = 1
        levels_mock.get_status.return_value = {
            "current_level": 1,
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "in_progress_tasks": 0,
            "progress_percent": 0,
            "is_complete": False,
            "levels": {},
        }

        # TaskParser defaults
        parser_mock = mocks[2].return_value
        parser_mock.get_all_tasks.return_value = []
        parser_mock.total_tasks = 0
        parser_mock.levels = [1]

        # PortAllocator
        ports_mock = mocks[4].return_value
        ports_mock.allocate_one.return_value = 49152

        # SubprocessLauncher defaults
        launcher_mock = mocks[6].return_value
        spawn_result = MagicMock()
        spawn_result.success = True
        spawn_result.handle = MagicMock()
        spawn_result.handle.container_id = None
        launcher_mock.spawn.return_value = spawn_result
        launcher_mock.monitor.return_value = WorkerStatus.RUNNING
        launcher_mock.sync_state.return_value = None

        # WorktreeManager
        worktree_mock = mocks[3].return_value
        wt_info = MagicMock()
        wt_info.path = Path("/tmp/test-worktree")
        wt_info.branch = "zerg/test/worker-0"
        worktree_mock.create.return_value = wt_info

        return {
            "state": state_mock,
            "levels": levels_mock,
            "parser": parser_mock,
            "worktree": worktree_mock,
            "ports": ports_mock,
            "launcher": launcher_mock,
        }

    def __exit__(self, *args: object) -> None:
        for p in self._patches:
            p.stop()


# =============================================================================
# Test 1: Orchestrator creates registry and passes to consumers
# =============================================================================


class TestOrchestratorCreatesRegistryAndPassesToConsumers:
    """Verify the Orchestrator creates a WorkerRegistry and shares it."""

    def test_orchestrator_registry_is_worker_registry_instance(self) -> None:
        """Orchestrator.registry should be a WorkerRegistry instance."""
        with _patch_orchestrator_deps():
            orch = Orchestrator("test-feature")
            assert isinstance(orch.registry, WorkerRegistry)

    def test_registry_passed_to_worker_manager(self) -> None:
        """WorkerManager should receive the same WorkerRegistry reference."""
        with _patch_orchestrator_deps():
            orch = Orchestrator("test-feature")
            # WorkerManager stores the registry as _workers
            assert orch._worker_manager._workers is orch.registry

    def test_registry_passed_to_level_coordinator(self) -> None:
        """LevelCoordinator should receive the same WorkerRegistry reference."""
        with _patch_orchestrator_deps():
            orch = Orchestrator("test-feature")
            # LevelCoordinator stores the registry as _workers
            assert orch._level_coord._workers is orch.registry

    def test_workers_property_aliases_registry(self) -> None:
        """The backward-compatible _workers property should alias the registry."""
        with _patch_orchestrator_deps():
            orch = Orchestrator("test-feature")
            assert orch._workers is orch.registry

    def test_all_consumers_share_same_instance(self) -> None:
        """All components must share the exact same WorkerRegistry object."""
        with _patch_orchestrator_deps():
            orch = Orchestrator("test-feature")
            registry = orch.registry
            assert orch._worker_manager._workers is registry
            assert orch._level_coord._workers is registry
            assert orch._workers is registry


# =============================================================================
# Test 2: WorkerManager register propagates to shared registry
# =============================================================================


class TestWorkerManagerRegisterPropagates:
    """Verify that registering a worker via WorkerManager is visible everywhere."""

    def test_register_via_worker_manager_visible_in_registry(self) -> None:
        """A worker registered through WorkerManager should appear in the registry."""
        with _patch_orchestrator_deps():
            orch = Orchestrator("test-feature")

            worker = WorkerState(
                worker_id=0,
                status=WorkerStatus.RUNNING,
                port=49152,
                branch="zerg/test/worker-0",
            )
            orch.registry.register(0, worker)

            # Verify visible from all angles
            assert orch.registry.get(0) is worker
            assert orch._worker_manager._workers.get(0) is worker
            assert orch._level_coord._workers.get(0) is worker

    def test_register_via_registry_visible_in_level_coordinator(self) -> None:
        """Workers registered in the shared registry are visible to LevelCoordinator."""
        with _patch_orchestrator_deps():
            orch = Orchestrator("test-feature")

            worker = WorkerState(
                worker_id=1,
                status=WorkerStatus.INITIALIZING,
                port=49153,
                branch="zerg/test/worker-1",
            )
            orch.registry.register(1, worker)

            # LevelCoordinator should see the worker through its _workers ref
            assert 1 in orch._level_coord._workers
            assert orch._level_coord._workers[1].status == WorkerStatus.INITIALIZING

    def test_unregister_propagates_across_components(self) -> None:
        """Unregistering a worker should be reflected in all components."""
        with _patch_orchestrator_deps():
            orch = Orchestrator("test-feature")

            worker = WorkerState(
                worker_id=0,
                status=WorkerStatus.RUNNING,
                port=49152,
                branch="zerg/test/worker-0",
            )
            orch.registry.register(0, worker)
            assert 0 in orch._worker_manager._workers

            orch.registry.unregister(0)

            assert orch.registry.get(0) is None
            assert 0 not in orch._worker_manager._workers
            assert 0 not in orch._level_coord._workers

    def test_status_update_propagates(self) -> None:
        """Updating worker status in registry should be visible in all consumers."""
        with _patch_orchestrator_deps():
            orch = Orchestrator("test-feature")

            worker = WorkerState(
                worker_id=0,
                status=WorkerStatus.INITIALIZING,
                port=49152,
                branch="zerg/test/worker-0",
            )
            orch.registry.register(0, worker)

            orch.registry.update_status(0, WorkerStatus.RUNNING)

            # All components should see the updated status
            assert orch.registry.get(0).status == WorkerStatus.RUNNING
            assert orch._worker_manager._workers[0].status == WorkerStatus.RUNNING
            assert orch._level_coord._workers[0].status == WorkerStatus.RUNNING


# =============================================================================
# Test 3: Concurrent access from multiple components
# =============================================================================


class TestConcurrentAccessThreadSafety:
    """Verify thread-safety when multiple components access the registry."""

    def test_concurrent_register_and_read(self) -> None:
        """Multiple threads registering and reading simultaneously should not corrupt."""
        registry = WorkerRegistry()
        errors: list[str] = []
        worker_count = 50

        def register_workers(start: int, count: int) -> None:
            for i in range(start, start + count):
                try:
                    worker = WorkerState(
                        worker_id=i,
                        status=WorkerStatus.RUNNING,
                        port=49152 + i,
                        branch=f"zerg/test/worker-{i}",
                    )
                    registry.register(i, worker)
                except Exception as e:  # noqa: BLE001 — intentional: concurrency test; thread safety validation
                    errors.append(f"Register error for worker {i}: {e}")

        def read_workers() -> None:
            for _ in range(100):
                try:
                    _ = registry.all()
                    _ = len(registry)
                    _ = list(registry.keys())
                except Exception as e:  # noqa: BLE001 — intentional: concurrency test; thread safety validation
                    errors.append(f"Read error: {e}")

        threads = []
        # 5 writer threads, each registering 10 workers
        for t in range(5):
            threads.append(threading.Thread(target=register_workers, args=(t * 10, 10)))
        # 3 reader threads
        for _ in range(3):
            threads.append(threading.Thread(target=read_workers))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Thread safety errors: {errors}"
        assert len(registry) == worker_count

    def test_concurrent_register_and_unregister(self) -> None:
        """Concurrent register and unregister should not raise."""
        registry = WorkerRegistry()
        errors: list[str] = []

        # Pre-populate some workers
        for i in range(20):
            registry.register(
                i,
                WorkerState(
                    worker_id=i,
                    status=WorkerStatus.RUNNING,
                    port=49152 + i,
                    branch=f"zerg/test/worker-{i}",
                ),
            )

        def unregister_workers(ids: list[int]) -> None:
            for wid in ids:
                try:
                    registry.unregister(wid)
                except Exception as e:  # noqa: BLE001 — intentional: concurrency test; thread safety validation
                    errors.append(f"Unregister error for {wid}: {e}")

        def register_new_workers(start: int, count: int) -> None:
            for i in range(start, start + count):
                try:
                    registry.register(
                        i,
                        WorkerState(
                            worker_id=i,
                            status=WorkerStatus.INITIALIZING,
                            port=49200 + i,
                            branch=f"zerg/test/new-{i}",
                        ),
                    )
                except Exception as e:  # noqa: BLE001 — intentional: concurrency test; thread safety validation
                    errors.append(f"Register error for {i}: {e}")

        threads = [
            threading.Thread(target=unregister_workers, args=(list(range(0, 10)),)),
            threading.Thread(target=unregister_workers, args=(list(range(10, 20)),)),
            threading.Thread(target=register_new_workers, args=(100, 20)),
            threading.Thread(target=register_new_workers, args=(200, 20)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Thread safety errors: {errors}"
        # Original 20 removed, 40 new added
        assert len(registry) == 40

    def test_concurrent_update_status(self) -> None:
        """Concurrent status updates should not corrupt state."""
        registry = WorkerRegistry()
        errors: list[str] = []

        # Register a single worker
        registry.register(
            0,
            WorkerState(
                worker_id=0,
                status=WorkerStatus.INITIALIZING,
                port=49152,
                branch="zerg/test/worker-0",
            ),
        )

        statuses = [
            WorkerStatus.RUNNING,
            WorkerStatus.CHECKPOINTING,
            WorkerStatus.BLOCKED,
            WorkerStatus.RUNNING,
            WorkerStatus.STOPPED,
        ]

        def update_status_repeatedly(status_sequence: list[WorkerStatus]) -> None:
            for st in status_sequence:
                try:
                    registry.update_status(0, st)
                except Exception as e:  # noqa: BLE001 — intentional: concurrency test; thread safety validation
                    errors.append(f"Update error: {e}")

        threads = [
            threading.Thread(target=update_status_repeatedly, args=(statuses,)),
            threading.Thread(target=update_status_repeatedly, args=(list(reversed(statuses)),)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Thread safety errors: {errors}"
        # The worker should still exist and have a valid status
        worker = registry.get(0)
        assert worker is not None
        assert isinstance(worker.status, WorkerStatus)


# =============================================================================
# Test 4: Full orchestrator init with registry
# =============================================================================


class TestFullOrchestratorInitWithRegistry:
    """Verify that full Orchestrator init succeeds with WorkerRegistry."""

    def test_orchestrator_init_creates_registry(self) -> None:
        """Orchestrator.__init__ should create a WorkerRegistry, not a plain dict."""
        with _patch_orchestrator_deps():
            orch = Orchestrator("test-feature")
            assert isinstance(orch.registry, WorkerRegistry)
            assert len(orch.registry) == 0

    def test_orchestrator_init_with_custom_config(self) -> None:
        """Orchestrator init with custom config still uses WorkerRegistry."""
        from zerg.config import ZergConfig

        with _patch_orchestrator_deps():
            config = ZergConfig()
            orch = Orchestrator("test-feature", config=config)
            assert isinstance(orch.registry, WorkerRegistry)

    def test_orchestrator_init_with_launcher_mode(self) -> None:
        """Orchestrator init with explicit launcher mode uses WorkerRegistry."""
        with _patch_orchestrator_deps():
            orch = Orchestrator("test-feature", launcher_mode="subprocess")
            assert isinstance(orch.registry, WorkerRegistry)
            # Verify registry is passed to sub-components
            assert isinstance(orch._worker_manager._workers, WorkerRegistry)
            assert isinstance(orch._level_coord._workers, WorkerRegistry)

    def test_registry_dict_compatibility_in_status(self) -> None:
        """The status() method should work with WorkerRegistry dict-like interface."""
        with _patch_orchestrator_deps():
            orch = Orchestrator("test-feature")

            # Register a worker to verify dict-like iteration works in status()
            worker = WorkerState(
                worker_id=0,
                status=WorkerStatus.RUNNING,
                current_task="TASK-001",
                port=49152,
                branch="zerg/test/worker-0",
            )
            orch.registry.register(0, worker)

            status = orch.status()

            # Verify the status dict includes the worker
            assert 0 in status["workers"]
            assert status["workers"][0]["status"] == "running"
            assert status["workers"][0]["current_task"] == "TASK-001"

    def test_registry_supports_iteration_patterns(self) -> None:
        """Verify that common iteration patterns used by orchestrator work."""
        with _patch_orchestrator_deps():
            orch = Orchestrator("test-feature")

            # Register multiple workers
            for i in range(3):
                orch.registry.register(
                    i,
                    WorkerState(
                        worker_id=i,
                        status=WorkerStatus.RUNNING,
                        port=49152 + i,
                        branch=f"zerg/test/worker-{i}",
                    ),
                )

            # Test patterns used in orchestrator code
            # list(self._workers.keys())
            keys = list(orch._workers.keys())
            assert sorted(keys) == [0, 1, 2]

            # list(self._workers.items())
            items = list(orch._workers.items())
            assert len(items) == 3

            # wid in self._workers
            assert 0 in orch._workers
            assert 99 not in orch._workers

            # self._workers[wid]
            w = orch._workers[0]
            assert w.worker_id == 0

            # len(self._workers)
            assert len(orch._workers) == 3
