"""Comprehensive unit tests for ZERG worker_protocol module.

Tests the WorkerProtocol class and related components for worker-side
communication and task execution.
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from zerg.constants import DEFAULT_CONTEXT_THRESHOLD, ExitCode, TaskStatus
from zerg.worker_protocol import (
    CLAUDE_CLI_COMMAND,
    CLAUDE_CLI_DEFAULT_TIMEOUT,
    ClaudeInvocationResult,
    WorkerContext,
    WorkerProtocol,
    run_worker,
)


class TestClaudeInvocationResult:
    """Tests for ClaudeInvocationResult dataclass."""

    def test_creation(self) -> None:
        """Test result creation with all fields."""
        result = ClaudeInvocationResult(
            success=True,
            exit_code=0,
            stdout="output",
            stderr="",
            duration_ms=1000,
            task_id="TASK-001",
        )

        assert result.success is True
        assert result.exit_code == 0
        assert result.stdout == "output"
        assert result.stderr == ""
        assert result.duration_ms == 1000
        assert result.task_id == "TASK-001"
        assert isinstance(result.timestamp, datetime)

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        result = ClaudeInvocationResult(
            success=False,
            exit_code=1,
            stdout="out",
            stderr="err",
            duration_ms=500,
            task_id="TASK-002",
        )

        data = result.to_dict()

        assert data["success"] is False
        assert data["exit_code"] == 1
        assert data["stdout"] == "out"
        assert data["stderr"] == "err"
        assert data["duration_ms"] == 500
        assert data["task_id"] == "TASK-002"
        assert "timestamp" in data

    def test_to_dict_truncates_long_stdout(self) -> None:
        """Test that long stdout is truncated."""
        long_output = "x" * 2000
        result = ClaudeInvocationResult(
            success=True,
            exit_code=0,
            stdout=long_output,
            stderr="",
            duration_ms=100,
            task_id="TASK-001",
        )

        data = result.to_dict()

        assert len(data["stdout"]) == 1000

    def test_to_dict_truncates_long_stderr(self) -> None:
        """Test that long stderr is truncated."""
        long_error = "e" * 2000
        result = ClaudeInvocationResult(
            success=False,
            exit_code=1,
            stdout="",
            stderr=long_error,
            duration_ms=100,
            task_id="TASK-001",
        )

        data = result.to_dict()

        assert len(data["stderr"]) == 1000

    def test_to_dict_short_output_not_truncated(self) -> None:
        """Test that short outputs are not truncated."""
        result = ClaudeInvocationResult(
            success=True,
            exit_code=0,
            stdout="short",
            stderr="also short",
            duration_ms=100,
            task_id="TASK-001",
        )

        data = result.to_dict()

        assert data["stdout"] == "short"
        assert data["stderr"] == "also short"


class TestWorkerContext:
    """Tests for WorkerContext dataclass."""

    def test_creation_defaults(self) -> None:
        """Test creation with default threshold."""
        ctx = WorkerContext(
            worker_id=1,
            feature="test-feature",
            worktree_path=Path("/tmp/worktree"),
            branch="zerg/test-feature/worker-1",
        )

        assert ctx.worker_id == 1
        assert ctx.feature == "test-feature"
        assert ctx.worktree_path == Path("/tmp/worktree")
        assert ctx.branch == "zerg/test-feature/worker-1"
        assert ctx.context_threshold == DEFAULT_CONTEXT_THRESHOLD

    def test_creation_custom_threshold(self) -> None:
        """Test creation with custom threshold."""
        ctx = WorkerContext(
            worker_id=2,
            feature="custom",
            worktree_path=Path("/work"),
            branch="custom-branch",
            context_threshold=0.80,
        )

        assert ctx.context_threshold == 0.80


class TestWorkerProtocolInit:
    """Tests for WorkerProtocol initialization."""

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_init_with_explicit_args(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
        tmp_path: Path,
    ) -> None:
        """Test initialization with explicit arguments."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.75
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        protocol = WorkerProtocol(
            worker_id=3,
            feature="my-feature",
        )

        assert protocol.worker_id == 3
        assert protocol.feature == "my-feature"
        mock_state_cls.assert_called_with("my-feature", state_dir=None)

    @patch.dict(
        os.environ,
        {
            "ZERG_WORKER_ID": "5",
            "ZERG_FEATURE": "env-feature",
            "ZERG_BRANCH": "zerg/env-feature/worker-5",
            "ZERG_WORKTREE": "/tmp/test-worktree",
        },
        clear=False,
    )
    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_init_from_environment(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test initialization from environment variables."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        protocol = WorkerProtocol()

        assert protocol.worker_id == 5
        assert protocol.feature == "env-feature"
        assert protocol.branch == "zerg/env-feature/worker-5"
        assert protocol.worktree_path == Path("/tmp/test-worktree").resolve()

    @patch.dict(os.environ, {}, clear=True)
    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_init_defaults_when_no_env(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test initialization defaults when no environment vars set."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        protocol = WorkerProtocol()

        assert protocol.worker_id == 0
        assert protocol.feature == "unknown"

    @patch.dict(
        os.environ,
        {"ZERG_TASK_GRAPH": "/tmp/task-graph.json"},
        clear=False,
    )
    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    @patch("zerg.worker_protocol.TaskParser")
    def test_init_with_task_graph_env(
        self,
        mock_parser_cls,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
        tmp_path: Path,
    ) -> None:
        """Test initialization with task graph from environment."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        # Create fake task graph file
        task_graph_path = tmp_path / "task-graph.json"
        task_graph_path.write_text('{"feature": "test", "tasks": []}')

        with patch.dict(os.environ, {"ZERG_TASK_GRAPH": str(task_graph_path)}):
            protocol = WorkerProtocol()

        assert protocol.task_graph_path == Path(str(task_graph_path))

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    @patch("zerg.worker_protocol.TaskParser")
    def test_init_with_task_graph_arg(
        self,
        mock_parser_cls,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
        tmp_path: Path,
    ) -> None:
        """Test initialization with task graph path argument."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        # Create fake task graph file
        task_graph_path = tmp_path / "my-graph.json"
        task_graph_path.write_text('{"feature": "test", "tasks": []}')

        protocol = WorkerProtocol(
            worker_id=1,
            feature="test",
            task_graph_path=task_graph_path,
        )

        assert protocol.task_graph_path == task_graph_path
        mock_parser_cls.assert_called_once()

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    @patch("zerg.worker_protocol.TaskParser")
    def test_init_task_parser_error_handled(
        self,
        mock_parser_cls,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
        tmp_path: Path,
    ) -> None:
        """Test that task parser errors are handled gracefully."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        # Parser that raises exception
        mock_parser = MagicMock()
        mock_parser.parse.side_effect = Exception("Parse error")
        mock_parser_cls.return_value = mock_parser

        task_graph_path = tmp_path / "bad-graph.json"
        task_graph_path.write_text("invalid json {")

        # Should not raise
        protocol = WorkerProtocol(
            worker_id=1,
            feature="test",
            task_graph_path=task_graph_path,
        )

        # Parser should be set to None after error
        assert protocol.task_parser is None

    @patch.dict(os.environ, {"ZERG_SPEC_DIR": "/tmp/specs/myfeature"}, clear=False)
    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_init_with_spec_dir_env(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test initialization with ZERG_SPEC_DIR environment variable."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = True
        mock_spec_loader.load_and_format.return_value = "# Feature context"
        mock_spec_loader_cls.return_value = mock_spec_loader

        protocol = WorkerProtocol(worker_id=1, feature="test")

        # Spec loader should be initialized with parent of ZERG_SPEC_DIR
        mock_spec_loader_cls.assert_called()
        assert protocol._spec_context == "# Feature context"


class TestWorkerProtocolSignalReady:
    """Tests for signal_ready method."""

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_signal_ready(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test signaling ready status."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        protocol = WorkerProtocol(worker_id=1, feature="test")
        protocol.signal_ready()

        assert protocol._is_ready is True
        mock_state.set_worker_ready.assert_called_once_with(1)
        mock_state.append_event.assert_called()


class TestWorkerProtocolWaitForReady:
    """Tests for wait_for_ready method."""

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_wait_for_ready_already_ready(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test wait_for_ready when already ready."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        protocol = WorkerProtocol(worker_id=1, feature="test")
        protocol._is_ready = True

        result = protocol.wait_for_ready(timeout=0.1)

        assert result is True

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_wait_for_ready_timeout(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test wait_for_ready times out when not ready."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        protocol = WorkerProtocol(worker_id=1, feature="test")
        protocol._is_ready = False

        result = protocol.wait_for_ready(timeout=0.2)

        assert result is False

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_is_ready_property(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test is_ready property."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        protocol = WorkerProtocol(worker_id=1, feature="test")

        assert protocol.is_ready is False
        protocol._is_ready = True
        assert protocol.is_ready is True


class TestWorkerProtocolClaimTask:
    """Tests for claim_next_task method."""

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_claim_next_task_success(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test successfully claiming a task."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_state = MagicMock()
        mock_state.get_tasks_by_status.return_value = ["TASK-001", "TASK-002"]
        mock_state.claim_task.return_value = True
        mock_state_cls.return_value = mock_state

        protocol = WorkerProtocol(worker_id=1, feature="test")
        task = protocol.claim_next_task()

        assert task is not None
        assert task["id"] == "TASK-001"
        mock_state.claim_task.assert_called_with("TASK-001", 1)

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_claim_next_task_no_pending(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test claiming when no pending tasks."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_state = MagicMock()
        mock_state.get_tasks_by_status.return_value = []
        mock_state_cls.return_value = mock_state

        protocol = WorkerProtocol(worker_id=1, feature="test")
        task = protocol.claim_next_task(max_wait=0)

        assert task is None

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_claim_next_task_claim_fails(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test claiming when claim fails (already claimed by another worker)."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_state = MagicMock()
        mock_state.get_tasks_by_status.return_value = ["TASK-001"]
        mock_state.claim_task.return_value = False
        mock_state_cls.return_value = mock_state

        protocol = WorkerProtocol(worker_id=1, feature="test")
        task = protocol.claim_next_task(max_wait=0)

        assert task is None


class TestWorkerProtocolLoadTaskDetails:
    """Tests for _load_task_details method."""

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_load_task_details_from_parser(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test loading task details from task parser."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        protocol = WorkerProtocol(worker_id=1, feature="test")

        # Set up task parser mock
        mock_parser = MagicMock()
        mock_parser.get_task.return_value = {
            "id": "TASK-001",
            "title": "Test Task",
            "level": 1,
            "description": "A test task",
        }
        protocol.task_parser = mock_parser

        task = protocol._load_task_details("TASK-001")

        assert task["id"] == "TASK-001"
        assert task["title"] == "Test Task"
        mock_parser.get_task.assert_called_with("TASK-001")

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_load_task_details_fallback_stub(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test fallback to stub when task not in parser."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        protocol = WorkerProtocol(worker_id=1, feature="test")

        # Parser returns None
        mock_parser = MagicMock()
        mock_parser.get_task.return_value = None
        protocol.task_parser = mock_parser

        task = protocol._load_task_details("TASK-999")

        assert task["id"] == "TASK-999"
        assert task["title"] == "Task TASK-999"
        assert task["level"] == 1

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_load_task_details_no_parser(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test fallback stub when no parser available."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        protocol = WorkerProtocol(worker_id=1, feature="test")
        protocol.task_parser = None

        task = protocol._load_task_details("TASK-001")

        assert task["id"] == "TASK-001"
        assert task["level"] == 1


class TestWorkerProtocolBuildTaskPrompt:
    """Tests for _build_task_prompt method."""

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_build_task_prompt_basic(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test building basic task prompt."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        protocol = WorkerProtocol(worker_id=1, feature="test")

        task = {
            "id": "TASK-001",
            "title": "Test Task",
            "level": 1,
        }

        prompt = protocol._build_task_prompt(task)

        assert "# Task: Test Task" in prompt
        assert "Do NOT commit" in prompt

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_build_task_prompt_with_description(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test building prompt with description."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        protocol = WorkerProtocol(worker_id=1, feature="test")

        task = {
            "id": "TASK-001",
            "title": "Test Task",
            "level": 1,
            "description": "This is the task description",
        }

        prompt = protocol._build_task_prompt(task)

        assert "## Description" in prompt
        assert "This is the task description" in prompt

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_build_task_prompt_with_files(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test building prompt with file specifications."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        protocol = WorkerProtocol(worker_id=1, feature="test")

        task = {
            "id": "TASK-001",
            "title": "Test Task",
            "level": 1,
            "files": {
                "create": ["new_file.py"],
                "modify": ["existing.py"],
                "read": ["reference.py"],
            },
        }

        prompt = protocol._build_task_prompt(task)

        assert "## Files" in prompt
        assert "Create: new_file.py" in prompt
        assert "Modify: existing.py" in prompt
        assert "Reference: reference.py" in prompt

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_build_task_prompt_with_verification(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test building prompt with verification command."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        protocol = WorkerProtocol(worker_id=1, feature="test")

        task = {
            "id": "TASK-001",
            "title": "Test Task",
            "level": 1,
            "verification": {
                "command": "pytest tests/",
            },
        }

        prompt = protocol._build_task_prompt(task)

        assert "## Verification" in prompt
        assert "pytest tests/" in prompt

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_build_task_prompt_with_spec_context(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test building prompt with spec context prefix."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        protocol = WorkerProtocol(worker_id=1, feature="test")
        protocol._spec_context = "# Feature Context: test\n\nRequirements..."

        task = {
            "id": "TASK-001",
            "title": "Test Task",
            "level": 1,
        }

        prompt = protocol._build_task_prompt(task)

        assert prompt.startswith("# Feature Context: test")

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_build_task_prompt_uses_id_when_no_title(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test using task ID when title is missing."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        protocol = WorkerProtocol(worker_id=1, feature="test")

        task = {
            "id": "TASK-001",
            "level": 1,
        }

        prompt = protocol._build_task_prompt(task)

        assert "# Task: TASK-001" in prompt


class TestWorkerProtocolInvokeClaudeCode:
    """Tests for invoke_claude_code method."""

    @patch("zerg.worker_protocol.subprocess.run")
    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_invoke_claude_code_success(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
        mock_subprocess_run,
    ) -> None:
        """Test successful Claude Code invocation."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_subprocess_run.return_value = MagicMock(
            returncode=0,
            stdout="Task completed",
            stderr="",
        )

        protocol = WorkerProtocol(worker_id=1, feature="test")

        task = {"id": "TASK-001", "title": "Test", "level": 1}
        result = protocol.invoke_claude_code(task)

        assert result.success is True
        assert result.exit_code == 0
        assert result.stdout == "Task completed"
        assert result.task_id == "TASK-001"

    @patch("zerg.worker_protocol.subprocess.run")
    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_invoke_claude_code_failure(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
        mock_subprocess_run,
    ) -> None:
        """Test failed Claude Code invocation."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_subprocess_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error occurred",
        )

        protocol = WorkerProtocol(worker_id=1, feature="test")

        task = {"id": "TASK-001", "title": "Test", "level": 1}
        result = protocol.invoke_claude_code(task)

        assert result.success is False
        assert result.exit_code == 1
        assert "Error" in result.stderr

    @patch("zerg.worker_protocol.subprocess.run")
    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_invoke_claude_code_timeout(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
        mock_subprocess_run,
    ) -> None:
        """Test Claude Code invocation timeout."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_subprocess_run.side_effect = subprocess.TimeoutExpired(cmd=["claude"], timeout=30)

        protocol = WorkerProtocol(worker_id=1, feature="test")

        task = {"id": "TASK-001", "title": "Test", "level": 1}
        result = protocol.invoke_claude_code(task, timeout=30)

        assert result.success is False
        assert result.exit_code == -1
        assert "timed out" in result.stderr

    @patch("zerg.worker_protocol.subprocess.run")
    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_invoke_claude_code_not_found(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
        mock_subprocess_run,
    ) -> None:
        """Test Claude CLI not found."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_subprocess_run.side_effect = FileNotFoundError()

        protocol = WorkerProtocol(worker_id=1, feature="test")

        task = {"id": "TASK-001", "title": "Test", "level": 1}
        result = protocol.invoke_claude_code(task)

        assert result.success is False
        assert result.exit_code == -1
        assert "not found" in result.stderr

    @patch("zerg.worker_protocol.subprocess.run")
    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_invoke_claude_code_generic_exception(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
        mock_subprocess_run,
    ) -> None:
        """Test generic exception during Claude Code invocation."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_subprocess_run.side_effect = Exception("Unknown error")

        protocol = WorkerProtocol(worker_id=1, feature="test")

        task = {"id": "TASK-001", "title": "Test", "level": 1}
        result = protocol.invoke_claude_code(task)

        assert result.success is False
        assert result.exit_code == -1
        assert "Unknown error" in result.stderr

    @patch("zerg.worker_protocol.subprocess.run")
    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_invoke_claude_code_custom_timeout(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
        mock_subprocess_run,
    ) -> None:
        """Test Claude Code invocation with custom timeout."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_subprocess_run.return_value = MagicMock(
            returncode=0,
            stdout="done",
            stderr="",
        )

        protocol = WorkerProtocol(worker_id=1, feature="test")

        task = {"id": "TASK-001", "title": "Test", "level": 1}
        protocol.invoke_claude_code(task, timeout=600)

        # Verify timeout was passed
        call_kwargs = mock_subprocess_run.call_args[1]
        assert call_kwargs["timeout"] == 600


class TestWorkerProtocolRunVerification:
    """Tests for run_verification method."""

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_run_verification_success(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test successful verification."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_verifier = MagicMock()
        mock_verifier.verify_with_retry.return_value = MagicMock(
            success=True,
            duration_ms=500,
        )
        mock_verifier_cls.return_value = mock_verifier

        protocol = WorkerProtocol(worker_id=1, feature="test")

        task = {
            "id": "TASK-001",
            "verification": {
                "command": "pytest tests/",
                "timeout_seconds": 60,
            },
        }

        result = protocol.run_verification(task)

        assert result is True
        mock_verifier.verify_with_retry.assert_called_once()

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_run_verification_failure(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test failed verification."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_verifier = MagicMock()
        mock_verifier.verify_with_retry.return_value = MagicMock(
            success=False,
            stderr="Test failed",
            exit_code=1,
        )
        mock_verifier_cls.return_value = mock_verifier

        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        protocol = WorkerProtocol(worker_id=1, feature="test")

        task = {
            "id": "TASK-001",
            "verification": {"command": "pytest tests/"},
        }

        result = protocol.run_verification(task)

        assert result is False
        mock_state.append_event.assert_called()

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_run_verification_no_verification_spec(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test verification auto-passes when no spec."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        protocol = WorkerProtocol(worker_id=1, feature="test")

        task = {"id": "TASK-001", "title": "Test"}

        result = protocol.run_verification(task)

        assert result is True

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_run_verification_empty_command(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test verification auto-passes when command is empty."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        protocol = WorkerProtocol(worker_id=1, feature="test")

        task = {
            "id": "TASK-001",
            "verification": {"command": ""},
        }

        result = protocol.run_verification(task)

        assert result is True


class TestWorkerProtocolCommitTaskChanges:
    """Tests for commit_task_changes method."""

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_commit_task_changes_success(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test successful commit."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_git = MagicMock()
        mock_git.has_changes.return_value = True
        # BF-009: HEAD must change after commit
        mock_git.current_commit.side_effect = ["abc123", "def456"]
        mock_git_cls.return_value = mock_git

        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        protocol = WorkerProtocol(worker_id=1, feature="test")

        task = {"id": "TASK-001", "title": "Test Task"}
        result = protocol.commit_task_changes(task)

        assert result is True
        mock_git.commit.assert_called_once()
        call_args = mock_git.commit.call_args
        assert "TASK-001" in call_args[0][0]
        assert call_args[1]["add_all"] is True

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_commit_task_changes_no_changes(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test commit when no changes."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_git = MagicMock()
        mock_git.has_changes.return_value = False
        mock_git_cls.return_value = mock_git

        protocol = WorkerProtocol(worker_id=1, feature="test")

        task = {"id": "TASK-001", "title": "Test Task"}
        result = protocol.commit_task_changes(task)

        assert result is True
        mock_git.commit.assert_not_called()

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_commit_task_changes_exception(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test commit failure handling."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_git = MagicMock()
        mock_git.has_changes.return_value = True
        mock_git.commit.side_effect = Exception("Commit failed")
        mock_git_cls.return_value = mock_git

        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        protocol = WorkerProtocol(worker_id=1, feature="test")

        task = {"id": "TASK-001", "title": "Test Task"}
        result = protocol.commit_task_changes(task)

        assert result is False
        mock_state.append_event.assert_called()


class TestWorkerProtocolExecuteTask:
    """Tests for execute_task method."""

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_execute_task_success(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test successful task execution."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        mock_git = MagicMock()
        mock_git.has_changes.return_value = True
        mock_git_cls.return_value = mock_git

        mock_context = MagicMock()
        mock_context_cls.return_value = mock_context

        protocol = WorkerProtocol(worker_id=1, feature="test")

        # Mock the internal methods
        protocol.invoke_claude_code = MagicMock(
            return_value=ClaudeInvocationResult(
                success=True,
                exit_code=0,
                stdout="done",
                stderr="",
                duration_ms=100,
                task_id="TASK-001",
            )
        )
        protocol.run_verification = MagicMock(return_value=True)
        protocol.commit_task_changes = MagicMock(return_value=True)

        task = {"id": "TASK-001", "title": "Test", "level": 1}
        result = protocol.execute_task(task)

        assert result is True
        mock_state.set_task_status.assert_called()
        mock_context.track_task_execution.assert_called_with("TASK-001")

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_execute_task_claude_failure(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test task execution when Claude Code fails."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        protocol = WorkerProtocol(worker_id=1, feature="test")

        protocol.invoke_claude_code = MagicMock(
            return_value=ClaudeInvocationResult(
                success=False,
                exit_code=1,
                stdout="",
                stderr="Error",
                duration_ms=100,
                task_id="TASK-001",
            )
        )

        task = {"id": "TASK-001", "title": "Test", "level": 1}
        result = protocol.execute_task(task)

        assert result is False
        mock_state.append_event.assert_called()

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_execute_task_verification_failure(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test task execution when verification fails."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        protocol = WorkerProtocol(worker_id=1, feature="test")

        protocol.invoke_claude_code = MagicMock(
            return_value=ClaudeInvocationResult(
                success=True,
                exit_code=0,
                stdout="done",
                stderr="",
                duration_ms=100,
                task_id="TASK-001",
            )
        )
        protocol.run_verification = MagicMock(return_value=False)

        task = {
            "id": "TASK-001",
            "title": "Test",
            "level": 1,
            "verification": {"command": "pytest"},
        }
        result = protocol.execute_task(task)

        assert result is False

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_execute_task_commit_failure(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test task execution when commit fails."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        protocol = WorkerProtocol(worker_id=1, feature="test")

        protocol.invoke_claude_code = MagicMock(
            return_value=ClaudeInvocationResult(
                success=True,
                exit_code=0,
                stdout="done",
                stderr="",
                duration_ms=100,
                task_id="TASK-001",
            )
        )
        protocol.run_verification = MagicMock(return_value=True)
        protocol.commit_task_changes = MagicMock(return_value=False)

        task = {"id": "TASK-001", "title": "Test", "level": 1}
        result = protocol.execute_task(task)

        assert result is False

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_execute_task_exception(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test task execution handles exceptions."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        protocol = WorkerProtocol(worker_id=1, feature="test")

        protocol.invoke_claude_code = MagicMock(side_effect=Exception("Boom"))

        task = {"id": "TASK-001", "title": "Test", "level": 1}
        result = protocol.execute_task(task)

        assert result is False
        mock_state.append_event.assert_called()


class TestWorkerProtocolReporting:
    """Tests for report_complete and report_failed methods."""

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_report_complete(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test reporting task completion."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        protocol = WorkerProtocol(worker_id=1, feature="test")
        protocol.current_task = {"id": "TASK-001"}

        protocol.report_complete("TASK-001")

        assert protocol.tasks_completed == 1
        assert protocol.current_task is None
        mock_state.set_task_status.assert_called_with("TASK-001", TaskStatus.COMPLETE, worker_id=1)
        mock_state.append_event.assert_called()

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_report_failed(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test reporting task failure."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        protocol = WorkerProtocol(worker_id=1, feature="test")
        protocol.current_task = {"id": "TASK-001"}

        protocol.report_failed("TASK-001", "Something went wrong")

        assert protocol.current_task is None
        mock_state.set_task_status.assert_called_with(
            "TASK-001", TaskStatus.FAILED, worker_id=1, error="Something went wrong"
        )


class TestWorkerProtocolContextTracking:
    """Tests for context tracking methods."""

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_check_context_usage(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test checking context usage."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_context = MagicMock()
        mock_usage = MagicMock()
        mock_usage.usage_percent = 65.0
        mock_context.get_usage.return_value = mock_usage
        mock_context_cls.return_value = mock_context

        protocol = WorkerProtocol(worker_id=1, feature="test")
        usage = protocol.check_context_usage()

        assert usage == 0.65

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_should_checkpoint(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test should_checkpoint delegation."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_context = MagicMock()
        mock_context.should_checkpoint.return_value = True
        mock_context_cls.return_value = mock_context

        protocol = WorkerProtocol(worker_id=1, feature="test")
        result = protocol.should_checkpoint()

        assert result is True
        mock_context.should_checkpoint.assert_called_once()

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_track_file_read(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test tracking file reads."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_context = MagicMock()
        mock_context_cls.return_value = mock_context

        protocol = WorkerProtocol(worker_id=1, feature="test")
        protocol.track_file_read("/path/to/file.py", size=1000)

        mock_context.track_file_read.assert_called_with("/path/to/file.py", 1000)

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_track_tool_call(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test tracking tool calls."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_context = MagicMock()
        mock_context_cls.return_value = mock_context

        protocol = WorkerProtocol(worker_id=1, feature="test")
        protocol.track_tool_call()

        mock_context.track_tool_call.assert_called_once()


class TestWorkerProtocolCheckpointAndExit:
    """Tests for checkpoint_and_exit method."""

    @patch("zerg.worker_protocol.sys.exit")
    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_checkpoint_and_exit_with_changes(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
        mock_exit,
    ) -> None:
        """Test checkpoint and exit with pending changes."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_git = MagicMock()
        mock_git.has_changes.return_value = True
        mock_git_cls.return_value = mock_git

        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        protocol = WorkerProtocol(worker_id=1, feature="test")
        protocol.current_task = {"id": "TASK-001"}
        protocol.tasks_completed = 3

        protocol.checkpoint_and_exit()

        mock_git.commit.assert_called_once()
        assert "WIP" in mock_git.commit.call_args[0][0]
        mock_state.set_task_status.assert_called()
        mock_state.append_event.assert_called()
        mock_exit.assert_called_with(ExitCode.CHECKPOINT)

    @patch("zerg.worker_protocol.sys.exit")
    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_checkpoint_and_exit_no_changes(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
        mock_exit,
    ) -> None:
        """Test checkpoint and exit without pending changes."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_git = MagicMock()
        mock_git.has_changes.return_value = False
        mock_git_cls.return_value = mock_git

        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        protocol = WorkerProtocol(worker_id=1, feature="test")
        protocol.current_task = None

        protocol.checkpoint_and_exit()

        mock_git.commit.assert_not_called()
        mock_exit.assert_called_with(ExitCode.CHECKPOINT)

    @patch("zerg.worker_protocol.sys.exit")
    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_checkpoint_and_exit_no_current_task(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
        mock_exit,
    ) -> None:
        """Test checkpoint when no current task."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_git = MagicMock()
        mock_git.has_changes.return_value = True
        mock_git_cls.return_value = mock_git

        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        protocol = WorkerProtocol(worker_id=1, feature="test")
        protocol.current_task = None

        protocol.checkpoint_and_exit()

        # Should commit with "no-task" reference
        assert "no-task" in mock_git.commit.call_args[0][0]


class TestWorkerProtocolGetStatus:
    """Tests for get_status method."""

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_get_status(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test getting worker status."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_context = MagicMock()
        mock_usage = MagicMock()
        mock_usage.usage_percent = 50.0
        mock_context.get_usage.return_value = mock_usage
        mock_context_cls.return_value = mock_context

        protocol = WorkerProtocol(worker_id=1, feature="test")
        protocol.tasks_completed = 5
        protocol.current_task = {"id": "TASK-003"}
        protocol._started_at = datetime(2024, 1, 1, 12, 0, 0)

        status = protocol.get_status()

        assert status["worker_id"] == 1
        assert status["feature"] == "test"
        assert status["tasks_completed"] == 5
        assert status["current_task"] == "TASK-003"
        assert status["context_usage"] == 0.5
        assert status["started_at"] == "2024-01-01T12:00:00"

    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_get_status_no_current_task(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
    ) -> None:
        """Test status when no current task."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_context = MagicMock()
        mock_usage = MagicMock()
        mock_usage.usage_percent = 30.0
        mock_context.get_usage.return_value = mock_usage
        mock_context_cls.return_value = mock_context

        protocol = WorkerProtocol(worker_id=1, feature="test")
        protocol.current_task = None
        protocol._started_at = None

        status = protocol.get_status()

        assert status["current_task"] is None
        assert status["started_at"] is None


class TestWorkerProtocolStart:
    """Tests for start method (main execution loop)."""

    @patch("zerg.worker_protocol.time")
    @patch("zerg.worker_protocol.sys.exit")
    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_start_no_tasks(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
        mock_exit,
        mock_time,
    ) -> None:
        """Test start when no tasks available."""
        # Make time.time() return values that quickly exceed max_wait
        call_count = 0

        def mock_time_fn():
            nonlocal call_count
            call_count += 1
            return call_count * 200.0

        mock_time.time.side_effect = mock_time_fn
        mock_time.sleep = MagicMock()

        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_context = MagicMock()
        mock_context.should_checkpoint.return_value = False
        mock_context_cls.return_value = mock_context

        mock_state = MagicMock()
        mock_state.get_tasks_by_status.return_value = []
        mock_state_cls.return_value = mock_state

        protocol = WorkerProtocol(worker_id=1, feature="test")
        protocol.start()

        mock_exit.assert_called_with(ExitCode.SUCCESS)

    @patch("zerg.worker_protocol.time")
    @patch("zerg.worker_protocol.sys.exit")
    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_start_executes_tasks(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
        mock_exit,
        mock_time,
    ) -> None:
        """Test start executes available tasks."""
        # Make time.time() return values that quickly exceed max_wait
        call_count = 0

        def mock_time_fn():
            nonlocal call_count
            call_count += 1
            return call_count * 200.0

        mock_time.time.side_effect = mock_time_fn
        mock_time.sleep = MagicMock()

        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_context = MagicMock()
        mock_context.should_checkpoint.return_value = False
        mock_context_cls.return_value = mock_context

        mock_state = MagicMock()

        # First call returns tasks, subsequent calls return empty (infinite iterator)
        def get_tasks_side_effect(*args):
            if not hasattr(get_tasks_side_effect, "called"):
                get_tasks_side_effect.called = True
                return ["TASK-001"]
            return []

        mock_state.get_tasks_by_status.side_effect = get_tasks_side_effect
        mock_state.claim_task.return_value = True
        mock_state_cls.return_value = mock_state

        protocol = WorkerProtocol(worker_id=1, feature="test")

        # Mock execute_task to succeed
        protocol.execute_task = MagicMock(return_value=True)

        protocol.start()

        protocol.execute_task.assert_called_once()
        mock_exit.assert_called_with(ExitCode.SUCCESS)

    @patch("zerg.worker_protocol.time")
    @patch("zerg.worker_protocol.sys.exit")
    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_start_task_execution_failure(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
        mock_exit,
        mock_time,
    ) -> None:
        """Test start handles task execution failure and calls report_failed."""
        # Make time.time() return values that quickly exceed max_wait
        call_count = 0

        def mock_time_fn():
            nonlocal call_count
            call_count += 1
            return call_count * 200.0

        mock_time.time.side_effect = mock_time_fn
        mock_time.sleep = MagicMock()

        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_context = MagicMock()
        mock_context.should_checkpoint.return_value = False
        mock_context_cls.return_value = mock_context

        mock_state = MagicMock()

        # First call returns task, subsequent calls return empty (infinite iterator)
        def get_tasks_side_effect(*args):
            if not hasattr(get_tasks_side_effect, "called"):
                get_tasks_side_effect.called = True
                return ["TASK-001"]
            return []

        mock_state.get_tasks_by_status.side_effect = get_tasks_side_effect
        mock_state.claim_task.return_value = True
        mock_state_cls.return_value = mock_state

        protocol = WorkerProtocol(worker_id=1, feature="test")

        # Mock execute_task to FAIL - this triggers line 183
        protocol.execute_task = MagicMock(return_value=False)
        # Mock report_failed to verify it gets called
        protocol.report_failed = MagicMock()

        protocol.start()

        # Verify execute_task was called
        protocol.execute_task.assert_called_once()
        # Verify report_failed was called with the task ID and error message
        protocol.report_failed.assert_called_once_with("TASK-001", "Task execution failed")
        mock_exit.assert_called_with(ExitCode.SUCCESS)

    @patch("zerg.worker_protocol.sys.exit")
    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.ZergConfig")
    def test_start_checkpoints_on_high_context(
        self,
        mock_config_cls,
        mock_spec_loader_cls,
        mock_context_cls,
        mock_git_cls,
        mock_verifier_cls,
        mock_state_cls,
        mock_exit,
    ) -> None:
        """Test start checkpoints when context threshold exceeded."""
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config

        mock_spec_loader = MagicMock()
        mock_spec_loader.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec_loader

        mock_context = MagicMock()
        mock_context.should_checkpoint.return_value = True
        mock_context_cls.return_value = mock_context

        mock_git = MagicMock()
        mock_git.has_changes.return_value = False
        mock_git_cls.return_value = mock_git

        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        protocol = WorkerProtocol(worker_id=1, feature="test")
        protocol.start()

        mock_exit.assert_called_with(ExitCode.CHECKPOINT)


class TestRunWorker:
    """Tests for run_worker function."""

    @patch("zerg.worker_protocol.sys.exit")
    @patch("zerg.worker_protocol.WorkerProtocol")
    def test_run_worker_success(self, mock_protocol_cls, mock_exit) -> None:
        """Test run_worker entry point."""
        mock_protocol = MagicMock()
        mock_protocol_cls.return_value = mock_protocol

        run_worker()

        mock_protocol_cls.assert_called_once()
        mock_protocol.start.assert_called_once()

    @patch("zerg.worker_protocol.sys.exit")
    @patch("zerg.worker_protocol.WorkerProtocol")
    def test_run_worker_exception(self, mock_protocol_cls, mock_exit) -> None:
        """Test run_worker handles exceptions."""
        mock_protocol_cls.side_effect = Exception("Init failed")

        run_worker()

        mock_exit.assert_called_with(ExitCode.ERROR)


class TestModuleConstants:
    """Tests for module-level constants."""

    def test_default_timeout(self) -> None:
        """Test default Claude CLI timeout."""
        assert CLAUDE_CLI_DEFAULT_TIMEOUT == 1800

    def test_cli_command(self) -> None:
        """Test Claude CLI command name."""
        assert CLAUDE_CLI_COMMAND == "claude"
