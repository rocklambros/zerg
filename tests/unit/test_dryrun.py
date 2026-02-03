"""Unit tests for ZERG dry-run simulator.

Tests cover all validation, analysis, and rendering paths in zerg/dryrun.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from zerg.config import QualityGate, ZergConfig
from zerg.constants import GateResult
from zerg.dryrun import (
    DryRunReport,
    DryRunSimulator,
    GateCheckResult,
)
from zerg.preflight import CheckResult, PreflightReport
from zerg.risk_scoring import RiskReport
from zerg.types import GateRunResult

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def valid_task_graph() -> dict[str, Any]:
    """A valid task graph with 2 levels and 3 tasks."""
    return {
        "feature": "test-feature",
        "tasks": [
            {
                "id": "T1-001",
                "title": "First Task",
                "level": 1,
                "dependencies": [],
                "files": {"create": ["src/a.py"], "modify": [], "read": []},
                "verification": {"command": "python -c 'print(1)'", "timeout_seconds": 30},
                "estimate_minutes": 10,
                "critical_path": True,
            },
            {
                "id": "T1-002",
                "title": "Second Task",
                "level": 1,
                "dependencies": [],
                "files": {"create": ["src/b.py"], "modify": [], "read": []},
                "verification": {"command": "python -c 'print(2)'", "timeout_seconds": 30},
                "estimate_minutes": 15,
                "critical_path": False,
            },
            {
                "id": "T2-001",
                "title": "Third Task",
                "level": 2,
                "dependencies": ["T1-001", "T1-002"],
                "files": {"create": ["src/c.py"], "modify": [], "read": []},
                "verification": {"command": "python -c 'print(3)'", "timeout_seconds": 30},
                "estimate_minutes": 20,
                "critical_path": True,
            },
        ],
        "levels": {
            "1": {"name": "foundation", "tasks": ["T1-001", "T1-002"], "parallel": True},
            "2": {"name": "core", "tasks": ["T2-001"], "parallel": True},
        },
        "critical_path_minutes": 30,
    }


@pytest.fixture
def default_config() -> ZergConfig:
    """A default ZergConfig with no quality gates."""
    return ZergConfig()


@pytest.fixture
def config_with_gates() -> ZergConfig:
    """A ZergConfig with quality gates configured."""
    return ZergConfig(
        quality_gates=[
            QualityGate(name="lint", command="ruff check .", required=True),
            QualityGate(name="typecheck", command="mypy .", required=False),
        ]
    )


# =============================================================================
# Basic simulation
# =============================================================================


class TestBasicSimulation:
    """Tests for the happy-path simulation."""

    def test_basic_simulation(self, valid_task_graph: dict[str, Any], default_config: ZergConfig) -> None:
        """A valid task graph produces a report with no errors."""
        sim = DryRunSimulator(
            task_data=valid_task_graph,
            workers=2,
            feature="test-feature",
            config=default_config,
        )
        # Mock preflight so environment-specific checks (Docker image
        # availability, disk space) don't cause spurious failures in CI.
        mock_preflight = PreflightReport(checks=[CheckResult(name="mock", passed=True, message="ok", severity="error")])
        with patch.object(sim, "_run_preflight", return_value=mock_preflight):
            report = sim.run()

        assert not report.has_errors
        assert report.feature == "test-feature"
        assert report.workers == 2
        assert report.timeline is not None
        assert report.timeline.total_sequential_minutes == 45  # 10+15+20

    def test_report_dataclass_fields(self) -> None:
        """DryRunReport defaults are sane."""
        report = DryRunReport(feature="x", workers=1, mode="auto")
        assert not report.has_errors
        assert not report.has_warnings


# =============================================================================
# Level structure validation
# =============================================================================


class TestLevelStructureValidation:
    """Tests for _validate_level_structure."""

    def test_level_gap_warning(self, default_config: ZergConfig) -> None:
        """Non-contiguous levels produce a warning."""
        task_data = {
            "feature": "gap-test",
            "tasks": [
                {
                    "id": "T1",
                    "title": "A",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["a.py"], "modify": [], "read": []},
                    "verification": {"command": "true"},
                    "estimate_minutes": 5,
                },
                {
                    "id": "T3",
                    "title": "B",
                    "level": 3,
                    "dependencies": ["T1"],
                    "files": {"create": ["b.py"], "modify": [], "read": []},
                    "verification": {"command": "true"},
                    "estimate_minutes": 5,
                },
            ],
            "levels": {
                "1": {"name": "first", "tasks": ["T1"]},
                "3": {"name": "third", "tasks": ["T3"]},
            },
        }
        sim = DryRunSimulator(
            task_data=task_data,
            workers=1,
            feature="gap-test",
            config=default_config,
        )
        issues = sim._validate_level_structure()
        assert any("Gap" in i or "missing" in i.lower() for i in issues)


# =============================================================================
# File ownership
# =============================================================================


class TestFileOwnershipValidation:
    """Tests for _validate_file_ownership."""

    def test_file_ownership_conflict(self, default_config: ZergConfig) -> None:
        """Duplicate file claims are detected."""
        task_data = {
            "feature": "conflict-test",
            "tasks": [
                {
                    "id": "T1",
                    "title": "A",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["shared.py"], "modify": [], "read": []},
                    "verification": {"command": "true"},
                    "estimate_minutes": 5,
                },
                {
                    "id": "T2",
                    "title": "B",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": [], "modify": ["shared.py"], "read": []},
                    "verification": {"command": "true"},
                    "estimate_minutes": 5,
                },
            ],
            "levels": {"1": {"name": "first", "tasks": ["T1", "T2"]}},
        }
        sim = DryRunSimulator(
            task_data=task_data,
            workers=2,
            feature="conflict-test",
            config=default_config,
        )
        issues = sim._validate_file_ownership()
        assert len(issues) > 0
        assert "shared.py" in issues[0]


# =============================================================================
# Dependencies
# =============================================================================


class TestDependencyValidation:
    """Tests for _validate_dependencies."""

    def test_dependency_cycle(self, default_config: ZergConfig) -> None:
        """Cycle in dependencies is detected."""
        task_data = {
            "feature": "cycle-test",
            "tasks": [
                {
                    "id": "T1",
                    "title": "A",
                    "level": 1,
                    "dependencies": ["T2"],
                    "files": {"create": ["a.py"], "modify": [], "read": []},
                    "verification": {"command": "true"},
                    "estimate_minutes": 5,
                },
                {
                    "id": "T2",
                    "title": "B",
                    "level": 1,
                    "dependencies": ["T1"],
                    "files": {"create": ["b.py"], "modify": [], "read": []},
                    "verification": {"command": "true"},
                    "estimate_minutes": 5,
                },
            ],
            "levels": {"1": {"name": "first", "tasks": ["T1", "T2"]}},
        }
        sim = DryRunSimulator(
            task_data=task_data,
            workers=2,
            feature="cycle-test",
            config=default_config,
        )
        issues = sim._validate_dependencies()
        assert len(issues) > 0
        assert any("cycle" in i.lower() or "level" in i.lower() for i in issues)


# =============================================================================
# Missing verifications
# =============================================================================


class TestMissingVerifications:
    """Tests for _check_missing_verifications."""

    def test_missing_verification(self, default_config: ZergConfig) -> None:
        """Tasks without verification command produce warnings."""
        task_data = {
            "feature": "no-verify",
            "tasks": [
                {
                    "id": "T1",
                    "title": "A",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["a.py"], "modify": [], "read": []},
                    "estimate_minutes": 5,
                },
                {
                    "id": "T2",
                    "title": "B",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["b.py"], "modify": [], "read": []},
                    "verification": {},
                    "estimate_minutes": 5,
                },
            ],
            "levels": {"1": {"name": "first", "tasks": ["T1", "T2"]}},
        }
        sim = DryRunSimulator(
            task_data=task_data,
            workers=1,
            feature="no-verify",
            config=default_config,
        )
        warnings = sim._check_missing_verifications()
        assert len(warnings) == 2
        assert "T1" in warnings[0]
        assert "T2" in warnings[1]


# =============================================================================
# Timeline
# =============================================================================


class TestTimeline:
    """Tests for _compute_timeline."""

    def test_timeline_single_level(self, default_config: ZergConfig) -> None:
        """Wall time for a single level equals max worker load."""
        task_data = {
            "feature": "single-level",
            "tasks": [
                {
                    "id": "T1",
                    "title": "A",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["a.py"], "modify": [], "read": []},
                    "verification": {"command": "true"},
                    "estimate_minutes": 10,
                },
                {
                    "id": "T2",
                    "title": "B",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["b.py"], "modify": [], "read": []},
                    "verification": {"command": "true"},
                    "estimate_minutes": 20,
                },
            ],
            "levels": {"1": {"name": "first", "tasks": ["T1", "T2"]}},
        }
        sim = DryRunSimulator(
            task_data=task_data,
            workers=2,
            feature="single-level",
            config=default_config,
        )
        from zerg.assign import WorkerAssignment

        assigner = WorkerAssignment(2)
        assigner.assign(task_data["tasks"], "single-level")
        timeline = sim._compute_timeline(assigner)

        # With 2 workers, the 20m task goes to one worker and 10m to another
        assert timeline.estimated_wall_minutes == 20
        assert timeline.total_sequential_minutes == 30

    def test_timeline_multi_level(self, valid_task_graph: dict[str, Any], default_config: ZergConfig) -> None:
        """Wall time across levels sums per-level max."""
        sim = DryRunSimulator(
            task_data=valid_task_graph,
            workers=2,
            feature="multi",
            config=default_config,
        )
        from zerg.assign import WorkerAssignment

        assigner = WorkerAssignment(2)
        assigner.assign(valid_task_graph["tasks"], "multi")
        timeline = sim._compute_timeline(assigner)

        # Level 1: two tasks (10m, 15m) on 2 workers -> wall=15m
        # Level 2: one task (20m) -> wall=20m
        assert timeline.estimated_wall_minutes == 35
        assert timeline.total_sequential_minutes == 45

    def test_timeline_efficiency(self, default_config: ZergConfig) -> None:
        """Efficiency is sequential / (wall * workers)."""
        task_data = {
            "feature": "efficiency",
            "tasks": [
                {
                    "id": "T1",
                    "title": "A",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["a.py"], "modify": [], "read": []},
                    "verification": {"command": "true"},
                    "estimate_minutes": 10,
                },
                {
                    "id": "T2",
                    "title": "B",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["b.py"], "modify": [], "read": []},
                    "verification": {"command": "true"},
                    "estimate_minutes": 10,
                },
            ],
            "levels": {"1": {"name": "first", "tasks": ["T1", "T2"]}},
        }
        sim = DryRunSimulator(
            task_data=task_data,
            workers=2,
            feature="eff",
            config=default_config,
        )
        from zerg.assign import WorkerAssignment

        assigner = WorkerAssignment(2)
        assigner.assign(task_data["tasks"], "eff")
        timeline = sim._compute_timeline(assigner)

        # sequential=20, wall=10, workers=2 -> efficiency = 20/(10*2) = 1.0
        assert timeline.parallelization_efficiency == pytest.approx(1.0)


# =============================================================================
# Resources
# =============================================================================


class TestResourceChecks:
    """Tests for _check_resources."""

    def test_resource_no_git(
        self,
        default_config: ZergConfig,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Missing .git directory is an error."""
        monkeypatch.chdir(tmp_path)

        task_data = {"feature": "no-git", "tasks": [], "levels": {}}
        sim = DryRunSimulator(
            task_data=task_data,
            workers=1,
            feature="no-git",
            config=default_config,
        )
        issues = sim._check_resources()
        assert any(".git" in i for i in issues)


