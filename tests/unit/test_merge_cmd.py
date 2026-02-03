"""Comprehensive unit tests for ZERG merge command module.

Tests for zerg/commands/merge_cmd.py covering:
- detect_feature() function
- create_merge_plan() function
- show_merge_plan() function
- run_quality_gates() function
- merge_cmd() click command with all code paths
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from zerg.commands.merge_cmd import (
    create_merge_plan,
    detect_feature,
    merge_cmd,
    run_quality_gates,
    show_merge_plan,
)
from zerg.config import QualityGate, ZergConfig
from zerg.constants import GateResult, LevelMergeStatus
from zerg.merge import MergeFlowResult


@pytest.fixture
def zerg_state_dir(tmp_path: Path) -> Path:
    """Create .zerg/state directory structure."""
    state_dir = tmp_path / ".zerg" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


@pytest.fixture
def feature_state_file(zerg_state_dir: Path) -> Path:
    """Create a feature state file with workers."""
    state = {
        "feature": "test-feature",
        "current_level": 1,
        "paused": False,
        "error": None,
        "tasks": {},
        "workers": {
            "0": {
                "worker_id": 0,
                "status": "running",
                "port": 49152,
                "branch": "zerg/test-feature/worker-0",
                "started_at": datetime.now().isoformat(),
            },
            "1": {
                "worker_id": 1,
                "status": "running",
                "port": 49153,
                "branch": "zerg/test-feature/worker-1",
                "started_at": datetime.now().isoformat(),
            },
        },
        "levels": {"1": {"status": "complete", "merge_status": "pending"}},
        "execution_log": [],
    }
    state_file = zerg_state_dir / "test-feature.json"
    state_file.write_text(json.dumps(state, indent=2))
    return state_file


@pytest.fixture
def mock_state_manager() -> MagicMock:
    """Create a mock StateManager with properly mocked workers."""
    mock = MagicMock()
    mock.exists.return_value = True
    mock.get_current_level.return_value = 1
    mock.get_level_merge_status.return_value = LevelMergeStatus.COMPLETE

    class MockStatus:
        def __init__(self, value: str):
            self.value = value

    worker0 = MagicMock()
    worker0.worker_id = 0
    worker0.status = MockStatus("running")
    worker0.branch = "zerg/test-feature/worker-0"

    worker1 = MagicMock()
    worker1.worker_id = 1
    worker1.status = MockStatus("running")
    worker1.branch = "zerg/test-feature/worker-1"

    workers = {0: worker0, 1: worker1}
    mock.get_all_workers.return_value = workers
    return mock


@pytest.fixture
def mock_config() -> ZergConfig:
    """Create a mock ZergConfig with quality gates."""
    config = ZergConfig()
    config.quality_gates = [
        QualityGate(name="lint", command="ruff check .", required=True),
        QualityGate(name="test", command="pytest", required=True),
        QualityGate(name="typecheck", command="mypy .", required=False),
    ]
    return config


class TestDetectFeature:
    """Tests for detect_feature function."""

    def test_detect_feature_no_state_dir(self, tmp_path: Path, monkeypatch) -> None:
        """Test detect_feature returns None when .zerg/state does not exist."""
        monkeypatch.chdir(tmp_path)
        result = detect_feature()
        assert result is None

    def test_detect_feature_empty_state_dir(self, tmp_path: Path, zerg_state_dir: Path, monkeypatch) -> None:
        """Test detect_feature returns None when state dir is empty."""
        monkeypatch.chdir(tmp_path)
        result = detect_feature()
        assert result is None

    def test_detect_feature_single_state_file(self, tmp_path: Path, feature_state_file: Path, monkeypatch) -> None:
        """Test detect_feature returns feature name from single state file."""
        monkeypatch.chdir(tmp_path)
        result = detect_feature()
        assert result == "test-feature"

    def test_detect_feature_multiple_state_files_returns_most_recent(
        self, tmp_path: Path, zerg_state_dir: Path, monkeypatch
    ) -> None:
        """Test detect_feature returns most recently modified feature."""
        monkeypatch.chdir(tmp_path)
        old_file = zerg_state_dir / "old-feature.json"
        old_file.write_text('{"feature": "old-feature"}')
        time.sleep(0.01)
        new_file = zerg_state_dir / "new-feature.json"
        new_file.write_text('{"feature": "new-feature"}')
        result = detect_feature()
        assert result == "new-feature"


class TestCreateMergePlan:
    """Tests for create_merge_plan function."""

    def test_create_merge_plan_basic(self, mock_state_manager: MagicMock) -> None:
        """Test create_merge_plan returns correct structure."""
        plan = create_merge_plan(
            state=mock_state_manager,
            feature="test-feature",
            level=1,
            target="main",
            skip_gates=False,
        )
        assert plan["feature"] == "test-feature"
        assert plan["level"] == 1
        assert plan["target"] == "main"
        assert plan["staging_branch"] == "zerg/test-feature/staging"
        assert plan["skip_gates"] is False
        assert plan["gates"] == ["lint", "typecheck", "test"]

    def test_create_merge_plan_skip_gates(self, mock_state_manager: MagicMock) -> None:
        """Test create_merge_plan with skip_gates=True."""
        plan = create_merge_plan(
            state=mock_state_manager,
            feature="test-feature",
            level=1,
            target="main",
            skip_gates=True,
        )
        assert plan["skip_gates"] is True
        assert plan["gates"] == []

    def test_create_merge_plan_includes_branches(self, mock_state_manager: MagicMock) -> None:
        """Test create_merge_plan includes worker branches."""
        plan = create_merge_plan(
            state=mock_state_manager,
            feature="test-feature",
            level=1,
            target="main",
            skip_gates=False,
        )
        assert len(plan["branches"]) == 2
        assert plan["branches"][0]["branch"] == "zerg/test-feature/worker-0"

    def test_create_merge_plan_empty_workers(self) -> None:
        """Test create_merge_plan with no workers."""
        mock_state = MagicMock()
        mock_state.get_all_workers.return_value = {}
        plan = create_merge_plan(
            state=mock_state,
            feature="empty-feature",
            level=1,
            target="main",
            skip_gates=False,
        )
        assert plan["branches"] == []


class TestShowMergePlan:
    """Tests for show_merge_plan function."""

    def test_show_merge_plan_normal(self) -> None:
        """Test show_merge_plan displays plan correctly."""
        plan = {
            "feature": "test-feature",
            "level": 1,
            "target": "main",
            "staging_branch": "zerg/test-feature/staging",
            "branches": [{"branch": "worker-0", "worker_id": 0, "status": "running"}],
            "gates": ["lint", "test"],
            "skip_gates": False,
        }
        show_merge_plan(plan, dry_run=False)

    def test_show_merge_plan_dry_run(self) -> None:
        """Test show_merge_plan with dry_run flag."""
        plan = {
            "feature": "test-feature",
            "level": 1,
            "target": "main",
            "staging_branch": "zerg/test-feature/staging",
            "branches": [],
            "gates": ["lint"],
            "skip_gates": False,
        }
        show_merge_plan(plan, dry_run=True)

    def test_show_merge_plan_skipped_gates(self) -> None:
        """Test show_merge_plan when gates are skipped."""
        plan = {
            "feature": "test-feature",
            "level": 1,
            "target": "main",
            "staging_branch": "zerg/test-feature/staging",
            "branches": [],
            "gates": [],
            "skip_gates": True,
        }
        show_merge_plan(plan, dry_run=False)


class TestRunQualityGates:
    """Tests for run_quality_gates function."""

    def test_run_quality_gates_all_pass(self, mock_config: ZergConfig) -> None:
        """Test run_quality_gates when all gates pass."""
        with patch("zerg.commands.merge_cmd.GateRunner") as mock_runner_cls:
            mock_runner = MagicMock()
            pass_result = MagicMock()
            pass_result.result = GateResult.PASS
            mock_runner.run_gate.return_value = pass_result
            mock_runner_cls.return_value = mock_runner
            result = run_quality_gates(mock_config, "test-feature", 1)
            assert result == GateResult.PASS

    def test_run_quality_gates_one_fails(self, mock_config: ZergConfig) -> None:
        """Test run_quality_gates when one gate fails."""
        with patch("zerg.commands.merge_cmd.GateRunner") as mock_runner_cls:
            mock_runner = MagicMock()
            pass_result = MagicMock()
            pass_result.result = GateResult.PASS
            fail_result = MagicMock()
            fail_result.result = GateResult.FAIL
            mock_runner.run_gate.side_effect = [pass_result, fail_result]
            mock_runner_cls.return_value = mock_runner
            result = run_quality_gates(mock_config, "test-feature", 1)
            assert result == GateResult.FAIL

    def test_run_quality_gates_skips_non_required(self) -> None:
        """Test run_quality_gates skips non-required gates."""
        config = ZergConfig()
        config.quality_gates = [QualityGate(name="opt", command="echo", required=False)]
        with patch("zerg.commands.merge_cmd.GateRunner") as mock_runner_cls:
            mock_runner = MagicMock()
            mock_runner_cls.return_value = mock_runner
            result = run_quality_gates(config, "test-feature", 1)
            assert result == GateResult.PASS
            mock_runner.run_gate.assert_not_called()

    def test_run_quality_gates_skips_empty_command(self) -> None:
        """Test run_quality_gates skips gates with empty command."""
        config = ZergConfig()
        config.quality_gates = [QualityGate(name="empty", command="", required=True)]
        with patch("zerg.commands.merge_cmd.GateRunner") as mock_runner_cls:
            mock_runner = MagicMock()
            mock_runner_cls.return_value = mock_runner
            result = run_quality_gates(config, "test-feature", 1)
            assert result == GateResult.PASS
            mock_runner.run_gate.assert_not_called()

    def test_run_quality_gates_empty_gates(self) -> None:
        """Test run_quality_gates with no gates configured."""
        config = ZergConfig()
        config.quality_gates = []
        with patch("zerg.commands.merge_cmd.GateRunner") as mock_runner_cls:
            mock_runner = MagicMock()
            mock_runner_cls.return_value = mock_runner
            result = run_quality_gates(config, "test-feature", 1)
            assert result == GateResult.PASS


class TestMergeCmdNoFeature:
    """Tests for merge_cmd when no feature is found."""

    def test_merge_cmd_no_feature_no_state_dir(self, tmp_path: Path, monkeypatch) -> None:
        """Test merge_cmd fails when no feature can be detected."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(merge_cmd, [])
        assert result.exit_code == 1
        assert "No active feature found" in result.output

    def test_merge_cmd_no_feature_empty_state_dir(self, tmp_path: Path, zerg_state_dir: Path, monkeypatch) -> None:
        """Test merge_cmd fails when state dir is empty."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(merge_cmd, [])
        assert result.exit_code == 1
        assert "No active feature found" in result.output


class TestMergeCmdFeatureNotFound:
    """Tests for merge_cmd when specified feature does not exist."""

    def test_merge_cmd_feature_not_found(self, tmp_path: Path, zerg_state_dir: Path, monkeypatch) -> None:
        """Test merge_cmd fails when specified feature has no state."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(merge_cmd, ["--feature", "nonexistent"])
        assert result.exit_code == 1
        assert "No state found for feature" in result.output


