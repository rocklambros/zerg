"""Unit tests for inception.py - scaffold generation."""

from pathlib import Path

from zerg.charter import ProjectCharter
from zerg.inception import (
    _build_template_context,
    _evaluate_condition,
    _render_template,
    _to_kebab_case,
    _to_snake_case,
    scaffold_project,
)
from zerg.tech_selector import TechStack


class TestNameConversions:
    """Tests for name conversion utilities."""

    def test_to_snake_case_simple(self) -> None:
        """Test simple snake_case conversion."""
        assert _to_snake_case("myProject") == "my_project"

    def test_to_snake_case_with_hyphens(self) -> None:
        """Test snake_case with hyphens."""
        assert _to_snake_case("my-project") == "my_project"

    def test_to_snake_case_with_spaces(self) -> None:
        """Test snake_case with spaces."""
        assert _to_snake_case("my project") == "my_project"

    def test_to_snake_case_already_snake(self) -> None:
        """Test already snake_case input."""
        assert _to_snake_case("my_project") == "my_project"

    def test_to_kebab_case_simple(self) -> None:
        """Test simple kebab-case conversion."""
        assert _to_kebab_case("myProject") == "my-project"

    def test_to_kebab_case_with_underscores(self) -> None:
        """Test kebab-case with underscores."""
        assert _to_kebab_case("my_project") == "my-project"

    def test_to_kebab_case_with_spaces(self) -> None:
        """Test kebab-case with spaces."""
        assert _to_kebab_case("my project") == "my-project"


class TestTemplateContext:
    """Tests for template context building."""

    def test_builds_context_with_names(self) -> None:
        """Test that context includes name variations."""
        charter = ProjectCharter(
            name="MyProject",
            description="A test project",
        )
        stack = TechStack(language="python")

        context = _build_template_context(charter, stack)

        assert context["project_name"] == "MyProject"
        assert context["project_name_snake"] == "my_project"
        assert context["project_name_kebab"] == "my-project"

    def test_builds_context_with_stack_info(self) -> None:
        """Test that context includes stack information."""
        charter = ProjectCharter(name="test", description="Test")
        stack = TechStack(
            language="python",
            language_version="3.12",
            primary_framework="fastapi",
            test_framework="pytest",
        )

        context = _build_template_context(charter, stack)

        assert context["language"] == "python"
        assert context["language_version"] == "3.12"
        assert context["framework"] == "fastapi"
        assert context["test_framework"] == "pytest"

    def test_builds_context_with_charter_details(self) -> None:
        """Test that context includes charter details."""
        charter = ProjectCharter(
            name="test",
            description="Test",
            security_level="strict",
            testing_strategy="comprehensive",
        )
        stack = TechStack(language="python")

        context = _build_template_context(charter, stack)

        assert context["security_level"] == "strict"
        assert context["testing_strategy"] == "comprehensive"


class TestEvaluateCondition:
    """Tests for condition evaluation."""

    def test_truthy_check_true(self) -> None:
        """Test truthy check with true value."""
        assert _evaluate_condition("framework", {"framework": "fastapi"}) is True

    def test_truthy_check_false(self) -> None:
        """Test truthy check with false value."""
        assert _evaluate_condition("framework", {"framework": ""}) is False

    def test_truthy_check_missing(self) -> None:
        """Test truthy check with missing value."""
        assert _evaluate_condition("missing", {}) is False

    def test_equality_true(self) -> None:
        """Test equality check that matches."""
        context = {"framework": "fastapi"}
        assert _evaluate_condition("framework == 'fastapi'", context) is True

    def test_equality_false(self) -> None:
        """Test equality check that doesn't match."""
        context = {"framework": "flask"}
        assert _evaluate_condition("framework == 'fastapi'", context) is False

    def test_inequality_true(self) -> None:
        """Test inequality check that matches."""
        context = {"framework": "flask"}
        assert _evaluate_condition("framework != 'fastapi'", context) is True

    def test_in_operator_true(self) -> None:
        """Test 'in' operator with matching value."""
        context = {"framework": "fastapi"}
        assert _evaluate_condition("framework in ['fastapi', 'flask']", context) is True

    def test_in_operator_false(self) -> None:
        """Test 'in' operator with non-matching value."""
        context = {"framework": "django"}
        assert _evaluate_condition("framework in ['fastapi', 'flask']", context) is False


