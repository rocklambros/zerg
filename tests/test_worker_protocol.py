"""Tests for ZERG worker protocol."""

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


class TestWorkerContext:
    """Tests for WorkerContext dataclass."""

    def test_init(self, tmp_path: Path) -> None:
        """Test WorkerContext initialization."""
        ctx = WorkerContext(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="zerg/test/worker-0",
        )

        assert ctx.worker_id == 0
        assert ctx.feature == "test-feature"
        assert ctx.worktree_path == tmp_path
        assert ctx.context_threshold == 0.7  # Default


class TestWorkerProtocol:
    """Tests for WorkerProtocol."""

    @pytest.fixture
    def mock_state_manager(self) -> MagicMock:
        """Create mock state manager."""
        mock = MagicMock()
        mock.load.return_value = {}
        mock.get_tasks_by_status.return_value = []
        return mock

    @pytest.fixture
    def mock_git_ops(self) -> MagicMock:
        """Create mock git ops."""
        mock = MagicMock()
        mock.has_changes.return_value = False
        return mock

    @pytest.fixture
    def protocol(
        self,
        tmp_path: Path,
        mock_state_manager: MagicMock,
        mock_git_ops: MagicMock,
        monkeypatch,
    ) -> WorkerProtocol:
        """Create WorkerProtocol with mocked dependencies."""
        # Set environment
        monkeypatch.setenv("ZERG_WORKER_ID", "0")
        monkeypatch.setenv("ZERG_FEATURE", "test-feature")
        monkeypatch.setenv("ZERG_WORKTREE", str(tmp_path))
        monkeypatch.chdir(tmp_path)

        # Create minimal config
        (tmp_path / ".zerg").mkdir()

        with patch("zerg.worker_protocol.StateManager", return_value=mock_state_manager):
            with patch("zerg.worker_protocol.GitOps", return_value=mock_git_ops):
                with patch("zerg.worker_protocol.VerificationExecutor"):
                    protocol = WorkerProtocol(
                        worker_id=0,
                        feature="test-feature",
                    )
                    return protocol

    def test_init(self, protocol: WorkerProtocol) -> None:
        """Test protocol initialization."""
        assert protocol.worker_id == 0
        assert protocol.feature == "test-feature"
        assert protocol.tasks_completed == 0
        assert protocol.current_task is None

    def test_context_tracker_initialized(self, protocol: WorkerProtocol) -> None:
        """Test context tracker is initialized."""
        assert protocol.context_tracker is not None
        assert protocol.context_tracker.threshold_percent == 70.0

    def test_check_context_usage(self, protocol: WorkerProtocol) -> None:
        """Test context usage check."""
        usage = protocol.check_context_usage()

        # Should return a float 0-1
        assert isinstance(usage, float)
        assert 0.0 <= usage <= 1.0

    def test_should_checkpoint_initially_false(self, protocol: WorkerProtocol) -> None:
        """Test checkpoint not needed initially."""
        assert protocol.should_checkpoint() is False

    def test_track_file_read(self, protocol: WorkerProtocol, tmp_path: Path) -> None:
        """Test tracking file reads."""
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        protocol.track_file_read(test_file)

        # Verify tracked in context tracker
        usage = protocol.context_tracker.get_usage()
        assert usage.files_read == 1

    def test_track_tool_call(self, protocol: WorkerProtocol) -> None:
        """Test tracking tool calls."""
        protocol.track_tool_call()
        protocol.track_tool_call()

        usage = protocol.context_tracker.get_usage()
        assert usage.tool_calls == 2

    def test_execute_task_tracks_context(
        self,
        protocol: WorkerProtocol,
        mock_state_manager: MagicMock,
    ) -> None:
        """Test task execution tracks context."""
        task = {
            "id": "TASK-001",
            "title": "Test Task",
            "level": 1,
        }

        # Mock verification to succeed
        protocol.verifier = MagicMock()
        protocol.verifier.verify.return_value = MagicMock(success=True)

        protocol.execute_task(task)

        # Verify task was tracked
        usage = protocol.context_tracker.get_usage()
        assert usage.tasks_executed == 1

    def test_get_status(self, protocol: WorkerProtocol) -> None:
        """Test getting worker status."""
        status = protocol.get_status()

        assert status["worker_id"] == 0
        assert status["feature"] == "test-feature"
        assert status["tasks_completed"] == 0
        assert "context_usage" in status
        assert "context_threshold" in status

    def test_claim_next_task_none_available(
        self,
        protocol: WorkerProtocol,
        mock_state_manager: MagicMock,
    ) -> None:
        """Test claiming when no tasks available."""
        mock_state_manager.get_tasks_by_status.return_value = []

        task = protocol.claim_next_task(max_wait=0.1)

        assert task is None

    def test_report_complete(
        self,
        protocol: WorkerProtocol,
        mock_state_manager: MagicMock,
    ) -> None:
        """Test reporting task completion."""
        protocol.current_task = {"id": "TASK-001", "title": "Test", "level": 1}

        protocol.report_complete("TASK-001")

        mock_state_manager.set_task_status.assert_called()
        mock_state_manager.append_event.assert_called()
        assert protocol.tasks_completed == 1
        assert protocol.current_task is None

    def test_report_failed(
        self,
        protocol: WorkerProtocol,
        mock_state_manager: MagicMock,
    ) -> None:
        """Test reporting task failure."""
        protocol.current_task = {"id": "TASK-001", "title": "Test", "level": 1}

        protocol.report_failed("TASK-001", "Test error")

        mock_state_manager.set_task_status.assert_called_with(
            "TASK-001",
            TaskStatus.FAILED,
            worker_id=0,
            error="Test error",
        )
        assert protocol.current_task is None


