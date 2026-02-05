"""Unit tests for command authoring functions."""

import shutil
from pathlib import Path

import pytest


class TestScaffoldGenerator:
    """Tests for ScaffoldGenerator class."""

    def test_import(self) -> None:
        """ScaffoldGenerator can be imported."""
        from zerg.validate_commands import ScaffoldGenerator

        assert ScaffoldGenerator is not None

    def test_scaffold_creates_file(self, tmp_path: Path) -> None:
        """scaffold() creates command file."""
        from zerg.validate_commands import ScaffoldGenerator

        # Copy template to temp dir
        template_src = Path("zerg/data/commands/_template.md")
        template_dst = tmp_path / "_template.md"
        shutil.copy(template_src, template_dst)

        gen = ScaffoldGenerator(commands_dir=tmp_path)
        result = gen.scaffold("test-command", description="A test command")

        assert result.exists()
        assert result.name == "test-command.md"

    def test_scaffold_replaces_placeholders(self, tmp_path: Path) -> None:
        """scaffold() replaces template placeholders."""
        from zerg.validate_commands import ScaffoldGenerator

        template_src = Path("zerg/data/commands/_template.md")
        template_dst = tmp_path / "_template.md"
        shutil.copy(template_src, template_dst)

        gen = ScaffoldGenerator(commands_dir=tmp_path)
        result = gen.scaffold("my-command", description="My description")

        content = result.read_text()
        assert "MyCommand" in content  # PascalCase conversion
        assert "my-command" in content
        assert "{CommandName}" not in content  # Placeholder replaced

    def test_scaffold_raises_if_template_missing(self, tmp_path: Path) -> None:
        """scaffold() raises FileNotFoundError if template doesn't exist."""
        from zerg.validate_commands import ScaffoldGenerator

        gen = ScaffoldGenerator(commands_dir=tmp_path)

        with pytest.raises(FileNotFoundError):
            gen.scaffold("test-command")

    def test_scaffold_raises_if_file_exists(self, tmp_path: Path) -> None:
        """scaffold() raises FileExistsError if command file already exists."""
        from zerg.validate_commands import ScaffoldGenerator

        # Copy template
        template_src = Path("zerg/data/commands/_template.md")
        template_dst = tmp_path / "_template.md"
        shutil.copy(template_src, template_dst)

        # Create existing file
        existing = tmp_path / "existing-command.md"
        existing.write_text("# Already exists")

        gen = ScaffoldGenerator(commands_dir=tmp_path)

        with pytest.raises(FileExistsError):
            gen.scaffold("existing-command")

    def test_scaffold_with_flags(self, tmp_path: Path) -> None:
        """scaffold() generates flags table when flags provided."""
        from zerg.validate_commands import ScaffoldGenerator

        template_src = Path("zerg/data/commands/_template.md")
        template_dst = tmp_path / "_template.md"
        shutil.copy(template_src, template_dst)

        gen = ScaffoldGenerator(commands_dir=tmp_path)
        flags = [
            {"name": "--workers", "default": "5", "description": "Number of workers"},
            {"name": "--verbose", "default": "false", "description": "Enable verbose output"},
        ]
        result = gen.scaffold("flagged-command", description="Command with flags", flags=flags)

        content = result.read_text()
        assert "--workers" in content
        assert "--verbose" in content
        assert "Number of workers" in content

    def test_scaffold_replaces_description(self, tmp_path: Path) -> None:
        """scaffold() replaces description placeholder."""
        from zerg.validate_commands import ScaffoldGenerator

        template_src = Path("zerg/data/commands/_template.md")
        template_dst = tmp_path / "_template.md"
        shutil.copy(template_src, template_dst)

        gen = ScaffoldGenerator(commands_dir=tmp_path)
        result = gen.scaffold("desc-command", description="Custom description for testing")

        content = result.read_text()
        assert "Custom description for testing" in content
        assert "{Short description of the command's purpose.}" not in content


class TestValidateRequiredSections:
    """Tests for validate_required_sections function."""

    def test_import(self) -> None:
        """Function can be imported."""
        from zerg.validate_commands import validate_required_sections

        assert validate_required_sections is not None

    def test_detects_missing_sections(self, tmp_path: Path) -> None:
        """Detects when required sections are missing."""
        from zerg.validate_commands import validate_required_sections

        # Create minimal file missing sections
        (tmp_path / "bad-command.md").write_text("# Bad Command\n\nNo sections here.")

        # Use strict=True to test detection behavior (default is warn-only)
        passed, errors = validate_required_sections(tmp_path, strict=True)
        assert not passed
        assert any("bad-command" in e for e in errors)

    def test_passes_with_all_sections(self, tmp_path: Path) -> None:
        """Passes when all required sections present."""
        from zerg.validate_commands import validate_required_sections

        content = """# Good Command

## Pre-Flight

Check stuff.

## Task Tracking

Track stuff.

## Help

Help stuff.
"""
        (tmp_path / "good-command.md").write_text(content)

        passed, errors = validate_required_sections(tmp_path)
        assert passed
        assert not errors

    def test_accepts_section_variants(self, tmp_path: Path) -> None:
        """Accepts various section header formats."""
        from zerg.validate_commands import validate_required_sections

        # Test with alternative header names
        content = """# Variant Command

## Pre-flight

Pre-flight checks.

## Track in Claude Task System

Task tracking here.

## Help

Help text.
"""
        (tmp_path / "variant-command.md").write_text(content)

        passed, errors = validate_required_sections(tmp_path)
        assert passed
        assert not errors


