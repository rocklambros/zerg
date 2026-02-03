"""ZERG debug command - systematic debugging with root cause analysis."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from zerg.logging import get_logger

if TYPE_CHECKING:
    from zerg.diagnostics.log_analyzer import LogPattern
    from zerg.diagnostics.recovery import RecoveryPlan
    from zerg.diagnostics.state_introspector import ZergHealthReport
    from zerg.diagnostics.system_diagnostics import SystemHealthReport
    from zerg.diagnostics.types import (
        ErrorFingerprint,
        ScoredHypothesis,
        TimelineEvent,
    )

console = Console()
logger = get_logger("debug")


class DebugPhase(Enum):
    """Phases of debugging process."""

    SYMPTOM = "symptom"
    HYPOTHESIS = "hypothesis"
    TEST = "test"
    ROOT_CAUSE = "root_cause"


@dataclass
class DebugConfig:
    """Configuration for debug command."""

    verbose: bool = False
    max_hypotheses: int = 3
    auto_test: bool = False


@dataclass
class Hypothesis:
    """A hypothesis about the problem cause."""

    description: str
    likelihood: str  # high, medium, low
    test_command: str = ""
    tested: bool = False
    confirmed: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "description": self.description,
            "likelihood": self.likelihood,
            "test_command": self.test_command,
            "tested": self.tested,
            "confirmed": self.confirmed,
        }


@dataclass
class ParsedError:
    """Parsed error information."""

    error_type: str = ""
    message: str = ""
    file: str = ""
    line: int = 0
    stack_trace: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "error_type": self.error_type,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "stack_trace": self.stack_trace,
        }


@dataclass
class DiagnosticResult:
    """Result of diagnostic analysis."""

    symptom: str
    hypotheses: list[Hypothesis]
    root_cause: str
    recommendation: str
    phase: DebugPhase = DebugPhase.ROOT_CAUSE
    confidence: float = 0.8
    parsed_error: ParsedError | None = None
    # Deep diagnostics fields (optional, backward compatible)
    zerg_health: ZergHealthReport | None = None
    system_health: SystemHealthReport | None = None
    recovery_plan: RecoveryPlan | None = None
    evidence: list[str] = field(default_factory=list)
    log_patterns: list[LogPattern] = field(default_factory=list)
    # Enhanced diagnostic fields
    error_intel: ErrorFingerprint | None = None
    timeline: list[TimelineEvent] = field(default_factory=list)
    scored_hypotheses: list[ScoredHypothesis] = field(default_factory=list)
    correlations: list[dict[str, Any]] = field(default_factory=list)
    env_report: dict[str, Any] | None = None
    fix_suggestions: list[str] = field(default_factory=list)
    # Design escalation fields
    design_escalation: bool = False
    design_escalation_reason: str = ""

    @property
    def has_root_cause(self) -> bool:
        """Check if root cause was found."""
        return bool(self.root_cause)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "symptom": self.symptom,
            "root_cause": self.root_cause,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "phase": self.phase.value,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "parsed_error": (self.parsed_error.to_dict() if self.parsed_error else None),
        }
        if self.zerg_health is not None:
            result["zerg_health"] = self.zerg_health.to_dict()
        if self.system_health is not None:
            result["system_health"] = self.system_health.to_dict()
        if self.recovery_plan is not None:
            result["recovery_plan"] = self.recovery_plan.to_dict()
        if self.evidence:
            result["evidence"] = self.evidence
        if self.log_patterns:
            result["log_patterns"] = [p.to_dict() for p in self.log_patterns]
        # Enhanced fields
        if self.error_intel is not None:
            result["error_intel"] = self.error_intel.to_dict()
        if self.timeline:
            result["timeline"] = [t.to_dict() for t in self.timeline]
        if self.scored_hypotheses:
            result["scored_hypotheses"] = [h.to_dict() for h in self.scored_hypotheses]
        if self.correlations:
            result["correlations"] = self.correlations
        if self.env_report is not None:
            result["env_report"] = self.env_report
        if self.fix_suggestions:
            result["fix_suggestions"] = self.fix_suggestions
        if self.design_escalation:
            result["design_escalation"] = self.design_escalation
            result["design_escalation_reason"] = self.design_escalation_reason
        return result


class ErrorParser:
    """Parse error messages and stack traces."""

    # Python error patterns
    PYTHON_ERROR = re.compile(r"(\w+Error|\w+Exception):\s*(.+)")
    PYTHON_FILE_LINE = re.compile(r'File "([^"]+)", line (\d+)')

    # JavaScript error patterns
    JS_ERROR = re.compile(r"(TypeError|ReferenceError|SyntaxError|Error):\s*(.+)")
    JS_FILE_LINE = re.compile(r"at\s+.+\(([^:]+):(\d+):\d+\)")

    # Go error patterns
    GO_FILE_LINE = re.compile(r"([^\s]+\.go):(\d+)")

    # Rust error patterns
    RUST_ERROR = re.compile(r"error\[E\d+\]:\s*(.+)")
    RUST_FILE_LINE = re.compile(r"-->\s*([^:]+):(\d+):\d+")

    def parse(self, error: str) -> ParsedError:
        """Parse error string."""
        result = ParsedError()

        # Try Python patterns first
        match = self.PYTHON_ERROR.search(error)
        if match:
            result.error_type = match.group(1)
            result.message = match.group(2)

        match = self.PYTHON_FILE_LINE.search(error)
        if match:
            result.file = match.group(1)
            result.line = int(match.group(2))

        # Try JavaScript patterns
        if not result.error_type:
            match = self.JS_ERROR.search(error)
            if match:
                result.error_type = match.group(1)
                result.message = match.group(2)

            match = self.JS_FILE_LINE.search(error)
            if match:
                result.file = match.group(1)
                result.line = int(match.group(2))

        # Try Go patterns
        if not result.file:
            match = self.GO_FILE_LINE.search(error)
            if match:
                result.file = match.group(1)
                result.line = int(match.group(2))

        # Try Rust patterns
        if not result.error_type:
            match = self.RUST_ERROR.search(error)
            if match:
                result.error_type = "RustError"
                result.message = match.group(1)

            match = self.RUST_FILE_LINE.search(error)
            if match:
                result.file = match.group(1)
                result.line = int(match.group(2))

        # Extract stack trace lines
        lines = error.strip().split("\n")
        for line in lines:
            stripped = line.strip()
            if (
                stripped.startswith("File ")
                or stripped.startswith("at ")
                or stripped.startswith("-->")
                or re.match(r"^\s*\d+:", stripped)
            ):
                result.stack_trace.append(stripped)

        return result


class StackTraceAnalyzer:
    """Analyze stack traces for patterns."""

    COMMON_PATTERNS = {
        "recursion": [r"maximum recursion", r"RecursionError", r"stack overflow"],
        "memory": [r"MemoryError", r"out of memory", r"OOM", r"heap"],
        "timeout": [r"TimeoutError", r"timed out", r"deadline exceeded"],
        "connection": [r"ConnectionError", r"connection refused", r"ECONNREFUSED"],
        "permission": [r"PermissionError", r"permission denied", r"EACCES"],
        "import": [r"ImportError", r"ModuleNotFoundError", r"cannot find module"],
        "type": [r"TypeError", r"type error", r"incompatible types"],
        "value": [r"ValueError", r"invalid value", r"invalid argument"],
        "key": [r"KeyError", r"undefined key", r"missing key"],
        "attribute": [r"AttributeError", r"has no attribute", r"undefined property"],
        "index": [r"IndexError", r"index out of range", r"out of bounds"],
        "file": [r"FileNotFoundError", r"no such file", r"ENOENT"],
        "syntax": [r"SyntaxError", r"unexpected token", r"parse error"],
        "assertion": [r"AssertionError", r"assertion failed"],
    }

    def analyze(self, stack_trace: str) -> list[str]:
        """Analyze stack trace for patterns."""
        patterns = []
        trace_lower = stack_trace.lower()

        for name, pattern_list in self.COMMON_PATTERNS.items():
            for pattern in pattern_list:
                if re.search(pattern, trace_lower, re.IGNORECASE):
                    if name not in patterns:
                        patterns.append(name)
                    break

        return patterns


class HypothesisGenerator:
    """Generate hypotheses based on error patterns."""

    HYPOTHESIS_TEMPLATES = {
        "recursion": Hypothesis(
            description="Infinite recursion or circular reference",
            likelihood="high",
            test_command="Check for circular imports or recursive calls",
        ),
        "memory": Hypothesis(
            description="Memory exhaustion from large data or leak",
            likelihood="high",
            test_command="Monitor memory usage, check for unbounded collections",
        ),
        "timeout": Hypothesis(
            description="Operation taking too long or blocked",
            likelihood="medium",
            test_command="Check network calls, database queries, or long computations",
        ),
        "connection": Hypothesis(
            description="Network or service connection failure",
            likelihood="high",
            test_command="Verify service is running and accessible",
        ),
        "permission": Hypothesis(
            description="Insufficient permissions for file or resource",
            likelihood="high",
            test_command="Check file permissions and user access rights",
        ),
        "import": Hypothesis(
            description="Missing module or incorrect import path",
            likelihood="high",
            test_command="Verify package is installed and import path is correct",
        ),
        "type": Hypothesis(
            description="Type mismatch or invalid operation on type",
            likelihood="medium",
            test_command="Check argument types and function signatures",
        ),
        "value": Hypothesis(
            description="Invalid value passed to function",
            likelihood="medium",
            test_command="Validate input data and constraints",
        ),
        "key": Hypothesis(
            description="Missing key in dictionary or mapping",
            likelihood="high",
            test_command="Verify key exists before access, use .get() with default",
        ),
        "attribute": Hypothesis(
            description="Accessing non-existent attribute or method",
            likelihood="high",
            test_command="Check object type and available attributes",
        ),
        "index": Hypothesis(
            description="Array/list index out of bounds",
            likelihood="high",
            test_command="Verify collection length before index access",
        ),
        "file": Hypothesis(
            description="File or directory does not exist",
            likelihood="high",
            test_command="Verify path exists and is accessible",
        ),
        "syntax": Hypothesis(
            description="Syntax error in source code",
            likelihood="high",
            test_command="Check for missing brackets, quotes, or keywords",
        ),
        "assertion": Hypothesis(
            description="Assertion condition failed",
            likelihood="medium",
            test_command="Review assertion condition and input values",
        ),
    }

    def generate(self, patterns: list[str], parsed: ParsedError) -> list[Hypothesis]:
        """Generate hypotheses from patterns."""
        hypotheses = []

        for pattern in patterns:
            if pattern in self.HYPOTHESIS_TEMPLATES:
                template = self.HYPOTHESIS_TEMPLATES[pattern]
                hypotheses.append(
                    Hypothesis(
                        description=template.description,
                        likelihood=template.likelihood,
                        test_command=template.test_command,
                    )
                )

        # Add location-specific hypothesis if we have file info
        if parsed.file and parsed.line:
            hypotheses.insert(
                0,
                Hypothesis(
                    description=f"Error at {parsed.file}:{parsed.line}",
                    likelihood="high",
                    test_command=f"Review code at {parsed.file} line {parsed.line}",
                ),
            )

        return hypotheses


class DebugCommand:
    """Main debug command orchestrator."""

    def __init__(self, config: DebugConfig | None = None) -> None:
        """Initialize debug command."""
        self.config = config or DebugConfig()
        self.parser = ErrorParser()
        self.analyzer = StackTraceAnalyzer()
        self.hypothesis_generator = HypothesisGenerator()

    def run(
        self,
        error: str = "",
        stack_trace: str = "",
        feature: str | None = None,
        worker_id: int | None = None,
        deep: bool = False,
        auto_fix: bool = False,
        env: bool = False,
    ) -> DiagnosticResult:
        """Run debug analysis.

        Args:
            error: Error message to analyze
            stack_trace: Stack trace content
            feature: ZERG feature to investigate
            worker_id: Specific worker ID to investigate
            deep: Run system-level diagnostics
            auto_fix: Generate and execute recovery plan
            env: Run environment diagnostics
        """
        full_error = f"{error}\n{stack_trace}".strip()

        # Phase 1: Parse symptom
        symptom = error or "Unknown error"
        parsed = self.parser.parse(full_error)

        # Phase 2: Analyze patterns
        patterns = self.analyzer.analyze(full_error)

        # Phase 3: Generate hypotheses
        hypotheses = self.hypothesis_generator.generate(patterns, parsed)
        hypotheses = hypotheses[: self.config.max_hypotheses]

        # Phase 4: Determine root cause
        root_cause, recommendation, confidence = self._determine_root_cause(parsed, hypotheses)

        result = DiagnosticResult(
            symptom=symptom,
            hypotheses=hypotheses,
            root_cause=root_cause,
            recommendation=recommendation,
            confidence=confidence,
            parsed_error=parsed,
        )

        # Deep diagnostics: ZERG state introspection
        if feature:
            result = self._run_zerg_diagnostics(result, feature, worker_id)

        # Deep diagnostics: system-level checks
        if deep:
            result = self._run_system_diagnostics(result)

        # Recovery planning
        if auto_fix or feature:
            result = self._plan_recovery(result)

        # Enhanced diagnostics pipeline
        result = self._run_enhanced_diagnostics(result, full_error, stack_trace, feature, worker_id, deep, env)

        return result

    def _run_enhanced_diagnostics(
        self,
        result: DiagnosticResult,
        full_error: str,
        stack_trace: str,
        feature: str | None,
        worker_id: int | None,
        deep: bool,
        env: bool,
    ) -> DiagnosticResult:
        """Run enhanced diagnostic engines (error intel, log correlation, etc.)."""
        # Enhanced: Error Intelligence
        try:
            from zerg.diagnostics.error_intel import ErrorIntelEngine

            intel = ErrorIntelEngine()
            result.error_intel = intel.analyze(full_error, stack_trace)
            intel_evidence = intel.get_evidence(result.error_intel)
            for ev in intel_evidence:
                result.evidence.append(ev.description)
        except Exception as e:
            logger.warning(f"Error intelligence failed: {e}")

        # Enhanced: Log Correlation (when feature provided)
        if feature:
            try:
                from zerg.diagnostics.log_correlator import LogCorrelationEngine
                from zerg.diagnostics.types import TimelineEvent as TEType

                correlator = LogCorrelationEngine()
                log_result = correlator.analyze(worker_id=worker_id)
                timeline_raw = log_result.get("timeline", [])
                result.timeline = [TEType(**e) if isinstance(e, dict) else e for e in timeline_raw]
                result.correlations = log_result.get("correlations", [])
            except Exception as e:
                logger.warning(f"Log correlation failed: {e}")

        # Enhanced: Hypothesis Engine
        try:
            from zerg.diagnostics.hypothesis_engine import HypothesisEngine
            from zerg.diagnostics.types import Evidence as TypedEvidence

            hypo_engine = HypothesisEngine()
            if result.error_intel:
                # Convert string evidence to typed Evidence for the engine
                typed_evidence = [
                    TypedEvidence(
                        description=ev_str,
                        source="diagnostic",
                        confidence=0.5,
                    )
                    for ev_str in result.evidence
                ]
                result.scored_hypotheses = hypo_engine.analyze(result.error_intel, typed_evidence)
        except Exception as e:
            logger.warning(f"Hypothesis engine failed: {e}")

        # Enhanced: Code-Aware Fixes
        try:
            from zerg.diagnostics.code_fixer import CodeAwareFixer

            fixer = CodeAwareFixer()
            if result.error_intel:
                from zerg.diagnostics.types import Evidence as TypedEvidence2

                typed_evidence_fix = [
                    TypedEvidence2(
                        description=ev_str,
                        source="diagnostic",
                        confidence=0.5,
                    )
                    for ev_str in result.evidence
                ]
                fix_result = fixer.analyze(result.error_intel, typed_evidence_fix)
                result.fix_suggestions = fix_result.get("suggestions", [])
        except Exception as e:
            logger.warning(f"Code fixer failed: {e}")

        # Enhanced: Environment Diagnostics
        if deep or env:
            try:
                from zerg.diagnostics.env_diagnostics import EnvDiagnosticsEngine

                env_engine = EnvDiagnosticsEngine()
                result.env_report = env_engine.run_all()
            except Exception as e:
                logger.warning(f"Environment diagnostics failed: {e}")

        return result

    def _run_zerg_diagnostics(
        self,
        result: DiagnosticResult,
        feature: str,
        worker_id: int | None = None,
    ) -> DiagnosticResult:
        """Run ZERG state introspection and log analysis."""
        from zerg.diagnostics.log_analyzer import LogAnalyzer
        from zerg.diagnostics.state_introspector import ZergStateIntrospector

        try:
            introspector = ZergStateIntrospector()
            result.zerg_health = introspector.get_health_report(feature)

            # Add evidence from health report
            health = result.zerg_health
            if health.failed_tasks:
                result.evidence.append(f"{len(health.failed_tasks)} failed task(s)")
            if health.stale_tasks:
                result.evidence.append(f"{len(health.stale_tasks)} stale task(s)")
            if health.global_error:
                result.evidence.append(f"Global error: {health.global_error}")

            # Log analysis
            analyzer = LogAnalyzer()
            result.log_patterns = analyzer.scan_worker_logs(worker_id)

            if result.log_patterns:
                result.evidence.append(f"{len(result.log_patterns)} error pattern(s) in logs")
        except Exception as e:
            logger.warning(f"ZERG diagnostics failed: {e}")
            result.evidence.append(f"ZERG diagnostics error: {e}")

        return result

    def _run_system_diagnostics(self, result: DiagnosticResult) -> DiagnosticResult:
        """Run system-level diagnostic checks."""
        from zerg.diagnostics.system_diagnostics import SystemDiagnostics

        try:
            sys_diag = SystemDiagnostics()
            result.system_health = sys_diag.run_all()

            health = result.system_health
            if not health.git_clean:
                result.evidence.append(f"{health.git_uncommitted_files} uncommitted file(s)")
            if health.port_conflicts:
                result.evidence.append(f"Port conflicts: {health.port_conflicts}")
            if health.orphaned_worktrees:
                result.evidence.append(f"{len(health.orphaned_worktrees)} orphaned worktree(s)")
            if health.disk_free_gb < 1.0:
                result.evidence.append(f"Low disk space: {health.disk_free_gb:.1f} GB free")
        except Exception as e:
            logger.warning(f"System diagnostics failed: {e}")
            result.evidence.append(f"System diagnostics error: {e}")

        return result

    def _plan_recovery(self, result: DiagnosticResult) -> DiagnosticResult:
        """Generate a recovery plan from diagnostic results."""
        from zerg.diagnostics.recovery import RecoveryPlanner

        try:
            planner = RecoveryPlanner()
            result.recovery_plan = planner.plan(result, health=result.zerg_health)
            if result.recovery_plan.needs_design:
                result.design_escalation = True
                result.design_escalation_reason = result.recovery_plan.design_reason
        except Exception as e:
            logger.warning(f"Recovery planning failed: {e}")
            result.evidence.append(f"Recovery planning error: {e}")

        return result

    def _determine_root_cause(self, parsed: ParsedError, hypotheses: list[Hypothesis]) -> tuple[str, str, float]:
        """Determine most likely root cause."""
        confidence = 0.5

        if parsed.error_type and parsed.file:
            confidence = 0.9
            return (
                f"{parsed.error_type} at {parsed.file}:{parsed.line}",
                f"Review code at {parsed.file} line {parsed.line}. Error: {parsed.message}",
                confidence,
            )

        if parsed.error_type:
            confidence = 0.7
            return (
                f"{parsed.error_type}: {parsed.message}",
                f"Investigate {parsed.error_type} - {parsed.message}",
                confidence,
            )

        if hypotheses:
            top = hypotheses[0]
            confidence = {"high": 0.8, "medium": 0.6, "low": 0.4}.get(top.likelihood, 0.5)
            return (
                top.description,
                top.test_command or f"Investigate: {top.description}",
                confidence,
            )

        return "Unknown cause", "Collect more diagnostic information", 0.3

    def format_result(self, result: DiagnosticResult, fmt: str = "text") -> str:
        """Format diagnostic result."""
        if fmt == "json":
            return json.dumps(result.to_dict(), indent=2)

        lines = [
            "Diagnostic Report",
            "=" * 50,
            "",
            f"Symptom: {result.symptom[:100]}",
            "",
        ]

        if result.parsed_error and result.parsed_error.error_type:
            lines.append("Parsed Error:")
            lines.append(f"  Type: {result.parsed_error.error_type}")
            if result.parsed_error.message:
                lines.append(f"  Message: {result.parsed_error.message[:80]}")
            if result.parsed_error.file:
                lines.append(f"  Location: {result.parsed_error.file}:{result.parsed_error.line}")
            lines.append("")

        if result.hypotheses:
            lines.append("Hypotheses:")
            for i, h in enumerate(result.hypotheses, 1):
                icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(h.likelihood, "⚪")
                lines.append(f"  {i}. {icon} [{h.likelihood}] {h.description}")
                if h.test_command and self.config.verbose:
                    lines.append(f"     Test: {h.test_command}")
            lines.append("")

        # Append sections from helpers
        lines.extend(self._format_zerg_health_text(result))
        lines.extend(self._format_log_patterns_text(result))
        lines.extend(self._format_system_health_text(result))

        # Evidence section
        if result.evidence and self.config.verbose:
            lines.append("Evidence:")
            for ev in result.evidence:
                lines.append(f"  - {ev}")
            lines.append("")

        lines.extend(self._format_enhanced_sections_text(result))

        lines.extend(
            [
                f"Root Cause: {result.root_cause}",
                f"Confidence: {result.confidence:.0%}",
                "",
                f"Recommendation: {result.recommendation}",
            ]
        )

        lines.extend(self._format_recovery_plan_text(result))
        lines.extend(self._format_design_escalation_text(result))

        return "\n".join(lines)

    def _format_zerg_health_text(self, result: DiagnosticResult) -> list[str]:
        """Format ZERG health section for text output."""
        lines: list[str] = []
        if result.zerg_health is not None:
            health = result.zerg_health
            if self.config.verbose:
                lines.append("ZERG Health:")
                lines.append(f"  Feature: {health.feature}")
                lines.append(f"  Total Tasks: {health.total_tasks}")
                if health.task_summary:
                    summary = ", ".join(f"{k}: {v}" for k, v in health.task_summary.items())
                    lines.append(f"  Status: {summary}")
                if health.failed_tasks:
                    lines.append(f"  Failed: {len(health.failed_tasks)} task(s)")
                if health.global_error:
                    lines.append(f"  Error: {health.global_error}")
                lines.append("")
            else:
                failed = len(health.failed_tasks) if health.failed_tasks else 0
                summary = f"ZERG: {health.feature} — {health.total_tasks} tasks"
                if failed:
                    summary += f", {failed} failed"
                lines.append(summary)
                lines.append("")
        return lines

    def _format_log_patterns_text(self, result: DiagnosticResult) -> list[str]:
        """Format log patterns section for text output."""
        lines: list[str] = []
        if result.log_patterns and self.config.verbose:
            lines.append("Log Patterns:")
            for pat in result.log_patterns[:5]:
                workers = ", ".join(str(w) for w in pat.worker_ids)
                lines.append(f"  [{pat.count}x] {pat.pattern[:80]} (workers: {workers})")
            lines.append("")
        return lines

    def _format_system_health_text(self, result: DiagnosticResult) -> list[str]:
        """Format system health section for text output."""
        lines: list[str] = []
        if result.system_health is not None:
            sys_h = result.system_health
            if self.config.verbose:
                lines.append("System Health:")
                lines.append(f"  Git: {'clean' if sys_h.git_clean else 'dirty'}")
                lines.append(f"  Branch: {sys_h.git_branch}")
                lines.append(f"  Disk Free: {sys_h.disk_free_gb:.1f} GB")
                if sys_h.port_conflicts:
                    lines.append(f"  Port Conflicts: {sys_h.port_conflicts}")
                if sys_h.orphaned_worktrees:
                    lines.append(f"  Orphaned Worktrees: {len(sys_h.orphaned_worktrees)}")
                lines.append("")
            else:
                git_state = "clean" if sys_h.git_clean else "dirty"
                lines.append(f"System: git {git_state}, {sys_h.disk_free_gb:.1f}GB free")
                lines.append("")
        return lines

    def _format_enhanced_sections_text(self, result: DiagnosticResult) -> list[str]:
        """Format enhanced diagnostic sections (error intel, scored hypotheses, etc.)."""
        lines: list[str] = []

        # Error Intelligence section
        if result.error_intel is not None:
            intel = result.error_intel
            lines.append("Error Intelligence:")
            lines.append(f"  Language: {intel.language}")
            lines.append(f"  Type: {intel.error_type}")
            if intel.file:
                loc = f"{intel.file}:{intel.line}" if intel.line else intel.file
                lines.append(f"  Location: {loc}")
            if intel.hash:
                lines.append(f"  Fingerprint: {intel.hash}")
            lines.append("")

        # Scored Hypotheses section
        if result.scored_hypotheses:
            lines.append("Scored Hypotheses (Bayesian):")
            for i, sh in enumerate(result.scored_hypotheses, 1):
                lines.append(f"  {i}. [{sh.posterior_probability:.0%}] {sh.description}")
                if sh.suggested_fix and self.config.verbose:
                    lines.append(f"     Fix: {sh.suggested_fix}")
            lines.append("")

        # Fix Suggestions section
        if result.fix_suggestions:
            lines.append("Fix Suggestions:")
            for i, fix in enumerate(result.fix_suggestions, 1):
                lines.append(f"  {i}. {fix}")
            lines.append("")

        # Environment Report section
        if result.env_report is not None and self.config.verbose:
            lines.append("Environment Report:")
            python_info = result.env_report.get("python", {})
            venv_info = python_info.get("venv", {})
            if venv_info:
                active = "active" if venv_info.get("active") else "inactive"
                lines.append(f"  Python venv: {active}")
            resources = result.env_report.get("resources", {})
            memory = resources.get("memory", {})
            if memory:
                lines.append(
                    f"  Memory: {memory.get('available_gb', 0):.1f}GB available"
                    f" / {memory.get('total_gb', 0):.1f}GB total"
                )
            disk = resources.get("disk", {})
            if disk:
                lines.append(f"  Disk: {disk.get('free_gb', 0):.1f}GB free ({disk.get('used_percent', 0):.0f}% used)")
            config_issues = result.env_report.get("config", [])
            if config_issues:
                lines.append(f"  Config issues: {len(config_issues)}")
            lines.append("")

        return lines

    def _format_recovery_plan_text(self, result: DiagnosticResult) -> list[str]:
        """Format recovery plan section for text output."""
        lines: list[str] = []
        if result.recovery_plan is not None:
            plan = result.recovery_plan
            lines.append("")
            if self.config.verbose:
                lines.append("Recovery Plan:")
                for i, step in enumerate(plan.steps, 1):
                    risk_icon = {"safe": "G", "moderate": "Y", "destructive": "R"}.get(step.risk, "?")
                    lines.append(f"  {i}. [{risk_icon}] {step.description}")
                    lines.append(f"     $ {step.command}")
                if plan.verification_command:
                    lines.append(f"  Verify: {plan.verification_command}")
                if plan.prevention:
                    lines.append(f"  Prevent: {plan.prevention}")
            else:
                lines.append(f"Recovery: {len(plan.steps)} steps available (use --verbose)")
        return lines

    def _format_design_escalation_text(self, result: DiagnosticResult) -> list[str]:
        """Format design escalation section for text output."""
        lines: list[str] = []
        if result.design_escalation:
            lines.append("")
            lines.append("DESIGN ESCALATION")
            lines.append(f"  Reason: {result.design_escalation_reason}")
            lines.append("  Action: Run 'zerg design' or '/zerg:design' to redesign")
        return lines


def _load_stacktrace_file(filepath: str) -> str:
    """Load stack trace from file."""
    try:
        path = Path(filepath)
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception as e:
        logger.debug(f"Diagnostic check failed: {e}")
    return ""


def _write_markdown_report(
    result: DiagnosticResult,
    debugger: DebugCommand,
    report_path: str,
) -> None:
    """Write a full markdown report to the given path."""
    lines: list[str] = [
        "# ZERG Diagnostic Report",
        "",
        f"**Symptom:** {result.symptom}",
        "",
        f"**Root Cause:** {result.root_cause}",
        "",
        f"**Confidence:** {result.confidence:.0%}",
        "",
        f"**Recommendation:** {result.recommendation}",
        "",
    ]

    if result.parsed_error and result.parsed_error.error_type:
        lines.append("## Parsed Error")
        lines.append(f"- **Type:** {result.parsed_error.error_type}")
        if result.parsed_error.message:
            lines.append(f"- **Message:** {result.parsed_error.message}")
        if result.parsed_error.file:
            lines.append(f"- **Location:** {result.parsed_error.file}:{result.parsed_error.line}")
        lines.append("")

    if result.hypotheses:
        lines.append("## Hypotheses")
        for i, h in enumerate(result.hypotheses, 1):
            lines.append(f"{i}. **[{h.likelihood}]** {h.description}")
            if h.test_command:
                lines.append(f"   - Test: {h.test_command}")
        lines.append("")

    if result.error_intel is not None:
        lines.append("## Error Intelligence")
        lines.append(f"- **Language:** {result.error_intel.language}")
        lines.append(f"- **Type:** {result.error_intel.error_type}")
        if result.error_intel.file:
            lines.append(f"- **File:** {result.error_intel.file}:{result.error_intel.line}")
        if result.error_intel.hash:
            lines.append(f"- **Fingerprint:** {result.error_intel.hash}")
        lines.append("")

    if result.scored_hypotheses:
        lines.append("## Scored Hypotheses (Bayesian)")
        for i, sh in enumerate(result.scored_hypotheses, 1):
            lines.append(f"{i}. **[{sh.posterior_probability:.0%}]** {sh.description}")
            if sh.suggested_fix:
                lines.append(f"   - Fix: {sh.suggested_fix}")
        lines.append("")

    if result.fix_suggestions:
        lines.append("## Fix Suggestions")
        for i, fix in enumerate(result.fix_suggestions, 1):
            lines.append(f"{i}. {fix}")
        lines.append("")

    if result.evidence:
        lines.append("## Evidence")
        for ev in result.evidence:
            lines.append(f"- {ev}")
        lines.append("")

    if result.env_report is not None:
        lines.append("## Environment Report")
        lines.append(f"```json\n{json.dumps(result.env_report, indent=2)}\n```")
        lines.append("")

    if result.design_escalation:
        lines.append("## Design Escalation")
        lines.append(f"**Reason:** {result.design_escalation_reason}")
        lines.append("")
        lines.append("**Action:** Run `zerg design` or `/zerg:design` to redesign")
        lines.append("")

    # Write text format at the end
    lines.append("## Full Text Report")
    lines.append("```")
    lines.append(debugger.format_result(result, "text"))
    lines.append("```")

    Path(report_path).write_text("\n".join(lines), encoding="utf-8")


def _resolve_inputs(
    error: str | None,
    stacktrace: str | None,
    feature: str | None,
    deep: bool,
    auto_fix: bool,
    interactive: bool,
) -> tuple[str, str, str | None]:
    """Resolve and validate debug command inputs.

    Returns:
        Tuple of (error_message, stack_trace_content, feature).
        Raises SystemExit(0) if no input is provided.
    """
    # Handle interactive mode
    if interactive:
        console.print("[yellow]Interactive mode coming soon[/yellow]")

    # Load stack trace from file if provided
    stack_trace_content = ""
    if stacktrace:
        stack_trace_content = _load_stacktrace_file(stacktrace)
        if not stack_trace_content:
            console.print(f"[yellow]Warning: Could not load {stacktrace}[/yellow]")

    # Need at least error, stack trace, or feature
    error_message = error or ""
    if not error_message and not stack_trace_content and not feature:
        console.print("[yellow]No error provided[/yellow]")
        console.print("Use --error to specify an error message")
        console.print("Use --stacktrace to provide a stack trace file")
        console.print("Use --feature to investigate a ZERG feature")
        raise SystemExit(0)

    # Auto-detect feature if not provided but deep/auto-fix requested
    if not feature and (deep or auto_fix):
        try:
            from zerg.diagnostics.state_introspector import (
                ZergStateIntrospector,
            )

            introspector = ZergStateIntrospector()
            feature = introspector.find_latest_feature()
            if feature:
                console.print(f"[dim]Auto-detected feature: {feature}[/dim]")
        except Exception as e:
            logger.debug(f"Diagnostic check failed: {e}")

    # If only feature given (no error), set a default symptom
    if not error_message and not stack_trace_content and feature:
        error_message = f"Investigating feature: {feature}"

    return error_message, stack_trace_content, feature


def _display_symptom_phase(result: DiagnosticResult) -> None:
    """Display Phase 1: Symptom Analysis output."""
    console.print(Panel("[bold]Phase 1: Symptom Analysis[/bold]", style="cyan"))
    console.print(f"  Error: {result.symptom[:100]}")

    if result.parsed_error and result.parsed_error.error_type:
        console.print(f"  Type: [yellow]{result.parsed_error.error_type}[/yellow]")
        if result.parsed_error.file:
            console.print(f"  Location: [cyan]{result.parsed_error.file}:{result.parsed_error.line}[/cyan]")
    console.print()


def _display_hypotheses_phase(result: DiagnosticResult, verbose: bool) -> None:
    """Display Phase 2: Hypothesis Generation output."""
    if not result.hypotheses:
        return

    console.print(Panel("[bold]Phase 2: Hypothesis Generation[/bold]", style="cyan"))
    table = Table()
    table.add_column("#", style="dim")
    table.add_column("Likelihood")
    table.add_column("Hypothesis")

    for i, h in enumerate(result.hypotheses, 1):
        likelihood_color = {
            "high": "red",
            "medium": "yellow",
            "low": "green",
        }.get(h.likelihood, "white")
        table.add_row(
            str(i),
            f"[{likelihood_color}]{h.likelihood}[/{likelihood_color}]",
            h.description,
        )

    console.print(table)

    if verbose:
        console.print("\n[dim]Test commands:[/dim]")
        for i, h in enumerate(result.hypotheses, 1):
            if h.test_command:
                console.print(f"  {i}. {h.test_command}")
    console.print()


def _display_enhanced_sections(result: DiagnosticResult) -> None:
    """Display enhanced diagnostic sections (error intel, scored hypotheses, fixes)."""
    # Error Intelligence
    if result.error_intel is not None:
        console.print(Panel("[bold]Error Intelligence[/bold]", style="cyan"))
        intel = result.error_intel
        console.print(f"  Language: [bold]{intel.language}[/bold]")
        console.print(f"  Type: [yellow]{intel.error_type}[/yellow]")
        if intel.file:
            loc = f"{intel.file}:{intel.line}" if intel.line else intel.file
            console.print(f"  Location: [cyan]{loc}[/cyan]")
        if intel.hash:
            console.print(f"  Fingerprint: [dim]{intel.hash}[/dim]")
        console.print()

    # Scored Hypotheses
    if result.scored_hypotheses:
        console.print(
            Panel(
                "[bold]Scored Hypotheses (Bayesian)[/bold]",
                style="cyan",
            )
        )
        sh_table = Table()
        sh_table.add_column("#", style="dim")
        sh_table.add_column("Probability")
        sh_table.add_column("Hypothesis")

        for i, sh in enumerate(result.scored_hypotheses, 1):
            prob = sh.posterior_probability
            prob_color = "red" if prob >= 0.7 else "yellow" if prob >= 0.4 else "green"
            sh_table.add_row(
                str(i),
                f"[{prob_color}]{prob:.0%}[/{prob_color}]",
                sh.description,
            )

        console.print(sh_table)
        console.print()

    # Fix Suggestions
    if result.fix_suggestions:
        fix_lines = "\n".join(f"  {i}. {fix}" for i, fix in enumerate(result.fix_suggestions, 1))
        console.print(
            Panel(
                f"[bold]Fix Suggestions[/bold]\n{fix_lines}",
                style="green",
            )
        )
        console.print()


def _display_health_sections(result: DiagnosticResult, verbose: bool) -> None:
    """Display ZERG health, system health, environment, and evidence sections."""
    # ZERG health
    if result.zerg_health is not None:
        health = result.zerg_health
        if verbose:
            console.print(Panel("[bold]ZERG State[/bold]", style="cyan"))
            console.print(f"  Feature: {health.feature}")
            console.print(f"  Tasks: {health.total_tasks}")
            if health.task_summary:
                summary = ", ".join(f"{k}: {v}" for k, v in health.task_summary.items())
                console.print(f"  Status: {summary}")
            if health.failed_tasks:
                console.print(f"  [red]Failed: {len(health.failed_tasks)}[/red]")
            if health.global_error:
                console.print(f"  [red]Error: {health.global_error}[/red]")
            console.print()
        else:
            failed = len(health.failed_tasks) if health.failed_tasks else 0
            summary = f"ZERG: {health.feature} — {health.total_tasks} tasks"
            if failed:
                summary += f", {failed} failed"
            console.print(f"  [dim]{summary}[/dim]")

    # System health
    if result.system_health is not None:
        sys_h = result.system_health
        if verbose:
            console.print(Panel("[bold]System Health[/bold]", style="cyan"))
            git_status = (
                "[green]clean[/green]"
                if sys_h.git_clean
                else f"[yellow]dirty ({sys_h.git_uncommitted_files} files)[/yellow]"
            )
            console.print(f"  Git: {git_status}")
            console.print(f"  Branch: {sys_h.git_branch}")
            disk_color = "green" if sys_h.disk_free_gb >= 5.0 else "yellow" if sys_h.disk_free_gb >= 1.0 else "red"
            console.print(f"  Disk: [{disk_color}]{sys_h.disk_free_gb:.1f} GB free[/{disk_color}]")
            if sys_h.port_conflicts:
                console.print(f"  [yellow]Port conflicts: {sys_h.port_conflicts}[/yellow]")
            console.print()
        else:
            git_state = "clean" if sys_h.git_clean else "dirty"
            console.print(f"  [dim]System: git {git_state}, {sys_h.disk_free_gb:.1f}GB free[/dim]")

    # Environment Report
    if result.env_report is not None and verbose:
        console.print(Panel("[bold]Environment Report[/bold]", style="cyan"))
        python_info = result.env_report.get("python", {})
        venv_info = python_info.get("venv", {})
        if venv_info:
            active = "active" if venv_info.get("active") else "inactive"
            venv_color = "green" if venv_info.get("active") else "yellow"
            console.print(f"  Python venv: [{venv_color}]{active}[/{venv_color}]")
        resources = result.env_report.get("resources", {})
        memory = resources.get("memory", {})
        if memory:
            console.print(
                f"  Memory: {memory.get('available_gb', 0):.1f}GB available / {memory.get('total_gb', 0):.1f}GB total"
            )
        disk_info = resources.get("disk", {})
        if disk_info:
            console.print(
                f"  Disk: {disk_info.get('free_gb', 0):.1f}GB free ({disk_info.get('used_percent', 0):.0f}% used)"
            )
        config_issues = result.env_report.get("config", [])
        if config_issues:
            console.print(f"  [yellow]Config issues: {len(config_issues)}[/yellow]")
        console.print()

    # Evidence
    if result.evidence and verbose:
        console.print(Panel("[bold]Evidence[/bold]", style="cyan"))
        for ev in result.evidence:
            console.print(f"  - {ev}")
        console.print()


def _display_root_cause_phase(result: DiagnosticResult) -> None:
    """Display Phase 4: Root Cause and recommendation."""
    console.print(Panel("[bold]Phase 4: Root Cause[/bold]", style="cyan"))
    confidence_color = "green" if result.confidence >= 0.7 else "yellow" if result.confidence >= 0.5 else "red"
    console.print(f"  Root Cause: [bold]{result.root_cause}[/bold]")
    console.print(f"  Confidence: [{confidence_color}]{result.confidence:.0%}[/{confidence_color}]")
    console.print()
    console.print(
        Panel(
            f"[bold]Recommendation:[/bold] {result.recommendation}",
            style="green",
        )
    )


def _display_recovery_and_escalation(result: DiagnosticResult, verbose: bool) -> None:
    """Display recovery plan and design escalation sections."""
    if result.recovery_plan is not None:
        plan = result.recovery_plan
        console.print()
        if verbose:
            console.print(Panel("[bold]Recovery Plan[/bold]", style="cyan"))
            for i, step in enumerate(plan.steps, 1):
                risk_color = {
                    "safe": "green",
                    "moderate": "yellow",
                    "destructive": "red",
                }.get(step.risk, "white")
                console.print(f"  {i}. [{risk_color}][{step.risk}][/{risk_color}] {step.description}")
                console.print(f"     [dim]$ {step.command}[/dim]")
            if plan.prevention:
                console.print(f"\n  [dim]Prevention: {plan.prevention}[/dim]")
        else:
            console.print(f"  [dim]Recovery: {len(plan.steps)} steps available (use --verbose)[/dim]")

    if result.design_escalation:
        console.print()
        console.print(
            Panel(
                f"[bold]Design Escalation[/bold]\n"
                f"  Reason: {result.design_escalation_reason}\n"
                f"  Action: Run [bold]zerg design[/bold] or "
                f"[bold]/zerg:design[/bold] to redesign",
                style="yellow",
            )
        )


def _display_rich_output(
    result: DiagnosticResult,
    debugger: DebugCommand,
    verbose: bool,
) -> str:
    """Display rich console output for diagnostic result.

    Returns the text-formatted output content.
    """
    _display_symptom_phase(result)
    _display_hypotheses_phase(result, verbose)
    _display_enhanced_sections(result)
    _display_health_sections(result, verbose)
    _display_root_cause_phase(result)
    _display_recovery_and_escalation(result, verbose)

    return debugger.format_result(result, "text")


@click.command()
@click.option("--error", "-e", help="Error message to analyze")
@click.option("--stacktrace", "-s", help="Path to stack trace file")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--output", "-o", help="Output file for diagnostic report")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--feature", "-f", help="ZERG feature to investigate")
@click.option("--worker", "-w", type=int, help="Specific worker ID to investigate")
@click.option("--deep", is_flag=True, help="Run system-level diagnostics")
@click.option("--auto-fix", is_flag=True, help="Generate and execute recovery plan")
@click.option("--env", is_flag=True, help="Run environment diagnostics")
@click.option("--interactive", "-i", is_flag=True, help="Interactive debug mode")
@click.option("--report", "report_path", help="Write full markdown report to file")
@click.pass_context
def debug(
    ctx: click.Context,
    error: str | None,
    stacktrace: str | None,
    verbose: bool,
    output: str | None,
    json_output: bool,
    feature: str | None,
    worker: int | None,
    deep: bool,
    auto_fix: bool,
    env: bool,
    interactive: bool,
    report_path: str | None,
) -> None:
    """Systematic debugging with root cause analysis.

    Four-phase process:
    1. Symptom: Parse and identify the error
    2. Hypothesis: Generate possible causes
    3. Test: Verify hypotheses with diagnostics
    4. Root Cause: Determine actual cause with confidence score

    Deep diagnostics (with --feature or --deep):
    5. ZERG state introspection and log analysis
    6. System health checks (git, disk, docker, ports)
    7. Recovery planning with executable steps

    Enhanced diagnostics:
    8. Error intelligence with multi-language fingerprinting
    9. Bayesian hypothesis scoring
    10. Code-aware fix suggestions
    11. Environment diagnostics (--env)

    Examples:

        zerg debug --error "ValueError: invalid literal"

        zerg debug --stacktrace trace.txt

        zerg debug --feature my-feature --deep

        zerg debug --feature my-feature --auto-fix

        zerg debug --error "ImportError" --json

        zerg debug --error "TypeError" --env

        zerg debug --error "KeyError" --report diag.md
    """
    try:
        console.print("\n[bold cyan]ZERG Debug[/bold cyan]\n")

        # Resolve and validate inputs
        error_message, stack_trace_content, feature = _resolve_inputs(
            error, stacktrace, feature, deep, auto_fix, interactive
        )

        # Create config
        config = DebugConfig(
            verbose=verbose,
            max_hypotheses=5 if verbose else 3,
        )

        # Run diagnostics
        debugger = DebugCommand(config)
        result = debugger.run(
            error=error_message,
            stack_trace=stack_trace_content,
            feature=feature,
            worker_id=worker,
            deep=deep,
            auto_fix=auto_fix,
            env=env,
        )

        # Output
        if json_output:
            output_content = debugger.format_result(result, "json")
            console.print(output_content)
        else:
            output_content = _display_rich_output(result, debugger, verbose)

        # Write to file if requested
        if output:
            Path(output).write_text(output_content, encoding="utf-8")
            console.print(f"\n[green]✓[/green] Report written to {output}")

        # Write markdown report if requested
        if report_path:
            _write_markdown_report(result, debugger, report_path)
            console.print(f"\n[green]✓[/green] Markdown report written to {report_path}")

        raise SystemExit(0)

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        raise SystemExit(130) from None
    except SystemExit:
        raise
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        if verbose:
            console.print_exception()
        logger.exception("Debug command failed")
        raise SystemExit(1) from e
