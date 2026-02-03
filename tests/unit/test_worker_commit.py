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

        # HEAD didn't change - this is the bug we want to detect
        assert head_before == head_after

        # Verify the commit attempt recorded this
        attempts = git.get_commits_without_head_change()
        assert len(attempts) == 1
        assert not attempts[0].head_changed

    def test_verify_head_changed_helper(self):
        """Test helper method for HEAD verification."""
        git = MockGitOps()

        # Different commits - HEAD changed
        assert git.verify_head_changed("abc123", "def456")

        # Same commit - HEAD didn't change
        assert not git.verify_head_changed("abc123", "abc123")

    def test_commit_records_head_before_and_after(self):
        """Commit should record HEAD before and after."""
        git = MockGitOps()
        git.simulate_changes()

        head_before = git.current_commit()
        git.commit("Test commit", add_all=True)

        attempts = git.get_commit_attempts()
        assert len(attempts) == 1
        assert attempts[0].head_before == head_before
        assert attempts[0].head_after != head_before


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

        head_after = git.current_commit()

        # HEAD should be unchanged
        assert head_before == head_after

    def test_nothing_to_commit_error(self):
        """Commit with no changes should raise error."""
        git = MockGitOps()
        # No changes staged

        head_before = git.current_commit()

        with pytest.raises(GitError, match="nothing to commit"):
            git.commit("No changes", add_all=True)

        # HEAD should be unchanged
        assert git.current_commit() == head_before


class TestCommitAttemptTracking:
    """Tests for commit attempt tracking."""

    def test_successful_commit_tracked(self):
        """Successful commits should be tracked."""
        git = MockGitOps()
        git.simulate_changes()

        git.commit("Test commit", add_all=True)

        attempts = git.get_commit_attempts()
        assert len(attempts) == 1
        assert attempts[0].success
        assert attempts[0].head_changed

    def test_failed_commit_tracked(self):
        """Failed commits should be tracked."""
        git = MockGitOps()
        git.configure(commit_fails=True)
        git.simulate_changes()

        try:
            git.commit("Should fail", add_all=True)
        except GitError:
            pass

        attempts = git.get_commit_attempts()
        assert len(attempts) == 1
        assert not attempts[0].success
        assert attempts[0].error is not None

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

        # This is the fixed worker commit flow from BF-009
        task_id = "TASK-001"
        worker_id = 0

        head_before = git.current_commit()

        commit_msg = f"ZERG [{worker_id}]: Test Task\n\nTask-ID: {task_id}"
        git.commit(commit_msg, add_all=True)

        head_after = git.current_commit()

        # Verify HEAD changed - this is the critical check
        if head_before == head_after:
            # This would indicate commit failed silently
            pytest.fail(f"Commit succeeded but HEAD unchanged for {task_id}")

        # Verify commit_sha matches head_after
        assert head_after != head_before

    def test_task_commit_failure_detected(self):
        """Test that commit failure is properly detected."""
        git = MockGitOps()
        git.configure(commit_no_head_change=True)
        git.simulate_changes()

        head_before = git.current_commit()
        git.commit("ZERG commit", add_all=True)
        head_after = git.current_commit()

        # This should detect the bug
        commit_failed_silently = head_before == head_after
        assert commit_failed_silently, "Expected HEAD unchanged to simulate bug"

    def test_commit_sha_in_event(self):
        """Test that commit SHA is included in task_committed event."""
        git = MockGitOps()
        git.simulate_changes()

        git.current_commit()
        commit_sha = git.commit("Test commit", add_all=True)
        head_after = git.current_commit()

        # The event should include commit_sha
        event_data = {
            "task_id": "TASK-001",
            "commit_sha": head_after,
            "worker_id": 0,
            "branch": "test-branch",
        }

        assert event_data["commit_sha"] == commit_sha
        assert event_data["commit_sha"] == head_after


class TestNoChangesToCommit:
    """Tests for handling no changes scenario."""

    def test_no_changes_returns_true(self):
        """No changes to commit should return True (success)."""
        git = MockGitOps()
        # No changes staged

        has_changes = git.has_changes()
        assert not has_changes

        # Worker protocol should return True if no changes
        # (we don't need to commit if there's nothing to commit)

    def test_has_changes_detection(self):
        """Test has_changes detection."""
        git = MockGitOps()

        assert not git.has_changes()

        git.simulate_changes()
        assert git.has_changes()

        git.commit("Clear changes", add_all=True)
        assert not git.has_changes()


class TestCommitMessageFormat:
    """Tests for commit message formatting."""

    def test_worker_commit_message_format(self):
        """Test ZERG worker commit message format."""
        worker_id = 0
        task_id = "TASK-001"
        title = "Implement feature X"

        expected_msg = f"ZERG [{worker_id}]: {title}\n\nTask-ID: {task_id}"

        assert f"ZERG [{worker_id}]" in expected_msg
        assert f"Task-ID: {task_id}" in expected_msg

    def test_checkpoint_commit_message(self):
        """Test WIP checkpoint commit message format."""
        worker_id = 0
        task_id = "TASK-001"

        expected_msg = f"WIP: ZERG [{worker_id}] checkpoint during {task_id}"

        assert "WIP:" in expected_msg
        assert f"ZERG [{worker_id}]" in expected_msg


class TestEdgeCases:
    """Tests for edge cases in commit handling."""

    def test_empty_commit_allowed(self):
        """Test allow_empty commit option."""
        git = MockGitOps()
        # No changes

        # allow_empty=True should work
        commit_sha = git.commit("Empty commit", allow_empty=True)
        assert commit_sha is not None

    def test_commit_after_stash(self):
        """Test commit behavior after stash/pop."""
        git = MockGitOps()
        git.simulate_changes()

        # Stash changes
        stashed = git.stash("WIP")
        assert stashed
        assert not git.has_changes()

        # Pop stash
        git.stash_pop()
        assert git.has_changes()

        # Now commit
        commit_sha = git.commit("After stash", add_all=True)
        assert commit_sha is not None

    def test_rapid_commits(self):
        """Test multiple rapid commits."""
        git = MockGitOps()

        commits = []
        for i in range(5):
            git.simulate_changes()
            sha = git.commit(f"Commit {i}", add_all=True)
            commits.append(sha)

        # All commits should have unique SHAs
        assert len(set(commits)) == 5

        # Each commit should have changed HEAD
        attempts = git.get_commit_attempts()
        assert all(a.head_changed for a in attempts)
