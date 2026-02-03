"""Commit history intelligence -- squash, reorder, rewrite.

Provides analysis of commit history for cleanup opportunities,
planning of rewrites without execution, and safe non-destructive
execution of history rewrites on cleaned branches.
"""

from __future__ import annotations

import os
import re
import tempfile
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from zerg.exceptions import GitError
from zerg.git.commit_engine import COMMIT_TYPE_PATTERNS
from zerg.git.config import GitConfig
from zerg.git.types import CommitInfo, CommitType
from zerg.logging import get_logger

if TYPE_CHECKING:
    from zerg.git.base import GitRunner

logger = get_logger("git.history_engine")

# Valid branch name pattern -- no shell injection, no weird chars
_BRANCH_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._/-]*$")

# Conventional commit prefix pattern
_CONVENTIONAL_RE = re.compile(r"^(feat|fix|docs|style|refactor|test|chore|perf|ci|build|revert)" r"(\(.+\))?:\s+.+")

# Small commit threshold (lines changed)
_SMALL_COMMIT_LINES = 5

# Time window for grouping small commits (seconds)
_SMALL_COMMIT_WINDOW = timedelta(hours=1)


def _validate_branch_name(name: str) -> None:
    """Validate a branch name against safe pattern.

    Args:
        name: Branch name to validate.

    Raises:
        ValueError: If the branch name is invalid.
    """
    if not name or not _BRANCH_NAME_RE.match(name):
        raise ValueError(f"Invalid branch name: {name!r}. Must match ^[a-zA-Z0-9][a-zA-Z0-9._/-]*$")


def _parse_date(date_str: str) -> datetime:
    """Parse a git date string into a datetime.

    Handles ISO 8601 format from git log %ai (e.g. 2025-01-15 10:30:00 +0000).

    Args:
        date_str: Date string from git log.

    Returns:
        Parsed datetime (naive, for comparison purposes).
    """
    # Strip timezone offset for simpler comparison
    clean = date_str.strip()
    # Try ISO-like format from git: "2025-01-15 10:30:00 +0000"
    for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(clean, fmt).replace(tzinfo=None)
        except ValueError:
            continue
    # Fallback: return epoch so comparison doesn't crash
    logger.warning("Could not parse date: %s", date_str)
    return datetime(2000, 1, 1)


def _detect_type_from_message(message: str) -> CommitType | None:
    """Detect commit type from a commit message using pattern matching.

    Args:
        message: Commit message string.

    Returns:
        Detected CommitType or None if no match.
    """
    lower = message.lower()
    for commit_type, patterns in COMMIT_TYPE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, lower, re.IGNORECASE):
                return commit_type
    return None


def _get_lines_changed(runner: GitRunner, sha: str) -> int:
    """Get the total lines changed for a commit.

    Args:
        runner: GitRunner instance.
        sha: Commit SHA.

    Returns:
        Total lines added + deleted.
    """
    try:
        result = runner._run("show", "--format=", "--numstat", sha, check=False)
        total = 0
        for line in (result.stdout or "").strip().splitlines():
            parts = line.split("\t", 2)
            if len(parts) >= 2:
                ins = int(parts[0]) if parts[0] != "-" else 0
                dels = int(parts[1]) if parts[1] != "-" else 0
                total += ins + dels
        return total
    except Exception:
        return 0


