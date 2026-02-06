"""Tests for ZERG StepGenerator module."""

from unittest.mock import MagicMock

import pytest

from zerg.step_generator import (
    DetailLevel,
    Step,
    StepAction,
    StepGenerator,
    TaskDefinition,
    VerifyMode,
    generate_steps_for_task,
)


class TestEnums:
    """Tests for DetailLevel, StepAction, and VerifyMode enums."""

    @pytest.mark.parametrize(
        "member,value",
        [
            (DetailLevel.STANDARD, "standard"),
            (DetailLevel.MEDIUM, "medium"),
            (DetailLevel.HIGH, "high"),
        ],
    )
    def test_detail_level_values(self, member, value):
        """DetailLevel members have correct values."""
        assert member.value == value
        assert DetailLevel(value) == member

    def test_step_action_values(self):
        """All TDD actions have correct values."""
        assert StepAction.WRITE_TEST.value == "write_test"
        assert StepAction.VERIFY_FAIL.value == "verify_fail"
        assert StepAction.IMPLEMENT.value == "implement"
        assert StepAction.VERIFY_PASS.value == "verify_pass"
        assert StepAction.FORMAT.value == "format"
        assert StepAction.COMMIT.value == "commit"

    def test_verify_mode_values(self):
        """All verify modes have correct values."""
        assert VerifyMode.EXIT_CODE.value == "exit_code"
        assert VerifyMode.EXIT_CODE_NONZERO.value == "exit_code_nonzero"
        assert VerifyMode.NONE.value == "none"


class TestStep:
    """Tests for Step dataclass."""

    def test_create_minimal(self):
        """Step can be created with minimal fields."""
        step = Step(step=1, action=StepAction.WRITE_TEST)
        assert step.file is None
        assert step.verify == VerifyMode.EXIT_CODE

    def test_to_dict_full(self):
        """to_dict with all fields produces correct output."""
        step = Step(
            step=3,
            action=StepAction.IMPLEMENT,
            file="zerg/foo.py",
            code_snippet="class Foo: pass",
            run="pytest tests/",
            verify=VerifyMode.EXIT_CODE_NONZERO,
        )
        result = step.to_dict()
        assert result["step"] == 3
        assert result["action"] == "implement"
        assert result["file"] == "zerg/foo.py"
        assert result["verify"] == "exit_code_nonzero"


class TestTaskDefinition:
    """Tests for TaskDefinition dataclass."""

    def test_create_minimal(self):
        """TaskDefinition with minimal fields has defaults."""
        task = TaskDefinition(id="TEST-001", title="Test Task")
        assert task.description == ""
        assert task.files == {}

    def test_from_dict(self):
        """TaskDefinition can be created from dictionary."""
        data = {
            "id": "TEST-002",
            "title": "Dict Task",
            "description": "From dict",
            "files": {"create": ["new.py"]},
            "verification": {"command": "python -m pytest"},
        }
        task = TaskDefinition.from_dict(data)
        assert task.id == "TEST-002"
        assert task.files["create"] == ["new.py"]


class TestStepGeneratorInit:
    """Tests for StepGenerator initialization."""

    def test_default_project_root(self, tmp_path, monkeypatch):
        """Default project root is current directory."""
        monkeypatch.chdir(tmp_path)
        gen = StepGenerator()
        assert gen.project_root == tmp_path

    def test_with_ast_analyzer(self, tmp_path):
        """AST analyzer is stored when provided."""
        mock_analyzer = MagicMock()
        gen = StepGenerator(project_root=tmp_path, ast_analyzer=mock_analyzer)
        assert gen.ast_analyzer is mock_analyzer


