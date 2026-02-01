"""GitOps -- high-level git operations for branch management and merging."""

from dataclasses import dataclass
from pathlib import Path

from zerg.exceptions import GitError, MergeConflictError
from zerg.git.base import GitRunner
from zerg.logging import get_logger

logger = get_logger("git.ops")


@dataclass
class BranchInfo:
    """Information about a git branch."""

    name: str
    commit: str
    is_current: bool = False
    upstream: str | None = None


class GitOps(GitRunner):
    """Git operations for branch management, merging, and rebasing.

    Inherits low-level command execution from GitRunner and adds
    all higher-level operations: branching, merging, rebasing,
    staging branches, stashing, fetch/push, etc.
    """

    def __init__(self, repo_path: str | Path = ".") -> None:
        """Initialize git operations.

        Args:
            repo_path: Path to the git repository
        """
        super().__init__(repo_path)

    def branch_exists(self, branch: str) -> bool:
        """Check if a branch exists.

        Args:
            branch: Branch name

        Returns:
            True if branch exists
        """
        result = self._run("branch", "--list", branch, check=False)
        return bool(result.stdout.strip())

    def create_branch(self, branch: str, base: str = "HEAD") -> str:
        """Create a new branch.

        Args:
            branch: Branch name to create
            base: Base ref to branch from

        Returns:
            Commit SHA of new branch
        """
        self._run("branch", branch, base)
        logger.info(f"Created branch {branch} from {base}")
        return self.get_commit(branch)

    def delete_branch(self, branch: str, force: bool = False) -> None:
        """Delete a branch.

        Args:
            branch: Branch name to delete
            force: Force delete even if not merged
        """
        flag = "-D" if force else "-d"
        self._run("branch", flag, branch)
        logger.info(f"Deleted branch {branch}")

    def checkout(self, ref: str) -> None:
        """Checkout a branch or commit.

        Args:
            ref: Branch name or commit SHA
        """
        self._run("checkout", ref)
        logger.info(f"Checked out {ref}")

    def get_commit(self, ref: str = "HEAD") -> str:
        """Get commit SHA for a reference.

        Args:
            ref: Reference (branch, tag, or commit)

        Returns:
            Full commit SHA
        """
        result = self._run("rev-parse", ref)
        return result.stdout.strip()

    def has_conflicts(self) -> bool:
        """Check if there are merge conflicts.

        Returns:
            True if there are conflicts
        """
        result = self._run("diff", "--name-only", "--diff-filter=U", check=False)
        return bool(result.stdout.strip())

    def get_conflicting_files(self) -> list[str]:
        """Get list of files with merge conflicts.

        Returns:
            List of file paths with conflicts
        """
        result = self._run("diff", "--name-only", "--diff-filter=U", check=False)
        return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]

    def commit(
        self,
        message: str,
        add_all: bool = False,
        allow_empty: bool = False,
    ) -> str:
        """Create a commit.

        Args:
            message: Commit message
            add_all: Whether to add all changes
            allow_empty: Allow empty commits

        Returns:
            Commit SHA
        """
        if add_all:
            self._run("add", "-A")

        args = ["commit", "-m", message]
        if allow_empty:
            args.append("--allow-empty")

        self._run(*args)
        commit_sha = self.current_commit()
        logger.info(f"Created commit {commit_sha[:8]}: {message[:50]}")
        return commit_sha

    def merge(
        self,
        branch: str,
        message: str | None = None,
        no_ff: bool = True,
    ) -> str:
        """Merge a branch into the current branch.

        Args:
            branch: Branch to merge
            message: Merge commit message
            no_ff: Force merge commit (no fast-forward)

        Returns:
            Merge commit SHA

        Raises:
            MergeConflictError: If merge has conflicts
        """
        args = ["merge", branch]
        if no_ff:
            args.append("--no-ff")
        if message:
            args.extend(["-m", message])

        try:
            self._run(*args)
        except GitError:
            if self.has_conflicts():
                conflicts = self.get_conflicting_files()
                self.abort_merge()
                raise MergeConflictError(
                    f"Merge conflict: {branch} into {self.current_branch()}",
                    source_branch=branch,
                    target_branch=self.current_branch(),
                    conflicting_files=conflicts,
                ) from None
            raise

        commit_sha = self.current_commit()
        logger.info(f"Merged {branch} into {self.current_branch()}: {commit_sha[:8]}")
        return commit_sha

    def abort_merge(self) -> None:
        """Abort an in-progress merge."""
        self._run("merge", "--abort", check=False)
        logger.info("Aborted merge")

    def rebase(self, onto: str) -> None:
        """Rebase current branch onto another.

        Args:
            onto: Branch to rebase onto

        Raises:
            MergeConflictError: If rebase has conflicts
        """
        try:
            self._run("rebase", onto)
        except GitError:
            if self.has_conflicts():
                conflicts = self.get_conflicting_files()
                self.abort_rebase()
                raise MergeConflictError(
                    f"Rebase conflict onto {onto}",
                    source_branch=self.current_branch(),
                    target_branch=onto,
                    conflicting_files=conflicts,
                ) from None
            raise

        logger.info(f"Rebased onto {onto}")

    def abort_rebase(self) -> None:
        """Abort an in-progress rebase."""
        self._run("rebase", "--abort", check=False)
        logger.info("Aborted rebase")

    def create_staging_branch(self, feature: str, base: str = "main") -> str:
        """Create a staging branch for merging worker branches.

        Args:
            feature: Feature name
            base: Base branch to start from

        Returns:
            Staging branch name
        """
        staging_branch = f"zerg/{feature}/staging"

        # Delete if exists
        if self.branch_exists(staging_branch):
            self.delete_branch(staging_branch, force=True)

        self.create_branch(staging_branch, base)
        logger.info(f"Created staging branch {staging_branch} from {base}")
        return staging_branch

    def list_branches(self, pattern: str | None = None) -> list[BranchInfo]:
        """List branches, optionally filtered by pattern.

        Args:
            pattern: Glob pattern to filter branches

        Returns:
            List of BranchInfo objects
        """
        args = ["branch", "-v", "--format=%(refname:short)|%(objectname:short)|%(HEAD)"]
        if pattern:
            args.extend(["--list", pattern])

        result = self._run(*args)
        branches = []

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 3:
                branches.append(
                    BranchInfo(
                        name=parts[0],
                        commit=parts[1],
                        is_current=parts[2] == "*",
                    )
                )

        return branches

    def list_worker_branches(self, feature: str) -> list[str]:
        """List all worker branches for a feature.

        Args:
            feature: Feature name

        Returns:
            List of worker branch names
        """
        branches = self.list_branches(f"zerg/{feature}/worker-*")
        return [b.name for b in branches]

    def delete_feature_branches(self, feature: str, force: bool = True) -> int:
        """Delete all branches for a feature.

        Args:
            feature: Feature name
            force: Force delete

        Returns:
            Number of branches deleted
        """
        branches = self.list_branches(f"zerg/{feature}/*")
        count = 0

        for branch in branches:
            if not branch.is_current:
                self.delete_branch(branch.name, force=force)
                count += 1

        logger.info(f"Deleted {count} branches for feature {feature}")
        return count

    def fetch(self, remote: str = "origin", branch: str | None = None) -> None:
        """Fetch from remote.

        Args:
            remote: Remote name
            branch: Specific branch to fetch
        """
        args = ["fetch", remote]
        if branch:
            args.append(branch)
        self._run(*args)

    def push(
        self,
        remote: str = "origin",
        branch: str | None = None,
        force: bool = False,
        set_upstream: bool = False,
    ) -> None:
        """Push to remote.

        Args:
            remote: Remote name
            branch: Branch to push (defaults to current)
            force: Force push
            set_upstream: Set upstream tracking
        """
        args = ["push", remote]
        if branch:
            args.append(branch)
        if force:
            args.append("--force")
        if set_upstream:
            args.append("--set-upstream")

        self._run(*args)
        logger.info(f"Pushed to {remote}/{branch or 'current'}")

    def stash(self, message: str | None = None) -> bool:
        """Stash changes.

        Args:
            message: Stash message

        Returns:
            True if changes were stashed
        """
        if not self.has_changes():
            return False

        args = ["stash", "push"]
        if message:
            args.extend(["-m", message])

        self._run(*args)
        logger.info("Stashed changes")
        return True

    def stash_pop(self) -> None:
        """Pop the most recent stash."""
        self._run("stash", "pop")
        logger.info("Popped stash")
