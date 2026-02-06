"""Tests for zerg.config module."""

from pathlib import Path

from zerg.config import QualityGate, WorkersConfig, ZergConfig


class TestZergConfig:
    """Tests for ZergConfig class."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = ZergConfig()

        assert config.workers.max_concurrent == 5
        assert config.workers.timeout_minutes == 30  # Default from constants
        assert config.context_threshold == 0.7

    def test_workers_config(self) -> None:
        """Test workers configuration."""
        workers = WorkersConfig(
            max_concurrent=10,
            timeout_minutes=120,
            context_threshold_percent=80,
        )

        assert workers.max_concurrent == 10
        assert workers.timeout_minutes == 120
        assert workers.context_threshold_percent == 80

    def test_context_threshold_property(self) -> None:
        """Test context threshold property conversion."""
        config = ZergConfig()
        # Default is 70%
        assert config.context_threshold == 0.7

    def test_quality_gates_default(self) -> None:
        """Test default quality gates."""
        config = ZergConfig()

        assert isinstance(config.quality_gates, list)
        assert len(config.quality_gates) == 0  # Empty by default

    def test_quality_gates_custom(self) -> None:
        """Test custom quality gates."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="lint", command="ruff check .", required=True),
            QualityGate(name="test", command="pytest", required=True),
        ]

        assert len(config.quality_gates) == 2
        assert config.quality_gates[0].name == "lint"
        assert config.quality_gates[0].required is True

    def test_mcp_servers_default(self) -> None:
        """Test default MCP servers."""
        config = ZergConfig()

        assert isinstance(config.mcp_servers, list)
        assert "filesystem" in config.mcp_servers

    def test_load_creates_default(self, tmp_path: Path, monkeypatch) -> None:
        """Test load creates default config if none exists."""
        monkeypatch.chdir(tmp_path)

        config = ZergConfig.load()

        assert config is not None
        assert config.workers.max_concurrent == 5

    def test_load_from_yaml(self, tmp_path: Path, monkeypatch) -> None:
        """Test loading config from YAML file."""
        monkeypatch.chdir(tmp_path)

        # Create config directory and file
        config_dir = tmp_path / ".zerg"
        config_dir.mkdir()

        config_file = config_dir / "config.yaml"
        config_file.write_text("""
workers:
  max_concurrent: 8
  timeout_minutes: 30
  context_threshold_percent: 60
security:
  level: minimal
mcp_servers: []
""")

        config = ZergConfig.load()

        assert config.workers.max_concurrent == 8
        assert config.workers.timeout_minutes == 30
        assert config.context_threshold == 0.6
        assert config.security.level == "minimal"

    def test_to_dict(self) -> None:
        """Test config serialization to dict."""
        config = ZergConfig()

        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert "workers" in config_dict
        assert "project" in config_dict

    def test_get_gate(self) -> None:
        """Test getting a gate by name."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="lint", command="ruff check", required=True),
            QualityGate(name="test", command="pytest", required=True),
        ]

        lint_gate = config.get_gate("lint")
        assert lint_gate is not None
        assert lint_gate.name == "lint"

        missing_gate = config.get_gate("nonexistent")
        assert missing_gate is None

    def test_get_required_gates(self) -> None:
        """Test getting required gates."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="lint", command="ruff check", required=True),
            QualityGate(name="format", command="ruff format", required=False),
            QualityGate(name="test", command="pytest", required=True),
        ]

        required = config.get_required_gates()

        assert len(required) == 2
        assert all(g.required for g in required)

    def test_fixture_sample_config(self, sample_config: ZergConfig) -> None:
        """Test the sample_config fixture."""
        assert sample_config.workers.max_concurrent == 5
        assert sample_config.context_threshold == 0.7
        assert len(sample_config.quality_gates) == 2

    def test_launcher_type_default(self) -> None:
        """Test default launcher type is subprocess."""
        config = ZergConfig()
        assert config.workers.launcher_type == "subprocess"

    def test_launcher_type_container(self) -> None:
        """Test container launcher type."""
        from zerg.config import WorkersConfig

        workers = WorkersConfig(launcher_type="container")
        assert workers.launcher_type == "container"

    def test_get_launcher_type(self) -> None:
        """Test get_launcher_type method."""
        from zerg.launcher_types import LauncherType

        config = ZergConfig()
        launcher_type = config.get_launcher_type()

        assert launcher_type == LauncherType.SUBPROCESS

    def test_launcher_type_from_yaml(self, tmp_path: Path, monkeypatch) -> None:
        """Test loading launcher type from YAML."""
        monkeypatch.chdir(tmp_path)

        config_dir = tmp_path / ".zerg"
        config_dir.mkdir()

        config_file = config_dir / "config.yaml"
        config_file.write_text("""
workers:
  launcher_type: container
""")

        config = ZergConfig.load()
        assert config.workers.launcher_type == "container"
