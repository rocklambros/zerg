"""Semgrep adapter for static performance and security analysis."""

from __future__ import annotations

import json
import logging
import subprocess

from zerg.performance.adapters.base import BaseToolAdapter
from zerg.performance.types import DetectedStack, PerformanceFinding, Severity

logger = logging.getLogger(__name__)

# Semgrep registry configs per language
STACK_CONFIGS: dict[str, list[str]] = {
    "python": ["p/python", "p/python-best-practices"],
    "javascript": ["p/javascript", "p/nodejs"],
    "typescript": ["p/typescript"],
    "go": ["p/golang"],
    "rust": ["p/rust"],
    "java": ["p/java"],
    "ruby": ["p/ruby"],
}

INFRA_CONFIGS: dict[str, list[str]] = {
    "docker": ["p/dockerfile"],
}

ALWAYS_CONFIGS: list[str] = []  # Can add p/performance if available

# Map semgrep severity strings to our Severity enum
_SEVERITY_MAP: dict[str, Severity] = {
    "ERROR": Severity.HIGH,
    "WARNING": Severity.MEDIUM,
    "INFO": Severity.LOW,
}

# Best-effort mapping of check_id patterns to factor IDs and metadata.
# Each entry: (check_id_substring, factor_id, factor_name, category)
_CHECK_ID_FACTOR_MAP: list[tuple[str, int, str, str]] = [
    # Database
    ("n-plus-one", 46, "N+1 query detection", "Database"),
    ("n+1", 46, "N+1 query detection", "Database"),
    ("nplusone", 46, "N+1 query detection", "Database"),
    ("sql-injection", 127, "SQL injection vectors", "Security Patterns"),
    ("sqli", 127, "SQL injection vectors", "Security Patterns"),
    ("prepared-statement", 49, "Prepared statement usage", "Database"),
    ("parameterized", 49, "Prepared statement usage", "Database"),
    ("connection-pool", 48, "Connection pool sizing", "Database"),
    ("select-without-limit", 50, "Result set pagination", "Database"),
    ("orm", 51, "ORM query inspection", "Database"),
    ("eager-load", 52, "Eager loading patterns", "Database"),
    ("select_related", 52, "Eager loading patterns", "Database"),
    ("prefetch_related", 52, "Eager loading patterns", "Database"),
    # Concurrency
    ("blocking-io", 22, "Blocking vs async I/O", "Disk I/O"),
    ("blocking-call", 62, "Blocking calls in async context", "Concurrency"),
    ("sync-in-async", 62, "Blocking calls in async context", "Concurrency"),
    ("sequential-await", 64, "Sequential awaits in loops", "Concurrency"),
    ("await-in-loop", 64, "Sequential awaits in loops", "Concurrency"),
    ("lock-granularity", 58, "Lock granularity", "Concurrency"),
    ("thread-pool", 61, "Thread pool sizing", "Concurrency"),
    ("async-overhead", 63, "Unnecessary async overhead", "Concurrency"),
    ("over-synchron", 65, "Over-synchronization", "Concurrency"),
    ("thread-per-request", 66, "Thread-per-request assumption", "Concurrency"),
    ("read-write-lock", 59, "Read-write lock usage", "Concurrency"),
    ("lock-free", 60, "Lock-free structure correctness", "Concurrency"),
    # Code-Level Patterns
    ("string-concat", 67, "String concatenation in loops", "Code-Level Patterns"),
    ("string-concat-query", 73, "String concatenation for queries", "Code-Level Patterns"),
    ("regex", 68, "Regex compilation placement", "Code-Level Patterns"),
    ("redos", 68, "Regex compilation placement", "Code-Level Patterns"),
    ("exception-control-flow", 69, "Exception for control flow", "Code-Level Patterns"),
    ("reflection", 70, "Reflection in hot paths", "Code-Level Patterns"),
    ("lazy-init", 71, "Lazy initialization overhead", "Code-Level Patterns"),
    ("collection-type", 72, "Collection type mismatch", "Code-Level Patterns"),
    ("list-membership", 72, "Collection type mismatch", "Code-Level Patterns"),
    # Network I/O
    ("async-io", 33, "Async I/O for high concurrency", "Network I/O"),
    ("request-batch", 34, "Request batching", "Network I/O"),
    ("serialization", 35, "Serialization format overhead", "Network I/O"),
    ("tcp-tuning", 36, "TCP tuning", "Network I/O"),
    ("nagle", 36, "TCP tuning", "Network I/O"),
    ("dns-cach", 39, "DNS resolution caching", "Network I/O"),
    ("chatty", 42, "Chatty interface detection", "Network I/O"),
    ("sync-external", 43, "Synchronous external calls", "Network I/O"),
    ("blocking-http", 43, "Synchronous external calls", "Network I/O"),
    ("retry", 44, "Retry logic", "Network I/O"),
    ("timeout", 45, "Timeout configuration", "Network I/O"),
    ("missing-timeout", 45, "Timeout configuration", "Network I/O"),
    # Memory
    ("unbounded", 21, "Unbounded collection growth", "Memory"),
    ("memory-alignment", 17, "Memory alignment", "Memory"),
    ("copy-elim", 18, "Copy elimination", "Memory"),
    ("zero-copy", 18, "Copy elimination", "Memory"),
    # Error Handling
    ("swallowed-exception", 89, "Swallowed exceptions", "Error Handling"),
    ("empty-catch", 89, "Swallowed exceptions", "Error Handling"),
    ("bare-except", 89, "Swallowed exceptions", "Error Handling"),
    ("exception-class", 88, "Exception class proliferation", "Error Handling"),
    ("sensitive-log", 90, "Sensitive data in logs", "Error Handling"),
    ("password-log", 90, "Sensitive data in logs", "Error Handling"),
    ("redundant-valid", 91, "Redundant validation", "Error Handling"),
    # Security Patterns
    ("command-injection", 128, "Command injection vectors", "Security Patterns"),
    ("path-traversal", 129, "Path traversal vectors", "Security Patterns"),
    ("ssrf", 130, "SSRF vectors", "Security Patterns"),
    ("deserializ", 131, "Deserialization of untrusted data", "Security Patterns"),
    ("hardcoded-secret", 132, "Hardcoded secrets", "Security Patterns"),
    ("hardcoded-password", 132, "Hardcoded secrets", "Security Patterns"),
    ("weak-crypto", 133, "Weak cryptography", "Security Patterns"),
    ("md5", 133, "Weak cryptography", "Security Patterns"),
    ("sha1", 133, "Weak cryptography", "Security Patterns"),
    ("insecure-random", 134, "Insufficient randomness", "Security Patterns"),
    ("input-validation", 135, "Missing input validation", "Security Patterns"),
    ("xss", 136, "Missing output encoding", "Security Patterns"),
    ("tls", 137, "Insecure TLS configuration", "Security Patterns"),
    ("auth-check", 138, "Missing authentication checks", "Security Patterns"),
    ("authorization", 139, "Missing authorization checks", "Security Patterns"),
    ("debug-endpoint", 140, "Exposed debug endpoints", "Security Patterns"),
    # Observability
    ("log-volume", 108, "Log volume in hot paths", "Observability"),
    ("high-cardinality", 109, "High-cardinality metrics", "Observability"),
    ("trace-context", 110, "Trace context propagation", "Observability"),
    ("audit-log", 112, "Audit log separation", "Observability"),
    # Caching
    ("cache-eviction", 53, "Eviction policy configuration", "Caching"),
    ("cache-stampede", 54, "Cache stampede prevention", "Caching"),
    ("cache-key", 57, "Cache key construction", "Caching"),
    ("repeated-pars", 56, "Repeated parsing elimination", "Caching"),
    # Abstraction and Structure
    ("over-abstract", 74, "Over-abstraction", "Abstraction and Structure"),
    ("dead-code", 86, "Dead code", "Code Volume"),
    ("boilerplate", 87, "Boilerplate explosion", "Code Volume"),
]

