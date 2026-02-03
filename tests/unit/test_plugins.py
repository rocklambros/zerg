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
        """Test registering callback and emitting event verifies called."""
        registry = PluginRegistry()
        callback = MagicMock()

        registry.register_hook("build_started", callback)

        event = LifecycleEvent(event_type="build_started", data={"level": 1})
        registry.emit_event(event)

        callback.assert_called_once_with(event)

    def test_emit_event_catches_exceptions(self) -> None:
        """Test that hook raises exception but does not crash."""
        registry = PluginRegistry()

        def bad_hook(event: LifecycleEvent) -> None:
            raise ValueError("hook exploded")

        good_callback = MagicMock()

        registry.register_hook("danger", bad_hook)
        registry.register_hook("danger", good_callback)

        event = LifecycleEvent(event_type="danger", data={})
        # Must not raise, should call good_callback despite bad_hook failure
        registry.emit_event(event)

        # Verify good callback was still called
        good_callback.assert_called_once_with(event)

    def test_register_and_run_gate(self) -> None:
        """Test mock QualityGatePlugin, run_plugin_gate returns result."""
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

    def test_run_plugin_gate_catches_exceptions(self) -> None:
        """Test gate plugin that raises exception returns ERROR result."""
        registry = PluginRegistry()

        class ExplodingGate(QualityGatePlugin):
            @property
            def name(self) -> str:
                return "boom"

            def run(self, ctx: GateContext) -> GateRunResult:
                raise RuntimeError("intentional failure")

        registry.register_gate(ExplodingGate())

        ctx = GateContext(feature="test", level=1, cwd=Path("."), config=None)
        result = registry.run_plugin_gate("boom", ctx)

        assert result.result is GateResult.ERROR
        assert result.exit_code == -1
        assert "intentional failure" in result.stderr

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
    def test_load_yaml_hooks_registers_shell_commands(self, mock_subprocess_run: MagicMock) -> None:
        """Test providing HookConfig list, emit, verify subprocess called."""
        registry = PluginRegistry()
        hooks_config = [{"event": "test_event", "command": "echo hello"}]
        registry.load_yaml_hooks(hooks_config)

        event = LifecycleEvent(event_type="test_event", data={})
        registry.emit_event(event)

        mock_subprocess_run.assert_called_once_with(["echo", "hello"], check=False, timeout=300)

    @patch("zerg.plugins.subprocess.run")
    def test_load_yaml_hooks_multiple_events(self, mock_subprocess_run: MagicMock) -> None:
        """Test multiple YAML hooks for different events."""
        registry = PluginRegistry()
        hooks_config = [
            {"event": "task_started", "command": "notify-send start"},
            {"event": "task_completed", "command": "notify-send done"},
        ]
        registry.load_yaml_hooks(hooks_config)

        # Emit first event
        event1 = LifecycleEvent(event_type="task_started", data={})
        registry.emit_event(event1)

        mock_subprocess_run.assert_called_with(["notify-send", "start"], check=False, timeout=300)

        mock_subprocess_run.reset_mock()

        # Emit second event
        event2 = LifecycleEvent(event_type="task_completed", data={})
        registry.emit_event(event2)

        mock_subprocess_run.assert_called_with(["notify-send", "done"], check=False, timeout=300)

    def test_multiple_hooks_same_event(self) -> None:
        """Test multiple callbacks registered for same event type."""
        registry = PluginRegistry()
        callback1 = MagicMock()
        callback2 = MagicMock()
        callback3 = MagicMock()

        registry.register_hook("shared", callback1)
        registry.register_hook("shared", callback2)
        registry.register_hook("shared", callback3)

        event = LifecycleEvent(event_type="shared", data={})
        registry.emit_event(event)

        callback1.assert_called_once_with(event)
        callback2.assert_called_once_with(event)
        callback3.assert_called_once_with(event)


class TestABCConstraints:
    """Verify abstract base classes cannot be directly instantiated."""

    def test_abc_not_instantiable(self) -> None:
        with pytest.raises(TypeError):
            QualityGatePlugin()  # type: ignore[abstract]

        with pytest.raises(TypeError):
            LifecycleHookPlugin()  # type: ignore[abstract]

        with pytest.raises(TypeError):
            LauncherPlugin()  # type: ignore[abstract]


