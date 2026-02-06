"""Tests for ZERG WorkerRegistry module."""

import threading

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

    def test_register_and_get(self):
        """Registering a worker makes it retrievable."""
        registry = WorkerRegistry()
        worker = _make_worker(1)
        registry.register(1, worker)
        assert registry.get(1) is worker
        assert len(registry) == 1

    def test_unregister_removes_worker(self):
        """Unregistering a worker removes it from the registry."""
        registry = WorkerRegistry()
        registry.register(1, _make_worker(1))
        registry.unregister(1)
        assert registry.get(1) is None
        assert len(registry) == 0

    def test_unregister_nonexistent_is_noop(self):
        """Unregistering a worker that does not exist does not raise."""
        registry = WorkerRegistry()
        registry.unregister(999)

    def test_register_overwrites_existing(self):
        """Registering with the same ID replaces the previous worker."""
        registry = WorkerRegistry()
        w1 = _make_worker(1, status=WorkerStatus.READY)
        w2 = _make_worker(1, status=WorkerStatus.RUNNING)
        registry.register(1, w1)
        registry.register(1, w2)
        assert registry.get(1) is w2
        assert len(registry) == 1


class TestUpdateStatus:
    """Tests for update_status()."""

    def test_update_existing_worker_status(self):
        """update_status changes the status of an existing worker."""
        registry = WorkerRegistry()
        registry.register(1, _make_worker(1, status=WorkerStatus.READY))
        registry.update_status(1, WorkerStatus.RUNNING)
        assert registry.get(1).status == WorkerStatus.RUNNING

    def test_update_missing_worker_is_noop(self):
        """update_status on a nonexistent worker does not raise."""
        registry = WorkerRegistry()
        registry.update_status(999, WorkerStatus.CRASHED)


class TestAllAndActive:
    """Tests for all() and active() methods."""

    def test_all_returns_copy(self):
        """all() returns a shallow copy, not the internal dict."""
        registry = WorkerRegistry()
        registry.register(1, _make_worker(1))
        snapshot = registry.all()
        snapshot[99] = _make_worker(99)
        assert 99 not in registry

    def test_active_excludes_terminal(self):
        """active() excludes STOPPED and CRASHED workers."""
        registry = WorkerRegistry()
        registry.register(1, _make_worker(1, status=WorkerStatus.RUNNING))
        registry.register(2, _make_worker(2, status=WorkerStatus.STOPPED))
        registry.register(3, _make_worker(3, status=WorkerStatus.CRASHED))
        active = registry.active()
        assert 1 in active
        assert 2 not in active
        assert 3 not in active


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
                    registry.register(wid, _make_worker(wid))
                    assert registry.get(wid) is not None
                    registry.unregister(wid)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=register_and_unregister, args=(t,)) for t in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert errors == []
        assert len(registry) == 0


class TestContainerProtocol:
    """Tests for __len__, __contains__, __getitem__, __iter__, __repr__."""

    def test_contains_and_len(self):
        """'in' operator and len() work correctly."""
        registry = WorkerRegistry()
        registry.register(5, _make_worker(5))
        assert 5 in registry
        assert 42 not in registry
        assert len(registry) == 1

    def test_getitem_existing_and_missing(self):
        """registry[wid] returns worker or raises KeyError."""
        registry = WorkerRegistry()
        worker = _make_worker(7)
        registry.register(7, worker)
        assert registry[7] is worker
        with pytest.raises(KeyError):
            _ = registry[999]

    def test_keys_items_iter(self):
        """keys(), items(), and iter yield correct snapshots."""
        registry = WorkerRegistry()
        w1 = _make_worker(1)
        w2 = _make_worker(2)
        registry.register(1, w1)
        registry.register(2, w2)

        assert set(registry.keys()) == {1, 2}
        assert dict(registry.items())[1] is w1
        assert set(registry) == {1, 2}

    def test_repr(self):
        """repr shows correct worker count."""
        registry = WorkerRegistry()
        assert repr(registry) == "<WorkerRegistry workers=0>"
        registry.register(1, _make_worker(1))
        assert repr(registry) == "<WorkerRegistry workers=1>"
