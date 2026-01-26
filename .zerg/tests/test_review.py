"""Tests for ZERG v2 Review Command."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestReviewMode:
    """Tests for review mode enumeration."""

    def test_modes_exist(self):
        """Test review modes are defined."""
        from review import ReviewMode

        assert hasattr(ReviewMode, "PREPARE")
        assert hasattr(ReviewMode, "SELF")
        assert hasattr(ReviewMode, "RECEIVE")
        assert hasattr(ReviewMode, "FULL")


class TestReviewConfig:
    """Tests for review configuration."""

    def test_config_defaults(self):
        """Test ReviewConfig has sensible defaults."""
        from review import ReviewConfig

        config = ReviewConfig()
        assert config.mode == "full"

    def test_config_custom(self):
        """Test ReviewConfig with custom values."""
        from review import ReviewConfig

        config = ReviewConfig(mode="self", include_tests=False)
        assert config.mode == "self"
        assert config.include_tests is False


class TestReviewItem:
    """Tests for review items."""

    def test_item_creation(self):
        """Test ReviewItem can be created."""
        from review import ReviewItem

        item = ReviewItem(
            category="style",
            severity="suggestion",
            file="test.py",
            line=10,
            message="Consider using f-string",
        )
        assert item.category == "style"

    def test_item_to_dict(self):
        """Test ReviewItem serialization."""
        from review import ReviewItem

        item = ReviewItem(
            category="logic",
            severity="warning",
            file="auth.py",
            line=42,
            message="Potential race condition",
        )
        data = item.to_dict()
        assert data["category"] == "logic"
        assert data["line"] == 42


class TestReviewResult:
    """Tests for review results."""

    def test_result_creation(self):
        """Test ReviewResult can be created."""
        from review import ReviewResult

        result = ReviewResult(
            files_reviewed=5,
            items=[],
            spec_passed=True,
            quality_passed=True,
        )
        assert result.files_reviewed == 5

    def test_result_overall_passed(self):
        """Test ReviewResult overall pass check."""
        from review import ReviewResult

        passed = ReviewResult(
            files_reviewed=5,
            items=[],
            spec_passed=True,
            quality_passed=True,
        )
        assert passed.overall_passed is True

        failed = ReviewResult(
            files_reviewed=5,
            items=[],
            spec_passed=True,
            quality_passed=False,
        )
        assert failed.overall_passed is False


class TestSelfReviewChecklist:
    """Tests for self-review checklist."""

    def test_checklist_creation(self):
        """Test SelfReviewChecklist can be created."""
        from review import SelfReviewChecklist

        checklist = SelfReviewChecklist()
        assert checklist is not None

    def test_checklist_items(self):
        """Test checklist has items."""
        from review import SelfReviewChecklist

        checklist = SelfReviewChecklist()
        items = checklist.get_items()
        assert len(items) > 0


class TestReviewCommand:
    """Tests for ReviewCommand class."""

    def test_command_creation(self):
        """Test ReviewCommand can be created."""
        from review import ReviewCommand

        cmd = ReviewCommand()
        assert cmd is not None

    def test_command_supported_modes(self):
        """Test ReviewCommand lists supported modes."""
        from review import ReviewCommand

        cmd = ReviewCommand()
        modes = cmd.supported_modes()
        assert "prepare" in modes
        assert "self" in modes
        assert "full" in modes

    def test_command_run_returns_result(self):
        """Test run returns ReviewResult."""
        from review import ReviewCommand, ReviewResult

        cmd = ReviewCommand()
        result = cmd.run(files=[], mode="self", dry_run=True)
        assert isinstance(result, ReviewResult)

    def test_command_format_text(self):
        """Test text output format."""
        from review import ReviewCommand, ReviewResult

        cmd = ReviewCommand()
        result = ReviewResult(
            files_reviewed=5,
            items=[],
            spec_passed=True,
            quality_passed=True,
        )
        output = cmd.format_result(result, format="text")
        assert "Review" in output

    def test_command_format_json(self):
        """Test JSON output format."""
        import json

        from review import ReviewCommand, ReviewResult

        cmd = ReviewCommand()
        result = ReviewResult(
            files_reviewed=5,
            items=[],
            spec_passed=True,
            quality_passed=True,
        )
        output = cmd.format_result(result, format="json")
        data = json.loads(output)
        assert data["files_reviewed"] == 5
