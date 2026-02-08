"""Unit tests for zerg/launchers/base.py — WorkerLauncher ABC.

Covers: init defaults, get_handle, get_all_workers, terminate_all,
get_status_summary, sync_state, terminate_async, wait_all_async,
and abstract method interface via concrete stub.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

from zerg.constants import WorkerStatus
from zerg.launcher_types import LauncherConfig, SpawnResult, WorkerHandle
from zerg.launchers.base import WorkerLauncher

# ---------------------------------------------------------------------------
# Concrete stub for testing the ABC
# ---------------------------------------------------------------------------


class StubLauncher(WorkerLauncher):
    """Minimal concrete implementation for testing base class behavior."""

    def __init__(self, config: LauncherConfig | None = None) -> None:
        super().__init__(config)
        # Configurable return values per worker_id
        self.spawn_results: dict[int, SpawnResult] = {}
        # Sequence of results for retry testing (pops from front)
        self.spawn_result_sequence: list[SpawnResult] = []
        self.monitor_results: dict[int, WorkerStatus] = {}
        self.terminate_results: dict[int, bool] = {}
        self.output_results: dict[int, str] = {}
        # Track calls for assertions
        self.spawn_calls: list[tuple] = []
        self.monitor_calls: list[int] = []
        self.terminate_calls: list[tuple] = []
        self.get_output_calls: list[tuple] = []

    def spawn(
        self,
        worker_id: int,
        feature: str,
        worktree_path: Path,
        branch: str,
        env: dict[str, str] | None = None,
    ) -> SpawnResult:
        self.spawn_calls.append((worker_id, feature, worktree_path, branch, env))
        # Use sequence if available, otherwise use dict/default
        if self.spawn_result_sequence:
            result = self.spawn_result_sequence.pop(0)
        else:
            result = self.spawn_results.get(
                worker_id,
                SpawnResult(success=True, worker_id=worker_id),
            )
        if result.success:
            handle = WorkerHandle(worker_id=worker_id, pid=1000 + worker_id)
            self._workers[worker_id] = handle
            result.handle = handle
        return result

    def monitor(self, worker_id: int) -> WorkerStatus:
        self.monitor_calls.append(worker_id)
        return self.monitor_results.get(worker_id, WorkerStatus.RUNNING)

    def terminate(self, worker_id: int, force: bool = False) -> bool:
        self.terminate_calls.append((worker_id, force))
        result = self.terminate_results.get(worker_id, True)
        if result and worker_id in self._workers:
            del self._workers[worker_id]
        return result

    def get_output(self, worker_id: int, tail: int = 100) -> str:
        self.get_output_calls.append((worker_id, tail))
        return self.output_results.get(worker_id, "")


# ---------------------------------------------------------------------------
# Tests: Initialization
# ---------------------------------------------------------------------------


class TestWorkerLauncherInit:
    """Tests for __init__ and default config."""

    def test_default_config_created_when_none(self) -> None:
        launcher = StubLauncher(config=None)
        assert isinstance(launcher.config, LauncherConfig)
        assert launcher._workers == {}

    def test_custom_config_preserved(self) -> None:
        cfg = LauncherConfig(timeout_seconds=999)
        launcher = StubLauncher(config=cfg)
        assert launcher.config is cfg
        assert launcher.config.timeout_seconds == 999


# ---------------------------------------------------------------------------
# Tests: Abstract methods exercise (lines 61, 73, 86, 99)
# ---------------------------------------------------------------------------


class TestAbstractMethods:
    """Ensure abstract methods are callable on concrete subclass."""

    def test_spawn_returns_result(self, tmp_path: Path) -> None:
        launcher = StubLauncher()
        result = launcher.spawn(1, "feat", tmp_path, "branch-1")
        assert result.success is True
        assert result.worker_id == 1
        assert launcher.spawn_calls == [(1, "feat", tmp_path, "branch-1", None)]

    def test_monitor_returns_status(self) -> None:
        launcher = StubLauncher()
        launcher.monitor_results[5] = WorkerStatus.STOPPED
        assert launcher.monitor(5) == WorkerStatus.STOPPED

    def test_terminate_returns_bool(self) -> None:
        launcher = StubLauncher()
        launcher.terminate_results[3] = False
        assert launcher.terminate(3, force=True) is False
        assert launcher.terminate_calls == [(3, True)]

    def test_get_output_returns_string(self) -> None:
        launcher = StubLauncher()
        launcher.output_results[2] = "hello world"
        assert launcher.get_output(2, tail=50) == "hello world"
        assert launcher.get_output_calls == [(2, 50)]


# ---------------------------------------------------------------------------
# Tests: get_handle / get_all_workers
# ---------------------------------------------------------------------------


class TestWorkerAccessors:
    """Tests for get_handle and get_all_workers."""

    def test_get_handle_returns_none_for_unknown(self) -> None:
        launcher = StubLauncher()
        assert launcher.get_handle(999) is None

    def test_get_handle_returns_handle_after_spawn(self, tmp_path: Path) -> None:
        launcher = StubLauncher()
        launcher.spawn(1, "feat", tmp_path, "b")
        handle = launcher.get_handle(1)
        assert handle is not None
        assert handle.worker_id == 1
        assert handle.pid == 1001

    def test_get_all_workers_returns_copy(self, tmp_path: Path) -> None:
        launcher = StubLauncher()
        launcher.spawn(1, "f", tmp_path, "b")
        launcher.spawn(2, "f", tmp_path, "b")
        workers = launcher.get_all_workers()
        assert len(workers) == 2
        assert 1 in workers and 2 in workers
        # Verify it is a copy, not the same dict
        workers[99] = MagicMock()
        assert 99 not in launcher._workers


# ---------------------------------------------------------------------------
# Tests: terminate_all
# ---------------------------------------------------------------------------


class TestTerminateAll:
    """Tests for terminate_all."""

    def test_terminate_all_empty(self) -> None:
        launcher = StubLauncher()
        assert launcher.terminate_all() == {}

    def test_terminate_all_succeeds(self, tmp_path: Path) -> None:
        launcher = StubLauncher()
        launcher.spawn(1, "f", tmp_path, "b")
        launcher.spawn(2, "f", tmp_path, "b")
        results = launcher.terminate_all(force=True)
        assert results == {1: True, 2: True}
        assert launcher._workers == {}

    def test_terminate_all_partial_failure(self, tmp_path: Path) -> None:
        launcher = StubLauncher()
        launcher.spawn(1, "f", tmp_path, "b")
        launcher.spawn(2, "f", tmp_path, "b")
        launcher.terminate_results[2] = False
        results = launcher.terminate_all()
        assert results[1] is True
        assert results[2] is False


# ---------------------------------------------------------------------------
# Tests: get_status_summary
# ---------------------------------------------------------------------------


class TestGetStatusSummary:
    """Tests for get_status_summary."""

    def test_empty_summary(self) -> None:
        launcher = StubLauncher()
        summary = launcher.get_status_summary()
        assert summary == {"total": 0, "by_status": {}, "alive": 0}

    def test_summary_with_mixed_statuses(self, tmp_path: Path) -> None:
        launcher = StubLauncher()
        launcher.spawn(1, "f", tmp_path, "b")
        launcher.spawn(2, "f", tmp_path, "b")
        # Manually set statuses for testing
        launcher._workers[1].status = WorkerStatus.RUNNING
        launcher._workers[2].status = WorkerStatus.STOPPED
        summary = launcher.get_status_summary()
        assert summary["total"] == 2
        assert summary["by_status"]["running"] == 1
        assert summary["by_status"]["stopped"] == 1
        # RUNNING is alive, STOPPED is not
        assert summary["alive"] == 1


# ---------------------------------------------------------------------------
# Tests: sync_state (lines 160-177)
# ---------------------------------------------------------------------------


class TestSyncState:
    """Tests for sync_state — reconcile internal state with actual status."""

    def test_sync_state_removes_stopped_workers(self, tmp_path: Path) -> None:
        launcher = StubLauncher()
        launcher.spawn(1, "f", tmp_path, "b")
        launcher.spawn(2, "f", tmp_path, "b")
        launcher.spawn(3, "f", tmp_path, "b")
        # Worker 1 stopped, worker 2 crashed, worker 3 still running
        launcher.monitor_results[1] = WorkerStatus.STOPPED
        launcher.monitor_results[2] = WorkerStatus.CRASHED
        launcher.monitor_results[3] = WorkerStatus.RUNNING

        results = launcher.sync_state()

        assert results == {
            1: WorkerStatus.STOPPED,
            2: WorkerStatus.CRASHED,
            3: WorkerStatus.RUNNING,
        }
        # Stopped and crashed workers removed from tracking
        assert 1 not in launcher._workers
        assert 2 not in launcher._workers
        # Running worker still tracked
        assert 3 in launcher._workers

    def test_sync_state_empty(self) -> None:
        launcher = StubLauncher()
        assert launcher.sync_state() == {}

    def test_sync_state_all_running(self, tmp_path: Path) -> None:
        launcher = StubLauncher()
        launcher.spawn(1, "f", tmp_path, "b")
        launcher.monitor_results[1] = WorkerStatus.RUNNING
        results = launcher.sync_state()
        assert results == {1: WorkerStatus.RUNNING}
        assert 1 in launcher._workers


# ---------------------------------------------------------------------------
# Tests: terminate_async (line 385)
# ---------------------------------------------------------------------------


class TestTerminateAsync:
    """Tests for terminate_async — default async wrapper around sync terminate."""

    def test_terminate_async_delegates_to_sync(self, tmp_path: Path) -> None:
        launcher = StubLauncher()
        launcher.spawn(1, "f", tmp_path, "b")
        result = asyncio.run(launcher.terminate_async(1, force=True))
        assert result is True
        assert (1, True) in launcher.terminate_calls

    def test_terminate_async_failure(self, tmp_path: Path) -> None:
        launcher = StubLauncher()
        launcher.spawn(1, "f", tmp_path, "b")
        launcher.terminate_results[1] = False
        result = asyncio.run(launcher.terminate_async(1))
        assert result is False


# ---------------------------------------------------------------------------
# Tests: wait_all_async (lines 399-413)
# ---------------------------------------------------------------------------


class TestWaitAllAsync:
    """Tests for wait_all_async — poll workers until terminal status."""

    def test_wait_all_returns_final_statuses(self, tmp_path: Path) -> None:
        launcher = StubLauncher()
        launcher.spawn(1, "f", tmp_path, "b")
        launcher.spawn(2, "f", tmp_path, "b")
        # Start as RUNNING, then flip to terminal on second call
        call_counts: dict[int, int] = {1: 0, 2: 0}

        def counting_monitor(wid: int) -> WorkerStatus:
            call_counts[wid] += 1
            if call_counts[wid] >= 2:
                return WorkerStatus.STOPPED
            return WorkerStatus.RUNNING

        launcher.monitor = counting_monitor  # type: ignore[assignment]

        results = asyncio.run(launcher.wait_all_async([1, 2]))
        assert results[1] == WorkerStatus.STOPPED
        assert results[2] == WorkerStatus.STOPPED

    def test_wait_all_immediate_terminal(self, tmp_path: Path) -> None:
        """Workers already in terminal state return immediately."""
        launcher = StubLauncher()
        launcher.spawn(1, "f", tmp_path, "b")
        launcher.monitor_results[1] = WorkerStatus.CRASHED
        results = asyncio.run(launcher.wait_all_async([1]))
        assert results[1] == WorkerStatus.CRASHED

    def test_wait_all_empty_list(self) -> None:
        launcher = StubLauncher()
        results = asyncio.run(launcher.wait_all_async([]))
        assert results == {}


# ---------------------------------------------------------------------------
# Tests: spawn_async (default async wrapper)
# ---------------------------------------------------------------------------


class TestSpawnAsync:
    """Tests for spawn_async — default async wrapper around sync spawn."""

    def test_spawn_async_delegates_to_sync(self, tmp_path: Path) -> None:
        launcher = StubLauncher()
        result = asyncio.run(launcher.spawn_async(1, "feat", tmp_path, "b"))
        assert result.success is True
        assert result.worker_id == 1
        assert len(launcher.spawn_calls) == 1


# ---------------------------------------------------------------------------
# Tests: _spawn_with_retry_impl (lines 214-246)
# ---------------------------------------------------------------------------


class TestSpawnWithRetryImpl:
    """Tests for the core retry logic via _spawn_with_retry_impl."""

    def test_success_on_first_attempt(self, tmp_path: Path) -> None:
        """First spawn succeeds, no retries needed."""
        launcher = StubLauncher()
        sleep_calls: list[float] = []

        async def fake_spawn(wid: int, feat: str, wt: Path, br: str, e: dict | None) -> SpawnResult:
            return SpawnResult(success=True, worker_id=wid)

        async def fake_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        result = asyncio.run(
            launcher._spawn_with_retry_impl(
                worker_id=1,
                feature="f",
                worktree_path=tmp_path,
                branch="b",
                env=None,
                max_attempts=3,
                backoff_strategy="exponential",
                backoff_base_seconds=1.0,
                backoff_max_seconds=10.0,
                spawn_fn=fake_spawn,
                sleep_fn=fake_sleep,
            )
        )
        assert result.success is True
        assert sleep_calls == []  # No retries, no sleeps

    def test_success_after_retry(self, tmp_path: Path) -> None:
        """First attempt fails, second succeeds."""
        call_count = 0
        sleep_calls: list[float] = []

        async def failing_then_success_spawn(wid: int, feat: str, wt: Path, br: str, e: dict | None) -> SpawnResult:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return SpawnResult(success=False, worker_id=wid, error="transient")
            return SpawnResult(success=True, worker_id=wid)

        async def fake_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        launcher = StubLauncher()
        result = asyncio.run(
            launcher._spawn_with_retry_impl(
                worker_id=1,
                feature="f",
                worktree_path=tmp_path,
                branch="b",
                env=None,
                max_attempts=3,
                backoff_strategy="fixed",
                backoff_base_seconds=1.0,
                backoff_max_seconds=10.0,
                spawn_fn=failing_then_success_spawn,
                sleep_fn=fake_sleep,
            )
        )
        assert result.success is True
        assert call_count == 2
        assert len(sleep_calls) == 1  # Slept once between attempt 1 and 2

    def test_all_attempts_exhausted(self, tmp_path: Path) -> None:
        """All attempts fail, returns error with last_error message."""
        sleep_calls: list[float] = []

        async def always_fail_spawn(wid: int, feat: str, wt: Path, br: str, e: dict | None) -> SpawnResult:
            return SpawnResult(success=False, worker_id=wid, error="boom")

        async def fake_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        launcher = StubLauncher()
        result = asyncio.run(
            launcher._spawn_with_retry_impl(
                worker_id=7,
                feature="f",
                worktree_path=tmp_path,
                branch="b",
                env=None,
                max_attempts=3,
                backoff_strategy="exponential",
                backoff_base_seconds=1.0,
                backoff_max_seconds=30.0,
                spawn_fn=always_fail_spawn,
                sleep_fn=fake_sleep,
            )
        )
        assert result.success is False
        assert result.worker_id == 7
        assert "All 3 spawn attempts failed" in result.error
        assert "boom" in result.error
        # Slept between attempt 1-2 and 2-3 (not after last)
        assert len(sleep_calls) == 2

    def test_unknown_error_fallback(self, tmp_path: Path) -> None:
        """When error is None, fallback to 'Unknown error'."""

        async def fail_no_error(wid: int, feat: str, wt: Path, br: str, e: dict | None) -> SpawnResult:
            return SpawnResult(success=False, worker_id=wid, error=None)

        async def fake_sleep(delay: float) -> None:
            pass

        launcher = StubLauncher()
        result = asyncio.run(
            launcher._spawn_with_retry_impl(
                worker_id=1,
                feature="f",
                worktree_path=tmp_path,
                branch="b",
                env=None,
                max_attempts=1,
                backoff_strategy="fixed",
                backoff_base_seconds=1.0,
                backoff_max_seconds=10.0,
                spawn_fn=fail_no_error,
                sleep_fn=fake_sleep,
            )
        )
        assert result.success is False
        assert "Unknown error" in result.error


# ---------------------------------------------------------------------------
# Tests: spawn_with_retry sync wrapper (lines 280-300)
# ---------------------------------------------------------------------------


class TestSpawnWithRetrySync:
    """Tests for spawn_with_retry — sync wrapper using asyncio.run."""

    @patch("zerg.launchers.base.time.sleep")
    def test_spawn_with_retry_succeeds_first_try(self, mock_sleep: MagicMock, tmp_path: Path) -> None:
        launcher = StubLauncher()
        result = launcher.spawn_with_retry(
            worker_id=1,
            feature="f",
            worktree_path=tmp_path,
            branch="b",
            max_attempts=2,
        )
        assert result.success is True
        assert result.worker_id == 1
        mock_sleep.assert_not_called()

    @patch("zerg.launchers.base.time.sleep")
    def test_spawn_with_retry_retries_on_failure(self, mock_sleep: MagicMock, tmp_path: Path) -> None:
        launcher = StubLauncher()
        # First call fails, second succeeds
        launcher.spawn_result_sequence = [
            SpawnResult(success=False, worker_id=1, error="fail"),
            SpawnResult(success=True, worker_id=1),
        ]
        result = launcher.spawn_with_retry(
            worker_id=1,
            feature="f",
            worktree_path=tmp_path,
            branch="b",
            max_attempts=3,
            backoff_strategy="fixed",
            backoff_base_seconds=0.01,
            backoff_max_seconds=1.0,
        )
        assert result.success is True
        assert len(launcher.spawn_calls) == 2
        assert mock_sleep.call_count == 1

    @patch("zerg.launchers.base.time.sleep")
    def test_spawn_with_retry_all_fail(self, mock_sleep: MagicMock, tmp_path: Path) -> None:
        launcher = StubLauncher()
        launcher.spawn_result_sequence = [
            SpawnResult(success=False, worker_id=1, error="err1"),
            SpawnResult(success=False, worker_id=1, error="err2"),
        ]
        result = launcher.spawn_with_retry(
            worker_id=1,
            feature="f",
            worktree_path=tmp_path,
            branch="b",
            max_attempts=2,
        )
        assert result.success is False
        assert "err2" in result.error


# ---------------------------------------------------------------------------
# Tests: spawn_with_retry_async (line 333)
# ---------------------------------------------------------------------------


class TestSpawnWithRetryAsync:
    """Tests for spawn_with_retry_async — async retry wrapper."""

    def test_async_retry_success(self, tmp_path: Path) -> None:
        launcher = StubLauncher()
        # Use spawn_result_sequence for the async path (spawn_async calls spawn)
        launcher.spawn_result_sequence = [
            SpawnResult(success=False, worker_id=1, error="transient"),
            SpawnResult(success=True, worker_id=1),
        ]

        async def run() -> SpawnResult:
            return await launcher.spawn_with_retry_async(
                worker_id=1,
                feature="f",
                worktree_path=tmp_path,
                branch="b",
                max_attempts=3,
                backoff_strategy="fixed",
                backoff_base_seconds=0.01,
                backoff_max_seconds=0.1,
            )

        result = asyncio.run(run())
        assert result.success is True
        assert len(launcher.spawn_calls) == 2

    def test_async_retry_all_fail(self, tmp_path: Path) -> None:
        launcher = StubLauncher()
        launcher.spawn_result_sequence = [
            SpawnResult(success=False, worker_id=1, error="nope"),
            SpawnResult(success=False, worker_id=1, error="still no"),
        ]

        async def run() -> SpawnResult:
            return await launcher.spawn_with_retry_async(
                worker_id=1,
                feature="f",
                worktree_path=tmp_path,
                branch="b",
                max_attempts=2,
                backoff_strategy="fixed",
                backoff_base_seconds=0.01,
                backoff_max_seconds=0.1,
            )

        result = asyncio.run(run())
        assert result.success is False
        assert "still no" in result.error
