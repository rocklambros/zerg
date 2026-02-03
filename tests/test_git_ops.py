"""Tests for zerg.git_ops module."""

from pathlib import Path

import pytest

from zerg.exceptions import GitError, MergeConflictError
from zerg.git_ops import BranchInfo, GitOps


class TestGitOps:
    """Tests for GitOps class."""

    def test_create_git_ops(self, tmp_repo: Path) -> None:
        """Test creating GitOps with valid repo."""
        ops = GitOps(tmp_repo)

        assert ops is not None
        assert ops.repo_path == tmp_repo

    def test_create_git_ops_invalid_repo(self, tmp_path: Path) -> None:
        """Test creating GitOps with invalid repo raises error."""
        with pytest.raises(GitError):
            GitOps(tmp_path)

    def test_current_branch(self, tmp_repo: Path) -> None:
        """Test getting current branch."""
        ops = GitOps(tmp_repo)

        branch = ops.current_branch()

        assert isinstance(branch, str)
        assert branch

    def test_current_commit(self, tmp_repo: Path) -> None:
        """Test getting current commit."""
        ops = GitOps(tmp_repo)

        commit = ops.current_commit()

        assert isinstance(commit, str)
        assert len(commit) == 40  # Full SHA

    def test_branch_exists(self, tmp_repo: Path) -> None:
        """Test checking if branch exists."""
        ops = GitOps(tmp_repo)
        current = ops.current_branch()

        assert ops.branch_exists(current) is True
        assert ops.branch_exists("nonexistent-branch") is False

    def test_create_branch(self, tmp_repo: Path) -> None:
        """Test creating a new branch."""
        ops = GitOps(tmp_repo)

        commit = ops.create_branch("test-branch")

        assert ops.branch_exists("test-branch") is True
        assert isinstance(commit, str)

    def test_delete_branch(self, tmp_repo: Path) -> None:
        """Test deleting a branch."""
        ops = GitOps(tmp_repo)
        ops.create_branch("to-delete")

        ops.delete_branch("to-delete")

        assert ops.branch_exists("to-delete") is False

    def test_checkout(self, tmp_repo: Path) -> None:
        """Test checking out a branch."""
        ops = GitOps(tmp_repo)
        ops.create_branch("checkout-test")

        ops.checkout("checkout-test")

        assert ops.current_branch() == "checkout-test"

    def test_get_commit(self, tmp_repo: Path) -> None:
        """Test getting commit SHA for ref."""
        ops = GitOps(tmp_repo)

        commit = ops.get_commit("HEAD")

        assert isinstance(commit, str)
        assert len(commit) == 40

    def test_has_changes_no_changes(self, tmp_repo: Path) -> None:
        """Test has_changes with clean working tree."""
        ops = GitOps(tmp_repo)

        assert ops.has_changes() is False

    def test_has_changes_with_changes(self, tmp_repo: Path) -> None:
        """Test has_changes with modifications."""
        ops = GitOps(tmp_repo)

        # Create untracked file
        (tmp_repo / "newfile.txt").write_text("new content")

        assert ops.has_changes() is True

    def test_commit(self, tmp_repo: Path) -> None:
        """Test creating a commit."""
        ops = GitOps(tmp_repo)

        # Make a change
        (tmp_repo / "test.txt").write_text("test content")

        commit = ops.commit("Test commit", add_all=True)

        assert isinstance(commit, str)
        assert len(commit) == 40

    def test_commit_allow_empty(self, tmp_repo: Path) -> None:
        """Test creating an empty commit."""
        ops = GitOps(tmp_repo)

        commit = ops.commit("Empty commit", allow_empty=True)

        assert isinstance(commit, str)

    def test_merge(self, tmp_repo: Path) -> None:
        """Test merging branches."""
        ops = GitOps(tmp_repo)
        original = ops.current_branch()

        # Create branch with changes
        ops.create_branch("feature")
        ops.checkout("feature")
        (tmp_repo / "feature.txt").write_text("feature content")
        ops.commit("Add feature", add_all=True)

        # Merge back
        ops.checkout(original)
        commit = ops.merge("feature", message="Merge feature")

        assert isinstance(commit, str)

    def test_merge_conflict(self, tmp_repo: Path) -> None:
        """Test merge with conflict raises MergeConflictError."""
        ops = GitOps(tmp_repo)
        original = ops.current_branch()

        # Create conflicting changes
        ops.create_branch("conflict")
        ops.checkout("conflict")
        (tmp_repo / "README.md").write_text("conflict content")
        ops.commit("Conflict change", add_all=True)

        ops.checkout(original)
        (tmp_repo / "README.md").write_text("main content")
        ops.commit("Main change", add_all=True)

        with pytest.raises(MergeConflictError):
            ops.merge("conflict")

    def test_merge_reraises_git_error_on_non_conflict_failure(self, tmp_repo: Path) -> None:
        """Test that merge re-raises GitError when failure is not a conflict."""
        ops = GitOps(tmp_repo)

        # Try to merge a non-existent branch
        with pytest.raises(GitError):
            ops.merge("nonexistent-branch")

    def test_create_staging_branch(self, tmp_repo: Path) -> None:
        """Test creating staging branch."""
        ops = GitOps(tmp_repo)

        staging = ops.create_staging_branch("test-feature", base=ops.current_branch())

        assert staging == "zerg/test-feature/staging"
        assert ops.branch_exists(staging)

    def test_create_staging_branch_deletes_existing(self, tmp_repo: Path) -> None:
        """Test that creating staging branch deletes existing one first."""
        ops = GitOps(tmp_repo)
        base = ops.current_branch()

        # Create staging branch first time
        staging = ops.create_staging_branch("dup-feature", base=base)
        assert ops.branch_exists(staging)

        # Make a commit on base so we can tell the difference
        (tmp_repo / "new-file.txt").write_text("content")
        ops.commit("New commit", add_all=True)
        new_commit = ops.current_commit()

        # Create staging branch again - should be recreated from new base
        staging2 = ops.create_staging_branch("dup-feature", base=base)
        assert staging2 == staging
        assert ops.branch_exists(staging)

        # Verify staging now has the new commit
        ops.checkout(staging)
        assert ops.current_commit() == new_commit

    def test_list_branches(self, tmp_repo: Path) -> None:
        """Test listing branches."""
        ops = GitOps(tmp_repo)
        ops.create_branch("list-test")

        branches = ops.list_branches()

        assert isinstance(branches, list)
        assert all(isinstance(b, BranchInfo) for b in branches)

    def test_list_branches_with_pattern(self, tmp_repo: Path) -> None:
        """Test listing branches with pattern."""
        ops = GitOps(tmp_repo)
        ops.create_branch("zerg/feature/worker-0")
        ops.create_branch("zerg/feature/worker-1")
        ops.create_branch("other-branch")

        branches = ops.list_branches("zerg/feature/worker-*")

        assert len(branches) == 2
        assert all("worker-" in b.name for b in branches)

    def test_list_branches_empty_result(self, tmp_repo: Path) -> None:
        """Test listing branches with pattern that matches nothing."""
        ops = GitOps(tmp_repo)

        branches = ops.list_branches("nonexistent-*")

        assert not branches

    def test_list_worker_branches(self, tmp_repo: Path) -> None:
        """Test listing worker branches for feature."""
        ops = GitOps(tmp_repo)
        ops.create_branch("zerg/myfeature/worker-0")
        ops.create_branch("zerg/myfeature/worker-1")

        workers = ops.list_worker_branches("myfeature")

        assert len(workers) == 2
        assert "zerg/myfeature/worker-0" in workers
        assert "zerg/myfeature/worker-1" in workers

    def test_delete_feature_branches(self, tmp_repo: Path) -> None:
        """Test deleting all feature branches."""
        ops = GitOps(tmp_repo)
        ops.create_branch("zerg/cleanup/worker-0")
        ops.create_branch("zerg/cleanup/worker-1")
        ops.create_branch("zerg/cleanup/staging")

        count = ops.delete_feature_branches("cleanup")

        assert count == 3
        assert not ops.branch_exists("zerg/cleanup/worker-0")

    def test_stash(self, tmp_repo: Path) -> None:
        """Test stashing changes."""
        ops = GitOps(tmp_repo)
        # Modify an existing tracked file (README.md from fixture)
        (tmp_repo / "README.md").write_text("modified content")

        stashed = ops.stash("Test stash")

        assert stashed is True
        # After stash, file should be reverted to original content
        assert (tmp_repo / "README.md").read_text() == "# Test Repo"

    def test_stash_pop(self, tmp_repo: Path) -> None:
        """Test popping stash."""
        ops = GitOps(tmp_repo)
        # Modify an existing tracked file
        (tmp_repo / "README.md").write_text("modified for pop test")
        ops.stash("Test stash")

        ops.stash_pop()

        assert (tmp_repo / "README.md").read_text() == "modified for pop test"

    def test_stash_no_changes(self, tmp_repo: Path) -> None:
        """Test stash with no changes returns False."""
        ops = GitOps(tmp_repo)

        stashed = ops.stash()

        assert stashed is False

    def test_has_conflicts(self, tmp_repo: Path) -> None:
        """Test has_conflicts returns False when no conflicts."""
        ops = GitOps(tmp_repo)

        assert ops.has_conflicts() is False

    def test_get_conflicting_files(self, tmp_repo: Path) -> None:
        """Test get_conflicting_files returns empty list when no conflicts."""
        ops = GitOps(tmp_repo)

        files = ops.get_conflicting_files()

        assert not files

    def test_rebase(self, tmp_repo: Path) -> None:
        """Test rebasing current branch onto another."""
        ops = GitOps(tmp_repo)
        original = ops.current_branch()

        # Create feature branch from current position
        ops.create_branch("feature-rebase")

        # Add a commit on main
        (tmp_repo / "main-file.txt").write_text("main content")
        ops.commit("Main commit", add_all=True)

        # Switch to feature, add a commit
        ops.checkout("feature-rebase")
        (tmp_repo / "feature-file.txt").write_text("feature content")
        ops.commit("Feature commit", add_all=True)

        # Rebase onto main
        ops.rebase(original)

        # Feature branch should now have both commits
        assert (tmp_repo / "main-file.txt").exists()
        assert (tmp_repo / "feature-file.txt").exists()

    def test_rebase_conflict(self, tmp_repo: Path) -> None:
        """Test rebase with conflict raises MergeConflictError."""
        ops = GitOps(tmp_repo)
        original = ops.current_branch()

        # Create feature branch
        ops.create_branch("conflict-rebase")

        # Add conflicting change on main
        (tmp_repo / "README.md").write_text("main rebase content")
        ops.commit("Main rebase change", add_all=True)

        # Switch to feature, add conflicting change
        ops.checkout("conflict-rebase")
        (tmp_repo / "README.md").write_text("feature rebase content")
        ops.commit("Feature rebase change", add_all=True)

        # Rebase should raise MergeConflictError
        with pytest.raises(MergeConflictError) as exc_info:
            ops.rebase(original)

        assert "rebase" in exc_info.value.message.lower() or "conflict" in exc_info.value.message.lower()

    def test_abort_rebase(self, tmp_repo: Path) -> None:
        """Test aborting a rebase does not raise error even without active rebase."""
        ops = GitOps(tmp_repo)

        # Should not raise even if no rebase is in progress
        ops.abort_rebase()

    def test_fetch(self, tmp_repo: Path) -> None:
        """Test fetch command."""
        ops = GitOps(tmp_repo)

        # Fetch without remote will fail, but we test the method paths
        with pytest.raises(GitError):
            ops.fetch("origin")

    def test_fetch_with_branch(self, tmp_repo: Path) -> None:
        """Test fetch with specific branch."""
        ops = GitOps(tmp_repo)

        # Fetch with branch arg should also fail without remote
        with pytest.raises(GitError):
            ops.fetch("origin", "main")

    def test_push(self, tmp_repo: Path) -> None:
        """Test push command."""
        ops = GitOps(tmp_repo)

        # Push without remote will fail
        with pytest.raises(GitError):
            ops.push("origin")

    def test_push_with_options(self, tmp_repo: Path) -> None:
        """Test push with various options."""
        ops = GitOps(tmp_repo)

        # Test that push command is constructed with options
        with pytest.raises(GitError):
            ops.push("origin", branch="main", force=True, set_upstream=True)


class TestBranchInfo:
    """Tests for BranchInfo dataclass."""

    def test_create_branch_info(self) -> None:
        """Test creating BranchInfo."""
        info = BranchInfo(
            name="test-branch",
            commit="abc123",
            is_current=True,
            upstream="origin/test-branch",
        )

        assert info.name == "test-branch"
        assert info.commit == "abc123"
        assert info.is_current is True
        assert info.upstream == "origin/test-branch"

    def test_branch_info_defaults(self) -> None:
        """Test BranchInfo default values."""
        info = BranchInfo(name="test", commit="abc")

        assert info.is_current is False
        assert info.upstream is None
