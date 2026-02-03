"""Risk scoring for ZERG task graphs.

Assesses per-task risk, identifies critical paths, and computes
an overall risk grade for a planned rush execution.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from zerg.logging import get_logger

logger = get_logger("risk_scoring")

# Risk grade thresholds (lower score = less risk)
GRADE_THRESHOLDS = {
    "A": 0.25,
    "B": 0.50,
    "C": 0.75,
    # D = anything above 0.75
}


@dataclass
class TaskRisk:
    """Risk assessment for a single task."""

    task_id: str
    score: float  # 0.0 (low) to 1.0 (high)
    factors: list[str] = field(default_factory=list)
    on_critical_path: bool = False


@dataclass
class RiskReport:
    """Aggregate risk report for a task graph."""

    task_risks: list[TaskRisk] = field(default_factory=list)
    critical_path: list[str] = field(default_factory=list)
    overall_score: float = 0.0
    grade: str = "A"
    risk_factors: list[str] = field(default_factory=list)

    @property
    def high_risk_tasks(self) -> list[TaskRisk]:
        return [t for t in self.task_risks if t.score >= 0.7]


class RiskScorer:
    """Compute risk scores for a ZERG task graph."""

    def __init__(self, task_data: dict[str, Any], worker_count: int = 5) -> None:
        self.task_data = task_data
        self.worker_count = worker_count
        self.tasks = task_data.get("tasks", [])
        self._task_map: dict[str, dict[str, Any]] = {t["id"]: t for t in self.tasks if "id" in t}

    def score(self) -> RiskReport:
        """Compute risk for the entire task graph."""
        report = RiskReport()

        # Per-task risk
        for task in self.tasks:
            risk = self._score_task(task)
            report.task_risks.append(risk)

        # Critical path
        report.critical_path = self._find_critical_path()
        for tr in report.task_risks:
            if tr.task_id in report.critical_path:
                tr.on_critical_path = True

        # Overall risk factors
        report.risk_factors = self._identify_risk_factors()

        # Overall score = weighted average of task scores
        if report.task_risks:
            # Weight critical-path tasks higher
            total_weight = 0.0
            weighted_sum = 0.0
            for tr in report.task_risks:
                weight = 2.0 if tr.on_critical_path else 1.0
                weighted_sum += tr.score * weight
                total_weight += weight
            report.overall_score = weighted_sum / total_weight if total_weight > 0 else 0.0
        else:
            report.overall_score = 0.0

        # Risk factor contributions
        factor_count = len(report.risk_factors)
        if factor_count > 0:
            report.overall_score = min(1.0, report.overall_score + factor_count * 0.05)

        # Grade
        report.grade = self._compute_grade(report.overall_score)

        return report

    def _score_task(self, task: dict[str, Any]) -> TaskRisk:
        """Score risk for a single task."""
        task_id = task.get("id", "unknown")
        factors: list[str] = []
        score = 0.0

        # Factor: file count
        files = task.get("files", {})
        file_count = len(files.get("create", [])) + len(files.get("modify", []))
        if file_count > 5:
            score += 0.2
            factors.append(f"High file count ({file_count})")
        elif file_count > 3:
            score += 0.1
            factors.append(f"Moderate file count ({file_count})")

        # Factor: no verification
        verification = task.get("verification")
        if not verification or not verification.get("command"):
            score += 0.25
            factors.append("No verification command")

        # Factor: dependency depth
        dep_depth = self._dependency_depth(task_id)
        if dep_depth > 3:
            score += 0.15
            factors.append(f"Deep dependency chain ({dep_depth})")
        elif dep_depth > 1:
            score += 0.05

        # Factor: high estimate
        estimate = task.get("estimate_minutes", 15)
        if estimate > 30:
            score += 0.15
            factors.append(f"Long estimate ({estimate}m)")
        elif estimate > 20:
            score += 0.05

        # Factor: many dependencies
        deps = task.get("dependencies", [])
        if len(deps) > 3:
            score += 0.1
            factors.append(f"Many dependencies ({len(deps)})")

        return TaskRisk(
            task_id=task_id,
            score=min(1.0, score),
            factors=factors,
        )

    def _dependency_depth(self, task_id: str, visited: set[str] | None = None) -> int:
        """Compute the maximum dependency depth for a task."""
        if visited is None:
            visited = set()
        if task_id in visited:
            return 0  # cycle protection
        visited.add(task_id)

        task = self._task_map.get(task_id)
        if not task:
            return 0

        deps = task.get("dependencies", [])
        if not deps:
            return 0

        return 1 + max(self._dependency_depth(d, visited.copy()) for d in deps)

    def _find_critical_path(self) -> list[str]:
        """Find the longest path through the dependency graph by estimated time."""
        # Build adjacency: task -> list of tasks that depend on it
        dependents: dict[str, list[str]] = defaultdict(list)
        for task in self.tasks:
            for dep in task.get("dependencies", []):
                dependents[dep].append(task["id"])

        # Find roots (no dependencies)
        roots = [t["id"] for t in self.tasks if not t.get("dependencies")]

        # DFS to find longest path by cumulative estimate
        best_path: list[str] = []
        best_cost = 0

        def dfs(node: str, path: list[str], cost: int) -> None:
            nonlocal best_path, best_cost
            task = self._task_map.get(node)
            node_cost = task.get("estimate_minutes", 15) if task else 15
            new_cost = cost + node_cost
            new_path = path + [node]

            children = dependents.get(node, [])
            if not children:
                if new_cost > best_cost:
                    best_cost = new_cost
                    best_path = new_path
            else:
                for child in children:
                    dfs(child, new_path, new_cost)

        for root in roots:
            dfs(root, [], 0)

        return best_path

    def _identify_risk_factors(self) -> list[str]:
        """Identify graph-level risk factors."""
        factors: list[str] = []

        # Factor: cross-level file edits
        level_files: dict[int, set[str]] = defaultdict(set)
        for task in self.tasks:
            level = task.get("level", 1)
            files = task.get("files", {})
            for f in files.get("modify", []):
                level_files[level].add(f)

        for l1 in level_files:
            for l2 in level_files:
                if l1 < l2:
                    overlap = level_files[l1] & level_files[l2]
                    if overlap:
                        factors.append(f"Files modified in both L{l1} and L{l2}: {', '.join(sorted(overlap))}")

        # Factor: missing verifications
        no_verify = sum(
            1 for t in self.tasks if not t.get("verification") or not t.get("verification", {}).get("command")
        )
        if no_verify > 0:
            factors.append(f"{no_verify} task(s) missing verification commands")

        # Factor: high task count per worker
        tasks_per_worker = len(self.tasks) / max(self.worker_count, 1)
        if tasks_per_worker > 5:
            factors.append(f"High task density: {tasks_per_worker:.1f} tasks/worker")

        # Factor: unbalanced levels
        level_counts: dict[int, int] = defaultdict(int)
        for task in self.tasks:
            level_counts[task.get("level", 1)] += 1
        if level_counts:
            max_tasks = max(level_counts.values())
            min_tasks = min(level_counts.values())
            if max_tasks > 3 * min_tasks and min_tasks > 0:
                factors.append(f"Unbalanced levels: {min_tasks}-{max_tasks} tasks per level")

        return factors

    @staticmethod
    def _compute_grade(score: float) -> str:
        """Convert numeric score to letter grade."""
        for grade, threshold in sorted(GRADE_THRESHOLDS.items()):
            if score <= threshold:
                return grade
        return "D"
