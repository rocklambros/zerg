"""Unit tests for resilience configuration fields in ZERG config module.

Tests for FR-1 (spawn retry), FR-2 (task timeout), FR-3 (heartbeat),
and FR-6 (auto-respawn) configuration options.
"""

from pathlib import Path

import pytest
import yaml

from zerg.config import ResilienceConfig, WorkersConfig, ZergConfig

# Mark all tests in this module as slow (PR #115 added 550+ lines)
pytestmark = pytest.mark.slow


class TestResilienceConfig:
    """Tests for ResilienceConfig model."""

    def test_defaults_and_toggle(self) -> None:
        """Test ResilienceConfig defaults and can be disabled."""
        config = ResilienceConfig()
        assert config.enabled is True

        config2 = ResilienceConfig(enabled=False)
        assert config2.enabled is False

    def test_resilience_config_in_zerg_config(self) -> None:
        """Test that ZergConfig has resilience attribute."""
        config = ZergConfig()
        assert isinstance(config.resilience, ResilienceConfig)
        assert config.resilience.enabled is True


class TestWorkersConfigFields:
    """Tests for WorkersConfig field defaults and customization."""

    def test_spawn_retry_defaults_and_custom(self) -> None:
        """Test spawn retry, backoff, and strategy defaults/custom."""
        config = WorkersConfig()
        assert config.spawn_retry_attempts == 3
        assert config.spawn_backoff_base_seconds == 2
        assert config.spawn_backoff_max_seconds == 30

        config2 = WorkersConfig(spawn_retry_attempts=5, spawn_backoff_strategy="fixed")
        assert config2.spawn_retry_attempts == 5
        assert config2.spawn_backoff_strategy == "fixed"

    @pytest.mark.parametrize("strategy", ["exponential", "linear", "fixed"])
    def test_spawn_backoff_strategy_valid(self, strategy: str) -> None:
        """Test spawn_backoff_strategy accepts all valid values."""
        assert WorkersConfig(spawn_backoff_strategy=strategy).spawn_backoff_strategy == strategy

    def test_task_timeout_and_heartbeat_defaults(self) -> None:
        """Test task timeout and heartbeat defaults/custom."""
        config = WorkersConfig()
        assert config.task_stale_timeout_seconds == 600
        assert config.heartbeat_interval_seconds == 30
        assert config.heartbeat_stale_threshold == 120

    def test_auto_respawn_defaults_and_custom(self) -> None:
        """Test auto_respawn defaults and customization."""
        config = WorkersConfig()
        assert config.auto_respawn is True
        assert config.max_respawn_attempts == 5

        config2 = WorkersConfig(auto_respawn=False, max_respawn_attempts=10)
        assert config2.auto_respawn is False
        assert config2.max_respawn_attempts == 10


class TestWorkersConfigBoundaryRejection:
    """Tests for boundary value rejection across all config fields."""

    @pytest.mark.parametrize(
        "field, bad_value",
        [
            ("spawn_retry_attempts", -1),
            ("spawn_retry_attempts", 11),
            ("spawn_backoff_base_seconds", 0),
            ("spawn_backoff_max_seconds", 301),
            ("task_stale_timeout_seconds", 59),
            ("task_stale_timeout_seconds", 3601),
            ("heartbeat_interval_seconds", 4),
            ("heartbeat_stale_threshold", 601),
            ("max_respawn_attempts", -1),
            ("max_respawn_attempts", 21),
        ],
    )
    def test_boundary_rejected(self, field: str, bad_value: int) -> None:
        """Test config fields reject out-of-range values."""
        with pytest.raises(ValueError):
            WorkersConfig(**{field: bad_value})

    def test_spawn_backoff_strategy_invalid_rejected(self) -> None:
        """Test spawn_backoff_strategy rejects invalid values."""
        with pytest.raises(ValueError):
            WorkersConfig(spawn_backoff_strategy="invalid")


class TestResilienceConfigYAMLAndSerialization:
    """Tests for YAML loading and serialization."""

    def test_load_full_resilience_config_from_yaml(self, tmp_path: Path) -> None:
        """Test loading complete resilience configuration from YAML."""
        config_data = {
            "resilience": {"enabled": True},
            "workers": {
                "spawn_retry_attempts": 4,
                "spawn_backoff_strategy": "fixed",
                "spawn_backoff_base_seconds": 5,
                "spawn_backoff_max_seconds": 60,
                "task_stale_timeout_seconds": 1200,
                "heartbeat_interval_seconds": 45,
                "heartbeat_stale_threshold": 180,
                "auto_respawn": True,
                "max_respawn_attempts": 8,
            },
        }
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ZergConfig.load(config_file)

        assert config.resilience.enabled is True
        assert config.workers.spawn_retry_attempts == 4
        assert config.workers.spawn_backoff_strategy == "fixed"
        assert config.workers.task_stale_timeout_seconds == 1200
        assert config.workers.auto_respawn is True

    def test_workers_config_resilience_fields_to_dict(self) -> None:
        """Test WorkersConfig resilience fields serialize to dict correctly."""
        config = WorkersConfig(
            spawn_retry_attempts=4,
            spawn_backoff_strategy="linear",
            auto_respawn=False,
            max_respawn_attempts=3,
        )
        data = config.model_dump()
        assert data["spawn_retry_attempts"] == 4
        assert data["spawn_backoff_strategy"] == "linear"
        assert data["auto_respawn"] is False

    def test_zerg_config_resilience_roundtrip(self, tmp_path: Path) -> None:
        """Test ZergConfig with resilience settings survives save/load roundtrip."""
        original = ZergConfig()
        original.resilience.enabled = True
        original.workers.spawn_retry_attempts = 7
        original.workers.task_stale_timeout_seconds = 800
        original.workers.auto_respawn = False

        config_file = tmp_path / "config.yaml"
        original.save(config_file)
        loaded = ZergConfig.load(config_file)

        assert loaded.resilience.enabled is True
        assert loaded.workers.spawn_retry_attempts == 7
        assert loaded.workers.task_stale_timeout_seconds == 800
        assert loaded.workers.auto_respawn is False
