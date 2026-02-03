"""Tests for ZERG iterative improvement loop controller."""

from __future__ import annotations

import click
import pytest
from click.testing import CliRunner

from zerg.commands.loop_mixin import loop_options
from zerg.config import LoopConfig
from zerg.loops import (
    IterationResult,
    LoopController,
    LoopStatus,
    LoopSummary,
)


class TestLoopStatus:
    """Tests for LoopStatus enum."""

    def test_enum_values(self) -> None:
        """All expected status values exist."""
        assert LoopStatus.RUNNING.value == "running"
        assert LoopStatus.CONVERGED.value == "converged"
        assert LoopStatus.PLATEAU.value == "plateau"
        assert LoopStatus.REGRESSED.value == "regressed"
        assert LoopStatus.MAX_ITERATIONS.value == "max_iterations"
        assert LoopStatus.ABORTED.value == "aborted"

    def test_enum_count(self) -> None:
        """Enum has exactly 6 members."""
        assert len(LoopStatus) == 6


class TestIterationResult:
    """Tests for IterationResult dataclass."""

    def test_is_regression_negative_delta(self) -> None:
        """Negative delta is a regression."""
        result = IterationResult(iteration=2, score=0.3, improved=False, delta=-0.2, duration_seconds=1.0)
        assert result.is_regression is True

    def test_is_regression_positive_delta(self) -> None:
        """Positive delta is not a regression."""
        result = IterationResult(iteration=1, score=0.5, improved=True, delta=0.5, duration_seconds=1.0)
        assert result.is_regression is False

    def test_is_regression_zero_delta(self) -> None:
        """Zero delta is not a regression."""
        result = IterationResult(iteration=2, score=0.5, improved=False, delta=0.0, duration_seconds=0.5)
        assert result.is_regression is False

    def test_to_dict(self) -> None:
        """to_dict returns expected structure."""
        result = IterationResult(
            iteration=1,
            score=0.75,
            improved=True,
            delta=0.25,
            duration_seconds=1.234,
            details={"metric": "coverage"},
        )
        d = result.to_dict()
        assert d["iteration"] == 1
        assert d["score"] == 0.75
        assert d["improved"] is True
        assert d["delta"] == 0.25
        assert d["duration_seconds"] == 1.23
        assert d["is_regression"] is False
        assert d["details"] == {"metric": "coverage"}

    def test_to_dict_rounds_values(self) -> None:
        """to_dict rounds delta and duration."""
        result = IterationResult(
            iteration=1,
            score=0.5,
            improved=True,
            delta=0.123456789,
            duration_seconds=2.999999,
        )
        d = result.to_dict()
        assert d["delta"] == 0.1235
        assert d["duration_seconds"] == 3.0

    def test_default_details_empty(self) -> None:
        """Default details is an empty dict."""
        result = IterationResult(iteration=1, score=0.5, improved=True, delta=0.5, duration_seconds=0.1)
        assert result.details == {}


class TestLoopSummary:
    """Tests for LoopSummary dataclass."""

    def _make_summary(
        self,
        status: LoopStatus = LoopStatus.CONVERGED,
        iterations: list[IterationResult] | None = None,
        best_score: float = 0.9,
        best_iteration: int = 3,
    ) -> LoopSummary:
        """Helper to create a LoopSummary."""
        if iterations is None:
            iterations = [
                IterationResult(1, 0.5, True, 0.5, 1.0),
                IterationResult(2, 0.8, True, 0.3, 1.0),
                IterationResult(3, 0.9, True, 0.1, 1.0),
            ]
        return LoopSummary(
            status=status,
            iterations=iterations,
            best_score=best_score,
            best_iteration=best_iteration,
            total_duration_seconds=3.5,
        )

    def test_improvement_calculated(self) -> None:
        """Improvement is best_score minus first iteration score."""
        summary = self._make_summary()
        assert summary.improvement == pytest.approx(0.4)

    def test_improvement_empty_iterations(self) -> None:
        """Improvement is 0.0 when no iterations exist."""
        summary = self._make_summary(iterations=[], best_score=0.0, best_iteration=0)
        assert summary.improvement == 0.0

    def test_converged_true(self) -> None:
        """converged is True when status is CONVERGED."""
        summary = self._make_summary(status=LoopStatus.CONVERGED)
        assert summary.converged is True

    def test_converged_false(self) -> None:
        """converged is False for non-CONVERGED statuses."""
        for status in [
            LoopStatus.PLATEAU,
            LoopStatus.REGRESSED,
            LoopStatus.MAX_ITERATIONS,
            LoopStatus.ABORTED,
        ]:
            summary = self._make_summary(status=status)
            assert summary.converged is False

    def test_to_dict(self) -> None:
        """to_dict returns complete structure."""
        summary = self._make_summary()
        d = summary.to_dict()
        assert d["status"] == "converged"
        assert len(d["iterations"]) == 3
        assert d["best_score"] == 0.9
        assert d["best_iteration"] == 3
        assert d["converged"] is True
        assert d["improvement"] == pytest.approx(0.4)
        assert d["total_duration_seconds"] == 3.5


