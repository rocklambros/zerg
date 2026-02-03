"""Tests for StateManager load/save edge cases and persistence behavior.

Tests cover:
1. Load with missing state file (creates new)
2. Load with corrupt JSON file
3. Save with write permission error
4. Save creates backup before overwrite
5. Atomic save prevents partial writes
"""

import json
import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from zerg.exceptions import StateError
from zerg.state import StateManager


class TestLoadMissingStateFile:
    """Tests for loading when state file does not exist."""

    def test_load_creates_new_state_when_file_missing(self, tmp_path: Path) -> None:
        """Test that load() creates a new initial state when file doesn't exist."""
        state_dir = tmp_path / "state"
        state_dir.mkdir(parents=True)
        manager = StateManager("new-feature", state_dir=state_dir)

        # Verify file does not exist before load
        state_file = state_dir / "new-feature.json"
        assert not state_file.exists()

        state = manager.load()

        # Should have created initial state structure
        assert state["feature"] == "new-feature"
        assert state["current_level"] == 0
        assert state["tasks"] == {}
        assert state["workers"] == {}
        assert state["levels"] == {}
        assert state["execution_log"] == []
        assert state["paused"] is False
        assert state["error"] is None
        assert "started_at" in state

    def test_load_creates_state_directory_if_missing(self, tmp_path: Path) -> None:
        """Test that load() works even if state directory doesn't exist initially."""
        state_dir = tmp_path / "nested" / "deep" / "state"
        # Do not create the directory - StateManager.__init__ creates it
        manager = StateManager("test-feature", state_dir=state_dir)

        state = manager.load()

        assert state_dir.exists()
        assert state["feature"] == "test-feature"

    def test_load_multiple_times_returns_same_initial_state(self, tmp_path: Path) -> None:
        """Test that multiple loads without save return consistent initial state."""
        manager = StateManager("test-feature", state_dir=tmp_path)

        state1 = manager.load()
        # Modify the returned copy
        state1["current_level"] = 999

        state2 = manager.load()

        # Second load should still have initial values since file was never saved
        assert state2["current_level"] == 0

    def test_load_returns_copy_not_internal_reference(self, tmp_path: Path) -> None:
        """Test that load() returns a copy of state, not the internal reference."""
        manager = StateManager("test-feature", state_dir=tmp_path)

        state = manager.load()
        state["tasks"]["modified"] = {"status": "tampered"}

        # Internal state should not be affected
        fresh_state = manager.load()
        assert "modified" not in fresh_state["tasks"]


class TestLoadCorruptJsonFile:
    """Tests for loading corrupt/invalid JSON files."""

    def test_load_raises_state_error_on_invalid_json(self, tmp_path: Path) -> None:
        """Test that load() raises StateError for invalid JSON."""
        state_file = tmp_path / "corrupt-feature.json"
        state_file.write_text("{ this is not valid json }")

        manager = StateManager("corrupt-feature", state_dir=tmp_path)

        with pytest.raises(StateError) as exc_info:
            manager.load()

        assert "Failed to parse state file" in str(exc_info.value)

    def test_load_raises_state_error_on_truncated_json(self, tmp_path: Path) -> None:
        """Test that load() raises StateError for truncated JSON."""
        state_file = tmp_path / "truncated-feature.json"
        state_file.write_text('{"feature": "test", "current_level": 1')

        manager = StateManager("truncated-feature", state_dir=tmp_path)

        with pytest.raises(StateError) as exc_info:
            manager.load()

        assert "Failed to parse state file" in str(exc_info.value)

    def test_load_raises_state_error_on_empty_file(self, tmp_path: Path) -> None:
        """Test that load() raises StateError for empty file."""
        state_file = tmp_path / "empty-feature.json"
        state_file.write_text("")

        manager = StateManager("empty-feature", state_dir=tmp_path)

        with pytest.raises(StateError) as exc_info:
            manager.load()

        assert "Failed to parse state file" in str(exc_info.value)

    def test_load_raises_state_error_on_null_bytes(self, tmp_path: Path) -> None:
        """Test that load() raises StateError for file with null bytes."""
        state_file = tmp_path / "null-feature.json"
        state_file.write_bytes(b'{"feature": "test"\x00\x00}')

        manager = StateManager("null-feature", state_dir=tmp_path)

        with pytest.raises(StateError) as exc_info:
            manager.load()

        assert "Failed to parse state file" in str(exc_info.value)

    def test_load_raises_on_binary_content(self, tmp_path: Path) -> None:
        """Test that load() raises an exception for binary content.

        Note: The current implementation raises UnicodeDecodeError rather than
        StateError because the file cannot be decoded as UTF-8 text before
        JSON parsing even begins. This test documents the actual behavior.
        """
        state_file = tmp_path / "binary-feature.json"
        state_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00")

        manager = StateManager("binary-feature", state_dir=tmp_path)

        # Current behavior: UnicodeDecodeError is raised (not wrapped in StateError)
        # This could be considered a bug - ideally all file errors should be
        # wrapped in StateError for consistent error handling
        with pytest.raises(UnicodeDecodeError):
            manager.load()

    def test_load_handles_json_with_trailing_comma(self, tmp_path: Path) -> None:
        """Test that load() raises StateError for JSON with trailing comma."""
        state_file = tmp_path / "trailing-comma.json"
        state_file.write_text('{"feature": "test", "level": 1,}')

        manager = StateManager("trailing-comma", state_dir=tmp_path)

        with pytest.raises(StateError) as exc_info:
            manager.load()

        assert "Failed to parse state file" in str(exc_info.value)


