"""Unit tests for ZERG worker_protocol module.

Tests the WorkerProtocol class and related components for worker-side
communication and task execution.
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from zerg.constants import DEFAULT_CONTEXT_THRESHOLD, ExitCode, TaskStatus
from zerg.protocol_state import WorkerProtocol, run_worker
from zerg.protocol_types import (
    CLAUDE_CLI_COMMAND,
    CLAUDE_CLI_DEFAULT_TIMEOUT,
    ClaudeInvocationResult,
    WorkerContext,
)


class TestClaudeInvocationResult:
    """Tests for ClaudeInvocationResult dataclass."""

    def test_creation_and_to_dict(self) -> None:
        """Test result creation and serialization."""
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
        assert isinstance(result.timestamp, datetime)

        data = result.to_dict()
        assert data["success"] is True
        assert data["task_id"] == "TASK-001"
        assert "timestamp" in data

    def test_to_dict_truncates_long_output(self) -> None:
        """Test that long stdout/stderr is truncated."""
        result = ClaudeInvocationResult(
            success=True,
            exit_code=0,
            stdout="x" * 2000,
            stderr="e" * 2000,
            duration_ms=100,
            task_id="TASK-001",
        )

        data = result.to_dict()
        assert len(data["stdout"]) == 1000
        assert len(data["stderr"]) == 1000


class TestWorkerContext:
    """Tests for WorkerContext dataclass."""

    def test_creation_defaults_and_custom(self) -> None:
        """Test creation with defaults and custom threshold."""
        ctx = WorkerContext(
            worker_id=1,
            feature="test-feature",
            worktree_path=Path("/tmp/worktree"),
            branch="zerg/test-feature/worker-1",
        )
        assert ctx.worker_id == 1
        assert ctx.context_threshold == DEFAULT_CONTEXT_THRESHOLD

        ctx2 = WorkerContext(
            worker_id=2,
            feature="custom",
            worktree_path=Path("/work"),
            branch="custom-branch",
            context_threshold=0.80,
        )
        assert ctx2.context_threshold == 0.80


# Common mock setup helper
def _make_protocol(
    mock_config_cls,
    mock_spec_loader_cls,
    mock_context_cls=None,
    mock_git_cls=None,
    mock_verifier_cls=None,
    mock_state_cls=None,
    **overrides,
):
    """Create a WorkerProtocol with standard mocks."""
    mock_config = MagicMock()
    mock_config.context_threshold = 0.70
    mock_config.plugins = MagicMock()
    mock_config.plugins.enabled = False
    mock_config.logging = MagicMock()
    mock_config_cls.load.return_value = mock_config

    mock_spec_loader = MagicMock()
    mock_spec_loader.specs_exist.return_value = overrides.get("specs_exist", False)
    if overrides.get("spec_context"):
        mock_spec_loader.load_and_format.return_value = overrides["spec_context"]
    mock_spec_loader_cls.return_value = mock_spec_loader

    return WorkerProtocol(
        worker_id=overrides.get("worker_id", 1),
        feature=overrides.get("feature", "test"),
        **{k: v for k, v in overrides.items() if k in ("task_graph_path",)},
    )


class TestWorkerProtocolInit:
    """Tests for WorkerProtocol initialization."""

    @patch("zerg.protocol_state.StateManager")
    @patch("zerg.protocol_state.VerificationExecutor")
    @patch("zerg.protocol_state.GitOps")
    @patch("zerg.protocol_state.ContextTracker")
    @patch("zerg.protocol_state.SpecLoader")
    @patch("zerg.protocol_state.ZergConfig")
    def test_init_with_explicit_args(self, mock_config_cls, mock_spec_loader_cls, *mocks) -> None:
        """Test initialization with explicit arguments."""
        protocol = _make_protocol(mock_config_cls, mock_spec_loader_cls, worker_id=3, feature="my-feature")
        assert protocol.worker_id == 3
        assert protocol.feature == "my-feature"

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
    @patch("zerg.protocol_state.StateManager")
    @patch("zerg.protocol_state.VerificationExecutor")
    @patch("zerg.protocol_state.GitOps")
    @patch("zerg.protocol_state.ContextTracker")
    @patch("zerg.protocol_state.SpecLoader")
    @patch("zerg.protocol_state.ZergConfig")
    def test_init_from_environment(self, mock_config_cls, mock_spec_loader_cls, *mocks) -> None:
        """Test initialization from environment variables."""
        protocol = _make_protocol(mock_config_cls, mock_spec_loader_cls, worker_id=5, feature="env-feature")
        # Re-create without explicit args to test env
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config
        mock_spec = MagicMock()
        mock_spec.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec
        protocol = WorkerProtocol()
        assert protocol.worker_id == 5
        assert protocol.feature == "env-feature"

    @patch.dict(os.environ, {}, clear=True)
    @patch("zerg.protocol_state.StateManager")
    @patch("zerg.protocol_state.VerificationExecutor")
    @patch("zerg.protocol_state.GitOps")
    @patch("zerg.protocol_state.ContextTracker")
    @patch("zerg.protocol_state.SpecLoader")
    @patch("zerg.protocol_state.ZergConfig")
    def test_init_defaults_when_no_env(self, mock_config_cls, mock_spec_loader_cls, *mocks) -> None:
        """Test initialization defaults when no environment vars set."""
        protocol = _make_protocol(mock_config_cls, mock_spec_loader_cls)
        # Defaults: worker_id=1 from helper, but without env the default should be 0
        mock_config = MagicMock()
        mock_config.context_threshold = 0.70
        mock_config.plugins = MagicMock()
        mock_config.plugins.enabled = False
        mock_config.logging = MagicMock()
        mock_config_cls.load.return_value = mock_config
        mock_spec = MagicMock()
        mock_spec.specs_exist.return_value = False
        mock_spec_loader_cls.return_value = mock_spec
        protocol = WorkerProtocol()
        assert protocol.worker_id == 0
        assert protocol.feature == "unknown"

    def test_init_task_parser_error_handled(self, tmp_path: Path) -> None:
        """Test that task parser errors are handled gracefully."""
        task_graph_path = tmp_path / "bad-graph.json"
        task_graph_path.write_text("invalid json {")

        with (
            patch("zerg.protocol_state.TaskParser") as mock_parser_cls,
            patch("zerg.protocol_state.StateManager"),
            patch("zerg.protocol_state.VerificationExecutor"),
            patch("zerg.protocol_state.GitOps"),
            patch("zerg.protocol_state.ContextTracker"),
            patch("zerg.protocol_state.SpecLoader") as mock_spec_loader_cls,
            patch("zerg.protocol_state.ZergConfig") as mock_config_cls,
        ):
            mock_parser = MagicMock()
            mock_parser.parse.side_effect = Exception("Parse error")
            mock_parser_cls.return_value = mock_parser

            protocol = _make_protocol(mock_config_cls, mock_spec_loader_cls, task_graph_path=task_graph_path)
            assert protocol.task_parser is None


class TestWorkerProtocolSignalReady:
    """Tests for signal_ready method."""

    @patch("zerg.protocol_state.StateManager")
    @patch("zerg.protocol_state.VerificationExecutor")
    @patch("zerg.protocol_state.GitOps")
    @patch("zerg.protocol_state.ContextTracker")
    @patch("zerg.protocol_state.SpecLoader")
    @patch("zerg.protocol_state.ZergConfig")
    def test_signal_ready(self, mock_config_cls, mock_spec_loader_cls, *mocks) -> None:
        """Test signaling ready status."""
        mock_state = MagicMock()
        mocks[-1].return_value = mock_state  # StateManager

        protocol = _make_protocol(mock_config_cls, mock_spec_loader_cls)
        protocol.signal_ready()
        assert protocol._is_ready is True


class TestWorkerProtocolClaimTask:
    """Tests for claim_next_task method."""

    @patch("zerg.protocol_state.StateManager")
    @patch("zerg.protocol_state.VerificationExecutor")
    @patch("zerg.protocol_state.GitOps")
    @patch("zerg.protocol_state.ContextTracker")
    @patch("zerg.protocol_state.SpecLoader")
    @patch("zerg.protocol_state.ZergConfig")
    def test_claim_next_task_success(self, mock_config_cls, mock_spec_loader_cls, *mocks) -> None:
        """Test successfully claiming a task."""
        mock_state = MagicMock()
        mock_state.get_tasks_by_status.return_value = ["TASK-001", "TASK-002"]
        mock_state.claim_task.return_value = True
        mocks[-1].return_value = mock_state

        protocol = _make_protocol(mock_config_cls, mock_spec_loader_cls)
        task = protocol.claim_next_task()
        assert task is not None
        assert task["id"] == "TASK-001"

    @patch("zerg.protocol_state.StateManager")
    @patch("zerg.protocol_state.VerificationExecutor")
    @patch("zerg.protocol_state.GitOps")
    @patch("zerg.protocol_state.ContextTracker")
    @patch("zerg.protocol_state.SpecLoader")
    @patch("zerg.protocol_state.ZergConfig")
    def test_claim_next_task_no_pending(self, mock_config_cls, mock_spec_loader_cls, *mocks) -> None:
        """Test claiming when no pending tasks."""
        mock_state = MagicMock()
        mock_state.get_tasks_by_status.return_value = []
        mocks[-1].return_value = mock_state

        protocol = _make_protocol(mock_config_cls, mock_spec_loader_cls)
        task = protocol.claim_next_task(max_wait=0)
        assert task is None


class TestWorkerProtocolBuildTaskPrompt:
    """Tests for _build_task_prompt method."""

    @patch("zerg.protocol_state.StateManager")
    @patch("zerg.protocol_state.VerificationExecutor")
    @patch("zerg.protocol_state.GitOps")
    @patch("zerg.protocol_state.ContextTracker")
    @patch("zerg.protocol_state.SpecLoader")
    @patch("zerg.protocol_state.ZergConfig")
    def test_build_task_prompt_basic(self, mock_config_cls, mock_spec_loader_cls, *mocks) -> None:
        """Test building basic task prompt."""
        protocol = _make_protocol(mock_config_cls, mock_spec_loader_cls)
        task = {"id": "TASK-001", "title": "Test Task", "level": 1}
        prompt = protocol._handler._build_task_prompt(task)
        assert "# Task: Test Task" in prompt
        assert "Do NOT commit" in prompt

    @patch("zerg.protocol_state.StateManager")
    @patch("zerg.protocol_state.VerificationExecutor")
    @patch("zerg.protocol_state.GitOps")
    @patch("zerg.protocol_state.ContextTracker")
    @patch("zerg.protocol_state.SpecLoader")
    @patch("zerg.protocol_state.ZergConfig")
    def test_build_task_prompt_with_files_and_verification(self, mock_config_cls, mock_spec_loader_cls, *mocks) -> None:
        """Test building prompt with file specs and verification."""
        protocol = _make_protocol(mock_config_cls, mock_spec_loader_cls)
        task = {
            "id": "TASK-001",
            "title": "Test Task",
            "level": 1,
            "files": {"create": ["new_file.py"], "modify": ["existing.py"], "read": ["reference.py"]},
            "verification": {"command": "pytest tests/"},
        }
        prompt = protocol._handler._build_task_prompt(task)
        assert "## Files" in prompt
        assert "Create: new_file.py" in prompt
        assert "## Verification" in prompt
        assert "pytest tests/" in prompt


class TestWorkerProtocolInvokeClaudeCode:
    """Tests for invoke_claude_code method."""

    @patch("zerg.protocol_handler.subprocess.run")
    @patch("zerg.protocol_state.StateManager")
    @patch("zerg.protocol_state.VerificationExecutor")
    @patch("zerg.protocol_state.GitOps")
    @patch("zerg.protocol_state.ContextTracker")
    @patch("zerg.protocol_state.SpecLoader")
    @patch("zerg.protocol_state.ZergConfig")
    def test_invoke_claude_code_success(self, mock_config_cls, mock_spec_loader_cls, *mocks) -> None:
        """Test successful Claude Code invocation."""
        mock_subprocess_run = mocks[-1]
        mock_subprocess_run.return_value = MagicMock(returncode=0, stdout="Task completed", stderr="")

        protocol = _make_protocol(mock_config_cls, mock_spec_loader_cls)
        task = {"id": "TASK-001", "title": "Test", "level": 1}
        result = protocol._handler.invoke_claude_code(task)

        assert result.success is True
        assert result.exit_code == 0

    @patch("zerg.protocol_handler.subprocess.run")
    @patch("zerg.protocol_state.StateManager")
    @patch("zerg.protocol_state.VerificationExecutor")
    @patch("zerg.protocol_state.GitOps")
    @patch("zerg.protocol_state.ContextTracker")
    @patch("zerg.protocol_state.SpecLoader")
    @patch("zerg.protocol_state.ZergConfig")
    def test_invoke_claude_code_errors(self, mock_config_cls, mock_spec_loader_cls, *mocks) -> None:
        """Test Claude Code invocation error handling for timeout, not found, and generic errors."""
        mock_subprocess_run = mocks[-1]

        cases = [
            (subprocess.TimeoutExpired(cmd=["claude"], timeout=30), "timed out"),
            (FileNotFoundError(), "not found"),
            (Exception("Unknown error"), "Unknown error"),
        ]

        protocol = _make_protocol(mock_config_cls, mock_spec_loader_cls)
        task = {"id": "TASK-001", "title": "Test", "level": 1}

        for side_effect, expected_stderr_substr in cases:
            mock_subprocess_run.side_effect = side_effect
            result = protocol._handler.invoke_claude_code(task, timeout=30)

            assert result.success is False
            assert result.exit_code == -1
            assert expected_stderr_substr in result.stderr


class TestWorkerProtocolRunVerification:
    """Tests for run_verification method."""

    @patch("zerg.protocol_state.StateManager")
    @patch("zerg.protocol_state.VerificationExecutor")
    @patch("zerg.protocol_state.GitOps")
    @patch("zerg.protocol_state.ContextTracker")
    @patch("zerg.protocol_state.SpecLoader")
    @patch("zerg.protocol_state.ZergConfig")
    def test_run_verification_success(self, mock_config_cls, mock_spec_loader_cls, *mocks) -> None:
        """Test successful verification."""
        mock_verifier = MagicMock()
        mock_verifier.verify_with_retry.return_value = MagicMock(success=True, duration_ms=500)
        mocks[-4].return_value = mock_verifier

        protocol = _make_protocol(mock_config_cls, mock_spec_loader_cls)
        task = {"id": "TASK-001", "verification": {"command": "pytest tests/", "timeout_seconds": 60}}
        result = protocol._handler.run_verification(task)
        assert result is True

    @patch("zerg.protocol_state.StateManager")
    @patch("zerg.protocol_state.VerificationExecutor")
    @patch("zerg.protocol_state.GitOps")
    @patch("zerg.protocol_state.ContextTracker")
    @patch("zerg.protocol_state.SpecLoader")
    @patch("zerg.protocol_state.ZergConfig")
    def test_run_verification_no_spec_auto_passes(self, mock_config_cls, mock_spec_loader_cls, *mocks) -> None:
        """Test verification auto-passes when no spec."""
        protocol = _make_protocol(mock_config_cls, mock_spec_loader_cls)
        task = {"id": "TASK-001", "title": "Test"}
        result = protocol._handler.run_verification(task)
        assert result is True


class TestWorkerProtocolCommitTaskChanges:
    """Tests for commit_task_changes method."""

    @patch("zerg.protocol_state.StateManager")
    @patch("zerg.protocol_state.VerificationExecutor")
    @patch("zerg.protocol_state.GitOps")
    @patch("zerg.protocol_state.ContextTracker")
    @patch("zerg.protocol_state.SpecLoader")
    @patch("zerg.protocol_state.ZergConfig")
    def test_commit_task_changes_success(self, mock_config_cls, mock_spec_loader_cls, *mocks) -> None:
        """Test successful commit."""
        mock_git = MagicMock()
        mock_git.has_changes.return_value = True
        mock_git.current_commit.side_effect = ["abc123", "def456"]
        mocks[-3].return_value = mock_git

        protocol = _make_protocol(mock_config_cls, mock_spec_loader_cls)
        task = {"id": "TASK-001", "title": "Test Task"}
        result = protocol._handler.commit_task_changes(task)
        assert result is True

    @patch("zerg.protocol_state.StateManager")
    @patch("zerg.protocol_state.VerificationExecutor")
    @patch("zerg.protocol_state.GitOps")
    @patch("zerg.protocol_state.ContextTracker")
    @patch("zerg.protocol_state.SpecLoader")
    @patch("zerg.protocol_state.ZergConfig")
    def test_commit_task_changes_no_changes(self, mock_config_cls, mock_spec_loader_cls, *mocks) -> None:
        """Test commit when no changes."""
        mock_git = MagicMock()
        mock_git.has_changes.return_value = False
        mocks[-3].return_value = mock_git

        protocol = _make_protocol(mock_config_cls, mock_spec_loader_cls)
        task = {"id": "TASK-001", "title": "Test Task"}
        result = protocol._handler.commit_task_changes(task)
        assert result is True


class TestWorkerProtocolExecuteTask:
    """Tests for execute_task method."""

    @patch("zerg.protocol_state.StateManager")
    @patch("zerg.protocol_state.VerificationExecutor")
    @patch("zerg.protocol_state.GitOps")
    @patch("zerg.protocol_state.ContextTracker")
    @patch("zerg.protocol_state.SpecLoader")
    @patch("zerg.protocol_state.ZergConfig")
    def test_execute_task_success(self, mock_config_cls, mock_spec_loader_cls, *mocks) -> None:
        """Test successful task execution."""
        protocol = _make_protocol(mock_config_cls, mock_spec_loader_cls)
        protocol._handler.invoke_claude_code = MagicMock(
            return_value=ClaudeInvocationResult(
                success=True, exit_code=0, stdout="done", stderr="", duration_ms=100, task_id="TASK-001"
            )
        )
        protocol._handler.run_verification = MagicMock(return_value=True)
        protocol._handler.commit_task_changes = MagicMock(return_value=True)

        task = {"id": "TASK-001", "title": "Test", "level": 1}
        result = protocol._handler.execute_task(task)
        assert result is True

    @patch("zerg.protocol_state.StateManager")
    @patch("zerg.protocol_state.VerificationExecutor")
    @patch("zerg.protocol_state.GitOps")
    @patch("zerg.protocol_state.ContextTracker")
    @patch("zerg.protocol_state.SpecLoader")
    @patch("zerg.protocol_state.ZergConfig")
    def test_execute_task_claude_failure(self, mock_config_cls, mock_spec_loader_cls, *mocks) -> None:
        """Test task execution when Claude Code fails."""
        protocol = _make_protocol(mock_config_cls, mock_spec_loader_cls)
        protocol._handler.invoke_claude_code = MagicMock(
            return_value=ClaudeInvocationResult(
                success=False, exit_code=1, stdout="", stderr="Error", duration_ms=100, task_id="TASK-001"
            )
        )

        task = {"id": "TASK-001", "title": "Test", "level": 1}
        result = protocol._handler.execute_task(task)
        assert result is False


class TestWorkerProtocolReporting:
    """Tests for report_complete and report_failed methods."""

    @patch("zerg.protocol_state.StateManager")
    @patch("zerg.protocol_state.VerificationExecutor")
    @patch("zerg.protocol_state.GitOps")
    @patch("zerg.protocol_state.ContextTracker")
    @patch("zerg.protocol_state.SpecLoader")
    @patch("zerg.protocol_state.ZergConfig")
    def test_report_complete(self, mock_config_cls, mock_spec_loader_cls, *mocks) -> None:
        """Test reporting task completion."""
        mock_state = MagicMock()
        mocks[-1].return_value = mock_state

        protocol = _make_protocol(mock_config_cls, mock_spec_loader_cls)
        protocol.current_task = {"id": "TASK-001"}
        protocol.report_complete("TASK-001")

        assert protocol.tasks_completed == 1
        assert protocol.current_task is None
        mock_state.set_task_status.assert_called_with("TASK-001", TaskStatus.COMPLETE, worker_id=1)

    @patch("zerg.protocol_state.StateManager")
    @patch("zerg.protocol_state.VerificationExecutor")
    @patch("zerg.protocol_state.GitOps")
    @patch("zerg.protocol_state.ContextTracker")
    @patch("zerg.protocol_state.SpecLoader")
    @patch("zerg.protocol_state.ZergConfig")
    def test_report_failed(self, mock_config_cls, mock_spec_loader_cls, *mocks) -> None:
        """Test reporting task failure."""
        mock_state = MagicMock()
        mocks[-1].return_value = mock_state

        protocol = _make_protocol(mock_config_cls, mock_spec_loader_cls)
        protocol.current_task = {"id": "TASK-001"}
        protocol.report_failed("TASK-001", "Something went wrong")

        assert protocol.current_task is None
        mock_state.set_task_status.assert_called_with(
            "TASK-001", TaskStatus.FAILED, worker_id=1, error="Something went wrong"
        )


class TestRunWorker:
    """Tests for run_worker function."""

    @patch("zerg.protocol_state.sys.exit")
    @patch("zerg.protocol_state.WorkerProtocol")
    def test_run_worker_success(self, mock_protocol_cls, mock_exit) -> None:
        """Test run_worker entry point."""
        mock_protocol = MagicMock()
        mock_protocol_cls.return_value = mock_protocol
        run_worker()
        mock_protocol.start.assert_called_once()

    @patch("zerg.protocol_state.sys.exit")
    @patch("zerg.protocol_state.WorkerProtocol")
    def test_run_worker_exception(self, mock_protocol_cls, mock_exit) -> None:
        """Test run_worker handles exceptions."""
        mock_protocol_cls.side_effect = Exception("Init failed")
        run_worker()
        mock_exit.assert_called_with(ExitCode.ERROR)


class TestModuleConstants:
    """Tests for module-level constants."""

    def test_default_timeout_and_cli_command(self) -> None:
        """Test module-level constants."""
        assert CLAUDE_CLI_DEFAULT_TIMEOUT == 1800
        assert CLAUDE_CLI_COMMAND == "claude"
