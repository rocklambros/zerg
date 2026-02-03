"""Dry-run simulation for ZERG rush command.

Validates everything a real rush would validate, shows timeline estimates,
worker load balance, risk assessment, pre-flight checks, and optionally
pre-runs quality gates.
"""

from __future__ import annotations

import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from zerg.assign import WorkerAssignment
from zerg.config import ZergConfig
from zerg.gates import GateRunner
from zerg.preflight import PreflightChecker, PreflightReport
from zerg.render_utils import render_gantt_chart
from zerg.risk_scoring import RiskReport, RiskScorer
from zerg.validation import (
    validate_dependencies,
    validate_file_ownership,
)

console = Console()


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class LevelTimeline:
    """Timeline estimate for a single level."""

    level: int
    task_count: int
    wall_minutes: int
    worker_loads: dict[int, int] = field(default_factory=dict)


@dataclass
class TimelineEstimate:
    """Overall timeline estimate for the rush."""

    total_sequential_minutes: int
    estimated_wall_minutes: int
    critical_path_minutes: int
    parallelization_efficiency: float
    per_level: dict[int, LevelTimeline] = field(default_factory=dict)


@dataclass
class GateCheckResult:
    """Result of a single quality gate check."""

    name: str
    command: str
    required: bool
    status: str  # passed | failed | not_run | error
    duration_ms: int | None = None


@dataclass
class DryRunReport:
    """Complete dry-run simulation report."""

    feature: str
    workers: int
    mode: str
    level_issues: list[str] = field(default_factory=list)
    file_ownership_issues: list[str] = field(default_factory=list)
    dependency_issues: list[str] = field(default_factory=list)
    resource_issues: list[str] = field(default_factory=list)
    missing_verifications: list[str] = field(default_factory=list)
    timeline: TimelineEstimate | None = None
    gate_results: list[GateCheckResult] = field(default_factory=list)
    task_data: dict[str, Any] = field(default_factory=dict)
    worker_loads: dict[int, dict[str, Any]] = field(default_factory=dict)
    preflight: PreflightReport | None = None
    risk: RiskReport | None = None

    @property
    def has_errors(self) -> bool:
        return bool(
            self.level_issues
            or self.file_ownership_issues
            or self.dependency_issues
            or self.resource_issues
            or any(g.status == "failed" and g.required for g in self.gate_results)
            or (self.preflight and not self.preflight.passed)
        )

    @property
    def has_warnings(self) -> bool:
        return bool(
            self.missing_verifications
            or any(g.status == "failed" and not g.required for g in self.gate_results)
            or (self.preflight and self.preflight.warnings)
            or (self.risk and self.risk.grade in ("C", "D"))
        )


# ---------------------------------------------------------------------------
# Simulator
# ---------------------------------------------------------------------------


