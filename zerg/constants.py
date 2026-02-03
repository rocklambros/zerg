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
    STALLED = "stalled"


class MergeStatus(Enum):
    """Branch merge status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    MERGED = "merged"
    CONFLICT = "conflict"
    FAILED = "failed"


class LevelMergeStatus(Enum):
    """Level merge protocol status.

    Tracks the state of merging all worker branches after a level completes.
    """

    PENDING = "pending"  # Level not yet complete, merge not started
    WAITING = "waiting"  # Waiting for all workers to finish level
    COLLECTING = "collecting"  # Gathering worker branches for merge
    MERGING = "merging"  # Merge in progress
    VALIDATING = "validating"  # Running quality gates on merged code
    REBASING = "rebasing"  # Rebasing worker branches onto merged base
    COMPLETE = "complete"  # Merge successful, ready for next level
    CONFLICT = "conflict"  # Merge conflict detected, needs intervention
    FAILED = "failed"  # Merge or validation failed


class ExitCode(IntEnum):
    """Worker exit codes."""

    SUCCESS = 0
    ERROR = 1
    CHECKPOINT = 2
    BLOCKED = 3
    ESCALATION = 4


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
LOGS_WORKERS_DIR = ".zerg/logs/workers"
LOGS_TASKS_DIR = ".zerg/logs/tasks"
WORKTREES_DIR = ".zerg-worktrees"
GSD_DIR = ".gsd"
SPECS_DIR = ".gsd/specs"

# Analysis depth environment variable
ZERG_ANALYSIS_DEPTH = "ZERG_ANALYSIS_DEPTH"

# Compact mode environment variable
ZERG_COMPACT_MODE = "ZERG_COMPACT_MODE"


class LogPhase(Enum):
    """Execution phases for structured logging."""

    CLAIM = "claim"
    EXECUTE = "execute"
    VERIFY = "verify"
    COMMIT = "commit"
    CLEANUP = "cleanup"


class LogEvent(Enum):
    """Structured log event types."""

    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    VERIFICATION_PASSED = "verification_passed"
    VERIFICATION_FAILED = "verification_failed"
    ARTIFACT_CAPTURED = "artifact_captured"
    LEVEL_STARTED = "level_started"
    LEVEL_COMPLETE = "level_complete"
    MERGE_STARTED = "merge_started"
    MERGE_COMPLETE = "merge_complete"
    HEARTBEAT_STALE = "heartbeat_stale"
    ESCALATION_CREATED = "escalation_created"
    ESCALATION_RESOLVED = "escalation_resolved"
    WORKER_AUTO_RESTARTED = "worker_auto_restarted"
    WORKER_REASSIGNED = "worker_reassigned"
    VERIFICATION_TIER_PASSED = "verification_tier_passed"
    VERIFICATION_TIER_FAILED = "verification_tier_failed"


class PluginHookEvent(Enum):
    """Plugin lifecycle hook event types."""

    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    LEVEL_COMPLETE = "level_complete"
    MERGE_COMPLETE = "merge_complete"
    RUSH_FINISHED = "rush_finished"
    QUALITY_GATE_RUN = "quality_gate_run"
    WORKER_SPAWNED = "worker_spawned"
    WORKER_EXITED = "worker_exited"
    PRE_TASK_PROMPT = "pre_task_prompt"
    POST_CONTEXT_BUILD = "post_context_build"


class ResilienceEvent(Enum):
    """Resilience event types for structured logging.

    Used for logging resilience-related events to .zerg/monitor.log.
    All events use ISO8601 timestamps with milliseconds and include
    worker ID prefix for correlation.
    """

    # Worker lifecycle events
    WORKER_SPAWN = "worker_spawn"
    WORKER_SPAWN_RETRY = "worker_spawn_retry"
    WORKER_SPAWN_FAILED = "worker_spawn_failed"
    WORKER_READY = "worker_ready"
    WORKER_EXIT = "worker_exit"
    WORKER_CRASH = "worker_crash"
    WORKER_RESPAWN = "worker_respawn"

    # Task lifecycle events
    TASK_CLAIMED = "task_claimed"
    TASK_STARTED = "task_started"
    TASK_COMPLETE = "task_complete"
    TASK_FAILED = "task_failed"
    TASK_TIMEOUT = "task_timeout"
    TASK_REASSIGNED = "task_reassigned"

    # Heartbeat events
    HEARTBEAT_STALE = "heartbeat_stale"
    HEARTBEAT_RECOVERED = "heartbeat_recovered"

    # State reconciliation events
    STATE_RECONCILE_START = "state_reconcile_start"
    STATE_RECONCILE_FIX = "state_reconcile_fix"
    STATE_RECONCILE_COMPLETE = "state_reconcile_complete"

    # Level events
    LEVEL_CHECK = "level_check"
    LEVEL_COMPLETE = "level_complete"
