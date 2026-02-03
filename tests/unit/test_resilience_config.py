"""Unit tests for resilience configuration fields in ZERG config module.

Tests for FR-1 (spawn retry), FR-2 (task timeout), FR-3 (heartbeat),
and FR-6 (auto-respawn) configuration options.
"""

from pathlib import Path

import pytest
import yaml

from zerg.config import ResilienceConfig, WorkersConfig, ZergConfig


class TestResilienceConfig:
    """Tests for ResilienceConfig model."""

    def test_enabled_defaults_to_true(self) -> None:
        """Test that ResilienceConfig.enabled defaults to True (FR-1 through FR-9)."""
        config = ResilienceConfig()
        assert config.enabled is True

    def test_enabled_can_be_disabled(self) -> None:
        """Test that resilience can be disabled via config."""
        config = ResilienceConfig(enabled=False)
        assert config.enabled is False

    def test_resilience_config_in_zerg_config(self) -> None:
        """Test that ZergConfig has resilience attribute."""
        config = ZergConfig()
        assert hasattr(config, "resilience")
        assert isinstance(config.resilience, ResilienceConfig)
        assert config.resilience.enabled is True


class TestWorkersConfigSpawnRetry:
    """Tests for WorkersConfig spawn retry fields (FR-1)."""

    def test_spawn_retry_attempts_default(self) -> None:
        """Test spawn_retry_attempts defaults to 3."""
        config = WorkersConfig()
        assert config.spawn_retry_attempts == 3

    def test_spawn_retry_attempts_custom(self) -> None:
        """Test spawn_retry_attempts can be customized."""
        config = WorkersConfig(spawn_retry_attempts=5)
        assert config.spawn_retry_attempts == 5

    def test_spawn_retry_attempts_minimum_valid(self) -> None:
        """Test spawn_retry_attempts accepts minimum value 0."""
        config = WorkersConfig(spawn_retry_attempts=0)
        assert config.spawn_retry_attempts == 0

    def test_spawn_retry_attempts_maximum_valid(self) -> None:
        """Test spawn_retry_attempts accepts maximum value 10."""
        config = WorkersConfig(spawn_retry_attempts=10)
        assert config.spawn_retry_attempts == 10

    def test_spawn_retry_attempts_below_minimum_rejected(self) -> None:
        """Test spawn_retry_attempts rejects values below 0."""
        with pytest.raises(ValueError):
            WorkersConfig(spawn_retry_attempts=-1)

    def test_spawn_retry_attempts_above_maximum_rejected(self) -> None:
        """Test spawn_retry_attempts rejects values above 10."""
        with pytest.raises(ValueError):
            WorkersConfig(spawn_retry_attempts=11)

    def test_spawn_backoff_strategy_default(self) -> None:
        """Test spawn_backoff_strategy defaults to exponential."""
        config = WorkersConfig()
        assert config.spawn_backoff_strategy == "exponential"

    def test_spawn_backoff_strategy_valid_values(self) -> None:
        """Test spawn_backoff_strategy accepts all valid values."""
        for strategy in ["exponential", "linear", "fixed"]:
            config = WorkersConfig(spawn_backoff_strategy=strategy)
            assert config.spawn_backoff_strategy == strategy

    def test_spawn_backoff_strategy_invalid_rejected(self) -> None:
        """Test spawn_backoff_strategy rejects invalid values."""
        with pytest.raises(ValueError):
            WorkersConfig(spawn_backoff_strategy="invalid")

    def test_spawn_backoff_base_seconds_default(self) -> None:
        """Test spawn_backoff_base_seconds defaults to 2."""
        config = WorkersConfig()
        assert config.spawn_backoff_base_seconds == 2

    def test_spawn_backoff_base_seconds_custom(self) -> None:
        """Test spawn_backoff_base_seconds can be customized."""
        config = WorkersConfig(spawn_backoff_base_seconds=5)
        assert config.spawn_backoff_base_seconds == 5

    def test_spawn_backoff_base_seconds_minimum_valid(self) -> None:
        """Test spawn_backoff_base_seconds accepts minimum value 1."""
        config = WorkersConfig(spawn_backoff_base_seconds=1)
        assert config.spawn_backoff_base_seconds == 1

    def test_spawn_backoff_base_seconds_maximum_valid(self) -> None:
        """Test spawn_backoff_base_seconds accepts maximum value 60."""
        config = WorkersConfig(spawn_backoff_base_seconds=60)
        assert config.spawn_backoff_base_seconds == 60

    def test_spawn_backoff_base_seconds_below_minimum_rejected(self) -> None:
        """Test spawn_backoff_base_seconds rejects values below 1."""
        with pytest.raises(ValueError):
            WorkersConfig(spawn_backoff_base_seconds=0)

    def test_spawn_backoff_base_seconds_above_maximum_rejected(self) -> None:
        """Test spawn_backoff_base_seconds rejects values above 60."""
        with pytest.raises(ValueError):
            WorkersConfig(spawn_backoff_base_seconds=61)

    def test_spawn_backoff_max_seconds_default(self) -> None:
        """Test spawn_backoff_max_seconds defaults to 30."""
        config = WorkersConfig()
        assert config.spawn_backoff_max_seconds == 30

    def test_spawn_backoff_max_seconds_custom(self) -> None:
        """Test spawn_backoff_max_seconds can be customized."""
        config = WorkersConfig(spawn_backoff_max_seconds=60)
        assert config.spawn_backoff_max_seconds == 60

    def test_spawn_backoff_max_seconds_minimum_valid(self) -> None:
        """Test spawn_backoff_max_seconds accepts minimum value 1."""
        config = WorkersConfig(spawn_backoff_max_seconds=1)
        assert config.spawn_backoff_max_seconds == 1

    def test_spawn_backoff_max_seconds_maximum_valid(self) -> None:
        """Test spawn_backoff_max_seconds accepts maximum value 300."""
        config = WorkersConfig(spawn_backoff_max_seconds=300)
        assert config.spawn_backoff_max_seconds == 300

    def test_spawn_backoff_max_seconds_below_minimum_rejected(self) -> None:
        """Test spawn_backoff_max_seconds rejects values below 1."""
        with pytest.raises(ValueError):
            WorkersConfig(spawn_backoff_max_seconds=0)

    def test_spawn_backoff_max_seconds_above_maximum_rejected(self) -> None:
        """Test spawn_backoff_max_seconds rejects values above 300."""
        with pytest.raises(ValueError):
            WorkersConfig(spawn_backoff_max_seconds=301)


