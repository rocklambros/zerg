"""AI-powered git bisect with predictive ranking, semantic testing, and root cause analysis.

Provides intelligent commit ranking to reduce bisect iterations,
semantic test output analysis, and automated root cause reports.
"""

from __future__ import annotations

import re
import shlex
import subprocess
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from zerg.git.commit_engine import COMMIT_TYPE_PATTERNS
from zerg.git.config import GitConfig
from zerg.git.types import CommitInfo, CommitType
from zerg.logging import get_logger

if TYPE_CHECKING:
    from zerg.git.base import GitRunner

logger = get_logger("git.bisect_engine")

# Commit types that are more likely to introduce bugs
_HIGH_RISK_TYPES: frozenset[CommitType] = frozenset(
    {
        CommitType.FEAT,
        CommitType.REFACTOR,
        CommitType.FIX,
        CommitType.PERF,
        CommitType.REVERT,
    }
)

_LOW_RISK_TYPES: frozenset[CommitType] = frozenset(
    {
        CommitType.DOCS,
        CommitType.STYLE,
        CommitType.CHORE,
        CommitType.CI,
        CommitType.BUILD,
    }
)


def _detect_commit_type_from_message(message: str) -> CommitType | None:
    """Detect commit type from a commit message using conventional commit patterns.

    Args:
        message: The commit message string.

    Returns:
        Detected CommitType or None if no match found.
    """
    # Try conventional commit prefix first (e.g., "feat: ..." or "feat(scope): ...")
    prefix_match = re.match(r"^(\w+)(?:\(.*?\))?:\s", message)
    if prefix_match:
        prefix = prefix_match.group(1).lower()
        for ct in CommitType:
            if ct.value == prefix:
                return ct

    # Fall back to pattern matching
    lower_msg = message.lower()
    for commit_type, patterns in COMMIT_TYPE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, lower_msg, re.IGNORECASE):
                return commit_type

    return None


def _extract_file_hints_from_symptom(symptom: str) -> list[str]:
    """Extract potential file paths or module names from a symptom description.

    Looks for patterns like file extensions, module paths, and common path separators.

    Args:
        symptom: The symptom description string.

    Returns:
        List of potential file path fragments.
    """
    hints: list[str] = []

    # Match file-like patterns (e.g., foo/bar.py, src/main.js)
    file_patterns = re.findall(r"[\w./\\-]+\.\w{1,5}", symptom)
    hints.extend(file_patterns)

    # Match module paths (e.g., zerg.git.base, foo.bar)
    module_patterns = re.findall(r"\b[\w]+(?:\.[\w]+){2,}\b", symptom)
    for mod in module_patterns:
        # Convert dotted module to path
        hints.append(mod.replace(".", "/"))

    return hints


def _sanitize_text(text: str) -> str:
    """Sanitize text for inclusion in markdown reports.

    Prevents markdown injection and removes control characters.

    Args:
        text: Raw text to sanitize.

    Returns:
        Sanitized text safe for markdown inclusion.
    """
    # Remove control characters except newline and tab
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Escape backticks to prevent code block injection
    sanitized = sanitized.replace("```", r"\`\`\`")
    return sanitized