class HistoryAnalyzer:
    """Analyzes commit history for cleanup opportunities."""

    def __init__(self, runner: GitRunner) -> None:
        self.runner = runner

    def get_commits(self, base_branch: str = "main") -> list[CommitInfo]:
        """Get commits between base branch and HEAD.

        Uses git log with a custom format and --name-only to capture
        both metadata and file lists per commit.

        Args:
            base_branch: Base branch to compare against.

        Returns:
            List of CommitInfo objects, oldest first.
        """
        _validate_branch_name(base_branch)

        result = self.runner._run(
            "log",
            f"{base_branch}..HEAD",
            "--format=%H|||%s|||%an|||%ai",
            "--name-only",
            check=False,
        )

        output = (result.stdout or "").strip()
        if not output:
            return []

        return self._parse_log_output(output)

    def _parse_log_output(self, output: str) -> list[CommitInfo]:
        """Parse the combined log + name-only output.

        The format alternates between commit metadata lines
        (containing |||) and file name lines.

        Args:
            output: Raw git log output.

        Returns:
            List of CommitInfo, oldest first.
        """
        commits: list[CommitInfo] = []
        current_sha = ""
        current_message = ""
        current_author = ""
        current_date = ""
        current_files: list[str] = []

        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue

            if "|||" in line:
                # Save previous commit if exists
                if current_sha:
                    commits.append(
                        CommitInfo(
                            sha=current_sha,
                            message=current_message,
                            author=current_author,
                            date=current_date,
                            files=tuple(current_files),
                            commit_type=_detect_type_from_message(current_message),
                        )
                    )

                # Parse new commit line
                parts = line.split("|||", 3)
                if len(parts) == 4:
                    current_sha = parts[0].strip()
                    current_message = parts[1].strip()
                    current_author = parts[2].strip()
                    current_date = parts[3].strip()
                    current_files = []
                else:
                    current_sha = ""
            else:
                # File name line
                if current_sha and line:
                    current_files.append(line)

        # Don't forget the last commit
        if current_sha:
            commits.append(
                CommitInfo(
                    sha=current_sha,
                    message=current_message,
                    author=current_author,
                    date=current_date,
                    files=tuple(current_files),
                    commit_type=_detect_type_from_message(current_message),
                )
            )

        # Reverse so oldest is first (git log outputs newest first)
        commits.reverse()
        return commits

    def find_squash_candidates(self, commits: list[CommitInfo]) -> list[list[CommitInfo]]:
        """Find groups of commits that should be squashed together.

        Groups by:
        - WIP commits (message starts with "wip" case-insensitive)
        - fixup! commits (message starts with "fixup!")
        - squash! commits (message starts with "squash!")
        - Related commits: same files changed within sequence
        - Small commits: fewer than 5 lines changed AND within 1 hour

        Args:
            commits: List of CommitInfo objects (oldest first).

        Returns:
            List of groups, where each group is a list of commits to squash.
        """
        if not commits:
            return []

        groups: list[list[CommitInfo]] = []
        used: set[str] = set()

        # Pass 1: WIP commits
        wip_group: list[CommitInfo] = []
        for c in commits:
            if re.match(r"^wip\b", c.message, re.IGNORECASE):
                wip_group.append(c)
                used.add(c.sha)
        if len(wip_group) >= 2:
            groups.append(wip_group)
        elif wip_group:
            # Single WIP still worth flagging for squash with neighbors
            used.discard(wip_group[0].sha)

        # Pass 2: fixup! and squash! commits paired with their targets
        for c in commits:
            if c.sha in used:
                continue
            for prefix in ("fixup!", "squash!"):
                if c.message.startswith(prefix):
                    target_msg = c.message[len(prefix) :].strip()
                    group = [c]
                    for other in commits:
                        if other.sha != c.sha and other.sha not in used:
                            if other.message.strip() == target_msg:
                                group.insert(0, other)  # target first
                                used.add(other.sha)
                    if len(group) >= 2:
                        used.add(c.sha)
                        groups.append(group)
                    elif len(group) == 1:
                        # fixup/squash without matching target -- still a candidate
                        used.add(c.sha)
                        groups.append(group)
                    break

        # Pass 3: Related commits (same files changed in sequence)
        remaining = [c for c in commits if c.sha not in used]
        i = 0
        while i < len(remaining):
            c = remaining[i]
            if not c.files:
                i += 1
                continue

            group = [c]
            files_set = set(c.files)

            j = i + 1
            while j < len(remaining):
                other = remaining[j]
                if other.files and files_set & set(other.files):
                    group.append(other)
                    files_set.update(other.files)
                    j += 1
                else:
                    break

            if len(group) >= 2:
                for g in group:
                    used.add(g.sha)
                groups.append(group)
                i = j
            else:
                i += 1

        # Pass 4: Small commits within time window
        remaining = [c for c in commits if c.sha not in used]
        i = 0
        while i < len(remaining):
            c = remaining[i]
            c_date = _parse_date(c.date)

            group = [c]
            j = i + 1
            while j < len(remaining):
                other = remaining[j]
                o_date = _parse_date(other.date)
                if abs((o_date - c_date).total_seconds()) <= _SMALL_COMMIT_WINDOW.total_seconds():
                    group.append(other)
                    j += 1
                else:
                    break

            if len(group) >= 2:
                for g in group:
                    used.add(g.sha)
                groups.append(group)
                i = j
            else:
                i += 1

        return groups

    def find_reorder_groups(self, commits: list[CommitInfo]) -> dict[str, list[CommitInfo]]:
        """Group commits by primary directory, then by type.

        Args:
            commits: List of CommitInfo objects.

        Returns:
            Dict of group_name to list of commits.
        """
        groups: dict[str, list[CommitInfo]] = {}

        for c in commits:
            # Determine primary directory
            if c.files:
                # Use the most common top-level directory
                dirs: dict[str, int] = {}
                for f in c.files:
                    parts = f.split("/", 1)
                    d = parts[0] if len(parts) > 1 else "."
                    dirs[d] = dirs.get(d, 0) + 1
                primary_dir = max(dirs, key=dirs.get)  # type: ignore[arg-type]
            else:
                primary_dir = "."

            # Determine type label
            type_label = c.commit_type.value if c.commit_type else "other"
            group_name = f"{primary_dir}/{type_label}"

            groups.setdefault(group_name, []).append(c)

        return groups