class TestWorkersConfigTaskTimeout:
    """Tests for WorkersConfig task timeout fields (FR-2)."""

    def test_task_stale_timeout_seconds_default(self) -> None:
        """Test task_stale_timeout_seconds defaults to 600 (10 minutes)."""
        config = WorkersConfig()
        assert config.task_stale_timeout_seconds == 600

    def test_task_stale_timeout_seconds_custom(self) -> None:
        """Test task_stale_timeout_seconds can be customized."""
        config = WorkersConfig(task_stale_timeout_seconds=1200)
        assert config.task_stale_timeout_seconds == 1200

    def test_task_stale_timeout_seconds_minimum_valid(self) -> None:
        """Test task_stale_timeout_seconds accepts minimum value 60."""
        config = WorkersConfig(task_stale_timeout_seconds=60)
        assert config.task_stale_timeout_seconds == 60

    def test_task_stale_timeout_seconds_maximum_valid(self) -> None:
        """Test task_stale_timeout_seconds accepts maximum value 3600."""
        config = WorkersConfig(task_stale_timeout_seconds=3600)
        assert config.task_stale_timeout_seconds == 3600

    def test_task_stale_timeout_seconds_below_minimum_rejected(self) -> None:
        """Test task_stale_timeout_seconds rejects values below 60."""
        with pytest.raises(ValueError):
            WorkersConfig(task_stale_timeout_seconds=59)

    def test_task_stale_timeout_seconds_above_maximum_rejected(self) -> None:
        """Test task_stale_timeout_seconds rejects values above 3600."""
        with pytest.raises(ValueError):
            WorkersConfig(task_stale_timeout_seconds=3601)


