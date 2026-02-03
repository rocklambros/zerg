"""Extended integration tests for git operations (TC-019).

Tests advanced git operations including merge, rebase, and conflict handling.
"""

import subprocess
from pathlib import Path

import pytest

from zerg.exceptions import GitError, MergeConflictError
from zerg.git_ops import GitOps


@pytest.fixture
def git_repo_with_branches(tmp_path: Path):
    """Create a git repo with multiple branches for testing."""
    # Initialize repo
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)

    # Create initial commit
    (tmp_path / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "Initial commit"], cwd=tmp_path, check=True)

    # Create feature branch with changes
    subprocess.run(["git", "branch", "feature-1"], cwd=tmp_path, check=True)
    subprocess.run(["git", "checkout", "feature-1"], cwd=tmp_path, check=True)
    (tmp_path / "feature.py").write_text("# Feature code")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "Add feature"], cwd=tmp_path, check=True)

    # Return to main
    main_branch = "main"
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    if "master" in result.stdout:
        main_branch = "master"

    subprocess.run(["git", "checkout", main_branch], cwd=tmp_path, check=True)

    return tmp_path


class TestBranchOperations:
    """Tests for branch operations."""

    def test_list_branches(self, git_repo_with_branches: Path) -> None:
        """Test listing all branches."""
        ops = GitOps(git_repo_with_branches)

        branches = ops.list_branches()

        assert len(branches) >= 2
        branch_names = [b.name for b in branches]
        assert "feature-1" in branch_names

    def test_list_branches_with_pattern(self, git_repo_with_branches: Path) -> None:
        """Test listing branches with pattern."""
        ops = GitOps(git_repo_with_branches)

        branches = ops.list_branches(pattern="feature-*")

        assert len(branches) >= 1
        assert all("feature" in b.name for b in branches)

    def test_current_branch_marked(self, git_repo_with_branches: Path) -> None:
        """Test current branch is marked."""
        ops = GitOps(git_repo_with_branches)

        branches = ops.list_branches()
        current = [b for b in branches if b.is_current]

        assert len(current) == 1

    def test_create_branch_from_commit(self, git_repo_with_branches: Path) -> None:
        """Test creating branch from specific commit."""
        ops = GitOps(git_repo_with_branches)
        commit = ops.current_commit()

        new_commit = ops.create_branch("from-commit", commit)

        assert ops.branch_exists("from-commit")
        assert new_commit == commit

    def test_delete_unmerged_branch_fails(self, git_repo_with_branches: Path) -> None:
        """Test deleting unmerged branch without force fails."""
        ops = GitOps(git_repo_with_branches)

        with pytest.raises(GitError):
            ops.delete_branch("feature-1", force=False)

    def test_delete_unmerged_branch_force(self, git_repo_with_branches: Path) -> None:
        """Test force deleting unmerged branch."""
        ops = GitOps(git_repo_with_branches)

        ops.delete_branch("feature-1", force=True)

        assert not ops.branch_exists("feature-1")


class TestMergeOperations:
    """Tests for merge operations."""

    def test_merge_branch(self, git_repo_with_branches: Path) -> None:
        """Test merging a branch."""
        ops = GitOps(git_repo_with_branches)

        merge_commit = ops.merge("feature-1", message="Merge feature-1")

        assert len(merge_commit) == 40
        # Feature file should exist after merge
        assert (git_repo_with_branches / "feature.py").exists()

    def test_merge_no_ff(self, git_repo_with_branches: Path) -> None:
        """Test merge creates commit with no-ff."""
        ops = GitOps(git_repo_with_branches)
        before_commit = ops.current_commit()

        merge_commit = ops.merge("feature-1", no_ff=True)

        assert merge_commit != before_commit

    def test_merge_conflict_detected(self, git_repo_with_branches: Path) -> None:
        """Test merge conflict is detected."""
        ops = GitOps(git_repo_with_branches)

        # Create conflicting change on main
        (git_repo_with_branches / "feature.py").write_text("# Main change")
        subprocess.run(["git", "add", "-A"], cwd=git_repo_with_branches, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "Conflict"], cwd=git_repo_with_branches, check=True)

        with pytest.raises(MergeConflictError) as exc_info:
            ops.merge("feature-1")

        assert "feature.py" in exc_info.value.conflicting_files

    def test_abort_merge(self, git_repo_with_branches: Path) -> None:
        """Test aborting a merge."""
        ops = GitOps(git_repo_with_branches)

        # Create conflicting state
        (git_repo_with_branches / "feature.py").write_text("# Main change")
        subprocess.run(["git", "add", "-A"], cwd=git_repo_with_branches, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "Conflict"], cwd=git_repo_with_branches, check=True)

        # Start merge that will conflict
        subprocess.run(
            ["git", "merge", "--no-commit", "feature-1"],
            cwd=git_repo_with_branches,
            capture_output=True,
        )

        # Abort should work
        ops.abort_merge()

        # Should be clean
        assert not ops.has_conflicts()