class RewritePlanner:
    """Creates a rewrite plan without executing."""

    def plan_squash(self, groups: list[list[CommitInfo]]) -> list[dict]:
        """Plan squash operations for commit groups.

        Args:
            groups: List of commit groups from find_squash_candidates.

        Returns:
            List of squash plan dicts with action, commits, message.
        """
        plans: list[dict] = []

        for group in groups:
            if not group:
                continue

            shas = [c.sha for c in group]
            message = self._generate_squash_message(group)
            plans.append(
                {
                    "action": "squash",
                    "commits": shas,
                    "message": message,
                }
            )

        return plans

    def plan_reorder(self, groups: dict[str, list[CommitInfo]]) -> list[str]:
        """Plan commit reordering based on groups.

        Args:
            groups: Dict of group_name to commits from find_reorder_groups.

        Returns:
            Ordered list of commit SHAs in the new order.
        """
        ordered: list[str] = []

        # Sort groups by name for deterministic output
        for group_name in sorted(groups.keys()):
            for commit in groups[group_name]:
                if commit.sha not in ordered:
                    ordered.append(commit.sha)

        return ordered

    def plan_rewrite_messages(self, commits: list[CommitInfo]) -> list[dict]:
        """Plan message rewrites for non-conventional commits.

        Args:
            commits: List of CommitInfo objects.

        Returns:
            List of rewrite plan dicts with sha, old, new.
        """
        rewrites: list[dict] = []

        for c in commits:
            if _CONVENTIONAL_RE.match(c.message):
                continue

            # Generate a conventional message
            detected_type = _detect_type_from_message(c.message) or CommitType.CHORE
            # Clean up the original message for the description
            clean_msg = c.message.strip()
            # Remove common prefixes
            for prefix in ("wip ", "wip: ", "WIP ", "WIP: "):
                if clean_msg.startswith(prefix):
                    clean_msg = clean_msg[len(prefix) :]
                    break

            new_msg = f"{detected_type.value}: {clean_msg}" if clean_msg else f"{detected_type.value}: update"
            rewrites.append(
                {
                    "sha": c.sha,
                    "old": c.message,
                    "new": new_msg,
                }
            )

        return rewrites

    def _generate_squash_message(self, group: list[CommitInfo]) -> str:
        """Generate a conventional commit message for a squash group.

        Uses the dominant commit type from the group.

        Args:
            group: List of commits to squash.

        Returns:
            Generated conventional commit message.
        """
        # Count commit types
        type_counts: dict[CommitType, int] = {}
        for c in group:
            ct = c.commit_type or CommitType.CHORE
            type_counts[ct] = type_counts.get(ct, 0) + 1

        primary_type = max(type_counts, key=type_counts.get)  # type: ignore[arg-type]

        # Collect all unique files
        all_files: set[str] = set()
        for c in group:
            all_files.update(c.files)

        # Build description
        if len(all_files) == 1:
            desc = f"update {next(iter(all_files)).rsplit('/', 1)[-1].rsplit('.', 1)[0]}"
        elif len(all_files) <= 3:
            stems = [f.rsplit("/", 1)[-1].rsplit(".", 1)[0] for f in sorted(all_files)]
            desc = f"update {', '.join(stems)}"
        else:
            desc = f"update {len(all_files)} files"

        return f"{primary_type.value}: {desc}"


