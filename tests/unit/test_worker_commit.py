"""Unit tests for worker commit verification.

Tests BF-009: Worker protocol HEAD verification after commit.
"""

import pytest

from tests.mocks.mock_git import MockGitOps
from zerg.exceptions import GitError


class TestHeadVerification:
    """Tests for verifying HEAD changed after commit."""

    def test_commit_changes_head(self):
        """Successful commit should change HEAD."""
        git = MockGitOps()
        git.simulate_changes()

        head_before = git.current_commit()
        commit_sha = git.commit("Test commit", add_all=True)
        head_after = git.current_commit()

        assert head_before != head_after
        assert head_after == commit_sha

    def test_commit_without_head_change_detected(self):
        """Commit where HEAD doesn't change should be detected."""
        git = MockGitOps()
        git.configure(commit_no_head_change=True)
        git.simulate_changes()

        head_before = git.current_commit()
        git.commit("Test commit", add_all=True)
        head_after = git.current_commit()

        assert head_before == head_after
        attempts = git.get_commits_without_head_change()
        assert len(attempts) == 1
        assert not attempts[0].head_changed


class TestCommitFailureHandling:
    """Tests for handling commit failures."""

    def test_commit_failure_preserves_head(self):
        """Failed commit should not change HEAD."""
        git = MockGitOps()
        git.configure(commit_fails=True)
        git.simulate_changes()

        head_before = git.current_commit()
        with pytest.raises(GitError):
            git.commit("Should fail", add_all=True)

        assert git.current_commit() == head_before

    def test_nothing_to_commit_error(self):
        """Commit with no changes should raise error."""
        git = MockGitOps()
        head_before = git.current_commit()

        with pytest.raises(GitError, match="nothing to commit"):
            git.commit("No changes", add_all=True)

        assert git.current_commit() == head_before


class TestCommitAttemptTracking:
    """Tests for commit attempt tracking."""

    def test_successful_and_failed_commits_tracked(self):
        """Successful and failed commits should both be tracked."""
        git = MockGitOps()

        # Successful commit
        git.simulate_changes()
        git.commit("Test commit", add_all=True)
        attempts = git.get_commit_attempts()
        assert len(attempts) == 1
        assert attempts[0].success
        assert attempts[0].head_changed

        # Failed commit
        git2 = MockGitOps()
        git2.configure(commit_fails=True)
        git2.simulate_changes()
        try:
            git2.commit("Should fail", add_all=True)
        except GitError:
            pass  # Expected: commit configured to fail; verify tracking below
        attempts2 = git2.get_commit_attempts()
        assert len(attempts2) == 1
        assert not attempts2[0].success
        assert attempts2[0].error is not None

    def test_multiple_commits_tracked(self):
        """Multiple commits should all be tracked."""
        git = MockGitOps()
        for i in range(3):
            git.simulate_changes()
            git.commit(f"Commit {i}", add_all=True)

        attempts = git.get_commit_attempts()
        assert len(attempts) == 3
        assert all(a.success for a in attempts)


class TestWorkerCommitIntegration:
    """Integration tests for worker commit flow."""

    def test_task_commit_with_verification(self):
        """Test the expected worker commit flow with HEAD verification."""
        git = MockGitOps()
        git.simulate_changes()

        head_before = git.current_commit()
        commit_msg = "ZERG [0]: Test Task\n\nTask-ID: TASK-001"
        git.commit(commit_msg, add_all=True)
        head_after = git.current_commit()

        assert head_after != head_before


class TestNoChangesAndEdgeCases:
    """Tests for no-changes and edge cases."""

    def test_has_changes_detection(self):
        """Test has_changes detection through lifecycle."""
        git = MockGitOps()
        assert not git.has_changes()

        git.simulate_changes()
        assert git.has_changes()

        git.commit("Clear changes", add_all=True)
        assert not git.has_changes()

    def test_empty_commit_allowed(self):
        """Test allow_empty commit option."""
        git = MockGitOps()
        commit_sha = git.commit("Empty commit", allow_empty=True)
        assert commit_sha is not None

    def test_rapid_commits_unique_shas(self):
        """Multiple rapid commits should have unique SHAs."""
        git = MockGitOps()
        commits = []
        for i in range(5):
            git.simulate_changes()
            sha = git.commit(f"Commit {i}", add_all=True)
            commits.append(sha)

        assert len(set(commits)) == 5
        attempts = git.get_commit_attempts()
        assert all(a.head_changed for a in attempts)
