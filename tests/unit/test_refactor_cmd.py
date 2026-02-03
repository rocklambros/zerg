"""Comprehensive unit tests for ZERG refactor command - 100% coverage target.

Tests cover:
- TransformType enum
- RefactorConfig dataclass
- RefactorSuggestion dataclass
- RefactorResult dataclass with properties
- BaseTransform base class
- DeadCodeTransform for dead code detection
- SimplifyTransform for code simplification
- TypesTransform for type annotation suggestions
- NamingTransform for naming improvement suggestions
- PatternsTransform for design pattern suggestions
- RefactorCommand orchestration
- _collect_files helper function
- CLI command with all options
"""

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

# =============================================================================
# TransformType Enum Tests
# =============================================================================


class TestTransformTypeEnum:
    """Tests for TransformType enum."""

    def test_dead_code_value(self) -> None:
        """Test dead-code enum value."""
        assert TransformType.DEAD_CODE.value == "dead-code"

    def test_simplify_value(self) -> None:
        """Test simplify enum value."""
        assert TransformType.SIMPLIFY.value == "simplify"

    def test_types_value(self) -> None:
        """Test types enum value."""
        assert TransformType.TYPES.value == "types"

    def test_patterns_value(self) -> None:
        """Test patterns enum value."""
        assert TransformType.PATTERNS.value == "patterns"

    def test_naming_value(self) -> None:
        """Test naming enum value."""
        assert TransformType.NAMING.value == "naming"

    def test_all_transform_types_exist(self) -> None:
        """Test all expected transform types are defined."""
        expected = {"dead-code", "simplify", "types", "patterns", "naming"}
        actual = {t.value for t in TransformType}
        assert actual == expected


# =============================================================================
# RefactorConfig Dataclass Tests
# =============================================================================


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
            exclude_patterns=["*.test.py", "*_test.py"],
        )

        assert config.dry_run is True
        assert config.interactive is True
        assert config.backup is False
        assert config.exclude_patterns == ["*.test.py", "*_test.py"]


# =============================================================================
# RefactorSuggestion Dataclass Tests
# =============================================================================


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

    def test_custom_confidence(self) -> None:
        """Test custom confidence value."""
        suggestion = RefactorSuggestion(
            transform_type=TransformType.NAMING,
            file="test.py",
            line=5,
            original="x = 1",
            suggested="x = 1",
            reason="Consider more descriptive name",
            confidence=0.5,
        )

        assert suggestion.confidence == 0.5

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

        assert result == {
            "transform": "simplify",
            "file": "module.py",
            "line": 25,
            "original": "if x == True:",
            "suggested": "if x:",
            "reason": "Simplify boolean comparison",
            "confidence": 0.9,
        }


# =============================================================================
# RefactorResult Dataclass Tests
# =============================================================================


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

        result = RefactorResult(
            files_analyzed=5,
            suggestions=suggestions,
            applied=1,
        )

        assert result.total_suggestions == 2

    def test_total_suggestions_empty(self) -> None:
        """Test total_suggestions with no suggestions."""
        result = RefactorResult(
            files_analyzed=5,
            suggestions=[],
            applied=0,
        )

        assert result.total_suggestions == 0

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

        result = RefactorResult(
            files_analyzed=3,
            suggestions=suggestions,
            applied=0,
        )

        grouped = result.by_transform()

        assert len(grouped["dead-code"]) == 2
        assert len(grouped["simplify"]) == 1

    def test_by_transform_empty(self) -> None:
        """Test by_transform with no suggestions."""
        result = RefactorResult(
            files_analyzed=3,
            suggestions=[],
            applied=0,
        )

        grouped = result.by_transform()

        assert grouped == {}

    def test_default_errors(self) -> None:
        """Test default errors list."""
        result = RefactorResult(
            files_analyzed=1,
            suggestions=[],
            applied=0,
        )

        assert result.errors == []

    def test_custom_errors(self) -> None:
        """Test custom errors list."""
        result = RefactorResult(
            files_analyzed=1,
            suggestions=[],
            applied=0,
            errors=["Error 1", "Error 2"],
        )

        assert result.errors == ["Error 1", "Error 2"]


# =============================================================================
# BaseTransform Tests
# =============================================================================