class TestWorkersConfigHeartbeat:
    """Tests for WorkersConfig heartbeat fields (FR-3)."""

    def test_heartbeat_interval_seconds_default(self) -> None:
        """Test heartbeat_interval_seconds defaults to 30."""
        config = WorkersConfig()
        assert config.heartbeat_interval_seconds == 30

    def test_heartbeat_interval_seconds_custom(self) -> None:
        """Test heartbeat_interval_seconds can be customized."""
        config = WorkersConfig(heartbeat_interval_seconds=15)
        assert config.heartbeat_interval_seconds == 15

    def test_heartbeat_interval_seconds_minimum_valid(self) -> None:
        """Test heartbeat_interval_seconds accepts minimum value 5."""
        config = WorkersConfig(heartbeat_interval_seconds=5)
        assert config.heartbeat_interval_seconds == 5

    def test_heartbeat_interval_seconds_maximum_valid(self) -> None:
        """Test heartbeat_interval_seconds accepts maximum value 300."""
        config = WorkersConfig(heartbeat_interval_seconds=300)
        assert config.heartbeat_interval_seconds == 300

    def test_heartbeat_interval_seconds_below_minimum_rejected(self) -> None:
        """Test heartbeat_interval_seconds rejects values below 5."""
        with pytest.raises(ValueError):
            WorkersConfig(heartbeat_interval_seconds=4)

    def test_heartbeat_interval_seconds_above_maximum_rejected(self) -> None:
        """Test heartbeat_interval_seconds rejects values above 300."""
        with pytest.raises(ValueError):
            WorkersConfig(heartbeat_interval_seconds=301)

    def test_heartbeat_stale_threshold_default(self) -> None:
        """Test heartbeat_stale_threshold defaults to 120 (2 minutes)."""
        config = WorkersConfig()
        assert config.heartbeat_stale_threshold == 120

    def test_heartbeat_stale_threshold_custom(self) -> None:
        """Test heartbeat_stale_threshold can be customized."""
        config = WorkersConfig(heartbeat_stale_threshold=180)
        assert config.heartbeat_stale_threshold == 180

    def test_heartbeat_stale_threshold_minimum_valid(self) -> None:
        """Test heartbeat_stale_threshold accepts minimum value 30."""
        config = WorkersConfig(heartbeat_stale_threshold=30)
        assert config.heartbeat_stale_threshold == 30

    def test_heartbeat_stale_threshold_maximum_valid(self) -> None:
        """Test heartbeat_stale_threshold accepts maximum value 600."""
        config = WorkersConfig(heartbeat_stale_threshold=600)
        assert config.heartbeat_stale_threshold == 600

    def test_heartbeat_stale_threshold_below_minimum_rejected(self) -> None:
        """Test heartbeat_stale_threshold rejects values below 30."""
        with pytest.raises(ValueError):
            WorkersConfig(heartbeat_stale_threshold=29)

    def test_heartbeat_stale_threshold_above_maximum_rejected(self) -> None:
        """Test heartbeat_stale_threshold rejects values above 600."""
        with pytest.raises(ValueError):
            WorkersConfig(heartbeat_stale_threshold=601)


class TestWorkersConfigAutoRespawn:
    """Tests for WorkersConfig auto-respawn fields (FR-6)."""

    def test_auto_respawn_default(self) -> None:
        """Test auto_respawn defaults to True."""
        config = WorkersConfig()
        assert config.auto_respawn is True

    def test_auto_respawn_can_be_disabled(self) -> None:
        """Test auto_respawn can be disabled."""
        config = WorkersConfig(auto_respawn=False)
        assert config.auto_respawn is False

    def test_max_respawn_attempts_default(self) -> None:
        """Test max_respawn_attempts defaults to 5."""
        config = WorkersConfig()
        assert config.max_respawn_attempts == 5

    def test_max_respawn_attempts_custom(self) -> None:
        """Test max_respawn_attempts can be customized."""
        config = WorkersConfig(max_respawn_attempts=10)
        assert config.max_respawn_attempts == 10

    def test_max_respawn_attempts_minimum_valid(self) -> None:
        """Test max_respawn_attempts accepts minimum value 0."""
        config = WorkersConfig(max_respawn_attempts=0)
        assert config.max_respawn_attempts == 0

    def test_max_respawn_attempts_maximum_valid(self) -> None:
        """Test max_respawn_attempts accepts maximum value 20."""
        config = WorkersConfig(max_respawn_attempts=20)
        assert config.max_respawn_attempts == 20

    def test_max_respawn_attempts_below_minimum_rejected(self) -> None:
        """Test max_respawn_attempts rejects values below 0."""
        with pytest.raises(ValueError):
            WorkersConfig(max_respawn_attempts=-1)

    def test_max_respawn_attempts_above_maximum_rejected(self) -> None:
        """Test max_respawn_attempts rejects values above 20."""
        with pytest.raises(ValueError):
            WorkersConfig(max_respawn_attempts=21)