class TestMergeCmdDryRun:
    """Tests for merge_cmd dry run mode."""

    def test_merge_cmd_dry_run_shows_plan(self, tmp_path: Path, feature_state_file: Path, monkeypatch) -> None:
        """Test merge_cmd dry run shows plan without changes."""
        monkeypatch.chdir(tmp_path)
        with patch("zerg.commands.merge_cmd.MergeCoordinator"):
            runner = CliRunner()
            result = runner.invoke(merge_cmd, ["--feature", "test-feature", "--dry-run"])
            assert result.exit_code == 0
            assert "dry run" in result.output.lower()

    def test_merge_cmd_dry_run_exits_early(self, tmp_path: Path, feature_state_file: Path, monkeypatch) -> None:
        """Test merge_cmd dry run exits without merging."""
        monkeypatch.chdir(tmp_path)
        with (
            patch("zerg.commands.merge_cmd.MergeCoordinator"),
            patch("zerg.commands.merge_cmd.Orchestrator") as mock_orch,
        ):
            runner = CliRunner()
            runner.invoke(merge_cmd, ["--feature", "test-feature", "--dry-run"])
            mock_orch.assert_not_called()


class TestMergeCmdGateFails:
    """Tests for merge_cmd when quality gates fail."""

    def test_merge_cmd_gate_failure_exits(self, tmp_path: Path, feature_state_file: Path, monkeypatch) -> None:
        """Test merge_cmd exits when quality gates fail."""
        monkeypatch.chdir(tmp_path)
        with (
            patch("zerg.commands.merge_cmd.MergeCoordinator"),
            patch("zerg.commands.merge_cmd.run_quality_gates") as mock_gates,
        ):
            mock_gates.return_value = GateResult.FAIL
            runner = CliRunner()
            result = runner.invoke(merge_cmd, ["--feature", "test-feature", "--level", "1"])
            assert result.exit_code == 1
            assert "Quality gates failed" in result.output

    def test_merge_cmd_skip_gates_bypasses_check(self, tmp_path: Path, feature_state_file: Path, monkeypatch) -> None:
        """Test merge_cmd with --skip-gates bypasses gate check."""
        monkeypatch.chdir(tmp_path)
        with (
            patch("zerg.commands.merge_cmd.MergeCoordinator"),
            patch("zerg.commands.merge_cmd.run_quality_gates") as mock_gates,
            patch("zerg.commands.merge_cmd.Orchestrator") as mock_orch_cls,
        ):
            mock_orch = MagicMock()
            mock_orch._merge_level.return_value = MergeFlowResult(
                success=True,
                level=1,
                source_branches=[],
                target_branch="main",
                merge_commit="abc123",
            )
            mock_orch_cls.return_value = mock_orch
            runner = CliRunner()
            runner.invoke(
                merge_cmd,
                ["--feature", "test-feature", "--skip-gates"],
                input="y\n",
            )
            mock_gates.assert_not_called()


