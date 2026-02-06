"""Tests for ZergConfig singleton caching with mtime invalidation.

Tests cover:
- Singleton pattern returns same instance
- mtime-based cache invalidation on file changes
- force_reload parameter bypasses cache
- Thread safety under concurrent access
- invalidate_cache() method works correctly
"""

import os
import threading
import time
from pathlib import Path

import pytest

from zerg.config import ZergConfig


@pytest.fixture(autouse=True)
def reset_cache() -> None:
    """Reset ZergConfig cache before and after each test."""
    ZergConfig.invalidate_cache()
    yield
    ZergConfig.invalidate_cache()


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Create a temporary .zerg directory with config file."""
    zerg_dir = tmp_path / ".zerg"
    zerg_dir.mkdir()
    return zerg_dir


@pytest.fixture
def config_file(config_dir: Path) -> Path:
    """Create a config file with default content."""
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        """
workers:
  max_concurrent: 5
  timeout_minutes: 30
"""
    )
    return config_path


class TestSingletonPattern:
    """Tests for singleton behavior of ZergConfig.load()."""

    def test_singleton_returns_same_instance(
        self, tmp_path: Path, config_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that consecutive calls to load() return the same instance."""
        monkeypatch.chdir(tmp_path)

        c1 = ZergConfig.load()
        c2 = ZergConfig.load()

        assert c1 is c2, "load() should return cached singleton instance"

    def test_singleton_with_explicit_path(self, config_file: Path) -> None:
        """Test singleton behavior with explicit config path."""
        c1 = ZergConfig.load(config_path=config_file)
        c2 = ZergConfig.load(config_path=config_file)

        assert c1 is c2, "load() with explicit path should use cache"

    def test_different_paths_different_instances(self, config_dir: Path, tmp_path: Path) -> None:
        """Test that different config paths result in different instances."""
        # Create two config files
        config1 = config_dir / "config.yaml"
        config1.write_text("workers:\n  max_concurrent: 5\n")

        config2 = tmp_path / "other_config.yaml"
        config2.write_text("workers:\n  max_concurrent: 10\n")

        c1 = ZergConfig.load(config_path=config1)

        # Invalidate to switch paths
        ZergConfig.invalidate_cache()
        c2 = ZergConfig.load(config_path=config2)

        assert c1 is not c2, "Different paths should produce different instances"
        assert c1.workers.max_concurrent == 5
        assert c2.workers.max_concurrent == 10


