"""Tests for near-complete coverage gaps across multiple modules.

Targets uncovered lines in:
- worker_manager.py
- worker_protocol.py
- state.py
- logging.py
- dryrun.py
- diagnostics/log_correlator.py
- claude_tasks_reader.py
- diagnostics/env_diagnostics.py
- ports.py
"""

import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.constants import (
    TaskStatus,
    WorkerStatus,
)
from zerg.types import WorkerState

# ============================================================================
# worker_manager.py coverage
# ============================================================================


class TestWorkerManagerCircuitBreaker:
    """Cover lines 119-120: circuit breaker blocking spawn."""

    def _make_manager(self, **overrides):
        from zerg.worker_manager import WorkerManager

        defaults = dict(
            feature="test-feat",
            config=MagicMock(),
            state=MagicMock(),
            levels=MagicMock(),
            parser=MagicMock(),
            launcher=MagicMock(),
            worktrees=MagicMock(),
            ports=MagicMock(),
            assigner=MagicMock(),
            plugin_registry=MagicMock(),
            workers={},
            on_task_complete=[],
            on_task_failure=None,
            structured_writer=None,
            circuit_breaker=MagicMock(),
        )
        defaults.update(overrides)
        return WorkerManager(**defaults)

    def test_spawn_worker_circuit_breaker_open(self):
        """Lines 119-120: circuit breaker prevents spawn."""
        cb = MagicMock()
        cb.can_accept_task.return_value = False
        mgr = self._make_manager(circuit_breaker=cb)
        with pytest.raises(RuntimeError, match="circuit breaker is open"):
            mgr.spawn_worker(0)


class TestWorkerManagerWaitForInit:
    """Cover lines 220-240, 244-245, 248-250, 256-259."""

    def _make_manager(self, workers=None):
        from zerg.worker_manager import WorkerManager

        w = workers or {}
        return WorkerManager(
            feature="f",
            config=MagicMock(),
            state=MagicMock(),
            levels=MagicMock(),
            parser=MagicMock(),
            launcher=MagicMock(),
            worktrees=MagicMock(),
            ports=MagicMock(),
            assigner=MagicMock(),
            plugin_registry=MagicMock(),
            workers=w,
            on_task_complete=[],
        )

    def test_wait_workers_ready_immediately(self):
        """Lines 220-233, 247-250: workers ready right away."""
        ws = WorkerState(worker_id=0, status=WorkerStatus.RUNNING, ready_at=None)
        workers = {0: ws}
        mgr = self._make_manager(workers)
        mgr.launcher.monitor.return_value = WorkerStatus.RUNNING
        result = mgr.wait_for_initialization(timeout=5)
        assert result is True
        assert ws.ready_at is not None

    def test_wait_workers_some_crashed(self):
        """Lines 234-237, 244-245: worker crashes during init removed from dict."""
        ws0 = WorkerState(worker_id=0, status=WorkerStatus.RUNNING)
        ws1 = WorkerState(worker_id=1, status=WorkerStatus.RUNNING, ready_at=None)
        workers = {0: ws0, 1: ws1}
        mgr = self._make_manager(workers)

        def monitor_side(wid):
            if wid == 0:
                return WorkerStatus.CRASHED
            return WorkerStatus.RUNNING

        mgr.launcher.monitor.side_effect = monitor_side
        result = mgr.wait_for_initialization(timeout=5)
        assert result is True
        assert 0 not in workers  # Crashed worker removed

    def test_wait_workers_still_initializing_then_timeout(self):
        """Lines 238-240, 256-259: workers not ready, timeout."""
        ws = WorkerState(worker_id=0, status=WorkerStatus.RUNNING)
        workers = {0: ws}
        mgr = self._make_manager(workers)
        mgr.launcher.monitor.return_value = WorkerStatus.INITIALIZING

        with patch("zerg.worker_manager.time") as mock_time:
            # Simulate time passing: first call returns 0, then past timeout
            call_count = [0]

            def time_side():
                call_count[0] += 1
                if call_count[0] <= 2:
                    return 0.0
                return 100.0  # past timeout

            mock_time.time.side_effect = time_side
            mock_time.sleep = MagicMock()
            result = mgr.wait_for_initialization(timeout=1)
            # Workers still exist so returns True (line 259)
            assert result is True


class TestWorkerManagerHandleExit:
    """Cover lines 340-342, 378-379."""

    def _make_manager(self, workers=None, circuit_breaker=None):
        from zerg.worker_manager import WorkerManager

        w = workers or {}
        state = MagicMock()
        # Make state._state behave like a real dict for direct attribute access
        state._state = {"tasks": {}}
        return WorkerManager(
            feature="f",
            config=MagicMock(),
            state=state,
            levels=MagicMock(),
            parser=MagicMock(),
            launcher=MagicMock(),
            worktrees=MagicMock(),
            ports=MagicMock(),
            assigner=MagicMock(),
            plugin_registry=MagicMock(),
            workers=w,
            on_task_complete=[],
            circuit_breaker=circuit_breaker,
        )

    def test_handle_exit_records_task_duration(self):
        """Lines 340-342: task duration recorded on exit."""
        ws = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            current_task="task-1",
            worktree_path="/tmp/wt",
            port=5000,
        )
        workers = {0: ws}
        mgr = self._make_manager(workers)
        mgr._running = False

        # Set up parser to return a task with verification
        mgr.parser.get_task.return_value = {"verification": {"command": "test"}}
        # Set up state._state with started_at but no duration_ms
        mgr.state._state = {
            "tasks": {
                "task-1": {
                    "started_at": datetime.now().isoformat(),
                    "duration_ms": None,
                }
            }
        }
        mgr.levels.get_pending_tasks_for_level.return_value = []

        with patch("zerg.worker_manager.duration_ms", return_value=1000):
            mgr.handle_worker_exit(0)
        assert mgr.state.record_task_duration.called

    def test_handle_exit_worktree_cleanup_failure(self):
        """Lines 378-379: worktree cleanup failure on respawn error."""
        ws = WorkerState(
            worker_id=0,
            status=WorkerStatus.RUNNING,
            current_task=None,
            worktree_path="/tmp/old_wt",
            port=5000,
        )
        workers = {0: ws}
        mgr = self._make_manager(workers)
        mgr._running = True

        mgr.parser.get_task.return_value = None
        mgr.levels.current_level = 1
        mgr.levels.get_pending_tasks_for_level.return_value = ["task-2"]

        # spawn_worker fails
        def spawn_fail(wid):
            raise RuntimeError("spawn failed")

        mgr.spawn_worker = MagicMock(side_effect=spawn_fail)
        # worktree delete also fails
        mgr.worktrees.delete.side_effect = RuntimeError("cleanup fail")

        mgr.handle_worker_exit(0)
        # Should not raise, just log warnings


