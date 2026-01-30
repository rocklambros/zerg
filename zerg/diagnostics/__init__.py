"""ZERG diagnostics package - deep debugging with state introspection."""

from zerg.diagnostics.code_fixer import (
    CodeAwareFixer,
    DependencyAnalyzer,
    FixSuggestionGenerator,
    GitContextAnalyzer,
)
from zerg.diagnostics.env_diagnostics import (
    ConfigValidator,
    DockerDiagnostics,
    EnvDiagnosticsEngine,
    PythonEnvDiagnostics,
    ResourceDiagnostics,
)
from zerg.diagnostics.error_intel import (
    ErrorChainAnalyzer,
    ErrorFingerprinter,
    ErrorIntelEngine,
    LanguageDetector,
    MultiLangErrorParser,
)
from zerg.diagnostics.hypothesis_engine import (
    BayesianScorer,
    HypothesisChainer,
    HypothesisEngine,
    HypothesisGenerator,
    HypothesisTestRunner,
)
from zerg.diagnostics.knowledge_base import KNOWN_PATTERNS, KnownPattern, PatternMatcher
from zerg.diagnostics.log_analyzer import LogAnalyzer, LogPattern
from zerg.diagnostics.log_correlator import (
    CrossWorkerCorrelator,
    ErrorEvolutionTracker,
    LogCorrelationEngine,
    TemporalClusterer,
    TimelineBuilder,
)
from zerg.diagnostics.recovery import RecoveryPlan, RecoveryPlanner, RecoveryStep
from zerg.diagnostics.state_introspector import ZergHealthReport, ZergStateIntrospector
from zerg.diagnostics.system_diagnostics import SystemDiagnostics, SystemHealthReport
from zerg.diagnostics.types import (
    DiagnosticContext,
    ErrorCategory,
    ErrorFingerprint,
    ErrorSeverity,
    Evidence,
    ScoredHypothesis,
    TimelineEvent,
)

__all__ = [
    "BayesianScorer",
    "CodeAwareFixer",
    "ConfigValidator",
    "CrossWorkerCorrelator",
    "DependencyAnalyzer",
    "DiagnosticContext",
    "DockerDiagnostics",
    "EnvDiagnosticsEngine",
    "ErrorCategory",
    "ErrorChainAnalyzer",
    "ErrorEvolutionTracker",
    "ErrorFingerprint",
    "ErrorFingerprinter",
    "ErrorIntelEngine",
    "ErrorSeverity",
    "Evidence",
    "FixSuggestionGenerator",
    "GitContextAnalyzer",
    "HypothesisChainer",
    "HypothesisEngine",
    "HypothesisGenerator",
    "HypothesisTestRunner",
    "KNOWN_PATTERNS",
    "KnownPattern",
    "LanguageDetector",
    "LogAnalyzer",
    "LogCorrelationEngine",
    "LogPattern",
    "MultiLangErrorParser",
    "PatternMatcher",
    "PythonEnvDiagnostics",
    "RecoveryPlan",
    "RecoveryPlanner",
    "RecoveryStep",
    "ResourceDiagnostics",
    "ScoredHypothesis",
    "SystemDiagnostics",
    "SystemHealthReport",
    "TemporalClusterer",
    "TimelineBuilder",
    "TimelineEvent",
    "ZergHealthReport",
    "ZergStateIntrospector",
]
