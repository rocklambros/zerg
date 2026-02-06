"""Unit tests for worktree.py."""

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.exceptions import WorktreeError
from zerg.worktree import WorktreeInfo, WorktreeManager


class TestWorktreeInfo:
    """Tests for WorktreeInfo dataclass."""

    def test_properties_and_defaults(self) -> None:
        """Test name property and default values."""
        info = WorktreeInfo(
            path=Path("/tmp/worktrees/feature/worker-0"),
            branch="zerg/feature/worker-0",
            commit="abc123",
        )
        assert info.name == "worker-0"
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


class TestRunGit:
    """Tests for _run_git method."""

    def test_run_git_success(self, tmp_repo: Path) -> None:
        """Test successful git command execution."""
        manager = WorktreeManager(tmp_repo)
        assert manager._run_git("status").returncode == 0

    def test_run_git_failure_raises_error(self, tmp_repo: Path) -> None:
        """Test failed git command raises WorktreeError."""
        manager = WorktreeManager(tmp_repo)
        with pytest.raises(WorktreeError):
            manager._run_git("nonexistent-command")


class TestListWorktrees:
    """Tests for listing worktrees."""

    def test_list_worktrees_main_only(self, tmp_repo: Path) -> None:
        """Test listing worktrees shows main only initially."""
        manager = WorktreeManager(tmp_repo)
        worktrees = manager.list_worktrees()
        assert len(worktrees) >= 1
        assert worktrees[0].path == tmp_repo

    def test_list_worktrees_handles_bare(self, tmp_repo: Path) -> None:
        """Test parsing handles bare worktree indication."""
        manager = WorktreeManager(tmp_repo)
        with patch.object(manager, "_run_git") as mock_git:
            mock_result = MagicMock()
            mock_result.stdout = "worktree /tmp/bare\nHEAD abc123\nbare\n"
            mock_git.return_value = mock_result
            worktrees = manager.list_worktrees()
            assert worktrees[0].is_bare is True


class TestParseWorktreeInfo:
    """Tests for parsing worktree info from git output."""

    def test_parse_simple_worktree(self, tmp_repo: Path) -> None:
        """Test parsing simple worktree data."""
        manager = WorktreeManager(tmp_repo)
        data = {"path": "/tmp/worktree", "commit": "abc123", "branch": "refs/heads/main"}
        info = manager._parse_worktree_info(data)
        assert info.path == Path("/tmp/worktree")
        assert info.branch == "main"

    def test_parse_detached_worktree(self, tmp_repo: Path) -> None:
        """Test parsing detached HEAD worktree."""
        manager = WorktreeManager(tmp_repo)
        data = {"path": "/tmp/worktree", "commit": "abc123", "detached": "true"}
        info = manager._parse_worktree_info(data)
        assert info.is_detached is True
        assert info.branch == ""


class TestWorktreeExistence:
    """Tests for worktree existence checking."""

    def test_exists(self, tmp_repo: Path) -> None:
        """Test exists returns True/False correctly."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("test-feature", 0)
        assert manager.exists(info.path) is True
        assert manager.exists(tmp_repo / "nonexistent") is False


class TestBranchNaming:
    """Tests for branch and path name generation."""

    def test_get_branch_and_worktree_path(self, tmp_repo: Path) -> None:
        """Test branch name and worktree path generation."""
        manager = WorktreeManager(tmp_repo)
        assert manager.get_branch_name("my-feature", 5) == "zerg/my-feature/worker-5"
        expected = tmp_repo / ".zerg-worktrees" / "my-feature" / "worker-5"
        assert manager.get_worktree_path("my-feature", 5) == expected


class TestWorktreeCreation:
    """Tests for worktree creation."""

    def test_create_worktree(self, tmp_repo: Path) -> None:
        """Test creating a worktree."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("test-feature", 0)
        assert info.path.exists()
        assert info.branch == "zerg/test-feature/worker-0"
        expected_path = tmp_repo / ".zerg-worktrees" / "test-feature" / "worker-0"
        assert info.path == expected_path

    def test_create_worktree_replaces_existing(self, tmp_repo: Path) -> None:
        """Test creating worktree replaces existing one."""
        manager = WorktreeManager(tmp_repo)
        info1 = manager.create("test-feature", 0)
        (info1.path / "test.txt").write_text("test")
        info2 = manager.create("test-feature", 0)
        assert not (info2.path / "test.txt").exists()


class TestWorktreeDeletion:
    """Tests for worktree deletion."""

    def test_delete_worktree(self, tmp_repo: Path) -> None:
        """Test deleting a worktree."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("test-feature", 0)
        manager.delete(info.path)
        assert not info.path.exists()

    def test_delete_all_worktrees(self, tmp_repo: Path) -> None:
        """Test deleting all worktrees for a feature."""
        manager = WorktreeManager(tmp_repo)
        manager.create("test-feature", 0)
        manager.create("test-feature", 1)
        manager.create("test-feature", 2)
        count = manager.delete_all("test-feature")
        assert count == 3
        feature_dir = tmp_repo / ".zerg-worktrees" / "test-feature"
        assert not feature_dir.exists()


class TestWorktreeRetrieval:
    """Tests for getting worktree info."""

    def test_get_worktree(self, tmp_repo: Path) -> None:
        """Test getting worktree info by path (found and not found)."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("test-feature", 0)
        retrieved = manager.get_worktree(info.path)
        assert retrieved is not None
        assert retrieved.branch == info.branch
        assert manager.get_worktree(tmp_repo / "nonexistent") is None


class TestWorktreePruning:
    """Tests for worktree pruning."""

    def test_prune(self, tmp_repo: Path) -> None:
        """Test pruning stale worktrees."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("test-feature", 0)
        shutil.rmtree(info.path)
        manager.prune()


class TestWorktreeSync:
    """Tests for worktree synchronization."""

    def test_sync_with_base_success(self, tmp_repo: Path) -> None:
        """Test sync_with_base succeeds when mocked."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("test-feature", 0)
        mock_result = MagicMock(returncode=0)

        with patch("zerg.worktree.subprocess.run", return_value=mock_result) as mock_run:
            manager.sync_with_base(info.path, base_branch="main")
            assert mock_run.call_count == 2
            assert "fetch" in mock_run.call_args_list[0][0][0]
            assert "rebase" in mock_run.call_args_list[1][0][0]


class TestGetHeadCommit:
    """Tests for _get_head_commit method."""

    def test_get_head_commit(self, tmp_repo: Path) -> None:
        """Test getting HEAD commit of worktree."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("test-feature", 0)
        commit = manager._get_head_commit(info.path)
        assert len(commit) == 40
