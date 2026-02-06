"""Unit tests for ZERG build command — thinned Phase 4/5."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from zerg.command_executor import CommandValidationError
from zerg.commands.build import (
    BuildCommand,
    BuildConfig,
    BuildDetector,
    BuildResult,
    BuildRunner,
    BuildSystem,
    ErrorCategory,
    ErrorRecovery,
    _watch_loop,
    build,
)


class TestBuildSystem:
    def test_all_build_systems(self) -> None:
        assert {bs.value for bs in BuildSystem} == {"npm", "cargo", "make", "gradle", "go", "python"}


class TestErrorCategory:
    def test_all_error_categories(self) -> None:
        assert {ec.value for ec in ErrorCategory} == {
            "missing_dependency",
            "type_error",
            "resource_exhaustion",
            "network_timeout",
            "syntax_error",
            "unknown",
        }


class TestBuildConfig:
    def test_default_values(self) -> None:
        config = BuildConfig()
        assert config.mode == "dev"
        assert config.clean is False
        assert config.retry == 3


class TestBuildResult:
    def test_to_dict(self) -> None:
        d = BuildResult(
            success=True, duration_seconds=2.5, artifacts=["build/app"], warnings=["w"], retries=1
        ).to_dict()
        assert d["success"] is True and d["retries"] == 1


class TestBuildDetector:
    @pytest.mark.parametrize(
        "filename,expected_system",
        [
            ("package.json", BuildSystem.NPM),
            ("Cargo.toml", BuildSystem.CARGO),
            ("Makefile", BuildSystem.MAKE),
            ("pyproject.toml", BuildSystem.PYTHON),
        ],
    )
    def test_detect_project_by_file(self, tmp_path: Path, filename: str, expected_system: BuildSystem) -> None:
        (tmp_path / filename).write_text("{}" if filename.endswith(".json") else "")
        assert expected_system in BuildDetector().detect(tmp_path)

    def test_detect_no_build_system(self, tmp_path: Path) -> None:
        assert BuildDetector().detect(tmp_path) == []


class TestErrorRecovery:
    @pytest.mark.parametrize(
        "error_msg,expected_category",
        [
            ("ModuleNotFoundError: No module named 'foo'", ErrorCategory.MISSING_DEPENDENCY),
            ("TypeError: expected str, got int", ErrorCategory.TYPE_ERROR),
            ("JavaScript heap out of memory", ErrorCategory.RESOURCE_EXHAUSTION),
            ("SyntaxError: invalid syntax", ErrorCategory.SYNTAX_ERROR),
            ("Something unexpected", ErrorCategory.UNKNOWN),
        ],
    )
    def test_classify_error(self, error_msg: str, expected_category: ErrorCategory) -> None:
        assert ErrorRecovery().classify(error_msg) == expected_category


class TestBuildRunner:
    @pytest.mark.parametrize(
        "system,mode,expected_cmd",
        [
            (BuildSystem.NPM, "dev", "npm run dev"),
            (BuildSystem.NPM, "prod", "npm run build"),
            (BuildSystem.PYTHON, "dev", "pip install -e ."),
        ],
    )
    def test_get_command(self, system: BuildSystem, mode: str, expected_cmd: str) -> None:
        assert BuildRunner().get_command(system, mode) == expected_cmd

    @patch("zerg.commands.build.CommandExecutor")
    def test_run_successful_build(self, mock_executor_class: MagicMock) -> None:
        mock_executor = MagicMock()
        mock_result = MagicMock(success=True)
        mock_executor.execute.return_value = mock_result
        mock_executor_class.return_value = mock_executor
        assert BuildRunner().run(BuildSystem.PYTHON, BuildConfig(mode="dev"), ".").success is True

    @patch("zerg.commands.build.CommandExecutor")
    def test_run_command_validation_error(self, mock_executor_class: MagicMock) -> None:
        mock_executor = MagicMock()
        mock_executor.execute.side_effect = CommandValidationError("Invalid command")
        mock_executor_class.return_value = mock_executor
        result = BuildRunner().run(BuildSystem.PYTHON, BuildConfig(mode="dev"), ".")
        assert result.success is False


class TestBuildCommand:
    def test_init_default_config(self) -> None:
        builder = BuildCommand()
        assert builder.config.mode == "dev"

    @patch.object(BuildRunner, "run")
    def test_run_with_retries_on_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = BuildResult(success=False, duration_seconds=0.5, artifacts=[], errors=["Failed"])
        config = BuildConfig(retry=3)
        result = BuildCommand(config).run(system=BuildSystem.MAKE, cwd=str(tmp_path))
        assert result.success is False and result.retries == 3

    def test_format_result_json(self) -> None:
        builder = BuildCommand()
        result = BuildResult(success=True, duration_seconds=1.5, artifacts=["dist/app.js"], retries=0)
        assert json.loads(builder.format_result(result, fmt="json"))["success"] is True


class TestWatchLoop:
    @patch("zerg.commands.build.time.sleep")
    @patch("zerg.commands.build.console")
    def test_watch_loop_detects_changes(self, mock_console: MagicMock, mock_sleep: MagicMock, tmp_path: Path) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text("initial")
        mock_builder = MagicMock()
        mock_builder.run.return_value = BuildResult(success=True, duration_seconds=1.0, artifacts=[])
        call_count = [0]

        def sleep_side_effect(duration: float) -> None:
            call_count[0] += 1
            if call_count[0] == 1:
                test_file.write_text("modified")
            elif call_count[0] >= 3:
                raise KeyboardInterrupt

        mock_sleep.side_effect = sleep_side_effect
        _watch_loop(mock_builder, BuildSystem.PYTHON, str(tmp_path))
        mock_builder.run.assert_called()


class TestBuildCLI:
    def test_build_help(self) -> None:
        assert CliRunner().invoke(build, ["--help"]).exit_code == 0

    @patch("zerg.commands.build.BuildCommand")
    @patch("zerg.commands.build.console")
    def test_build_keyboard_interrupt(self, mock_console: MagicMock, mock_builder_class: MagicMock) -> None:
        mock_builder_class.side_effect = KeyboardInterrupt
        assert CliRunner().invoke(build, []).exit_code == 130
