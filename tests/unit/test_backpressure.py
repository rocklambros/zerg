"""Tests for BackpressureController."""

import pytest

from zerg.backpressure import BackpressureController, LevelPressure


class TestLevelPressure:
    """Tests for the LevelPressure dataclass."""

    def test_defaults(self) -> None:
        lp = LevelPressure(level=1)
        assert lp.level == 1
        assert lp.total_tasks == 0
        assert lp.completed_tasks == 0
        assert lp.failed_tasks == 0
        assert lp.paused is False
        assert lp.paused_at is None
        assert len(lp.recent_outcomes) == 0


class TestRegisterLevel:
    """Tests for register_level and initial state."""

    def test_register_level_sets_total_tasks(self) -> None:
        ctrl = BackpressureController()
        ctrl.register_level(1, total_tasks=5)
        status = ctrl.get_status()
        assert 1 in status
        assert status[1]["total_tasks"] == 5
        assert status[1]["completed"] == 0
        assert status[1]["failed"] == 0
        assert status[1]["paused"] is False

    def test_register_level_overwrites_existing(self) -> None:
        ctrl = BackpressureController()
        ctrl.register_level(1, total_tasks=5)
        ctrl.record_failure(1)
        ctrl.register_level(1, total_tasks=10)
        # Re-registering resets counters
        assert ctrl.get_status()[1]["total_tasks"] == 10
        assert ctrl.get_status()[1]["failed"] == 0


class TestRecordSuccess:
    """Tests for record_success."""

    def test_increments_completed_tasks(self) -> None:
        ctrl = BackpressureController()
        ctrl.register_level(1, total_tasks=3)
        ctrl.record_success(1)
        ctrl.record_success(1)
        status = ctrl.get_status()[1]
        assert status["completed"] == 2
        assert status["failed"] == 0

    def test_appends_to_recent_outcomes(self) -> None:
        ctrl = BackpressureController()
        ctrl.record_success(1)
        assert ctrl.get_failure_rate(1) == 0.0

    def test_auto_creates_level(self) -> None:
        ctrl = BackpressureController()
        ctrl.record_success(99)
        assert 99 in ctrl.get_status()


class TestRecordFailure:
    """Tests for record_failure."""

    def test_increments_failed_tasks(self) -> None:
        ctrl = BackpressureController()
        ctrl.register_level(1, total_tasks=3)
        ctrl.record_failure(1)
        status = ctrl.get_status()[1]
        assert status["failed"] == 1
        assert status["completed"] == 0

    def test_appends_to_recent_outcomes(self) -> None:
        ctrl = BackpressureController()
        ctrl.record_failure(1)
        assert ctrl.get_failure_rate(1) == 1.0

    def test_auto_creates_level(self) -> None:
        ctrl = BackpressureController()
        ctrl.record_failure(42)
        assert 42 in ctrl.get_status()


