"""Unit tests for ZERG refactor command - thinned per TSR2-L3-002."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from zerg.commands.refactor import (
    BaseTransform,
    DeadCodeTransform,
    NamingTransform,
    PatternsTransform,
    RefactorCommand,
    RefactorConfig,
    RefactorResult,
    RefactorSuggestion,
    SimplifyTransform,
    TransformType,
    TypesTransform,
    _collect_files,
    refactor,
)


class TestTransformTypeEnum:
    """Tests for TransformType enum."""

    def test_all_transform_types_exist(self) -> None:
        """Test all expected transform types are defined."""
        expected = {"dead-code", "simplify", "types", "patterns", "naming"}
        actual = {t.value for t in TransformType}
        assert actual == expected


class TestRefactorConfig:
    """Tests for RefactorConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = RefactorConfig()
        assert config.dry_run is False
        assert config.interactive is False
        assert config.backup is True
        assert config.exclude_patterns == []

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = RefactorConfig(
            dry_run=True,
            interactive=True,
            backup=False,
            exclude_patterns=["*.test.py"],
        )
        assert config.dry_run is True
        assert config.backup is False


class TestRefactorSuggestion:
    """Tests for RefactorSuggestion dataclass."""

    def test_default_confidence(self) -> None:
        """Test default confidence value."""
        suggestion = RefactorSuggestion(
            transform_type=TransformType.DEAD_CODE,
            file="test.py",
            line=10,
            original="# TODO: fix this",
            suggested="",
            reason="Consider removing TODO comment",
        )
        assert suggestion.confidence == 0.9

    def test_to_dict(self) -> None:
        """Test to_dict method."""
        suggestion = RefactorSuggestion(
            transform_type=TransformType.SIMPLIFY,
            file="module.py",
            line=25,
            original="if x == True:",
            suggested="if x:",
            reason="Simplify boolean comparison",
            confidence=0.9,
        )
        result = suggestion.to_dict()
        assert result["transform"] == "simplify"
        assert result["file"] == "module.py"
        assert result["line"] == 25


class TestRefactorResult:
    """Tests for RefactorResult dataclass."""

    def test_total_suggestions_property(self) -> None:
        """Test total_suggestions property."""
        suggestions = [
            RefactorSuggestion(
                transform_type=TransformType.DEAD_CODE,
                file="a.py",
                line=1,
                original="# TODO",
                suggested="",
                reason="Remove TODO",
            ),
            RefactorSuggestion(
                transform_type=TransformType.SIMPLIFY,
                file="b.py",
                line=2,
                original="if x == True:",
                suggested="if x:",
                reason="Simplify",
            ),
        ]
        result = RefactorResult(files_analyzed=5, suggestions=suggestions, applied=1)
        assert result.total_suggestions == 2

    def test_by_transform_grouping(self) -> None:
        """Test by_transform groups suggestions correctly."""
        suggestions = [
            RefactorSuggestion(
                transform_type=TransformType.DEAD_CODE,
                file="a.py",
                line=1,
                original="# TODO",
                suggested="",
                reason="Remove",
            ),
            RefactorSuggestion(
                transform_type=TransformType.DEAD_CODE,
                file="b.py",
                line=2,
                original="# FIXME",
                suggested="",
                reason="Remove",
            ),
            RefactorSuggestion(
                transform_type=TransformType.SIMPLIFY,
                file="c.py",
                line=3,
                original="if x == True:",
                suggested="if x:",
                reason="Simplify",
            ),
        ]
        result = RefactorResult(files_analyzed=3, suggestions=suggestions, applied=0)
        grouped = result.by_transform()
        assert len(grouped["dead-code"]) == 2
        assert len(grouped["simplify"]) == 1


