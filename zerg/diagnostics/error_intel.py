"""Multi-language error intelligence engine for parsing, classifying, and deduplicating errors."""

from __future__ import annotations

import hashlib
import re

from zerg.diagnostics.types import (
    ErrorCategory,
    ErrorFingerprint,
    ErrorSeverity,
    Evidence,
)
from zerg.logging import get_logger

__all__ = [
    "ErrorChainAnalyzer",
    "ErrorFingerprinter",
    "ErrorIntelEngine",
    "LanguageDetector",
    "MultiLangErrorParser",
]

logger = get_logger("error_intel")


class LanguageDetector:
    """Detect the programming language from error text."""

    # Pattern pairs: (compiled regex, language name)
    _PATTERNS: list[tuple[re.Pattern[str], str]] = [
        # Python: File "...", line N  OR  Traceback (most recent call last)
        (re.compile(r'File ".*", line \d+|Traceback \(most recent call last\)'), "python"),
        # Rust: error[ENNN]  OR  --> file:line:col
        (re.compile(r"error\[E\d{4}\]|-->\s*\S+:\d+:\d+"), "rust"),
        # Go: goroutine  OR  .go:line
        (re.compile(r"goroutine \d+|\.go:\d+"), "go"),
        # Java: at package.Class(File.java:N)  OR  Exception in thread
        (re.compile(r"at \S+\.\S+\(\S+\.java:\d+\)|Exception in thread"), "java"),
        # C++: file:line:col: error:
        (re.compile(r"\S+:\d+:\d+: error:"), "cpp"),
        # JS/TS: at ... (file:N:N)  OR  TypeError:
        (re.compile(r"at .+\(\S+:\d+:\d+\)|TypeError:|ReferenceError:|SyntaxError:"), "javascript"),
    ]

    def detect(self, error_text: str) -> str:
        """Detect language from error text.

        Args:
            error_text: Raw error output.

        Returns:
            Language identifier string.
        """
        for pattern, language in self._PATTERNS:
            if pattern.search(error_text):
                return language
        return "unknown"