class TestMergeCmdSuccess:
    """Tests for successful merge_cmd execution."""

    def test_merge_cmd_successful_merge(self, tmp_path: Path, feature_state_file: Path, monkeypatch) -> None:
        """Test merge_cmd completes successfully."""
        monkeypatch.chdir(tmp_path)
        with (
            patch("zerg.commands.merge_cmd.MergeCoordinator"),
            patch("zerg.commands.merge_cmd.run_quality_gates") as mock_gates,
            patch("zerg.commands.merge_cmd.Orchestrator") as mock_orch_cls,
        ):
            mock_gates.return_value = GateResult.PASS
            mock_orch = MagicMock()
            mock_orch._merge_level.return_value = MergeFlowResult(
                success=True,
                level=1,
                source_branches=["worker-0"],
                target_branch="main",
                merge_commit="abc123def456",
            )
            mock_orch_cls.return_value = mock_orch
            runner = CliRunner()
            result = runner.invoke(
                merge_cmd,
                ["--feature", "test-feature", "--level", "1"],
                input="y\n",
            )
            assert result.exit_code == 0
            assert "merged successfully" in result.output
            assert "abc123de" in result.output


class TestMergeCmdFailure:
    """Tests for merge_cmd failure scenarios."""

    def test_merge_cmd_merge_fails_with_error(self, tmp_path: Path, feature_state_file: Path, monkeypatch) -> None:
        """Test merge_cmd handles merge failure with error message."""
        monkeypatch.chdir(tmp_path)
        with (
            patch("zerg.commands.merge_cmd.MergeCoordinator") as mock_coord_cls,
            patch("zerg.commands.merge_cmd.run_quality_gates") as mock_gates,
            patch("zerg.commands.merge_cmd.Orchestrator") as mock_orch_cls,
        ):
            mock_gates.return_value = GateResult.PASS
            mock_orch = MagicMock()
            mock_result = MagicMock()
            mock_result.success = False
            mock_result.merge_commit = None
            mock_result.error = "Could not fast-forward"
            del mock_result.conflicts
            mock_orch._merge_level.return_value = mock_result
            mock_orch_cls.return_value = mock_orch
            mock_coord = MagicMock()
            mock_coord.full_merge_flow.return_value = MergeFlowResult(
                success=False,
                level=1,
                source_branches=[],
                target_branch="main",
                error="Could not fast-forward",
            )
            mock_coord_cls.return_value = mock_coord
            runner = CliRunner()
            result = runner.invoke(
                merge_cmd,
                ["--feature", "test-feature", "--level", "1"],
                input="y\n",
            )
            assert result.exit_code == 1
            assert "Merge failed" in result.output

    def test_merge_cmd_merge_fails_with_conflicts(self, tmp_path: Path, feature_state_file: Path, monkeypatch) -> None:
        """Test merge_cmd handles merge failure with conflicts."""
        monkeypatch.chdir(tmp_path)
        with (
            patch("zerg.commands.merge_cmd.MergeCoordinator"),
            patch("zerg.commands.merge_cmd.run_quality_gates") as mock_gates,
            patch("zerg.commands.merge_cmd.Orchestrator") as mock_orch_cls,
        ):
            mock_gates.return_value = GateResult.PASS
            mock_orch = MagicMock()
            result_obj = MagicMock()
            result_obj.success = False
            result_obj.merge_commit = None
            result_obj.error = "Merge conflict"
            result_obj.conflicts = ["src/main.py", "src/utils.py"]
            mock_orch._merge_level.return_value = result_obj
            mock_orch_cls.return_value = mock_orch
            runner = CliRunner()
            result = runner.invoke(
                merge_cmd,
                ["--feature", "test-feature", "--level", "1"],
                input="y\n",
            )
            assert result.exit_code == 1
            assert "Merge failed" in result.output
            assert "src/main.py" in result.output

    def test_merge_cmd_orchestrator_exception_fallback(
        self, tmp_path: Path, feature_state_file: Path, monkeypatch
    ) -> None:
        """Test merge_cmd falls back to MergeCoordinator on exception."""
        monkeypatch.chdir(tmp_path)
        with (
            patch("zerg.commands.merge_cmd.run_quality_gates") as mock_gates,
            patch("zerg.commands.merge_cmd.Orchestrator") as mock_orch_cls,
            patch("zerg.commands.merge_cmd.MergeCoordinator") as mock_coord_cls,
        ):
            mock_gates.return_value = GateResult.PASS
            mock_orch = MagicMock()
            mock_orch._merge_level.side_effect = RuntimeError("Orchestrator failed")
            mock_orch_cls.return_value = mock_orch
            mock_coord = MagicMock()
            mock_coord.full_merge_flow.return_value = MergeFlowResult(
                success=True,
                level=1,
                source_branches=[],
                target_branch="main",
                merge_commit="fallback123",
            )
            mock_coord_cls.return_value = mock_coord
            runner = CliRunner()
            result = runner.invoke(
                merge_cmd,
                ["--feature", "test-feature", "--level", "1"],
                input="y\n",
            )
            assert "merged successfully" in result.output

    def test_merge_cmd_fallback_fails(self, tmp_path: Path, feature_state_file: Path, monkeypatch) -> None:
        """Test merge_cmd handles fallback MergeCoordinator failure."""
        monkeypatch.chdir(tmp_path)
        with (
            patch("zerg.commands.merge_cmd.run_quality_gates") as mock_gates,
            patch("zerg.commands.merge_cmd.Orchestrator") as mock_orch_cls,
            patch("zerg.commands.merge_cmd.MergeCoordinator") as mock_coord_cls,
        ):
            mock_gates.return_value = GateResult.PASS
            mock_orch = MagicMock()
            mock_orch._merge_level.side_effect = RuntimeError("Orchestrator failed")
            mock_orch_cls.return_value = mock_orch
            mock_coord = MagicMock()
            mock_coord.full_merge_flow.return_value = MergeFlowResult(
                success=False,
                level=1,
                source_branches=[],
                target_branch="main",
                error="Fallback also failed",
            )
            mock_coord_cls.return_value = mock_coord
            runner = CliRunner()
            result = runner.invoke(
                merge_cmd,
                ["--feature", "test-feature", "--level", "1"],
                input="y\n",
            )
            assert result.exit_code == 1
            assert "Merge failed" in result.output

    def test_merge_cmd_fallback_with_conflicts(self, tmp_path: Path, feature_state_file: Path, monkeypatch) -> None:
        """Test merge_cmd handles fallback with conflicts."""
        monkeypatch.chdir(tmp_path)
        with (
            patch("zerg.commands.merge_cmd.run_quality_gates") as mock_gates,
            patch("zerg.commands.merge_cmd.Orchestrator") as mock_orch_cls,
            patch("zerg.commands.merge_cmd.MergeCoordinator") as mock_coord_cls,
        ):
            mock_gates.return_value = GateResult.PASS
            mock_orch = MagicMock()
            mock_orch._merge_level.side_effect = RuntimeError("Orchestrator failed")
            mock_orch_cls.return_value = mock_orch
            mock_coord = MagicMock()
            mock_result = MagicMock()
            mock_result.success = False
            mock_result.conflicts = ["conflict.py"]
            mock_coord.full_merge_flow.return_value = mock_result
            mock_coord_cls.return_value = mock_coord
            runner = CliRunner()
            result = runner.invoke(
                merge_cmd,
                ["--feature", "test-feature", "--level", "1"],
                input="y\n",
            )
            assert result.exit_code == 1
            assert "conflict.py" in result.output