# =============================================================================
# Quality gates
# =============================================================================


class TestQualityGates:
    """Tests for _check_quality_gates."""

    def test_gates_not_run(self, config_with_gates: ZergConfig) -> None:
        """Default (run_gates=False) lists gates as not_run."""
        task_data = {"feature": "gates", "tasks": [], "levels": {}}
        sim = DryRunSimulator(
            task_data=task_data,
            workers=1,
            feature="gates",
            config=config_with_gates,
            run_gates=False,
        )
        results = sim._check_quality_gates()
        assert len(results) == 2
        assert all(r.status == "not_run" for r in results)
        assert results[0].name == "lint"
        assert results[0].required is True
        assert results[1].name == "typecheck"
        assert results[1].required is False

    @patch("zerg.dryrun.GateRunner")
    def test_gates_run(self, mock_runner_cls: MagicMock, config_with_gates: ZergConfig) -> None:
        """run_gates=True calls GateRunner."""
        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner
        mock_runner.run_all_gates.return_value = (
            True,
            [
                GateRunResult(
                    gate_name="lint",
                    result=GateResult.PASS,
                    command="ruff check .",
                    exit_code=0,
                    stdout="",
                    stderr="",
                    duration_ms=100,
                ),
                GateRunResult(
                    gate_name="typecheck",
                    result=GateResult.FAIL,
                    command="mypy .",
                    exit_code=1,
                    stdout="",
                    stderr="errors",
                    duration_ms=200,
                ),
            ],
        )

        task_data = {"feature": "gates", "tasks": [], "levels": {}}
        sim = DryRunSimulator(
            task_data=task_data,
            workers=1,
            feature="gates",
            config=config_with_gates,
            run_gates=True,
        )
        results = sim._check_quality_gates()

        mock_runner.run_all_gates.assert_called_once_with(stop_on_failure=False)
        assert len(results) == 2
        assert results[0].status == "passed"
        assert results[1].status == "failed"


