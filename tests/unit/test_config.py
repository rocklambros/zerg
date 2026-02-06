"""Tests for ZERG configuration module."""

from pathlib import Path

import pytest
import yaml

from zerg.config import (
    LoggingConfig,
    PortsConfig,
    ProjectConfig,
    QualityGate,
    ResourcesConfig,
    SecurityConfig,
    WorkersConfig,
    ZergConfig,
)
from zerg.launcher_types import LauncherType


class TestProjectConfig:
    """Tests for ProjectConfig model."""

    def test_default_and_custom(self) -> None:
        """Test default and custom project configuration."""
        default = ProjectConfig()
        assert default.name == "zerg"
        custom = ProjectConfig(name="custom", description="Custom project")
        assert custom.name == "custom"


class TestWorkersConfig:
    """Tests for WorkersConfig model."""

    def test_default_values(self) -> None:
        """Test default workers configuration."""
        config = WorkersConfig()
        assert config.max_concurrent == 5
        assert config.timeout_minutes == 30
        assert config.retry_attempts == 3
        assert config.launcher_type == "subprocess"

    def test_custom_values(self) -> None:
        """Test custom workers configuration."""
        config = WorkersConfig(max_concurrent=8, timeout_minutes=60, launcher_type="container")
        assert config.max_concurrent == 8
        assert config.timeout_minutes == 60

    @pytest.mark.parametrize(
        "field,value",
        [
            ("max_concurrent", 0),
            ("max_concurrent", 11),
            ("timeout_minutes", 0),
            ("retry_attempts", -1),
            ("context_threshold_percent", 49),
            ("launcher_type", "invalid"),
        ],
    )
    def test_validation_rejects_invalid(self, field: str, value) -> None:
        """Test validation rejects out-of-range values."""
        with pytest.raises(ValueError):
            WorkersConfig(**{field: value})


class TestPortsConfig:
    """Tests for PortsConfig model."""

    def test_default_values(self) -> None:
        """Test default ports configuration."""
        config = PortsConfig()
        assert config.range_start == 49152
        assert config.range_end == 65535

    def test_validation_rejects_invalid(self) -> None:
        """Test validation rejects out-of-range values."""
        with pytest.raises(ValueError):
            PortsConfig(range_start=1023)
        with pytest.raises(ValueError):
            PortsConfig(range_end=65536)


class TestQualityGate:
    """Tests for QualityGate model."""

    def test_minimal_and_full(self) -> None:
        """Test minimal and full quality gate configuration."""
        minimal = QualityGate(name="test", command="echo test")
        assert minimal.required is False
        assert minimal.timeout == 300

        full = QualityGate(name="test", command="pytest", required=True, timeout=600, coverage_threshold=80)
        assert full.required is True
        assert full.coverage_threshold == 80

    def test_timeout_validation(self) -> None:
        """Test timeout validation bounds."""
        with pytest.raises(ValueError):
            QualityGate(name="test", command="echo", timeout=0)
        with pytest.raises(ValueError):
            QualityGate(name="test", command="echo", timeout=3601)


class TestResourcesConfig:
    """Tests for ResourcesConfig model."""

    def test_default_values(self) -> None:
        """Test default resources configuration."""
        config = ResourcesConfig()
        assert config.cpu_cores == 2
        assert config.memory_gb == 4


class TestLoggingConfig:
    """Tests for LoggingConfig model."""

    def test_default_values(self) -> None:
        """Test default logging configuration."""
        config = LoggingConfig()
        assert config.level == "info"
        assert config.directory == ".zerg/logs"

    def test_level_validation(self) -> None:
        """Test level pattern validation."""
        with pytest.raises(ValueError):
            LoggingConfig(level="invalid")
        for level in ["debug", "info", "warn", "error"]:
            assert LoggingConfig(level=level).level == level