class SafeRewriter:
    """Executes rewrites non-destructively on cleaned branches."""

    def __init__(self, runner: GitRunner) -> None:
        self.runner = runner

    def create_cleaned_branch(self, branch_name: str) -> str:
        """Create a cleaned branch from the current branch.

        Args:
            branch_name: Base name for the new branch.

        Returns:
            Name of the created branch.

        Raises:
            ValueError: If branch name is invalid.
        """
        _validate_branch_name(branch_name)
        new_name = f"{branch_name}-cleaned"
        _validate_branch_name(new_name)

        self.runner._run("checkout", "-b", new_name)
        logger.info("Created cleaned branch: %s", new_name)
        return new_name

    def execute_squash(self, plan: list[dict], base: str = "main") -> bool:
        """Execute squash operations using GIT_SEQUENCE_EDITOR.

        Writes a script that modifies the rebase todo list, then runs
        git rebase -i with GIT_SEQUENCE_EDITOR pointing to that script.

        Args:
            plan: List of squash plan dicts from RewritePlanner.plan_squash.
            base: Base branch/ref for the rebase.

        Returns:
            True if all squashes succeeded, False otherwise.
        """
        _validate_branch_name(base)

        if not plan:
            return True

        # Build the sed-like replacement script
        # Collect all commits that should be squashed (not the first in each group)
        squash_shas: set[str] = set()
        for entry in plan:
            commits = entry.get("commits", [])
            # First commit in group gets "pick", rest get "squash"
            for sha in commits[1:]:
                squash_shas.add(sha[:7])  # Short SHA for rebase todo

        if not squash_shas:
            return True

        # Create a script that replaces "pick <sha>" with "squash <sha>"
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                delete=False,
                prefix="zerg_rebase_",
            ) as script_file:
                script_path = script_file.name
                # Write a Python script that modifies the todo file
                script_file.write("#!/usr/bin/env python3\n")
                script_file.write("import sys\n")
                script_file.write("todo_file = sys.argv[1]\n")
                script_file.write("with open(todo_file, 'r') as f:\n")
                script_file.write("    lines = f.readlines()\n")
                script_file.write("new_lines = []\n")
                script_file.write(f"squash_shas = {squash_shas!r}\n")
                script_file.write("for line in lines:\n")
                script_file.write("    parts = line.split()\n")
                script_file.write("    if len(parts) >= 2 and parts[0] == 'pick' and parts[1] in squash_shas:\n")
                script_file.write("        new_lines.append('squash ' + ' '.join(parts[1:]) + '\\n')\n")
                script_file.write("    else:\n")
                script_file.write("        new_lines.append(line)\n")
                script_file.write("with open(todo_file, 'w') as f:\n")
                script_file.write("    f.writelines(new_lines)\n")

            os.chmod(script_path, 0o755)

            # Set GIT_SEQUENCE_EDITOR and run rebase
            env = os.environ.copy()
            env["GIT_SEQUENCE_EDITOR"] = f"python3 {script_path}"

            import subprocess

            cmd = [
                "git",
                "-C",
                str(self.runner.repo_path),
                "rebase",
                "-i",
                base,
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )

            if result.returncode != 0:
                logger.error("Squash rebase failed: %s", result.stderr)
                # Abort the rebase on failure
                self.runner._run("rebase", "--abort", check=False)
                return False

            logger.info("Squash rebase completed successfully")
            return True

        except Exception as exc:
            logger.error("Squash execution failed: %s", exc)
            self.runner._run("rebase", "--abort", check=False)
            return False
        finally:
            # Clean up the temp script
            try:
                os.unlink(script_path)
            except (OSError, UnboundLocalError):
                pass

    def execute_reorder(self, ordered_shas: list[str], base: str = "main") -> bool:
        """Execute commit reordering using GIT_SEQUENCE_EDITOR.

        Args:
            ordered_shas: Ordered list of commit SHAs.
            base: Base branch/ref for the rebase.

        Returns:
            True if reorder succeeded, False otherwise.
        """
        _validate_branch_name(base)

        if not ordered_shas:
            return True

        # Build short SHA lookup for the todo list
        short_shas = [sha[:7] for sha in ordered_shas]

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                delete=False,
                prefix="zerg_reorder_",
            ) as script_file:
                script_path = script_file.name
                script_file.write("#!/usr/bin/env python3\n")
                script_file.write("import sys\n")
                script_file.write("todo_file = sys.argv[1]\n")
                script_file.write("with open(todo_file, 'r') as f:\n")
                script_file.write("    lines = f.readlines()\n")
                script_file.write(f"order = {short_shas!r}\n")
                script_file.write("pick_lines = {}\n")
                script_file.write("other_lines = []\n")
                script_file.write("for line in lines:\n")
                script_file.write("    parts = line.split()\n")
                script_file.write("    if len(parts) >= 2 and parts[0] == 'pick' and parts[1] in order:\n")
                script_file.write("        pick_lines[parts[1]] = line\n")
                script_file.write("    else:\n")
                script_file.write("        other_lines.append(line)\n")
                script_file.write("new_lines = []\n")
                script_file.write("for sha in order:\n")
                script_file.write("    if sha in pick_lines:\n")
                script_file.write("        new_lines.append(pick_lines[sha])\n")
                script_file.write("new_lines.extend(other_lines)\n")
                script_file.write("with open(todo_file, 'w') as f:\n")
                script_file.write("    f.writelines(new_lines)\n")

            os.chmod(script_path, 0o755)

            env = os.environ.copy()
            env["GIT_SEQUENCE_EDITOR"] = f"python3 {script_path}"

            import subprocess

            cmd = [
                "git",
                "-C",
                str(self.runner.repo_path),
                "rebase",
                "-i",
                base,
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )

            if result.returncode != 0:
                logger.error("Reorder rebase failed: %s", result.stderr)
                self.runner._run("rebase", "--abort", check=False)
                return False

            logger.info("Reorder rebase completed successfully")
            return True

        except Exception as exc:
            logger.error("Reorder execution failed: %s", exc)
            self.runner._run("rebase", "--abort", check=False)
            return False
        finally:
            try:
                os.unlink(script_path)
            except (OSError, UnboundLocalError):
                pass

    def preview(self, plan: list[dict] | dict) -> str:
        """Return a human-readable preview of what would change.

        Args:
            plan: Squash plan (list of dicts) or rewrite plan.

        Returns:
            Formatted preview string.
        """
        lines: list[str] = ["History Rewrite Preview", "=" * 40]

        if isinstance(plan, list):
            for i, entry in enumerate(plan, 1):
                action = entry.get("action", "unknown")
                if action == "squash":
                    commits = entry.get("commits", [])
                    message = entry.get("message", "")
                    lines.append(f"\n{i}. SQUASH {len(commits)} commits:")
                    for sha in commits:
                        lines.append(f"   - {sha[:8]}")
                    lines.append(f"   New message: {message}")
                elif "old" in entry and "new" in entry:
                    sha = entry.get("sha", "unknown")
                    lines.append(f"\n{i}. REWRITE {sha[:8]}:")
                    lines.append(f"   Old: {entry['old']}")
                    lines.append(f"   New: {entry['new']}")
        elif isinstance(plan, dict):
            lines.append("\nReorder plan:")
            for group_name, commits in plan.items():
                lines.append(f"\n  {group_name}:")
                for c in commits:
                    sha = c.sha if hasattr(c, "sha") else str(c)
                    lines.append(f"    - {sha[:8]}")

        return "\n".join(lines)


