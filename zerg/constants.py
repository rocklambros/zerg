"""ZERG constants and enumerations."""

from enum import Enum, IntEnum


class Level(IntEnum):
    """Task execution levels (dependency waves)."""

    FOUNDATION = 1
    CORE = 2
    INTEGRATION = 3
    COMMANDS = 4
    QUALITY = 5


class TaskStatus(Enum):
    """Task execution status."""

    TODO = "todo"
    PENDING = "pending"
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    VERIFYING = "verifying"
    COMPLETE = "complete"
    FAILED = "failed"
    BLOCKED = "blocked"
    PAUSED = "paused"


class GateResult(Enum):
    """Quality gate execution result."""

    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    TIMEOUT = "timeout"
    ERROR = "error"


class WorkerStatus(Enum):
    """Worker instance status."""

    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    IDLE = "idle"
    CHECKPOINTING = "checkpointing"
    STOPPING = "stopping"
    STOPPED = "stopped"
    CRASHED = "crashed"
    BLOCKED = "blocked"


class MergeStatus(Enum):
    """Branch merge status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    MERGED = "merged"
    CONFLICT = "conflict"
    FAILED = "failed"


class ExitCode(IntEnum):
    """Worker exit codes."""

    SUCCESS = 0
    ERROR = 1
    CHECKPOINT = 2
    BLOCKED = 3


# Default configuration values
DEFAULT_WORKERS = 5
DEFAULT_TIMEOUT_MINUTES = 30
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_CONTEXT_THRESHOLD = 0.70
DEFAULT_PORT_RANGE_START = 49152
DEFAULT_PORT_RANGE_END = 65535
DEFAULT_PORTS_PER_WORKER = 10

# Level names mapping
LEVEL_NAMES = {
    Level.FOUNDATION: "foundation",
    Level.CORE: "core",
    Level.INTEGRATION: "integration",
    Level.COMMANDS: "commands",
    Level.QUALITY: "quality",
}

# State file locations
STATE_DIR = ".zerg/state"
LOGS_DIR = ".zerg/logs"
WORKTREES_DIR = ".zerg-worktrees"
SPECS_DIR = ".gsd/specs"
