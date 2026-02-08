"""Unit tests for inception module: project detection, scaffolding, template rendering, and orchestration."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from zerg.charter import ProjectCharter
from zerg.commands.init import is_empty_project
from zerg.inception import (
    _build_template_context,
    _evaluate_condition,
    _init_git_repo,
    _process_conditionals,
    _render_template,
    _resolve_if_block,
    _show_inception_summary,
    _to_kebab_case,
    _to_snake_case,
    run_inception_mode,
    scaffold_project,
)
from zerg.tech_selector import TechStack

# ---------------------------------------------------------------------------
# Existing tests for is_empty_project (preserved)
# ---------------------------------------------------------------------------


class TestIsEmptyProject:
    """Tests for empty project detection."""

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Test that empty directory is detected as empty."""
        assert is_empty_project(tmp_path) is True

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        """Test that nonexistent directory is detected as empty."""
        nonexistent = tmp_path / "does-not-exist"
        assert is_empty_project(nonexistent) is True

    def test_directory_with_git(self, tmp_path: Path) -> None:
        """Test that directory with .git is not empty."""
        (tmp_path / ".git").mkdir()
        assert is_empty_project(tmp_path) is False

    def test_directory_with_pyproject(self, tmp_path: Path) -> None:
        """Test that directory with pyproject.toml is not empty."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_package_json(self, tmp_path: Path) -> None:
        """Test that directory with package.json is not empty."""
        (tmp_path / "package.json").write_text('{"name": "test"}')
        assert is_empty_project(tmp_path) is False

    def test_directory_with_go_mod(self, tmp_path: Path) -> None:
        """Test that directory with go.mod is not empty."""
        (tmp_path / "go.mod").write_text("module test")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_cargo_toml(self, tmp_path: Path) -> None:
        """Test that directory with Cargo.toml is not empty."""
        (tmp_path / "Cargo.toml").write_text("[package]\nname = 'test'")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_src_dir(self, tmp_path: Path) -> None:
        """Test that directory with src/ is not empty."""
        (tmp_path / "src").mkdir()
        assert is_empty_project(tmp_path) is False

    def test_directory_with_python_file(self, tmp_path: Path) -> None:
        """Test that directory with .py file is not empty."""
        (tmp_path / "main.py").write_text("print('hello')")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_typescript_file(self, tmp_path: Path) -> None:
        """Test that directory with .ts file is not empty."""
        (tmp_path / "index.ts").write_text("console.log('hello');")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_only_readme(self, tmp_path: Path) -> None:
        """Test that directory with only README is empty (no project indicators)."""
        (tmp_path / "README.md").write_text("# Project")
        assert is_empty_project(tmp_path) is True

    def test_directory_with_only_dotfiles(self, tmp_path: Path) -> None:
        """Test that directory with non-project dotfiles is empty."""
        (tmp_path / ".env").write_text("KEY=value")
        (tmp_path / ".gitignore").write_text("*.pyc")
        assert is_empty_project(tmp_path) is True

    def test_directory_with_csproj(self, tmp_path: Path) -> None:
        """Test that directory with .csproj file is not empty."""
        (tmp_path / "MyProject.csproj").write_text("<Project></Project>")
        assert is_empty_project(tmp_path) is False

    def test_default_path_uses_cwd(self, tmp_path: Path, monkeypatch) -> None:
        """Test that default path uses current working directory."""
        monkeypatch.chdir(tmp_path)
        # Empty directory
        assert is_empty_project() is True

        # Add project indicator
        (tmp_path / "pyproject.toml").write_text("[project]")
        assert is_empty_project() is False


# ---------------------------------------------------------------------------
# Helper factories for common test objects
# ---------------------------------------------------------------------------


def _make_charter(**overrides) -> ProjectCharter:
    """Create a ProjectCharter with sensible defaults and optional overrides."""
    defaults = dict(
        name="TestProject",
        description="A test project",
        purpose="Testing inception scaffolding",
        primary_language="python",
        target_platforms=["api"],
        security_level="standard",
        testing_strategy="standard",
    )
    defaults.update(overrides)
    return ProjectCharter(**defaults)


def _make_stack(**overrides) -> TechStack:
    """Create a TechStack with sensible defaults and optional overrides."""
    defaults = dict(
        language="python",
        language_version="3.12",
        package_manager="uv",
        primary_framework="fastapi",
        test_framework="pytest",
        linter="ruff",
        formatter="ruff",
        database_driver="",
        orm="",
        dockerfile=True,
        ci_provider="github-actions",
    )
    defaults.update(overrides)
    return TechStack(**defaults)


# ---------------------------------------------------------------------------
# Tests for scaffold_project — file routing per language
# ---------------------------------------------------------------------------


class TestScaffoldProject:
    """Tests for scaffold_project covering all language-specific file placement."""

    def test_python_scaffold_creates_package_and_tests(self, tmp_path: Path) -> None:
        """Python templates place source in package dir, tests in tests/."""
        charter = _make_charter(name="MyApp")
        stack = _make_stack(language="python")

        created = scaffold_project(charter, stack, output_dir=tmp_path)

        # main.py should be inside the snake_case package directory
        assert any("my_app/main.py" in k for k in created), f"Expected my_app/main.py in {list(created.keys())}"
        # test file should be in tests/
        assert any("tests/test_main.py" in k for k in created), f"Expected tests/test_main.py in {list(created.keys())}"
        # tests/__init__.py must also exist
        assert (tmp_path / "tests" / "__init__.py").exists()

    def test_typescript_scaffold_places_src_files(self, tmp_path: Path) -> None:
        """TypeScript index.ts and index.test.ts go in src/ directory (lines 83-85)."""
        charter = _make_charter(name="TsProject")
        stack = _make_stack(
            language="typescript",
            language_version="5.x",
            package_manager="pnpm",
            primary_framework="fastify",
            test_framework="vitest",
            linter="eslint",
            formatter="prettier",
        )

        created = scaffold_project(charter, stack, output_dir=tmp_path)

        assert any("src/index.ts" in k for k in created), f"Expected src/index.ts in {list(created.keys())}"
        assert any("src/index.test.ts" in k for k in created), f"Expected src/index.test.ts in {list(created.keys())}"
        assert (tmp_path / "src").is_dir()

    def test_go_scaffold_places_files_at_root(self, tmp_path: Path) -> None:
        """Go main.go and main_test.go stay at project root (line 88)."""
        charter = _make_charter(name="GoProject")
        stack = _make_stack(
            language="go",
            language_version="1.22",
            package_manager="go mod",
            primary_framework="gin",
            test_framework="go test",
            linter="golangci-lint",
            formatter="gofmt",
        )

        created = scaffold_project(charter, stack, output_dir=tmp_path)

        assert any(k == "main.go" for k in created), f"Expected main.go at root in {list(created.keys())}"
        assert any(k == "main_test.go" for k in created), f"Expected main_test.go at root in {list(created.keys())}"

    def test_rust_scaffold_places_main_rs_in_src(self, tmp_path: Path) -> None:
        """Rust main.rs goes in src/ directory (lines 91-93)."""
        charter = _make_charter(name="RustProject")
        stack = _make_stack(
            language="rust",
            language_version="stable",
            package_manager="cargo",
            primary_framework="axum",
            test_framework="cargo test",
            linter="clippy",
            formatter="rustfmt",
        )

        created = scaffold_project(charter, stack, output_dir=tmp_path)

        assert any("src/main.rs" in k for k in created), f"Expected src/main.rs in {list(created.keys())}"
        assert (tmp_path / "src").is_dir()

    def test_scaffold_no_templates_returns_empty(self, tmp_path: Path) -> None:
        """Scaffold for unknown language with no template dir returns empty dict."""
        charter = _make_charter(name="UnknownLang")
        stack = _make_stack(language="haskell")

        created = scaffold_project(charter, stack, output_dir=tmp_path)
        assert created == {}

    def test_gitignore_template_renamed(self, tmp_path: Path) -> None:
        """Templates named 'gitignore' become '.gitignore' in output."""
        charter = _make_charter(name="MyApp")
        stack = _make_stack(language="python")

        created = scaffold_project(charter, stack, output_dir=tmp_path)

        assert any(".gitignore" in k for k in created), f"Expected .gitignore in {list(created.keys())}"

    def test_scaffold_default_output_dir(self, tmp_path: Path, monkeypatch) -> None:
        """When output_dir is None, scaffold_project defaults to current directory."""
        monkeypatch.chdir(tmp_path)
        charter = _make_charter(name="DefaultDir")
        stack = _make_stack(language="python")

        created = scaffold_project(charter, stack, output_dir=None)
        # Files should have been created under tmp_path (cwd)
        assert len(created) > 0


# ---------------------------------------------------------------------------
# Tests for _build_template_context
# ---------------------------------------------------------------------------


class TestBuildTemplateContext:
    """Tests for _build_template_context."""

    def test_context_contains_all_expected_keys(self) -> None:
        """Verify that the context dict has every key templates might reference."""
        charter = _make_charter(name="My Cool App")
        stack = _make_stack(database_driver="asyncpg", orm="sqlalchemy")

        ctx = _build_template_context(charter, stack)

        expected_keys = {
            "project_name",
            "project_name_snake",
            "project_name_kebab",
            "description",
            "purpose",
            "language",
            "language_version",
            "framework",
            "test_framework",
            "linter",
            "formatter",
            "database_driver",
            "orm",
            "dockerfile",
            "ci_provider",
            "security_level",
            "testing_strategy",
        }
        assert expected_keys.issubset(ctx.keys())

    def test_name_conversion_in_context(self) -> None:
        """Project name is converted to snake_case and kebab-case in context."""
        charter = _make_charter(name="MyApp")
        stack = _make_stack()
        ctx = _build_template_context(charter, stack)

        assert ctx["project_name_snake"] == "my_app"
        assert ctx["project_name_kebab"] == "my-app"


# ---------------------------------------------------------------------------
# Tests for _render_template and _process_conditionals
# ---------------------------------------------------------------------------


class TestRenderTemplate:
    """Tests for template rendering with variable substitution and conditionals."""

    def test_simple_variable_substitution(self) -> None:
        """Variables inside {{ }} are replaced."""
        ctx = {"name": "hello"}
        result = _render_template("Say {{ name }}", ctx)
        assert result == "Say hello"

    def test_unresolved_variables_removed(self) -> None:
        """Unresolved {{ var }} placeholders are replaced with empty string."""
        result = _render_template("Hello {{ unknown_var }}!", {})
        assert "unknown_var" not in result

    def test_none_value_renders_empty(self) -> None:
        """None values render as empty string."""
        ctx = {"framework": None}
        result = _render_template("Framework: {{ framework }}", ctx)
        assert result == "Framework: "

    def test_if_true_condition(self) -> None:
        """True condition renders if-block content."""
        template = "{% if show %}visible{% endif %}"
        result = _render_template(template, {"show": True})
        assert "visible" in result

    def test_if_false_condition_renders_empty(self) -> None:
        """False condition renders nothing."""
        template = "{% if show %}hidden{% endif %}"
        result = _render_template(template, {"show": False})
        assert "hidden" not in result

    def test_if_else_renders_else_branch(self) -> None:
        """When condition is false, else branch is rendered."""
        template = "{% if show %}yes{% else %}no{% endif %}"
        result = _render_template(template, {"show": False})
        assert "no" in result
        assert "yes" not in result

    def test_elif_branch_matches(self) -> None:
        """When if is false but elif is true, elif content renders (line 265)."""
        template = "{% if lang == 'go' %}go code{% elif lang == 'python' %}py code{% else %}other{% endif %}"
        result = _render_template(template, {"lang": "python"})
        assert "py code" in result
        assert "go code" not in result
        assert "other" not in result

    def test_elif_falls_through_to_else(self) -> None:
        """When if and elif are both false, else branch renders."""
        template = "{% if lang == 'go' %}go{% elif lang == 'python' %}py{% else %}other{% endif %}"
        result = _render_template(template, {"lang": "rust"})
        assert "other" in result
        assert "go" not in result
        assert "py" not in result


# ---------------------------------------------------------------------------
# Tests for _evaluate_condition
# ---------------------------------------------------------------------------


class TestEvaluateCondition:
    """Tests for the condition evaluator."""

    def test_truthy_variable(self) -> None:
        assert _evaluate_condition("flag", {"flag": True}) is True

    def test_falsy_variable(self) -> None:
        assert _evaluate_condition("flag", {"flag": False}) is False

    def test_missing_variable_is_falsy(self) -> None:
        assert _evaluate_condition("missing", {}) is False

    def test_equality_match(self) -> None:
        assert _evaluate_condition("lang == 'python'", {"lang": "python"}) is True

    def test_equality_mismatch(self) -> None:
        assert _evaluate_condition("lang == 'go'", {"lang": "python"}) is False

    def test_inequality_match(self) -> None:
        assert _evaluate_condition("lang != 'go'", {"lang": "python"}) is True

    def test_inequality_mismatch(self) -> None:
        assert _evaluate_condition("lang != 'python'", {"lang": "python"}) is False

    def test_in_operator_match(self) -> None:
        assert _evaluate_condition("lang in ['python', 'go']", {"lang": "go"}) is True

    def test_in_operator_no_match(self) -> None:
        assert _evaluate_condition("lang in ['python', 'go']", {"lang": "rust"}) is False


# ---------------------------------------------------------------------------
# Tests for name conversion helpers
# ---------------------------------------------------------------------------


class TestNameConversion:
    """Tests for _to_snake_case and _to_kebab_case."""

    def test_snake_case_camel(self) -> None:
        assert _to_snake_case("MyApp") == "my_app"

    def test_snake_case_hyphens(self) -> None:
        assert _to_snake_case("my-cool-app") == "my_cool_app"

    def test_snake_case_spaces(self) -> None:
        assert _to_snake_case("My Cool App") == "my_cool_app"

    def test_kebab_case_camel(self) -> None:
        assert _to_kebab_case("MyApp") == "my-app"

    def test_kebab_case_underscores(self) -> None:
        assert _to_kebab_case("my_cool_app") == "my-cool-app"

    def test_kebab_case_spaces(self) -> None:
        assert _to_kebab_case("My Cool App") == "my-cool-app"


# ---------------------------------------------------------------------------
# Tests for run_inception_mode (lines 369-423)
# ---------------------------------------------------------------------------


class TestRunInceptionMode:
    """Tests for the full inception orchestration workflow."""

    @patch("zerg.inception._show_inception_summary")
    @patch("zerg.inception._init_git_repo")
    @patch("zerg.inception.write_project_md")
    @patch("zerg.inception.scaffold_project")
    @patch("zerg.inception.select_technology")
    @patch("zerg.inception.gather_requirements")
    def test_successful_run(
        self,
        mock_gather,
        mock_select,
        mock_scaffold,
        mock_write_md,
        mock_init_git,
        mock_summary,
    ) -> None:
        """Successful inception returns True and calls all steps."""
        charter = _make_charter()
        stack = _make_stack()
        mock_gather.return_value = charter
        mock_select.return_value = stack
        mock_scaffold.return_value = {"main.py": Path("main.py")}
        mock_write_md.return_value = Path("PROJECT.md")

        result = run_inception_mode(security_level="standard")

        assert result is True
        mock_gather.assert_called_once()
        mock_select.assert_called_once_with(charter)
        mock_scaffold.assert_called_once_with(charter, stack)
        mock_write_md.assert_called_once_with(charter)
        mock_init_git.assert_called_once()
        mock_summary.assert_called_once_with(charter, stack, {"main.py": Path("main.py")})

    @patch("zerg.inception.scaffold_project")
    @patch("zerg.inception.select_technology")
    @patch("zerg.inception.gather_requirements")
    def test_empty_scaffold_shows_warning(
        self,
        mock_gather,
        mock_select,
        mock_scaffold,
    ) -> None:
        """When scaffold returns no files, the warning path executes (line 393-394)."""
        mock_gather.return_value = _make_charter()
        mock_select.return_value = _make_stack()
        mock_scaffold.return_value = {}

        with (
            patch("zerg.inception.write_project_md", return_value=Path("PROJECT.md")),
            patch("zerg.inception._init_git_repo"),
            patch("zerg.inception._show_inception_summary"),
        ):
            result = run_inception_mode()

        assert result is True

    @patch("zerg.inception.gather_requirements", side_effect=KeyboardInterrupt)
    def test_keyboard_interrupt_returns_false(self, mock_gather) -> None:
        """KeyboardInterrupt during inception returns False (lines 417-418)."""
        result = run_inception_mode()
        assert result is False

    @patch("zerg.inception.gather_requirements", side_effect=RuntimeError("boom"))
    def test_exception_returns_false(self, mock_gather) -> None:
        """Unhandled exception during inception returns False (lines 420-423)."""
        result = run_inception_mode()
        assert result is False


# ---------------------------------------------------------------------------
# Tests for _init_git_repo (lines 428-456)
# ---------------------------------------------------------------------------


class TestInitGitRepo:
    """Tests for git repository initialization."""

    def test_git_already_exists_skips(self, tmp_path: Path, monkeypatch) -> None:
        """When .git directory exists, init is skipped (lines 428-429)."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()
        # Should not raise or call subprocess
        _init_git_repo()

    @patch("zerg.inception.subprocess.run")
    def test_git_init_success(self, mock_run, tmp_path: Path, monkeypatch) -> None:
        """Successful git init and initial commit (lines 432-451)."""
        monkeypatch.chdir(tmp_path)
        mock_run.return_value = MagicMock(returncode=0)
        _init_git_repo()
        # Should call git init, git add, git commit
        assert mock_run.call_count == 3

    @patch("zerg.inception.subprocess.run")
    def test_git_init_called_process_error(self, mock_run, tmp_path: Path, monkeypatch) -> None:
        """CalledProcessError is caught gracefully (lines 452-454)."""
        import subprocess as sp

        monkeypatch.chdir(tmp_path)
        mock_run.side_effect = sp.CalledProcessError(1, "git")
        # Should not raise
        _init_git_repo()

    @patch("zerg.inception.subprocess.run", side_effect=FileNotFoundError)
    def test_git_not_found(self, mock_run, tmp_path: Path, monkeypatch) -> None:
        """FileNotFoundError when git is missing is caught (lines 455-456)."""
        monkeypatch.chdir(tmp_path)
        _init_git_repo()


