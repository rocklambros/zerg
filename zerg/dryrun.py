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

from zerg.assign import WorkerAssignment
from zerg.config import ZergConfig
from zerg.gates import GateRunner
from zerg.preflight import PreflightChecker, PreflightReport
from zerg.rendering.dryrun_renderer import DryRunRenderer
from zerg.risk_scoring import RiskReport, RiskScorer
from zerg.validation import (
    validate_dependencies,
    validate_file_ownership,
)

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

        renderer = DryRunRenderer()
        renderer.render(report)
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
            pass  # Best-effort disk usage check

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
