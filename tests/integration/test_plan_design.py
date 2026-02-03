"""Integration tests for ZERG plan→design workflow."""

import json
from pathlib import Path

from click.testing import CliRunner

from zerg.cli import cli


class TestPlanCommand:
    """Tests for plan command."""

    def test_plan_creates_requirements(self, tmp_path: Path, monkeypatch) -> None:
        """Test plan command creates requirements.md in spec directory."""
        monkeypatch.chdir(tmp_path)

        # Create .gsd directory
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)

        runner = CliRunner()
        result = runner.invoke(cli, ["plan", "test-feature", "--no-interactive", "--template", "minimal"])

        assert result.exit_code == 0
        assert "✓" in result.output

        # Check files created
        requirements = tmp_path / ".gsd" / "specs" / "test-feature" / "requirements.md"
        assert requirements.exists()

        content = requirements.read_text()
        assert "test-feature" in content
        assert "Status" in content

    def test_plan_sanitizes_feature_name(self, tmp_path: Path, monkeypatch) -> None:
        """Test plan command sanitizes feature names."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)

        runner = CliRunner()
        result = runner.invoke(cli, ["plan", "My Feature Name", "--no-interactive"])

        assert result.exit_code == 0

        # Should be lowercased with hyphens
        spec_dir = tmp_path / ".gsd" / "specs" / "my-feature-name"
        assert spec_dir.exists()

    def test_plan_sets_current_feature(self, tmp_path: Path, monkeypatch) -> None:
        """Test plan command sets .current-feature file."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)

        runner = CliRunner()
        result = runner.invoke(cli, ["plan", "user-auth", "--no-interactive"])

        assert result.exit_code == 0

        current = tmp_path / ".gsd" / ".current-feature"
        assert current.exists()
        assert current.read_text().strip() == "user-auth"

    def test_plan_different_templates(self, tmp_path: Path, monkeypatch) -> None:
        """Test plan command with different templates."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)

        runner = CliRunner()

        # Minimal template
        result = runner.invoke(cli, ["plan", "min-feat", "--no-interactive", "--template", "minimal"])
        assert result.exit_code == 0
        req_path = tmp_path / ".gsd" / "specs" / "min-feat" / "requirements.md"
        content = req_path.read_text()
        assert "Problem Statement" in content

        # Detailed template
        (tmp_path / ".gsd" / "specs" / "detail-feat").mkdir(parents=True, exist_ok=True)
        result = runner.invoke(cli, ["plan", "detail-feat", "--no-interactive", "--template", "detailed"])
        assert result.exit_code == 0
        req_path = tmp_path / ".gsd" / "specs" / "detail-feat" / "requirements.md"
        content = req_path.read_text()
        assert "Risk Assessment" in content


class TestDesignCommand:
    """Tests for design command."""

    def test_design_requires_feature(self, tmp_path: Path, monkeypatch) -> None:
        """Test design command requires active feature or --feature flag."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["design"])

        assert result.exit_code == 1
        assert "No active feature" in result.output

    def test_design_requires_requirements(self, tmp_path: Path, monkeypatch) -> None:
        """Test design command requires requirements.md."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs" / "test-feature").mkdir(parents=True)
        (tmp_path / ".gsd" / ".current-feature").write_text("test-feature")

        runner = CliRunner()
        result = runner.invoke(cli, ["design"])

        assert result.exit_code == 1
        assert "Requirements not found" in result.output

    def test_design_creates_artifacts(self, tmp_path: Path, monkeypatch) -> None:
        """Test design command creates design.md and task-graph.json."""
        monkeypatch.chdir(tmp_path)
        spec_dir = tmp_path / ".gsd" / "specs" / "test-feature"
        spec_dir.mkdir(parents=True)
        (tmp_path / ".gsd" / ".current-feature").write_text("test-feature")

        # Create approved requirements
        (spec_dir / "requirements.md").write_text("""# Requirements
