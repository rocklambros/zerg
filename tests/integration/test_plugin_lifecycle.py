"""Integration tests for the plugin lifecycle system."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from zerg.config import QualityGate, ZergConfig
from zerg.constants import GateResult, PluginHookEvent
from zerg.gates import GateRunner
from zerg.plugins import (
    GateContext,
    LifecycleEvent,
    PluginRegistry,
    QualityGatePlugin,
)
from zerg.types import GateRunResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EVENT_TYPES = [
    PluginHookEvent.TASK_STARTED,
    PluginHookEvent.TASK_COMPLETED,
    PluginHookEvent.LEVEL_COMPLETE,
    PluginHookEvent.MERGE_COMPLETE,
    PluginHookEvent.RUSH_FINISHED,
]


class _PassingGate(QualityGatePlugin):
    """Concrete gate that always passes."""

    @property
    def name(self) -> str:
        return "passing-gate"

    def run(self, ctx: GateContext) -> GateRunResult:
        return GateRunResult(
            gate_name=self.name,
            result=GateResult.PASS,
            command="true",
            exit_code=0,
        )


class _CapturingGate(QualityGatePlugin):
    """Gate that captures its context for later inspection."""

    def __init__(self) -> None:
        self.captured_ctx: GateContext | None = None

    @property
    def name(self) -> str:
        return "capturing-gate"

    def run(self, ctx: GateContext) -> GateRunResult:
        self.captured_ctx = ctx
        return GateRunResult(
            gate_name=self.name,
            result=GateResult.PASS,
            command="capture",
            exit_code=0,
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPluginLifecycle:
    """Integration tests covering the full plugin lifecycle."""

    def test_full_lifecycle_events_emitted(self) -> None:
        """All 5 core event types reach their registered hooks."""
        registry = PluginRegistry()
        hooks: dict[str, MagicMock] = {}

        for evt in EVENT_TYPES:
            mock_cb = MagicMock()
            hooks[evt.value] = mock_cb
            registry.register_hook(evt.value, mock_cb)

        for evt in EVENT_TYPES:
            event = LifecycleEvent(event_type=evt.value, data={"info": evt.value})
            registry.emit_event(event)

        for evt in EVENT_TYPES:
            mock_cb = hooks[evt.value]
            mock_cb.assert_called_once()
            received: LifecycleEvent = mock_cb.call_args[0][0]
            assert isinstance(received, LifecycleEvent)
            assert received.event_type == evt.value
            assert received.data == {"info": evt.value}

    def test_plugin_gate_runs_after_config(self) -> None:
        """A registered QualityGatePlugin runs and returns its result."""
        registry = PluginRegistry()
        gate = _PassingGate()
        registry.register_gate(gate)

        ctx = GateContext(
            feature="test-feature",
            level=1,
            cwd=Path("/tmp"),
            config=None,
        )
        result = registry.run_plugin_gate("passing-gate", ctx)

        assert result.result == GateResult.PASS
        assert result.gate_name == "passing-gate"

    @patch("zerg.plugins.subprocess.run")
    def test_yaml_hook_executes_command(self, mock_run: MagicMock) -> None:
        """YAML-defined hooks invoke subprocess.run on emit."""
        registry = PluginRegistry()
        hooks_config = [{"event": "test_event", "command": "echo hello"}]
        registry.load_yaml_hooks(hooks_config)

        event = LifecycleEvent(event_type="test_event", data={})
        registry.emit_event(event)

        mock_run.assert_called_once_with(["echo", "hello"], check=False, timeout=300)

    def test_exception_in_hook_doesnt_crash(self) -> None:
        """A hook raising an exception does not propagate to the caller."""
        registry = PluginRegistry()

        def _bad_hook(event: LifecycleEvent) -> None:
            raise RuntimeError("hook exploded")

        good_mock = MagicMock()
        registry.register_hook("boom", _bad_hook)
        registry.register_hook("boom", good_mock)

        event = LifecycleEvent(event_type="boom", data={})
        registry.emit_event(event)  # must not raise

        good_mock.assert_called_once()

        # Registry still works for subsequent events
        follow_up_mock = MagicMock()
        registry.register_hook("after", follow_up_mock)
        registry.emit_event(LifecycleEvent(event_type="after", data={}))
        follow_up_mock.assert_called_once()

    @patch("zerg.plugins.subprocess.run")
    def test_plugin_timeout_enforced(self, mock_run: MagicMock) -> None:
        """A YAML hook that times out does not crash the registry."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="sleep 999", timeout=300)

        registry = PluginRegistry()
        hooks_config = [{"event": "slow_event", "command": "sleep 999"}]
        registry.load_yaml_hooks(hooks_config)

        event = LifecycleEvent(event_type="slow_event", data={})
        registry.emit_event(event)  # must not raise

    def test_multiple_hooks_same_event(self) -> None:
        """Multiple hooks registered for the same event all fire."""
        registry = PluginRegistry()
        mocks = [MagicMock() for _ in range(3)]

        for m in mocks:
            registry.register_hook("shared", m)

        event = LifecycleEvent(event_type="shared", data={"n": 3})
        registry.emit_event(event)

        for m in mocks:
            m.assert_called_once_with(event)

    def test_gate_context_passed_correctly(self) -> None:
        """GateContext fields are faithfully forwarded to the gate plugin."""
        registry = PluginRegistry()
        gate = _CapturingGate()
        registry.register_gate(gate)

        expected_cwd = Path("/usr/src/project")
        expected_config = {"lint": True, "threshold": 80}

        ctx = GateContext(
            feature="auth-system",
            level=2,
            cwd=expected_cwd,
            config=expected_config,
        )
        result = registry.run_plugin_gate("capturing-gate", ctx)

        assert result.result == GateResult.PASS
        assert gate.captured_ctx is not None
        assert gate.captured_ctx.feature == "auth-system"
        assert gate.captured_ctx.level == 2
        assert gate.captured_ctx.cwd == expected_cwd
        assert gate.captured_ctx.config == expected_config

    def test_plugin_gate_runs_after_merge(self, tmp_path: Path) -> None:
        """Plugin gates run through GateRunner after config gates complete."""
        # Create a registry and register a plugin gate
        registry = PluginRegistry()
        plugin_gate = _PassingGate()
        registry.register_gate(plugin_gate)

        # Create a config with one regular gate
        config = ZergConfig(
            feature="test-feature",
            quality_gates=[
                QualityGate(
                    name="lint",
                    command="true",
                    timeout=30,
                    required=True,
                    coverage_threshold=0,
                )
            ],
        )

        # Create GateRunner with plugin registry
        runner = GateRunner(config=config, plugin_registry=registry)

        # Run all gates (config + plugin)
        all_passed, results = runner.run_all_gates(
            cwd=tmp_path,
            feature="test-feature",
            level=1,
        )

        # Should have both config gate and plugin gate results
        assert all_passed
        assert len(results) == 2

        # First result is config gate
        assert results[0].gate_name == "lint"
        assert results[0].result == GateResult.PASS

        # Second result is plugin gate
        assert results[1].gate_name == "passing-gate"
        assert results[1].result == GateResult.PASS
