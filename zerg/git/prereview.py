"""Pre-review context assembly for Claude Code AI analysis.

Prepares scoped context from git diffs and security rules so that
Claude Code can perform focused code review without loading entire files.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from zerg.git.config import GitConfig
from zerg.logging import get_logger

if TYPE_CHECKING:
    from zerg.git.base import GitRunner

logger = get_logger("git.prereview")

# Extension-to-domain mapping for security rule filtering
_EXTENSION_DOMAINS: dict[str, list[str]] = {
    ".py": ["python"],
    ".js": ["javascript"],
    ".jsx": ["javascript"],
    ".ts": ["javascript"],
    ".tsx": ["javascript"],
    ".mjs": ["javascript"],
    ".cjs": ["javascript"],
    ".dockerfile": ["docker"],
    ".yaml": ["docker"],
    ".yml": ["docker"],
}

# Filenames (case-insensitive) that map to docker domain
_FILENAME_DOMAINS: dict[str, list[str]] = {
    "dockerfile": ["docker"],
    "docker-compose.yml": ["docker"],
    "docker-compose.yaml": ["docker"],
}

# Subdirectory name within rules_dir that maps to each domain
_DOMAIN_RULE_PATHS: dict[str, list[str]] = {
    "python": ["languages/python"],
    "javascript": ["languages/javascript"],
    "docker": ["containers/docker"],
    "owasp": ["_core"],
}


class ContextPreparer:
    """Prepares code context from changed files for AI review."""

    def __init__(self, runner: GitRunner) -> None:
        self._runner = runner

    def get_changed_files(self, base_branch: str = "main") -> list[str]:
        """Get list of files changed between base branch and HEAD.

        Args:
            base_branch: Branch to diff against.

        Returns:
            List of changed file paths relative to repo root.
        """
        result = self._runner._run("diff", "--name-only", f"{base_branch}..HEAD")
        output = result.stdout.strip()
        if not output:
            return []
        return [line.strip() for line in output.splitlines() if line.strip()]

    def get_file_hunks(
        self,
        filepath: str,
        base_branch: str = "main",
        budget_chars: int = 2000,
    ) -> str:
        """Get diff hunks for a single file, truncated to budget.

        Args:
            filepath: Path to the file (relative to repo root).
            base_branch: Branch to diff against.
            budget_chars: Maximum characters to return.

        Returns:
            Diff hunk text, truncated if necessary.
        """
        result = self._runner._run("diff", f"{base_branch}..HEAD", "--", filepath)
        hunks = result.stdout
        if len(hunks) <= budget_chars:
            return hunks
        return hunks[:budget_chars] + "\n... [truncated]"

    def prepare_context(
        self,
        base_branch: str = "main",
        budget_chars: int = 16000,
    ) -> dict:
        """Prepare full review context with budget-aware hunk distribution.

        Allocates 50% of budget to code hunks (split evenly across files),
        leaving the remaining 50% for rules context assembled elsewhere.

        Args:
            base_branch: Branch to diff against.
            budget_chars: Total character budget for the context.

        Returns:
            Dict with keys: files, total_files, truncated.
        """
        changed = self.get_changed_files(base_branch)
        if not changed:
            return {"files": [], "total_files": 0, "truncated": False}

        hunk_budget = int(budget_chars * 0.5)
        per_file_budget = max(200, hunk_budget // len(changed))
        truncated = False

        files = []
        for fpath in changed:
            hunks = self.get_file_hunks(fpath, base_branch, per_file_budget)
            if hunks.endswith("... [truncated]"):
                truncated = True
            ext = Path(fpath).suffix
            files.append(
                {
                    "path": fpath,
                    "hunks": hunks,
                    "extension": ext,
                }
            )

        return {
            "files": files,
            "total_files": len(files),
            "truncated": truncated,
        }


class DomainFilter:
    """Filters security/quality rules by file extension."""

    def __init__(self, rules_dir: Path | None = None) -> None:
        """Initialize with optional rules directory.

        Args:
            rules_dir: Path to security rules. Defaults to
                .claude/rules/security/ in the current working directory.
        """
        if rules_dir is not None:
            self._rules_dir = Path(rules_dir).resolve()
        else:
            self._rules_dir = Path.cwd() / ".claude" / "rules" / "security"

    def get_domains_for_extension(self, ext: str) -> list[str]:
        """Get applicable rule domains for a file extension.

        Always includes 'owasp' as the core ruleset.

        Args:
            ext: File extension including dot (e.g. '.py').

        Returns:
            List of domain names.
        """
        domains = list(_EXTENSION_DOMAINS.get(ext.lower(), []))
        if "owasp" not in domains:
            domains.append("owasp")
        return domains

    def get_domains_for_filename(self, filename: str) -> list[str]:
        """Get applicable rule domains for a specific filename.

        Args:
            filename: The filename (no directory part).

        Returns:
            List of domain names.
        """
        domains = list(_FILENAME_DOMAINS.get(filename.lower(), []))
        if "owasp" not in domains:
            domains.append("owasp")
        return domains

    def get_rules_summary(
        self,
        domains: list[str],
        budget_chars: int = 4000,
    ) -> str:
        """Extract Quick Reference tables from rule files for given domains.

        Reads rule markdown files, extracts sections starting with
        '## Quick Reference', and concatenates them within the budget.

        Args:
            domains: List of domain names to include.
            budget_chars: Maximum characters for the summary.

        Returns:
            Formatted rules summary string.
        """
        resolved_rules_dir = self._rules_dir.resolve()
        summaries: list[str] = []
        chars_used = 0

        for domain in domains:
            paths = _DOMAIN_RULE_PATHS.get(domain, [])
            for rel_path in paths:
                domain_dir = (resolved_rules_dir / rel_path).resolve()
                # Security: ensure path is within rules_dir
                if not domain_dir.is_relative_to(resolved_rules_dir):
                    logger.warning(f"Skipping path outside rules dir: {domain_dir}")
                    continue
                if not domain_dir.is_dir():
                    continue

                for md_file in sorted(domain_dir.glob("*.md")):
                    md_resolved = md_file.resolve()
                    if not md_resolved.is_relative_to(resolved_rules_dir):
                        continue
                    content = md_resolved.read_text(encoding="utf-8")
                    ref_table = self._extract_quick_reference(content)
                    if ref_table:
                        header = f"### {domain.upper()} Rules\n"
                        section = header + ref_table + "\n"
                        if chars_used + len(section) > budget_chars:
                            remaining = budget_chars - chars_used
                            if remaining > 50:
                                summaries.append(section[:remaining] + "\n... [truncated]")
                            break
                        summaries.append(section)
                        chars_used += len(section)

        return "\n".join(summaries)

    def filter_for_files(self, file_paths: list[str]) -> dict:
        """Determine all applicable domains and rules for a set of files.

        Args:
            file_paths: List of file paths to analyze.

        Returns:
            Dict with keys: domains, rules_summary, per_file_domains.
        """
        all_domains: set[str] = set()
        per_file: dict[str, list[str]] = {}

        for fpath in file_paths:
            p = Path(fpath)
            ext = p.suffix
            filename = p.name

            # Check filename-based domains first, then extension
            if filename.lower() in _FILENAME_DOMAINS:
                domains = self.get_domains_for_filename(filename)
            else:
                domains = self.get_domains_for_extension(ext)

            per_file[fpath] = domains
            all_domains.update(domains)

        summary = self.get_rules_summary(sorted(all_domains))

        return {
            "domains": all_domains,
            "rules_summary": summary,
            "per_file_domains": per_file,
        }

    @staticmethod
    def _extract_quick_reference(content: str) -> str:
        """Extract the Quick Reference section from markdown content.

        Args:
            content: Full markdown content.

        Returns:
            Quick Reference table text, or empty string if not found.
        """
        pattern = r"## Quick Reference\s*\n(.*?)(?=\n## |\n---|\Z)"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(0).strip()
        return ""


class ReviewReporter:
    """Saves review context as structured markdown reports."""

    def __init__(self, project_root: Path) -> None:
        self._project_root = Path(project_root).resolve()

    def generate_report(
        self,
        context: dict,
        rules: dict,
        branch: str,
    ) -> str:
        """Generate a structured markdown report for AI review.

        Args:
            context: Output from ContextPreparer.prepare_context().
            rules: Output from DomainFilter.filter_for_files().
            branch: Branch name being reviewed.

        Returns:
            Markdown-formatted report string.
        """
        timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        per_file = rules.get("per_file_domains", {})
        files = context.get("files", [])
        total = context.get("total_files", 0)

        lines = [
            f"# Pre-Review Context: {branch}",
            f"Generated: {timestamp}",
            "",
            f"## Changed Files ({total})",
            "| File | Extension | Domains |",
            "|------|-----------|---------|",
        ]

        for f in files:
            fpath = f["path"]
            ext = f["extension"]
            domains = ", ".join(per_file.get(fpath, []))
            # Sanitize path for markdown table (no pipes)
            safe_path = fpath.replace("|", "\\|")
            lines.append(f"| {safe_path} | {ext} | {domains} |")

        lines.append("")
        lines.append("## Security Rules Summary")
        lines.append(rules.get("rules_summary", "No rules loaded."))
        lines.append("")
        lines.append("## Code Changes")

        for f in files:
            safe_path = f["path"].replace("|", "\\|")
            lines.append(f"### {safe_path}")
            lines.append("```diff")
            lines.append(f["hunks"])
            lines.append("```")
            lines.append("")

        lines.append("## Review Instructions")
        lines.append(
            "Analyze the above changes against the security rules. "
            "Report findings with severity, file, line, and suggestion."
        )

        return "\n".join(lines)

    def save_report(self, report: str, branch: str) -> Path:
        """Save report to the review-reports directory.

        Args:
            report: Markdown report content.
            branch: Branch name (used in filename).

        Returns:
            Path to the saved report file.

        Raises:
            ValueError: If the resolved path is outside project root.
        """
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        # Sanitize branch name for filesystem safety
        safe_branch = re.sub(r"[^\w\-]", "_", branch)
        report_dir = (self._project_root / ".zerg" / "review-reports").resolve()

        # Security: ensure report dir is within project root
        if not report_dir.is_relative_to(self._project_root):
            raise ValueError(f"Report directory {report_dir} is outside project root")

        report_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{timestamp}-{safe_branch}.md"
        report_path = (report_dir / filename).resolve()

        # Security: validate final path is within project root
        if not report_path.is_relative_to(self._project_root):
            raise ValueError(f"Report path {report_path} is outside project root")

        report_path.write_text(report, encoding="utf-8")
        logger.info(f"Saved review report to {report_path}")
        return report_path


class PreReviewEngine:
    """Main entry point for pre-review context assembly."""

    def __init__(self, runner: GitRunner, config: GitConfig) -> None:
        self._runner = runner
        self._config = config

    def run(
        self,
        base_branch: str = "main",
        focus: str | None = None,
    ) -> int:
        """Assemble review context and save report.

        Args:
            base_branch: Branch to diff against.
            focus: Optional domain filter (e.g. 'security').

        Returns:
            0 on success, 1 on failure (e.g. no changes found).
        """
        preparer = ContextPreparer(self._runner)
        context = preparer.prepare_context(base_branch)

        if context["total_files"] == 0:
            logger.warning("No changes found to review.")
            return 1

        file_paths = [f["path"] for f in context["files"]]

        rules_dir_path = self._runner.repo_path / ".claude" / "rules" / "security"
        domain_filter = DomainFilter(rules_dir=rules_dir_path if rules_dir_path.is_dir() else None)
        rules = domain_filter.filter_for_files(file_paths)

        # Apply focus filter if specified
        if focus:
            focused_domains = {d for d in rules["domains"] if focus.lower() in d.lower()}
            # Always keep owasp when filtering
            focused_domains.add("owasp")
            rules["domains"] = focused_domains
            rules["rules_summary"] = domain_filter.get_rules_summary(sorted(focused_domains))

        branch = self._runner.current_branch()
        reporter = ReviewReporter(self._runner.repo_path)
        report = reporter.generate_report(context, rules, branch)
        reporter.save_report(report, branch)

        logger.info(f"Pre-review context assembled: {context['total_files']} files, {len(rules['domains'])} domains")
        return 0
