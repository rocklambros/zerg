"""Tests for BackpressureController."""

import pytest

from zerg.backpressure import BackpressureController, LevelPressure


class TestLevelPressure:
    """Tests for the LevelPressure dataclass."""

    def test_defaults(self) -> None:
        lp = LevelPressure(level=1)
        assert lp.level == 1
        assert lp.total_tasks == 0
        assert lp.paused is False


class TestRegisterLevel:
    """Tests for register_level and initial state."""

    def test_register_level_sets_total_tasks(self) -> None:
        ctrl = BackpressureController()
        ctrl.register_level(1, total_tasks=5)
        status = ctrl.get_status()
        assert status[1]["total_tasks"] == 5
        assert status[1]["paused"] is False


class TestRecordSuccessAndFailure:
    """Tests for record_success and record_failure."""

    def test_increments_counters(self) -> None:
        ctrl = BackpressureController()
        ctrl.register_level(1, total_tasks=3)
        ctrl.record_success(1)
        ctrl.record_success(1)
        ctrl.record_failure(1)
        status = ctrl.get_status()[1]
        assert status["completed"] == 2
        assert status["failed"] == 1

    def test_auto_creates_level(self) -> None:
        ctrl = BackpressureController()
        ctrl.record_success(99)
        ctrl.record_failure(42)
        assert 99 in ctrl.get_status()
        assert 42 in ctrl.get_status()


class TestShouldPause:
    """Tests for should_pause logic."""

    def test_returns_false_with_insufficient_data(self) -> None:
        ctrl = BackpressureController(failure_rate_threshold=0.5)
        ctrl.record_failure(1)
        ctrl.record_failure(1)
        assert ctrl.should_pause(1) is False

    def test_triggers_at_threshold(self) -> None:
        ctrl = BackpressureController(failure_rate_threshold=0.5)
        ctrl.register_level(1, total_tasks=5)
        ctrl.record_success(1)
        ctrl.record_success(1)
        ctrl.record_failure(1)
        ctrl.record_failure(1)
        ctrl.record_failure(1)
        assert ctrl.should_pause(1) is True

    def test_returns_false_when_already_paused(self) -> None:
        ctrl = BackpressureController(failure_rate_threshold=0.5)
        ctrl.register_level(1, total_tasks=5)
        ctrl.record_failure(1)
        ctrl.record_failure(1)
        ctrl.record_failure(1)
        ctrl.pause_level(1)
        assert ctrl.should_pause(1) is False


class TestPauseAndResume:
    """Tests for pause_level and resume_level."""

    def test_pause_and_resume_lifecycle(self) -> None:
        ctrl = BackpressureController()
        ctrl.register_level(1, total_tasks=5)
        assert ctrl.is_paused(1) is False
        ctrl.pause_level(1)
        assert ctrl.is_paused(1) is True
        assert ctrl._levels[1].paused_at is not None
        ctrl.resume_level(1)
        assert ctrl.is_paused(1) is False
        assert ctrl._levels[1].paused_at is None

    def test_resume_clears_window(self) -> None:
        ctrl = BackpressureController()
        ctrl.register_level(1, total_tasks=5)
        ctrl.record_failure(1)
        ctrl.record_failure(1)
        ctrl.record_failure(1)
        assert ctrl.get_failure_rate(1) == 1.0
        ctrl.pause_level(1)
        ctrl.resume_level(1)
        assert ctrl.get_failure_rate(1) == 0.0

    def test_is_paused_returns_false_for_unknown_level(self) -> None:
        ctrl = BackpressureController()
        assert ctrl.is_paused(999) is False


class TestGetFailureRate:
    """Tests for get_failure_rate calculation."""

    @pytest.mark.parametrize(
        "outcomes, expected",
        [
            ([], 0.0),
            ([True] * 5, 0.0),
            ([False] * 5, 1.0),
            ([True, False, True, False], 0.5),
        ],
        ids=["empty", "all_success", "all_failure", "mixed"],
    )
    def test_failure_rate_scenarios(self, outcomes, expected) -> None:
        ctrl = BackpressureController()
        ctrl.register_level(1, total_tasks=10)
        for outcome in outcomes:
            if outcome:
                ctrl.record_success(1)
            else:
                ctrl.record_failure(1)
        assert ctrl.get_failure_rate(1) == pytest.approx(expected)

    def test_sliding_window_evicts_old(self) -> None:
        ctrl = BackpressureController(window_size=3)
        ctrl.record_failure(1)
        ctrl.record_failure(1)
        ctrl.record_failure(1)
        assert ctrl.get_failure_rate(1) == 1.0
        ctrl.record_success(1)
        assert ctrl.get_failure_rate(1) == pytest.approx(2 / 3)


class TestDisabledController:
    """Tests for disabled controller behavior."""

    def test_disabled_noops(self) -> None:
        ctrl = BackpressureController(enabled=False)
        assert ctrl.enabled is False
        ctrl.record_success(1)
        ctrl.record_failure(1)
        assert 1 not in ctrl.get_status()
        assert ctrl.should_pause(1) is False


class TestMultipleLevels:
    """Tests for independent tracking of multiple levels."""

    def test_levels_tracked_independently(self) -> None:
        ctrl = BackpressureController(failure_rate_threshold=0.5)
        ctrl.register_level(1, total_tasks=5)
        ctrl.register_level(2, total_tasks=3)
        for _ in range(4):
            ctrl.record_failure(1)
        for _ in range(3):
            ctrl.record_success(2)
        assert ctrl.get_failure_rate(1) == 1.0
        assert ctrl.get_failure_rate(2) == 0.0
        assert ctrl.should_pause(1) is True
        assert ctrl.should_pause(2) is False
