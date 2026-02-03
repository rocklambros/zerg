"""Extended tests for ZERG worktree management (TC-014).

Tests worktree creation, deletion, synchronization, and edge cases.
"""

import subprocess
from pathlib import Path

import pytest

from zerg.exceptions import WorktreeError
from zerg.worktree import WorktreeInfo, WorktreeManager


class TestWorktreeInfo:
    """Tests for WorktreeInfo dataclass."""

    def test_name_property(self) -> None:
        """Test name property extracts path name."""
        info = WorktreeInfo(
            path=Path("/tmp/worktrees/feature/worker-0"),
            branch="zerg/feature/worker-0",
            commit="abc123",
        )

        assert info.name == "worker-0"

    def test_default_values(self) -> None:
        """Test default values for optional fields."""
        info = WorktreeInfo(
            path=Path("/tmp/wt"),
            branch="main",
            commit="abc123",
        )

        assert info.is_bare is False
        assert info.is_detached is False


class TestWorktreeManagerInit:
    """Tests for WorktreeManager initialization."""

    def test_init_with_valid_repo(self, tmp_repo: Path) -> None:
        """Test initialization with valid repository."""
        manager = WorktreeManager(tmp_repo)

        assert manager.repo_path == tmp_repo

    def test_init_with_invalid_repo(self, tmp_path: Path) -> None:
        """Test initialization with non-git directory."""
        with pytest.raises(WorktreeError) as exc_info:
            WorktreeManager(tmp_path)

        assert "Not a git repository" in str(exc_info.value)

    def test_init_resolves_path(self, tmp_repo: Path) -> None:
        """Test initialization resolves relative paths."""
        manager = WorktreeManager(".")

        assert manager.repo_path.is_absolute()


class TestListWorktrees:
    """Tests for listing worktrees."""

    def test_list_worktrees_main_only(self, tmp_repo: Path) -> None:
        """Test listing worktrees shows main only initially."""
        manager = WorktreeManager(tmp_repo)

        worktrees = manager.list_worktrees()

        # At least the main worktree should exist
        assert len(worktrees) >= 1
        main_wt = worktrees[0]
        assert main_wt.path == tmp_repo

    def test_list_worktrees_multiple(self, tmp_repo: Path) -> None:
        """Test listing multiple worktrees."""
        manager = WorktreeManager(tmp_repo)

        # Create additional worktree
        manager.create("test-feature", 0)

        worktrees = manager.list_worktrees()

        assert len(worktrees) >= 2


class TestWorktreeCreation:
    """Tests for worktree creation."""

    def test_create_worktree(self, tmp_repo: Path) -> None:
        """Test creating a worktree."""
        manager = WorktreeManager(tmp_repo)

        info = manager.create("test-feature", 0)

        assert info.path.exists()
        assert info.branch == "zerg/test-feature/worker-0"
        assert info.commit

    def test_create_worktree_creates_branch(self, tmp_repo: Path) -> None:
        """Test creating worktree creates the branch."""
        manager = WorktreeManager(tmp_repo)

        manager.create("test-feature", 0)

        # Check branch exists
        result = subprocess.run(
            ["git", "branch", "--list", "zerg/test-feature/worker-0"],
            cwd=tmp_repo,
            capture_output=True,
            text=True,
        )
        assert "zerg/test-feature/worker-0" in result.stdout

    def test_create_worktree_in_expected_location(self, tmp_repo: Path) -> None:
        """Test worktree is created in expected directory."""
        manager = WorktreeManager(tmp_repo)

        info = manager.create("test-feature", 0)

        expected_path = tmp_repo / ".zerg-worktrees" / "test-feature" / "worker-0"
        assert info.path == expected_path

    def test_create_worktree_custom_base_branch(self, tmp_repo: Path) -> None:
        """Test creating worktree from custom base branch."""
        manager = WorktreeManager(tmp_repo)

        # First create a develop branch
        subprocess.run(
            ["git", "branch", "develop"],
            cwd=tmp_repo,
            check=True,
        )

        info = manager.create("test-feature", 0, base_branch="develop")

        assert info.path.exists()

    def test_create_worktree_replaces_existing(self, tmp_repo: Path) -> None:
        """Test creating worktree replaces existing one."""
        manager = WorktreeManager(tmp_repo)

        # Create first worktree
        info1 = manager.create("test-feature", 0)

        # Create file in worktree
        (info1.path / "test.txt").write_text("test")

        # Create again (should replace)
        info2 = manager.create("test-feature", 0)

        # File should not exist
        assert not (info2.path / "test.txt").exists()


class TestWorktreeDeletion:
    """Tests for worktree deletion."""

    def test_delete_worktree(self, tmp_repo: Path) -> None:
        """Test deleting a worktree."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("test-feature", 0)

        manager.delete(info.path)

        assert not info.path.exists()

    def test_delete_worktree_force(self, tmp_repo: Path) -> None:
        """Test force deleting a dirty worktree."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("test-feature", 0)

        # Make worktree dirty
        (info.path / "dirty.txt").write_text("uncommitted")

        manager.delete(info.path, force=True)

        assert not info.path.exists()

    def test_delete_all_worktrees(self, tmp_repo: Path) -> None:
        """Test deleting all worktrees for a feature."""
        manager = WorktreeManager(tmp_repo)

        # Create multiple worktrees
        manager.create("test-feature", 0)
        manager.create("test-feature", 1)
        manager.create("test-feature", 2)

        count = manager.delete_all("test-feature")

        assert count == 3

        # Verify all deleted
        feature_dir = tmp_repo / ".zerg" / "worktrees" / "test-feature"
        assert not feature_dir.exists() or not any(feature_dir.iterdir())


