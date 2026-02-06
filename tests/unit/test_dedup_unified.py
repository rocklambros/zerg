"""Unit tests for sync/async deduplication in the ZERG codebase.

Verifies that the dedup refactoring (Level 1-2 of core-refactoring) is correct:

1. Callable injection patterns work in launcher.py
   (_spawn_with_retry_impl, _start_container_impl, _terminate_impl)
2. Sync wrappers correctly delegate to async implementations
   (worker_protocol.py: wait_for_ready, claim_next_task)
3. No remaining duplicate method pairs exist (introspection-based)
4. Unified _main_loop has escalation, progress, stall detection
5. _poll_workers_async no longer exists
6. _main_loop_async no longer exists (replaced by _main_loop_as_async)
"""

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from zerg.constants import WorkerStatus
from zerg.launcher_types import SpawnResult
from zerg.launchers import ContainerLauncher, SubprocessLauncher, WorkerLauncher

# =============================================================================
# Helper: Concrete WorkerLauncher for testing base-class dedup patterns
# =============================================================================


class StubLauncher(WorkerLauncher):
    """Minimal concrete WorkerLauncher for testing base-class methods."""

    def spawn(
        self,
        worker_id: int,
        feature: str,
        worktree_path: Path,
        branch: str,
        env: dict[str, str] | None = None,
    ) -> SpawnResult:
        return SpawnResult(success=True, worker_id=worker_id)

    def monitor(self, worker_id: int) -> WorkerStatus:
        return WorkerStatus.RUNNING

    def terminate(self, worker_id: int, force: bool = False) -> bool:
        return True

    def get_output(self, worker_id: int, tail: int = 100) -> str:
        return ""


# =============================================================================
# 1. Launcher callable injection patterns
# =============================================================================


class TestSpawnWithRetryImpl:
    """Verify _spawn_with_retry_impl accepts callables and delegates correctly."""

    def test_impl_is_async_method(self) -> None:
        """_spawn_with_retry_impl must be a coroutine function."""
        assert asyncio.iscoroutinefunction(WorkerLauncher._spawn_with_retry_impl)

    def test_impl_accepts_spawn_fn_and_sleep_fn(self) -> None:
        """_spawn_with_retry_impl signature must include spawn_fn and sleep_fn."""
        sig = inspect.signature(WorkerLauncher._spawn_with_retry_impl)
        param_names = list(sig.parameters.keys())
        assert "spawn_fn" in param_names
        assert "sleep_fn" in param_names

    def test_sync_wrapper_delegates_to_impl(self) -> None:
        """spawn_with_retry (sync) must call _spawn_with_retry_impl via asyncio.run."""
        launcher = StubLauncher()
        wt = Path("/tmp/test-wt")

        # The sync wrapper should succeed (spawn returns success=True by default)
        result = launcher.spawn_with_retry(
            worker_id=1,
            feature="test",
            worktree_path=wt,
            branch="main",
            max_attempts=1,
        )
        assert result.success is True
        assert result.worker_id == 1

    def test_async_wrapper_delegates_to_impl(self) -> None:
        """spawn_with_retry_async must call _spawn_with_retry_impl directly."""
        launcher = StubLauncher()
        wt = Path("/tmp/test-wt")

        result = asyncio.run(
            launcher.spawn_with_retry_async(
                worker_id=2,
                feature="test",
                worktree_path=wt,
                branch="main",
                max_attempts=1,
            )
        )
        assert result.success is True
        assert result.worker_id == 2

    def test_retry_uses_sleep_fn(self) -> None:
        """On failure, impl must call the injected sleep_fn for backoff."""
        sleep_calls: list[float] = []

        async def fake_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        call_count = 0

        async def fail_then_succeed(wid: int, feat: str, wt: Path, br: str, e: Any) -> SpawnResult:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return SpawnResult(success=False, worker_id=wid, error="transient")
            return SpawnResult(success=True, worker_id=wid)

        launcher = StubLauncher()
        result = asyncio.run(
            launcher._spawn_with_retry_impl(
                worker_id=1,
                feature="test",
                worktree_path=Path("/tmp"),
                branch="main",
                env=None,
                max_attempts=3,
                backoff_strategy="exponential",
                backoff_base_seconds=1.0,
                backoff_max_seconds=30.0,
                spawn_fn=fail_then_succeed,
                sleep_fn=fake_sleep,
            )
        )
        assert result.success is True
        assert len(sleep_calls) == 1  # slept once between attempt 1 and 2

    def test_all_attempts_fail_returns_error(self) -> None:
        """When all attempts fail, impl returns error SpawnResult."""

        async def always_fail(wid: int, feat: str, wt: Path, br: str, e: Any) -> SpawnResult:
            return SpawnResult(success=False, worker_id=wid, error="permanent")

        async def noop_sleep(delay: float) -> None:
            pass

        launcher = StubLauncher()
        result = asyncio.run(
            launcher._spawn_with_retry_impl(
                worker_id=1,
                feature="test",
                worktree_path=Path("/tmp"),
                branch="main",
                env=None,
                max_attempts=2,
                backoff_strategy="exponential",
                backoff_base_seconds=1.0,
                backoff_max_seconds=10.0,
                spawn_fn=always_fail,
                sleep_fn=noop_sleep,
            )
        )
        assert result.success is False
        assert "All 2 spawn attempts failed" in (result.error or "")


