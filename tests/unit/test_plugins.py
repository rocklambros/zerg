"""Unit tests for the ZERG plugin system (zerg/plugins.py)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from zerg.constants import GateResult
from zerg.plugins import (
    GateContext,
    LauncherPlugin,
    LifecycleEvent,
    LifecycleHookPlugin,
    PluginRegistry,
    QualityGatePlugin,
)
from zerg.types import GateRunResult

# ---------------------------------------------------------------------------
# Concrete test doubles
# ---------------------------------------------------------------------------


class StubGatePlugin(QualityGatePlugin):
    """Minimal concrete quality gate for testing."""

    def __init__(self, gate_name: str = "stub-gate") -> None:
        self._name = gate_name

    @property
    def name(self) -> str:
        return self._name

    def run(self, ctx: GateContext) -> GateRunResult:
        return GateRunResult(
            gate_name=self._name,
            result=GateResult.PASS,
            command="echo ok",
            exit_code=0,
        )


class StubLauncherPlugin(LauncherPlugin):
    """Minimal concrete launcher for testing."""

    def __init__(self, launcher_name: str = "stub-launcher") -> None:
        self._name = launcher_name

    @property
    def name(self) -> str:
        return self._name

    def create_launcher(self, config: Any) -> Any:
        return {"launcher": self._name, "config": config}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPluginRegistry:
    """Tests for PluginRegistry core behaviour."""

    def test_registry_empty_by_default(self) -> None:
        registry = PluginRegistry()
        assert registry._hooks == {}
        assert registry._gates == {}
        assert registry._launchers == {}

    def test_register_and_emit_hook(self) -> None:
        registry = PluginRegistry()
        callback = MagicMock()

        registry.register_hook("build_started", callback)

        event = LifecycleEvent(event_type="build_started", data={"level": 1})
        registry.emit_event(event)

        callback.assert_called_once_with(event)

    def test_emit_event_catches_exceptions(self) -> None:
        registry = PluginRegistry()

        def bad_hook(event: LifecycleEvent) -> None:
            raise ValueError("hook exploded")

        registry.register_hook("danger", bad_hook)

        event = LifecycleEvent(event_type="danger", data={})
        # Must not raise
        registry.emit_event(event)

    def test_register_and_run_gate(self) -> None:
        registry = PluginRegistry()
        gate = StubGatePlugin("my-gate")
        registry.register_gate(gate)

        ctx = GateContext(feature="auth", level=1, cwd=Path("/tmp"), config=None)
        result = registry.run_plugin_gate("my-gate", ctx)

        assert result.gate_name == "my-gate"
        assert result.result is GateResult.PASS
        assert result.exit_code == 0

    def test_run_plugin_gate_unknown_returns_error(self) -> None:
        registry = PluginRegistry()

        ctx = GateContext(feature="auth", level=1, cwd=Path("/tmp"), config=None)
        result = registry.run_plugin_gate("nonexistent", ctx)

        assert result.result is GateResult.ERROR
        assert result.gate_name == "nonexistent"
        assert result.exit_code == -1
        assert "not found" in result.stderr

    def test_get_launcher_returns_none_for_unknown(self) -> None:
        registry = PluginRegistry()
        assert registry.get_launcher("nonexistent") is None

    def test_get_launcher_returns_registered(self) -> None:
        registry = PluginRegistry()
        launcher = StubLauncherPlugin("docker")
        registry.register_launcher(launcher)

        retrieved = registry.get_launcher("docker")
        assert retrieved is launcher

    @patch("zerg.plugins.subprocess.run")
    def test_load_yaml_hooks_registers_shell_commands(
        self, mock_subprocess_run: MagicMock
    ) -> None:
        registry = PluginRegistry()
        hooks_config = [{"event": "test_event", "command": "echo hello"}]
        registry.load_yaml_hooks(hooks_config)

        event = LifecycleEvent(event_type="test_event", data={})
        registry.emit_event(event)

        mock_subprocess_run.assert_called_once_with(
            ["echo", "hello"], check=False, timeout=300
        )


class TestABCConstraints:
    """Verify abstract base classes cannot be directly instantiated."""

    def test_abc_not_instantiable(self) -> None:
        with pytest.raises(TypeError):
            QualityGatePlugin()  # type: ignore[abstract]

        with pytest.raises(TypeError):
            LifecycleHookPlugin()  # type: ignore[abstract]

        with pytest.raises(TypeError):
            LauncherPlugin()  # type: ignore[abstract]


class TestDataclasses:
    """Verify dataclass field access for LifecycleEvent and GateContext."""

    def test_lifecycle_event_dataclass(self) -> None:
        now = datetime(2026, 1, 29, 12, 0, 0)
        event = LifecycleEvent(
            event_type="task_completed",
            data={"task_id": "t-1"},
            timestamp=now,
        )

        assert event.event_type == "task_completed"
        assert event.data == {"task_id": "t-1"}
        assert event.timestamp == now

    def test_lifecycle_event_default_timestamp(self) -> None:
        event = LifecycleEvent(event_type="ping", data={})
        assert isinstance(event.timestamp, datetime)

    def test_gate_context_dataclass(self) -> None:
        ctx = GateContext(
            feature="payments",
            level=3,
            cwd=Path("/workspace"),
            config={"timeout": 60},
        )

        assert ctx.feature == "payments"
        assert ctx.level == 3
        assert ctx.cwd == Path("/workspace")
        assert ctx.config == {"timeout": 60}
