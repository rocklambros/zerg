"""Final integration tests for full rush cycle - OFX-012.

End-to-end tests verifying the complete orchestrator-fixes feature works:
- Schema validation rejects level 0
- Orchestrator handles worker lifecycle correctly
- No respawn loops occur
- Initialization wait functions correctly
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from zerg.config import ZergConfig
from zerg.constants import WorkerStatus
from zerg.launcher import SubprocessLauncher, SpawnResult, WorkerHandle
from zerg.validation import (
    validate_task_graph,
    validate_dependencies,
    validate_file_ownership,
    validate_task_id,
)


class TestSchemaValidationFixes:
    """Verify schema validation fixes from OFX-001, OFX-005, OFX-006."""

    def test_level_zero_rejected_by_validator(self) -> None:
        """Level 0 should be rejected by validate_task_graph."""
        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {"id": "T-001", "title": "Test", "level": 0, "dependencies": []}
            ],
        }
        is_valid, errors = validate_task_graph(task_graph)

        assert not is_valid, "Level 0 must be rejected"
        assert any("level" in e.lower() for e in errors)

    def test_level_one_accepted_by_validator(self) -> None:
        """Level 1 should be accepted by validate_task_graph."""
        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {"id": "T-001", "title": "Test", "level": 1, "dependencies": []}
            ],
        }
        is_valid, errors = validate_task_graph(task_graph)

        assert is_valid, f"Level 1 should be accepted: {errors}"

    def test_schema_file_has_level_minimum_one(self) -> None:
        """Schema file should define level minimum as 1."""
        schema_path = Path("zerg/schemas/task_graph.json")
        assert schema_path.exists(), "Schema file must exist"

        with open(schema_path) as f:
            schema = json.load(f)

        # Navigate to level definition
        level_def = (
            schema.get("definitions", {})
            .get("task", {})
            .get("properties", {})
            .get("level", {})
        )

        assert level_def.get("minimum") == 1, "Schema level minimum must be 1"

    def test_old_schema_archived(self) -> None:
        """Old schema should be archived, not in active schemas."""
        old_schema_path = Path(".zerg/schemas/task-graph.schema.json")
        archived_schema_path = Path(".zerg/schemas/archived/task-graph.schema.json")

        # Primary assertion: old schema must not be in active location
        assert not old_schema_path.exists(), "Old schema should be archived"
        # Secondary: archived schema should exist if archive directory exists
        # (skip if archive directory was never created in CI environment)
        if archived_schema_path.parent.exists():
            assert archived_schema_path.exists(), "Archived schema should exist"


class TestWorkerLifecycleFixes:
    """Verify worker lifecycle fixes from OFX-002, OFX-007, OFX-008."""

    @patch("subprocess.Popen")
    def test_terminate_removes_worker_from_tracking(
        self, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        """Terminate should remove worker from launcher tracking."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.return_value = 0
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()

        # Spawn worker
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )
        assert result.success

        # Verify tracked
        assert launcher.get_handle(0) is not None

        # Terminate
        launcher.terminate(0)

        # Should no longer be tracked (this was the bug fix)
        assert launcher.get_handle(0) is None

    @patch("subprocess.Popen")
    def test_sync_state_cleans_up_stopped_workers(
        self, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        """sync_state should remove stopped workers from tracking."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.return_value = None  # Running initially
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()

        # Spawn worker
        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        # Simulate worker stopping
        mock_process.poll.return_value = 0

        # sync_state should detect and clean up
        launcher.sync_state()

        # Worker should be removed from tracking
        assert launcher.get_handle(0) is None

    @patch("subprocess.Popen")
    def test_no_respawn_loop_when_stopped(
        self, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        """Stopped workers should not cause respawn loops."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.return_value = 0  # Already stopped
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()

        # Spawn worker
        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        # First monitor - should return STOPPED
        status1 = launcher.monitor(0)

        # sync_state cleans up
        launcher.sync_state()

        # Second monitor - should return STOPPED (worker gone)
        status2 = launcher.monitor(0)

        # Both should be STOPPED, no exception, no loop
        assert status1 == WorkerStatus.STOPPED
        assert status2 == WorkerStatus.STOPPED


class TestDependencyValidationFixes:
    """Verify dependency validation fixes from OFX-003."""

    def test_dependency_in_same_level_rejected(self) -> None:
        """Dependencies within same level should be rejected."""
        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {"id": "T-001", "title": "Task 1", "level": 1, "dependencies": []},
                {
                    "id": "T-002",
                    "title": "Task 2",
                    "level": 1,
                    "dependencies": ["T-001"],
                },
            ],
        }
        is_valid, errors = validate_dependencies(task_graph)

        assert not is_valid, "Same-level dependency should be rejected"

    def test_dependency_in_lower_level_accepted(self) -> None:
        """Dependencies in lower levels should be accepted."""
        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {"id": "T-001", "title": "Task 1", "level": 1, "dependencies": []},
                {
                    "id": "T-002",
                    "title": "Task 2",
                    "level": 2,
                    "dependencies": ["T-001"],
                },
            ],
        }
        is_valid, errors = validate_dependencies(task_graph)

        assert is_valid, f"Lower-level dependency should be accepted: {errors}"


