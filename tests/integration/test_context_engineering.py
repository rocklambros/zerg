"""Integration tests for the context engineering pipeline.

Tests the end-to-end flow from ContextEngineeringPlugin registration through
PluginRegistry dispatch, Orchestrator.generate_task_contexts, and worker prompt
injection with task-scoped context.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.context_plugin import ContextEngineeringPlugin
from zerg.plugin_config import ContextEngineeringConfig
from zerg.plugins import ContextPlugin, PluginRegistry
from zerg.security_rules import filter_rules_for_files, summarize_rules

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

EXPECTED_CORE_MD_FILES = [
    "debug.core.md",
    "design.core.md",
    "init.core.md",
    "merge.core.md",
    "plan.core.md",
    "plugins.core.md",
    "rush.core.md",
    "status.core.md",
    "worker.core.md",
]


def _make_task(
    task_id: str = "1-1",
    title: str = "Implement widget",
    description: str = "Build the widget module",
    create: list[str] | None = None,
    modify: list[str] | None = None,
    context: str | None = None,
) -> dict:
    """Helper to build a minimal task dict for testing."""
    task: dict = {
        "id": task_id,
        "title": title,
        "description": description,
        "level": 1,
        "files": {},
    }
    if create:
        task["files"]["create"] = create
    if modify:
        task["files"]["modify"] = modify
    if context is not None:
        task["context"] = context
    return task


def _make_task_graph(tasks: list[dict], feature: str = "test-feature") -> dict:
    """Helper to build a minimal task graph dict."""
    return {"feature": feature, "tasks": tasks}


# ---------------------------------------------------------------------------
# 1. Plugin registration
# ---------------------------------------------------------------------------


class TestPluginRegistration:
    """ContextEngineeringPlugin registers correctly in PluginRegistry."""

    def test_plugin_registration(self) -> None:
        """ContextEngineeringPlugin registers in PluginRegistry and is discoverable."""
        registry = PluginRegistry()
        plugin = ContextEngineeringPlugin()

        registry.register_context_plugin(plugin)

        plugins = registry.get_context_plugins()
        assert len(plugins) == 1
        assert plugins[0].name == "context-engineering"
        assert isinstance(plugins[0], ContextPlugin)


# ---------------------------------------------------------------------------
# 2. Registry dispatch
# ---------------------------------------------------------------------------


class TestRegistryBuildTaskContext:
    """Registry.build_task_context dispatches correctly to registered plugin."""

    def test_registry_build_task_context(self) -> None:
        """Registry dispatches build_task_context to registered plugin and returns result."""
        registry = PluginRegistry()
        plugin = ContextEngineeringPlugin(ContextEngineeringConfig(security_rule_filtering=False))
        registry.register_context_plugin(plugin)

        task = _make_task(create=["zerg/foo.py"])
        task_graph = _make_task_graph([task])

        result = registry.build_task_context(task, task_graph, "test-feature")
        assert isinstance(result, str)

    def test_registry_no_plugins_returns_empty(self) -> None:
        """Registry with no context plugins returns empty string."""
        registry = PluginRegistry()
        task = _make_task()
        result = registry.build_task_context(task, {}, "feat")
        assert result == ""


# ---------------------------------------------------------------------------
# 3. Orchestrator.generate_task_contexts fills missing
# ---------------------------------------------------------------------------


class TestGenerateTaskContexts:
    """Orchestrator.generate_task_contexts populates tasks without context."""

    def _make_orchestrator_mock(self, registry: PluginRegistry) -> MagicMock:
        """Build a mock Orchestrator with a real _plugin_registry."""
        from zerg.orchestrator import Orchestrator

        mock_orch = MagicMock(spec=Orchestrator)
        mock_orch._plugin_registry = registry
        # Bind the real method to the mock
        mock_orch.generate_task_contexts = Orchestrator.generate_task_contexts.__get__(mock_orch, Orchestrator)
        return mock_orch

    def test_generate_task_contexts_fills_missing(self) -> None:
        """Tasks without context get populated via the registry."""
        registry = PluginRegistry()

        # Use a mock plugin that returns deterministic context
        plugin = MagicMock(spec=ContextPlugin)
        plugin.name = "mock-ctx"
        plugin.build_task_context.return_value = "## Injected Context"
        registry.register_context_plugin(plugin)

        orch = self._make_orchestrator_mock(registry)

        task_a = _make_task(task_id="1-1")
        task_b = _make_task(task_id="1-2")
        graph = _make_task_graph([task_a, task_b])

        contexts = orch.generate_task_contexts(graph)

        assert "1-1" in contexts
        assert "1-2" in contexts
        assert task_a["context"] == "## Injected Context"
        assert task_b["context"] == "## Injected Context"

    def test_generate_task_contexts_skips_existing(self) -> None:
        """Tasks that already have context are not overwritten."""
        registry = PluginRegistry()

        plugin = MagicMock(spec=ContextPlugin)
        plugin.name = "mock-ctx"
        plugin.build_task_context.return_value = "## New Context"
        registry.register_context_plugin(plugin)

        orch = self._make_orchestrator_mock(registry)

        existing_ctx = "## Pre-existing Design Context"
        task = _make_task(task_id="2-1", context=existing_ctx)
        graph = _make_task_graph([task])

        contexts = orch.generate_task_contexts(graph)

        # Should not appear in returned dict and original context unchanged
        assert "2-1" not in contexts
        assert task["context"] == existing_ctx
        plugin.build_task_context.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Fallback behavior
# ---------------------------------------------------------------------------


class TestFallbackBehavior:
    """When plugin fails, build_task_context returns empty string (fallback)."""

    def test_fallback_returns_empty_on_error(self) -> None:
        """Plugin returns empty string when internal logic raises and fallback is enabled."""
        config = ContextEngineeringConfig(fallback_to_full=True)
        plugin = ContextEngineeringPlugin(config)

        task = _make_task(create=["src/main.py"])
        task_graph = _make_task_graph([task])

        # Patch the inner build to force an exception
        with patch.object(plugin, "_build_context_inner", side_effect=ValueError("bad")):
            result = plugin.build_task_context(task, task_graph, "feat")

        assert result == ""

    def test_fallback_disabled_raises(self) -> None:
        """Plugin re-raises when fallback_to_full is disabled."""
        config = ContextEngineeringConfig(fallback_to_full=False)
        plugin = ContextEngineeringPlugin(config)

        task = _make_task(create=["src/main.py"])
        task_graph = _make_task_graph([task])

        with patch.object(plugin, "_build_context_inner", side_effect=ValueError("bad")):
            with pytest.raises(ValueError, match="bad"):
                plugin.build_task_context(task, task_graph, "feat")


# ---------------------------------------------------------------------------
# 5. Split files existence
# ---------------------------------------------------------------------------


class TestSplitFilesExist:
    """All 9 expected .core.md split command files exist."""

    def test_split_files_exist(self) -> None:
        """All expected .core.md files are present in zerg/data/commands/."""
        commands_dir = Path(__file__).resolve().parents[2] / "zerg" / "data" / "commands"

        missing = []
        for filename in EXPECTED_CORE_MD_FILES:
            path = commands_dir / filename
            if not path.exists():
                missing.append(filename)

        assert not missing, f"Missing .core.md files: {missing}"

    def test_get_split_command_path_returns_existing(self) -> None:
        """Plugin's get_split_command_path finds existing .core.md files."""
        plugin = ContextEngineeringPlugin()

        # init should always have a .core.md
        result = plugin.get_split_command_path("init")
        assert result is not None
        assert result.name == "init.core.md"
        assert result.exists()

    def test_get_split_command_path_returns_none_for_missing(self) -> None:
        """Plugin returns None for commands without a .core.md file."""
        plugin = ContextEngineeringPlugin()
        result = plugin.get_split_command_path("nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# 6. Security filtering end-to-end
# ---------------------------------------------------------------------------


class TestSecurityFilteringEndToEnd:
    """Task with .py files gets python security rules filtered and summarized."""

    @pytest.mark.parametrize(
        "file_paths,expected_lang",
        [
            (["zerg/context_plugin.py", "zerg/plugins.py"], "python"),
            (["src/app.js"], "javascript"),
        ],
    )
    def test_language_files_get_language_rules(self, tmp_path: Path, file_paths: list[str], expected_lang: str) -> None:
        """filter_rules_for_files returns language-specific rules for matching files."""
        rules_dir = tmp_path / "security"
        (rules_dir / "_core").mkdir(parents=True)
        (rules_dir / "languages" / expected_lang).mkdir(parents=True)

        (rules_dir / "_core" / "owasp-2025.md").write_text("## Rule: Core\n")
        (rules_dir / "languages" / expected_lang / "CLAUDE.md").write_text(
            f"## Rule: {expected_lang} rule\n**Level**: strict\n"
        )

        result = filter_rules_for_files(file_paths, rules_dir)

        rule_names = [p.name for p in result]
        assert "owasp-2025.md" in rule_names
        assert any(expected_lang in str(p) for p in result)

    def test_no_matching_rules_for_unknown_ext(self, tmp_path: Path) -> None:
        """Files with unknown extensions only get core OWASP rules."""
        rules_dir = tmp_path / "security"
        (rules_dir / "_core").mkdir(parents=True)
        (rules_dir / "_core" / "owasp-2025.md").write_text("## Rule: Core\n")

        result = filter_rules_for_files(["README.md", "logo.png"], rules_dir)
        assert len(result) == 1
        assert result[0].name == "owasp-2025.md"

    def test_summarize_rules_respects_budget(self, tmp_path: Path) -> None:
        """summarize_rules truncates output to stay within token budget."""
        rule_file = tmp_path / "big_rule.md"
        # Generate a large rule file with many rules
        lines = []
        for i in range(100):
            lines.append(f"## Rule: Rule Number {i}")
            lines.append("**Level**: strict")
            lines.append(f"**When**: Always apply rule {i}.")
            lines.append("")
        rule_file.write_text("\n".join(lines))

        # Very small budget: 50 tokens ~ 200 chars
        summary = summarize_rules([rule_file], max_tokens=50)
        assert len(summary) <= 200 + 100  # some tolerance for header


# ---------------------------------------------------------------------------
# 7. Token estimation
# ---------------------------------------------------------------------------


class TestTokenEstimation:
    """Plugin provides reasonable token estimates for tasks."""

    def test_estimate_scales_with_files(self) -> None:
        """More files produce higher token estimates."""
        plugin = ContextEngineeringPlugin()

        small_task = _make_task(create=["a.py"])
        big_task = _make_task(create=["a.py", "b.py", "c.py", "d.py", "e.py"])

        small_est = plugin.estimate_context_tokens(small_task)
        big_est = plugin.estimate_context_tokens(big_task)

        assert big_est > small_est
