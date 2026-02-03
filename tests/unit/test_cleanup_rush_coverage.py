"""Coverage tests for uncovered paths in cleanup.py and rush.py.

Targets:
  cleanup.py lines 60-62, 360-458
  rush.py lines 114, 118-124, 128-132, 150, 212-233, 238-266
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from zerg.cli import cli
from zerg.commands.cleanup import cleanup_structured_logs
from zerg.commands.rush import _render_standalone_risk, _run_preflight

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_logging_config(tmp_path: Path) -> MagicMock:
    """Create a mock ZergConfig with logging settings pointing at tmp_path."""
    config = MagicMock()
    config.logging.directory = str(tmp_path / "logs")
    config.logging.retain_days = 7
    return config


@pytest.fixture
def minimal_task_graph() -> dict[str, Any]:
    """Minimal valid task graph for rush tests."""
    return {
        "schema": "1.0",
        "feature": "cov-feature",
        "version": "1.0.0",
        "generated": "2026-01-31T00:00:00Z",
        "total_tasks": 1,
        "estimated_duration_minutes": 10,
        "max_parallelization": 1,
        "tasks": [
            {
                "id": "L1-001",
                "title": "Only task",
                "description": "Single task",
                "level": 1,
                "dependencies": [],
                "files": {"create": ["a.py"], "modify": [], "read": []},
                "verification": {"command": "true", "timeout_seconds": 10},
                "estimate_minutes": 10,
                "critical_path": True,
            },
        ],
        "levels": {
            "1": {
                "name": "only",
                "tasks": ["L1-001"],
                "parallel": True,
                "estimated_minutes": 10,
                "depends_on_levels": [],
            },
        },
    }


@pytest.fixture
def task_graph_file(tmp_path: Path, minimal_task_graph: dict[str, Any]) -> Path:
    """Write task graph to tmp dir and return path."""
    tasks_dir = tmp_path / ".gsd" / "tasks"
    tasks_dir.mkdir(parents=True)
    tg = tasks_dir / "task-graph.json"
    tg.write_text(json.dumps(minimal_task_graph))
    return tg


def _set_old_mtime(path: Path, days: int = 30) -> None:
    """Set a path's mtime to N days ago."""
    import os

    old_time = time.time() - (days * 86400)
    os.utime(path, (old_time, old_time))


# ===================================================================
# cleanup.py: lines 60-62 -- --logs flag invokes cleanup_structured_logs
# ===================================================================


class TestCleanupLogsOnlyFlag:
    """Test the --logs flag in the cleanup command (lines 60-62)."""

    def test_logs_only_flag_invokes_structured_cleanup(self, tmp_path: Path, monkeypatch) -> None:
        """--logs should call cleanup_structured_logs and return."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        with (
            patch("zerg.commands.cleanup.ZergConfig") as mock_cfg_cls,
            patch("zerg.commands.cleanup.cleanup_structured_logs") as mock_fn,
        ):
            mock_cfg_cls.load.return_value = MagicMock()
            result = runner.invoke(cli, ["cleanup", "--logs"])

        assert result.exit_code == 0
        mock_fn.assert_called_once()

    def test_logs_only_with_dry_run(self, tmp_path: Path, monkeypatch) -> None:
        """--logs --dry-run should forward dry_run=True."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        with (
            patch("zerg.commands.cleanup.ZergConfig") as mock_cfg_cls,
            patch("zerg.commands.cleanup.cleanup_structured_logs") as mock_fn,
        ):
            mock_cfg_cls.load.return_value = MagicMock()
            result = runner.invoke(cli, ["cleanup", "--logs", "--dry-run"])

        assert result.exit_code == 0
        call_args = mock_fn.call_args
        # dry_run is the second positional arg
        assert call_args[0][1] is True or call_args[1].get("dry_run") is True


# ===================================================================
# cleanup.py: lines 360-458 -- cleanup_structured_logs function
# ===================================================================


