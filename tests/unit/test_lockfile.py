"""Tests for advisory lockfile functions in zerg.commands._utils."""

import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from zerg.commands._utils import acquire_feature_lock, check_feature_lock, release_feature_lock


class TestAcquireFeatureLock:
    """Tests for acquire_feature_lock()."""

    def test_acquires_lock_when_none_exists(self, tmp_path: Path) -> None:
        """Lock is acquired when no lock file exists; file is created."""
        gsd_dir = str(tmp_path)
        feature = "my-feature"

        result = acquire_feature_lock(feature, gsd_dir=gsd_dir)

        assert result is True
        lock_path = tmp_path / "specs" / feature / ".lock"
        assert lock_path.exists()

        # Verify lock content format: "pid:timestamp"
        content = lock_path.read_text().strip()
        pid_str, ts_str = content.split(":", 1)
        assert int(pid_str) == os.getpid()
        assert float(ts_str) > 0

    def test_returns_false_when_active_lock_exists(self, tmp_path: Path) -> None:
        """Returns False when another session holds an active lock."""
        gsd_dir = str(tmp_path)
        feature = "locked-feature"
        lock_dir = tmp_path / "specs" / feature
        lock_dir.mkdir(parents=True)
        lock_path = lock_dir / ".lock"

        # Write a recent lock from a different PID
        lock_path.write_text(f"99999:{time.time()}")

        result = acquire_feature_lock(feature, gsd_dir=gsd_dir)

        assert result is False
        # Original lock should still be intact
        content = lock_path.read_text()
        assert content.startswith("99999:")

    def test_cleans_up_stale_lock_and_acquires(self, tmp_path: Path) -> None:
        """Stale lock (> 2 hours old) is cleaned up and new lock acquired."""
        gsd_dir = str(tmp_path)
        feature = "stale-feature"
        lock_dir = tmp_path / "specs" / feature
        lock_dir.mkdir(parents=True)
        lock_path = lock_dir / ".lock"

        # Write a lock from 3 hours ago
        stale_timestamp = time.time() - 10800  # 3 hours ago
        lock_path.write_text(f"12345:{stale_timestamp}")

        result = acquire_feature_lock(feature, gsd_dir=gsd_dir)

        assert result is True
        # Verify new lock was written with current PID
        content = lock_path.read_text().strip()
        pid_str, _ = content.split(":", 1)
        assert int(pid_str) == os.getpid()

    def test_cleans_up_corrupt_lock_and_acquires(self, tmp_path: Path) -> None:
        """Corrupt lock file is removed and new lock acquired."""
        gsd_dir = str(tmp_path)
        feature = "corrupt-feature"
        lock_dir = tmp_path / "specs" / feature
        lock_dir.mkdir(parents=True)
        lock_path = lock_dir / ".lock"

        # Write garbage content
        lock_path.write_text("not-valid-lock-content")

        result = acquire_feature_lock(feature, gsd_dir=gsd_dir)

        assert result is True
        content = lock_path.read_text().strip()
        pid_str, ts_str = content.split(":", 1)
        assert int(pid_str) == os.getpid()
        assert float(ts_str) > 0

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Lock acquisition creates parent directories if they do not exist."""
        gsd_dir = str(tmp_path)
        feature = "new-feature"

        # Verify the specs dir does not exist yet
        assert not (tmp_path / "specs" / feature).exists()

        result = acquire_feature_lock(feature, gsd_dir=gsd_dir)

        assert result is True
        assert (tmp_path / "specs" / feature / ".lock").exists()

    def test_lock_just_at_boundary_is_still_active(self, tmp_path: Path) -> None:
        """A lock exactly at the 2-hour boundary is still considered active."""
        gsd_dir = str(tmp_path)
        feature = "boundary-feature"
        lock_dir = tmp_path / "specs" / feature
        lock_dir.mkdir(parents=True)
        lock_path = lock_dir / ".lock"

        # Write a lock at exactly 7200 seconds ago (boundary)
        current_time = time.time()
        boundary_timestamp = current_time - 7200
        lock_path.write_text(f"54321:{boundary_timestamp}")

        # At the boundary (time.time() - ts == 7200), the condition > 7200 is False
        # so the lock should be considered active
        with patch("zerg.commands._utils.time") as mock_time:
            mock_time.time.return_value = current_time
            result = acquire_feature_lock(feature, gsd_dir=gsd_dir)

        assert result is False


class TestReleaseFeatureLock:
    """Tests for release_feature_lock()."""

    def test_removes_lock_file(self, tmp_path: Path) -> None:
        """Lock file is removed on release."""
        gsd_dir = str(tmp_path)
        feature = "release-me"
        lock_dir = tmp_path / "specs" / feature
        lock_dir.mkdir(parents=True)
        lock_path = lock_dir / ".lock"
        lock_path.write_text(f"{os.getpid()}:{time.time()}")

        release_feature_lock(feature, gsd_dir=gsd_dir)

        assert not lock_path.exists()

    def test_no_error_when_lock_does_not_exist(self, tmp_path: Path) -> None:
        """No error raised when releasing a lock that does not exist."""
        gsd_dir = str(tmp_path)
        feature = "no-lock-here"

        # Should not raise
        release_feature_lock(feature, gsd_dir=gsd_dir)

    def test_no_error_when_spec_dir_does_not_exist(self, tmp_path: Path) -> None:
        """No error raised when the spec directory itself does not exist."""
        gsd_dir = str(tmp_path)
        feature = "nonexistent-spec"

        # The specs/feature directory does not exist at all
        assert not (tmp_path / "specs" / feature).exists()

        # Should not raise
        release_feature_lock(feature, gsd_dir=gsd_dir)


class TestCheckFeatureLock:
    """Tests for check_feature_lock()."""

    def test_returns_dict_for_active_lock(self, tmp_path: Path) -> None:
        """Returns dict with pid, timestamp, age_seconds for active lock."""
        gsd_dir = str(tmp_path)
        feature = "active-check"
        lock_dir = tmp_path / "specs" / feature
        lock_dir.mkdir(parents=True)
        lock_path = lock_dir / ".lock"

        current_time = 1700000000.0
        lock_timestamp = current_time - 300  # 5 minutes ago
        lock_path.write_text(f"42:{lock_timestamp}")

        with patch("zerg.commands._utils.time") as mock_time:
            mock_time.time.return_value = current_time
            result = check_feature_lock(feature, gsd_dir=gsd_dir)

        assert result is not None
        assert result["pid"] == 42
        assert result["timestamp"] == lock_timestamp
        assert result["age_seconds"] == pytest.approx(300.0, abs=1.0)

    def test_returns_none_when_no_lock(self, tmp_path: Path) -> None:
        """Returns None when no lock file exists."""
        gsd_dir = str(tmp_path)
        feature = "unlocked"

        result = check_feature_lock(feature, gsd_dir=gsd_dir)

        assert result is None

    def test_returns_none_when_lock_is_stale(self, tmp_path: Path) -> None:
        """Returns None when the lock is older than 2 hours (stale)."""
        gsd_dir = str(tmp_path)
        feature = "stale-check"
        lock_dir = tmp_path / "specs" / feature
        lock_dir.mkdir(parents=True)
        lock_path = lock_dir / ".lock"

        # Lock from 3 hours ago
        stale_timestamp = time.time() - 10800
        lock_path.write_text(f"12345:{stale_timestamp}")

        result = check_feature_lock(feature, gsd_dir=gsd_dir)

        assert result is None

    def test_returns_none_for_corrupt_lock(self, tmp_path: Path) -> None:
        """Returns None for a lock file with corrupt/unparseable content."""
        gsd_dir = str(tmp_path)
        feature = "corrupt-check"
        lock_dir = tmp_path / "specs" / feature
        lock_dir.mkdir(parents=True)
        lock_path = lock_dir / ".lock"

        lock_path.write_text("garbage-data-no-colon")

        result = check_feature_lock(feature, gsd_dir=gsd_dir)

        assert result is None

    def test_returns_none_for_empty_lock_file(self, tmp_path: Path) -> None:
        """Returns None for an empty lock file."""
        gsd_dir = str(tmp_path)
        feature = "empty-lock"
        lock_dir = tmp_path / "specs" / feature
        lock_dir.mkdir(parents=True)
        lock_path = lock_dir / ".lock"

        lock_path.write_text("")

        result = check_feature_lock(feature, gsd_dir=gsd_dir)

        assert result is None

    def test_returns_none_for_non_numeric_pid(self, tmp_path: Path) -> None:
        """Returns None when the PID portion is not a valid integer."""
        gsd_dir = str(tmp_path)
        feature = "bad-pid"
        lock_dir = tmp_path / "specs" / feature
        lock_dir.mkdir(parents=True)
        lock_path = lock_dir / ".lock"

        lock_path.write_text(f"not-a-pid:{time.time()}")

        result = check_feature_lock(feature, gsd_dir=gsd_dir)

        # check_feature_lock parses pid with int() which raises ValueError
        # for non-numeric strings, but the try/except catches ValueError
        # Note: the int() call happens AFTER the stale check, so the function
        # will attempt int("not-a-pid") which raises ValueError -> returns None
        assert result is None
