"""Integration test: IncrementalIndex with repo map formatting.

Verifies: create temp Python files -> IncrementalIndex.update_incremental() ->
get_stats() -> format_repo_map_stats(). No API keys needed.
"""

from __future__ import annotations

from pathlib import Path

from zerg.repo_map import IncrementalIndex
from zerg.status_formatter import format_repo_map_stats


def _write_python_file(filepath: Path, content: str) -> None:
    """Write a Python source file, creating parent dirs as needed."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")


class TestIncrementalIndexWiring:
    """End-to-end test for incremental indexing and stats formatting."""

    def test_index_then_modify_detects_change(self, tmp_path: Path) -> None:
        """Full lifecycle: index -> get_stats -> modify -> re-index -> verify."""
        repo_root = tmp_path / "repo"
        state_dir = tmp_path / "state"
        repo_root.mkdir()
        state_dir.mkdir()

        # Step 1: Create a Python file with one function
        py_file = repo_root / "module_a.py"
        _write_python_file(
            py_file,
            'def greet(name: str) -> str:\n    """Say hello."""\n    return f"Hello, {name}"\n',
        )

        # Step 2: Create IncrementalIndex and run first indexing
        index = IncrementalIndex(state_dir=state_dir)
        graph = index.update_incremental(root=repo_root, languages=["python"])

        # Step 3: Verify initial stats
        stats = index.get_stats()
        assert stats["indexed_files"] >= 1, f"Expected at least 1 indexed file, got {stats}"
        assert stats["total_files"] >= 1
        assert stats["last_updated"] is not None

        # The symbol graph should contain our function
        all_symbols = []
        for mod_symbols in graph.modules.values():
            all_symbols.extend(mod_symbols)
        symbol_names = [s.name for s in all_symbols]
        assert "greet" in symbol_names

        # Step 4: Format stats for dashboard
        formatted = format_repo_map_stats(stats)
        assert "Files tracked" in formatted
        assert "Files indexed" in formatted

        # Record initial stale count (all files are new on first index)
        stats["stale_files"]

        # Step 5: Modify the file (add a new function)
        _write_python_file(
            py_file,
            (
                'def greet(name: str) -> str:\n    """Say hello."""\n    return f"Hello, {name}"\n\n'
                'def farewell(name: str) -> str:\n    """Say goodbye."""\n    return f"Bye, {name}"\n'
            ),
        )

        # Step 6: Re-index — should detect the MD5 change
        graph2 = index.update_incremental(root=repo_root, languages=["python"])
        stats2 = index.get_stats()

        # The stale count should be >= 1 because the file changed
        assert stats2["stale_files"] >= 1

        # The new function should appear in the graph
        all_symbols2 = []
        for mod_symbols in graph2.modules.values():
            all_symbols2.extend(mod_symbols)
        symbol_names2 = [s.name for s in all_symbols2]
        assert "greet" in symbol_names2
        assert "farewell" in symbol_names2

        # Step 7: Format updated stats
        formatted2 = format_repo_map_stats(stats2)
        assert "Files tracked" in formatted2

    def test_unchanged_file_not_reindexed(self, tmp_path: Path) -> None:
        """A file with the same content should not be marked stale on re-index."""
        repo_root = tmp_path / "repo"
        state_dir = tmp_path / "state"
        repo_root.mkdir()
        state_dir.mkdir()

        py_file = repo_root / "stable.py"
        _write_python_file(py_file, "X = 42\n")

        index = IncrementalIndex(state_dir=state_dir)

        # First index: file is new -> stale
        index.update_incremental(root=repo_root, languages=["python"])
        stats1 = index.get_stats()
        assert stats1["stale_files"] >= 1

        # Second index: file unchanged -> stale should be 0
        index.update_incremental(root=repo_root, languages=["python"])
        stats2 = index.get_stats()
        assert stats2["stale_files"] == 0

    def test_multiple_files_selective_reparse(self, tmp_path: Path) -> None:
        """Only changed files should be re-extracted on update."""
        repo_root = tmp_path / "repo"
        state_dir = tmp_path / "state"
        repo_root.mkdir()
        state_dir.mkdir()

        file_a = repo_root / "a.py"
        file_b = repo_root / "b.py"
        _write_python_file(file_a, "def func_a(): pass\n")
        _write_python_file(file_b, "def func_b(): pass\n")

        index = IncrementalIndex(state_dir=state_dir)

        # First index: both files are new
        index.update_incremental(root=repo_root, languages=["python"])
        stats1 = index.get_stats()
        assert stats1["stale_files"] == 2
        assert stats1["total_files"] == 2

        # Modify only file_a
        _write_python_file(file_a, "def func_a(): pass\ndef func_a2(): pass\n")

        # Re-index: only file_a should be stale
        index.update_incremental(root=repo_root, languages=["python"])
        stats2 = index.get_stats()
        assert stats2["stale_files"] == 1
        assert stats2["total_files"] == 2

    def test_format_repo_map_stats_with_real_index_data(self, tmp_path: Path) -> None:
        """Verify format_repo_map_stats handles real IncrementalIndex output."""
        repo_root = tmp_path / "repo"
        state_dir = tmp_path / "state"
        repo_root.mkdir()
        state_dir.mkdir()

        _write_python_file(repo_root / "example.py", "Y = 99\n")

        index = IncrementalIndex(state_dir=state_dir)
        index.update_incremental(root=repo_root, languages=["python"])
        stats = index.get_stats()

        formatted = format_repo_map_stats(stats)
        assert "No repo map data available" not in formatted
        assert "Files tracked" in formatted
        # Should show at least 1 file
        assert str(stats["total_files"]) in formatted