class TestWorkerProtocolContextIntegration:
    """Integration tests for context tracking in worker protocol."""

    def test_high_activity_triggers_checkpoint(self, tmp_path: Path, monkeypatch) -> None:
        """Test that high activity triggers checkpoint."""
        monkeypatch.setenv("ZERG_WORKER_ID", "0")
        monkeypatch.setenv("ZERG_FEATURE", "test-feature")
        monkeypatch.setenv("ZERG_WORKTREE", str(tmp_path))
        monkeypatch.chdir(tmp_path)

        (tmp_path / ".zerg").mkdir()

        with patch("zerg.worker_protocol.StateManager"):
            with patch("zerg.worker_protocol.GitOps"):
                with patch("zerg.worker_protocol.VerificationExecutor"):
                    protocol = WorkerProtocol(
                        worker_id=0,
                        feature="test-feature",
                    )

                    # Simulate heavy activity
                    for i in range(300):
                        protocol.context_tracker.track_task_execution(f"TASK-{i:03d}")
                        protocol.context_tracker.track_file_read(
                            f"/fake/file{i}.py",
                            size=5000,
                        )

                    # Should trigger checkpoint
                    assert protocol.should_checkpoint() is True


class TestClaudeInvocationResult:
    """Tests for ClaudeInvocationResult dataclass."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        result = ClaudeInvocationResult(
            success=True,
            exit_code=0,
            stdout="output",
            stderr="",
            duration_ms=1000,
            task_id="TASK-001",
        )

        d = result.to_dict()
        assert d["success"] is True
        assert d["exit_code"] == 0
        assert d["task_id"] == "TASK-001"
        assert "timestamp" in d

    def test_truncates_long_output(self) -> None:
        """Test that long output is truncated in dict."""
        long_output = "x" * 2000
        result = ClaudeInvocationResult(
            success=True,
            exit_code=0,
            stdout=long_output,
            stderr=long_output,
            duration_ms=100,
            task_id="TASK-001",
        )

        d = result.to_dict()
        assert len(d["stdout"]) == 1000
        assert len(d["stderr"]) == 1000


class TestWorkerReady:
    """Tests for worker ready signal (L3-001)."""

    @pytest.fixture
    def protocol(self, tmp_path: Path, monkeypatch) -> WorkerProtocol:
        """Create WorkerProtocol with mocked dependencies."""
        monkeypatch.setenv("ZERG_WORKER_ID", "0")
        monkeypatch.setenv("ZERG_FEATURE", "test-feature")
        monkeypatch.setenv("ZERG_WORKTREE", str(tmp_path))
        monkeypatch.chdir(tmp_path)

        (tmp_path / ".zerg").mkdir()

        with patch("zerg.worker_protocol.StateManager") as state_mock:
            with patch("zerg.worker_protocol.GitOps"):
                with patch("zerg.worker_protocol.VerificationExecutor"):
                    state = MagicMock()
                    state.load.return_value = {}
                    state_mock.return_value = state

                    protocol = WorkerProtocol(
                        worker_id=0,
                        feature="test-feature",
                    )
                    protocol.state = state
                    return protocol

    def test_signal_ready(self, protocol: WorkerProtocol) -> None:
        """Test signaling ready state."""
        assert protocol.is_ready is False

        protocol.signal_ready()

        assert protocol.is_ready is True
        protocol.state.set_worker_ready.assert_called_once_with(0)
        protocol.state.append_event.assert_called()

    def test_wait_for_ready_already_ready(self, protocol: WorkerProtocol) -> None:
        """Test wait_for_ready when already ready."""
        protocol._is_ready = True

        result = protocol.wait_for_ready(timeout=0.1)

        assert result is True

    def test_wait_for_ready_timeout(self, protocol: WorkerProtocol) -> None:
        """Test wait_for_ready timeout."""
        result = protocol.wait_for_ready(timeout=0.1)

        assert result is False


class TestTaskLoading:
    """Tests for task loading from task graph (L3-001)."""

    @pytest.fixture
    def task_graph(self, tmp_path: Path) -> Path:
        """Create a test task graph file."""
        graph = {
            "schema": "task-graph-v1",
            "feature": "test-feature",
            "tasks": [
                {
                    "id": "TASK-001",
                    "title": "Test Task One",
                    "description": "A test task",
                    "level": 1,
                    "dependencies": [],
                    "files": {
                        "create": ["new_file.py"],
                        "modify": ["existing.py"],
                        "read": ["reference.py"],
                    },
                    "verification": {
                        "command": "pytest tests/",
                        "timeout_seconds": 60,
                    },
                },
            ],
            "levels": {"1": {"name": "Level 1", "tasks": ["TASK-001"]}},
        }

        graph_path = tmp_path / "task-graph.json"
        graph_path.write_text(json.dumps(graph))
        return graph_path

    def test_load_task_details_from_graph(self, tmp_path: Path, task_graph: Path, monkeypatch) -> None:
        """Test loading task details from task graph."""
        monkeypatch.setenv("ZERG_WORKER_ID", "0")
        monkeypatch.setenv("ZERG_FEATURE", "test-feature")
        monkeypatch.setenv("ZERG_WORKTREE", str(tmp_path))
        monkeypatch.chdir(tmp_path)

        (tmp_path / ".zerg").mkdir()

        with patch("zerg.worker_protocol.StateManager"):
            with patch("zerg.worker_protocol.GitOps"):
                with patch("zerg.worker_protocol.VerificationExecutor"):
                    protocol = WorkerProtocol(
                        worker_id=0,
                        feature="test-feature",
                        task_graph_path=task_graph,
                    )

                    task = protocol._load_task_details("TASK-001")

                    assert task["id"] == "TASK-001"
                    assert task["title"] == "Test Task One"
                    assert task["description"] == "A test task"
                    assert "files" in task
                    assert "verification" in task

    def test_load_task_details_missing(self, tmp_path: Path, task_graph: Path, monkeypatch) -> None:
        """Test loading non-existent task returns stub."""
        monkeypatch.setenv("ZERG_WORKER_ID", "0")
        monkeypatch.setenv("ZERG_FEATURE", "test-feature")
        monkeypatch.setenv("ZERG_WORKTREE", str(tmp_path))
        monkeypatch.chdir(tmp_path)

        (tmp_path / ".zerg").mkdir()

        with patch("zerg.worker_protocol.StateManager"):
            with patch("zerg.worker_protocol.GitOps"):
                with patch("zerg.worker_protocol.VerificationExecutor"):
                    protocol = WorkerProtocol(
                        worker_id=0,
                        feature="test-feature",
                        task_graph_path=task_graph,
                    )

                    task = protocol._load_task_details("TASK-999")

                    assert task["id"] == "TASK-999"
                    assert "title" in task


class TestClaudeCodeInvocation:
    """Tests for Claude Code CLI invocation (L3-002)."""

    @pytest.fixture
    def protocol(self, tmp_path: Path, monkeypatch) -> WorkerProtocol:
        """Create WorkerProtocol with mocked dependencies."""
        monkeypatch.setenv("ZERG_WORKER_ID", "0")
        monkeypatch.setenv("ZERG_FEATURE", "test-feature")
        monkeypatch.setenv("ZERG_WORKTREE", str(tmp_path))
        monkeypatch.chdir(tmp_path)

        (tmp_path / ".zerg").mkdir()

        with patch("zerg.worker_protocol.StateManager") as state_mock:
            with patch("zerg.worker_protocol.GitOps"):
                with patch("zerg.worker_protocol.VerificationExecutor"):
                    state = MagicMock()
                    state.load.return_value = {}
                    state_mock.return_value = state

                    protocol = WorkerProtocol(
                        worker_id=0,
                        feature="test-feature",
                    )
                    protocol.state = state
                    return protocol

    def test_build_task_prompt_basic(self, protocol: WorkerProtocol) -> None:
        """Test building basic task prompt."""
        task = {
            "id": "TASK-001",
            "title": "Test Task",
        }

        prompt = protocol._build_task_prompt(task)

        assert "# Task: Test Task" in prompt
        assert "## Instructions" in prompt

    def test_build_task_prompt_with_description(self, protocol: WorkerProtocol) -> None:
        """Test building task prompt with description."""
        task = {
            "id": "TASK-001",
            "title": "Test Task",
            "description": "This is a detailed description",
        }

        prompt = protocol._build_task_prompt(task)

        assert "## Description" in prompt
        assert "This is a detailed description" in prompt

    def test_build_task_prompt_with_files(self, protocol: WorkerProtocol) -> None:
        """Test building task prompt with file specifications."""
        task = {
            "id": "TASK-001",
            "title": "Test Task",
            "files": {
                "create": ["new.py"],
                "modify": ["existing.py"],
                "read": ["reference.py"],
            },
        }

        prompt = protocol._build_task_prompt(task)

        assert "## Files" in prompt
        assert "Create: new.py" in prompt
        assert "Modify: existing.py" in prompt
        assert "Reference: reference.py" in prompt

    def test_invoke_claude_code_success(self, protocol: WorkerProtocol) -> None:
        """Test successful Claude Code invocation."""
        task = {"id": "TASK-001", "title": "Test"}

        with patch("zerg.worker_protocol.subprocess.run") as run_mock:
            run_mock.return_value = MagicMock(
                returncode=0,
                stdout="Success output",
                stderr="",
            )

            result = protocol.invoke_claude_code(task)

            assert result.success is True
            assert result.exit_code == 0
            assert result.stdout == "Success output"
            run_mock.assert_called_once()

    def test_invoke_claude_code_failure(self, protocol: WorkerProtocol) -> None:
        """Test failed Claude Code invocation."""
        task = {"id": "TASK-001", "title": "Test"}

        with patch("zerg.worker_protocol.subprocess.run") as run_mock:
            run_mock.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Error output",
            )

            result = protocol.invoke_claude_code(task)

            assert result.success is False
            assert result.exit_code == 1

    def test_invoke_claude_code_timeout(self, protocol: WorkerProtocol) -> None:
        """Test Claude Code timeout handling."""
        import subprocess

        task = {"id": "TASK-001", "title": "Test"}

        with patch("zerg.worker_protocol.subprocess.run") as run_mock:
            run_mock.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=30)

            result = protocol.invoke_claude_code(task, timeout=30)

            assert result.success is False
            assert "timed out" in result.stderr

    def test_invoke_claude_code_not_found(self, protocol: WorkerProtocol) -> None:
        """Test Claude CLI not found handling."""
        task = {"id": "TASK-001", "title": "Test"}

        with patch("zerg.worker_protocol.subprocess.run") as run_mock:
            run_mock.side_effect = FileNotFoundError()

            result = protocol.invoke_claude_code(task)

            assert result.success is False
            assert "not found" in result.stderr


class TestVerificationFlow:
    """Tests for verification and commit flow (L3-003)."""

    @pytest.fixture
    def protocol(self, tmp_path: Path, monkeypatch) -> WorkerProtocol:
        """Create WorkerProtocol with mocked dependencies."""
        monkeypatch.setenv("ZERG_WORKER_ID", "0")
        monkeypatch.setenv("ZERG_FEATURE", "test-feature")
        monkeypatch.setenv("ZERG_WORKTREE", str(tmp_path))
        monkeypatch.chdir(tmp_path)

        (tmp_path / ".zerg").mkdir()

        state = MagicMock()
        state.load.return_value = {}

        git = MagicMock()
        git.has_changes.return_value = True
        # Simulate HEAD change after commit (BF-009 verification)
        git.current_commit.side_effect = ["abc1234", "def5678"]

        verifier = MagicMock()

        with patch("zerg.worker_protocol.StateManager", return_value=state):
            with patch("zerg.worker_protocol.GitOps", return_value=git):
                with patch("zerg.worker_protocol.VerificationExecutor", return_value=verifier):
                    protocol = WorkerProtocol(
                        worker_id=0,
                        feature="test-feature",
                    )
                    protocol.state = state
                    protocol.git = git
                    protocol.verifier = verifier
                    return protocol

    def test_run_verification_success(self, protocol: WorkerProtocol) -> None:
        """Test successful verification."""
        task = {
            "id": "TASK-001",
            "verification": {"command": "pytest", "timeout_seconds": 30},
        }

        result = MagicMock()
        result.success = True
        result.duration_ms = 1000
        protocol.verifier.verify_with_retry.return_value = result

        success = protocol.run_verification(task)

        assert success is True
        protocol.state.append_event.assert_called()

    def test_run_verification_failure(self, protocol: WorkerProtocol) -> None:
        """Test failed verification."""
        task = {
            "id": "TASK-001",
            "verification": {"command": "pytest", "timeout_seconds": 30},
        }

        result = MagicMock()
        result.success = False
        result.exit_code = 1
        result.stderr = "Test failed"
        protocol.verifier.verify_with_retry.return_value = result

        success = protocol.run_verification(task)

        assert success is False

    def test_run_verification_no_spec(self, protocol: WorkerProtocol) -> None:
        """Test verification auto-passes when no spec."""
        task = {"id": "TASK-001"}

        success = protocol.run_verification(task)

        assert success is True

    def test_commit_task_changes_success(self, protocol: WorkerProtocol) -> None:
        """Test successful commit."""
        task = {"id": "TASK-001", "title": "Test Task"}

        success = protocol.commit_task_changes(task)

        assert success is True
        protocol.git.commit.assert_called_once()
        protocol.state.append_event.assert_called()

    def test_commit_task_changes_no_changes(self, protocol: WorkerProtocol) -> None:
        """Test commit when no changes."""
        task = {"id": "TASK-001", "title": "Test Task"}
        protocol.git.has_changes.return_value = False

        success = protocol.commit_task_changes(task)

        assert success is True
        protocol.git.commit.assert_not_called()

    def test_commit_task_changes_failure(self, protocol: WorkerProtocol) -> None:
        """Test commit failure handling."""
        task = {"id": "TASK-001", "title": "Test Task"}
        protocol.git.commit.side_effect = Exception("Git error")

        success = protocol.commit_task_changes(task)

        assert success is False
        protocol.state.append_event.assert_called()

    def test_execute_task_full_flow(self, protocol: WorkerProtocol) -> None:
        """Test full task execution flow."""
        task = {
            "id": "TASK-001",
            "title": "Test Task",
            "verification": {"command": "pytest", "timeout_seconds": 30},
        }

        # Mock Claude Code success
        with patch.object(protocol, "invoke_claude_code") as claude_mock:
            claude_mock.return_value = ClaudeInvocationResult(
                success=True,
                exit_code=0,
                stdout="Done",
                stderr="",
                duration_ms=1000,
                task_id="TASK-001",
            )

            # Mock verification success
            verify_result = MagicMock()
            verify_result.success = True
            verify_result.duration_ms = 500
            protocol.verifier.verify_with_retry.return_value = verify_result

            success = protocol.execute_task(task)

            assert success is True
            claude_mock.assert_called_once()
            protocol.git.commit.assert_called_once()

    def test_execute_task_claude_failure(self, protocol: WorkerProtocol) -> None:
        """Test task execution when Claude Code fails."""
        task = {"id": "TASK-001", "title": "Test Task"}

        with patch.object(protocol, "invoke_claude_code") as claude_mock:
            claude_mock.return_value = ClaudeInvocationResult(
                success=False,
                exit_code=1,
                stdout="",
                stderr="Error",
                duration_ms=1000,
                task_id="TASK-001",
            )

            success = protocol.execute_task(task)

            assert success is False
            protocol.git.commit.assert_not_called()