class CommitRanker:
    """Ranks commits by probability of causing a given symptom.

    Uses file overlap, change size, recency, and commit type
    to produce a normalized score for each commit in a range.
    """

    def __init__(self, runner: GitRunner) -> None:
        self._runner = runner

    def get_commits_in_range(self, good: str, bad: str) -> list[CommitInfo]:
        """Get all commits between good and bad refs.

        Args:
            good: The known-good commit SHA or ref.
            bad: The known-bad commit SHA or ref.

        Returns:
            List of CommitInfo objects ordered from oldest to newest.
        """
        result = self._runner._run(
            "log",
            f"{good}..{bad}",
            "--format=%H|||%s|||%an|||%ai",
            "--name-only",
        )
        return self._parse_log_output(result.stdout)

    def _parse_log_output(self, output: str) -> list[CommitInfo]:
        """Parse git log output with name-only into CommitInfo objects.

        Expected format per commit block:
            SHA|||subject|||author|||date
            file1
            file2
            (blank line)

        Args:
            output: Raw git log output.

        Returns:
            List of parsed CommitInfo objects.
        """
        commits: list[CommitInfo] = []
        if not output or not output.strip():
            return commits

        blocks = output.strip().split("\n\n")
        for block in blocks:
            lines = [line for line in block.strip().splitlines() if line.strip()]
            if not lines:
                continue

            header = lines[0]
            parts = header.split("|||")
            if len(parts) < 4:
                continue

            sha = parts[0].strip()
            message = parts[1].strip()
            author = parts[2].strip()
            date = parts[3].strip()
            files = tuple(line.strip() for line in lines[1:] if line.strip())
            commit_type = _detect_commit_type_from_message(message)

            commits.append(
                CommitInfo(
                    sha=sha,
                    message=message,
                    author=author,
                    date=date,
                    files=files,
                    commit_type=commit_type,
                )
            )

        return commits

    def rank(
        self,
        commits: list[CommitInfo],
        symptom: str,
        failing_files: list[str] | None = None,
    ) -> list[dict]:
        """Rank commits by likelihood of causing the symptom.

        Score formula: file_overlap * 0.4 + size * 0.2 + recency * 0.2 + type * 0.2

        Args:
            commits: List of commits to rank.
            symptom: Description of the failure symptom.
            failing_files: Optional list of files known to be failing.

        Returns:
            List of dicts with keys: commit, score, reasons. Sorted by score descending.
        """
        if not commits:
            return []

        # Extract file hints from symptom if failing_files not provided
        target_files = failing_files or _extract_file_hints_from_symptom(symptom)

        # Precompute normalization values
        max_files = max((len(c.files) for c in commits), default=1) or 1
        total_commits = len(commits)

        results: list[dict] = []
        for idx, commit in enumerate(commits):
            reasons: list[str] = []

            # File overlap score (0.0 - 1.0)
            file_overlap = 0.0
            if target_files and commit.files:
                overlap_count = sum(1 for cf in commit.files for tf in target_files if tf in cf or cf in tf)
                file_overlap = min(overlap_count / max(len(target_files), 1), 1.0)
                if file_overlap > 0:
                    reasons.append(f"file overlap: {overlap_count} matching files")

            # Size score (0.0 - 1.0) - larger changes = higher risk
            size_score = len(commit.files) / max_files if commit.files else 0.0
            if size_score > 0.5:
                reasons.append(f"large change: {len(commit.files)} files")

            # Recency score (0.0 - 1.0) - more recent = higher score
            recency_score = (idx + 1) / total_commits
            if recency_score > 0.7:
                reasons.append("recent commit")

            # Type score (0.0 - 1.0)
            type_score = 0.5  # default for unknown type
            if commit.commit_type in _HIGH_RISK_TYPES:
                type_score = 1.0
                reasons.append(f"high-risk type: {commit.commit_type.value}")
            elif commit.commit_type in _LOW_RISK_TYPES:
                type_score = 0.1
                reasons.append(f"low-risk type: {commit.commit_type.value}")

            total_score = file_overlap * 0.4 + size_score * 0.2 + recency_score * 0.2 + type_score * 0.2

            if not reasons:
                reasons.append("baseline score")

            results.append(
                {
                    "commit": commit,
                    "score": round(total_score, 4),
                    "reasons": reasons,
                }
            )

        results.sort(key=lambda r: r["score"], reverse=True)
        return results


class SemanticTester:
    """Analyzes test output semantically to determine pass/fail status.

    Runs test commands and parses output for common test framework patterns.
    """

    def run_test(self, command: str, timeout: int = 120) -> dict:
        """Run a test command and capture output.

        Args:
            command: Test command string to execute.
            timeout: Maximum execution time in seconds.

        Returns:
            Dict with keys: exit_code, stdout, stderr, passed.
        """
        args = shlex.split(command)
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "passed": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                "passed": False,
            }
        except FileNotFoundError:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Command not found: {args[0]}",
                "passed": False,
            }

    def analyze_output(self, result: dict) -> dict:
        """Analyze test output to extract structured failure information.

        Looks for common test framework patterns (pytest, unittest, jest, etc.).

        Args:
            result: Dict from run_test with stdout, stderr, exit_code.

        Returns:
            Dict with keys: status, failing_tests, error_message.
        """
        combined = result.get("stdout", "") + "\n" + result.get("stderr", "")
        exit_code = result.get("exit_code", -1)

        if exit_code == 0:
            return {
                "status": "pass",
                "failing_tests": [],
                "error_message": "",
            }

        failing_tests: list[str] = []
        error_message = ""

        # Extract failing test names from common patterns
        # pytest: "FAILED tests/test_foo.py::test_bar"
        pytest_fails = re.findall(r"FAILED\s+([\w/.:-]+)", combined)
        failing_tests.extend(pytest_fails)

        # unittest: "FAIL: test_bar (tests.test_foo.TestFoo)"
        unittest_fails = re.findall(r"FAIL:\s+([\w]+)\s+\(", combined)
        failing_tests.extend(unittest_fails)

        # Generic: "test_foo ... FAIL"
        generic_fails = re.findall(r"(test_\w+)\s+\.{3}\s+FAIL", combined)
        failing_tests.extend(generic_fails)

        # Extract error messages
        error_lines = re.findall(r"(?:ERROR|Error|error)[:]\s*(.+)", combined)
        if error_lines:
            error_message = error_lines[0].strip()

        # Determine status
        if "ERROR" in combined and not failing_tests:
            status = "error"
            if not error_message:
                error_message = "Test execution error"
        else:
            status = "fail"

        return {
            "status": status,
            "failing_tests": failing_tests,
            "error_message": error_message,
        }


