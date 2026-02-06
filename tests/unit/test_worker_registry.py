"""Tests for ZERG WorkerRegistry module."""

import threading
from collections.abc import ItemsView, KeysView

import pytest

from zerg.constants import WorkerStatus
from zerg.types import WorkerState
from zerg.worker_registry import WorkerRegistry


def _make_worker(
    worker_id: int,
    status: WorkerStatus = WorkerStatus.READY,
    current_task: str | None = None,
) -> WorkerState:
    """Helper to create a WorkerState with minimal boilerplate."""
    return WorkerState(worker_id=worker_id, status=status, current_task=current_task)


class TestRegisterUnregister:
    """Tests for register/unregister lifecycle."""

    def test_register_adds_worker(self):
        """Registering a worker makes it retrievable."""
        registry = WorkerRegistry()
        worker = _make_worker(1)
        registry.register(1, worker)

        assert registry.get(1) is worker
        assert len(registry) == 1

    def test_unregister_removes_worker(self):
        """Unregistering a worker removes it from the registry."""
        registry = WorkerRegistry()
        worker = _make_worker(1)
        registry.register(1, worker)
        registry.unregister(1)

        assert registry.get(1) is None
        assert len(registry) == 0

    def test_unregister_nonexistent_is_noop(self):
        """Unregistering a worker that does not exist does not raise."""
        registry = WorkerRegistry()
        registry.unregister(999)  # should not raise
        assert len(registry) == 0

    def test_register_overwrites_existing(self):
        """Registering with the same ID replaces the previous worker."""
        registry = WorkerRegistry()
        w1 = _make_worker(1, status=WorkerStatus.READY)
        w2 = _make_worker(1, status=WorkerStatus.RUNNING)
        registry.register(1, w1)
        registry.register(1, w2)

        assert registry.get(1) is w2
        assert len(registry) == 1

    def test_register_multiple_workers(self):
        """Multiple workers can be registered independently."""
        registry = WorkerRegistry()
        for wid in range(5):
            registry.register(wid, _make_worker(wid))

        assert len(registry) == 5
        for wid in range(5):
            assert registry.get(wid) is not None


class TestGetExistingMissing:
    """Tests for get() returning WorkerState or None."""

    def test_get_existing_returns_worker(self):
        """get() returns the WorkerState for a registered ID."""
        registry = WorkerRegistry()
        worker = _make_worker(42)
        registry.register(42, worker)

        result = registry.get(42)
        assert result is worker
        assert result.worker_id == 42

    def test_get_missing_returns_none(self):
        """get() returns None for an unregistered ID."""
        registry = WorkerRegistry()
        assert registry.get(999) is None

    def test_get_after_unregister_returns_none(self):
        """get() returns None after the worker is unregistered."""
        registry = WorkerRegistry()
        registry.register(1, _make_worker(1))
        registry.unregister(1)
        assert registry.get(1) is None


class TestUpdateStatus:
    """Tests for update_status()."""

    def test_update_existing_worker_status(self):
        """update_status changes the status of an existing worker."""
        registry = WorkerRegistry()
        worker = _make_worker(1, status=WorkerStatus.READY)
        registry.register(1, worker)

        registry.update_status(1, WorkerStatus.RUNNING)
        assert registry.get(1).status == WorkerStatus.RUNNING

    def test_update_missing_worker_is_noop(self):
        """update_status on a nonexistent worker does not raise."""
        registry = WorkerRegistry()
        registry.update_status(999, WorkerStatus.CRASHED)  # should not raise

    def test_update_status_multiple_transitions(self):
        """Status can be updated through multiple transitions."""
        registry = WorkerRegistry()
        worker = _make_worker(1, status=WorkerStatus.INITIALIZING)
        registry.register(1, worker)

        transitions = [
            WorkerStatus.READY,
            WorkerStatus.RUNNING,
            WorkerStatus.IDLE,
            WorkerStatus.STOPPING,
            WorkerStatus.STOPPED,
        ]
        for status in transitions:
            registry.update_status(1, status)
            assert registry.get(1).status == status


