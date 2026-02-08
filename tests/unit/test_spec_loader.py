"""Unit tests for SpecLoader utility."""

from pathlib import Path
from unittest.mock import patch  # noqa: F401

import pytest

from zerg.spec_loader import CHARS_PER_TOKEN, SpecContent, SpecLoader


class TestSpecLoader:
    """Tests for SpecLoader class."""

    @pytest.fixture
    def temp_gsd_dir(self, tmp_path: Path) -> Path:
        """Create a temporary GSD directory structure."""
        gsd = tmp_path / ".gsd"
        gsd.mkdir()
        specs = gsd / "specs"
        specs.mkdir()
        return gsd

    @pytest.fixture
    def loader(self, temp_gsd_dir: Path) -> SpecLoader:
        """Create a SpecLoader with temp directory."""
        return SpecLoader(gsd_dir=temp_gsd_dir)

    def test_init_default_dir(self) -> None:
        """Test initialization with default directory."""
        loader = SpecLoader()
        assert loader.gsd_dir == Path(".gsd")

    def test_init_custom_dir(self, temp_gsd_dir: Path) -> None:
        """Test initialization with custom directory."""
        loader = SpecLoader(gsd_dir=temp_gsd_dir)
        assert loader.gsd_dir == temp_gsd_dir

    def test_get_spec_dir(self, loader: SpecLoader) -> None:
        """Test get_spec_dir returns correct path."""
        spec_dir = loader.get_spec_dir("my-feature")
        assert spec_dir == loader.gsd_dir / "specs" / "my-feature"

    def test_load_feature_specs_empty(self, loader: SpecLoader) -> None:
        """Test loading specs when none exist."""
        specs = loader.load_feature_specs("nonexistent")
        assert specs.requirements == ""
        assert specs.design == ""
        assert specs.feature == "nonexistent"

    def test_load_feature_specs_requirements_only(self, loader: SpecLoader, temp_gsd_dir: Path) -> None:
        """Test loading when only requirements exist."""
        feature_dir = temp_gsd_dir / "specs" / "test-feature"
        feature_dir.mkdir(parents=True)
        (feature_dir / "requirements.md").write_text("# Requirements\n\nUser can login.")

        specs = loader.load_feature_specs("test-feature")
        assert "User can login" in specs.requirements
        assert specs.design == ""
        assert specs.feature == "test-feature"

    def test_load_feature_specs_design_only(self, loader: SpecLoader, temp_gsd_dir: Path) -> None:
        """Test loading when only design exists."""
        feature_dir = temp_gsd_dir / "specs" / "test-feature"
        feature_dir.mkdir(parents=True)
        (feature_dir / "design.md").write_text("# Design\n\nUse JWT tokens.")

        specs = loader.load_feature_specs("test-feature")
        assert specs.requirements == ""
        assert "Use JWT tokens" in specs.design

    def test_load_feature_specs_both(self, loader: SpecLoader, temp_gsd_dir: Path) -> None:
        """Test loading both requirements and design."""
        feature_dir = temp_gsd_dir / "specs" / "test-feature"
        feature_dir.mkdir(parents=True)
        (feature_dir / "requirements.md").write_text("# Requirements\n\nMust be fast.")
        (feature_dir / "design.md").write_text("# Design\n\nUse caching.")

        specs = loader.load_feature_specs("test-feature")
        assert "Must be fast" in specs.requirements
        assert "Use caching" in specs.design

    def test_load_feature_specs_uppercase(self, loader: SpecLoader, temp_gsd_dir: Path) -> None:
        """Test loading uppercase named files."""
        feature_dir = temp_gsd_dir / "specs" / "test-feature"
        feature_dir.mkdir(parents=True)
        (feature_dir / "REQUIREMENTS.md").write_text("# REQUIREMENTS")
        (feature_dir / "ARCHITECTURE.md").write_text("# ARCHITECTURE")

        specs = loader.load_feature_specs("test-feature")
        assert "REQUIREMENTS" in specs.requirements
        assert "ARCHITECTURE" in specs.design

    def test_format_context_prompt_empty(self, loader: SpecLoader) -> None:
        """Test formatting with empty content."""
        result = loader.format_context_prompt("", "", feature=None)
        assert result == ""

    def test_format_context_prompt_with_feature(self, loader: SpecLoader) -> None:
        """Test formatting includes feature header."""
        result = loader.format_context_prompt(
            requirements="Some requirements",
            design="Some design",
            feature="my-feature",
        )
        assert "# Feature Context: my-feature" in result
        assert "## Requirements Summary" in result
        assert "## Design Decisions" in result
        assert "---" in result

    def test_format_context_prompt_requirements_only(self, loader: SpecLoader) -> None:
        """Test formatting with only requirements."""
        result = loader.format_context_prompt(
            requirements="Must handle 1000 requests/sec",
            design="",
            feature="perf",
        )
        assert "## Requirements Summary" in result
        assert "1000 requests/sec" in result
        assert "## Design Decisions" not in result

    def test_format_context_prompt_design_only(self, loader: SpecLoader) -> None:
        """Test formatting with only design."""
        result = loader.format_context_prompt(
            requirements="",
            design="Use Redis for caching",
            feature="cache",
        )
        assert "## Requirements Summary" not in result
        assert "## Design Decisions" in result
        assert "Redis" in result

    def test_estimate_tokens(self, loader: SpecLoader) -> None:
        """Test token estimation."""
        text = "a" * 100
        tokens = loader._estimate_tokens(text)
        assert tokens == 100 // CHARS_PER_TOKEN

    def test_truncate_to_tokens_short_text(self, loader: SpecLoader) -> None:
        """Test truncation doesn't affect short text."""
        short_text = "This is short."
        result = loader._truncate_to_tokens(short_text, 100)
        assert result == short_text

    def test_truncate_to_tokens_long_text(self, loader: SpecLoader) -> None:
        """Test truncation on long text."""
        long_text = "A" * 10000
        result = loader._truncate_to_tokens(long_text, 100)
        assert len(result) < len(long_text)
        assert "truncated" in result

    def test_truncate_at_paragraph(self, loader: SpecLoader) -> None:
        """Test truncation prefers paragraph boundaries."""
        text = "First paragraph.\n\nSecond paragraph.\n\nThird very long paragraph " + "x" * 1000
        result = loader._truncate_to_tokens(text, 50)
        # Should truncate at a clean boundary
        assert "truncated" in result

    def test_load_and_format(self, loader: SpecLoader, temp_gsd_dir: Path) -> None:
        """Test combined load and format."""
        feature_dir = temp_gsd_dir / "specs" / "auth"
        feature_dir.mkdir(parents=True)
        (feature_dir / "requirements.md").write_text("Users need to login securely.")
        (feature_dir / "design.md").write_text("Use OAuth 2.0 with PKCE.")

        result = loader.load_and_format("auth")
        assert "# Feature Context: auth" in result
        assert "login securely" in result
        assert "OAuth 2.0" in result

    def test_specs_exist_true(self, loader: SpecLoader, temp_gsd_dir: Path) -> None:
        """Test specs_exist returns True when files exist."""
        feature_dir = temp_gsd_dir / "specs" / "test"
        feature_dir.mkdir(parents=True)
        (feature_dir / "requirements.md").write_text("content")

        assert loader.specs_exist("test") is True

    def test_specs_exist_false_no_dir(self, loader: SpecLoader) -> None:
        """Test specs_exist returns False when dir doesn't exist."""
        assert loader.specs_exist("nonexistent") is False

    def test_specs_exist_false_empty_dir(self, loader: SpecLoader, temp_gsd_dir: Path) -> None:
        """Test specs_exist returns False when dir is empty."""
        feature_dir = temp_gsd_dir / "specs" / "empty"
        feature_dir.mkdir(parents=True)

        assert loader.specs_exist("empty") is False

    # --- Tests for _load_file OSError handling (lines 101-103) ---

    def test_load_file_oserror_returns_empty(self, loader: SpecLoader, temp_gsd_dir: Path) -> None:
        """Test _load_file returns empty string on OSError."""
        feature_dir = temp_gsd_dir / "specs" / "broken"
        feature_dir.mkdir(parents=True)
        broken_file = feature_dir / "requirements.md"
        broken_file.write_text("content")

        with patch.object(Path, "read_text", side_effect=OSError("Permission denied")):
            result = loader._load_file(broken_file)

        assert result == ""

    def test_load_feature_specs_oserror_graceful(self, loader: SpecLoader, temp_gsd_dir: Path) -> None:
        """Test load_feature_specs handles OSError in file reading gracefully."""
        feature_dir = temp_gsd_dir / "specs" / "err-feature"
        feature_dir.mkdir(parents=True)
        (feature_dir / "requirements.md").write_text("good content")

        with patch.object(Path, "read_text", side_effect=OSError("Disk error")):
            specs = loader.load_feature_specs("err-feature")

        assert specs.requirements == ""
        assert specs.design == ""

    # --- Tests for truncation at paragraph boundary (line 188) ---

    def test_truncate_at_paragraph_boundary_in_upper_half(self, loader: SpecLoader) -> None:
        """Test truncation at paragraph boundary when boundary is in upper half of text."""
        # Build text where a paragraph boundary (\n\n) falls in the upper half
        # of the max_chars window, so line 188 is triggered.
        # max_tokens=50 => max_chars=200
        # We need \n\n after position 100 (max_chars//2) but before position 200
        first_part = "A" * 120  # 120 chars
        second_part = "B" * 200  # makes total > 200
        text = first_part + "\n\n" + second_part
        result = loader._truncate_to_tokens(text, 50)
        # Should truncate at the \n\n boundary
        assert result.startswith("A" * 120)
        assert "truncated" in result
        assert "B" * 50 not in result

    # --- Tests for truncation at sentence boundary (line 196) ---

    def test_truncate_at_sentence_boundary(self, loader: SpecLoader) -> None:
        """Test truncation at sentence boundary when no paragraph boundary is suitable."""
        # max_tokens=50 => max_chars=200
        # No \n\n in upper half, but a ". " in upper half
        # Put a sentence end after position 100 but before 200
        text = "A" * 110 + ". " + "B" * 200
        result = loader._truncate_to_tokens(text, 50)
        # Should truncate at ". " boundary
        assert result.startswith("A" * 110 + ".")
        assert "truncated" in result

    def test_truncate_at_sentence_newline_boundary(self, loader: SpecLoader) -> None:
        """Test truncation at sentence-newline boundary (.\n pattern)."""
        # max_tokens=50 => max_chars=200
        # No \n\n in upper half, but a ".\n" in upper half
        text = "A" * 130 + ".\n" + "B" * 200
        result = loader._truncate_to_tokens(text, 50)
        assert result.startswith("A" * 130 + ".")
        assert "truncated" in result

    # --- Tests for format_task_context (lines 219-247) ---

    def test_format_task_context_with_matching_specs(self, loader: SpecLoader, temp_gsd_dir: Path) -> None:
        """Test format_task_context extracts relevant sections for a task."""
        feature_dir = temp_gsd_dir / "specs" / "auth"
        feature_dir.mkdir(parents=True)
        (feature_dir / "requirements.md").write_text(
            "Users must authenticate with tokens.\n\n"
            "The system handles login securely.\n\n"
            "Unrelated paragraph about deployment."
        )
        (feature_dir / "design.md").write_text(
            "Authentication uses JWT tokens.\n\nDatabase schema for sessions.\n\nUnrelated design notes."
        )

        task = {
            "title": "Implement token authentication",
            "description": "Add JWT token validation for login endpoints",
            "files": {"modify": ["src/auth/tokens.py"]},
        }

        result = loader.format_task_context(task, "auth")
        assert "Relevant Requirements" in result or "Relevant Design" in result

    def test_format_task_context_no_specs(self, loader: SpecLoader) -> None:
        """Test format_task_context returns empty when no specs exist."""
        task = {
            "title": "Some task",
            "description": "Some description",
            "files": {"modify": ["src/main.py"]},
        }

        result = loader.format_task_context(task, "nonexistent-feature")
        assert result == ""

    def test_format_task_context_no_keywords(self, loader: SpecLoader, temp_gsd_dir: Path) -> None:
        """Test format_task_context returns empty when task has no extractable keywords."""
        feature_dir = temp_gsd_dir / "specs" / "kw-feature"
        feature_dir.mkdir(parents=True)
        (feature_dir / "requirements.md").write_text("Some requirements content here.")

        # Task with short words only (length <= 3), which get filtered out
        task = {
            "title": "do it",
            "description": "go on",
            "files": {},
        }

        result = loader.format_task_context(task, "kw-feature")
        assert result == ""

    def test_format_task_context_oserror(self, loader: SpecLoader) -> None:
        """Test format_task_context returns empty string on OSError loading specs."""
        task = {
            "title": "Some longer task title",
            "description": "A description with enough words",
            "files": {},
        }

        with patch.object(SpecLoader, "load_feature_specs", side_effect=OSError("disk")):
            result = loader.format_task_context(task, "broken")

        assert result == ""

    def test_format_task_context_design_only_relevant(self, loader: SpecLoader, temp_gsd_dir: Path) -> None:
        """Test format_task_context with only design having relevant sections."""
        feature_dir = temp_gsd_dir / "specs" / "design-only"
        feature_dir.mkdir(parents=True)
        (feature_dir / "design.md").write_text(
            "The caching layer uses Redis for speed.\n\n"
            "Unrelated paragraph about testing.\n\n"
            "Another unrelated section."
        )

        task = {
            "title": "Implement caching with Redis",
            "description": "Add Redis caching layer for performance",
            "files": {"modify": ["src/cache.py"]},
        }

        result = loader.format_task_context(task, "design-only")
        # Should include relevant design content
        assert "Relevant Design" in result

    # --- Tests for _extract_task_keywords (lines 258-269) ---

    def test_extract_task_keywords_from_title_and_description(self, loader: SpecLoader) -> None:
        """Test keyword extraction from title and description fields."""
        task = {
            "title": "Implement authentication system",
            "description": "Build secure login with tokens",
        }

        keywords = loader._extract_task_keywords(task)
        assert "implement" in keywords
        assert "authentication" in keywords
        assert "system" in keywords
        assert "secure" in keywords
        assert "login" in keywords
        assert "tokens" in keywords
        assert "with" in keywords
        # Short words (<=3 chars) should be excluded
        assert "add" not in keywords

    def test_extract_task_keywords_from_files(self, loader: SpecLoader) -> None:
        """Test keyword extraction from file paths."""
        task = {
            "title": "Update code",
            "description": "",
            "files": {
                "modify": ["src/auth/token-validator.py", "src/user_service.py"],
                "read": ["config/settings.py"],
            },
        }

        keywords = loader._extract_task_keywords(task)
        # File stems split on - and _ with parts > 2 chars
        assert "token" in keywords
        assert "validator" in keywords
        assert "user" in keywords
        assert "service" in keywords
        assert "settings" in keywords

    def test_extract_task_keywords_empty_task(self, loader: SpecLoader) -> None:
        """Test keyword extraction from empty task returns empty set."""
        task: dict = {}
        keywords = loader._extract_task_keywords(task)
        assert keywords == set()

    def test_extract_task_keywords_files_non_list_ignored(self, loader: SpecLoader) -> None:
        """Test keyword extraction ignores non-list file values."""
        task = {
            "title": "Some longer title here",
            "description": "",
            "files": {"modify": "not-a-list"},  # string instead of list
        }

        keywords = loader._extract_task_keywords(task)
        # Should not crash, just skip the non-list value
        assert "longer" in keywords
        assert "title" in keywords
        # "not-a-list" is a string, not a list, so file stem extraction is skipped
        assert "list" not in keywords

    # --- Tests for _extract_relevant_sections (lines 281-290) ---

    def test_extract_relevant_sections_matches(self, loader: SpecLoader) -> None:
        """Test extracting sections that match keywords."""
        text = (
            "This paragraph discusses authentication.\n\n"
            "This paragraph is about database setup.\n\n"
            "Another paragraph mentioning authentication and tokens.\n\n"
            "Completely unrelated content about weather."
        )
        keywords = {"authentication", "tokens"}

        result = loader._extract_relevant_sections(text, keywords)
        assert "authentication" in result
        assert "tokens" in result
        # The paragraph with 2 matches should appear first (higher score)
        assert result.index("Another paragraph") < result.index("This paragraph discusses")

    def test_extract_relevant_sections_no_matches(self, loader: SpecLoader) -> None:
        """Test extracting sections returns empty when no keywords match."""
        text = "Paragraph about apples.\n\nParagraph about oranges."
        keywords = {"authentication", "tokens"}

        result = loader._extract_relevant_sections(text, keywords)
        assert result == ""

    def test_extract_relevant_sections_empty_paragraphs_skipped(self, loader: SpecLoader) -> None:
        """Test that empty paragraphs are skipped in section extraction."""
        text = "Relevant authentication content.\n\n\n\n\n\nMore about tokens."
        keywords = {"authentication", "tokens"}

        result = loader._extract_relevant_sections(text, keywords)
        assert "authentication" in result
        assert "tokens" in result

    def test_extract_relevant_sections_limits_to_five(self, loader: SpecLoader) -> None:
        """Test that at most 5 relevant sections are returned."""
        paragraphs = [f"Paragraph {i} about authentication." for i in range(10)]
        text = "\n\n".join(paragraphs)
        keywords = {"authentication"}

        result = loader._extract_relevant_sections(text, keywords)
        # Should contain exactly 5 paragraphs
        assert result.count("authentication") == 5


class TestSpecContent:
    """Tests for SpecContent named tuple."""

    def test_spec_content_creation(self) -> None:
        """Test SpecContent can be created."""
        spec = SpecContent(
            requirements="req content",
            design="design content",
            feature="my-feature",
        )
        assert spec.requirements == "req content"
        assert spec.design == "design content"
        assert spec.feature == "my-feature"

    def test_spec_content_immutable(self) -> None:
        """Test SpecContent is immutable (NamedTuple)."""
        spec = SpecContent("req", "design", "feature")
        with pytest.raises(AttributeError):
            spec.requirements = "new"  # type: ignore