class MultiLangErrorParser:
    """Parse error text into structured ErrorFingerprint across multiple languages."""

    # --- Python patterns ---
    _PY_FILE_LINE = re.compile(r'File "([^"]+)", line (\d+)(?:, in (\w+))?')
    _PY_ERROR = re.compile(r"(\w+(?:Error|Exception|Warning)):\s*(.+)")

    # --- JavaScript / TypeScript patterns ---
    _JS_AT = re.compile(r"at\s+(\S+)\s+\(([^:]+):(\d+):(\d+)\)")
    _JS_AT_SIMPLE = re.compile(r"at\s+([^(]+):(\d+):(\d+)")
    _JS_ERROR = re.compile(r"(TypeError|ReferenceError|SyntaxError|RangeError|Error):\s*(.+)")

    # --- Go patterns ---
    _GO_FILE_LINE = re.compile(r"(\S+\.go):(\d+)")
    _GO_PANIC = re.compile(r"panic:\s*(.+)")
    _GO_GOROUTINE = re.compile(r"goroutine \d+")

    # --- Rust patterns ---
    _RUST_ERROR = re.compile(r"error\[(E\d{4})\]:\s*(.+)")
    _RUST_LOCATION = re.compile(r"-->\s*(\S+):(\d+):(\d+)")

    # --- Java patterns ---
    _JAVA_AT = re.compile(r"at\s+([\w$.]+)\.([\w$]+)\((\w+\.java):(\d+)\)")
    _JAVA_EXCEPTION = re.compile(r"([\w$.]+(?:Exception|Error))(?::\s*(.+))?")

    # --- C++ patterns ---
    _CPP_ERROR = re.compile(r"(\S+):(\d+):(\d+): error:\s*(.+)")

    def parse(self, error_text: str) -> ErrorFingerprint:
        """Parse error text into an ErrorFingerprint.

        Delegates to language-specific parsers based on detected language.

        Args:
            error_text: Raw error output.

        Returns:
            Populated ErrorFingerprint.
        """
        detector = LanguageDetector()
        lang = detector.detect(error_text)

        from collections.abc import Callable

        dispatch: dict[str, Callable[[str], ErrorFingerprint]] = {
            "python": self._parse_python,
            "javascript": self._parse_javascript,
            "typescript": self._parse_javascript,
            "go": self._parse_go,
            "rust": self._parse_rust,
            "java": self._parse_java,
            "cpp": self._parse_cpp,
        }

        parser_fn = dispatch.get(lang, self._parse_unknown)
        fp = parser_fn(error_text)
        fp.language = lang
        return fp

    def _parse_python(self, text: str) -> ErrorFingerprint:
        fp = ErrorFingerprint(
            hash="",
            language="python",
            error_type="",
            message_template="",
            file="",
        )

        # Extract file/line/function
        matches = self._PY_FILE_LINE.findall(text)
        if matches:
            # Use the last match (closest to error)
            file_path, line_str, func = matches[-1]
            fp.file = file_path
            fp.line = int(line_str)
            fp.function = func
            # Derive module from file path
            fp.module = file_path.replace("/", ".").removesuffix(".py")

        # Extract error type and message
        err_match = self._PY_ERROR.search(text)
        if err_match:
            fp.error_type = err_match.group(1)
            fp.message_template = err_match.group(2).strip()

        return fp

    def _parse_javascript(self, text: str) -> ErrorFingerprint:
        fp = ErrorFingerprint(
            hash="",
            language="javascript",
            error_type="",
            message_template="",
            file="",
        )

        # Extract error type
        err_match = self._JS_ERROR.search(text)
        if err_match:
            fp.error_type = err_match.group(1)
            fp.message_template = err_match.group(2).strip()

        # Extract location from at Function (file:line:col)
        at_match = self._JS_AT.search(text)
        if at_match:
            fp.function = at_match.group(1)
            fp.file = at_match.group(2)
            fp.line = int(at_match.group(3))
            fp.column = int(at_match.group(4))
        else:
            at_simple = self._JS_AT_SIMPLE.search(text)
            if at_simple:
                fp.file = at_simple.group(1).strip()
                fp.line = int(at_simple.group(2))
                fp.column = int(at_simple.group(3))

        return fp

    def _parse_go(self, text: str) -> ErrorFingerprint:
        fp = ErrorFingerprint(hash="", language="go", error_type="", message_template="", file="")

        # Panic message
        panic_match = self._GO_PANIC.search(text)
        if panic_match:
            fp.error_type = "panic"
            fp.message_template = panic_match.group(1).strip()

        # File location
        file_match = self._GO_FILE_LINE.search(text)
        if file_match:
            fp.file = file_match.group(1)
            fp.line = int(file_match.group(2))

        # If no panic, check for generic error pattern
        if not fp.error_type:
            fp.error_type = "runtime_error"
            # Try to get first non-empty line as message
            for line in text.strip().split("\n"):
                stripped = line.strip()
                if stripped and not self._GO_GOROUTINE.match(stripped):
                    fp.message_template = stripped
                    break

        return fp

    def _parse_rust(self, text: str) -> ErrorFingerprint:
        fp = ErrorFingerprint(hash="", language="rust", error_type="", message_template="", file="")

        # error[ENNN]: message
        err_match = self._RUST_ERROR.search(text)
        if err_match:
            fp.error_type = err_match.group(1)
            fp.message_template = err_match.group(2).strip()

        # --> file:line:col
        loc_match = self._RUST_LOCATION.search(text)
        if loc_match:
            fp.file = loc_match.group(1)
            fp.line = int(loc_match.group(2))
            fp.column = int(loc_match.group(3))

        return fp

    def _parse_java(self, text: str) -> ErrorFingerprint:
        fp = ErrorFingerprint(hash="", language="java", error_type="", message_template="", file="")

        # Exception name and message
        exc_match = self._JAVA_EXCEPTION.search(text)
        if exc_match:
            fp.error_type = exc_match.group(1)
            fp.message_template = (exc_match.group(2) or "").strip()

        # at package.Class.method(File.java:line)
        at_match = self._JAVA_AT.search(text)
        if at_match:
            fp.module = at_match.group(1)
            fp.function = at_match.group(2)
            fp.file = at_match.group(3)
            fp.line = int(at_match.group(4))

        return fp

    def _parse_cpp(self, text: str) -> ErrorFingerprint:
        fp = ErrorFingerprint(hash="", language="cpp", error_type="", message_template="", file="")

        # file:line:col: error: message
        err_match = self._CPP_ERROR.search(text)
        if err_match:
            fp.file = err_match.group(1)
            fp.line = int(err_match.group(2))
            fp.column = int(err_match.group(3))
            fp.error_type = "compile_error"
            fp.message_template = err_match.group(4).strip()

        return fp

    def _parse_unknown(self, text: str) -> ErrorFingerprint:
        fp = ErrorFingerprint(
            hash="",
            language="unknown",
            error_type="unknown",
            message_template="",
            file="",
        )
        # Use first non-empty line as message
        for line in text.strip().split("\n"):
            stripped = line.strip()
            if stripped:
                fp.message_template = stripped
                break
        return fp