class TestBaseTransform:
    """Tests for BaseTransform base class."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        """Test that BaseTransform cannot be instantiated directly (abstract)."""
        with pytest.raises(TypeError, match="abstract"):
            BaseTransform()


class TestDeadCodeTransform:
    """Tests for DeadCodeTransform class."""

    def test_analyze_detects_todo(self) -> None:
        """Test analyze detects TODO comments."""
        transform = DeadCodeTransform()
        content = "# TODO: fix this bug\nx = 1"
        suggestions = transform.analyze(content, "test.py")
        assert len(suggestions) == 1
        assert suggestions[0].transform_type == TransformType.DEAD_CODE

    def test_analyze_no_dead_code(self) -> None:
        """Test analyze with no dead code."""
        transform = DeadCodeTransform()
        content = "x = 1\ny = x + 1"
        suggestions = transform.analyze(content, "test.py")
        assert suggestions == []

    def test_apply_returns_content(self) -> None:
        """Test apply returns content unchanged."""
        transform = DeadCodeTransform()
        content = "# TODO: fix\nx = 1"
        result = transform.apply(content, [])
        assert result == content


class TestSimplifyTransform:
    """Tests for SimplifyTransform class."""

    @pytest.mark.parametrize(
        "code,expected_fragment",
        [
            ("if x == True:", "if x:"),
            ("if x == False:", "if not x:"),
            ("if x == None:", "is None"),
            ("if len(items) == 0:", "not items"),
        ],
    )
    def test_analyze_detects_simplifications(self, code: str, expected_fragment: str) -> None:
        """Test analyze detects various simplification opportunities."""
        transform = SimplifyTransform()
        suggestions = transform.analyze(code, "test.py")
        assert len(suggestions) == 1
        assert expected_fragment in suggestions[0].suggested

    def test_analyze_no_simplifications(self) -> None:
        """Test analyze with no simplification opportunities."""
        transform = SimplifyTransform()
        content = "if x is None:\n    pass"
        suggestions = transform.analyze(content, "test.py")
        assert suggestions == []

    def test_apply_applies_simplifications(self) -> None:
        """Test apply applies simplifications."""
        transform = SimplifyTransform()
        content = "if x == True:\n    pass"
        result = transform.apply(content, [])
        assert "if x:" in result


class TestTypesTransform:
    """Tests for TypesTransform class."""

    def test_analyze_detects_missing_return_type(self) -> None:
        """Test analyze detects functions without return type hints."""
        transform = TypesTransform()
        content = "def foo(x):"
        suggestions = transform.analyze(content, "test.py")
        assert len(suggestions) == 1
        assert "-> None:" in suggestions[0].suggested

    def test_analyze_ignores_private_functions(self) -> None:
        """Test analyze ignores private functions."""
        transform = TypesTransform()
        content = "def _private_func(x):"
        suggestions = transform.analyze(content, "test.py")
        assert suggestions == []


class TestNamingTransform:
    """Tests for NamingTransform class."""

    def test_analyze_detects_poor_names(self) -> None:
        """Test analyze detects poor variable names."""
        transform = NamingTransform()
        content = "x = 1"
        suggestions = transform.analyze(content, "test.py")
        assert len(suggestions) == 1
        assert "'x'" in suggestions[0].reason

    def test_analyze_accepts_good_names(self) -> None:
        """Test analyze accepts good variable names."""
        transform = NamingTransform()
        content = "user_count = 10\nmax_retries = 3"
        suggestions = transform.analyze(content, "test.py")
        assert suggestions == []


class TestPatternsTransform:
    """Tests for PatternsTransform class."""

    def test_analyze_detects_deep_nesting(self) -> None:
        """Test analyze detects deeply nested code."""
        transform = PatternsTransform()
        content = "            if x:"
        suggestions = transform.analyze(content, "test.py")
        assert len(suggestions) == 1
        assert "guard clause" in suggestions[0].suggested

    def test_analyze_accepts_shallow_nesting(self) -> None:
        """Test analyze accepts shallowly nested code."""
        transform = PatternsTransform()
        content = "    if x:\n        pass"
        suggestions = transform.analyze(content, "test.py")
        assert suggestions == []


class TestRefactorCommand:
    """Tests for RefactorCommand class."""

    def test_init_default_config(self) -> None:
        """Test initialization with default config."""
        refactorer = RefactorCommand()
        assert refactorer.config.dry_run is False

    def test_supported_transforms(self) -> None:
        """Test supported_transforms returns all transforms."""
        refactorer = RefactorCommand()
        transforms = refactorer.supported_transforms()
        assert "dead-code" in transforms
        assert "simplify" in transforms

    def test_run_dry_run(self, tmp_path: Path) -> None:
        """Test run in dry run mode."""
        test_file = tmp_path / "test.py"
        test_file.write_text("# TODO: fix\nx = 1")
        refactorer = RefactorCommand()
        result = refactorer.run(files=[str(test_file)], transforms=["dead-code"], dry_run=True)
        assert result.files_analyzed == 1
        assert result.total_suggestions == 1
        assert result.applied == 0

    def test_run_applies_changes(self, tmp_path: Path) -> None:
        """Test run applies changes when not dry run."""
        test_file = tmp_path / "test.py"
        test_file.write_text("if x == True:\n    pass")
        refactorer = RefactorCommand()
        result = refactorer.run(files=[str(test_file)], transforms=["simplify"], dry_run=False)
        assert result.applied > 0
        content = test_file.read_text()
        assert "if x:" in content

    def test_run_handles_read_error(self, tmp_path: Path) -> None:
        """Test run handles file read errors."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1")
        refactorer = RefactorCommand()
        with patch.object(Path, "read_text", side_effect=PermissionError("No access")):
            result = refactorer.run(files=[str(test_file)], transforms=["dead-code"], dry_run=True)
        assert len(result.errors) > 0

    def test_format_result_json(self) -> None:
        """Test format_result with JSON output."""
        suggestions = [
            RefactorSuggestion(
                transform_type=TransformType.DEAD_CODE,
                file="test.py",
                line=1,
                original="# TODO",
                suggested="",
                reason="Remove",
            )
        ]
        result = RefactorResult(files_analyzed=1, suggestions=suggestions, applied=0)
        refactorer = RefactorCommand()
        output = refactorer.format_result(result, fmt="json")
        parsed = json.loads(output)
        assert parsed["files_analyzed"] == 1

    def test_format_result_text(self) -> None:
        """Test format_result with text output."""
        result = RefactorResult(files_analyzed=5, suggestions=[], applied=0)
        refactorer = RefactorCommand()
        output = refactorer.format_result(result, fmt="text")
        assert "Suggestions: 0" in output