class BisectRunner:
    """Runs bisect process with predictive optimization and git bisect fallback."""

    def __init__(
        self,
        runner: GitRunner,
        ranker: CommitRanker,
        tester: SemanticTester,
    ) -> None:
        self._runner = runner
        self._ranker = ranker
        self._tester = tester

    def run_predictive(
        self,
        good: str,
        bad: str,
        symptom: str,
        test_cmd: str,
    ) -> dict | None:
        """Try to find the culprit commit using predictive ranking.

        Tests the highest-scored commits first. If a commit with score > 0.9
        is found, tests it directly.

        Args:
            good: Known-good commit ref.
            bad: Known-bad commit ref.
            symptom: Description of the failure.
            test_cmd: Command to test each commit.

        Returns:
            Dict with culprit, score, test_result, or None if no confident match.
        """
        commits = self._ranker.get_commits_in_range(good, bad)
        if not commits:
            return None

        ranked = self._ranker.rank(commits, symptom)

        # Save current ref for cleanup
        original_ref = self._runner.current_commit()

        try:
            for entry in ranked:
                commit: CommitInfo = entry["commit"]
                score: float = entry["score"]

                # Only test commits with reasonable confidence
                if score < 0.3:
                    break

                # Checkout this commit
                self._runner._run("checkout", commit.sha, check=False)

                # Run the test
                test_result = self._tester.run_test(test_cmd)

                if not test_result["passed"]:
                    return {
                        "culprit": commit,
                        "score": score,
                        "test_result": test_result,
                    }
        finally:
            # Restore original position
            self._runner._run("checkout", original_ref, check=False)

        return None

    def run_git_bisect(
        self,
        good: str,
        bad: str,
        test_cmd: str,
    ) -> dict | None:
        """Fall back to standard git bisect.

        Args:
            good: Known-good commit ref.
            bad: Known-bad commit ref.
            test_cmd: Command to run for bisect testing.

        Returns:
            Dict with culprit_sha and message, or None on failure.
        """
        try:
            # Start bisect
            self._runner._run("bisect", "start", check=False)
            self._runner._run("bisect", "bad", bad, check=False)
            self._runner._run("bisect", "good", good, check=False)

            # Run automated bisect
            args = shlex.split(test_cmd)
            result = self._runner._run(
                "bisect",
                "run",
                *args,
                check=False,
                timeout=600,
            )

            output = result.stdout or ""

            # Parse the result - git bisect prints the first bad commit
            sha_match = re.search(r"([0-9a-f]{40}) is the first bad commit", output)
            if sha_match:
                culprit_sha = sha_match.group(1)
                # Extract commit message
                msg_match = re.search(r"commit message:\s*(.+)", output, re.DOTALL)
                message = msg_match.group(1).strip() if msg_match else ""
                return {
                    "culprit_sha": culprit_sha,
                    "message": message,
                }

            return None
        finally:
            # Always clean up
            self._runner._run("bisect", "reset", check=False)

    def run(
        self,
        good: str,
        bad: str,
        symptom: str,
        test_cmd: str,
    ) -> dict:
        """Orchestrate bisect: predictive first, then git bisect fallback.

        Args:
            good: Known-good commit ref.
            bad: Known-bad commit ref.
            symptom: Description of the failure.
            test_cmd: Command to test with.

        Returns:
            Result dict with method used and findings.
        """
        logger.info("Starting predictive bisect for symptom: %s", symptom)

        # Try predictive approach first
        predictive_result = self.run_predictive(good, bad, symptom, test_cmd)
        if predictive_result:
            logger.info(
                "Predictive bisect found culprit: %s (score: %.2f)",
                predictive_result["culprit"].sha[:8],
                predictive_result["score"],
            )
            return {
                "method": "predictive",
                "culprit": predictive_result["culprit"],
                "score": predictive_result["score"],
                "test_result": predictive_result["test_result"],
            }

        # Fall back to git bisect
        logger.info("Predictive bisect inconclusive, falling back to git bisect")
        bisect_result = self.run_git_bisect(good, bad, test_cmd)
        if bisect_result:
            return {
                "method": "git_bisect",
                "culprit_sha": bisect_result["culprit_sha"],
                "message": bisect_result["message"],
            }

        return {
            "method": "failed",
            "culprit": None,
            "message": "Could not identify culprit commit",
        }


