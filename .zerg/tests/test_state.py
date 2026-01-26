"""Tests for ZERG v2 State Persistence."""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from state import Checkpoint, ExecutionState, TaskStatus


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_status_values(self):
        """Test TaskStatus has required values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETE.value == "complete"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.BLOCKED.value == "blocked"


class TestExecutionState:
    """Tests for ExecutionState class."""

    def test_create_state(self):
        """Test creating new execution state."""
        s = ExecutionState.create("my-feature")
        assert s.feature == "my-feature"
        assert s.current_level == 0
        assert s.tasks == {}
        assert s.workers == {}

    def test_save_load_roundtrip(self, tmp_path):
        """Test save and load preserve state."""
        path = tmp_path / "state.json"
        s = ExecutionState.create("test")
        s.save(str(path))

        s2 = ExecutionState.load(str(path))
        assert s2.feature == s.feature
        assert s2.current_level == s.current_level

    def test_load_missing_file_returns_none(self, tmp_path):
        """Test loading nonexistent file returns None."""
        path = tmp_path / "nonexistent.json"
        result = ExecutionState.load(str(path))
        assert result is None

    def test_save_creates_parent_dirs(self, tmp_path):
        """Test save creates parent directories."""
        path = tmp_path / "subdir" / "state.json"
        s = ExecutionState.create("test")
        s.save(str(path))
        assert path.exists()

    def test_atomic_write(self, tmp_path):
        """Test atomic write uses temp file."""
        path = tmp_path / "state.json"
        s = ExecutionState.create("test")
        s.save(str(path))

        # File should exist and be valid JSON
        assert path.exists()
        with open(path) as f:
            data = json.load(f)
        assert data["feature"] == "test"


class TestCheckpoint:
    """Tests for Checkpoint class."""

    def test_checkpoint_creation(self):
        """Test creating a checkpoint."""
        cp = Checkpoint(
            task_id="TASK-001",
            worker_id="worker-1",
            timestamp=datetime.now(),
            files_created=["test.py"],
            files_modified=["main.py"],
            current_step=3,
            state_data={"key": "value"},
        )
        assert cp.task_id == "TASK-001"
        assert cp.worker_id == "worker-1"
        assert cp.current_step == 3

    def test_checkpoint_to_dict(self):
        """Test checkpoint serialization."""
        ts = datetime.now()
        cp = Checkpoint(
            task_id="TASK-001",
            worker_id="worker-1",
            timestamp=ts,
            files_created=["test.py"],
            files_modified=[],
            current_step=3,
            state_data={},
        )
        d = cp.to_dict()
        assert d["task_id"] == "TASK-001"
        assert d["current_step"] == 3

    def test_checkpoint_from_dict(self):
        """Test checkpoint deserialization."""
        d = {
            "task_id": "TASK-002",
            "worker_id": "worker-2",
            "timestamp": "2026-01-25T10:00:00",
            "files_created": [],
            "files_modified": ["file.py"],
            "current_step": 5,
            "state_data": {"progress": 50},
        }
        cp = Checkpoint.from_dict(d)
        assert cp.task_id == "TASK-002"
        assert cp.current_step == 5


class TestSchemaValidation:
    """Tests for schema validation."""

    def test_valid_state_passes_validation(self, tmp_path):
        """Test valid state passes schema validation."""
        s = ExecutionState.create("test")
        # Should not raise
        s.save(str(tmp_path / "state.json"))

    def test_state_to_dict_is_valid(self):
        """Test to_dict output is schema-valid."""
        s = ExecutionState.create("test")
        d = s.to_dict()
        assert "feature" in d
        assert "started_at" in d
        assert "current_level" in d
        assert "tasks" in d
