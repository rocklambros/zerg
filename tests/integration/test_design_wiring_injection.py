"""Integration tests for wiring task injection in /zerg:design.

Verifies that task graphs include the mandatory wiring verification task
in Level 5 and that the verification command format is correct.
"""

from pathlib import Path

import pytest


class TestWiringTaskInjectionInstructions:
    """Tests for wiring task injection instructions in design.core.md."""

    @pytest.fixture
    def design_core_content(self) -> str:
        """Read design.core.md content."""
        design_core_path = Path("zerg/data/commands/design.core.md")
        return design_core_path.read_text()

    def test_wiring_task_section_exists(self, design_core_content: str) -> None:
        """design.core.md contains wiring verification section."""
        assert "Mandatory Wiring Verification Task" in design_core_content

    def test_wiring_task_title_documented(self, design_core_content: str) -> None:
        """Wiring task title is documented."""
        assert "Run wiring verification" in design_core_content

    def test_validate_commands_in_verification(self, design_core_content: str) -> None:
        """Verification command includes validate_commands."""
        assert "python -m zerg.validate_commands" in design_core_content

    def test_pytest_in_verification(self, design_core_content: str) -> None:
        """Verification command includes pytest with timeout."""
        assert "pytest" in design_core_content
        assert "--timeout=60" in design_core_content

    def test_level_5_quality_documented(self, design_core_content: str) -> None:
        """Level 5 quality-wiring is documented."""
        assert "quality-wiring" in design_core_content
        assert '"level": 5' in design_core_content or "level 5" in design_core_content.lower()

    def test_dependency_wiring_rules_documented(self, design_core_content: str) -> None:
        """Dependency wiring rules are documented."""
        assert "L4 TASK IDs" in design_core_content or "Level 4" in design_core_content

    def test_no_consumers_documented(self, design_core_content: str) -> None:
        """Empty consumers (leaf task) is documented."""
        assert '"consumers": []' in design_core_content


class TestWiringTaskFormat:
    """Tests for wiring task JSON format in instructions."""

    @pytest.fixture
    def design_core_content(self) -> str:
        """Read design.core.md content."""
        design_core_path = Path("zerg/data/commands/design.core.md")
        return design_core_path.read_text()

    def test_task_template_has_required_fields(self, design_core_content: str) -> None:
        """Task template includes all required fields."""
        required_patterns = [
            '"id":',
            '"title":',
            '"description":',
            '"phase":',
            '"level":',
            '"dependencies":',
            '"files":',
            '"verification":',
            '"consumers":',
        ]

        # Find the wiring task template section
        assert "Task Template" in design_core_content

        for pattern in required_patterns:
            assert pattern in design_core_content, f"Missing {pattern} in task template"

    def test_verification_timeout_documented(self, design_core_content: str) -> None:
        """Verification timeout of 120 seconds is documented."""
        assert '"timeout_seconds": 120' in design_core_content

    def test_phase_is_quality(self, design_core_content: str) -> None:
        """Wiring task phase is 'quality'."""
        assert '"phase": "quality"' in design_core_content


class TestValidateCommandsIntegration:
    """Tests for validate_commands integration."""

    def test_validate_commands_runnable(self) -> None:
        """validate_commands module can be run as main."""
        import subprocess

        result = subprocess.run(
            ["python", "-m", "zerg.validate_commands", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Should exit cleanly (help output) or show usage
        assert result.returncode == 0 or "usage" in result.stdout.lower() or "usage" in result.stderr.lower()

    def test_validate_commands_passes_on_current_codebase(self) -> None:
        """validate_commands passes on the current ZERG codebase."""
        import subprocess

        result = subprocess.run(
            ["python", "-m", "zerg.validate_commands"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Current codebase should pass validation
        assert result.returncode == 0, f"validate_commands failed: {result.stdout}\n{result.stderr}"


class TestTestScopeIntegration:
    """Tests for test_scope module integration."""

    def test_test_scope_importable(self) -> None:
        """test_scope module can be imported."""
        from zerg.test_scope import (
            build_pytest_path_filter,
            find_affected_tests,
            get_modified_modules,
            get_scoped_test_paths,
        )

        assert callable(get_scoped_test_paths)
        assert callable(get_modified_modules)
        assert callable(find_affected_tests)
        assert callable(build_pytest_path_filter)

    def test_test_scope_with_real_task_graph(self) -> None:
        """test_scope works with a realistic task graph."""
        from zerg.test_scope import build_pytest_path_filter

        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {
                    "id": "TASK-001",
                    "files": {
                        "create": ["zerg/new_module.py"],
                        "modify": [],
                        "read": [],
                    },
                },
                {
                    "id": "TASK-002",
                    "files": {
                        "create": ["tests/unit/test_new_module.py"],
                        "modify": [],
                        "read": [],
                    },
                },
            ],
        }

        result = build_pytest_path_filter(task_graph, Path("tests"))

        # Should include the new test file
        assert "tests/unit/test_new_module.py" in result