class TestBaseTransform:
    """Tests for BaseTransform base class."""

    def test_name_attribute(self) -> None:
        """Test name class attribute."""
        assert BaseTransform.name == "base"

    def test_cannot_instantiate_abstract_class(self) -> None:
        """Test that BaseTransform cannot be instantiated directly (abstract)."""
        with pytest.raises(TypeError, match="abstract"):
            BaseTransform()


# =============================================================================
# DeadCodeTransform Tests
# =============================================================================


class TestDeadCodeTransform:
    """Tests for DeadCodeTransform class."""

    def test_name_attribute(self) -> None:
        """Test name class attribute."""
        assert DeadCodeTransform.name == "dead-code"

    def test_analyze_detects_todo(self) -> None:
        """Test analyze detects TODO comments."""
        transform = DeadCodeTransform()
        content = "# TODO: fix this bug\nx = 1"

        suggestions = transform.analyze(content, "test.py")

        assert len(suggestions) == 1
        assert suggestions[0].transform_type == TransformType.DEAD_CODE
        assert "TODO" in suggestions[0].original
        assert suggestions[0].confidence == 0.7

    def test_analyze_detects_fixme(self) -> None:
        """Test analyze detects FIXME comments."""
        transform = DeadCodeTransform()
        content = "# FIXME: broken\nx = 1"

        suggestions = transform.analyze(content, "test.py")

        assert len(suggestions) == 1
        assert "FIXME" in suggestions[0].original

    def test_analyze_detects_pass(self) -> None:
        """Test analyze detects empty pass statements."""
        transform = DeadCodeTransform()
        content = "def foo():\n    pass"

        suggestions = transform.analyze(content, "test.py")

        assert len(suggestions) == 1
        assert suggestions[0].original == "pass"

    def test_analyze_case_insensitive(self) -> None:
        """Test analyze is case insensitive."""
        transform = DeadCodeTransform()
        content = "# todo: something\n# FIXME: something"

        suggestions = transform.analyze(content, "test.py")

        assert len(suggestions) == 2

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


# =============================================================================
# SimplifyTransform Tests
# =============================================================================


class TestSimplifyTransform:
    """Tests for SimplifyTransform class."""

    def test_name_attribute(self) -> None:
        """Test name class attribute."""
        assert SimplifyTransform.name == "simplify"

    def test_analyze_detects_true_comparison(self) -> None:
        """Test analyze detects == True comparison."""
        transform = SimplifyTransform()
        content = "if x == True:"

        suggestions = transform.analyze(content, "test.py")

        assert len(suggestions) == 1
        assert "if x:" in suggestions[0].suggested

    def test_analyze_detects_false_comparison(self) -> None:
        """Test analyze detects == False comparison."""
        transform = SimplifyTransform()
        content = "if x == False:"

        suggestions = transform.analyze(content, "test.py")

        assert len(suggestions) == 1
        assert "if not x:" in suggestions[0].suggested

    def test_analyze_detects_none_equality(self) -> None:
        """Test analyze detects == None comparison."""
        transform = SimplifyTransform()
        content = "if x == None:"

        suggestions = transform.analyze(content, "test.py")

        assert len(suggestions) == 1
        assert "is None" in suggestions[0].suggested

    def test_analyze_detects_none_inequality(self) -> None:
        """Test analyze detects != None comparison."""
        transform = SimplifyTransform()
        content = "if x != None:"

        suggestions = transform.analyze(content, "test.py")

        assert len(suggestions) == 1
        assert "is not None" in suggestions[0].suggested

    def test_analyze_detects_len_zero(self) -> None:
        """Test analyze detects len(x) == 0."""
        transform = SimplifyTransform()
        content = "if len(items) == 0:"

        suggestions = transform.analyze(content, "test.py")

        assert len(suggestions) == 1
        assert "not items" in suggestions[0].suggested

    def test_analyze_detects_len_greater_zero(self) -> None:
        """Test analyze detects len(x) > 0."""
        transform = SimplifyTransform()
        content = "if len(items) > 0:"

        suggestions = transform.analyze(content, "test.py")

        assert len(suggestions) == 1
        assert "items" in suggestions[0].suggested

    def test_analyze_detects_empty_list_comparison(self) -> None:
        """Test analyze detects == [] comparison."""
        transform = SimplifyTransform()
        content = "if items == []:"

        suggestions = transform.analyze(content, "test.py")

        assert len(suggestions) == 1
        assert "not items" in suggestions[0].suggested

    def test_analyze_detects_non_empty_list_comparison(self) -> None:
        """Test analyze detects != [] comparison."""
        transform = SimplifyTransform()
        content = "if items != []:"

        suggestions = transform.analyze(content, "test.py")

        assert len(suggestions) == 1

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


