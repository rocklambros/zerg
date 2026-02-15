"""ZERG - Parallel Claude Code execution system.

Overwhelm features with coordinated worker instances.
"""

__version__ = "0.3.2"
__author__ = "ZERG Team"

from zerg.architecture import ArchitectureChecker, ArchitectureConfig
from zerg.architecture_gate import ArchitectureGate
from zerg.constants import GateResult, Level, TaskStatus, WorkerStatus
from zerg.exceptions import ZergError
from zerg.worker_metrics import (
    LevelMetrics,
    TaskExecutionMetrics,
    WorkerMetrics,
    WorkerMetricsCollector,
    estimate_execution_cost,
)

__all__ = [
    "__version__",
    "Level",
    "TaskStatus",
    "GateResult",
    "WorkerStatus",
    "ZergError",
    # Architecture
    "ArchitectureChecker",
    "ArchitectureConfig",
    "ArchitectureGate",
    # Worker Metrics
    "TaskExecutionMetrics",
    "WorkerMetrics",
    "LevelMetrics",
    "WorkerMetricsCollector",
    "estimate_execution_cost",
]
