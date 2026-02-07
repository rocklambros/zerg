"""Dry-run report renderer.

Extracts all Rich rendering logic from ``zerg.dryrun.DryRunSimulator``
into a dedicated renderer class for clean SRP separation.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from zerg.rendering.shared import render_gantt_chart

if TYPE_CHECKING:
    from zerg.dryrun import DryRunReport

console = Console()


class DryRunRenderer:
    """Render a :class:`DryRunReport` to the terminal via Rich.

    Moved from ``DryRunSimulator._render_*`` methods by TASK-013.
    """

    def render(self, report: DryRunReport) -> None:
        """Render the full dry-run report.

        Args:
            report: Completed dry-run report to display.
        """
        console.print()

        # 1. Pre-flight panel
        self.render_preflight(report)

        # 2. Validation panel
        self.render_validation(report)

        # 3. Risk assessment
        self.render_risk(report)

        # 4. Per-level task tables
        self.render_levels(report)

        # 5. Worker load balance
        self.render_worker_loads(report)

        # 6. Gantt-style timeline
        self.render_gantt(report)

        # 7. Timeline estimate
        self.render_timeline(report)

        # 8. Projected status snapshots
        self.render_snapshots(report)

        # 9. Quality gates
        self.render_gates(report)

        # 10. Summary
        self.render_summary(report)

    def render_preflight(self, report: DryRunReport) -> None:
        """Render pre-flight checks panel."""
        pf = report.preflight
        if not pf:
            return

        lines: list[Text] = []
        for check in pf.checks:
            line = Text()
            if check.passed:
                line.append("  \u2713 ", style="green")
            elif check.severity == "warning":
                line.append("  \u26a0 ", style="yellow")
            else:
                line.append("  \u2717 ", style="red")
            line.append(f"{check.name}: {check.message}")
            lines.append(line)

        content = Text("\n").join(lines) if lines else Text("  No checks run")
        console.print(Panel(content, title="[bold]Pre-flight[/bold]", title_align="left"))

    def render_validation(self, report: DryRunReport) -> None:
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
                line.append("  \u2713 ", style="green")
                line.append(label)
            else:
                # Missing verifications are warnings, others are errors
                is_warning = label == "Verifications"
                symbol = "\u26a0" if is_warning else "\u2717"
                style = "yellow" if is_warning else "red"
                line.append(f"  {symbol} ", style=style)
                line.append(f"{label} ({len(issues)} issue{'s' if len(issues) != 1 else ''})")
                for issue in issues:
                    detail = Text()
                    detail.append(f"    \u2192 {issue}", style="dim")
                    lines.append(line)
                    line = detail
            lines.append(line)

        content = Text("\n").join(lines) if lines else Text("  No checks run")
        console.print(Panel(content, title="[bold]Validation[/bold]", title_align="left"))

    def render_risk(self, report: DryRunReport) -> None:
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
            cp_line.append(" \u2192 ".join(risk.critical_path))
            lines.append(cp_line)

        # Risk factors
        for factor in risk.risk_factors:
            fl = Text()
            fl.append("  \u26a0 ", style="yellow")
            fl.append(factor)
            lines.append(fl)

        # High-risk tasks
        for tr in risk.high_risk_tasks:
            tl = Text()
            tl.append("  \u2717 ", style="red")
            tl.append(f"{tr.task_id}: score {tr.score:.2f}")
            if tr.factors:
                tl.append(f" ({', '.join(tr.factors)})", style="dim")
            lines.append(tl)

        content = Text("\n").join(lines)
        console.print(Panel(content, title="[bold]Risk Assessment[/bold]", title_align="left"))

    def render_levels(self, report: DryRunReport) -> None:
        """Render per-level task tables."""
        from zerg.assign import WorkerAssignment

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
                critical = "\u2b50 " if task.get("critical_path") else ""
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

    def render_worker_loads(self, report: DryRunReport) -> None:
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
            line.append("\u2588" * filled, style="cyan")
            line.append("\u2591" * (bar_width - filled), style="dim")
            line.append(f" {minutes}m ({task_count} tasks)")
            lines.append(line)

        content = Text("\n").join(lines)
        console.print(Panel(content, title="[bold]Worker Load Balance[/bold]", title_align="left"))

    def render_gantt(self, report: DryRunReport) -> None:
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

    def render_timeline(self, report: DryRunReport) -> None:
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

    def render_snapshots(self, report: DryRunReport) -> None:
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
                end_line.append(" \u2192 merging \u2192 next level", style="dim")
            lines.append(end_line)

            cumulative = end

        content = Text("\n").join(lines)
        console.print(Panel(content, title="[bold]Projected Snapshots[/bold]", title_align="left"))

    def render_gates(self, report: DryRunReport) -> None:
        """Render quality gates panel."""
        if not report.gate_results:
            return

        lines: list[Text] = []
        for gate in report.gate_results:
            line = Text()
            if gate.status == "passed":
                line.append("  \u2713 ", style="green")
            elif gate.status == "failed":
                line.append("  \u2717 ", style="red")
            elif gate.status == "not_run":
                line.append("  \u25cb ", style="dim")
            else:
                line.append("  ! ", style="yellow")

            req_str = " (required)" if gate.required else ""
            dur_str = f" [{gate.duration_ms}ms]" if gate.duration_ms is not None else ""
            line.append(f"{gate.name}{req_str}{dur_str}")
            lines.append(line)

        content = Text("\n").join(lines)
        console.print(Panel(content, title="[bold]Quality Gates[/bold]", title_align="left"))

    def render_summary(self, report: DryRunReport) -> None:
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
            msg = f"\u2717 {error_count} error(s), {warning_count} warning(s) \u2014 not ready to rush"
            console.print(f"[bold red]{msg}[/bold red]")
        elif warning_count > 0:
            msg = f"\u26a0 {warning_count} warning(s) \u2014 ready to rush (with warnings)"
            console.print(f"[bold yellow]{msg}[/bold yellow]")
        else:
            console.print("[bold green]\u2713 All checks passed \u2014 ready to rush[/bold green]")
        console.print()
