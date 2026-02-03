"""Comprehensive tests for ZERG configuration module."""

import os
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
from zerg.launcher import LauncherType


class TestProjectConfig:
    """Tests for ProjectConfig model."""

    def test_default_values(self) -> None:
        """Test default project configuration values."""
        config = ProjectConfig()
        assert config.name == "zerg"
        assert config.description == "Parallel Claude Code execution system"

    def test_custom_values(self) -> None:
        """Test custom project configuration values."""
        config = ProjectConfig(name="custom", description="Custom project")
        assert config.name == "custom"
        assert config.description == "Custom project"


class TestWorkersConfig:
    """Tests for WorkersConfig model."""

    def test_default_values(self) -> None:
        """Test default workers configuration."""
        config = WorkersConfig()
        assert config.max_concurrent == 5
        assert config.timeout_minutes == 30
        assert config.retry_attempts == 3
        assert config.context_threshold_percent == 70
        assert config.launcher_type == "subprocess"

    def test_custom_values(self) -> None:
        """Test custom workers configuration."""
        config = WorkersConfig(
            max_concurrent=8,
            timeout_minutes=60,
            retry_attempts=5,
            context_threshold_percent=80,
            launcher_type="container",
        )
        assert config.max_concurrent == 8
        assert config.timeout_minutes == 60
        assert config.retry_attempts == 5
        assert config.context_threshold_percent == 80
        assert config.launcher_type == "container"

    def test_validation_max_concurrent_min(self) -> None:
        """Test max_concurrent minimum validation."""
        with pytest.raises(ValueError):
            WorkersConfig(max_concurrent=0)

    def test_validation_max_concurrent_max(self) -> None:
        """Test max_concurrent maximum validation."""
        with pytest.raises(ValueError):
            WorkersConfig(max_concurrent=11)

    def test_validation_timeout_min(self) -> None:
        """Test timeout_minutes minimum validation."""
        with pytest.raises(ValueError):
            WorkersConfig(timeout_minutes=0)

    def test_validation_timeout_max(self) -> None:
        """Test timeout_minutes maximum validation."""
        with pytest.raises(ValueError):
            WorkersConfig(timeout_minutes=121)

    def test_validation_retry_min(self) -> None:
        """Test retry_attempts minimum validation."""
        with pytest.raises(ValueError):
            WorkersConfig(retry_attempts=-1)

    def test_validation_retry_max(self) -> None:
        """Test retry_attempts maximum validation."""
        with pytest.raises(ValueError):
            WorkersConfig(retry_attempts=11)

    def test_validation_context_threshold_min(self) -> None:
        """Test context_threshold_percent minimum validation."""
        with pytest.raises(ValueError):
            WorkersConfig(context_threshold_percent=49)

    def test_validation_context_threshold_max(self) -> None:
        """Test context_threshold_percent maximum validation."""
        with pytest.raises(ValueError):
            WorkersConfig(context_threshold_percent=91)

    def test_validation_launcher_type_pattern(self) -> None:
        """Test launcher_type pattern validation."""
        with pytest.raises(ValueError):
            WorkersConfig(launcher_type="invalid")


class TestPortsConfig:
    """Tests for PortsConfig model."""

    def test_default_values(self) -> None:
        """Test default ports configuration."""
        config = PortsConfig()
        assert config.range_start == 49152
        assert config.range_end == 65535
        assert config.ports_per_worker == 10

    def test_custom_values(self) -> None:
        """Test custom ports configuration."""
        config = PortsConfig(
            range_start=50000,
            range_end=60000,
            ports_per_worker=5,
        )
        assert config.range_start == 50000
        assert config.range_end == 60000
        assert config.ports_per_worker == 5

    def test_validation_range_start_min(self) -> None:
        """Test range_start minimum validation."""
        with pytest.raises(ValueError):
            PortsConfig(range_start=1023)

    def test_validation_range_end_max(self) -> None:
        """Test range_end maximum validation."""
        with pytest.raises(ValueError):
            PortsConfig(range_end=65536)

    def test_validation_ports_per_worker_min(self) -> None:
        """Test ports_per_worker minimum validation."""
        with pytest.raises(ValueError):
            PortsConfig(ports_per_worker=0)


class TestQualityGate:
    """Tests for QualityGate model."""

    def test_minimal_gate(self) -> None:
        """Test minimal quality gate configuration."""
        gate = QualityGate(name="test", command="echo test")
        assert gate.name == "test"
        assert gate.command == "echo test"
        assert gate.required is False
        assert gate.timeout == 300
        assert gate.coverage_threshold is None

    def test_full_gate(self) -> None:
        """Test full quality gate configuration."""
        gate = QualityGate(
            name="test",
            command="pytest",
            required=True,
            timeout=600,
            coverage_threshold=80,
        )
        assert gate.name == "test"
        assert gate.command == "pytest"
        assert gate.required is True
        assert gate.timeout == 600
        assert gate.coverage_threshold == 80

    def test_timeout_validation_min(self) -> None:
        """Test timeout minimum validation."""
        with pytest.raises(ValueError):
            QualityGate(name="test", command="echo", timeout=0)

    def test_timeout_validation_max(self) -> None:
        """Test timeout maximum validation."""
        with pytest.raises(ValueError):
            QualityGate(name="test", command="echo", timeout=3601)


