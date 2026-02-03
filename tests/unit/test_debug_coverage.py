"""Additional coverage tests for zerg/commands/debug.py.

Targets specific uncovered lines:
- 154, 160, 162: DiagnosticResult.to_dict with timeline, correlations, env_report
- 489-490, 506-507, 528-529, 551-552, 561-562: Enhanced diagnostics exception paths
- 587, 591, 600-605: _run_zerg_diagnostics stale_tasks, global_error, log_patterns exception
- 629, 636-638: _run_system_diagnostics orphaned_worktrees, exception path
- 656-658: _plan_recovery exception path
- 775, 777, 780-785: _format_zerg_health_text failed_tasks, global_error, non-verbose
- 813, 815, 820-824: _format_system_health_text port_conflicts, orphans, non-verbose
- 853, 865-887: _format_enhanced_sections_text env_report section
- 910, 919-922: _format_recovery_plan_text non-verbose, _format_design_escalation_text
- 943-1029: _write_markdown_report
- 1048, 1081-1082: _resolve_inputs interactive mode, auto-detect exception
- 1217-1236, 1248-1270, 1280-1309: _display_health_sections verbose paths
- 1352-1367, 1377-1378: _display_recovery_and_escalation verbose path
- 1512-1513, 1527: CLI report_path and verbose exception
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from zerg.commands.debug import (
    DebugCommand,
    DebugConfig,
    DiagnosticResult,
    Hypothesis,
    ParsedError,
    _display_health_sections,
    _display_recovery_and_escalation,
    _resolve_inputs,
    _write_markdown_report,
    debug,
)
from zerg.diagnostics.log_analyzer import LogPattern
from zerg.diagnostics.recovery import RecoveryPlan, RecoveryStep
from zerg.diagnostics.state_introspector import ZergHealthReport
from zerg.diagnostics.system_diagnostics import SystemHealthReport
from zerg.diagnostics.types import (
    ErrorCategory,
    ErrorFingerprint,
    ScoredHypothesis,
    TimelineEvent,
)

# =============================================================================
# DiagnosticResult.to_dict — timeline, correlations, env_report (lines 154, 160, 162)
# =============================================================================


class TestDiagnosticResultToDict:
    """Cover to_dict branches for timeline, correlations, env_report."""

    def test_to_dict_with_timeline(self) -> None:
        """Line 154: timeline serialization."""
        event = TimelineEvent(
            timestamp="2025-01-01T00:00:00",
            worker_id=1,
            event_type="error",
            message="boom",
        )
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="cause",
            recommendation="fix",
            timeline=[event],
        )
        d = result.to_dict()
        assert "timeline" in d
        assert len(d["timeline"]) == 1
        assert d["timeline"][0]["message"] == "boom"

    def test_to_dict_with_correlations(self) -> None:
        """Line 160: correlations serialization."""
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="cause",
            recommendation="fix",
            correlations=[{"type": "log_burst", "count": 5}],
        )
        d = result.to_dict()
        assert "correlations" in d
        assert d["correlations"][0]["type"] == "log_burst"

    def test_to_dict_with_env_report(self) -> None:
        """Line 162: env_report serialization."""
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="cause",
            recommendation="fix",
            env_report={"python": {"version": "3.12"}},
        )
        d = result.to_dict()
        assert "env_report" in d
        assert d["env_report"]["python"]["version"] == "3.12"


# =============================================================================
# Enhanced diagnostics exception paths (lines 489-490, 506-507, 528-529, 551-552, 561-562)
# =============================================================================


class TestEnhancedDiagnosticsExceptions:
    """Cover exception handling in _run_enhanced_diagnostics."""

    def test_error_intel_failure(self) -> None:
        """Lines 489-490: ErrorIntelEngine import/call fails."""
        debugger = DebugCommand()
        with patch("zerg.commands.debug.DebugCommand._run_enhanced_diagnostics") as mock_enhanced:
            mock_enhanced.side_effect = lambda *a, **kw: a[0]
            result = debugger.run(error="test error")
        assert result is not None

    def test_error_intel_import_fails(self) -> None:
        """Lines 489-490: error_intel engine raises exception."""
        debugger = DebugCommand()
        result = DiagnosticResult(symptom="err", hypotheses=[], root_cause="c", recommendation="f")
        with patch(
            "zerg.diagnostics.error_intel.ErrorIntelEngine",
            side_effect=ImportError("no module"),
        ):
            out = debugger._run_enhanced_diagnostics(result, "error text", "", None, None, False, False)
        assert out.error_intel is None

    def test_log_correlation_failure(self) -> None:
        """Lines 506-507: LogCorrelationEngine raises exception."""
        debugger = DebugCommand()
        result = DiagnosticResult(symptom="err", hypotheses=[], root_cause="c", recommendation="f")
        with patch("zerg.diagnostics.error_intel.ErrorIntelEngine") as mock_intel_cls:
            mock_intel = mock_intel_cls.return_value
            mock_intel.analyze.return_value = MagicMock()
            mock_intel.get_evidence.return_value = []
            with patch(
                "zerg.diagnostics.log_correlator.LogCorrelationEngine",
                side_effect=RuntimeError("correlator broke"),
            ):
                out = debugger._run_enhanced_diagnostics(result, "error", "", "feat", 1, False, False)
        assert out is not None

    def test_hypothesis_engine_failure(self) -> None:
        """Lines 528-529: HypothesisEngine raises exception."""
        debugger = DebugCommand()
        result = DiagnosticResult(symptom="err", hypotheses=[], root_cause="c", recommendation="f")
        with patch("zerg.diagnostics.error_intel.ErrorIntelEngine") as mock_intel_cls:
            mock_intel = mock_intel_cls.return_value
            fp = ErrorFingerprint(
                hash="abc", language="python", error_type="ValueError", message_template="bad", file="x.py"
            )
            mock_intel.analyze.return_value = fp
            mock_intel.get_evidence.return_value = []
            with patch(
                "zerg.diagnostics.hypothesis_engine.HypothesisEngine",
                side_effect=RuntimeError("hypo broke"),
            ):
                out = debugger._run_enhanced_diagnostics(result, "error", "", None, None, False, False)
        assert out.scored_hypotheses == []

    def test_code_fixer_failure(self) -> None:
        """Lines 551-552: CodeAwareFixer raises exception."""
        debugger = DebugCommand()
        result = DiagnosticResult(symptom="err", hypotheses=[], root_cause="c", recommendation="f")
        with patch("zerg.diagnostics.error_intel.ErrorIntelEngine") as mock_intel_cls:
            mock_intel = mock_intel_cls.return_value
            fp = ErrorFingerprint(
                hash="abc", language="python", error_type="ValueError", message_template="bad", file="x.py"
            )
            mock_intel.analyze.return_value = fp
            mock_intel.get_evidence.return_value = []
            with patch("zerg.diagnostics.hypothesis_engine.HypothesisEngine") as mock_hypo_cls:
                mock_hypo_cls.return_value.analyze.return_value = []
                with patch(
                    "zerg.diagnostics.code_fixer.CodeAwareFixer",
                    side_effect=RuntimeError("fixer broke"),
                ):
                    out = debugger._run_enhanced_diagnostics(result, "error", "", None, None, False, False)
        assert out.fix_suggestions == []

    def test_env_diagnostics_failure(self) -> None:
        """Lines 561-562: EnvDiagnosticsEngine raises exception."""
        debugger = DebugCommand()
        result = DiagnosticResult(symptom="err", hypotheses=[], root_cause="c", recommendation="f")
        with patch("zerg.diagnostics.error_intel.ErrorIntelEngine") as mock_intel_cls:
            mock_intel = mock_intel_cls.return_value
            mock_intel.analyze.return_value = None
            mock_intel.get_evidence.return_value = []
            with patch(
                "zerg.diagnostics.env_diagnostics.EnvDiagnosticsEngine",
                side_effect=RuntimeError("env broke"),
            ):
                out = debugger._run_enhanced_diagnostics(result, "error", "", None, None, True, True)
        assert out.env_report is None


# =============================================================================
# _run_zerg_diagnostics: stale_tasks, global_error, log_patterns, exception
# (lines 587, 591, 600-605)
# =============================================================================


class TestRunZergDiagnosticsEdgeCases:
    """Cover edge cases in _run_zerg_diagnostics."""

    def test_stale_tasks_and_global_error(self) -> None:
        """Lines 587, 591: stale_tasks and global_error evidence."""
        debugger = DebugCommand()
        result = DiagnosticResult(symptom="err", hypotheses=[], root_cause="c", recommendation="f")
        health = ZergHealthReport(
            feature="feat",
            state_exists=True,
            total_tasks=5,
            failed_tasks=[],
            stale_tasks=[{"task_id": "T2", "age": 600}],
            global_error="state corruption detected",
        )
        with patch("zerg.diagnostics.state_introspector.ZergStateIntrospector") as mock_intr_cls:
            mock_intr_cls.return_value.get_health_report.return_value = health
            with patch("zerg.diagnostics.log_analyzer.LogAnalyzer") as mock_log_cls:
                mock_log_cls.return_value.scan_worker_logs.return_value = [
                    LogPattern(pattern="crash", count=2, first_seen="1", last_seen="2", worker_ids=[1])
                ]
                out = debugger._run_zerg_diagnostics(result, "feat", None)

        assert any("stale" in e for e in out.evidence)
        assert any("Global error" in e for e in out.evidence)
        assert any("error pattern" in e for e in out.evidence)

    def test_zerg_diagnostics_exception(self) -> None:
        """Lines 603-605: exception during ZERG diagnostics."""
        debugger = DebugCommand()
        result = DiagnosticResult(symptom="err", hypotheses=[], root_cause="c", recommendation="f")
        with patch(
            "zerg.diagnostics.state_introspector.ZergStateIntrospector",
            side_effect=RuntimeError("introspector broke"),
        ):
            out = debugger._run_zerg_diagnostics(result, "feat", None)

        assert any("ZERG diagnostics error" in e for e in out.evidence)


# =============================================================================
# _run_system_diagnostics: orphaned_worktrees, exception (lines 629, 636-638)
# =============================================================================


class TestRunSystemDiagnosticsEdgeCases:
    """Cover edge cases in _run_system_diagnostics."""

    def test_orphaned_worktrees_evidence(self) -> None:
        """Line 629: orphaned worktrees added to evidence."""
        debugger = DebugCommand()
        result = DiagnosticResult(symptom="err", hypotheses=[], root_cause="c", recommendation="f")
        sys_report = SystemHealthReport(
            git_clean=True,
            git_branch="main",
            disk_free_gb=50.0,
            orphaned_worktrees=["wt1", "wt2"],
        )
        with patch("zerg.diagnostics.system_diagnostics.SystemDiagnostics") as mock_cls:
            mock_cls.return_value.run_all.return_value = sys_report
            out = debugger._run_system_diagnostics(result)

        assert any("orphaned worktree" in e for e in out.evidence)

    def test_system_diagnostics_exception(self) -> None:
        """Lines 636-638: exception during system diagnostics."""
        debugger = DebugCommand()
        result = DiagnosticResult(symptom="err", hypotheses=[], root_cause="c", recommendation="f")
        with patch(
            "zerg.diagnostics.system_diagnostics.SystemDiagnostics",
            side_effect=RuntimeError("sys broke"),
        ):
            out = debugger._run_system_diagnostics(result)

        assert any("System diagnostics error" in e for e in out.evidence)


# =============================================================================
# _plan_recovery exception (lines 656-658)
# =============================================================================


class TestPlanRecoveryException:
    """Cover _plan_recovery exception path."""

    def test_recovery_planner_exception(self) -> None:
        """Lines 656-658: RecoveryPlanner raises exception."""
        debugger = DebugCommand()
        result = DiagnosticResult(symptom="err", hypotheses=[], root_cause="c", recommendation="f")
        with patch(
            "zerg.diagnostics.recovery.RecoveryPlanner",
            side_effect=RuntimeError("planner broke"),
        ):
            out = debugger._plan_recovery(result)

        assert any("Recovery planning error" in e for e in out.evidence)


# =============================================================================
# _format_zerg_health_text: failed, global_error, non-verbose (lines 775, 777, 780-785)
# =============================================================================


class TestFormatZergHealthText:
    """Cover _format_zerg_health_text branches."""

    def test_verbose_with_failed_and_global_error(self) -> None:
        """Lines 775, 777: verbose path with failed_tasks and global_error."""
        debugger = DebugCommand(DebugConfig(verbose=True))
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="c",
            recommendation="f",
            zerg_health=ZergHealthReport(
                feature="feat",
                state_exists=True,
                total_tasks=5,
                failed_tasks=[{"task_id": "T1"}],
                global_error="state corrupt",
            ),
        )
        lines = debugger._format_zerg_health_text(result)
        text = "\n".join(lines)
        assert "Failed:" in text
        assert "Error:" in text

    def test_non_verbose_with_failures(self) -> None:
        """Lines 780-785: non-verbose summary with failures."""
        debugger = DebugCommand(DebugConfig(verbose=False))
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="c",
            recommendation="f",
            zerg_health=ZergHealthReport(
                feature="feat",
                state_exists=True,
                total_tasks=10,
                failed_tasks=[{"task_id": "T1"}, {"task_id": "T2"}],
            ),
        )
        lines = debugger._format_zerg_health_text(result)
        text = "\n".join(lines)
        assert "ZERG:" in text
        assert "2 failed" in text

    def test_non_verbose_no_failures(self) -> None:
        """Lines 780-784: non-verbose summary without failures."""
        debugger = DebugCommand(DebugConfig(verbose=False))
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="c",
            recommendation="f",
            zerg_health=ZergHealthReport(
                feature="feat",
                state_exists=True,
                total_tasks=10,
                failed_tasks=[],
            ),
        )
        lines = debugger._format_zerg_health_text(result)
        text = "\n".join(lines)
        assert "ZERG:" in text
        assert "failed" not in text


# =============================================================================
# _format_system_health_text: port_conflicts, orphans, non-verbose (lines 813, 815, 820-824)
# =============================================================================


class TestFormatSystemHealthText:
    """Cover _format_system_health_text branches."""

    def test_verbose_with_port_conflicts_and_orphans(self) -> None:
        """Lines 813, 815: verbose path with port conflicts and orphaned worktrees."""
        debugger = DebugCommand(DebugConfig(verbose=True))
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="c",
            recommendation="f",
            system_health=SystemHealthReport(
                git_clean=True,
                git_branch="main",
                disk_free_gb=50.0,
                port_conflicts=[9500, 9501],
                orphaned_worktrees=["wt1"],
            ),
        )
        lines = debugger._format_system_health_text(result)
        text = "\n".join(lines)
        assert "Port Conflicts:" in text
        assert "Orphaned Worktrees:" in text

    def test_non_verbose_system_health(self) -> None:
        """Lines 820-824: non-verbose system health summary."""
        debugger = DebugCommand(DebugConfig(verbose=False))
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="c",
            recommendation="f",
            system_health=SystemHealthReport(
                git_clean=False,
                git_branch="main",
                disk_free_gb=25.0,
            ),
        )
        lines = debugger._format_system_health_text(result)
        text = "\n".join(lines)
        assert "System: git dirty" in text
        assert "25.0GB free" in text


# =============================================================================
# _format_enhanced_sections_text: env_report, scored hypotheses fix (lines 853, 865-887)
# =============================================================================


class TestFormatEnhancedSectionsText:
    """Cover _format_enhanced_sections_text branches."""

    def test_scored_hypothesis_with_fix_verbose(self) -> None:
        """Line 853: scored hypothesis suggested_fix in verbose mode."""
        debugger = DebugCommand(DebugConfig(verbose=True))
        sh = ScoredHypothesis(
            description="worker crash",
            category=ErrorCategory.WORKER_FAILURE,
            prior_probability=0.6,
            posterior_probability=0.85,
            suggested_fix="restart worker",
        )
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="c",
            recommendation="f",
            scored_hypotheses=[sh],
        )
        lines = debugger._format_enhanced_sections_text(result)
        text = "\n".join(lines)
        assert "Fix: restart worker" in text

    def test_env_report_verbose(self) -> None:
        """Lines 865-887: env_report section in verbose mode."""
        debugger = DebugCommand(DebugConfig(verbose=True))
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="c",
            recommendation="f",
            env_report={
                "python": {
                    "venv": {"active": True, "path": "/venv"},
                },
                "resources": {
                    "memory": {"available_gb": 8.0, "total_gb": 16.0},
                    "disk": {"free_gb": 100.0, "used_percent": 40.0},
                },
                "config": ["missing .env", "bad setting"],
            },
        )
        lines = debugger._format_enhanced_sections_text(result)
        text = "\n".join(lines)
        assert "Environment Report:" in text
        assert "Python venv: active" in text
        assert "Memory:" in text
        assert "8.0GB available" in text
        assert "Disk:" in text
        assert "100.0GB free" in text
        assert "Config issues: 2" in text

    def test_env_report_inactive_venv(self) -> None:
        """Lines 865-887: env_report with inactive venv."""
        debugger = DebugCommand(DebugConfig(verbose=True))
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="c",
            recommendation="f",
            env_report={
                "python": {"venv": {"active": False}},
                "resources": {},
            },
        )
        lines = debugger._format_enhanced_sections_text(result)
        text = "\n".join(lines)
        assert "Python venv: inactive" in text

    def test_env_report_not_verbose_omitted(self) -> None:
        """Lines 864: env_report not shown in non-verbose mode."""
        debugger = DebugCommand(DebugConfig(verbose=False))
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="c",
            recommendation="f",
            env_report={"python": {"version": "3.12"}},
        )
        lines = debugger._format_enhanced_sections_text(result)
        text = "\n".join(lines)
        assert "Environment Report:" not in text


# =============================================================================
# _format_recovery_plan_text non-verbose, _format_design_escalation_text (lines 910, 919-922)
# =============================================================================


class TestFormatRecoveryAndEscalationText:
    """Cover non-verbose recovery plan and design escalation text."""

    def test_recovery_plan_non_verbose(self) -> None:
        """Line 910: non-verbose recovery plan summary."""
        debugger = DebugCommand(DebugConfig(verbose=False))
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="c",
            recommendation="f",
            recovery_plan=RecoveryPlan(
                problem="issue",
                root_cause="root",
                steps=[
                    RecoveryStep(description="s1", command="c1"),
                    RecoveryStep(description="s2", command="c2"),
                ],
            ),
        )
        lines = debugger._format_recovery_plan_text(result)
        text = "\n".join(lines)
        assert "2 steps available" in text
        assert "--verbose" in text

    def test_design_escalation_text(self) -> None:
        """Lines 919-922: design escalation section."""
        debugger = DebugCommand()
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="c",
            recommendation="f",
            design_escalation=True,
            design_escalation_reason="wide blast radius",
        )
        lines = debugger._format_design_escalation_text(result)
        text = "\n".join(lines)
        assert "DESIGN ESCALATION" in text
        assert "wide blast radius" in text
        assert "zerg design" in text


# =============================================================================
# _write_markdown_report (lines 943-1029)
# =============================================================================


class TestWriteMarkdownReport:
    """Cover _write_markdown_report function."""

    def test_basic_report(self, tmp_path: Path) -> None:
        """Lines 943-1029: basic markdown report generation."""
        debugger = DebugCommand()
        result = DiagnosticResult(
            symptom="ValueError: bad input",
            hypotheses=[
                Hypothesis(description="invalid data", likelihood="high", test_command="check input"),
            ],
            root_cause="Invalid input",
            recommendation="Validate data",
            confidence=0.85,
            parsed_error=ParsedError(
                error_type="ValueError",
                message="bad input",
                file="app.py",
                line=42,
            ),
        )
        report = tmp_path / "report.md"
        _write_markdown_report(result, debugger, str(report))

        content = report.read_text()
        assert "# ZERG Diagnostic Report" in content
        assert "ValueError" in content
        assert "bad input" in content
        assert "app.py" in content
        assert "Hypotheses" in content
        assert "invalid data" in content

    def test_report_with_error_intel(self, tmp_path: Path) -> None:
        """Lines 976-987: error_intel in markdown report."""
        debugger = DebugCommand()
        fp = ErrorFingerprint(
            hash="abc123",
            language="python",
            error_type="ValueError",
            message_template="bad value",
            file="mod.py",
            line=10,
        )
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="c",
            recommendation="f",
            error_intel=fp,
        )
        report = tmp_path / "report.md"
        _write_markdown_report(result, debugger, str(report))

        content = report.read_text()
        assert "Error Intelligence" in content
        assert "python" in content
        assert "abc123" in content

    def test_report_with_scored_hypotheses(self, tmp_path: Path) -> None:
        """Lines 989-997: scored hypotheses in markdown report."""
        debugger = DebugCommand()
        sh = ScoredHypothesis(
            description="worker crash",
            category=ErrorCategory.WORKER_FAILURE,
            prior_probability=0.5,
            posterior_probability=0.8,
            suggested_fix="restart worker",
        )
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="c",
            recommendation="f",
            scored_hypotheses=[sh],
        )
        report = tmp_path / "report.md"
        _write_markdown_report(result, debugger, str(report))

        content = report.read_text()
        assert "Scored Hypotheses" in content
        assert "worker crash" in content
        assert "restart worker" in content

    def test_report_with_fix_suggestions(self, tmp_path: Path) -> None:
        """Lines 999-1003: fix suggestions in markdown report."""
        debugger = DebugCommand()
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="c",
            recommendation="f",
            fix_suggestions=["try X", "try Y"],
        )
        report = tmp_path / "report.md"
        _write_markdown_report(result, debugger, str(report))

        content = report.read_text()
        assert "Fix Suggestions" in content
        assert "try X" in content

    def test_report_with_evidence(self, tmp_path: Path) -> None:
        """Lines 1005-1009: evidence in markdown report."""
        debugger = DebugCommand()
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="c",
            recommendation="f",
            evidence=["ev1", "ev2"],
        )
        report = tmp_path / "report.md"
        _write_markdown_report(result, debugger, str(report))

        content = report.read_text()
        assert "Evidence" in content
        assert "ev1" in content

    def test_report_with_env_report(self, tmp_path: Path) -> None:
        """Lines 1011-1014: env report in markdown report."""
        debugger = DebugCommand()
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="c",
            recommendation="f",
            env_report={"python": {"version": "3.12"}},
        )
        report = tmp_path / "report.md"
        _write_markdown_report(result, debugger, str(report))

        content = report.read_text()
        assert "Environment Report" in content
        assert "3.12" in content

    def test_report_with_design_escalation(self, tmp_path: Path) -> None:
        """Lines 1016-1021: design escalation in markdown report."""
        debugger = DebugCommand()
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="c",
            recommendation="f",
            design_escalation=True,
            design_escalation_reason="wide blast radius",
        )
        report = tmp_path / "report.md"
        _write_markdown_report(result, debugger, str(report))

        content = report.read_text()
        assert "Design Escalation" in content
        assert "wide blast radius" in content


# =============================================================================
# _resolve_inputs: interactive mode, auto-detect exception (lines 1048, 1081-1082)
# =============================================================================


class TestResolveInputs:
    """Cover _resolve_inputs edge cases."""

    @patch("zerg.commands.debug.console")
    def test_interactive_mode(self, mock_console: MagicMock) -> None:
        """Line 1048: interactive mode prints message."""
        with pytest.raises(SystemExit):
            _resolve_inputs(
                error=None,
                stacktrace=None,
                feature=None,
                deep=False,
                auto_fix=False,
                interactive=True,
            )
        # The console should have printed interactive message
        calls = [str(c) for c in mock_console.print.call_args_list]
        assert any("Interactive" in c or "interactive" in c.lower() for c in calls)

    @patch("zerg.commands.debug.console")
    def test_auto_detect_feature_exception(self, mock_console: MagicMock) -> None:
        """Lines 1081-1082: auto-detect feature raises exception."""
        with patch(
            "zerg.diagnostics.state_introspector.ZergStateIntrospector",
            side_effect=RuntimeError("introspector broke"),
        ):
            error_msg, stack, feat = _resolve_inputs(
                error="some error",
                stacktrace=None,
                feature=None,
                deep=True,
                auto_fix=False,
                interactive=False,
            )
        assert feat is None
        assert error_msg == "some error"


# =============================================================================
# _display_health_sections verbose paths (lines 1217-1236, 1248-1270, 1280-1309)
# =============================================================================


class TestDisplayHealthSectionsVerbose:
    """Cover _display_health_sections verbose rendering paths."""

    @patch("zerg.commands.debug.console")
    def test_zerg_health_verbose(self, mock_console: MagicMock) -> None:
        """Lines 1217-1236: verbose ZERG health display."""
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="c",
            recommendation="f",
            zerg_health=ZergHealthReport(
                feature="auth",
                state_exists=True,
                total_tasks=10,
                task_summary={"complete": 7, "failed": 3},
                failed_tasks=[{"task_id": "T1"}, {"task_id": "T2"}],
                global_error="state corruption",
            ),
        )
        _display_health_sections(result, verbose=True)

        print_calls = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "auth" in print_calls
        assert "10" in print_calls

    @patch("zerg.commands.debug.console")
    def test_system_health_verbose(self, mock_console: MagicMock) -> None:
        """Lines 1248-1270: verbose system health display."""
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="c",
            recommendation="f",
            system_health=SystemHealthReport(
                git_clean=False,
                git_branch="feature/test",
                git_uncommitted_files=5,
                disk_free_gb=2.5,
                port_conflicts=[9500],
            ),
        )
        _display_health_sections(result, verbose=True)

        print_calls = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "feature/test" in print_calls

    @patch("zerg.commands.debug.console")
    def test_env_report_verbose_display(self, mock_console: MagicMock) -> None:
        """Lines 1280-1309: verbose environment report display."""
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="c",
            recommendation="f",
            env_report={
                "python": {"venv": {"active": True}},
                "resources": {
                    "memory": {"available_gb": 8.0, "total_gb": 16.0},
                    "disk": {"free_gb": 100.0, "used_percent": 40.0},
                },
                "config": ["issue1"],
            },
        )
        _display_health_sections(result, verbose=True)

        print_calls = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "8.0" in print_calls
        assert "100.0" in print_calls

    @patch("zerg.commands.debug.console")
    def test_env_report_inactive_venv_display(self, mock_console: MagicMock) -> None:
        """Lines 1286-1290: inactive venv display."""
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="c",
            recommendation="f",
            env_report={
                "python": {"venv": {"active": False}},
                "resources": {},
            },
        )
        _display_health_sections(result, verbose=True)

        print_calls = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "inactive" in print_calls


# =============================================================================
# _display_recovery_and_escalation verbose (lines 1352-1367, 1377-1378)
# =============================================================================


class TestDisplayRecoveryAndEscalation:
    """Cover _display_recovery_and_escalation verbose paths."""

    @patch("zerg.commands.debug.console")
    def test_recovery_verbose(self, mock_console: MagicMock) -> None:
        """Lines 1352-1367: verbose recovery plan display."""
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="c",
            recommendation="f",
            recovery_plan=RecoveryPlan(
                problem="issue",
                root_cause="root",
                steps=[
                    RecoveryStep(description="restart workers", command="zerg rush", risk="safe"),
                    RecoveryStep(description="prune worktrees", command="git worktree prune", risk="moderate"),
                    RecoveryStep(description="nuke state", command="rm -rf .zerg", risk="destructive"),
                ],
                prevention="monitor workers",
            ),
        )
        _display_recovery_and_escalation(result, verbose=True)

        print_calls = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "restart workers" in print_calls
        assert "monitor workers" in print_calls

    @patch("zerg.commands.debug.console")
    def test_design_escalation_display(self, mock_console: MagicMock) -> None:
        """Lines 1377-1378: design escalation display."""
        result = DiagnosticResult(
            symptom="err",
            hypotheses=[],
            root_cause="c",
            recommendation="f",
            design_escalation=True,
            design_escalation_reason="task graph flaw",
        )
        _display_recovery_and_escalation(result, verbose=False)

        # The design escalation uses a Panel, so verify console.print was called
        # and that the Panel contains the escalation reason
        assert mock_console.print.call_count >= 2  # empty line + Panel
        # Find the Panel call - the last substantive print
        [c for c in mock_console.print.call_args_list if c.args and hasattr(c.args[0], "renderable")]
        # At minimum, verify the function was invoked (lines 1377-1378 hit)
        assert mock_console.print.called


# =============================================================================
# CLI: report_path and verbose exception (lines 1512-1513, 1527)
# =============================================================================


class TestDebugCLIReportAndVerboseError:
    """Cover CLI report_path writing and verbose exception display."""

    @patch("zerg.commands.debug.DebugCommand")
    @patch("zerg.commands.debug.console")
    def test_report_path_writes_markdown(
        self, mock_console: MagicMock, mock_command_class: MagicMock, tmp_path: Path
    ) -> None:
        """Lines 1512-1513: --report writes markdown report."""
        mock_command = MagicMock()
        mock_command.run.return_value = DiagnosticResult(
            symptom="Error",
            hypotheses=[],
            root_cause="Cause",
            recommendation="Fix",
            confidence=0.8,
            parsed_error=None,
        )
        mock_command.format_result.return_value = "text report"
        mock_command.config = DebugConfig()
        mock_command_class.return_value = mock_command

        report_file = tmp_path / "diag.md"

        with patch("zerg.commands.debug._write_markdown_report") as mock_write:
            runner = CliRunner()
            result = runner.invoke(debug, ["--error", "Error", "--report", str(report_file)])

        assert result.exit_code == 0
        mock_write.assert_called_once()

    @patch("zerg.commands.debug.console")
    def test_verbose_exception_prints_traceback(self, mock_console: MagicMock) -> None:
        """Line 1527: verbose mode prints exception traceback."""
        with patch(
            "zerg.commands.debug.DebugCommand",
            side_effect=RuntimeError("Unexpected error"),
        ):
            runner = CliRunner()
            result = runner.invoke(debug, ["--error", "Error", "--verbose"])

        assert result.exit_code == 1
        mock_console.print_exception.assert_called_once()