class TestSecurityConfig:
    """Tests for SecurityConfig model."""

    def test_default_values(self) -> None:
        """Test default security configuration."""
        config = SecurityConfig()
        assert config.level == "standard"
        assert config.pre_commit_hooks is True

    def test_level_validation(self) -> None:
        """Test level pattern validation."""
        with pytest.raises(ValueError):
            SecurityConfig(level="invalid")
        for level in ["minimal", "standard", "strict"]:
            assert SecurityConfig(level=level).level == level


class TestZergConfig:
    """Tests for ZergConfig model."""

    @pytest.mark.smoke
    def test_default_values(self) -> None:
        """Test default ZergConfig values."""
        config = ZergConfig()
        assert config.project.name == "zerg"
        assert config.workers.max_concurrent == 5
        assert config.ports.range_start == 49152
        assert config.quality_gates == []

    @pytest.mark.smoke
    def test_from_dict(self) -> None:
        """Test creating config from dictionary."""
        data = {
            "project": {"name": "test-project"},
            "workers": {"max_concurrent": 3},
            "quality_gates": [{"name": "lint", "command": "ruff check", "required": True}],
        }
        config = ZergConfig.from_dict(data)
        assert config.project.name == "test-project"
        assert config.workers.max_concurrent == 3
        assert len(config.quality_gates) == 1

    @pytest.mark.smoke
    def test_to_dict(self) -> None:
        """Test converting config to dictionary."""
        config = ZergConfig()
        data = config.to_dict()
        assert isinstance(data, dict)
        assert data["project"]["name"] == "zerg"

    @pytest.mark.smoke
    def test_context_threshold_property(self) -> None:
        """Test context_threshold property conversion."""
        config = ZergConfig()
        config.workers.context_threshold_percent = 70
        assert config.context_threshold == 0.7

    def test_get_gate(self) -> None:
        """Test getting quality gate by name (found and not found)."""
        config = ZergConfig()
        config.quality_gates = [QualityGate(name="lint", command="ruff check")]
        assert config.get_gate("lint") is not None
        assert config.get_gate("nonexistent") is None

    def test_get_launcher_type(self) -> None:
        """Test getting launcher type."""
        config = ZergConfig()
        config.workers.launcher_type = "subprocess"
        assert config.get_launcher_type() == LauncherType.SUBPROCESS
        config.workers.launcher_type = "container"
        assert config.get_launcher_type() == LauncherType.CONTAINER


class TestZergConfigLoad:
    """Tests for ZergConfig.load method."""

    def test_load_from_file(self, tmp_path: Path) -> None:
        """Test loading config from YAML file."""
        config_data = {
            "project": {"name": "loaded-project"},
            "workers": {"max_concurrent": 8},
        }
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ZergConfig.load(config_file)
        assert config.project.name == "loaded-project"
        assert config.workers.max_concurrent == 8

    def test_load_nonexistent_returns_defaults(self, tmp_path: Path) -> None:
        """Test loading with non-existent path returns defaults."""
        config = ZergConfig.load(tmp_path / "nonexistent.yaml")
        assert config.project.name == "zerg"


class TestZergConfigSave:
    """Tests for ZergConfig.save method."""

    def test_save_custom_path(self, tmp_path: Path) -> None:
        """Test saving to custom path."""
        config = ZergConfig()
        config.project.name = "custom-saved"
        custom_path = tmp_path / "custom" / "config.yaml"
        config.save(custom_path)

        assert custom_path.exists()
        with open(custom_path) as f:
            data = yaml.safe_load(f)
        assert data["project"]["name"] == "custom-saved"

    def test_save_full_config_round_trip(self, tmp_path: Path) -> None:
        """Test saving full config and reloading."""
        config = ZergConfig()
        config.project.name = "full-project"
        config.workers.max_concurrent = 8
        config.quality_gates = [QualityGate(name="lint", command="ruff", required=True)]
        config.security.level = "strict"

        config_file = tmp_path / "full-config.yaml"
        config.save(config_file)

        loaded = ZergConfig.load(config_file)
        assert loaded.project.name == "full-project"
        assert loaded.workers.max_concurrent == 8
        assert loaded.security.level == "strict"
