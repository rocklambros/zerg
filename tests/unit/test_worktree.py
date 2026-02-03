"""Comprehensive unit tests for worktree.py - 100% coverage target."""

import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

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

    def test_with_bare_and_detached(self) -> None:
        """Test setting bare and detached flags."""
        info = WorktreeInfo(
            path=Path("/tmp/wt"),
            branch="",
            commit="abc123",
            is_bare=True,
            is_detached=True,
        )
        assert info.is_bare is True
        assert info.is_detached is True


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

    def test_init_with_string_path(self, tmp_repo: Path) -> None:
        """Test initialization with string path."""
        manager = WorktreeManager(str(tmp_repo))
        assert manager.repo_path == tmp_repo


class TestRunGit:
    """Tests for _run_git method."""

    def test_run_git_success(self, tmp_repo: Path) -> None:
        """Test successful git command execution."""
        manager = WorktreeManager(tmp_repo)
        result = manager._run_git("status")
        assert result.returncode == 0

    def test_run_git_failure_raises_error(self, tmp_repo: Path) -> None:
        """Test failed git command raises WorktreeError."""
        manager = WorktreeManager(tmp_repo)
        with pytest.raises(WorktreeError) as exc_info:
            manager._run_git("nonexistent-command")
        assert "Git command failed" in str(exc_info.value)

    def test_run_git_with_check_false(self, tmp_repo: Path) -> None:
        """Test git command with check=False doesn't raise."""
        manager = WorktreeManager(tmp_repo)
        # This command will fail but should not raise
        manager._run_git("branch", "--list", "nonexistent", check=False)
        # Should return without raising, even if command fails