class TestWorktreeExistence:
    """Tests for worktree existence checking."""

    def test_exists_true(self, tmp_repo: Path) -> None:
        """Test exists returns True for existing worktree."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("test-feature", 0)

        assert manager.exists(info.path) is True

    def test_exists_false(self, tmp_repo: Path) -> None:
        """Test exists returns False for non-existing path."""
        manager = WorktreeManager(tmp_repo)

        assert manager.exists(tmp_repo / "nonexistent") is False


class TestBranchNaming:
    """Tests for branch name generation."""

    def test_get_branch_name(self, tmp_repo: Path) -> None:
        """Test branch name generation."""
        manager = WorktreeManager(tmp_repo)

        branch = manager.get_branch_name("my-feature", 5)

        assert branch == "zerg/my-feature/worker-5"

    def test_get_worktree_path(self, tmp_repo: Path) -> None:
        """Test worktree path generation."""
        manager = WorktreeManager(tmp_repo)

        path = manager.get_worktree_path("my-feature", 5)

        expected = tmp_repo / ".zerg-worktrees" / "my-feature" / "worker-5"
        assert path == expected


class TestWorktreeRetrieval:
    """Tests for getting worktree info."""

    def test_get_worktree_found(self, tmp_repo: Path) -> None:
        """Test getting worktree info by path."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("test-feature", 0)

        retrieved = manager.get_worktree(info.path)

        assert retrieved is not None
        assert retrieved.branch == info.branch

    def test_get_worktree_not_found(self, tmp_repo: Path) -> None:
        """Test getting worktree info for non-existing path."""
        manager = WorktreeManager(tmp_repo)

        retrieved = manager.get_worktree(tmp_repo / "nonexistent")

        assert retrieved is None


class TestWorktreePruning:
    """Tests for worktree pruning."""

    def test_prune(self, tmp_repo: Path) -> None:
        """Test pruning stale worktrees."""
        manager = WorktreeManager(tmp_repo)

        # Create and manually delete directory (leaving stale reference)
        info = manager.create("test-feature", 0)
        import shutil

        shutil.rmtree(info.path)

        # Prune should not raise
        manager.prune()


class TestWorktreeSync:
    """Tests for worktree synchronization."""

    def test_sync_with_base(self, tmp_repo: Path) -> None:
        """Test syncing worktree with base branch."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("test-feature", 0)

        # This would fail without a remote, so we test it doesn't crash
        # on a local repo setup
        try:
            manager.sync_with_base(info.path)
        except subprocess.CalledProcessError:
            # Expected - no remote configured
            pass


class TestParseWorktreeInfo:
    """Tests for parsing worktree info from git output."""

    def test_parse_simple_worktree(self, tmp_repo: Path) -> None:
        """Test parsing simple worktree data."""
        manager = WorktreeManager(tmp_repo)

        data = {
            "path": "/tmp/worktree",
            "commit": "abc123",
            "branch": "refs/heads/main",
        }

        info = manager._parse_worktree_info(data)

        assert info.path == Path("/tmp/worktree")
        assert info.commit == "abc123"
        assert info.branch == "main"  # refs/heads/ stripped

    def test_parse_bare_worktree(self, tmp_repo: Path) -> None:
        """Test parsing bare worktree."""
        manager = WorktreeManager(tmp_repo)

        data = {
            "path": "/tmp/worktree",
            "commit": "abc123",
            "bare": "true",
        }

        info = manager._parse_worktree_info(data)

        assert info.is_bare is True

    def test_parse_detached_worktree(self, tmp_repo: Path) -> None:
        """Test parsing detached HEAD worktree."""
        manager = WorktreeManager(tmp_repo)

        data = {
            "path": "/tmp/worktree",
            "commit": "abc123",
            "detached": "true",
        }

        info = manager._parse_worktree_info(data)

        assert info.is_detached is True


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_create_multiple_workers_same_feature(self, tmp_repo: Path) -> None:
        """Test creating multiple workers for same feature."""
        manager = WorktreeManager(tmp_repo)

        infos = [manager.create("test-feature", i) for i in range(5)]

        assert len(infos) == 5
        paths = [info.path for info in infos]
        assert len(set(paths)) == 5  # All unique paths

    def test_feature_with_special_characters(self, tmp_repo: Path) -> None:
        """Test feature names with allowed characters."""
        manager = WorktreeManager(tmp_repo)

        # Hyphenated feature name
        info = manager.create("my-feature-name", 0)

        assert info.path.exists()

    def test_get_head_commit(self, tmp_repo: Path) -> None:
        """Test getting HEAD commit of worktree."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("test-feature", 0)

        commit = manager._get_head_commit(info.path)

        assert len(commit) == 40  # Full SHA
