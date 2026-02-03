"""Unit tests for is_empty_project() detection function."""

from pathlib import Path

from zerg.commands.init import is_empty_project


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