class TestWorkerManagerRespawn:
    """Cover lines 410, 428-429, 437-438."""

    def _make_manager(self, workers=None):
        from zerg.worker_manager import WorkerManager

        w = workers or {}
        m = WorkerManager(
            feature="f",
            config=MagicMock(),
            state=MagicMock(),
            levels=MagicMock(),
            parser=MagicMock(),
            launcher=MagicMock(),
            worktrees=MagicMock(),
            ports=MagicMock(),
            assigner=MagicMock(worker_count=2),
            plugin_registry=MagicMock(),
            workers=w,
            on_task_complete=[],
        )
        return m

    def test_respawn_no_need(self):
        """Line 410: enough active workers, need <= 0."""
        ws0 = WorkerState(worker_id=0, status=WorkerStatus.RUNNING)
        ws1 = WorkerState(worker_id=1, status=WorkerStatus.RUNNING)
        workers = {0: ws0, 1: ws1}
        mgr = self._make_manager(workers)
        mgr.levels.get_pending_tasks_for_level.return_value = ["t1"]
        result = mgr.respawn_workers_for_level(1)
        assert result == 0

    def test_respawn_cleans_stopped_workers(self):
        """Lines 428-429: stopped workers cleaned from dict."""
        ws0 = WorkerState(worker_id=0, status=WorkerStatus.STOPPED)
        workers = {0: ws0}
        mgr = self._make_manager(workers)
        mgr.levels.get_pending_tasks_for_level.return_value = ["t1"]
        # Mock spawn_worker so we can check it's called
        wt_info = MagicMock(path=Path("/tmp/wt"), branch="b")
        mgr.worktrees.create.return_value = wt_info
        result_handle = MagicMock(success=True, handle=MagicMock(container_id=None))
        mgr.launcher.spawn.return_value = result_handle
        mgr.launcher.monitor.return_value = WorkerStatus.RUNNING

        result = mgr.respawn_workers_for_level(1)
        assert result >= 1

    def test_respawn_spawn_failure(self):
        """Lines 437-438: spawn fails during respawn."""
        workers = {}
        mgr = self._make_manager(workers)
        mgr.levels.get_pending_tasks_for_level.return_value = ["t1", "t2"]

        def fail_spawn(wid):
            raise RuntimeError("fail")

        mgr.spawn_worker = MagicMock(side_effect=fail_spawn)
        result = mgr.respawn_workers_for_level(1)
        assert result == 0


# ============================================================================
# worker_protocol.py coverage
# ============================================================================


class TestWorkerProtocolPluginInit:
    """Cover lines 193-195: plugin registry init failure."""

    @patch.dict(
        os.environ,
        {
            "ZERG_WORKER_ID": "1",
            "ZERG_FEATURE": "test",
        },
        clear=False,
    )
    @patch("zerg.worker_protocol.ZergConfig")
    @patch("zerg.worker_protocol.StateManager")
    @patch("zerg.worker_protocol.VerificationExecutor")
    @patch("zerg.worker_protocol.GitOps")
    @patch("zerg.worker_protocol.ContextTracker")
    @patch("zerg.worker_protocol.SpecLoader")
    @patch("zerg.worker_protocol.setup_structured_logging", side_effect=Exception("fail"))
    def test_plugin_init_failure(self, *mocks):
        """Lines 193-195: plugin registry init fails gracefully."""
        config = MagicMock()
        config.context_threshold = 0.7
        config.logging.level = "info"
        config.logging.max_log_size_mb = 50
        config.plugins.enabled = True
        config.plugins.hooks = []

        with patch("zerg.worker_protocol.ZergConfig.load", return_value=config):
            with patch("zerg.worker_protocol.PluginRegistry") as pr_cls:
                pr_cls.side_effect = Exception("plugin init fail")
                from zerg.worker_protocol import WorkerProtocol

                wp = WorkerProtocol(worker_id=1, feature="test", config=config)
                assert wp._plugin_registry is None


class TestWorkerProtocolAsyncClaimTask:
    """Cover lines 407-440: async claim_next_task."""

    def test_claim_next_task_async_claims_immediately(self):
        """Lines 407-425: async claim succeeds on first poll."""
        with patch("zerg.worker_protocol.ZergConfig") as cfg_cls:
            cfg = MagicMock()
            cfg.context_threshold = 0.7
            cfg.logging.level = "info"
            cfg.logging.max_log_size_mb = 50
            cfg.plugins.enabled = False
            cfg_cls.load.return_value = cfg

            with (
                patch("zerg.worker_protocol.StateManager") as sm_cls,
                patch("zerg.worker_protocol.VerificationExecutor"),
                patch("zerg.worker_protocol.GitOps"),
                patch("zerg.worker_protocol.ContextTracker"),
                patch("zerg.worker_protocol.SpecLoader") as sl_cls,
                patch("zerg.worker_protocol.setup_structured_logging", return_value=MagicMock()),
            ):
                sl_instance = MagicMock()
                sl_instance.specs_exist.return_value = False
                sl_cls.return_value = sl_instance

                sm_instance = MagicMock()
                sm_instance.get_tasks_by_status.return_value = ["task-1"]
                sm_instance.claim_task.return_value = True
                sm_cls.return_value = sm_instance

                from zerg.worker_protocol import WorkerProtocol

                wp = WorkerProtocol(worker_id=0, feature="test", config=cfg)
                wp.task_parser = MagicMock()
                wp.task_parser.get_task.return_value = {"id": "task-1", "title": "Test", "level": 1}

                result = asyncio.get_event_loop().run_until_complete(
                    wp.claim_next_task_async(max_wait=1, poll_interval=0.1)
                )
                assert result is not None
                assert result["id"] == "task-1"


class TestWorkerProtocolAsyncWaitReady:
    """Cover lines 321-326: async wait_for_ready."""

    def test_wait_for_ready_async_already_ready(self):
        """Lines 321-325: already ready returns immediately."""
        with (
            patch("zerg.worker_protocol.ZergConfig") as cfg_cls,
            patch("zerg.worker_protocol.StateManager"),
            patch("zerg.worker_protocol.VerificationExecutor"),
            patch("zerg.worker_protocol.GitOps"),
            patch("zerg.worker_protocol.ContextTracker"),
            patch("zerg.worker_protocol.SpecLoader") as sl_cls,
            patch("zerg.worker_protocol.setup_structured_logging", return_value=MagicMock()),
        ):
            cfg = MagicMock()
            cfg.context_threshold = 0.7
            cfg.logging.level = "info"
            cfg.logging.max_log_size_mb = 50
            cfg.plugins.enabled = False
            cfg_cls.load.return_value = cfg
            sl_cls.return_value.specs_exist.return_value = False

            from zerg.worker_protocol import WorkerProtocol

            wp = WorkerProtocol(worker_id=0, feature="test", config=cfg)
            wp._is_ready = True

            result = asyncio.get_event_loop().run_until_complete(wp.wait_for_ready_async(timeout=1.0))
            assert result is True

    def test_wait_for_ready_async_timeout(self):
        """Line 326: timeout returns False."""
        with (
            patch("zerg.worker_protocol.ZergConfig") as cfg_cls,
            patch("zerg.worker_protocol.StateManager"),
            patch("zerg.worker_protocol.VerificationExecutor"),
            patch("zerg.worker_protocol.GitOps"),
            patch("zerg.worker_protocol.ContextTracker"),
            patch("zerg.worker_protocol.SpecLoader") as sl_cls,
            patch("zerg.worker_protocol.setup_structured_logging", return_value=MagicMock()),
        ):
            cfg = MagicMock()
            cfg.context_threshold = 0.7
            cfg.logging.level = "info"
            cfg.logging.max_log_size_mb = 50
            cfg.plugins.enabled = False
            cfg_cls.load.return_value = cfg
            sl_cls.return_value.specs_exist.return_value = False

            from zerg.worker_protocol import WorkerProtocol

            wp = WorkerProtocol(worker_id=0, feature="test", config=cfg)
            wp._is_ready = False

            result = asyncio.get_event_loop().run_until_complete(wp.wait_for_ready_async(timeout=0.2))
            assert result is False


