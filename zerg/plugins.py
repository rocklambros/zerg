"""ZERG plugin system with ABCs and registry for quality gates, lifecycle hooks, and launchers."""

from __future__ import annotations

import abc
import importlib.metadata
import logging
import shlex
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from zerg.constants import GateResult, PluginHookEvent
from zerg.types import GateRunResult

logger = logging.getLogger(__name__)


# ============================================================================
# Dataclasses
# ============================================================================


@dataclass
class LifecycleEvent:
    """An event emitted during ZERG lifecycle phases."""

    event_type: str
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class GateContext:
    """Context passed to quality gate plugins for execution."""

    feature: str
    level: int
    cwd: Path
    config: Any


# ============================================================================
# Abstract Base Classes
# ============================================================================


class QualityGatePlugin(abc.ABC):
    """Abstract base class for quality gate plugins."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique name identifying this quality gate."""

    @abc.abstractmethod
    def run(self, ctx: GateContext) -> GateRunResult:
        """Execute the quality gate and return the result."""


class LifecycleHookPlugin(abc.ABC):
    """Abstract base class for lifecycle hook plugins."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique name identifying this lifecycle hook."""

    @abc.abstractmethod
    def on_event(self, event: LifecycleEvent) -> None:
        """Handle a lifecycle event."""


class LauncherPlugin(abc.ABC):
    """Abstract base class for worker launcher plugins."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique name identifying this launcher."""

    @abc.abstractmethod
    def create_launcher(self, config: Any) -> Any:
        """Create and return a WorkerLauncher instance from the given config."""


class ContextPlugin(abc.ABC):
    """Abstract base class for context engineering plugins."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique name identifying this context plugin."""

    @abc.abstractmethod
    def build_task_context(self, task: dict, task_graph: dict, feature: str) -> str:
        """Build context string for a specific task.

        Args:
            task: Task dict from task-graph.json
            task_graph: Full task graph dict
            feature: Feature name
        Returns:
            Markdown context string to inject into worker prompt
        """

    @abc.abstractmethod
    def estimate_context_tokens(self, task: dict) -> int:
        """Estimate token count for task context."""


# ============================================================================
# Plugin Registry
# ============================================================================


