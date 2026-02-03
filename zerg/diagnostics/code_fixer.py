"""Code-aware recovery planning with dependency analysis, git context, and fix suggestions."""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path
from typing import Any

from zerg.diagnostics.recovery import RecoveryStep
from zerg.diagnostics.types import ErrorCategory, ErrorFingerprint, Evidence
from zerg.logging import get_logger

logger = get_logger("diagnostics.code_fixer")

__all__ = [
    "CodeAwareFixer",
    "DependencyAnalyzer",
    "FixSuggestionGenerator",
    "GitContextAnalyzer",
]


class DependencyAnalyzer:
    """Analyze Python file imports and dependency chains."""

    def analyze_imports(self, file_path: str) -> list[str]:
        """Parse a Python file using ast and extract all import module names.

        Returns empty list on parse failure.
        """
        try:
            source = Path(file_path).read_text(encoding="utf-8")
            tree = ast.parse(source, filename=file_path)
        except (OSError, SyntaxError, ValueError):
            return []

        modules: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.append(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
        return modules

    def find_missing_deps(self, error_text: str) -> list[str]:
        """Extract module names from ImportError/ModuleNotFoundError messages."""
        missing: list[str] = []
        for match in re.finditer(r"No module named '?(\w+)'?", error_text):
            missing.append(match.group(1))
        for match in re.finditer(r"cannot import name '(\w+)'", error_text):
            missing.append(match.group(1))
        return missing

    def trace_import_chain(self, module: str, project_root: Path) -> list[str]:
        """Find files importing the given module by searching .py files.

        Uses basic string search for speed rather than AST parsing.
        Returns list of file paths.
        """
        importing_files: list[str] = []
        pattern = re.compile(rf"(?:from\s+{re.escape(module)}\s+import|import\s+{re.escape(module)})")
        for py_file in project_root.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
                if pattern.search(content):
                    importing_files.append(str(py_file))
            except OSError:
                continue
        return importing_files


class GitContextAnalyzer:
    """Analyze git history for context around errors."""

    SUBPROCESS_TIMEOUT = 5

    def _run_git(self, args: list[str]) -> tuple[str, bool]:
        """Run a git command with timeout. Returns (stdout, success)."""
        try:
            result = subprocess.run(
                ["git", *args],
                capture_output=True,
                text=True,
                timeout=self.SUBPROCESS_TIMEOUT,
            )
            return result.stdout.strip(), result.returncode == 0
        except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
            return "", False

    def get_recent_changes(self, file_path: str, n: int = 5) -> list[dict[str, str]]:
        """Get recent git log entries for a file.

        Returns list of {"hash", "author", "date", "message"}. Empty list on failure.
        """
        output, success = self._run_git(["log", f"-{n}", "--format=%H|%an|%aI|%s", "--", file_path])
        if not success or not output:
            return []

        changes: list[dict[str, str]] = []
        for line in output.splitlines():
            parts = line.split("|", 3)
            if len(parts) == 4:
                changes.append(
                    {
                        "hash": parts[0],
                        "author": parts[1],
                        "date": parts[2],
                        "message": parts[3],
                    }
                )
        return changes

    def get_blame_context(self, file_path: str, line: int, context: int = 3) -> list[dict[str, str]]:
        """Get git blame for lines around the given line number.

        Returns list of {"line", "hash", "author", "content"}. Empty list on failure.
        """
        start = max(1, line - context)
        end = line + context
        output, success = self._run_git(["blame", f"-L{start},{end}", "--porcelain", file_path])
        if not success or not output:
            return []

        blame_entries: list[dict[str, str]] = []
        current_hash = ""
        current_author = ""
        current_line = str(start)
        for raw_line in output.splitlines():
            if raw_line.startswith("\t"):
                blame_entries.append(
                    {
                        "line": current_line,
                        "hash": current_hash[:8],
                        "author": current_author,
                        "content": raw_line[1:],
                    }
                )
                current_line = str(int(current_line) + 1)
            elif raw_line.startswith("author "):
                current_author = raw_line[len("author ") :]
            elif len(raw_line) >= 40 and raw_line[0].isalnum():
                parts = raw_line.split()
                if parts:
                    current_hash = parts[0]
        return blame_entries

    def suggest_bisect(self, good_ref: str = "HEAD~10", bad_ref: str = "HEAD") -> str:
        """Return a formatted git bisect command string."""
        return f"git bisect start {bad_ref} {good_ref}"


class FixSuggestionGenerator:
    """Generate human-readable fix suggestions and recovery steps."""

    def suggest(
        self,
        fingerprint: ErrorFingerprint,
        evidence: list[Evidence],
    ) -> list[str]:
        """Generate human-readable fix suggestions based on error type and location.

        Returns 1-5 suggestions.
        """
        suggestions: list[str] = []

        category = self._infer_category(fingerprint)

        if category == ErrorCategory.CODE_ERROR:
            if fingerprint.file and fingerprint.line:
                suggestions.append(f"Review code at {fingerprint.file}:{fingerprint.line}")
            elif fingerprint.file:
                suggestions.append(f"Review code in {fingerprint.file}")
            suggestions.append("Check variable types and function signatures")

        elif category == ErrorCategory.DEPENDENCY:
            module = fingerprint.module or fingerprint.error_type
            suggestions.append(f"Install missing module: pip install {module}")
            suggestions.append("Check virtual environment is active")

        elif category == ErrorCategory.INFRASTRUCTURE:
            suggestions.append("Restart service")
            suggestions.append("Check Docker status: docker info")

        elif category == ErrorCategory.STATE_CORRUPTION:
            suggestions.append("Restore from backup")
            suggestions.append("Rebuild state from task graph")

        elif category == ErrorCategory.MERGE_CONFLICT:
            if fingerprint.file:
                suggestions.append(f"Resolve conflicts in {fingerprint.file}")
            suggestions.append("Check file ownership in task graph")

        if not suggestions:
            suggestions.append(f"Investigate error: {fingerprint.error_type}: {fingerprint.message_template}")

        # Add evidence-based suggestions
        for ev in evidence:
            if ev.source == "code" and ev.confidence > 0.7:
                suggestion = f"Review: {ev.description}"
                if suggestion not in suggestions and len(suggestions) < 5:
                    suggestions.append(suggestion)

        return suggestions[:5]

    def generate_recovery_steps(
        self,
        fingerprint: ErrorFingerprint,
        evidence: list[Evidence],
    ) -> list[RecoveryStep]:
        """Generate executable RecoveryStep objects from error fingerprint."""
        steps: list[RecoveryStep] = []
        category = self._infer_category(fingerprint)

        if category == ErrorCategory.CODE_ERROR:
            if fingerprint.file:
                steps.append(
                    RecoveryStep(
                        description=f"Run linter on {fingerprint.file}",
                        command=f"python -m ruff check {fingerprint.file}",
                        risk="safe",
                        reversible=True,
                    )
                )
            steps.append(
                RecoveryStep(
                    description="Run type checker",
                    command="python -m mypy --ignore-missing-imports .",
                    risk="safe",
                    reversible=True,
                )
            )

        elif category == ErrorCategory.DEPENDENCY:
            module = fingerprint.module or "."
            steps.append(
                RecoveryStep(
                    description=f"Install missing dependency: {module}",
                    command=f"pip install {module}",
                    risk="safe",
                    reversible=True,
                )
            )
            steps.append(
                RecoveryStep(
                    description="Reinstall project in editable mode",
                    command="pip install -e .",
                    risk="safe",
                    reversible=True,
                )
            )

        elif category == ErrorCategory.INFRASTRUCTURE:
            steps.append(
                RecoveryStep(
                    description="Check Docker status",
                    command="docker info",
                    risk="safe",
                    reversible=True,
                )
            )
            steps.append(
                RecoveryStep(
                    description="Restart Docker containers",
                    command="docker compose restart",
                    risk="moderate",
                    reversible=True,
                )
            )

        elif category == ErrorCategory.STATE_CORRUPTION:
            steps.append(
                RecoveryStep(
                    description="Validate state JSON files",
                    command='find .zerg/state -name "*.json" -exec python -m json.tool {} \\;',
                    risk="safe",
                    reversible=True,
                )
            )
            steps.append(
                RecoveryStep(
                    description="Restore state from backup",
                    command="cp .zerg/state/*.json.bak .zerg/state/",
                    risk="moderate",
                    reversible=True,
                )
            )

        elif category == ErrorCategory.MERGE_CONFLICT:
            steps.append(
                RecoveryStep(
                    description="Abort current merge",
                    command="git merge --abort",
                    risk="moderate",
                    reversible=True,
                )
            )
            steps.append(
                RecoveryStep(
                    description="Prune stale worktrees",
                    command="git worktree prune",
                    risk="safe",
                    reversible=True,
                )
            )

        if not steps:
            steps.append(
                RecoveryStep(
                    description=f"Investigate: {fingerprint.error_type}",
                    command="zerg debug --deep",
                    risk="safe",
                    reversible=True,
                )
            )

        return steps

    def _infer_category(self, fingerprint: ErrorFingerprint) -> ErrorCategory:
        """Infer error category from fingerprint fields."""
        error_lower = fingerprint.error_type.lower()
        message_lower = fingerprint.message_template.lower()
        combined = f"{error_lower} {message_lower}"

        if "import" in combined or "modulenotfound" in combined:
            return ErrorCategory.DEPENDENCY
        if "merge" in combined or "conflict" in combined:
            return ErrorCategory.MERGE_CONFLICT
        if "corrupt" in combined or "state" in combined:
            return ErrorCategory.STATE_CORRUPTION
        if "docker" in combined or "connection" in combined or "timeout" in combined:
            return ErrorCategory.INFRASTRUCTURE
        if fingerprint.file and fingerprint.line:
            return ErrorCategory.CODE_ERROR
        return ErrorCategory.UNKNOWN


class CodeAwareFixer:
    """Facade combining dependency, git, and fix suggestion analysis."""

    def __init__(self) -> None:
        self.dependency_analyzer = DependencyAnalyzer()
        self.git_analyzer = GitContextAnalyzer()
        self.suggestion_generator = FixSuggestionGenerator()

    def analyze(
        self,
        fingerprint: ErrorFingerprint,
        evidence: list[Evidence],
        project_root: Path = Path("."),
    ) -> dict[str, Any]:
        """Run full code-aware analysis and return combined results.

        Returns dict with 'dependencies', 'git_context', 'suggestions',
        and 'recovery_steps'.
        """
        result: dict[str, Any] = {}

        # Dependency analysis for Python files
        if fingerprint.file and fingerprint.file.endswith(".py"):
            file_path = str(project_root / fingerprint.file)
            imports = self.dependency_analyzer.analyze_imports(file_path)
            missing = self.dependency_analyzer.find_missing_deps(fingerprint.message_template)
            result["dependencies"] = {
                "imports": imports,
                "missing": missing,
            }

        # Git context if file and line are available
        if fingerprint.file and fingerprint.line:
            recent = self.git_analyzer.get_recent_changes(fingerprint.file)
            blame = self.git_analyzer.get_blame_context(fingerprint.file, fingerprint.line)
            result["git_context"] = {
                "recent_changes": recent,
                "blame": blame,
            }

        # Fix suggestions
        result["suggestions"] = self.suggestion_generator.suggest(fingerprint, evidence)

        # Recovery steps as dicts
        steps = self.suggestion_generator.generate_recovery_steps(fingerprint, evidence)
        result["recovery_steps"] = [s.to_dict() for s in steps]

        return result
