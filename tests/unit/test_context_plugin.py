"""Tests for ZERG context engineering plugin module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.context_plugin import ContextEngineeringPlugin
from zerg.plugin_config import ContextEngineeringConfig


class TestContextPluginName:
    """Tests for plugin identity."""

    def test_plugin_name(self) -> None:
        """Test name property returns 'context-engineering'."""
        plugin = ContextEngineeringPlugin()

        assert plugin.name == "context-engineering"


class TestBuildTaskContext:
    """Tests for build_task_context method."""

    def test_build_task_context_with_files(self, tmp_path: Path) -> None:
        """Test building context for a task that owns Python files."""
        config = ContextEngineeringConfig(
            security_rule_filtering=True,
            command_splitting=False,
            task_context_budget_tokens=4000,
        )
        plugin = ContextEngineeringPlugin(config=config)

        # Set up a minimal security rules directory so filtering can find files
        rules_dir = tmp_path / ".claude" / "rules" / "security"
        lang_dir = rules_dir / "languages" / "python"
        lang_dir.mkdir(parents=True)
        rule_file = lang_dir / "CLAUDE.md"
        rule_file.write_text(
            "## Rule: Use Parameterized Queries\n"
            "**Level**: `strict`\n"
            "**When**: Constructing database queries with user input.\n"
        )
        core_dir = rules_dir / "_core"
        core_dir.mkdir(parents=True)
        owasp_file = core_dir / "owasp-2025.md"
        owasp_file.write_text(
            "## Rule: Enforce Server-Side Access Control\n"
            "**Level**: `strict`\n"
            "**When**: Any endpoint accessing protected resources.\n"
        )

        task = {
            "id": "T-1",
            "description": "Add user API endpoint",
            "files": {
                "create": ["src/api/users.py"],
                "modify": ["src/models/user.py"],
            },
        }

        with patch(
            "zerg.context_plugin.DEFAULT_RULES_DIR", rules_dir
        ), patch(
            "zerg.context_plugin.SpecLoader"
        ) as mock_loader_cls:
            mock_loader_cls.return_value.format_task_context.return_value = (
                "## Spec: user API endpoint"
            )
            result = plugin.build_task_context(task, {}, "user-auth")

        # Should include security section and spec section
        assert isinstance(result, str)
        # The spec loader mock returns content, so we expect something
        assert "Spec" in result or "Security" in result

    def test_build_task_context_empty_files(self) -> None:
        """Test building context for a task with no files returns gracefully."""
        config = ContextEngineeringConfig(
            security_rule_filtering=True,
            command_splitting=False,
        )
        plugin = ContextEngineeringPlugin(config=config)

        task = {
            "id": "T-2",
            "description": "Planning task with no files",
            "files": {},
        }

        with patch("zerg.context_plugin.SpecLoader") as mock_loader_cls:
            mock_loader_cls.return_value.format_task_context.return_value = ""
            result = plugin.build_task_context(task, {}, "feature-x")

        # No files means no security section; empty spec returns empty
        assert isinstance(result, str)

    def test_build_task_context_security_filtering(self, tmp_path: Path) -> None:
        """Test that security rules are filtered by file extension."""
        config = ContextEngineeringConfig(
            security_rule_filtering=True,
            command_splitting=False,
            task_context_budget_tokens=4000,
        )
        plugin = ContextEngineeringPlugin(config=config)

        # Create only Python rules, no JS rules
        rules_dir = tmp_path / ".claude" / "rules" / "security"
        py_dir = rules_dir / "languages" / "python"
        py_dir.mkdir(parents=True)
        (py_dir / "CLAUDE.md").write_text(
            "### Rule: Safe subprocess\n**Level**: `strict`\n"
            "**When**: Executing system commands.\n"
        )
        core_dir = rules_dir / "_core"
        core_dir.mkdir(parents=True)
        (core_dir / "owasp-2025.md").write_text(
            "### Rule: Parameterized Queries\n**Level**: `strict`\n"
            "**When**: Constructing queries.\n"
        )

        # Task has only .py files -- should get python rules
        task = {
            "id": "T-3",
            "files": {"create": ["app.py"]},
            "description": "Python task",
        }

        with patch(
            "zerg.context_plugin.DEFAULT_RULES_DIR", rules_dir
        ), patch("zerg.context_plugin.SpecLoader") as mock_loader_cls:
            mock_loader_cls.return_value.format_task_context.return_value = ""
            result = plugin.build_task_context(task, {}, "feat")

        # Should include security content (python rules matched)
        assert "Security Rules" in result
        assert "Safe subprocess" in result or "Parameterized" in result

    def test_build_task_context_budget_limit(self, tmp_path: Path) -> None:
        """Test that result stays within the configured token budget."""
        budget = 1000
        config = ContextEngineeringConfig(
            security_rule_filtering=True,
            command_splitting=False,
            task_context_budget_tokens=budget,
        )
        plugin = ContextEngineeringPlugin(config=config)

        # Create a large rule file to test budget enforcement
        rules_dir = tmp_path / ".claude" / "rules" / "security"
        core_dir = rules_dir / "_core"
        core_dir.mkdir(parents=True)
        # Write a rule file that would be large
        (core_dir / "owasp-2025.md").write_text(
            ("### Rule: Test Rule\n**Level**: `strict`\n**When**: Always.\n" * 100)
        )
        py_dir = rules_dir / "languages" / "python"
        py_dir.mkdir(parents=True)
        (py_dir / "CLAUDE.md").write_text(
            ("### Rule: PY Rule\n**Level**: `strict`\n**When**: Always.\n" * 100)
        )

        task = {
            "id": "T-4",
            "files": {"create": ["main.py"]},
            "description": "Test",
        }

        with patch(
            "zerg.context_plugin.DEFAULT_RULES_DIR", rules_dir
        ), patch("zerg.context_plugin.SpecLoader") as mock_loader_cls:
            mock_loader_cls.return_value.format_task_context.return_value = ""
            result = plugin.build_task_context(task, {}, "feat")

        # Budget is 1000 tokens ~ 4000 chars; result should not wildly exceed
        # (security gets 30% = 300 tokens = 1200 chars)
        assert len(result) < budget * 4 * 2  # generous upper bound

    def test_build_task_context_fallback_on_error(self) -> None:
        """Test that fallback_to_full=True returns '' on internal error."""
        config = ContextEngineeringConfig(fallback_to_full=True)
        plugin = ContextEngineeringPlugin(config=config)

        task = {"id": "T-5", "description": "test", "files": {"create": ["a.py"]}}

        with patch.object(
            plugin, "_build_context_inner", side_effect=RuntimeError("boom")
        ):
            result = plugin.build_task_context(task, {}, "feat")

        assert result == ""

    def test_build_task_context_raises_without_fallback(self) -> None:
        """Test that fallback_to_full=False re-raises the exception."""
        config = ContextEngineeringConfig(fallback_to_full=False)
        plugin = ContextEngineeringPlugin(config=config)

        task = {"id": "T-6", "description": "test", "files": {"create": ["a.py"]}}

        with patch.object(
            plugin, "_build_context_inner", side_effect=RuntimeError("boom")
        ):
            with pytest.raises(RuntimeError, match="boom"):
                plugin.build_task_context(task, {}, "feat")


class TestEstimateContextTokens:
    """Tests for estimate_context_tokens method."""

    def test_estimate_context_tokens(self) -> None:
        """Test token estimation returns a reasonable value."""
        plugin = ContextEngineeringPlugin()

        task = {
            "id": "T-7",
            "description": "A moderately long description for estimation",
            "files": {
                "create": ["a.py", "b.py"],
                "modify": ["c.py"],
            },
        }

        tokens = plugin.estimate_context_tokens(task)

        # file_count = 3, description = ~48 chars
        # expected: 3 * 500 + 48 // 4 = 1512
        assert tokens > 0
        assert tokens >= 3 * 500  # at least file-based component


class TestGetSplitCommandPath:
    """Tests for get_split_command_path method."""

    def test_get_split_command_path_exists(self, tmp_path: Path) -> None:
        """Test returns path when core split file exists."""
        config = ContextEngineeringConfig(command_splitting=True)
        plugin = ContextEngineeringPlugin(config=config)

        # Point splitter to tmp_path
        plugin._splitter.commands_dir = tmp_path

        core_file = tmp_path / "zerg:init.core.md"
        core_file.write_text("# Core instructions only")

        result = plugin.get_split_command_path("zerg:init")

        assert result is not None
        assert result == core_file

    def test_get_split_command_path_missing(self, tmp_path: Path) -> None:
        """Test returns None when core split file does not exist."""
        config = ContextEngineeringConfig(command_splitting=True)
        plugin = ContextEngineeringPlugin(config=config)

        plugin._splitter.commands_dir = tmp_path

        result = plugin.get_split_command_path("zerg:nonexistent")

        assert result is None

    def test_get_split_command_path_disabled(self, tmp_path: Path) -> None:
        """Test returns None when command splitting is disabled."""
        config = ContextEngineeringConfig(command_splitting=False)
        plugin = ContextEngineeringPlugin(config=config)

        plugin._splitter.commands_dir = tmp_path

        # Even if the file exists, splitting is off
        core_file = tmp_path / "zerg:init.core.md"
        core_file.write_text("# Core")

        result = plugin.get_split_command_path("zerg:init")

        assert result is None
