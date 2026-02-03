"""Unit tests for tech_selector.py - technology stack selection."""

from unittest.mock import patch

from zerg.charter import ProjectCharter
from zerg.tech_selector import (
    FRAMEWORK_RECOMMENDATIONS,
    SUPPORTED_LANGUAGES,
    TechStack,
    recommend_stack,
    select_technology,
)


class TestSupportedLanguages:
    """Tests for SUPPORTED_LANGUAGES constant."""

    def test_contains_python(self) -> None:
        """Test that Python is supported."""
        assert "python" in SUPPORTED_LANGUAGES
        assert SUPPORTED_LANGUAGES["python"]["name"] == "Python"

    def test_contains_typescript(self) -> None:
        """Test that TypeScript is supported."""
        assert "typescript" in SUPPORTED_LANGUAGES
        assert SUPPORTED_LANGUAGES["typescript"]["name"] == "TypeScript"

    def test_contains_go(self) -> None:
        """Test that Go is supported."""
        assert "go" in SUPPORTED_LANGUAGES
        assert SUPPORTED_LANGUAGES["go"]["name"] == "Go"

    def test_contains_rust(self) -> None:
        """Test that Rust is supported."""
        assert "rust" in SUPPORTED_LANGUAGES
        assert SUPPORTED_LANGUAGES["rust"]["name"] == "Rust"

    def test_all_languages_have_required_fields(self) -> None:
        """Test that all languages have required fields."""
        required_fields = ["name", "version", "package_manager", "test_framework", "linter"]

        for lang, info in SUPPORTED_LANGUAGES.items():
            for field in required_fields:
                assert field in info, f"{lang} missing {field}"


class TestFrameworkRecommendations:
    """Tests for framework recommendations."""

    def test_python_api_frameworks(self) -> None:
        """Test Python API framework recommendations."""
        assert "fastapi" in FRAMEWORK_RECOMMENDATIONS["python"]["api"]
        assert "flask" in FRAMEWORK_RECOMMENDATIONS["python"]["api"]

    def test_python_cli_frameworks(self) -> None:
        """Test Python CLI framework recommendations."""
        assert "typer" in FRAMEWORK_RECOMMENDATIONS["python"]["cli"]
        assert "click" in FRAMEWORK_RECOMMENDATIONS["python"]["cli"]

    def test_typescript_api_frameworks(self) -> None:
        """Test TypeScript API framework recommendations."""
        assert "fastify" in FRAMEWORK_RECOMMENDATIONS["typescript"]["api"]
        assert "express" in FRAMEWORK_RECOMMENDATIONS["typescript"]["api"]

    def test_go_api_frameworks(self) -> None:
        """Test Go API framework recommendations."""
        assert "gin" in FRAMEWORK_RECOMMENDATIONS["go"]["api"]
        assert "echo" in FRAMEWORK_RECOMMENDATIONS["go"]["api"]


class TestTechStack:
    """Tests for TechStack dataclass."""

    def test_default_values(self) -> None:
        """Test TechStack default values."""
        stack = TechStack()

        assert stack.language == ""
        assert stack.dockerfile is True
        assert stack.ci_provider == "github-actions"
        assert stack.additional_frameworks == []

    def test_custom_values(self) -> None:
        """Test TechStack with custom values."""
        stack = TechStack(
            language="python",
            language_version="3.12",
            package_manager="uv",
            primary_framework="fastapi",
            test_framework="pytest",
        )

        assert stack.language == "python"
        assert stack.language_version == "3.12"
        assert stack.primary_framework == "fastapi"

    def test_to_dict(self) -> None:
        """Test TechStack to_dict conversion."""
        stack = TechStack(
            language="go",
            primary_framework="gin",
        )

        data = stack.to_dict()

        assert data["language"] == "go"
        assert data["primary_framework"] == "gin"
        assert "dockerfile" in data

    def test_from_dict(self) -> None:
        """Test TechStack from_dict creation."""
        data = {
            "language": "rust",
            "primary_framework": "axum",
            "test_framework": "cargo test",
        }

        stack = TechStack.from_dict(data)

        assert stack.language == "rust"
        assert stack.primary_framework == "axum"

    def test_round_trip_serialization(self) -> None:
        """Test TechStack serialization round-trip."""
        original = TechStack(
            language="typescript",
            language_version="5.x",
            package_manager="pnpm",
            primary_framework="fastify",
            test_framework="vitest",
            linter="eslint",
            formatter="prettier",
            dockerfile=True,
            ci_provider="github-actions",
        )

        data = original.to_dict()
        restored = TechStack.from_dict(data)

        assert restored.language == original.language
        assert restored.primary_framework == original.primary_framework
        assert restored.dockerfile == original.dockerfile


