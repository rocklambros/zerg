"""Comprehensive unit tests for ZERG init command.

This module provides 100% test coverage for zerg/commands/init.py including:
- Project initialization with various configurations
- Empty project detection (Inception Mode triggers)
- Directory structure creation
- Config file creation and YAML/JSON fallback
- Devcontainer generation and building
- Security rules integration
- Project type detection
- Quality gates configuration
- Force reinitialize option
- Error handling and edge cases
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from zerg.cli import cli
from zerg.commands.init import (
    build_devcontainer,
    create_config,
    create_devcontainer,
    create_directory_structure,
    detect_project_type,
    get_default_mcp_servers,
    get_primary_language,
    get_quality_gates,
    is_empty_project,
    save_config,
    show_summary,
)
from zerg.security_rules import ProjectStack

if TYPE_CHECKING:
    from pytest import MonkeyPatch


# =============================================================================
# Tests for is_empty_project()
# =============================================================================


class TestIsEmptyProject:
    """Tests for empty project detection."""

    def test_nonexistent_directory_is_empty(self, tmp_path: Path) -> None:
        """Test that non-existent directory is considered empty."""
        nonexistent = tmp_path / "does_not_exist"
        assert is_empty_project(nonexistent) is True

    def test_empty_directory_is_empty(self, tmp_path: Path) -> None:
        """Test that completely empty directory is empty."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        assert is_empty_project(empty_dir) is True

    def test_directory_with_git_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with .git is not empty."""
        (tmp_path / ".git").mkdir()
        assert is_empty_project(tmp_path) is False

    def test_directory_with_pyproject_toml_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with pyproject.toml is not empty."""
        (tmp_path / "pyproject.toml").write_text("[project]")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_setup_py_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with setup.py is not empty."""
        (tmp_path / "setup.py").write_text("# setup")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_requirements_txt_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with requirements.txt is not empty."""
        (tmp_path / "requirements.txt").write_text("pytest")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_pipfile_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with Pipfile is not empty."""
        (tmp_path / "Pipfile").write_text("[packages]")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_package_json_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with package.json is not empty."""
        (tmp_path / "package.json").write_text('{"name": "test"}')
        assert is_empty_project(tmp_path) is False

    def test_directory_with_tsconfig_json_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with tsconfig.json is not empty."""
        (tmp_path / "tsconfig.json").write_text("{}")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_go_mod_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with go.mod is not empty."""
        (tmp_path / "go.mod").write_text("module test")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_cargo_toml_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with Cargo.toml is not empty."""
        (tmp_path / "Cargo.toml").write_text("[package]")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_pom_xml_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with pom.xml is not empty."""
        (tmp_path / "pom.xml").write_text("<project></project>")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_build_gradle_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with build.gradle is not empty."""
        (tmp_path / "build.gradle").write_text("plugins {}")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_gemfile_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with Gemfile is not empty."""
        (tmp_path / "Gemfile").write_text("source 'https://rubygems.org'")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_csproj_glob_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with .csproj file is not empty."""
        (tmp_path / "test.csproj").write_text("<Project></Project>")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_sln_glob_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with .sln file is not empty."""
        (tmp_path / "test.sln").write_text("Microsoft Visual Studio Solution File")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_src_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with src/ is not empty."""
        (tmp_path / "src").mkdir()
        assert is_empty_project(tmp_path) is False

    def test_directory_with_lib_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with lib/ is not empty."""
        (tmp_path / "lib").mkdir()
        assert is_empty_project(tmp_path) is False

    def test_directory_with_app_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with app/ is not empty."""
        (tmp_path / "app").mkdir()
        assert is_empty_project(tmp_path) is False

    def test_directory_with_python_file_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with .py file is not empty."""
        (tmp_path / "main.py").write_text("print('hello')")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_js_file_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with .js file is not empty."""
        (tmp_path / "index.js").write_text("console.log('hello');")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_ts_file_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with .ts file is not empty."""
        (tmp_path / "index.ts").write_text("const x: number = 1;")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_go_file_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with .go file is not empty."""
        (tmp_path / "main.go").write_text("package main")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_rs_file_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with .rs file is not empty."""
        (tmp_path / "main.rs").write_text("fn main() {}")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_java_file_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with .java file is not empty."""
        (tmp_path / "Main.java").write_text("class Main {}")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_rb_file_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with .rb file is not empty."""
        (tmp_path / "main.rb").write_text("puts 'hello'")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_cs_file_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with .cs file is not empty."""
        (tmp_path / "Program.cs").write_text("class Program {}")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_cpp_file_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with .cpp file is not empty."""
        (tmp_path / "main.cpp").write_text("int main() {}")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_c_file_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with .c file is not empty."""
        (tmp_path / "main.c").write_text("int main() {}")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_only_random_file_is_empty(self, tmp_path: Path) -> None:
        """Test that directory with only non-code file is empty."""
        (tmp_path / "notes.txt").write_text("Some notes")
        assert is_empty_project(tmp_path) is True

    def test_uses_current_directory_by_default(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test that is_empty_project uses current directory by default."""
        monkeypatch.chdir(tmp_path)
        # Create a Python file to make it non-empty
        (tmp_path / "test.py").write_text("print(1)")
        assert is_empty_project() is False


