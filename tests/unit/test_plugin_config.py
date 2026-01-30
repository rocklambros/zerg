"""Unit tests for zerg.plugin_config models."""

import pytest
from pydantic import ValidationError

from zerg.plugin_config import HookConfig, LauncherPluginConfig, PluginGateConfig, PluginsConfig


def test_plugins_config_defaults():
    config = PluginsConfig()
    assert config.enabled is True
    assert config.hooks == []
    assert config.quality_gates == []
    assert config.launchers == []


def test_hook_config_creation():
    hook = HookConfig(event="task_started", command="echo hi")
    assert hook.event == "task_started"
    assert hook.command == "echo hi"
    assert hook.timeout == 60


def test_gate_config_creation():
    gate = PluginGateConfig(name="lint", command="ruff check")
    assert gate.name == "lint"
    assert gate.command == "ruff check"
    assert gate.required is False
    assert gate.timeout == 300


def test_launcher_config_creation():
    launcher = LauncherPluginConfig(name="k8s", entry_point="pkg:K8sLauncher")
    assert launcher.name == "k8s"
    assert launcher.entry_point == "pkg:K8sLauncher"


def test_plugins_config_with_hooks():
    hooks = [
        HookConfig(event="task_started", command="echo start"),
        HookConfig(event="task_completed", command="echo done", timeout=120),
    ]
    config = PluginsConfig(hooks=hooks)
    assert len(config.hooks) == 2
    assert config.hooks[0].event == "task_started"
    assert config.hooks[1].timeout == 120


def test_plugins_config_with_gates():
    gates = [
        PluginGateConfig(name="lint", command="ruff check", required=True),
        PluginGateConfig(name="typecheck", command="mypy ."),
    ]
    config = PluginsConfig(quality_gates=gates)
    assert len(config.quality_gates) == 2
    assert config.quality_gates[0].required is True
    assert config.quality_gates[1].name == "typecheck"


def test_plugins_config_serialization():
    config = PluginsConfig(
        enabled=False,
        hooks=[HookConfig(event="pre_merge", command="./check.sh", timeout=30)],
        quality_gates=[PluginGateConfig(name="security", command="bandit -r .", required=True)],
        launchers=[LauncherPluginConfig(name="docker", entry_point="zerg.docker:DockerLauncher")],
    )
    data = config.model_dump()
    restored = PluginsConfig(**data)
    assert restored == config
    assert data["enabled"] is False
    assert data["hooks"][0]["event"] == "pre_merge"
    assert data["quality_gates"][0]["required"] is True
    assert data["launchers"][0]["entry_point"] == "zerg.docker:DockerLauncher"


def test_hook_config_timeout_validation():
    with pytest.raises(ValidationError):
        HookConfig(event="test", command="echo", timeout=0)

    with pytest.raises(ValidationError):
        HookConfig(event="test", command="echo", timeout=601)

    # Boundary values should succeed
    hook_min = HookConfig(event="test", command="echo", timeout=1)
    assert hook_min.timeout == 1
    hook_max = HookConfig(event="test", command="echo", timeout=600)
    assert hook_max.timeout == 600


def test_gate_config_required_default():
    gate = PluginGateConfig(name="check", command="true")
    assert gate.required is False


def test_plugins_config_disabled():
    config = PluginsConfig(enabled=False)
    assert config.enabled is False
    assert config.hooks == []
    assert config.quality_gates == []
    assert config.launchers == []
