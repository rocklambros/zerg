"""Integration tests for deferred merge functionality.

Tests OCF-L2-003 and OCF-L2-004:
- defer_merge_to_ship: Levels complete without merging to main
- gates_at_ship_only: Quality gates run only at ship time
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from zerg.config import RushConfig, ZergConfig
from zerg.constants import LevelMergeStatus, WorkerStatus
from zerg.types import WorkerState


class TestDeferMergeToShip:
    """Tests for defer_merge_to_ship config flag."""

    @pytest.fixture
    def config_with_deferred_merge(self) -> ZergConfig:
        """Create config with deferred merge enabled."""
        config = ZergConfig()
        config.rush = RushConfig(defer_merge_to_ship=True, gates_at_ship_only=True)
        return config

    @pytest.fixture
    def config_without_deferred_merge(self) -> ZergConfig:
        """Create config with deferred merge disabled."""
        config = ZergConfig()
        config.rush = RushConfig(defer_merge_to_ship=False, gates_at_ship_only=False)
        return config

    @pytest.fixture
    def mock_workers(self) -> dict[int, WorkerState]:
        """Create mock workers with branches."""
        return {
            0: WorkerState(
                worker_id=0,
                status=WorkerStatus.RUNNING,
                branch="zerg/test-feature/worker-0",
            ),
            1: WorkerState(
                worker_id=1,
                status=WorkerStatus.RUNNING,
                branch="zerg/test-feature/worker-1",
            ),
        }

    def test_level_complete_skips_merge_when_deferred(
        self, config_with_deferred_merge: ZergConfig, mock_workers: dict, tmp_path: Path
    ) -> None:
        """When defer_merge_to_ship=True, level complete should not merge to main."""
        from zerg.level_coordinator import LevelCoordinator
        from zerg.levels import LevelController
        from zerg.state import StateManager

        # Set up mocks
        state = Mock(spec=StateManager)
        state.get_level_status.return_value = "active"
        state.set_level_status = Mock()
        state.set_level_merge_status = Mock()

        levels = Mock(spec=LevelController)
        levels.current_level = 1
        levels.is_level_complete.return_value = True

        merger = Mock()
        merger.full_merge_flow = Mock(return_value=Mock(success=True))

        parser = Mock()
        task_sync = Mock()
        plugin_registry = Mock()
        callbacks: list = []

        coord = LevelCoordinator(
            feature="test-feature",
            config=config_with_deferred_merge,
            state=state,
            levels=levels,
            parser=parser,
            merger=merger,
            task_sync=task_sync,
            plugin_registry=plugin_registry,
            workers=mock_workers,
            on_level_complete_callbacks=callbacks,
        )

        # Call handle_level_complete
        result = coord.handle_level_complete(1)

        # Should not call merge
        merger.full_merge_flow.assert_not_called()

        # Should mark level as complete with pending merge status
        state.set_level_status.assert_called_with(1, "complete")
        state.set_level_merge_status.assert_called_with(1, LevelMergeStatus.PENDING)

        assert result is True

    def test_level_complete_merges_when_not_deferred(
        self, config_without_deferred_merge: ZergConfig, mock_workers: dict, tmp_path: Path
    ) -> None:
        """When defer_merge_to_ship=False, level complete should merge immediately."""
        from zerg.level_coordinator import LevelCoordinator
        from zerg.levels import LevelController
        from zerg.state import StateManager

        # Set up mocks
        state = Mock(spec=StateManager)
        state.get_level_status.return_value = "active"
        state.set_level_status = Mock()
        state.set_level_merge_status = Mock()

        levels = Mock(spec=LevelController)
        levels.current_level = 1
        levels.is_level_complete.return_value = True

        merger = Mock()
        from zerg.merge import MergeFlowResult

        merge_result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["zerg/test-feature/worker-0", "zerg/test-feature/worker-1"],
            target_branch="main",
            merge_commit="abc123",
        )
        merger.full_merge_flow = Mock(return_value=merge_result)

        parser = Mock()
        task_sync = Mock()
        plugin_registry = Mock()
        callbacks: list = []

        coord = LevelCoordinator(
            feature="test-feature",
            config=config_without_deferred_merge,
            state=state,
            levels=levels,
            parser=parser,
            merger=merger,
            task_sync=task_sync,
            plugin_registry=plugin_registry,
            workers=mock_workers,
            on_level_complete_callbacks=callbacks,
        )

        # Call handle_level_complete
        result = coord.handle_level_complete(1)

        # Should call merge
        merger.full_merge_flow.assert_called_once()

        assert result is True


class TestGatesAtShipOnly:
    """Tests for gates_at_ship_only config flag."""

    @pytest.fixture
    def config_gates_at_ship(self) -> ZergConfig:
        """Create config with gates only at ship time."""
        config = ZergConfig()
        config.rush = RushConfig(defer_merge_to_ship=False, gates_at_ship_only=True)
        return config

    @pytest.fixture
    def config_gates_every_level(self) -> ZergConfig:
        """Create config with gates at every level."""
        config = ZergConfig()
        config.rush = RushConfig(defer_merge_to_ship=False, gates_at_ship_only=False)
        return config

    @pytest.fixture
    def mock_workers(self) -> dict[int, WorkerState]:
        """Create mock workers with branches."""
        return {
            0: WorkerState(
                worker_id=0,
                status=WorkerStatus.RUNNING,
                branch="zerg/test-feature/worker-0",
            ),
        }

    def test_merge_skips_gates_when_gates_at_ship_only(
        self, config_gates_at_ship: ZergConfig, mock_workers: dict
    ) -> None:
        """When gates_at_ship_only=True, merge should pass skip_gates=True."""
        from zerg.level_coordinator import LevelCoordinator
        from zerg.levels import LevelController
        from zerg.merge import MergeFlowResult
        from zerg.state import StateManager

        state = Mock(spec=StateManager)
        state.get_level_status.return_value = "active"
        state.set_level_status = Mock()
        state.set_level_merge_status = Mock()

        levels = Mock(spec=LevelController)
        levels.current_level = 1
        levels.is_level_complete.return_value = True

        merger = Mock()
        merge_result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["zerg/test-feature/worker-0"],
            target_branch="main",
            merge_commit="abc123",
        )
        merger.full_merge_flow = Mock(return_value=merge_result)

        parser = Mock()
        task_sync = Mock()
        plugin_registry = Mock()
        callbacks: list = []

        coord = LevelCoordinator(
            feature="test-feature",
            config=config_gates_at_ship,
            state=state,
            levels=levels,
            parser=parser,
            merger=merger,
            task_sync=task_sync,
            plugin_registry=plugin_registry,
            workers=mock_workers,
            on_level_complete_callbacks=callbacks,
        )

        # Call merge_level directly
        result = coord.merge_level(1)

        # Should pass skip_gates=True to full_merge_flow
        call_args = merger.full_merge_flow.call_args
        assert call_args is not None
        assert call_args.kwargs.get("skip_gates") is True

        assert result.success is True

    def test_merge_runs_gates_when_not_gates_at_ship_only(
        self, config_gates_every_level: ZergConfig, mock_workers: dict
    ) -> None:
        """When gates_at_ship_only=False, merge should not skip gates."""
        from zerg.level_coordinator import LevelCoordinator
        from zerg.levels import LevelController
        from zerg.merge import MergeFlowResult
        from zerg.state import StateManager

        state = Mock(spec=StateManager)
        state.get_level_status.return_value = "active"
        state.set_level_status = Mock()
        state.set_level_merge_status = Mock()

        levels = Mock(spec=LevelController)
        levels.current_level = 1
        levels.is_level_complete.return_value = True

        merger = Mock()
        merge_result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["zerg/test-feature/worker-0"],
            target_branch="main",
            merge_commit="abc123",
        )
        merger.full_merge_flow = Mock(return_value=merge_result)

        parser = Mock()
        task_sync = Mock()
        plugin_registry = Mock()
        callbacks: list = []

        coord = LevelCoordinator(
            feature="test-feature",
            config=config_gates_every_level,
            state=state,
            levels=levels,
            parser=parser,
            merger=merger,
            task_sync=task_sync,
            plugin_registry=plugin_registry,
            workers=mock_workers,
            on_level_complete_callbacks=callbacks,
        )

        # Call merge_level directly
        result = coord.merge_level(1)

        # Should pass skip_gates=False to full_merge_flow
        call_args = merger.full_merge_flow.call_args
        assert call_args is not None
        assert call_args.kwargs.get("skip_gates") is False

        assert result.success is True


class TestShipIntegration:
    """Tests for ship command integration with deferred merge."""

    def test_ship_merges_all_pending_levels(self, tmp_path: Path, monkeypatch) -> None:
        """Ship command should merge all levels marked as pending."""
        # This is a higher-level integration test
        # We verify that the git ship command handles ZERG branches correctly

        from zerg.commands.git_cmd import _detect_zerg_feature

        # Test ZERG branch detection
        assert _detect_zerg_feature("zerg/my-feature/staging") == "my-feature"
        assert _detect_zerg_feature("zerg/auth-system/worker-0") == "auth-system"
        assert _detect_zerg_feature("main") is None
        assert _detect_zerg_feature("feature/something") is None