class TestAll:
    """Tests for all() returning a copy of all workers."""

    def test_all_returns_copy(self):
        """all() returns a shallow copy, not the internal dict."""
        registry = WorkerRegistry()
        registry.register(1, _make_worker(1))
        registry.register(2, _make_worker(2))

        snapshot = registry.all()
        assert len(snapshot) == 2
        assert 1 in snapshot
        assert 2 in snapshot

        # Mutating the copy should not affect the registry
        snapshot[99] = _make_worker(99)
        assert 99 not in registry

    def test_all_empty_registry(self):
        """all() returns an empty dict for an empty registry."""
        registry = WorkerRegistry()
        assert registry.all() == {}

    def test_all_returns_same_worker_objects(self):
        """all() returns a shallow copy -- worker objects are identical references."""
        registry = WorkerRegistry()
        worker = _make_worker(1)
        registry.register(1, worker)

        snapshot = registry.all()
        assert snapshot[1] is worker


class TestActive:
    """Tests for active() returning non-terminal workers."""

    def test_active_excludes_stopped(self):
        """active() excludes workers with STOPPED status."""
        registry = WorkerRegistry()
        registry.register(1, _make_worker(1, status=WorkerStatus.RUNNING))
        registry.register(2, _make_worker(2, status=WorkerStatus.STOPPED))

        active = registry.active()
        assert 1 in active
        assert 2 not in active

    def test_active_excludes_crashed(self):
        """active() excludes workers with CRASHED status."""
        registry = WorkerRegistry()
        registry.register(1, _make_worker(1, status=WorkerStatus.READY))
        registry.register(2, _make_worker(2, status=WorkerStatus.CRASHED))

        active = registry.active()
        assert 1 in active
        assert 2 not in active

    def test_active_includes_all_non_terminal(self):
        """active() includes workers in any non-terminal status."""
        non_terminal = [
            WorkerStatus.INITIALIZING,
            WorkerStatus.READY,
            WorkerStatus.RUNNING,
            WorkerStatus.IDLE,
            WorkerStatus.CHECKPOINTING,
            WorkerStatus.STOPPING,
            WorkerStatus.BLOCKED,
            WorkerStatus.STALLED,
        ]
        registry = WorkerRegistry()
        for i, status in enumerate(non_terminal):
            registry.register(i, _make_worker(i, status=status))

        active = registry.active()
        assert len(active) == len(non_terminal)

    def test_active_empty_when_all_terminal(self):
        """active() returns empty dict when all workers are terminal."""
        registry = WorkerRegistry()
        registry.register(1, _make_worker(1, status=WorkerStatus.STOPPED))
        registry.register(2, _make_worker(2, status=WorkerStatus.CRASHED))

        assert registry.active() == {}

    def test_active_empty_registry(self):
        """active() returns empty dict on empty registry."""
        registry = WorkerRegistry()
        assert registry.active() == {}


class TestByLevel:
    """Tests for by_level() -- currently returns all as fallback."""

    def test_by_level_returns_all_workers(self):
        """by_level() currently returns all workers as a fallback."""
        registry = WorkerRegistry()
        registry.register(1, _make_worker(1))
        registry.register(2, _make_worker(2))
        registry.register(3, _make_worker(3))

        result = registry.by_level(1)
        assert len(result) == 3
        assert 1 in result
        assert 2 in result
        assert 3 in result

    def test_by_level_returns_copy(self):
        """by_level() returns a copy, not the internal dict."""
        registry = WorkerRegistry()
        registry.register(1, _make_worker(1))

        result = registry.by_level(1)
        result[99] = _make_worker(99)
        assert 99 not in registry

    def test_by_level_empty_registry(self):
        """by_level() returns empty dict on empty registry."""
        registry = WorkerRegistry()
        assert registry.by_level(1) == {}

    def test_by_level_different_levels_return_same(self):
        """by_level() returns same result regardless of level argument (fallback behavior)."""
        registry = WorkerRegistry()
        registry.register(1, _make_worker(1))
        registry.register(2, _make_worker(2))

        assert registry.by_level(1) == registry.by_level(2)
        assert registry.by_level(1) == registry.by_level(99)


