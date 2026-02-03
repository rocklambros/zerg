"""Unit tests for zerg.token_aggregator module."""

from __future__ import annotations

from zerg.token_aggregator import (
    _DEFAULT_BASELINE_MULTIPLIER,
    BREAKDOWN_KEYS,
    AggregateResult,
    SavingsResult,
    TokenAggregator,
)
from zerg.token_tracker import TokenTracker


def _seed_worker(tmp_path, worker_id: str, tasks: dict) -> None:
    """Helper: create a token file for a worker via TokenTracker."""
    tracker = TokenTracker(state_dir=tmp_path)
    for task_id, breakdown in tasks.items():
        tracker.record_task(worker_id, task_id, breakdown)


class TestAggregateEmpty:
    """Tests for aggregation with no data."""

    def test_empty_returns_zeros(self, tmp_path) -> None:
        """Aggregate with no worker files returns all zeros."""
        agg = TokenAggregator(state_dir=tmp_path)
        result = agg.aggregate()

        assert result.total_tokens == 0
        assert result.total_tasks == 0
        assert result.tokens_per_task == 0.0
        assert result.per_worker == {}
        assert isinstance(result, AggregateResult)


class TestAggregateSingleWorker:
    """Tests for aggregation with one worker."""

    def test_single_worker_matches(self, tmp_path) -> None:
        """Aggregate with one worker matches that worker's data."""
        _seed_worker(
            tmp_path,
            "w0",
            {
                "T1": {"command_template": 100, "task_context": 200},
                "T2": {"command_template": 50, "task_context": 50},
            },
        )

        agg = TokenAggregator(state_dir=tmp_path)
        result = agg.aggregate()

        assert result.total_tokens == 400  # (100+200) + (50+50)
        assert result.total_tasks == 2
        assert result.tokens_per_task == 200.0
        assert "w0" in result.per_worker


class TestAggregateMultiWorker:
    """Tests for aggregation across multiple workers."""

    def test_multi_worker_sums(self, tmp_path) -> None:
        """Aggregate sums correctly across workers."""
        _seed_worker(tmp_path, "w0", {"T1": {"command_template": 100}})
        _seed_worker(tmp_path, "w1", {"T2": {"command_template": 200}})

        agg = TokenAggregator(state_dir=tmp_path)
        result = agg.aggregate()

        assert result.total_tokens == 300
        assert result.total_tasks == 2
        assert len(result.per_worker) == 2

    def test_breakdown_totals_sum(self, tmp_path) -> None:
        """Per-component breakdown sums are correct across workers."""
        _seed_worker(
            tmp_path,
            "w0",
            {
                "T1": {"command_template": 10, "task_context": 20},
            },
        )
        _seed_worker(
            tmp_path,
            "w1",
            {
                "T2": {"command_template": 30, "task_context": 40},
            },
        )

        agg = TokenAggregator(state_dir=tmp_path)
        result = agg.aggregate()

        assert result.breakdown_totals["command_template"] == 40
        assert result.breakdown_totals["task_context"] == 60


class TestSavingsCalculation:
    """Tests for calculate_savings."""

    def test_savings_with_default_multiplier(self, tmp_path) -> None:
        """Without explicit baseline, uses default multiplier."""
        _seed_worker(tmp_path, "w0", {"T1": {"command_template": 100}})

        agg = TokenAggregator(state_dir=tmp_path)
        savings = agg.calculate_savings()

        assert savings.context_injected_tokens == 100
        assert savings.full_spec_baseline_tokens == int(100 * _DEFAULT_BASELINE_MULTIPLIER)
        assert savings.tokens_saved == savings.full_spec_baseline_tokens - 100
        assert savings.savings_pct > 0

    def test_savings_with_explicit_baseline(self, tmp_path) -> None:
        """With explicit full_spec_tokens, uses that as baseline."""
        _seed_worker(tmp_path, "w0", {"T1": {"command_template": 100}})

        agg = TokenAggregator(state_dir=tmp_path)
        savings = agg.calculate_savings(full_spec_tokens=500)

        assert savings.full_spec_baseline_tokens == 500
        assert savings.tokens_saved == 400
        assert savings.savings_pct == 80.0

    def test_savings_zero_baseline_no_division_by_zero(self, tmp_path) -> None:
        """When both injected and baseline are 0, no division by zero."""
        agg = TokenAggregator(state_dir=tmp_path)
        savings = agg.calculate_savings(full_spec_tokens=0)

        assert savings.savings_pct == 0.0
        assert savings.tokens_saved == 0
        assert isinstance(savings, SavingsResult)


class TestEfficiencyRatio:
    """Tests for efficiency_ratio."""

    def test_ratio_with_tasks(self, tmp_path) -> None:
        """tokens_per_task = total / tasks."""
        _seed_worker(
            tmp_path,
            "w0",
            {
                "T1": {"command_template": 100},
                "T2": {"command_template": 200},
            },
        )

        agg = TokenAggregator(state_dir=tmp_path)
        ratio = agg.efficiency_ratio()

        assert ratio == 150.0  # 300 / 2

    def test_ratio_zero_tasks(self, tmp_path) -> None:
        """With no tasks, efficiency_ratio returns 0.0."""
        agg = TokenAggregator(state_dir=tmp_path)
        ratio = agg.efficiency_ratio()

        assert ratio == 0.0


class TestBreakdownKeys:
    """Tests for breakdown_totals completeness."""

    def test_all_breakdown_keys_present(self, tmp_path) -> None:
        """Aggregate result contains all BREAKDOWN_KEYS even if data has none."""
        _seed_worker(tmp_path, "w0", {"T1": {"command_template": 10}})

        agg = TokenAggregator(state_dir=tmp_path)
        result = agg.aggregate()

        for key in BREAKDOWN_KEYS:
            assert key in result.breakdown_totals
