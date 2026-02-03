"""AI-powered PR creation with full project context.

Assembles context from commits, issues, and project files, generates
structured PR bodies with conventional commit titles, and creates PRs
via the GitHub CLI with graceful degradation when gh is unavailable.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zerg.git.config import GitConfig, GitPRConfig
from zerg.git.types import CommitInfo, CommitType
from zerg.logging import get_logger

if TYPE_CHECKING:
    from zerg.git.base import GitRunner

logger = get_logger("git.pr_engine")

# Conventional commit prefix to GitHub label mapping
_TYPE_LABEL_MAP: dict[CommitType, str] = {
    CommitType.FEAT: "enhancement",
    CommitType.FIX: "bug",
    CommitType.DOCS: "documentation",
    CommitType.TEST: "testing",
    CommitType.CHORE: "maintenance",
    CommitType.PERF: "performance",
    CommitType.CI: "maintenance",
    CommitType.BUILD: "maintenance",
    CommitType.STYLE: "maintenance",
    CommitType.REFACTOR: "maintenance",
    CommitType.REVERT: "bug",
}

# Pattern to detect conventional commit type from message
_CONVENTIONAL_RE = re.compile(
    r"^(?P<type>feat|fix|docs|style|refactor|test|chore|perf|ci|build|revert)" r"(?:\([^)]*\))?:\s*(?P<summary>.+)",
    re.IGNORECASE,
)


def _sanitize_pr_content(text: str) -> str:
    """Sanitize text for inclusion in PR body to prevent injection.

    Strips backtick sequences that could break markdown fences and
    removes HTML tags that could be used for XSS in PR rendering.

    Args:
        text: Raw text to sanitize.

    Returns:
        Sanitized text safe for PR body inclusion.
    """
    # Remove potential HTML injection
    sanitized = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    sanitized = re.sub(r"<iframe[^>]*>.*?</iframe>", "", sanitized, flags=re.DOTALL | re.IGNORECASE)
    # Escape backtick runs of 3+ that could break code fences
    sanitized = re.sub(r"(`{3,})", r"\\\1", sanitized)
    return sanitized


def _parse_commit_type(message: str) -> CommitType | None:
    """Extract conventional commit type from a commit message.

    Args:
        message: Full commit message string.

    Returns:
        Detected CommitType or None if not conventional.
    """
    match = _CONVENTIONAL_RE.match(message.strip())
    if not match:
        return None
    type_str = match.group("type").lower()
    try:
        return CommitType(type_str)
    except ValueError:
        return None


@dataclass
class PRContext:
    """Assembled context for PR generation."""

    commits: list[CommitInfo] = field(default_factory=list)
    issues: list[dict[str, Any]] = field(default_factory=list)
    specs: list[str] = field(default_factory=list)
    tests: list[str] = field(default_factory=list)
    claude_md: str | None = None


class ContextAssembler:
    """Assembles PR context from multiple project sources.

    Gathers commits, linked issues, spec files, and project
    documentation based on the configured context depth.
    """

    def assemble(
        self,
        runner: GitRunner,
        config: GitPRConfig,
        base_branch: str,
    ) -> PRContext:
        """Assemble PR context from the repository.

        Args:
            runner: GitRunner for executing git commands.
            config: PR configuration controlling context depth.
            base_branch: Branch to diff against (e.g. "main").

        Returns:
            PRContext with gathered information.
        """
        ctx = PRContext()

        # Always get commits (minimum context)
        ctx.commits = self._get_commits(runner, base_branch)

        if config.context_depth in ("issues", "full"):
            ctx.issues = self._get_linked_issues(runner)

        if config.context_depth == "full":
            ctx.specs = self._get_specs(runner)
            ctx.claude_md = self._get_claude_md(runner)

        return ctx

    def _get_commits(self, runner: GitRunner, base_branch: str) -> list[CommitInfo]:
        """Get commits since base branch.

        Args:
            runner: GitRunner instance.
            base_branch: Branch to compare against.

        Returns:
            List of CommitInfo objects for each commit.
        """
        try:
            result = runner._run(
                "log",
                f"{base_branch}..HEAD",
                "--format=%H|||%s|||%an|||%ai",
                "--name-only",
                check=False,
            )
        except Exception:
            logger.warning("Failed to get commit log")
            return []

        if not result.stdout or result.returncode != 0:
            return []

        return self._parse_log_output(result.stdout)

    def _parse_log_output(self, output: str) -> list[CommitInfo]:
        """Parse git log output into CommitInfo objects.

        The format is: SHA|||subject|||author|||date followed by
        file names on subsequent lines until an empty line.

        Args:
            output: Raw git log output.

        Returns:
            List of parsed CommitInfo objects.
        """
        commits: list[CommitInfo] = []
        blocks = output.strip().split("\n\n")

        for block in blocks:
            if not block.strip():
                continue
            lines = block.strip().splitlines()
            if not lines:
                continue

            header = lines[0]
            parts = header.split("|||", 3)
            if len(parts) < 4:
                continue

            sha, message, author, date = parts
            files = tuple(line.strip() for line in lines[1:] if line.strip())
            commit_type = _parse_commit_type(message)

            commits.append(
                CommitInfo(
                    sha=sha.strip(),
                    message=_sanitize_pr_content(message.strip()),
                    author=author.strip(),
                    date=date.strip(),
                    files=files,
                    commit_type=commit_type,
                )
            )

        return commits

    def _get_linked_issues(self, runner: GitRunner) -> list[dict[str, Any]]:
        """Get open issues from GitHub CLI.

        Args:
            runner: GitRunner instance (used for repo_path context).

        Returns:
            List of issue dicts with number, title, state keys.
            Empty list if gh is not available.
        """
        try:
            result = subprocess.run(
                [
                    "gh",
                    "issue",
                    "list",
                    "--json",
                    "number,title,state",
                    "--limit",
                    "20",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
                cwd=str(runner.repo_path),
            )
            if result.returncode == 0 and result.stdout.strip():
                issues: list[dict[str, Any]] = json.loads(result.stdout)
                return issues
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            logger.debug("GitHub CLI not available or failed; skipping issues")
        except Exception:
            logger.debug("Unexpected error fetching issues; skipping")

        return []

    def _get_specs(self, runner: GitRunner) -> list[str]:
        """List spec files from .gsd/specs/ directory.

        Args:
            runner: GitRunner for repo_path access.

        Returns:
            List of spec file names, or empty list if directory missing.
        """
        specs_dir = (runner.repo_path / ".gsd" / "specs").resolve()
        if not specs_dir.is_relative_to(runner.repo_path):
            return []
        if not specs_dir.is_dir():
            return []

        return sorted(f.name for f in specs_dir.iterdir() if f.is_file())

    def _get_claude_md(self, runner: GitRunner) -> str | None:
        """Read CLAUDE.md from repository root if it exists.

        Args:
            runner: GitRunner for repo_path access.

        Returns:
            Contents of CLAUDE.md or None if not found.
        """
        claude_path = (runner.repo_path / "CLAUDE.md").resolve()
        if not claude_path.is_relative_to(runner.repo_path):
            return None
        if not claude_path.is_file():
            return None

        try:
            content = claude_path.read_text(encoding="utf-8")
            # Truncate to first 2000 chars to avoid bloating context
            return content[:2000] if len(content) > 2000 else content
        except OSError:
            return None


class PRGenerator:
    """Generates structured PR title, body, labels, and reviewers."""

    def generate(self, context: PRContext, config: GitPRConfig) -> dict[str, Any]:
        """Generate PR data from assembled context.

        Args:
            context: Assembled PRContext with commits, issues, etc.
            config: PR generation configuration.

        Returns:
            Dict with keys: title, body, labels, reviewers.
        """
        title = self._generate_title(context.commits)
        body = self._generate_body(context, config)
        labels = self._generate_labels(context.commits, config)
        reviewers = self._suggest_reviewers(context, config)

        return {
            "title": title,
            "body": body,
            "labels": labels,
            "reviewers": reviewers,
        }

    def _generate_title(self, commits: list[CommitInfo]) -> str:
        """Generate conventional-format PR title from commits.

        Uses the first commit's conventional prefix if available,
        otherwise synthesizes from commit types.

        Args:
            commits: List of commits in this PR.

        Returns:
            PR title string.
        """
        if not commits:
            return "chore: update"

        # If single commit, use its message directly
        if len(commits) == 1:
            msg = commits[0].message
            # Ensure it fits title length
            return msg[:72] if len(msg) > 72 else msg

        # Multiple commits: find dominant type
        type_counts: dict[CommitType, int] = {}
        for commit in commits:
            ct = commit.commit_type
            if ct:
                type_counts[ct] = type_counts.get(ct, 0) + 1

        if type_counts:
            dominant_type = max(type_counts, key=lambda t: type_counts[t])
        else:
            dominant_type = CommitType.CHORE

        # Build summary from first commit's content
        first_match = _CONVENTIONAL_RE.match(commits[0].message)
        if first_match:
            summary = first_match.group("summary")
        else:
            summary = commits[0].message

        title = f"{dominant_type.value}: {summary}"
        return title[:72] if len(title) > 72 else title

    def _generate_body(self, context: PRContext, config: GitPRConfig) -> str:
        """Generate structured markdown PR body.

        Sections: Summary, Changes, Test Plan, Linked Issues.

        Args:
            context: Assembled PR context.
            config: PR configuration.

        Returns:
            Markdown-formatted PR body.
        """
        sections: list[str] = []

        # Summary section
        sections.append("## Summary\n")
        for commit in context.commits[:10]:
            sanitized = _sanitize_pr_content(commit.message)
            sections.append(f"- {sanitized}")
        sections.append("")

        # Changes section with file table
        all_files = self._collect_changed_files(context.commits)
        if all_files:
            sections.append("## Changes\n")
            sections.append("| File | Status |")
            sections.append("|------|--------|")
            for filepath in sorted(all_files)[:30]:
                sanitized_path = _sanitize_pr_content(filepath)
                sections.append(f"| `{sanitized_path}` | modified |")
            if len(all_files) > 30:
                sections.append(f"| ... | +{len(all_files) - 30} more files |")
            sections.append("")

        # Size warning
        total_files = len(all_files)
        if total_files > config.size_warning_loc:
            sections.append(
                f"> **Warning**: This PR touches {total_files} files, "
                f"exceeding the threshold of {config.size_warning_loc}. "
                "Consider splitting into smaller PRs.\n"
            )

        # Test plan section
        sections.append("## Test Plan\n")
        test_files = [f for f in all_files if self._is_test_file(f)]
        if test_files:
            for tf in test_files[:10]:
                sections.append(f"- [ ] Verify `{_sanitize_pr_content(tf)}`")
        else:
            sections.append("- [ ] Add test coverage for changes")
        sections.append("")

        # Linked issues
        if context.issues:
            sections.append("## Linked Issues\n")
            for issue in context.issues[:5]:
                number = issue.get("number", "?")
                title = _sanitize_pr_content(str(issue.get("title", "Untitled")))
                sections.append(f"- #{number}: {title}")
            sections.append("")

        return "\n".join(sections)

    def _generate_labels(self, commits: list[CommitInfo], config: GitPRConfig) -> list[str]:
        """Generate auto-labels from commit types.

        Args:
            commits: List of commits.
            config: PR configuration.

        Returns:
            Deduplicated list of label strings.
        """
        if not config.auto_label:
            return []

        labels: set[str] = set()
        for commit in commits:
            if commit.commit_type and commit.commit_type in _TYPE_LABEL_MAP:
                labels.add(_TYPE_LABEL_MAP[commit.commit_type])

        return sorted(labels)

    def _suggest_reviewers(self, context: PRContext, config: GitPRConfig) -> list[str]:
        """Suggest reviewers from CODEOWNERS or commit history.

        Args:
            context: PR context (not currently using runner directly).
            config: PR configuration.

        Returns:
            List of reviewer usernames/handles.
        """
        if not config.reviewer_suggestion:
            return []

        # Collect unique authors from commits (excluding duplicates)
        authors: list[str] = []
        seen: set[str] = set()
        for commit in context.commits:
            author = commit.author.strip()
            if author and author not in seen:
                seen.add(author)
                authors.append(author)

        return authors[:3]

    @staticmethod
    def _collect_changed_files(commits: list[CommitInfo]) -> list[str]:
        """Collect unique changed files from all commits.

        Args:
            commits: List of CommitInfo with file lists.

        Returns:
            Deduplicated sorted list of file paths.
        """
        files: set[str] = set()
        for commit in commits:
            files.update(commit.files)
        return sorted(files)

    @staticmethod
    def _is_test_file(filepath: str) -> bool:
        """Check if a file path looks like a test file."""
        name = Path(filepath).name.lower()
        parts = Path(filepath).parts
        return (
            name.startswith("test_")
            or name.endswith("_test.py")
            or name.endswith(".test.js")
            or name.endswith(".test.ts")
            or any(p in ("test", "tests", "__tests__") for p in parts)
        )


class PRCreator:
    """Creates PRs via GitHub CLI with graceful degradation."""

    def create(
        self,
        runner: GitRunner,
        pr_data: dict[str, Any],
        draft: bool = False,
    ) -> dict[str, Any]:
        """Create a PR using gh CLI or save as draft file.

        Args:
            runner: GitRunner for repo_path context.
            pr_data: Dict with title, body, labels, reviewers keys.
            draft: Whether to create as draft PR.

        Returns:
            Dict with url and number on success, or path on fallback.
        """
        title = pr_data.get("title", "Update")
        body = pr_data.get("body", "")
        labels = pr_data.get("labels", [])
        reviewers = pr_data.get("reviewers", [])

        cmd: list[str] = [
            "gh",
            "pr",
            "create",
            "--title",
            title,
            "--body",
            body,
        ]

        if draft:
            cmd.append("--draft")

        for label in labels:
            cmd.extend(["--label", label])

        for reviewer in reviewers:
            cmd.extend(["--reviewer", reviewer])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
                cwd=str(runner.repo_path),
            )
            url = result.stdout.strip()
            # Extract PR number from URL (e.g., https://github.com/owner/repo/pull/42)
            number = self._extract_pr_number(url)
            logger.info("PR created: %s", url)
            return {"url": url, "number": number}

        except FileNotFoundError:
            logger.warning("GitHub CLI not found; saving PR draft to file")
            return self._save_draft(runner, pr_data)
        except subprocess.CalledProcessError as e:
            logger.warning("gh pr create failed: %s", e.stderr)
            return self._save_draft(runner, pr_data)
        except subprocess.TimeoutExpired:
            logger.warning("gh pr create timed out")
            return self._save_draft(runner, pr_data)

    def _save_draft(self, runner: GitRunner, pr_data: dict[str, Any]) -> dict[str, Any]:
        """Save PR body to a draft file for manual creation.

        Args:
            runner: GitRunner for repo_path access.
            pr_data: PR data dict with title and body.

        Returns:
            Dict with path key pointing to the saved file.
        """
        drafts_dir = (runner.repo_path / ".zerg" / "pr-drafts").resolve()
        if not drafts_dir.is_relative_to(runner.repo_path):
            logger.error("Draft directory path traversal detected")
            return {"error": "Invalid draft path"}

        drafts_dir.mkdir(parents=True, exist_ok=True)

        # Get branch name for filename
        try:
            branch_result = runner._run("rev-parse", "--abbrev-ref", "HEAD", check=False)
            branch = branch_result.stdout.strip() if branch_result.stdout else "unknown"
        except Exception:
            branch = "unknown"

        # Sanitize branch name for filename
        safe_branch = re.sub(r"[^\w\-.]", "_", branch)
        draft_path = drafts_dir / f"{safe_branch}.md"

        content = f"# {pr_data.get('title', 'PR Draft')}\n\n{pr_data.get('body', '')}"
        draft_path.write_text(content, encoding="utf-8")

        logger.info("PR draft saved to %s", draft_path)
        return {"path": str(draft_path), "branch": branch}

    @staticmethod
    def _extract_pr_number(url: str) -> int | None:
        """Extract PR number from a GitHub PR URL.

        Args:
            url: GitHub PR URL string.

        Returns:
            PR number as int, or None if parsing fails.
        """
        match = re.search(r"/pull/(\d+)", url)
        return int(match.group(1)) if match else None


class PREngine:
    """Main entry point orchestrating the full PR creation workflow.

    Coordinates ContextAssembler, PRGenerator, and PRCreator to
    assemble context, generate PR content, and create the PR.
    """

    def __init__(self, runner: GitRunner, config: GitConfig) -> None:
        """Initialize PR engine.

        Args:
            runner: GitRunner instance for the repository.
            config: Full git configuration.
        """
        self.runner = runner
        self.config = config
        self._assembler = ContextAssembler()
        self._generator = PRGenerator()
        self._creator = PRCreator()

    def run(
        self,
        base_branch: str = "main",
        draft: bool = False,
        reviewer: str | None = None,
    ) -> int:
        """Orchestrate the full PR creation workflow.

        Steps:
        1. Assemble context from commits, issues, and project files.
        2. Generate structured PR title, body, labels, and reviewers.
        3. Create PR via gh CLI or save as draft.

        Args:
            base_branch: Branch to compare against.
            draft: Whether to create as draft PR.
            reviewer: Optional explicit reviewer to add.

        Returns:
            0 on success, 1 on failure.
        """
        pr_config = self.config.pr

        # Step 1: Assemble context
        logger.info("Assembling PR context against %s", base_branch)
        context = self._assembler.assemble(self.runner, pr_config, base_branch)

        if not context.commits:
            logger.warning("No commits found between %s and HEAD", base_branch)
            return 1

        # Step 2: Generate PR content
        logger.info("Generating PR content from %d commits", len(context.commits))
        pr_data = self._generator.generate(context, pr_config)

        # Add explicit reviewer if provided
        if reviewer:
            reviewers = pr_data.get("reviewers", [])
            if reviewer not in reviewers:
                reviewers.append(reviewer)
            pr_data["reviewers"] = reviewers

        # Step 3: Create PR
        logger.info("Creating PR: %s", pr_data["title"])
        result = self._creator.create(self.runner, pr_data, draft=draft)

        if "error" in result:
            logger.error("PR creation failed: %s", result["error"])
            return 1

        if "url" in result:
            logger.info("PR created successfully: %s", result["url"])
        elif "path" in result:
            logger.info("PR draft saved to: %s", result["path"])

        self._last_result = result
        return 0

    @property
    def result(self) -> dict[str, Any] | None:
        """Last PR creation result."""
        return getattr(self, "_last_result", None)