class TestEntryPointDiscovery:
    """Tests for load_entry_points discovering plugins from installed packages."""

    @patch("zerg.plugins.importlib.metadata.entry_points")
    def test_load_entry_points_quality_gate(self, mock_entry_points: MagicMock) -> None:
        """Test loading QualityGatePlugin from entry points."""
        mock_ep = MagicMock()
        mock_ep.name = "custom_gate"
        mock_ep.load.return_value = StubGatePlugin

        # Mock Python 3.12+ entry_points() with select method
        mock_eps_obj = MagicMock()
        mock_eps_obj.select.return_value = [mock_ep]
        mock_entry_points.return_value = mock_eps_obj

        registry = PluginRegistry()
        registry.load_entry_points()

        # Verify gate was registered
        ctx = GateContext(feature="test", level=1, cwd=Path("."), config=None)
        result = registry.run_plugin_gate("stub-gate", ctx)
        assert result.result is GateResult.PASS

    @patch("zerg.plugins.importlib.metadata.entry_points")
    def test_load_entry_points_lifecycle_hook(self, mock_entry_points: MagicMock) -> None:
        """Test loading LifecycleHookPlugin from entry points."""

        class TestHook(LifecycleHookPlugin):
            _calls: list[LifecycleEvent] = []

            @property
            def name(self) -> str:
                return "test-hook"

            def on_event(self, event: LifecycleEvent) -> None:
                TestHook._calls.append(event)

        mock_ep = MagicMock()
        mock_ep.name = "test_hook"
        mock_ep.load.return_value = TestHook

        mock_eps_obj = MagicMock()
        mock_eps_obj.select.return_value = [mock_ep]
        mock_entry_points.return_value = mock_eps_obj

        registry = PluginRegistry()
        TestHook._calls.clear()
        registry.load_entry_points()

        # Emit event to verify hook was registered (must use a PluginHookEvent type)
        event = LifecycleEvent(event_type="task_started", data={})
        registry.emit_event(event)

        assert len(TestHook._calls) == 1
        assert TestHook._calls[0] == event

    @patch("zerg.plugins.importlib.metadata.entry_points")
    def test_load_entry_points_launcher(self, mock_entry_points: MagicMock) -> None:
        """Test loading LauncherPlugin from entry points."""
        mock_ep = MagicMock()
        mock_ep.name = "custom_launcher"
        mock_ep.load.return_value = StubLauncherPlugin

        mock_eps_obj = MagicMock()
        mock_eps_obj.select.return_value = [mock_ep]
        mock_entry_points.return_value = mock_eps_obj

        registry = PluginRegistry()
        registry.load_entry_points()

        launcher = registry.get_launcher("stub-launcher")
        assert launcher is not None
        assert isinstance(launcher, StubLauncherPlugin)

    @patch("zerg.plugins.importlib.metadata.entry_points")
    def test_load_entry_points_fallback_dict_interface(self, mock_entry_points: MagicMock) -> None:
        """Test entry points using dict interface (Python <3.12)."""
        mock_ep = MagicMock()
        mock_ep.name = "legacy_plugin"
        mock_ep.load.return_value = StubGatePlugin

        # Mock pre-3.12 dict-like interface (no select method)
        mock_entry_points.return_value = {"zerg.plugins": [mock_ep]}

        registry = PluginRegistry()
        registry.load_entry_points()

        ctx = GateContext(feature="test", level=1, cwd=Path("."), config=None)
        result = registry.run_plugin_gate("stub-gate", ctx)
        assert result.result is GateResult.PASS

    @patch("zerg.plugins.importlib.metadata.entry_points")
    def test_load_entry_points_unknown_type_warns(self, mock_entry_points: MagicMock) -> None:
        """Test entry point that doesn't implement plugin ABC logs warning."""

        class NotAPlugin:
            pass

        mock_ep = MagicMock()
        mock_ep.name = "invalid"
        mock_ep.load.return_value = NotAPlugin

        mock_eps_obj = MagicMock()
        mock_eps_obj.select.return_value = [mock_ep]
        mock_entry_points.return_value = mock_eps_obj

        registry = PluginRegistry()

        with patch("zerg.plugins.logger.warning") as mock_warn:
            registry.load_entry_points()

        assert mock_warn.called
        warn_msg = str(mock_warn.call_args[0][0])
        assert "did not produce a recognised plugin type" in warn_msg

    @patch("zerg.plugins.importlib.metadata.entry_points")
    def test_load_entry_points_load_failure_warns(self, mock_entry_points: MagicMock) -> None:
        """Test entry point that fails to load logs warning and continues."""
        mock_ep = MagicMock()
        mock_ep.name = "broken"
        mock_ep.load.side_effect = ImportError("module not found")

        mock_eps_obj = MagicMock()
        mock_eps_obj.select.return_value = [mock_ep]
        mock_entry_points.return_value = mock_eps_obj

        registry = PluginRegistry()

        with patch("zerg.plugins.logger.warning") as mock_warn:
            registry.load_entry_points()

        assert mock_warn.called
        warn_msg = str(mock_warn.call_args[0][0])
        assert "Failed to load entry point" in warn_msg

    @patch("zerg.plugins.importlib.metadata.entry_points")
    def test_load_entry_points_custom_group(self, mock_entry_points: MagicMock) -> None:
        """Test loading from custom entry point group."""
        mock_ep = MagicMock()
        mock_ep.name = "custom"
        mock_ep.load.return_value = StubLauncherPlugin

        mock_eps_obj = MagicMock()
        mock_eps_obj.select.return_value = [mock_ep]
        mock_entry_points.return_value = mock_eps_obj

        registry = PluginRegistry()
        registry.load_entry_points(group="custom.plugins")

        launcher = registry.get_launcher("stub-launcher")
        assert launcher is not None


class TestDataclasses:
    """Verify dataclass field access for LifecycleEvent and GateContext."""

    def test_lifecycle_event_dataclass(self) -> None:
        """Test LifecycleEvent dataclass fields."""
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
        """Test LifecycleEvent uses current time as default timestamp."""
        event = LifecycleEvent(event_type="ping", data={})
        assert isinstance(event.timestamp, datetime)

    def test_gate_context_dataclass(self) -> None:
        """Test GateContext dataclass fields."""
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