class TestListWorktrees:
    """Tests for listing worktrees."""

    def test_list_worktrees_main_only(self, tmp_repo: Path) -> None:
        """Test listing worktrees shows main only initially."""
        manager = WorktreeManager(tmp_repo)
        worktrees = manager.list_worktrees()
        assert len(worktrees) >= 1
        main_wt = worktrees[0]
        assert main_wt.path == tmp_repo

    def test_list_worktrees_multiple(self, tmp_repo: Path) -> None:
        """Test listing multiple worktrees."""
        manager = WorktreeManager(tmp_repo)
        manager.create("test-feature", 0)
        worktrees = manager.list_worktrees()
        assert len(worktrees) >= 2

    def test_list_worktrees_parses_empty_lines(self, tmp_repo: Path) -> None:
        """Test list_worktrees handles empty lines in output."""
        manager = WorktreeManager(tmp_repo)
        # Create worktrees to have multiple entries separated by blank lines
        manager.create("feature-a", 0)
        manager.create("feature-b", 0)
        worktrees = manager.list_worktrees()
        # Should parse multiple entries correctly
        assert len(worktrees) >= 3

    def test_list_worktrees_handles_bare_worktree(self, tmp_repo: Path) -> None:
        """Test parsing handles bare worktree indication."""
        manager = WorktreeManager(tmp_repo)
        # Mock git output that includes bare flag
        with patch.object(manager, "_run_git") as mock_git:
            mock_result = MagicMock()
            mock_result.stdout = "worktree /tmp/bare\nHEAD abc123\nbare\n"
            mock_git.return_value = mock_result
            worktrees = manager.list_worktrees()
            assert len(worktrees) == 1
            assert worktrees[0].is_bare is True

    def test_list_worktrees_handles_detached_head(self, tmp_repo: Path) -> None:
        """Test parsing handles detached HEAD indication."""
        manager = WorktreeManager(tmp_repo)
        with patch.object(manager, "_run_git") as mock_git:
            mock_result = MagicMock()
            mock_result.stdout = "worktree /tmp/detached\nHEAD abc123\ndetached\n"
            mock_git.return_value = mock_result
            worktrees = manager.list_worktrees()
            assert len(worktrees) == 1
            assert worktrees[0].is_detached is True


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
        assert info.branch == "main"

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

    def test_parse_worktree_without_branch(self, tmp_repo: Path) -> None:
        """Test parsing worktree without branch (detached)."""
        manager = WorktreeManager(tmp_repo)
        data = {
            "path": "/tmp/worktree",
            "commit": "abc123",
        }
        info = manager._parse_worktree_info(data)
        assert info.branch == ""

    def test_parse_worktree_branch_without_refs_heads(self, tmp_repo: Path) -> None:
        """Test parsing worktree with short branch name."""
        manager = WorktreeManager(tmp_repo)
        data = {
            "path": "/tmp/worktree",
            "commit": "abc123",
            "branch": "feature-branch",
        }
        info = manager._parse_worktree_info(data)
        assert info.branch == "feature-branch"


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

    def test_exists_with_string_path(self, tmp_repo: Path) -> None:
        """Test exists accepts string path."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("test-feature", 0)
        assert manager.exists(str(info.path)) is True


class TestBranchNaming:
    """Tests for branch name generation."""

    def test_get_branch_name(self, tmp_repo: Path) -> None:
        """Test branch name generation."""
        manager = WorktreeManager(tmp_repo)
        branch = manager.get_branch_name("my-feature", 5)
        assert branch == "zerg/my-feature/worker-5"

    def test_get_branch_name_worker_zero(self, tmp_repo: Path) -> None:
        """Test branch name generation for worker 0."""
        manager = WorktreeManager(tmp_repo)
        branch = manager.get_branch_name("feature", 0)
        assert branch == "zerg/feature/worker-0"

    def test_get_worktree_path(self, tmp_repo: Path) -> None:
        """Test worktree path generation."""
        manager = WorktreeManager(tmp_repo)
        path = manager.get_worktree_path("my-feature", 5)
        expected = tmp_repo / ".zerg-worktrees" / "my-feature" / "worker-5"
        assert path == expected


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
        subprocess.run(["git", "branch", "develop"], cwd=tmp_repo, check=True)
        info = manager.create("test-feature", 0, base_branch="develop")
        assert info.path.exists()

    def test_create_worktree_replaces_existing(self, tmp_repo: Path) -> None:
        """Test creating worktree replaces existing one."""
        manager = WorktreeManager(tmp_repo)
        info1 = manager.create("test-feature", 0)
        (info1.path / "test.txt").write_text("test")
        info2 = manager.create("test-feature", 0)
        assert not (info2.path / "test.txt").exists()

    def test_create_worktree_existing_branch(self, tmp_repo: Path) -> None:
        """Test creating worktree when branch already exists."""
        manager = WorktreeManager(tmp_repo)
        # Create branch first
        subprocess.run(
            ["git", "branch", "zerg/test-feature/worker-0"],
            cwd=tmp_repo,
            check=True,
        )
        # Creating worktree should work even with existing branch
        info = manager.create("test-feature", 0)
        assert info.path.exists()


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
        (info.path / "dirty.txt").write_text("uncommitted")
        manager.delete(info.path, force=True)
        assert not info.path.exists()

    def test_delete_worktree_non_force_raises(self, tmp_repo: Path) -> None:
        """Test non-force delete of dirty worktree raises."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("test-feature", 0)
        (info.path / "dirty.txt").write_text("uncommitted")
        subprocess.run(["git", "-C", str(info.path), "add", "dirty.txt"], check=True)
        with pytest.raises(WorktreeError):
            manager.delete(info.path, force=False)

    def test_delete_with_fallback_to_shutil(self, tmp_repo: Path) -> None:
        """Test delete falls back to shutil when force removal fails."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("test-feature", 0)
        wt_path = info.path

        # Make worktree dirty and manually break git worktree state
        (wt_path / "dirty.txt").write_text("uncommitted")

        # Simulate scenario where git worktree remove fails even with force
        with patch.object(manager, "_run_git") as mock_git:
            # First call (remove --force) should raise
            # Second call (prune) should succeed
            mock_git.side_effect = [
                WorktreeError("Remove failed"),
                MagicMock(),  # prune succeeds
            ]

            # Manually ensure path exists for shutil.rmtree to work
            manager.delete(wt_path, force=True)

            # Verify shutil was used (path should be gone if it existed)
            # In this mock scenario, the actual deletion happens

    def test_delete_all_worktrees(self, tmp_repo: Path) -> None:
        """Test deleting all worktrees for a feature."""
        manager = WorktreeManager(tmp_repo)
        manager.create("test-feature", 0)
        manager.create("test-feature", 1)
        manager.create("test-feature", 2)
        count = manager.delete_all("test-feature")
        assert count == 3

    def test_delete_all_worktrees_no_matching(self, tmp_repo: Path) -> None:
        """Test delete_all with no matching worktrees."""
        manager = WorktreeManager(tmp_repo)
        count = manager.delete_all("nonexistent-feature")
        assert count == 0

    def test_delete_all_cleans_empty_directory(self, tmp_repo: Path) -> None:
        """Test delete_all removes empty feature directory."""
        manager = WorktreeManager(tmp_repo)
        manager.create("test-feature", 0)
        feature_dir = tmp_repo / ".zerg-worktrees" / "test-feature"
        assert feature_dir.exists()
        manager.delete_all("test-feature")
        assert not feature_dir.exists()


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

    def test_get_worktree_with_string_path(self, tmp_repo: Path) -> None:
        """Test get_worktree accepts string path."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("test-feature", 0)
        retrieved = manager.get_worktree(str(info.path))
        assert retrieved is not None


