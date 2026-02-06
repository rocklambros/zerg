"""Tests for ZERG git_ops module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.exceptions import GitError, MergeConflictError
from zerg.git_ops import BranchInfo, GitOps


class TestGitOpsInit:
    def test_init_valid_and_string(self, tmp_repo: Path) -> None:
        ops = GitOps(tmp_repo)
        assert ops.repo_path == tmp_repo
        ops2 = GitOps(str(tmp_repo))
        assert ops2.repo_path == tmp_repo

    def test_init_invalid_repo(self, tmp_path: Path) -> None:
        with pytest.raises(GitError) as exc_info:
            GitOps(tmp_path)
        assert "Not a git repository" in str(exc_info.value)


class TestGitOpsRun:
    def test_run_success_and_failure(self, tmp_repo: Path) -> None:
        ops = GitOps(tmp_repo)
        assert ops._run("status").returncode == 0
        with pytest.raises(GitError):
            ops._run("checkout", "nonexistent-branch")

    def test_run_no_check(self, tmp_repo: Path) -> None:
        ops = GitOps(tmp_repo)
        result = ops._run("checkout", "nonexistent-branch", check=False)
        assert result.returncode != 0


class TestGitOpsBranch:
    def test_current_branch_and_commit(self, tmp_repo: Path) -> None:
        ops = GitOps(tmp_repo)
        assert isinstance(ops.current_branch(), str) and ops.current_branch()
        assert len(ops.current_commit()) == 40

    def test_branch_lifecycle(self, tmp_repo: Path) -> None:
        ops = GitOps(tmp_repo)
        ops.create_branch("test-branch")
        assert ops.branch_exists("test-branch")
        ops.delete_branch("test-branch")
        assert not ops.branch_exists("test-branch")

    def test_checkout(self, tmp_repo: Path) -> None:
        ops = GitOps(tmp_repo)
        ops.create_branch("checkout-test")
        ops.checkout("checkout-test")
        assert ops.current_branch() == "checkout-test"


class TestGitOpsChanges:
    def test_has_changes(self, tmp_repo: Path) -> None:
        ops = GitOps(tmp_repo)
        assert ops.has_changes() is False
        (tmp_repo / "new-file.txt").write_text("content")
        assert ops.has_changes() is True

    def test_has_conflicts_false(self, tmp_repo: Path) -> None:
        ops = GitOps(tmp_repo)
        assert ops.has_conflicts() is False and ops.get_conflicting_files() == []


class TestGitOpsCommit:
    def test_commit_basic(self, tmp_repo: Path) -> None:
        ops = GitOps(tmp_repo)
        (tmp_repo / "test.txt").write_text("content")
        commit = ops.commit("Test commit", add_all=True)
        assert len(commit) == 40 and not ops.has_changes()

    def test_commit_allow_empty(self, tmp_repo: Path) -> None:
        ops = GitOps(tmp_repo)
        assert len(ops.commit("Empty commit", allow_empty=True)) == 40


class TestGitOpsMerge:
    def test_merge_basic(self, tmp_repo: Path) -> None:
        ops = GitOps(tmp_repo)
        original = ops.current_branch()
        ops.create_branch("feature")
        ops.checkout("feature")
        (tmp_repo / "feature.txt").write_text("feature content")
        ops.commit("Add feature", add_all=True)
        ops.checkout(original)
        assert len(ops.merge("feature", message="Merge feature")) == 40

    def test_merge_conflict(self, tmp_repo: Path) -> None:
        ops = GitOps(tmp_repo)
        original = ops.current_branch()
        ops.create_branch("conflict")
        ops.checkout("conflict")
        (tmp_repo / "README.md").write_text("conflict content")
        ops.commit("Conflict change", add_all=True)
        ops.checkout(original)
        (tmp_repo / "README.md").write_text("main content")
        ops.commit("Main change", add_all=True)
        with pytest.raises(MergeConflictError) as exc_info:
            ops.merge("conflict")
        assert "README.md" in exc_info.value.conflicting_files


class TestGitOpsStagingBranch:
    def test_create_staging_branch(self, tmp_repo: Path) -> None:
        ops = GitOps(tmp_repo)
        staging = ops.create_staging_branch("test-feature", base=ops.current_branch())
        assert staging == "zerg/test-feature/staging" and ops.branch_exists(staging)


class TestGitOpsListBranches:
    def test_list_branches_with_pattern(self, tmp_repo: Path) -> None:
        ops = GitOps(tmp_repo)
        ops.create_branch("zerg/feat/worker-0")
        ops.create_branch("zerg/feat/worker-1")
        branches = ops.list_branches("zerg/feat/worker-*")
        assert len(branches) == 2 and all(isinstance(b, BranchInfo) for b in branches)

    def test_list_worker_branches(self, tmp_repo: Path) -> None:
        ops = GitOps(tmp_repo)
        ops.create_branch("zerg/myfeature/worker-0")
        ops.create_branch("zerg/myfeature/worker-1")
        workers = ops.list_worker_branches("myfeature")
        assert len(workers) == 2


class TestGitOpsStash:
    def test_stash_and_pop(self, tmp_repo: Path) -> None:
        ops = GitOps(tmp_repo)
        (tmp_repo / "README.md").write_text("modified")
        assert ops.stash("Test stash") is True
        assert (tmp_repo / "README.md").read_text() == "# Test Repo"
        ops.stash_pop()
        assert (tmp_repo / "README.md").read_text() == "modified"

    def test_stash_no_changes(self, tmp_repo: Path) -> None:
        assert GitOps(tmp_repo).stash() is False


class TestBranchInfo:
    def test_create(self) -> None:
        info = BranchInfo(name="test-branch", commit="abc123def456", is_current=True, upstream="origin/test-branch")
        assert info.name == "test-branch" and info.is_current is True
        minimal = BranchInfo(name="test", commit="abc123")
        assert minimal.is_current is False and minimal.upstream is None


class TestGitOpsPush:
    def test_push_args(self, tmp_repo: Path) -> None:
        ops = GitOps(tmp_repo)
        with patch.object(ops, "_run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            ops.push("origin", "main", force=True, set_upstream=True)
            call_args = mock_run.call_args[0]
            assert "--force" in call_args and "--set-upstream" in call_args