class TestCleanupStructuredLogs:
    """Test cleanup_structured_logs covering lines 360-458."""

    def test_no_dirs_exist(self, mock_logging_config: MagicMock) -> None:
        """When log dirs do not exist, runs without error."""
        cleanup_structured_logs(mock_logging_config, dry_run=False)

    def test_empty_dirs(self, mock_logging_config: MagicMock) -> None:
        """When log dirs exist but are empty, outputs no-clean messages."""
        log_dir = Path(mock_logging_config.logging.directory)
        (log_dir / "tasks").mkdir(parents=True)
        (log_dir / "workers").mkdir(parents=True)

        cleanup_structured_logs(mock_logging_config, dry_run=False)

    def test_old_task_dirs_removed(self, mock_logging_config: MagicMock) -> None:
        """Task dirs older than retain_days are removed."""
        log_dir = Path(mock_logging_config.logging.directory)
        tasks_dir = log_dir / "tasks"
        tasks_dir.mkdir(parents=True)

        old_dir = tasks_dir / "old-task-001"
        old_dir.mkdir()
        _set_old_mtime(old_dir)

        cleanup_structured_logs(mock_logging_config, dry_run=False)
        assert not old_dir.exists()

    def test_old_task_dirs_dry_run(self, mock_logging_config: MagicMock) -> None:
        """Dry run does not remove old task dirs."""
        log_dir = Path(mock_logging_config.logging.directory)
        tasks_dir = log_dir / "tasks"
        tasks_dir.mkdir(parents=True)

        old_dir = tasks_dir / "old-task-002"
        old_dir.mkdir()
        _set_old_mtime(old_dir)

        cleanup_structured_logs(mock_logging_config, dry_run=True)
        assert old_dir.exists()

    def test_recent_task_dirs_kept(self, mock_logging_config: MagicMock) -> None:
        """Task dirs newer than retain_days are kept."""
        log_dir = Path(mock_logging_config.logging.directory)
        tasks_dir = log_dir / "tasks"
        tasks_dir.mkdir(parents=True)

        recent_dir = tasks_dir / "recent-task"
        recent_dir.mkdir()

        cleanup_structured_logs(mock_logging_config, dry_run=False)
        assert recent_dir.exists()

    def test_old_worker_jsonl_removed(self, mock_logging_config: MagicMock) -> None:
        """Worker JSONL files older than retain_days are removed."""
        log_dir = Path(mock_logging_config.logging.directory)
        workers_dir = log_dir / "workers"
        workers_dir.mkdir(parents=True)

        old_file = workers_dir / "worker-0.jsonl"
        old_file.write_text('{"event": "test"}\n')
        _set_old_mtime(old_file)

        cleanup_structured_logs(mock_logging_config, dry_run=False)
        assert not old_file.exists()

    def test_old_worker_jsonl_dry_run(self, mock_logging_config: MagicMock) -> None:
        """Dry run does not remove old worker JSONL files."""
        log_dir = Path(mock_logging_config.logging.directory)
        workers_dir = log_dir / "workers"
        workers_dir.mkdir(parents=True)

        old_file = workers_dir / "worker-0.jsonl"
        old_file.write_text('{"event": "test"}\n')
        _set_old_mtime(old_file)

        cleanup_structured_logs(mock_logging_config, dry_run=True)
        assert old_file.exists()

    def test_recent_worker_jsonl_kept(self, mock_logging_config: MagicMock) -> None:
        """Recent worker JSONL files are kept."""
        log_dir = Path(mock_logging_config.logging.directory)
        workers_dir = log_dir / "workers"
        workers_dir.mkdir(parents=True)

        recent_file = workers_dir / "worker-0.jsonl"
        recent_file.write_text('{"event": "test"}\n')

        cleanup_structured_logs(mock_logging_config, dry_run=False)
        assert recent_file.exists()

    def test_rotated_worker_file_old(self, mock_logging_config: MagicMock) -> None:
        """Rotated (.1 suffix) JSONL files older than retain_days are removed."""
        log_dir = Path(mock_logging_config.logging.directory)
        workers_dir = log_dir / "workers"
        workers_dir.mkdir(parents=True)

        rotated = workers_dir / "worker-0.jsonl.1"
        rotated.write_text('{"event": "old"}\n')
        _set_old_mtime(rotated)

        cleanup_structured_logs(mock_logging_config, dry_run=False)
        assert not rotated.exists()

    def test_old_orchestrator_jsonl_removed(self, mock_logging_config: MagicMock) -> None:
        """Old orchestrator.jsonl is removed."""
        log_dir = Path(mock_logging_config.logging.directory)
        log_dir.mkdir(parents=True, exist_ok=True)

        orch_file = log_dir / "orchestrator.jsonl"
        orch_file.write_text('{"event":"init"}\n')
        _set_old_mtime(orch_file)

        cleanup_structured_logs(mock_logging_config, dry_run=False)
        assert not orch_file.exists()

    def test_old_orchestrator_jsonl_dry_run(self, mock_logging_config: MagicMock) -> None:
        """Dry run does not remove old orchestrator.jsonl."""
        log_dir = Path(mock_logging_config.logging.directory)
        log_dir.mkdir(parents=True, exist_ok=True)

        orch_file = log_dir / "orchestrator.jsonl"
        orch_file.write_text('{"event":"init"}\n')
        _set_old_mtime(orch_file)

        cleanup_structured_logs(mock_logging_config, dry_run=True)
        assert orch_file.exists()

    def test_task_dir_rmtree_error(self, mock_logging_config: MagicMock) -> None:
        """Errors during rmtree are captured, not raised."""
        log_dir = Path(mock_logging_config.logging.directory)
        tasks_dir = log_dir / "tasks"
        tasks_dir.mkdir(parents=True)

        old_dir = tasks_dir / "bad-task"
        old_dir.mkdir()
        _set_old_mtime(old_dir)

        with patch("zerg.commands.cleanup.shutil.rmtree", side_effect=OSError("perm")):
            cleanup_structured_logs(mock_logging_config, dry_run=False)

    def test_worker_unlink_error(self, mock_logging_config: MagicMock) -> None:
        """Errors during worker file unlink are captured, not raised."""
        log_dir = Path(mock_logging_config.logging.directory)
        workers_dir = log_dir / "workers"
        workers_dir.mkdir(parents=True)

        old_file = workers_dir / "worker-x.jsonl"
        old_file.write_text("{}\n")
        _set_old_mtime(old_file)

        with patch.object(Path, "unlink", side_effect=OSError("locked")):
            cleanup_structured_logs(mock_logging_config, dry_run=False)

    def test_non_dir_in_tasks_skipped(self, mock_logging_config: MagicMock) -> None:
        """Files (not dirs) inside tasks/ are skipped."""
        log_dir = Path(mock_logging_config.logging.directory)
        tasks_dir = log_dir / "tasks"
        tasks_dir.mkdir(parents=True)

        (tasks_dir / "random-file.txt").write_text("not a dir")

        cleanup_structured_logs(mock_logging_config, dry_run=False)

    def test_summary_with_errors(self, mock_logging_config: MagicMock) -> None:
        """When errors occur, summary reports error count."""
        log_dir = Path(mock_logging_config.logging.directory)
        log_dir.mkdir(parents=True, exist_ok=True)

        orch_file = log_dir / "orchestrator.jsonl"
        orch_file.write_text("{}\n")
        _set_old_mtime(orch_file)

        with patch.object(Path, "unlink", side_effect=OSError("fail")):
            cleanup_structured_logs(mock_logging_config, dry_run=False)