class TestLoopControllerRun:
    """Tests for LoopController.run() method."""

    def test_converges(self) -> None:
        """Loop detects convergence when delta is small but positive."""
        # Scores: 0.5, 0.8, 0.95, 0.96 (delta=0.01 < threshold=0.02)
        scores = [0.5, 0.8, 0.95, 0.96]
        controller = LoopController(max_iterations=10, convergence_threshold=0.02)
        summary = controller.run(lambda i: scores[min(i - 1, len(scores) - 1)], initial_score=0.0)
        assert summary.status == LoopStatus.CONVERGED
        assert summary.best_score >= 0.95

    def test_plateau(self) -> None:
        """Loop detects plateau when score stays the same."""
        controller = LoopController(max_iterations=10, plateau_threshold=2, convergence_threshold=0.02)
        summary = controller.run(lambda i: 0.5, initial_score=0.5)
        assert summary.status == LoopStatus.PLATEAU
        assert len(summary.iterations) == 2

    def test_regression_stops(self) -> None:
        """Loop stops on regression when rollback_on_regression is True."""
        scores = [0.8, 0.5]
        controller = LoopController(
            max_iterations=10,
            rollback_on_regression=True,
            convergence_threshold=0.02,
        )
        summary = controller.run(lambda i: scores[min(i - 1, len(scores) - 1)], initial_score=0.0)
        # First iteration: 0.0 -> 0.8 (improved)
        # Second iteration: 0.8 -> 0.5 (regression, delta=-0.3)
        assert summary.status == LoopStatus.REGRESSED
        assert summary.best_score == 0.8
        assert summary.best_iteration == 1

    def test_regression_ignored_when_disabled(self) -> None:
        """Loop continues past regression when rollback_on_regression is False."""
        scores = [0.8, 0.5, 0.9]
        controller = LoopController(
            max_iterations=3,
            rollback_on_regression=False,
            convergence_threshold=0.02,
            plateau_threshold=10,
        )
        summary = controller.run(lambda i: scores[min(i - 1, len(scores) - 1)], initial_score=0.0)
        assert summary.status == LoopStatus.MAX_ITERATIONS
        assert summary.best_score == 0.9

    def test_max_iterations_reached(self) -> None:
        """Loop stops at max_iterations when no other condition triggers."""
        # Each iteration improves by a large amount (no convergence/plateau)
        controller = LoopController(
            max_iterations=3,
            convergence_threshold=0.02,
            plateau_threshold=10,
        )
        summary = controller.run(lambda i: i * 0.3, initial_score=0.0)
        assert summary.status == LoopStatus.MAX_ITERATIONS
        assert len(summary.iterations) == 3

    def test_exception_aborts(self) -> None:
        """Loop aborts when improve_fn raises an exception."""

        def failing_fn(i: int) -> float:
            if i == 2:
                raise RuntimeError("test failure")
            return 0.5

        controller = LoopController(max_iterations=5)
        summary = controller.run(failing_fn, initial_score=0.0)
        assert summary.status == LoopStatus.ABORTED
        assert len(summary.iterations) == 1

    def test_tracks_best_score_and_iteration(self) -> None:
        """Best score and iteration are tracked correctly."""
        scores = [0.3, 0.9, 0.7]
        controller = LoopController(
            max_iterations=3,
            rollback_on_regression=False,
            convergence_threshold=0.02,
            plateau_threshold=10,
        )
        summary = controller.run(lambda i: scores[min(i - 1, len(scores) - 1)], initial_score=0.0)
        assert summary.best_score == 0.9
        assert summary.best_iteration == 2

    def test_duration_tracked(self) -> None:
        """Total and per-iteration durations are positive."""
        controller = LoopController(max_iterations=2, plateau_threshold=10)
        summary = controller.run(lambda i: i * 0.4, initial_score=0.0)
        assert summary.total_duration_seconds > 0
        for iteration in summary.iterations:
            assert iteration.duration_seconds >= 0