class TestShouldPause:
    """Tests for should_pause logic."""

    def test_returns_false_with_insufficient_data(self) -> None:
        ctrl = BackpressureController(failure_rate_threshold=0.5)
        ctrl.record_failure(1)
        ctrl.record_failure(1)
        # Only 2 outcomes, minimum is 3
        assert ctrl.should_pause(1) is False

    def test_returns_false_below_threshold(self) -> None:
        ctrl = BackpressureController(failure_rate_threshold=0.5)
        ctrl.register_level(1, total_tasks=5)
        ctrl.record_success(1)
        ctrl.record_success(1)
        ctrl.record_failure(1)
        # 1/3 = 0.33 < 0.5
        assert ctrl.should_pause(1) is False

    def test_triggers_at_threshold(self) -> None:
        ctrl = BackpressureController(failure_rate_threshold=0.5)
        ctrl.register_level(1, total_tasks=5)
        ctrl.record_success(1)
        ctrl.record_success(1)
        ctrl.record_failure(1)
        ctrl.record_failure(1)
        ctrl.record_failure(1)
        # 3/5 = 0.6 >= 0.5
        assert ctrl.should_pause(1) is True

    def test_triggers_at_exact_threshold(self) -> None:
        ctrl = BackpressureController(failure_rate_threshold=0.5)
        ctrl.register_level(1, total_tasks=4)
        ctrl.record_success(1)
        ctrl.record_failure(1)
        ctrl.record_success(1)
        ctrl.record_failure(1)
        # 2/4 = 0.5 >= 0.5
        assert ctrl.should_pause(1) is True

    def test_returns_false_when_already_paused(self) -> None:
        ctrl = BackpressureController(failure_rate_threshold=0.5)
        ctrl.register_level(1, total_tasks=5)
        ctrl.record_failure(1)
        ctrl.record_failure(1)
        ctrl.record_failure(1)
        # Manually pause the level
        ctrl.pause_level(1)
        # Even though failure rate is high, should_pause returns False
        assert ctrl.should_pause(1) is False

    def test_returns_false_when_disabled(self) -> None:
        ctrl = BackpressureController(enabled=False)
        ctrl.register_level(1, total_tasks=3)
        # Force outcomes directly since record_* is no-op when disabled
        pressure = ctrl._get_or_create(1)
        pressure.recent_outcomes.extend([False, False, False])
        assert ctrl.should_pause(1) is False


class TestPauseAndResume:
    """Tests for pause_level and resume_level."""

    def test_pause_level(self) -> None:
        ctrl = BackpressureController()
        ctrl.register_level(1, total_tasks=3)
        assert ctrl.is_paused(1) is False
        ctrl.pause_level(1)
        assert ctrl.is_paused(1) is True

    def test_pause_sets_timestamp(self) -> None:
        ctrl = BackpressureController()
        ctrl.register_level(1, total_tasks=3)
        ctrl.pause_level(1)
        pressure = ctrl._levels[1]
        assert pressure.paused_at is not None
        assert pressure.paused_at > 0

    def test_resume_level(self) -> None:
        ctrl = BackpressureController()
        ctrl.register_level(1, total_tasks=3)
        ctrl.pause_level(1)
        assert ctrl.is_paused(1) is True
        ctrl.resume_level(1)
        assert ctrl.is_paused(1) is False

    def test_resume_clears_window(self) -> None:
        ctrl = BackpressureController()
        ctrl.register_level(1, total_tasks=5)
        ctrl.record_failure(1)
        ctrl.record_failure(1)
        ctrl.record_failure(1)
        assert ctrl.get_failure_rate(1) == 1.0
        ctrl.pause_level(1)
        ctrl.resume_level(1)
        # Window cleared, failure rate resets
        assert ctrl.get_failure_rate(1) == 0.0
        assert ctrl.get_status()[1]["window_size"] == 0

    def test_resume_clears_paused_at(self) -> None:
        ctrl = BackpressureController()
        ctrl.register_level(1, total_tasks=3)
        ctrl.pause_level(1)
        ctrl.resume_level(1)
        pressure = ctrl._levels[1]
        assert pressure.paused_at is None

    def test_is_paused_returns_false_for_unknown_level(self) -> None:
        ctrl = BackpressureController()
        assert ctrl.is_paused(999) is False


