"""Retry backoff calculator for ZERG task retries."""

import random


class RetryBackoffCalculator:
    """Calculate backoff delays for task retries."""

    @staticmethod
    def calculate_delay(
        attempt: int,
        strategy: str,
        base_seconds: int,
        max_seconds: int,
    ) -> float:
        """Calculate backoff delay with jitter.

        Args:
            attempt: Retry attempt number (1-based)
            strategy: Backoff strategy (exponential, linear, fixed)
            base_seconds: Base delay in seconds
            max_seconds: Maximum delay cap in seconds

        Returns:
            Delay in seconds with ±10% jitter applied
        """
        if strategy == "exponential":
            delay = base_seconds * (2**attempt)
        elif strategy == "linear":
            delay = base_seconds * attempt
        elif strategy == "fixed":
            delay = base_seconds
        else:
            raise ValueError(f"Unknown backoff strategy: {strategy}")

        # Cap at max
        delay = min(delay, max_seconds)

        # Add ±10% jitter
        jitter = delay * 0.1
        delay = delay + random.uniform(-jitter, jitter)

        return float(max(0.0, delay))
