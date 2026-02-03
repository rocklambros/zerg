"""Extended integration tests for worker protocol (TC-020).

Tests worker protocol operations including task execution and completion reporting.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.constants import TaskStatus
from zerg.worker_protocol import (
    ClaudeInvocationResult,
    WorkerContext,
    WorkerProtocol,
)


@pytest.fixture
def worker_env(tmp_path: Path, monkeypatch):
    """Set up worker environment."""
    monkeypatch.chdir(tmp_path)

    # Create state directory
    (tmp_path / ".zerg").mkdir()

    # Set environment variables
    monkeypatch.setenv("ZERG_WORKER_ID", "0")
    monkeypatch.setenv("ZERG_FEATURE", "test-feature")
    monkeypatch.setenv("ZERG_BRANCH", "zerg/test-feature/worker-0")
    monkeypatch.setenv("ZERG_WORKTREE", str(tmp_path))

    # Create task graph with correct format
    task_graph = {
        "feature": "test-feature",
        "tasks": [
            {
                "id": "TASK-001",
                "title": "Test task 1",
                "level": 1,
                "files": ["src/a.py"],
                "verification": "pytest tests/test_a.py",
            },
            {
                "id": "TASK-002",
                "title": "Test task 2",
                "level": 1,
                "files": ["src/b.py"],
                "verification": "pytest tests/test_b.py",
            },
        ],
    }
    task_graph_path = tmp_path / ".zerg" / "task-graph.json"
    task_graph_path.write_text(json.dumps(task_graph))
    monkeypatch.setenv("ZERG_TASK_GRAPH", str(task_graph_path))

    # Initialize git repo
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "Initial"], cwd=tmp_path, check=True)

    return tmp_path


class TestWorkerContext:
    """Tests for WorkerContext dataclass."""

    def test_context_creation(self, tmp_path: Path) -> None:
        """Test creating worker context."""
        ctx = WorkerContext(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="zerg/test/worker-0",
        )

        assert ctx.worker_id == 0
        assert ctx.feature == "test-feature"
        assert ctx.worktree_path == tmp_path
        assert ctx.branch == "zerg/test/worker-0"

    def test_context_default_threshold(self, tmp_path: Path) -> None:
        """Test default context threshold."""
        ctx = WorkerContext(
            worker_id=0,
            feature="test",
            worktree_path=tmp_path,
            branch="test",
        )

        assert ctx.context_threshold == 0.7


class TestClaudeInvocationResult:
    """Tests for ClaudeInvocationResult dataclass."""

    def test_result_creation(self) -> None:
        """Test creating invocation result."""
        result = ClaudeInvocationResult(
            success=True,
            exit_code=0,
            stdout="Output",
            stderr="",
            duration_ms=1000,
            task_id="TASK-001",
        )

        assert result.success is True
        assert result.exit_code == 0
        assert result.duration_ms == 1000

    def test_result_to_dict(self) -> None:
        """Test converting result to dict."""
        result = ClaudeInvocationResult(
            success=True,
            exit_code=0,
            stdout="Output",
            stderr="",
            duration_ms=1000,
            task_id="TASK-001",
        )

        data = result.to_dict()

        assert data["success"] is True
        assert data["task_id"] == "TASK-001"
        assert "timestamp" in data

    def test_result_truncates_long_output(self) -> None:
        """Test long output is truncated in dict."""
        long_output = "x" * 2000
        result = ClaudeInvocationResult(
            success=True,
            exit_code=0,
            stdout=long_output,
            stderr="",
            duration_ms=1000,
            task_id="TASK-001",
        )

        data = result.to_dict()

        assert len(data["stdout"]) == 1000


class TestWorkerProtocolInit:
    """Tests for WorkerProtocol initialization."""

    def test_init_from_environment(self, worker_env: Path) -> None:
        """Test initialization from environment variables."""
        with patch("zerg.worker_protocol.ZergConfig") as config_mock:
            config = MagicMock()
            config.context_threshold = 0.7
            config_mock.load.return_value = config

            protocol = WorkerProtocol()

            assert protocol.worker_id == 0
            assert protocol.feature == "test-feature"
            assert protocol.worktree_path == worker_env

    def test_init_with_explicit_values(self, worker_env: Path) -> None:
        """Test initialization with explicit values."""
        with patch("zerg.worker_protocol.ZergConfig") as config_mock:
            config = MagicMock()
            config.context_threshold = 0.7
            config_mock.load.return_value = config

            protocol = WorkerProtocol(
                worker_id=5,
                feature="explicit-feature",
            )

            assert protocol.worker_id == 5
            assert protocol.feature == "explicit-feature"


class TestWorkerReadiness:
    """Tests for worker ready signaling."""

    def test_signal_ready(self, worker_env: Path) -> None:
        """Test signaling ready state."""
        with (
            patch("zerg.worker_protocol.ZergConfig") as config_mock,
            patch("zerg.worker_protocol.StateManager") as state_mock,
        ):
            config = MagicMock()
            config.context_threshold = 0.7
            config_mock.load.return_value = config

            state = MagicMock()
            state_mock.return_value = state

            protocol = WorkerProtocol()
            protocol.signal_ready()

            assert protocol.is_ready is True
            state.set_worker_ready.assert_called_with(0)

    def test_ready_event_logged(self, worker_env: Path) -> None:
        """Test ready event is logged."""
        with (
            patch("zerg.worker_protocol.ZergConfig") as config_mock,
            patch("zerg.worker_protocol.StateManager") as state_mock,
        ):
            config = MagicMock()
            config.context_threshold = 0.7
            config_mock.load.return_value = config

            state = MagicMock()
            state_mock.return_value = state

            protocol = WorkerProtocol()
            protocol.signal_ready()

            state.append_event.assert_called()

    def test_wait_for_ready(self, worker_env: Path) -> None:
        """Test waiting for ready state."""
        with patch("zerg.worker_protocol.ZergConfig") as config_mock, patch("zerg.worker_protocol.StateManager"):
            config = MagicMock()
            config.context_threshold = 0.7
            config_mock.load.return_value = config

            protocol = WorkerProtocol()
            protocol._is_ready = True

            result = protocol.wait_for_ready(timeout=1.0)

            assert result is True


class TestTaskClaiming:
    """Tests for task claiming."""

    def test_claim_next_task(self, worker_env: Path) -> None:
        """Test claiming next available task."""
        with (
            patch("zerg.worker_protocol.ZergConfig") as config_mock,
            patch("zerg.worker_protocol.StateManager") as state_mock,
        ):
            config = MagicMock()
            config.context_threshold = 0.7
            config_mock.load.return_value = config

            state = MagicMock()
            state.get_tasks_by_status.return_value = ["TASK-001", "TASK-002"]
            state.claim_task.return_value = True
            state_mock.return_value = state

            protocol = WorkerProtocol()
            task = protocol.claim_next_task()

            assert task is not None
            assert task["id"] == "TASK-001"

    def test_claim_returns_none_when_no_tasks(self, worker_env: Path) -> None:
        """Test claim returns None when no tasks available."""
        with (
            patch("zerg.worker_protocol.ZergConfig") as config_mock,
            patch("zerg.worker_protocol.StateManager") as state_mock,
        ):
            config = MagicMock()
            config.context_threshold = 0.7
            config_mock.load.return_value = config

            state = MagicMock()
            state.get_tasks_by_status.return_value = []
            state_mock.return_value = state

            protocol = WorkerProtocol()
            task = protocol.claim_next_task(max_wait=0.1)

            assert task is None

    def test_claim_tries_multiple_tasks(self, worker_env: Path) -> None:
        """Test claiming tries multiple tasks if first fails."""
        with (
            patch("zerg.worker_protocol.ZergConfig") as config_mock,
            patch("zerg.worker_protocol.StateManager") as state_mock,
        ):
            config = MagicMock()
            config.context_threshold = 0.7
            config_mock.load.return_value = config

            state = MagicMock()
            state.get_tasks_by_status.return_value = ["TASK-001", "TASK-002"]
            # First claim fails, second succeeds
            state.claim_task.side_effect = [False, True]
            state_mock.return_value = state

            protocol = WorkerProtocol()
            task = protocol.claim_next_task()

            assert task is not None
            assert task["id"] == "TASK-002"


class TestTaskExecution:
    """Tests for task execution."""

    def test_execute_task_updates_status(self, worker_env: Path) -> None:
        """Test task execution updates status."""
        with (
            patch("zerg.worker_protocol.ZergConfig") as config_mock,
            patch("zerg.worker_protocol.StateManager") as state_mock,
            patch.object(WorkerProtocol, "invoke_claude_code") as invoke_mock,
            patch.object(WorkerProtocol, "run_verification") as verify_mock,
        ):
            config = MagicMock()
            config.context_threshold = 0.7
            config_mock.load.return_value = config

            state = MagicMock()
            state_mock.return_value = state

            invoke_result = ClaudeInvocationResult(
                success=True, exit_code=0, stdout="", stderr="", duration_ms=1000, task_id="TASK-001"
            )
            invoke_mock.return_value = invoke_result
            verify_mock.return_value = True

            protocol = WorkerProtocol()
            task = {"id": "TASK-001", "title": "Test", "verification": "true"}

            protocol.execute_task(task)

            state.set_task_status.assert_called()

    def test_execute_task_runs_verification(self, worker_env: Path) -> None:
        """Test task execution runs verification."""
        with (
            patch("zerg.worker_protocol.ZergConfig") as config_mock,
            patch("zerg.worker_protocol.StateManager") as state_mock,
            patch.object(WorkerProtocol, "invoke_claude_code") as invoke_mock,
            patch.object(WorkerProtocol, "run_verification") as verify_mock,
        ):
            config = MagicMock()
            config.context_threshold = 0.7
            config_mock.load.return_value = config

            state = MagicMock()
            state_mock.return_value = state

            invoke_result = ClaudeInvocationResult(
                success=True, exit_code=0, stdout="", stderr="", duration_ms=1000, task_id="TASK-001"
            )
            invoke_mock.return_value = invoke_result
            verify_mock.return_value = True

            protocol = WorkerProtocol()
            task = {"id": "TASK-001", "title": "Test", "verification": "pytest"}

            protocol.execute_task(task)

            verify_mock.assert_called_once()
            call_args = verify_mock.call_args
            assert call_args[0][0] == task  # first positional arg is the task


class TestCompletionReporting:
    """Tests for completion reporting."""

    def test_report_complete(self, worker_env: Path) -> None:
        """Test reporting task completion."""
        with (
            patch("zerg.worker_protocol.ZergConfig") as config_mock,
            patch("zerg.worker_protocol.StateManager") as state_mock,
        ):
            config = MagicMock()
            config.context_threshold = 0.7
            config_mock.load.return_value = config

            state = MagicMock()
            state_mock.return_value = state

            protocol = WorkerProtocol()
            protocol.tasks_completed = 0

            protocol.report_complete("TASK-001")

            state.set_task_status.assert_called_with("TASK-001", TaskStatus.COMPLETE, worker_id=0)
            assert protocol.tasks_completed == 1

    def test_report_failed(self, worker_env: Path) -> None:
        """Test reporting task failure."""
        with (
            patch("zerg.worker_protocol.ZergConfig") as config_mock,
            patch("zerg.worker_protocol.StateManager") as state_mock,
        ):
            config = MagicMock()
            config.context_threshold = 0.7
            config_mock.load.return_value = config

            state = MagicMock()
            state_mock.return_value = state

            protocol = WorkerProtocol()

            protocol.report_failed("TASK-001", "Test error")

            state.set_task_status.assert_called()
            # Check error is recorded
            call_args = state.set_task_status.call_args
            assert "error" in str(call_args)

    def test_multiple_completions_tracked(self, worker_env: Path) -> None:
        """Test multiple task completions are tracked."""
        with (
            patch("zerg.worker_protocol.ZergConfig") as config_mock,
            patch("zerg.worker_protocol.StateManager") as state_mock,
        ):
            config = MagicMock()
            config.context_threshold = 0.7
            config_mock.load.return_value = config

            state = MagicMock()
            state_mock.return_value = state

            protocol = WorkerProtocol()

            protocol.report_complete("TASK-001")
            protocol.report_complete("TASK-002")
            protocol.report_complete("TASK-003")

            assert protocol.tasks_completed == 3


class TestClaudeInvocation:
    """Tests for Claude Code CLI invocation."""

    def test_invoke_returns_result(self, worker_env: Path) -> None:
        """Test invoke returns ClaudeInvocationResult."""
        with (
            patch("zerg.worker_protocol.ZergConfig") as config_mock,
            patch("zerg.worker_protocol.StateManager"),
            patch("subprocess.run") as run_mock,
        ):
            config = MagicMock()
            config.context_threshold = 0.7
            config_mock.load.return_value = config

            process = MagicMock()
            process.returncode = 0
            process.stdout = "Success"
            process.stderr = ""
            run_mock.return_value = process

            protocol = WorkerProtocol()
            task = {"id": "TASK-001", "title": "Test"}

            result = protocol.invoke_claude_code(task)

            assert isinstance(result, ClaudeInvocationResult)

    def test_invoke_failure_recorded(self, worker_env: Path) -> None:
        """Test invocation failure is recorded."""
        with (
            patch("zerg.worker_protocol.ZergConfig") as config_mock,
            patch("zerg.worker_protocol.StateManager"),
            patch("subprocess.run") as run_mock,
        ):
            config = MagicMock()
            config.context_threshold = 0.7
            config_mock.load.return_value = config

            process = MagicMock()
            process.returncode = 1
            process.stdout = ""
            process.stderr = "Error"
            run_mock.return_value = process

            protocol = WorkerProtocol()
            task = {"id": "TASK-001", "title": "Test"}

            result = protocol.invoke_claude_code(task)

            assert result.success is False
            assert result.exit_code == 1


class TestVerification:
    """Tests for task verification."""

    def test_run_verification_success(self, worker_env: Path) -> None:
        """Test successful verification."""
        with (
            patch("zerg.worker_protocol.ZergConfig") as config_mock,
            patch("zerg.worker_protocol.StateManager"),
            patch("zerg.worker_protocol.VerificationExecutor") as verify_mock,
        ):
            config = MagicMock()
            config.context_threshold = 0.7
            config_mock.load.return_value = config

            verifier = MagicMock()
            result = MagicMock()
            result.success = True
            result.duration_ms = 100
            verifier.verify_with_retry.return_value = result
            verify_mock.return_value = verifier

            protocol = WorkerProtocol()
            # Verification should be a dict with "command" key
            task = {"id": "TASK-001", "verification": {"command": "pytest"}}

            success = protocol.run_verification(task)

            assert success is True

    def test_run_verification_failure(self, worker_env: Path) -> None:
        """Test verification failure."""
        with (
            patch("zerg.worker_protocol.ZergConfig") as config_mock,
            patch("zerg.worker_protocol.StateManager"),
            patch("zerg.worker_protocol.VerificationExecutor") as verify_mock,
        ):
            config = MagicMock()
            config.context_threshold = 0.7
            config_mock.load.return_value = config

            verifier = MagicMock()
            result = MagicMock()
            result.success = False
            result.exit_code = 1
            result.stderr = "Test failed"
            verifier.verify_with_retry.return_value = result
            verify_mock.return_value = verifier

            protocol = WorkerProtocol()
            # Verification should be a dict with "command" key
            task = {"id": "TASK-001", "verification": {"command": "pytest"}}

            success = protocol.run_verification(task)

            assert success is False

    def test_run_verification_no_command_passes(self, worker_env: Path) -> None:
        """Test verification with no command auto-passes."""
        with patch("zerg.worker_protocol.ZergConfig") as config_mock, patch("zerg.worker_protocol.StateManager"):
            config = MagicMock()
            config.context_threshold = 0.7
            config_mock.load.return_value = config

            protocol = WorkerProtocol()
            # No verification field
            task = {"id": "TASK-001"}

            success = protocol.run_verification(task)

            assert success is True

    def test_run_verification_empty_command_passes(self, worker_env: Path) -> None:
        """Test verification with empty command auto-passes."""
        with patch("zerg.worker_protocol.ZergConfig") as config_mock, patch("zerg.worker_protocol.StateManager"):
            config = MagicMock()
            config.context_threshold = 0.7
            config_mock.load.return_value = config

            protocol = WorkerProtocol()
            # Empty command
            task = {"id": "TASK-001", "verification": {"command": ""}}

            success = protocol.run_verification(task)

            assert success is True
