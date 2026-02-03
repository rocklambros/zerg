"""What-if analysis engine for ZERG rush planning.

Compares different worker counts and execution modes to help
choose optimal rush configuration.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console
from rich.table import Table

from zerg.assign import WorkerAssignment
from zerg.logging import get_logger

logger = get_logger("whatif")
console = Console()


@dataclass
class ScenarioResult:
    """Result of a single what-if scenario."""

    label: str
    workers: int
    mode: str
    total_sequential_minutes: int
    estimated_wall_minutes: int
    efficiency: float  # 0.0 to 1.0
    per_level_wall: dict[int, int] = field(default_factory=dict)
    max_worker_load: int = 0
    min_worker_load: int = 0


@dataclass
class WhatIfReport:
    """Comparison of multiple scenarios."""

    scenarios: list[ScenarioResult] = field(default_factory=list)
    recommendation: str = ""


class WhatIfEngine:
    """Compare different rush configurations."""

    # Overhead multipliers per mode
    MODE_OVERHEAD = {
        "subprocess": 1.0,
        "container": 1.15,  # ~15% overhead for container startup/networking
        "task": 1.05,
        "auto": 1.0,
    }

    def __init__(self, task_data: dict[str, Any], feature: str = "") -> None:
        self.task_data = task_data
        self.feature = feature
        self.tasks = task_data.get("tasks", [])

    def compare_worker_counts(
        self,
        counts: list[int] | None = None,
        mode: str = "auto",
    ) -> WhatIfReport:
        """Compare different worker counts."""
        if counts is None:
            counts = [3, 5, 7]

        report = WhatIfReport()

        for count in counts:
            scenario = self._simulate(count, mode, label=f"{count} workers")
            report.scenarios.append(scenario)

        report.recommendation = self._recommend(report.scenarios)
        return report

    def compare_modes(
        self,
        modes: list[str] | None = None,
        workers: int = 5,
    ) -> WhatIfReport:
        """Compare different execution modes."""
        if modes is None:
            modes = ["subprocess", "container"]

        report = WhatIfReport()

        for mode in modes:
            scenario = self._simulate(workers, mode, label=f"{mode} mode")
            report.scenarios.append(scenario)

        report.recommendation = self._recommend(report.scenarios)
        return report

    def compare_all(
        self,
        counts: list[int] | None = None,
        modes: list[str] | None = None,
    ) -> WhatIfReport:
        """Compare combinations of worker counts and modes."""
        if counts is None:
            counts = [3, 5]
        if modes is None:
            modes = ["subprocess", "container"]

        report = WhatIfReport()

        for mode in modes:
            for count in counts:
                label = f"{count}w/{mode}"
                scenario = self._simulate(count, mode, label=label)
                report.scenarios.append(scenario)

        report.recommendation = self._recommend(report.scenarios)
        return report

    def render(self, report: WhatIfReport) -> None:
        """Render a what-if comparison table."""
        table = Table(title="What-If Comparison", show_header=True)
        table.add_column("Scenario", style="cyan", width=20)
        table.add_column("Workers", justify="center", width=8)
        table.add_column("Mode", width=12)
        table.add_column("Wall Time", justify="right", width=10)
        table.add_column("Efficiency", justify="right", width=10)
        table.add_column("Worker Load", justify="right", width=14)

        for s in report.scenarios:
            if ":" in report.recommendation:
                is_best = s.label == report.recommendation.split(":")[0].strip()
            else:
                is_best = False
            style = "bold green" if is_best else ""

            load_str = f"{s.min_worker_load}-{s.max_worker_load}m"
            table.add_row(
                s.label,
                str(s.workers),
                s.mode,
                f"{s.estimated_wall_minutes}m",
                f"{s.efficiency:.0%}",
                load_str,
                style=style,
            )

        console.print(table)

        if report.recommendation:
            console.print(f"\n[bold]Recommendation:[/bold] {report.recommendation}")

    def _simulate(self, workers: int, mode: str, label: str) -> ScenarioResult:
        """Simulate a single scenario."""
        assigner = WorkerAssignment(workers)
        assigner.assign(self.tasks, self.feature or "whatif")

        # Group tasks by level
        level_tasks: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for task in self.tasks:
            level_tasks[task.get("level", 1)].append(task)

        total_sequential = sum(t.get("estimate_minutes", 15) for t in self.tasks)
        per_level_wall: dict[int, int] = {}

        for level_num in sorted(level_tasks.keys()):
            worker_loads: dict[int, int] = defaultdict(int)
            for task in level_tasks[level_num]:
                worker_id = assigner.get_task_worker(task["id"])
                if worker_id is not None:
                    worker_loads[worker_id] += task.get("estimate_minutes", 15)
            per_level_wall[level_num] = max(worker_loads.values()) if worker_loads else 0

        raw_wall = sum(per_level_wall.values())

        # Apply mode overhead
        overhead = self.MODE_OVERHEAD.get(mode, 1.0)
        estimated_wall = int(raw_wall * overhead)

        efficiency = total_sequential / (estimated_wall * workers) if estimated_wall > 0 and workers > 0 else 0.0

        # Worker load range
        summary = assigner.get_workload_summary()
        loads = [info.get("estimated_minutes", 0) for info in summary.values()]
        max_load = max(loads) if loads else 0
        min_load = min(loads) if loads else 0

        return ScenarioResult(
            label=label,
            workers=workers,
            mode=mode,
            total_sequential_minutes=total_sequential,
            estimated_wall_minutes=estimated_wall,
            efficiency=efficiency,
            per_level_wall=per_level_wall,
            max_worker_load=max_load,
            min_worker_load=min_load,
        )

    @staticmethod
    def _recommend(scenarios: list[ScenarioResult]) -> str:
        """Pick best scenario balancing speed and efficiency."""
        if not scenarios:
            return ""

        # Score: lower wall time is better, but penalize very low efficiency
        best = min(
            scenarios,
            key=lambda s: s.estimated_wall_minutes * (1.0 + max(0, 0.5 - s.efficiency)),
        )

        return f"{best.label}: {best.estimated_wall_minutes}m wall time, {best.efficiency:.0%} efficiency"