# =============================================================================
# TypesTransform Tests
# =============================================================================


class TestTypesTransform:
    """Tests for TypesTransform class."""

    def test_name_attribute(self) -> None:
        """Test name class attribute."""
        assert TypesTransform.name == "types"

    def test_analyze_detects_missing_return_type(self) -> None:
        """Test analyze detects functions without return type hints."""
        transform = TypesTransform()
        content = "def foo(x):"

        suggestions = transform.analyze(content, "test.py")

        assert len(suggestions) == 1
        assert "-> None:" in suggestions[0].suggested
        assert suggestions[0].confidence == 0.6

    def test_analyze_ignores_private_functions(self) -> None:
        """Test analyze ignores private functions."""
        transform = TypesTransform()
        content = "def _private_func(x):"

        suggestions = transform.analyze(content, "test.py")

        assert suggestions == []

    def test_analyze_ignores_typed_functions(self) -> None:
        """Test analyze ignores functions with return type hints."""
        transform = TypesTransform()
        content = "def foo(x) -> int:"

        suggestions = transform.analyze(content, "test.py")

        assert suggestions == []

    def test_analyze_multiple_functions(self) -> None:
        """Test analyze finds multiple functions."""
        transform = TypesTransform()
        content = "def foo():\n    pass\n\ndef bar(x):\n    pass"

        suggestions = transform.analyze(content, "test.py")

        assert len(suggestions) == 2

    def test_apply_returns_content(self) -> None:
        """Test apply returns content unchanged."""
        transform = TypesTransform()
        content = "def foo():\n    pass"

        result = transform.apply(content, [])

        assert result == content


# =============================================================================
# NamingTransform Tests
# =============================================================================


class TestNamingTransform:
    """Tests for NamingTransform class."""

    def test_name_attribute(self) -> None:
        """Test name class attribute."""
        assert NamingTransform.name == "naming"

    def test_analyze_detects_poor_names(self) -> None:
        """Test analyze detects poor variable names."""
        transform = NamingTransform()
        content = "x = 1"

        suggestions = transform.analyze(content, "test.py")

        assert len(suggestions) == 1
        assert suggestions[0].confidence == 0.5
        assert "'x'" in suggestions[0].reason

    def test_analyze_detects_tmp_name(self) -> None:
        """Test analyze detects 'tmp' variable name."""
        transform = NamingTransform()
        content = "tmp = get_data()"

        suggestions = transform.analyze(content, "test.py")

        assert len(suggestions) == 1
        assert "'tmp'" in suggestions[0].reason

    def test_analyze_detects_data_name(self) -> None:
        """Test analyze detects 'data' variable name."""
        transform = NamingTransform()
        content = "data = fetch()"

        suggestions = transform.analyze(content, "test.py")

        assert len(suggestions) == 1
        assert "'data'" in suggestions[0].reason

    def test_analyze_detects_result_name(self) -> None:
        """Test analyze detects 'result' variable name."""
        transform = NamingTransform()
        content = "result = compute()"

        suggestions = transform.analyze(content, "test.py")

        assert len(suggestions) == 1
        assert "'result'" in suggestions[0].reason

    def test_analyze_accepts_good_names(self) -> None:
        """Test analyze accepts good variable names."""
        transform = NamingTransform()
        content = "user_count = 10\nmax_retries = 3"

        suggestions = transform.analyze(content, "test.py")

        assert suggestions == []

    def test_analyze_multiple_poor_names(self) -> None:
        """Test analyze finds multiple poor names."""
        transform = NamingTransform()
        content = "x = 1\ny = 2\ntemp = x + y"

        suggestions = transform.analyze(content, "test.py")

        assert len(suggestions) == 3

    def test_apply_returns_content(self) -> None:
        """Test apply returns content unchanged."""
        transform = NamingTransform()
        content = "x = 1"

        result = transform.apply(content, [])

        assert result == content


# =============================================================================
# PatternsTransform Tests
# =============================================================================