class TestLoopControllerShouldContinue:
    """Tests for LoopController.should_continue() method."""

    def test_empty_list_returns_true(self) -> None:
        """Empty iteration list means continue."""
        controller = LoopController(max_iterations=5)
        assert controller.should_continue([]) is True

    def test_max_iterations_returns_false(self) -> None:
        """Returns False when max iterations reached."""
        controller = LoopController(max_iterations=2)
        iterations = [
            IterationResult(1, 0.5, True, 0.5, 1.0),
            IterationResult(2, 0.8, True, 0.3, 1.0),
        ]
        assert controller.should_continue(iterations) is False

    def test_plateau_returns_false(self) -> None:
        """Returns False after plateau_threshold non-improving iterations."""
        controller = LoopController(max_iterations=10, plateau_threshold=2)
        iterations = [
            IterationResult(1, 0.5, True, 0.5, 1.0),
            IterationResult(2, 0.5, False, 0.0, 1.0),
            IterationResult(3, 0.5, False, 0.0, 1.0),
        ]
        assert controller.should_continue(iterations) is False

    def test_regression_returns_false(self) -> None:
        """Returns False after regression when rollback enabled."""
        controller = LoopController(max_iterations=10, rollback_on_regression=True)
        iterations = [
            IterationResult(1, 0.5, True, 0.5, 1.0),
            IterationResult(2, 0.3, False, -0.2, 1.0),
        ]
        assert controller.should_continue(iterations) is False

    def test_regression_allowed_continues(self) -> None:
        """Returns True after regression when rollback disabled."""
        controller = LoopController(
            max_iterations=10,
            rollback_on_regression=False,
            plateau_threshold=10,
        )
        iterations = [
            IterationResult(1, 0.5, True, 0.5, 1.0),
            IterationResult(2, 0.3, False, -0.2, 1.0),
        ]
        assert controller.should_continue(iterations) is True

    def test_improving_continues(self) -> None:
        """Returns True when still improving."""
        controller = LoopController(max_iterations=10)
        iterations = [
            IterationResult(1, 0.5, True, 0.5, 1.0),
        ]
        assert controller.should_continue(iterations) is True


class TestLoopOptions:
    """Tests for loop_options Click decorator."""

    def test_adds_loop_flag(self) -> None:
        """Decorator adds --loop flag."""

        @click.command()
        @loop_options
        def cmd(loop: bool, iterations: int | None, convergence: float | None) -> None:
            click.echo(f"loop={loop}")

        runner = CliRunner()
        result = runner.invoke(cmd, ["--loop"])
        assert result.exit_code == 0
        assert "loop=True" in result.output

    def test_adds_iterations_option(self) -> None:
        """Decorator adds --iterations option."""

        @click.command()
        @loop_options
        def cmd(loop: bool, iterations: int | None, convergence: float | None) -> None:
            click.echo(f"iterations={iterations}")

        runner = CliRunner()
        result = runner.invoke(cmd, ["--iterations", "7"])
        assert result.exit_code == 0
        assert "iterations=7" in result.output

    def test_adds_convergence_option(self) -> None:
        """Decorator adds --convergence option."""

        @click.command()
        @loop_options
        def cmd(loop: bool, iterations: int | None, convergence: float | None) -> None:
            click.echo(f"convergence={convergence}")

        runner = CliRunner()
        result = runner.invoke(cmd, ["--convergence", "0.05"])
        assert result.exit_code == 0
        assert "convergence=0.05" in result.output

    def test_defaults_are_none_and_false(self) -> None:
        """Default values are False for loop, None for iterations and convergence."""

        @click.command()
        @loop_options
        def cmd(loop: bool, iterations: int | None, convergence: float | None) -> None:
            click.echo(f"loop={loop} iterations={iterations} convergence={convergence}")

        runner = CliRunner()
        result = runner.invoke(cmd, [])
        assert result.exit_code == 0
        assert "loop=False" in result.output
        assert "iterations=None" in result.output
        assert "convergence=None" in result.output


class TestLoopConfig:
    """Tests for LoopConfig Pydantic model."""

    def test_default_values(self) -> None:
        """Default configuration values are correct."""
        config = LoopConfig()
        assert config.max_iterations == 5
        assert config.plateau_threshold == 2
        assert config.rollback_on_regression is True
        assert config.convergence_threshold == 0.02

    def test_custom_values(self) -> None:
        """Custom values are accepted."""
        config = LoopConfig(
            max_iterations=8,
            plateau_threshold=4,
            rollback_on_regression=False,
            convergence_threshold=0.1,
        )
        assert config.max_iterations == 8
        assert config.plateau_threshold == 4
        assert config.rollback_on_regression is False
        assert config.convergence_threshold == 0.1

    def test_max_iterations_bounds(self) -> None:
        """max_iterations must be between 1 and 10."""
        with pytest.raises(Exception):
            LoopConfig(max_iterations=0)
        with pytest.raises(Exception):
            LoopConfig(max_iterations=11)

    def test_plateau_threshold_bounds(self) -> None:
        """plateau_threshold must be between 1 and 5."""
        with pytest.raises(Exception):
            LoopConfig(plateau_threshold=0)
        with pytest.raises(Exception):
            LoopConfig(plateau_threshold=6)

    def test_convergence_threshold_bounds(self) -> None:
        """convergence_threshold must be between 0.001 and 0.5."""
        with pytest.raises(Exception):
            LoopConfig(convergence_threshold=0.0001)
        with pytest.raises(Exception):
            LoopConfig(convergence_threshold=0.6)

    def test_in_zerg_config(self) -> None:
        """LoopConfig is accessible from ZergConfig."""
        from zerg.config import ZergConfig

        config = ZergConfig()
        assert isinstance(config.improvement_loops, LoopConfig)
        assert config.improvement_loops.max_iterations == 5