class TestGetFailureRate:
    """Tests for get_failure_rate calculation."""

    def test_zero_for_unknown_level(self) -> None:
        ctrl = BackpressureController()
        assert ctrl.get_failure_rate(1) == 0.0

    def test_zero_for_empty_window(self) -> None:
        ctrl = BackpressureController()
        ctrl.register_level(1, total_tasks=3)
        assert ctrl.get_failure_rate(1) == 0.0

    def test_all_successes(self) -> None:
        ctrl = BackpressureController()
        for _ in range(5):
            ctrl.record_success(1)
        assert ctrl.get_failure_rate(1) == 0.0

    def test_all_failures(self) -> None:
        ctrl = BackpressureController()
        for _ in range(5):
            ctrl.record_failure(1)
        assert ctrl.get_failure_rate(1) == 1.0

    def test_mixed_outcomes(self) -> None:
        ctrl = BackpressureController()
        ctrl.record_success(1)
        ctrl.record_failure(1)
        ctrl.record_success(1)
        ctrl.record_failure(1)
        assert ctrl.get_failure_rate(1) == pytest.approx(0.5)

    def test_sliding_window_evicts_old(self) -> None:
        ctrl = BackpressureController(window_size=3)
        ctrl.record_failure(1)  # [F]
        ctrl.record_failure(1)  # [F, F]
        ctrl.record_failure(1)  # [F, F, F]
        assert ctrl.get_failure_rate(1) == 1.0
        ctrl.record_success(1)  # [F, F, S] (first F evicted)
        assert ctrl.get_failure_rate(1) == pytest.approx(2 / 3)
        ctrl.record_success(1)  # [F, S, S]
        assert ctrl.get_failure_rate(1) == pytest.approx(1 / 3)
        ctrl.record_success(1)  # [S, S, S]
        assert ctrl.get_failure_rate(1) == 0.0


class TestDisabledController:
    """Tests for disabled controller behavior."""

    def test_enabled_property(self) -> None:
        ctrl = BackpressureController(enabled=False)
        assert ctrl.enabled is False

    def test_record_success_noop(self) -> None:
        ctrl = BackpressureController(enabled=False)
        ctrl.record_success(1)
        # Level not created since operation was a no-op
        assert 1 not in ctrl.get_status()

    def test_record_failure_noop(self) -> None:
        ctrl = BackpressureController(enabled=False)
        ctrl.record_failure(1)
        assert 1 not in ctrl.get_status()

    def test_should_pause_always_false(self) -> None:
        ctrl = BackpressureController(enabled=False)
        assert ctrl.should_pause(1) is False


class TestGetStatus:
    """Tests for get_status."""

    def test_empty_status(self) -> None:
        ctrl = BackpressureController()
        assert ctrl.get_status() == {}

    def test_status_contains_all_fields(self) -> None:
        ctrl = BackpressureController()
        ctrl.register_level(1, total_tasks=5)
        ctrl.record_success(1)
        ctrl.record_failure(1)
        status = ctrl.get_status()[1]
        assert status["total_tasks"] == 5
        assert status["completed"] == 1
        assert status["failed"] == 1
        assert status["failure_rate"] == pytest.approx(0.5)
        assert status["paused"] is False
        assert status["window_size"] == 2

    def test_status_with_paused_level(self) -> None:
        ctrl = BackpressureController()
        ctrl.register_level(1, total_tasks=3)
        ctrl.pause_level(1)
        assert ctrl.get_status()[1]["paused"] is True


class TestMultipleLevels:
    """Tests for independent tracking of multiple levels."""

    def test_levels_tracked_independently(self) -> None:
        ctrl = BackpressureController(failure_rate_threshold=0.5)
        ctrl.register_level(1, total_tasks=5)
        ctrl.register_level(2, total_tasks=3)

        # Level 1: all failures
        for _ in range(4):
            ctrl.record_failure(1)

        # Level 2: all successes
        for _ in range(3):
            ctrl.record_success(2)

        assert ctrl.get_failure_rate(1) == 1.0
        assert ctrl.get_failure_rate(2) == 0.0
        assert ctrl.should_pause(1) is True
        assert ctrl.should_pause(2) is False

    def test_pausing_one_level_does_not_affect_other(self) -> None:
        ctrl = BackpressureController()
        ctrl.register_level(1, total_tasks=3)
        ctrl.register_level(2, total_tasks=3)
        ctrl.pause_level(1)
        assert ctrl.is_paused(1) is True
        assert ctrl.is_paused(2) is False

    def test_status_shows_all_levels(self) -> None:
        ctrl = BackpressureController()
        ctrl.register_level(1, total_tasks=5)
        ctrl.register_level(2, total_tasks=3)
        ctrl.register_level(3, total_tasks=7)
        status = ctrl.get_status()
        assert set(status.keys()) == {1, 2, 3}
