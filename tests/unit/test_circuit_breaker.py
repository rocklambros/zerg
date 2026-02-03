"""Tests for ZERG CircuitBreaker module."""

import time

from zerg.circuit_breaker import CircuitBreaker, CircuitState, WorkerCircuit


class TestWorkerCircuit:
    """Tests for WorkerCircuit dataclass."""

    def test_default_state_is_closed(self):
        """New circuits start in CLOSED state."""
        circuit = WorkerCircuit(worker_id=0)
        assert circuit.state == CircuitState.CLOSED
        assert circuit.failure_count == 0
        assert circuit.success_count == 0
        assert circuit.last_failure_time is None
        assert circuit.half_open_task_id is None

    def test_worker_id_stored(self):
        """Worker ID is stored correctly."""
        circuit = WorkerCircuit(worker_id=42)
        assert circuit.worker_id == 42


class TestCircuitState:
    """Tests for CircuitState enum."""

    def test_state_values(self):
        """States have correct string values."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"


class TestCircuitBreakerInit:
    """Tests for CircuitBreaker initialization."""

    def test_defaults(self):
        """Default parameters are set correctly."""
        cb = CircuitBreaker()
        assert cb.enabled is True

    def test_custom_params(self):
        """Custom parameters are respected."""
        cb = CircuitBreaker(failure_threshold=5, cooldown_seconds=120.0, enabled=False)
        assert cb.enabled is False

    def test_get_circuit_creates_new(self):
        """get_circuit creates a new circuit for unknown worker."""
        cb = CircuitBreaker()
        circuit = cb.get_circuit(0)
        assert circuit.worker_id == 0
        assert circuit.state == CircuitState.CLOSED

    def test_get_circuit_returns_existing(self):
        """get_circuit returns the same circuit object on repeated calls."""
        cb = CircuitBreaker()
        c1 = cb.get_circuit(0)
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

    def test_no_transition_below_threshold(self):
        """Circuit stays closed below threshold."""
        cb = CircuitBreaker(failure_threshold=5)
        for i in range(4):
            cb.record_failure(0, task_id=f"T{i}")
        assert cb.get_circuit(0).state == CircuitState.CLOSED

    def test_success_resets_failure_count(self):
        """A success resets the consecutive failure counter."""
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure(0, task_id="T1")
        cb.record_failure(0, task_id="T2")
        cb.record_success(0, task_id="T3")
        assert cb.get_circuit(0).failure_count == 0
        # Now need 3 more failures to open
        cb.record_failure(0, task_id="T4")
        cb.record_failure(0, task_id="T5")
        assert cb.get_circuit(0).state == CircuitState.CLOSED

    def test_failure_count_tracks_correctly(self):
        """Failure count increments on each failure."""
        cb = CircuitBreaker(failure_threshold=10)
        for i in range(5):
            cb.record_failure(0, task_id=f"T{i}")
        assert cb.get_circuit(0).failure_count == 5


class TestOpenToHalfOpen:
    """Tests for OPEN -> HALF_OPEN transition after cooldown."""

    def test_cooldown_elapsed_transitions(self):
        """Circuit transitions to HALF_OPEN after cooldown period."""
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.05)
        # Trip the breaker
        cb.record_failure(0, task_id="T1")
        assert cb.get_circuit(0).state == CircuitState.OPEN
        assert cb.can_accept_task(0) is False

        # Wait for cooldown
        time.sleep(0.06)
        assert cb.can_accept_task(0) is True
        assert cb.get_circuit(0).state == CircuitState.HALF_OPEN

    def test_cooldown_not_elapsed_stays_open(self):
        """Circuit stays OPEN before cooldown expires."""
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=10.0)
        cb.record_failure(0, task_id="T1")
        assert cb.get_circuit(0).state == CircuitState.OPEN
        assert cb.can_accept_task(0) is False


class TestHalfOpenToClosed:
    """Tests for HALF_OPEN -> CLOSED on probe success."""

    def test_success_closes_circuit(self):
        """Successful probe in HALF_OPEN closes the circuit."""
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.01)
        cb.record_failure(0, task_id="T1")
        time.sleep(0.02)
        cb.can_accept_task(0)  # Triggers HALF_OPEN
        assert cb.get_circuit(0).state == CircuitState.HALF_OPEN

        cb.mark_half_open_task(0, "T2")
        cb.record_success(0, task_id="T2")
        assert cb.get_circuit(0).state == CircuitState.CLOSED
        assert cb.get_circuit(0).half_open_task_id is None

    def test_success_resets_failure_count(self):
        """Success during HALF_OPEN resets failure count."""
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.01)
        cb.record_failure(0, task_id="T1")
        time.sleep(0.02)
        cb.can_accept_task(0)
        cb.record_success(0, task_id="T2")
        assert cb.get_circuit(0).failure_count == 0


class TestHalfOpenToOpen:
    """Tests for HALF_OPEN -> OPEN on probe failure."""

    def test_failure_reopens_circuit(self):
        """Failed probe in HALF_OPEN reopens the circuit."""
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.01)
        cb.record_failure(0, task_id="T1")
        time.sleep(0.02)
        cb.can_accept_task(0)  # Triggers HALF_OPEN
        assert cb.get_circuit(0).state == CircuitState.HALF_OPEN

        cb.mark_half_open_task(0, "T2")
        cb.record_failure(0, task_id="T2", error="probe failed")
        assert cb.get_circuit(0).state == CircuitState.OPEN
        assert cb.get_circuit(0).half_open_task_id is None


class TestCanAcceptTask:
    """Tests for can_accept_task in each state."""

    def test_closed_accepts(self):
        """CLOSED circuit accepts tasks."""
        cb = CircuitBreaker()
        assert cb.can_accept_task(0) is True

    def test_open_rejects(self):
        """OPEN circuit rejects tasks (before cooldown)."""
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=9999)
        cb.record_failure(0, task_id="T1")
        assert cb.can_accept_task(0) is False

    def test_half_open_allows_one_probe(self):
        """HALF_OPEN allows one task (probe), then blocks."""
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.01)
        cb.record_failure(0, task_id="T1")
        time.sleep(0.02)

        # First call transitions and allows
        assert cb.can_accept_task(0) is True
        # Mark the probe task
        cb.mark_half_open_task(0, "T2")
        # Second call should block because probe already in-flight
        assert cb.can_accept_task(0) is False

    def test_half_open_allows_after_probe_cleared(self):
        """HALF_OPEN allows another task after probe result is recorded."""
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.01)
        cb.record_failure(0, task_id="T1")
        time.sleep(0.02)
        cb.can_accept_task(0)
        cb.mark_half_open_task(0, "T2")
        cb.record_success(0, task_id="T2")
        # Now CLOSED, should accept
        assert cb.can_accept_task(0) is True


class TestDisabledCircuitBreaker:
    """Tests for disabled circuit breaker."""

    def test_always_allows_tasks(self):
        """Disabled breaker always accepts tasks."""
        cb = CircuitBreaker(enabled=False, failure_threshold=1)
        cb.record_failure(0, task_id="T1")
        cb.record_failure(0, task_id="T2")
        cb.record_failure(0, task_id="T3")
        assert cb.can_accept_task(0) is True

    def test_record_success_noop(self):
        """Disabled breaker does not track successes."""
        cb = CircuitBreaker(enabled=False)
        cb.record_success(0, task_id="T1")
        # Circuit is created by get_circuit but success_count stays 0
        # because record_success returns early
        assert cb.get_circuit(0).success_count == 0

    def test_record_failure_noop(self):
        """Disabled breaker does not track failures."""
        cb = CircuitBreaker(enabled=False)
        cb.record_failure(0, task_id="T1")
        assert cb.get_circuit(0).failure_count == 0


class TestReset:
    """Tests for circuit reset."""

    def test_reset_restores_defaults(self):
        """Reset restores circuit to initial state."""
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure(0, task_id="T1")
        assert cb.get_circuit(0).state == CircuitState.OPEN
        cb.reset(0)
        circuit = cb.get_circuit(0)
        assert circuit.state == CircuitState.CLOSED
        assert circuit.failure_count == 0
        assert circuit.success_count == 0

    def test_reset_nonexistent_noop(self):
        """Resetting a worker that has no circuit is a no-op."""
        cb = CircuitBreaker()
        cb.reset(999)  # Should not raise


class TestGetStatus:
    """Tests for get_status."""

    def test_empty_status(self):
        """Empty breaker returns empty status."""
        cb = CircuitBreaker()
        assert cb.get_status() == {}

    def test_status_reports_all_workers(self):
        """Status includes all tracked workers."""
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_success(0, task_id="T1")
        cb.record_failure(1, task_id="T2")
        status = cb.get_status()
        assert 0 in status
        assert 1 in status
        assert status[0]["state"] == "closed"
        assert status[0]["success_count"] == 1
        assert status[1]["failure_count"] == 1

    def test_status_reflects_state_changes(self):
        """Status reflects state transitions."""
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure(0, task_id="T1")
        status = cb.get_status()
        assert status[0]["state"] == "open"


class TestIndependentWorkerCircuits:
    """Tests for independent per-worker circuits."""

    def test_workers_are_independent(self):
        """Failures in one worker don't affect another."""
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure(0, task_id="T1")
        cb.record_failure(0, task_id="T2")
        assert cb.get_circuit(0).state == CircuitState.OPEN
        assert cb.get_circuit(1).state == CircuitState.CLOSED
        assert cb.can_accept_task(1) is True

    def test_multiple_workers_tracked(self):
        """Multiple workers are tracked independently."""
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure(0, task_id="T1")
        cb.record_success(1, task_id="T2")
        cb.record_failure(2, task_id="T3")

        assert cb.get_circuit(0).state == CircuitState.OPEN
        assert cb.get_circuit(1).state == CircuitState.CLOSED
        assert cb.get_circuit(2).state == CircuitState.OPEN

    def test_reset_one_worker_preserves_others(self):
        """Resetting one worker does not affect others."""
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure(0, task_id="T1")
        cb.record_failure(1, task_id="T2")
        cb.reset(0)
        assert cb.get_circuit(0).state == CircuitState.CLOSED
        assert cb.get_circuit(1).state == CircuitState.OPEN


class TestMarkHalfOpenTask:
    """Tests for mark_half_open_task."""

    def test_marks_task_id(self):
        """Task ID is recorded on the circuit."""
        cb = CircuitBreaker()
        cb.mark_half_open_task(0, "probe-task")
        assert cb.get_circuit(0).half_open_task_id == "probe-task"

    def test_cleared_on_success(self):
        """Half-open task ID is cleared on success."""
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.01)
        cb.record_failure(0, task_id="T1")
        time.sleep(0.02)
        cb.can_accept_task(0)
        cb.mark_half_open_task(0, "probe")
        cb.record_success(0, task_id="probe")
        assert cb.get_circuit(0).half_open_task_id is None

    def test_cleared_on_failure(self):
        """Half-open task ID is cleared on failure."""
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.01)
        cb.record_failure(0, task_id="T1")
        time.sleep(0.02)
        cb.can_accept_task(0)
        cb.mark_half_open_task(0, "probe")
        cb.record_failure(0, task_id="probe", error="err")
        assert cb.get_circuit(0).half_open_task_id is None