class TestRecommendStack:
    """Tests for recommend_stack function."""

    def test_recommends_python_for_api(self) -> None:
        """Test that Python is recommended for API projects."""
        charter = ProjectCharter(
            name="test",
            description="Test",
            target_platforms=["api"],
        )

        stack = recommend_stack(charter)

        assert stack.language == "python"

    def test_recommends_fastapi_for_python_api(self) -> None:
        """Test that FastAPI is recommended for Python API."""
        charter = ProjectCharter(
            name="test",
            description="Test",
            primary_language="python",
            target_platforms=["api"],
        )

        stack = recommend_stack(charter)

        assert stack.primary_framework == "fastapi"

    def test_recommends_go_for_high_performance(self) -> None:
        """Test that Go is recommended for high-performance CLI."""
        charter = ProjectCharter(
            name="test",
            description="Test",
            target_platforms=["cli"],
            performance_needs="high",
        )

        stack = recommend_stack(charter)

        assert stack.language == "go"

    def test_respects_specified_language(self) -> None:
        """Test that specified language is used."""
        charter = ProjectCharter(
            name="test",
            description="Test",
            primary_language="rust",
            target_platforms=["api"],
        )

        stack = recommend_stack(charter)

        assert stack.language == "rust"

    def test_sets_language_ecosystem(self) -> None:
        """Test that language ecosystem is set correctly."""
        charter = ProjectCharter(
            name="test",
            description="Test",
            primary_language="python",
        )

        stack = recommend_stack(charter)

        assert stack.package_manager == "uv"
        assert stack.test_framework == "pytest"
        assert stack.linter == "ruff"

    def test_sets_database_tools_when_storage_specified(self) -> None:
        """Test that database tools are set when storage is specified."""
        charter = ProjectCharter(
            name="test",
            description="Test",
            primary_language="python",
            data_storage=["postgresql"],
        )

        stack = recommend_stack(charter)

        assert stack.database_driver != ""
        assert "asyncpg" in stack.database_driver or "pg" in stack.database_driver

    def test_sets_devops_from_charter(self) -> None:
        """Test that DevOps settings come from charter."""
        charter = ProjectCharter(
            name="test",
            description="Test",
            containerized=False,
            ci_cd_needed=False,
        )

        stack = recommend_stack(charter)

        assert stack.dockerfile is False
        assert stack.ci_provider == "none"


class TestSelectTechnology:
    """Tests for select_technology function."""

    @patch("zerg.tech_selector.Prompt.ask")
    def test_returns_tech_stack(self, mock_prompt: patch) -> None:
        """Test that select_technology returns a TechStack."""
        mock_prompt.side_effect = ["python", "fastapi"]

        charter = ProjectCharter(
            name="test",
            description="Test",
            target_platforms=["api"],
        )

        stack = select_technology(charter)

        assert isinstance(stack, TechStack)
        assert stack.language == "python"

    @patch("zerg.tech_selector.Prompt.ask")
    def test_uses_recommended_defaults(self, mock_prompt: patch) -> None:
        """Test that recommended values are used as defaults."""
        # Accept defaults by returning empty strings (Prompt.ask will use default)
        mock_prompt.side_effect = ["python", "fastapi"]

        charter = ProjectCharter(
            name="test",
            description="Test",
            primary_language="python",
            target_platforms=["api"],
        )

        stack = select_technology(charter)

        # Should have Python ecosystem settings
        assert stack.test_framework == "pytest"
        assert stack.linter == "ruff"

    @patch("zerg.tech_selector.Prompt.ask")
    def test_handles_none_framework(self, mock_prompt: patch) -> None:
        """Test that 'none' framework is handled correctly."""
        mock_prompt.side_effect = ["python", "none"]

        charter = ProjectCharter(
            name="test",
            description="Test",
            target_platforms=["library"],
        )

        stack = select_technology(charter)

        assert stack.primary_framework == ""

    @patch("zerg.tech_selector.Prompt.ask")
    def test_updates_charter_with_selections(self, mock_prompt: patch) -> None:
        """Test that charter is updated with final selections."""
        mock_prompt.side_effect = ["go", "gin"]

        charter = ProjectCharter(
            name="test",
            description="Test",
            target_platforms=["api"],
        )

        select_technology(charter)

        # Charter should be updated
        assert charter.primary_language == "go"
        assert "gin" in charter.frameworks

    @patch("zerg.tech_selector.Prompt.ask")
    def test_falls_back_to_python_for_unknown_language(self, mock_prompt: patch) -> None:
        """Test that unknown language falls back to Python."""
        mock_prompt.side_effect = ["unknown-lang", "none"]

        charter = ProjectCharter(
            name="test",
            description="Test",
        )

        stack = select_technology(charter)

        assert stack.language == "python"
