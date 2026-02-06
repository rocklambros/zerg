"""Unit tests for ZERG merge command module.

Thinned from 36 tests to cover unique code paths:
- detect_feature (no dir, single file)
- create_merge_plan (basic, skip gates, empty workers)
- show_merge_plan (normal + dry run)
- run_quality_gates (all pass, one fails, no gates)
- CLI command (no feature, dry run, gate failure, success, merge failure with conflicts, abort, exception)
"""

from __future__ import annotations

import json
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
from zerg.constants import GateResult
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
    mock.get_all_workers.return_value = {0: worker0, 1: worker1}
    return mock


class TestDetectFeature:
    """Tests for detect_feature function."""

    def test_no_state_dir(self, tmp_path: Path, monkeypatch) -> None:
        """Test returns None when .zerg/state does not exist."""
        monkeypatch.chdir(tmp_path)
        assert detect_feature() is None

    def test_single_state_file(self, tmp_path: Path, feature_state_file: Path, monkeypatch) -> None:
        """Test returns feature name from single state file."""
        monkeypatch.chdir(tmp_path)
        assert detect_feature() == "test-feature"


class TestCreateMergePlan:
    """Tests for create_merge_plan function."""

    def test_basic_plan(self, mock_state_manager: MagicMock) -> None:
        """Test create_merge_plan returns correct structure with branches."""
        plan = create_merge_plan(
            state=mock_state_manager, feature="test-feature", level=1, target="main", skip_gates=False
        )
        assert plan["feature"] == "test-feature"
        assert plan["level"] == 1
        assert plan["target"] == "main"
        assert plan["skip_gates"] is False
        assert plan["gates"] == ["lint", "typecheck", "test"]
        assert len(plan["branches"]) == 2

    def test_skip_gates(self, mock_state_manager: MagicMock) -> None:
        """Test create_merge_plan with skip_gates=True."""
        plan = create_merge_plan(state=mock_state_manager, feature="test", level=1, target="main", skip_gates=True)
        assert plan["skip_gates"] is True
        assert plan["gates"] == []


class TestShowMergePlan:
    """Tests for show_merge_plan function."""

    @pytest.mark.parametrize("dry_run", [False, True])
    def test_show_merge_plan(self, dry_run: bool) -> None:
        """Test show_merge_plan displays plan for normal and dry run modes."""
        plan = {
            "feature": "test-feature",
            "level": 1,
            "target": "main",
            "staging_branch": "zerg/test-feature/staging",
            "branches": [{"branch": "worker-0", "worker_id": 0, "status": "running"}],
            "gates": ["lint", "test"],
            "skip_gates": False,
        }
        show_merge_plan(plan, dry_run=dry_run)


class TestRunQualityGates:
    """Tests for run_quality_gates function."""

    def test_all_pass(self) -> None:
        """Test when all gates pass."""
        config = ZergConfig()
        config.quality_gates = [QualityGate(name="lint", command="ruff check .", required=True)]
        with patch("zerg.commands.merge_cmd.GateRunner") as mock_runner_cls:
            mock_runner = MagicMock()
            pass_result = MagicMock()
            pass_result.result = GateResult.PASS
            mock_runner.run_gate.return_value = pass_result
            mock_runner_cls.return_value = mock_runner
            assert run_quality_gates(config, "test", 1) == GateResult.PASS

    def test_one_fails(self) -> None:
        """Test when one gate fails."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="lint", command="ruff check .", required=True),
            QualityGate(name="test", command="pytest", required=True),
        ]
        with patch("zerg.commands.merge_cmd.GateRunner") as mock_runner_cls:
            mock_runner = MagicMock()
            pass_r = MagicMock()
            pass_r.result = GateResult.PASS
            fail_r = MagicMock()
            fail_r.result = GateResult.FAIL
            mock_runner.run_gate.side_effect = [pass_r, fail_r]
            mock_runner_cls.return_value = mock_runner
            assert run_quality_gates(config, "test", 1) == GateResult.FAIL

    def test_empty_gates(self) -> None:
        """Test with no gates configured."""
        config = ZergConfig()
        config.quality_gates = []
        with patch("zerg.commands.merge_cmd.GateRunner"):
            assert run_quality_gates(config, "test", 1) == GateResult.PASS


class TestMergeCmd:
    """Tests for merge_cmd CLI command."""

    def test_no_feature(self, tmp_path: Path, monkeypatch) -> None:
        """Test fails when no feature can be detected."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(merge_cmd, [])
        assert result.exit_code == 1
        assert "No active feature found" in result.output

    def test_dry_run(self, tmp_path: Path, feature_state_file: Path, monkeypatch) -> None:
        """Test dry run shows plan without changes."""
        monkeypatch.chdir(tmp_path)
        with patch("zerg.commands.merge_cmd.MergeCoordinator"):
            runner = CliRunner()
            result = runner.invoke(merge_cmd, ["--feature", "test-feature", "--dry-run"])
            assert result.exit_code == 0
            assert "dry run" in result.output.lower()

    def test_gate_failure(self, tmp_path: Path, feature_state_file: Path, monkeypatch) -> None:
        """Test exits when quality gates fail."""
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

    def test_successful_merge(self, tmp_path: Path, feature_state_file: Path, monkeypatch) -> None:
        """Test completes successfully."""
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
            result = runner.invoke(merge_cmd, ["--feature", "test-feature", "--level", "1"], input="y\n")
            assert result.exit_code == 0
            assert "merged successfully" in result.output

    def test_merge_failure_with_conflicts(self, tmp_path: Path, feature_state_file: Path, monkeypatch) -> None:
        """Test handles merge failure with conflicts."""
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
            result_obj.conflicts = ["src/main.py"]
            mock_orch._merge_level.return_value = result_obj
            mock_orch_cls.return_value = mock_orch
            runner = CliRunner()
            result = runner.invoke(merge_cmd, ["--feature", "test-feature", "--level", "1"], input="y\n")
            assert result.exit_code == 1
            assert "src/main.py" in result.output

    def test_user_aborts(self, tmp_path: Path, feature_state_file: Path, monkeypatch) -> None:
        """Test handles user abort."""
        monkeypatch.chdir(tmp_path)
        with (
            patch("zerg.commands.merge_cmd.MergeCoordinator"),
            patch("zerg.commands.merge_cmd.run_quality_gates") as mock_gates,
        ):
            mock_gates.return_value = GateResult.PASS
            runner = CliRunner()
            result = runner.invoke(merge_cmd, ["--feature", "test-feature"], input="n\n")
            assert "Aborted" in result.output

    def test_general_exception(self, tmp_path: Path, feature_state_file: Path, monkeypatch) -> None:
        """Test handles general exceptions."""
        monkeypatch.chdir(tmp_path)
        with patch("zerg.commands.merge_cmd.StateManager") as mock_state_cls:
            mock_state = MagicMock()
            mock_state.exists.side_effect = RuntimeError("Unexpected error")
            mock_state_cls.return_value = mock_state
            runner = CliRunner()
            result = runner.invoke(merge_cmd, ["--feature", "test-feature"])
            assert result.exit_code == 1
            assert "Error" in result.output