class TestCollectFiles:
    """Tests for _collect_files helper function."""

    def test_collect_files_file_path(self, tmp_path: Path) -> None:
        """Test collect_files with file path."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1")
        files = _collect_files(str(test_file))
        assert files == [str(test_file)]

    def test_collect_files_directory(self, tmp_path: Path) -> None:
        """Test collect_files with directory path."""
        (tmp_path / "a.py").write_text("x = 1")
        (tmp_path / "b.py").write_text("y = 2")
        (tmp_path / "readme.txt").write_text("text")
        files = _collect_files(str(tmp_path))
        assert len(files) == 2
        assert all(f.endswith(".py") for f in files)

    def test_collect_files_nonexistent_path(self) -> None:
        """Test collect_files with nonexistent path."""
        files = _collect_files("/nonexistent/path")
        assert files == []


class TestRefactorCLI:
    """Tests for refactor CLI command."""

    def test_refactor_help(self) -> None:
        """Test refactor --help."""
        runner = CliRunner()
        result = runner.invoke(refactor, ["--help"])
        assert result.exit_code == 0
        assert "transforms" in result.output

    @patch("zerg.commands.refactor.RefactorCommand")
    @patch("zerg.commands.refactor.console")
    def test_refactor_dry_run(self, mock_console: MagicMock, mock_command_class: MagicMock) -> None:
        """Test refactor --dry-run."""
        mock_command = MagicMock()
        mock_command.run.return_value = RefactorResult(files_analyzed=5, suggestions=[], applied=0)
        mock_command_class.return_value = mock_command
        runner = CliRunner()
        result = runner.invoke(refactor, ["--dry-run"])
        assert result.exit_code == 0

    @patch("zerg.commands.refactor.console")
    def test_refactor_keyboard_interrupt(self, mock_console: MagicMock) -> None:
        """Test refactor handles KeyboardInterrupt."""
        with patch("zerg.commands.refactor._collect_files", side_effect=KeyboardInterrupt):
            runner = CliRunner()
            result = runner.invoke(refactor, [])
            assert result.exit_code == 130

    @patch("zerg.commands.refactor.console")
    def test_refactor_generic_exception(self, mock_console: MagicMock) -> None:
        """Test refactor handles generic exception."""
        with patch("zerg.commands.refactor._collect_files", side_effect=RuntimeError("Unexpected error")):
            runner = CliRunner()
            result = runner.invoke(refactor, [])
            assert result.exit_code == 1
