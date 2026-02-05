"""Unit tests for single-pass directory traversal optimization.

Verifies that detect_project_stack() and _collect_files() use single rglob('*')
traversal pattern instead of multiple separate traversals.

Related: FR-3 from performance-core requirements.
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from zerg.repo_map import _SKIP_DIRS, _collect_files
from zerg.security_rules import detect_project_stack


class TestDetectProjectStackSingleTraversal:
    """Tests for detect_project_stack single-pass traversal."""

    def test_detect_project_stack_finds_languages(self, tmp_path: Path) -> None:
        """detect_project_stack finds all languages in single pass."""
        # Create temp directory with mixed file types
        (tmp_path / "main.py").write_text("# Python file")
        (tmp_path / "app.js").write_text("// JavaScript file")
        (tmp_path / "Dockerfile").write_text("FROM python:3.12")

        # Call detect_project_stack
        stack = detect_project_stack(tmp_path)

        # Verify correct languages detected
        assert "python" in stack.languages
        assert "javascript" in stack.languages

        # Verify correct infrastructure detected
        assert "docker" in stack.infrastructure

    def test_detect_project_stack_handles_nested_files(self, tmp_path: Path) -> None:
        """detect_project_stack finds files in nested directories."""
        # Create nested structure
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("# Python")
        (tmp_path / "lib").mkdir()
        (tmp_path / "lib" / "utils.js").write_text("// JS")
        (tmp_path / "docker-compose.yml").write_text("version: '3'")

        stack = detect_project_stack(tmp_path)

        assert "python" in stack.languages
        assert "javascript" in stack.languages
        assert "docker" in stack.infrastructure

    def test_detect_project_stack_single_rglob_call(self, tmp_path: Path) -> None:
        """detect_project_stack uses only one rglob call with '*' pattern."""
        # Create minimal files
        (tmp_path / "test.py").write_text("# Python")

        # Patch Path.rglob to track calls
        original_rglob = Path.rglob
        rglob_calls: list[str] = []

        def tracking_rglob(self: Path, pattern: str):
            rglob_calls.append(pattern)
            return original_rglob(self, pattern)

        with mock.patch.object(Path, "rglob", tracking_rglob):
            detect_project_stack(tmp_path)

        # Verify rglob was called exactly once with '*' pattern
        assert len(rglob_calls) == 1, f"Expected 1 rglob call, got {len(rglob_calls)}: {rglob_calls}"
        assert rglob_calls[0] == "*", f"Expected pattern '*', got '{rglob_calls[0]}'"

    def test_detect_project_stack_empty_directory(self, tmp_path: Path) -> None:
        """detect_project_stack handles empty directories gracefully."""
        stack = detect_project_stack(tmp_path)

        assert len(stack.languages) == 0
        assert len(stack.infrastructure) == 0


class TestCollectFilesSingleTraversal:
    """Tests for _collect_files single-pass traversal."""

    def test_collect_files_returns_correct_extensions(self, tmp_path: Path) -> None:
        """_collect_files returns only files with correct extensions."""
        # Create mixed file types
        (tmp_path / "main.py").write_text("# Python")
        (tmp_path / "app.js").write_text("// JavaScript")
        (tmp_path / "style.css").write_text("/* CSS */")
        (tmp_path / "data.json").write_text("{}")

        # Collect only Python files
        files = _collect_files(tmp_path, ["python"])
        file_names = [f.name for f in files]

        assert "main.py" in file_names
        assert "app.js" not in file_names
        assert "style.css" not in file_names

    def test_collect_files_multiple_languages(self, tmp_path: Path) -> None:
        """_collect_files handles multiple languages."""
        (tmp_path / "main.py").write_text("# Python")
        (tmp_path / "app.js").write_text("// JavaScript")
        (tmp_path / "component.jsx").write_text("// JSX")
        (tmp_path / "utils.ts").write_text("// TypeScript")
        (tmp_path / "data.txt").write_text("Text")

        files = _collect_files(tmp_path, ["python", "javascript", "typescript"])
        file_names = {f.name for f in files}

        assert "main.py" in file_names
        assert "app.js" in file_names
        assert "component.jsx" in file_names
        assert "utils.ts" in file_names
        assert "data.txt" not in file_names

    def test_collect_files_single_rglob_call(self, tmp_path: Path) -> None:
        """_collect_files uses only one rglob call with '*' pattern."""
        (tmp_path / "test.py").write_text("# Python")

        original_rglob = Path.rglob
        rglob_calls: list[str] = []

        def tracking_rglob(self: Path, pattern: str):
            rglob_calls.append(pattern)
            return original_rglob(self, pattern)

        with mock.patch.object(Path, "rglob", tracking_rglob):
            _collect_files(tmp_path, ["python", "javascript"])

        # Verify single rglob call with '*' pattern
        assert len(rglob_calls) == 1, f"Expected 1 rglob call, got {len(rglob_calls)}: {rglob_calls}"
        assert rglob_calls[0] == "*", f"Expected pattern '*', got '{rglob_calls[0]}'"

    def test_collect_files_skips_directories(self, tmp_path: Path) -> None:
        """_collect_files skips configured directories."""
        # Create files in skip directories
        for skip_dir in [".git", "node_modules", "__pycache__"]:
            skip_path = tmp_path / skip_dir
            skip_path.mkdir()
            (skip_path / "hidden.py").write_text("# Hidden")

        # Create file in allowed location
        (tmp_path / "main.py").write_text("# Main")

        files = _collect_files(tmp_path, ["python"])
        file_names = [f.name for f in files]

        # Should find main.py but not hidden.py in skip dirs
        assert "main.py" in file_names
        assert "hidden.py" not in file_names

    def test_collect_files_skips_dotfiles(self, tmp_path: Path) -> None:
        """_collect_files skips files in dot directories."""
        # Create .hidden directory
        hidden_dir = tmp_path / ".hidden"
        hidden_dir.mkdir()
        (hidden_dir / "secret.py").write_text("# Secret")

        # Create visible file
        (tmp_path / "visible.py").write_text("# Visible")

        files = _collect_files(tmp_path, ["python"])
        file_names = [f.name for f in files]

        assert "visible.py" in file_names
        assert "secret.py" not in file_names

    def test_collect_files_empty_language_list(self, tmp_path: Path) -> None:
        """_collect_files returns empty list for empty language list."""
        (tmp_path / "main.py").write_text("# Python")

        files = _collect_files(tmp_path, [])

        assert not files

    def test_collect_files_nested_structure(self, tmp_path: Path) -> None:
        """_collect_files finds files in nested directories."""
        # Create nested structure
        (tmp_path / "src" / "app").mkdir(parents=True)
        (tmp_path / "src" / "app" / "main.py").write_text("# Main")
        (tmp_path / "src" / "app" / "utils.py").write_text("# Utils")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_main.py").write_text("# Test")

        files = _collect_files(tmp_path, ["python"])

        assert len(files) == 3
        file_names = {f.name for f in files}
        assert "main.py" in file_names
        assert "utils.py" in file_names
        assert "test_main.py" in file_names


class TestSkipDirectoriesHonored:
    """Tests verifying skip directories are properly honored."""

    def test_skip_dirs_constant_matches_expected(self) -> None:
        """_SKIP_DIRS contains expected directories."""
        expected = {"node_modules", "__pycache__", "venv", ".venv", "dist", "build"}
        assert _SKIP_DIRS == expected

    def test_all_skip_dirs_honored_in_collect_files(self, tmp_path: Path) -> None:
        """All directories in _SKIP_DIRS are skipped by _collect_files."""
        # Create a file in each skip directory
        for skip_dir in _SKIP_DIRS:
            skip_path = tmp_path / skip_dir
            skip_path.mkdir()
            (skip_path / "file.py").write_text("# Skipped")

        # Create allowed file
        (tmp_path / "allowed.py").write_text("# Allowed")

        files = _collect_files(tmp_path, ["python"])
        file_names = [f.name for f in files]

        # Only allowed.py should be found
        assert len(files) == 1
        assert "allowed.py" in file_names

    def test_deeply_nested_skip_dirs(self, tmp_path: Path) -> None:
        """Skip directories are honored even when deeply nested."""
        # Create: src/lib/node_modules/dep/index.py
        deep_skip = tmp_path / "src" / "lib" / "node_modules" / "dep"
        deep_skip.mkdir(parents=True)
        (deep_skip / "index.py").write_text("# Should be skipped")

        # Create allowed file
        (tmp_path / "src" / "lib" / "main.py").write_text("# Allowed")

        files = _collect_files(tmp_path, ["python"])
        file_names = [f.name for f in files]

        assert "main.py" in file_names
        assert "index.py" not in file_names


class TestTraversalPerformance:
    """Tests verifying traversal efficiency patterns."""

    def test_no_pattern_specific_rglob_calls(self, tmp_path: Path) -> None:
        """Neither function uses pattern-specific rglob like '*.py'."""
        (tmp_path / "test.py").write_text("# Python")
        (tmp_path / "test.js").write_text("// JS")

        original_rglob = Path.rglob
        pattern_calls: list[str] = []

        def tracking_rglob(self: Path, pattern: str):
            pattern_calls.append(pattern)
            return original_rglob(self, pattern)

        with mock.patch.object(Path, "rglob", tracking_rglob):
            # Call both functions
            detect_project_stack(tmp_path)
            _collect_files(tmp_path, ["python", "javascript"])

        # All calls should be '*', never '*.py' or '*.js'
        for pattern in pattern_calls:
            assert pattern == "*", f"Found pattern-specific rglob: '{pattern}'"

    def test_large_directory_single_traversal(self, tmp_path: Path) -> None:
        """Single traversal handles large directory structures efficiently."""
        # Create a moderately large structure
        for i in range(10):
            subdir = tmp_path / f"pkg_{i}"
            subdir.mkdir()
            for j in range(10):
                (subdir / f"mod_{j}.py").write_text(f"# Module {i}.{j}")

        original_rglob = Path.rglob
        rglob_count = [0]

        def counting_rglob(self: Path, pattern: str):
            rglob_count[0] += 1
            return original_rglob(self, pattern)

        with mock.patch.object(Path, "rglob", counting_rglob):
            files = _collect_files(tmp_path, ["python"])

        # Should find all 100 files with single rglob call
        assert len(files) == 100
        assert rglob_count[0] == 1


class TestEdgeCases:
    """Edge case tests for traversal functions."""

    def test_symlinks_handled(self, tmp_path: Path) -> None:
        """Symlinks are handled without errors."""
        # Create a file and symlink to it
        (tmp_path / "real.py").write_text("# Real")

        # Create symlink (skip on Windows if not supported)
        try:
            (tmp_path / "link.py").symlink_to(tmp_path / "real.py")
        except OSError:
            pytest.skip("Symlinks not supported on this platform")

        files = _collect_files(tmp_path, ["python"])
        # Should handle symlinks without crashing
        assert len(files) >= 1

    def test_special_characters_in_filenames(self, tmp_path: Path) -> None:
        """Files with special characters are handled."""
        # Create files with various special characters
        (tmp_path / "normal.py").write_text("# Normal")
        (tmp_path / "with spaces.py").write_text("# Spaces")
        (tmp_path / "with-dashes.py").write_text("# Dashes")

        files = _collect_files(tmp_path, ["python"])
        file_names = {f.name for f in files}

        assert "normal.py" in file_names
        assert "with spaces.py" in file_names
        assert "with-dashes.py" in file_names

    def test_empty_files_included(self, tmp_path: Path) -> None:
        """Empty files are included in traversal."""
        (tmp_path / "empty.py").write_text("")
        (tmp_path / "nonempty.py").write_text("# Content")

        files = _collect_files(tmp_path, ["python"])
        file_names = {f.name for f in files}

        assert "empty.py" in file_names
        assert "nonempty.py" in file_names

    def test_non_utf8_files(self, tmp_path: Path) -> None:
        """Files with non-UTF8 content are handled in traversal."""
        # Write binary content
        (tmp_path / "binary.py").write_bytes(b"\xff\xfe# Binary\n")
        (tmp_path / "normal.py").write_text("# Normal")

        # _collect_files should not crash
        files = _collect_files(tmp_path, ["python"])
        file_names = {f.name for f in files}

        # Both files should be found (content not read at traversal time)
        assert "binary.py" in file_names
        assert "normal.py" in file_names
