"""Base class for performance analysis tool adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod

from zerg.performance.types import DetectedStack, PerformanceFinding


class BaseToolAdapter(ABC):
    """Base class for performance analysis tool adapters."""

    name: str = "base"
    tool_name: str = ""  # Binary name for shutil.which
    factors_covered: list[int] = []  # Factor IDs from catalog

    @abstractmethod
    def run(
        self,
        files: list[str],
        project_path: str,
        stack: DetectedStack,
    ) -> list[PerformanceFinding]:
        """Execute tool and return findings."""
        ...

    def is_applicable(self, stack: DetectedStack) -> bool:
        """Whether this adapter applies to the detected stack."""
        return True