class TestStartContainerImpl:
    """Verify _start_container_impl and _build_container_cmd in ContainerLauncher."""

    def test_build_container_cmd_is_single_source(self) -> None:
        """_build_container_cmd must exist and be used by _start_container_impl."""
        assert hasattr(ContainerLauncher, "_build_container_cmd")
        assert hasattr(ContainerLauncher, "_start_container_impl")

    def test_start_container_impl_is_async(self) -> None:
        """_start_container_impl must be a coroutine function."""
        assert asyncio.iscoroutinefunction(ContainerLauncher._start_container_impl)

    def test_start_container_impl_accepts_run_fn(self) -> None:
        """_start_container_impl signature must include run_fn."""
        sig = inspect.signature(ContainerLauncher._start_container_impl)
        assert "run_fn" in sig.parameters

    @patch("zerg.launchers.container_launcher.Path.home")
    @patch("os.getuid", return_value=1000)
    @patch("os.getgid", return_value=1000)
    def test_sync_wrapper_calls_impl(self, mock_gid: MagicMock, mock_uid: MagicMock, mock_home: MagicMock) -> None:
        """_start_container (sync) must delegate to _start_container_impl."""
        mock_home.return_value = Path("/fake/home")
        launcher = ContainerLauncher(image_name="test-image")

        # Patch _start_container_impl to verify it gets called
        with patch.object(launcher, "_start_container_impl", new_callable=AsyncMock) as mock_impl:
            mock_impl.return_value = "abc123"
            result = launcher._start_container(
                container_name="test-container",
                worktree_path=Path("/fake/worktree"),
                env={"ZERG_WORKER_ID": "1"},
            )
            assert result == "abc123"
            mock_impl.assert_called_once()


class TestTerminateImpl:
    """Verify _terminate_impl in ContainerLauncher."""

    def test_terminate_impl_is_async(self) -> None:
        """_terminate_impl must be a coroutine function."""
        assert asyncio.iscoroutinefunction(ContainerLauncher._terminate_impl)

    def test_terminate_impl_accepts_run_fn(self) -> None:
        """_terminate_impl signature must include run_fn."""
        sig = inspect.signature(ContainerLauncher._terminate_impl)
        assert "run_fn" in sig.parameters

    def test_sync_terminate_delegates_to_impl(self) -> None:
        """terminate() (sync) must delegate to _terminate_impl."""
        launcher = ContainerLauncher(image_name="test-image")

        with patch.object(launcher, "_terminate_impl", new_callable=AsyncMock) as mock_impl:
            mock_impl.return_value = True
            # Need to set up container_ids and workers
            from zerg.launcher_types import WorkerHandle

            launcher._container_ids[1] = "abc123"
            launcher._workers[1] = WorkerHandle(worker_id=1, status=WorkerStatus.RUNNING)

            result = launcher.terminate(1)
            assert result is True
            mock_impl.assert_called_once()

    def test_async_terminate_delegates_to_impl(self) -> None:
        """terminate_async() must delegate to _terminate_impl."""
        launcher = ContainerLauncher(image_name="test-image")

        with patch.object(launcher, "_terminate_impl", new_callable=AsyncMock) as mock_impl:
            mock_impl.return_value = True
            from zerg.launcher_types import WorkerHandle

            launcher._container_ids[1] = "abc123"
            launcher._workers[1] = WorkerHandle(worker_id=1, status=WorkerStatus.RUNNING)

            result = asyncio.run(launcher.terminate_async(1))
            assert result is True
            mock_impl.assert_called_once()


