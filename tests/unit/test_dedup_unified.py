"""Unit tests for sync/async deduplication in the ZERG codebase.

Verifies that the dedup refactoring (Level 1-2 of core-refactoring) is correct:

1. Callable injection patterns work in launcher.py
2. Sync wrappers correctly delegate to async implementations
3. No remaining duplicate method pairs exist (introspection-based)
4. Unified _main_loop has escalation, progress, stall detection
"""

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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

    def test_impl_signature_and_type(self) -> None:
        """_spawn_with_retry_impl must be async and accept spawn_fn/sleep_fn."""
        assert asyncio.iscoroutinefunction(WorkerLauncher._spawn_with_retry_impl)
        sig = inspect.signature(WorkerLauncher._spawn_with_retry_impl)
        param_names = list(sig.parameters.keys())
        assert "spawn_fn" in param_names
        assert "sleep_fn" in param_names

    @pytest.mark.parametrize("use_async", [False, True], ids=["sync", "async"])
    def test_wrapper_delegates_to_impl(self, use_async: bool) -> None:
        """Both sync and async spawn_with_retry must delegate to impl."""
        launcher = StubLauncher()
        wt = Path("/tmp/test-wt")
        kwargs = dict(worker_id=1, feature="test", worktree_path=wt, branch="main", max_attempts=1)

        if use_async:
            result = asyncio.run(launcher.spawn_with_retry_async(**kwargs))
        else:
            result = launcher.spawn_with_retry(**kwargs)

        assert result.success is True
        assert result.worker_id == 1

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
        assert len(sleep_calls) == 1

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


class TestContainerLauncherImpl:
    """Verify _start_container_impl and _terminate_impl in ContainerLauncher."""

    @pytest.mark.parametrize(
        "attr",
        ["_build_container_cmd", "_start_container_impl", "_terminate_impl"],
    )
    def test_impl_methods_exist(self, attr: str) -> None:
        """ContainerLauncher must have all impl methods."""
        assert hasattr(ContainerLauncher, attr)

    @pytest.mark.parametrize(
        "method,param",
        [("_start_container_impl", "run_fn"), ("_terminate_impl", "run_fn")],
    )
    def test_impl_is_async_with_injection(self, method: str, param: str) -> None:
        """Impl methods must be async and accept injected callables."""
        fn = getattr(ContainerLauncher, method)
        assert asyncio.iscoroutinefunction(fn)
        sig = inspect.signature(fn)
        assert param in sig.parameters

    @patch("zerg.launchers.container_launcher.Path.home")
    @patch("os.getuid", return_value=1000)
    @patch("os.getgid", return_value=1000)
    def test_sync_start_container_delegates(
        self, mock_gid: MagicMock, mock_uid: MagicMock, mock_home: MagicMock
    ) -> None:
        """_start_container (sync) must delegate to _start_container_impl."""
        mock_home.return_value = Path("/fake/home")
        launcher = ContainerLauncher(image_name="test-image")
        with patch.object(launcher, "_start_container_impl", new_callable=AsyncMock) as mock_impl:
            mock_impl.return_value = "abc123"
            result = launcher._start_container(
                container_name="test-container",
                worktree_path=Path("/fake/worktree"),
                env={"ZERG_WORKER_ID": "1"},
            )
            assert result == "abc123"
            mock_impl.assert_called_once()

    def test_terminate_sync_delegates(self) -> None:
        """terminate() (sync) must delegate to _terminate_impl."""
        launcher = ContainerLauncher(image_name="test-image")
        with patch.object(launcher, "_terminate_impl", new_callable=AsyncMock) as mock_impl:
            mock_impl.return_value = True
            from zerg.launcher_types import WorkerHandle

            launcher._container_ids[1] = "abc123"
            launcher._workers[1] = WorkerHandle(worker_id=1, status=WorkerStatus.RUNNING)
            result = launcher.terminate(1)
            assert result is True
            mock_impl.assert_called_once()


# =============================================================================
# 2. No remaining duplicate method pairs (introspection)
# =============================================================================


