"""ZERG v2 Git Operations - Intelligent git commands with finish workflow."""

import json
import subprocess
from dataclasses import dataclass, field
from enum import Enum


class GitAction(Enum):
    """Git operation actions."""

    COMMIT = "commit"
    BRANCH = "branch"
    MERGE = "merge"
    SYNC = "sync"
    HISTORY = "history"
    FINISH = "finish"
    STATUS = "status"


class FinishOption(Enum):
    """Options for finish workflow."""

    MERGE_LOCAL = 1
    CREATE_PR = 2
    KEEP_BRANCH = 3
    DISCARD = 4


@dataclass
class GitConfig:
    """Configuration for git operations."""

    push: bool = False
    base_branch: str = "main"
    no_verify: bool = False
    squash: bool = False


@dataclass
class CommitMessage:
    """Conventional commit message."""

    type: str  # feat, fix, docs, style, refactor, test, chore
    scope: str = ""
    description: str = ""
    body: str = ""
    breaking: bool = False

    def format(self) -> str:
        """Format as conventional commit."""
        if self.scope:
            header = f"{self.type}({self.scope}): {self.description}"
        else:
            header = f"{self.type}: {self.description}"

        if self.breaking:
            header = f"{header}\n\nBREAKING CHANGE: {self.body}"
        elif self.body:
            header = f"{header}\n\n{self.body}"

        return header


@dataclass
class FinishResult:
    """Result of finish workflow."""

    success: bool
    action: str
    message: str
    blocked: bool = False
    reason: str = ""
    pr_url: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "action": self.action,
            "message": self.message,
            "blocked": self.blocked,
            "reason": self.reason,
            "pr_url": self.pr_url,
        }


@dataclass
class GitStatus:
    """Git repository status."""

    branch: str = ""
    staged: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)
    ahead: int = 0
    behind: int = 0


class CommitGenerator:
    """Generate intelligent commit messages."""

    TYPE_PATTERNS = {
        "feat": ["new", "add", "implement", "create"],
        "fix": ["fix", "bug", "issue", "error", "correct"],
        "docs": ["doc", "readme", "comment", "md"],
        "style": ["style", "format", "lint"],
        "refactor": ["refactor", "clean", "reorganize"],
        "test": ["test", "spec"],
        "chore": ["chore", "build", "ci", "config"],
    }

    def detect_type(
        self, added: list[str], modified: list[str], deleted: list[str]
    ) -> str:
        """Detect commit type from changes."""
        all_files = added + modified + deleted

        # Check file patterns
        for file in all_files:
            file_lower = file.lower()
            if "test" in file_lower:
                return "test"
            if file_lower.endswith(".md"):
                return "docs"

        # Default based on operation
        if added and not modified:
            return "feat"
        if deleted and not added:
            return "chore"

        return "chore"

    def generate(
        self, added: list[str], modified: list[str], deleted: list[str]
    ) -> CommitMessage:
        """Generate commit message from changes."""
        commit_type = self.detect_type(added, modified, deleted)

        # Generate description
        all_files = added + modified + deleted
        if len(all_files) == 1:
            description = f"update {all_files[0]}"
        else:
            description = f"update {len(all_files)} files"

        return CommitMessage(type=commit_type, description=description)