class TestMtimeInvalidation:
    """Tests for mtime-based cache invalidation."""

    def test_mtime_invalidation_on_file_change(
        self, tmp_path: Path, config_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that modifying the config file invalidates the cache."""
        monkeypatch.chdir(tmp_path)

        # Load initial config
        c1 = ZergConfig.load()
        assert c1.workers.max_concurrent == 5

        # Wait a bit to ensure mtime changes (some filesystems have 1s resolution)
        time.sleep(0.1)

        # Modify the file
        config_file.write_text(
            """
workers:
  max_concurrent: 10
  timeout_minutes: 60
"""
        )

        # Update mtime explicitly to ensure change is detected
        current_time = time.time()
        os.utime(config_file, (current_time, current_time))

        # Load again - should get new instance due to mtime change
        c2 = ZergConfig.load()

        assert c1 is not c2, "Changed mtime should invalidate cache"
        assert c2.workers.max_concurrent == 10

    def test_unchanged_file_uses_cache(
        self, tmp_path: Path, config_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that unchanged file returns cached instance."""
        monkeypatch.chdir(tmp_path)

        c1 = ZergConfig.load()

        # Don't modify the file, just load again
        c2 = ZergConfig.load()

        assert c1 is c2, "Unchanged file should return cached instance"

    def test_mtime_uses_utime_manipulation(self, config_file: Path) -> None:
        """Test that os.utime can be used to simulate file changes."""
        c1 = ZergConfig.load(config_path=config_file)

        # Use os.utime to change mtime without modifying content
        future_time = time.time() + 100
        os.utime(config_file, (future_time, future_time))

        c2 = ZergConfig.load(config_path=config_file)

        assert c1 is not c2, "os.utime mtime change should invalidate cache"


class TestForceReload:
    """Tests for force_reload parameter."""

    def test_force_reload_bypasses_cache(
        self, tmp_path: Path, config_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that force_reload=True returns a new instance."""
        monkeypatch.chdir(tmp_path)

        c1 = ZergConfig.load()
        c2 = ZergConfig.load(force_reload=True)

        assert c1 is not c2, "force_reload=True should bypass cache"

    def test_force_reload_updates_cache(
        self, tmp_path: Path, config_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that force_reload updates the cached instance."""
        monkeypatch.chdir(tmp_path)

        c1 = ZergConfig.load()
        c2 = ZergConfig.load(force_reload=True)
        c3 = ZergConfig.load()  # Should use the new cached instance

        assert c1 is not c2
        assert c2 is c3, "Subsequent load should use newly cached instance"

    def test_force_reload_with_modified_file(
        self, tmp_path: Path, config_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test force_reload picks up file changes immediately."""
        monkeypatch.chdir(tmp_path)

        c1 = ZergConfig.load()
        assert c1.workers.max_concurrent == 5

        # Modify file (max_concurrent must be <= 10 per WorkersConfig validation)
        config_file.write_text("workers:\n  max_concurrent: 8\n")

        # Force reload to pick up changes
        c2 = ZergConfig.load(force_reload=True)

        assert c2.workers.max_concurrent == 8


class TestThreadSafety:
    """Tests for thread safety under concurrent access."""

    def test_concurrent_load_returns_same_instance(
        self, tmp_path: Path, config_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that concurrent loads all return the same instance."""
        monkeypatch.chdir(tmp_path)

        results: list[ZergConfig] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def load_config() -> None:
            try:
                config = ZergConfig.load()
                with lock:
                    results.append(config)
            except Exception as e:
                with lock:
                    errors.append(e)

        # Launch 10 threads concurrently
        threads = [threading.Thread(target=load_config) for _ in range(10)]

        for t in threads:
            t.start()

        for t in threads:
            t.join(timeout=5.0)

        assert not errors, f"Errors during concurrent access: {errors}"
        assert len(results) == 10, "All threads should complete successfully"

        # All instances should be the same object
        first = results[0]
        for config in results[1:]:
            assert config is first, "All threads should receive same cached instance"

    def test_concurrent_load_with_force_reload(
        self, tmp_path: Path, config_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test concurrent access with some force_reload calls."""
        monkeypatch.chdir(tmp_path)

        results: list[ZergConfig] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def load_config(force: bool = False) -> None:
            try:
                config = ZergConfig.load(force_reload=force)
                with lock:
                    results.append(config)
            except Exception as e:
                with lock:
                    errors.append(e)

        # Mix of normal and force_reload calls
        threads = []
        for i in range(10):
            force = i % 3 == 0  # Every 3rd thread forces reload
            threads.append(threading.Thread(target=load_config, args=(force,)))

        for t in threads:
            t.start()

        for t in threads:
            t.join(timeout=5.0)

        assert not errors, f"Errors during concurrent access: {errors}"
        assert len(results) == 10, "All threads should complete successfully"

        # All results should be valid ZergConfig instances
        for config in results:
            assert isinstance(config, ZergConfig)
            assert config.workers.max_concurrent == 5

    def test_no_race_conditions_in_cache_update(
        self, tmp_path: Path, config_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that cache updates don't cause race conditions."""
        monkeypatch.chdir(tmp_path)

        errors: list[Exception] = []
        lock = threading.Lock()

        def stress_test() -> None:
            try:
                for _ in range(50):
                    config = ZergConfig.load()
                    # Verify config is valid
                    _ = config.workers.max_concurrent
                    _ = config.to_dict()
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=stress_test) for _ in range(5)]

        for t in threads:
            t.start()

        for t in threads:
            t.join(timeout=10.0)

        assert not errors, f"Race condition errors: {errors}"


class TestInvalidateCache:
    """Tests for invalidate_cache() method."""

    def test_invalidate_cache_clears_singleton(
        self, tmp_path: Path, config_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that invalidate_cache() causes next load to create new instance."""
        monkeypatch.chdir(tmp_path)

        c1 = ZergConfig.load()
        ZergConfig.invalidate_cache()
        c2 = ZergConfig.load()

        assert c1 is not c2, "invalidate_cache should clear singleton"

    def test_invalidate_cache_resets_all_state(self, config_file: Path) -> None:
        """Test that invalidate_cache resets path and mtime tracking."""
        # Load with explicit path to populate cache
        _ = ZergConfig.load(config_path=config_file)

        # Invalidate
        ZergConfig.invalidate_cache()

        # Verify internal state is cleared
        assert ZergConfig._cached_instance is None
        assert ZergConfig._cache_mtime is None
        assert ZergConfig._cache_path is None

    def test_invalidate_cache_is_thread_safe(
        self, tmp_path: Path, config_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that invalidate_cache is thread-safe."""
        monkeypatch.chdir(tmp_path)

        errors: list[Exception] = []
        lock = threading.Lock()

        def load_and_invalidate() -> None:
            try:
                for _ in range(20):
                    config = ZergConfig.load()
                    _ = config.workers.max_concurrent
                    ZergConfig.invalidate_cache()
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=load_and_invalidate) for _ in range(5)]

        for t in threads:
            t.start()

        for t in threads:
            t.join(timeout=10.0)

        assert not errors, f"Thread safety errors: {errors}"


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_missing_file_creates_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that missing config file creates default config."""
        monkeypatch.chdir(tmp_path)

        # No .zerg directory or config file
        config = ZergConfig.load()

        assert config is not None
        assert config.workers.max_concurrent == 5  # Default value

    def test_missing_file_caches_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that default config is cached when file doesn't exist."""
        monkeypatch.chdir(tmp_path)

        c1 = ZergConfig.load()
        c2 = ZergConfig.load()

        assert c1 is c2, "Default config should be cached"

    def test_file_deletion_after_cache(
        self, tmp_path: Path, config_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test behavior when config file is deleted after caching."""
        monkeypatch.chdir(tmp_path)

        # Load and cache
        c1 = ZergConfig.load()
        assert c1.workers.max_concurrent == 5

        # Delete the file
        config_file.unlink()

        # Cache should still be valid for now (file was deleted, mtime check fails)
        # But invalidate and reload should create default
        ZergConfig.invalidate_cache()
        c2 = ZergConfig.load()

        # c2 should be a default config since file is gone
        assert c2.workers.max_concurrent == 5  # Default value

    def test_empty_config_file(self, tmp_path: Path, config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading empty config file."""
        monkeypatch.chdir(tmp_path)

        config_file = config_dir / "config.yaml"
        config_file.write_text("")

        config = ZergConfig.load()

        assert config is not None
        # Should use defaults for all values
        assert config.workers.max_concurrent == 5

    def test_partial_config_file(self, tmp_path: Path, config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading config with only some values specified."""
        monkeypatch.chdir(tmp_path)

        config_file = config_dir / "config.yaml"
        config_file.write_text("workers:\n  max_concurrent: 8\n")

        config = ZergConfig.load()

        assert config.workers.max_concurrent == 8
        assert config.workers.timeout_minutes == 30  # Default


class TestCacheWithDifferentPaths:
    """Tests for cache behavior with different config paths."""

    def test_switching_paths_reloads(self, tmp_path: Path) -> None:
        """Test that switching config paths causes reload."""
        # Create two config files
        dir1 = tmp_path / "project1" / ".zerg"
        dir1.mkdir(parents=True)
        config1 = dir1 / "config.yaml"
        config1.write_text("workers:\n  max_concurrent: 3\n")

        dir2 = tmp_path / "project2" / ".zerg"
        dir2.mkdir(parents=True)
        config2 = dir2 / "config.yaml"
        config2.write_text("workers:\n  max_concurrent: 7\n")

        # Load first config
        c1 = ZergConfig.load(config_path=config1)
        assert c1.workers.max_concurrent == 3

        # Load second config (different path)
        c2 = ZergConfig.load(config_path=config2)

        # Should get new instance since path changed
        assert c2 is not c1
        assert c2.workers.max_concurrent == 7

    def test_absolute_vs_relative_paths(
        self, tmp_path: Path, config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that absolute and relative paths to same file are treated consistently."""
        monkeypatch.chdir(tmp_path)

        config_file = config_dir / "config.yaml"
        config_file.write_text("workers:\n  max_concurrent: 6\n")

        # Load with relative path (default)
        c1 = ZergConfig.load()

        # Load with absolute path
        c2 = ZergConfig.load(config_path=config_file.resolve())

        # Both should work and have correct values
        assert c1.workers.max_concurrent == 6
        assert c2.workers.max_concurrent == 6
