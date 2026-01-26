"""Tests for ZERG v2 Spawn Command."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSpawnStrategy:
    """Tests for SpawnStrategy enum."""

    def test_strategies_exist(self):
        """Test spawn strategies are defined."""
        from spawn import SpawnStrategy

        assert hasattr(SpawnStrategy, "CONSERVATIVE")
        assert hasattr(SpawnStrategy, "BALANCED")
        assert hasattr(SpawnStrategy, "AGGRESSIVE")


class TestSpawnConfig:
    """Tests for SpawnConfig dataclass."""

    def test_config_defaults(self):
        """Test SpawnConfig default values."""
        from spawn import SpawnConfig

        config = SpawnConfig()
        assert config.strategy == "balanced"
        assert config.max_depth == 3
        assert config.validate_only is False

    def test_config_custom(self):
        """Test SpawnConfig with custom values."""
        from spawn import SpawnConfig

        config = SpawnConfig(strategy="conservative", max_depth=2)
        assert config.strategy == "conservative"
        assert config.max_depth == 2


class TestSubGoal:
    """Tests for SubGoal dataclass."""

    def test_subgoal_creation(self):
        """Test SubGoal can be created."""
        from spawn import SubGoal

        sg = SubGoal(id="SG-1", description="Setup infrastructure")
        assert sg.id == "SG-1"
        assert sg.description == "Setup infrastructure"

    def test_subgoal_to_dict(self):
        """Test SubGoal serialization."""
        from spawn import SubGoal

        sg = SubGoal(id="SG-2", description="Implement feature", level=1)
        data = sg.to_dict()
        assert data["id"] == "SG-2"
        assert data["level"] == 1


class TestGoalAnalysis:
    """Tests for GoalAnalysis dataclass."""

    def test_analysis_creation(self):
        """Test GoalAnalysis can be created."""
        from spawn import GoalAnalysis

        analysis = GoalAnalysis(
            goal="Add authentication",
            complexity="medium",
            domain="auth",
            estimated_sub_goals=5,
        )
        assert analysis.goal == "Add authentication"
        assert analysis.domain == "auth"

    def test_analysis_to_dict(self):
        """Test GoalAnalysis serialization."""
        from spawn import GoalAnalysis

        analysis = GoalAnalysis(
            goal="Test", complexity="low", domain="general", estimated_sub_goals=3
        )
        data = analysis.to_dict()
        assert data["complexity"] == "low"


class TestSpawnResult:
    """Tests for SpawnResult dataclass."""

    def test_result_creation(self):
        """Test SpawnResult can be created."""
        from spawn import GoalAnalysis, SpawnResult

        analysis = GoalAnalysis(
            goal="Test", complexity="low", domain="general", estimated_sub_goals=2
        )
        result = SpawnResult(
            goal="Test",
            analysis=analysis,
            sub_goals=[],
            task_count=5,
            level_count=2,
        )
        assert result.goal == "Test"
        assert result.task_count == 5

    def test_result_to_markdown(self):
        """Test SpawnResult markdown output."""
        from spawn import GoalAnalysis, SpawnResult, SubGoal

        analysis = GoalAnalysis(
            goal="Feature", complexity="medium", domain="api", estimated_sub_goals=3
        )
        sub_goals = [SubGoal(id="SG-1", description="Setup", tasks=[])]
        result = SpawnResult(
            goal="Feature",
            analysis=analysis,
            sub_goals=sub_goals,
            task_count=3,
            level_count=1,
        )
        md = result.to_markdown()
        assert "# Goal Decomposition: Feature" in md
        assert "Analysis" in md


class TestGoalAnalyzer:
    """Tests for GoalAnalyzer."""

    def test_analyzer_creation(self):
        """Test GoalAnalyzer can be created."""
        from spawn import GoalAnalyzer

        analyzer = GoalAnalyzer()
        assert analyzer is not None

    def test_analyze_auth_goal(self):
        """Test analyzing authentication goal."""
        from spawn import GoalAnalyzer

        analyzer = GoalAnalyzer()
        result = analyzer.analyze("Add JWT authentication with OAuth2")
        assert result.domain == "auth"

    def test_analyze_api_goal(self):
        """Test analyzing API goal."""
        from spawn import GoalAnalyzer

        analyzer = GoalAnalyzer()
        result = analyzer.analyze("Create REST API endpoints for users")
        assert result.domain == "api"


class TestTaskDecomposer:
    """Tests for TaskDecomposer."""

    def test_decomposer_creation(self):
        """Test TaskDecomposer can be created."""
        from spawn import TaskDecomposer

        decomposer = TaskDecomposer()
        assert decomposer is not None

    def test_decompose_returns_subgoals(self):
        """Test decomposition returns sub-goals."""
        from spawn import GoalAnalysis, TaskDecomposer

        decomposer = TaskDecomposer()
        analysis = GoalAnalysis(
            goal="Feature", complexity="medium", domain="api", estimated_sub_goals=3
        )
        sub_goals = decomposer.decompose(analysis)
        assert len(sub_goals) > 0


class TestGraphValidator:
    """Tests for GraphValidator."""

    def test_validator_creation(self):
        """Test GraphValidator can be created."""
        from spawn import GraphValidator

        validator = GraphValidator()
        assert validator is not None

    def test_validate_empty_fails(self):
        """Test empty sub-goals fails validation."""
        from spawn import GraphValidator

        validator = GraphValidator()
        valid, errors = validator.validate([])
        assert valid is False
        assert len(errors) > 0

    def test_validate_with_tasks_passes(self):
        """Test sub-goals with tasks passes."""
        from spawn import GraphValidator, SubGoal

        validator = GraphValidator()
        sub_goals = [
            SubGoal(
                id="SG-1", description="Test", tasks=[{"id": "T1", "title": "Task"}]
            )
        ]
        valid, errors = validator.validate(sub_goals)
        assert valid is True


class TestSpawnCommand:
    """Tests for SpawnCommand."""

    def test_command_creation(self):
        """Test SpawnCommand can be created."""
        from spawn import SpawnCommand

        cmd = SpawnCommand()
        assert cmd is not None

    def test_command_run(self):
        """Test running spawn."""
        from spawn import SpawnCommand, SpawnResult

        cmd = SpawnCommand()
        result = cmd.run(goal="Add user authentication")
        assert isinstance(result, SpawnResult)
        assert result.goal == "Add user authentication"

    def test_command_run_conservative(self):
        """Test running with conservative strategy."""
        from spawn import SpawnCommand

        cmd = SpawnCommand()
        result = cmd.run(goal="Small feature", strategy="conservative")
        assert result.validated is True

    def test_command_format_text(self):
        """Test text output formatting."""
        from spawn import GoalAnalysis, SpawnCommand, SpawnResult

        cmd = SpawnCommand()
        analysis = GoalAnalysis(
            goal="Test", complexity="low", domain="general", estimated_sub_goals=2
        )
        result = SpawnResult(
            goal="Test",
            analysis=analysis,
            sub_goals=[],
            task_count=0,
            level_count=0,
        )
        output = cmd.format_result(result, format="text")
        assert "Spawn Result" in output
        assert "Test" in output