class RootCauseAnalyzer:
    """Produces a root cause report for a culprit commit."""

    def analyze(
        self,
        runner: GitRunner,
        culprit: CommitInfo,
        symptom: str,
    ) -> dict:
        """Analyze a culprit commit to produce a root cause report.

        Args:
            runner: GitRunner instance for executing git commands.
            culprit: The identified culprit commit.
            symptom: The original symptom description.

        Returns:
            Dict with commit, diff_summary, likely_cause, suggestion.
        """
        # Get the stat summary
        stat_result = runner._run("show", "--stat", culprit.sha, check=False)
        diff_summary = stat_result.stdout.strip() if stat_result.stdout else ""

        # Determine likely cause based on commit type and files
        likely_cause = self._determine_cause(culprit, symptom)
        suggestion = self._build_suggestion(culprit)

        return {
            "commit": culprit,
            "diff_summary": diff_summary,
            "likely_cause": likely_cause,
            "suggestion": suggestion,
        }

    def _determine_cause(self, culprit: CommitInfo, symptom: str) -> str:
        """Determine the likely cause based on commit metadata.

        Args:
            culprit: The culprit commit.
            symptom: The symptom description.

        Returns:
            Human-readable likely cause string.
        """
        ct = culprit.commit_type

        if ct == CommitType.REFACTOR:
            return f"Refactoring in commit {culprit.sha[:8]} likely broke existing behavior"
        elif ct == CommitType.FEAT:
            return f"New feature in commit {culprit.sha[:8]} introduced a regression"
        elif ct == CommitType.FIX:
            return f"Bug fix in commit {culprit.sha[:8]} may have introduced a side effect"
        elif ct == CommitType.PERF:
            return f"Performance change in commit {culprit.sha[:8]} altered behavior"
        elif ct == CommitType.REVERT:
            return f"Revert in commit {culprit.sha[:8]} undid a required change"
        else:
            return f"Changes in commit {culprit.sha[:8]} ({culprit.message}) correlate with symptom"

    def _build_suggestion(self, culprit: CommitInfo) -> str:
        """Build a suggestion for reviewing the culprit.

        Args:
            culprit: The culprit commit.

        Returns:
            Actionable suggestion string.
        """
        if culprit.files:
            file_list = ", ".join(culprit.files[:5])
            suffix = f" and {len(culprit.files) - 5} more" if len(culprit.files) > 5 else ""
            return f"Review changes in {file_list}{suffix}"
        return f"Review full diff of commit {culprit.sha[:8]}"