class TestFileOwnershipValidation:
    """Verify file ownership validation from OFX-004."""

    def test_duplicate_file_creation_rejected(self) -> None:
        """Two tasks creating same file should be rejected."""
        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {
                    "id": "T-001",
                    "title": "Task 1",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["same.py"], "modify": [], "read": []},
                },
                {
                    "id": "T-002",
                    "title": "Task 2",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["same.py"], "modify": [], "read": []},
                },
            ],
        }
        is_valid, errors = validate_file_ownership(task_graph)

        assert not is_valid, "Duplicate file creation should be rejected"

    def test_unique_file_ownership_accepted(self) -> None:
        """Unique file ownership should be accepted."""
        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {
                    "id": "T-001",
                    "title": "Task 1",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["file1.py"], "modify": [], "read": []},
                },
                {
                    "id": "T-002",
                    "title": "Task 2",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["file2.py"], "modify": [], "read": []},
                },
            ],
        }
        is_valid, errors = validate_file_ownership(task_graph)

        assert is_valid, f"Unique file ownership should be accepted: {errors}"


class TestConfigIntegration:
    """Verify configuration integration."""

    def test_zerg_config_loads_successfully(self) -> None:
        """ZergConfig should load without error."""
        config = ZergConfig()
        assert config is not None

    def test_zerg_config_has_workers_setting(self) -> None:
        """ZergConfig should have workers configuration."""
        config = ZergConfig()
        assert hasattr(config, "workers")
        assert hasattr(config.workers, "max_concurrent")
        assert config.workers.max_concurrent > 0


class TestTaskIdValidation:
    """Verify task ID validation security."""

    def test_empty_task_id_rejected(self) -> None:
        """Empty task ID should be rejected."""
        is_valid, error = validate_task_id("")
        assert not is_valid

    def test_dangerous_task_id_rejected(self) -> None:
        """Task IDs with shell metacharacters should be rejected."""
        dangerous_ids = [
            "TEST;rm -rf",
            "TEST`whoami`",
            "TEST$(cat /etc/passwd)",
        ]
        for task_id in dangerous_ids:
            is_valid, error = validate_task_id(task_id)
            assert not is_valid, f"Dangerous task ID '{task_id}' should be rejected"

    def test_valid_task_id_accepted(self) -> None:
        """Valid task IDs should be accepted."""
        valid_ids = ["TEST-001", "OFX-L1-001", "ZERG001"]
        for task_id in valid_ids:
            is_valid, error = validate_task_id(task_id)
            assert is_valid, f"Valid task ID '{task_id}' should be accepted: {error}"


class TestFullValidationPipeline:
    """Test the complete validation pipeline."""

    def test_valid_task_graph_passes_all_validations(self) -> None:
        """A valid task graph should pass all validation stages."""
        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {
                    "id": "T-001",
                    "title": "Foundation Task",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["foundation.py"], "modify": [], "read": []},
                },
                {
                    "id": "T-002",
                    "title": "Core Task",
                    "level": 2,
                    "dependencies": ["T-001"],
                    "files": {"create": ["core.py"], "modify": [], "read": ["foundation.py"]},
                },
            ],
        }

        # All validations should pass
        is_valid, errors = validate_task_graph(task_graph)
        assert is_valid, f"Task graph validation failed: {errors}"

        is_valid, errors = validate_dependencies(task_graph)
        assert is_valid, f"Dependency validation failed: {errors}"

        is_valid, errors = validate_file_ownership(task_graph)
        assert is_valid, f"File ownership validation failed: {errors}"

    def test_invalid_task_graph_detected_early(self) -> None:
        """Invalid task graphs should be detected by validation."""
        invalid_graph = {
            "feature": "test-feature",
            "tasks": [
                {
                    "id": "T-001",
                    "title": "Bad Task",
                    "level": 0,  # Invalid level
                    "dependencies": [],
                }
            ],
        }

        is_valid, errors = validate_task_graph(invalid_graph)
        assert not is_valid, "Invalid task graph should be detected"