class TestPatternsTransform:
    """Tests for PatternsTransform class."""

    def test_name_attribute(self) -> None:
        """Test name class attribute."""
        assert PatternsTransform.name == "patterns"

    def test_analyze_detects_deep_nesting(self) -> None:
        """Test analyze detects deeply nested code."""
        transform = PatternsTransform()
        # 3+ levels of indentation (12+ spaces)
        content = "            if x:"

        suggestions = transform.analyze(content, "test.py")

        assert len(suggestions) == 1
        assert suggestions[0].confidence == 0.7
        assert "guard clause" in suggestions[0].suggested

    def test_analyze_accepts_shallow_nesting(self) -> None:
        """Test analyze accepts shallowly nested code."""
        transform = PatternsTransform()
        content = "    if x:\n        pass"

        suggestions = transform.analyze(content, "test.py")

        assert suggestions == []

    def test_analyze_no_if_statements(self) -> None:
        """Test analyze with no if statements."""
        transform = PatternsTransform()
        content = "x = 1\ny = 2"

        suggestions = transform.analyze(content, "test.py")

        assert suggestions == []

    def test_apply_returns_content(self) -> None:
        """Test apply returns content unchanged."""
        transform = PatternsTransform()
        content = "            if x:"

        result = transform.apply(content, [])

        assert result == content


# =============================================================================
# RefactorCommand Tests
# =============================================================================


