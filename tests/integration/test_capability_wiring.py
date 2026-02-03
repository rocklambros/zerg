"""Integration tests for capability wiring: rush -> Orchestrator -> WorkerManager -> launcher.

Verifies the full chain from ResolvedCapabilities through Orchestrator construction,
WorkerManager env injection, and ContextEngineeringPlugin section builders.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from zerg.capability_resolver import ResolvedCapabilities
from zerg.context_plugin import ContextEngineeringPlugin
from zerg.plugin_config import ContextEngineeringConfig

# ---------------------------------------------------------------------------
# Orchestrator -> WorkerManager wiring
# ---------------------------------------------------------------------------


class TestOrchestratorCapabilityWiring:
    """Verify Orchestrator passes capabilities down to WorkerManager."""

    @pytest.fixture
    def mock_orchestrator_deps(self):
        """Mock all Orchestrator dependencies so __init__ completes."""
        with (
            patch("zerg.orchestrator.StateManager") as state_mock,
            patch("zerg.orchestrator.LevelController") as levels_mock,
            patch("zerg.orchestrator.TaskParser") as parser_mock,
            patch("zerg.orchestrator.GateRunner") as gates_mock,
            patch("zerg.orchestrator.WorktreeManager") as worktree_mock,
            patch("zerg.orchestrator.ContainerManager") as container_mock,
            patch("zerg.orchestrator.PortAllocator") as ports_mock,
            patch("zerg.orchestrator.MergeCoordinator") as merge_mock,
            patch("zerg.orchestrator.TaskSyncBridge") as task_sync_mock,
            patch("zerg.orchestrator.SubprocessLauncher") as subprocess_launcher_mock,
            patch("zerg.orchestrator.ContainerLauncher") as container_launcher_mock,
            patch("zerg.orchestrator.setup_structured_logging") as log_mock,
        ):
            state = MagicMock()
            state.load.return_value = {}
            state.get_task_status.return_value = None
            state.get_task_retry_count.return_value = 0
            state_mock.return_value = state

            levels = MagicMock()
            levels.current_level = 1
            levels_mock.return_value = levels

            parser = MagicMock()
            parser.get_all_tasks.return_value = []
            parser.total_tasks = 0
            parser.levels = [1]
            parser_mock.return_value = parser

            gates_mock.return_value = MagicMock()
            worktree_mock.return_value = MagicMock()
            container_mock.return_value = MagicMock()
            ports_mock.return_value = MagicMock()
            merge_mock.return_value = MagicMock()
            task_sync_mock.return_value = MagicMock()
            subprocess_launcher_mock.return_value = MagicMock()
            container_launcher_mock.return_value = MagicMock()
            log_mock.return_value = MagicMock()

            yield {
                "state": state,
                "levels": levels,
                "parser": parser,
                "subprocess_launcher": subprocess_launcher_mock,
            }

    def test_orchestrator_passes_capabilities_to_worker_manager(self, mock_orchestrator_deps):
        """Orchestrator(capabilities=...) flows through to _worker_manager._capabilities."""
        from zerg.orchestrator import Orchestrator

        caps = ResolvedCapabilities(tdd=True, depth_tier="think")
        orch = Orchestrator(
            feature="test-feat",
            repo_path="/tmp",
            capabilities=caps,
        )
        assert orch._worker_manager._capabilities is caps
        assert orch._worker_manager._capabilities.tdd is True
        assert orch._worker_manager._capabilities.depth_tier == "think"


# ---------------------------------------------------------------------------
# WorkerManager -> launcher.spawn(env=) wiring
# ---------------------------------------------------------------------------


class TestWorkerManagerSpawnEnv:
    """Verify WorkerManager.spawn_worker() passes ZERG_* env to launcher.spawn()."""

    def test_worker_manager_spawn_passes_env(self):
        """spawn_worker() calls launcher.spawn with env= containing ZERG_* vars."""
        from zerg.worker_manager import WorkerManager

        caps = ResolvedCapabilities(tdd=True, compact=True, depth_tier="think")

        launcher = MagicMock()
        spawn_result = MagicMock()
        spawn_result.success = True
        spawn_result.handle = MagicMock()
        spawn_result.handle.container_id = None
        launcher.spawn.return_value = spawn_result

        ports = MagicMock()
        ports.allocate_one.return_value = 9000

        worktrees = MagicMock()
        wt_info = MagicMock()
        wt_info.path = "/tmp/wt"
        wt_info.branch = "feature-branch"
        worktrees.create.return_value = wt_info

        state = MagicMock()
        plugin_registry = MagicMock()
        plugin_registry.emit.return_value = None

        wm = WorkerManager(
            feature="test-feat",
            config=MagicMock(),
            state=state,
            levels=MagicMock(),
            parser=MagicMock(),
            launcher=launcher,
            worktrees=worktrees,
            ports=ports,
            assigner=None,
            plugin_registry=plugin_registry,
            workers={},
            on_task_complete=[],
            capabilities=caps,
        )

        wm.spawn_worker(worker_id=1)

        # Verify launcher.spawn was called with env= containing ZERG_* keys
        launcher.spawn.assert_called_once()
        call_kwargs = launcher.spawn.call_args
        env_arg = call_kwargs.kwargs.get("env") or call_kwargs[1].get("env")
        assert env_arg is not None, "launcher.spawn was not called with env="
        assert "ZERG_TDD_MODE" in env_arg
        assert env_arg["ZERG_TDD_MODE"] == "1"
        assert "ZERG_COMPACT_MODE" in env_arg
        assert env_arg["ZERG_COMPACT_MODE"] == "1"
        assert "ZERG_ANALYSIS_DEPTH" in env_arg
        assert env_arg["ZERG_ANALYSIS_DEPTH"] == "think"


# ---------------------------------------------------------------------------
# ContextEngineeringPlugin section builders (env var driven)
# ---------------------------------------------------------------------------


class TestContextPluginDepthSection:
    """Verify _build_depth_section reads ZERG_ANALYSIS_DEPTH env var."""

    def test_depth_section_contains_tier(self, monkeypatch):
        monkeypatch.setenv("ZERG_ANALYSIS_DEPTH", "think")
        plugin = ContextEngineeringPlugin(ContextEngineeringConfig())
        section = plugin._build_depth_section(max_tokens=500)
        assert "think" in section.lower()

    def test_depth_section_empty_for_standard(self, monkeypatch):
        monkeypatch.setenv("ZERG_ANALYSIS_DEPTH", "standard")
        plugin = ContextEngineeringPlugin(ContextEngineeringConfig())
        section = plugin._build_depth_section(max_tokens=500)
        assert section == ""


class TestContextPluginTddSection:
    """Verify _build_tdd_section reads ZERG_TDD_MODE env var."""

    def test_tdd_section_contains_red(self, monkeypatch):
        monkeypatch.setenv("ZERG_TDD_MODE", "1")
        plugin = ContextEngineeringPlugin(ContextEngineeringConfig())
        section = plugin._build_tdd_section(max_tokens=500)
        assert "RED" in section

    def test_tdd_section_empty_when_off(self, monkeypatch):
        monkeypatch.setenv("ZERG_TDD_MODE", "0")
        plugin = ContextEngineeringPlugin(ContextEngineeringConfig())
        section = plugin._build_tdd_section(max_tokens=500)
        assert section == ""


class TestContextPluginEfficiencySection:
    """Verify _build_efficiency_section reads ZERG_COMPACT_MODE env var."""

    def test_efficiency_section_contains_compact(self, monkeypatch):
        monkeypatch.setenv("ZERG_COMPACT_MODE", "1")
        plugin = ContextEngineeringPlugin(ContextEngineeringConfig())
        section = plugin._build_efficiency_section()
        assert "Compact" in section

    def test_efficiency_section_empty_when_off(self, monkeypatch):
        monkeypatch.setenv("ZERG_COMPACT_MODE", "0")
        plugin = ContextEngineeringPlugin(ContextEngineeringConfig())
        section = plugin._build_efficiency_section()
        assert section == ""
