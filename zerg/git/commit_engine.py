"""Smart commit engine with configurable AI aggression.

Provides diff analysis, commit message generation, staging suggestions,
pre-commit validation, and orchestration of the full commit workflow.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from zerg.git.config import GitCommitConfig, GitConfig
from zerg.git.types import CommitType, DiffAnalysis
from zerg.logging import get_logger

if TYPE_CHECKING:
    from zerg.git.base import GitRunner

logger = get_logger("git.commit_engine")

# Conventional commit type patterns absorbed from git_cmd.py
COMMIT_TYPE_PATTERNS: dict[CommitType, list[str]] = {
    CommitType.FEAT: [r"add\s+", r"implement\s+", r"create\s+", r"new\s+", r"feature"],
    CommitType.FIX: [r"fix\s+", r"bug\s*fix", r"resolve\s+", r"correct\s+", r"patch"],
    CommitType.DOCS: [r"doc[s]?\s+", r"readme", r"comment", r"documentation"],
    CommitType.STYLE: [r"format", r"style", r"lint", r"whitespace", r"prettier"],
    CommitType.REFACTOR: [r"refactor", r"restructure", r"reorganize", r"clean\s*up"],
    CommitType.TEST: [r"test", r"spec", r"coverage"],
    CommitType.CHORE: [r"chore", r"build", r"ci", r"deps", r"bump", r"update.*dep"],
}

# File extension to commit type mapping for fast path detection
_EXT_TYPE_MAP: dict[str, CommitType] = {
    ".md": CommitType.DOCS,
    ".rst": CommitType.DOCS,
    ".txt": CommitType.DOCS,
}

# Directory patterns that strongly signal commit type
_DIR_TYPE_MAP: dict[str, CommitType] = {
    "test": CommitType.TEST,
    "tests": CommitType.TEST,
    "__tests__": CommitType.TEST,
    "spec": CommitType.TEST,
    "docs": CommitType.DOCS,
    "doc": CommitType.DOCS,
}


class DiffAnalyzer:
    """Analyzes git diffs to produce structured DiffAnalysis objects."""

    def analyze_staged(self, runner: GitRunner) -> DiffAnalysis:
        """Analyze staged (cached) changes.

        Args:
            runner: GitRunner instance for executing git commands.

        Returns:
            DiffAnalysis with file groupings and statistics.
        """
        return self._analyze(runner, cached=True)

    def analyze_unstaged(self, runner: GitRunner) -> DiffAnalysis:
        """Analyze unstaged (working tree) changes.

        Args:
            runner: GitRunner instance for executing git commands.

        Returns:
            DiffAnalysis with file groupings and statistics.
        """
        return self._analyze(runner, cached=False)

    def _analyze(self, runner: GitRunner, *, cached: bool) -> DiffAnalysis:
        """Run git diff commands and parse output into DiffAnalysis.

        Args:
            runner: GitRunner instance.
            cached: If True, analyze staged changes; otherwise unstaged.

        Returns:
            Populated DiffAnalysis dataclass.
        """
        stat_args = ["diff", "--stat"]
        numstat_args = ["diff", "--numstat"]

        if cached:
            stat_args.append("--cached")
            numstat_args.append("--cached")

        runner._run(*stat_args, check=False)
        numstat_result = runner._run(*numstat_args, check=False)

        return self._parse_numstat(numstat_result.stdout or "")

    def _parse_numstat(self, numstat_output: str) -> DiffAnalysis:
        """Parse git diff --numstat output into a DiffAnalysis.

        Format per line: <insertions>\\t<deletions>\\t<filename>
        Binary files show '-' for insertions/deletions.

        Args:
            numstat_output: Raw output from git diff --numstat.

        Returns:
            Populated DiffAnalysis.
        """
        analysis = DiffAnalysis()

        for line in numstat_output.strip().splitlines():
            line = line.strip()
            if not line:
                continue

            parts = line.split("\t", 2)
            if len(parts) < 3:
                continue

            ins_str, del_str, filepath = parts

            # Binary files use '-' for stats
            insertions = int(ins_str) if ins_str != "-" else 0
            deletions = int(del_str) if del_str != "-" else 0

            analysis.files_changed.append(filepath)
            analysis.insertions += insertions
            analysis.deletions += deletions

            # Group by extension
            ext = PurePosixPath(filepath).suffix or "(no ext)"
            analysis.by_extension.setdefault(ext, []).append(filepath)

            # Group by top-level directory
            path_parts = PurePosixPath(filepath).parts
            directory = path_parts[0] if len(path_parts) > 1 else "."
            analysis.by_directory.setdefault(directory, []).append(filepath)

        return analysis


class CommitMessageGenerator:
    """Generates conventional commit messages from diff analysis."""

    def __init__(self, config: GitCommitConfig) -> None:
        self.config = config

    def detect_commit_type(self, diff: DiffAnalysis) -> CommitType:
        """Detect conventional commit type from file patterns and diff stats.

        Priority order:
        1. File-based heuristics (test files, doc files, CI config)
        2. Directory-based heuristics (tests/, docs/)
        3. Pattern matching against filenames
        4. Fallback to CHORE

        Args:
            diff: Analyzed diff data.

        Returns:
            Detected CommitType.
        """
        files = diff.files_changed
        if not files:
            return CommitType.CHORE

        # 1. Check if majority of files are test files
        test_files = [f for f in files if self._is_test_file(f)]
        if len(test_files) > len(files) / 2:
            return CommitType.TEST

        # 2. Check if majority of files are documentation
        doc_files = [f for f in files if self._is_doc_file(f)]
        if len(doc_files) > len(files) / 2:
            return CommitType.DOCS

        # 3. Check directory-based signals
        dir_type = self._detect_from_directories(diff.by_directory)
        if dir_type is not None:
            return dir_type

        # 4. Pattern matching against combined file names
        combined = " ".join(files).lower()
        for commit_type, patterns in COMMIT_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, combined, re.IGNORECASE):
                    return commit_type

        return CommitType.CHORE

    def generate(self, diff: DiffAnalysis) -> str:
        """Generate a single conventional commit message.

        Args:
            diff: Analyzed diff data.

        Returns:
            Formatted commit message string.
        """
        commit_type = self.detect_commit_type(diff)
        scope = self._infer_scope(diff)
        summary = self._build_summary(diff)

        if scope:
            return f"{commit_type.value}({scope}): {summary}"
        return f"{commit_type.value}: {summary}"

    def suggest(self, diff: DiffAnalysis) -> list[str]:
        """Generate 3 candidate commit messages for suggest mode.

        Provides variations: concise, descriptive, and scope-focused.

        Args:
            diff: Analyzed diff data.

        Returns:
            List of 3 candidate message strings.
        """
        commit_type = self.detect_commit_type(diff)
        scope = self._infer_scope(diff)
        summary = self._build_summary(diff)

        candidates: list[str] = []

        # Candidate 1: concise (no scope)
        candidates.append(f"{commit_type.value}: {summary}")

        # Candidate 2: with scope if available
        if scope:
            candidates.append(f"{commit_type.value}({scope}): {summary}")
        else:
            # Alternative wording
            alt_summary = self._build_summary_verbose(diff)
            candidates.append(f"{commit_type.value}: {alt_summary}")

        # Candidate 3: stats-based
        stats_summary = self._build_stats_summary(diff)
        candidates.append(f"{commit_type.value}: {stats_summary}")

        return candidates

    # --- Private helpers ---

    @staticmethod
    def _is_test_file(filepath: str) -> bool:
        """Check if a file is a test file."""
        name = PurePosixPath(filepath).name.lower()
        parts = PurePosixPath(filepath).parts
        return (
            name.startswith("test_")
            or name.endswith("_test.py")
            or name.endswith(".test.js")
            or name.endswith(".test.ts")
            or name.endswith(".spec.js")
            or name.endswith(".spec.ts")
            or any(p in ("test", "tests", "__tests__", "spec") for p in parts)
        )

    @staticmethod
    def _is_doc_file(filepath: str) -> bool:
        """Check if a file is a documentation file."""
        ext = PurePosixPath(filepath).suffix.lower()
        name = PurePosixPath(filepath).name.lower()
        return ext in _EXT_TYPE_MAP or name in ("readme", "changelog", "license", "contributing")

    @staticmethod
    def _detect_from_directories(by_directory: dict[str, list[str]]) -> CommitType | None:
        """Detect commit type from directory grouping."""
        if not by_directory:
            return None

        # If a single directory dominates and maps to a known type
        for dirname, dir_files in by_directory.items():
            lower_dir = dirname.lower()
            if lower_dir in _DIR_TYPE_MAP:
                return _DIR_TYPE_MAP[lower_dir]

        return None

    @staticmethod
    def _infer_scope(diff: DiffAnalysis) -> str | None:
        """Infer scope from file groupings.

        Returns a scope string when all files share a clear common directory.
        """
        dirs = list(diff.by_directory.keys())
        if len(dirs) == 1 and dirs[0] != ".":
            return dirs[0]
        return None

    @staticmethod
    def _build_summary(diff: DiffAnalysis) -> str:
        """Build a concise summary from changed files."""
        files = diff.files_changed
        if not files:
            return "update files"

        if len(files) == 1:
            return f"update {PurePosixPath(files[0]).stem}"

        if len(files) <= 3:
            stems = [PurePosixPath(f).stem for f in files[:3]]
            return f"update {', '.join(stems)}"

        # Group by directory for larger changes
        dirs = list(diff.by_directory.keys())
        if dirs:
            dir_names = [d for d in dirs[:2] if d != "."]
            if dir_names:
                return f"update {', '.join(dir_names)} files"

        return f"update {len(files)} files"

    @staticmethod
    def _build_summary_verbose(diff: DiffAnalysis) -> str:
        """Build a more descriptive summary."""
        files = diff.files_changed
        if not files:
            return "update project files"

        n = len(files)
        ins = diff.insertions
        dels = diff.deletions
        if ins and dels:
            return f"update {n} files (+{ins}/-{dels})"
        if ins:
            return f"add content across {n} files"
        if dels:
            return f"remove content across {n} files"
        return f"update {n} files"

    @staticmethod
    def _build_stats_summary(diff: DiffAnalysis) -> str:
        """Build a stats-oriented summary."""
        n = len(diff.files_changed)
        ins = diff.insertions
        dels = diff.deletions
        parts = [f"{n} file{'s' if n != 1 else ''}"]
        if ins:
            parts.append(f"+{ins}")
        if dels:
            parts.append(f"-{dels}")
        return f"update {', '.join(parts)}"


class StagingSuggester:
    """Suggests unstaged files related to already-staged files."""

    def suggest_related(self, runner: GitRunner, staged_files: list[str]) -> list[str]:
        """Find unstaged files related to the given staged files.

        Looks for unstaged files in the same directories or with matching
        extension patterns as the staged files.

        Args:
            runner: GitRunner instance for querying unstaged changes.
            staged_files: List of already-staged file paths.

        Returns:
            List of unstaged file paths that appear related.
        """
        if not staged_files:
            return []

        # Get unstaged files
        result = runner._run("diff", "--name-only", check=False)
        unstaged_raw = result.stdout.strip() if result.stdout else ""
        if not unstaged_raw:
            return []

        unstaged_files = [f for f in unstaged_raw.splitlines() if f.strip()]

        # Build sets for matching
        staged_dirs = {str(PurePosixPath(f).parent) for f in staged_files}
        staged_exts = {PurePosixPath(f).suffix for f in staged_files if PurePosixPath(f).suffix}

        related: list[str] = []
        for uf in unstaged_files:
            if uf in staged_files:
                continue
            uf_dir = str(PurePosixPath(uf).parent)
            uf_ext = PurePosixPath(uf).suffix
            if uf_dir in staged_dirs or (uf_ext and uf_ext in staged_exts):
                related.append(uf)

        return related


class PreCommitValidator:
    """Validates commit messages before committing."""

    # Patterns that indicate work-in-progress
    _WIP_PATTERNS = [
        re.compile(r"^wip\b", re.IGNORECASE),
        re.compile(r"^work.in.progress\b", re.IGNORECASE),
    ]

    _FIXUP_PREFIX = "fixup!"
    _MIN_LENGTH = 10
    _MAX_FIRST_LINE = 72

    def validate(self, message: str) -> list[str]:
        """Validate a commit message and return a list of issues.

        Checks for:
        - Empty message
        - Message too short (<10 chars)
        - First line too long (>72 chars)
        - WIP markers
        - fixup! prefix

        Args:
            message: The commit message to validate.

        Returns:
            List of issue description strings. Empty list means valid.
        """
        issues: list[str] = []

        stripped = message.strip()
        if not stripped:
            issues.append("Commit message is empty")
            return issues

        if len(stripped) < self._MIN_LENGTH:
            issues.append(f"Commit message too short ({len(stripped)} chars, minimum {self._MIN_LENGTH})")

        first_line = stripped.splitlines()[0]
        if len(first_line) > self._MAX_FIRST_LINE:
            issues.append(f"First line too long ({len(first_line)} chars, maximum {self._MAX_FIRST_LINE})")

        for wip_pat in self._WIP_PATTERNS:
            if wip_pat.search(first_line):
                issues.append("Commit message contains WIP marker")
                break

        if first_line.startswith(self._FIXUP_PREFIX):
            issues.append("Commit message has fixup! prefix")

        return issues


class CommitEngine:
    """Main entry point orchestrating the full commit workflow.

    Coordinates DiffAnalyzer, CommitMessageGenerator, PreCommitValidator,
    and StagingSuggester based on the configured mode.
    """

    def __init__(self, runner: GitRunner, config: GitConfig) -> None:
        self.runner = runner
        self.config = config
        self._analyzer = DiffAnalyzer()
        self._generator = CommitMessageGenerator(config.commit)
        self._validator = PreCommitValidator()
        self._suggester = StagingSuggester()

    def run(self, mode: str | None = None) -> int:
        """Orchestrate the commit flow based on mode.

        Modes:
        - auto: stage all -> analyze -> generate message -> commit
        - confirm (default): analyze -> generate message -> return 0 for confirmation
        - suggest: analyze -> return 3 candidates -> return 0

        Args:
            mode: Override mode. If None, uses config.commit.mode.

        Returns:
            Exit code. 0 for success, 1 for failure.
        """
        effective_mode = mode or self.config.commit.mode

        if effective_mode == "auto":
            return self._run_auto()
        elif effective_mode == "suggest":
            return self._run_suggest()
        else:
            return self._run_confirm()

    @property
    def message(self) -> str | None:
        """Last generated commit message (set after run in confirm/auto modes)."""
        return getattr(self, "_last_message", None)

    @property
    def suggestions(self) -> list[str] | None:
        """Last generated suggestions (set after run in suggest mode)."""
        return getattr(self, "_last_suggestions", None)

    def _run_auto(self) -> int:
        """Auto mode: stage all, analyze, generate, commit."""
        # Stage all changes
        self.runner._run("add", "-A", check=False)

        diff = self._analyzer.analyze_staged(self.runner)
        if not diff.files_changed:
            logger.info("No staged changes to commit")
            return 1

        message = self._generator.generate(diff)
        issues = self._validator.validate(message)
        if issues:
            logger.warning("Generated message has validation issues: %s", issues)

        # Perform the commit
        sign_args = ["-S"] if self.config.commit.sign else []
        self.runner._run("commit", "-m", message, *sign_args)

        self._last_message = message
        logger.info("Auto-committed: %s", message)
        return 0

    def _run_confirm(self) -> int:
        """Confirm mode: analyze staged, generate message, store for confirmation."""
        diff = self._analyzer.analyze_staged(self.runner)
        if not diff.files_changed:
            logger.info("No staged changes to analyze")
            return 1

        message = self._generator.generate(diff)
        self._last_message = message
        return 0

    def _run_suggest(self) -> int:
        """Suggest mode: analyze staged, generate 3 candidates."""
        diff = self._analyzer.analyze_staged(self.runner)
        if not diff.files_changed:
            logger.info("No staged changes to analyze")
            return 1

        suggestions = self._generator.suggest(diff)
        self._last_suggestions = suggestions
        return 0
