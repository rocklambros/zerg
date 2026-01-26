"""ZERG v2 Spawn Command - Meta-orchestration with adaptive task decomposition."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SpawnStrategy(Enum):
    """Task decomposition strategies."""

    CONSERVATIVE = "conservative"  # Small tasks (5-15 min)
    BALANCED = "balanced"  # Medium tasks (15-30 min)
    AGGRESSIVE = "aggressive"  # Large tasks (30-60 min)


@dataclass
class SpawnConfig:
    """Configuration for spawn operations."""

    strategy: str = "balanced"
    max_depth: int = 3
    validate_only: bool = False
    auto_execute: bool = False


@dataclass
class SubGoal:
    """A decomposed sub-goal."""

    id: str
    description: str
    tasks: list[dict] = field(default_factory=list)
    level: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "description": self.description,
            "tasks": self.tasks,
            "level": self.level,
        }


@dataclass
class GoalAnalysis:
    """Analysis of a high-level goal."""

    goal: str
    complexity: str  # low, medium, high
    domain: str  # auth, api, ui, data, etc.
    estimated_sub_goals: int
    key_entities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "goal": self.goal,
            "complexity": self.complexity,
            "domain": self.domain,
            "estimated_sub_goals": self.estimated_sub_goals,
            "key_entities": self.key_entities,
        }


@dataclass
class SpawnResult:
    """Result of spawn operation."""

    goal: str
    analysis: GoalAnalysis
    sub_goals: list[SubGoal]
    task_count: int
    level_count: int
    validated: bool = True
    errors: list[str] = field(default_factory=list)
    spawned_at: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "goal": self.goal,
            "analysis": self.analysis.to_dict(),
            "sub_goals": [sg.to_dict() for sg in self.sub_goals],
            "task_count": self.task_count,
            "level_count": self.level_count,
            "validated": self.validated,
            "errors": self.errors,
            "spawned_at": self.spawned_at,
        }

    def to_markdown(self) -> str:
        """Generate markdown breakdown."""
        lines = [
            f"# Goal Decomposition: {self.goal}",
            "",
            "## Analysis",
            f"- Complexity: {self.analysis.complexity}",
            f"- Domain: {self.analysis.domain}",
            f"- Key entities: {', '.join(self.analysis.key_entities)}",
            "",
            "## Breakdown",
        ]

        for sg in self.sub_goals:
            lines.append(f"\n### {sg.id}: {sg.description}")
            for task in sg.tasks:
                lines.append(f"  - {task.get('id', 'TASK')}: {task.get('title', 'Task')}")

        lines.extend([
            "",
            "## Summary",
            f"- Total tasks: {self.task_count}",
            f"- Levels: {self.level_count}",
            f"- Validated: {'Yes' if self.validated else 'No'}",
        ])

        if self.errors:
            lines.extend(["", "## Errors"])
            for error in self.errors:
                lines.append(f"- {error}")

        return "\n".join(lines)


class GoalAnalyzer:
    """Analyze high-level goals."""

    DOMAIN_KEYWORDS = {
        "auth": ["auth", "login", "oauth", "jwt", "session", "password"],
        "api": ["api", "endpoint", "rest", "graphql", "route"],
        "ui": ["ui", "component", "form", "button", "page", "view"],
        "data": ["data", "database", "model", "schema", "migration"],
        "test": ["test", "spec", "coverage", "e2e", "integration"],
    }

    def analyze(self, goal: str) -> GoalAnalysis:
        """Analyze a goal statement."""
        goal_lower = goal.lower()

        # Detect domain
        domain = "general"
        for d, keywords in self.DOMAIN_KEYWORDS.items():
            if any(kw in goal_lower for kw in keywords):
                domain = d
                break

        # Estimate complexity
        word_count = len(goal.split())
        if word_count < 10:
            complexity = "low"
        elif word_count < 25:
            complexity = "medium"
        else:
            complexity = "high"

        # Extract key entities (nouns)
        entities = self._extract_entities(goal)

        # Estimate sub-goals
        estimated = max(3, min(10, word_count // 5))

        return GoalAnalysis(
            goal=goal,
            complexity=complexity,
            domain=domain,
            estimated_sub_goals=estimated,
            key_entities=entities,
        )

    def _extract_entities(self, goal: str) -> list[str]:
        """Extract key entities from goal."""
        # Simple extraction - in practice would use NLP
        words = goal.split()
        entities = []
        for word in words:
            # Filter common words
            if len(word) > 3 and word[0].isupper():
                entities.append(word)
        return entities[:5]


class TaskDecomposer:
    """Decompose goals into tasks."""

    STRATEGY_SIZES = {
        "conservative": (5, 15),  # min, max minutes
        "balanced": (15, 30),
        "aggressive": (30, 60),
    }

    def decompose(
        self,
        analysis: GoalAnalysis,
        strategy: str = "balanced",
        max_depth: int = 3,
    ) -> list[SubGoal]:
        """Decompose goal into sub-goals and tasks."""
        sub_goals = []

        # Create infrastructure sub-goal
        sub_goals.append(SubGoal(
            id="SG-1",
            description=f"{analysis.domain.title()} infrastructure",
            level=0,
            tasks=self._generate_tasks("SG-1", 3, 0),
        ))

        # Create domain-specific sub-goals
        for i, entity in enumerate(analysis.key_entities[:3], 2):
            sub_goals.append(SubGoal(
                id=f"SG-{i}",
                description=f"{entity} implementation",
                level=1,
                tasks=self._generate_tasks(f"SG-{i}", 3, 1),
            ))

        # Create integration sub-goal
        sub_goals.append(SubGoal(
            id=f"SG-{len(sub_goals) + 1}",
            description="Integration and testing",
            level=2,
            tasks=self._generate_tasks(f"SG-{len(sub_goals) + 1}", 3, 2),
        ))

        return sub_goals

    def _generate_tasks(self, prefix: str, count: int, level: int) -> list[dict]:
        """Generate task stubs."""
        return [
            {
                "id": f"{prefix}-TASK-{i:03d}",
                "title": f"Task {i} for {prefix}",
                "level": level,
            }
            for i in range(1, count + 1)
        ]


class GraphValidator:
    """Validate decomposed task graphs."""

    def validate(self, sub_goals: list[SubGoal]) -> tuple[bool, list[str]]:
        """Validate the task graph."""
        errors = []

        if not sub_goals:
            errors.append("No sub-goals generated")
            return False, errors

        # Check for cycles (simplified)
        levels = [sg.level for sg in sub_goals]
        if max(levels) > 10:
            errors.append("Too many levels detected")

        # Check task count
        total_tasks = sum(len(sg.tasks) for sg in sub_goals)
        if total_tasks > 100:
            errors.append("Too many tasks generated")

        # Check for empty sub-goals
        for sg in sub_goals:
            if not sg.tasks:
                errors.append(f"Sub-goal {sg.id} has no tasks")

        return len(errors) == 0, errors


class SpawnCommand:
    """Main spawn command orchestrator."""

    def __init__(self, config: SpawnConfig | None = None):
        """Initialize spawn command."""
        self.config = config or SpawnConfig()
        self.analyzer = GoalAnalyzer()
        self.decomposer = TaskDecomposer()
        self.validator = GraphValidator()

    def run(
        self,
        goal: str,
        strategy: str = "balanced",
        max_depth: int = 3,
        validate_only: bool = False,
    ) -> SpawnResult:
        """Run spawn operation."""
        # Analyze the goal
        analysis = self.analyzer.analyze(goal)

        # Decompose into sub-goals
        sub_goals = self.decomposer.decompose(
            analysis, strategy=strategy, max_depth=max_depth
        )

        # Validate
        valid, errors = self.validator.validate(sub_goals)

        # Calculate metrics
        task_count = sum(len(sg.tasks) for sg in sub_goals)
        level_count = len({sg.level for sg in sub_goals})

        return SpawnResult(
            goal=goal,
            analysis=analysis,
            sub_goals=sub_goals,
            task_count=task_count,
            level_count=level_count,
            validated=valid,
            errors=errors,
            spawned_at=datetime.now().isoformat(),
        )

    def format_result(self, result: SpawnResult, format: str = "text") -> str:
        """Format spawn result."""
        if format == "json":
            return json.dumps(result.to_dict(), indent=2)

        if format == "markdown":
            return result.to_markdown()

        lines = [
            "Spawn Result",
            "=" * 40,
            f"Goal: {result.goal}",
            f"Complexity: {result.analysis.complexity}",
            f"Domain: {result.analysis.domain}",
            "",
            "Sub-Goals:",
        ]

        for sg in result.sub_goals:
            lines.append(f"  {sg.id}: {sg.description} ({len(sg.tasks)} tasks)")

        lines.extend([
            "",
            f"Total Tasks: {result.task_count}",
            f"Levels: {result.level_count}",
            f"Validated: {'Yes' if result.validated else 'No'}",
        ])

        return "\n".join(lines)


__all__ = [
    "SpawnStrategy",
    "SpawnConfig",
    "SubGoal",
    "GoalAnalysis",
    "SpawnResult",
    "GoalAnalyzer",
    "TaskDecomposer",
    "GraphValidator",
    "SpawnCommand",
]