class TestThreadSafety:
    """Concurrent register/unregister should not corrupt state."""

    def test_concurrent_register_unregister(self):
        """Multiple threads registering/unregistering should not corrupt state."""
        registry = WorkerRegistry()
        errors: list[Exception] = []
        num_threads = 10
        ops_per_thread = 100

        def register_and_unregister(thread_id: int) -> None:
            try:
                for i in range(ops_per_thread):
                    wid = thread_id * 1000 + i
                    worker = _make_worker(wid)
                    registry.register(wid, worker)
                    # Verify it is accessible
                    assert registry.get(wid) is not None
                    registry.unregister(wid)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=register_and_unregister, args=(t,)) for t in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert errors == [], f"Thread safety errors: {errors}"
        # After all threads complete, registry should be empty
        assert len(registry) == 0

    def test_concurrent_reads_and_writes(self):
        """Mixed reads and writes from multiple threads should not raise."""
        registry = WorkerRegistry()
        errors: list[Exception] = []
        barrier = threading.Barrier(6)

        def writer(start_id: int) -> None:
            try:
                barrier.wait(timeout=5)
                for i in range(50):
                    wid = start_id + i
                    registry.register(wid, _make_worker(wid))
            except Exception as exc:
                errors.append(exc)

        def reader() -> None:
            try:
                barrier.wait(timeout=5)
                for _ in range(50):
                    _ = registry.all()
                    _ = registry.active()
                    _ = len(registry)
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=writer, args=(0,)),
            threading.Thread(target=writer, args=(1000,)),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert errors == [], f"Concurrent read/write errors: {errors}"

    def test_concurrent_update_status(self):
        """Concurrent status updates should not corrupt worker state."""
        registry = WorkerRegistry()
        worker = _make_worker(1, status=WorkerStatus.READY)
        registry.register(1, worker)
        errors: list[Exception] = []

        statuses = [
            WorkerStatus.RUNNING,
            WorkerStatus.IDLE,
            WorkerStatus.READY,
            WorkerStatus.CHECKPOINTING,
        ]

        def update_loop(status: WorkerStatus) -> None:
            try:
                for _ in range(100):
                    registry.update_status(1, status)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=update_loop, args=(s,)) for s in statuses]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert errors == [], f"Concurrent update errors: {errors}"
        # Final status should be one of the valid statuses
        final = registry.get(1).status
        assert final in statuses


class TestLenContains:
    """Tests for __len__ and __contains__."""

    def test_len_empty(self):
        """len() is 0 for empty registry."""
        registry = WorkerRegistry()
        assert len(registry) == 0

    def test_len_after_register(self):
        """len() reflects number of registered workers."""
        registry = WorkerRegistry()
        registry.register(1, _make_worker(1))
        registry.register(2, _make_worker(2))
        assert len(registry) == 2

    def test_len_after_unregister(self):
        """len() decreases after unregistering a worker."""
        registry = WorkerRegistry()
        registry.register(1, _make_worker(1))
        registry.register(2, _make_worker(2))
        registry.unregister(1)
        assert len(registry) == 1

    def test_contains_registered(self):
        """'in' operator returns True for registered worker IDs."""
        registry = WorkerRegistry()
        registry.register(5, _make_worker(5))
        assert 5 in registry

    def test_not_contains_unregistered(self):
        """'in' operator returns False for unregistered worker IDs."""
        registry = WorkerRegistry()
        assert 42 not in registry

    def test_contains_after_unregister(self):
        """'in' operator returns False after worker is unregistered."""
        registry = WorkerRegistry()
        registry.register(1, _make_worker(1))
        registry.unregister(1)
        assert 1 not in registry


class TestGetItem:
    """Tests for __getitem__ dict-like access."""

    def test_getitem_existing(self):
        """registry[wid] returns the WorkerState for a registered ID."""
        registry = WorkerRegistry()
        worker = _make_worker(7)
        registry.register(7, worker)

        assert registry[7] is worker

    def test_getitem_missing_raises_keyerror(self):
        """registry[wid] raises KeyError for a missing ID."""
        registry = WorkerRegistry()
        with pytest.raises(KeyError):
            _ = registry[999]

    def test_getitem_after_unregister_raises_keyerror(self):
        """registry[wid] raises KeyError after worker is unregistered."""
        registry = WorkerRegistry()
        registry.register(1, _make_worker(1))
        registry.unregister(1)
        with pytest.raises(KeyError):
            _ = registry[1]