class TestResilienceConfigFromYAML:
    """Tests for loading resilience config from YAML files."""

    def test_load_resilience_enabled_from_yaml(self, tmp_path: Path) -> None:
        """Test loading resilience.enabled from YAML."""
        config_data = {"resilience": {"enabled": False}}
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ZergConfig.load(config_file)
        assert config.resilience.enabled is False

    def test_load_spawn_retry_from_yaml(self, tmp_path: Path) -> None:
        """Test loading spawn retry config from YAML."""
        config_data = {
            "workers": {
                "spawn_retry_attempts": 5,
                "spawn_backoff_strategy": "linear",
                "spawn_backoff_base_seconds": 3,
                "spawn_backoff_max_seconds": 45,
            }
        }
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ZergConfig.load(config_file)
        assert config.workers.spawn_retry_attempts == 5
        assert config.workers.spawn_backoff_strategy == "linear"
        assert config.workers.spawn_backoff_base_seconds == 3
        assert config.workers.spawn_backoff_max_seconds == 45

    def test_load_task_timeout_from_yaml(self, tmp_path: Path) -> None:
        """Test loading task timeout config from YAML."""
        config_data = {"workers": {"task_stale_timeout_seconds": 900}}
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ZergConfig.load(config_file)
        assert config.workers.task_stale_timeout_seconds == 900

    def test_load_heartbeat_from_yaml(self, tmp_path: Path) -> None:
        """Test loading heartbeat config from YAML."""
        config_data = {
            "workers": {
                "heartbeat_interval_seconds": 20,
                "heartbeat_stale_threshold": 90,
            }
        }
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ZergConfig.load(config_file)
        assert config.workers.heartbeat_interval_seconds == 20
        assert config.workers.heartbeat_stale_threshold == 90

    def test_load_auto_respawn_from_yaml(self, tmp_path: Path) -> None:
        """Test loading auto-respawn config from YAML."""
        config_data = {
            "workers": {"auto_respawn": False, "max_respawn_attempts": 10}
        }
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ZergConfig.load(config_file)
        assert config.workers.auto_respawn is False
        assert config.workers.max_respawn_attempts == 10

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

        # Verify resilience master toggle
        assert config.resilience.enabled is True

        # Verify spawn retry (FR-1)
        assert config.workers.spawn_retry_attempts == 4
        assert config.workers.spawn_backoff_strategy == "fixed"
        assert config.workers.spawn_backoff_base_seconds == 5
        assert config.workers.spawn_backoff_max_seconds == 60

        # Verify task timeout (FR-2)
        assert config.workers.task_stale_timeout_seconds == 1200

        # Verify heartbeat (FR-3)
        assert config.workers.heartbeat_interval_seconds == 45
        assert config.workers.heartbeat_stale_threshold == 180

        # Verify auto-respawn (FR-6)
        assert config.workers.auto_respawn is True
        assert config.workers.max_respawn_attempts == 8


class TestResilienceConfigToDict:
    """Tests for resilience config serialization to dict."""

    def test_resilience_config_to_dict(self) -> None:
        """Test ResilienceConfig serializes to dict correctly."""
        config = ResilienceConfig(enabled=False)
        data = config.model_dump()
        assert data == {"enabled": False}

    def test_workers_config_resilience_fields_to_dict(self) -> None:
        """Test WorkersConfig resilience fields serialize to dict correctly."""
        config = WorkersConfig(
            spawn_retry_attempts=4,
            spawn_backoff_strategy="linear",
            spawn_backoff_base_seconds=3,
            spawn_backoff_max_seconds=50,
            task_stale_timeout_seconds=900,
            heartbeat_interval_seconds=20,
            heartbeat_stale_threshold=100,
            auto_respawn=False,
            max_respawn_attempts=3,
        )
        data = config.model_dump()

        assert data["spawn_retry_attempts"] == 4
        assert data["spawn_backoff_strategy"] == "linear"
        assert data["spawn_backoff_base_seconds"] == 3
        assert data["spawn_backoff_max_seconds"] == 50
        assert data["task_stale_timeout_seconds"] == 900
        assert data["heartbeat_interval_seconds"] == 20
        assert data["heartbeat_stale_threshold"] == 100
        assert data["auto_respawn"] is False
        assert data["max_respawn_attempts"] == 3

    def test_zerg_config_resilience_roundtrip(self, tmp_path: Path) -> None:
        """Test ZergConfig with resilience settings survives save/load roundtrip."""
        original = ZergConfig()
        original.resilience.enabled = True
        original.workers.spawn_retry_attempts = 7
        original.workers.spawn_backoff_strategy = "exponential"
        original.workers.task_stale_timeout_seconds = 800
        original.workers.heartbeat_interval_seconds = 25
        original.workers.auto_respawn = False
        original.workers.max_respawn_attempts = 15

        config_file = tmp_path / "config.yaml"
        original.save(config_file)

        loaded = ZergConfig.load(config_file)

        assert loaded.resilience.enabled is True
        assert loaded.workers.spawn_retry_attempts == 7
        assert loaded.workers.spawn_backoff_strategy == "exponential"
        assert loaded.workers.task_stale_timeout_seconds == 800
        assert loaded.workers.heartbeat_interval_seconds == 25
        assert loaded.workers.auto_respawn is False
        assert loaded.workers.max_respawn_attempts == 15


