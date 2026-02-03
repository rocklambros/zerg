"""Tests for zerg.diagnostics.types module."""

from __future__ import annotations

from zerg.diagnostics.types import (
    DiagnosticContext,
    ErrorCategory,
    ErrorFingerprint,
    ErrorSeverity,
    Evidence,
    ScoredHypothesis,
    TimelineEvent,
)

# ---------------------------------------------------------------------------
# ErrorSeverity enum
# ---------------------------------------------------------------------------


class TestErrorSeverity:
    """Tests for ErrorSeverity enum."""

    def test_has_critical(self) -> None:
        assert ErrorSeverity.CRITICAL.value == "critical"

    def test_has_error(self) -> None:
        assert ErrorSeverity.ERROR.value == "error"

    def test_has_warning(self) -> None:
        assert ErrorSeverity.WARNING.value == "warning"

    def test_has_info(self) -> None:
        assert ErrorSeverity.INFO.value == "info"

    def test_member_count(self) -> None:
        assert len(ErrorSeverity) == 4


# ---------------------------------------------------------------------------
# ErrorCategory enum
# ---------------------------------------------------------------------------


class TestErrorCategory:
    """Tests for ErrorCategory enum."""

    def test_has_all_ten_values(self) -> None:
        expected = {
            "worker_failure",
            "task_failure",
            "state_corruption",
            "infrastructure",
            "code_error",
            "dependency",
            "merge_conflict",
            "environment",
            "configuration",
            "unknown",
        }
        actual = {member.value for member in ErrorCategory}
        assert actual == expected

    def test_member_count(self) -> None:
        assert len(ErrorCategory) == 10


# ---------------------------------------------------------------------------
# ErrorFingerprint dataclass
# ---------------------------------------------------------------------------


class TestErrorFingerprint:
    """Tests for ErrorFingerprint dataclass."""

    def test_instantiate_with_defaults(self) -> None:
        fp = ErrorFingerprint(
            hash="abc123",
            language="python",
            error_type="ImportError",
            message_template="No module named {mod}",
            file="main.py",
        )
        assert fp.line == 0
        assert fp.column == 0
        assert fp.function == ""
        assert fp.module == ""
        assert fp.chain == []

    def test_to_dict_keys(self) -> None:
        fp = ErrorFingerprint(
            hash="h1",
            language="python",
            error_type="TypeError",
            message_template="tmpl",
            file="f.py",
            line=10,
            column=5,
            function="foo",
            module="bar",
        )
        d = fp.to_dict()
        assert d == {
            "hash": "h1",
            "language": "python",
            "error_type": "TypeError",
            "message_template": "tmpl",
            "file": "f.py",
            "line": 10,
            "column": 5,
            "function": "foo",
            "module": "bar",
            "chain": [],
        }

    def test_chain_nesting(self) -> None:
        inner = ErrorFingerprint(
            hash="inner",
            language="python",
            error_type="ValueError",
            message_template="bad value",
            file="a.py",
        )
        outer = ErrorFingerprint(
            hash="outer",
            language="python",
            error_type="RuntimeError",
            message_template="wrapped",
            file="b.py",
            chain=[inner],
        )
        d = outer.to_dict()
        assert len(d["chain"]) == 1
        assert d["chain"][0]["hash"] == "inner"
        assert d["chain"][0]["error_type"] == "ValueError"


# ---------------------------------------------------------------------------
# TimelineEvent dataclass
# ---------------------------------------------------------------------------


class TestTimelineEvent:
    """Tests for TimelineEvent dataclass."""

    def test_instantiate_with_defaults(self) -> None:
        evt = TimelineEvent(
            timestamp="2025-01-01T00:00:00Z",
            worker_id=1,
            event_type="error",
            message="something failed",
        )
        assert evt.source_file == ""
        assert evt.line_number == 0
        assert evt.correlation_id == ""

    def test_to_dict(self) -> None:
        evt = TimelineEvent(
            timestamp="t1",
            worker_id=2,
            event_type="info",
            message="msg",
            source_file="x.py",
            line_number=42,
            correlation_id="corr-1",
        )
        d = evt.to_dict()
        assert d["worker_id"] == 2
        assert d["event_type"] == "info"
        assert d["line_number"] == 42
        assert d["correlation_id"] == "corr-1"


# ---------------------------------------------------------------------------
# Evidence dataclass
# ---------------------------------------------------------------------------


class TestEvidence:
    """Tests for Evidence dataclass."""

    def test_instantiate_with_defaults(self) -> None:
        ev = Evidence(description="found log entry", source="log", confidence=0.8)
        assert ev.data == {}

    def test_confidence_bounds(self) -> None:
        for val in (0.0, 0.5, 1.0):
            ev = Evidence(description="d", source="s", confidence=val)
            assert ev.confidence == val

    def test_to_dict(self) -> None:
        ev = Evidence(
            description="desc",
            source="git",
            confidence=0.9,
            data={"file": "a.py"},
        )
        d = ev.to_dict()
        assert d == {
            "description": "desc",
            "source": "git",
            "confidence": 0.9,
            "data": {"file": "a.py"},
        }


# ---------------------------------------------------------------------------
# ScoredHypothesis dataclass
# ---------------------------------------------------------------------------


class TestScoredHypothesis:
    """Tests for ScoredHypothesis dataclass."""

    def test_instantiate_with_defaults(self) -> None:
        hyp = ScoredHypothesis(
            description="maybe import error",
            category=ErrorCategory.CODE_ERROR,
            prior_probability=0.3,
        )
        assert hyp.evidence_for == []
        assert hyp.evidence_against == []
        assert hyp.posterior_probability == 0.5
        assert hyp.test_command == ""
        assert hyp.test_result is None
        assert hyp.suggested_fix == ""

    def test_empty_evidence_lists(self) -> None:
        hyp = ScoredHypothesis(
            description="h",
            category=ErrorCategory.UNKNOWN,
            prior_probability=0.1,
            evidence_for=[],
            evidence_against=[],
        )
        d = hyp.to_dict()
        assert d["evidence_for"] == []
        assert d["evidence_against"] == []

    def test_to_dict_with_evidence(self) -> None:
        ev = Evidence(description="log line", source="log", confidence=0.7)
        hyp = ScoredHypothesis(
            description="worker crash",
            category=ErrorCategory.WORKER_FAILURE,
            prior_probability=0.5,
            evidence_for=[ev],
            suggested_fix="restart worker",
        )
        d = hyp.to_dict()
        assert d["category"] == "worker_failure"
        assert len(d["evidence_for"]) == 1
        assert d["suggested_fix"] == "restart worker"


# ---------------------------------------------------------------------------
# DiagnosticContext dataclass
# ---------------------------------------------------------------------------


class TestDiagnosticContext:
    """Tests for DiagnosticContext dataclass."""

    def test_default_values(self) -> None:
        ctx = DiagnosticContext()
        assert ctx.feature == ""
        assert ctx.worker_id is None
        assert ctx.error_text == ""
        assert ctx.stack_trace == ""
        assert ctx.deep is False
        assert ctx.auto_fix is False
        assert ctx.interactive is False
        assert ctx.verbose is False

    def test_to_dict(self) -> None:
        ctx = DiagnosticContext(
            feature="auth",
            worker_id=3,
            error_text="err",
            deep=True,
        )
        d = ctx.to_dict()
        assert d["feature"] == "auth"
        assert d["worker_id"] == 3
        assert d["deep"] is True
        assert d["auto_fix"] is False