class TestResourcesConfig:
    """Tests for ResourcesConfig model."""

    def test_default_values(self) -> None:
        """Test default resources configuration."""
        config = ResourcesConfig()
        assert config.cpu_cores == 2
        assert config.memory_gb == 4
        assert config.disk_gb == 10

    def test_custom_values(self) -> None:
        """Test custom resources configuration."""
        config = ResourcesConfig(
            cpu_cores=4,
            memory_gb=8,
            disk_gb=20,
        )
        assert config.cpu_cores == 4
        assert config.memory_gb == 8
        assert config.disk_gb == 20


class TestLoggingConfig:
    """Tests for LoggingConfig model."""

    def test_default_values(self) -> None:
        """Test default logging configuration."""
        config = LoggingConfig()
        assert config.level == "info"
        assert config.directory == ".zerg/logs"
        assert config.retain_days == 7

    def test_custom_values(self) -> None:
        """Test custom logging configuration."""
        config = LoggingConfig(
            level="debug",
            directory="/var/log/zerg",
            retain_days=30,
        )
        assert config.level == "debug"
        assert config.directory == "/var/log/zerg"
        assert config.retain_days == 30

    def test_level_pattern_validation(self) -> None:
        """Test level pattern validation."""
        with pytest.raises(ValueError):
            LoggingConfig(level="invalid")

    def test_valid_log_levels(self) -> None:
        """Test all valid log levels."""
        for level in ["debug", "info", "warn", "error"]:
            config = LoggingConfig(level=level)
            assert config.level == level


class TestSecurityConfig:
    """Tests for SecurityConfig model."""

    def test_default_values(self) -> None:
        """Test default security configuration."""
        config = SecurityConfig()
        assert config.level == "standard"
        assert config.pre_commit_hooks is True
        assert config.audit_logging is True
        assert config.container_readonly is True

    def test_custom_values(self) -> None:
        """Test custom security configuration."""
        config = SecurityConfig(
            level="strict",
            pre_commit_hooks=False,
            audit_logging=False,
            container_readonly=False,
        )
        assert config.level == "strict"
        assert config.pre_commit_hooks is False
        assert config.audit_logging is False
        assert config.container_readonly is False

    def test_level_pattern_validation(self) -> None:
        """Test level pattern validation."""
        with pytest.raises(ValueError):
            SecurityConfig(level="invalid")

    def test_valid_security_levels(self) -> None:
        """Test all valid security levels."""
        for level in ["minimal", "standard", "strict"]:
            config = SecurityConfig(level=level)
            assert config.level == level