class TestSaveWritePermissionError:
    """Tests for save() handling write permission errors."""

    @pytest.mark.skipif(os.name == "nt", reason="Permission tests unreliable on Windows")
    def test_save_raises_on_readonly_directory(self, tmp_path: Path) -> None:
        """Test that save() raises an error when directory is read-only."""
        state_dir = tmp_path / "readonly_state"
        state_dir.mkdir()
        manager = StateManager("test-feature", state_dir=state_dir)
        manager.load()
        manager._state["current_level"] = 5

        # Make directory read-only
        original_mode = state_dir.stat().st_mode
        try:
            state_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)

            with pytest.raises(PermissionError):
                manager.save()
        finally:
            # Restore permissions for cleanup
            state_dir.chmod(original_mode)

    @pytest.mark.skipif(os.name == "nt", reason="Permission tests unreliable on Windows")
    def test_save_succeeds_even_with_readonly_file(self, tmp_path: Path) -> None:
        """Test that atomic save succeeds even when state file is read-only.

        With atomic save, we write to a temp file then rename to the target.
        Renaming overwrites even read-only files on most systems, so this
        should succeed where a direct write would fail.
        """
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager.save()  # Create the file first

        state_file = tmp_path / "test-feature.json"
        original_mode = state_file.stat().st_mode

        try:
            # Make file read-only
            state_file.chmod(stat.S_IRUSR)

            manager._state["current_level"] = 10

            # Atomic save (temp + rename) should succeed despite read-only target
            manager.save()

            # Verify the save worked
            state_file.chmod(original_mode)  # Restore to read
            content = json.loads(state_file.read_text())
            assert content["current_level"] == 10
        finally:
            # Restore permissions for cleanup
            state_file.chmod(original_mode)

    def test_save_handles_oserror_gracefully(self, tmp_path: Path) -> None:
        """Test that save() propagates OSError when write fails."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # Mock open to raise OSError
        with patch("builtins.open", side_effect=OSError("Disk full")):
            with pytest.raises(OSError) as exc_info:
                manager.save()

            assert "Disk full" in str(exc_info.value)


class TestSaveCreatesBackup:
    """Tests for backup creation before overwrite.

    NOTE: The current StateManager implementation does NOT create backups.
    These tests document the expected behavior if backup functionality
    were implemented. They are marked as xfail until the feature is added.
    """

    def test_save_creates_backup_before_overwrite(self, tmp_path: Path) -> None:
        """Test that save() creates a backup file before overwriting."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager._state["current_level"] = 1
        manager.save()

        # Modify and save again
        manager._state["current_level"] = 2
        manager.save()

        # Should have created a backup file
        backup_file = tmp_path / "test-feature.json.bak"
        assert backup_file.exists(), "Backup file should be created on second save"

        # Backup should contain the previous state (level 1)
        backup_content = json.loads(backup_file.read_text())
        assert backup_content["current_level"] == 1

    def test_save_backup_contains_previous_state(self, tmp_path: Path) -> None:
        """Test that backup contains the exact previous state."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager._state["tasks"] = {"TASK-001": {"status": "complete"}}
        manager.save()

        # Modify state significantly
        manager._state["tasks"] = {"TASK-002": {"status": "pending"}}
        manager._state["current_level"] = 5
        manager.save()

        backup_file = tmp_path / "test-feature.json.bak"
        assert backup_file.exists(), "Backup file should exist after second save"
        backup_content = json.loads(backup_file.read_text())

        assert backup_content["tasks"] == {"TASK-001": {"status": "complete"}}
        assert backup_content["current_level"] == 0

    def test_backup_file_created_on_second_save(self, tmp_path: Path) -> None:
        """Test that backup file is created on second save."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager._state["current_level"] = 1
        manager.save()

        # Save again to trigger backup scenario
        manager._state["current_level"] = 2
        manager.save()

        # Backup file should now be created
        backup_file = tmp_path / "test-feature.json.bak"
        assert backup_file.exists(), "Backup file should be created on second save"


