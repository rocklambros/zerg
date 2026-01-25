"""ZERG - Parallel Claude Code execution system.

Overwhelm features with coordinated worker instances.
"""

__version__ = "0.1.0"
__author__ = "ZERG Team"

from zerg.constants import Level, TaskStatus, GateResult, WorkerStatus
from zerg.exceptions import ZergError

__all__ = [
    "__version__",
    "Level",
    "TaskStatus",
    "GateResult",
    "WorkerStatus",
    "ZergError",
]
