"""Tests for ZERG protocol handler module.

Tests cover: task execution pipeline, Claude CLI invocation, prompt building,
verification dispatch, commit flow, error handling, and plugin/structured
logging integration.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from zerg.constants import (
    LogEvent,
    PluginHookEvent,
    TaskStatus,
    WorkerStatus,
)
from zerg.protocol_handler import ProtocolHandler
from zerg.protocol_types import CLAUDE_CLI_COMMAND, CLAUDE_CLI_DEFAULT_TIMEOUT, ClaudeInvocationResult
from zerg.verify import VerificationExecutionResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_config(**overrides: Any) -> MagicMock:
    """Create a minimal ZergConfig mock."""
    cfg = MagicMock()
    cfg.logging = MagicMock()
    cfg.logging.ephemeral_retain_on_success = False
    cfg.logging.ephemeral_retain_on_failure = True
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _make_handler(
    tmp_path: Path,
    *,
    spec_context: str = "",
    structured_writer: MagicMock | None = None,
    plugin_registry: MagicMock | None = None,
) -> ProtocolHandler:
    """Build a ProtocolHandler with all collaborators mocked."""
    return ProtocolHandler(
        worker_id=1,
        feature="test-feature",
        branch="zerg/test-feature/w1",
        worktree_path=tmp_path,
        state=MagicMock(),
        git=MagicMock(),
        verifier=MagicMock(),
        context_tracker=MagicMock(),
        config=_make_config(),
        spec_context=spec_context,
        structured_writer=structured_writer,
        plugin_registry=plugin_registry,
    )


def _make_task(**overrides: Any) -> dict[str, Any]:
    """Return a minimal Task dict."""
    base: dict[str, Any] = {
        "id": "TASK-001",
        "title": "Implement auth module",
        "description": "Add JWT-based authentication.",
        "level": 1,
        "files": {
            "create": ["src/auth.py"],
            "modify": ["src/app.py"],
            "read": ["docs/spec.md"],
        },
        "verification": {
            "command": "pytest tests/test_auth.py",
            "timeout_seconds": 30,
        },
    }
    base.update(overrides)
    return base


def _success_claude_result(task_id: str = "TASK-001") -> ClaudeInvocationResult:
    return ClaudeInvocationResult(
        success=True,
        exit_code=0,
        stdout="All done",
        stderr="",
        duration_ms=500,
        task_id=task_id,
    )


def _failed_claude_result(task_id: str = "TASK-001") -> ClaudeInvocationResult:
    return ClaudeInvocationResult(
        success=False,
        exit_code=1,
        stdout="",
        stderr="Something went wrong",
        duration_ms=200,
        task_id=task_id,
    )


def _success_verify_result(task_id: str = "TASK-001") -> VerificationExecutionResult:
    return VerificationExecutionResult(
        task_id=task_id,
        success=True,
        exit_code=0,
        stdout="ok",
        stderr="",
        duration_ms=100,
        command="pytest tests/test_auth.py",
    )


def _failed_verify_result(task_id: str = "TASK-001") -> VerificationExecutionResult:
    return VerificationExecutionResult(
        task_id=task_id,
        success=False,
        exit_code=1,
        stdout="",
        stderr="assertion failed",
        duration_ms=100,
        command="pytest tests/test_auth.py",
    )


# ===================================================================
# _build_task_prompt
# ===================================================================


class TestBuildTaskPrompt:
    """Tests for prompt construction from task specifications."""

    def test_basic_prompt_includes_title_and_instructions(self, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)
        task = _make_task()
        prompt = handler._build_task_prompt(task)

        assert "# Task: Implement auth module" in prompt
        assert "## Instructions" in prompt
        assert "Do NOT commit" in prompt

    def test_prompt_includes_description(self, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)
        task = _make_task()
        prompt = handler._build_task_prompt(task)

        assert "## Description" in prompt
        assert "JWT-based authentication" in prompt

    def test_prompt_includes_files_section(self, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)
        task = _make_task()
        prompt = handler._build_task_prompt(task)

        assert "## Files" in prompt
        assert "Create: src/auth.py" in prompt
        assert "Modify: src/app.py" in prompt
        assert "Reference: docs/spec.md" in prompt

    def test_prompt_includes_verification(self, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)
        task = _make_task()
        prompt = handler._build_task_prompt(task)

        assert "## Verification" in prompt
        assert "pytest tests/test_auth.py" in prompt

    def test_prompt_with_spec_context(self, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path, spec_context="# Feature Requirements\nBuild auth")
        task = _make_task()
        prompt = handler._build_task_prompt(task)

        assert "# Feature Requirements" in prompt

    def test_task_scoped_context_overrides_spec_context(self, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path, spec_context="SHOULD NOT APPEAR")
        task = _make_task(context="# Task Context (Scoped)\nOnly relevant info")
        prompt = handler._build_task_prompt(task)

        assert "# Task Context (Scoped)" in prompt
        assert "Only relevant info" in prompt
        assert "SHOULD NOT APPEAR" not in prompt

    def test_prompt_no_description(self, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)
        task = _make_task()
        del task["description"]
        prompt = handler._build_task_prompt(task)

        assert "## Description" not in prompt

    def test_prompt_no_files(self, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)
        task = _make_task()
        del task["files"]
        prompt = handler._build_task_prompt(task)

        assert "## Files" not in prompt

    def test_prompt_no_verification(self, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)
        task = _make_task()
        del task["verification"]
        prompt = handler._build_task_prompt(task)

        assert "## Verification" not in prompt

    def test_prompt_falls_back_to_task_id_when_no_title(self, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)
        task = _make_task()
        del task["title"]
        prompt = handler._build_task_prompt(task)

        assert "# Task: TASK-001" in prompt


# ===================================================================
# invoke_claude_code
# ===================================================================


class TestInvokeClaudeCode:
    """Tests for Claude CLI invocation."""

    @patch("zerg.protocol_handler.subprocess.run")
    def test_successful_invocation(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="output", stderr="")
        handler = _make_handler(tmp_path)
        task = _make_task()

        result = handler.invoke_claude_code(task)

        assert result.success is True
        assert result.exit_code == 0
        assert result.stdout == "output"
        assert result.task_id == "TASK-001"
        assert result.duration_ms >= 0

        # Verify correct CLI arguments
        args, kwargs = mock_run.call_args
        cmd = args[0]
        assert cmd[0] == CLAUDE_CLI_COMMAND
        assert "--print" in cmd
        assert "--dangerously-skip-permissions" in cmd

    @patch("zerg.protocol_handler.subprocess.run")
    def test_failed_invocation(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error msg")
        handler = _make_handler(tmp_path)
        task = _make_task()

        result = handler.invoke_claude_code(task)

        assert result.success is False
        assert result.exit_code == 1
        assert result.stderr == "error msg"

    @patch("zerg.protocol_handler.subprocess.run")
    def test_timeout_returns_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=30)
        handler = _make_handler(tmp_path)
        task = _make_task()

        result = handler.invoke_claude_code(task, timeout=30)

        assert result.success is False
        assert result.exit_code == -1
        assert "timed out" in result.stderr

    @patch("zerg.protocol_handler.subprocess.run")
    def test_file_not_found_returns_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.side_effect = FileNotFoundError("claude not found")
        handler = _make_handler(tmp_path)
        task = _make_task()

        result = handler.invoke_claude_code(task)

        assert result.success is False
        assert result.exit_code == -1
        assert "not found" in result.stderr

    @patch("zerg.protocol_handler.subprocess.run")
    def test_generic_exception_returns_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.side_effect = OSError("Unexpected OS error")
        handler = _make_handler(tmp_path)
        task = _make_task()

        result = handler.invoke_claude_code(task)

        assert result.success is False
        assert result.exit_code == -1
        assert "Unexpected OS error" in result.stderr

    @patch("zerg.protocol_handler.subprocess.run")
    def test_custom_timeout_used(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        handler = _make_handler(tmp_path)
        task = _make_task()

        handler.invoke_claude_code(task, timeout=60)

        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 60

    @patch("zerg.protocol_handler.subprocess.run")
    def test_default_timeout_used(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        handler = _make_handler(tmp_path)
        task = _make_task()

        handler.invoke_claude_code(task)

        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == CLAUDE_CLI_DEFAULT_TIMEOUT

    @patch("zerg.protocol_handler.subprocess.run")
    def test_env_vars_include_zerg_ids(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        handler = _make_handler(tmp_path)
        task = _make_task()

        handler.invoke_claude_code(task)

        _, kwargs = mock_run.call_args
        env = kwargs["env"]
        assert env["ZERG_TASK_ID"] == "TASK-001"
        assert env["ZERG_WORKER_ID"] == "1"


# ===================================================================
# run_verification
# ===================================================================


class TestRunVerification:
    """Tests for verification dispatch."""

    def test_no_verification_spec_auto_passes(self, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)
        task = _make_task()
        del task["verification"]

        result = handler.run_verification(task)

        assert result is True
        handler.verifier.verify_with_retry.assert_not_called()

    def test_empty_command_auto_passes(self, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)
        task = _make_task(verification={"command": "", "timeout_seconds": 30})

        result = handler.run_verification(task)

        assert result is True
        handler.verifier.verify_with_retry.assert_not_called()

    def test_verification_passes(self, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)
        handler.verifier.verify_with_retry.return_value = _success_verify_result()
        task = _make_task()

        result = handler.run_verification(task)

        assert result is True
        handler.state.append_event.assert_called_once()
        event_name = handler.state.append_event.call_args[0][0]
        assert event_name == "verification_passed"

    def test_verification_fails(self, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)
        handler.verifier.verify_with_retry.return_value = _failed_verify_result()
        task = _make_task()

        result = handler.run_verification(task)

        assert result is False
        handler.state.append_event.assert_called_once()
        event_name = handler.state.append_event.call_args[0][0]
        assert event_name == "verification_failed"

    def test_verification_captures_artifact(self, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)
        handler.verifier.verify_with_retry.return_value = _success_verify_result()
        task = _make_task()
        artifact = MagicMock()

        handler.run_verification(task, artifact=artifact)

        artifact.capture_verification.assert_called_once_with("ok", "", 0)

    def test_verification_structured_log_on_pass(self, tmp_path: Path) -> None:
        writer = MagicMock()
        handler = _make_handler(tmp_path, structured_writer=writer)
        handler.verifier.verify_with_retry.return_value = _success_verify_result()
        task = _make_task()

        handler.run_verification(task)

        writer.emit.assert_called_once()
        emit_args = writer.emit.call_args
        assert emit_args[0][0] == "info"
        assert emit_args[1]["event"] == LogEvent.VERIFICATION_PASSED

    def test_verification_passes_cwd_and_retry(self, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)
        handler.verifier.verify_with_retry.return_value = _success_verify_result()
        task = _make_task()

        handler.run_verification(task, max_retries=3)

        handler.verifier.verify_with_retry.assert_called_once_with(
            "pytest tests/test_auth.py",
            "TASK-001",
            max_retries=3,
            timeout=30,
            cwd=tmp_path,
        )


# ===================================================================
# commit_task_changes
# ===================================================================


class TestCommitTaskChanges:
    """Tests for git commit flow."""

    def test_no_changes_returns_true(self, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)
        handler.git.has_changes.return_value = False
        task = _make_task()

        result = handler.commit_task_changes(task)

        assert result is True
        handler.git.commit.assert_not_called()

    def test_successful_commit(self, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)
        handler.git.has_changes.return_value = True
        handler.git.current_commit.side_effect = ["abc123", "def456"]
        task = _make_task()

        result = handler.commit_task_changes(task)

        assert result is True
        handler.git.commit.assert_called_once()
        commit_msg = handler.git.commit.call_args[0][0]
        assert "ZERG [1]" in commit_msg
        assert "Implement auth module" in commit_msg
        assert "Task-ID: TASK-001" in commit_msg

    def test_head_unchanged_returns_false(self, tmp_path: Path) -> None:
        """BF-009: HEAD unchanged after commit means commit silently failed."""
        handler = _make_handler(tmp_path)
        handler.git.has_changes.return_value = True
        handler.git.current_commit.return_value = "same_sha"
        task = _make_task()

        result = handler.commit_task_changes(task)

        assert result is False
        handler.state.append_event.assert_called()
        event_name = handler.state.append_event.call_args[0][0]
        assert event_name == "commit_verification_failed"

    def test_commit_exception_returns_false(self, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)
        handler.git.has_changes.return_value = True
        handler.git.current_commit.side_effect = RuntimeError("git broken")
        task = _make_task()

        result = handler.commit_task_changes(task)

        assert result is False
        handler.state.append_event.assert_called()
        event_name = handler.state.append_event.call_args[0][0]
        assert event_name == "commit_failed"

    @patch("zerg.protocol_handler.subprocess.run")
    def test_commit_captures_diff_artifact(self, mock_run: MagicMock, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)
        handler.git.has_changes.return_value = True
        handler.git.current_commit.side_effect = ["abc", "def"]

        # Simulate git diff calls
        mock_run.side_effect = [
            MagicMock(stdout="cached diff"),
            MagicMock(stdout="unstaged diff"),
        ]
        task = _make_task()
        artifact = MagicMock()

        handler.commit_task_changes(task, artifact=artifact)

        artifact.capture_git_diff.assert_called_once_with("cached diffunstaged diff")

    def test_successful_commit_emits_task_committed_event(self, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)
        handler.git.has_changes.return_value = True
        handler.git.current_commit.side_effect = ["abc123", "def456"]
        task = _make_task()

        handler.commit_task_changes(task)

        # Last event should be task_committed
        calls = handler.state.append_event.call_args_list
        assert len(calls) == 1
        assert calls[0][0][0] == "task_committed"
        data = calls[0][0][1]
        assert data["commit_sha"] == "def456"
        assert data["branch"] == "zerg/test-feature/w1"


# ===================================================================
# execute_task — full pipeline
# ===================================================================


class TestExecuteTask:
    """Tests for the full execute_task pipeline."""

    @patch("zerg.protocol_handler.subprocess.run")
    def test_successful_pipeline(self, _mock_run: MagicMock, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)

        # Wire up collaborators for a fully successful path
        with patch.object(handler, "invoke_claude_code", return_value=_success_claude_result()):
            with patch.object(handler, "run_verification", return_value=True):
                with patch.object(handler, "commit_task_changes", return_value=True):
                    task = _make_task()
                    result = handler.execute_task(task)

        assert result is True
        handler.state.set_task_status.assert_called_once_with("TASK-001", TaskStatus.IN_PROGRESS, worker_id=1)
        handler.context_tracker.track_task_execution.assert_called_once_with("TASK-001")
        handler.state.record_task_duration.assert_called_once()

    @patch("zerg.protocol_handler.subprocess.run")
    def test_claude_failure_returns_false(self, _mock_run: MagicMock, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)

        with patch.object(handler, "invoke_claude_code", return_value=_failed_claude_result()):
            task = _make_task()
            result = handler.execute_task(task)

        assert result is False
        handler.state.append_event.assert_called()
        event_name = handler.state.append_event.call_args[0][0]
        assert event_name == "claude_failed"

    @patch("zerg.protocol_handler.subprocess.run")
    def test_verification_failure_returns_false(self, _mock_run: MagicMock, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)

        with patch.object(handler, "invoke_claude_code", return_value=_success_claude_result()):
            with patch.object(handler, "run_verification", return_value=False):
                task = _make_task()
                result = handler.execute_task(task)

        assert result is False

    @patch("zerg.protocol_handler.subprocess.run")
    def test_commit_failure_returns_false(self, _mock_run: MagicMock, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)

        with patch.object(handler, "invoke_claude_code", return_value=_success_claude_result()):
            with patch.object(handler, "run_verification", return_value=True):
                with patch.object(handler, "commit_task_changes", return_value=False):
                    task = _make_task()
                    result = handler.execute_task(task)

        assert result is False

    @patch("zerg.protocol_handler.subprocess.run")
    def test_exception_during_execution(self, _mock_run: MagicMock, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)

        with patch.object(handler, "invoke_claude_code", side_effect=RuntimeError("boom")):
            task = _make_task()
            result = handler.execute_task(task)

        assert result is False
        handler.state.append_event.assert_called()
        event_name = handler.state.append_event.call_args[0][0]
        assert event_name == "task_exception"

    @patch("zerg.protocol_handler.subprocess.run")
    def test_update_worker_state_callback(self, _mock_run: MagicMock, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)
        callback = MagicMock()

        with patch.object(handler, "invoke_claude_code", return_value=_success_claude_result()):
            with patch.object(handler, "run_verification", return_value=True):
                with patch.object(handler, "commit_task_changes", return_value=True):
                    task = _make_task()
                    handler.execute_task(task, update_worker_state=callback)

        callback.assert_called_once_with(WorkerStatus.RUNNING, current_task="TASK-001")

    @patch("zerg.protocol_handler.subprocess.run")
    def test_no_verification_skips_verification(self, _mock_run: MagicMock, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path)

        with patch.object(handler, "invoke_claude_code", return_value=_success_claude_result()):
            with patch.object(handler, "commit_task_changes", return_value=True):
                task = _make_task()
                del task["verification"]
                result = handler.execute_task(task)

        assert result is True

    @patch("zerg.protocol_handler.subprocess.run")
    def test_structured_writer_task_started(self, _mock_run: MagicMock, tmp_path: Path) -> None:
        writer = MagicMock()
        handler = _make_handler(tmp_path, structured_writer=writer)

        with patch.object(handler, "invoke_claude_code", return_value=_success_claude_result()):
            with patch.object(handler, "run_verification", return_value=True):
                with patch.object(handler, "commit_task_changes", return_value=True):
                    task = _make_task()
                    handler.execute_task(task)

        # First emit should be task_started
        first_call = writer.emit.call_args_list[0]
        assert first_call[1]["event"] == LogEvent.TASK_STARTED

    @patch("zerg.protocol_handler.subprocess.run")
    def test_structured_writer_task_completed(self, _mock_run: MagicMock, tmp_path: Path) -> None:
        writer = MagicMock()
        handler = _make_handler(tmp_path, structured_writer=writer)

        with patch.object(handler, "invoke_claude_code", return_value=_success_claude_result()):
            with patch.object(handler, "run_verification", return_value=True):
                with patch.object(handler, "commit_task_changes", return_value=True):
                    task = _make_task()
                    handler.execute_task(task)

        # Last emit should be task_completed
        last_call = writer.emit.call_args_list[-1]
        assert last_call[1]["event"] == LogEvent.TASK_COMPLETED

    @patch("zerg.protocol_handler.subprocess.run")
    def test_structured_writer_claude_failure(self, _mock_run: MagicMock, tmp_path: Path) -> None:
        writer = MagicMock()
        handler = _make_handler(tmp_path, structured_writer=writer)

        with patch.object(handler, "invoke_claude_code", return_value=_failed_claude_result()):
            task = _make_task()
            handler.execute_task(task)

        # Should emit TASK_STARTED then TASK_FAILED
        emit_events = [c[1]["event"] for c in writer.emit.call_args_list]
        assert LogEvent.TASK_STARTED in emit_events
        assert LogEvent.TASK_FAILED in emit_events

    @patch("zerg.protocol_handler.subprocess.run")
    def test_structured_writer_verification_failure(self, _mock_run: MagicMock, tmp_path: Path) -> None:
        writer = MagicMock()
        handler = _make_handler(tmp_path, structured_writer=writer)

        with patch.object(handler, "invoke_claude_code", return_value=_success_claude_result()):
            with patch.object(handler, "run_verification", return_value=False):
                task = _make_task()
                handler.execute_task(task)

        emit_events = [c[1]["event"] for c in writer.emit.call_args_list]
        assert LogEvent.VERIFICATION_FAILED in emit_events

    @patch("zerg.protocol_handler.subprocess.run")
    def test_structured_writer_exception(self, _mock_run: MagicMock, tmp_path: Path) -> None:
        writer = MagicMock()
        handler = _make_handler(tmp_path, structured_writer=writer)

        with patch.object(handler, "invoke_claude_code", side_effect=RuntimeError("boom")):
            task = _make_task()
            handler.execute_task(task)

        emit_events = [c[1]["event"] for c in writer.emit.call_args_list]
        assert LogEvent.TASK_FAILED in emit_events

    @patch("zerg.protocol_handler.subprocess.run")
    def test_plugin_task_started_event(self, _mock_run: MagicMock, tmp_path: Path) -> None:
        registry = MagicMock()
        handler = _make_handler(tmp_path, plugin_registry=registry)

        with patch.object(handler, "invoke_claude_code", return_value=_success_claude_result()):
            with patch.object(handler, "run_verification", return_value=True):
                with patch.object(handler, "commit_task_changes", return_value=True):
                    task = _make_task()
                    handler.execute_task(task)

        # Verify both TASK_STARTED and TASK_COMPLETED plugin events
        emit_calls = registry.emit_event.call_args_list
        event_types = [c[0][0].event_type for c in emit_calls]
        assert PluginHookEvent.TASK_STARTED.value in event_types
        assert PluginHookEvent.TASK_COMPLETED.value in event_types

    @patch("zerg.protocol_handler.subprocess.run")
    def test_plugin_task_completed_failure_event(self, _mock_run: MagicMock, tmp_path: Path) -> None:
        registry = MagicMock()
        handler = _make_handler(tmp_path, plugin_registry=registry)

        with patch.object(handler, "invoke_claude_code", side_effect=RuntimeError("boom")):
            task = _make_task()
            handler.execute_task(task)

        # Exception path should still emit TASK_COMPLETED with success=False
        emit_calls = registry.emit_event.call_args_list
        completed_events = [c[0][0] for c in emit_calls if c[0][0].event_type == PluginHookEvent.TASK_COMPLETED.value]
        assert len(completed_events) == 1
        assert completed_events[0].data["success"] is False
        assert "boom" in completed_events[0].data["error"]

    @patch("zerg.protocol_handler.subprocess.run")
    def test_plugin_exception_suppressed(self, _mock_run: MagicMock, tmp_path: Path) -> None:
        """Plugin errors should not crash the execution pipeline."""
        registry = MagicMock()
        registry.emit_event.side_effect = RuntimeError("plugin crash")
        handler = _make_handler(tmp_path, plugin_registry=registry)

        with patch.object(handler, "invoke_claude_code", return_value=_success_claude_result()):
            with patch.object(handler, "run_verification", return_value=True):
                with patch.object(handler, "commit_task_changes", return_value=True):
                    task = _make_task()
                    result = handler.execute_task(task)

        # Pipeline should still succeed despite plugin failure
        assert result is True


# ===================================================================
# Constructor
# ===================================================================


class TestProtocolHandlerInit:
    """Tests for ProtocolHandler initialization."""

    def test_attributes_stored(self, tmp_path: Path) -> None:
        handler = _make_handler(tmp_path, spec_context="some context")

        assert handler.worker_id == 1
        assert handler.feature == "test-feature"
        assert handler.branch == "zerg/test-feature/w1"
        assert handler.worktree_path == tmp_path
        assert handler._spec_context == "some context"

    def test_optional_fields_default_to_none(self, tmp_path: Path) -> None:
        handler = ProtocolHandler(
            worker_id=2,
            feature="f",
            branch="b",
            worktree_path=tmp_path,
            state=MagicMock(),
            git=MagicMock(),
            verifier=MagicMock(),
            context_tracker=MagicMock(),
            config=_make_config(),
        )

        assert handler._structured_writer is None
        assert handler._plugin_registry is None
        assert handler._spec_context == ""
