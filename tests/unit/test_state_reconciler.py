"""Tests for ZERG state reconciler module.

Comprehensive tests for reconciliation logic, level parsing from task IDs,
inconsistency detection and fixes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.constants import TaskStatus
from zerg.state_reconciler import (
    ReconciliationFix,
    ReconciliationResult,
    StateReconciler,
)


class TestReconciliationFix:
    """Tests for ReconciliationFix dataclass."""

    def test_creation(self) -> None:
        fix = ReconciliationFix(
            fix_type="task_status_sync",
            task_id="RES-L3-001",
            level=3,
            worker_id=2,
            old_value="pending",
            new_value="complete",
            reason="Disk shows complete, syncing to LevelController",
        )
        assert fix.fix_type == "task_status_sync"
        assert fix.task_id == "RES-L3-001"
        assert fix.level == 3
        assert fix.worker_id == 2
        assert fix.old_value == "pending"
        assert fix.new_value == "complete"

    def test_to_dict(self) -> None:
        fix = ReconciliationFix(
            fix_type="level_parsed",
            task_id="COV-L2-005",
            level=2,
            worker_id=None,
            old_value=None,
            new_value=2,
            reason="Parsed level 2 from task ID pattern",
        )
        d = fix.to_dict()
        assert d["fix_type"] == "level_parsed"
        assert d["task_id"] == "COV-L2-005"
        assert d["level"] == 2
        assert d["worker_id"] is None
        assert d["old_value"] is None
        assert d["new_value"] == 2
        assert "Parsed level" in d["reason"]

    def test_to_dict_with_none_task_id(self) -> None:
        fix = ReconciliationFix(
            fix_type="level_counts_corrected",
            task_id=None,
            level=1,
            worker_id=None,
            old_value={"completed": 2, "failed": 1},
            new_value={"completed": 3, "failed": 1},
            reason="Corrected level task counts from disk state",
        )
        d = fix.to_dict()
        assert d["task_id"] is None
        assert d["level"] == 1


class TestReconciliationResult:
    """Tests for ReconciliationResult dataclass."""

    def test_default_creation(self) -> None:
        result = ReconciliationResult(reconciliation_type="periodic")
        assert result.reconciliation_type == "periodic"
        assert result.timestamp is not None
        assert result.fixes_applied == []
        assert result.divergences_found == 0
        assert result.tasks_checked == 0
        assert result.workers_checked == 0
        assert result.level_checked is None
        assert result.errors == []

    def test_success_property_no_errors(self) -> None:
        result = ReconciliationResult(reconciliation_type="periodic")
        assert result.success is True

    def test_success_property_with_errors(self) -> None:
        result = ReconciliationResult(
            reconciliation_type="level_transition",
            errors=["Task X not in terminal state"],
        )
        assert result.success is False

    def test_had_fixes_property_false(self) -> None:
        result = ReconciliationResult(reconciliation_type="periodic")
        assert result.had_fixes is False

    def test_had_fixes_property_true(self) -> None:
        fix = ReconciliationFix(
            fix_type="test",
            task_id="A-L1-001",
            level=1,
            worker_id=None,
            old_value="x",
            new_value="y",
            reason="test fix",
        )
        result = ReconciliationResult(
            reconciliation_type="periodic",
            fixes_applied=[fix],
        )
        assert result.had_fixes is True

    def test_to_dict(self) -> None:
        fix = ReconciliationFix(
            fix_type="task_status_sync",
            task_id="A-L1-001",
            level=1,
            worker_id=1,
            old_value="pending",
            new_value="complete",
            reason="Disk shows complete",
        )
        result = ReconciliationResult(
            reconciliation_type="level_transition",
            fixes_applied=[fix],
            divergences_found=1,
            tasks_checked=5,
            workers_checked=2,
            level_checked=1,
        )
        d = result.to_dict()
        assert d["reconciliation_type"] == "level_transition"
        assert "timestamp" in d
        assert len(d["fixes_applied"]) == 1
        assert d["divergences_found"] == 1
        assert d["tasks_checked"] == 5
        assert d["workers_checked"] == 2
        assert d["level_checked"] == 1
        assert d["success"] is True
        assert d["had_fixes"] is True


class TestParseLevelFromTaskId:
    """Tests for parse_level_from_task_id method."""

    @pytest.fixture
    def reconciler(self) -> StateReconciler:
        """Create a StateReconciler with mocked dependencies."""
        mock_state = MagicMock()
        mock_state._state = {"tasks": {}, "workers": {}}
        mock_levels = MagicMock()
        return StateReconciler(state=mock_state, levels=mock_levels)

    def test_parses_standard_format(self, reconciler: StateReconciler) -> None:
        """Test parsing level from standard task ID format."""
        assert reconciler.parse_level_from_task_id("RES-L3-003") == 3
        assert reconciler.parse_level_from_task_id("COV-L1-001") == 1
        assert reconciler.parse_level_from_task_id("TEST-L5-010") == 5

    def test_parses_double_digit_level(self, reconciler: StateReconciler) -> None:
        """Test parsing double-digit levels."""
        assert reconciler.parse_level_from_task_id("TASK-L10-001") == 10
        assert reconciler.parse_level_from_task_id("A-L12-B") == 12

    def test_returns_none_for_no_level_pattern(self, reconciler: StateReconciler) -> None:
        """Test returns None when no level pattern found."""
        assert reconciler.parse_level_from_task_id("TASK-001") is None
        assert reconciler.parse_level_from_task_id("simple_task") is None
        assert reconciler.parse_level_from_task_id("") is None

    def test_returns_none_for_invalid_patterns(self, reconciler: StateReconciler) -> None:
        """Test returns None for similar but invalid patterns."""
        # Missing hyphen after number
        assert reconciler.parse_level_from_task_id("TASK-L3") is None
        # Missing hyphen before L
        assert reconciler.parse_level_from_task_id("TASKL3-001") is None
        # Lowercase l
        assert reconciler.parse_level_from_task_id("TASK-l3-001") is None

    def test_extracts_first_match(self, reconciler: StateReconciler) -> None:
        """Test extracts first level if multiple patterns present."""
        # Multiple level patterns - should return first
        result = reconciler.parse_level_from_task_id("A-L2-L3-001")
        assert result == 2


class TestReconcileTaskStates:
    """Tests for task state reconciliation."""

    @pytest.fixture
    def mock_state(self) -> MagicMock:
        """Create a mock StateManager."""
        mock = MagicMock()
        mock._state = {"tasks": {}, "workers": {}}
        return mock

    @pytest.fixture
    def mock_levels(self) -> MagicMock:
        """Create a mock LevelController."""
        return MagicMock()

    @pytest.fixture
    def reconciler(
        self, mock_state: MagicMock, mock_levels: MagicMock
    ) -> StateReconciler:
        """Create a StateReconciler with mocked dependencies."""
        return StateReconciler(state=mock_state, levels=mock_levels)

    def test_syncs_complete_task_to_level_controller(
        self,
        reconciler: StateReconciler,
        mock_state: MagicMock,
        mock_levels: MagicMock,
    ) -> None:
        """Test that complete tasks on disk are synced to LevelController."""
        mock_state._state = {
            "tasks": {
                "A-L1-001": {
                    "status": "complete",
                    "level": 1,
                    "worker_id": 1,
                }
            },
            "workers": {},
        }
        mock_levels.get_task_status.return_value = "pending"

        result = reconciler.reconcile_periodic()

        assert result.divergences_found == 1
        mock_levels.mark_task_complete.assert_called_once_with("A-L1-001")
        assert len(result.fixes_applied) == 1
        assert result.fixes_applied[0].fix_type == "task_status_sync"

    def test_syncs_failed_task_to_level_controller(
        self,
        reconciler: StateReconciler,
        mock_state: MagicMock,
        mock_levels: MagicMock,
    ) -> None:
        """Test that failed tasks on disk are synced to LevelController."""
        mock_state._state = {
            "tasks": {
                "A-L1-002": {
                    "status": "failed",
                    "level": 1,
                    "worker_id": 2,
                }
            },
            "workers": {},
        }
        mock_levels.get_task_status.return_value = "in_progress"

        result = reconciler.reconcile_periodic()

        assert result.divergences_found == 1
        mock_levels.mark_task_failed.assert_called_once_with("A-L1-002")
        assert len(result.fixes_applied) == 1

    def test_syncs_in_progress_task_to_level_controller(
        self,
        reconciler: StateReconciler,
        mock_state: MagicMock,
        mock_levels: MagicMock,
    ) -> None:
        """Test that in_progress tasks on disk are synced to LevelController."""
        mock_state._state = {
            "tasks": {
                "A-L1-003": {
                    "status": "in_progress",
                    "level": 1,
                    "worker_id": 3,
                }
            },
            "workers": {},
        }
        mock_levels.get_task_status.return_value = "pending"

        result = reconciler.reconcile_periodic()

        assert result.divergences_found == 1
        mock_levels.mark_task_in_progress.assert_called_once_with("A-L1-003", 3)

    def test_no_fix_when_states_match(
        self,
        reconciler: StateReconciler,
        mock_state: MagicMock,
        mock_levels: MagicMock,
    ) -> None:
        """Test no fix applied when disk and LevelController states match."""
        mock_state._state = {
            "tasks": {
                "A-L1-001": {
                    "status": "complete",
                    "level": 1,
                }
            },
            "workers": {},
        }
        mock_levels.get_task_status.return_value = "complete"

        result = reconciler.reconcile_periodic()

        assert result.divergences_found == 0
        assert len(result.fixes_applied) == 0
        mock_levels.mark_task_complete.assert_not_called()


class TestFixMissingTaskLevels:
    """Tests for fixing tasks with missing level field."""

    @pytest.fixture
    def mock_state(self) -> MagicMock:
        """Create a mock StateManager."""
        mock = MagicMock()
        mock._state = {"tasks": {}, "workers": {}}
        return mock

    @pytest.fixture
    def reconciler(self, mock_state: MagicMock) -> StateReconciler:
        """Create a StateReconciler with mocked dependencies."""
        mock_levels = MagicMock()
        mock_levels.get_task_status.return_value = None
        return StateReconciler(state=mock_state, levels=mock_levels)

    def test_parses_and_fixes_missing_level(
        self, reconciler: StateReconciler, mock_state: MagicMock
    ) -> None:
        """Test that tasks with missing level get it parsed from ID."""
        mock_state._state = {
            "tasks": {
                "RES-L3-001": {
                    "status": "pending",
                    "level": None,  # Missing level
                }
            },
            "workers": {},
        }

        result = reconciler.reconcile_periodic()

        # Level should be set in state
        assert mock_state._state["tasks"]["RES-L3-001"]["level"] == 3
        # Save should be called
        mock_state.save.assert_called_once()
        # Fix should be recorded
        level_fixes = [f for f in result.fixes_applied if f.fix_type == "level_parsed"]
        assert len(level_fixes) == 1
        assert level_fixes[0].new_value == 3

    def test_no_fix_when_level_cannot_be_parsed(
        self, reconciler: StateReconciler, mock_state: MagicMock
    ) -> None:
        """Test no fix when level cannot be parsed from task ID."""
        mock_state._state = {
            "tasks": {
                "SIMPLE-TASK": {
                    "status": "pending",
                    "level": None,
                }
            },
            "workers": {},
        }

        result = reconciler.reconcile_periodic()

        # Level should still be None
        assert mock_state._state["tasks"]["SIMPLE-TASK"]["level"] is None
        # No level_parsed fix
        level_fixes = [f for f in result.fixes_applied if f.fix_type == "level_parsed"]
        assert len(level_fixes) == 0

    def test_no_fix_when_level_already_set(
        self, reconciler: StateReconciler, mock_state: MagicMock
    ) -> None:
        """Test no fix when level is already set."""
        mock_state._state = {
            "tasks": {
                "RES-L3-001": {
                    "status": "pending",
                    "level": 3,  # Already set
                }
            },
            "workers": {},
        }

        result = reconciler.reconcile_periodic()

        # No level_parsed fix
        level_fixes = [f for f in result.fixes_applied if f.fix_type == "level_parsed"]
        assert len(level_fixes) == 0


class TestFixStuckInProgressTasks:
    """Tests for fixing tasks stuck in_progress with dead workers."""

    @pytest.fixture
    def mock_state(self) -> MagicMock:
        """Create a mock StateManager."""
        mock = MagicMock()
        mock._state = {"tasks": {}, "workers": {}}
        return mock

    @pytest.fixture
    def mock_levels(self) -> MagicMock:
        """Create a mock LevelController."""
        mock = MagicMock()
        mock.get_task_status.return_value = None
        return mock

    @pytest.fixture
    def reconciler(
        self, mock_state: MagicMock, mock_levels: MagicMock
    ) -> StateReconciler:
        """Create a StateReconciler with mocked dependencies."""
        return StateReconciler(state=mock_state, levels=mock_levels)

    def test_marks_stuck_task_failed_when_worker_dead(
        self,
        reconciler: StateReconciler,
        mock_state: MagicMock,
        mock_levels: MagicMock,
    ) -> None:
        """Test tasks in_progress with dead workers get marked failed."""
        mock_state._state = {
            "tasks": {
                "A-L1-001": {
                    "status": "in_progress",
                    "level": 1,
                    "worker_id": 5,  # Worker 5 assigned
                }
            },
            "workers": {
                "1": {"status": "running"},  # Worker 1 active
                # Worker 5 not in workers dict = dead
            },
        }
        mock_levels.get_task_status.return_value = "in_progress"

        result = reconciler.reconcile_level_transition(1)

        # Task should be marked failed
        mock_state.set_task_status.assert_called_with(
            "A-L1-001", "failed", error_message="worker_crash"
        )
        mock_levels.mark_task_failed.assert_called()
        # Retry count should be reset (crash, not task bug)
        mock_state.reset_task_retry.assert_called_with("A-L1-001")
        # Fix should be recorded
        stuck_fixes = [
            f for f in result.fixes_applied if f.fix_type == "stuck_task_recovered"
        ]
        assert len(stuck_fixes) == 1
        assert stuck_fixes[0].worker_id == 5

    def test_no_fix_when_worker_still_active(
        self,
        reconciler: StateReconciler,
        mock_state: MagicMock,
        mock_levels: MagicMock,
    ) -> None:
        """Test no fix when worker is still running."""
        mock_state._state = {
            "tasks": {
                "A-L1-001": {
                    "status": "in_progress",
                    "level": 1,
                    "worker_id": 1,
                }
            },
            "workers": {
                "1": {"status": "running"},  # Worker 1 is active
            },
        }
        mock_levels.get_task_status.return_value = "in_progress"

        result = reconciler.reconcile_level_transition(1)

        mock_state.set_task_status.assert_not_called()
        stuck_fixes = [
            f for f in result.fixes_applied if f.fix_type == "stuck_task_recovered"
        ]
        assert len(stuck_fixes) == 0

    def test_handles_worker_status_variants(
        self,
        reconciler: StateReconciler,
        mock_state: MagicMock,
        mock_levels: MagicMock,
    ) -> None:
        """Test handles different active worker statuses (ready, running, idle)."""
        mock_state._state = {
            "tasks": {
                "A-L1-001": {"status": "in_progress", "level": 1, "worker_id": 1},
                "A-L1-002": {"status": "in_progress", "level": 1, "worker_id": 2},
                "A-L1-003": {"status": "in_progress", "level": 1, "worker_id": 3},
                "A-L1-004": {"status": "in_progress", "level": 1, "worker_id": 4},
            },
            "workers": {
                "1": {"status": "ready"},
                "2": {"status": "running"},
                "3": {"status": "idle"},
                # Worker 4 is stopped
                "4": {"status": "stopped"},
            },
        }
        mock_levels.get_task_status.return_value = "in_progress"

        result = reconciler.reconcile_level_transition(1)

        # Only worker 4's task should be marked stuck
        stuck_fixes = [
            f for f in result.fixes_applied if f.fix_type == "stuck_task_recovered"
        ]
        assert len(stuck_fixes) == 1
        assert stuck_fixes[0].task_id == "A-L1-004"


class TestLevelTransitionReconciliation:
    """Tests for level transition reconciliation (thorough check)."""

    @pytest.fixture
    def mock_state(self) -> MagicMock:
        """Create a mock StateManager."""
        mock = MagicMock()
        mock._state = {"tasks": {}, "workers": {}}
        return mock

    @pytest.fixture
    def mock_levels(self) -> MagicMock:
        """Create a mock LevelController with LevelStatus."""
        mock = MagicMock()
        mock.get_task_status.return_value = None
        return mock

    @pytest.fixture
    def reconciler(
        self, mock_state: MagicMock, mock_levels: MagicMock
    ) -> StateReconciler:
        """Create a StateReconciler with mocked dependencies."""
        return StateReconciler(state=mock_state, levels=mock_levels)

    def test_verifies_all_tasks_in_terminal_state(
        self,
        reconciler: StateReconciler,
        mock_state: MagicMock,
        mock_levels: MagicMock,
    ) -> None:
        """Test level transition checks all tasks are complete or failed."""
        mock_state._state = {
            "tasks": {
                "A-L1-001": {"status": "complete", "level": 1},
                "A-L1-002": {"status": "failed", "level": 1},
                "A-L1-003": {"status": "complete", "level": 1},
            },
            "workers": {},
        }
        mock_levels.get_task_status.return_value = "complete"
        mock_levels.get_level_status.return_value = None

        result = reconciler.reconcile_level_transition(1)

        assert result.level_checked == 1
        assert result.success is True
        assert len(result.errors) == 0

    def test_errors_when_task_not_in_terminal_state(
        self,
        reconciler: StateReconciler,
        mock_state: MagicMock,
        mock_levels: MagicMock,
    ) -> None:
        """Test error when task still in_progress at level transition."""
        mock_state._state = {
            "tasks": {
                "A-L1-001": {"status": "complete", "level": 1},
                "A-L1-002": {"status": "in_progress", "level": 1},  # Not terminal!
            },
            "workers": {
                "1": {"status": "running"},  # Worker still active
            },
        }
        mock_levels.get_task_status.return_value = "in_progress"
        mock_levels.get_level_status.return_value = None

        result = reconciler.reconcile_level_transition(1)

        assert result.success is False
        assert len(result.errors) > 0
        assert any("not in terminal state" in e for e in result.errors)

    def test_only_checks_tasks_at_specified_level(
        self,
        reconciler: StateReconciler,
        mock_state: MagicMock,
        mock_levels: MagicMock,
    ) -> None:
        """Test that level filter is applied correctly."""
        mock_state._state = {
            "tasks": {
                "A-L1-001": {"status": "complete", "level": 1},
                "A-L2-001": {"status": "in_progress", "level": 2},  # Different level
            },
            "workers": {"1": {"status": "running"}},
        }
        mock_levels.get_task_status.return_value = "complete"
        mock_levels.get_level_status.return_value = None

        result = reconciler.reconcile_level_transition(1)

        # Should only check level 1, so L2 task shouldn't cause error
        assert result.success is True


class TestPeriodicVsThoroughReconciliation:
    """Tests comparing periodic vs level transition reconciliation."""

    @pytest.fixture
    def mock_state(self) -> MagicMock:
        """Create a mock StateManager."""
        mock = MagicMock()
        mock._state = {"tasks": {}, "workers": {}}
        return mock

    @pytest.fixture
    def mock_levels(self) -> MagicMock:
        """Create a mock LevelController."""
        return MagicMock()

    @pytest.fixture
    def reconciler(
        self, mock_state: MagicMock, mock_levels: MagicMock
    ) -> StateReconciler:
        """Create a StateReconciler with mocked dependencies."""
        return StateReconciler(state=mock_state, levels=mock_levels)

    def test_periodic_does_not_check_level_filter(
        self, reconciler: StateReconciler, mock_state: MagicMock
    ) -> None:
        """Test periodic reconciliation checks all tasks."""
        mock_state._state = {
            "tasks": {
                "A-L1-001": {"status": "complete", "level": 1},
                "A-L2-001": {"status": "complete", "level": 2},
                "A-L3-001": {"status": "complete", "level": 3},
            },
            "workers": {},
        }

        result = reconciler.reconcile_periodic()

        assert result.reconciliation_type == "periodic"
        assert result.tasks_checked == 3
        assert result.level_checked is None

    def test_level_transition_filters_by_level(
        self,
        reconciler: StateReconciler,
        mock_state: MagicMock,
        mock_levels: MagicMock,
    ) -> None:
        """Test level transition only checks specified level."""
        mock_state._state = {
            "tasks": {
                "A-L1-001": {"status": "complete", "level": 1},
                "A-L2-001": {"status": "pending", "level": 2},
            },
            "workers": {},
        }
        mock_levels.get_task_status.return_value = "complete"
        mock_levels.get_level_status.return_value = None

        result = reconciler.reconcile_level_transition(1)

        assert result.reconciliation_type == "level_transition"
        assert result.level_checked == 1

    def test_level_transition_does_final_check(
        self,
        reconciler: StateReconciler,
        mock_state: MagicMock,
        mock_levels: MagicMock,
    ) -> None:
        """Test level transition does final consistency check."""
        mock_state._state = {
            "tasks": {
                "A-L1-001": {"status": "pending", "level": 1},  # Still pending!
            },
            "workers": {},
        }
        mock_levels.get_task_status.return_value = "pending"
        mock_levels.get_level_status.return_value = None

        result = reconciler.reconcile_level_transition(1)

        # Should fail final check
        assert result.success is False
        assert any("not in terminal state" in e for e in result.errors)


class TestStaleWorkerDetection:
    """Tests for stale worker detection with heartbeat monitor."""

    @pytest.fixture
    def mock_state(self) -> MagicMock:
        """Create a mock StateManager."""
        mock = MagicMock()
        mock._state = {"tasks": {}, "workers": {"1": {}, "2": {}}}
        return mock

    @pytest.fixture
    def mock_heartbeat_monitor(self) -> MagicMock:
        """Create a mock HeartbeatMonitor."""
        return MagicMock()

    def test_detects_stale_workers(
        self, mock_state: MagicMock, mock_heartbeat_monitor: MagicMock
    ) -> None:
        """Test stale workers are detected via heartbeat monitor."""
        mock_levels = MagicMock()
        mock_levels.get_task_status.return_value = None
        mock_heartbeat_monitor.get_stalled_workers.return_value = [1]

        reconciler = StateReconciler(
            state=mock_state,
            levels=mock_levels,
            heartbeat_monitor=mock_heartbeat_monitor,
        )

        result = reconciler.reconcile_periodic()

        mock_heartbeat_monitor.get_stalled_workers.assert_called_once()
        assert result.workers_checked >= 1

    def test_no_stale_check_without_monitor(self, mock_state: MagicMock) -> None:
        """Test no stale check when heartbeat monitor not provided."""
        mock_levels = MagicMock()
        mock_levels.get_task_status.return_value = None

        reconciler = StateReconciler(state=mock_state, levels=mock_levels)

        result = reconciler.reconcile_periodic()

        assert result.workers_checked == 0


class TestLevelCompletionVerification:
    """Tests for level completion verification and correction."""

    @pytest.fixture
    def mock_state(self) -> MagicMock:
        """Create a mock StateManager."""
        mock = MagicMock()
        mock._state = {"tasks": {}, "workers": {}}
        return mock

    @pytest.fixture
    def mock_levels(self) -> MagicMock:
        """Create a mock LevelController."""
        return MagicMock()

    @pytest.fixture
    def reconciler(
        self, mock_state: MagicMock, mock_levels: MagicMock
    ) -> StateReconciler:
        """Create a StateReconciler with mocked dependencies."""
        return StateReconciler(state=mock_state, levels=mock_levels)

    def test_corrects_level_completed_count_mismatch(
        self,
        reconciler: StateReconciler,
        mock_state: MagicMock,
        mock_levels: MagicMock,
    ) -> None:
        """Test corrects mismatch between LevelController and disk counts."""
        mock_state._state = {
            "tasks": {
                "A-L1-001": {"status": "complete", "level": 1},
                "A-L1-002": {"status": "complete", "level": 1},
                "A-L1-003": {"status": "failed", "level": 1},
            },
            "workers": {},
        }
        mock_levels.get_task_status.return_value = "complete"

        # Mock level status with wrong counts
        level_status = MagicMock()
        level_status.completed_tasks = 1  # Wrong - should be 2
        level_status.failed_tasks = 0  # Wrong - should be 1
        mock_levels.get_level_status.return_value = level_status

        result = reconciler.reconcile_level_transition(1)

        # Should correct the counts
        assert level_status.completed_tasks == 2
        assert level_status.failed_tasks == 1

        # Fix should be recorded
        count_fixes = [
            f for f in result.fixes_applied if f.fix_type == "level_counts_corrected"
        ]
        assert len(count_fixes) == 1

    def test_no_fix_when_counts_match(
        self,
        reconciler: StateReconciler,
        mock_state: MagicMock,
        mock_levels: MagicMock,
    ) -> None:
        """Test no fix when LevelController counts are accurate."""
        mock_state._state = {
            "tasks": {
                "A-L1-001": {"status": "complete", "level": 1},
                "A-L1-002": {"status": "complete", "level": 1},
            },
            "workers": {},
        }
        mock_levels.get_task_status.return_value = "complete"

        # Correct counts
        level_status = MagicMock()
        level_status.completed_tasks = 2
        level_status.failed_tasks = 0
        mock_levels.get_level_status.return_value = level_status

        result = reconciler.reconcile_level_transition(1)

        count_fixes = [
            f for f in result.fixes_applied if f.fix_type == "level_counts_corrected"
        ]
        assert len(count_fixes) == 0


class TestErrorHandling:
    """Tests for error handling in reconciliation."""

    def test_handles_exception_in_periodic(self) -> None:
        """Test periodic reconciliation handles exceptions gracefully."""
        mock_state = MagicMock()
        mock_state._state = {"tasks": {}, "workers": {}}

        mock_levels = MagicMock()
        mock_levels.get_task_status.side_effect = RuntimeError("Test error")

        reconciler = StateReconciler(state=mock_state, levels=mock_levels)

        # Add a task to trigger the error
        mock_state._state["tasks"]["A-L1-001"] = {"status": "complete", "level": 1}

        result = reconciler.reconcile_periodic()

        assert result.success is False
        assert len(result.errors) > 0
        assert any("failed" in e.lower() for e in result.errors)

    def test_handles_exception_in_level_transition(self) -> None:
        """Test level transition reconciliation handles exceptions gracefully."""
        mock_state = MagicMock()
        mock_state._state = {"tasks": {}, "workers": {}}

        mock_levels = MagicMock()
        mock_levels.get_task_status.side_effect = RuntimeError("Test error")

        reconciler = StateReconciler(state=mock_state, levels=mock_levels)

        # Add a task to trigger the error
        mock_state._state["tasks"]["A-L1-001"] = {"status": "complete", "level": 1}

        result = reconciler.reconcile_level_transition(1)

        assert result.success is False
        assert len(result.errors) > 0