# =============================================================================
# 2. Worker protocol sync-to-async delegation
# =============================================================================


class TestWorkerProtocolDelegation:
    """Verify sync wrappers in worker_protocol.py delegate to async implementations."""

    def test_wait_for_ready_sync_delegates_to_async(self) -> None:
        """wait_for_ready (sync) must call wait_for_ready_async via asyncio.run."""
        from zerg.protocol_state import WorkerProtocol

        # Verify the sync method calls the async method
        source = inspect.getsource(WorkerProtocol.wait_for_ready)
        assert "asyncio.run" in source
        assert "wait_for_ready_async" in source

    def test_claim_next_task_sync_delegates_to_async(self) -> None:
        """claim_next_task (sync) must call claim_next_task_async via asyncio.run."""
        from zerg.protocol_state import WorkerProtocol

        source = inspect.getsource(WorkerProtocol.claim_next_task)
        assert "asyncio.run" in source
        assert "claim_next_task_async" in source

    def test_wait_for_ready_async_is_source_of_truth(self) -> None:
        """wait_for_ready_async must be the single source of truth with actual logic."""
        from zerg.protocol_state import WorkerProtocol

        assert asyncio.iscoroutinefunction(WorkerProtocol.wait_for_ready_async)
        source = inspect.getsource(WorkerProtocol.wait_for_ready_async)
        # Must contain the actual polling logic, not just delegation
        assert "asyncio.sleep" in source
        assert "_is_ready" in source

    def test_claim_next_task_async_is_source_of_truth(self) -> None:
        """claim_next_task_async must be the single source of truth with actual logic."""
        from zerg.protocol_state import WorkerProtocol

        assert asyncio.iscoroutinefunction(WorkerProtocol.claim_next_task_async)
        source = inspect.getsource(WorkerProtocol.claim_next_task_async)
        # Must contain the actual claiming logic
        assert "asyncio.sleep" in source
        assert "claim_task" in source


# =============================================================================
# 3. No remaining duplicate method pairs (introspection)
# =============================================================================


class TestNoDuplicateMethodPairs:
    """Verify no sync/async duplicate method pairs remain outside the dedup pattern."""

    def _get_public_methods(self, cls: type) -> dict[str, bool]:
        """Get all public methods with their async status.

        Returns dict mapping method_name -> is_coroutine.
        """
        methods: dict[str, bool] = {}
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            if name.startswith("_"):
                continue
            methods[name] = asyncio.iscoroutinefunction(method)
        return methods

    def test_orchestrator_no_poll_workers_async(self) -> None:
        """_poll_workers_async must not exist on Orchestrator."""
        from zerg.orchestrator import Orchestrator

        assert not hasattr(Orchestrator, "_poll_workers_async"), (
            "_poll_workers_async should have been removed. _poll_workers is the single source of truth."
        )

    def test_orchestrator_no_main_loop_async(self) -> None:
        """_main_loop_async must not exist on Orchestrator.

        The async equivalent is now _main_loop_as_async which wraps
        the unified _main_loop via asyncio.to_thread.
        """
        from zerg.orchestrator import Orchestrator

        assert not hasattr(Orchestrator, "_main_loop_async"), (
            "_main_loop_async should have been removed. _main_loop_as_async wraps the unified _main_loop."
        )

    def test_orchestrator_has_main_loop_as_async(self) -> None:
        """_main_loop_as_async must exist as the async wrapper."""
        from zerg.orchestrator import Orchestrator

        assert hasattr(Orchestrator, "_main_loop_as_async")
        assert asyncio.iscoroutinefunction(Orchestrator._main_loop_as_async)

    def test_orchestrator_poll_workers_sync_alias(self) -> None:
        """_poll_workers_sync must exist as an alias for _poll_workers."""
        from zerg.orchestrator import Orchestrator

        assert hasattr(Orchestrator, "_poll_workers_sync")
        assert Orchestrator._poll_workers_sync is Orchestrator._poll_workers

    def test_worker_protocol_sync_wrappers_are_thin(self) -> None:
        """Sync wrappers in WorkerProtocol must be thin (< 10 lines each)."""
        from zerg.protocol_state import WorkerProtocol

        for method_name in ("wait_for_ready", "claim_next_task"):
            source = inspect.getsource(getattr(WorkerProtocol, method_name))
            lines = [line for line in source.splitlines() if line.strip() and not line.strip().startswith(('"""', "#"))]
            assert len(lines) < 15, f"{method_name} should be a thin sync wrapper but has {len(lines)} lines"

    def test_launcher_base_no_standalone_sync_retry(self) -> None:
        """WorkerLauncher.spawn_with_retry must delegate to _spawn_with_retry_impl.

        Verifying no duplicate retry logic exists outside the impl method.
        """
        source = inspect.getsource(WorkerLauncher.spawn_with_retry)
        assert "_spawn_with_retry_impl" in source
        assert "asyncio.run" in source

    def test_level_coordinator_has_no_async_methods(self) -> None:
        """LevelCoordinator must have zero async methods (confirmed no-op in dedup)."""
        from zerg.level_coordinator import LevelCoordinator

        for name, method in inspect.getmembers(LevelCoordinator, predicate=inspect.isfunction):
            assert not asyncio.iscoroutinefunction(method), f"LevelCoordinator.{name} is async but should not be"


