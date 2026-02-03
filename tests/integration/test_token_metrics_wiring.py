"""Integration test: token metrics pipeline end-to-end.

Verifies the full flow: TokenCounter -> TokenTracker -> TokenAggregator -> format_token_table.
No API keys needed — uses heuristic counting mode only.
"""

from __future__ import annotations

import pytest

from zerg.config import TokenMetricsConfig
from zerg.status_formatter import format_token_table
from zerg.token_aggregator import TokenAggregator
from zerg.token_counter import TokenCounter
from zerg.token_tracker import TokenTracker


class TestTokenMetricsPipeline:
    """End-to-end test for the token metrics pipeline."""

    def test_count_record_aggregate_format(self, tmp_path: pytest.TempPathFactory) -> None:
        """Walk the full pipeline from counting to dashboard rendering."""
        # Step 1: Create a TokenCounter in heuristic mode (no API)
        config = TokenMetricsConfig(
            api_counting=False,
            cache_enabled=False,
        )
        counter = TokenCounter(config=config)

        # Step 2: Count some sample text
        sample_text = "def hello_world():\n    print('Hello, ZERG!')\n" * 10
        result = counter.count(sample_text)
        assert result.count > 0
        assert result.mode == "estimated"
        assert result.source == "heuristic"

        # Step 3: Create a TokenTracker with tmp_path as state_dir
        tracker = TokenTracker(state_dir=tmp_path)

        # Step 4: Record a task with breakdown
        breakdown = {
            "command_template": result.count // 2,
            "task_context": result.count // 4,
            "repo_map": result.count // 8,
            "security_rules": result.count // 8,
            "spec_excerpt": 0,
        }
        tracker.record_task(
            worker_id="w1",
            task_id="TASK-001",
            breakdown=breakdown,
            mode=result.mode,
        )

        # Verify the tracker persisted correctly
        worker_data = tracker.read("w1")
        assert worker_data is not None
        assert worker_data["cumulative"]["tasks_completed"] == 1
        assert worker_data["cumulative"]["total_tokens"] == sum(breakdown.values())

        # Record a second task for the same worker
        second_text = "class Zergling:\n    pass\n" * 5
        result2 = counter.count(second_text)
        breakdown2 = {
            "command_template": result2.count,
            "task_context": 0,
            "repo_map": 0,
            "security_rules": 0,
            "spec_excerpt": 0,
        }
        tracker.record_task(
            worker_id="w1",
            task_id="TASK-002",
            breakdown=breakdown2,
            mode=result2.mode,
        )

        # Record a task for a different worker
        tracker.record_task(
            worker_id="w2",
            task_id="TASK-003",
            breakdown={"command_template": 100, "task_context": 200},
            mode="estimated",
        )

        # Step 5: Create a TokenAggregator with same tmp_path
        aggregator = TokenAggregator(state_dir=tmp_path)

        # Step 6: Aggregate and verify totals
        agg = aggregator.aggregate()
        assert agg.total_tasks == 3
        assert agg.total_tokens > 0

        expected_w1_tokens = sum(breakdown.values()) + sum(breakdown2.values())
        assert agg.per_worker["w1"]["total_tokens"] == expected_w1_tokens
        assert agg.per_worker["w1"]["tasks_completed"] == 2
        assert agg.per_worker["w2"]["total_tokens"] == 300
        assert agg.per_worker["w2"]["tasks_completed"] == 1

        # Step 7: Format as dashboard table
        table_output = format_token_table(agg.per_worker)

        # Step 8: Verify the output contains expected data
        assert "w1" in table_output
        assert "w2" in table_output
        assert "TOTAL" in table_output
        assert "Worker" in table_output
        assert "Tasks" in table_output

    def test_empty_state_dir_produces_empty_aggregate(self, tmp_path: pytest.TempPathFactory) -> None:
        """Aggregator on empty state dir returns zero totals."""
        aggregator = TokenAggregator(state_dir=tmp_path)
        agg = aggregator.aggregate()
        assert agg.total_tokens == 0
        assert agg.total_tasks == 0
        assert agg.per_worker == {}

    def test_savings_calculation(self, tmp_path: pytest.TempPathFactory) -> None:
        """Verify savings calculation uses the default baseline multiplier."""
        tracker = TokenTracker(state_dir=tmp_path)
        tracker.record_task(
            worker_id="w1",
            task_id="TASK-001",
            breakdown={"command_template": 1000, "task_context": 500},
            mode="estimated",
        )

        aggregator = TokenAggregator(state_dir=tmp_path)
        savings = aggregator.calculate_savings()

        assert savings.context_injected_tokens == 1500
        # Default multiplier is 2.5, so baseline = 1500 * 2.5 = 3750
        assert savings.full_spec_baseline_tokens == 3750
        assert savings.tokens_saved == 3750 - 1500
        assert savings.savings_pct > 0
