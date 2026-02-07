"""Tests for StateManager load/save edge cases and persistence behavior.

Tests cover:
1. Load with missing state file (creates new)
2. Load with corrupt JSON file
3. Save with write permission error
4. Atomic save prevents partial writes
"""

import json
import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from zerg.exceptions import StateError
from zerg.state import StateManager


class TestLoadEdgeCases:
    """Tests for loading edge cases: missing files, corrupt JSON, copy semantics."""

    def test_load_creates_new_state_and_returns_copy(self, tmp_path: Path) -> None:
        """Test load creates initial state when file missing and returns a copy."""
        state_dir = tmp_path / "state"
        state_dir.mkdir(parents=True)
        manager = StateManager("new-feature", state_dir=state_dir)

        state = manager.load()
        assert state["feature"] == "new-feature"
        assert state["current_level"] == 0
        assert state["tasks"] == {}

        # Verify returned state is a copy
        state["current_level"] = 999
        assert manager.load()["current_level"] == 0

    @pytest.mark.parametrize(
        "content,name",
        [
            ("{ this is not valid json }", "invalid"),
            ('{"feature": "test", "current_level": 1', "truncated"),
            ("", "empty"),
            ('{"feature": "test", "level": 1,}', "trailing-comma"),
        ],
        ids=["invalid-json", "truncated-json", "empty-file", "trailing-comma"],
    )
    def test_load_raises_state_error_on_corrupt_json(self, tmp_path: Path, content: str, name: str) -> None:
        """Test load raises StateError for various corrupt JSON formats."""
        feature = f"{name}-feature"
        (tmp_path / f"{feature}.json").write_text(content)
        manager = StateManager(feature, state_dir=tmp_path)
        with pytest.raises(StateError, match="Failed to parse state file"):
            manager.load()

    def test_load_raises_on_binary_content(self, tmp_path: Path) -> None:
        """Test load raises for binary content (UnicodeDecodeError)."""
        (tmp_path / "binary-feature.json").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00")
        manager = StateManager("binary-feature", state_dir=tmp_path)
        with pytest.raises(UnicodeDecodeError):
            manager.load()


class TestSaveEdgeCases:
    """Tests for save edge cases: permissions, datetime, atomic writes."""

    @pytest.mark.skipif(os.name == "nt", reason="Permission tests unreliable on Windows")
    def test_save_raises_on_readonly_directory(self, tmp_path: Path) -> None:
        """Test save raises PermissionError on read-only directory."""
        state_dir = tmp_path / "readonly_state"
        state_dir.mkdir()
        manager = StateManager("test-feature", state_dir=state_dir)
        manager.load()
        original_mode = state_dir.stat().st_mode
        try:
            state_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)
            with pytest.raises(PermissionError):
                manager.save()
        finally:
            state_dir.chmod(original_mode)

    def test_save_handles_datetime_and_creates_valid_json(self, tmp_path: Path) -> None:
        """Test save handles datetime objects and creates valid indented JSON."""
        from datetime import datetime

        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager._persistence._state["custom_datetime"] = datetime(2026, 1, 27, 12, 0, 0)
        manager.save()

        state_file = tmp_path / "test-feature.json"
        content = state_file.read_text()
        assert "2026-01-27" in content
        assert "\n" in content  # Indented, not minified

    def test_atomic_save_preserves_original_on_write_failure(self, tmp_path: Path) -> None:
        """Test original file preserved if write to temp file fails."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager._persistence._state["current_level"] = 1
        manager.save()

        original_content = (tmp_path / "test-feature.json").read_text()
        manager._persistence._state["current_level"] = 999

        with patch("json.dump", side_effect=OSError("Simulated write failure")):
            with pytest.raises(OSError):
                manager.save()

        assert (tmp_path / "test-feature.json").read_text() == original_content

    def test_save_overwrites_existing_content_completely(self, tmp_path: Path) -> None:
        """Test save completely overwrites, doesn't append."""
        state_file = tmp_path / "test-feature.json"
        state_file.write_text(json.dumps({"data": "x" * 10000}))
        initial_size = state_file.stat().st_size

        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager._persistence._state = {"feature": "test-feature", "small": True}
        manager.save()

        assert state_file.stat().st_size < initial_size


class TestConcurrentAccess:
    """Tests for thread safety."""

    def test_load_save_thread_safety(self, tmp_path: Path) -> None:
        """Test concurrent load/save operations are thread-safe."""
        import threading
        import time

        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        errors = []

        def worker(worker_id: int) -> None:
            try:
                for i in range(10):
                    manager._persistence._state[f"worker_{worker_id}_key_{i}"] = i
                    manager.save()
                    time.sleep(0.001)
                    manager.load()
            except (OSError, json.JSONDecodeError, KeyError, StateError) as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0, f"Errors during concurrent access: {errors}"
