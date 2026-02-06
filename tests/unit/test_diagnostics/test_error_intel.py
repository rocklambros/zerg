"""Tests for zerg.diagnostics.error_intel module."""

from __future__ import annotations

import pytest

from zerg.diagnostics.error_intel import (
    ErrorChainAnalyzer,
    ErrorFingerprinter,
    ErrorIntelEngine,
    LanguageDetector,
    MultiLangErrorParser,
)
from zerg.diagnostics.types import (
    ErrorCategory,
    ErrorFingerprint,
    ErrorSeverity,
    Evidence,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def detector() -> LanguageDetector:
    return LanguageDetector()


@pytest.fixture
def parser() -> MultiLangErrorParser:
    return MultiLangErrorParser()


@pytest.fixture
def chain_analyzer() -> ErrorChainAnalyzer:
    return ErrorChainAnalyzer()


@pytest.fixture
def fingerprinter() -> ErrorFingerprinter:
    return ErrorFingerprinter()


@pytest.fixture
def engine() -> ErrorIntelEngine:
    return ErrorIntelEngine()


# ---------------------------------------------------------------------------
# TestLanguageDetector
# ---------------------------------------------------------------------------


class TestLanguageDetector:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ('File "test.py", line 42', "python"),
            ("Traceback (most recent call last)", "python"),
            ("at Object.<anonymous> (test.js:10:5)", "javascript"),
            ("goroutine 1 [running]:\nmain.go:42", "go"),
            ("error[E0308]: mismatched types\n --> src/main.rs:5:5", "rust"),
            ("at com.example.Main.run(Main.java:15)", "java"),
            ("main.cpp:42:5: error: expected ;", "cpp"),
        ],
    )
    def test_detect_language(self, detector: LanguageDetector, text: str, expected: str) -> None:
        assert detector.detect(text) == expected

    def test_detect_unknown(self, detector: LanguageDetector) -> None:
        assert detector.detect("random text with no error pattern") == "unknown"


# ---------------------------------------------------------------------------
# TestMultiLangErrorParser
# ---------------------------------------------------------------------------


class TestMultiLangErrorParser:
    def test_parse_python_value_error(self, parser: MultiLangErrorParser) -> None:
        fp = parser.parse('ValueError: invalid literal\n  File "test.py", line 42')
        assert fp.error_type == "ValueError"
        assert fp.file == "test.py"
        assert fp.line == 42
        assert fp.language == "python"

    def test_parse_empty_string(self, parser: MultiLangErrorParser) -> None:
        fp = parser.parse("")
        assert fp.language == "unknown"
        assert fp.error_type == "unknown"
        assert fp.file == ""


# ---------------------------------------------------------------------------
# TestErrorChainAnalyzer
# ---------------------------------------------------------------------------


class TestErrorChainAnalyzer:
    def test_python_chained_exception(self, chain_analyzer: ErrorChainAnalyzer) -> None:
        text = (
            'ValueError: bad value\n  File "a.py", line 1\n'
            "The above exception was the direct cause of the following exception:\n"
            'RuntimeError: wrapper\n  File "b.py", line 5'
        )
        fps = chain_analyzer.analyze_chain(text)
        assert len(fps) >= 2
        assert len(fps[0].chain) == 1

    def test_single_error_no_chain(self, chain_analyzer: ErrorChainAnalyzer) -> None:
        text = 'ValueError: oops\n  File "x.py", line 1'
        fps = chain_analyzer.analyze_chain(text)
        assert len(fps) == 1


# ---------------------------------------------------------------------------
# TestErrorFingerprinter
# ---------------------------------------------------------------------------


class TestErrorFingerprinter:
    def test_same_error_same_hash(self, fingerprinter: ErrorFingerprinter) -> None:
        fp1 = ErrorFingerprint(
            hash="",
            language="python",
            error_type="ValueError",
            message_template="bad value",
            file="test.py",
            line=10,
        )
        fp2 = ErrorFingerprint(
            hash="",
            language="python",
            error_type="ValueError",
            message_template="bad value",
            file="test.py",
            line=10,
        )
        assert fingerprinter.fingerprint(fp1) == fingerprinter.fingerprint(fp2)

    def test_different_error_different_hash(self, fingerprinter: ErrorFingerprinter) -> None:
        fp1 = ErrorFingerprint(
            hash="",
            language="python",
            error_type="ValueError",
            message_template="bad value",
            file="test.py",
        )
        fp2 = ErrorFingerprint(
            hash="",
            language="python",
            error_type="TypeError",
            message_template="wrong type",
            file="test.py",
        )
        assert fingerprinter.fingerprint(fp1) != fingerprinter.fingerprint(fp2)


# ---------------------------------------------------------------------------
# TestErrorIntelEngine
# ---------------------------------------------------------------------------


class TestErrorIntelEngine:
    def test_analyze_full_flow(self, engine: ErrorIntelEngine) -> None:
        fp = engine.analyze('ValueError: bad\n  File "test.py", line 1')
        assert fp.hash
        assert fp.error_type == "ValueError"
        assert fp.language == "python"
        assert fp.file == "test.py"

    @pytest.mark.parametrize(
        "error_type,message,expected_cat,expected_sev",
        [
            ("ValueError", "bad", ErrorCategory.CODE_ERROR, ErrorSeverity.ERROR),
            ("MemoryError", "", ErrorCategory.INFRASTRUCTURE, ErrorSeverity.CRITICAL),
            ("ImportError", "No module named foo", ErrorCategory.DEPENDENCY, None),
        ],
    )
    def test_classify(self, engine: ErrorIntelEngine, error_type, message, expected_cat, expected_sev) -> None:
        fp = ErrorFingerprint(hash="abc", language="python", error_type=error_type, message_template=message, file="")
        category, severity = engine.classify(fp)
        assert category == expected_cat
        if expected_sev is not None:
            assert severity == expected_sev

    def test_get_evidence(self, engine: ErrorIntelEngine) -> None:
        fp = ErrorFingerprint(
            hash="abc",
            language="python",
            error_type="ValueError",
            message_template="bad value",
            file="test.py",
            line=10,
            function="do_thing",
        )
        evidence = engine.get_evidence(fp)
        assert isinstance(evidence, list)
        assert len(evidence) >= 3
        assert all(isinstance(e, Evidence) for e in evidence)

    def test_deduplicate(self, engine: ErrorIntelEngine) -> None:
        fp1 = ErrorFingerprint(
            hash="aaa", language="python", error_type="ValueError", message_template="x", file="f.py"
        )
        fp2 = ErrorFingerprint(
            hash="aaa", language="python", error_type="ValueError", message_template="x", file="f.py"
        )
        fp3 = ErrorFingerprint(hash="bbb", language="python", error_type="TypeError", message_template="y", file="g.py")
        result = engine.deduplicate([fp1, fp2, fp3])
        assert len(result) == 2