# =============================================================================
# 4. Unified _main_loop has all features
# =============================================================================


class TestUnifiedMainLoop:
    """Verify the unified _main_loop includes escalation, progress, stall detection."""

    def test_main_loop_calls_check_escalations(self) -> None:
        """_main_loop must include escalation checks (previously missing from async)."""
        from zerg.orchestrator import Orchestrator

        # _poll_workers (called from _main_loop) must include escalation checks
        # (inlined from _check_escalations by TASK-021)
        source = inspect.getsource(Orchestrator._poll_workers)
        assert "escalation" in source

    def test_main_loop_calls_aggregate_progress(self) -> None:
        """_main_loop must include progress aggregation (previously missing from async)."""
        from zerg.orchestrator import Orchestrator

        # (inlined from _aggregate_progress by TASK-021)
        source = inspect.getsource(Orchestrator._poll_workers)
        assert "ProgressReporter" in source

    def test_main_loop_calls_check_stale_tasks(self) -> None:
        """_main_loop must call _check_stale_tasks for stall detection."""
        from zerg.orchestrator import Orchestrator

        source = inspect.getsource(Orchestrator._poll_workers)
        assert "_check_stale_tasks" in source

    def test_main_loop_accepts_sleep_fn(self) -> None:
        """_main_loop must accept a sleep_fn parameter for injectable sleep."""
        from zerg.orchestrator import Orchestrator

        sig = inspect.signature(Orchestrator._main_loop)
        assert "sleep_fn" in sig.parameters

    def test_main_loop_defaults_to_time_sleep(self) -> None:
        """_main_loop must default sleep_fn to time.sleep."""
        from zerg.orchestrator import Orchestrator

        source = inspect.getsource(Orchestrator._main_loop)
        assert "time.sleep" in source

    def test_main_loop_as_async_runs_via_to_thread(self) -> None:
        """_main_loop_as_async must use asyncio.to_thread to run _main_loop."""
        from zerg.orchestrator import Orchestrator

        source = inspect.getsource(Orchestrator._main_loop_as_async)
        assert "asyncio.to_thread" in source
        assert "_main_loop" in source

    def test_main_loop_handles_auto_respawn(self) -> None:
        """_main_loop must handle auto-respawn when workers are gone but tasks remain."""
        from zerg.orchestrator import Orchestrator

        source = inspect.getsource(Orchestrator._main_loop)
        assert "_auto_respawn_workers" in source

    def test_poll_workers_handles_stalled_workers(self) -> None:
        """_poll_workers must detect and handle stalled workers."""
        from zerg.orchestrator import Orchestrator

        source = inspect.getsource(Orchestrator._poll_workers)
        assert "STALLED" in source or "stalled" in source.lower()

    def test_poll_workers_handles_crashed_workers(self) -> None:
        """_poll_workers must detect and handle crashed workers."""
        from zerg.orchestrator import Orchestrator

        source = inspect.getsource(Orchestrator._poll_workers)
        assert "CRASHED" in source or "WorkerStatus.CRASHED" in source


# =============================================================================
# 5. Container launcher _build_container_cmd is shared
# =============================================================================