class TestMergeCmdUserAbort:
    """Tests for merge_cmd user abort scenarios."""

    def test_merge_cmd_user_aborts(self, tmp_path: Path, feature_state_file: Path, monkeypatch) -> None:
        """Test merge_cmd handles user abort."""
        monkeypatch.chdir(tmp_path)
        with (
            patch("zerg.commands.merge_cmd.MergeCoordinator"),
            patch("zerg.commands.merge_cmd.run_quality_gates") as mock_gates,
        ):
            mock_gates.return_value = GateResult.PASS
            runner = CliRunner()
            result = runner.invoke(merge_cmd, ["--feature", "test-feature"], input="n\n")
            assert "Aborted" in result.output


class TestMergeCmdTargetBranch:
    """Tests for merge_cmd target branch handling."""

    def test_merge_cmd_default_target(self, tmp_path: Path, feature_state_file: Path, monkeypatch) -> None:
        """Test merge_cmd uses main as default target."""
        monkeypatch.chdir(tmp_path)
        with (
            patch("zerg.commands.merge_cmd.MergeCoordinator"),
            patch("zerg.commands.merge_cmd.run_quality_gates") as mock_gates,
            patch("zerg.commands.merge_cmd.Orchestrator") as mock_orch_cls,
        ):
            mock_gates.return_value = GateResult.PASS
            mock_orch = MagicMock()
            mock_orch._merge_level.return_value = MergeFlowResult(
                success=True,
                level=1,
                source_branches=[],
                target_branch="main",
                merge_commit="abc123",
            )
            mock_orch_cls.return_value = mock_orch
            runner = CliRunner()
            result = runner.invoke(merge_cmd, ["--feature", "test-feature"], input="y\n")
            assert "main" in result.output

    def test_merge_cmd_custom_target(self, tmp_path: Path, feature_state_file: Path, monkeypatch) -> None:
        """Test merge_cmd with custom target branch."""
        monkeypatch.chdir(tmp_path)
        with (
            patch("zerg.commands.merge_cmd.MergeCoordinator"),
            patch("zerg.commands.merge_cmd.run_quality_gates") as mock_gates,
            patch("zerg.commands.merge_cmd.Orchestrator") as mock_orch_cls,
        ):
            mock_gates.return_value = GateResult.PASS
            mock_orch = MagicMock()
            mock_orch._merge_level.return_value = MergeFlowResult(
                success=True,
                level=1,
                source_branches=[],
                target_branch="develop",
                merge_commit="abc123",
            )
            mock_orch_cls.return_value = mock_orch
            runner = CliRunner()
            result = runner.invoke(
                merge_cmd,
                ["--feature", "test-feature", "--target", "develop"],
                input="y\n",
            )
            assert "develop" in result.output


