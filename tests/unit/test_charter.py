"""Unit tests for charter.py - ProjectCharter and requirements gathering."""

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
        assert charter.security_level == "standard"
        assert charter.ci_cd_needed is True
        assert charter.containerized is True
        assert charter.target_platforms == []
        assert charter.frameworks == []

    def test_custom_values(self) -> None:
        """Test creating charter with custom values."""
        charter = ProjectCharter(
            name="my-project",
            description="A test project",
            primary_language="python",
            target_platforms=["api", "cli"],
            security_level="strict",
        )

        assert charter.name == "my-project"
        assert charter.description == "A test project"
        assert charter.primary_language == "python"
        assert charter.target_platforms == ["api", "cli"]
        assert charter.security_level == "strict"

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

    def test_from_dict_handles_missing_fields(self) -> None:
        """Test that from_dict handles missing fields gracefully."""
        data = {"name": "minimal"}

        charter = ProjectCharter.from_dict(data)

        assert charter.name == "minimal"
        assert charter.description == ""
        assert charter.security_level == "standard"

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
        # Mock all prompts
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