class BisectEngine:
    """Main entry point for AI-powered git bisect.

    Orchestrates commit ranking, predictive bisection, semantic testing,
    root cause analysis, and report generation.
    """

    def __init__(self, runner: GitRunner, config: GitConfig) -> None:
        self._runner = runner
        self._config = config
        self._ranker = CommitRanker(runner)
        self._tester = SemanticTester()
        self._bisect_runner = BisectRunner(runner, self._ranker, self._tester)
        self._analyzer = RootCauseAnalyzer()

    def run(
        self,
        symptom: str,
        test_cmd: str | None = None,
        good: str | None = None,
        bad: str | None = None,
    ) -> int:
        """Run the full bisect workflow.

        Args:
            symptom: Description of the failure to investigate.
            test_cmd: Test command to validate each commit. Auto-detected if None.
            good: Known-good commit ref. Defaults to latest tag or first commit.
            bad: Known-bad commit ref. Defaults to HEAD.

        Returns:
            0 on success, 1 on failure.
        """
        # Resolve defaults
        bad = bad or self._runner.current_commit()
        good = good or self._find_good_default()
        test_cmd = test_cmd or self._detect_test_command()

        if not test_cmd:
            logger.error("No test command provided and auto-detection failed")
            return 1

        logger.info(
            "Bisecting: good=%s bad=%s test_cmd=%s",
            good[:8] if len(good) >= 8 else good,
            bad[:8] if len(bad) >= 8 else bad,
            test_cmd,
        )

        # Run the bisect
        result = self._bisect_runner.run(good, bad, symptom, test_cmd)

        # Analyze if we found a culprit
        culprit = result.get("culprit")
        if culprit and isinstance(culprit, CommitInfo):
            analysis = self._analyzer.analyze(self._runner, culprit, symptom)
            result["analysis"] = analysis

        # Save report
        self._save_report(symptom, test_cmd, result)

        if result.get("method") == "failed":
            logger.error("Bisect failed to find culprit")
            return 1

        logger.info("Bisect complete. Report saved.")
        return 0

    def _find_good_default(self) -> str:
        """Find a default good ref (latest tag, or first commit).

        Returns:
            Commit SHA or tag name to use as the good ref.
        """
        # Try latest tag
        try:
            result = self._runner._run(
                "describe",
                "--tags",
                "--abbrev=0",
                check=False,
            )
            tag = result.stdout.strip() if result.stdout else ""
            if tag and result.returncode == 0:
                return tag
        except Exception:
            pass

        # Fall back to first commit
        try:
            result = self._runner._run(
                "rev-list",
                "--max-parents=0",
                "HEAD",
            )
            return result.stdout.strip().splitlines()[0]
        except Exception:
            return "HEAD~10"

    def _detect_test_command(self) -> str | None:
        """Auto-detect test command from project configuration.

        Checks pyproject.toml, then package.json for test scripts.

        Returns:
            Detected test command string, or None if not found.
        """
        repo_path = self._runner.repo_path

        # Check pyproject.toml
        pyproject = repo_path / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text(encoding="utf-8")
            # Look for pytest configuration
            if "pytest" in content or "tool.pytest" in content:
                return "pytest -x -q"

        # Check package.json
        package_json = repo_path / "package.json"
        if package_json.exists():
            return "npm test"

        return None

    def _save_report(self, symptom: str, test_cmd: str, result: dict) -> None:
        """Save the bisect report to a markdown file.

        Args:
            symptom: Original symptom description.
            test_cmd: Test command used.
            result: Full result dict from bisect.
        """
        report_dir = self._runner.repo_path / ".zerg" / "bisect-reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        # Validate report path is within repo
        resolved = report_dir.resolve()
        repo_resolved = self._runner.repo_path.resolve()
        if not resolved.is_relative_to(repo_resolved):
            logger.error("Report directory outside repository, skipping save")
            return

        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        try:
            branch = self._runner.current_branch()
        except Exception:
            branch = "unknown"

        # Sanitize branch name for filename
        safe_branch = re.sub(r"[^\w-]", "_", branch)
        report_path = report_dir / f"{timestamp}-{safe_branch}.md"

        # Build report content
        lines: list[str] = [
            f"# Bisect Report: {_sanitize_text(safe_branch)}",
            "",
            f"**Date**: {datetime.now(UTC).isoformat()}",
            f"**Symptom**: {_sanitize_text(symptom)}",
            f"**Test Command**: `{_sanitize_text(test_cmd)}`",
            f"**Method**: {result.get('method', 'unknown')}",
            "",
        ]

        culprit = result.get("culprit")
        if culprit and isinstance(culprit, CommitInfo):
            lines.extend(
                [
                    "## Culprit Commit",
                    "",
                    f"- **SHA**: `{culprit.sha}`",
                    f"- **Message**: {_sanitize_text(culprit.message)}",
                    f"- **Author**: {_sanitize_text(culprit.author)}",
                    f"- **Date**: {culprit.date}",
                    "",
                ]
            )

            if culprit.files:
                lines.append("### Changed Files")
                lines.append("")
                for f in culprit.files:
                    lines.append(f"- `{_sanitize_text(f)}`")
                lines.append("")

        analysis = result.get("analysis")
        if analysis:
            lines.extend(
                [
                    "## Root Cause Analysis",
                    "",
                    f"**Likely Cause**: {_sanitize_text(analysis.get('likely_cause', ''))}",
                    "",
                    f"**Suggestion**: {_sanitize_text(analysis.get('suggestion', ''))}",
                    "",
                ]
            )

        if result.get("method") == "failed":
            lines.extend(
                [
                    "## Result",
                    "",
                    "Bisect was unable to identify a culprit commit.",
                    "",
                ]
            )

        report_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Report saved to %s", report_path)