# ---------------------------------------------------------------------------
# Tests for _show_inception_summary (lines 471-489)
# ---------------------------------------------------------------------------


class TestShowInceptionSummary:
    """Tests for the inception summary display."""

    def test_summary_with_framework_and_platforms(self) -> None:
        """Summary renders table with framework and platform rows (lines 471-489)."""
        charter = _make_charter(target_platforms=["web", "api"])
        stack = _make_stack(primary_framework="fastapi")
        created = {"main.py": Path("main.py"), ".gitignore": Path(".gitignore")}

        # Should not raise
        _show_inception_summary(charter, stack, created)

    def test_summary_without_framework(self) -> None:
        """Summary renders without framework row when empty (line 480-481)."""
        charter = _make_charter(target_platforms=[])
        stack = _make_stack(primary_framework="")
        created = {}

        # Should not raise
        _show_inception_summary(charter, stack, created)

    def test_summary_with_no_platforms(self) -> None:
        """Summary skips platforms row when target_platforms is empty (line 486)."""
        charter = _make_charter(target_platforms=[])
        stack = _make_stack()
        created = {"a.py": Path("a.py")}

        _show_inception_summary(charter, stack, created)


# ---------------------------------------------------------------------------
# Tests for _resolve_if_block (direct, targeting line 265)
# ---------------------------------------------------------------------------