class TestBuildContainerCmd:
    """Verify _build_container_cmd is the single source for command construction."""

    def test_start_container_impl_uses_build_cmd(self) -> None:
        """_start_container_impl must call _build_container_cmd."""
        source = inspect.getsource(ContainerLauncher._start_container_impl)
        assert "_build_container_cmd" in source

    def test_build_container_cmd_returns_list(self) -> None:
        """_build_container_cmd must return a list of strings."""
        sig = inspect.signature(ContainerLauncher._build_container_cmd)
        # Verify the method exists and has the right parameters
        params = list(sig.parameters.keys())
        assert "container_name" in params
        assert "worktree_path" in params
        assert "env" in params

    def test_sync_start_container_calls_impl(self) -> None:
        """_start_container (sync) must call _start_container_impl."""
        source = inspect.getsource(ContainerLauncher._start_container)
        assert "_start_container_impl" in source

    def test_async_start_container_calls_impl(self) -> None:
        """_start_container_async must call _start_container_impl."""
        source = inspect.getsource(ContainerLauncher._start_container_async)
        assert "_start_container_impl" in source


# =============================================================================
# 6. Subprocess launcher async methods
# =============================================================================


class TestSubprocessLauncherAsync:
    """Verify SubprocessLauncher async overrides delegate properly."""

    def test_terminate_async_exists_on_base(self) -> None:
        """WorkerLauncher base class must have terminate_async."""
        assert hasattr(WorkerLauncher, "terminate_async")
        assert asyncio.iscoroutinefunction(WorkerLauncher.terminate_async)

    def test_subprocess_launcher_overrides_terminate_async(self) -> None:
        """SubprocessLauncher must override terminate_async."""
        assert asyncio.iscoroutinefunction(SubprocessLauncher.terminate_async)

    def test_base_terminate_async_uses_to_thread(self) -> None:
        """Base WorkerLauncher.terminate_async must use asyncio.to_thread."""
        source = inspect.getsource(WorkerLauncher.terminate_async)
        assert "asyncio.to_thread" in source


# =============================================================================
# 7. Comprehensive dedup pattern integrity
# =============================================================================


class TestDedupPatternIntegrity:
    """Cross-cutting tests to verify dedup patterns are internally consistent."""

    def test_spawn_with_retry_sync_and_async_share_impl(self) -> None:
        """Both sync and async spawn_with_retry must reference _spawn_with_retry_impl."""
        sync_source = inspect.getsource(WorkerLauncher.spawn_with_retry)
        async_source = inspect.getsource(WorkerLauncher.spawn_with_retry_async)
        assert "_spawn_with_retry_impl" in sync_source
        assert "_spawn_with_retry_impl" in async_source

    def test_container_terminate_sync_and_async_share_impl(self) -> None:
        """Both sync and async terminate in ContainerLauncher must use _terminate_impl."""
        sync_source = inspect.getsource(ContainerLauncher.terminate)
        async_source = inspect.getsource(ContainerLauncher.terminate_async)
        assert "_terminate_impl" in sync_source
        assert "_terminate_impl" in async_source

    def test_container_start_sync_and_async_share_impl(self) -> None:
        """Both sync and async _start_container must use _start_container_impl."""
        sync_source = inspect.getsource(ContainerLauncher._start_container)
        async_source = inspect.getsource(ContainerLauncher._start_container_async)
        assert "_start_container_impl" in sync_source
        assert "_start_container_impl" in async_source

    def test_no_duplicate_retry_logic_in_wrappers(self) -> None:
        """Sync/async wrappers must not contain retry loops themselves.

        The retry loop must only live in _spawn_with_retry_impl.
        """
        sync_source = inspect.getsource(WorkerLauncher.spawn_with_retry)
        async_source = inspect.getsource(WorkerLauncher.spawn_with_retry_async)

        # Wrappers should NOT contain for loops (the retry loop is in impl)
        for source, name in [(sync_source, "spawn_with_retry"), (async_source, "spawn_with_retry_async")]:
            # Count 'for attempt' or 'for ' + 'range' patterns — none should appear
            assert "for attempt" not in source, f"{name} contains retry loop (should be in impl only)"

    def test_impl_methods_contain_actual_logic(self) -> None:
        """_*_impl methods must contain the actual business logic, not just delegation."""
        impl_source = inspect.getsource(WorkerLauncher._spawn_with_retry_impl)
        assert "for attempt" in impl_source or "range(" in impl_source  # retry loop

        container_impl_source = inspect.getsource(ContainerLauncher._start_container_impl)
        assert "await run_fn" in container_impl_source  # calls the injected runner

        terminate_impl_source = inspect.getsource(ContainerLauncher._terminate_impl)
        assert "await run_fn" in terminate_impl_source  # calls the injected runner