class TestZergConfig:
    """Tests for ZergConfig model."""

    def test_default_values(self) -> None:
        """Test default ZergConfig values."""
        config = ZergConfig()
        assert config.project.name == "zerg"
        assert config.workers.max_concurrent == 5
        assert config.ports.range_start == 49152
        assert config.quality_gates == []
        assert config.mcp_servers == ["filesystem", "github", "fetch"]
        assert config.resources.cpu_cores == 2
        assert config.logging.level == "info"
        assert config.security.level == "standard"

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
        assert config.quality_gates[0].name == "lint"

    def test_to_dict(self) -> None:
        """Test converting config to dictionary."""
        config = ZergConfig()
        data = config.to_dict()
        assert isinstance(data, dict)
        assert "project" in data
        assert "workers" in data
        assert "ports" in data
        assert "quality_gates" in data
        assert data["project"]["name"] == "zerg"

    def test_context_threshold_property(self) -> None:
        """Test context_threshold property conversion."""
        config = ZergConfig()
        config.workers.context_threshold_percent = 70
        assert config.context_threshold == 0.7

        config.workers.context_threshold_percent = 85
        assert config.context_threshold == 0.85

    def test_get_gate_found(self) -> None:
        """Test getting a quality gate by name."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="lint", command="ruff check"),
            QualityGate(name="test", command="pytest"),
        ]
        gate = config.get_gate("lint")
        assert gate is not None
        assert gate.name == "lint"
        assert gate.command == "ruff check"

    def test_get_gate_not_found(self) -> None:
        """Test getting a non-existent quality gate."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="lint", command="ruff check"),
        ]
        gate = config.get_gate("nonexistent")
        assert gate is None

    def test_get_required_gates(self) -> None:
        """Test getting required quality gates."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="lint", command="ruff check", required=True),
            QualityGate(name="format", command="ruff format", required=False),
            QualityGate(name="test", command="pytest", required=True),
        ]
        required = config.get_required_gates()
        assert len(required) == 2
        assert all(g.required for g in required)
        assert {g.name for g in required} == {"lint", "test"}

    def test_get_launcher_type_subprocess(self) -> None:
        """Test getting subprocess launcher type."""
        config = ZergConfig()
        config.workers.launcher_type = "subprocess"
        assert config.get_launcher_type() == LauncherType.SUBPROCESS

    def test_get_launcher_type_container(self) -> None:
        """Test getting container launcher type."""
        config = ZergConfig()
        config.workers.launcher_type = "container"
        assert config.get_launcher_type() == LauncherType.CONTAINER


class TestZergConfigLoad:
    """Tests for ZergConfig.load method."""

    def test_load_default_path_not_exists(self, tmp_path: Path) -> None:
        """Test loading with default path that doesn't exist."""
        orig_dir = os.getcwd()
        os.chdir(tmp_path)
        try:
            config = ZergConfig.load()
            # Should return default config
            assert config.project.name == "zerg"
        finally:
            os.chdir(orig_dir)

    def test_load_custom_path_not_exists(self, tmp_path: Path) -> None:
        """Test loading with custom path that doesn't exist."""
        config = ZergConfig.load(tmp_path / "nonexistent.yaml")
        assert config.project.name == "zerg"

    def test_load_from_file(self, tmp_path: Path) -> None:
        """Test loading config from YAML file."""
        config_data = {
            "project": {"name": "loaded-project", "description": "Loaded desc"},
            "workers": {"max_concurrent": 8},
        }
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ZergConfig.load(config_file)
        assert config.project.name == "loaded-project"
        assert config.project.description == "Loaded desc"
        assert config.workers.max_concurrent == 8

    def test_load_empty_file(self, tmp_path: Path) -> None:
        """Test loading empty YAML file."""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")

        config = ZergConfig.load(config_file)
        # Should return default config
        assert config.project.name == "zerg"

    def test_load_with_quality_gates(self, tmp_path: Path) -> None:
        """Test loading config with quality gates."""
        config_data = {
            "quality_gates": [
                {"name": "lint", "command": "ruff check", "required": True},
                {"name": "test", "command": "pytest", "timeout": 600},
            ]
        }
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ZergConfig.load(config_file)
        assert len(config.quality_gates) == 2
        assert config.quality_gates[0].name == "lint"
        assert config.quality_gates[1].timeout == 600

    def test_load_with_string_path(self, tmp_path: Path) -> None:
        """Test loading config with string path."""
        config_data = {"project": {"name": "string-path-project"}}
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ZergConfig.load(str(config_file))
        assert config.project.name == "string-path-project"


class TestZergConfigSave:
    """Tests for ZergConfig.save method."""

    def test_save_default_path(self, tmp_path: Path) -> None:
        """Test saving to default path."""
        orig_dir = os.getcwd()
        os.chdir(tmp_path)
        try:
            config = ZergConfig()
            config.project.name = "saved-project"
            config.save()

            saved_file = tmp_path / ".zerg" / "config.yaml"
            assert saved_file.exists()

            with open(saved_file) as f:
                data = yaml.safe_load(f)
            assert data["project"]["name"] == "saved-project"
        finally:
            os.chdir(orig_dir)

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

    def test_save_with_string_path(self, tmp_path: Path) -> None:
        """Test saving with string path."""
        config = ZergConfig()
        config.project.name = "string-saved"
        config.save(str(tmp_path / "string-config.yaml"))

        saved_file = tmp_path / "string-config.yaml"
        assert saved_file.exists()

    def test_save_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test that save creates parent directories."""
        config = ZergConfig()
        deep_path = tmp_path / "a" / "b" / "c" / "config.yaml"
        config.save(deep_path)

        assert deep_path.exists()

    def test_save_overwrites_existing(self, tmp_path: Path) -> None:
        """Test that save overwrites existing file."""
        config_file = tmp_path / "config.yaml"

        # Save first config
        config1 = ZergConfig()
        config1.project.name = "first"
        config1.save(config_file)

        # Save second config
        config2 = ZergConfig()
        config2.project.name = "second"
        config2.save(config_file)

        with open(config_file) as f:
            data = yaml.safe_load(f)
        assert data["project"]["name"] == "second"

    def test_save_full_config(self, tmp_path: Path) -> None:
        """Test saving full config with all options."""
        config = ZergConfig()
        config.project.name = "full-project"
        config.workers.max_concurrent = 8
        config.ports.range_start = 50000
        config.quality_gates = [
            QualityGate(name="lint", command="ruff", required=True),
        ]
        config.mcp_servers = ["filesystem", "github"]
        config.resources.cpu_cores = 4
        config.logging.level = "debug"
        config.security.level = "strict"

        config_file = tmp_path / "full-config.yaml"
        config.save(config_file)

        # Reload and verify
        loaded = ZergConfig.load(config_file)
        assert loaded.project.name == "full-project"
        assert loaded.workers.max_concurrent == 8
        assert loaded.ports.range_start == 50000
        assert len(loaded.quality_gates) == 1
        assert loaded.mcp_servers == ["filesystem", "github"]
        assert loaded.resources.cpu_cores == 4
        assert loaded.logging.level == "debug"
        assert loaded.security.level == "strict"
