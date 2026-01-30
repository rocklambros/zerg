"""Backpressure controller for level failure rate management."""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from zerg.logging import get_logger

logger = get_logger("backpressure")


@dataclass
class LevelPressure:
    """Pressure state for a single level."""

    level: int
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    paused: bool = False
    paused_at: float | None = None
    # Sliding window of recent outcomes (True=success, False=failure)
    recent_outcomes: deque[bool] = field(default_factory=lambda: deque(maxlen=10))


class BackpressureController:
    """Monitors failure rates per level and applies backpressure.

    When the failure rate within a sliding window exceeds the threshold,
    the level is paused to prevent wasting resources on a broken level.

    Attributes:
        failure_rate_threshold: Fraction of failures that triggers pause (0.0-1.0)
        window_size: Number of recent task outcomes to consider
        enabled: Whether backpressure is active
    """

    def __init__(
        self,
        failure_rate_threshold: float = 0.5,
        window_size: int = 10,
        enabled: bool = True,
    ) -> None:
        self._threshold = failure_rate_threshold
        self._window_size = window_size
        self._enabled = enabled
        self._levels: dict[int, LevelPressure] = {}

    @property
    def enabled(self) -> bool:
        return self._enabled

    def register_level(self, level: int, total_tasks: int) -> None:
        """Register a level for monitoring."""
        self._levels[level] = LevelPressure(
            level=level,
            total_tasks=total_tasks,
            recent_outcomes=deque(maxlen=self._window_size),
        )

    def record_success(self, level: int) -> None:
        """Record a successful task at this level."""
        if not self._enabled:
            return
        pressure = self._get_or_create(level)
        pressure.completed_tasks += 1
        pressure.recent_outcomes.append(True)

    def record_failure(self, level: int) -> None:
        """Record a failed task at this level."""
        if not self._enabled:
            return
        pressure = self._get_or_create(level)
        pressure.failed_tasks += 1
        pressure.recent_outcomes.append(False)

    def should_pause(self, level: int) -> bool:
        """Check if level should be paused due to high failure rate.

        Returns True if:
        - Backpressure is enabled
        - Window has enough data (>= 3 outcomes)
        - Failure rate in window exceeds threshold
        - Level is not already paused
        """
        if not self._enabled:
            return False

        pressure = self._get_or_create(level)
        if pressure.paused:
            return False  # Already paused

        outcomes = pressure.recent_outcomes
        if len(outcomes) < 3:  # Need minimum data
            return False

        failures = sum(1 for o in outcomes if not o)
        failure_rate = failures / len(outcomes)

        if failure_rate >= self._threshold:
            logger.warning(
                f"Level {level} failure rate {failure_rate:.0%} "
                f"exceeds threshold {self._threshold:.0%} "
                f"({failures}/{len(outcomes)} recent tasks failed)"
            )
            return True

        return False

    def pause_level(self, level: int) -> None:
        """Mark a level as paused."""
        pressure = self._get_or_create(level)
        pressure.paused = True
        pressure.paused_at = time.monotonic()
        logger.info(f"Level {level} paused due to backpressure")

    def resume_level(self, level: int) -> None:
        """Resume a paused level."""
        pressure = self._get_or_create(level)
        pressure.paused = False
        pressure.paused_at = None
        # Clear the window to give level a fresh start
        pressure.recent_outcomes.clear()
        logger.info(f"Level {level} resumed")

    def is_paused(self, level: int) -> bool:
        """Check if a level is currently paused."""
        pressure = self._levels.get(level)
        return pressure.paused if pressure else False

    def get_failure_rate(self, level: int) -> float:
        """Get current failure rate for a level."""
        pressure = self._levels.get(level)
        if not pressure or not pressure.recent_outcomes:
            return 0.0
        failures = sum(1 for o in pressure.recent_outcomes if not o)
        return failures / len(pressure.recent_outcomes)

    def get_status(self) -> dict[int, dict[str, Any]]:
        """Get status of all monitored levels."""
        return {
            lvl: {
                "total_tasks": p.total_tasks,
                "completed": p.completed_tasks,
                "failed": p.failed_tasks,
                "failure_rate": self.get_failure_rate(lvl),
                "paused": p.paused,
                "window_size": len(p.recent_outcomes),
            }
            for lvl, p in self._levels.items()
        }

    def _get_or_create(self, level: int) -> LevelPressure:
        """Get or create pressure state for a level."""
        if level not in self._levels:
            self._levels[level] = LevelPressure(
                level=level,
                recent_outcomes=deque(maxlen=self._window_size),
            )
        return self._levels[level]