- **Status**: APPROVED
- **Feature**: test-feature
""")

        runner = CliRunner()
        result = runner.invoke(cli, ["design"])

        assert result.exit_code == 0

        # Check artifacts created
        assert (spec_dir / "design.md").exists()
        assert (spec_dir / "task-graph.json").exists()

        # Validate task graph structure
        with open(spec_dir / "task-graph.json") as f:
            task_graph = json.load(f)

        assert "tasks" in task_graph
        assert "version" in task_graph
        assert task_graph["version"] == "2.0"

    def test_design_validate_only(self, tmp_path: Path, monkeypatch) -> None:
        """Test design --validate-only validates existing task graph."""
        monkeypatch.chdir(tmp_path)
        spec_dir = tmp_path / ".gsd" / "specs" / "test-feature"
        spec_dir.mkdir(parents=True)
        (tmp_path / ".gsd" / ".current-feature").write_text("test-feature")

        # Create requirements
        (spec_dir / "requirements.md").write_text("- **Status**: APPROVED")

        # Create valid task graph
        task_graph = {
            "version": "2.0",
            "tasks": [
                {
                    "id": "TEST-L1-001",
                    "title": "Test task",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": [], "modify": [], "read": []},
                }
            ],
            "levels": {"1": {"name": "test", "tasks": ["TEST-L1-001"]}},
        }
        with open(spec_dir / "task-graph.json", "w") as f:
            json.dump(task_graph, f)

        runner = CliRunner()
        result = runner.invoke(cli, ["design", "--validate-only"])

        assert result.exit_code == 0
        assert "valid" in result.output.lower()


class TestPlanDesignFlow:
    """Tests for the complete plan→design workflow."""

    def test_full_flow(self, tmp_path: Path, monkeypatch) -> None:
        """Test complete plan→design workflow."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)

        runner = CliRunner()

        # Step 1: Create plan
        result = runner.invoke(cli, ["plan", "user-auth", "--no-interactive"])
        assert result.exit_code == 0

        # Step 2: Approve requirements (simulate)
        req_path = tmp_path / ".gsd" / "specs" / "user-auth" / "requirements.md"
        content = req_path.read_text().replace("DRAFT", "APPROVED")
        req_path.write_text(content)

        # Step 3: Generate design
        result = runner.invoke(cli, ["design"])
        assert result.exit_code == 0

        # Step 4: Validate
        result = runner.invoke(cli, ["design", "--validate-only"])
        assert result.exit_code == 0

        # Verify all artifacts exist
        spec_dir = tmp_path / ".gsd" / "specs" / "user-auth"
        assert (spec_dir / "requirements.md").exists()
        assert (spec_dir / "design.md").exists()
        assert (spec_dir / "task-graph.json").exists()
        assert (spec_dir / ".started").exists()

    def test_flow_respects_feature_flag(self, tmp_path: Path, monkeypatch) -> None:
        """Test design --feature flag overrides current feature."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)

        runner = CliRunner()

        # Create two features
        runner.invoke(cli, ["plan", "feature-a", "--no-interactive"])
        runner.invoke(cli, ["plan", "feature-b", "--no-interactive"])

        # Approve feature-a
        req_a = tmp_path / ".gsd" / "specs" / "feature-a" / "requirements.md"
        content = req_a.read_text().replace("DRAFT", "APPROVED")
        req_a.write_text(content)

        # Design with explicit feature flag (current is feature-b)
        result = runner.invoke(cli, ["design", "--feature", "feature-a"])
        assert result.exit_code == 0

        # Only feature-a should have design artifacts
        assert (tmp_path / ".gsd" / "specs" / "feature-a" / "design.md").exists()


class TestTaskGraphValidation:
    """Tests for task graph validation."""

    def test_validates_circular_dependencies(self, tmp_path: Path, monkeypatch) -> None:
        """Test validation detects circular dependencies."""
        monkeypatch.chdir(tmp_path)
        spec_dir = tmp_path / ".gsd" / "specs" / "test"
        spec_dir.mkdir(parents=True)
        (tmp_path / ".gsd" / ".current-feature").write_text("test")
        (spec_dir / "requirements.md").write_text("- **Status**: APPROVED")

        # Create task graph with self-reference
        task_graph = {
            "version": "2.0",
            "tasks": [
                {
                    "id": "TEST-001",
                    "title": "Self ref",
                    "level": 1,
                    "dependencies": ["TEST-001"],
                    "files": {"create": [], "modify": [], "read": []},
                }
            ],
        }
        with open(spec_dir / "task-graph.json", "w") as f:
            json.dump(task_graph, f)

        runner = CliRunner()
        result = runner.invoke(cli, ["design", "--validate-only"])

        assert result.exit_code == 1
        assert "self-reference" in result.output.lower()

    def test_validates_missing_dependencies(self, tmp_path: Path, monkeypatch) -> None:
        """Test validation detects missing dependencies."""
        monkeypatch.chdir(tmp_path)
        spec_dir = tmp_path / ".gsd" / "specs" / "test"
        spec_dir.mkdir(parents=True)
        (tmp_path / ".gsd" / ".current-feature").write_text("test")
        (spec_dir / "requirements.md").write_text("- **Status**: APPROVED")

        # Create task graph with unknown dependency
        task_graph = {
            "version": "2.0",
            "tasks": [
                {
                    "id": "TEST-001",
                    "title": "Missing dep",
                    "level": 1,
                    "dependencies": ["NONEXISTENT"],
                    "files": {"create": [], "modify": [], "read": []},
                }
            ],
        }
        with open(spec_dir / "task-graph.json", "w") as f:
            json.dump(task_graph, f)

        runner = CliRunner()
        result = runner.invoke(cli, ["design", "--validate-only"])

        assert result.exit_code == 1
        assert "unknown dependency" in result.output.lower()

    def test_validates_file_ownership_conflicts(self, tmp_path: Path, monkeypatch) -> None:
        """Test validation detects file ownership conflicts."""
        monkeypatch.chdir(tmp_path)
        spec_dir = tmp_path / ".gsd" / "specs" / "test"
        spec_dir.mkdir(parents=True)
        (tmp_path / ".gsd" / ".current-feature").write_text("test")
        (spec_dir / "requirements.md").write_text("- **Status**: APPROVED")

        # Create task graph with file conflict
        task_graph = {
            "version": "2.0",
            "tasks": [
                {
                    "id": "TEST-001",
                    "title": "Task 1",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["src/shared.py"], "modify": [], "read": []},
                },
                {
                    "id": "TEST-002",
                    "title": "Task 2",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["src/shared.py"], "modify": [], "read": []},
                },
            ],
        }
        with open(spec_dir / "task-graph.json", "w") as f:
            json.dump(task_graph, f)

        runner = CliRunner()
        result = runner.invoke(cli, ["design", "--validate-only"])

        assert result.exit_code == 1
        assert "conflict" in result.output.lower()
