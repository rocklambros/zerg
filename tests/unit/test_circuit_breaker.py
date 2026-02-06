"""Tests for ZERG CircuitBreaker module."""

import time

import pytest

from zerg.circuit_breaker import CircuitBreaker, CircuitState, WorkerCircuit


class TestWorkerCircuitAndState:
    """Tests for WorkerCircuit dataclass and CircuitState enum."""

    def test_default_state_is_closed(self):
        """New circuits start in CLOSED state with zero counters."""
        circuit = WorkerCircuit(worker_id=0)
        assert circuit.state == CircuitState.CLOSED
        assert circuit.failure_count == 0
        assert circuit.success_count == 0
        assert circuit.last_failure_time is None

    @pytest.mark.parametrize(
        "state, value",
        [
            (CircuitState.CLOSED, "closed"),
            (CircuitState.OPEN, "open"),
            (CircuitState.HALF_OPEN, "half_open"),
        ],
    )
    def test_state_values(self, state, value):
        """CircuitState enum has correct string values."""
        assert state.value == value


class TestCircuitBreakerInit:
    """Tests for CircuitBreaker initialization."""

    def test_defaults_and_get_circuit(self):
        """Default params, get_circuit creates new and returns existing."""
        cb = CircuitBreaker()
        assert cb.enabled is True

        c1 = cb.get_circuit(0)
        assert c1.worker_id == 0
        assert c1.state == CircuitState.CLOSED

        c2 = cb.get_circuit(0)
        assert c1 is c2


class TestClosedToOpen:
    """Tests for CLOSED -> OPEN transition after N failures."""

    def test_transition_at_threshold(self):
        """Circuit opens after exactly failure_threshold failures."""
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure(0, task_id="T1", error="err1")
        assert cb.get_circuit(0).state == CircuitState.CLOSED
        cb.record_failure(0, task_id="T2", error="err2")
        assert cb.get_circuit(0).state == CircuitState.CLOSED
        cb.record_failure(0, task_id="T3", error="err3")
        assert cb.get_circuit(0).state == CircuitState.OPEN

    def test_success_resets_failure_count(self):
        """A success resets the consecutive failure counter."""
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure(0, task_id="T1")
        cb.record_failure(0, task_id="T2")
        cb.record_success(0, task_id="T3")
        assert cb.get_circuit(0).failure_count == 0
        cb.record_failure(0, task_id="T4")
        cb.record_failure(0, task_id="T5")
        assert cb.get_circuit(0).state == CircuitState.CLOSED


class TestOpenToHalfOpen:
    """Tests for OPEN -> HALF_OPEN transition after cooldown."""

    def test_cooldown_elapsed_transitions(self):
        """Circuit transitions to HALF_OPEN after cooldown period."""
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.05)
        cb.record_failure(0, task_id="T1")
        assert cb.get_circuit(0).state == CircuitState.OPEN
        assert cb.can_accept_task(0) is False

        time.sleep(0.06)
        assert cb.can_accept_task(0) is True
        assert cb.get_circuit(0).state == CircuitState.HALF_OPEN

    def test_cooldown_not_elapsed_stays_open(self):
        """Circuit stays OPEN before cooldown expires."""
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=10.0)
        cb.record_failure(0, task_id="T1")
        assert cb.can_accept_task(0) is False


class TestHalfOpenTransitions:
    """Tests for HALF_OPEN -> CLOSED and HALF_OPEN -> OPEN transitions."""

    def test_success_closes_circuit(self):
        """Successful probe in HALF_OPEN closes the circuit."""
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.01)
        cb.record_failure(0, task_id="T1")
        time.sleep(0.02)
        cb.can_accept_task(0)
        assert cb.get_circuit(0).state == CircuitState.HALF_OPEN

        cb.mark_half_open_task(0, "T2")
        cb.record_success(0, task_id="T2")
        assert cb.get_circuit(0).state == CircuitState.CLOSED
        assert cb.get_circuit(0).failure_count == 0
        assert cb.get_circuit(0).half_open_task_id is None

    def test_failure_reopens_circuit(self):
        """Failed probe in HALF_OPEN reopens the circuit."""
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.01)
        cb.record_failure(0, task_id="T1")
        time.sleep(0.02)
        cb.can_accept_task(0)
        assert cb.get_circuit(0).state == CircuitState.HALF_OPEN

        cb.mark_half_open_task(0, "T2")
        cb.record_failure(0, task_id="T2", error="probe failed")
        assert cb.get_circuit(0).state == CircuitState.OPEN
        assert cb.get_circuit(0).half_open_task_id is None


class TestCanAcceptTask:
    """Tests for can_accept_task in each state."""

    def test_closed_accepts_open_rejects(self):
        """CLOSED accepts; OPEN rejects."""
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=9999)
        assert cb.can_accept_task(0) is True
        cb.record_failure(0, task_id="T1")
        assert cb.can_accept_task(0) is False

    def test_half_open_allows_one_probe(self):
        """HALF_OPEN allows one task (probe), then blocks."""
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.01)
        cb.record_failure(0, task_id="T1")
        time.sleep(0.02)

        assert cb.can_accept_task(0) is True
        cb.mark_half_open_task(0, "T2")
        assert cb.can_accept_task(0) is False


class TestDisabledCircuitBreaker:
    """Tests for disabled circuit breaker."""

    def test_disabled_always_allows_no_tracking(self):
        """Disabled breaker always accepts tasks and doesn't track."""
        cb = CircuitBreaker(enabled=False, failure_threshold=1)
        cb.record_failure(0, task_id="T1")
        cb.record_failure(0, task_id="T2")
        cb.record_success(0, task_id="T3")
        assert cb.can_accept_task(0) is True
        assert cb.get_circuit(0).failure_count == 0
        assert cb.get_circuit(0).success_count == 0


class TestResetAndStatus:
    """Tests for circuit reset and status reporting."""

    def test_reset_restores_defaults(self):
        """Reset restores circuit to initial state."""
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure(0, task_id="T1")
        assert cb.get_circuit(0).state == CircuitState.OPEN
        cb.reset(0)
        circuit = cb.get_circuit(0)
        assert circuit.state == CircuitState.CLOSED
        assert circuit.failure_count == 0

    def test_status_reports_all_workers(self):
        """Status includes all tracked workers with correct state."""
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_success(0, task_id="T1")
        cb.record_failure(1, task_id="T2")
        status = cb.get_status()
        assert status[0]["state"] == "closed"
        assert status[0]["success_count"] == 1
        assert status[1]["failure_count"] == 1


class TestIndependentWorkerCircuits:
    """Tests for independent per-worker circuits."""

    def test_workers_are_independent(self):
        """Failures in one worker don't affect another; reset is isolated."""
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure(0, task_id="T1")
        cb.record_failure(0, task_id="T2")
        assert cb.get_circuit(0).state == CircuitState.OPEN
        assert cb.get_circuit(1).state == CircuitState.CLOSED
        assert cb.can_accept_task(1) is True

        cb.record_failure(1, task_id="T3")
        cb.record_failure(1, task_id="T4")
        cb.reset(0)
        assert cb.get_circuit(0).state == CircuitState.CLOSED
        assert cb.get_circuit(1).state == CircuitState.OPEN
