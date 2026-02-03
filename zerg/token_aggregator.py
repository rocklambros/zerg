"""Aggregate token usage across all ZERG workers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from zerg.token_tracker import TokenTracker

logger = logging.getLogger(__name__)

BREAKDOWN_KEYS = (
    "command_template",
    "task_context",
    "repo_map",
    "security_rules",
    "spec_excerpt",
)

# Rough multiplier: full-spec injection is ~2.5x the optimized context size.
_DEFAULT_BASELINE_MULTIPLIER = 2.5


@dataclass
class AggregateResult:
    """Cumulative token usage across all workers."""

    total_tokens: int = 0
    total_tasks: int = 0
    tokens_per_task: float = 0.0
    per_worker: dict = field(default_factory=dict)
    breakdown_totals: dict = field(default_factory=dict)


@dataclass
class SavingsResult:
    """Token savings compared to a full-spec baseline."""

    context_injected_tokens: int = 0
    full_spec_baseline_tokens: int = 0
    tokens_saved: int = 0
    savings_pct: float = 0.0
    breakdown: dict = field(default_factory=dict)


class TokenAggregator:
    """Read all worker token files, compute cumulative totals and savings.

    All public methods catch exceptions internally and return zero/empty
    results rather than raising.
    """

    def __init__(self, state_dir: str | Path | None = None) -> None:
        self._tracker = TokenTracker(state_dir=state_dir)

    def aggregate(self) -> AggregateResult:
        """Aggregate token data from every worker."""
        try:
            all_data = self._tracker.read_all()
            if not all_data:
                return AggregateResult()

            total_tokens = 0
            total_tasks = 0
            per_worker: dict = {}
            breakdown_totals: dict = {k: 0 for k in BREAKDOWN_KEYS}

            for wid, wdata in all_data.items():
                cum = wdata.get("cumulative", {})
                w_tokens = cum.get("total_tokens", 0)
                w_tasks = cum.get("tasks_completed", 0)

                total_tokens += w_tokens
                total_tasks += w_tasks
                per_worker[wid] = {
                    "total_tokens": w_tokens,
                    "tasks_completed": w_tasks,
                }

                # Sum per-component breakdowns across all tasks
                for task_info in wdata.get("tasks", {}).values():
                    bd = task_info.get("breakdown", {})
                    for key in BREAKDOWN_KEYS:
                        breakdown_totals[key] += int(bd.get(key, 0))

            tokens_per_task = total_tokens / total_tasks if total_tasks > 0 else 0.0

            return AggregateResult(
                total_tokens=total_tokens,
                total_tasks=total_tasks,
                tokens_per_task=tokens_per_task,
                per_worker=per_worker,
                breakdown_totals=breakdown_totals,
            )
        except Exception:
            logger.warning("Failed to aggregate token data", exc_info=True)
            return AggregateResult()

    def calculate_savings(self, full_spec_tokens: int = 0) -> SavingsResult:
        """Compare injected context tokens against a full-spec baseline.

        Args:
            full_spec_tokens: Known token count for full-spec injection per
                task. If 0, estimates as total_tokens * baseline multiplier.
        """
        try:
            agg = self.aggregate()
            injected = agg.total_tokens

            if full_spec_tokens > 0:
                baseline = full_spec_tokens
            else:
                baseline = int(injected * _DEFAULT_BASELINE_MULTIPLIER)

            saved = baseline - injected
            pct = (saved / baseline * 100.0) if baseline > 0 else 0.0

            # Per-component savings (estimate each component at same ratio)
            bd = agg.breakdown_totals
            component_breakdown: dict = {}
            for key, val in bd.items():
                est_full = (
                    int(val * _DEFAULT_BASELINE_MULTIPLIER)
                    if full_spec_tokens == 0
                    else val  # no per-component baseline available
                )
                component_breakdown[key] = {
                    "injected": val,
                    "baseline": est_full,
                    "saved": est_full - val,
                }

            return SavingsResult(
                context_injected_tokens=injected,
                full_spec_baseline_tokens=baseline,
                tokens_saved=saved,
                savings_pct=round(pct, 2),
                breakdown=component_breakdown,
            )
        except Exception:
            logger.warning("Failed to calculate token savings", exc_info=True)
            return SavingsResult()

    def efficiency_ratio(self) -> float:
        """Return tokens per completed task, or 0.0 if no tasks."""
        try:
            agg = self.aggregate()
            return agg.tokens_per_task
        except Exception:
            logger.warning("Failed to compute efficiency ratio", exc_info=True)
            return 0.0