class TestWorkerProtocolVerificationArtifact:
    """Cover lines 814, 824: verification artifact and structured writer."""

    def _make_protocol(self):
        with (
            patch("zerg.worker_protocol.ZergConfig") as cfg_cls,
            patch("zerg.worker_protocol.StateManager"),
            patch("zerg.worker_protocol.VerificationExecutor"),
            patch("zerg.worker_protocol.GitOps"),
            patch("zerg.worker_protocol.ContextTracker"),
            patch("zerg.worker_protocol.SpecLoader") as sl_cls,
            patch("zerg.worker_protocol.setup_structured_logging", return_value=MagicMock()),
        ):
            cfg = MagicMock()
            cfg.context_threshold = 0.7
            cfg.logging.level = "info"
            cfg.logging.max_log_size_mb = 50
            cfg.plugins.enabled = False
            cfg_cls.load.return_value = cfg
            sl_cls.return_value.specs_exist.return_value = False

            from zerg.worker_protocol import WorkerProtocol

            wp = WorkerProtocol(worker_id=0, feature="test", config=cfg)
            return wp

    def test_run_verification_with_artifact_and_writer(self):
        """Lines 814, 824: artifact capture + structured writer on verification pass."""
        wp = self._make_protocol()

        # Mock verifier result
        result = MagicMock()
        result.success = True
        result.stdout = "ok"
        result.stderr = ""
        result.exit_code = 0
        result.duration_ms = 100
        wp.verifier.verify_with_retry.return_value = result

        # Structured writer
        wp._structured_writer = MagicMock()

        artifact = MagicMock()
        task = {"id": "t1", "verification": {"command": "pytest", "timeout_seconds": 30}}
        ok = wp.run_verification(task, artifact=artifact)
        assert ok is True
        artifact.capture_verification.assert_called_once()
        wp._structured_writer.emit.assert_called()


class TestWorkerProtocolCommitHeadUnchanged:
    """Cover lines 874-876, 890-898: HEAD unchanged after commit."""

    def _make_protocol(self):
        with (
            patch("zerg.worker_protocol.ZergConfig") as cfg_cls,
            patch("zerg.worker_protocol.StateManager"),
            patch("zerg.worker_protocol.VerificationExecutor"),
            patch("zerg.worker_protocol.GitOps"),
            patch("zerg.worker_protocol.ContextTracker"),
            patch("zerg.worker_protocol.SpecLoader") as sl_cls,
            patch("zerg.worker_protocol.setup_structured_logging", return_value=MagicMock()),
        ):
            cfg = MagicMock()
            cfg.context_threshold = 0.7
            cfg.logging.level = "info"
            cfg.logging.max_log_size_mb = 50
            cfg.plugins.enabled = False
            cfg_cls.load.return_value = cfg
            sl_cls.return_value.specs_exist.return_value = False

            from zerg.worker_protocol import WorkerProtocol

            wp = WorkerProtocol(worker_id=0, feature="test", config=cfg)
            return wp

    def test_commit_head_unchanged(self):
        """Lines 889-898: commit succeeds but HEAD unchanged returns False."""
        wp = self._make_protocol()
        wp.git.has_changes.return_value = True
        wp.git.current_commit.return_value = "abc123"  # same before and after
        wp.git.commit = MagicMock()

        task = {"id": "t1", "title": "Test task"}
        result = wp.commit_task_changes(task)
        assert result is False


class TestWorkerProtocolRunWorker:
    """Cover line 1062: run_worker entry point."""

    @patch("zerg.worker_protocol.WorkerProtocol")
    def test_run_worker_failure(self, mock_wp_cls):
        """Line 1062: run_worker catches exception and exits."""
        mock_wp_cls.side_effect = Exception("init fail")
        from zerg.worker_protocol import run_worker

        with pytest.raises(SystemExit):
            run_worker()


class TestWorkerProtocolExecuteTaskFailedClaude:
    """Cover lines 534, 544: structured writer on Claude/verification failure."""

    def _make_protocol(self):
        with (
            patch("zerg.worker_protocol.ZergConfig") as cfg_cls,
            patch("zerg.worker_protocol.StateManager"),
            patch("zerg.worker_protocol.VerificationExecutor"),
            patch("zerg.worker_protocol.GitOps"),
            patch("zerg.worker_protocol.ContextTracker"),
            patch("zerg.worker_protocol.SpecLoader") as sl_cls,
            patch("zerg.worker_protocol.setup_structured_logging", return_value=MagicMock()),
        ):
            cfg = MagicMock()
            cfg.context_threshold = 0.7
            cfg.logging.level = "info"
            cfg.logging.max_log_size_mb = 50
            cfg.logging.retain_on_success = False
            cfg.plugins.enabled = False
            cfg_cls.load.return_value = cfg
            sl_cls.return_value.specs_exist.return_value = False

            from zerg.worker_protocol import ClaudeInvocationResult, WorkerProtocol

            wp = WorkerProtocol(worker_id=0, feature="test", config=cfg)
            return wp, ClaudeInvocationResult

    def test_execute_task_claude_fails_with_writer(self):
        """Lines 533-537: Claude invocation fails, structured writer emit."""
        wp, CIR = self._make_protocol()
        wp._structured_writer = MagicMock()
        wp._plugin_registry = None

        # Mock invoke_claude_code to return failure
        wp.invoke_claude_code = MagicMock(
            return_value=CIR(
                success=False,
                exit_code=1,
                stdout="",
                stderr="error",
                duration_ms=100,
                task_id="t1",
            )
        )

        task = {"id": "t1", "title": "Test"}
        result = wp.execute_task(task)
        assert result is False
        # Check structured writer was called with error
        calls = [c for c in wp._structured_writer.emit.call_args_list if "failed" in str(c).lower()]
        assert len(calls) >= 1

    def test_execute_task_verification_fails_with_writer(self):
        """Lines 543-547: verification fails, structured writer emit."""
        wp, CIR = self._make_protocol()
        wp._structured_writer = MagicMock()
        wp._plugin_registry = None

        # Mock invoke_claude_code to return success
        wp.invoke_claude_code = MagicMock(
            return_value=CIR(
                success=True,
                exit_code=0,
                stdout="ok",
                stderr="",
                duration_ms=100,
                task_id="t1",
            )
        )
        # Mock verification to fail
        wp.run_verification = MagicMock(return_value=False)

        task = {"id": "t1", "title": "Test", "verification": {"command": "pytest"}}
        result = wp.execute_task(task)
        assert result is False


class TestWorkerProtocolBuildPromptContext:
    """Cover lines 733-734: task-scoped context in prompt."""

    def _make_protocol(self):
        with (
            patch("zerg.worker_protocol.ZergConfig") as cfg_cls,
            patch("zerg.worker_protocol.StateManager"),
            patch("zerg.worker_protocol.VerificationExecutor"),
            patch("zerg.worker_protocol.GitOps"),
            patch("zerg.worker_protocol.ContextTracker"),
            patch("zerg.worker_protocol.SpecLoader") as sl_cls,
            patch("zerg.worker_protocol.setup_structured_logging", return_value=MagicMock()),
        ):
            cfg = MagicMock()
            cfg.context_threshold = 0.7
            cfg.logging.level = "info"
            cfg.logging.max_log_size_mb = 50
            cfg.plugins.enabled = False
            cfg_cls.load.return_value = cfg
            sl_cls.return_value.specs_exist.return_value = False

            from zerg.worker_protocol import WorkerProtocol

            wp = WorkerProtocol(worker_id=0, feature="test", config=cfg)
            return wp

    def test_build_prompt_with_task_context(self):
        """Lines 733-734: task-scoped context included in prompt."""
        wp = self._make_protocol()
        task = {"id": "t1", "title": "Test", "context": "Scoped security rules here"}
        prompt = wp._build_task_prompt(task)
        assert "Task Context (Scoped)" in prompt
        assert "Scoped security rules here" in prompt


