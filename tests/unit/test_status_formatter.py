"""Unit tests for zerg.status_formatter."""

from __future__ import annotations

from datetime import UTC, datetime

from zerg.status_formatter import (
    format_escalations,
    format_health_table,
    format_repo_map_stats,
    format_savings,
    format_token_table,
)

# ---------------------------------------------------------------------------
# format_health_table
# ---------------------------------------------------------------------------


class TestFormatHealthTableEmpty:
    """Tests for format_health_table with no data."""

    def test_empty_list_returns_message(self) -> None:
        result = format_health_table([])
        assert result == "No worker data available"

    def test_none_heartbeats_treated_as_empty(self) -> None:
        # Passing an empty list explicitly
        result = format_health_table([])
        assert "No worker data" in result


class TestFormatHealthTableWithData:
    """Tests for format_health_table with actual heartbeat data."""

    @staticmethod
    def _make_heartbeat(
        worker_id: int = 1,
        task_id: str = "TASK-001",
        step: str = "execute",
        progress_pct: int = 50,
    ) -> dict:
        now = datetime.now(UTC).isoformat()
        return {
            "worker_id": worker_id,
            "timestamp": now,
            "task_id": task_id,
            "step": step,
            "progress_pct": progress_pct,
        }

    def test_contains_expected_columns(self) -> None:
        hb = self._make_heartbeat()
        result = format_health_table([hb])
        assert "Worker" in result
        assert "Status" in result
        assert "Task" in result
        assert "Step" in result
        assert "Progress" in result
        assert "Restarts" in result

    def test_worker_id_appears_in_output(self) -> None:
        hb = self._make_heartbeat(worker_id=3)
        result = format_health_table([hb])
        assert "3" in result

    def test_task_id_appears_in_output(self) -> None:
        hb = self._make_heartbeat(task_id="TASK-007")
        result = format_health_table([hb])
        assert "TASK-007" in result

    def test_multiple_workers_sorted_by_id(self) -> None:
        hbs = [
            self._make_heartbeat(worker_id=3),
            self._make_heartbeat(worker_id=1),
            self._make_heartbeat(worker_id=2),
        ]
        result = format_health_table(hbs)
        lines = result.split("\n")
        # Data rows are lines 3,4,5 (after top border, header, separator)
        data_lines = [ln for ln in lines if "\u2502" in ln and "Worker" not in ln]
        assert len(data_lines) == 3
        # Worker 1 should appear before worker 3
        idx_1 = next(i for i, ln in enumerate(data_lines) if " 1 " in ln)
        idx_3 = next(i for i, ln in enumerate(data_lines) if " 3 " in ln)
        assert idx_1 < idx_3

    def test_column_alignment_consistent_width(self) -> None:
        hbs = [
            self._make_heartbeat(worker_id=1),
            self._make_heartbeat(worker_id=2),
        ]
        result = format_health_table(hbs)
        lines = result.split("\n")
        # All lines should have the same width (box-drawing table)
        widths = {len(line) for line in lines if line.strip()}
        assert len(widths) == 1, f"Inconsistent line widths: {widths}"

    def test_stale_heartbeat_shows_stale_status(self) -> None:
        old_ts = "2020-01-01T00:00:00+00:00"
        hb = {
            "worker_id": 1,
            "timestamp": old_ts,
            "task_id": "TASK-001",
            "step": "execute",
            "progress_pct": 50,
        }
        result = format_health_table([hb])
        assert "stale" in result

    def test_restarts_from_progress_data(self) -> None:
        hb = self._make_heartbeat(worker_id=1)
        progress = [
            {
                "worker_id": 1,
                "tier_results": [{"retry": 2}, {"retry": 1}],
            }
        ]
        result = format_health_table([hb], progress_data=progress)
        assert "3" in result  # 2 + 1 = 3 restarts


# ---------------------------------------------------------------------------
# format_escalations
# ---------------------------------------------------------------------------


class TestFormatEscalationsEmpty:
    """Tests for format_escalations with no data."""

    def test_empty_list_returns_no_escalations(self) -> None:
        result = format_escalations([])
        assert result == "No escalations"


class TestFormatEscalationsWithData:
    """Tests for format_escalations with escalation data."""

    def test_shows_unresolved_count(self) -> None:
        escalations = [
            {
                "worker_id": 1,
                "task_id": "TASK-001",
                "category": "timeout",
                "message": "Task exceeded timeout",
                "resolved": False,
            },
            {
                "worker_id": 2,
                "task_id": "TASK-002",
                "category": "error",
                "message": "Build failed",
                "resolved": True,
            },
        ]
        result = format_escalations(escalations)
        assert "1 unresolved" in result
        assert "1 resolved" in result

    def test_all_resolved_shows_zero_unresolved(self) -> None:
        escalations = [
            {
                "worker_id": 1,
                "task_id": "TASK-001",
                "category": "timeout",
                "message": "done",
                "resolved": True,
            }
        ]
        result = format_escalations(escalations)
        assert "0 unresolved" in result

    def test_shows_task_and_worker(self) -> None:
        escalations = [
            {
                "worker_id": 5,
                "task_id": "TASK-042",
                "category": "build_failure",
                "message": "Compilation error",
                "resolved": False,
            }
        ]
        result = format_escalations(escalations)
        assert "TASK-042" in result
        assert "Worker 5" in result
        assert "build_failure" in result


# ---------------------------------------------------------------------------
# format_repo_map_stats
# ---------------------------------------------------------------------------


