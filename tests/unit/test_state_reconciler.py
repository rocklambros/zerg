"""Tests for ZERG state reconciler module.

Covers reconciliation logic, level parsing from task IDs,
inconsistency detection and fixes.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from zerg.state_reconciler import (
    ReconciliationFix,
    ReconciliationResult,
    StateReconciler,
)

pytestmark = pytest.mark.slow


class TestReconciliationDataclasses:
    """Tests for ReconciliationFix and ReconciliationResult dataclasses."""

    def test_fix_creation_and_to_dict(self) -> None:
        """Test ReconciliationFix creation and dict serialization."""
        fix = ReconciliationFix(
            fix_type="task_status_sync",
            task_id="RES-L3-001",
            level=3,
            worker_id=2,
            old_value="pending",
            new_value="complete",
            reason="Disk shows complete, syncing to LevelController",
        )
        d = fix.to_dict()
        assert d["fix_type"] == "task_status_sync"
        assert d["task_id"] == "RES-L3-001"
        assert d["level"] == 3

    def test_result_properties_and_to_dict(self) -> None:
        """Test ReconciliationResult success/had_fixes properties and dict serialization."""
        # Empty result: success=True, had_fixes=False
        result = ReconciliationResult(reconciliation_type="periodic")
        assert result.success is True
        assert result.had_fixes is False

        # With errors: success=False
        result_err = ReconciliationResult(
            reconciliation_type="level_transition",
            errors=["Task X not in terminal state"],
        )
        assert result_err.success is False

        # With fixes: had_fixes=True, to_dict works
        fix = ReconciliationFix(
            fix_type="test",
            task_id="A-L1-001",
            level=1,
            worker_id=None,
            old_value="x",
            new_value="y",
            reason="test",
        )
        result_fix = ReconciliationResult(
            reconciliation_type="periodic",
            fixes_applied=[fix],
            divergences_found=1,
            tasks_checked=5,
            workers_checked=2,
        )
        assert result_fix.had_fixes is True
        d = result_fix.to_dict()
        assert len(d["fixes_applied"]) == 1


class TestParseLevelFromTaskId:
    """Tests for parse_level_from_task_id method."""

    @pytest.fixture
    def reconciler(self) -> StateReconciler:
        mock_state = MagicMock()
        mock_state._state = {"tasks": {}, "workers": {}}
        return StateReconciler(state=mock_state, levels=MagicMock())

    @pytest.mark.parametrize(
        "task_id,expected",
        [
            ("RES-L3-003", 3),
            ("COV-L1-001", 1),
            ("TASK-L10-001", 10),
            ("TASK-001", None),
            ("simple_task", None),
            ("", None),
        ],
        ids=["standard", "level-1", "double-digit", "no-pattern", "no-level", "empty"],
    )
    def test_parse_level_from_task_id(self, reconciler: StateReconciler, task_id: str, expected) -> None:
        """Test parsing level from various task ID formats."""
        assert reconciler.parse_level_from_task_id(task_id) == expected


class TestReconcileTaskStates:
    """Tests for task state reconciliation (periodic)."""

    @pytest.fixture
    def setup(self):
        mock_state = MagicMock()
        mock_state._state = {"tasks": {}, "workers": {}}
        mock_levels = MagicMock()
        reconciler = StateReconciler(state=mock_state, levels=mock_levels)
        return reconciler, mock_state, mock_levels

    def test_syncs_complete_task_to_level_controller(self, setup) -> None:
        """Test complete tasks on disk are synced to LevelController."""
        reconciler, mock_state, mock_levels = setup
        mock_state._state = {
            "tasks": {"A-L1-001": {"status": "complete", "level": 1, "worker_id": 1}},
            "workers": {},
        }
        mock_levels.get_task_status.return_value = "pending"
        result = reconciler.reconcile_periodic()
        assert result.divergences_found == 1
        mock_levels.mark_task_complete.assert_called_once_with("A-L1-001")

    def test_no_fix_when_states_match(self, setup) -> None:
        """Test no fix applied when disk and LevelController states match."""
        reconciler, mock_state, mock_levels = setup
        mock_state._state = {
            "tasks": {"A-L1-001": {"status": "complete", "level": 1}},
            "workers": {},
        }
        mock_levels.get_task_status.return_value = "complete"
        result = reconciler.reconcile_periodic()
        assert result.divergences_found == 0

    def test_parses_and_fixes_missing_level(self, setup) -> None:
        """Test tasks with missing level get it parsed from ID."""
        reconciler, mock_state, mock_levels = setup
        mock_state._state = {
            "tasks": {"RES-L3-001": {"status": "pending", "level": None}},
            "workers": {},
        }
        mock_levels.get_task_status.return_value = None
        result = reconciler.reconcile_periodic()
        assert mock_state._state["tasks"]["RES-L3-001"]["level"] == 3
        level_fixes = [f for f in result.fixes_applied if f.fix_type == "level_parsed"]
        assert len(level_fixes) == 1


class TestLevelTransitionReconciliation:
    """Tests for level transition reconciliation."""

    @pytest.fixture
    def setup(self):
        mock_state = MagicMock()
        mock_state._state = {"tasks": {}, "workers": {}}
        mock_levels = MagicMock()
        reconciler = StateReconciler(state=mock_state, levels=mock_levels)
        return reconciler, mock_state, mock_levels

    def test_marks_stuck_task_failed_when_worker_dead(self, setup) -> None:
        """Test tasks in_progress with dead workers get marked failed."""
        reconciler, mock_state, mock_levels = setup
        mock_state._state = {
            "tasks": {"A-L1-001": {"status": "in_progress", "level": 1, "worker_id": 5}},
            "workers": {"1": {"status": "running"}},
        }
        mock_levels.get_task_status.return_value = "in_progress"
        result = reconciler.reconcile_level_transition(1)
        mock_state.set_task_status.assert_called_with("A-L1-001", "failed", error_message="worker_crash")
        stuck_fixes = [f for f in result.fixes_applied if f.fix_type == "stuck_task_recovered"]
        assert len(stuck_fixes) == 1

    def test_errors_when_task_not_in_terminal_state(self, setup) -> None:
        """Test error when task still in_progress at level transition."""
        reconciler, mock_state, mock_levels = setup
        mock_state._state = {
            "tasks": {"A-L1-002": {"status": "in_progress", "level": 1}},
            "workers": {"1": {"status": "running"}},
        }
        mock_levels.get_task_status.return_value = "in_progress"
        mock_levels.get_level_status.return_value = None
        result = reconciler.reconcile_level_transition(1)
        assert result.success is False
        assert any("not in terminal state" in e for e in result.errors)

    def test_only_checks_tasks_at_specified_level(self, setup) -> None:
        """Test level filter is applied: L2 task ignored when checking L1."""
        reconciler, mock_state, mock_levels = setup
        mock_state._state = {
            "tasks": {
                "A-L1-001": {"status": "complete", "level": 1},
                "A-L2-001": {"status": "in_progress", "level": 2},
            },
            "workers": {"1": {"status": "running"}},
        }
        mock_levels.get_task_status.return_value = "complete"
        mock_levels.get_level_status.return_value = None
        result = reconciler.reconcile_level_transition(1)
        assert result.success is True


class TestErrorHandling:
    """Tests for error handling in reconciliation."""

    def test_handles_exception_in_periodic(self) -> None:
        """Test periodic reconciliation handles exceptions gracefully."""
        mock_state = MagicMock()
        mock_state._state = {"tasks": {"A-L1-001": {"status": "complete", "level": 1}}, "workers": {}}
        mock_levels = MagicMock()
        mock_levels.get_task_status.side_effect = RuntimeError("Test error")
        reconciler = StateReconciler(state=mock_state, levels=mock_levels)
        result = reconciler.reconcile_periodic()
        assert result.success is False
        assert len(result.errors) > 0