class TestMergeCmdAutoDetectLevel:
    """Tests for merge_cmd auto-detecting level from state."""

    def test_merge_cmd_auto_detects_level(self, tmp_path: Path, feature_state_file: Path, monkeypatch) -> None:
        """Test merge_cmd auto-detects level when not specified."""
        monkeypatch.chdir(tmp_path)
        with (
            patch("zerg.commands.merge_cmd.MergeCoordinator"),
            patch("zerg.commands.merge_cmd.run_quality_gates") as mock_gates,
            patch("zerg.commands.merge_cmd.Orchestrator") as mock_orch_cls,
            patch("zerg.commands.merge_cmd.StateManager") as mock_state_cls,
        ):
            mock_gates.return_value = GateResult.PASS
            mock_state = MagicMock()
            mock_state.exists.return_value = True
            mock_state.get_current_level.return_value = 2
            mock_state.get_all_workers.return_value = {}
            mock_state.get_level_merge_status.return_value = LevelMergeStatus.COMPLETE
            mock_state_cls.return_value = mock_state
            mock_orch = MagicMock()
            mock_orch._merge_level.return_value = MergeFlowResult(
                success=True,
                level=2,
                source_branches=[],
                target_branch="main",
                merge_commit="abc123",
            )
            mock_orch_cls.return_value = mock_orch
            runner = CliRunner()
            runner.invoke(merge_cmd, ["--feature", "test-feature"], input="y\n")
            mock_orch._merge_level.assert_called_with(2)