class TestFormatRepoMapStatsNone:
    """Tests for format_repo_map_stats with None input."""

    def test_none_returns_no_data_message(self) -> None:
        result = format_repo_map_stats(None)
        assert result == "No repo map data available"

    def test_empty_dict_returns_no_data_message(self) -> None:
        result = format_repo_map_stats({})
        assert result == "No repo map data available"

    def test_zero_counts_returns_no_data_message(self) -> None:
        result = format_repo_map_stats({"total_files": 0, "indexed_files": 0, "stale_files": 0})
        assert result == "No repo map data available"


class TestFormatRepoMapStatsWithData:
    """Tests for format_repo_map_stats with valid data."""

    def test_shows_file_counts(self) -> None:
        data = {
            "total_files": 42,
            "indexed_files": 40,
            "stale_files": 2,
            "last_updated": "2026-01-15T10:00:00",
        }
        result = format_repo_map_stats(data)
        assert "42" in result
        assert "40" in result
        assert "2" in result
        assert "Files tracked" in result
        assert "Files indexed" in result
        assert "Stale files" in result

    def test_shows_last_updated(self) -> None:
        data = {
            "total_files": 10,
            "indexed_files": 10,
            "stale_files": 0,
            "last_updated": "2026-01-15T10:00:00",
        }
        result = format_repo_map_stats(data)
        assert "2026-01-15" in result


# ---------------------------------------------------------------------------
# format_token_table
# ---------------------------------------------------------------------------


class TestFormatTokenTableEmpty:
    """Tests for format_token_table with no data."""

    def test_empty_dict_returns_no_data_message(self) -> None:
        result = format_token_table({})
        assert result == "No token data available"

    def test_none_returns_no_data_message(self) -> None:
        result = format_token_table(None)
        assert result == "No token data available"


class TestFormatTokenTableWithData:
    """Tests for format_token_table with worker data."""

    @staticmethod
    def _sample_data() -> dict:
        return {
            "w1": {
                "total_tokens": 5000,
                "tasks_completed": 2,
                "mode": "estimated",
            },
            "w2": {
                "total_tokens": 8000,
                "tasks_completed": 4,
                "mode": "exact",
            },
        }

    def test_contains_expected_columns(self) -> None:
        result = format_token_table(self._sample_data())
        assert "Worker" in result
        assert "Tasks" in result
        assert "Tokens/Task" in result
        assert "Total" in result
        assert "Mode" in result

    def test_shows_estimated_mode(self) -> None:
        result = format_token_table(self._sample_data())
        assert "(estimated)" in result

    def test_shows_exact_mode(self) -> None:
        result = format_token_table(self._sample_data())
        assert "(exact)" in result

    def test_shows_worker_ids(self) -> None:
        result = format_token_table(self._sample_data())
        assert "w1" in result
        assert "w2" in result

    def test_shows_total_row(self) -> None:
        result = format_token_table(self._sample_data())
        assert "TOTAL" in result

    def test_total_tokens_sum(self) -> None:
        result = format_token_table(self._sample_data())
        # 5000 + 8000 = 13000 -> formatted as "13,000"
        assert "13,000" in result

    def test_single_worker_zero_tasks(self) -> None:
        data = {"w1": {"total_tokens": 0, "tasks_completed": 0}}
        result = format_token_table(data)
        assert "w1" in result
        assert "TOTAL" in result


# ---------------------------------------------------------------------------
# format_savings
# ---------------------------------------------------------------------------


class TestFormatSavingsNone:
    """Tests for format_savings with None input."""

    def test_none_returns_no_data_message(self) -> None:
        result = format_savings(None)
        assert result == "No savings data available"


class TestFormatSavingsWithDict:
    """Tests for format_savings with dict input."""

    def test_shows_percentage(self) -> None:
        data = {
            "context_injected_tokens": 4000,
            "full_spec_baseline_tokens": 10000,
            "tokens_saved": 6000,
            "savings_pct": 60.0,
            "breakdown": None,
        }
        result = format_savings(data)
        assert "60.0%" in result

    def test_shows_token_counts(self) -> None:
        data = {
            "context_injected_tokens": 4000,
            "full_spec_baseline_tokens": 10000,
            "tokens_saved": 6000,
            "savings_pct": 60.0,
            "breakdown": None,
        }
        result = format_savings(data)
        assert "4,000" in result
        assert "10,000" in result
        assert "6,000" in result

    def test_zero_baseline_returns_no_data(self) -> None:
        data = {
            "context_injected_tokens": 0,
            "full_spec_baseline_tokens": 0,
            "tokens_saved": 0,
            "savings_pct": 0.0,
            "breakdown": None,
        }
        result = format_savings(data)
        assert result == "No savings data available"

    def test_with_breakdown(self) -> None:
        data = {
            "context_injected_tokens": 4000,
            "full_spec_baseline_tokens": 10000,
            "tokens_saved": 6000,
            "savings_pct": 60.0,
            "breakdown": {
                "command_template": {"injected": 1000, "saved": 1500},
                "task_context": {"injected": 3000, "saved": 4500},
            },
        }
        result = format_savings(data)
        assert "Breakdown" in result
        assert "command_template" in result
        assert "task_context" in result


class TestFormatSavingsWithDataclass:
    """Tests for format_savings with SavingsResult dataclass."""

    def test_dataclass_input(self) -> None:
        from zerg.token_aggregator import SavingsResult

        sr = SavingsResult(
            context_injected_tokens=3000,
            full_spec_baseline_tokens=7500,
            tokens_saved=4500,
            savings_pct=60.0,
            breakdown={"repo_map": {"injected": 500, "saved": 750}},
        )
        result = format_savings(sr)
        assert "60.0%" in result
        assert "3,000" in result
        assert "repo_map" in result
