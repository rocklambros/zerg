"""Tests for ZERG command splitter module."""

from pathlib import Path

import pytest

from zerg.command_splitter import CHARS_PER_TOKEN, MIN_LINES_TO_SPLIT, CommandSplitter


class TestEstimateTokens:
    """Tests for token estimation."""

    def test_estimate_tokens(self) -> None:
        """Test basic token estimation from text length."""
        splitter = CommandSplitter()

        text = "a" * 400  # 400 chars / 4 = 100 tokens
        tokens = splitter.estimate_tokens(text)

        assert tokens == 400 // CHARS_PER_TOKEN
        assert tokens == 100

    def test_estimate_tokens_empty(self) -> None:
        """Test token estimation on empty string."""
        splitter = CommandSplitter()

        assert splitter.estimate_tokens("") == 0


class TestAnalyzeFile:
    """Tests for file structure analysis."""

    def test_analyze_file(self, tmp_path: Path) -> None:
        """Test that analyze_file correctly parses markdown sections."""
        md_file = tmp_path / "zerg:test.md"
        lines = [
            "# Main Title",
            "",
            "Some introduction text.",
            "",
            "## Section One",
            "",
            "Content of section one.",
            "",
            "## Section Two",
            "",
            "Content of section two.",
            "",
            "## Section Three",
            "",
            "Content of section three with TaskCreate reference.",
        ]
        md_file.write_text("\n".join(lines))

        splitter = CommandSplitter(commands_dir=tmp_path)
        result = splitter.analyze_file(md_file)

        assert result["total_lines"] == len(lines)
        # Should detect 4 sections: Main Title, Section One, Two, Three
        assert len(result["sections"]) == 4
        assert result["sections"][0]["header"] == "Main Title"
        assert result["sections"][1]["header"] == "Section One"
        assert result["has_task_tracking"] is True
        assert "suggested_split_line" in result


class TestSplitFile:
    """Tests for file splitting."""

    def test_split_file_creates_both(self, tmp_path: Path) -> None:
        """Test that split_file creates .core.md and .details.md files."""
        md_file = tmp_path / "zerg:bigcmd.md"
        # Create a file well over MIN_LINES_TO_SPLIT
        content_lines = [f"Line {i}" for i in range(400)]
        content_lines[0] = "# Big Command"
        content_lines[50] = "## Phase One"
        content_lines[150] = "## Phase Two"
        content_lines[250] = "## Phase Three"
        md_file.write_text("\n".join(content_lines))

        splitter = CommandSplitter(commands_dir=tmp_path)
        core_path, details_path = splitter.split_file(md_file)

        assert core_path.exists()
        assert details_path.exists()
        assert core_path.name == "zerg:bigcmd.core.md"
        assert details_path.name == "zerg:bigcmd.details.md"

        # Core should be shorter than the original
        core_content = core_path.read_text()
        details_content = details_path.read_text()
        assert len(core_content) < len("\n".join(content_lines))
        assert len(details_content) > 0

    def test_short_file_not_split(self, tmp_path: Path) -> None:
        """Test that files under MIN_LINES_TO_SPLIT are not split."""
        md_file = tmp_path / "zerg:small.md"
        content_lines = [f"Line {i}" for i in range(50)]
        md_file.write_text("\n".join(content_lines))

        splitter = CommandSplitter(commands_dir=tmp_path)
        core_path, details_path = splitter.split_file(md_file)

        # When skipped, both return the original path
        assert core_path == md_file
        assert details_path == md_file


class TestLoadCommand:
    """Tests for loading command files."""

    def test_load_command_core(self, tmp_path: Path) -> None:
        """Test that load_command prefers .core.md when available."""
        # Create both the full file and the core split
        full_file = tmp_path / "zerg:example.md"
        full_file.write_text("# Full content with everything")

        core_file = tmp_path / "zerg:example.core.md"
        core_file.write_text("# Core content only")

        splitter = CommandSplitter(commands_dir=tmp_path)
        content = splitter.load_command("zerg:example")

        assert content == "# Core content only"

    def test_load_command_full_fallback(self, tmp_path: Path) -> None:
        """Test that load_command falls back to full .md when no core exists."""
        full_file = tmp_path / "zerg:example.md"
        full_file.write_text("# Full content")

        splitter = CommandSplitter(commands_dir=tmp_path)
        content = splitter.load_command("zerg:example")

        assert content == "# Full content"

    def test_load_command_not_found(self, tmp_path: Path) -> None:
        """Test that load_command raises FileNotFoundError for missing commands."""
        splitter = CommandSplitter(commands_dir=tmp_path)

        with pytest.raises(FileNotFoundError):
            splitter.load_command("zerg:nonexistent")
