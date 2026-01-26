"""Tests for zerg.worktree module."""

from pathlib import Path

import pytest

from zerg.exceptions import WorktreeError
from zerg.worktree import WorktreeInfo, WorktreeManager


class TestWorktreeManager:
    """Tests for WorktreeManager class."""

    def test_create_manager(self, tmp_repo: Path) -> None:
        """Test creating a WorktreeManager."""
        manager = WorktreeManager(tmp_repo)

        assert manager is not None
        assert manager.repo_path == tmp_repo

    def test_create_manager_invalid_repo(self, tmp_path: Path) -> None:
        """Test creating manager with invalid repo raises error."""
        with pytest.raises(WorktreeError):
            WorktreeManager(tmp_path)

    def test_worktree_path(self, tmp_repo: Path) -> None:
        """Test getting worktree path."""
        manager = WorktreeManager(tmp_repo)

        path = manager.get_worktree_path("test-feature", 0)

        assert "test-feature" in str(path)
        assert "worker-0" in str(path)

    def test_branch_name(self, tmp_repo: Path) -> None:
        """Test getting branch name."""
        manager = WorktreeManager(tmp_repo)

        branch = manager.get_branch_name("test-feature", 1)

        assert "test-feature" in branch
        assert "worker-1" in branch
        assert branch == "zerg/test-feature/worker-1"

    def test_create_worktree(self, tmp_repo: Path) -> None:
        """Test creating a worktree."""
        manager = WorktreeManager(tmp_repo)

        wt = manager.create("test-feature", 0)

        assert wt is not None
        assert wt.path.exists()
        assert "worker-0" in str(wt.path)
        assert wt.branch == "zerg/test-feature/worker-0"

    def test_exists(self, tmp_repo: Path) -> None:
        """Test checking if worktree exists."""
        manager = WorktreeManager(tmp_repo)

        wt = manager.create("exists-test", 0)

        assert manager.exists(wt.path) is True
        assert manager.exists(tmp_repo / "nonexistent") is False

    def test_delete_worktree(self, tmp_repo: Path) -> None:
        """Test deleting a worktree."""
        manager = WorktreeManager(tmp_repo)
        wt = manager.create("delete-test", 0)
        wt_path = wt.path

        manager.delete(wt_path)

        assert not manager.exists(wt_path)

    def test_delete_worktree_force(self, tmp_repo: Path) -> None:
        """Test force deleting a worktree."""
        manager = WorktreeManager(tmp_repo)
        wt = manager.create("force-delete-test", 0)

        # Create uncommitted change
        (wt.path / "uncommitted.txt").write_text("uncommitted")

        manager.delete(wt.path, force=True)

        assert not manager.exists(wt.path)

    def test_list_worktrees(self, tmp_repo: Path) -> None:
        """Test listing worktrees."""
        manager = WorktreeManager(tmp_repo)

        worktrees = manager.list_worktrees()

        assert isinstance(worktrees, list)
        # At minimum, the main repo should show up
        assert len(worktrees) >= 1

    def test_list_worktrees_with_created(self, tmp_repo: Path) -> None:
        """Test listing worktrees includes created ones."""
        manager = WorktreeManager(tmp_repo)
        manager.create("list-test", 0)
        manager.create("list-test", 1)

        worktrees = manager.list_worktrees()

        # Should have main repo + 2 created worktrees
        assert len(worktrees) >= 3

    def test_get_worktree(self, tmp_repo: Path) -> None:
        """Test getting a specific worktree by path."""
        manager = WorktreeManager(tmp_repo)
        wt = manager.create("get-test", 0)

        found = manager.get_worktree(wt.path)

        assert found is not None
        assert found.path == wt.path
        assert found.branch == wt.branch

    def test_get_worktree_not_found(self, tmp_repo: Path) -> None:
        """Test getting a worktree that doesn't exist."""
        manager = WorktreeManager(tmp_repo)

        found = manager.get_worktree(tmp_repo / "nonexistent")

        assert found is None

    def test_delete_all(self, tmp_repo: Path) -> None:
        """Test deleting all worktrees for a feature."""
        manager = WorktreeManager(tmp_repo)
        manager.create("delete-all-test", 0)
        manager.create("delete-all-test", 1)
        manager.create("delete-all-test", 2)

        count = manager.delete_all("delete-all-test")

        assert count == 3

    def test_prune(self, tmp_repo: Path) -> None:
        """Test pruning stale worktree references."""
        manager = WorktreeManager(tmp_repo)

        # This should not raise
        manager.prune()


class TestWorktreeInfo:
    """Tests for WorktreeInfo dataclass."""

    def test_create_worktree_info(self, tmp_path: Path) -> None:
        """Test creating WorktreeInfo."""
        info = WorktreeInfo(
            path=tmp_path,
            branch="test-branch",
            commit="abc123",
        )

        assert info.path == tmp_path
        assert info.branch == "test-branch"
        assert info.commit == "abc123"

    def test_worktree_info_defaults(self, tmp_path: Path) -> None:
        """Test WorktreeInfo default values."""
        info = WorktreeInfo(
            path=tmp_path,
            branch="test",
            commit="abc",
        )

        assert info.is_bare is False
        assert info.is_detached is False

    def test_worktree_info_name(self, tmp_path: Path) -> None:
        """Test WorktreeInfo name property."""
        wt_path = tmp_path / "my-worktree"
        wt_path.mkdir()
        info = WorktreeInfo(
            path=wt_path,
            branch="test",
            commit="abc",
        )

        assert info.name == "my-worktree"
