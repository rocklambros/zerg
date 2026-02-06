"""Unit tests for ZERG build command - thinned per TSR2-L3-002."""

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
    """Tests for BuildSystem enum."""

    def test_all_build_systems_have_values(self) -> None:
        """Test that all build systems have string values."""
        expected = {"npm", "cargo", "make", "gradle", "go", "python"}
        actual = {bs.value for bs in BuildSystem}
        assert actual == expected


class TestErrorCategory:
    """Tests for ErrorCategory enum."""

    def test_all_error_categories(self) -> None:
        """Test all error categories exist."""
        expected = {
            "missing_dependency",
            "type_error",
            "resource_exhaustion",
            "network_timeout",
            "syntax_error",
            "unknown",
        }
        actual = {ec.value for ec in ErrorCategory}
        assert actual == expected


class TestBuildConfig:
    """Tests for BuildConfig dataclass."""

    def test_default_values(self) -> None:
        """Test BuildConfig default values."""
        config = BuildConfig()
        assert config.mode == "dev"
        assert config.clean is False
        assert config.watch is False
        assert config.retry == 3
        assert config.target == "all"

    def test_custom_values(self) -> None:
        """Test BuildConfig with custom values."""
        config = BuildConfig(
            mode="prod",
            clean=True,
            watch=True,
            retry=5,
            target="frontend",
        )
        assert config.mode == "prod"
        assert config.clean is True
        assert config.watch is True
        assert config.retry == 5
        assert config.target == "frontend"