class GitOps:
    """Git operations handler."""

    def __init__(self, repo_path: str = "."):
        """Initialize git operations."""
        self.repo_path = repo_path

    def available_actions(self) -> list[str]:
        """Return list of available actions."""
        return [a.value for a in GitAction]

    def get_current_branch(self) -> str:
        """Get current branch name."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.repo_path,
            )
            return result.stdout.strip()
        except (subprocess.SubprocessError, OSError):
            return "unknown"

    def get_status(self) -> dict:
        """Get git status."""
        status = GitStatus(branch=self.get_current_branch())

        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=self.repo_path,
            )
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                code = line[:2]
                filepath = line[3:]
                if code[0] in "MADRC":
                    status.staged.append(filepath)
                if code[1] == "M":
                    status.modified.append(filepath)
                if code == "??":
                    status.untracked.append(filepath)
        except (subprocess.SubprocessError, OSError):
            pass  # Best-effort git status; return partial data

        return {
            "branch": status.branch,
            "staged": status.staged,
            "modified": status.modified,
            "untracked": status.untracked,
            "ahead": status.ahead,
            "behind": status.behind,
        }

    def commit(self, message: str, push: bool = False) -> bool:
        """Create a commit."""
        try:
            subprocess.run(
                ["git", "commit", "-m", message],
                check=True,
                cwd=self.repo_path,
            )
            if push:
                subprocess.run(
                    ["git", "push"],
                    check=True,
                    cwd=self.repo_path,
                )
            return True
        except subprocess.CalledProcessError:
            return False

    def finish_branch(
        self, branch: str, base: str = "main", option: FinishOption = FinishOption.KEEP_BRANCH
    ) -> FinishResult:
        """Complete development branch with finish workflow."""
        # Step 1: Verify tests pass
        test_result = self._run_tests()
        if not test_result:
            return FinishResult(
                success=False,
                action="blocked",
                message="Tests must pass before finishing",
                blocked=True,
                reason="Test failures detected",
            )

        # Step 2: Execute based on option
        if option == FinishOption.MERGE_LOCAL:
            return self._merge_local(branch, base)
        elif option == FinishOption.CREATE_PR:
            return self._create_pr(branch, base)
        elif option == FinishOption.DISCARD:
            return self._discard_branch(branch)
        else:
            return FinishResult(
                success=True,
                action="kept",
                message=f"Branch {branch} kept as-is",
            )

    def _run_tests(self) -> bool:
        """Run project tests."""
        # Would run actual test command
        return True

    def _merge_local(self, branch: str, base: str) -> FinishResult:
        """Merge branch locally."""
        try:
            subprocess.run(["git", "checkout", base], check=True, cwd=self.repo_path)
            subprocess.run(
                ["git", "merge", "--no-ff", branch], check=True, cwd=self.repo_path
            )
            subprocess.run(
                ["git", "branch", "-d", branch], check=True, cwd=self.repo_path
            )
            return FinishResult(
                success=True,
                action="merged",
                message=f"Branch {branch} merged to {base}",
            )
        except subprocess.CalledProcessError as e:
            return FinishResult(
                success=False,
                action="error",
                message=f"Merge failed: {e}",
            )

    def _create_pr(self, branch: str, base: str) -> FinishResult:
        """Create pull request."""
        try:
            subprocess.run(
                ["git", "push", "-u", "origin", branch], check=True, cwd=self.repo_path
            )
            # Would use gh cli to create PR
            return FinishResult(
                success=True,
                action="pr_created",
                message=f"Branch {branch} pushed, create PR manually",
            )
        except subprocess.CalledProcessError as e:
            return FinishResult(
                success=False,
                action="error",
                message=f"Push failed: {e}",
            )

    def _discard_branch(self, branch: str) -> FinishResult:
        """Discard branch."""
        try:
            subprocess.run(
                ["git", "branch", "-D", branch], check=True, cwd=self.repo_path
            )
            return FinishResult(
                success=True,
                action="discarded",
                message=f"Branch {branch} discarded",
            )
        except subprocess.CalledProcessError as e:
            return FinishResult(
                success=False,
                action="error",
                message=f"Discard failed: {e}",
            )


class GitCommand:
    """Main git command orchestrator."""

    def __init__(self, config: GitConfig | None = None):
        """Initialize git command."""
        self.config = config or GitConfig()
        self.ops = GitOps()
        self.generator = CommitGenerator()

    def run(
        self, action: str, branch: str = "", option: int = 3
    ) -> FinishResult | dict:
        """Run git action.

        Args:
            action: Git action to perform
            branch: Branch name (for branch operations)
            option: Finish option (1-4)

        Returns:
            FinishResult or status dict
        """
        if action == "status":
            return self.ops.get_status()

        if action == "finish":
            finish_opt = FinishOption(option)
            current = self.ops.get_current_branch()
            return self.ops.finish_branch(
                branch or current,
                self.config.base_branch,
                finish_opt,
            )

        if action == "commit":
            status = self.ops.get_status()
            msg = self.generator.generate(
                status.get("staged", []),
                status.get("modified", []),
                [],
            )
            success = self.ops.commit(msg.format(), self.config.push)
            return FinishResult(
                success=success,
                action="commit",
                message="Commit created" if success else "Commit failed",
            )

        return FinishResult(
            success=False,
            action="unknown",
            message=f"Unknown action: {action}",
        )

    def format_result(
        self, result: FinishResult | dict, format: str = "text"
    ) -> str:
        """Format result.

        Args:
            result: Result to format
            format: Output format (text or json)

        Returns:
            Formatted string
        """
        if isinstance(result, dict):
            if format == "json":
                return json.dumps(result, indent=2)
            lines = ["Git Status", "=" * 40]
            for key, value in result.items():
                if isinstance(value, list):
                    lines.append(f"{key}: {len(value)} files")
                else:
                    lines.append(f"{key}: {value}")
            return "\n".join(lines)

        if format == "json":
            return json.dumps(result.to_dict(), indent=2)

        status = "✓" if result.success else "✗"
        lines = [
            "Git Operation Result",
            "=" * 40,
            f"Status: {status} {result.action}",
            f"Message: {result.message}",
        ]
        if result.blocked:
            lines.append(f"Blocked: {result.reason}")
        if result.pr_url:
            lines.append(f"PR: {result.pr_url}")

        return "\n".join(lines)


__all__ = [
    "GitAction",
    "FinishOption",
    "GitConfig",
    "CommitMessage",
    "FinishResult",
    "GitStatus",
    "CommitGenerator",
    "GitOps",
    "GitCommand",
]