# =============================================================================
# Report properties
# =============================================================================


class TestReportProperties:
    """Tests for DryRunReport.has_errors and has_warnings."""

    def test_report_has_errors_on_level_issues(self) -> None:
        report = DryRunReport(feature="x", workers=1, mode="auto", level_issues=["bad"])
        assert report.has_errors

    def test_report_has_errors_on_file_ownership(self) -> None:
        report = DryRunReport(
            feature="x",
            workers=1,
            mode="auto",
            file_ownership_issues=["conflict"],
        )
        assert report.has_errors

    def test_report_has_errors_on_dependency_issues(self) -> None:
        report = DryRunReport(feature="x", workers=1, mode="auto", dependency_issues=["cycle"])
        assert report.has_errors

    def test_report_has_errors_on_resource_issues(self) -> None:
        report = DryRunReport(feature="x", workers=1, mode="auto", resource_issues=["no git"])
        assert report.has_errors

    def test_report_has_errors_on_required_gate_failure(self) -> None:
        report = DryRunReport(
            feature="x",
            workers=1,
            mode="auto",
            gate_results=[
                GateCheckResult(name="lint", command="x", required=True, status="failed"),
            ],
        )
        assert report.has_errors

    def test_report_no_error_on_optional_gate_failure(self) -> None:
        report = DryRunReport(
            feature="x",
            workers=1,
            mode="auto",
            gate_results=[
                GateCheckResult(
                    name="lint",
                    command="x",
                    required=False,
                    status="failed",
                ),
            ],
        )
        assert not report.has_errors
        assert report.has_warnings

    def test_report_has_warnings_on_missing_verifications(self) -> None:
        report = DryRunReport(feature="x", workers=1, mode="auto", missing_verifications=["T1"])
        assert report.has_warnings
        assert not report.has_errors