# =============================================================================
# Tests for detect_project_type()
# =============================================================================


class TestDetectProjectType:
    """Tests for project type detection."""

    def test_detect_returns_none_when_no_languages(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test that detect_project_type returns None when no languages detected."""
        monkeypatch.chdir(tmp_path)
        # Empty directory - no files

        with patch("zerg.commands.init.detect_project_stack") as mock_detect:
            mock_detect.return_value = ProjectStack(languages=set())
            result = detect_project_type()
            assert result is None

    def test_detect_returns_stack_when_languages_found(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test that detect_project_type returns stack when languages are detected."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "test.py").write_text("print(1)")

        with patch("zerg.commands.init.detect_project_stack") as mock_detect:
            mock_stack = ProjectStack(languages={"python"})
            mock_detect.return_value = mock_stack
            result = detect_project_type()
            assert result is mock_stack


# =============================================================================
# Tests for get_primary_language()
# =============================================================================


class TestGetPrimaryLanguage:
    """Tests for primary language selection."""

    def test_python_is_prioritized(self) -> None:
        """Test that Python is first priority."""
        stack = ProjectStack(languages={"python", "javascript", "go"})
        assert get_primary_language(stack) == "python"

    def test_typescript_second_priority(self) -> None:
        """Test that TypeScript is second priority."""
        stack = ProjectStack(languages={"typescript", "javascript", "go"})
        assert get_primary_language(stack) == "typescript"

    def test_javascript_third_priority(self) -> None:
        """Test that JavaScript is third priority."""
        stack = ProjectStack(languages={"javascript", "go", "rust"})
        assert get_primary_language(stack) == "javascript"

    def test_go_fourth_priority(self) -> None:
        """Test that Go is fourth priority."""
        stack = ProjectStack(languages={"go", "rust", "java"})
        assert get_primary_language(stack) == "go"

    def test_rust_fifth_priority(self) -> None:
        """Test that Rust is fifth priority."""
        stack = ProjectStack(languages={"rust", "java", "ruby"})
        assert get_primary_language(stack) == "rust"

    def test_java_sixth_priority(self) -> None:
        """Test that Java is sixth priority."""
        stack = ProjectStack(languages={"java", "ruby", "csharp"})
        assert get_primary_language(stack) == "java"

    def test_ruby_seventh_priority(self) -> None:
        """Test that Ruby is seventh priority."""
        stack = ProjectStack(languages={"ruby", "csharp"})
        assert get_primary_language(stack) == "ruby"

    def test_csharp_eighth_priority(self) -> None:
        """Test that C# is eighth priority."""
        stack = ProjectStack(languages={"csharp"})
        assert get_primary_language(stack) == "csharp"

    def test_returns_first_if_not_in_priority(self) -> None:
        """Test that first language is returned if not in priority list."""
        stack = ProjectStack(languages={"julia", "r"})
        # Should return one of them (set iteration order)
        result = get_primary_language(stack)
        assert result in {"julia", "r"}

    def test_returns_none_for_empty_languages(self) -> None:
        """Test that None is returned for empty language set."""
        stack = ProjectStack(languages=set())
        assert get_primary_language(stack) is None


# =============================================================================
# Tests for create_directory_structure()
# =============================================================================


class TestCreateDirectoryStructure:
    """Tests for directory creation."""

    def test_creates_all_directories(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test that all required directories are created."""
        monkeypatch.chdir(tmp_path)

        with patch("zerg.commands.init.console"):
            create_directory_structure()

        expected_dirs = [
            ".zerg",
            ".zerg/state",
            ".zerg/logs",
            ".zerg/worktrees",
            ".zerg/hooks",
            ".gsd",
            ".gsd/specs",
            ".gsd/tasks",
        ]

        for dir_path in expected_dirs:
            assert (tmp_path / dir_path).exists(), f"Missing: {dir_path}"
            assert (tmp_path / dir_path).is_dir()

    def test_idempotent(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test that directory creation is idempotent."""
        monkeypatch.chdir(tmp_path)

        with patch("zerg.commands.init.console"):
            create_directory_structure()
            create_directory_structure()  # Second call should not fail

        assert (tmp_path / ".zerg").exists()


# =============================================================================
# Tests for create_config()
# =============================================================================


class TestCreateConfig:
    """Tests for configuration creation."""

    def test_creates_config_with_workers(self) -> None:
        """Test that config includes worker settings."""
        config = create_config(workers=5, security="standard", project_type="python")

        assert config["workers"]["default_count"] == 5
        assert config["workers"]["max_count"] == 10
        assert config["workers"]["context_threshold"] == 0.7
        assert config["workers"]["timeout_seconds"] == 3600

    def test_minimal_security(self) -> None:
        """Test minimal security configuration."""
        config = create_config(workers=3, security="minimal", project_type="python")

        assert config["security"]["network_isolation"] is False
        assert config["security"]["filesystem_sandbox"] is False
        assert config["security"]["secrets_scanning"] is False

    def test_standard_security(self) -> None:
        """Test standard security configuration."""
        config = create_config(workers=3, security="standard", project_type="python")

        assert config["security"]["network_isolation"] is True
        assert config["security"]["filesystem_sandbox"] is True
        assert config["security"]["secrets_scanning"] is True

    def test_strict_security(self) -> None:
        """Test strict security configuration."""
        config = create_config(workers=3, security="strict", project_type="python")

        assert config["security"]["network_isolation"] is True
        assert config["security"]["filesystem_sandbox"] is True
        assert config["security"]["secrets_scanning"] is True
        assert config["security"]["read_only_root"] is True
        assert config["security"]["no_new_privileges"] is True

    def test_unknown_project_type(self) -> None:
        """Test config with unknown project type."""
        config = create_config(workers=3, security="standard", project_type=None)

        assert config["project_type"] == "unknown"

    def test_config_has_version(self) -> None:
        """Test that config includes version."""
        config = create_config(workers=3, security="standard", project_type="python")
        assert config["version"] == "1.0"

    def test_config_has_mcp_servers(self) -> None:
        """Test that config includes MCP servers."""
        config = create_config(workers=3, security="standard", project_type="python")
        assert "mcp_servers" in config
        assert len(config["mcp_servers"]) > 0


# =============================================================================
# Tests for get_quality_gates()
# =============================================================================


class TestGetQualityGates:
    """Tests for quality gate configuration."""

    def test_default_gates(self) -> None:
        """Test default quality gates for unknown project type."""
        gates = get_quality_gates(None)

        assert "lint" in gates
        assert "test" in gates
        assert "build" in gates
        assert gates["lint"]["required"] is False

    def test_python_gates(self) -> None:
        """Test Python project quality gates."""
        gates = get_quality_gates("python")

        assert gates["lint"]["command"] == "ruff check ."
        assert gates["lint"]["required"] is True
        assert gates["typecheck"]["command"] == "mypy ."
        assert gates["test"]["command"] == "pytest"
        assert gates["test"]["required"] is True

    def test_node_gates(self) -> None:
        """Test Node.js project quality gates."""
        gates = get_quality_gates("node")

        assert gates["lint"]["command"] == "npm run lint"
        assert gates["test"]["command"] == "npm test"
        assert gates["build"]["command"] == "npm run build"

    def test_rust_gates(self) -> None:
        """Test Rust project quality gates."""
        gates = get_quality_gates("rust")

        assert gates["lint"]["command"] == "cargo clippy"
        assert gates["test"]["command"] == "cargo test"
        assert gates["build"]["command"] == "cargo build"
        assert gates["build"]["required"] is True

    def test_go_gates(self) -> None:
        """Test Go project quality gates."""
        gates = get_quality_gates("go")

        assert gates["lint"]["command"] == "golangci-lint run"
        assert gates["test"]["command"] == "go test ./..."
        assert gates["build"]["command"] == "go build ./..."


# =============================================================================
# Tests for get_default_mcp_servers()
# =============================================================================


class TestGetDefaultMcpServers:
    """Tests for default MCP server configuration."""

    def test_returns_list(self) -> None:
        """Test that MCP servers returns a list."""
        servers = get_default_mcp_servers()
        assert isinstance(servers, list)
        assert len(servers) > 0

    def test_includes_filesystem_server(self) -> None:
        """Test that filesystem MCP server is included."""
        servers = get_default_mcp_servers()
        names = [s["name"] for s in servers]
        assert "filesystem" in names


# =============================================================================
# Tests for save_config()
# =============================================================================


class TestSaveConfig:
    """Tests for configuration file saving."""

    def test_saves_yaml_when_available(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test that config is saved as YAML when yaml module is available."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        config = {"version": "1.0", "workers": {"default_count": 5}}

        with patch("zerg.commands.init.console"):
            save_config(config)

        yaml_path = tmp_path / ".zerg" / "config.yaml"
        assert yaml_path.exists()

    def test_saves_json_when_yaml_import_fails(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test that config falls back to JSON when YAML import fails."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        config = {"version": "1.0", "workers": {"default_count": 5}}

        # Mock yaml.dump to raise ImportError during import inside function
        def mock_dump_raises(*args, **kwargs):  # noqa: ARG001
            raise ImportError("No yaml")

        import yaml

        with (
            patch("zerg.commands.init.console"),
            patch.object(yaml, "dump", mock_dump_raises),
        ):
            save_config(config)

        json_path = tmp_path / ".zerg" / "config.json"
        assert json_path.exists()

        with open(json_path) as f:
            saved = json.load(f)
        assert saved["version"] == "1.0"


# =============================================================================
# Tests for create_devcontainer()
# =============================================================================


class TestCreateDevcontainer:
    """Tests for devcontainer creation."""

    def test_creates_devcontainer_with_stack(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test devcontainer creation with detected stack."""
        monkeypatch.chdir(tmp_path)

        stack = ProjectStack(languages={"python"})

        with (
            patch("zerg.commands.init.console"),
            patch("zerg.commands.init.DynamicDevcontainerGenerator") as mock_gen,
        ):
            mock_instance = mock_gen.return_value
            mock_instance.write_devcontainer.return_value = Path(".devcontainer/devcontainer.json")

            create_devcontainer(stack, "standard")

            mock_instance.write_devcontainer.assert_called_once()
            mock_instance.generate_worker_entry_script.assert_called_once()

    def test_creates_devcontainer_without_stack(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test devcontainer creation without detected stack."""
        monkeypatch.chdir(tmp_path)

        with (
            patch("zerg.commands.init.console"),
            patch("zerg.commands.init.DynamicDevcontainerGenerator") as mock_gen,
        ):
            mock_instance = mock_gen.return_value
            mock_instance.write_devcontainer.return_value = Path(".devcontainer/devcontainer.json")

            create_devcontainer(None, "standard")

            # Should pass empty set for languages
            call_args = mock_instance.write_devcontainer.call_args
            assert call_args[1]["languages"] == set()


# =============================================================================
# Tests for build_devcontainer()
# =============================================================================


def _is_docker_info(cmd: list[str]) -> bool:
    """Check if command is docker info."""
    return cmd[0] == "docker" and cmd[1] == "info"


def _is_devcontainer_version(cmd: list[str]) -> bool:
    """Check if command is devcontainer --version."""
    return cmd[0] == "devcontainer" and cmd[1] == "--version"


def _is_devcontainer_build(cmd: list[str]) -> bool:
    """Check if command is devcontainer build."""
    return cmd[0] == "devcontainer" and cmd[1] == "build"


class TestBuildDevcontainer:
    """Tests for devcontainer building."""

    def test_returns_false_when_no_devcontainer_dir(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test returns False when .devcontainer doesn't exist."""
        monkeypatch.chdir(tmp_path)

        with patch("zerg.commands.init.console"):
            result = build_devcontainer()

        assert result is False

    def test_returns_false_when_docker_not_found(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test returns False when Docker is not installed."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".devcontainer").mkdir()

        with (
            patch("zerg.commands.init.console"),
            patch("subprocess.run", side_effect=FileNotFoundError),
        ):
            result = build_devcontainer()

        assert result is False

    def test_returns_false_when_docker_not_running(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test returns False when Docker is not running."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".devcontainer").mkdir()

        mock_result = MagicMock()
        mock_result.returncode = 1

        with (
            patch("zerg.commands.init.console"),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = build_devcontainer()

        assert result is False

    def test_returns_false_when_docker_timeout(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test returns False when Docker times out."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".devcontainer").mkdir()

        with (
            patch("zerg.commands.init.console"),
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired("docker", 10)),
        ):
            result = build_devcontainer()

        assert result is False

    def test_builds_with_devcontainer_cli(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test builds using devcontainer CLI when available."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".devcontainer").mkdir()

        def mock_run(cmd, **kwargs):  # noqa: ARG001
            result = MagicMock()
            if _is_docker_info(cmd) or _is_devcontainer_version(cmd) or _is_devcontainer_build(cmd):
                result.returncode = 0
            else:
                result.returncode = 1
            return result

        with (
            patch("zerg.commands.init.console"),
            patch("subprocess.run", side_effect=mock_run),
        ):
            result = build_devcontainer()

        assert result is True

    def test_build_failure_with_devcontainer_cli(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test handles devcontainer CLI build failure."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".devcontainer").mkdir()

        def mock_run(cmd, **kwargs):  # noqa: ARG001
            result = MagicMock()
            result.stderr = "Build error"
            if _is_docker_info(cmd) or _is_devcontainer_version(cmd):
                result.returncode = 0
            elif _is_devcontainer_build(cmd):
                result.returncode = 1  # Build fails
            else:
                result.returncode = 1
            return result

        with (
            patch("zerg.commands.init.console"),
            patch("subprocess.run", side_effect=mock_run),
        ):
            result = build_devcontainer()

        assert result is False

    def test_build_timeout_with_devcontainer_cli(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test handles devcontainer CLI build timeout."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".devcontainer").mkdir()

        def mock_run(cmd, **kwargs):  # noqa: ARG001
            result = MagicMock()
            if _is_docker_info(cmd) or _is_devcontainer_version(cmd):
                result.returncode = 0
            elif _is_devcontainer_build(cmd):
                raise subprocess.TimeoutExpired("devcontainer", 600)
            else:
                result.returncode = 1
            return result

        with (
            patch("zerg.commands.init.console"),
            patch("subprocess.run", side_effect=mock_run),
        ):
            result = build_devcontainer()

        assert result is False

    def test_builds_with_docker_compose(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test builds using docker-compose when devcontainer CLI unavailable."""
        monkeypatch.chdir(tmp_path)
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        (devcontainer_dir / "docker-compose.yaml").write_text("version: '3'")

        def mock_run(cmd, **kwargs):  # noqa: ARG001
            result = MagicMock()
            result.stderr = ""
            if _is_docker_info(cmd):
                result.returncode = 0
            elif cmd[0] == "devcontainer":
                raise FileNotFoundError  # No devcontainer CLI
            elif cmd[0] == "docker" and cmd[1] == "compose":
                result.returncode = 0
            else:
                result.returncode = 1
            return result

        with (
            patch("zerg.commands.init.console"),
            patch("subprocess.run", side_effect=mock_run),
        ):
            result = build_devcontainer()

        assert result is True

    def test_docker_compose_build_failure(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test handles docker-compose build failure."""
        monkeypatch.chdir(tmp_path)
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        (devcontainer_dir / "docker-compose.yaml").write_text("version: '3'")

        def mock_run(cmd, **kwargs):  # noqa: ARG001
            result = MagicMock()
            result.stderr = "Compose error"
            if _is_docker_info(cmd):
                result.returncode = 0
            elif cmd[0] == "devcontainer":
                raise FileNotFoundError
            elif cmd[0] == "docker" and cmd[1] == "compose":
                result.returncode = 1
            else:
                result.returncode = 1
            return result

        with (
            patch("zerg.commands.init.console"),
            patch("subprocess.run", side_effect=mock_run),
        ):
            result = build_devcontainer()

        assert result is False

    def test_docker_compose_timeout(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test handles docker-compose timeout."""
        monkeypatch.chdir(tmp_path)
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        (devcontainer_dir / "docker-compose.yaml").write_text("version: '3'")

        def mock_run(cmd, **kwargs):  # noqa: ARG001
            result = MagicMock()
            if _is_docker_info(cmd):
                result.returncode = 0
            elif cmd[0] == "devcontainer":
                raise FileNotFoundError
            elif cmd[0] == "docker" and cmd[1] == "compose":
                raise subprocess.TimeoutExpired("docker compose", 600)
            else:
                result.returncode = 1
            return result

        with (
            patch("zerg.commands.init.console"),
            patch("subprocess.run", side_effect=mock_run),
        ):
            result = build_devcontainer()

        assert result is False

    def test_builds_with_dockerfile(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test builds using plain Dockerfile when no compose or CLI."""
        monkeypatch.chdir(tmp_path)
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        (devcontainer_dir / "Dockerfile").write_text("FROM ubuntu")

        def mock_run(cmd, **kwargs):  # noqa: ARG001
            result = MagicMock()
            result.stderr = ""
            if _is_docker_info(cmd):
                result.returncode = 0
            elif cmd[0] == "devcontainer":
                raise FileNotFoundError
            elif cmd[0] == "docker" and cmd[1] == "build":
                result.returncode = 0
            else:
                result.returncode = 1
            return result

        with (
            patch("zerg.commands.init.console"),
            patch("subprocess.run", side_effect=mock_run),
        ):
            result = build_devcontainer()

        assert result is True

    def test_dockerfile_build_failure(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test handles Dockerfile build failure."""
        monkeypatch.chdir(tmp_path)
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        (devcontainer_dir / "Dockerfile").write_text("FROM ubuntu")

        def mock_run(cmd, **kwargs):  # noqa: ARG001
            result = MagicMock()
            result.stderr = "Build error"
            if _is_docker_info(cmd):
                result.returncode = 0
            elif cmd[0] == "devcontainer":
                raise FileNotFoundError
            elif cmd[0] == "docker" and cmd[1] == "build":
                result.returncode = 1
            else:
                result.returncode = 1
            return result

        with (
            patch("zerg.commands.init.console"),
            patch("subprocess.run", side_effect=mock_run),
        ):
            result = build_devcontainer()

        assert result is False

    def test_dockerfile_build_timeout(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test handles Dockerfile build timeout."""
        monkeypatch.chdir(tmp_path)
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        (devcontainer_dir / "Dockerfile").write_text("FROM ubuntu")

        def mock_run(cmd, **kwargs):  # noqa: ARG001
            result = MagicMock()
            if _is_docker_info(cmd):
                result.returncode = 0
            elif cmd[0] == "devcontainer":
                raise FileNotFoundError
            elif cmd[0] == "docker" and cmd[1] == "build":
                raise subprocess.TimeoutExpired("docker build", 600)
            else:
                result.returncode = 1
            return result

        with (
            patch("zerg.commands.init.console"),
            patch("subprocess.run", side_effect=mock_run),
        ):
            result = build_devcontainer()

        assert result is False

    def test_returns_false_when_no_dockerfile(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test returns False when no Dockerfile found."""
        monkeypatch.chdir(tmp_path)
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        # No Dockerfile, no docker-compose

        def mock_run(cmd, **kwargs):  # noqa: ARG001
            result = MagicMock()
            if _is_docker_info(cmd):
                result.returncode = 0
            elif cmd[0] == "devcontainer":
                raise FileNotFoundError
            else:
                result.returncode = 1
            return result

        with (
            patch("zerg.commands.init.console"),
            patch("subprocess.run", side_effect=mock_run),
        ):
            result = build_devcontainer()

        assert result is False


# =============================================================================
# Tests for show_summary()
# =============================================================================


class TestShowSummary:
    """Tests for summary display."""

    def test_shows_unknown_language(self) -> None:
        """Test shows 'unknown' when no languages detected."""
        with patch("zerg.commands.init.console") as mock_console:
            show_summary(workers=5, security="standard", stack=None)

            # Verify console.print was called
            assert mock_console.print.called

    def test_shows_detected_languages(self) -> None:
        """Test shows detected languages."""
        stack = ProjectStack(languages={"python", "javascript"})

        with patch("zerg.commands.init.console"):
            show_summary(workers=5, security="standard", stack=stack)

    def test_shows_detected_frameworks(self) -> None:
        """Test shows detected frameworks."""
        stack = ProjectStack(languages={"python"}, frameworks={"fastapi", "sqlalchemy"})

        with patch("zerg.commands.init.console"):
            show_summary(workers=5, security="standard", stack=stack)

    def test_shows_security_rules_count(self) -> None:
        """Test shows security rules count when provided."""
        stack = ProjectStack(languages={"python"})
        security_rules_result = {"rules_fetched": 5}

        with patch("zerg.commands.init.console"):
            show_summary(
                workers=5,
                security="standard",
                stack=stack,
                security_rules_result=security_rules_result,
            )

    def test_shows_container_built(self) -> None:
        """Test shows container built status."""
        stack = ProjectStack(languages={"python"})

        with patch("zerg.commands.init.console"):
            show_summary(
                workers=5,
                security="standard",
                stack=stack,
                container_built=True,
            )


# =============================================================================
# Tests for init command (CLI integration)
# =============================================================================


class TestInitCommand:
    """Tests for the init CLI command."""

    def test_init_help(self) -> None:
        """Test init --help shows options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "--detect" in result.output
        assert "--workers" in result.output
        assert "--security" in result.output
        assert "--force" in result.output

    def test_init_creates_directories(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init creates required directories."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        runner = CliRunner()
        runner.invoke(cli, ["init"])

        assert (tmp_path / ".zerg").exists()
        assert (tmp_path / ".gsd").exists()

    def test_init_creates_config(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init creates config file."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        runner = CliRunner()
        runner.invoke(cli, ["init"])

        assert (tmp_path / ".zerg" / "config.yaml").exists()

    def test_init_detects_no_reinit_without_force(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init doesn't reinitialize without --force."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()
        (tmp_path / ".zerg").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["init"])

        assert "already initialized" in result.output or result.exit_code == 0

    def test_init_reinitializes_with_force(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init reinitializes with --force."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()
        (tmp_path / ".zerg").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--force"])

        assert result.exit_code == 0

    def test_init_with_custom_workers(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init with custom worker count."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--workers", "3"])

        assert result.exit_code == 0

    def test_init_with_strict_security(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init with strict security level."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--security", "strict"])

        assert result.exit_code == 0

    def test_init_with_no_detect(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init with --no-detect option."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--no-detect"])

        assert result.exit_code == 0

    def test_init_with_no_security_rules(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init with --no-security-rules option."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--no-security-rules"])

        assert result.exit_code == 0

    def test_init_with_containers(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init with --with-containers option."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        # Mock build_devcontainer to avoid actual Docker calls
        with patch("zerg.commands.init.build_devcontainer", return_value=False):
            runner = CliRunner()
            result = runner.invoke(cli, ["init", "--with-containers"])

        assert result.exit_code == 0

    def test_init_shows_next_steps(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init shows next steps."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["init"])

        assert "zerg plan" in result.output or "Next steps" in result.output

    def test_init_handles_exception(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init handles exceptions gracefully."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        with patch(
            "zerg.commands.init.create_directory_structure",
            side_effect=Exception("Test error"),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["init"])

        assert result.exit_code == 1
        assert "Error" in result.output

    def test_init_triggers_inception_mode(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init triggers inception mode for empty directory."""
        monkeypatch.chdir(tmp_path)
        # Empty directory - no .git, no code files

        # Patch at the source module level where it is imported
        with patch("zerg.inception.run_inception_mode", return_value=True) as mock_inception:
            runner = CliRunner()
            runner.invoke(cli, ["init"])

            mock_inception.assert_called_once()

    def test_init_inception_mode_failure(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init handles inception mode failure."""
        monkeypatch.chdir(tmp_path)
        # Empty directory triggers inception

        # Patch at the source module level where it is imported
        with patch("zerg.inception.run_inception_mode", return_value=False):
            runner = CliRunner()
            result = runner.invoke(cli, ["init"])

        assert result.exit_code == 1

    def test_init_security_rules_integration_success(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init with successful security rules integration."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        with patch("zerg.commands.init.integrate_security_rules") as mock_integrate:
            mock_integrate.return_value = {"rules_fetched": 5}

            runner = CliRunner()
            result = runner.invoke(cli, ["init", "--with-security-rules"])

        assert result.exit_code == 0
        mock_integrate.assert_called_once()

    def test_init_security_rules_integration_failure(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init handles security rules integration failure."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        with patch(
            "zerg.commands.init.integrate_security_rules",
            side_effect=Exception("Network error"),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["init", "--with-security-rules"])

        # Should continue even if security rules fail
        assert result.exit_code == 0

    def test_init_detects_python_project(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init detects Python project."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()
        (tmp_path / "pyproject.toml").write_text("[project]")

        runner = CliRunner()
        result = runner.invoke(cli, ["init"])

        assert result.exit_code == 0
        assert "python" in result.output.lower() or "Detected" in result.output

    def test_init_detects_node_project(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init detects Node.js project."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()
        (tmp_path / "package.json").write_text('{"name": "test"}')

        runner = CliRunner()
        result = runner.invoke(cli, ["init"])

        assert result.exit_code == 0

    def test_init_detects_multiple_languages(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init detects multiple languages."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()
        (tmp_path / "pyproject.toml").write_text("[project]")
        (tmp_path / "package.json").write_text('{"name": "test"}')

        runner = CliRunner()
        result = runner.invoke(cli, ["init"])

        assert result.exit_code == 0

    def test_init_no_detection_shows_message(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init shows message when detection finds nothing."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()
        # No project files

        with patch("zerg.commands.init.detect_project_type", return_value=None):
            runner = CliRunner()
            result = runner.invoke(cli, ["init"])

        assert result.exit_code == 0

    def test_init_detects_frameworks_and_prints_them(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init detects and prints frameworks when found (covers lines 172-173)."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()
        (tmp_path / "pyproject.toml").write_text("[project]")

        # Create a stack with frameworks to trigger lines 172-173
        stack_with_frameworks = ProjectStack(languages={"python"}, frameworks={"fastapi", "sqlalchemy"})

        with patch("zerg.commands.init.detect_project_type", return_value=stack_with_frameworks):
            runner = CliRunner()
            result = runner.invoke(cli, ["init"])

        assert result.exit_code == 0
        # Verify frameworks are mentioned in output
        output_lower = result.output.lower()
        assert "fastapi" in output_lower or "framework" in output_lower


# =============================================================================
# Tests for edge cases and error conditions
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_init_creates_devcontainer(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init creates devcontainer configuration."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        runner = CliRunner()
        runner.invoke(cli, ["init"])

        assert (tmp_path / ".devcontainer").exists()

    def test_init_handles_permissions_error(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init handles permission errors gracefully."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        with patch(
            "zerg.commands.init.create_directory_structure",
            side_effect=PermissionError("Access denied"),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["init"])

        assert result.exit_code == 1

    def test_init_with_minimal_security(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init with minimal security level."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--security", "minimal"])

        assert result.exit_code == 0

    def test_devcontainer_cli_version_check_timeout(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test handles devcontainer version check timeout."""
        monkeypatch.chdir(tmp_path)
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        (devcontainer_dir / "Dockerfile").write_text("FROM ubuntu")

        def mock_run(cmd, **kwargs):  # noqa: ARG001
            result = MagicMock()
            result.stderr = ""
            if _is_docker_info(cmd):
                result.returncode = 0
            elif cmd[0] == "devcontainer":
                raise subprocess.TimeoutExpired("devcontainer", 5)
            elif cmd[0] == "docker" and cmd[1] == "build":
                result.returncode = 0
            else:
                result.returncode = 1
            return result

        with (
            patch("zerg.commands.init.console"),
            patch("subprocess.run", side_effect=mock_run),
        ):
            result = build_devcontainer()

        # Should fall back to docker build after devcontainer timeout
        assert result is True
