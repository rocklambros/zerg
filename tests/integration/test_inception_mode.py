"""Integration tests for Inception Mode - full workflow testing."""

from pathlib import Path
from unittest.mock import patch

from zerg.charter import ProjectCharter
from zerg.commands.init import is_empty_project
from zerg.inception import run_inception_mode, scaffold_project
from zerg.tech_selector import TechStack


class TestInceptionModeIntegration:
    """Integration tests for complete Inception Mode workflow."""

    @patch("zerg.inception.gather_requirements")
    @patch("zerg.inception.select_technology")
    def test_full_workflow_creates_project(
        self,
        mock_select: patch,
        mock_gather: patch,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """Test that full inception workflow creates a project."""
        monkeypatch.chdir(tmp_path)

        # Mock the interactive functions
        mock_gather.return_value = ProjectCharter(
            name="test-api",
            description="A test API project",
            target_platforms=["api"],
            security_level="standard",
        )
        mock_select.return_value = TechStack(
            language="python",
            language_version="3.12",
            package_manager="uv",
            primary_framework="fastapi",
            test_framework="pytest",
            linter="ruff",
            formatter="ruff",
            type_checker="mypy",
        )

        # Run inception
        result = run_inception_mode(security_level="standard")

        # Verify success
        assert result is True

        # Verify files created
        assert (tmp_path / "pyproject.toml").exists()
        assert (tmp_path / ".gsd" / "PROJECT.md").exists()
        assert (tmp_path / "test_api" / "main.py").exists()
        assert (tmp_path / "tests").exists()

    @patch("zerg.inception.gather_requirements")
    @patch("zerg.inception.select_technology")
    def test_inception_initializes_git(
        self,
        mock_select: patch,
        mock_gather: patch,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """Test that inception initializes git repository."""
        monkeypatch.chdir(tmp_path)

        mock_gather.return_value = ProjectCharter(
            name="git-test",
            description="Test git init",
        )
        mock_select.return_value = TechStack(
            language="python",
            language_version="3.12",
        )

        run_inception_mode()

        # Verify git initialized
        assert (tmp_path / ".git").exists()

    @patch("zerg.inception.gather_requirements")
    @patch("zerg.inception.select_technology")
    def test_inception_creates_project_md(
        self,
        mock_select: patch,
        mock_gather: patch,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """Test that inception creates PROJECT.md."""
        monkeypatch.chdir(tmp_path)

        mock_gather.return_value = ProjectCharter(
            name="doc-test",
            description="Testing documentation",
            primary_language="go",
        )
        mock_select.return_value = TechStack(
            language="go",
            language_version="1.22",
        )

        run_inception_mode()

        project_md = tmp_path / ".gsd" / "PROJECT.md"
        assert project_md.exists()

        content = project_md.read_text()
        assert "doc-test" in content
        assert "Testing documentation" in content


class TestEmptyProjectDetectionIntegration:
    """Integration tests for empty project detection with init flow."""

    def test_empty_dir_triggers_inception(self, tmp_path: Path) -> None:
        """Test that empty directory is detected correctly."""
        assert is_empty_project(tmp_path) is True

    def test_project_with_code_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with code is not empty."""
        (tmp_path / "main.py").write_text("print('hello')")
        assert is_empty_project(tmp_path) is False

    def test_project_with_package_json_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with package.json is not empty."""
        (tmp_path / "package.json").write_text('{"name": "test"}')
        assert is_empty_project(tmp_path) is False


class TestScaffoldIntegration:
    """Integration tests for scaffold generation."""

    def test_python_api_scaffold_complete(self, tmp_path: Path) -> None:
        """Test that Python API scaffold is complete and valid."""
        charter = ProjectCharter(
            name="python-api",
            description="A Python API project",
        )
        stack = TechStack(
            language="python",
            language_version="3.12",
            package_manager="uv",
            primary_framework="fastapi",
            test_framework="pytest",
            linter="ruff",
            formatter="ruff",
            type_checker="mypy",
        )

        files = scaffold_project(charter, stack, tmp_path)

        # Verify key files exist
        assert "pyproject.toml" in files
        assert ".gitignore" in files
        assert "README.md" in files

        # Verify pyproject.toml is valid
        pyproject = tmp_path / "pyproject.toml"
        content = pyproject.read_text()
        assert "[project]" in content
        assert "python-api" in content
        assert "fastapi" in content

    def test_python_cli_scaffold_complete(self, tmp_path: Path) -> None:
        """Test that Python CLI scaffold is complete."""
        charter = ProjectCharter(
            name="my-cli",
            description="A CLI tool",
        )
        stack = TechStack(
            language="python",
            language_version="3.12",
            package_manager="uv",
            primary_framework="typer",
            test_framework="pytest",
            linter="ruff",
        )

        scaffold_project(charter, stack, tmp_path)

        # Verify CLI-specific content
        pyproject = tmp_path / "pyproject.toml"
        content = pyproject.read_text()
        assert "typer" in content

        # Verify main.py has CLI structure
        main_py = tmp_path / "my_cli" / "main.py"
        if main_py.exists():
            main_content = main_py.read_text()
            assert "typer" in main_content or "app" in main_content

    def test_typescript_scaffold_complete(self, tmp_path: Path) -> None:
        """Test that TypeScript scaffold is complete."""
        charter = ProjectCharter(
            name="ts-api",
            description="A TypeScript API",
        )
        stack = TechStack(
            language="typescript",
            language_version="5.x",
            package_manager="pnpm",
            primary_framework="fastify",
            test_framework="vitest",
        )

        files = scaffold_project(charter, stack, tmp_path)

        # Verify TypeScript files
        assert "package.json" in files
        assert "tsconfig.json" in files

        # Verify package.json content
        package_json = tmp_path / "package.json"
        content = package_json.read_text()
        assert '"name"' in content
        assert "ts-api" in content or "tsapi" in content.lower()

    def test_go_scaffold_complete(self, tmp_path: Path) -> None:
        """Test that Go scaffold is complete."""
        charter = ProjectCharter(
            name="go-api",
            description="A Go API",
        )
        stack = TechStack(
            language="go",
            language_version="1.22",
            package_manager="go mod",
            primary_framework="gin",
            test_framework="go test",
        )

        files = scaffold_project(charter, stack, tmp_path)

        # Verify Go files
        assert "go.mod" in files
        assert "main.go" in files

    def test_rust_scaffold_complete(self, tmp_path: Path) -> None:
        """Test that Rust scaffold is complete."""
        charter = ProjectCharter(
            name="rust-api",
            description="A Rust API",
        )
        stack = TechStack(
            language="rust",
            language_version="stable",
            package_manager="cargo",
            primary_framework="axum",
            test_framework="cargo test",
        )

        files = scaffold_project(charter, stack, tmp_path)

        # Verify Rust files
        assert "Cargo.toml" in files

        # Verify Cargo.toml content
        cargo_toml = tmp_path / "Cargo.toml"
        content = cargo_toml.read_text()
        assert "rust_api" in content or "rust-api" in content


class TestInceptionHandlesErrors:
    """Tests for error handling in inception mode."""

    @patch("zerg.inception.gather_requirements")
    def test_handles_keyboard_interrupt(
        self,
        mock_gather: patch,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """Test that KeyboardInterrupt is handled gracefully."""
        monkeypatch.chdir(tmp_path)
        mock_gather.side_effect = KeyboardInterrupt()

        result = run_inception_mode()

        assert result is False

    @patch("zerg.inception.gather_requirements")
    def test_handles_general_exception(
        self,
        mock_gather: patch,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """Test that general exceptions are handled."""
        monkeypatch.chdir(tmp_path)
        mock_gather.side_effect = Exception("Test error")

        result = run_inception_mode()

        assert result is False