class TestRenderTemplate:
    """Tests for template rendering."""

    def test_simple_substitution(self) -> None:
        """Test simple variable substitution."""
        template = "Hello {{ name }}!"
        context = {"name": "World"}

        result = _render_template(template, context)

        assert result == "Hello World!"

    def test_multiple_substitutions(self) -> None:
        """Test multiple variable substitutions."""
        template = "{{ greeting }} {{ name }}!"
        context = {"greeting": "Hello", "name": "World"}

        result = _render_template(template, context)

        assert result == "Hello World!"

    def test_missing_variable_becomes_empty(self) -> None:
        """Test that missing variables become empty strings."""
        template = "Hello {{ name }}!"
        context = {}

        result = _render_template(template, context)

        assert result == "Hello !"

    def test_simple_if_true(self) -> None:
        """Test simple if block with true condition."""
        template = "{% if show %}Visible{% endif %}"
        context = {"show": True}

        result = _render_template(template, context)

        assert "Visible" in result

    def test_simple_if_false(self) -> None:
        """Test simple if block with false condition."""
        template = "{% if show %}Visible{% endif %}"
        context = {"show": False}

        result = _render_template(template, context)

        assert "Visible" not in result

    def test_if_with_equality(self) -> None:
        """Test if block with equality condition."""
        template = "{% if lang == 'python' %}Python code{% endif %}"
        context = {"lang": "python"}

        result = _render_template(template, context)

        assert "Python code" in result


class TestScaffoldProject:
    """Tests for scaffold_project function."""

    def test_creates_files(self, tmp_path: Path) -> None:
        """Test that scaffold creates files."""
        charter = ProjectCharter(
            name="test-project",
            description="A test project",
        )
        stack = TechStack(
            language="python",
            language_version="3.12",
            package_manager="uv",
            primary_framework="",
            test_framework="pytest",
            linter="ruff",
            formatter="ruff",
            type_checker="mypy",
        )

        files = scaffold_project(charter, stack, tmp_path)

        assert len(files) > 0

    def test_creates_pyproject_for_python(self, tmp_path: Path) -> None:
        """Test that pyproject.toml is created for Python projects."""
        charter = ProjectCharter(name="py-project", description="Python project")
        stack = TechStack(
            language="python",
            language_version="3.12",
            package_manager="uv",
        )

        files = scaffold_project(charter, stack, tmp_path)

        assert "pyproject.toml" in files

    def test_creates_package_dir_for_python(self, tmp_path: Path) -> None:
        """Test that package directory is created for Python projects."""
        charter = ProjectCharter(name="my-package", description="Test")
        stack = TechStack(
            language="python",
            language_version="3.12",
        )

        scaffold_project(charter, stack, tmp_path)

        pkg_dir = tmp_path / "my_package"
        assert pkg_dir.exists()
        assert (pkg_dir / "__init__.py").exists()

    def test_creates_tests_dir(self, tmp_path: Path) -> None:
        """Test that tests directory is created."""
        charter = ProjectCharter(name="test-project", description="Test")
        stack = TechStack(
            language="python",
            language_version="3.12",
        )

        scaffold_project(charter, stack, tmp_path)

        tests_dir = tmp_path / "tests"
        assert tests_dir.exists()
        assert (tests_dir / "__init__.py").exists()

    def test_creates_gitignore(self, tmp_path: Path) -> None:
        """Test that .gitignore is created."""
        charter = ProjectCharter(name="test-project", description="Test")
        stack = TechStack(
            language="python",
            language_version="3.12",
        )

        files = scaffold_project(charter, stack, tmp_path)

        assert ".gitignore" in files

    def test_handles_missing_language_templates(self, tmp_path: Path) -> None:
        """Test graceful handling of missing language templates."""
        charter = ProjectCharter(name="test", description="Test")
        stack = TechStack(language="nonexistent-language")

        files = scaffold_project(charter, stack, tmp_path)

        # Should return empty dict without error
        assert files == {}

    def test_substitutes_project_name(self, tmp_path: Path) -> None:
        """Test that project name is substituted in templates."""
        charter = ProjectCharter(
            name="awesome-api",
            description="An awesome API",
        )
        stack = TechStack(
            language="python",
            language_version="3.12",
            primary_framework="fastapi",
        )

        scaffold_project(charter, stack, tmp_path)

        # Check pyproject.toml contains project name
        pyproject = tmp_path / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            assert "awesome-api" in content or "awesome_api" in content
