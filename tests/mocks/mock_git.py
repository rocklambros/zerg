"""Mock GitOps with commit verification.

Provides MockGitOps for testing worker commit behavior with
configurable commit verification and HEAD tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from zerg.exceptions import GitError, MergeConflictError


@dataclass
class CommitAttempt:
    """Record of a commit attempt."""

    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    head_before: str = ""
    head_after: str = ""
    success: bool = False
    files_staged: bool = False
    head_changed: bool = False
    error: str | None = None


@dataclass
class BranchInfo:
    """Information about a git branch."""

    name: str
    commit: str
    is_current: bool = False


class MockGitOps:
    """Mock GitOps with commit verification for testing.

    Simulates git operations with HEAD tracking and configurable
    commit behavior for testing worker commit verification.

    Example:
        git = MockGitOps()
        git.simulate_changes()  # Stage some changes

        head_before = git.current_commit()
        git.commit("Test commit", add_all=True)
        head_after = git.current_commit()

        assert head_before != head_after  # HEAD changed

        # Test commit failure
        git.configure(commit_fails=True)
        git.simulate_changes()

        head_before = git.current_commit()
        try:
            git.commit("Should fail")
        except GitError:
            pass

        assert git.current_commit() == head_before  # HEAD unchanged
    """

    def __init__(self, repo_path: str | Path = ".") -> None:
        """Initialize mock git operations.

        Args:
            repo_path: Simulated repository path
        """
        self.repo_path = Path(repo_path).resolve()

        # State tracking
        self._current_branch = "main"
        self._branches: dict[str, str] = {"main": "initial000"}
        self._commit_counter = 0
        self._commits: list[str] = ["initial000"]
        self._changes_staged = False
        self._stash: list[str] = []

        # Commit attempt tracking
        self._commit_attempts: list[CommitAttempt] = []

        # Configurable behavior
        self._commit_fails = False
        self._commit_no_head_change = False
        self._has_conflicts = False
        self._conflicting_files: list[str] = []
        self._fail_checkout_branches: set[str] = set()
        self._fail_merge_branches: set[str] = set()

    def configure(
        self,
        commit_fails: bool = False,
        commit_no_head_change: bool = False,
        has_conflicts: bool = False,
        conflicting_files: list[str] | None = None,
        fail_checkout_branches: list[str] | None = None,
        fail_merge_branches: list[str] | None = None,
    ) -> MockGitOps:
        """Configure mock behavior.

        Args:
            commit_fails: Whether commits should fail
            commit_no_head_change: Commit succeeds but HEAD doesn't change
            has_conflicts: Whether merges have conflicts
            conflicting_files: Files that conflict
            fail_checkout_branches: Branches where checkout fails
            fail_merge_branches: Branches where merge fails

        Returns:
            Self for chaining
        """
        self._commit_fails = commit_fails
        self._commit_no_head_change = commit_no_head_change
        self._has_conflicts = has_conflicts
        self._conflicting_files = conflicting_files or []
        self._fail_checkout_branches = set(fail_checkout_branches or [])
        self._fail_merge_branches = set(fail_merge_branches or [])
        return self

    def current_branch(self) -> str:
        """Get current branch name.

        Returns:
            Current branch name
        """
        return self._current_branch

    def current_commit(self) -> str:
        """Get current commit SHA.

        Returns:
            Current commit SHA
        """
        return self._branches.get(self._current_branch, "unknown")

    def branch_exists(self, branch: str) -> bool:
        """Check if branch exists.

        Args:
            branch: Branch name

        Returns:
            True if branch exists
        """
        return branch in self._branches

    def create_branch(self, branch: str, base: str = "HEAD") -> str:
        """Create a new branch.

        Args:
            branch: Branch name
            base: Base ref

        Returns:
            Commit SHA
        """
        base_commit = self._branches.get(
            base if base != "HEAD" else self._current_branch,
            "unknown",
        )
        self._branches[branch] = base_commit
        return base_commit

    def delete_branch(self, branch: str, force: bool = False) -> None:
        """Delete a branch.

        Args:
            branch: Branch name
            force: Force delete
        """
        if branch in self._branches and branch != self._current_branch:
            del self._branches[branch]

    def checkout(self, ref: str) -> None:
        """Checkout a branch or commit.

        Args:
            ref: Branch or commit

        Raises:
            GitError: If checkout fails
        """
        if ref in self._fail_checkout_branches:
            raise GitError(f"Simulated checkout failure for {ref}")

        if ref in self._branches:
            self._current_branch = ref

    def get_commit(self, ref: str = "HEAD") -> str:
        """Get commit SHA for ref.

        Args:
            ref: Reference

        Returns:
            Commit SHA
        """
        if ref == "HEAD":
            ref = self._current_branch
        return self._branches.get(ref, "unknown")

    def has_changes(self) -> bool:
        """Check for uncommitted changes.

        Returns:
            True if there are changes
        """
        return self._changes_staged

    def has_conflicts(self) -> bool:
        """Check for merge conflicts.

        Returns:
            True if there are conflicts
        """
        return self._has_conflicts and len(self._conflicting_files) > 0

    def get_conflicting_files(self) -> list[str]:
        """Get list of conflicting files.

        Returns:
            List of file paths
        """
        return self._conflicting_files if self._has_conflicts else []

    def commit(
        self,
        message: str,
        add_all: bool = False,
        allow_empty: bool = False,
    ) -> str:
        """Create a commit with HEAD verification.

        Args:
            message: Commit message
            add_all: Whether to add all changes
            allow_empty: Allow empty commits

        Returns:
            Commit SHA

        Raises:
            GitError: If commit fails
        """
        head_before = self.current_commit()

        attempt = CommitAttempt(
            message=message,
            head_before=head_before,
            files_staged=self._changes_staged or allow_empty,
        )

        # Check if there are changes to commit
        if not self._changes_staged and not allow_empty:
            attempt.error = "nothing to commit"
            attempt.head_after = head_before
            self._commit_attempts.append(attempt)
            raise GitError("nothing to commit, working tree clean")

        # Check for configured failure
        if self._commit_fails:
            attempt.error = "Simulated commit failure"
            attempt.head_after = head_before
            self._commit_attempts.append(attempt)
            raise GitError("Simulated commit failure")

        # Check for HEAD-no-change mode (commit succeeds but HEAD doesn't move)
        if self._commit_no_head_change:
            attempt.success = True
            attempt.head_after = head_before
            attempt.head_changed = False
            self._commit_attempts.append(attempt)
            self._changes_staged = False
            return head_before  # Return old HEAD (bug simulation)

        # Normal successful commit
        self._commit_counter += 1
        new_commit = f"commit{self._commit_counter:06d}"
        self._commits.append(new_commit)
        self._branches[self._current_branch] = new_commit
        self._changes_staged = False

        attempt.success = True
        attempt.head_after = new_commit
        attempt.head_changed = True
        self._commit_attempts.append(attempt)

        return new_commit

    def merge(
        self,
        branch: str,
        message: str | None = None,
        no_ff: bool = True,
    ) -> str:
        """Merge a branch.

        Args:
            branch: Branch to merge
            message: Merge message
            no_ff: No fast-forward

        Returns:
            Merge commit SHA

        Raises:
            MergeConflictError: If merge has conflicts
            GitError: If merge fails
        """
        if branch in self._fail_merge_branches:
            raise GitError(f"Simulated merge failure for {branch}")

        if self._has_conflicts:
            raise MergeConflictError(
                f"Merge conflict: {branch}",
                source_branch=branch,
                target_branch=self._current_branch,
                conflicting_files=self._conflicting_files,
            )

        return self.commit(message or f"Merge {branch}")

    def abort_merge(self) -> None:
        """Abort merge."""
        self._has_conflicts = False
        self._conflicting_files = []

    def rebase(self, onto: str) -> None:
        """Rebase current branch.

        Args:
            onto: Branch to rebase onto

        Raises:
            MergeConflictError: If rebase has conflicts
        """
        if self._has_conflicts:
            raise MergeConflictError(
                f"Rebase conflict onto {onto}",
                source_branch=self._current_branch,
                target_branch=onto,
                conflicting_files=self._conflicting_files,
            )

    def abort_rebase(self) -> None:
        """Abort rebase."""
        pass

    def create_staging_branch(self, feature: str, base: str = "main") -> str:
        """Create staging branch.

        Args:
            feature: Feature name
            base: Base branch

        Returns:
            Staging branch name
        """
        staging = f"zerg/{feature}/staging"
        self.create_branch(staging, base)
        return staging

    def list_branches(self, pattern: str | None = None) -> list[BranchInfo]:
        """List branches.

        Args:
            pattern: Filter pattern

        Returns:
            List of branch info
        """
        result = []
        for name, commit in self._branches.items():
            if pattern is None or name.startswith(pattern.replace("*", "")):
                result.append(
                    BranchInfo(
                        name=name,
                        commit=commit,
                        is_current=(name == self._current_branch),
                    )
                )
        return result

    def list_worker_branches(self, feature: str) -> list[str]:
        """List worker branches for feature.

        Args:
            feature: Feature name

        Returns:
            List of branch names
        """
        prefix = f"zerg/{feature}/worker-"
        return [b for b in self._branches if b.startswith(prefix)]

    def delete_feature_branches(self, feature: str, force: bool = True) -> int:
        """Delete all feature branches.

        Args:
            feature: Feature name
            force: Force delete

        Returns:
            Number deleted
        """
        prefix = f"zerg/{feature}/"
        to_delete = [b for b in self._branches if b.startswith(prefix)]
        for branch in to_delete:
            self.delete_branch(branch, force)
        return len(to_delete)

    def fetch(self, remote: str = "origin", branch: str | None = None) -> None:
        """Mock fetch - no-op.

        Args:
            remote: Remote name
            branch: Branch to fetch
        """
        pass

    def push(
        self,
        remote: str = "origin",
        branch: str | None = None,
        force: bool = False,
        set_upstream: bool = False,
    ) -> None:
        """Mock push - no-op.

        Args:
            remote: Remote name
            branch: Branch to push
            force: Force push
            set_upstream: Set upstream
        """
        pass

    def stash(self, message: str | None = None) -> bool:
        """Stash changes.

        Args:
            message: Stash message

        Returns:
            True if changes were stashed
        """
        if not self._changes_staged:
            return False
        self._stash.append(message or "stash")
        self._changes_staged = False
        return True

    def stash_pop(self) -> None:
        """Pop stash."""
        if self._stash:
            self._stash.pop()
            self._changes_staged = True

    # Helper methods for testing

    def simulate_changes(self) -> None:
        """Simulate staged changes."""
        self._changes_staged = True

    def add_branch(self, name: str, commit: str | None = None) -> None:
        """Add a branch for testing.

        Args:
            name: Branch name
            commit: Optional commit SHA
        """
        self._branches[name] = commit or f"commit_{name}"

    def get_commit_attempts(self) -> list[CommitAttempt]:
        """Get all commit attempts.

        Returns:
            List of CommitAttempt records
        """
        return self._commit_attempts.copy()

    def get_successful_commits(self) -> list[CommitAttempt]:
        """Get successful commits.

        Returns:
            List of successful CommitAttempt records
        """
        return [c for c in self._commit_attempts if c.success]

    def get_commits_with_head_change(self) -> list[CommitAttempt]:
        """Get commits where HEAD changed.

        Returns:
            List of CommitAttempt records with HEAD change
        """
        return [c for c in self._commit_attempts if c.head_changed]

    def get_commits_without_head_change(self) -> list[CommitAttempt]:
        """Get commits where HEAD didn't change.

        Returns:
            List of CommitAttempt records without HEAD change
        """
        return [c for c in self._commit_attempts if c.success and not c.head_changed]

    def verify_head_changed(self, head_before: str, head_after: str) -> bool:
        """Verify that HEAD changed after commit.

        Args:
            head_before: HEAD before commit
            head_after: HEAD after commit

        Returns:
            True if HEAD changed
        """
        return head_before != head_after

    def reset(self) -> None:
        """Reset mock state."""
        self._current_branch = "main"
        self._branches = {"main": "initial000"}
        self._commit_counter = 0
        self._commits = ["initial000"]
        self._changes_staged = False
        self._stash.clear()
        self._commit_attempts.clear()
        self._commit_fails = False
        self._commit_no_head_change = False
        self._has_conflicts = False
        self._conflicting_files = []