class TestAtomicSave:
    """Tests for atomic save preventing partial writes.

    NOTE: The current StateManager implementation does NOT use atomic saves.
    These tests document the expected behavior if atomic save functionality
    were implemented. They are marked as xfail until the feature is added.

    Atomic save pattern: write to temp file, then rename/move to final location.
    This prevents partial writes from corrupting state on crash/interrupt.
    """

    def test_atomic_save_uses_temp_file(self, tmp_path: Path) -> None:
        """Test that save() writes to a temp file first via tempfile.mkstemp."""
        import tempfile

        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        temp_files_created = []
        original_mkstemp = tempfile.mkstemp

        def tracking_mkstemp(*args, **kwargs):
            result = original_mkstemp(*args, **kwargs)
            temp_files_created.append(result[1])  # result is (fd, path)
            return result

        with patch("tempfile.mkstemp", side_effect=tracking_mkstemp):
            manager.save()

        # Should have written to a temp file during save
        assert len(temp_files_created) > 0, "Atomic save should use temp file"
        # Verify the temp file had .tmp suffix
        assert any(".tmp" in f for f in temp_files_created)

    def test_atomic_save_preserves_original_on_write_failure(self, tmp_path: Path) -> None:
        """Test that original file is preserved if write to temp fails.

        With atomic save, if writing to the temp file fails, the original
        file should remain unchanged.
        """
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager._state["current_level"] = 1
        manager.save()

        # Read original content
        state_file = tmp_path / "test-feature.json"
        original_content = state_file.read_text()
        original_parsed = json.loads(original_content)
        assert original_parsed["current_level"] == 1

        # Now simulate a failure during write
        manager._state["current_level"] = 999

        with patch("json.dump", side_effect=OSError("Simulated write failure")):
            with pytest.raises(OSError):
                manager.save()

        # With atomic save, original file should be unchanged
        current_content = state_file.read_text()
        assert current_content == original_content, "Original file should be preserved on failure"

    def test_save_uses_temp_file_for_atomic_write(self, tmp_path: Path) -> None:
        """Test that save uses temp file for atomic write.

        The implementation now uses atomic save: write to temp file, then rename.
        """
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager._state["current_level"] = 1
        manager.save()

        state_file = tmp_path / "test-feature.json"

        # Verify the final file exists and has correct content
        assert state_file.exists()
        content = json.loads(state_file.read_text())
        assert content["current_level"] == 1

        # Verify no leftover temp files
        temp_files = list(tmp_path.glob("*.tmp"))
        assert len(temp_files) == 0, "No temp files should remain after successful save"

    def test_atomic_save_no_partial_content_on_interrupt(self, tmp_path: Path) -> None:
        """Test that state file has no partial content if interrupted mid-write."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager._state["current_level"] = 1
        manager._state["tasks"] = {"TASK-001": {"status": "complete"}}
        manager.save()

        state_file = tmp_path / "test-feature.json"

        # Simulate interruption during write by making json.dump fail partway
        manager._state["current_level"] = 2
        manager._state["tasks"]["TASK-002"] = {"status": "pending"}

        def partial_dump(obj, f, **kwargs):
            f.write('{"feature": "test-feature", "current_level": 2, "tasks":')
            raise OSError("Simulated interrupt during write")

        with patch("json.dump", side_effect=partial_dump):
            with pytest.raises(IOError):
                manager.save()

        # State file should still be valid JSON with original content
        # (atomic save should not have modified it)
        content = state_file.read_text()
        parsed = json.loads(content)
        assert parsed["current_level"] == 1, "Original content should be preserved"


class TestSaveEdgeCases:
    """Additional edge case tests for save() behavior."""

    def test_save_handles_datetime_serialization(self, tmp_path: Path) -> None:
        """Test that save() handles datetime objects via default=str."""
        from datetime import datetime

        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager._state["custom_datetime"] = datetime(2026, 1, 27, 12, 0, 0)

        # Should not raise - datetime should be serialized to string
        manager.save()

        state_file = tmp_path / "test-feature.json"
        content = json.loads(state_file.read_text())
        assert "2026-01-27" in content["custom_datetime"]

    def test_save_handles_large_state(self, tmp_path: Path) -> None:
        """Test that save() handles large state data."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()

        # Add many tasks
        for i in range(1000):
            manager._state["tasks"][f"TASK-{i:04d}"] = {
                "status": "pending",
                "description": f"Task {i} " * 100,  # ~900 chars per task
            }

        manager.save()

        # Verify all data was saved
        state_file = tmp_path / "test-feature.json"
        content = json.loads(state_file.read_text())
        assert len(content["tasks"]) == 1000

    def test_save_creates_valid_json_format(self, tmp_path: Path) -> None:
        """Test that save() creates properly indented JSON."""
        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager._state["current_level"] = 3
        manager.save()

        state_file = tmp_path / "test-feature.json"
        content = state_file.read_text()

        # Should be indented (not minified)
        assert "\n" in content
        assert "  " in content  # Check for indentation

    def test_save_overwrites_existing_content_completely(self, tmp_path: Path) -> None:
        """Test that save() completely overwrites, doesn't append."""
        state_file = tmp_path / "test-feature.json"
        # Write a large initial file
        large_content = {"data": "x" * 10000}
        state_file.write_text(json.dumps(large_content))
        initial_size = state_file.stat().st_size

        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        manager._state = {"feature": "test-feature", "small": True}
        manager.save()

        # New file should be smaller
        final_size = state_file.stat().st_size
        assert final_size < initial_size

        # And should contain only new content
        content = json.loads(state_file.read_text())
        assert "data" not in content or content.get("data") != "x" * 10000


class TestConcurrentAccess:
    """Tests for thread safety and concurrent access patterns."""

    def test_load_save_thread_safety(self, tmp_path: Path) -> None:
        """Test that concurrent load/save operations are thread-safe."""
        import threading
        import time

        manager = StateManager("test-feature", state_dir=tmp_path)
        manager.load()
        errors = []

        def worker(worker_id: int) -> None:
            try:
                for i in range(10):
                    manager._state[f"worker_{worker_id}_key_{i}"] = i
                    manager.save()
                    time.sleep(0.001)
                    manager.load()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent access: {errors}"

    def test_load_under_lock(self, tmp_path: Path) -> None:
        """Test that load() acquires lock properly."""
        manager = StateManager("test-feature", state_dir=tmp_path)

        # Acquire the lock manually
        with manager._lock:
            # Load should still work (reentrant lock)
            state = manager.load()
            assert state["feature"] == "test-feature"
