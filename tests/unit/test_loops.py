"""Tests for ZERG iterative improvement loop controller — thinned Phase 4/5."""

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
    def test_enum_values(self) -> None:
        assert {s.value for s in LoopStatus} == {
            "running",
            "converged",
            "plateau",
            "regressed",
            "max_iterations",
            "aborted",
        }


class TestIterationResult:
    @pytest.mark.parametrize(
        "delta,expected",
        [(-0.2, True), (0.5, False), (0.0, False)],
    )
    def test_is_regression(self, delta: float, expected: bool) -> None:
        assert (
            IterationResult(iteration=1, score=0.5, improved=False, delta=delta, duration_seconds=1.0).is_regression
            is expected
        )

    def test_to_dict(self) -> None:
        d = IterationResult(
            iteration=1, score=0.75, improved=True, delta=0.25, duration_seconds=1.234, details={"m": "c"}
        ).to_dict()
        assert d["score"] == 0.75 and d["is_regression"] is False and d["details"] == {"m": "c"}


class TestLoopSummary:
    def _make_summary(self, status: LoopStatus = LoopStatus.CONVERGED, iterations: list | None = None) -> LoopSummary:
        if iterations is None:
            iterations = [
                IterationResult(1, 0.5, True, 0.5, 1.0),
                IterationResult(2, 0.8, True, 0.3, 1.0),
                IterationResult(3, 0.9, True, 0.1, 1.0),
            ]
        return LoopSummary(
            status=status, iterations=iterations, best_score=0.9, best_iteration=3, total_duration_seconds=3.5
        )

    def test_improvement_and_converged(self) -> None:
        s = self._make_summary()
        assert s.improvement == pytest.approx(0.4)
        assert s.converged is True

    def test_to_dict(self) -> None:
        d = self._make_summary().to_dict()
        assert d["status"] == "converged" and len(d["iterations"]) == 3


class TestLoopControllerRun:
    def test_converges(self) -> None:
        scores = [0.5, 0.8, 0.95, 0.96]
        summary = LoopController(max_iterations=10, convergence_threshold=0.02).run(
            lambda i: scores[min(i - 1, len(scores) - 1)], initial_score=0.0
        )
        assert summary.status == LoopStatus.CONVERGED

    def test_plateau(self) -> None:
        summary = LoopController(max_iterations=10, plateau_threshold=2, convergence_threshold=0.02).run(
            lambda i: 0.5, initial_score=0.5
        )
        assert summary.status == LoopStatus.PLATEAU

    def test_regression_stops(self) -> None:
        scores = [0.8, 0.5]
        summary = LoopController(max_iterations=10, rollback_on_regression=True, convergence_threshold=0.02).run(
            lambda i: scores[min(i - 1, len(scores) - 1)], initial_score=0.0
        )
        assert summary.status == LoopStatus.REGRESSED and summary.best_score == 0.8

    def test_max_iterations_reached(self) -> None:
        summary = LoopController(max_iterations=3, convergence_threshold=0.02, plateau_threshold=10).run(
            lambda i: i * 0.3, initial_score=0.0
        )
        assert summary.status == LoopStatus.MAX_ITERATIONS and len(summary.iterations) == 3

    def test_exception_aborts(self) -> None:
        def failing_fn(i: int) -> float:
            if i == 2:
                raise RuntimeError("test failure")
            return 0.5

        summary = LoopController(max_iterations=5).run(failing_fn, initial_score=0.0)
        assert summary.status == LoopStatus.ABORTED


class TestLoopControllerShouldContinue:
    def test_empty_list_returns_true(self) -> None:
        assert LoopController(max_iterations=5).should_continue([]) is True

    def test_max_iterations_returns_false(self) -> None:
        iters = [IterationResult(1, 0.5, True, 0.5, 1.0), IterationResult(2, 0.8, True, 0.3, 1.0)]
        assert LoopController(max_iterations=2).should_continue(iters) is False

    def test_regression_returns_false(self) -> None:
        iters = [IterationResult(1, 0.5, True, 0.5, 1.0), IterationResult(2, 0.3, False, -0.2, 1.0)]
        assert LoopController(max_iterations=10, rollback_on_regression=True).should_continue(iters) is False


class TestLoopOptions:
    def test_defaults_are_none_and_false(self) -> None:
        @click.command()
        @loop_options
        def cmd(loop: bool, iterations: int | None, convergence: float | None) -> None:
            click.echo(f"loop={loop} iterations={iterations} convergence={convergence}")

        result = CliRunner().invoke(cmd, [])
        assert "loop=False" in result.output and "iterations=None" in result.output


class TestLoopConfig:
    def test_default_values(self) -> None:
        config = LoopConfig()
        assert config.max_iterations == 5
        assert config.plateau_threshold == 2
        assert config.rollback_on_regression is True

    @pytest.mark.parametrize(
        "field,bad_values",
        [
            ("max_iterations", [0, 11]),
            ("plateau_threshold", [0, 6]),
            ("convergence_threshold", [0.0001, 0.6]),
        ],
    )
    def test_bounds_validation(self, field: str, bad_values: list) -> None:
        for val in bad_values:
            with pytest.raises(Exception):
                LoopConfig(**{field: val})