class TestKeysItems:
    """Tests for keys() and items() snapshot behavior."""

    def test_keys_returns_keysview(self):
        """keys() returns a KeysView of worker IDs."""
        registry = WorkerRegistry()
        registry.register(1, _make_worker(1))
        registry.register(2, _make_worker(2))

        k = registry.keys()
        assert isinstance(k, KeysView)
        assert set(k) == {1, 2}

    def test_items_returns_itemsview(self):
        """items() returns an ItemsView of (id, WorkerState) pairs."""
        registry = WorkerRegistry()
        w1 = _make_worker(1)
        w2 = _make_worker(2)
        registry.register(1, w1)
        registry.register(2, w2)

        it = registry.items()
        assert isinstance(it, ItemsView)
        items_dict = dict(it)
        assert items_dict[1] is w1
        assert items_dict[2] is w2

    def test_keys_is_snapshot(self):
        """keys() returns a snapshot; subsequent mutations don't affect it."""
        registry = WorkerRegistry()
        registry.register(1, _make_worker(1))

        k = registry.keys()
        registry.register(2, _make_worker(2))

        # The snapshot should still show only worker 1
        assert set(k) == {1}

    def test_items_is_snapshot(self):
        """items() returns a snapshot; subsequent mutations don't affect it."""
        registry = WorkerRegistry()
        registry.register(1, _make_worker(1))

        it = registry.items()
        registry.register(2, _make_worker(2))

        items_dict = dict(it)
        assert 2 not in items_dict

    def test_keys_empty(self):
        """keys() on empty registry returns empty KeysView."""
        registry = WorkerRegistry()
        k = registry.keys()
        assert len(list(k)) == 0

    def test_items_empty(self):
        """items() on empty registry returns empty ItemsView."""
        registry = WorkerRegistry()
        it = registry.items()
        assert len(list(it)) == 0


class TestIter:
    """Tests for __iter__ over worker IDs."""

    def test_iter_yields_worker_ids(self):
        """Iterating over registry yields registered worker IDs."""
        registry = WorkerRegistry()
        registry.register(10, _make_worker(10))
        registry.register(20, _make_worker(20))
        registry.register(30, _make_worker(30))

        ids = list(registry)
        assert set(ids) == {10, 20, 30}

    def test_iter_is_snapshot(self):
        """Iterator is a snapshot; mutations during iteration don't affect it."""
        registry = WorkerRegistry()
        registry.register(1, _make_worker(1))
        registry.register(2, _make_worker(2))

        it = iter(registry)
        registry.register(3, _make_worker(3))

        ids = list(it)
        assert 3 not in ids

    def test_iter_empty(self):
        """Iterating over empty registry yields no items."""
        registry = WorkerRegistry()
        assert list(registry) == []

    def test_iter_supports_for_loop(self):
        """Registry supports standard for-in loop."""
        registry = WorkerRegistry()
        registry.register(1, _make_worker(1))
        registry.register(2, _make_worker(2))

        collected = []
        for wid in registry:
            collected.append(wid)
        assert set(collected) == {1, 2}


class TestRepr:
    """Tests for __repr__."""

    def test_repr_empty(self):
        """repr shows 0 workers for empty registry."""
        registry = WorkerRegistry()
        assert repr(registry) == "<WorkerRegistry workers=0>"

    def test_repr_with_workers(self):
        """repr shows correct worker count."""
        registry = WorkerRegistry()
        registry.register(1, _make_worker(1))
        registry.register(2, _make_worker(2))
        assert repr(registry) == "<WorkerRegistry workers=2>"

    def test_repr_after_unregister(self):
        """repr updates after unregister."""
        registry = WorkerRegistry()
        registry.register(1, _make_worker(1))
        registry.unregister(1)
        assert repr(registry) == "<WorkerRegistry workers=0>"
