"""Tests for StepGenerator module.

Tests the TDD-style step generation for tasks based on detail level.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from zerg.step_generator import (
    DetailLevel,
    FormatterConfig,
    Step,
    StepAction,
    StepGenerator,
    VerifyMode,
    generate_steps_for_task,
)

pytestmark = pytest.mark.smoke


class TestDetailLevel:
    """Tests for DetailLevel enum."""

    def test_detail_level_values(self) -> None:
        """Test DetailLevel enum has correct values."""
        assert DetailLevel.STANDARD.value == "standard"
        assert DetailLevel.MEDIUM.value == "medium"
        assert DetailLevel.HIGH.value == "high"

    def test_detail_level_from_string(self) -> None:
        """Test creating DetailLevel from string."""
        assert DetailLevel("standard") == DetailLevel.STANDARD
        assert DetailLevel("medium") == DetailLevel.MEDIUM
        assert DetailLevel("high") == DetailLevel.HIGH


class TestStepAction:
    """Tests for StepAction enum."""

    def test_step_action_values(self) -> None:
        """Test StepAction enum has correct TDD sequence values."""
        assert StepAction.WRITE_TEST.value == "write_test"
        assert StepAction.VERIFY_FAIL.value == "verify_fail"
        assert StepAction.IMPLEMENT.value == "implement"
        assert StepAction.VERIFY_PASS.value == "verify_pass"
        assert StepAction.FORMAT.value == "format"
        assert StepAction.COMMIT.value == "commit"


class TestVerifyMode:
    """Tests for VerifyMode enum."""

    def test_verify_mode_values(self) -> None:
        """Test VerifyMode enum has correct values."""
        assert VerifyMode.EXIT_CODE.value == "exit_code"
        assert VerifyMode.EXIT_CODE_NONZERO.value == "exit_code_nonzero"
        assert VerifyMode.NONE.value == "none"


class TestStep:
    """Tests for Step dataclass."""

    def test_step_creation(self) -> None:
        """Test creating a Step."""
        step = Step(
            step=1,
            action=StepAction.WRITE_TEST,
            file="tests/test_foo.py",
            code_snippet="def test_foo(): pass",
            run="pytest tests/test_foo.py",
            verify=VerifyMode.EXIT_CODE,
        )
        assert step.step == 1
        assert step.action == StepAction.WRITE_TEST
        assert step.file == "tests/test_foo.py"
        assert step.code_snippet == "def test_foo(): pass"
        assert step.run == "pytest tests/test_foo.py"
        assert step.verify == VerifyMode.EXIT_CODE

    def test_step_defaults(self) -> None:
        """Test Step default values."""
        step = Step(step=1, action=StepAction.WRITE_TEST)
        assert step.file is None
        assert step.code_snippet is None
        assert step.run is None
        assert step.verify == VerifyMode.EXIT_CODE

    def test_step_to_dict(self) -> None:
        """Test Step serialization to dictionary."""
        step = Step(
            step=1,
            action=StepAction.WRITE_TEST,
            file="tests/test_foo.py",
            code_snippet="def test_foo(): pass",
            run="pytest",
            verify=VerifyMode.EXIT_CODE,
        )
        result = step.to_dict()
        assert result["step"] == 1
        assert result["action"] == "write_test"
        assert result["file"] == "tests/test_foo.py"
        assert result["code_snippet"] == "def test_foo(): pass"
        assert result["run"] == "pytest"
        assert result["verify"] == "exit_code"

    def test_step_to_dict_omits_none(self) -> None:
        """Test Step serialization omits None values."""
        step = Step(step=1, action=StepAction.WRITE_TEST)
        result = step.to_dict()
        assert "file" not in result
        assert "code_snippet" not in result
        assert "run" not in result
        assert "step" in result
        assert "action" in result
        assert "verify" in result


class TestFormatterConfig:
    """Tests for FormatterConfig dataclass."""

    def test_formatter_config_creation(self) -> None:
        """Test creating a FormatterConfig."""
        config = FormatterConfig(
            format_cmd="ruff format",
            fix_cmd="ruff check --fix",
            file_patterns=["*.py"],
        )
        assert config.format_cmd == "ruff format"
        assert config.fix_cmd == "ruff check --fix"
        assert config.file_patterns == ["*.py"]


class TestStepGenerator:
    """Tests for StepGenerator class."""

    @pytest.fixture
    def sample_task(self) -> dict[str, Any]:
        """Create a sample task for testing."""
        return {
            "id": "TEST-L1-001",
            "title": "Add user authentication",
            "description": "Implement JWT-based user authentication",
            "files": {
                "create": ["zerg/auth.py"],
                "modify": [],
                "read": [],
            },
            "verification": {
                "command": "pytest tests/unit/test_auth.py -v",
                "timeout_seconds": 30,
            },
        }

    @pytest.fixture
    def task_with_modify(self) -> dict[str, Any]:
        """Create a task that modifies existing files."""
        return {
            "id": "TEST-L1-002",
            "title": "Fix authentication bug",
            "description": "Fix token validation issue",
            "files": {
                "create": [],
                "modify": ["zerg/auth.py"],
                "read": [],
            },
        }

    def test_standard_detail_returns_empty(self, sample_task: dict[str, Any]) -> None:
        """Test standard detail level returns no steps."""
        generator = StepGenerator()
        steps = generator.generate(sample_task, DetailLevel.STANDARD)
        assert steps == []

    def test_standard_detail_string_returns_empty(self, sample_task: dict[str, Any]) -> None:
        """Test standard detail level as string returns no steps."""
        generator = StepGenerator()
        steps = generator.generate(sample_task, "standard")
        assert steps == []

    def test_medium_detail_generates_6_steps(self, sample_task: dict[str, Any]) -> None:
        """Test medium detail level generates 6 TDD steps."""
        generator = StepGenerator()
        steps = generator.generate(sample_task, DetailLevel.MEDIUM)
        assert len(steps) == 6

    def test_high_detail_generates_6_steps(self, sample_task: dict[str, Any]) -> None:
        """Test high detail level generates 6 TDD steps."""
        generator = StepGenerator()
        steps = generator.generate(sample_task, DetailLevel.HIGH)
        assert len(steps) == 6

    def test_step_order_matches_tdd_sequence(self, sample_task: dict[str, Any]) -> None:
        """Test steps are in correct TDD sequence."""
        generator = StepGenerator()
        steps = generator.generate(sample_task, DetailLevel.MEDIUM)

        expected_actions = [
            StepAction.WRITE_TEST,
            StepAction.VERIFY_FAIL,
            StepAction.IMPLEMENT,
            StepAction.VERIFY_PASS,
            StepAction.FORMAT,
            StepAction.COMMIT,
        ]

        actual_actions = [step.action for step in steps]
        assert actual_actions == expected_actions

    def test_step_numbers_sequential(self, sample_task: dict[str, Any]) -> None:
        """Test step numbers are sequential starting from 1."""
        generator = StepGenerator()
        steps = generator.generate(sample_task, DetailLevel.MEDIUM)

        expected_numbers = [1, 2, 3, 4, 5, 6]
        actual_numbers = [step.step for step in steps]
        assert actual_numbers == expected_numbers

    def test_verify_fail_step_expects_nonzero_exit(self, sample_task: dict[str, Any]) -> None:
        """Test verify_fail step expects nonzero exit code."""
        generator = StepGenerator()
        steps = generator.generate(sample_task, DetailLevel.MEDIUM)

        verify_fail_step = steps[1]  # Second step
        assert verify_fail_step.action == StepAction.VERIFY_FAIL
        assert verify_fail_step.verify == VerifyMode.EXIT_CODE_NONZERO

    def test_verify_pass_step_expects_zero_exit(self, sample_task: dict[str, Any]) -> None:
        """Test verify_pass step expects zero exit code."""
        generator = StepGenerator()
        steps = generator.generate(sample_task, DetailLevel.MEDIUM)

        verify_pass_step = steps[3]  # Fourth step
        assert verify_pass_step.action == StepAction.VERIFY_PASS
        assert verify_pass_step.verify == VerifyMode.EXIT_CODE

    def test_write_test_step_has_no_verification(self, sample_task: dict[str, Any]) -> None:
        """Test write_test step has no verification."""
        generator = StepGenerator()
        steps = generator.generate(sample_task, DetailLevel.MEDIUM)

        write_test_step = steps[0]
        assert write_test_step.action == StepAction.WRITE_TEST
        assert write_test_step.verify == VerifyMode.NONE

    def test_implement_step_has_no_verification(self, sample_task: dict[str, Any]) -> None:
        """Test implement step has no verification."""
        generator = StepGenerator()
        steps = generator.generate(sample_task, DetailLevel.MEDIUM)

        implement_step = steps[2]
        assert implement_step.action == StepAction.IMPLEMENT
        assert implement_step.verify == VerifyMode.NONE

    def test_format_step_has_run_command(self, sample_task: dict[str, Any]) -> None:
        """Test format step has a run command."""
        generator = StepGenerator()
        steps = generator.generate(sample_task, DetailLevel.MEDIUM)

        format_step = steps[4]
        assert format_step.action == StepAction.FORMAT
        assert format_step.run is not None
        assert "format" in format_step.run.lower() or "ruff" in format_step.run.lower()

    def test_commit_step_has_commit_command(self, sample_task: dict[str, Any]) -> None:
        """Test commit step has git commit command."""
        generator = StepGenerator()
        steps = generator.generate(sample_task, DetailLevel.MEDIUM)

        commit_step = steps[5]
        assert commit_step.action == StepAction.COMMIT
        assert commit_step.run is not None
        assert "git" in commit_step.run
        assert "commit" in commit_step.run

    def test_commit_message_includes_task_id(self, sample_task: dict[str, Any]) -> None:
        """Test commit message includes task ID."""
        generator = StepGenerator()
        steps = generator.generate(sample_task, DetailLevel.MEDIUM)

        commit_step = steps[5]
        assert "TEST-L1-001" in commit_step.run

    def test_medium_detail_no_code_snippets(self, sample_task: dict[str, Any]) -> None:
        """Test medium detail level does not include code snippets."""
        generator = StepGenerator()
        steps = generator.generate(sample_task, DetailLevel.MEDIUM)

        for step in steps:
            assert step.code_snippet is None

    def test_high_detail_includes_code_snippets(self, sample_task: dict[str, Any]) -> None:
        """Test high detail level includes code snippets for write_test and implement."""
        generator = StepGenerator()
        steps = generator.generate(sample_task, DetailLevel.HIGH)

        write_test_step = steps[0]
        implement_step = steps[2]

        assert write_test_step.code_snippet is not None
        assert implement_step.code_snippet is not None

    def test_high_detail_test_snippet_contains_test(self, sample_task: dict[str, Any]) -> None:
        """Test high detail test snippet contains test code."""
        generator = StepGenerator()
        steps = generator.generate(sample_task, DetailLevel.HIGH)

        write_test_step = steps[0]
        snippet = write_test_step.code_snippet
        assert "test" in snippet.lower()
        assert "def " in snippet or "class " in snippet

    def test_high_detail_impl_snippet_contains_module(self, sample_task: dict[str, Any]) -> None:
        """Test high detail impl snippet contains module structure."""
        generator = StepGenerator()
        steps = generator.generate(sample_task, DetailLevel.HIGH)

        implement_step = steps[2]
        snippet = implement_step.code_snippet
        assert "from __future__" in snippet or "class " in snippet or "def " in snippet

    def test_test_file_path_generation_python(self, sample_task: dict[str, Any]) -> None:
        """Test Python test file path generation."""
        generator = StepGenerator()
        steps = generator.generate(sample_task, DetailLevel.MEDIUM)

        write_test_step = steps[0]
        assert write_test_step.file is not None
        assert write_test_step.file.endswith(".py")
        assert "test_" in write_test_step.file

    def test_impl_file_path_from_task(self, sample_task: dict[str, Any]) -> None:
        """Test implementation file path from task."""
        generator = StepGenerator()
        steps = generator.generate(sample_task, DetailLevel.MEDIUM)

        implement_step = steps[2]
        assert implement_step.file == "zerg/auth.py"

    def test_verification_command_from_task(self, sample_task: dict[str, Any]) -> None:
        """Test verification command comes from task."""
        generator = StepGenerator()
        steps = generator.generate(sample_task, DetailLevel.MEDIUM)

        verify_fail_step = steps[1]
        verify_pass_step = steps[3]

        assert verify_fail_step.run == "pytest tests/unit/test_auth.py -v"
        assert verify_pass_step.run == "pytest tests/unit/test_auth.py -v"

    def test_default_verification_command(self, task_with_modify: dict[str, Any]) -> None:
        """Test default verification command when not specified."""
        generator = StepGenerator()
        steps = generator.generate(task_with_modify, DetailLevel.MEDIUM)

        verify_step = steps[1]
        assert "pytest" in verify_step.run

    def test_generate_steps_dict(self, sample_task: dict[str, Any]) -> None:
        """Test generate_steps_dict returns list of dicts."""
        generator = StepGenerator()
        steps_dict = generator.generate_steps_dict(sample_task, DetailLevel.MEDIUM)

        assert isinstance(steps_dict, list)
        assert len(steps_dict) == 6
        for step in steps_dict:
            assert isinstance(step, dict)
            assert "step" in step
            assert "action" in step
            assert "verify" in step


class TestStepGeneratorFormatterDetection:
    """Tests for StepGenerator formatter detection."""

    def test_format_step_uses_detected_formatter(self, tmp_path: Path) -> None:
        """Test format step uses detected formatter from pyproject.toml."""
        # Create pyproject.toml with ruff config
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.ruff]\nline-length = 88\n")

        generator = StepGenerator(project_root=tmp_path)
        task = {
            "id": "TEST-001",
            "title": "Test task",
            "files": {"create": ["foo.py"]},
        }
        steps = generator.generate(task, DetailLevel.MEDIUM)

        format_step = steps[4]
        assert "ruff format" in format_step.run

    def test_format_step_detects_black(self, tmp_path: Path) -> None:
        """Test format step detects black formatter."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.black]\nline-length = 88\n")

        generator = StepGenerator(project_root=tmp_path)
        task = {
            "id": "TEST-001",
            "title": "Test task",
            "files": {"create": ["foo.py"]},
        }
        steps = generator.generate(task, DetailLevel.MEDIUM)

        format_step = steps[4]
        assert "black" in format_step.run

    def test_format_step_detects_prettier(self, tmp_path: Path) -> None:
        """Test format step detects prettier formatter."""
        prettierrc = tmp_path / ".prettierrc"
        prettierrc.write_text("{}\n")

        generator = StepGenerator(project_root=tmp_path)
        task = {
            "id": "TEST-001",
            "title": "Test task",
            "files": {"create": ["foo.js"]},
        }
        steps = generator.generate(task, DetailLevel.MEDIUM)

        format_step = steps[4]
        assert "prettier" in format_step.run

    def test_format_step_fallback_to_ruff(self, tmp_path: Path) -> None:
        """Test format step falls back to ruff when no formatter detected."""
        generator = StepGenerator(project_root=tmp_path)
        task = {
            "id": "TEST-001",
            "title": "Test task",
            "files": {"create": ["foo.py"]},
        }
        steps = generator.generate(task, DetailLevel.MEDIUM)

        format_step = steps[4]
        assert "ruff format" in format_step.run


