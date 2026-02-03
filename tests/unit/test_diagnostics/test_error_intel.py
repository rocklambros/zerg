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


# Common error strings
@pytest.fixture
def python_value_error() -> str:
    return 'ValueError: invalid literal\n  File "test.py", line 42'


@pytest.fixture
def js_type_error() -> str:
    return "TypeError: undefined is not a function\n    at doStuff (app.js:10:3)"


@pytest.fixture
def go_panic() -> str:
    return "goroutine 1 [running]:\nmain.main()\n\tmain.go:15 +0x40"


@pytest.fixture
def rust_error() -> str:
    return "error[E0308]: mismatched types\n --> src/main.rs:5:20"


@pytest.fixture
def java_exception() -> str:
    return "java.lang.NullPointerException\n\tat com.example.App.main(App.java:10)"


# ---------------------------------------------------------------------------
# TestLanguageDetector
# ---------------------------------------------------------------------------


class TestLanguageDetector:
    def test_detect_python(self, detector: LanguageDetector) -> None:
        assert detector.detect('File "test.py", line 42') == "python"

    def test_detect_python_traceback(self, detector: LanguageDetector) -> None:
        assert detector.detect("Traceback (most recent call last)") == "python"

    def test_detect_javascript(self, detector: LanguageDetector) -> None:
        assert detector.detect("at Object.<anonymous> (test.js:10:5)") == "javascript"

    def test_detect_go(self, detector: LanguageDetector) -> None:
        assert detector.detect("goroutine 1 [running]:\nmain.go:42") == "go"

    def test_detect_rust(self, detector: LanguageDetector) -> None:
        text = "error[E0308]: mismatched types\n --> src/main.rs:5:5"
        assert detector.detect(text) == "rust"

    def test_detect_java(self, detector: LanguageDetector) -> None:
        assert detector.detect("at com.example.Main.run(Main.java:15)") == "java"

    def test_detect_cpp(self, detector: LanguageDetector) -> None:
        assert detector.detect("main.cpp:42:5: error: expected ;") == "cpp"

    def test_detect_unknown(self, detector: LanguageDetector) -> None:
        assert detector.detect("random text with no error pattern") == "unknown"


# ---------------------------------------------------------------------------
# TestMultiLangErrorParser
# ---------------------------------------------------------------------------


class TestMultiLangErrorParser:
    def test_parse_python_value_error(self, parser: MultiLangErrorParser, python_value_error: str) -> None:
        fp = parser.parse(python_value_error)
        assert fp.error_type == "ValueError"
        assert fp.file == "test.py"
        assert fp.line == 42
        assert fp.language == "python"

    def test_parse_javascript_type_error(self, parser: MultiLangErrorParser, js_type_error: str) -> None:
        fp = parser.parse(js_type_error)
        assert fp.error_type == "TypeError"
        assert fp.file == "app.js"
        assert fp.line == 10
        assert fp.column == 3
        assert fp.function == "doStuff"
        assert fp.language == "javascript"

    def test_parse_go_panic(self, parser: MultiLangErrorParser, go_panic: str) -> None:
        fp = parser.parse(go_panic)
        assert fp.language == "go"
        assert fp.file == "main.go"
        assert fp.line == 15

    def test_parse_rust_error(self, parser: MultiLangErrorParser, rust_error: str) -> None:
        fp = parser.parse(rust_error)
        assert fp.error_type == "E0308"
        assert fp.message_template == "mismatched types"
        assert fp.file == "src/main.rs"
        assert fp.line == 5
        assert fp.column == 20
        assert fp.language == "rust"

    def test_parse_java_exception(self, parser: MultiLangErrorParser, java_exception: str) -> None:
        fp = parser.parse(java_exception)
        assert fp.error_type == "java.lang.NullPointerException"
        assert fp.file == "App.java"
        assert fp.line == 10
        assert fp.function == "main"
        assert fp.module == "com.example.App"
        assert fp.language == "java"

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
        # First fingerprint should link to second via chain
        assert len(fps[0].chain) == 1

    def test_java_caused_by(self, chain_analyzer: ErrorChainAnalyzer) -> None:
        text = (
            "java.lang.RuntimeException: top\n"
            "\tat com.example.Top.run(Top.java:10)\n"
            "Caused by: java.io.IOException: disk full\n"
            "\tat com.example.IO.write(IO.java:20)"
        )
        fps = chain_analyzer.analyze_chain(text)
        assert len(fps) >= 2

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

    def test_different_line_same_hash(self, fingerprinter: ErrorFingerprinter) -> None:
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
            line=99,
        )
        # Line numbers are excluded from hash -> same hash
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

    def test_hash_length(self, fingerprinter: ErrorFingerprinter) -> None:
        fp = ErrorFingerprint(
            hash="",
            language="python",
            error_type="ValueError",
            message_template="x",
            file="f.py",
        )
        assert len(fingerprinter.fingerprint(fp)) == 16


# ---------------------------------------------------------------------------
# TestErrorIntelEngine
# ---------------------------------------------------------------------------


class TestErrorIntelEngine:
    def test_analyze_full_flow(self, engine: ErrorIntelEngine) -> None:
        fp = engine.analyze('ValueError: bad\n  File "test.py", line 1')
        assert fp.hash  # non-empty hash
        assert fp.error_type == "ValueError"
        assert fp.language == "python"
        assert fp.file == "test.py"

    def test_classify_value_error(self, engine: ErrorIntelEngine) -> None:
        fp = ErrorFingerprint(
            hash="abc",
            language="python",
            error_type="ValueError",
            message_template="bad",
            file="test.py",
        )
        category, severity = engine.classify(fp)
        assert category == ErrorCategory.CODE_ERROR
        assert severity == ErrorSeverity.ERROR

    def test_classify_memory_error(self, engine: ErrorIntelEngine) -> None:
        fp = ErrorFingerprint(
            hash="abc",
            language="python",
            error_type="MemoryError",
            message_template="",
            file="",
        )
        category, severity = engine.classify(fp)
        assert severity == ErrorSeverity.CRITICAL
        assert category == ErrorCategory.INFRASTRUCTURE

    def test_classify_import_error(self, engine: ErrorIntelEngine) -> None:
        fp = ErrorFingerprint(
            hash="abc",
            language="python",
            error_type="ImportError",
            message_template="No module named foo",
            file="",
        )
        category, severity = engine.classify(fp)
        assert category == ErrorCategory.DEPENDENCY

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
        assert len(evidence) >= 3  # file, error_type, message, function
        assert all(isinstance(e, Evidence) for e in evidence)
        descriptions = [e.description for e in evidence]
        assert any("test.py" in d for d in descriptions)
        assert any("ValueError" in d for d in descriptions)

    def test_deduplicate(self, engine: ErrorIntelEngine) -> None:
        fp1 = ErrorFingerprint(
            hash="aaa",
            language="python",
            error_type="ValueError",
            message_template="x",
            file="f.py",
        )
        fp2 = ErrorFingerprint(
            hash="aaa",
            language="python",
            error_type="ValueError",
            message_template="x",
            file="f.py",
        )
        fp3 = ErrorFingerprint(
            hash="bbb",
            language="python",
            error_type="TypeError",
            message_template="y",
            file="g.py",
        )
        result = engine.deduplicate([fp1, fp2, fp3])
        assert len(result) == 2
        assert result[0].hash == "aaa"
        assert result[1].hash == "bbb"