class ErrorChainAnalyzer:
    """Analyze chained exceptions (e.g. Python cause chains, Java Caused by)."""

    _CHAIN_MARKERS = [
        # Python 3 exception chaining
        "The above exception was the direct cause of the following exception:",
        "During handling of the above exception, another exception occurred:",
        # Java / JVM
        "Caused by:",
        # Go convention
        "caused by:",
    ]

    def analyze_chain(self, error_text: str) -> list[ErrorFingerprint]:
        """Split chained errors and parse each independently.

        Args:
            error_text: Full error output possibly containing chained exceptions.

        Returns:
            List of ErrorFingerprints linked via their chain field.
        """
        sections = self._split_chain(error_text)
        parser = MultiLangErrorParser()
        fingerprints = [parser.parse(section) for section in sections]

        # Link chain: each fingerprint's chain field contains subsequent items
        for i in range(len(fingerprints) - 1):
            fingerprints[i].chain = [fingerprints[i + 1]]

        return fingerprints

    def _split_chain(self, text: str) -> list[str]:
        """Split error text on chain markers."""
        # Build a combined pattern from all markers
        escaped = [re.escape(m) for m in self._CHAIN_MARKERS]
        pattern = "|".join(escaped)
        sections = re.split(pattern, text)
        # Filter empty sections
        return [s.strip() for s in sections if s.strip()]


class ErrorFingerprinter:
    """Create stable hashes for error deduplication."""

    def fingerprint(self, error: ErrorFingerprint) -> str:
        """Create a stable hash from error_type + message_template + file.

        Line numbers are intentionally excluded so the same logical error
        appearing at different lines deduplicates correctly.

        Args:
            error: ErrorFingerprint to hash.

        Returns:
            First 16 hex characters of SHA-256 hash.
        """
        key = f"{error.error_type}:{error.message_template}:{error.file}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]