class TestRebaseOperations:
    """Tests for rebase operations."""

    def test_rebase_branch(self, git_repo_with_branches: Path) -> None:
        """Test rebasing a branch."""
        ops = GitOps(git_repo_with_branches)

        # Checkout feature and add more commits
        ops.checkout("feature-1")
        (git_repo_with_branches / "feature2.py").write_text("# More feature")
        ops.commit("Add more feature", add_all=True)

        # Add commit to main
        main_branch = "main" if ops.branch_exists("main") else "master"
        ops.checkout(main_branch)
        (git_repo_with_branches / "main.py").write_text("# Main code")
        ops.commit("Add main code", add_all=True)

        # Rebase feature onto main
        ops.checkout("feature-1")
        ops.rebase(main_branch)

        # Feature should have main's changes
        assert (git_repo_with_branches / "main.py").exists()


class TestCommitOperations:
    """Tests for commit operations."""

    def test_commit_with_message(self, git_repo_with_branches: Path) -> None:
        """Test creating a commit with message."""
        ops = GitOps(git_repo_with_branches)

        (git_repo_with_branches / "new.py").write_text("# New file")
        commit = ops.commit("Add new file", add_all=True)

        assert len(commit) == 40

    def test_empty_commit_fails(self, git_repo_with_branches: Path) -> None:
        """Test empty commit fails without allow_empty."""
        ops = GitOps(git_repo_with_branches)

        with pytest.raises(GitError):
            ops.commit("Empty commit")

    def test_empty_commit_allowed(self, git_repo_with_branches: Path) -> None:
        """Test empty commit allowed with flag."""
        ops = GitOps(git_repo_with_branches)

        commit = ops.commit("Empty commit", allow_empty=True)

        assert len(commit) == 40

    def test_has_changes_detection(self, git_repo_with_branches: Path) -> None:
        """Test detection of uncommitted changes."""
        ops = GitOps(git_repo_with_branches)

        assert not ops.has_changes()

        (git_repo_with_branches / "dirty.py").write_text("# Dirty")

        assert ops.has_changes()


class TestStagingBranch:
    """Tests for staging branch operations."""

    def test_create_staging_branch(self, git_repo_with_branches: Path) -> None:
        """Test creating staging branch."""
        ops = GitOps(git_repo_with_branches)
        main_branch = "main" if ops.branch_exists("main") else "master"

        staging = ops.create_staging_branch("test-feature", base=main_branch)

        assert ops.branch_exists(staging)
        assert "staging" in staging

    def test_staging_branch_from_main(self, git_repo_with_branches: Path) -> None:
        """Test staging branch is based on main."""
        ops = GitOps(git_repo_with_branches)
        main_branch = "main" if ops.branch_exists("main") else "master"
        main_commit = ops.get_commit(main_branch)

        staging = ops.create_staging_branch("test-feature", base=main_branch)
        staging_commit = ops.get_commit(staging)

        assert staging_commit == main_commit