class TestNoDuplicateMethodPairs:
    """Verify no sync/async duplicate method pairs remain outside the dedup pattern."""

    @pytest.mark.parametrize(
        "attr,should_exist",
        [
            ("_poll_workers_async", False),
            ("_main_loop_async", False),
            ("_main_loop_as_async", True),
            ("_poll_workers_sync", True),
        ],
    )
    def test_orchestrator_method_presence(self, attr: str, should_exist: bool) -> None:
        """Orchestrator must have correct methods after dedup refactoring."""
        from zerg.orchestrator import Orchestrator

        assert hasattr(Orchestrator, attr) == should_exist

    def test_worker_protocol_sync_wrappers_are_thin(self) -> None:
        """Sync wrappers in WorkerProtocol must be thin (< 15 lines each)."""
        from zerg.protocol_state import WorkerProtocol

        for method_name in ("wait_for_ready", "claim_next_task"):
            source = inspect.getsource(getattr(WorkerProtocol, method_name))
            lines = [line for line in source.splitlines() if line.strip() and not line.strip().startswith(('"""', "#"))]
            assert len(lines) < 15, f"{method_name} should be a thin sync wrapper but has {len(lines)} lines"

    def test_level_coordinator_has_no_async_methods(self) -> None:
        """LevelCoordinator must have zero async methods."""
        from zerg.level_coordinator import LevelCoordinator

        for name, method in inspect.getmembers(LevelCoordinator, predicate=inspect.isfunction):
            assert not asyncio.iscoroutinefunction(method), f"LevelCoordinator.{name} is async but should not be"


# =============================================================================
# 3. Unified _main_loop has all features
# =============================================================================


class TestUnifiedMainLoop:
    """Verify the unified _main_loop includes escalation, progress, stall detection."""

    @pytest.mark.parametrize(
        "keyword",
        ["escalation", "ProgressReporter", "_check_stale_tasks", "STALLED", "CRASHED"],
        ids=["escalation", "progress", "stale-tasks", "stalled", "crashed"],
    )
    def test_poll_workers_contains_feature(self, keyword: str) -> None:
        """_poll_workers must include all required features."""
        from zerg.orchestrator import Orchestrator

        source = inspect.getsource(Orchestrator._poll_workers)
        assert keyword in source or keyword.lower() in source.lower()

    def test_main_loop_injectable_sleep(self) -> None:
        """_main_loop must accept sleep_fn and default to time.sleep."""
        from zerg.orchestrator import Orchestrator

        sig = inspect.signature(Orchestrator._main_loop)
        assert "sleep_fn" in sig.parameters
        source = inspect.getsource(Orchestrator._main_loop)
        assert "time.sleep" in source

    def test_main_loop_as_async_uses_to_thread(self) -> None:
        """_main_loop_as_async must use asyncio.to_thread."""
        from zerg.orchestrator import Orchestrator

        source = inspect.getsource(Orchestrator._main_loop_as_async)
        assert "asyncio.to_thread" in source


# =============================================================================
# 4. Dedup pattern integrity
# =============================================================================


class TestDedupPatternIntegrity:
    """Cross-cutting tests to verify dedup patterns are internally consistent."""

    @pytest.mark.parametrize(
        "cls,sync_method,async_method,impl_name",
        [
            (WorkerLauncher, "spawn_with_retry", "spawn_with_retry_async", "_spawn_with_retry_impl"),
            (ContainerLauncher, "terminate", "terminate_async", "_terminate_impl"),
            (ContainerLauncher, "_start_container", "_start_container_async", "_start_container_impl"),
        ],
    )
    def test_sync_and_async_share_impl(self, cls: type, sync_method: str, async_method: str, impl_name: str) -> None:
        """Both sync and async wrappers must reference the shared impl."""
        sync_source = inspect.getsource(getattr(cls, sync_method))
        async_source = inspect.getsource(getattr(cls, async_method))
        assert impl_name in sync_source
        assert impl_name in async_source

    def test_no_duplicate_retry_logic_in_wrappers(self) -> None:
        """Sync/async wrappers must not contain retry loops themselves."""
        for method_name in ("spawn_with_retry", "spawn_with_retry_async"):
            source = inspect.getsource(getattr(WorkerLauncher, method_name))
            assert "for attempt" not in source, f"{method_name} contains retry loop (should be in impl only)"

    def test_subprocess_launcher_async_terminate(self) -> None:
        """WorkerLauncher base and SubprocessLauncher must have terminate_async."""
        assert asyncio.iscoroutinefunction(WorkerLauncher.terminate_async)
        assert asyncio.iscoroutinefunction(SubprocessLauncher.terminate_async)
        source = inspect.getsource(WorkerLauncher.terminate_async)
        assert "asyncio.to_thread" in source
