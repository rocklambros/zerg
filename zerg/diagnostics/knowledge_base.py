"""Failure pattern knowledge base for hypothesis-driven debugging."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from zerg.logging import get_logger

logger = get_logger("diagnostics.knowledge_base")

__all__ = ["KnownPattern", "KNOWN_PATTERNS", "PatternMatcher"]


@dataclass
class KnownPattern:
    """A known failure pattern with prior probability and resolution guidance."""

    name: str
    category: str  # matches ErrorCategory enum values
    symptoms: list[str]  # regex patterns
    prior_probability: float  # 0.0 - 1.0
    common_causes: list[str]
    fix_templates: list[str]
    related_patterns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "category": self.category,
            "symptoms": self.symptoms,
            "prior_probability": self.prior_probability,
            "common_causes": self.common_causes,
            "fix_templates": self.fix_templates,
            "related_patterns": self.related_patterns,
        }


# ---------------------------------------------------------------------------
# Known patterns: Python errors
# ---------------------------------------------------------------------------

_PYTHON_PATTERNS: list[KnownPattern] = [
    KnownPattern(
        name="import_error",
        category="python",
        symptoms=[
            r"ImportError:\s+cannot import name",
            r"ImportError:\s+No module named",
            r"ImportError:\s+DLL load failed",
        ],
        prior_probability=0.15,
        common_causes=[
            "Package not installed in current environment",
            "Circular import between modules",
            "Incompatible package version installed",
        ],
        fix_templates=[
            "pip install {module}",
            "Check for circular imports between {file} and its dependencies",
        ],
        related_patterns=["module_not_found", "circular_import", "dependency_conflict"],
    ),
    KnownPattern(
        name="module_not_found",
        category="python",
        symptoms=[
            r"ModuleNotFoundError:\s+No module named",
            r"No module named\s+'\w+'",
            r"ModuleNotFoundError.*pip install",
        ],
        prior_probability=0.14,
        common_causes=[
            "Package not installed",
            "Virtual environment not activated",
            "Typo in module name",
        ],
        fix_templates=[
            "pip install {module}",
            "Activate the correct virtual environment: source .venv/bin/activate",
        ],
        related_patterns=["import_error", "dependency_conflict", "env_misconfiguration"],
    ),
    KnownPattern(
        name="type_error",
        category="python",
        symptoms=[
            r"TypeError:\s+.*takes \d+ positional argument",
            r"TypeError:\s+.*got an unexpected keyword argument",
            r"TypeError:\s+unsupported operand type",
            r"TypeError:\s+.*is not callable",
        ],
        prior_probability=0.12,
        common_causes=[
            "Wrong number of arguments passed to function",
            "Incompatible types in operation",
            "API changed between versions",
        ],
        fix_templates=[
            "Check function signature of {function} and adjust call site",
            "Verify type compatibility between operands",
        ],
        related_patterns=["attribute_error", "version_mismatch"],
    ),
    KnownPattern(
        name="value_error",
        category="python",
        symptoms=[
            r"ValueError:\s+invalid literal for int\(\)",
            r"ValueError:\s+.*not in list",
            r"ValueError:\s+too many values to unpack",
        ],
        prior_probability=0.10,
        common_causes=[
            "Invalid input data format",
            "Unexpected data shape or content",
            "Incorrect unpacking of return values",
        ],
        fix_templates=[
            "Validate input data before processing: assert isinstance({var}, expected_type)",
            "Add input sanitization for {field}",
        ],
        related_patterns=["type_error", "key_error"],
    ),
    KnownPattern(
        name="key_error",
        category="python",
        symptoms=[
            r"KeyError:\s+",
            r"KeyError:\s+'[\w\-\.]+'",
            r"KeyError.*dict",
        ],
        prior_probability=0.10,
        common_causes=[
            "Missing key in dictionary or config",
            "Misspelled dictionary key",
            "State file missing expected field",
        ],
        fix_templates=[
            "Use dict.get({key}, default) instead of dict[{key}]",
            "Verify {key} exists in the data source before access",
        ],
        related_patterns=["attribute_error", "state_corruption"],
    ),
    KnownPattern(
        name="attribute_error",
        category="python",
        symptoms=[
            r"AttributeError:\s+'NoneType' object has no attribute",
            r"AttributeError:\s+'[\w]+' object has no attribute '[\w]+'",
            r"AttributeError:\s+module '[\w.]+' has no attribute",
        ],
        prior_probability=0.10,
        common_causes=[
            "Variable is None when object expected",
            "Wrong object type due to failed initialization",
            "Module API changed between versions",
        ],
        fix_templates=[
            "Add None check before accessing .{attr}: if obj is not None",
            "Verify {module} version matches expected API",
        ],
        related_patterns=["type_error", "import_error"],
    ),
    KnownPattern(
        name="recursion_error",
        category="python",
        symptoms=[
            r"RecursionError:\s+maximum recursion depth exceeded",
            r"RecursionError",
            r"maximum recursion depth",
        ],
        prior_probability=0.03,
        common_causes=[
            "Infinite recursion due to missing base case",
            "Circular data structure serialization",
            "Circular import chain",
        ],
        fix_templates=[
            "Add or fix base case in recursive function {function}",
            "Use sys.setrecursionlimit() as temporary workaround",
            "Refactor to iterative approach",
        ],
        related_patterns=["circular_import"],
    ),
    KnownPattern(
        name="memory_error",
        category="python",
        symptoms=[
            r"MemoryError",
            r"MemoryError:\s+",
            r"Cannot allocate memory",
            r"std::bad_alloc",
        ],
        prior_probability=0.02,
        common_causes=[
            "Loading dataset too large for available RAM",
            "Unbounded list/dict growth in loop",
            "Memory leak from unclosed resources",
        ],
        fix_templates=[
            "Process data in chunks or use streaming",
            "Add memory limits and monitoring",
        ],
        related_patterns=["disk_space_low"],
    ),
    KnownPattern(
        name="file_not_found",
        category="python",
        symptoms=[
            r"FileNotFoundError:\s+\[Errno 2\]",
            r"No such file or directory",
            r"FileNotFoundError.*'[\w/\\.]+'",
        ],
        prior_probability=0.08,
        common_causes=[
            "File path is incorrect or relative to wrong directory",
            "File was deleted or moved",
            "Working directory differs from expected",
        ],
        fix_templates=[
            "Use pathlib.Path and verify existence: Path({path}).exists()",
            "Check working directory with os.getcwd()",
        ],
        related_patterns=["permission_error", "state_file_missing"],
    ),
    KnownPattern(
        name="permission_error",
        category="python",
        symptoms=[
            r"PermissionError:\s+\[Errno 13\]",
            r"Permission denied",
            r"PermissionError.*'[\w/\\.]+'",
        ],
        prior_probability=0.05,
        common_causes=[
            "File owned by different user or root",
            "Read-only filesystem or directory",
            "SELinux or AppArmor policy denial",
        ],
        fix_templates=[
            "Check file permissions: ls -la {path}",
            "Run with appropriate permissions or fix ownership",
        ],
        related_patterns=["file_not_found", "docker_failure"],
    ),
    KnownPattern(
        name="syntax_error",
        category="python",
        symptoms=[
            r"SyntaxError:\s+invalid syntax",
            r"SyntaxError:\s+unexpected EOF",
            r"SyntaxError:\s+EOL while scanning",
            r"IndentationError:",
        ],
        prior_probability=0.06,
        common_causes=[
            "Typo or missing punctuation in source code",
            "Python version incompatibility (e.g. walrus operator on 3.7)",
            "Corrupted file encoding",
        ],
        fix_templates=[
            "Check syntax at {file}:{line}",
            "Verify Python version compatibility",
        ],
        related_patterns=["encoding_error"],
    ),
    KnownPattern(
        name="assertion_error",
        category="python",
        symptoms=[
            r"AssertionError",
            r"AssertionError:\s+",
            r"assert\s+.*failed",
        ],
        prior_probability=0.05,
        common_causes=[
            "Test assertion failed due to unexpected value",
            "Precondition violation in production code",
            "Data invariant broken",
        ],
        fix_templates=[
            "Review assertion condition and expected vs actual values",
            "Add diagnostic logging before the assertion",
        ],
        related_patterns=["task_verification_failed", "value_error"],
    ),
    KnownPattern(
        name="os_error",
        category="python",
        symptoms=[
            r"OSError:\s+\[Errno",
            r"OSError:\s+",
            r"BlockingIOError",
        ],
        prior_probability=0.04,
        common_causes=[
            "System resource exhaustion (file descriptors, disk)",
            "Network interface unavailable",
            "Device or resource busy",
        ],
        fix_templates=[
            "Check system resources: ulimit -n, df -h",
            "Ensure resources are properly closed (use context managers)",
        ],
        related_patterns=["permission_error", "disk_space_low"],
    ),
    KnownPattern(
        name="connection_error",
        category="python",
        symptoms=[
            r"ConnectionError",
            r"ConnectionRefusedError:\s+\[Errno 111\]",
            r"ConnectionResetError",
            r"requests\.exceptions\.ConnectionError",
        ],
        prior_probability=0.06,
        common_causes=[
            "Target service is down or unreachable",
            "Firewall blocking the connection",
            "DNS resolution failure",
        ],
        fix_templates=[
            "Verify service is running: curl -v {url}",
            "Check network connectivity and DNS resolution",
        ],
        related_patterns=["timeout_error", "port_conflict"],
    ),
    KnownPattern(
        name="timeout_error",
        category="python",
        symptoms=[
            r"TimeoutError",
            r"socket\.timeout",
            r"requests\.exceptions\.Timeout",
            r"asyncio\.TimeoutError",
        ],
        prior_probability=0.06,
        common_causes=[
            "Service responding too slowly",
            "Network latency or packet loss",
            "Deadlock in target service",
        ],
        fix_templates=[
            "Increase timeout value for {operation}",
            "Add retry logic with exponential backoff",
        ],
        related_patterns=["connection_error", "task_timeout"],
    ),
]

# ---------------------------------------------------------------------------
# Known patterns: ZERG-specific
# ---------------------------------------------------------------------------

_ZERG_PATTERNS: list[KnownPattern] = [
    KnownPattern(
        name="worker_crash",
        category="zerg",
        symptoms=[
            r"worker.*crash",
            r"worker.*died unexpectedly",
            r"Process exited with code [^0]",
            r"SIGKILL|SIGSEGV|SIGABRT",
        ],
        prior_probability=0.08,
        common_causes=[
            "Out-of-memory kill by OS",
            "Unhandled exception in worker code",
            "Container resource limit exceeded",
        ],
        fix_templates=[
            "Check worker logs: cat .zerg/logs/worker-{id}.log",
            "Increase container memory limit in .zerg/config.yaml",
            "Run /zerg:retry to restart failed worker",
        ],
        related_patterns=["worker_timeout", "memory_error", "docker_failure"],
    ),
    KnownPattern(
        name="worker_timeout",
        category="zerg",
        symptoms=[
            r"worker.*timed?\s*out",
            r"Worker \d+ exceeded time limit",
            r"task_timeout_seconds exceeded",
        ],
        prior_probability=0.07,
        common_causes=[
            "Task too complex for allocated time",
            "Worker stuck on external dependency",
            "Deadlock in task execution",
        ],
        fix_templates=[
            "Increase timeout in .zerg/config.yaml: task_timeout_seconds",
            "Split task into smaller sub-tasks",
            "Check for blocking operations in task",
        ],
        related_patterns=["worker_crash", "task_timeout"],
    ),
    KnownPattern(
        name="state_corruption",
        category="zerg",
        symptoms=[
            r"JSONDecodeError",
            r"invalid.*state.*json",
            r"state.*corrupt",
            r"Expecting.*JSON",
        ],
        prior_probability=0.05,
        common_causes=[
            "Concurrent write to state file without locking",
            "Worker crashed mid-write",
            "Disk full during state save",
        ],
        fix_templates=[
            "Restore from backup: cp .zerg/state/state.json.bak .zerg/state/state.json",
            "Re-initialize state: /zerg:init --force",
        ],
        related_patterns=["state_file_missing", "disk_space_low"],
    ),
    KnownPattern(
        name="state_file_missing",
        category="zerg",
        symptoms=[
            r"state\.json.*not found",
            r"FileNotFoundError.*\.zerg/state",
            r"No state file found",
        ],
        prior_probability=0.04,
        common_causes=[
            "Project not initialized with /zerg:init",
            "State directory accidentally deleted",
            "Working directory is wrong",
        ],
        fix_templates=[
            "Initialize project: /zerg:init",
            "Verify working directory: pwd",
        ],
        related_patterns=["state_corruption", "file_not_found"],
    ),
    KnownPattern(
        name="task_timeout",
        category="zerg",
        symptoms=[
            r"task.*timed?\s*out",
            r"Task .* exceeded.*timeout",
            r"execution time limit reached",
        ],
        prior_probability=0.06,
        common_causes=[
            "Verification command hangs",
            "Infinite loop in generated code",
            "External dependency unreachable",
        ],
        fix_templates=[
            "Check task verification command in task-graph.json",
            "Add timeout to verification: timeout 60 {command}",
        ],
        related_patterns=["worker_timeout", "timeout_error"],
    ),
    KnownPattern(
        name="task_verification_failed",
        category="zerg",
        symptoms=[
            r"verification.*fail",
            r"Verification command returned non-zero",
            r"task.*verify.*error",
            r"quality gate.*fail",
        ],
        prior_probability=0.10,
        common_causes=[
            "Generated code has syntax or logic errors",
            "Missing dependencies for verification command",
            "Verification command is too strict or incorrect",
        ],
        fix_templates=[
            "Review verification command output in worker log",
            "Run verification manually: {verify_command}",
            "Update verification criteria in task-graph.json",
        ],
        related_patterns=["assertion_error", "syntax_error"],
    ),
    KnownPattern(
        name="merge_conflict",
        category="zerg",
        symptoms=[
            r"CONFLICT.*Merge conflict",
            r"merge.*conflict",
            r"Automatic merge failed",
            r"both modified:\s+",
        ],
        prior_probability=0.07,
        common_causes=[
            "Overlapping file ownership between tasks",
            "Manual edits on base branch during rush",
            "Incorrect file ownership in task-graph.json",
        ],
        fix_templates=[
            "Check file ownership in task-graph.json for overlaps",
            "Resolve conflicts manually: git mergetool",
            "Re-run /zerg:merge after fixing conflicts",
        ],
        related_patterns=["worktree_orphan"],
    ),
    KnownPattern(
        name="port_conflict",
        category="zerg",
        symptoms=[
            r"Address already in use",
            r"port.*already.*in use",
            r"EADDRINUSE",
            r"bind.*failed.*address",
        ],
        prior_probability=0.04,
        common_causes=[
            "Previous instance still running on same port",
            "Multiple workers trying to bind same port",
            "System service occupying required port",
        ],
        fix_templates=[
            "Kill process on port: lsof -ti:{port} | xargs kill",
            "Use a different port in configuration",
        ],
        related_patterns=["connection_error", "docker_failure"],
    ),
    KnownPattern(
        name="worktree_orphan",
        category="zerg",
        symptoms=[
            r"worktree.*orphan",
            r"fatal:.*is already checked out",
            r"worktree.*lock",
            r"\.zerg/worktrees.*not a git",
        ],
        prior_probability=0.04,
        common_causes=[
            "Previous rush left worktrees without cleanup",
            "Worker crashed before worktree removal",
            "Manual deletion of .zerg directory without git worktree prune",
        ],
        fix_templates=[
            "Prune stale worktrees: git worktree prune",
            "Remove manually: git worktree remove .zerg/worktrees/{name}",
        ],
        related_patterns=["merge_conflict", "state_corruption"],
    ),
    KnownPattern(
        name="disk_space_low",
        category="zerg",
        symptoms=[
            r"No space left on device",
            r"ENOSPC",
            r"disk.*full",
            r"OSError.*\[Errno 28\]",
        ],
        prior_probability=0.03,
        common_causes=[
            "Docker images consuming disk space",
            "Large log files from previous runs",
            "Many worktrees not cleaned up",
        ],
        fix_templates=[
            "Free disk space: docker system prune -af",
            "Clean old logs: rm -rf .zerg/logs/*.old",
            "Remove stale worktrees: git worktree prune && rm -rf .zerg/worktrees/*",
        ],
        related_patterns=["memory_error", "state_corruption", "docker_failure"],
    ),
    KnownPattern(
        name="docker_failure",
        category="zerg",
        symptoms=[
            r"docker.*not found",
            r"Cannot connect to the Docker daemon",
            r"docker.*permission denied",
            r"Error response from daemon",
        ],
        prior_probability=0.06,
        common_causes=[
            "Docker daemon not running",
            "User not in docker group",
            "Docker Desktop not started",
        ],
        fix_templates=[
            "Start Docker daemon: sudo systemctl start docker",
            "Add user to docker group: sudo usermod -aG docker $USER",
            "Check Docker status: docker info",
        ],
        related_patterns=["permission_error", "worker_crash"],
    ),
    KnownPattern(
        name="config_invalid",
        category="zerg",
        symptoms=[
            r"config.*invalid",
            r"yaml.*error",
            r"Invalid configuration",
            r"KeyError.*config",
        ],
        prior_probability=0.04,
        common_causes=[
            "YAML syntax error in .zerg/config.yaml",
            "Missing required configuration field",
            "Type mismatch in configuration value",
        ],
        fix_templates=[
            "Validate config: python -c \"import yaml; yaml.safe_load(open('.zerg/config.yaml'))\"",
            "Check config against schema in documentation",
        ],
        related_patterns=["state_corruption", "key_error"],
    ),
    KnownPattern(
        name="level_sync_failure",
        category="zerg",
        symptoms=[
            r"level.*sync.*fail",
            r"workers.*not.*complete.*level",
            r"dependency level.*blocked",
            r"Cannot proceed to level \d+",
        ],
        prior_probability=0.05,
        common_causes=[
            "One or more workers in previous level failed",
            "Task dependency cycle in task-graph.json",
            "State file not updated after level completion",
        ],
        fix_templates=[
            "Check failed tasks: /zerg:status",
            "Retry failed tasks: /zerg:retry --level {level}",
            "Verify task-graph.json has no cycles",
        ],
        related_patterns=["worker_crash", "task_verification_failed", "state_corruption"],
    ),
]

# ---------------------------------------------------------------------------
# Known patterns: General
# ---------------------------------------------------------------------------

_GENERAL_PATTERNS: list[KnownPattern] = [
    KnownPattern(
        name="dependency_conflict",
        category="general",
        symptoms=[
            r"dependency conflict",
            r"incompatible.*version",
            r"ResolutionImpossible",
            r"Could not find a version that satisfies",
        ],
        prior_probability=0.07,
        common_causes=[
            "Two packages require incompatible versions of a shared dependency",
            "Lock file out of sync with requirements",
            "Package yanked or removed from PyPI",
        ],
        fix_templates=[
            "Update lock file: pip install --upgrade -r requirements.txt",
            "Use pip-compile to resolve dependency tree",
        ],
        related_patterns=["import_error", "module_not_found", "version_mismatch"],
    ),
    KnownPattern(
        name="version_mismatch",
        category="general",
        symptoms=[
            r"version.*mismatch",
            r"requires.*version",
            r"unsupported.*version",
            r"DeprecationWarning.*removed in",
        ],
        prior_probability=0.06,
        common_causes=[
            "Library upgraded with breaking API changes",
            "Python version too old or too new for package",
            "Pinned version conflicts with runtime requirement",
        ],
        fix_templates=[
            "Pin compatible version: pip install {package}=={version}",
            "Check compatibility matrix in documentation",
        ],
        related_patterns=["dependency_conflict", "type_error", "attribute_error"],
    ),
    KnownPattern(
        name="env_misconfiguration",
        category="general",
        symptoms=[
            r"environment variable.*not set",
            r"ANTHROPIC_API_KEY.*missing",
            r"env.*not configured",
            r"KeyError.*ENV\b|KEY\b|SECRET\b|TOKEN\b",
        ],
        prior_probability=0.06,
        common_causes=[
            "Required environment variable not exported",
            ".env file missing or not loaded",
            "Variable set in wrong shell profile",
        ],
        fix_templates=[
            "Set environment variable: export {var}={value}",
            "Create .env file with required variables",
            "Source environment: source .env",
        ],
        related_patterns=["config_invalid", "key_error"],
    ),
    KnownPattern(
        name="circular_import",
        category="general",
        symptoms=[
            r"circular import",
            r"ImportError.*partially initialized module",
            r"cannot import name.*from partially initialized",
            r"most likely due to a circular import",
        ],
        prior_probability=0.04,
        common_causes=[
            "Module A imports module B which imports module A",
            "Type annotations causing import cycles",
            "Shared utility module importing from consumers",
        ],
        fix_templates=[
            "Use TYPE_CHECKING guard: from __future__ import annotations",
            "Move shared code to a separate utility module",
            "Use lazy imports inside functions",
        ],
        related_patterns=["import_error", "recursion_error"],
    ),
    KnownPattern(
        name="encoding_error",
        category="general",
        symptoms=[
            r"UnicodeDecodeError",
            r"UnicodeEncodeError",
            r"codec can't decode",
            r"codec can't encode",
        ],
        prior_probability=0.03,
        common_causes=[
            "File saved with wrong encoding",
            "Binary data read as text",
            "Locale mismatch between systems",
        ],
        fix_templates=[
            "Open file with explicit encoding: open({path}, encoding='utf-8')",
            "Set PYTHONIOENCODING=utf-8 in environment",
        ],
        related_patterns=["syntax_error", "file_not_found"],
    ),
]

# ---------------------------------------------------------------------------
# Combined list
# ---------------------------------------------------------------------------

KNOWN_PATTERNS: list[KnownPattern] = _PYTHON_PATTERNS + _ZERG_PATTERNS + _GENERAL_PATTERNS


# ---------------------------------------------------------------------------
# PatternMatcher
# ---------------------------------------------------------------------------


class PatternMatcher:
    """Match error text against known failure patterns."""

    def __init__(self) -> None:
        self._patterns = KNOWN_PATTERNS
        self._compiled: dict[str, list[re.Pattern[str]]] = {}
        for pattern in self._patterns:
            self._compiled[pattern.name] = [re.compile(s, re.IGNORECASE) for s in pattern.symptoms]

    def match(self, error_text: str) -> list[tuple[KnownPattern, float]]:
        """Return matched patterns with match scores (0-1).

        Score = matched_symptoms / total_symptoms.
        Only patterns with at least one matching symptom are returned.
        Results are sorted by score descending.
        """
        results: list[tuple[KnownPattern, float]] = []
        for pattern in self._patterns:
            compiled = self._compiled[pattern.name]
            total = len(compiled)
            matched = sum(1 for rx in compiled if rx.search(error_text))
            if matched > 0:
                score = matched / total
                results.append((pattern, score))
        results.sort(key=lambda item: item[1], reverse=True)
        return results

    def get_prior(self, category: str) -> float:
        """Return average prior probability for all patterns in *category*."""
        priors = [p.prior_probability for p in self._patterns if p.category == category]
        if not priors:
            return 0.0
        return sum(priors) / len(priors)

    def get_related(self, pattern_name: str) -> list[KnownPattern]:
        """Return related patterns by name."""
        source: KnownPattern | None = None
        for p in self._patterns:
            if p.name == pattern_name:
                source = p
                break
        if source is None:
            return []
        by_name: dict[str, KnownPattern] = {p.name: p for p in self._patterns}
        return [by_name[n] for n in source.related_patterns if n in by_name]