class PluginRegistry:
    """Central registry for discovering, registering, and dispatching plugins."""

    def __init__(self) -> None:
        self._hooks: dict[str, list[Callable[..., Any]]] = {}
        self._gates: dict[str, QualityGatePlugin] = {}
        self._gate_metadata: dict[str, dict[str, Any]] = {}  # required flag + metadata
        self._launchers: dict[str, LauncherPlugin] = {}
        self._context_plugins: dict[str, ContextPlugin] = {}

    # -- Registration --------------------------------------------------------

    def register_hook(self, event_type: str, callback: Callable[..., Any]) -> None:
        """Register a callback for a specific event type."""
        self._hooks.setdefault(event_type, []).append(callback)

    def register_gate(self, plugin: QualityGatePlugin, required: bool = True) -> None:
        """Register a quality gate plugin by its name.

        Args:
            plugin: The quality gate plugin instance
            required: Whether gate failure blocks merge (default: True)
        """
        self._gates[plugin.name] = plugin
        self._gate_metadata[plugin.name] = {"required": required}

    def register_launcher(self, plugin: LauncherPlugin) -> None:
        """Register a launcher plugin by its name."""
        self._launchers[plugin.name] = plugin

    def register_context_plugin(self, plugin: ContextPlugin) -> None:
        """Register a context plugin by its name."""
        self._context_plugins[plugin.name] = plugin

    # -- Dispatching ---------------------------------------------------------

    def emit_event(self, event: LifecycleEvent) -> None:
        """Emit a lifecycle event to all registered hooks for its type.

        Each hook invocation is individually wrapped so that a failing hook
        never prevents other hooks from running and never crashes the caller.
        """
        for callback in self._hooks.get(event.event_type, []):
            try:
                callback(event)
            except Exception:
                logger.warning(
                    "Hook callback %r failed for event type %r",
                    callback,
                    event.event_type,
                    exc_info=True,
                )

    def run_plugin_gate(self, name: str, ctx: GateContext) -> GateRunResult:
        """Run a named quality gate plugin and return its result.

        Returns a GateRunResult with GateResult.ERROR if the plugin is not
        found or if the plugin raises an exception during execution.
        """
        plugin = self._gates.get(name)
        if plugin is None:
            return GateRunResult(
                gate_name=name,
                result=GateResult.ERROR,
                command="",
                exit_code=-1,
                stderr=f"Plugin gate '{name}' not found in registry",
            )

        try:
            return plugin.run(ctx)
        except Exception as exc:
            logger.warning(
                "Plugin gate %r raised an exception",
                name,
                exc_info=True,
            )
            return GateRunResult(
                gate_name=name,
                result=GateResult.ERROR,
                command="",
                exit_code=-1,
                stderr=str(exc),
            )

    def get_launcher(self, name: str) -> LauncherPlugin | None:
        """Look up a launcher plugin by name, returning None if not found."""
        return self._launchers.get(name)

    def is_gate_required(self, name: str) -> bool:
        """Check if a plugin gate is required.

        Args:
            name: Plugin gate name

        Returns:
            True if gate is required (default if not found), False otherwise
        """
        metadata = self._gate_metadata.get(name, {})
        return bool(metadata.get("required", True))

    def get_context_plugins(self) -> list[ContextPlugin]:
        """Return all registered context plugins."""
        return list(self._context_plugins.values())

    def build_task_context(self, task: dict, task_graph: dict, feature: str) -> str:
        """Build combined context from all registered context plugins.

        Calls each plugin's ``build_task_context`` method and concatenates the
        results.  Exceptions from individual plugins are caught and logged so
        that one failing plugin does not prevent others from contributing.
        """
        parts: list[str] = []
        for plugin in self._context_plugins.values():
            try:
                result = plugin.build_task_context(task, task_graph, feature)
                if result:
                    parts.append(result)
            except Exception:
                logger.warning(
                    "Context plugin %r failed for task %r",
                    plugin.name,
                    task.get("id", "unknown"),
                    exc_info=True,
                )
        return "\n\n---\n\n".join(parts)

    # -- YAML hook loading ---------------------------------------------------

    def load_yaml_hooks(self, hooks_config: list[dict[str, Any]]) -> None:
        """Load lifecycle hooks defined in YAML configuration.

        Each item in *hooks_config* must have ``event`` and ``command`` keys.
        The command is parsed with ``shlex.split`` and executed via
        ``subprocess.run`` (no shell) for security.
        """
        for item in hooks_config:
            event_type = item["event"]
            command = item["command"]

            def _make_hook(cmd: str) -> Callable[[LifecycleEvent], None]:
                """Create a closure capturing the shell command string."""

                def _hook(event: LifecycleEvent) -> None:
                    args = shlex.split(cmd)
                    subprocess.run(args, check=False, timeout=300)  # noqa: S603

                return _hook

            self.register_hook(event_type, _make_hook(command))

    # -- Entry point discovery -----------------------------------------------

    def load_entry_points(self, group: str = "zerg.plugins") -> None:
        """Discover and register plugins from installed package entry points.

        Each entry point should reference a class implementing one of the
        plugin ABCs (QualityGatePlugin, LifecycleHookPlugin, LauncherPlugin,
        ContextPlugin).
        """
        eps = importlib.metadata.entry_points()

        # importlib.metadata.entry_points() returns a dict-like on older
        # Python and a SelectableGroups on 3.12+.  Handle both.
        discovered = (
            eps.select(group=group) if hasattr(eps, "select") else eps.get(group, [])  # type: ignore[attr-defined]
        )

        for ep in discovered:
            try:
                plugin_cls = ep.load()
                instance = plugin_cls()

                if isinstance(instance, QualityGatePlugin):
                    self.register_gate(instance)
                    logger.info("Registered quality gate plugin: %s", instance.name)
                elif isinstance(instance, LifecycleHookPlugin):
                    # Register for all lifecycle event types
                    for event_type in PluginHookEvent:
                        self.register_hook(event_type.value, instance.on_event)
                    logger.info("Registered lifecycle hook plugin: %s", instance.name)
                elif isinstance(instance, LauncherPlugin):
                    self.register_launcher(instance)
                    logger.info("Registered launcher plugin: %s", instance.name)
                elif isinstance(instance, ContextPlugin):
                    self.register_context_plugin(instance)
                    logger.info("Registered context plugin: %s", instance.name)
                else:
                    logger.warning(
                        "Entry point %r did not produce a recognised plugin type: %s",
                        ep.name,
                        type(instance).__name__,
                    )
            except Exception:
                logger.warning(
                    "Failed to load entry point %r from group %r",
                    ep.name,
                    group,
                    exc_info=True,
                )