class TestBuildResult:
    """Tests for BuildResult dataclass."""

    def test_successful_result(self) -> None:
        """Test successful BuildResult."""
        result = BuildResult(
            success=True,
            duration_seconds=1.5,
            artifacts=["dist/app.js"],
        )
        assert result.success is True
        assert result.duration_seconds == 1.5
        assert result.artifacts == ["dist/app.js"]
        assert result.errors == []
        assert result.warnings == []
        assert result.retries == 0

    def test_to_dict(self) -> None:
        """Test BuildResult.to_dict method."""
        result = BuildResult(
            success=True,
            duration_seconds=2.5,
            artifacts=["build/app"],
            errors=[],
            warnings=["warning1"],
            retries=1,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["duration_seconds"] == 2.5
        assert d["artifacts"] == ["build/app"]
        assert d["retries"] == 1


class TestBuildDetector:
    """Tests for BuildDetector class."""

    @pytest.mark.parametrize(
        "filename,expected_system",
        [
            ("package.json", BuildSystem.NPM),
            ("Cargo.toml", BuildSystem.CARGO),
            ("Makefile", BuildSystem.MAKE),
            ("build.gradle", BuildSystem.GRADLE),
            ("go.mod", BuildSystem.GO),
            ("pyproject.toml", BuildSystem.PYTHON),
        ],
    )
    def test_detect_project_by_file(self, tmp_path: Path, filename: str, expected_system: BuildSystem) -> None:
        """Test detection of project by marker file."""
        (tmp_path / filename).write_text("{}" if filename.endswith(".json") else "")
        detector = BuildDetector()
        detected = detector.detect(tmp_path)
        assert expected_system in detected

    def test_detect_no_build_system(self, tmp_path: Path) -> None:
        """Test detection with no build system."""
        detector = BuildDetector()
        detected = detector.detect(tmp_path)
        assert detected == []

    def test_detect_multiple_build_systems(self, tmp_path: Path) -> None:
        """Test detection of multiple build systems."""
        (tmp_path / "package.json").write_text("{}")
        (tmp_path / "pyproject.toml").write_text("")
        detector = BuildDetector()
        detected = detector.detect(tmp_path)
        assert BuildSystem.NPM in detected
        assert BuildSystem.PYTHON in detected


class TestErrorRecovery:
    """Tests for ErrorRecovery class."""

    @pytest.mark.parametrize(
        "error_msg,expected_category",
        [
            ("ModuleNotFoundError: No module named 'foo'", ErrorCategory.MISSING_DEPENDENCY),
            ("TypeError: expected str, got int", ErrorCategory.TYPE_ERROR),
            ("JavaScript heap out of memory", ErrorCategory.RESOURCE_EXHAUSTION),
            ("Request timeout after 30000ms", ErrorCategory.NETWORK_TIMEOUT),
            ("SyntaxError: invalid syntax", ErrorCategory.SYNTAX_ERROR),
            ("Something completely unexpected happened", ErrorCategory.UNKNOWN),
        ],
    )
    def test_classify_error(self, error_msg: str, expected_category: ErrorCategory) -> None:
        """Test classification of various error types."""
        recovery = ErrorRecovery()
        category = recovery.classify(error_msg)
        assert category == expected_category

    @pytest.mark.parametrize(
        "category,expected_action",
        [
            (ErrorCategory.MISSING_DEPENDENCY, "Install missing dependencies"),
            (ErrorCategory.TYPE_ERROR, "Fix type errors"),
            (ErrorCategory.RESOURCE_EXHAUSTION, "Reduce parallelism"),
            (ErrorCategory.NETWORK_TIMEOUT, "Retry with backoff"),
            (ErrorCategory.SYNTAX_ERROR, "Fix syntax errors"),
            (ErrorCategory.UNKNOWN, "Review error manually"),
        ],
    )
    def test_get_recovery_action(self, category: ErrorCategory, expected_action: str) -> None:
        """Test recovery action for each category."""
        recovery = ErrorRecovery()
        action = recovery.get_recovery_action(category)
        assert action == expected_action


class TestBuildRunner:
    """Tests for BuildRunner class."""

    @pytest.mark.parametrize(
        "system,mode,expected_cmd",
        [
            (BuildSystem.NPM, "dev", "npm run dev"),
            (BuildSystem.NPM, "prod", "npm run build"),
            (BuildSystem.CARGO, "dev", "cargo build"),
            (BuildSystem.CARGO, "prod", "cargo build --release"),
            (BuildSystem.PYTHON, "dev", "pip install -e ."),
            (BuildSystem.PYTHON, "prod", "python -m build"),
        ],
    )
    def test_get_command(self, system: BuildSystem, mode: str, expected_cmd: str) -> None:
        """Test build commands for various systems and modes."""
        runner = BuildRunner()
        cmd = runner.get_command(system, mode)
        assert cmd == expected_cmd

    @patch("zerg.commands.build.CommandExecutor")
    def test_run_successful_build(self, mock_executor_class: MagicMock) -> None:
        """Test successful build execution."""
        mock_executor = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_executor.execute.return_value = mock_result
        mock_executor_class.return_value = mock_executor

        runner = BuildRunner()
        config = BuildConfig(mode="dev")
        result = runner.run(BuildSystem.PYTHON, config, ".")
        assert result.success is True

    @patch("zerg.commands.build.CommandExecutor")
    def test_run_failed_build_with_stderr(self, mock_executor_class: MagicMock) -> None:
        """Test failed build with stderr output."""
        mock_executor = MagicMock()
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.stderr = "Build error occurred"
        mock_result.stdout = ""
        mock_executor.execute.return_value = mock_result
        mock_executor_class.return_value = mock_executor

        runner = BuildRunner()
        config = BuildConfig(mode="dev")
        result = runner.run(BuildSystem.PYTHON, config, ".")
        assert result.success is False
        assert "Build error occurred" in result.errors

    @patch("zerg.commands.build.CommandExecutor")
    def test_run_command_validation_error(self, mock_executor_class: MagicMock) -> None:
        """Test build with CommandValidationError."""
        mock_executor = MagicMock()
        mock_executor.execute.side_effect = CommandValidationError("Invalid command")
        mock_executor_class.return_value = mock_executor

        runner = BuildRunner()
        config = BuildConfig(mode="dev")
        result = runner.run(BuildSystem.PYTHON, config, ".")
        assert result.success is False
        assert "Command validation failed" in result.errors[0]


class TestBuildCommand:
    """Tests for BuildCommand class."""

    def test_init_default_config(self) -> None:
        """Test BuildCommand initialization with default config."""
        builder = BuildCommand()
        assert builder.config.mode == "dev"
        assert builder.config.retry == 3

    def test_supported_systems(self) -> None:
        """Test supported_systems method."""
        builder = BuildCommand()
        systems = builder.supported_systems()
        assert "npm" in systems
        assert "python" in systems

    @patch.object(BuildRunner, "run")
    def test_run_with_retries_on_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test run retries on failure."""
        mock_run.return_value = BuildResult(
            success=False,
            duration_seconds=0.5,
            artifacts=[],
            errors=["Build failed"],
        )

        config = BuildConfig(retry=3)
        builder = BuildCommand(config)
        result = builder.run(system=BuildSystem.MAKE, cwd=str(tmp_path))
        assert result.success is False
        assert result.retries == 3
        assert mock_run.call_count == 3

    @patch.object(BuildRunner, "run")
    def test_run_success_on_retry(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test run succeeds on retry."""
        mock_run.side_effect = [
            BuildResult(success=False, duration_seconds=0.5, artifacts=[], errors=["Failed"]),
            BuildResult(success=True, duration_seconds=1.0, artifacts=[]),
        ]

        config = BuildConfig(retry=3)
        builder = BuildCommand(config)
        result = builder.run(system=BuildSystem.MAKE, cwd=str(tmp_path))
        assert result.success is True
        assert result.retries == 1

    def test_format_result_json(self) -> None:
        """Test format_result with JSON output."""
        builder = BuildCommand()
        result = BuildResult(
            success=True,
            duration_seconds=1.5,
            artifacts=["dist/app.js"],
            retries=0,
        )
        output = builder.format_result(result, fmt="json")
        parsed = json.loads(output)
        assert parsed["success"] is True

    def test_format_result_text_success(self) -> None:
        """Test format_result with text output for success."""
        builder = BuildCommand()
        result = BuildResult(
            success=True,
            duration_seconds=1.5,
            artifacts=["dist/app.js", "dist/app.css"],
            retries=0,
        )
        output = builder.format_result(result, fmt="text")
        assert "SUCCESS" in output

    def test_format_result_text_failure(self) -> None:
        """Test format_result with text output for failure."""
        builder = BuildCommand()
        result = BuildResult(
            success=False,
            duration_seconds=0.5,
            artifacts=[],
            errors=["Error 1", "Error 2"],
            retries=2,
        )
        output = builder.format_result(result, fmt="text")
        assert "FAILED" in output
        assert "Retries: 2" in output


class TestWatchLoop:
    """Tests for _watch_loop function."""

    @patch("zerg.commands.build.time.sleep")
    @patch("zerg.commands.build.console")
    def test_watch_loop_detects_changes(self, mock_console: MagicMock, mock_sleep: MagicMock, tmp_path: Path) -> None:
        """Test watch loop detects file changes."""
        test_file = tmp_path / "test.py"
        test_file.write_text("initial content")

        mock_builder = MagicMock()
        mock_builder.run.return_value = BuildResult(success=True, duration_seconds=1.0, artifacts=[])

        call_count = [0]

        def sleep_side_effect(duration: float) -> None:
            call_count[0] += 1
            if call_count[0] == 1:
                test_file.write_text("modified content")
            elif call_count[0] >= 3:
                raise KeyboardInterrupt

        mock_sleep.side_effect = sleep_side_effect
        _watch_loop(mock_builder, BuildSystem.PYTHON, str(tmp_path))
        mock_builder.run.assert_called()

    @patch("zerg.commands.build.time.sleep")
    @patch("zerg.commands.build.console")
    def test_watch_loop_no_changes(self, mock_console: MagicMock, mock_sleep: MagicMock, tmp_path: Path) -> None:
        """Test watch loop does nothing without changes."""
        test_file = tmp_path / "test.py"
        test_file.write_text("content")

        mock_builder = MagicMock()

        call_count = [0]

        def sleep_side_effect(duration: float) -> None:
            call_count[0] += 1
            if call_count[0] >= 3:
                raise KeyboardInterrupt

        mock_sleep.side_effect = sleep_side_effect
        _watch_loop(mock_builder, BuildSystem.PYTHON, str(tmp_path))
        mock_builder.run.assert_not_called()


class TestBuildCLI:
    """Tests for build CLI command."""

    def test_build_help(self) -> None:
        """Test build --help."""
        runner = CliRunner()
        result = runner.invoke(build, ["--help"])
        assert result.exit_code == 0
        assert "mode" in result.output

    @patch("zerg.commands.build.BuildCommand")
    @patch("zerg.commands.build.console")
    def test_build_dry_run(self, mock_console: MagicMock, mock_builder_class: MagicMock) -> None:
        """Test build --dry-run."""
        mock_builder = MagicMock()
        mock_builder.detector.detect.return_value = [BuildSystem.PYTHON]
        mock_builder.run.return_value = BuildResult(
            success=True,
            duration_seconds=0.0,
            artifacts=[],
            warnings=["Dry run: would build with python"],
        )
        mock_builder_class.return_value = mock_builder

        runner = CliRunner()
        result = runner.invoke(build, ["--dry-run"])
        assert result.exit_code == 0

    @patch("zerg.commands.build.BuildCommand")
    @patch("zerg.commands.build.console")
    def test_build_failure_shows_recovery(self, mock_console: MagicMock, mock_builder_class: MagicMock) -> None:
        """Test build failure shows recovery suggestion."""
        mock_builder = MagicMock()
        mock_builder.detector.detect.return_value = [BuildSystem.NPM]
        mock_builder.run.return_value = BuildResult(
            success=False,
            duration_seconds=0.5,
            artifacts=[],
            errors=["ModuleNotFoundError: No module named 'foo'"],
            retries=3,
        )
        mock_builder_class.return_value = mock_builder

        runner = CliRunner()
        result = runner.invoke(build, [])
        assert result.exit_code == 1

    @patch("zerg.commands.build.BuildCommand")
    @patch("zerg.commands.build.console")
    def test_build_keyboard_interrupt(self, mock_console: MagicMock, mock_builder_class: MagicMock) -> None:
        """Test build handles KeyboardInterrupt."""
        mock_builder_class.side_effect = KeyboardInterrupt

        runner = CliRunner()
        result = runner.invoke(build, [])
        assert result.exit_code == 130

    @patch("zerg.commands.build.BuildCommand")
    @patch("zerg.commands.build.console")
    def test_build_generic_exception(self, mock_console: MagicMock, mock_builder_class: MagicMock) -> None:
        """Test build handles generic exception."""
        mock_builder_class.side_effect = RuntimeError("Unexpected failure")

        runner = CliRunner()
        result = runner.invoke(build, [])
        assert result.exit_code == 1