# ===================================================================
# rush.py: lines 212-233 -- _run_preflight function
# ===================================================================


class TestRunPreflight:
    """Test _run_preflight directly (lines 212-233).

    NOTE: The conftest autouse fixture patches _run_preflight itself,
    but we call the real function directly here, patching only PreflightChecker
    inside the preflight module where it lives.
    """

    def test_preflight_passes(self) -> None:
        """When all checks pass, returns True."""
        mock_report = MagicMock()
        mock_report.errors = []
        mock_report.warnings = []

        mock_checker = MagicMock()
        mock_checker.return_value.run_all.return_value = mock_report

        config = MagicMock()
        config.ports.range_start = 7860
        config.ports.range_end = 7960

        with patch("zerg.preflight.PreflightChecker", mock_checker):
            result = (
                _run_preflight.__wrapped__(config, "subprocess", 3)
                if hasattr(_run_preflight, "__wrapped__")
                else _run_preflight(config, "subprocess", 3)
            )

        assert result is True

    def test_preflight_fails_with_errors(self) -> None:
        """When preflight has errors, returns False."""

        @dataclass
        class FakeCheck:
            name: str = "docker"
            passed: bool = False
            message: str = "Docker not running"
            severity: str = "error"

        mock_report = MagicMock()
        mock_report.errors = [FakeCheck()]
        mock_report.warnings = []

        mock_checker = MagicMock()
        mock_checker.return_value.run_all.return_value = mock_report

        config = MagicMock()
        config.ports.range_start = 7860
        config.ports.range_end = 7960

        with patch("zerg.preflight.PreflightChecker", mock_checker):
            result = (
                _run_preflight.__wrapped__(config, "container", 5)
                if hasattr(_run_preflight, "__wrapped__")
                else _run_preflight(config, "container", 5)
            )

        assert result is False

    def test_preflight_with_warnings(self) -> None:
        """When preflight has warnings but no errors, returns True."""

        @dataclass
        class FakeCheck:
            name: str = "disk"
            passed: bool = False
            message: str = "Low disk space"
            severity: str = "warning"

        mock_report = MagicMock()
        mock_report.errors = []
        mock_report.warnings = [FakeCheck()]

        mock_checker = MagicMock()
        mock_checker.return_value.run_all.return_value = mock_report

        config = MagicMock()
        config.ports.range_start = 7860
        config.ports.range_end = 7960

        with patch("zerg.preflight.PreflightChecker", mock_checker):
            result = (
                _run_preflight.__wrapped__(config, "auto", 5)
                if hasattr(_run_preflight, "__wrapped__")
                else _run_preflight(config, "auto", 5)
            )

        assert result is True