class TestRefactorCommand:
    """Tests for RefactorCommand class."""

    def test_init_default_config(self) -> None:
        """Test initialization with default config."""
        refactorer = RefactorCommand()

        assert refactorer.config.dry_run is False
        assert refactorer.config.interactive is False

    def test_init_custom_config(self) -> None:
        """Test initialization with custom config."""
        config = RefactorConfig(dry_run=True, interactive=True)
        refactorer = RefactorCommand(config)

        assert refactorer.config.dry_run is True
        assert refactorer.config.interactive is True

    def test_supported_transforms(self) -> None:
        """Test supported_transforms returns all transforms."""
        refactorer = RefactorCommand()

        transforms = refactorer.supported_transforms()

        assert "dead-code" in transforms
        assert "simplify" in transforms
        assert "types" in transforms
        assert "patterns" in transforms
        assert "naming" in transforms

    def test_run_with_nonexistent_file(self) -> None:
        """Test run with nonexistent file."""
        refactorer = RefactorCommand()

        result = refactorer.run(
            files=["/nonexistent/path.py"],
            transforms=["dead-code"],
            dry_run=True,
        )

        assert result.files_analyzed == 1
        assert result.total_suggestions == 0

    def test_run_with_directory(self, tmp_path: Path) -> None:
        """Test run skips directories."""
        refactorer = RefactorCommand()

        result = refactorer.run(
            files=[str(tmp_path)],
            transforms=["dead-code"],
            dry_run=True,
        )

        assert result.files_analyzed == 1
        assert result.total_suggestions == 0

    def test_run_dry_run(self, tmp_path: Path) -> None:
        """Test run in dry run mode."""
        test_file = tmp_path / "test.py"
        test_file.write_text("# TODO: fix\nx = 1")

        refactorer = RefactorCommand()
        result = refactorer.run(
            files=[str(test_file)],
            transforms=["dead-code"],
            dry_run=True,
        )

        assert result.files_analyzed == 1
        assert result.total_suggestions == 1
        assert result.applied == 0

    def test_run_applies_changes(self, tmp_path: Path) -> None:
        """Test run applies changes when not dry run."""
        test_file = tmp_path / "test.py"
        test_file.write_text("if x == True:\n    pass")

        refactorer = RefactorCommand()
        result = refactorer.run(
            files=[str(test_file)],
            transforms=["simplify"],
            dry_run=False,
        )

        assert result.applied > 0

        # Check file was modified
        content = test_file.read_text()
        assert "if x:" in content

    def test_run_unknown_transform(self, tmp_path: Path) -> None:
        """Test run with unknown transform."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1")

        refactorer = RefactorCommand()
        result = refactorer.run(
            files=[str(test_file)],
            transforms=["unknown-transform"],
            dry_run=True,
        )

        assert result.total_suggestions == 0

    def test_run_multiple_transforms(self, tmp_path: Path) -> None:
        """Test run with multiple transforms."""
        test_file = tmp_path / "test.py"
        test_file.write_text("# TODO: fix\nif x == True:\n    pass")

        refactorer = RefactorCommand()
        result = refactorer.run(
            files=[str(test_file)],
            transforms=["dead-code", "simplify"],
            dry_run=True,
        )

        assert result.total_suggestions >= 2

    def test_run_handles_read_error(self, tmp_path: Path) -> None:
        """Test run handles file read errors."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1")

        refactorer = RefactorCommand()

        # Mock the file read to raise an exception
        with patch.object(Path, "read_text", side_effect=PermissionError("No access")):
            result = refactorer.run(
                files=[str(test_file)],
                transforms=["dead-code"],
                dry_run=True,
            )

        assert len(result.errors) > 0

    @patch("zerg.commands.refactor.Confirm")
    def test_run_interactive_mode_apply(self, mock_confirm: MagicMock, tmp_path: Path) -> None:
        """Test run in interactive mode with apply."""
        mock_confirm.ask.return_value = True

        test_file = tmp_path / "test.py"
        test_file.write_text("# TODO: fix")

        refactorer = RefactorCommand()
        result = refactorer.run(
            files=[str(test_file)],
            transforms=["dead-code"],
            dry_run=False,
            interactive=True,
        )

        assert mock_confirm.ask.called
        assert result.applied >= 1

    @patch("zerg.commands.refactor.Confirm")
    def test_run_interactive_mode_skip(self, mock_confirm: MagicMock, tmp_path: Path) -> None:
        """Test run in interactive mode with skip."""
        mock_confirm.ask.return_value = False

        test_file = tmp_path / "test.py"
        test_file.write_text("# TODO: fix")

        refactorer = RefactorCommand()
        result = refactorer.run(
            files=[str(test_file)],
            transforms=["dead-code"],
            dry_run=False,
            interactive=True,
        )

        assert mock_confirm.ask.called
        assert result.applied == 0

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
        result = RefactorResult(
            files_analyzed=1,
            suggestions=suggestions,
            applied=0,
        )

        refactorer = RefactorCommand()
        output = refactorer.format_result(result, fmt="json")

        parsed = json.loads(output)
        assert parsed["files_analyzed"] == 1
        assert parsed["total_suggestions"] == 1
        assert len(parsed["suggestions"]) == 1

    def test_format_result_text(self) -> None:
        """Test format_result with text output."""
        suggestions = [
            RefactorSuggestion(
                transform_type=TransformType.DEAD_CODE,
                file="test.py",
                line=1,
                original="# TODO: fix something",
                suggested="",
                reason="Remove TODO",
            )
        ]
        result = RefactorResult(
            files_analyzed=5,
            suggestions=suggestions,
            applied=1,
        )

        refactorer = RefactorCommand()
        output = refactorer.format_result(result, fmt="text")

        assert "Files Analyzed: 5" in output
        assert "Suggestions: 1" in output
        assert "Applied: 1" in output
        assert "dead-code" in output

    def test_format_result_text_no_suggestions(self) -> None:
        """Test format_result with no suggestions."""
        result = RefactorResult(
            files_analyzed=5,
            suggestions=[],
            applied=0,
        )

        refactorer = RefactorCommand()
        output = refactorer.format_result(result, fmt="text")

        assert "Suggestions: 0" in output

    def test_format_result_text_many_suggestions(self) -> None:
        """Test format_result truncates many suggestions."""
        suggestions = [
            RefactorSuggestion(
                transform_type=TransformType.DEAD_CODE,
                file=f"test{i}.py",
                line=i,
                original=f"# TODO {i}",
                suggested="",
                reason=f"Remove {i}",
            )
            for i in range(10)
        ]
        result = RefactorResult(
            files_analyzed=10,
            suggestions=suggestions,
            applied=0,
        )

        refactorer = RefactorCommand()
        output = refactorer.format_result(result, fmt="text")

        # Should show first 5 suggestions per transform
        assert "test0.py" in output
        assert "test4.py" in output


# =============================================================================
# _collect_files Tests
# =============================================================================


