"""Unit tests for ZERG constants module."""

from zerg.constants import (
    DEFAULT_CONTEXT_THRESHOLD,
    DEFAULT_PORT_RANGE_END,
    DEFAULT_PORT_RANGE_START,
    DEFAULT_PORTS_PER_WORKER,
    DEFAULT_RETRY_ATTEMPTS,
    DEFAULT_TIMEOUT_MINUTES,
    DEFAULT_WORKERS,
    LEVEL_NAMES,
    LOGS_DIR,
    SPECS_DIR,
    STATE_DIR,
    WORKTREES_DIR,
    ExitCode,
    GateResult,
    Level,
    LevelMergeStatus,
    MergeStatus,
    TaskStatus,
    WorkerStatus,
)


class TestLevel:
    """Tests for Level enumeration."""

    def test_level_values(self) -> None:
        """Test Level enum values."""
        assert Level.FOUNDATION == 1
        assert Level.CORE == 2
        assert Level.INTEGRATION == 3
        assert Level.COMMANDS == 4
        assert Level.QUALITY == 5

    def test_level_ordering(self) -> None:
        """Test levels can be compared."""
        assert Level.FOUNDATION < Level.CORE
        assert Level.CORE < Level.INTEGRATION
        assert Level.QUALITY > Level.COMMANDS

    def test_level_in_level_names(self) -> None:
        """Test all levels have names."""
        for level in Level:
            assert level in LEVEL_NAMES


class TestTaskStatus:
    """Tests for TaskStatus enumeration."""

    def test_task_status_values(self) -> None:
        """Test TaskStatus enum values."""
        assert TaskStatus.TODO.value == "todo"
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.CLAIMED.value == "claimed"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.VERIFYING.value == "verifying"
        assert TaskStatus.COMPLETE.value == "complete"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.BLOCKED.value == "blocked"
        assert TaskStatus.PAUSED.value == "paused"

    def test_task_status_all_values(self) -> None:
        """Test all TaskStatus values are strings."""
        for status in TaskStatus:
            assert isinstance(status.value, str)


class TestGateResult:
    """Tests for GateResult enumeration."""

    def test_gate_result_values(self) -> None:
        """Test GateResult enum values."""
        assert GateResult.PASS.value == "pass"
        assert GateResult.FAIL.value == "fail"
        assert GateResult.SKIP.value == "skip"
        assert GateResult.TIMEOUT.value == "timeout"
        assert GateResult.ERROR.value == "error"


class TestWorkerStatus:
    """Tests for WorkerStatus enumeration."""

    def test_worker_status_values(self) -> None:
        """Test WorkerStatus enum values."""
        assert WorkerStatus.INITIALIZING.value == "initializing"
        assert WorkerStatus.READY.value == "ready"
        assert WorkerStatus.RUNNING.value == "running"
        assert WorkerStatus.IDLE.value == "idle"
        assert WorkerStatus.STOPPED.value == "stopped"
        assert WorkerStatus.CRASHED.value == "crashed"


class TestMergeStatus:
    """Tests for MergeStatus enumeration."""

    def test_merge_status_values(self) -> None:
        """Test MergeStatus enum values."""
        assert MergeStatus.PENDING.value == "pending"
        assert MergeStatus.IN_PROGRESS.value == "in_progress"
        assert MergeStatus.MERGED.value == "merged"
        assert MergeStatus.CONFLICT.value == "conflict"
        assert MergeStatus.FAILED.value == "failed"


class TestLevelMergeStatus:
    """Tests for LevelMergeStatus enumeration."""

    def test_level_merge_status_values(self) -> None:
        """Test LevelMergeStatus enum values."""
        assert LevelMergeStatus.PENDING.value == "pending"
        assert LevelMergeStatus.WAITING.value == "waiting"
        assert LevelMergeStatus.COLLECTING.value == "collecting"
        assert LevelMergeStatus.MERGING.value == "merging"
        assert LevelMergeStatus.VALIDATING.value == "validating"
        assert LevelMergeStatus.REBASING.value == "rebasing"
        assert LevelMergeStatus.COMPLETE.value == "complete"
        assert LevelMergeStatus.CONFLICT.value == "conflict"
        assert LevelMergeStatus.FAILED.value == "failed"


class TestExitCode:
    """Tests for ExitCode enumeration."""

    def test_exit_code_values(self) -> None:
        """Test ExitCode enum values."""
        assert ExitCode.SUCCESS == 0
        assert ExitCode.ERROR == 1
        assert ExitCode.CHECKPOINT == 2
        assert ExitCode.BLOCKED == 3


class TestDefaultValues:
    """Tests for default configuration values."""

    def test_default_workers(self) -> None:
        """Test default worker count."""
        assert DEFAULT_WORKERS == 5
        assert DEFAULT_WORKERS > 0

    def test_default_timeout(self) -> None:
        """Test default timeout."""
        assert DEFAULT_TIMEOUT_MINUTES == 30
        assert DEFAULT_TIMEOUT_MINUTES > 0

    def test_default_retry(self) -> None:
        """Test default retry attempts."""
        assert DEFAULT_RETRY_ATTEMPTS == 3
        assert DEFAULT_RETRY_ATTEMPTS > 0

    def test_default_context_threshold(self) -> None:
        """Test default context threshold."""
        assert DEFAULT_CONTEXT_THRESHOLD == 0.70
        assert 0 < DEFAULT_CONTEXT_THRESHOLD < 1

    def test_port_range(self) -> None:
        """Test port range values."""
        assert DEFAULT_PORT_RANGE_START == 49152
        assert DEFAULT_PORT_RANGE_END == 65535
        assert DEFAULT_PORT_RANGE_START < DEFAULT_PORT_RANGE_END
        assert DEFAULT_PORTS_PER_WORKER == 10


class TestDirectoryConstants:
    """Tests for directory path constants."""

    def test_state_dir(self) -> None:
        """Test state directory path."""
        assert STATE_DIR == ".zerg/state"

    def test_logs_dir(self) -> None:
        """Test logs directory path."""
        assert LOGS_DIR == ".zerg/logs"

    def test_worktrees_dir(self) -> None:
        """Test worktrees directory path."""
        assert WORKTREES_DIR == ".zerg-worktrees"

    def test_specs_dir(self) -> None:
        """Test specs directory path."""
        assert SPECS_DIR == ".gsd/specs"


class TestLevelNames:
    """Tests for level names mapping."""

    def test_level_names_mapping(self) -> None:
        """Test level names are correct."""
        assert LEVEL_NAMES[Level.FOUNDATION] == "foundation"
        assert LEVEL_NAMES[Level.CORE] == "core"
        assert LEVEL_NAMES[Level.INTEGRATION] == "integration"
        assert LEVEL_NAMES[Level.COMMANDS] == "commands"
        assert LEVEL_NAMES[Level.QUALITY] == "quality"