# ===================================================================
# rush.py: lines 238-266 -- _render_standalone_risk
# ===================================================================


class TestRenderStandaloneRisk:
    """Test _render_standalone_risk (lines 238-266)."""

    def _make_risk_report(
        self,
        grade: str = "B",
        score: float = 0.45,
        critical_path: list[str] | None = None,
        risk_factors: list[str] | None = None,
    ) -> MagicMock:
        report = MagicMock()
        report.grade = grade
        report.overall_score = score
        report.critical_path = critical_path or []
        report.risk_factors = risk_factors or []
        return report

    def test_render_grade_a(self) -> None:
        """Render grade A risk report."""
        _render_standalone_risk(self._make_risk_report(grade="A", score=0.1))

    def test_render_grade_b_with_critical_path(self) -> None:
        """Render grade B with critical path."""
        _render_standalone_risk(
            self._make_risk_report(
                grade="B",
                score=0.45,
                critical_path=["L1-001", "L2-001"],
            )
        )

    def test_render_grade_c_with_risk_factors(self) -> None:
        """Render grade C with risk factors."""
        _render_standalone_risk(
            self._make_risk_report(
                grade="C",
                score=0.7,
                risk_factors=["High file overlap", "Long critical path"],
            )
        )

    def test_render_grade_d(self) -> None:
        """Render grade D (bold red)."""
        _render_standalone_risk(
            self._make_risk_report(
                grade="D",
                score=0.95,
                critical_path=["L1-001", "L2-001", "L3-001"],
                risk_factors=["Extreme complexity"],
            )
        )

    def test_render_unknown_grade(self) -> None:
        """Render unknown grade falls back to white."""
        _render_standalone_risk(self._make_risk_report(grade="X", score=0.5))


# ===================================================================
# rush.py: lines 113-114 -- preflight failure exits
# ===================================================================