class TestMergeCmdExceptionHandling:
    """Tests for merge_cmd exception handling."""

    def test_merge_cmd_general_exception(self, tmp_path: Path, feature_state_file: Path, monkeypatch) -> None:
        """Test merge_cmd handles general exceptions."""
        monkeypatch.chdir(tmp_path)
        with patch("zerg.commands.merge_cmd.StateManager") as mock_state_cls:
            mock_state = MagicMock()
            mock_state.exists.side_effect = RuntimeError("Unexpected error")
            mock_state_cls.return_value = mock_state
            runner = CliRunner()
            result = runner.invoke(merge_cmd, ["--feature", "test-feature"])
            assert result.exit_code == 1
            assert "Error" in result.output

    def test_merge_cmd_no_merge_status_after_success(
        self, tmp_path: Path, feature_state_file: Path, monkeypatch
    ) -> None:
        """Test merge_cmd handles case when merge status is None after success."""
        monkeypatch.chdir(tmp_path)
        with (
            patch("zerg.commands.merge_cmd.MergeCoordinator"),
            patch("zerg.commands.merge_cmd.run_quality_gates") as mock_gates,
            patch("zerg.commands.merge_cmd.Orchestrator") as mock_orch_cls,
            patch("zerg.commands.merge_cmd.StateManager") as mock_state_cls,
        ):
            mock_gates.return_value = GateResult.PASS
            mock_state = MagicMock()
            mock_state.exists.return_value = True
            mock_state.get_current_level.return_value = 1
            mock_state.get_all_workers.return_value = {}
            mock_state.get_level_merge_status.return_value = None
            mock_state_cls.return_value = mock_state
            mock_orch = MagicMock()
            mock_orch._merge_level.return_value = MergeFlowResult(
                success=True,
                level=1,
                source_branches=[],
                target_branch="main",
                merge_commit="abc123",
            )
            mock_orch_cls.return_value = mock_orch
            runner = CliRunner()
            result = runner.invoke(merge_cmd, ["--feature", "test-feature"], input="y\n")
            assert result.exit_code == 0


class TestMergeCmdSuccessNoCommit:
    """Tests for merge_cmd when merge succeeds but no commit is generated."""

    def test_merge_cmd_success_no_merge_commit(self, tmp_path: Path, feature_state_file: Path, monkeypatch) -> None:
        """Test merge_cmd handles success with no merge commit."""
        monkeypatch.chdir(tmp_path)
        with (
            patch("zerg.commands.merge_cmd.MergeCoordinator"),
            patch("zerg.commands.merge_cmd.run_quality_gates") as mock_gates,
            patch("zerg.commands.merge_cmd.Orchestrator") as mock_orch_cls,
        ):
            mock_gates.return_value = GateResult.PASS
            mock_orch = MagicMock()
            mock_orch._merge_level.return_value = MergeFlowResult(
                success=True,
                level=1,
                source_branches=[],
                target_branch="main",
                merge_commit=None,
            )
            mock_orch_cls.return_value = mock_orch
            runner = CliRunner()
            result = runner.invoke(merge_cmd, ["--feature", "test-feature"], input="y\n")
            assert result.exit_code == 0
            assert "merged successfully" in result.output
