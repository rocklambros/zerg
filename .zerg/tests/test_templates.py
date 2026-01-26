"""Tests for ZERG v2 Template Engine."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from template_engine import TemplateEngine, render


class TestVariableSubstitution:
    """Tests for variable substitution."""

    def test_simple_variable(self):
        """Test simple variable replacement."""
        engine = TemplateEngine()
        template = "Hello {{name}}"
        result = engine._render_template(template, {"name": "World"})
        assert result == "Hello World"

    def test_nested_variable(self):
        """Test nested variable replacement."""
        engine = TemplateEngine()
        template = "File: {{files.create}}"
        result = engine._render_template(template, {"files": {"create": "test.py"}})
        assert result == "File: test.py"

    def test_deep_nested_variable(self):
        """Test deeply nested variable replacement."""
        engine = TemplateEngine()
        template = "Value: {{a.b.c}}"
        result = engine._render_template(template, {"a": {"b": {"c": "deep"}}})
        assert result == "Value: deep"

    def test_missing_variable_preserved(self):
        """Test missing variable is preserved."""
        engine = TemplateEngine()
        template = "Hello {{missing}}"
        result = engine._render_template(template, {})
        assert result == "Hello {{missing}}"

    def test_multiple_variables(self):
        """Test multiple variables in template."""
        engine = TemplateEngine()
        template = "{{greeting}} {{name}}!"
        result = engine._render_template(template, {"greeting": "Hi", "name": "Alice"})
        assert result == "Hi Alice!"


class TestEachBlock:
    """Tests for {{#each}} block processing."""

    def test_each_block(self):
        """Test each block iteration."""
        engine = TemplateEngine()
        template = "{{#each items}}- {{this}}\n{{/each}}"
        result = engine._render_template(template, {"items": ["a", "b", "c"]})
        assert result == "- a\n- b\n- c\n"

    def test_each_empty_list(self):
        """Test each block with empty list."""
        engine = TemplateEngine()
        template = "{{#each items}}item{{/each}}"
        result = engine._render_template(template, {"items": []})
        assert result == ""

    def test_each_nested_key(self):
        """Test each with nested key."""
        engine = TemplateEngine()
        template = "{{#each files.create}}{{this}}{{/each}}"
        result = engine._render_template(
            template, {"files": {"create": ["a.py", "b.py"]}}
        )
        assert result == "a.pyb.py"


class TestIfBlock:
    """Tests for {{#if}} block processing."""

    def test_if_true(self):
        """Test if block with truthy value."""
        engine = TemplateEngine()
        template = "{{#if show}}Visible{{/if}}"
        result = engine._render_template(template, {"show": True})
        assert result == "Visible"

    def test_if_false(self):
        """Test if block with falsy value."""
        engine = TemplateEngine()
        template = "{{#if show}}Visible{{/if}}"
        result = engine._render_template(template, {"show": False})
        assert result == ""

    def test_if_missing(self):
        """Test if block with missing key."""
        engine = TemplateEngine()
        template = "{{#if missing}}Content{{/if}}"
        result = engine._render_template(template, {})
        assert result == ""

    def test_if_nested_key(self):
        """Test if with nested key."""
        engine = TemplateEngine()
        template = "{{#if config.debug}}Debug mode{{/if}}"
        result = engine._render_template(template, {"config": {"debug": True}})
        assert result == "Debug mode"


class TestTemplateLoading:
    """Tests for template loading."""

    def test_load_template_from_file(self, tmp_path):
        """Test loading template from file."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "test.md").write_text("Hello {{name}}")

        engine = TemplateEngine(template_dir)
        result = engine.render("test.md", {"name": "World"})
        assert result == "Hello World"

    def test_template_caching(self, tmp_path):
        """Test templates are cached."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "test.md").write_text("Hello {{name}}")

        engine = TemplateEngine(template_dir)
        engine.render("test.md", {"name": "World"})
        assert "test.md" in engine._cache

    def test_custom_template_override(self, tmp_path):
        """Test custom templates override default."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        custom_dir = template_dir / "custom"
        custom_dir.mkdir()
        (template_dir / "test.md").write_text("Default")
        (custom_dir / "test.md").write_text("Custom")

        engine = TemplateEngine(template_dir)
        result = engine.render("test.md", {})
        assert result == "Custom"


class TestRenderFunction:
    """Tests for convenience render function."""

    def test_render_with_real_templates(self, tmp_path, monkeypatch):
        """Test render function uses TemplateEngine."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "greeting.md").write_text("Hi {{name}}")

        # Patch the default template dir
        monkeypatch.setattr(TemplateEngine, "TEMPLATE_DIR", template_dir)

        result = render("greeting.md", {"name": "Bob"})
        assert result == "Hi Bob"


class TestComplexTemplates:
    """Tests for complex template scenarios."""

    def test_combined_features(self):
        """Test template with multiple features combined."""
        engine = TemplateEngine()
        template = """# {{title}}
{{#if description}}{{description}}{{/if}}
Files:
{{#each files}}- {{this}}
{{/each}}"""
        context = {
            "title": "Task",
            "description": "Do something",
            "files": ["a.py", "b.py"],
        }
        result = engine._render_template(template, context)
        assert "# Task" in result
        assert "Do something" in result
        assert "- a.py" in result
        assert "- b.py" in result

    def test_implementer_template_context(self, tmp_path):
        """Test context similar to implementer template."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "impl.md").write_text(
            """Task: {{task_id}}
{{#each files.create}}- Create: {{this}}
{{/each}}
Run: {{verification.command}}"""
        )

        engine = TemplateEngine(template_dir)
        context = {
            "task_id": "TASK-001",
            "files": {"create": ["src/auth.py", "tests/test_auth.py"]},
            "verification": {"command": "pytest tests/"},
        }
        result = engine.render("impl.md", context)
        assert "TASK-001" in result
        assert "src/auth.py" in result
        assert "pytest tests/" in result
