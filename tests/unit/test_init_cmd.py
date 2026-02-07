"""Unit tests for ZERG init command - thinned per TSR2-L3-002."""

from __future__ import annotations

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

    def test_directory_with_package_json_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with package.json is not empty."""
        (tmp_path / "package.json").write_text('{"name": "test"}')
        assert is_empty_project(tmp_path) is False

    def test_directory_with_python_file_is_not_empty(self, tmp_path: Path) -> None:
        """Test that directory with .py file is not empty."""
        (tmp_path / "main.py").write_text("print('hello')")
        assert is_empty_project(tmp_path) is False

    def test_directory_with_only_random_file_is_empty(self, tmp_path: Path) -> None:
        """Test that directory with only non-code file is empty."""
        (tmp_path / "notes.txt").write_text("Some notes")
        assert is_empty_project(tmp_path) is True


class TestDetectProjectType:
    """Tests for project type detection."""

    def test_detect_returns_none_when_no_languages(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test that detect_project_type returns None when no languages detected."""
        monkeypatch.chdir(tmp_path)
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


class TestGetPrimaryLanguage:
    """Tests for primary language selection."""

    def test_python_is_prioritized(self) -> None:
        """Test that Python is first priority."""
        stack = ProjectStack(languages={"python", "javascript", "go"})
        assert get_primary_language(stack) == "python"

    def test_returns_first_if_not_in_priority(self) -> None:
        """Test that first language is returned if not in priority list."""
        stack = ProjectStack(languages={"julia", "r"})
        result = get_primary_language(stack)
        assert result in {"julia", "r"}

    def test_returns_none_for_empty_languages(self) -> None:
        """Test that None is returned for empty language set."""
        stack = ProjectStack(languages=set())
        assert get_primary_language(stack) is None


class TestCreateDirectoryStructure:
    """Tests for directory creation."""

    def test_creates_all_directories(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test that all required directories are created."""
        monkeypatch.chdir(tmp_path)
        with patch("zerg.commands.init.console"):
            create_directory_structure()

        expected_dirs = [".zerg", ".zerg/state", ".zerg/logs", ".gsd", ".gsd/specs"]
        for dir_path in expected_dirs:
            assert (tmp_path / dir_path).exists(), f"Missing: {dir_path}"


class TestCreateConfig:
    """Tests for configuration creation."""

    def test_creates_config_with_workers(self) -> None:
        """Test that config includes worker settings."""
        config = create_config(workers=5, security="standard", project_type="python")
        assert config["workers"]["default_count"] == 5

    def test_minimal_security(self) -> None:
        """Test minimal security configuration."""
        config = create_config(workers=3, security="minimal", project_type="python")
        assert config["security"]["network_isolation"] is False

    def test_strict_security(self) -> None:
        """Test strict security configuration."""
        config = create_config(workers=3, security="strict", project_type="python")
        assert config["security"]["read_only_root"] is True
        assert config["security"]["no_new_privileges"] is True


class TestGetQualityGates:
    """Tests for quality gate configuration."""

    def test_default_gates(self) -> None:
        """Test default quality gates for unknown project type."""
        gates = get_quality_gates(None)
        assert "lint" in gates
        assert "test" in gates

    def test_python_gates(self) -> None:
        """Test Python project quality gates."""
        gates = get_quality_gates("python")
        assert gates["lint"]["command"] == "ruff check ."
        assert gates["test"]["command"] == "pytest"


class TestGetDefaultMcpServers:
    """Tests for default MCP server configuration."""

    def test_returns_list(self) -> None:
        """Test that MCP servers returns a list."""
        servers = get_default_mcp_servers()
        assert isinstance(servers, list)
        assert len(servers) > 0


class TestSaveConfig:
    """Tests for configuration file saving."""

    def test_saves_yaml_when_available(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test that config is saved as YAML when yaml module is available."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()
        config = {"version": "1.0", "workers": {"default_count": 5}}
        with patch("zerg.commands.init.console"):
            save_config(config)
        assert (tmp_path / ".zerg" / "config.yaml").exists()

    def test_saves_json_when_yaml_import_fails(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test that config falls back to JSON when YAML import fails."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()
        config = {"version": "1.0", "workers": {"default_count": 5}}

        def mock_dump_raises(*args, **kwargs):
            raise ImportError("No yaml")

        import yaml

        with (
            patch("zerg.commands.init.console"),
            patch.object(yaml, "dump", mock_dump_raises),
        ):
            save_config(config)

        json_path = tmp_path / ".zerg" / "config.json"
        assert json_path.exists()


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

    def test_builds_with_devcontainer_cli(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test builds using devcontainer CLI when available."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".devcontainer").mkdir()

        def mock_run(cmd, **kwargs):
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

        def mock_run(cmd, **kwargs):
            result = MagicMock()
            result.stderr = "Build error"
            if _is_docker_info(cmd) or _is_devcontainer_version(cmd):
                result.returncode = 0
            elif _is_devcontainer_build(cmd):
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


class TestShowSummary:
    """Tests for summary display."""

    def test_shows_unknown_language(self) -> None:
        """Test shows 'unknown' when no languages detected."""
        with patch("zerg.commands.init.console") as mock_console:
            show_summary(workers=5, security="standard", stack=None)
            assert mock_console.print.called


class TestInitCommand:
    """Tests for the init CLI command."""

    def test_init_help(self) -> None:
        """Test init --help shows options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--help"])
        assert result.exit_code == 0
        assert "--workers" in result.output

    def test_init_creates_directories(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init creates required directories."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()
        runner = CliRunner()
        runner.invoke(cli, ["init"])
        assert (tmp_path / ".zerg").exists()
        assert (tmp_path / ".gsd").exists()

    def test_init_reinitializes_with_force(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init reinitializes with --force."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()
        (tmp_path / ".zerg").mkdir()
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--force"])
        assert result.exit_code == 0

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

    def test_init_triggers_inception_mode(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init triggers inception mode for empty directory."""
        monkeypatch.chdir(tmp_path)
        with patch("zerg.inception.run_inception_mode", return_value=True) as mock_inception:
            runner = CliRunner()
            runner.invoke(cli, ["init"])
            mock_inception.assert_called_once()

    def test_init_security_rules_integration_success(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init with successful security rules integration."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()
        with patch("zerg.commands.init.integrate_security_rules") as mock_integrate:
            mock_integrate.return_value = {"rules_fetched": 5}
            runner = CliRunner()
            result = runner.invoke(cli, ["init", "--with-security-rules"])
        assert result.exit_code == 0

    def test_init_security_rules_integration_failure(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test init handles security rules integration failure."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()
        with patch(
            "zerg.commands.init.integrate_security_rules",
            side_effect=RuntimeError("Network error"),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["init", "--with-security-rules"])
        assert result.exit_code == 0
