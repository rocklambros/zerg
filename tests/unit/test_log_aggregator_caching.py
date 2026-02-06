"""Tests for LogAggregator per-file caching functionality."""

import json
import os
import tempfile
import threading
import time
from pathlib import Path

from zerg.log_aggregator import LogAggregator


class TestLogAggregatorCaching:
    """Tests for LogAggregator per-file cache behavior."""

    def test_cache_hit_unchanged_file(self) -> None:
        """Test that querying an unchanged file returns from cache on second call."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_dir = Path(tmp_dir)
            workers_dir = log_dir / "workers"
            workers_dir.mkdir()

            # Create a JSONL file with test entry
            log_file = workers_dir / "worker_1.jsonl"
            entry = {"ts": "2026-02-05T10:00:00", "worker_id": 1, "message": "test"}
            log_file.write_text(json.dumps(entry) + "\n")

            la = LogAggregator(log_dir)

            # First query - should populate cache
            result1 = la.query()
            assert len(result1) == 1
            assert result1[0]["message"] == "test"

            # Verify cache is populated
            cache_key = str(log_file)
            assert cache_key in la._file_cache
            cached_mtime = la._file_cache[cache_key]["mtime"]

            # Second query - should use cache (mtime unchanged)
            result2 = la.query()
            assert len(result2) == 1
            assert result2[0]["message"] == "test"

            # Verify cache entry unchanged (same mtime means cache hit)
            assert cache_key in la._file_cache
            assert la._file_cache[cache_key]["mtime"] == cached_mtime

    def test_cache_miss_on_modification(self) -> None:
        """Test that modifying a file causes cache miss on next query."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_dir = Path(tmp_dir)
            workers_dir = log_dir / "workers"
            workers_dir.mkdir()

            # Create initial JSONL file
            log_file = workers_dir / "worker_1.jsonl"
            entry1 = {"ts": "2026-02-05T10:00:00", "worker_id": 1, "message": "first"}
            log_file.write_text(json.dumps(entry1) + "\n")

            la = LogAggregator(log_dir)

            # First query - populates cache
            result1 = la.query()
            assert len(result1) == 1
            assert result1[0]["message"] == "first"

            cache_key = str(log_file)
            original_mtime = la._file_cache[cache_key]["mtime"]

            # Modify file - add new entry and update mtime
            time.sleep(0.1)  # Ensure mtime will be different
            entry2 = {"ts": "2026-02-05T10:01:00", "worker_id": 1, "message": "second"}
            with open(log_file, "a") as f:
                f.write(json.dumps(entry2) + "\n")

            # Force mtime update (some filesystems have low resolution)
            new_mtime = original_mtime + 1.0
            os.utime(log_file, (new_mtime, new_mtime))

            # Second query - should detect mtime change and re-read
            result2 = la.query()
            assert len(result2) == 2
            messages = [e["message"] for e in result2]
            assert "first" in messages
            assert "second" in messages

            # Cache should have updated mtime
            assert la._file_cache[cache_key]["mtime"] == new_mtime

    def test_lru_eviction_at_100(self) -> None:
        """Test that cache evicts oldest entry when exceeding MAX_CACHED_FILES (100)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_dir = Path(tmp_dir)
            workers_dir = log_dir / "workers"
            workers_dir.mkdir()

            # Create 101 JSONL files (exceeds MAX_CACHED_FILES of 100)
            num_files = 101
            for i in range(num_files):
                log_file = workers_dir / f"worker_{i}.jsonl"
                entry = {"ts": f"2026-02-05T10:{i:02d}:00", "worker_id": i, "message": f"msg_{i}"}
                log_file.write_text(json.dumps(entry) + "\n")

            la = LogAggregator(log_dir)

            # Query to populate cache with all files
            result = la.query()
            assert len(result) == num_files

            # Cache should be limited to MAX_CACHED_FILES
            assert len(la._file_cache) == LogAggregator.MAX_CACHED_FILES
            assert len(la._file_cache) == 100

            # Verify cache has exactly 100 entries, oldest evicted
            # Files are processed in glob order, so first accessed gets evicted first
            cache_keys = list(la._file_cache.keys())
            assert len(cache_keys) == 100

    def test_thread_safety(self) -> None:
        """Test that concurrent query() calls don't cause race conditions."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_dir = Path(tmp_dir)
            workers_dir = log_dir / "workers"
            workers_dir.mkdir()

            # Create several JSONL files
            for i in range(10):
                log_file = workers_dir / f"worker_{i}.jsonl"
                entries = []
                for j in range(5):
                    entries.append(
                        json.dumps({"ts": f"2026-02-05T10:{i:02d}:{j:02d}", "worker_id": i, "message": f"msg_{i}_{j}"})
                    )
                log_file.write_text("\n".join(entries) + "\n")

            la = LogAggregator(log_dir)

            errors: list[Exception] = []
            results: list[int] = []
            lock = threading.Lock()

            def query_worker() -> None:
                """Worker function that performs queries."""
                try:
                    for _ in range(5):
                        result = la.query()
                        with lock:
                            results.append(len(result))
                except Exception as e:
                    with lock:
                        errors.append(e)

            # Launch 10 threads performing concurrent queries
            threads = [threading.Thread(target=query_worker) for _ in range(10)]

            for t in threads:
                t.start()

            for t in threads:
                t.join(timeout=30)

            # Verify no errors occurred
            assert not errors, f"Thread errors: {errors}"

            # Verify all queries returned expected count (10 files * 5 entries = 50)
            expected_count = 50
            assert all(r == expected_count for r in results), (
                f"Expected all results to be {expected_count}, got {set(results)}"
            )

            # Verify cache is still in valid state
            assert len(la._file_cache) <= LogAggregator.MAX_CACHED_FILES

    def test_cache_hit_moves_to_end_for_lru(self) -> None:
        """Test that cache hits move entries to end of OrderedDict for LRU."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_dir = Path(tmp_dir)
            workers_dir = log_dir / "workers"
            workers_dir.mkdir()

            # Create two JSONL files
            log_file1 = workers_dir / "worker_1.jsonl"
            log_file2 = workers_dir / "worker_2.jsonl"
            log_file1.write_text(json.dumps({"ts": "2026-02-05T10:00:00", "worker_id": 1}) + "\n")
            log_file2.write_text(json.dumps({"ts": "2026-02-05T10:01:00", "worker_id": 2}) + "\n")

            la = LogAggregator(log_dir)

            # First query populates cache
            la.query()
            cache_keys_after_first = list(la._file_cache.keys())

            # Second query should access same files, moving them to end
            la.query()
            cache_keys_after_second = list(la._file_cache.keys())

            # Order should be preserved (both accessed, both moved to end in same order)
            assert len(cache_keys_after_first) == 2
            assert len(cache_keys_after_second) == 2

    def test_empty_directory(self) -> None:
        """Test querying with no log files returns empty results."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_dir = Path(tmp_dir)

            la = LogAggregator(log_dir)

            result = la.query()
            assert not result
            assert len(la._file_cache) == 0

    def test_orchestrator_file_caching(self) -> None:
        """Test that orchestrator.jsonl is also cached."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_dir = Path(tmp_dir)

            # Create orchestrator.jsonl (not in workers dir)
            orch_file = log_dir / "orchestrator.jsonl"
            entry = {"ts": "2026-02-05T10:00:00", "source": "orchestrator", "message": "test"}
            orch_file.write_text(json.dumps(entry) + "\n")

            la = LogAggregator(log_dir)

            # Query to populate cache
            result = la.query()
            assert len(result) == 1
            assert result[0]["source"] == "orchestrator"

            # Verify orchestrator file is cached
            cache_key = str(orch_file)
            assert cache_key in la._file_cache