# =============================================================================
# Render
# =============================================================================


class TestRender:
    """Tests for _render_report output."""

    def test_render_sections(
        self,
        valid_task_graph: dict[str, Any],
        default_config: ZergConfig,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Output contains panel headers for all sections."""
        sim = DryRunSimulator(
            task_data=valid_task_graph,
            workers=2,
            feature="render-test",
            config=default_config,
        )
        sim.run()

        captured = capsys.readouterr()
        assert "Validation" in captured.out
        assert "Level 1" in captured.out
        assert "Level 2" in captured.out
        assert "Worker Load Balance" in captured.out
        assert "Timeline Estimate" in captured.out
        assert "ready to rush" in captured.out.lower()

    def test_render_includes_preflight(
        self,
        valid_task_graph: dict[str, Any],
        default_config: ZergConfig,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Output contains Pre-flight panel."""
        sim = DryRunSimulator(
            task_data=valid_task_graph,
            workers=2,
            feature="pf-test",
            config=default_config,
        )
        sim.run()

        captured = capsys.readouterr()
        assert "Pre-flight" in captured.out

    def test_render_includes_risk(
        self,
        valid_task_graph: dict[str, Any],
        default_config: ZergConfig,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Output contains Risk Assessment panel."""
        sim = DryRunSimulator(
            task_data=valid_task_graph,
            workers=2,
            feature="risk-test",
            config=default_config,
        )
        sim.run()

        captured = capsys.readouterr()
        assert "Risk Assessment" in captured.out

    def test_render_includes_gantt(
        self,
        valid_task_graph: dict[str, Any],
        default_config: ZergConfig,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Output contains Gantt Timeline panel."""
        sim = DryRunSimulator(
            task_data=valid_task_graph,
            workers=2,
            feature="gantt-test",
            config=default_config,
        )
        sim.run()

        captured = capsys.readouterr()
        assert "Gantt Timeline" in captured.out

    def test_render_includes_snapshots(
        self,
        valid_task_graph: dict[str, Any],
        default_config: ZergConfig,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Output contains Projected Snapshots panel."""
        sim = DryRunSimulator(
            task_data=valid_task_graph,
            workers=2,
            feature="snap-test",
            config=default_config,
        )
        sim.run()

        captured = capsys.readouterr()
        assert "Projected Snapshots" in captured.out


# =============================================================================
# Preflight integration
# =============================================================================


class TestPreflightIntegration:
    """Tests for preflight integration in DryRunSimulator."""

    def test_preflight_report_included(
        self,
        valid_task_graph: dict[str, Any],
        default_config: ZergConfig,
    ) -> None:
        """Simulator populates preflight report."""
        sim = DryRunSimulator(
            task_data=valid_task_graph,
            workers=2,
            feature="pf-test",
            config=default_config,
        )
        report = sim.run()
        assert report.preflight is not None
        assert isinstance(report.preflight, PreflightReport)

    def test_preflight_failure_causes_error(self) -> None:
        """Report has_errors when preflight fails."""
        pf = PreflightReport(
            checks=[
                CheckResult(name="test", passed=False, message="fail", severity="error"),
            ]
        )
        report = DryRunReport(
            feature="x",
            workers=1,
            mode="auto",
            preflight=pf,
        )
        assert report.has_errors


# =============================================================================
# Risk integration
# =============================================================================


class TestRiskIntegration:
    """Tests for risk scoring integration in DryRunSimulator."""

    def test_risk_report_included(
        self,
        valid_task_graph: dict[str, Any],
        default_config: ZergConfig,
    ) -> None:
        """Simulator populates risk report."""
        sim = DryRunSimulator(
            task_data=valid_task_graph,
            workers=2,
            feature="risk-test",
            config=default_config,
        )
        report = sim.run()
        assert report.risk is not None
        assert isinstance(report.risk, RiskReport)

    def test_high_risk_produces_warning(self) -> None:
        """Report has_warnings when risk grade is C or D."""
        risk = RiskReport(grade="C", overall_score=0.7)
        report = DryRunReport(
            feature="x",
            workers=1,
            mode="auto",
            risk=risk,
        )
        assert report.has_warnings
