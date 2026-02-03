"""Iterative improvement loop controller for ZERG."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from zerg.logging import get_logger

logger = get_logger("loops")


class LoopStatus(Enum):
    """Status of an improvement loop."""

    RUNNING = "running"
    CONVERGED = "converged"
    PLATEAU = "plateau"
    REGRESSED = "regressed"
    MAX_ITERATIONS = "max_iterations"
    ABORTED = "aborted"


@dataclass
class IterationResult:
    """Result of a single iteration."""

    iteration: int
    score: float
    improved: bool
    delta: float  # Change from previous score
    duration_seconds: float
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_regression(self) -> bool:
        """Check if this iteration regressed."""
        return self.delta < 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "iteration": self.iteration,
            "score": self.score,
            "improved": self.improved,
            "delta": round(self.delta, 4),
            "duration_seconds": round(self.duration_seconds, 2),
            "is_regression": self.is_regression,
            "details": self.details,
        }


@dataclass
class LoopSummary:
    """Summary of completed loop execution."""

    status: LoopStatus
    iterations: list[IterationResult]
    best_score: float
    best_iteration: int
    total_duration_seconds: float

    @property
    def improvement(self) -> float:
        """Total improvement from first to best score."""
        if not self.iterations:
            return 0.0
        return self.best_score - self.iterations[0].score

    @property
    def converged(self) -> bool:
        """Check if loop converged."""
        return self.status == LoopStatus.CONVERGED

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "iterations": [r.to_dict() for r in self.iterations],
            "best_score": self.best_score,
            "best_iteration": self.best_iteration,
            "improvement": round(self.improvement, 4),
            "converged": self.converged,
            "total_duration_seconds": round(self.total_duration_seconds, 2),
        }


class LoopController:
    """Controls iterative improvement loops with convergence detection.

    The controller runs an improvement function repeatedly, tracking scores
    and detecting convergence, plateaus, or regressions.
    """

    def __init__(
        self,
        max_iterations: int = 5,
        convergence_threshold: float = 0.02,
        plateau_threshold: int = 2,
        rollback_on_regression: bool = True,
    ) -> None:
        """Initialize loop controller.

        Args:
            max_iterations: Maximum number of iterations.
            convergence_threshold: Minimum improvement to consider progress.
            plateau_threshold: Number of non-improving iterations before stopping.
            rollback_on_regression: Whether to stop and rollback on score regression.
        """
        self.max_iterations = max_iterations
        self.convergence_threshold = convergence_threshold
        self.plateau_threshold = plateau_threshold
        self.rollback_on_regression = rollback_on_regression

    def run(
        self,
        improve_fn: Callable[[int], float],
        initial_score: float = 0.0,
    ) -> LoopSummary:
        """Run the improvement loop.

        Args:
            improve_fn: Function that takes iteration number and returns a score.
                Higher scores are better.
            initial_score: Starting score before any iterations.

        Returns:
            LoopSummary with all iteration results.
        """
        iterations: list[IterationResult] = []
        best_score = initial_score
        best_iteration = 0
        plateau_count = 0
        previous_score = initial_score
        start_time = time.monotonic()
        status = LoopStatus.MAX_ITERATIONS

        for i in range(1, self.max_iterations + 1):
            iter_start = time.monotonic()

            try:
                score = improve_fn(i)
            except Exception as e:
                logger.error(f"Iteration {i} failed: {e}")
                status = LoopStatus.ABORTED
                break

            delta = score - previous_score
            improved = delta > self.convergence_threshold

            result = IterationResult(
                iteration=i,
                score=score,
                improved=improved,
                delta=delta,
                duration_seconds=time.monotonic() - iter_start,
            )
            iterations.append(result)

            logger.info(
                f"Iteration {i}: score={score:.4f} delta={delta:+.4f} {'improved' if improved else 'no improvement'}"
            )

            # Track best
            if score > best_score:
                best_score = score
                best_iteration = i

            # Check regression
            if delta < -self.convergence_threshold and self.rollback_on_regression:
                logger.warning(f"Regression detected at iteration {i}: {delta:+.4f}")
                status = LoopStatus.REGRESSED
                break

            # Check plateau
            if not improved:
                plateau_count += 1
                if plateau_count >= self.plateau_threshold:
                    logger.info(f"Plateau reached after {plateau_count} non-improving iterations")
                    status = LoopStatus.PLATEAU
                    break
            else:
                plateau_count = 0

            # Check convergence (delta approaching zero from positive side)
            if 0 < delta <= self.convergence_threshold and i > 1:
                logger.info(f"Converged at iteration {i}: delta={delta:.4f}")
                status = LoopStatus.CONVERGED
                break

            previous_score = score

        return LoopSummary(
            status=status,
            iterations=iterations,
            best_score=best_score,
            best_iteration=best_iteration,
            total_duration_seconds=time.monotonic() - start_time,
        )

    def should_continue(self, iterations: list[IterationResult]) -> bool:
        """Check if loop should continue based on history.

        Args:
            iterations: List of completed iteration results.

        Returns:
            True if loop should continue.
        """
        if not iterations:
            return True

        if len(iterations) >= self.max_iterations:
            return False

        # Check plateau
        non_improving = 0
        for result in reversed(iterations):
            if not result.improved:
                non_improving += 1
            else:
                break

        if non_improving >= self.plateau_threshold:
            return False

        # Check regression
        if self.rollback_on_regression and iterations[-1].is_regression:
            return False

        return True