# Default factor for unmatched findings
_DEFAULT_FACTOR_ID = 0
_DEFAULT_FACTOR_NAME = "General finding"
_DEFAULT_CATEGORY = "General"


class SemgrepAdapter(BaseToolAdapter):
    """Adapter for semgrep static analysis tool."""

    name: str = "semgrep"
    tool_name: str = "semgrep"
    factors_covered: list[int] = [
        # Code-Level Patterns
        67,  # String concatenation in loops
        68,  # Regex compilation placement
        69,  # Exception for control flow
        70,  # Reflection in hot paths
        71,  # Lazy initialization overhead
        72,  # Collection type mismatch
        73,  # String concatenation for queries
        # Concurrency
        58,  # Lock granularity
        59,  # Read-write lock usage
        60,  # Lock-free structure correctness
        61,  # Thread pool sizing
        62,  # Blocking calls in async context
        63,  # Unnecessary async overhead
        64,  # Sequential awaits in loops
        65,  # Over-synchronization
        66,  # Thread-per-request assumption
        # Error Handling
        88,  # Exception class proliferation
        89,  # Swallowed exceptions
        90,  # Sensitive data in logs
        91,  # Redundant validation
        # Network I/O
        32,  # Connection pooling
        33,  # Async I/O for high concurrency
        34,  # Request batching
        35,  # Serialization format overhead
        36,  # TCP tuning
        39,  # DNS resolution caching
        42,  # Chatty interface detection
        43,  # Synchronous external calls
        44,  # Retry logic
        45,  # Timeout configuration
        # Database
        46,  # N+1 query detection
        48,  # Connection pool sizing
        49,  # Prepared statement usage
        50,  # Result set pagination
        51,  # ORM query inspection
        52,  # Eager loading patterns
        # Memory
        17,  # Memory alignment
        18,  # Copy elimination
        21,  # Unbounded collection growth
        # Disk I/O
        22,  # Blocking vs async I/O
        25,  # Write batching
        26,  # Memory-mapped files
        # Security Patterns
        127,  # SQL injection vectors
        128,  # Command injection vectors
        129,  # Path traversal vectors
        130,  # SSRF vectors
        131,  # Deserialization of untrusted data
        132,  # Hardcoded secrets
        133,  # Weak cryptography
        134,  # Insufficient randomness
        135,  # Missing input validation
        136,  # Missing output encoding
        137,  # Insecure TLS configuration
        138,  # Missing authentication checks
        139,  # Missing authorization checks
        140,  # Exposed debug endpoints
        # Observability
        108,  # Log volume in hot paths
        109,  # High-cardinality metrics
        110,  # Trace context propagation
        112,  # Audit log separation
        # Caching
        53,  # Eviction policy configuration
        54,  # Cache stampede prevention
        56,  # Repeated parsing elimination
        57,  # Cache key construction
        # CPU and Compute
        9,  # Compiler optimization flags
        12,  # NUMA awareness
        # Abstraction and Structure
        74,  # Over-abstraction
        75,  # Premature generalization
        76,  # Design pattern theater
        77,  # Wrapper explosion
        78,  # DTO mapping chains
        # Code Volume
        83,  # Excessive null handling
        85,  # Comment noise
        87,  # Boilerplate explosion
        # Dependencies
        81,  # Framework maximalism
        82,  # Reinventing standard library
        # Architecture
        113,  # Service call depth
        114,  # Serialization boundary overhead
        116,  # Configuration sprawl
        117,  # Inconsistent patterns across services
        # AI Code Detection
        124,  # Security pattern coverage
        125,  # Excessive mocking in tests
        126,  # Missing performance tests
    ]

    def run(
        self,
        files: list[str],
        project_path: str,
        stack: DetectedStack,
    ) -> list[PerformanceFinding]:
        """Execute semgrep and return performance findings."""
        configs = self._build_configs(stack)
        if not configs:
            logger.warning("No semgrep configs determined for stack: %s", stack.languages)
            return []

        cmd = ["semgrep", "--json", "--quiet"] + [f"--config={c}" for c in configs] + [project_path]

        try:
            result = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            return self._parse_output(result.stdout)
        except subprocess.TimeoutExpired:
            logger.error("Semgrep timed out after 300s on %s", project_path)
            return []
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Semgrep execution failed: %s", exc)
            return []

    def _build_configs(self, stack: DetectedStack) -> list[str]:
        """Build the list of semgrep config strings from the detected stack."""
        configs: list[str] = list(ALWAYS_CONFIGS)
        for lang in stack.languages:
            lang_lower = lang.lower()
            if lang_lower in STACK_CONFIGS:
                configs.extend(STACK_CONFIGS[lang_lower])
        if stack.has_docker:
            configs.extend(INFRA_CONFIGS.get("docker", []))
        return configs

    def _parse_output(self, stdout: str) -> list[PerformanceFinding]:
        """Parse semgrep JSON output into PerformanceFinding instances."""
        if not stdout.strip():
            return []

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            logger.error("Failed to parse semgrep JSON output")
            return []

        results = data.get("results", [])
        findings: list[PerformanceFinding] = []

        for item in results:
            check_id = item.get("check_id", "")
            file_path = item.get("path", "")
            line = item.get("start", {}).get("line", 0)
            extra = item.get("extra", {})
            message = extra.get("message", "")
            raw_severity = extra.get("severity", "INFO").upper()

            severity = _SEVERITY_MAP.get(raw_severity, Severity.LOW)
            factor_id, factor_name, category = self._map_check_to_factor(check_id)

            findings.append(
                PerformanceFinding(
                    factor_id=factor_id,
                    factor_name=factor_name,
                    category=category,
                    severity=severity,
                    message=message,
                    file=file_path,
                    line=line,
                    tool=self.name,
                    rule_id=check_id,
                ),
            )

        return findings

    @staticmethod
    def _map_check_to_factor(check_id: str) -> tuple[int, str, str]:
        """Map a semgrep check_id to a factor ID, name, and category.

        Uses best-effort substring matching against known patterns.
        Returns defaults if no match is found.
        """
        check_lower = check_id.lower()
        for pattern, factor_id, factor_name, category in _CHECK_ID_FACTOR_MAP:
            if pattern in check_lower:
                return factor_id, factor_name, category
        return _DEFAULT_FACTOR_ID, _DEFAULT_FACTOR_NAME, _DEFAULT_CATEGORY