class TestWorkerBranches:
    """Tests for worker branch operations."""

    def test_list_worker_branches(self, git_repo_with_branches: Path) -> None:
        """Test listing worker branches."""
        ops = GitOps(git_repo_with_branches)

        # Create worker branches
        ops.create_branch("zerg/test-feature/worker-0")
        ops.create_branch("zerg/test-feature/worker-1")

        branches = ops.list_worker_branches("test-feature")

        assert len(branches) == 2
        assert "zerg/test-feature/worker-0" in branches
        assert "zerg/test-feature/worker-1" in branches

    def test_delete_feature_branches(self, git_repo_with_branches: Path) -> None:
        """Test deleting all feature branches."""
        ops = GitOps(git_repo_with_branches)

        # Create worker branches
        ops.create_branch("zerg/cleanup-test/worker-0")
        ops.create_branch("zerg/cleanup-test/worker-1")

        count = ops.delete_feature_branches("cleanup-test", force=True)

        assert count == 2
        assert not ops.branch_exists("zerg/cleanup-test/worker-0")
        assert not ops.branch_exists("zerg/cleanup-test/worker-1")


class TestStashOperations:
    """Tests for stash operations."""

    def test_stash_changes(self, git_repo_with_branches: Path) -> None:
        """Test stashing changes."""
        ops = GitOps(git_repo_with_branches)

        # Create dirty state - must be tracked file
        (git_repo_with_branches / "dirty.py").write_text("# Dirty")
        subprocess.run(["git", "add", "dirty.py"], cwd=git_repo_with_branches, check=True)

        result = ops.stash("Test stash")

        assert result is True
        assert not (git_repo_with_branches / "dirty.py").exists()

    def test_stash_pop(self, git_repo_with_branches: Path) -> None:
        """Test popping stash."""
        ops = GitOps(git_repo_with_branches)

        # Create and stash
        (git_repo_with_branches / "dirty.py").write_text("# Dirty")
        subprocess.run(["git", "add", "dirty.py"], cwd=git_repo_with_branches, check=True)
        ops.stash("Test stash")

        # Pop
        ops.stash_pop()

        # Changes should be back
        assert (git_repo_with_branches / "dirty.py").exists()


class TestCommitInfo:
    """Tests for commit information."""

    def test_get_head_commit(self, git_repo_with_branches: Path) -> None:
        """Test getting HEAD commit."""
        ops = GitOps(git_repo_with_branches)

        head = ops.current_commit()

        assert len(head) == 40

    def test_get_commit_for_ref(self, git_repo_with_branches: Path) -> None:
        """Test getting commit for arbitrary ref."""
        ops = GitOps(git_repo_with_branches)

        commit = ops.get_commit("feature-1")

        assert len(commit) == 40

    def test_different_branches_different_commits(self, git_repo_with_branches: Path) -> None:
        """Test different branches have different commits."""
        ops = GitOps(git_repo_with_branches)
        main_branch = "main" if ops.branch_exists("main") else "master"

        main_commit = ops.get_commit(main_branch)
        feature_commit = ops.get_commit("feature-1")

        assert main_commit != feature_commit


class TestConflictHandling:
    """Tests for conflict detection and handling."""

    def test_has_conflicts_false_normally(self, git_repo_with_branches: Path) -> None:
        """Test has_conflicts returns False normally."""
        ops = GitOps(git_repo_with_branches)

        assert ops.has_conflicts() is False

    def test_get_conflicting_files_empty_normally(self, git_repo_with_branches: Path) -> None:
        """Test get_conflicting_files returns empty list normally."""
        ops = GitOps(git_repo_with_branches)

        files = ops.get_conflicting_files()

        assert files == []

    def test_abort_rebase(self, git_repo_with_branches: Path) -> None:
        """Test aborting a rebase."""
        ops = GitOps(git_repo_with_branches)

        # Create rebase conflict scenario
        ops.checkout("feature-1")
        (git_repo_with_branches / "README.md").write_text("# Feature change")
        ops.commit("Change README", add_all=True)

        main_branch = "main" if ops.branch_exists("main") else "master"
        ops.checkout(main_branch)
        (git_repo_with_branches / "README.md").write_text("# Main change")
        ops.commit("Change README on main", add_all=True)

        ops.checkout("feature-1")

        # Try rebase which will conflict
        try:
            ops.rebase(main_branch)
        except GitError:
            ops.abort_rebase()

        # Should be back to original state
        assert not ops.has_conflicts()
