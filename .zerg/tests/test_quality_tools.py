"""Tests for ZERG v2 Quality Tools detection and configuration."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestToolConfig:
    """Tests for ToolConfig dataclass."""

    def test_config_creation(self):
        """Test ToolConfig can be created."""
        from quality_tools import ToolConfig

        config = ToolConfig(name="ruff", command="ruff check .")
        assert config.name == "ruff"
        assert config.command == "ruff check ."
        assert config.available is False

    def test_config_with_version(self):
        """Test ToolConfig with version."""
        from quality_tools import ToolConfig

        config = ToolConfig(
            name="pytest",
            command="pytest",
            version="7.4.0",
            available=True,
        )
        assert config.version == "7.4.0"
        assert config.available is True


class TestQualityToolset:
    """Tests for QualityToolset dataclass."""

    def test_toolset_creation(self):
        """Test QualityToolset can be created."""
        from quality_tools import QualityToolset

        toolset = QualityToolset(language="python")
        assert toolset.language == "python"
        assert toolset.linter is None

    def test_toolset_with_tools(self):
        """Test QualityToolset with detected tools."""
        from quality_tools import QualityToolset, ToolConfig

        linter = ToolConfig(name="ruff", command="ruff check .", available=True)
        toolset = QualityToolset(language="python", linter=linter)
        assert toolset.linter is not None
        assert toolset.linter.name == "ruff"

    def test_to_gates_config_empty(self):
        """Test to_gates_config with no tools."""
        from quality_tools import QualityToolset

        toolset = QualityToolset(language="python")
        gates = toolset.to_gates_config()
        assert gates == []

    def test_to_gates_config_with_linter(self):
        """Test to_gates_config with linter."""
        from quality_tools import QualityToolset, ToolConfig

        linter = ToolConfig(name="ruff", command="ruff check .", available=True)
        toolset = QualityToolset(language="python", linter=linter)
        gates = toolset.to_gates_config()
        assert len(gates) == 1
        assert gates[0]["name"] == "lint"
        assert gates[0]["command"] == "ruff check ."

    def test_to_gates_config_multiple_tools(self):
        """Test to_gates_config with multiple tools."""
        from quality_tools import QualityToolset, ToolConfig

        linter = ToolConfig(name="ruff", command="ruff check .", available=True)
        tester = ToolConfig(name="pytest", command="pytest", available=True)
        toolset = QualityToolset(language="python", linter=linter, test_runner=tester)
        gates = toolset.to_gates_config()
        assert len(gates) == 2
        names = [g["name"] for g in gates]
        assert "lint" in names
        assert "test" in names

    def test_summary(self):
        """Test summary method."""
        from quality_tools import QualityToolset, ToolConfig

        linter = ToolConfig(name="ruff", command="ruff check .", available=True)
        toolset = QualityToolset(language="python", linter=linter)
        summary = toolset.summary()
        assert "linter" in summary
        assert "ruff" in summary["linter"]
        assert summary["formatter"] == "not detected"


class TestLanguageTools:
    """Tests for language tool configurations."""

    def test_python_tools_exist(self):
        """Test Python tools are defined."""
        from quality_tools import PYTHON_TOOLS

        assert "linter" in PYTHON_TOOLS
        assert "test_runner" in PYTHON_TOOLS
        assert "security_scanner" in PYTHON_TOOLS

    def test_typescript_tools_exist(self):
        """Test TypeScript tools are defined."""
        from quality_tools import TYPESCRIPT_TOOLS

        assert "linter" in TYPESCRIPT_TOOLS
        assert "formatter" in TYPESCRIPT_TOOLS

    def test_go_tools_exist(self):
        """Test Go tools are defined."""
        from quality_tools import GO_TOOLS

        assert "linter" in GO_TOOLS
        assert "test_runner" in GO_TOOLS

    def test_rust_tools_exist(self):
        """Test Rust tools are defined."""
        from quality_tools import RUST_TOOLS

        assert "linter" in RUST_TOOLS
        assert "test_runner" in RUST_TOOLS


class TestToolDetector:
    """Tests for ToolDetector."""

    def test_detector_creation(self):
        """Test ToolDetector can be created."""
        from quality_tools import ToolDetector

        with tempfile.TemporaryDirectory() as tmpdir:
            detector = ToolDetector(Path(tmpdir))
            assert detector is not None

    def test_detect_python(self):
        """Test detecting Python tools."""
        from quality_tools import ToolDetector

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            # Create pyproject.toml to simulate Python project
            (project_path / "pyproject.toml").write_text("[tool.pytest]")

            detector = ToolDetector(project_path)
            toolset = detector.detect("python")
            assert toolset.language == "python"
            # May or may not detect tools depending on what's installed

    def test_detect_unknown_language(self):
        """Test detecting tools for unknown language."""
        from quality_tools import ToolDetector

        with tempfile.TemporaryDirectory() as tmpdir:
            detector = ToolDetector(Path(tmpdir))
            toolset = detector.detect("cobol")
            assert toolset.language == "cobol"
            assert toolset.linter is None


class TestQualityConfigGenerator:
    """Tests for QualityConfigGenerator."""

    def test_generator_creation(self):
        """Test QualityConfigGenerator can be created."""
        from quality_tools import QualityConfigGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            gen = QualityConfigGenerator(Path(tmpdir))
            assert gen is not None

    def test_generate_config(self):
        """Test generating configuration."""
        from quality_tools import QualityConfigGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            gen = QualityConfigGenerator(Path(tmpdir))
            config = gen.generate("python")
            assert "language" in config
            assert "tools" in config
            assert "quality_gates" in config
            assert config["language"] == "python"

    def test_generate_yaml_section(self):
        """Test generating YAML section."""
        from quality_tools import QualityConfigGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            gen = QualityConfigGenerator(Path(tmpdir))
            yaml = gen.generate_config_yaml_section("python")
            assert "quality_gates:" in yaml


class TestDetectAndConfigure:
    """Tests for detect_and_configure convenience function."""

    def test_detect_and_configure(self):
        """Test convenience function."""
        from quality_tools import detect_and_configure

        with tempfile.TemporaryDirectory() as tmpdir:
            toolset = detect_and_configure(Path(tmpdir), "python")
            assert toolset.language == "python"


class TestRealProjectDetection:
    """Tests with real project (ZERG itself)."""

    def test_detect_zerg_project_tools(self):
        """Test detecting tools in ZERG project."""
        from quality_tools import ToolDetector

        # Use the actual ZERG project path
        project_path = Path(__file__).parent.parent.parent
        if not (project_path / "pyproject.toml").exists():
            # Skip if not in expected location
            return

        detector = ToolDetector(project_path)
        toolset = detector.detect("python")

        # ZERG should have ruff and pytest available
        assert toolset.language == "python"
        # These may or may not be detected depending on environment
        # Just verify the detection runs without error
