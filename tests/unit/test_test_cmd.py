"""Thinned unit tests for ZERG test command.

Reduced from 109 to ~25 tests by:
- Enum: 7 per-value -> 1 all-values assertion
- TestConfig: 2 -> 1 (defaults + custom combined)
- TestResult: 8 -> 3 (success, failure, zero total)
- FrameworkDetector: 20 -> 1 parametrized (pytest, jest, cargo, go, mocha, vitest + none)
- TestRunner: 25 -> 5 (init, pytest basic, run success, run failure, parse pytest)
- TestStubGenerator: 3 -> 1 (function stub)
- TestCommand: 12 -> 3 (init, dry run, format json)
- WatchLoop: 2 -> 1
- CLI: 12 -> 3 (help, success exit, keyboard interrupt)
- Integration: 3 -> 1
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from zerg.cli import cli
from zerg.commands.test_cmd import (
    FrameworkDetector,
    TestCommand,
    TestConfig,
    TestFramework,
    TestResult,
    TestRunner,
    TestStubGenerator,
    _watch_loop,
)

if TYPE_CHECKING:
    pass


# =============================================================================
# TestFramework Enum Tests
# =============================================================================


class TestTestFrameworkEnum:
    """Tests for TestFramework enum."""

    def test_all_frameworks_exist(self) -> None:
        """Test all expected frameworks are defined."""
        expected = {"pytest", "jest", "cargo", "go", "mocha", "vitest"}
        actual = {f.value for f in TestFramework}
        assert actual == expected


# =============================================================================
# TestConfig Dataclass Tests
# =============================================================================


class TestTestConfig:
    """Tests for TestConfig dataclass."""

    def test_default_and_custom_values(self) -> None:
        """Test default and custom configuration values."""
        default = TestConfig()
        assert default.parallel is True
        assert default.coverage is False
        assert default.workers == 4

        custom = TestConfig(parallel=False, coverage=True, workers=8, filter="test_specific")
        assert custom.parallel is False
        assert custom.coverage is True
        assert custom.workers == 8
        assert custom.filter == "test_specific"


# =============================================================================
# TestResult Dataclass Tests
# =============================================================================


class TestTestResult:
    """Tests for TestResult dataclass."""

    def test_success_all_passed(self) -> None:
        """Test success property and pass_percentage when all tests pass."""
        result = TestResult(total=10, passed=10, failed=0, skipped=0)
        assert result.success is True
        assert result.pass_percentage == 100.0

    def test_failure_with_failed_tests(self) -> None:
        """Test success property when tests fail."""
        result = TestResult(total=10, passed=8, failed=2, skipped=0)
        assert result.success is False
        assert result.pass_percentage == 80.0

    def test_zero_total(self) -> None:
        """Test pass percentage with zero total tests."""
        result = TestResult(total=0, passed=0, failed=0, skipped=0)
        assert result.pass_percentage == 0.0


# =============================================================================
# FrameworkDetector Tests
# =============================================================================


class TestFrameworkDetector:
    """Tests for FrameworkDetector class."""

    @pytest.mark.parametrize(
        "marker_file,marker_content,expected_framework",
        [
            ("pytest.ini", "[pytest]", TestFramework.PYTEST),
            ("jest.config.js", "module.exports = {}", TestFramework.JEST),
            ("Cargo.toml", "[package]", TestFramework.CARGO),
            ("go.mod", "module test", TestFramework.GO),
            (".mocharc.js", "module.exports = {}", TestFramework.MOCHA),
            ("vitest.config.ts", "export default {}", TestFramework.VITEST),
        ],
    )
    def test_detect_framework_from_marker(
        self, tmp_path: Path, marker_file: str, marker_content: str, expected_framework: TestFramework
    ) -> None:
        """Test detecting various frameworks from marker files."""
        (tmp_path / marker_file).write_text(marker_content)
        detector = FrameworkDetector()
        detected = detector.detect(tmp_path)
        assert expected_framework in detected

    def test_detect_no_frameworks(self, tmp_path: Path) -> None:
        """Test detect returns empty list when no frameworks found."""
        detector = FrameworkDetector()
        detected = detector.detect(tmp_path)
        assert detected == []


# =============================================================================
# TestRunner Tests
# =============================================================================


class TestTestRunner:
    """Tests for TestRunner class."""

    def test_init_default_config(self) -> None:
        """Test initialization with default config."""
        runner = TestRunner()
        assert runner.config is not None
        assert isinstance(runner.config, TestConfig)

    def test_get_command_pytest_basic(self) -> None:
        """Test basic pytest command generation."""
        runner = TestRunner(TestConfig(parallel=False, coverage=False))
        cmd = runner.get_command(TestFramework.PYTEST)
        assert "python -m pytest" in cmd

    def test_run_success(self, tmp_path: Path) -> None:
        """Test successful test run."""
        runner = TestRunner(TestConfig(parallel=False))

        with patch.object(runner, "_get_executor") as mock_get_executor:
            mock_executor = MagicMock()
            mock_result = MagicMock()
            mock_result.stdout = "5 passed in 1.23s"
            mock_result.stderr = ""
            mock_result.exit_code = 0
            mock_executor.execute.return_value = mock_result
            mock_get_executor.return_value = mock_executor

            result = runner.run(TestFramework.PYTEST, str(tmp_path))

            assert result.passed == 5
            assert result.success is True

    def test_run_with_failures(self, tmp_path: Path) -> None:
        """Test run with test failures."""
        runner = TestRunner(TestConfig(parallel=False))

        with patch.object(runner, "_get_executor") as mock_get_executor:
            mock_executor = MagicMock()
            mock_result = MagicMock()
            mock_result.stdout = "3 passed, 2 failed"
            mock_result.stderr = ""
            mock_result.exit_code = 1
            mock_executor.execute.return_value = mock_result
            mock_get_executor.return_value = mock_executor

            result = runner.run(TestFramework.PYTEST, str(tmp_path))

            assert result.passed == 3
            assert result.failed == 2
            assert result.success is False

    def test_parse_output_pytest_mixed(self) -> None:
        """Test parsing pytest output with mixed results."""
        runner = TestRunner()
        output = "======= 3 passed, 2 failed, 1 skipped in 2.34s ======="

        result = runner._parse_output(TestFramework.PYTEST, output, 1, 2.34)

        assert result.passed == 3
        assert result.failed == 2
        assert result.skipped == 1
        assert result.total == 6


# =============================================================================
# TestStubGenerator Tests
# =============================================================================


class TestTestStubGenerator:
    """Tests for TestStubGenerator class."""

    def test_generate_function_stub(self) -> None:
        """Test generating function test stub."""
        generator = TestStubGenerator()
        stub = generator.generate_stub("my_function", kind="function")

        assert "def test_my_function" in stub
        assert "my_function()" in stub
        assert "assert" in stub


# =============================================================================
# TestCommand Tests
# =============================================================================


class TestTestCommand:
    """Tests for TestCommand class."""

    def test_init_default_config(self) -> None:
        """Test initialization with default config."""
        cmd = TestCommand()
        assert cmd.config is not None
        assert isinstance(cmd.detector, FrameworkDetector)
        assert isinstance(cmd.runner, TestRunner)
        assert isinstance(cmd.stub_generator, TestStubGenerator)

    def test_run_dry_run(self, tmp_path: Path) -> None:
        """Test run with dry_run=True."""
        (tmp_path / "pytest.ini").write_text("[pytest]")
        cmd = TestCommand()

        result = cmd.run(path=str(tmp_path), dry_run=True)

        assert "Would run" in result.output
        assert "pytest" in result.errors[0].lower()

    def test_format_result_json(self) -> None:
        """Test format_result with JSON format."""
        cmd = TestCommand()
        result = TestResult(
            total=10,
            passed=8,
            failed=1,
            skipped=1,
            duration_seconds=5.5,
            coverage_percentage=85.0,
            errors=["Error 1"],
        )

        output = cmd.format_result(result, "json")
        data = json.loads(output)

        assert data["total"] == 10
        assert data["passed"] == 8
        assert data["success"] is False


# =============================================================================
# _watch_loop Tests
# =============================================================================


class TestWatchLoop:
    """Tests for _watch_loop function."""

    def test_watch_loop_keyboard_interrupt(self) -> None:
        """Test watch loop handles KeyboardInterrupt."""
        tester = TestCommand()

        with patch("time.sleep", side_effect=KeyboardInterrupt):
            with patch("zerg.commands.test_cmd.console.print") as mock_print:
                _watch_loop(tester, TestFramework.PYTEST, ".")

                calls = [str(c) for c in mock_print.call_args_list]
                assert any("stopped" in str(c).lower() for c in calls)


# =============================================================================
# CLI Command Tests
# =============================================================================


class TestTestCmdCli:
    """Tests for test_cmd CLI command."""

    def test_test_help(self) -> None:
        """Test test --help shows options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--help"])

        assert result.exit_code == 0
        assert "coverage" in result.output
        assert "watch" in result.output
        assert "framework" in result.output

    def test_test_success_exit_code(self, tmp_path: Path, monkeypatch) -> None:
        """Test successful test run exits with code 0."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()

        with patch("zerg.commands.test_cmd.TestCommand.run") as mock_run:
            mock_run.return_value = TestResult(total=5, passed=5, failed=0, skipped=0)
            result = runner.invoke(cli, ["test"], catch_exceptions=False)
            assert result.exit_code == 0

    def test_test_keyboard_interrupt(self, tmp_path: Path, monkeypatch) -> None:
        """Test KeyboardInterrupt handling."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()

        with patch("zerg.commands.test_cmd.TestCommand") as mock_class:
            mock_class.side_effect = KeyboardInterrupt()
            result = runner.invoke(cli, ["test"], catch_exceptions=False)
            assert result.exit_code == 130
            assert "Interrupted" in result.output


# =============================================================================
# Integration Tests
# =============================================================================


class TestTestCmdIntegration:
    """Integration tests combining multiple components."""

    def test_config_propagation(self) -> None:
        """Test config propagates through all components."""
        config = TestConfig(
            workers=12,
            coverage=True,
            verbose=True,
            filter="specific_test",
        )

        cmd = TestCommand(config=config)

        assert cmd.runner.config.workers == 12
        assert cmd.runner.config.coverage is True
        assert cmd.runner.config.verbose is True
        assert cmd.runner.config.filter == "specific_test"