class TestStepGeneratorTestFilePaths:
    """Tests for test file path generation."""

    def test_python_test_file_path(self) -> None:
        """Test Python test file path generation."""
        generator = StepGenerator()
        test_file = generator._get_test_file("zerg/foo.py")
        assert test_file == "tests/unit/test_foo.py"

    def test_typescript_test_file_path(self) -> None:
        """Test TypeScript test file path generation."""
        generator = StepGenerator()
        test_file = generator._get_test_file("src/components/Button.tsx")
        assert test_file == "src/components/__tests__/Button.test.tsx"

    def test_javascript_test_file_path(self) -> None:
        """Test JavaScript test file path generation."""
        generator = StepGenerator()
        test_file = generator._get_test_file("src/utils/helper.js")
        assert test_file == "src/utils/__tests__/helper.test.js"


class TestConvenienceFunction:
    """Tests for generate_steps_for_task convenience function."""

    def test_generate_steps_for_task_standard(self) -> None:
        """Test convenience function with standard detail."""
        task = {"id": "TEST-001", "title": "Test"}
        steps = generate_steps_for_task(task, "standard")
        assert steps == []

    def test_generate_steps_for_task_medium(self) -> None:
        """Test convenience function with medium detail."""
        task = {
            "id": "TEST-001",
            "title": "Test",
            "files": {"create": ["foo.py"]},
        }
        steps = generate_steps_for_task(task, "medium")
        assert len(steps) == 6
        assert all(isinstance(s, dict) for s in steps)

    def test_generate_steps_for_task_with_project_root(self, tmp_path: Path) -> None:
        """Test convenience function with project_root."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.ruff]\n")

        task = {
            "id": "TEST-001",
            "title": "Test",
            "files": {"create": ["foo.py"]},
        }
        steps = generate_steps_for_task(task, "medium", project_root=tmp_path)
        assert len(steps) == 6