class TestRushPreflightFailure:
    """Test rush exits when preflight fails (line 113-114)."""

    def test_rush_exits_on_preflight_failure(
        self,
        tmp_path: Path,
        task_graph_file: Path,
        monkeypatch,
    ) -> None:
        """When preflight fails, rush should exit with code 1."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_cfg_cls,
            # Override the autouse conftest bypass for this test
            patch("zerg.commands.rush._run_preflight", return_value=False),
        ):
            mock_cfg_cls.load.return_value = MagicMock()
            result = runner.invoke(cli, ["rush", "--task-graph", str(task_graph_file), "--dry-run"])

        assert result.exit_code == 1


# ===================================================================
# rush.py: lines 117-124 -- what-if analysis branch
# ===================================================================


class TestRushWhatIf:
    """Test --what-if flag (lines 117-124)."""

    def test_what_if_with_dry_run(
        self,
        tmp_path: Path,
        task_graph_file: Path,
        monkeypatch,
    ) -> None:
        """--what-if --dry-run invokes WhatIfEngine then DryRunSimulator."""
        monkeypatch.chdir(tmp_path)

        mock_engine_cls = MagicMock()
        mock_engine_inst = MagicMock()
        mock_engine_cls.return_value = mock_engine_inst

        mock_sim_cls = MagicMock()
        mock_report = MagicMock()
        mock_report.has_errors = False
        mock_sim_cls.return_value.run.return_value = mock_report

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_cfg_cls,
            patch("zerg.whatif.WhatIfEngine", mock_engine_cls),
            patch("zerg.dryrun.DryRunSimulator", mock_sim_cls),
        ):
            mock_cfg_cls.load.return_value = MagicMock()
            runner.invoke(
                cli,
                ["rush", "--task-graph", str(task_graph_file), "--dry-run", "--what-if"],
            )

        mock_engine_inst.compare_all.assert_called_once()
        mock_engine_inst.render.assert_called_once()

    def test_what_if_without_dry_run_returns_early(
        self,
        tmp_path: Path,
        task_graph_file: Path,
        monkeypatch,
    ) -> None:
        """--what-if alone (no --dry-run) should return after rendering."""
        monkeypatch.chdir(tmp_path)

        mock_engine_cls = MagicMock()
        mock_engine_inst = MagicMock()
        mock_engine_cls.return_value = mock_engine_inst

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_cfg_cls,
            patch("zerg.whatif.WhatIfEngine", mock_engine_cls),
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
        ):
            mock_cfg_cls.load.return_value = MagicMock()
            result = runner.invoke(
                cli,
                ["rush", "--task-graph", str(task_graph_file), "--what-if"],
            )

        # Orchestrator should NOT be instantiated (early return at line 150)
        mock_orch_cls.assert_not_called()
        assert result.exit_code == 0


# ===================================================================
# rush.py: lines 127-132, 150 -- risk standalone branch
# ===================================================================


class TestRushRiskFlag:
    """Test --risk flag (lines 127-132, 150)."""

    def test_risk_standalone(
        self,
        tmp_path: Path,
        task_graph_file: Path,
        monkeypatch,
    ) -> None:
        """--risk (no --dry-run) renders risk and returns."""
        monkeypatch.chdir(tmp_path)

        mock_scorer_cls = MagicMock()
        mock_risk_report = MagicMock()
        mock_risk_report.grade = "B"
        mock_risk_report.overall_score = 0.4
        mock_risk_report.critical_path = ["L1-001"]
        mock_risk_report.risk_factors = ["Test factor"]
        mock_scorer_cls.return_value.score.return_value = mock_risk_report

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_cfg_cls,
            patch("zerg.risk_scoring.RiskScorer", mock_scorer_cls),
            patch("zerg.commands.rush._render_standalone_risk") as mock_render,
            patch("zerg.commands.rush.Orchestrator") as mock_orch_cls,
        ):
            mock_cfg_cls.load.return_value = MagicMock()
            result = runner.invoke(
                cli,
                ["rush", "--task-graph", str(task_graph_file), "--risk"],
            )

        mock_scorer_cls.assert_called_once()
        mock_render.assert_called_once_with(mock_risk_report)
        # Orchestrator not called because of early return at line 150
        mock_orch_cls.assert_not_called()
        assert result.exit_code == 0

    def test_risk_with_dry_run_skips_standalone_render(
        self,
        tmp_path: Path,
        task_graph_file: Path,
        monkeypatch,
    ) -> None:
        """--risk --dry-run should NOT render standalone risk (condition: risk and not dry_run)."""
        monkeypatch.chdir(tmp_path)

        mock_sim_cls = MagicMock()
        mock_report = MagicMock()
        mock_report.has_errors = False
        mock_sim_cls.return_value.run.return_value = mock_report

        runner = CliRunner()
        with (
            patch("zerg.commands.rush.ZergConfig") as mock_cfg_cls,
            patch("zerg.dryrun.DryRunSimulator", mock_sim_cls),
            patch("zerg.commands.rush._render_standalone_risk") as mock_render,
        ):
            mock_cfg_cls.load.return_value = MagicMock()
            runner.invoke(
                cli,
                ["rush", "--task-graph", str(task_graph_file), "--risk", "--dry-run"],
            )

        mock_render.assert_not_called()