class HistoryEngine:
    """Main entry point for history intelligence operations."""

    def __init__(self, runner: GitRunner, config: GitConfig) -> None:
        self.runner = runner
        self.config = config
        self._analyzer = HistoryAnalyzer(runner)
        self._planner = RewritePlanner()
        self._rewriter = SafeRewriter(runner)

    def run(self, action: str = "cleanup", base_branch: str = "main") -> int:
        """Run history intelligence operation.

        Args:
            action: Operation mode -- "cleanup" or "preview".
            base_branch: Base branch for comparison.

        Returns:
            0 for success, 1 for failure.
        """
        try:
            _validate_branch_name(base_branch)
            # Analyze
            commits = self._analyzer.get_commits(base_branch)
            if not commits:
                logger.info("No commits found between %s and HEAD", base_branch)
                return 0

            # Plan
            squash_groups = self._analyzer.find_squash_candidates(commits)
            squash_plan = self._planner.plan_squash(squash_groups)
            rewrite_plan = self._planner.plan_rewrite_messages(commits)

            if action == "preview":
                if squash_plan:
                    preview = self._rewriter.preview(squash_plan)
                    logger.info("\n%s", preview)
                if rewrite_plan:
                    preview = self._rewriter.preview(rewrite_plan)
                    logger.info("\n%s", preview)
                if not squash_plan and not rewrite_plan:
                    logger.info("History is already clean -- no changes needed")
                return 0

            elif action == "cleanup":
                if not squash_plan and not rewrite_plan:
                    logger.info("History is already clean -- no changes needed")
                    return 0

                # Preview first
                if squash_plan:
                    preview = self._rewriter.preview(squash_plan)
                    logger.info("\n%s", preview)

                # Create cleaned branch
                current = self.runner.current_branch()
                new_branch = self._rewriter.create_cleaned_branch(current)

                # Execute squash if needed
                if squash_plan:
                    success = self._rewriter.execute_squash(squash_plan, base_branch)
                    if not success:
                        logger.error("Squash failed on branch %s", new_branch)
                        return 1

                logger.info("History cleanup complete on branch %s", new_branch)
                return 0

            else:
                logger.error("Unknown action: %s", action)
                return 1

        except GitError as exc:
            logger.error("History operation failed: %s", exc)
            return 1
        except ValueError as exc:
            logger.error("Validation error: %s", exc)
            return 1