class TestStepGeneratorGeneration:
    """Tests for step generation at different detail levels."""

    def test_standard_returns_empty(self, tmp_path):
        """Standard detail returns empty step list."""
        gen = StepGenerator(project_root=tmp_path)
        task = TaskDefinition(id="TEST-001", title="Test")
        assert gen.generate_steps(task, DetailLevel.STANDARD) == []

    def test_medium_returns_six_tdd_steps(self, tmp_path):
        """Medium detail returns 6 TDD steps in correct order without snippets."""
        gen = StepGenerator(project_root=tmp_path)
        task = TaskDefinition(id="TEST-001", title="Test", files={"create": ["zerg/foo.py"]})
        steps = gen.generate_steps(task, DetailLevel.MEDIUM)

        assert len(steps) == 6
        expected_order = [
            StepAction.WRITE_TEST,
            StepAction.VERIFY_FAIL,
            StepAction.IMPLEMENT,
            StepAction.VERIFY_PASS,
            StepAction.FORMAT,
            StepAction.COMMIT,
        ]
        for i, step in enumerate(steps):
            assert step.action == expected_order[i]
            assert step.code_snippet is None

        assert steps[1].verify == VerifyMode.EXIT_CODE_NONZERO
        assert steps[3].verify == VerifyMode.EXIT_CODE

    def test_high_includes_code_snippets(self, tmp_path):
        """High detail includes code snippets for write_test and implement."""
        gen = StepGenerator(project_root=tmp_path)
        task = TaskDefinition(
            id="TEST-001",
            title="Test Feature",
            description="Implement test feature",
            files={"create": ["zerg/foo.py"]},
        )
        steps = gen.generate_steps(task, DetailLevel.HIGH)
        assert len(steps) == 6
        assert steps[0].code_snippet is not None
        assert steps[2].code_snippet is not None


class TestStepGeneratorFormatterIntegration:
    """Tests for formatter detection integration."""

    def test_format_step_uses_detected_formatter(self, tmp_path):
        """Format step uses detected formatter command."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.ruff]\nline-length = 88")

        gen = StepGenerator(project_root=tmp_path)
        task = TaskDefinition(id="TEST-001", title="Test", files={"create": ["zerg/foo.py"]})
        steps = gen.generate_steps(task, DetailLevel.MEDIUM)
        assert "ruff format" in steps[4].run


class TestStepGeneratorFileInference:
    """Tests for test/impl file inference."""

    def test_infers_test_and_impl_files(self, tmp_path):
        """Infers test file from impl and sets impl on implement step."""
        gen = StepGenerator(project_root=tmp_path)
        task = TaskDefinition(id="TEST-001", title="Test", files={"create": ["zerg/my_module.py"]})
        steps = gen.generate_steps(task, DetailLevel.MEDIUM)
        assert "test_my_module" in steps[0].file
        assert steps[2].file == "zerg/my_module.py"


class TestStepGeneratorVerification:
    """Tests for verification command integration."""

    def test_uses_task_verification_command(self, tmp_path):
        """Uses verification command from task definition."""
        gen = StepGenerator(project_root=tmp_path)
        task = TaskDefinition(
            id="TEST-001",
            title="Test",
            files={"create": ["zerg/foo.py"]},
            verification={"command": "python -m pytest tests/ -v"},
        )
        steps = gen.generate_steps(task, DetailLevel.MEDIUM)
        assert steps[1].run == "python -m pytest tests/ -v"
        assert steps[3].run == "python -m pytest tests/ -v"


class TestStepGeneratorHelpers:
    """Tests for helper methods."""

    def test_snake_and_pascal_case(self):
        """snake_case and pascal_case convert correctly."""
        assert StepGenerator._snake_case("Hello World") == "hello_world"
        assert StepGenerator._pascal_case("hello-world-test") == "HelloWorldTest"


class TestConvenienceFunction:
    """Tests for generate_steps_for_task function."""

    def test_returns_list_of_dicts(self, tmp_path, monkeypatch):
        """Convenience function returns list of dictionaries."""
        monkeypatch.chdir(tmp_path)
        task = {"id": "TEST-001", "title": "Test", "files": {"create": ["zerg/foo.py"]}}
        result = generate_steps_for_task(task, "medium")
        assert isinstance(result, list)
        assert all(isinstance(s, dict) for s in result)
        assert len(result) == 6


class TestASTAnalyzerIntegration:
    """Tests for AST analyzer integration."""

    def test_ast_analyzer_exception_handled(self, tmp_path):
        """Handles exceptions from AST analyzer gracefully."""
        mock_analyzer = MagicMock()
        mock_analyzer.extract_patterns.side_effect = Exception("Parse error")

        gen = StepGenerator(project_root=tmp_path, ast_analyzer=mock_analyzer)
        task = TaskDefinition(id="TEST-001", title="Test", files={"create": ["zerg/foo.py"]})
        steps = gen.generate_steps(task, DetailLevel.HIGH)
        assert len(steps) == 6
        assert steps[0].code_snippet is not None