class ErrorIntelEngine:
    """Facade combining detection, parsing, fingerprinting, classification, and evidence."""

    def __init__(self) -> None:
        self._detector = LanguageDetector()
        self._parser = MultiLangErrorParser()
        self._chain_analyzer = ErrorChainAnalyzer()
        self._fingerprinter = ErrorFingerprinter()

    def analyze(self, error_text: str, stack_trace: str = "") -> ErrorFingerprint:
        """Full analysis pipeline: detect, parse, fingerprint.

        Args:
            error_text: Error message.
            stack_trace: Optional stack trace (merged with error_text).

        Returns:
            Fully populated ErrorFingerprint with hash set.
        """
        combined = f"{error_text}\n{stack_trace}".strip()
        fp = self._parser.parse(combined)
        fp.hash = self._fingerprinter.fingerprint(fp)
        return fp

    # --- Category mapping ---
    _CATEGORY_MAP: dict[str, ErrorCategory] = {
        "ImportError": ErrorCategory.DEPENDENCY,
        "ModuleNotFoundError": ErrorCategory.DEPENDENCY,
        "TypeError": ErrorCategory.CODE_ERROR,
        "ValueError": ErrorCategory.CODE_ERROR,
        "AttributeError": ErrorCategory.CODE_ERROR,
        "KeyError": ErrorCategory.CODE_ERROR,
        "IndexError": ErrorCategory.CODE_ERROR,
        "NameError": ErrorCategory.CODE_ERROR,
        "SyntaxError": ErrorCategory.CODE_ERROR,
        "RuntimeError": ErrorCategory.CODE_ERROR,
        "AssertionError": ErrorCategory.CODE_ERROR,
        "FileNotFoundError": ErrorCategory.ENVIRONMENT,
        "PermissionError": ErrorCategory.ENVIRONMENT,
        "OSError": ErrorCategory.ENVIRONMENT,
        "IOError": ErrorCategory.ENVIRONMENT,
        "ConnectionError": ErrorCategory.INFRASTRUCTURE,
        "TimeoutError": ErrorCategory.INFRASTRUCTURE,
        "MemoryError": ErrorCategory.INFRASTRUCTURE,
        "RecursionError": ErrorCategory.CODE_ERROR,
        "compile_error": ErrorCategory.CODE_ERROR,
        "panic": ErrorCategory.CODE_ERROR,
        "runtime_error": ErrorCategory.CODE_ERROR,
        "ReferenceError": ErrorCategory.CODE_ERROR,
        "RangeError": ErrorCategory.CODE_ERROR,
    }

    # --- Severity mapping ---
    _SEVERITY_MAP: dict[str, ErrorSeverity] = {
        "MemoryError": ErrorSeverity.CRITICAL,
        "RecursionError": ErrorSeverity.CRITICAL,
        "SystemExit": ErrorSeverity.CRITICAL,
        "KeyboardInterrupt": ErrorSeverity.CRITICAL,
        "panic": ErrorSeverity.CRITICAL,
    }

    def classify(self, fingerprint: ErrorFingerprint) -> tuple[ErrorCategory, ErrorSeverity]:
        """Map an error fingerprint to a category and severity.

        Args:
            fingerprint: ErrorFingerprint to classify.

        Returns:
            Tuple of (ErrorCategory, ErrorSeverity).
        """
        category = self._CATEGORY_MAP.get(fingerprint.error_type, ErrorCategory.UNKNOWN)
        severity = self._SEVERITY_MAP.get(fingerprint.error_type, ErrorSeverity.ERROR)
        return category, severity

    def get_evidence(self, fingerprint: ErrorFingerprint) -> list[Evidence]:
        """Create Evidence objects from fingerprint data.

        Args:
            fingerprint: ErrorFingerprint to extract evidence from.

        Returns:
            List of Evidence objects.
        """
        evidence: list[Evidence] = []

        if fingerprint.file:
            loc = f"{fingerprint.file}:{fingerprint.line}" if fingerprint.line else fingerprint.file
            evidence.append(
                Evidence(
                    description=f"Error at {loc}",
                    source="code",
                    confidence=0.9,
                    data={"file": fingerprint.file, "line": fingerprint.line},
                )
            )

        if fingerprint.error_type:
            evidence.append(
                Evidence(
                    description=f"Error type: {fingerprint.error_type}",
                    source="code",
                    confidence=0.95,
                    data={"error_type": fingerprint.error_type},
                )
            )

        if fingerprint.message_template:
            evidence.append(
                Evidence(
                    description=f"Message: {fingerprint.message_template}",
                    source="code",
                    confidence=0.8,
                    data={"message": fingerprint.message_template},
                )
            )

        if fingerprint.function:
            evidence.append(
                Evidence(
                    description=f"In function: {fingerprint.function}",
                    source="code",
                    confidence=0.85,
                    data={"function": fingerprint.function},
                )
            )

        return evidence

    def deduplicate(self, fingerprints: list[ErrorFingerprint]) -> list[ErrorFingerprint]:
        """Remove duplicate errors based on hash.

        Args:
            fingerprints: List of ErrorFingerprints (must have hash set).

        Returns:
            Deduplicated list preserving first occurrence order.
        """
        seen: set[str] = set()
        unique: list[ErrorFingerprint] = []
        for fp in fingerprints:
            if fp.hash not in seen:
                seen.add(fp.hash)
                unique.append(fp)
        return unique
