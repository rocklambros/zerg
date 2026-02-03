"""Circuit breaker for worker failure management."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from zerg.logging import get_logger

logger = get_logger("circuit_breaker")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, tasks flow through
    OPEN = "open"  # Failures exceeded threshold, stop sending tasks
    HALF_OPEN = "half_open"  # Testing recovery, allow one task through


@dataclass
class WorkerCircuit:
    """Circuit state for a single worker."""

    worker_id: int
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float | None = None
    last_state_change: float = field(default_factory=time.monotonic)
    half_open_task_id: str | None = None  # Task sent during HALF_OPEN probe


class CircuitBreaker:
    """Manages circuit breakers per worker to prevent cascading failures.

    State machine:
    CLOSED -> OPEN: after ``failure_threshold`` consecutive failures
    OPEN -> HALF_OPEN: after ``cooldown_seconds`` elapsed
    HALF_OPEN -> CLOSED: if probe task succeeds
    HALF_OPEN -> OPEN: if probe task fails
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
        enabled: bool = True,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        self._enabled = enabled
        self._circuits: dict[int, WorkerCircuit] = {}

    @property
    def enabled(self) -> bool:
        """Whether the circuit breaker is enabled."""
        return self._enabled

    def get_circuit(self, worker_id: int) -> WorkerCircuit:
        """Get or create circuit for a worker."""
        if worker_id not in self._circuits:
            self._circuits[worker_id] = WorkerCircuit(worker_id=worker_id)
        return self._circuits[worker_id]

    def can_accept_task(self, worker_id: int) -> bool:
        """Check if worker can accept a new task.

        Returns True if circuit is CLOSED or transitioning to HALF_OPEN.
        """
        if not self._enabled:
            return True

        circuit = self.get_circuit(worker_id)

        if circuit.state == CircuitState.CLOSED:
            return True

        if circuit.state == CircuitState.OPEN:
            # Check if cooldown has elapsed
            elapsed = time.monotonic() - circuit.last_state_change
            if elapsed >= self._cooldown_seconds:
                # Transition to HALF_OPEN
                circuit.state = CircuitState.HALF_OPEN
                circuit.last_state_change = time.monotonic()
                logger.info(f"Worker {worker_id} circuit OPEN -> HALF_OPEN (cooldown {elapsed:.0f}s elapsed)")
                return True
            return False

        if circuit.state == CircuitState.HALF_OPEN:
            # Only allow one task through for probing
            return circuit.half_open_task_id is None

        return False

    def record_success(self, worker_id: int, task_id: str | None = None) -> None:
        """Record a successful task execution."""
        if not self._enabled:
            return
        circuit = self.get_circuit(worker_id)
        circuit.success_count += 1
        circuit.failure_count = 0  # Reset consecutive failures

        if circuit.state == CircuitState.HALF_OPEN:
            # Probe succeeded -- close circuit
            circuit.state = CircuitState.CLOSED
            circuit.last_state_change = time.monotonic()
            circuit.half_open_task_id = None
            logger.info(f"Worker {worker_id} circuit HALF_OPEN -> CLOSED (probe succeeded)")

    def record_failure(self, worker_id: int, task_id: str | None = None, error: str = "") -> None:
        """Record a failed task execution."""
        if not self._enabled:
            return
        circuit = self.get_circuit(worker_id)
        circuit.failure_count += 1
        circuit.last_failure_time = time.monotonic()

        if circuit.state == CircuitState.HALF_OPEN:
            # Probe failed -- reopen circuit
            circuit.state = CircuitState.OPEN
            circuit.last_state_change = time.monotonic()
            circuit.half_open_task_id = None
            logger.info(f"Worker {worker_id} circuit HALF_OPEN -> OPEN (probe failed: {error})")

        elif circuit.state == CircuitState.CLOSED:
            if circuit.failure_count >= self._failure_threshold:
                circuit.state = CircuitState.OPEN
                circuit.last_state_change = time.monotonic()
                logger.warning(
                    f"Worker {worker_id} circuit CLOSED -> OPEN ({circuit.failure_count} consecutive failures)"
                )

    def mark_half_open_task(self, worker_id: int, task_id: str) -> None:
        """Mark the task being used as a HALF_OPEN probe."""
        circuit = self.get_circuit(worker_id)
        circuit.half_open_task_id = task_id

    def reset(self, worker_id: int) -> None:
        """Reset circuit for a worker (e.g., after respawn)."""
        if worker_id in self._circuits:
            self._circuits[worker_id] = WorkerCircuit(worker_id=worker_id)

    def get_status(self) -> dict[int, dict[str, Any]]:
        """Get status of all circuits."""
        return {
            wid: {
                "state": c.state.value,
                "failure_count": c.failure_count,
                "success_count": c.success_count,
            }
            for wid, c in self._circuits.items()
        }