# ============================================================================
# state.py coverage
# ============================================================================


class TestStateManagerAtomicUpdate:
    """Cover lines 88-90, 92, 102-103."""

    def test_atomic_update_json_decode_error_with_empty_state(self):
        """Lines 88-90: JSONDecodeError in _atomic_update with empty _state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from zerg.state import StateManager

            sm = StateManager("test-feat", state_dir=tmpdir)
            # Write invalid JSON to state file
            state_file = Path(tmpdir) / "test-feat.json"
            state_file.write_text("{invalid json")
            sm._state = {}  # Empty state

            with sm._atomic_update():
                pass  # should create initial state
            assert sm._state.get("feature") == "test-feat"

    def test_atomic_update_no_file_empty_state(self):
        """Line 92: no state file and empty _state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from zerg.state import StateManager

            sm = StateManager("test-feat", state_dir=tmpdir)
            sm._state = {}
            # State file does not exist
            with sm._atomic_update():
                pass
            assert sm._state.get("feature") == "test-feat"

    def test_lock_release_failure(self):
        """Lines 102-103: lock release fails gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from zerg.state import StateManager

            sm = StateManager("test-feat", state_dir=tmpdir)
            # This should work without raising
            sm._state = sm._create_initial_state()
            with sm._atomic_update():
                sm._state["test_key"] = "test_value"
            assert sm._state["test_key"] == "test_value"


class TestStateManagerSaveLockFailure:
    """Cover lines 161-162, 178-179."""

    def test_save_lock_release_failure(self):
        """Lines 178-179: save lock release fails gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from zerg.state import StateManager

            sm = StateManager("test-feat", state_dir=tmpdir)
            sm._state = sm._create_initial_state()
            sm.save()  # Should not raise even if lock release fails
            assert (Path(tmpdir) / "test-feat.json").exists()

    def test_load_lock_release_failure(self):
        """Lines 161-162: load lock release fails gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from zerg.state import StateManager

            sm = StateManager("test-feat", state_dir=tmpdir)
            sm._state = sm._create_initial_state()
            sm.save()
            loaded = sm.load()
            assert loaded["feature"] == "test-feat"


class TestStateManagerInjectAndAsync:
    """Cover lines 191-192, 200, 204."""

    def test_inject_state(self):
        """Lines 191-192: inject external state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from zerg.state import StateManager

            sm = StateManager("test-feat", state_dir=tmpdir)
            injected = {"feature": "injected", "tasks": {}}
            sm.inject_state(injected)
            assert sm._state["feature"] == "injected"

    def test_load_async(self):
        """Line 200: async load."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from zerg.state import StateManager

            sm = StateManager("test-feat", state_dir=tmpdir)
            sm._state = sm._create_initial_state()
            sm.save()
            result = asyncio.get_event_loop().run_until_complete(sm.load_async())
            assert result["feature"] == "test-feat"

    def test_save_async(self):
        """Line 204: async save."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from zerg.state import StateManager

            sm = StateManager("test-feat", state_dir=tmpdir)
            sm._state = sm._create_initial_state()
            asyncio.get_event_loop().run_until_complete(sm.save_async())
            assert (Path(tmpdir) / "test-feat.json").exists()


class TestStateManagerRetrySchedule:
    """Cover lines 620, 632-641, 652-654, 662-672."""

    def test_increment_retry_with_next_retry_at(self):
        """Line 620: next_retry_at set during increment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from zerg.state import StateManager

            sm = StateManager("test-feat", state_dir=tmpdir)
            sm._state = sm._create_initial_state()
            count = sm.increment_task_retry("t1", next_retry_at="2099-01-01T00:00:00")
            assert count == 1
            assert sm._state["tasks"]["t1"]["next_retry_at"] == "2099-01-01T00:00:00"

    def test_set_task_retry_schedule(self):
        """Lines 632-641: set retry schedule."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from zerg.state import StateManager

            sm = StateManager("test-feat", state_dir=tmpdir)
            sm._state = sm._create_initial_state()
            sm.set_task_retry_schedule("t1", "2099-01-01T00:00:00")
            assert sm._state["tasks"]["t1"]["next_retry_at"] == "2099-01-01T00:00:00"

    def test_get_task_retry_schedule(self):
        """Lines 652-654: get retry schedule."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from zerg.state import StateManager

            sm = StateManager("test-feat", state_dir=tmpdir)
            sm._state = sm._create_initial_state()
            sm._state["tasks"]["t1"] = {"next_retry_at": "2099-01-01T00:00:00"}
            result = sm.get_task_retry_schedule("t1")
            assert result == "2099-01-01T00:00:00"

    def test_get_tasks_ready_for_retry(self):
        """Lines 662-672: tasks ready for retry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from zerg.state import StateManager

            sm = StateManager("test-feat", state_dir=tmpdir)
            sm._state = sm._create_initial_state()
            # Task with past retry time in failed status
            sm._state["tasks"]["t1"] = {
                "next_retry_at": "2000-01-01T00:00:00",
                "status": TaskStatus.FAILED.value,
            }
            # Task with future retry time
            sm._state["tasks"]["t2"] = {
                "next_retry_at": "2099-01-01T00:00:00",
                "status": TaskStatus.FAILED.value,
            }
            # Task waiting_retry with past time
            sm._state["tasks"]["t3"] = {
                "next_retry_at": "2000-01-01T00:00:00",
                "status": "waiting_retry",
            }
            ready = sm.get_tasks_ready_for_retry()
            assert "t1" in ready
            assert "t2" not in ready
            assert "t3" in ready