class TestCollectFiles:
    """Tests for _collect_files helper function."""

    def test_collect_files_none_path(self) -> None:
        """Test collect_files with None path defaults to current directory."""
        files = _collect_files(None)

        # Should return some files (or empty if no .py files)
        assert isinstance(files, list)

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

    def test_collect_files_excludes_pycache(self, tmp_path: Path) -> None:
        """Test collect_files excludes __pycache__."""
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "cached.py").write_text("x = 1")
        (tmp_path / "main.py").write_text("y = 2")

        files = _collect_files(str(tmp_path))

        assert len(files) == 1
        assert "__pycache__" not in files[0]

    def test_collect_files_excludes_git(self, tmp_path: Path) -> None:
        """Test collect_files excludes .git directory."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "hooks.py").write_text("x = 1")
        (tmp_path / "main.py").write_text("y = 2")

        files = _collect_files(str(tmp_path))

        assert len(files) == 1
        assert ".git" not in files[0]

    def test_collect_files_nonexistent_path(self) -> None:
        """Test collect_files with nonexistent path."""
        files = _collect_files("/nonexistent/path")

        assert files == []

    def test_collect_files_limits_results(self, tmp_path: Path) -> None:
        """Test collect_files limits to 50 files."""
        for i in range(60):
            (tmp_path / f"file{i}.py").write_text(f"x = {i}")

        files = _collect_files(str(tmp_path))

        assert len(files) <= 50


# =============================================================================
# CLI Command Tests
# =============================================================================


class TestRefactorCLI:
    """Tests for refactor CLI command."""

    def test_refactor_help(self) -> None:
        """Test refactor --help."""
        runner = CliRunner()
        result = runner.invoke(refactor, ["--help"])

        assert result.exit_code == 0
        assert "transforms" in result.output
        assert "dry-run" in result.output
        assert "interactive" in result.output
        assert "json" in result.output

    @patch("zerg.commands.refactor.RefactorCommand")
    @patch("zerg.commands.refactor.console")
    def test_refactor_dry_run(self, mock_console: MagicMock, mock_command_class: MagicMock) -> None:
        """Test refactor --dry-run."""
        mock_command = MagicMock()
        mock_command.run.return_value = RefactorResult(
            files_analyzed=5,
            suggestions=[],
            applied=0,
        )
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(refactor, ["--dry-run"])

        assert result.exit_code == 0

    @patch("zerg.commands.refactor._collect_files")
    @patch("zerg.commands.refactor.console")
    def test_refactor_no_files(self, mock_console: MagicMock, mock_collect: MagicMock) -> None:
        """Test refactor with no files found."""
        mock_collect.return_value = []

        runner = CliRunner()
        result = runner.invoke(refactor, ["/nonexistent"])

        assert result.exit_code == 0

    @patch("zerg.commands.refactor.RefactorCommand")
    @patch("zerg.commands.refactor.console")
    def test_refactor_json_output(self, mock_console: MagicMock, mock_command_class: MagicMock) -> None:
        """Test refactor --json."""
        mock_command = MagicMock()
        mock_command.run.return_value = RefactorResult(
            files_analyzed=1,
            suggestions=[],
            applied=0,
        )
        mock_command.format_result.return_value = '{"test": 1}'
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(refactor, ["--json", "--dry-run"])

        assert result.exit_code == 0
        mock_command.format_result.assert_called_with(mock_command.run.return_value, "json")

    @patch("zerg.commands.refactor.RefactorCommand")
    @patch("zerg.commands.refactor.console")
    def test_refactor_with_transforms(self, mock_console: MagicMock, mock_command_class: MagicMock) -> None:
        """Test refactor with specific transforms."""
        mock_command = MagicMock()
        mock_command.run.return_value = RefactorResult(
            files_analyzed=1,
            suggestions=[],
            applied=0,
        )
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(refactor, ["--transforms", "types,naming", "--dry-run"])

        assert result.exit_code == 0

    @patch("zerg.commands.refactor.RefactorCommand")
    @patch("zerg.commands.refactor.console")
    def test_refactor_with_suggestions(self, mock_console: MagicMock, mock_command_class: MagicMock) -> None:
        """Test refactor with suggestions found."""
        suggestions = [
            RefactorSuggestion(
                transform_type=TransformType.DEAD_CODE,
                file="test.py",
                line=1,
                original="# TODO",
                suggested="",
                reason="Remove",
            ),
            RefactorSuggestion(
                transform_type=TransformType.DEAD_CODE,
                file="test.py",
                line=2,
                original="# TODO 2",
                suggested="",
                reason="Remove 2",
            ),
            RefactorSuggestion(
                transform_type=TransformType.DEAD_CODE,
                file="test.py",
                line=3,
                original="# TODO 3",
                suggested="",
                reason="Remove 3",
            ),
            RefactorSuggestion(
                transform_type=TransformType.DEAD_CODE,
                file="test.py",
                line=4,
                original="# TODO 4",
                suggested="",
                reason="Remove 4",
            ),
        ]
        mock_command = MagicMock()
        mock_command.run.return_value = RefactorResult(
            files_analyzed=1,
            suggestions=suggestions,
            applied=0,
        )
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(refactor, ["--dry-run"])

        assert result.exit_code == 0

    @patch("zerg.commands.refactor.RefactorCommand")
    @patch("zerg.commands.refactor.console")
    def test_refactor_with_errors(self, mock_console: MagicMock, mock_command_class: MagicMock) -> None:
        """Test refactor with errors."""
        mock_command = MagicMock()
        mock_command.run.return_value = RefactorResult(
            files_analyzed=1,
            suggestions=[],
            applied=0,
            errors=["Error 1", "Error 2", "Error 3", "Error 4", "Error 5", "Error 6"],
        )
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(refactor, ["--dry-run"])

        assert result.exit_code == 0

    @patch("zerg.commands.refactor.RefactorCommand")
    @patch("zerg.commands.refactor.console")
    def test_refactor_applied_changes(self, mock_console: MagicMock, mock_command_class: MagicMock) -> None:
        """Test refactor with applied changes."""
        mock_command = MagicMock()
        mock_command.run.return_value = RefactorResult(
            files_analyzed=1,
            suggestions=[],
            applied=5,
        )
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(refactor, [])

        assert result.exit_code == 0

    @patch("zerg.commands.refactor.console")
    def test_refactor_keyboard_interrupt(self, mock_console: MagicMock) -> None:
        """Test refactor handles KeyboardInterrupt."""
        with patch(
            "zerg.commands.refactor._collect_files",
            side_effect=KeyboardInterrupt,
        ):
            runner = CliRunner()
            result = runner.invoke(refactor, [])

            assert result.exit_code == 130

    @patch("zerg.commands.refactor.console")
    def test_refactor_generic_exception(self, mock_console: MagicMock) -> None:
        """Test refactor handles generic exception."""
        with patch(
            "zerg.commands.refactor._collect_files",
            side_effect=RuntimeError("Unexpected error"),
        ):
            runner = CliRunner()
            result = runner.invoke(refactor, [])

            assert result.exit_code == 1

    def test_refactor_files_option_removed(self, tmp_path: Path) -> None:
        """Test that removed --files option is rejected."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1")

        runner = CliRunner()
        result = runner.invoke(refactor, ["--files", str(test_file), "--dry-run"])

        assert result.exit_code == 2  # Click rejects unknown option

    @patch("zerg.commands.refactor.RefactorCommand")
    @patch("zerg.commands.refactor.console")
    def test_refactor_suggestion_with_suggested_text(
        self, mock_console: MagicMock, mock_command_class: MagicMock
    ) -> None:
        """Test refactor displays suggested text when present."""
        suggestions = [
            RefactorSuggestion(
                transform_type=TransformType.SIMPLIFY,
                file="test.py",
                line=1,
                original="if x == True:",
                suggested="if x:",
                reason="Simplify",
            )
        ]
        mock_command = MagicMock()
        mock_command.run.return_value = RefactorResult(
            files_analyzed=1,
            suggestions=suggestions,
            applied=0,
        )
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(refactor, ["--dry-run"])

        assert result.exit_code == 0

    @patch("zerg.commands.refactor.RefactorCommand")
    @patch("zerg.commands.refactor.console")
    def test_refactor_no_suggestions_message(self, mock_console: MagicMock, mock_command_class: MagicMock) -> None:
        """Test refactor shows good code message when no suggestions."""
        mock_command = MagicMock()
        mock_command.run.return_value = RefactorResult(
            files_analyzed=1,
            suggestions=[],
            applied=0,
        )
        mock_command_class.return_value = mock_command

        runner = CliRunner()
        result = runner.invoke(refactor, ["--dry-run"])

        assert result.exit_code == 0
