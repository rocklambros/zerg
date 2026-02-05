"""Integration tests for command authoring flow.

Tests the full authoring lifecycle: scaffold -> validate -> document.
Verifies ScaffoldGenerator and DocGenerator work together correctly.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from zerg.validate_commands import (
    DEFAULT_COMMANDS_DIR,
    DocGenerator,
    ScaffoldGenerator,
    validate_required_sections,
    validate_task_references,
)


class TestAuthoringFlow:
    """Integration tests for scaffold -> validate -> document flow."""

    @pytest.fixture
    def temp_workspace(self, tmp_path: Path) -> dict[str, Path]:
        """Create temporary workspace with template.

        Sets up a minimal workspace with:
        - commands/ directory with _template.md copied from real project
        - docs/commands/ directory for generated documentation
        - docs/commands-quick.md index file
        """
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()

        # Copy template from real project
        template_src = Path("zerg/data/commands/_template.md")
        if template_src.exists():
            shutil.copy(template_src, commands_dir / "_template.md")
        else:
            # Fallback: create minimal template for test isolation
            (commands_dir / "_template.md").write_text(
                "# ZERG {CommandName}\n\n"
                "{Short description of the command's purpose.}\n\n"
                "## Pre-flight\n\n"
                "```bash\n# checks\n```\n\n"
                "## Task Tracking\n\n"
                "Call TaskCreate:\n"
                '  - subject: "[{CommandName}] action"\n\n'
                "Immediately call TaskUpdate:\n"
                '  - status: "in_progress"\n\n'
                "On completion, call TaskUpdate:\n"
                '  - status: "completed"\n\n'
                "## Help\n\n"
                "```\n/zerg:{command-name} -- help text\n```\n"
            )

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        commands_docs_dir = docs_dir / "commands"
        commands_docs_dir.mkdir()

        # Create minimal index
        (docs_dir / "commands.md").write_text("# ZERG Command Reference\n\n## Table of Contents\n\n")

        return {"commands": commands_dir, "docs": docs_dir}

    def test_scaffold_produces_valid_command(self, temp_workspace: dict[str, Path]) -> None:
        """Scaffolded command passes validation."""
        gen = ScaffoldGenerator(commands_dir=temp_workspace["commands"])
        result = gen.scaffold("test-cmd", description="Test command")

        assert result.exists()
        assert result.name == "test-cmd.md"

        # Should have task references
        passed, errors = validate_task_references(temp_workspace["commands"])
        test_errors = [e for e in errors if "test-cmd" in e]
        assert not test_errors, f"Generated command failed validation: {test_errors}"

    def test_scaffold_with_custom_flags(self, temp_workspace: dict[str, Path]) -> None:
        """Scaffolded command with custom flags includes flag table."""
        gen = ScaffoldGenerator(commands_dir=temp_workspace["commands"])
        flags = [
            {"name": "--verbose", "default": "false", "description": "Enable verbose output"},
            {"name": "--count", "default": "1", "description": "Number of iterations"},
        ]
        result = gen.scaffold("flagged-cmd", description="Command with flags", flags=flags)

        content = result.read_text()
        assert "--verbose" in content
        assert "--count" in content
        assert "Enable verbose output" in content

    def test_scaffold_rejects_duplicate_name(self, temp_workspace: dict[str, Path]) -> None:
        """Scaffolding fails if command already exists."""
        gen = ScaffoldGenerator(commands_dir=temp_workspace["commands"])
        gen.scaffold("duplicate-cmd", description="First version")

        with pytest.raises(FileExistsError):
            gen.scaffold("duplicate-cmd", description="Second version")

    def test_scaffold_rejects_missing_template(self, tmp_path: Path) -> None:
        """Scaffolding fails if template file is missing."""
        empty_commands_dir = tmp_path / "empty_commands"
        empty_commands_dir.mkdir()

        gen = ScaffoldGenerator(commands_dir=empty_commands_dir)

        with pytest.raises(FileNotFoundError):
            gen.scaffold("no-template", description="Missing template")

    def test_doc_generator_creates_docs(self, temp_workspace: dict[str, Path]) -> None:
        """DocGenerator creates documentation files."""
        # First scaffold a command
        scaffold = ScaffoldGenerator(commands_dir=temp_workspace["commands"])
        scaffold.scaffold("my-cmd", description="My command description")

        # Then generate docs
        doc_gen = DocGenerator(
            commands_dir=temp_workspace["commands"],
            docs_dir=temp_workspace["docs"],
        )

        # This should create the doc file
        doc_path = doc_gen.generate_command_doc("my-cmd")
        assert doc_path.exists()

        content = doc_path.read_text()
        assert "my-cmd" in content.lower() or "MyCmd" in content

    def test_doc_generator_extracts_help_text(self, temp_workspace: dict[str, Path]) -> None:
        """DocGenerator extracts help section from command file."""
        # Create a command with known help text
        scaffold = ScaffoldGenerator(commands_dir=temp_workspace["commands"])
        cmd_path = scaffold.scaffold("help-cmd", description="Command with help")

        # Verify the command was created with a Help section
        content = cmd_path.read_text()
        assert "## Help" in content

        doc_gen = DocGenerator(
            commands_dir=temp_workspace["commands"],
            docs_dir=temp_workspace["docs"],
        )

        help_text = doc_gen.extract_help_text(cmd_path)
        # Should extract something from the Help section
        assert isinstance(help_text, str)

    def test_doc_generator_updates_index(self, temp_workspace: dict[str, Path]) -> None:
        """DocGenerator updates wiki index with new command entry."""
        scaffold = ScaffoldGenerator(commands_dir=temp_workspace["commands"])
        scaffold.scaffold("indexed-cmd", description="Indexed command")

        doc_gen = DocGenerator(
            commands_dir=temp_workspace["commands"],
            docs_dir=temp_workspace["docs"],
        )

        doc_gen.update_wiki_index("indexed-cmd", "An indexed command description")

        index_content = (temp_workspace["docs"] / "commands-quick.md").read_text()
        assert "indexed-cmd" in index_content
        assert "An indexed command description" in index_content

    def test_full_flow_scaffold_to_docs(self, temp_workspace: dict[str, Path]) -> None:
        """Full flow: scaffold -> validate -> generate docs."""
        # Step 1: Scaffold
        scaffold = ScaffoldGenerator(commands_dir=temp_workspace["commands"])
        cmd_path = scaffold.scaffold("full-test", description="Full test command")
        assert cmd_path.exists()

        # Step 2: Validate task references
        passed, errors = validate_task_references(temp_workspace["commands"])
        test_errors = [e for e in errors if "full-test" in e]
        assert not test_errors, f"Validation errors: {test_errors}"

        # Step 3: Generate docs
        doc_gen = DocGenerator(
            commands_dir=temp_workspace["commands"],
            docs_dir=temp_workspace["docs"],
        )
        doc_path = doc_gen.generate_command_doc("full-test")
        assert doc_path.exists()

        # Step 4: Update index
        doc_gen.update_wiki_index("full-test", "Full test command")
        index_content = (temp_workspace["docs"] / "commands-quick.md").read_text()
        assert "full-test" in index_content


class TestCreateCommandFile:
    """Tests for the create-command.md file itself."""

    def test_create_command_exists(self) -> None:
        """create-command.md exists."""
        path = Path("zerg/data/commands/create-command.md")
        assert path.exists(), "create-command.md not found in expected location"

    def test_create_command_has_sections(self) -> None:
        """create-command.md has required sections."""
        path = Path("zerg/data/commands/create-command.md")
        content = path.read_text()

        # Check for Pre-Flight section (case-insensitive variants)
        assert "## Pre-Flight" in content or "## Pre-flight" in content, "Missing Pre-Flight section"

        # Check for Task Tracking section
        assert "## Task Tracking" in content, "Missing Task Tracking section"

        # Check for Help section
        assert "## Help" in content, "Missing Help section"

    def test_create_command_has_task_references(self) -> None:
        """create-command.md contains Task ecosystem markers."""
        path = Path("zerg/data/commands/create-command.md")
        content = path.read_text()

        # Should have TaskCreate reference
        assert "TaskCreate" in content, "Missing TaskCreate reference"

        # Should have TaskUpdate references
        assert "TaskUpdate" in content, "Missing TaskUpdate reference"

        # Should have status transitions
        assert "in_progress" in content, "Missing in_progress status transition"
        assert "completed" in content, "Missing completed status transition"

    def test_create_command_passes_validation(self) -> None:
        """create-command.md passes task reference validation."""
        passed, errors = validate_task_references(DEFAULT_COMMANDS_DIR)
        create_cmd_errors = [e for e in errors if "create-command" in e]
        assert not create_cmd_errors, f"Validation failed: {create_cmd_errors}"

    def test_create_command_passes_section_validation(self) -> None:
        """create-command.md passes required sections validation."""
        passed, errors = validate_required_sections(DEFAULT_COMMANDS_DIR)
        create_cmd_errors = [e for e in errors if "create-command" in e]
        assert not create_cmd_errors, f"Section validation failed: {create_cmd_errors}"


class TestTemplateFile:
    """Tests for the _template.md file."""

    def test_template_exists(self) -> None:
        """_template.md exists in commands directory."""
        path = DEFAULT_COMMANDS_DIR / "_template.md"
        assert path.exists(), "_template.md not found"

    def test_template_has_placeholders(self) -> None:
        """Template contains expected placeholder patterns."""
        path = DEFAULT_COMMANDS_DIR / "_template.md"
        content = path.read_text()

        # Should have CommandName placeholder for title
        assert "{CommandName}" in content, "Missing {CommandName} placeholder"

        # Should have command-name placeholder for usage
        assert "{command-name}" in content, "Missing {command-name} placeholder"

    def test_template_has_required_sections(self) -> None:
        """Template includes all required sections."""
        path = DEFAULT_COMMANDS_DIR / "_template.md"
        content = path.read_text()

        # Check for required sections
        assert "## Pre-flight" in content or "## Pre-Flight" in content
        assert "## Task Tracking" in content
        assert "## Help" in content

    def test_template_has_task_lifecycle_pattern(self) -> None:
        """Template includes complete Task lifecycle pattern."""
        path = DEFAULT_COMMANDS_DIR / "_template.md"
        content = path.read_text()

        # Must have TaskCreate with subject
        assert "TaskCreate" in content
        assert "subject:" in content

        # Must have in_progress and completed transitions
        assert "in_progress" in content
        assert "completed" in content
