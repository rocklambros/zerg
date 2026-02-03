"""Comprehensive unit tests for charter.py - 100% coverage target."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from zerg.charter import ProjectCharter, gather_requirements, write_project_md


class TestProjectCharter:
    """Tests for ProjectCharter dataclass."""

    def test_default_values(self) -> None:
        """Test that ProjectCharter has sensible defaults."""
        charter = ProjectCharter()

        assert charter.name == ""
        assert charter.description == ""
        assert charter.purpose == ""
        assert charter.primary_language == ""
        assert charter.security_level == "standard"
        assert charter.ci_cd_needed is True
        assert charter.containerized is True
        assert charter.target_platforms == []
        assert charter.frameworks == []
        assert charter.data_storage == []
        assert charter.constraints == []
        assert charter.integrations == []
        assert charter.notes == ""

    def test_custom_values(self) -> None:
        """Test creating charter with custom values."""
        charter = ProjectCharter(
            name="my-project",
            description="A test project",
            primary_language="python",
            target_platforms=["api", "cli"],
            security_level="strict",
            purpose="Solve testing problems",
        )

        assert charter.name == "my-project"
        assert charter.description == "A test project"
        assert charter.primary_language == "python"
        assert charter.target_platforms == ["api", "cli"]
        assert charter.security_level == "strict"
        assert charter.purpose == "Solve testing problems"

    def test_all_fields(self) -> None:
        """Test creating charter with all fields populated."""
        charter = ProjectCharter(
            name="full-project",
            description="Full project",
            purpose="Test all fields",
            primary_language="rust",
            target_platforms=["api", "cli", "web"],
            frameworks=["actix", "tokio"],
            architecture_style="microservices",
            data_storage=["postgresql", "redis"],
            performance_needs="high",
            security_level="strict",
            scalability="enterprise",
            testing_strategy="comprehensive",
            ci_cd_needed=False,
            containerized=False,
            constraints=["Must run on ARM", "No cloud dependencies"],
            integrations=["Slack", "GitHub"],
            notes="This is a test project",
        )

        assert charter.name == "full-project"
        assert charter.frameworks == ["actix", "tokio"]
        assert charter.constraints == ["Must run on ARM", "No cloud dependencies"]
        assert charter.integrations == ["Slack", "GitHub"]

    def test_to_dict(self) -> None:
        """Test converting charter to dictionary."""
        charter = ProjectCharter(
            name="test-project",
            description="Test description",
            primary_language="go",
        )

        data = charter.to_dict()

        assert data["name"] == "test-project"
        assert data["description"] == "Test description"
        assert data["primary_language"] == "go"
        assert "created_at" in data
        assert "created_by" in data
        assert isinstance(data["created_at"], str)

    def test_to_dict_all_fields(self) -> None:
        """Test to_dict includes all fields."""
        charter = ProjectCharter(
            name="test",
            description="test",
            purpose="test purpose",
            primary_language="python",
            target_platforms=["api"],
            frameworks=["fastapi"],
            architecture_style="monolith",
            data_storage=["postgresql"],
            performance_needs="medium",
            security_level="standard",
            scalability="team",
            testing_strategy="standard",
            ci_cd_needed=True,
            containerized=True,
            constraints=["constraint1"],
            integrations=["integration1"],
            notes="notes here",
        )

        data = charter.to_dict()

        assert data["purpose"] == "test purpose"
        assert data["target_platforms"] == ["api"]
        assert data["frameworks"] == ["fastapi"]
        assert data["architecture_style"] == "monolith"
        assert data["data_storage"] == ["postgresql"]
        assert data["performance_needs"] == "medium"
        assert data["scalability"] == "team"
        assert data["testing_strategy"] == "standard"
        assert data["constraints"] == ["constraint1"]
        assert data["integrations"] == ["integration1"]
        assert data["notes"] == "notes here"

    def test_from_dict(self) -> None:
        """Test creating charter from dictionary."""
        data = {
            "name": "restored-project",
            "description": "Restored from dict",
            "primary_language": "rust",
            "target_platforms": ["cli"],
            "security_level": "minimal",
            "created_at": "2026-01-26T10:00:00",
        }

        charter = ProjectCharter.from_dict(data)

        assert charter.name == "restored-project"
        assert charter.primary_language == "rust"
        assert charter.target_platforms == ["cli"]
        assert charter.security_level == "minimal"

    def test_from_dict_with_datetime_object(self) -> None:
        """Test from_dict handles datetime object."""
        dt = datetime(2026, 1, 26, 10, 0, 0)
        data = {
            "name": "test",
            "created_at": dt,
        }

        charter = ProjectCharter.from_dict(data)

        assert charter.created_at == dt

    def test_from_dict_without_created_at(self) -> None:
        """Test from_dict handles missing created_at."""
        data = {
            "name": "test",
        }

        charter = ProjectCharter.from_dict(data)

        assert charter.created_at is not None
        assert isinstance(charter.created_at, datetime)

    def test_from_dict_handles_missing_fields(self) -> None:
        """Test that from_dict handles missing fields gracefully."""
        data = {"name": "minimal"}

        charter = ProjectCharter.from_dict(data)

        assert charter.name == "minimal"
        assert charter.description == ""
        assert charter.security_level == "standard"
        assert charter.ci_cd_needed is True
        assert charter.containerized is True

    def test_from_dict_all_fields(self) -> None:
        """Test from_dict with all fields."""
        data = {
            "name": "full",
            "description": "full project",
            "purpose": "test purpose",
            "primary_language": "go",
            "target_platforms": ["api", "cli"],
            "frameworks": ["gin"],
            "architecture_style": "microservices",
            "data_storage": ["mongodb"],
            "performance_needs": "high",
            "security_level": "strict",
            "scalability": "enterprise",
            "testing_strategy": "comprehensive",
            "ci_cd_needed": False,
            "containerized": False,
            "constraints": ["c1", "c2"],
            "integrations": ["i1", "i2"],
            "notes": "some notes",
            "created_at": "2026-01-26T12:00:00",
            "created_by": "test-user",
        }

        charter = ProjectCharter.from_dict(data)

        assert charter.purpose == "test purpose"
        assert charter.frameworks == ["gin"]
        assert charter.architecture_style == "microservices"
        assert charter.data_storage == ["mongodb"]
        assert charter.performance_needs == "high"
        assert charter.scalability == "enterprise"
        assert charter.testing_strategy == "comprehensive"
        assert charter.ci_cd_needed is False
        assert charter.containerized is False
        assert charter.constraints == ["c1", "c2"]
        assert charter.integrations == ["i1", "i2"]
        assert charter.notes == "some notes"
        assert charter.created_by == "test-user"

    def test_round_trip_serialization(self) -> None:
        """Test that to_dict/from_dict round-trips correctly."""
        original = ProjectCharter(
            name="round-trip",
            description="Testing serialization",
            primary_language="typescript",
            target_platforms=["web", "api"],
            frameworks=["nextjs"],
            data_storage=["postgresql", "redis"],
            security_level="strict",
            ci_cd_needed=False,
        )

        data = original.to_dict()
        restored = ProjectCharter.from_dict(data)

        assert restored.name == original.name
        assert restored.description == original.description
        assert restored.primary_language == original.primary_language
        assert restored.target_platforms == original.target_platforms
        assert restored.frameworks == original.frameworks
        assert restored.data_storage == original.data_storage
        assert restored.security_level == original.security_level
        assert restored.ci_cd_needed == original.ci_cd_needed


class TestGatherRequirements:
    """Tests for gather_requirements function."""

    @patch("zerg.charter.Prompt.ask")
    @patch("zerg.charter.Confirm.ask")
    def test_gather_requirements_returns_charter(self, mock_confirm: patch, mock_prompt: patch) -> None:
        """Test that gather_requirements returns a ProjectCharter."""
        mock_prompt.side_effect = [
            "test-project",  # name
            "A test project",  # description
            "Solve testing problems",  # purpose
            "api",  # platforms
            "monolith",  # architecture
            "postgresql",  # storage
            "medium",  # performance
            "standard",  # security
            "team",  # scalability
            "standard",  # testing
            "none",  # integrations
            "",  # notes
        ]
        mock_confirm.side_effect = [True, True]  # ci_cd, containerized

        charter = gather_requirements()

        assert isinstance(charter, ProjectCharter)
        assert charter.name == "test-project"
        assert charter.description == "A test project"

    @patch("zerg.charter.Prompt.ask")
    @patch("zerg.charter.Confirm.ask")
    def test_gather_requirements_handles_none_storage(self, mock_confirm: patch, mock_prompt: patch) -> None:
        """Test that 'none' storage is handled correctly."""
        mock_prompt.side_effect = [
            "no-db-project",
            "Project without database",
            "",
            "cli",
            "monolith",
            "none",  # no storage
            "low",
            "minimal",
            "single-user",
            "minimal",
            "none",
            "",
        ]
        mock_confirm.side_effect = [False, False]

        charter = gather_requirements()

        assert charter.data_storage == []

    @patch("zerg.charter.Prompt.ask")
    @patch("zerg.charter.Confirm.ask")
    def test_gather_requirements_with_storage(self, mock_confirm: patch, mock_prompt: patch) -> None:
        """Test storage parsing with actual databases."""
        mock_prompt.side_effect = [
            "db-project",
            "Project with database",
            "",
            "api",
            "monolith",
            "postgresql, redis",  # multiple storage
            "medium",
            "standard",
            "team",
            "standard",
            "none",
            "",
        ]
        mock_confirm.side_effect = [True, True]

        charter = gather_requirements()

        assert "postgresql" in charter.data_storage
        assert "redis" in charter.data_storage

    @patch("zerg.charter.Prompt.ask")
    @patch("zerg.charter.Confirm.ask")
    def test_gather_requirements_multiple_platforms(self, mock_confirm: patch, mock_prompt: patch) -> None:
        """Test multiple target platforms."""
        mock_prompt.side_effect = [
            "multi-platform",
            "Multi-platform project",
            "",
            "api, web, cli",  # multiple platforms
            "monolith",
            "none",
            "medium",
            "standard",
            "team",
            "standard",
            "none",
            "",
        ]
        mock_confirm.side_effect = [True, True]

        charter = gather_requirements()

        assert "api" in charter.target_platforms
        assert "web" in charter.target_platforms
        assert "cli" in charter.target_platforms

    @patch("zerg.charter.Prompt.ask")
    @patch("zerg.charter.Confirm.ask")
    def test_gather_requirements_with_integrations(self, mock_confirm: patch, mock_prompt: patch) -> None:
        """Test handling integrations."""
        mock_prompt.side_effect = [
            "integrated-project",
            "Project with integrations",
            "",
            "api",
            "monolith",
            "none",
            "medium",
            "standard",
            "team",
            "standard",
            "Slack, GitHub, Jira",  # integrations
            "",
        ]
        mock_confirm.side_effect = [True, True]

        charter = gather_requirements()

        assert "Slack" in charter.integrations
        assert "GitHub" in charter.integrations
        assert "Jira" in charter.integrations

    @patch("zerg.charter.Prompt.ask")
    @patch("zerg.charter.Confirm.ask")
    def test_gather_requirements_with_notes(self, mock_confirm: patch, mock_prompt: patch) -> None:
        """Test handling notes."""
        mock_prompt.side_effect = [
            "noted-project",
            "Project with notes",
            "",
            "api",
            "monolith",
            "none",
            "medium",
            "standard",
            "team",
            "standard",
            "none",
            "Important: This project must be fast",  # notes
        ]
        mock_confirm.side_effect = [True, True]

        charter = gather_requirements()

        assert charter.notes == "Important: This project must be fast"


class TestWriteProjectMd:
    """Tests for write_project_md function."""

    def test_creates_project_md(self, tmp_path: Path) -> None:
        """Test that PROJECT.md is created."""
        charter = ProjectCharter(
            name="test-project",
            description="A test project",
            primary_language="python",
        )

        result = write_project_md(charter, tmp_path)

        assert result.exists()
        assert result.name == "PROJECT.md"

    def test_project_md_contains_name(self, tmp_path: Path) -> None:
        """Test that PROJECT.md contains project name."""
        charter = ProjectCharter(
            name="my-awesome-project",
            description="An awesome project",
        )

        result = write_project_md(charter, tmp_path)
        content = result.read_text()

        assert "# my-awesome-project" in content

    def test_project_md_contains_description(self, tmp_path: Path) -> None:
        """Test that PROJECT.md contains description."""
        charter = ProjectCharter(
            name="test",
            description="This is a comprehensive test project",
        )

        result = write_project_md(charter, tmp_path)
        content = result.read_text()

        assert "This is a comprehensive test project" in content

    def test_project_md_contains_purpose(self, tmp_path: Path) -> None:
        """Test that PROJECT.md contains purpose/problem statement."""
        charter = ProjectCharter(
            name="test",
            description="Test",
            purpose="Solve the world hunger problem",
        )

        result = write_project_md(charter, tmp_path)
        content = result.read_text()

        assert "Problem Statement" in content
        assert "Solve the world hunger problem" in content

    def test_project_md_without_purpose(self, tmp_path: Path) -> None:
        """Test PROJECT.md without purpose section."""
        charter = ProjectCharter(
            name="test",
            description="Test",
            purpose="",  # Empty purpose
        )

        result = write_project_md(charter, tmp_path)
        content = result.read_text()

        assert "Problem Statement" not in content

    def test_project_md_contains_technical_specs(self, tmp_path: Path) -> None:
        """Test that PROJECT.md contains technical specifications."""
        charter = ProjectCharter(
            name="test",
            description="Test",
            primary_language="go",
            target_platforms=["api", "cli"],
            architecture_style="microservices",
        )

        result = write_project_md(charter, tmp_path)
        content = result.read_text()

        assert "Technical Specifications" in content
        assert "go" in content
        assert "api, cli" in content
        assert "microservices" in content

    def test_project_md_contains_frameworks(self, tmp_path: Path) -> None:
        """Test that PROJECT.md contains frameworks."""
        charter = ProjectCharter(
            name="test",
            description="Test",
            frameworks=["fastapi", "sqlalchemy"],
        )

        result = write_project_md(charter, tmp_path)
        content = result.read_text()

        assert "Frameworks" in content
        assert "fastapi, sqlalchemy" in content

    def test_project_md_without_frameworks(self, tmp_path: Path) -> None:
        """Test PROJECT.md without frameworks."""
        charter = ProjectCharter(
            name="test",
            description="Test",
            frameworks=[],
        )

        result = write_project_md(charter, tmp_path)
        content = result.read_text()

        # Should not have frameworks line
        assert "**Frameworks**:" not in content

    def test_project_md_contains_data_storage(self, tmp_path: Path) -> None:
        """Test that PROJECT.md contains data storage."""
        charter = ProjectCharter(
            name="test",
            description="Test",
            data_storage=["postgresql", "redis", "elasticsearch"],
        )

        result = write_project_md(charter, tmp_path)
        content = result.read_text()

        assert "Data Storage" in content
        assert "postgresql, redis, elasticsearch" in content

    def test_project_md_without_data_storage(self, tmp_path: Path) -> None:
        """Test PROJECT.md without data storage."""
        charter = ProjectCharter(
            name="test",
            description="Test",
            data_storage=[],
        )

        result = write_project_md(charter, tmp_path)
        content = result.read_text()

        assert "**Data Storage**:" not in content

    def test_project_md_contains_nfr(self, tmp_path: Path) -> None:
        """Test that PROJECT.md contains non-functional requirements."""
        charter = ProjectCharter(
            name="test",
            description="Test",
            security_level="strict",
            performance_needs="high",
            scalability="enterprise",
        )

        result = write_project_md(charter, tmp_path)
        content = result.read_text()

        assert "Non-Functional Requirements" in content
        assert "strict" in content
        assert "high" in content
        assert "enterprise" in content

    def test_project_md_contains_dev_config(self, tmp_path: Path) -> None:
        """Test that PROJECT.md contains development configuration."""
        charter = ProjectCharter(
            name="test",
            description="Test",
            testing_strategy="comprehensive",
            ci_cd_needed=True,
            containerized=True,
        )

        result = write_project_md(charter, tmp_path)
        content = result.read_text()

        assert "Development Configuration" in content
        assert "comprehensive" in content
        assert "CI/CD" in content
        assert "Containerized" in content

    def test_project_md_contains_integrations(self, tmp_path: Path) -> None:
        """Test that PROJECT.md contains external integrations."""
        charter = ProjectCharter(
            name="test",
            description="Test",
            integrations=["Slack", "GitHub", "Jira"],
        )

        result = write_project_md(charter, tmp_path)
        content = result.read_text()

        assert "External Integrations" in content
        assert "- Slack" in content
        assert "- GitHub" in content
        assert "- Jira" in content

    def test_project_md_without_integrations(self, tmp_path: Path) -> None:
        """Test PROJECT.md without integrations section."""
        charter = ProjectCharter(
            name="test",
            description="Test",
            integrations=[],
        )

        result = write_project_md(charter, tmp_path)
        content = result.read_text()

        assert "External Integrations" not in content

    def test_project_md_contains_constraints(self, tmp_path: Path) -> None:
        """Test that PROJECT.md contains constraints."""
        charter = ProjectCharter(
            name="test",
            description="Test",
            constraints=["Must run on ARM", "No cloud dependencies", "HIPAA compliant"],
        )

        result = write_project_md(charter, tmp_path)
        content = result.read_text()

        assert "Constraints" in content
        assert "- Must run on ARM" in content
        assert "- No cloud dependencies" in content
        assert "- HIPAA compliant" in content

    def test_project_md_without_constraints(self, tmp_path: Path) -> None:
        """Test PROJECT.md without constraints section."""
        charter = ProjectCharter(
            name="test",
            description="Test",
            constraints=[],
        )

        result = write_project_md(charter, tmp_path)
        content = result.read_text()

        # The word "Constraints" appears in "Non-Functional Requirements" context
        # so we check for the section specifically
        lines = content.split("\n")
        constraint_section_found = False
        for i, line in enumerate(lines):
            if line.strip() == "## Constraints":
                constraint_section_found = True
                break
        assert not constraint_section_found

    def test_project_md_contains_notes(self, tmp_path: Path) -> None:
        """Test that PROJECT.md contains additional notes."""
        charter = ProjectCharter(
            name="test",
            description="Test",
            notes="This project has special requirements for performance optimization.",
        )

        result = write_project_md(charter, tmp_path)
        content = result.read_text()

        assert "Additional Notes" in content
        assert "This project has special requirements" in content

    def test_project_md_without_notes(self, tmp_path: Path) -> None:
        """Test PROJECT.md without notes section."""
        charter = ProjectCharter(
            name="test",
            description="Test",
            notes="",
        )

        result = write_project_md(charter, tmp_path)
        content = result.read_text()

        assert "Additional Notes" not in content

    def test_project_md_contains_metadata(self, tmp_path: Path) -> None:
        """Test that PROJECT.md contains generation metadata."""
        charter = ProjectCharter(
            name="test",
            description="Test",
        )

        result = write_project_md(charter, tmp_path)
        content = result.read_text()

        assert "Generated by ZERG Inception Mode" in content

    def test_project_md_creates_gsd_dir(self, tmp_path: Path) -> None:
        """Test that .gsd directory is created if not exists."""
        output_dir = tmp_path / ".gsd"
        charter = ProjectCharter(name="test", description="Test")

        result = write_project_md(charter, output_dir)

        assert output_dir.exists()
        assert result.parent == output_dir

    def test_project_md_default_output_dir(self, tmp_path: Path, monkeypatch) -> None:
        """Test that default output dir is .gsd."""
        monkeypatch.chdir(tmp_path)
        charter = ProjectCharter(name="test", description="Test")

        result = write_project_md(charter)

        assert result.parent.name == ".gsd"

    def test_project_md_default_values(self, tmp_path: Path) -> None:
        """Test PROJECT.md with default values shows TBD appropriately."""
        charter = ProjectCharter(
            name="test",
            description="Test",
            primary_language="",  # Empty
            architecture_style="",  # Empty
        )

        result = write_project_md(charter, tmp_path)
        content = result.read_text()

        assert "TBD" in content

    def test_project_md_with_all_sections(self, tmp_path: Path) -> None:
        """Test PROJECT.md with all sections populated."""
        charter = ProjectCharter(
            name="complete-project",
            description="A complete project",
            purpose="Test all sections",
            primary_language="python",
            target_platforms=["api", "cli"],
            frameworks=["fastapi", "typer"],
            architecture_style="monolith",
            data_storage=["postgresql"],
            performance_needs="high",
            security_level="strict",
            scalability="enterprise",
            testing_strategy="comprehensive",
            ci_cd_needed=True,
            containerized=True,
            constraints=["Must be fast"],
            integrations=["Slack"],
            notes="Important project",
        )

        result = write_project_md(charter, tmp_path)
        content = result.read_text()

        # Verify all major sections
        assert "# complete-project" in content
        assert "Problem Statement" in content
        assert "Technical Specifications" in content
        assert "Non-Functional Requirements" in content
        assert "Development Configuration" in content
        assert "External Integrations" in content
        assert "Constraints" in content
        assert "Additional Notes" in content

    def test_project_md_without_target_platforms(self, tmp_path: Path) -> None:
        """Test PROJECT.md without target platforms."""
        charter = ProjectCharter(
            name="test",
            description="Test",
            target_platforms=[],
        )

        result = write_project_md(charter, tmp_path)
        content = result.read_text()

        assert "**Target Platforms**:" not in content
