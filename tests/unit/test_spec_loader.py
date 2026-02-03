"""Unit tests for SpecLoader utility."""

from pathlib import Path

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
