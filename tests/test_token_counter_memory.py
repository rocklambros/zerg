"""Tests for TokenCounter in-memory cache functionality."""

import json
import threading
import time
from pathlib import Path

from zerg.config import TokenMetricsConfig
from zerg.token_counter import TokenCounter, TokenResult


class TestTokenCounterCache:
    """Tests for TokenCounter in-memory caching."""

    def test_cache_hit_returns_cache_source(self, tmp_path: Path, monkeypatch) -> None:
        """Test that second call returns result with source='cache'."""
        # Patch STATE_DIR to use temp path
        monkeypatch.setattr("zerg.token_counter.STATE_DIR", str(tmp_path))

        config = TokenMetricsConfig(
            cache_enabled=True,
            api_counting=False,  # Use heuristic to avoid API calls
            cache_ttl_seconds=3600,
        )
        tc = TokenCounter(config)

        # First call - should compute and store
        result1 = tc.count("test text for caching")
        assert result1.source in ("heuristic", "api")

        # Second call - should return from cache
        result2 = tc.count("test text for caching")
        assert result2.source == "cache"
        assert result2.count == result1.count
        assert result2.mode == result1.mode

    def test_lru_eviction_at_10000(self, tmp_path: Path, monkeypatch) -> None:
        """Test that cache evicts oldest entries when exceeding 10000."""
        monkeypatch.setattr("zerg.token_counter.STATE_DIR", str(tmp_path))

        config = TokenMetricsConfig(
            cache_enabled=True,
            api_counting=False,
            cache_ttl_seconds=3600,
        )
        tc = TokenCounter(config)

        # Add 10001 unique entries
        for i in range(10001):
            tc.count(f"unique text entry number {i}")

        # Verify cache has at most MAX_CACHE_ENTRIES
        assert len(tc._cache) <= TokenCounter.MAX_CACHE_ENTRIES
        assert len(tc._cache) == 10000

    def test_file_persistence(self, tmp_path: Path, monkeypatch) -> None:
        """Test that cache persists to file and loads on new instance."""
        monkeypatch.setattr("zerg.token_counter.STATE_DIR", str(tmp_path))

        config = TokenMetricsConfig(
            cache_enabled=True,
            api_counting=False,
            cache_ttl_seconds=3600,
        )

        # Create first TokenCounter, count some text
        tc1 = TokenCounter(config)
        test_text = "persistent test text"
        result1 = tc1.count(test_text)

        # Verify cache file exists
        cache_file = tmp_path / "token-cache.json"
        assert cache_file.exists()

        # Verify file contains the entry
        with open(cache_file) as f:
            data = json.load(f)
        assert data

        # Create new TokenCounter (should load from file)
        tc2 = TokenCounter(config)

        # Verify cached entry is present - should get cache hit
        result2 = tc2.count(test_text)
        assert result2.source == "cache"
        assert result2.count == result1.count

    def test_thread_safety(self, tmp_path: Path, monkeypatch) -> None:
        """Test that concurrent count() calls don't cause race conditions."""
        monkeypatch.setattr("zerg.token_counter.STATE_DIR", str(tmp_path))

        config = TokenMetricsConfig(
            cache_enabled=True,
            api_counting=False,
            cache_ttl_seconds=3600,
        )
        tc = TokenCounter(config)

        errors: list[Exception] = []
        results: list[TokenResult] = []
        lock = threading.Lock()

        def worker(thread_id: int) -> None:
            """Worker function for concurrent testing."""
            try:
                for i in range(100):
                    # Mix of shared and unique texts
                    if i % 2 == 0:
                        text = f"shared text {i % 10}"
                    else:
                        text = f"unique text thread {thread_id} iteration {i}"

                    result = tc.count(text)

                    with lock:
                        results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        # Launch 10 threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join()

        # Verify no errors occurred
        assert not errors, f"Thread errors: {errors}"

        # Verify we got results from all threads
        assert len(results) == 1000  # 10 threads * 100 iterations

    def test_cache_disabled(self, tmp_path: Path, monkeypatch) -> None:
        """Test that cache can be disabled via config."""
        monkeypatch.setattr("zerg.token_counter.STATE_DIR", str(tmp_path))

        config = TokenMetricsConfig(
            cache_enabled=False,
            api_counting=False,
        )
        tc = TokenCounter(config)

        # Call twice
        result1 = tc.count("test text")
        result2 = tc.count("test text")

        # Neither should be from cache when disabled
        assert result1.source == "heuristic"
        assert result2.source == "heuristic"

    def test_cache_ttl_expiration(self, tmp_path: Path, monkeypatch) -> None:
        """Test that cache entries expire after TTL."""
        monkeypatch.setattr("zerg.token_counter.STATE_DIR", str(tmp_path))

        # Use minimum allowed TTL
        config = TokenMetricsConfig(
            cache_enabled=True,
            api_counting=False,
            cache_ttl_seconds=60,  # Minimum allowed TTL
        )
        tc = TokenCounter(config)

        # First call
        result1 = tc.count("expiring text")
        assert result1.source == "heuristic"

        # Immediate second call - should hit cache
        result2 = tc.count("expiring text")
        assert result2.source == "cache"

        # Simulate TTL expiration by manipulating the cache entry timestamp
        import hashlib

        text_hash = hashlib.sha256(b"expiring text").hexdigest()
        with tc._cache_lock:
            if text_hash in tc._cache:
                # Set timestamp to expired (more than TTL seconds ago)
                tc._cache[text_hash]["timestamp"] = time.time() - 61

        # Third call - should miss cache due to TTL
        result3 = tc.count("expiring text")
        assert result3.source == "heuristic"

    def test_lru_order_maintained(self, tmp_path: Path, monkeypatch) -> None:
        """Test that LRU order is maintained correctly."""
        monkeypatch.setattr("zerg.token_counter.STATE_DIR", str(tmp_path))

        # Temporarily reduce max cache size for easier testing
        original_max = TokenCounter.MAX_CACHE_ENTRIES
        monkeypatch.setattr(TokenCounter, "MAX_CACHE_ENTRIES", 3)

        config = TokenMetricsConfig(
            cache_enabled=True,
            api_counting=False,
            cache_ttl_seconds=3600,
        )
        tc = TokenCounter(config)

        # Add 3 entries
        tc.count("first")
        tc.count("second")
        tc.count("third")

        assert len(tc._cache) == 3

        # Access "first" to move it to end (most recently used)
        tc.count("first")

        # Add a 4th entry - should evict "second" (least recently used)
        tc.count("fourth")

        assert len(tc._cache) == 3

        # "second" should be evicted (was LRU after "first" was accessed)
        # "first", "third", "fourth" should remain

        # Count again - "second" should miss cache
        result_second = tc.count("second")
        assert result_second.source == "heuristic"  # Was evicted

        # "first" should still hit cache
        result_first = tc.count("first")
        assert result_first.source == "cache"  # Still in cache

        # Restore original max
        monkeypatch.setattr(TokenCounter, "MAX_CACHE_ENTRIES", original_max)

    def test_o1_lookup_performance(self, tmp_path: Path, monkeypatch) -> None:
        """Test that cache lookup is O(1) - constant time regardless of size."""
        monkeypatch.setattr("zerg.token_counter.STATE_DIR", str(tmp_path))

        config = TokenMetricsConfig(
            cache_enabled=True,
            api_counting=False,
            cache_ttl_seconds=3600,
        )
        tc = TokenCounter(config)

        # Pre-populate cache with 5000 entries
        for i in range(5000):
            tc.count(f"prepopulated entry {i}")

        # Measure time for cache hit
        test_text = "performance test text"
        tc.count(test_text)  # First call to cache it

        # Time multiple cache hits
        start = time.perf_counter()
        for _ in range(1000):
            result = tc.count(test_text)
            assert result.source == "cache"
        elapsed = time.perf_counter() - start

        # 1000 cache hits should complete in well under 1 second
        # O(1) lookup means this shouldn't scale with cache size
        assert elapsed < 1.0, f"Cache lookup too slow: {elapsed}s for 1000 lookups"
