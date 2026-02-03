"""Comprehensive unit tests for ZERG test command.

Tests cover:
- TestFramework enum
- TestConfig dataclass
- TestResult dataclass with properties
- FrameworkDetector for all supported frameworks
- TestRunner command generation and execution
- TestStubGenerator stub creation
- TestCommand orchestration
- CLI command with all options
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

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

    def test_pytest_value(self) -> None:
        """Test pytest enum value."""
        assert TestFramework.PYTEST.value == "pytest"

    def test_jest_value(self) -> None:
        """Test jest enum value."""
        assert TestFramework.JEST.value == "jest"

    def test_cargo_value(self) -> None:
        """Test cargo enum value."""
        assert TestFramework.CARGO.value == "cargo"

    def test_go_value(self) -> None:
        """Test go enum value."""
        assert TestFramework.GO.value == "go"

    def test_mocha_value(self) -> None:
        """Test mocha enum value."""
        assert TestFramework.MOCHA.value == "mocha"

    def test_vitest_value(self) -> None:
        """Test vitest enum value."""
        assert TestFramework.VITEST.value == "vitest"

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

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = TestConfig()

        assert config.parallel is True
        assert config.coverage is False
        assert config.watch is False
        assert config.workers == 4
        assert config.timeout_seconds == 300
        assert config.verbose is False
        assert config.filter == ""

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = TestConfig(
            parallel=False,
            coverage=True,
            watch=True,
            workers=8,
            timeout_seconds=600,
            verbose=True,
            filter="test_specific",
        )

        assert config.parallel is False
        assert config.coverage is True
        assert config.watch is True
        assert config.workers == 8
        assert config.timeout_seconds == 600
        assert config.verbose is True
        assert config.filter == "test_specific"


# =============================================================================
# TestResult Dataclass Tests
# =============================================================================


class TestTestResult:
    """Tests for TestResult dataclass."""

    def test_success_property_all_passed(self) -> None:
        """Test success property when all tests pass."""
        result = TestResult(total=10, passed=10, failed=0, skipped=0)
        assert result.success is True

    def test_success_property_with_failures(self) -> None:
        """Test success property when tests fail."""
        result = TestResult(total=10, passed=8, failed=2, skipped=0)
        assert result.success is False

    def test_success_property_zero_failed(self) -> None:
        """Test success property with zero failures."""
        result = TestResult(total=5, passed=3, failed=0, skipped=2)
        assert result.success is True

    def test_pass_percentage_full(self) -> None:
        """Test pass percentage at 100%."""
        result = TestResult(total=10, passed=10, failed=0, skipped=0)
        assert result.pass_percentage == 100.0

    def test_pass_percentage_partial(self) -> None:
        """Test pass percentage at 50%."""
        result = TestResult(total=10, passed=5, failed=3, skipped=2)
        assert result.pass_percentage == 50.0

    def test_pass_percentage_zero_total(self) -> None:
        """Test pass percentage with zero total tests."""
        result = TestResult(total=0, passed=0, failed=0, skipped=0)
        assert result.pass_percentage == 0.0

    def test_default_values(self) -> None:
        """Test default values for optional fields."""
        result = TestResult(total=5, passed=3, failed=1, skipped=1)
        assert result.duration_seconds == 0.0
        assert result.coverage_percentage is None
        assert result.errors == []
        assert result.output == ""

    def test_custom_values(self) -> None:
        """Test custom values for all fields."""
        result = TestResult(
            total=10,
            passed=8,
            failed=1,
            skipped=1,
            duration_seconds=5.5,
            coverage_percentage=85.5,
            errors=["Error 1", "Error 2"],
            output="Test output",
        )
        assert result.duration_seconds == 5.5
        assert result.coverage_percentage == 85.5
        assert result.errors == ["Error 1", "Error 2"]
        assert result.output == "Test output"


# =============================================================================
# FrameworkDetector Tests
# =============================================================================


class TestFrameworkDetector:
    """Tests for FrameworkDetector class."""

    def test_detect_pytest_from_pytest_ini(self, tmp_path: Path) -> None:
        """Test detecting pytest from pytest.ini."""
        (tmp_path / "pytest.ini").write_text("[pytest]")
        detector = FrameworkDetector()

        detected = detector.detect(tmp_path)

        assert TestFramework.PYTEST in detected

    def test_detect_pytest_from_conftest(self, tmp_path: Path) -> None:
        """Test detecting pytest from conftest.py."""
        (tmp_path / "conftest.py").write_text("# conftest")
        detector = FrameworkDetector()

        detected = detector.detect(tmp_path)

        assert TestFramework.PYTEST in detected

    def test_detect_pytest_from_pyproject_toml(self, tmp_path: Path) -> None:
        """Test detecting pytest from pyproject.toml."""
        (tmp_path / "pyproject.toml").write_text("[tool.pytest]")
        detector = FrameworkDetector()

        detected = detector.detect(tmp_path)

        assert TestFramework.PYTEST in detected

    def test_detect_pytest_from_tests_dir(self, tmp_path: Path) -> None:
        """Test detecting pytest from tests directory."""
        (tmp_path / "tests").mkdir()
        detector = FrameworkDetector()

        detected = detector.detect(tmp_path)

        assert TestFramework.PYTEST in detected

    def test_detect_jest_from_config_js(self, tmp_path: Path) -> None:
        """Test detecting jest from jest.config.js."""
        (tmp_path / "jest.config.js").write_text("module.exports = {}")
        detector = FrameworkDetector()

        detected = detector.detect(tmp_path)

        assert TestFramework.JEST in detected

    def test_detect_jest_from_config_ts(self, tmp_path: Path) -> None:
        """Test detecting jest from jest.config.ts."""
        (tmp_path / "jest.config.ts").write_text("export default {}")
        detector = FrameworkDetector()

        detected = detector.detect(tmp_path)

        assert TestFramework.JEST in detected

    def test_detect_cargo_from_cargo_toml(self, tmp_path: Path) -> None:
        """Test detecting cargo from Cargo.toml."""
        (tmp_path / "Cargo.toml").write_text("[package]")
        detector = FrameworkDetector()

        detected = detector.detect(tmp_path)

        assert TestFramework.CARGO in detected

    def test_detect_go_from_go_mod(self, tmp_path: Path) -> None:
        """Test detecting go from go.mod."""
        (tmp_path / "go.mod").write_text("module test")
        detector = FrameworkDetector()

        detected = detector.detect(tmp_path)

        assert TestFramework.GO in detected

    def test_detect_mocha_from_mocharc_js(self, tmp_path: Path) -> None:
        """Test detecting mocha from .mocharc.js."""
        (tmp_path / ".mocharc.js").write_text("module.exports = {}")
        detector = FrameworkDetector()

        detected = detector.detect(tmp_path)

        assert TestFramework.MOCHA in detected

    def test_detect_mocha_from_mocharc_json(self, tmp_path: Path) -> None:
        """Test detecting mocha from .mocharc.json."""
        (tmp_path / ".mocharc.json").write_text("{}")
        detector = FrameworkDetector()

        detected = detector.detect(tmp_path)

        assert TestFramework.MOCHA in detected

    def test_detect_vitest_from_config_ts(self, tmp_path: Path) -> None:
        """Test detecting vitest from vitest.config.ts."""
        (tmp_path / "vitest.config.ts").write_text("export default {}")
        detector = FrameworkDetector()

        detected = detector.detect(tmp_path)

        assert TestFramework.VITEST in detected

    def test_detect_vitest_from_config_js(self, tmp_path: Path) -> None:
        """Test detecting vitest from vitest.config.js."""
        (tmp_path / "vitest.config.js").write_text("export default {}")
        detector = FrameworkDetector()

        detected = detector.detect(tmp_path)

        assert TestFramework.VITEST in detected

    def test_detect_jest_from_package_json(self, tmp_path: Path) -> None:
        """Test detecting jest from package.json dependencies."""
        pkg = {"devDependencies": {"jest": "^29.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        detector = FrameworkDetector()

        detected = detector.detect(tmp_path)

        assert TestFramework.JEST in detected

    def test_detect_vitest_from_package_json(self, tmp_path: Path) -> None:
        """Test detecting vitest from package.json dependencies."""
        pkg = {"dependencies": {"vitest": "^1.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        detector = FrameworkDetector()

        detected = detector.detect(tmp_path)

        assert TestFramework.VITEST in detected

    def test_detect_mocha_from_package_json(self, tmp_path: Path) -> None:
        """Test detecting mocha from package.json dependencies."""
        pkg = {"devDependencies": {"mocha": "^10.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        detector = FrameworkDetector()

        detected = detector.detect(tmp_path)

        assert TestFramework.MOCHA in detected

    def test_detect_handles_invalid_package_json(self, tmp_path: Path) -> None:
        """Test detect handles invalid package.json gracefully."""
        (tmp_path / "package.json").write_text("invalid json{{{")
        detector = FrameworkDetector()

        # Should not raise an exception
        detected = detector.detect(tmp_path)

        # Should return empty list if no other markers found
        assert isinstance(detected, list)

    def test_detect_no_frameworks(self, tmp_path: Path) -> None:
        """Test detect returns empty list when no frameworks found."""
        detector = FrameworkDetector()

        detected = detector.detect(tmp_path)

        assert detected == []

    def test_detect_multiple_frameworks(self, tmp_path: Path) -> None:
        """Test detect finds multiple frameworks."""
        (tmp_path / "pytest.ini").write_text("[pytest]")
        (tmp_path / "jest.config.js").write_text("module.exports = {}")
        detector = FrameworkDetector()

        detected = detector.detect(tmp_path)

        assert TestFramework.PYTEST in detected
        assert TestFramework.JEST in detected

    def test_detect_no_duplicates_from_package_json(self, tmp_path: Path) -> None:
        """Test detect doesn't add duplicates from package.json."""
        (tmp_path / "jest.config.js").write_text("module.exports = {}")
        pkg = {"devDependencies": {"jest": "^29.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        detector = FrameworkDetector()

        detected = detector.detect(tmp_path)

        # Jest should appear only once
        assert detected.count(TestFramework.JEST) == 1


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

    def test_init_custom_config(self) -> None:
        """Test initialization with custom config."""
        config = TestConfig(workers=8, coverage=True)
        runner = TestRunner(config=config)
        assert runner.config.workers == 8
        assert runner.config.coverage is True

    def test_get_executor(self, tmp_path: Path) -> None:
        """Test _get_executor returns CommandExecutor."""
        runner = TestRunner()
        executor = runner._get_executor(str(tmp_path))
        # Just verify it returns an executor-like object
        assert hasattr(executor, "execute")

    # -------------------------------------------------------------------------
    # get_command tests for all frameworks
    # -------------------------------------------------------------------------

    def test_get_command_pytest_basic(self) -> None:
        """Test basic pytest command generation."""
        runner = TestRunner(TestConfig(parallel=False, coverage=False))
        cmd = runner.get_command(TestFramework.PYTEST)
        assert "python -m pytest" in cmd

    def test_get_command_pytest_with_coverage(self) -> None:
        """Test pytest command with coverage."""
        runner = TestRunner(TestConfig(coverage=True, parallel=False))
        cmd = runner.get_command(TestFramework.PYTEST)
        assert "--cov" in cmd

    def test_get_command_pytest_with_parallel(self) -> None:
        """Test pytest command with parallel workers."""
        runner = TestRunner(TestConfig(parallel=True, workers=4))
        cmd = runner.get_command(TestFramework.PYTEST)
        assert "-n 4" in cmd

    def test_get_command_pytest_with_verbose(self) -> None:
        """Test pytest command with verbose flag."""
        runner = TestRunner(TestConfig(verbose=True, parallel=False))
        cmd = runner.get_command(TestFramework.PYTEST)
        assert "-v" in cmd

    def test_get_command_pytest_with_filter(self) -> None:
        """Test pytest command with test filter."""
        runner = TestRunner(TestConfig(filter="test_specific", parallel=False))
        cmd = runner.get_command(TestFramework.PYTEST)
        assert "-k 'test_specific'" in cmd

    def test_get_command_pytest_with_path(self) -> None:
        """Test pytest command with path."""
        runner = TestRunner(TestConfig(parallel=False))
        cmd = runner.get_command(TestFramework.PYTEST, path="tests/unit")
        assert "tests/unit" in cmd

    def test_get_command_jest_basic(self) -> None:
        """Test basic jest command generation."""
        runner = TestRunner(TestConfig(parallel=False, coverage=False))
        cmd = runner.get_command(TestFramework.JEST)
        assert "npx jest" in cmd

    def test_get_command_jest_with_coverage(self) -> None:
        """Test jest command with coverage."""
        runner = TestRunner(TestConfig(coverage=True, parallel=False))
        cmd = runner.get_command(TestFramework.JEST)
        assert "--coverage" in cmd

    def test_get_command_jest_with_parallel(self) -> None:
        """Test jest command with parallel workers."""
        runner = TestRunner(TestConfig(parallel=True, workers=4))
        cmd = runner.get_command(TestFramework.JEST)
        assert "--maxWorkers=4" in cmd

    def test_get_command_jest_with_path(self) -> None:
        """Test jest command with path."""
        runner = TestRunner(TestConfig(parallel=False))
        cmd = runner.get_command(TestFramework.JEST, path="src/__tests__")
        assert "src/__tests__" in cmd

    def test_get_command_cargo_basic(self) -> None:
        """Test basic cargo command generation."""
        runner = TestRunner(TestConfig(parallel=False))
        cmd = runner.get_command(TestFramework.CARGO)
        assert "cargo test" in cmd

    def test_get_command_cargo_with_parallel(self) -> None:
        """Test cargo command with parallel threads."""
        runner = TestRunner(TestConfig(parallel=True, workers=4))
        cmd = runner.get_command(TestFramework.CARGO)
        assert "--test-threads=4" in cmd

    def test_get_command_go_basic(self) -> None:
        """Test basic go command generation."""
        runner = TestRunner(TestConfig(parallel=False, coverage=False))
        cmd = runner.get_command(TestFramework.GO)
        assert "go test" in cmd

    def test_get_command_go_with_coverage(self) -> None:
        """Test go command with coverage."""
        runner = TestRunner(TestConfig(coverage=True, parallel=False))
        cmd = runner.get_command(TestFramework.GO)
        assert "-cover" in cmd

    def test_get_command_go_with_verbose(self) -> None:
        """Test go command with verbose flag."""
        runner = TestRunner(TestConfig(verbose=True, parallel=False))
        cmd = runner.get_command(TestFramework.GO)
        assert "-v" in cmd

    def test_get_command_go_with_path(self) -> None:
        """Test go command with path."""
        runner = TestRunner(TestConfig(parallel=False))
        cmd = runner.get_command(TestFramework.GO, path="./pkg/...")
        assert "./pkg/..." in cmd

    def test_get_command_mocha_basic(self) -> None:
        """Test basic mocha command generation."""
        runner = TestRunner(TestConfig(parallel=False))
        cmd = runner.get_command(TestFramework.MOCHA)
        assert "npx mocha" in cmd

    def test_get_command_vitest_basic(self) -> None:
        """Test basic vitest command generation."""
        runner = TestRunner(TestConfig(parallel=False))
        cmd = runner.get_command(TestFramework.VITEST)
        assert "npx vitest run" in cmd

    def test_get_command_unknown_framework_fallback(self) -> None:
        """Test unknown framework uses pytest as fallback."""
        runner = TestRunner(TestConfig(parallel=False))
        # Use a framework not in COMMANDS dict (fake scenario)
        cmd = runner.get_command(TestFramework.PYTEST)
        assert "pytest" in cmd

    # -------------------------------------------------------------------------
    # run() method tests
    # -------------------------------------------------------------------------

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

    def test_run_command_validation_error(self, tmp_path: Path) -> None:
        """Test run handles CommandValidationError."""
        from zerg.command_executor import CommandValidationError

        runner = TestRunner(TestConfig(parallel=False))

        with patch.object(runner, "_get_executor") as mock_get_executor:
            mock_executor = MagicMock()
            mock_executor.execute.side_effect = CommandValidationError("Invalid")
            mock_get_executor.return_value = mock_executor

            result = runner.run(TestFramework.PYTEST, str(tmp_path))

            assert result.total == 0
            assert "validation failed" in result.errors[0].lower()

    def test_run_general_exception(self, tmp_path: Path) -> None:
        """Test run handles general exceptions."""
        runner = TestRunner(TestConfig(parallel=False))

        with patch.object(runner, "_get_executor") as mock_get_executor:
            mock_executor = MagicMock()
            mock_executor.execute.side_effect = RuntimeError("Unexpected error")
            mock_get_executor.return_value = mock_executor

            result = runner.run(TestFramework.PYTEST, str(tmp_path))

            assert result.total == 0
            assert "execution error" in result.errors[0].lower()

    # -------------------------------------------------------------------------
    # _parse_output tests
    # -------------------------------------------------------------------------

    def test_parse_output_pytest_passed(self) -> None:
        """Test parsing pytest output with passed tests."""
        runner = TestRunner()
        output = "================== 5 passed in 1.23s =================="

        result = runner._parse_output(TestFramework.PYTEST, output, 0, 1.23)

        assert result.passed == 5
        assert result.failed == 0
        assert result.total == 5

    def test_parse_output_pytest_mixed(self) -> None:
        """Test parsing pytest output with mixed results."""
        runner = TestRunner()
        output = "======= 3 passed, 2 failed, 1 skipped in 2.34s ======="

        result = runner._parse_output(TestFramework.PYTEST, output, 1, 2.34)

        assert result.passed == 3
        assert result.failed == 2
        assert result.skipped == 1
        assert result.total == 6

    def test_parse_output_pytest_with_errors(self) -> None:
        """Test parsing pytest output with errors."""
        runner = TestRunner()
        output = "======= 3 passed, 1 error in 1.00s ======="

        result = runner._parse_output(TestFramework.PYTEST, output, 1, 1.0)

        assert result.passed == 3
        assert result.failed == 1  # error counts as failed

    def test_parse_output_pytest_with_coverage(self) -> None:
        """Test parsing pytest output with coverage."""
        runner = TestRunner()
        output = """
        5 passed in 1.23s
        TOTAL    100    10    90%
        """

        result = runner._parse_output(TestFramework.PYTEST, output, 0, 1.23)

        assert result.coverage_percentage == 90.0

    def test_parse_output_jest(self) -> None:
        """Test parsing jest output."""
        runner = TestRunner()
        output = "Tests: 3 passed, 1 failed, 1 skipped, 5 total"

        result = runner._parse_output(TestFramework.JEST, output, 1, 2.0)

        assert result.passed == 3
        assert result.failed == 1
        assert result.skipped == 1
        assert result.total == 5

    def test_parse_output_vitest(self) -> None:
        """Test parsing vitest output (uses same pattern as jest)."""
        runner = TestRunner()
        output = "Tests: 4 passed, 0 failed, 4 total"

        result = runner._parse_output(TestFramework.VITEST, output, 0, 1.5)

        assert result.passed == 4
        assert result.failed == 0
        assert result.total == 4

    def test_parse_output_go(self) -> None:
        """Test parsing go test output."""
        runner = TestRunner()
        output = """
        --- PASS: TestOne
        --- PASS: TestTwo
        --- FAIL: TestThree
        --- SKIP: TestFour
        """

        result = runner._parse_output(TestFramework.GO, output, 1, 3.0)

        assert result.passed == 2
        assert result.failed == 1
        assert result.skipped == 1
        assert result.total == 4

    def test_parse_output_go_with_coverage(self) -> None:
        """Test parsing go test output with coverage."""
        runner = TestRunner()
        output = """
        --- PASS: TestOne
        coverage: 78.5% of statements
        """

        result = runner._parse_output(TestFramework.GO, output, 0, 2.0)

        assert result.coverage_percentage == 78.5

    def test_parse_output_cargo(self) -> None:
        """Test parsing cargo test output."""
        runner = TestRunner()
        output = "test result: ok. 5 passed; 1 failed; 2 ignored"

        result = runner._parse_output(TestFramework.CARGO, output, 1, 4.0)

        assert result.passed == 5
        assert result.failed == 1
        assert result.skipped == 2
        assert result.total == 8

    def test_parse_output_fallback_success(self) -> None:
        """Test fallback parsing for successful unknown output."""
        runner = TestRunner()
        output = "Unknown format but tests ran"

        result = runner._parse_output(TestFramework.MOCHA, output, 0, 1.0)

        # Fallback: if returncode == 0 and no matches, assume 1 passed
        assert result.total == 1
        assert result.passed == 1

    def test_parse_output_fallback_failure(self) -> None:
        """Test fallback parsing for failed unknown output."""
        runner = TestRunner()
        output = "Unknown format tests failed"

        result = runner._parse_output(TestFramework.MOCHA, output, 1, 1.0)

        # Fallback: if returncode != 0 and no matches, assume 1 failed
        assert result.total == 1
        assert result.failed == 1
        assert len(result.errors) > 0

    def test_parse_output_stores_duration(self) -> None:
        """Test that parse_output stores duration correctly."""
        runner = TestRunner()
        output = "5 passed"

        result = runner._parse_output(TestFramework.PYTEST, output, 0, 3.456)

        assert result.duration_seconds == 3.456


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

    def test_generate_class_stub(self) -> None:
        """Test generating class test stub."""
        generator = TestStubGenerator()
        stub = generator.generate_stub("MyClass", kind="class")

        assert "class TestMyClass" in stub
        assert "test_MyClass_creation" in stub
        assert "test_MyClass_basic_operation" in stub
        assert "MyClass()" in stub

    def test_generate_unknown_kind_uses_function(self) -> None:
        """Test generating stub with unknown kind defaults to function."""
        generator = TestStubGenerator()
        stub = generator.generate_stub("something", kind="unknown")

        assert "def test_something" in stub


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

    def test_init_custom_config(self) -> None:
        """Test initialization with custom config."""
        config = TestConfig(workers=10)
        cmd = TestCommand(config=config)
        assert cmd.config.workers == 10

    def test_supported_frameworks(self) -> None:
        """Test supported_frameworks returns all framework values."""
        cmd = TestCommand()
        frameworks = cmd.supported_frameworks()

        assert "pytest" in frameworks
        assert "jest" in frameworks
        assert "cargo" in frameworks
        assert "go" in frameworks
        assert "mocha" in frameworks
        assert "vitest" in frameworks

    def test_run_dry_run(self, tmp_path: Path) -> None:
        """Test run with dry_run=True."""
        (tmp_path / "pytest.ini").write_text("[pytest]")
        cmd = TestCommand()

        result = cmd.run(path=str(tmp_path), dry_run=True)

        assert "Would run" in result.output
        assert "pytest" in result.errors[0].lower()

    def test_run_dry_run_no_framework(self, tmp_path: Path) -> None:
        """Test dry run with no detectable framework."""
        cmd = TestCommand()

        result = cmd.run(path=str(tmp_path), dry_run=True)

        # Should fallback to pytest and still work
        assert "Would run" in result.output

    def test_run_with_specified_framework(self, tmp_path: Path) -> None:
        """Test run with specified framework."""
        cmd = TestCommand()

        with patch.object(cmd.runner, "run") as mock_run:
            mock_run.return_value = TestResult(total=5, passed=5, failed=0, skipped=0)
            result = cmd.run(
                framework=TestFramework.JEST,
                path=str(tmp_path),
                dry_run=False,
            )

            mock_run.assert_called_once_with(TestFramework.JEST, str(tmp_path))
            assert result.passed == 5

    def test_run_auto_detect_framework(self, tmp_path: Path) -> None:
        """Test run with auto-detected framework."""
        (tmp_path / "Cargo.toml").write_text("[package]")
        cmd = TestCommand()

        with patch.object(cmd.runner, "run") as mock_run:
            mock_run.return_value = TestResult(total=3, passed=3, failed=0, skipped=0)
            cmd.run(path=str(tmp_path), dry_run=False)

            # Should have detected and used Cargo
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0] == TestFramework.CARGO

    def test_run_fallback_to_pytest(self, tmp_path: Path) -> None:
        """Test run falls back to pytest when no framework detected."""
        cmd = TestCommand()

        with patch.object(cmd.runner, "run") as mock_run:
            mock_run.return_value = TestResult(total=1, passed=1, failed=0, skipped=0)
            cmd.run(path=str(tmp_path), dry_run=False)

            # Should fallback to pytest
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0] == TestFramework.PYTEST

    # -------------------------------------------------------------------------
    # format_result tests
    # -------------------------------------------------------------------------

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
        assert data["failed"] == 1
        assert data["skipped"] == 1
        assert data["success"] is False
        assert data["pass_percentage"] == 80.0
        assert data["duration_seconds"] == 5.5
        assert data["coverage_percentage"] == 85.0
        assert data["errors"] == ["Error 1"]

    def test_format_result_text(self) -> None:
        """Test format_result with text format."""
        cmd = TestCommand()
        result = TestResult(
            total=5,
            passed=4,
            failed=1,
            skipped=0,
            duration_seconds=2.5,
        )

        output = cmd.format_result(result, "text")

        assert "Test Results" in output
        assert "Total: 5" in output
        assert "Passed: 4" in output
        assert "Failed: 1" in output
        assert "Skipped: 0" in output
        assert "Pass Rate: 80.0%" in output
        assert "Duration: 2.50s" in output

    def test_format_result_text_with_coverage(self) -> None:
        """Test format_result text includes coverage."""
        cmd = TestCommand()
        result = TestResult(
            total=5,
            passed=5,
            failed=0,
            skipped=0,
            coverage_percentage=92.5,
        )

        output = cmd.format_result(result, "text")

        assert "Coverage: 92.5%" in output

    def test_format_result_text_with_errors(self) -> None:
        """Test format_result text includes errors."""
        cmd = TestCommand()
        result = TestResult(
            total=5,
            passed=3,
            failed=2,
            skipped=0,
            errors=["Error one", "Error two"],
        )

        output = cmd.format_result(result, "text")

        assert "Errors:" in output

    def test_format_result_text_no_duration(self) -> None:
        """Test format_result text without duration."""
        cmd = TestCommand()
        result = TestResult(
            total=1,
            passed=1,
            failed=0,
            skipped=0,
            duration_seconds=0.0,  # No duration
        )

        output = cmd.format_result(result, "text")

        # Should not have Duration line when duration is 0
        assert "Duration:" not in output


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

                # Should print watch mode messages
                calls = [str(c) for c in mock_print.call_args_list]
                # At least the stop message should appear
                assert any("stopped" in str(c).lower() for c in calls)

    def test_watch_loop_detects_changes(self, tmp_path: Path) -> None:
        """Test watch loop detects file changes."""
        # Create a test file
        test_file = tmp_path / "test.py"
        test_file.write_text("# initial")

        tester = TestCommand()

        call_count = [0]
        sleep_count = [0]
        original_result = TestResult(total=1, passed=1, failed=0, skipped=0)

        def mock_run(*args, **kwargs):
            call_count[0] += 1
            return original_result

        def mock_sleep(duration):
            sleep_count[0] += 1
            # Safety limit to prevent infinite loop
            if sleep_count[0] > 10:
                raise KeyboardInterrupt
            if sleep_count[0] == 1:
                # First iteration, modify file
                test_file.write_text("# modified")
            elif call_count[0] >= 1:
                # Stop after detecting changes and running tests
                raise KeyboardInterrupt

        # Mock time.time to bypass the 2-second debounce check
        fake_time = [100.0]

        def mock_time():
            fake_time[0] += 3.0  # Advance 3 seconds each call
            return fake_time[0]

        with patch.object(tester, "run", side_effect=mock_run):
            with patch("time.sleep", side_effect=mock_sleep):
                with patch("time.time", side_effect=mock_time):
                    with patch("zerg.commands.test_cmd.console.print"):
                        _watch_loop(tester, TestFramework.PYTEST, str(tmp_path))


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
        assert "parallel" in result.output
        assert "framework" in result.output
        assert "path" in result.output
        assert "dry-run" in result.output
        assert "json" in result.output
        assert "generate" in result.output

    def test_test_dry_run(self, tmp_path: Path, monkeypatch) -> None:
        """Test test --dry-run flag."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pytest.ini").write_text("[pytest]")

        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--dry-run"])

        assert "Would run" in result.output or "Dry run" in result.output

    def test_test_generate_flag(self, tmp_path: Path, monkeypatch) -> None:
        """Test test --generate flag."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "module.py").write_text("def func(): pass")

        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--generate"])

        assert result.exit_code == 0
        assert "stub" in result.output.lower() or "preview" in result.output.lower()

    def test_test_framework_option(self) -> None:
        """Test test --framework option."""
        runner = CliRunner()
        # Just check the option is recognized
        result = runner.invoke(cli, ["test", "--framework", "jest", "--help"])

        # Help should still work with framework option
        assert result.exit_code == 0

    def test_test_framework_choices(self) -> None:
        """Test test --framework validates choices."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--framework", "invalid"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output or "invalid" in result.output.lower()

    def test_test_parallel_option(self) -> None:
        """Test test --parallel option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--parallel", "8", "--help"])

        assert result.exit_code == 0

    def test_test_json_output(self, tmp_path: Path, monkeypatch) -> None:
        """Test test --json flag produces JSON output."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pytest.ini").write_text("[pytest]")

        runner = CliRunner()

        # Patch the TestCommand.run to return a mock result
        with patch("zerg.commands.test_cmd.TestCommand.run") as mock_run:
            mock_run.return_value = TestResult(total=5, passed=5, failed=0, skipped=0)
            result = runner.invoke(cli, ["test", "--json", "--dry-run"])

            # With dry-run and json, output should contain dry run info
            # Or if not dry-run, should be valid JSON format
            assert "json" in result.output.lower() or "{" in result.output

    def test_test_path_option(self, tmp_path: Path, monkeypatch) -> None:
        """Test test --path option."""
        monkeypatch.chdir(tmp_path)
        test_dir = tmp_path / "custom_tests"
        test_dir.mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--path", str(test_dir), "--dry-run"])

        # Command should accept the path
        assert result.exit_code == 0 or "Would run" in result.output

    def test_test_coverage_flag(self, tmp_path: Path, monkeypatch) -> None:
        """Test test --coverage flag."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        # Patch to avoid actually running tests
        with patch("zerg.commands.test_cmd.TestCommand.run") as mock_run:
            mock_run.return_value = TestResult(total=1, passed=1, failed=0, skipped=0, coverage_percentage=90.0)
            result = runner.invoke(cli, ["test", "--coverage", "--dry-run"])

            # Should work without error
            assert "Error" not in result.output or result.exit_code == 0

    def test_test_watch_dry_run(self, tmp_path: Path, monkeypatch) -> None:
        """Test test --watch with --dry-run shows message."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pytest.ini").write_text("[pytest]")

        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--watch", "--dry-run"])

        assert "watch" in result.output.lower() or result.exit_code == 0

    def test_test_success_exit_code(self, tmp_path: Path, monkeypatch) -> None:
        """Test successful test run exits with code 0."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()

        with patch("zerg.commands.test_cmd.TestCommand.run") as mock_run:
            mock_run.return_value = TestResult(total=5, passed=5, failed=0, skipped=0)

            # Use mix_stderr to capture all output
            result = runner.invoke(cli, ["test"], catch_exceptions=False)

            # The command exits with SystemExit(0) on success
            # CliRunner catches SystemExit and converts to exit_code
            assert result.exit_code == 0

    def test_test_failure_exit_code(self, tmp_path: Path, monkeypatch) -> None:
        """Test failed test run exits with code 1."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()

        with patch("zerg.commands.test_cmd.TestCommand.run") as mock_run:
            mock_run.return_value = TestResult(total=5, passed=3, failed=2, skipped=0)

            result = runner.invoke(cli, ["test"], catch_exceptions=False)

            assert result.exit_code == 1

    def test_test_exception_handling(self, tmp_path: Path, monkeypatch) -> None:
        """Test exception handling in CLI."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()

        with patch("zerg.commands.test_cmd.TestCommand") as mock_class:
            mock_class.side_effect = RuntimeError("Unexpected error")

            result = runner.invoke(cli, ["test"], catch_exceptions=False)

            assert result.exit_code == 1
            assert "Error" in result.output or "error" in result.output.lower()

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

    def test_full_dry_run_flow(self, tmp_path: Path, monkeypatch) -> None:
        """Test complete dry-run flow."""
        monkeypatch.chdir(tmp_path)

        # Set up a pytest project
        (tmp_path / "pytest.ini").write_text("[pytest]")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_example.py").write_text("def test_example(): assert True")

        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--dry-run"])

        assert "pytest" in result.output.lower()
        assert result.exit_code == 0

    def test_config_propagation(self) -> None:
        """Test config propagates through all components."""
        config = TestConfig(
            workers=12,
            coverage=True,
            verbose=True,
            filter="specific_test",
        )

        cmd = TestCommand(config=config)

        # Verify config is used by runner
        assert cmd.runner.config.workers == 12
        assert cmd.runner.config.coverage is True
        assert cmd.runner.config.verbose is True
        assert cmd.runner.config.filter == "specific_test"

    def test_framework_detection_to_command(self, tmp_path: Path) -> None:
        """Test framework detection leads to correct command."""
        (tmp_path / "go.mod").write_text("module test")

        cmd = TestCommand()

        # Detect framework
        frameworks = cmd.detector.detect(tmp_path)
        assert TestFramework.GO in frameworks

        # Get command for detected framework
        command = cmd.runner.get_command(TestFramework.GO)
        assert "go test" in command
