"""Pressure tests for /zerg:create-command command."""

from pathlib import Path

import pytest

COMMAND_FILE = Path("zerg/data/commands/create-command.md")


class TestCreateCommand:
    """Verify /zerg:create-command command behavior."""

    def test_command_file_exists(self):
        """Command file must exist."""
        assert COMMAND_FILE.exists(), f"Command file not found: {COMMAND_FILE}"

    def test_passes_validation(self):
        """Command must pass validate_commands checks."""
        from zerg.validate_commands import DEFAULT_COMMANDS_DIR, validate_task_references

        passed, errors = validate_task_references(DEFAULT_COMMANDS_DIR)
        # Filter to just this command
        relevant = [e for e in errors if "create-command" in e]
        assert not relevant, f"Validation errors: {relevant}"

    def test_has_required_sections(self):
        """Command must have Pre-Flight, Task Tracking, Help."""
        content = COMMAND_FILE.read_text()
        assert "## Pre-Flight" in content or "## Pre-flight" in content, "Missing Pre-Flight section"
        assert "## Task Tracking" in content, "Missing Task Tracking section"
        assert "## Help" in content, "Missing Help section"

    def test_has_task_patterns(self):
        """Command must have TaskCreate and TaskUpdate patterns."""
        content = COMMAND_FILE.read_text()
        assert "TaskCreate:" in content, "Missing TaskCreate"
        assert "in_progress" in content, "Missing in_progress status"
        assert "completed" in content, "Missing completed status"

    @pytest.mark.skip(reason="Pressure test - requires manual verification")
    def test_scaffold_creates_valid_command(self):
        """Verify scaffolded command passes validation."""
        # TODO: Test that ScaffoldGenerator output passes validation
        pass

    @pytest.mark.skip(reason="Pressure test - requires manual verification")
    def test_interactive_mode_prompts(self):
        """Verify interactive mode prompts for input."""
        # TODO: Test interactive mode behavior
        pass