class TestValidateTaskPatterns:
    """Tests for validate_task_patterns function."""

    def test_import(self) -> None:
        """Function can be imported."""
        from zerg.validate_commands import validate_task_patterns

        assert validate_task_patterns is not None

    def test_detects_missing_lifecycle_patterns(self, tmp_path: Path) -> None:
        """Detects missing Task lifecycle patterns."""
        from zerg.validate_commands import validate_task_patterns

        content = """# Incomplete Command

## Pre-Flight

Check stuff.

## Task Tracking

Some text without proper patterns.

## Help

Help text.
"""
        (tmp_path / "incomplete.md").write_text(content)

        passed, errors = validate_task_patterns(tmp_path)
        assert not passed
        assert len(errors) > 0

    def test_passes_with_full_lifecycle(self, tmp_path: Path) -> None:
        """Passes when full Task lifecycle is present."""
        from zerg.validate_commands import validate_task_patterns

        content = """# Complete Command

## Pre-Flight

Check stuff.

## Task Tracking

TaskCreate:
  - subject: "[Test] Test action"

Then TaskUpdate status: "in_progress"

On completion TaskUpdate status: "completed"

## Help

Help text.
"""
        (tmp_path / "complete.md").write_text(content)

        passed, errors = validate_task_patterns(tmp_path)
        assert passed
        assert not errors


class TestDocGenerator:
    """Tests for DocGenerator class."""

    def test_import(self) -> None:
        """DocGenerator can be imported."""
        from zerg.validate_commands import DocGenerator

        assert DocGenerator is not None

    def test_extract_help_text(self, tmp_path: Path) -> None:
        """extract_help_text extracts help block."""
        from zerg.validate_commands import DocGenerator

        # Create file with help section
        cmd_file = tmp_path / "test.md"
        cmd_file.write_text(
            """# Test

## Help

```
test-command -- A test command.

Flags:
  --help    Show help
```
"""
        )

        gen = DocGenerator(commands_dir=tmp_path, docs_dir=tmp_path)
        help_text = gen.extract_help_text(cmd_file)

        assert "test-command" in help_text
        assert "--help" in help_text

    def test_extract_help_text_empty_when_missing(self, tmp_path: Path) -> None:
        """extract_help_text returns empty string when no help section."""
        from zerg.validate_commands import DocGenerator

        cmd_file = tmp_path / "no-help.md"
        cmd_file.write_text("# No Help\n\nJust content.")

        gen = DocGenerator(commands_dir=tmp_path, docs_dir=tmp_path)
        help_text = gen.extract_help_text(cmd_file)

        assert help_text == ""

    def test_extract_help_text_nonexistent_file(self, tmp_path: Path) -> None:
        """extract_help_text returns empty string for nonexistent file."""
        from zerg.validate_commands import DocGenerator

        gen = DocGenerator(commands_dir=tmp_path, docs_dir=tmp_path)
        help_text = gen.extract_help_text(tmp_path / "nonexistent.md")

        assert help_text == ""

    def test_generate_command_doc(self, tmp_path: Path) -> None:
        """generate_command_doc creates documentation file."""
        from zerg.validate_commands import DocGenerator

        # Create command file
        cmd_file = tmp_path / "commands" / "my-cmd.md"
        cmd_file.parent.mkdir(parents=True, exist_ok=True)
        cmd_file.write_text(
            """# /zerg:my-cmd

This is the description.

## Usage

```bash
/zerg:my-cmd [--flag]
```

## Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--flag` | `false` | A flag |

## Help

```
my-cmd -- My command.

Flags:
  --flag    A flag
```
"""
        )

        docs_dir = tmp_path / "docs"
        gen = DocGenerator(commands_dir=cmd_file.parent, docs_dir=docs_dir)
        result = gen.generate_command_doc("my-cmd")

        assert result.exists()
        assert result.name == "my-cmd.md"

        content = result.read_text()
        assert "/zerg:my-cmd" in content
        assert "This is the description" in content

    def test_generate_command_doc_raises_if_missing(self, tmp_path: Path) -> None:
        """generate_command_doc raises FileNotFoundError for missing command."""
        from zerg.validate_commands import DocGenerator

        gen = DocGenerator(commands_dir=tmp_path, docs_dir=tmp_path)

        with pytest.raises(FileNotFoundError):
            gen.generate_command_doc("nonexistent")

    def test_update_wiki_index(self, tmp_path: Path) -> None:
        """update_wiki_index adds entry to index file."""
        from zerg.validate_commands import DocGenerator

        docs_dir = tmp_path / "docs"
        gen = DocGenerator(commands_dir=tmp_path, docs_dir=docs_dir)

        # Call update_wiki_index (creates file if not exists)
        gen.update_wiki_index("new-cmd", "A new command")

        assert gen.index_path.exists()
        content = gen.index_path.read_text()
        assert "/zerg:new-cmd" in content
        assert "A new command" in content

    def test_update_wiki_index_updates_existing(self, tmp_path: Path) -> None:
        """update_wiki_index updates existing entry."""
        from zerg.validate_commands import DocGenerator

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)

        # Create existing index
        index_path = docs_dir / "commands-quick.md"
        index_path.write_text(
            """# ZERG Command Reference

## Table of Contents

  - [/zerg:old-cmd](#zergoldcmd) - Old description

---
"""
        )

        gen = DocGenerator(commands_dir=tmp_path, docs_dir=docs_dir)
        gen.update_wiki_index("old-cmd", "Updated description")

        content = index_path.read_text()
        assert "Updated description" in content
