"""Tests for zerg.git_ops module."""

from pathlib import Path

import pytest

from zerg.exceptions import GitError, MergeConflict
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
        """Test merge with conflict raises MergeConflict."""
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

        with pytest.raises(MergeConflict):
            ops.merge("conflict")

    def test_create_staging_branch(self, tmp_repo: Path) -> None:
        """Test creating staging branch."""
        ops = GitOps(tmp_repo)

        staging = ops.create_staging_branch("test-feature", base=ops.current_branch())

        assert staging == "zerg/test-feature/staging"
        assert ops.branch_exists(staging)

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