class TestResilienceConfigValidationEdgeCases:
    """Tests for resilience config validation edge cases."""

    def test_spawn_backoff_base_exceeds_max_is_valid(self) -> None:
        """Test that base > max is allowed (capped at runtime, not config time)."""
        # This should not raise - runtime logic caps at max
        config = WorkersConfig(
            spawn_backoff_base_seconds=50,  # Base > max (30)
            spawn_backoff_max_seconds=30,
        )
        assert config.spawn_backoff_base_seconds == 50
        assert config.spawn_backoff_max_seconds == 30

    def test_heartbeat_interval_exceeds_stale_threshold_is_valid(self) -> None:
        """Test that interval > stale threshold is allowed (might be intentional)."""
        # This configuration would make stale detection trigger immediately,
        # but it's a valid config - user might know what they're doing
        config = WorkersConfig(
            heartbeat_interval_seconds=200,  # Interval > threshold (120)
            heartbeat_stale_threshold=100,
        )
        assert config.heartbeat_interval_seconds == 200
        assert config.heartbeat_stale_threshold == 100

    def test_all_resilience_defaults_match_requirements(self) -> None:
        """Test all resilience field defaults match FR requirements."""
        config = WorkersConfig()

        # FR-1: spawn_retry_attempts default 3
        assert config.spawn_retry_attempts == 3

        # FR-1: spawn_backoff_strategy default exponential
        assert config.spawn_backoff_strategy == "exponential"

        # FR-1: spawn_backoff_base_seconds default 2
        assert config.spawn_backoff_base_seconds == 2

        # FR-1: spawn_backoff_max_seconds default 30
        assert config.spawn_backoff_max_seconds == 30

        # FR-2: task_stale_timeout_seconds default 600
        assert config.task_stale_timeout_seconds == 600

        # FR-3: heartbeat_interval_seconds default 30
        assert config.heartbeat_interval_seconds == 30

        # FR-3: heartbeat_stale_threshold default 120 (2 minutes)
        assert config.heartbeat_stale_threshold == 120

        # FR-6: auto_respawn default True
        assert config.auto_respawn is True

        # FR-6: max_respawn_attempts default 5
        assert config.max_respawn_attempts == 5

    def test_resilience_enabled_default_matches_requirements(self) -> None:
        """Test ResilienceConfig.enabled defaults to True per master toggle requirement."""
        config = ResilienceConfig()
        assert config.enabled is True


class TestZergConfigHasResilienceAttribute:
    """Tests for ZergConfig resilience integration."""

    def test_zerg_config_has_resilience_attribute(self) -> None:
        """Verify ZergConfig has resilience attribute per task requirements."""
        config = ZergConfig()
        assert hasattr(config, "resilience")

    def test_zerg_config_has_resilience_workers_fields(self) -> None:
        """Verify ZergConfig.workers has all resilience fields."""
        config = ZergConfig()

        # Spawn retry (FR-1)
        assert hasattr(config.workers, "spawn_retry_attempts")
        assert hasattr(config.workers, "spawn_backoff_strategy")
        assert hasattr(config.workers, "spawn_backoff_base_seconds")
        assert hasattr(config.workers, "spawn_backoff_max_seconds")

        # Task timeout (FR-2)
        assert hasattr(config.workers, "task_stale_timeout_seconds")

        # Heartbeat (FR-3)
        assert hasattr(config.workers, "heartbeat_interval_seconds")
        assert hasattr(config.workers, "heartbeat_stale_threshold")

        # Auto-respawn (FR-6)
        assert hasattr(config.workers, "auto_respawn")
        assert hasattr(config.workers, "max_respawn_attempts")