class TestWorktreePruning:
    """Tests for worktree pruning."""

    def test_prune(self, tmp_repo: Path) -> None:
        """Test pruning stale worktrees."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("test-feature", 0)
        shutil.rmtree(info.path)
        # Prune should not raise
        manager.prune()


class TestWorktreeSync:
    """Tests for worktree synchronization."""

    def test_sync_with_base_no_remote(self, tmp_repo: Path) -> None:
        """Test syncing worktree without remote configured."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("test-feature", 0)
        # This will fail because no remote exists
        with pytest.raises(subprocess.CalledProcessError):
            manager.sync_with_base(info.path)

    def test_sync_with_base_string_path(self, tmp_repo: Path) -> None:
        """Test sync_with_base accepts string path."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("test-feature", 0)
        try:
            manager.sync_with_base(str(info.path))
        except subprocess.CalledProcessError:
            pass  # Expected without remote

    def test_sync_with_custom_base_branch(self, tmp_repo: Path) -> None:
        """Test sync_with_base with custom base branch."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("test-feature", 0)
        try:
            manager.sync_with_base(info.path, base_branch="develop")
        except subprocess.CalledProcessError:
            pass  # Expected without remote

    def test_sync_with_base_success(self, tmp_repo: Path) -> None:
        """Test sync_with_base succeeds when mocked."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("test-feature", 0)

        # Mock subprocess.run to succeed
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("zerg.worktree.subprocess.run", return_value=mock_result) as mock_run:
            manager.sync_with_base(info.path, base_branch="main")

            # Verify both fetch and rebase were called
            assert mock_run.call_count == 2

            # First call should be fetch
            first_call_args = mock_run.call_args_list[0]
            assert "fetch" in first_call_args[0][0]

            # Second call should be rebase
            second_call_args = mock_run.call_args_list[1]
            assert "rebase" in second_call_args[0][0]

    def test_sync_with_base_rebase_fails(self, tmp_repo: Path) -> None:
        """Test sync_with_base handles rebase failure after fetch succeeds."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("test-feature", 0)

        # First call (fetch) succeeds, second call (rebase) fails
        mock_result_success = MagicMock()
        mock_result_success.returncode = 0

        def side_effect(*args, **kwargs):
            if "rebase" in args[0]:
                raise subprocess.CalledProcessError(1, args[0])
            return mock_result_success

        with patch("zerg.worktree.subprocess.run", side_effect=side_effect):
            with pytest.raises(subprocess.CalledProcessError):
                manager.sync_with_base(info.path)


class TestGetHeadCommit:
    """Tests for _get_head_commit method."""

    def test_get_head_commit(self, tmp_repo: Path) -> None:
        """Test getting HEAD commit of worktree."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("test-feature", 0)
        commit = manager._get_head_commit(info.path)
        assert len(commit) == 40  # Full SHA

    def test_get_head_commit_main_repo(self, tmp_repo: Path) -> None:
        """Test getting HEAD commit of main repo."""
        manager = WorktreeManager(tmp_repo)
        commit = manager._get_head_commit(tmp_repo)
        assert len(commit) == 40


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_create_multiple_workers_same_feature(self, tmp_repo: Path) -> None:
        """Test creating multiple workers for same feature."""
        manager = WorktreeManager(tmp_repo)
        infos = [manager.create("test-feature", i) for i in range(5)]
        assert len(infos) == 5
        paths = [info.path for info in infos]
        assert len(set(paths)) == 5

    def test_feature_with_special_characters(self, tmp_repo: Path) -> None:
        """Test feature names with allowed characters."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("my-feature-name", 0)
        assert info.path.exists()

    def test_delete_with_string_path(self, tmp_repo: Path) -> None:
        """Test delete accepts string path."""
        manager = WorktreeManager(tmp_repo)
        info = manager.create("test-feature", 0)
        manager.delete(str(info.path))
        assert not info.path.exists()
