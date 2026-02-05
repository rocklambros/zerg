"""Tests for RepoMap TTL-based caching.

Tests the caching behavior of build_map() including:
- Cache hits within TTL
- Cache misses after TTL expiration
- Cache invalidation via invalidate_cache()
- Thread safety under concurrent access
- Different root directories produce cache misses
"""

import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from zerg.repo_map import build_map, invalidate_cache


class TestRepoMapCaching:
    """Tests for RepoMap TTL-based caching."""

    @pytest.fixture(autouse=True)
    def setup_clean_cache(self) -> None:
        """Ensure clean cache state before each test."""
        invalidate_cache()

    @pytest.fixture
    def temp_repo(self, tmp_path: Path) -> Path:
        """Create a temporary directory with a Python file for testing.

        Args:
            tmp_path: pytest's temporary directory fixture

        Returns:
            Path to the temporary repository directory
        """
        # Create a simple Python file for the repo map to parse
        test_file = tmp_path / "sample.py"
        test_file.write_text(
            '''"""Sample module for testing."""


def sample_function(x: int) -> int:
    """Return x squared."""
    return x * x


class SampleClass:
    """A sample class."""

    def method(self) -> str:
        """Return a greeting."""
        return "hello"
'''
        )
        return tmp_path

    def test_cache_hit_within_ttl(self, temp_repo: Path) -> None:
        """Test that repeated calls within TTL return the same cached object.

        Verifies that two consecutive calls to build_map() return the exact
        same SymbolGraph instance (object identity, not just equality).
        """
        g1 = build_map(temp_repo)
        g2 = build_map(temp_repo)

        # Same object instance should be returned
        assert g1 is g2, "Expected same cached object within TTL"

    def test_cache_miss_after_ttl(self, temp_repo: Path) -> None:
        """Test that cache expires after TTL (30 seconds).

        Mocks time.time() to simulate TTL expiration and verifies
        that a new SymbolGraph is built after expiration.
        """
        # Build initial graph
        with patch("zerg.repo_map.time.time") as mock_time:
            # First call at t=0
            mock_time.return_value = 1000.0
            g1 = build_map(temp_repo)

            # Second call at t=5s (within TTL) - should hit cache
            mock_time.return_value = 1005.0
            g2 = build_map(temp_repo)
            assert g1 is g2, "Expected cache hit within TTL"

            # Third call at t=31s (after TTL) - should miss cache
            mock_time.return_value = 1031.0
            g3 = build_map(temp_repo)

            # Should be a different object after TTL expiration
            assert g1 is not g3, "Expected new object after TTL expiration"

    def test_invalidate_cache(self, temp_repo: Path) -> None:
        """Test that invalidate_cache() clears the cached result.

        Verifies that after calling invalidate_cache(), the next call
        to build_map() returns a new SymbolGraph instance.
        """
        g1 = build_map(temp_repo)

        # Invalidate the cache
        invalidate_cache()

        g2 = build_map(temp_repo)

        # Should be different objects after invalidation
        assert g1 is not g2, "Expected new object after cache invalidation"

    def test_thread_safety(self, temp_repo: Path) -> None:
        """Test that concurrent calls to build_map() are thread-safe.

        Launches multiple threads calling build_map() concurrently and
        verifies no race conditions occur and all threads get valid results.
        """
        results: list = []
        errors: list = []
        num_threads = 10

        def call_build_map() -> None:
            try:
                graph = build_map(temp_repo)
                results.append(graph)
            except Exception as e:
                errors.append(e)

        # Launch threads
        threads = [threading.Thread(target=call_build_map) for _ in range(num_threads)]

        for t in threads:
            t.start()

        for t in threads:
            t.join(timeout=10)

        # No errors should have occurred
        assert not errors, f"Thread errors occurred: {errors}"

        # All threads should have gotten a result
        assert len(results) == num_threads, f"Expected {num_threads} results, got {len(results)}"

        # All results should be the same cached instance
        first_result = results[0]
        for result in results[1:]:
            assert result is first_result, "All threads should receive same cached instance"

    def test_different_root_cache_miss(self, tmp_path: Path) -> None:
        """Test that different root directories produce cache misses.

        Verifies that build_map() with different root paths returns
        different SymbolGraph instances, not the cached one.
        """
        # Create two separate directories with Python files
        dir1 = tmp_path / "repo1"
        dir1.mkdir()
        (dir1 / "module1.py").write_text('"""Module 1."""\n\ndef func1(): pass\n')

        dir2 = tmp_path / "repo2"
        dir2.mkdir()
        (dir2 / "module2.py").write_text('"""Module 2."""\n\ndef func2(): pass\n')

        g1 = build_map(dir1)
        g2 = build_map(dir2)

        # Different roots should produce different graphs
        assert g1 is not g2, "Different root directories should not share cache"

        # Verify each graph has the expected module
        assert any("module1" in key for key in g1.modules.keys()), "g1 should contain module1"
        assert any("module2" in key for key in g2.modules.keys()), "g2 should contain module2"

    def test_different_languages_cache_miss(self, temp_repo: Path) -> None:
        """Test that different language configurations produce cache misses.

        Verifies that build_map() with different languages parameter
        returns different SymbolGraph instances.
        """
        g1 = build_map(temp_repo, languages=["python"])
        g2 = build_map(temp_repo, languages=["python", "javascript"])

        # Different languages should produce different graphs
        assert g1 is not g2, "Different language configs should not share cache"

    def test_cache_reuse_after_same_root_second_time(self, tmp_path: Path) -> None:
        """Test cache is properly keyed by root path.

        After accessing dir1, dir2, and then dir1 again, the third call
        should NOT hit the original cache (which was invalidated by dir2).
        """
        dir1 = tmp_path / "repo1"
        dir1.mkdir()
        (dir1 / "test.py").write_text('"""Test."""\n')

        dir2 = tmp_path / "repo2"
        dir2.mkdir()
        (dir2 / "test.py").write_text('"""Test."""\n')

        # First call with dir1
        g1 = build_map(dir1)

        # Second call with dir2 (should replace cache)
        g2 = build_map(dir2)

        # Third call with dir1 again (cache was replaced, should rebuild)
        g3 = build_map(dir1)

        # g1 and g3 should be different objects (cache was replaced)
        assert g1 is not g3, "Cache should have been replaced by intermediate call"
        assert g2 is not g3, "g2 and g3 should be different"

    def test_invalidate_cache_is_idempotent(self) -> None:
        """Test that multiple calls to invalidate_cache() are safe.

        Verifies that calling invalidate_cache() multiple times
        in succession does not cause errors.
        """
        # Should not raise any errors
        invalidate_cache()
        invalidate_cache()
        invalidate_cache()

    def test_build_map_returns_valid_graph(self, temp_repo: Path) -> None:
        """Test that build_map returns a valid SymbolGraph.

        Verifies the returned graph contains expected symbols from
        the test Python file.
        """
        graph = build_map(temp_repo)

        # Should have at least one module
        assert len(graph.modules) > 0, "Graph should contain at least one module"

        # Find the sample module
        sample_module = None
        for key in graph.modules:
            if "sample" in key:
                sample_module = graph.modules[key]
                break

        assert sample_module is not None, "Should find sample module"

        # Check for expected symbols
        symbol_names = [s.name for s in sample_module]
        assert "sample_function" in symbol_names, "Should contain sample_function"
        assert "SampleClass" in symbol_names, "Should contain SampleClass"