class TestResolveIfBlock:
    """Tests for _resolve_if_block to cover elif true return."""

    def test_elif_true_returns_elif_body(self) -> None:
        """When if is false and elif is true, the elif body is returned (line 265)."""
        # block_content is everything between {% if ... %} and {% endif %}
        block_content = "if body{% elif lang == 'rust' %}rust body{% else %}fallback"
        result = _resolve_if_block("lang == 'go'", block_content, {"lang": "rust"})
        assert "rust body" in result
        assert "if body" not in result

    def test_if_true_returns_if_body(self) -> None:
        """When if condition is true, the if body is returned."""
        block_content = "if body{% elif lang == 'rust' %}rust body{% else %}fallback"
        result = _resolve_if_block("lang == 'go'", block_content, {"lang": "go"})
        assert "if body" in result

    def test_no_elif_no_else_returns_empty(self) -> None:
        """When if is false with no elif/else, empty string returned."""
        result = _resolve_if_block("flag", "content here", {"flag": False})
        assert result == ""


# ---------------------------------------------------------------------------
# Tests for _process_conditionals (nested/complex)
# ---------------------------------------------------------------------------


class TestProcessConditionals:
    """Tests for _process_conditionals edge cases."""

    def test_no_conditionals_passthrough(self) -> None:
        """Template with no conditionals passes through unchanged."""
        template = "Just plain text"
        result = _process_conditionals(template, {})
        assert result == "Just plain text"

    def test_nested_conditionals_inner_resolved_first(self) -> None:
        """Inner if blocks are resolved before outer ones."""
        # The regex finds innermost if first, so inner resolves to "INNER",
        # then outer resolves the full block
        template = "{% if outer %}start {% if inner %}INNER{% endif %} end{% endif %}"
        result = _process_conditionals(template, {"outer": True, "inner": True})
        # Inner block resolves first; outer sees "start INNER end" then resolves
        assert "end" in result

    def test_nested_conditionals_inner_false(self) -> None:
        """Inner false if blocks are removed, outer still resolves."""
        template = "{% if outer %}start {% if inner %}HIDDEN{% endif %} end{% endif %}"
        result = _process_conditionals(template, {"outer": True, "inner": False})
        assert "HIDDEN" not in result