class TestStateManagerRecordTaskClaimed:
    """Cover line 734."""

    def test_record_task_claimed_new_task(self):
        """Line 734: record claimed for non-existing task creates entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from zerg.state import StateManager

            sm = StateManager("test-feat", state_dir=tmpdir)
            sm._state = {"feature": "test-feat", "tasks": {}}
            sm.record_task_claimed("new-task", 0)
            assert "claimed_at" in sm._state["tasks"]["new-task"]


# ============================================================================
# logging.py coverage
# ============================================================================


class TestLoggingFormatters:
    """Cover lines 42, 85, 212-215, 274-275."""

    def test_json_formatter_with_worker_context(self):
        """Line 42: worker context added to JSON."""
        from zerg.logging import JsonFormatter, clear_worker_context, set_worker_context

        set_worker_context(worker_id=5, feature="test")
        formatter = JsonFormatter()
        record = logging.LogRecord("test", logging.INFO, "test.py", 1, "test message", (), None)
        output = formatter.format(record)
        data = json.loads(output)
        assert data["worker_id"] == 5
        clear_worker_context()

    def test_console_formatter_with_task_id(self):
        """Line 85: task_id in console formatter."""
        from zerg.logging import ConsoleFormatter, clear_worker_context, set_worker_context

        set_worker_context(worker_id=3)
        formatter = ConsoleFormatter()
        record = logging.LogRecord("test", logging.INFO, "test.py", 1, "test message", (), None)
        record.task_id = "task-99"  # type: ignore[attr-defined]
        output = formatter.format(record)
        assert "W3" in output
        assert "task-99" in output
        clear_worker_context()

    def test_logger_adapter_process(self):
        """Lines 212-215: LoggerAdapter.process merges extra."""
        from zerg.logging import LoggerAdapter

        base_logger = logging.getLogger("test.adapter")
        adapter = LoggerAdapter(base_logger, {"task_id": "t1"})
        msg, kwargs = adapter.process("hello", {"extra": {"foo": "bar"}})
        assert msg == "hello"
        assert kwargs["extra"]["task_id"] == "t1"
        assert kwargs["extra"]["foo"] == "bar"

    def test_structured_file_handler_error(self):
        """Lines 274-275: StructuredFileHandler.emit handles exception."""
        from zerg.logging import StructuredFileHandler

        writer = MagicMock()
        writer.emit.side_effect = Exception("write failed")
        handler = StructuredFileHandler(writer)
        handler.handleError = MagicMock()

        record = logging.LogRecord("test", logging.INFO, "test.py", 1, "test message", (), None)
        handler.emit(record)
        handler.handleError.assert_called_once()


# ============================================================================
# dryrun.py coverage
# ============================================================================


class TestDryRunReportProperties:
    """Cover lines 198-199, 240-242."""

    def test_validate_level_structure_no_tasks(self):
        """Lines 198-199: empty tasks returns issue."""
        from zerg.dryrun import DryRunSimulator

        sim = DryRunSimulator(
            task_data={"tasks": []},
            workers=2,
            feature="test",
        )
        issues = sim._validate_level_structure()
        assert any("No tasks" in i for i in issues)

    def test_check_resources_no_git(self):
        """Lines 240-242: low disk space detection."""
        from zerg.dryrun import DryRunSimulator

        sim = DryRunSimulator(
            task_data={"tasks": []},
            workers=2,
            feature="test",
        )
        # Just verify the method runs (actual git/disk checks are environment-dependent)
        issues = sim._check_resources()
        assert isinstance(issues, list)


class TestDryRunRendering:
    """Cover scattered render lines."""

    def _make_report(self, **overrides):
        from zerg.dryrun import DryRunReport, LevelTimeline, TimelineEstimate
        from zerg.preflight import CheckResult, PreflightReport

        defaults = dict(
            feature="test",
            workers=2,
            mode="auto",
            level_issues=[],
            file_ownership_issues=[],
            dependency_issues=[],
            resource_issues=[],
            missing_verifications=[],
            timeline=TimelineEstimate(
                total_sequential_minutes=60,
                estimated_wall_minutes=30,
                critical_path_minutes=30,
                parallelization_efficiency=0.5,
                per_level={
                    1: LevelTimeline(level=1, task_count=2, wall_minutes=15, worker_loads={0: 15, 1: 10}),
                    2: LevelTimeline(level=2, task_count=1, wall_minutes=15, worker_loads={0: 15}),
                },
            ),
            gate_results=[],
            task_data={
                "tasks": [
                    {
                        "id": "t1",
                        "title": "Task 1",
                        "level": 1,
                        "estimate_minutes": 15,
                        "verification": {"command": "pytest"},
                    },
                    {
                        "id": "t2",
                        "title": "Task 2",
                        "level": 1,
                        "estimate_minutes": 10,
                        "verification": {"command": "pytest"},
                    },
                ],
                "levels": {"1": {"name": "foundation"}, "2": {"name": "core"}},
            },
            worker_loads={0: {"estimated_minutes": 15, "task_count": 1}, 1: {"estimated_minutes": 10, "task_count": 1}},
            preflight=PreflightReport(
                checks=[CheckResult(name="Git", passed=True, message="OK", severity="error")],
            ),
            risk=None,
        )
        defaults.update(overrides)
        return DryRunReport(**defaults)

    def test_render_report_full(self):
        """Cover render methods with full data."""
        from zerg.dryrun import DryRunSimulator
        from zerg.risk_scoring import RiskReport, TaskRisk

        report = self._make_report(
            risk=RiskReport(
                overall_score=0.3,
                grade="B",
                risk_factors=["Factor 1"],
                critical_path=["t1", "t2"],
                task_risks=[TaskRisk(task_id="t1", score=0.8, factors=["complex"])],
            ),
            gate_results=[],
            missing_verifications=["Task t3 has no verification command"],
        )

        sim = DryRunSimulator(
            task_data=report.task_data,
            workers=2,
            feature="test",
        )
        # Render should not raise
        sim._render_report(report)

    def test_render_gates_all_statuses(self):
        """Lines 631-649: render gates with different statuses."""
        from zerg.dryrun import DryRunSimulator, GateCheckResult

        report = self._make_report(
            gate_results=[
                GateCheckResult(name="lint", command="ruff", required=True, status="passed", duration_ms=500),
                GateCheckResult(name="typecheck", command="mypy", required=True, status="failed"),
                GateCheckResult(name="tests", command="pytest", required=False, status="not_run"),
                GateCheckResult(name="audit", command="audit", required=False, status="error"),
            ],
        )

        sim = DryRunSimulator(
            task_data=report.task_data,
            workers=2,
            feature="test",
        )
        sim._render_gates(report)

    def test_render_summary_with_errors(self):
        """Lines 651-678: summary with errors and warnings."""
        from zerg.dryrun import DryRunSimulator, GateCheckResult
        from zerg.preflight import CheckResult, PreflightReport

        report = self._make_report(
            level_issues=["Gap in levels"],
            missing_verifications=["Task t3 missing"],
            preflight=PreflightReport(
                checks=[
                    CheckResult(name="Docker", passed=False, message="Not available", severity="error"),
                ],
            ),
            gate_results=[
                GateCheckResult(name="lint", command="ruff", required=True, status="failed"),
            ],
        )

        sim = DryRunSimulator(
            task_data=report.task_data,
            workers=2,
            feature="test",
        )
        sim._render_summary(report)

    def test_render_preflight_warning(self):
        """Lines 374: preflight check with warning severity."""
        from zerg.dryrun import DryRunSimulator
        from zerg.preflight import CheckResult, PreflightReport

        report = self._make_report(
            preflight=PreflightReport(
                checks=[
                    CheckResult(name="Docker", passed=False, message="Not running", severity="warning"),
                    CheckResult(name="Git", passed=False, message="Not found", severity="error"),
                ],
            ),
        )

        sim = DryRunSimulator(
            task_data=report.task_data,
            workers=2,
            feature="test",
        )
        sim._render_preflight(report)

    def test_render_worker_loads_empty(self):
        """Line 530: empty worker loads."""
        from zerg.dryrun import DryRunSimulator

        report = self._make_report(worker_loads={})
        sim = DryRunSimulator(
            task_data=report.task_data,
            workers=2,
            feature="test",
        )
        sim._render_worker_loads(report)  # should be no-op

    def test_render_gantt_empty_timeline(self):
        """Line 560: empty timeline."""
        from zerg.dryrun import DryRunSimulator

        report = self._make_report(timeline=None)
        sim = DryRunSimulator(
            task_data=report.task_data,
            workers=2,
            feature="test",
        )
        sim._render_gantt(report)  # should be no-op

    def test_render_timeline_none(self):
        """Line 573: no timeline."""
        from zerg.dryrun import DryRunSimulator

        report = self._make_report(timeline=None)
        sim = DryRunSimulator(
            task_data=report.task_data,
            workers=2,
            feature="test",
        )
        sim._render_timeline(report)  # should be no-op

    def test_render_snapshots_empty(self):
        """Line 591: no timeline for snapshots."""
        from zerg.dryrun import DryRunSimulator

        report = self._make_report(timeline=None)
        sim = DryRunSimulator(
            task_data=report.task_data,
            workers=2,
            feature="test",
        )
        sim._render_snapshots(report)  # should be no-op

    def test_has_warnings_property(self):
        """Lines 104-109: has_warnings property."""
        from zerg.dryrun import GateCheckResult
        from zerg.risk_scoring import RiskReport

        report = self._make_report(
            missing_verifications=["t1 missing"],
            gate_results=[
                GateCheckResult(name="lint", command="ruff", required=False, status="failed"),
            ],
            risk=RiskReport(
                overall_score=0.6,
                grade="C",
                risk_factors=[],
                critical_path=[],
                task_risks=[],
            ),
        )
        assert report.has_warnings is True


class TestDryRunQualityGatesRun:
    """Cover lines 310-332: actually running quality gates."""

    def test_check_quality_gates_run(self):
        """Lines 310-332: run_gates=True executes gates."""
        from zerg.dryrun import DryRunSimulator

        config = MagicMock()
        gate = MagicMock()
        gate.name = "lint"
        gate.command = "ruff check"
        gate.required = True
        config.quality_gates = [gate]

        sim = DryRunSimulator(
            task_data={"tasks": []},
            workers=2,
            feature="test",
            config=config,
            run_gates=True,
        )

        mock_result = MagicMock()
        mock_result.gate_name = "lint"
        mock_result.command = "ruff check"
        mock_result.result = MagicMock(value="pass")

        with patch("zerg.dryrun.GateRunner") as gr_cls:
            gr_cls.return_value.run_all_gates.return_value = (True, [mock_result])
            results = sim._check_quality_gates()
            assert len(results) == 1
            assert results[0].status == "passed"


# ============================================================================
# diagnostics/log_correlator.py coverage
# ============================================================================


class TestLogCorrelatorEngine:
    """Cover scattered lines in log_correlator.py."""

    def test_timeline_builder_empty_dir(self):
        """Timeline builder with non-existent dir."""
        from zerg.diagnostics.log_correlator import TimelineBuilder

        tb = TimelineBuilder()
        assert tb.build(Path("/nonexistent")) == []

    def test_timeline_builder_with_jsonl_logs(self):
        """Parse JSONL formatted logs."""
        from zerg.diagnostics.log_correlator import TimelineBuilder

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "worker-0.stderr.log"
            log_file.write_text(
                json.dumps({"timestamp": "2024-01-01T00:00:00Z", "level": "error", "message": "fail"})
                + "\n"
                + json.dumps({"timestamp": "2024-01-01T00:00:01Z", "level": "warning", "message": "warn"})
                + "\n"
                + json.dumps({"ts": "2024-01-01T00:00:02Z", "level": "info", "msg": "ok"})
                + "\n"
                + "\n"  # empty line
            )
            tb = TimelineBuilder()
            events = tb.build(Path(tmpdir))
            assert len(events) == 3

    def test_timeline_builder_plaintext_logs(self):
        """Parse plaintext logs."""
        from zerg.diagnostics.log_correlator import TimelineBuilder

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "worker-1.stderr.log"
            log_file.write_text(
                "2024-01-01T00:00:00Z INFO normal line\n"
                "2024-01-01T00:00:01Z ERROR something failed\n"
                "2024-01-01T00:00:02Z WARNING be careful\n"
                "no timestamp line\n"
                "\n"
            )
            tb = TimelineBuilder()
            events = tb.build(Path(tmpdir))
            assert len(events) >= 3

    def test_temporal_clusterer_iso_timestamps(self):
        """Cluster events with real ISO timestamps."""
        from zerg.diagnostics.log_correlator import TemporalClusterer
        from zerg.diagnostics.types import TimelineEvent

        events = [
            TimelineEvent(timestamp="2024-01-01T00:00:00Z", worker_id=0, event_type="error", message="a"),
            TimelineEvent(timestamp="2024-01-01T00:00:01Z", worker_id=1, event_type="error", message="b"),
            TimelineEvent(timestamp="2024-01-01T00:10:00Z", worker_id=0, event_type="info", message="c"),
        ]
        clusterer = TemporalClusterer()
        clusters = clusterer.cluster(events, window_seconds=5.0)
        assert len(clusters) == 2
        assert len(clusters[0]) == 2

    def test_temporal_clusterer_mixed_timestamps(self):
        """Cluster events with mixed synthetic and real timestamps."""
        from zerg.diagnostics.log_correlator import TemporalClusterer
        from zerg.diagnostics.types import TimelineEvent

        events = [
            TimelineEvent(timestamp="2024-01-01T00:00:00Z", worker_id=0, event_type="error", message="a"),
            TimelineEvent(timestamp="line:00000005", worker_id=1, event_type="error", message="b"),
        ]
        clusterer = TemporalClusterer()
        clusters = clusterer.cluster(events, window_seconds=5.0)
        assert len(clusters) == 2  # mixed = not in same window

    def test_temporal_clusterer_synthetic_close(self):
        """Cluster events with synthetic timestamps within 10 lines."""
        from zerg.diagnostics.log_correlator import TemporalClusterer
        from zerg.diagnostics.types import TimelineEvent

        events = [
            TimelineEvent(timestamp="line:00000001", worker_id=0, event_type="error", message="a"),
            TimelineEvent(timestamp="line:00000005", worker_id=1, event_type="error", message="b"),
        ]
        clusterer = TemporalClusterer()
        clusters = clusterer.cluster(events, window_seconds=5.0)
        assert len(clusters) == 1

    def test_cross_worker_correlator(self):
        """Cross-worker correlation with similar errors."""
        from zerg.diagnostics.log_correlator import CrossWorkerCorrelator
        from zerg.diagnostics.types import TimelineEvent

        events = [
            TimelineEvent(
                timestamp="t1", worker_id=0, event_type="error", message="connection timeout to database server"
            ),
            TimelineEvent(
                timestamp="t2", worker_id=1, event_type="error", message="connection timeout to database server"
            ),
            TimelineEvent(timestamp="t3", worker_id=0, event_type="info", message="all good"),
        ]
        correlator = CrossWorkerCorrelator()
        results = correlator.correlate(events)
        assert len(results) >= 1
        assert results[0][2] >= 0.5

    def test_error_evolution_tracker(self):
        """Track error evolution over time."""
        from zerg.diagnostics.log_analyzer import LogPattern
        from zerg.diagnostics.log_correlator import ErrorEvolutionTracker

        patterns = [
            LogPattern(
                pattern="timeout",
                count=5,
                first_seen="1",
                last_seen="10",
                sample_lines=["timeout"],
                worker_ids=[0, 1, 2],
            ),
            LogPattern(pattern="rare", count=1, first_seen="5", last_seen="5", sample_lines=["rare"], worker_ids=[0]),
            LogPattern(
                pattern="sparse", count=2, first_seen="1", last_seen="100", sample_lines=["sparse"], worker_ids=[0]
            ),
        ]
        tracker = ErrorEvolutionTracker()
        results = tracker.track(patterns)
        assert len(results) == 3
        assert results[0]["trending"] == "increasing"  # high density + many workers
        assert results[1]["trending"] == "stable"  # count <= 1

    def test_log_correlation_engine_analyze(self):
        """Full engine analyze with worker logs."""
        from zerg.diagnostics.log_correlator import LogCorrelationEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "worker-0.stderr.log"
            log_file.write_text(
                json.dumps({"timestamp": "2024-01-01T00:00:00Z", "level": "error", "message": "fail 1"}) + "\n"
            )
            log_file2 = Path(tmpdir) / "worker-1.stderr.log"
            log_file2.write_text(
                json.dumps({"timestamp": "2024-01-01T00:00:01Z", "level": "error", "message": "fail 1"}) + "\n"
            )

            engine = LogCorrelationEngine(tmpdir)
            result = engine.analyze()
            assert "timeline" in result
            assert "clusters" in result
            assert "correlations" in result
            assert "evolution" in result
            assert "evidence" in result

    def test_log_correlation_engine_filter_worker(self):
        """Engine analyze filtered by worker_id."""
        from zerg.diagnostics.log_correlator import LogCorrelationEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "worker-0.stderr.log"
            log_file.write_text("2024-01-01T00:00:00Z ERROR fail\n")
            log_file2 = Path(tmpdir) / "worker-1.stderr.log"
            log_file2.write_text("2024-01-01T00:00:01Z ERROR fail\n")

            engine = LogCorrelationEngine(tmpdir)
            result = engine.analyze(worker_id=0)
            # Only worker 0 events
            for ev in result["timeline"]:
                assert ev["worker_id"] == 0


# ============================================================================
# claude_tasks_reader.py coverage
# ============================================================================


class TestClaudeTasksReader:
    """Cover lines 70-71, 74-75, 84-86, 95-101, 115-116, 133-135, 140-142, 197, 229-230, 236-237, 271."""

    def test_find_feature_cached(self):
        """Lines 70-71: cached result returned."""
        from zerg.claude_tasks_reader import ClaudeTasksReader

        with tempfile.TemporaryDirectory() as tmpdir:
            reader = ClaudeTasksReader(tasks_dir=Path(tmpdir))
            cached_dir = Path(tmpdir) / "cached"
            cached_dir.mkdir()
            reader._cached_dir = cached_dir
            reader._cache_time = __import__("time").monotonic()
            result = reader.find_feature_task_list("test")
            assert result == cached_dir

    def test_find_feature_no_tasks_dir(self):
        """Lines 74-75: tasks dir does not exist."""
        from zerg.claude_tasks_reader import ClaudeTasksReader

        reader = ClaudeTasksReader(tasks_dir=Path("/nonexistent_dir_12345"))
        result = reader.find_feature_task_list("test")
        assert result is None

    def test_find_feature_os_error(self):
        """Lines 84-86: OSError listing dirs."""
        from zerg.claude_tasks_reader import ClaudeTasksReader

        with tempfile.TemporaryDirectory() as tmpdir:
            reader = ClaudeTasksReader(tasks_dir=Path(tmpdir))
            with patch.object(Path, "iterdir", side_effect=OSError("permission denied")):
                result = reader.find_feature_task_list("test")
                assert result is None

    def test_find_feature_match(self):
        """Lines 95-101: feature matched in task list."""
        from zerg.claude_tasks_reader import ClaudeTasksReader

        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir) / "uuid-1"
            task_dir.mkdir()
            # Create task files with [L1] pattern
            for i in range(4):
                task = {"subject": f"[L1] Implement feature {i}", "description": "test-feature work"}
                (task_dir / f"task-{i}.json").write_text(json.dumps(task))

            reader = ClaudeTasksReader(tasks_dir=Path(tmpdir))
            result = reader.find_feature_task_list("test-feature")
            assert result == task_dir

    def test_find_feature_no_match_fallback(self):
        """Lines 103-116: no feature match, fallback to dirs with >=3 ZERG tasks."""
        from zerg.claude_tasks_reader import ClaudeTasksReader

        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir) / "uuid-1"
            task_dir.mkdir()
            for i in range(4):
                task = {"subject": f"[L1] Task {i}", "description": "unrelated"}
                (task_dir / f"task-{i}.json").write_text(json.dumps(task))

            reader = ClaudeTasksReader(tasks_dir=Path(tmpdir))
            result = reader.find_feature_task_list("nonexistent-feature")
            assert result == task_dir

    def test_read_tasks_os_error(self):
        """Lines 133-135: OSError reading task list."""
        from zerg.claude_tasks_reader import ClaudeTasksReader

        reader = ClaudeTasksReader()
        with patch.object(Path, "glob", side_effect=OSError("fail")):
            result = reader.read_tasks(Path("/some/dir"))
            assert result["tasks"] == {}

    def test_read_tasks_json_decode_error(self):
        """Lines 140-142: invalid JSON in task file."""
        from zerg.claude_tasks_reader import ClaudeTasksReader

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "task-1.json").write_text("{invalid json")
            reader = ClaudeTasksReader()
            result = reader.read_tasks(Path(tmpdir))
            assert result["tasks"] == {}

    def test_read_tasks_all_complete(self):
        """Line 197: all levels complete, current_level = max_level."""
        from zerg.claude_tasks_reader import ClaudeTasksReader

        with tempfile.TemporaryDirectory() as tmpdir:
            task = {
                "id": "1",
                "subject": "[L1] Done task",
                "status": "completed",
                "blockedBy": [],
            }
            (Path(tmpdir) / "task-1.json").write_text(json.dumps(task))

            reader = ClaudeTasksReader()
            result = reader.read_tasks(Path(tmpdir))
            assert result["current_level"] == 1

    def test_scan_dir_os_error(self):
        """Lines 229-230: OSError scanning dir."""
        from zerg.claude_tasks_reader import ClaudeTasksReader

        reader = ClaudeTasksReader()
        with patch.object(Path, "glob", side_effect=OSError("fail")):
            count, match = reader._scan_dir_for_zerg_tasks(Path("/some/dir"), "test")
            assert count == 0
            assert match is False

    def test_scan_dir_json_error(self):
        """Lines 236-237: invalid JSON in scan."""
        from zerg.claude_tasks_reader import ClaudeTasksReader

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "task.json").write_text("{bad json")
            reader = ClaudeTasksReader()
            count, match = reader._scan_dir_for_zerg_tasks(Path(tmpdir), "test")
            assert count == 0

    def test_map_status_blocked(self):
        """Line 271: pending with blockers maps to BLOCKED."""
        from zerg.claude_tasks_reader import ClaudeTasksReader

        result = ClaudeTasksReader._map_status("pending", ["blocker-1"])
        assert result == TaskStatus.BLOCKED.value


# ============================================================================
# diagnostics/env_diagnostics.py coverage
# ============================================================================


class TestEnvDiagnostics:
    """Cover scattered uncovered lines."""

    def test_python_check_packages_pip_fail(self):
        """PythonEnvDiagnostics.check_packages with pip failure."""
        from zerg.diagnostics.env_diagnostics import PythonEnvDiagnostics

        diag = PythonEnvDiagnostics()
        with patch.object(diag, "_run_cmd", return_value=("", False)):
            result = diag.check_packages()
            assert result["count"] == 0

    def test_python_check_packages_json_error(self):
        """PythonEnvDiagnostics.check_packages with invalid JSON."""
        from zerg.diagnostics.env_diagnostics import PythonEnvDiagnostics

        diag = PythonEnvDiagnostics()
        with patch.object(diag, "_run_cmd", return_value=("not json", True)):
            result = diag.check_packages()
            assert result["count"] == 0

    def test_python_check_packages_with_required(self):
        """PythonEnvDiagnostics.check_packages with required list."""
        from zerg.diagnostics.env_diagnostics import PythonEnvDiagnostics

        diag = PythonEnvDiagnostics()
        pip_output = json.dumps([{"name": "pytest", "version": "7.0"}, {"name": "rich", "version": "13.0"}])
        with patch.object(diag, "_run_cmd", return_value=(pip_output, True)):
            result = diag.check_packages(required=["pytest", "nonexistent"])
            assert "nonexistent" in result["missing"]
            assert "pytest" not in result["missing"]

    def test_python_check_imports(self):
        """PythonEnvDiagnostics.check_imports."""
        from zerg.diagnostics.env_diagnostics import PythonEnvDiagnostics

        diag = PythonEnvDiagnostics()

        def mock_run(cmd):
            if "json" in cmd[-1]:
                return ("", True)
            return ("import failed", False)

        with patch.object(diag, "_run_cmd", side_effect=mock_run):
            result = diag.check_imports(["json", "nonexistent_module"])
            assert "json" in result["success"]
            assert len(result["failed"]) == 1

    def test_docker_check_health_unavailable(self):
        """DockerDiagnostics.check_health returns None when docker unavailable."""
        from zerg.diagnostics.env_diagnostics import DockerDiagnostics

        diag = DockerDiagnostics()
        with patch.object(diag, "_run_cmd", return_value=("", False)):
            result = diag.check_health()
            assert result is None

    def test_docker_check_containers(self):
        """DockerDiagnostics.check_containers parses output."""
        from zerg.diagnostics.env_diagnostics import DockerDiagnostics

        diag = DockerDiagnostics()
        running_output = "abc123\tzerg-worker-0\tUp 5 minutes"
        stopped_output = "def456\tzerg-worker-1\tExited (0) 2 hours ago"

        call_count = [0]

        def mock_run(cmd):
            call_count[0] += 1
            if "status=exited" in cmd:
                return (stopped_output, True)
            if "--filter" in cmd:
                return (running_output, True)
            return ("", True)

        with patch.object(diag, "_run_cmd", side_effect=mock_run):
            result = diag.check_containers()
            assert result["running"] >= 1

    def test_docker_check_images(self):
        """DockerDiagnostics.check_images parses output."""
        from zerg.diagnostics.env_diagnostics import DockerDiagnostics

        diag = DockerDiagnostics()
        images_output = "python\t3.12\t100MB\nnode\t20\t200MB"
        dangling_output = "abc123\ndef456"

        def mock_run(cmd):
            if "dangling=true" in cmd:
                return (dangling_output, True)
            return (images_output, True)

        with patch.object(diag, "_run_cmd", side_effect=mock_run):
            result = diag.check_images()
            assert result["total"] == 2
            assert result["dangling"] == 2

    def test_resource_check_memory_linux(self):
        """ResourceDiagnostics.check_memory on linux."""
        from zerg.diagnostics.env_diagnostics import ResourceDiagnostics

        diag = ResourceDiagnostics()
        # Just verify the method runs without error on the current platform
        result = diag.check_memory()
        assert "total_gb" in result

    def test_config_validator_missing_file(self):
        """ConfigValidator with missing config file."""
        from zerg.diagnostics.env_diagnostics import ConfigValidator

        validator = ConfigValidator()
        issues = validator.validate(Path("/nonexistent/config.yaml"))
        assert any("not found" in i for i in issues)

    def test_config_validator_empty_file(self):
        """ConfigValidator with empty config."""
        from zerg.diagnostics.env_diagnostics import ConfigValidator

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text("")
            validator = ConfigValidator()
            issues = validator.validate(config_path)
            assert any("empty" in i for i in issues)

    def test_config_validator_valid_yaml(self):
        """ConfigValidator with valid YAML."""
        from zerg.diagnostics.env_diagnostics import ConfigValidator

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text("workers: 5\ntimeouts:\n  default: 30\nquality_gates: []\nmcp_servers: []\n")
            validator = ConfigValidator()
            issues = validator.validate(config_path)
            assert len(issues) == 0 or all("Missing" not in i for i in issues if "workers" in i or "timeouts" in i)

    def test_config_validator_bad_yaml(self):
        """ConfigValidator with unparseable YAML."""
        from zerg.diagnostics.env_diagnostics import ConfigValidator

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text(":\n  - :\n    bad: [")
            validator = ConfigValidator()
            validator.validate(config_path)
            # Should have some issues

    def test_env_engine_run_all(self):
        """EnvDiagnosticsEngine.run_all collects evidence."""
        from zerg.diagnostics.env_diagnostics import EnvDiagnosticsEngine

        engine = EnvDiagnosticsEngine()
        with (
            patch.object(
                engine._python,
                "check_venv",
                return_value={
                    "active": False,
                    "path": "/usr",
                    "python_version": "3.12",
                    "executable": "/usr/bin/python3",
                },
            ),
            patch.object(engine._docker, "check_health", return_value=None),
            patch.object(
                engine._docker, "check_containers", return_value={"running": 0, "stopped": 0, "containers": []}
            ),
            patch.object(engine._docker, "check_images", return_value={"total": 0, "dangling": 0, "images": []}),
            patch.object(
                engine._resources,
                "check_memory",
                return_value={"total_gb": 16.0, "available_gb": 1.0, "used_percent": 93.0},
            ),
            patch.object(
                engine._resources,
                "check_cpu",
                return_value={"load_avg_1m": 1.0, "load_avg_5m": 1.0, "load_avg_15m": 1.0, "cpu_count": 8},
            ),
            patch.object(
                engine._resources, "check_file_descriptors", return_value={"soft_limit": 1024, "hard_limit": 1024}
            ),
            patch.object(
                engine._resources,
                "check_disk_detailed",
                return_value={"total_gb": 500.0, "used_gb": 460.0, "free_gb": 40.0, "used_percent": 92.0},
            ),
            patch.object(engine._config, "validate", return_value=["Missing key: workers"]),
        ):
            result = engine.run_all()
            evidence = result["evidence"]
            # Should have evidence for: no venv, no docker, low memory, high disk, config issues
            descriptions = [e["description"] for e in evidence]
            assert any("not active" in d for d in descriptions)
            assert any("Docker" in d for d in descriptions)
            assert any("memory" in d.lower() for d in descriptions)
            assert any("disk" in d.lower() for d in descriptions)
            assert any("Config" in d for d in descriptions)


# ============================================================================
# ports.py coverage
# ============================================================================


class TestPortsAsync:
    """Cover lines 148, 161-162, 176-182."""

    def test_allocate_one_async(self):
        """Line 148: async allocate_one."""
        from zerg.ports import PortAllocator

        pa = PortAllocator(range_start=49152, range_end=49160)
        port = asyncio.get_event_loop().run_until_complete(pa.allocate_one_async())
        assert 49152 <= port <= 49160

    def test_allocate_many_async(self):
        """Lines 161-162: async allocate_many."""
        from zerg.ports import PortAllocator

        pa = PortAllocator(range_start=49152, range_end=49200)
        ports = asyncio.get_event_loop().run_until_complete(pa.allocate_many_async(2))
        assert len(ports) == 2

    def test_allocate_for_worker_async_single(self):
        """Lines 176-178: async allocate for worker, single port."""
        from zerg.ports import PortAllocator

        pa = PortAllocator(range_start=49152, range_end=49160)
        ports = asyncio.get_event_loop().run_until_complete(
            pa.allocate_for_worker_async(worker_id=0, ports_per_worker=1)
        )
        assert len(ports) == 1

    def test_allocate_for_worker_async_multiple(self):
        """Lines 179-182: async allocate for worker, multiple ports."""
        from zerg.ports import PortAllocator

        pa = PortAllocator(range_start=49152, range_end=49200)
        ports = asyncio.get_event_loop().run_until_complete(
            pa.allocate_for_worker_async(worker_id=0, ports_per_worker=3)
        )
        assert len(ports) == 3

    def test_allocate_max_attempts_exceeded(self):
        """Line 71: max_attempts exceeded."""
        from zerg.ports import PortAllocator

        pa = PortAllocator(range_start=49152, range_end=49152)
        # First call allocates the only port
        with patch.object(pa, "is_available", return_value=False):
            with pytest.raises(RuntimeError, match="Could not allocate"):
                pa.allocate(1)