class DryRunSimulator:
    """Simulate a full rush pipeline without executing tasks."""

    def __init__(
        self,
        task_data: dict[str, Any],
        workers: int,
        feature: str,
        config: ZergConfig | None = None,
        mode: str = "auto",
        run_gates: bool = False,
    ) -> None:
        self.task_data = task_data
        self.workers = workers
        self.feature = feature
        self.config = config or ZergConfig()
        self.mode = mode
        self.run_gates = run_gates

    # -- public entry point --------------------------------------------------

    def run(self) -> DryRunReport:
        """Orchestrate all checks and render the report."""
        report = DryRunReport(
            feature=self.feature,
            workers=self.workers,
            mode=self.mode,
            task_data=self.task_data,
        )

        # Pre-flight checks
        report.preflight = self._run_preflight()

        report.level_issues = self._validate_level_structure()
        report.file_ownership_issues = self._validate_file_ownership()
        report.dependency_issues = self._validate_dependencies()
        report.missing_verifications = self._check_missing_verifications()
        report.resource_issues = self._check_resources()

        # Risk scoring
        report.risk = self._compute_risk()

        # Worker assignment + timeline
        assigner = WorkerAssignment(self.workers)
        tasks = self.task_data.get("tasks", [])
        assigner.assign(tasks, self.feature)
        report.worker_loads = assigner.get_workload_summary()
        report.timeline = self._compute_timeline(assigner)

        # Quality gates
        report.gate_results = self._check_quality_gates()

        self._render_report(report)
        return report

    # -- pre-flight ----------------------------------------------------------

    def _run_preflight(self) -> PreflightReport:
        """Run pre-flight environment checks."""
        checker = PreflightChecker(
            mode=self.mode,
            worker_count=self.workers,
            port_range_start=self.config.ports.range_start,
            port_range_end=self.config.ports.range_end,
        )
        return checker.run_all()

    # -- risk scoring --------------------------------------------------------

    def _compute_risk(self) -> RiskReport:
        """Compute risk assessment for the task graph."""
        scorer = RiskScorer(self.task_data, self.workers)
        return scorer.score()

    # -- validation methods --------------------------------------------------

    def _validate_level_structure(self) -> list[str]:
        """Check for gaps or inconsistencies in level numbering."""
        issues: list[str] = []
        tasks = self.task_data.get("tasks", [])
        if not tasks:
            issues.append("No tasks defined in task graph")
            return issues

        levels_in_tasks = sorted({t.get("level", 1) for t in tasks})
        expected = list(range(levels_in_tasks[0], levels_in_tasks[-1] + 1))
        missing = set(expected) - set(levels_in_tasks)
        if missing:
            issues.append(f"Gap in level numbering: missing levels {sorted(missing)}")
        return issues

    def _validate_file_ownership(self) -> list[str]:
        """Check for duplicate file claims across tasks."""
        _, errors = validate_file_ownership(self.task_data)
        return errors

    def _validate_dependencies(self) -> list[str]:
        """Check for cycles and level violations."""
        _, errors = validate_dependencies(self.task_data)
        return errors

    def _check_missing_verifications(self) -> list[str]:
        """Warn about tasks lacking a verification command."""
        warnings: list[str] = []
        for task in self.task_data.get("tasks", []):
            verification = task.get("verification")
            if not verification or not verification.get("command"):
                warnings.append(f"Task {task.get('id', '?')} has no verification command")
        return warnings

    def _check_resources(self) -> list[str]:
        """Check git repo, disk space, etc."""
        issues: list[str] = []

        if not Path(".git").exists():
            issues.append("No .git directory found — not a git repository")

        try:
            usage = shutil.disk_usage(".")
            free_gb = usage.free / (1024**3)
            if free_gb < 1.0:
                issues.append(f"Low disk space: {free_gb:.1f} GB free")
        except OSError:
            pass

        return issues

    # -- analysis methods ----------------------------------------------------

    def _compute_timeline(self, assigner: WorkerAssignment) -> TimelineEstimate:
        """Compute per-level wall times and overall timeline."""
        tasks = self.task_data.get("tasks", [])

        # Group tasks by level
        level_tasks: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for task in tasks:
            level_tasks[task.get("level", 1)].append(task)

        total_sequential = sum(t.get("estimate_minutes", 15) for t in tasks)
        per_level: dict[int, LevelTimeline] = {}

        for level_num in sorted(level_tasks.keys()):
            # Compute per-worker load for this level
            worker_loads: dict[int, int] = defaultdict(int)
            for task in level_tasks[level_num]:
                worker_id = assigner.get_task_worker(task["id"])
                if worker_id is not None:
                    worker_loads[worker_id] += task.get("estimate_minutes", 15)

            wall = max(worker_loads.values()) if worker_loads else 0
            per_level[level_num] = LevelTimeline(
                level=level_num,
                task_count=len(level_tasks[level_num]),
                wall_minutes=wall,
                worker_loads=dict(worker_loads),
            )

        estimated_wall = sum(lt.wall_minutes for lt in per_level.values())
        critical_path = self.task_data.get("critical_path_minutes", estimated_wall)

        efficiency = (
            total_sequential / (estimated_wall * self.workers) if estimated_wall > 0 and self.workers > 0 else 0.0
        )

        return TimelineEstimate(
            total_sequential_minutes=total_sequential,
            estimated_wall_minutes=estimated_wall,
            critical_path_minutes=critical_path,
            parallelization_efficiency=efficiency,
            per_level=per_level,
        )

    def _check_quality_gates(self) -> list[GateCheckResult]:
        """Check or list quality gates."""
        gates = self.config.quality_gates
        if not gates:
            return []

        if not self.run_gates:
            return [
                GateCheckResult(
                    name=g.name,
                    command=g.command,
                    required=g.required,
                    status="not_run",
                )
                for g in gates
            ]

        # Actually run the gates
        runner = GateRunner(self.config)
        _, run_results = runner.run_all_gates(stop_on_failure=False)

        results: list[GateCheckResult] = []
        for rr in run_results:
            status_str = rr.result.value if hasattr(rr.result, "value") else str(rr.result)
            # Map GateResult values to our status strings
            status_map = {"pass": "passed", "fail": "failed", "error": "error", "timeout": "error"}
            mapped = status_map.get(status_str, status_str)

            # Find the gate config to get required flag
            gate_cfg = next((g for g in gates if g.name == rr.gate_name), None)
            results.append(
                GateCheckResult(
                    name=rr.gate_name,
                    command=rr.command,
                    required=gate_cfg.required if gate_cfg else False,
                    status=mapped,
                    duration_ms=rr.duration_ms,
                )
            )
        return results

    # -- render --------------------------------------------------------------

    def _render_report(self, report: DryRunReport) -> None:
        """Render the full dry-run report using Rich."""
        console.print()

        # 1. Pre-flight panel
        self._render_preflight(report)

        # 2. Validation panel
        self._render_validation(report)

        # 3. Risk assessment
        self._render_risk(report)

        # 4. Per-level task tables
        self._render_levels(report)

        # 5. Worker load balance
        self._render_worker_loads(report)

        # 6. Gantt-style timeline
        self._render_gantt(report)

        # 7. Timeline estimate
        self._render_timeline(report)

        # 8. Projected status snapshots
        self._render_snapshots(report)

        # 9. Quality gates
        self._render_gates(report)

        # 10. Summary
        self._render_summary(report)

    def _render_preflight(self, report: DryRunReport) -> None:
        """Render pre-flight checks panel."""
        pf = report.preflight
        if not pf:
            return

        lines: list[Text] = []
        for check in pf.checks:
            line = Text()
            if check.passed:
                line.append("  ✓ ", style="green")
            elif check.severity == "warning":
                line.append("  ⚠ ", style="yellow")
            else:
                line.append("  ✗ ", style="red")
            line.append(f"{check.name}: {check.message}")
            lines.append(line)

        content = Text("\n").join(lines) if lines else Text("  No checks run")
        console.print(Panel(content, title="[bold]Pre-flight[/bold]", title_align="left"))

    def _render_validation(self, report: DryRunReport) -> None:
        """Render the validation checks panel."""
        lines: list[Text] = []

        checks = [
            ("Level structure", report.level_issues),
            ("File ownership", report.file_ownership_issues),
            ("Dependencies", report.dependency_issues),
            ("Resources", report.resource_issues),
            ("Verifications", report.missing_verifications),
        ]

        for label, issues in checks:
            line = Text()
            if not issues:
                line.append("  ✓ ", style="green")
                line.append(label)
            else:
                # Missing verifications are warnings, others are errors
                is_warning = label == "Verifications"
                symbol = "⚠" if is_warning else "✗"
                style = "yellow" if is_warning else "red"
                line.append(f"  {symbol} ", style=style)
                line.append(f"{label} ({len(issues)} issue{'s' if len(issues) != 1 else ''})")
                for issue in issues:
                    detail = Text()
                    detail.append(f"    → {issue}", style="dim")
                    lines.append(line)
                    line = detail
            lines.append(line)

        content = Text("\n").join(lines) if lines else Text("  No checks run")
        console.print(Panel(content, title="[bold]Validation[/bold]", title_align="left"))

    def _render_risk(self, report: DryRunReport) -> None:
        """Render risk assessment panel."""
        risk = report.risk
        if not risk:
            return

        lines: list[Text] = []

        # Grade header
        grade_colors = {"A": "green", "B": "yellow", "C": "red", "D": "bold red"}
        grade_line = Text()
        grade_line.append("  Grade: ", style="dim")
        grade_line.append(
            risk.grade,
            style=grade_colors.get(risk.grade, "white"),
        )
        grade_line.append(f" (score: {risk.overall_score:.2f})")
        lines.append(grade_line)

        # Critical path
        if risk.critical_path:
            cp_line = Text()
            cp_line.append("  Critical path: ", style="dim")
            cp_line.append(" → ".join(risk.critical_path))
            lines.append(cp_line)

        # Risk factors
        for factor in risk.risk_factors:
            fl = Text()
            fl.append("  ⚠ ", style="yellow")
            fl.append(factor)
            lines.append(fl)

        # High-risk tasks
        for tr in risk.high_risk_tasks:
            tl = Text()
            tl.append("  ✗ ", style="red")
            tl.append(f"{tr.task_id}: score {tr.score:.2f}")
            if tr.factors:
                tl.append(f" ({', '.join(tr.factors)})", style="dim")
            lines.append(tl)

        content = Text("\n").join(lines)
        console.print(Panel(content, title="[bold]Risk Assessment[/bold]", title_align="left"))

    def _render_levels(self, report: DryRunReport) -> None:
        """Render per-level task tables."""
        tasks = report.task_data.get("tasks", [])
        levels_info = report.task_data.get("levels", {})

        # Group tasks by level
        level_tasks: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for task in tasks:
            level_tasks[task.get("level", 1)].append(task)

        # Build assigner for worker info
        assigner = WorkerAssignment(report.workers)
        assigner.assign(tasks, report.feature)

        # Get risk data for per-task risk column
        risk_map: dict[str, float] = {}
        if report.risk:
            for tr in report.risk.task_risks:
                risk_map[tr.task_id] = tr.score

        for level_num in sorted(level_tasks.keys()):
            level_info = levels_info.get(str(level_num), {})
            timeline = report.timeline.per_level.get(level_num) if report.timeline else None
            wall_str = f" (~{timeline.wall_minutes}m wall)" if timeline else ""

            console.print(f"\n[bold cyan]Level {level_num}[/bold cyan] - {level_info.get('name', 'unnamed')}{wall_str}")

            table = Table(show_header=True)
            table.add_column("Task", style="cyan", width=15)
            table.add_column("Title", width=35)
            table.add_column("Worker", justify="center", width=8)
            table.add_column("Est.", justify="right", width=6)
            table.add_column("Risk", justify="center", width=6)

            for task in level_tasks[level_num]:
                worker = assigner.get_task_worker(task["id"])
                critical = "⭐ " if task.get("critical_path") else ""
                risk_score = risk_map.get(task["id"], 0)
                if risk_score >= 0.7:
                    risk_str = f"[red]{risk_score:.1f}[/red]"
                elif risk_score >= 0.4:
                    risk_str = f"[yellow]{risk_score:.1f}[/yellow]"
                else:
                    risk_str = f"[green]{risk_score:.1f}[/green]"
                table.add_row(
                    task["id"],
                    critical + task.get("title", ""),
                    str(worker) if worker is not None else "-",
                    f"{task.get('estimate_minutes', '?')}m",
                    risk_str,
                )

            console.print(table)

    def _render_worker_loads(self, report: DryRunReport) -> None:
        """Render worker load balance panel."""
        if not report.worker_loads:
            return

        lines: list[Text] = []
        max_minutes = max(
            (w.get("estimated_minutes", 0) for w in report.worker_loads.values()),
            default=1,
        )
        max_minutes = max(max_minutes, 1)  # avoid div by zero

        bar_width = 30
        for worker_id in sorted(report.worker_loads.keys()):
            info = report.worker_loads[worker_id]
            minutes = info.get("estimated_minutes", 0)
            task_count = info.get("task_count", 0)
            filled = int(bar_width * minutes / max_minutes)

            line = Text()
            line.append(f"  W{worker_id} ", style="bold")
            line.append("█" * filled, style="cyan")
            line.append("░" * (bar_width - filled), style="dim")
            line.append(f" {minutes}m ({task_count} tasks)")
            lines.append(line)

        content = Text("\n").join(lines)
        console.print(Panel(content, title="[bold]Worker Load Balance[/bold]", title_align="left"))

    def _render_gantt(self, report: DryRunReport) -> None:
        """Render Gantt-style timeline visualization."""
        tl = report.timeline
        if not tl or not tl.per_level:
            return

        gantt_text = render_gantt_chart(
            per_level=tl.per_level,
            worker_count=report.workers,
            chart_width=50,
        )
        console.print(Panel(gantt_text, title="[bold]Gantt Timeline[/bold]", title_align="left"))

    def _render_timeline(self, report: DryRunReport) -> None:
        """Render timeline estimate panel."""
        tl = report.timeline
        if not tl:
            return

        lines = Text()
        lines.append("  Sequential:   ", style="dim")
        lines.append(f"{tl.total_sequential_minutes}m\n")
        lines.append("  Parallel:     ", style="dim")
        lines.append(f"{tl.estimated_wall_minutes}m ({report.workers} workers)\n")
        lines.append("  Critical Path:", style="dim")
        lines.append(f" {tl.critical_path_minutes}m\n")
        lines.append("  Efficiency:   ", style="dim")
        lines.append(f"{tl.parallelization_efficiency:.0%}")

        console.print(Panel(lines, title="[bold]Timeline Estimate[/bold]", title_align="left"))

    def _render_snapshots(self, report: DryRunReport) -> None:
        """Render projected status snapshots at key time points."""
        tl = report.timeline
        if not tl or not tl.per_level:
            return

        lines: list[Text] = []
        cumulative = 0

        for level_num in sorted(tl.per_level.keys()):
            lt = tl.per_level[level_num]
            midpoint = cumulative + lt.wall_minutes // 2
            end = cumulative + lt.wall_minutes

            # Midpoint snapshot
            active_workers = sum(1 for m in lt.worker_loads.values() if m > 0)
            idle_workers = report.workers - active_workers

            mid_line = Text()
            mid_line.append(f"  t={midpoint}m: ", style="bold")
            mid_line.append(f"L{level_num} ~50% complete, ")
            mid_line.append(f"{active_workers} workers active")
            if idle_workers > 0:
                mid_line.append(f", {idle_workers} idle", style="dim")
            lines.append(mid_line)

            # End snapshot
            end_line = Text()
            end_line.append(f"  t={end}m: ", style="bold")
            end_line.append(f"L{level_num} complete")
            if level_num < max(tl.per_level.keys()):
                end_line.append(" → merging → next level", style="dim")
            lines.append(end_line)

            cumulative = end

        content = Text("\n").join(lines)
        console.print(Panel(content, title="[bold]Projected Snapshots[/bold]", title_align="left"))

    def _render_gates(self, report: DryRunReport) -> None:
        """Render quality gates panel."""
        if not report.gate_results:
            return

        lines: list[Text] = []
        for gate in report.gate_results:
            line = Text()
            if gate.status == "passed":
                line.append("  ✓ ", style="green")
            elif gate.status == "failed":
                line.append("  ✗ ", style="red")
            elif gate.status == "not_run":
                line.append("  ○ ", style="dim")
            else:
                line.append("  ! ", style="yellow")

            req_str = " (required)" if gate.required else ""
            dur_str = f" [{gate.duration_ms}ms]" if gate.duration_ms is not None else ""
            line.append(f"{gate.name}{req_str}{dur_str}")
            lines.append(line)

        content = Text("\n").join(lines)
        console.print(Panel(content, title="[bold]Quality Gates[/bold]", title_align="left"))

    def _render_summary(self, report: DryRunReport) -> None:
        """Render summary line."""
        error_count = (
            len(report.level_issues)
            + len(report.file_ownership_issues)
            + len(report.dependency_issues)
            + len(report.resource_issues)
        )
        if report.preflight:
            error_count += len(report.preflight.errors)

        warning_count = len(report.missing_verifications)
        if report.preflight:
            warning_count += len(report.preflight.warnings)

        gate_failures = sum(1 for g in report.gate_results if g.status == "failed" and g.required)
        error_count += gate_failures

        console.print()
        if error_count > 0:
            console.print(
                f"[bold red]✗ {error_count} error(s), {warning_count} warning(s) — not ready to rush[/bold red]"
            )
        elif warning_count > 0:
            console.print(f"[bold yellow]⚠ {warning_count} warning(s) — ready to rush (with warnings)[/bold yellow]")
        else:
            console.print("[bold green]✓ All checks passed — ready to rush[/bold green]")
        console.print()
