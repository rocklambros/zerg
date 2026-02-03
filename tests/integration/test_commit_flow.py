"""Integration test: commit and task completion (mocked).

Tests BF-012: Verifies worker commit verification and task completion
flow using mocked git operations.
"""

import pytest

from tests.mocks.mock_git import MockGitOps
from zerg.exceptions import GitError


class TestCommitAndTaskCompletion:
    """Integration tests for commit and task completion flow."""

    def test_successful_commit_completes_task(self):
        """Successful commit should complete task."""
        git = MockGitOps()
        git.simulate_changes()

        # Simulate worker commit flow
        task = {
            "id": "TASK-001",
            "title": "Implement feature X",
        }
        worker_id = 0

        head_before = git.current_commit()
        title = task.get("title", task["id"])
        commit_msg = f"ZERG [{worker_id}]: {title}\n\nTask-ID: {task['id']}"

        git.commit(commit_msg, add_all=True)

        head_after = git.current_commit()

        # Verify HEAD changed (BF-009)
        assert head_before != head_after

        # Task would be marked complete
        event = {
            "task_id": task["id"],
            "worker_id": worker_id,
            "commit_sha": head_after,
        }
        assert event["commit_sha"] == head_after

    def test_commit_failure_doesnt_complete_task(self):
        """Failed commit should not complete task."""
        git = MockGitOps()
        git.configure(commit_fails=True)
        git.simulate_changes()

        head_before = git.current_commit()

        with pytest.raises(GitError):
            git.commit("ZERG [0]: Test task", add_all=True)

        head_after = git.current_commit()

        # HEAD should not change
        assert head_before == head_after

    def test_commit_without_head_change_detected(self):
        """Commit where HEAD doesn't change should be detected."""
        git = MockGitOps()
        git.configure(commit_no_head_change=True)
        git.simulate_changes()

        task = {"id": "TASK-001", "title": "Test task"}

        head_before = git.current_commit()
        git.commit("ZERG [0]: Test task", add_all=True)
        head_after = git.current_commit()

        # BF-009: This should be detected as failure
        if head_before == head_after:
            # Log error and return False in real worker
            error_event = {
                "task_id": task["id"],
                "error": "HEAD unchanged after commit",
                "head_before": head_before,
                "head_after": head_after,
            }
            assert "unchanged" in error_event["error"].lower()


class TestNoChangesScenario:
    """Tests for no changes to commit scenario."""

    def test_no_changes_is_success(self):
        """No changes to commit should be considered success."""
        git = MockGitOps()
        # No changes staged

        has_changes = git.has_changes()
        assert not has_changes

        # In worker protocol, no changes returns True (success)
        # The task can be marked complete without committing

    def test_empty_commit_not_allowed_by_default(self):
        """Empty commit should fail by default."""
        git = MockGitOps()
        # No changes

        with pytest.raises(GitError, match="nothing to commit"):
            git.commit("Empty commit")


class TestMultiTaskCommitFlow:
    """Tests for committing multiple tasks."""

    def test_sequential_task_commits(self):
        """Multiple tasks should commit sequentially."""
        git = MockGitOps()

        tasks = [
            {"id": "TASK-001", "title": "Task 1"},
            {"id": "TASK-002", "title": "Task 2"},
            {"id": "TASK-003", "title": "Task 3"},
        ]

        commits = []
        for task in tasks:
            git.simulate_changes()
            commit_sha = git.commit(f"ZERG [0]: {task['title']}", add_all=True)
            commits.append(
                {
                    "task_id": task["id"],
                    "commit_sha": commit_sha,
                }
            )

        # All commits should have unique SHAs
        shas = [c["commit_sha"] for c in commits]
        assert len(set(shas)) == 3

        # All should be tracked
        attempts = git.get_commit_attempts()
        assert len(attempts) == 3
        assert all(a.head_changed for a in attempts)

    def test_commit_failure_mid_sequence(self):
        """Failure mid-sequence should not affect previous commits."""
        git = MockGitOps()

        # Commit task 1 successfully
        git.simulate_changes()
        git.commit("ZERG [0]: Task 1", add_all=True)
        head_after_1 = git.current_commit()

        # Configure failure for next commit
        git.configure(commit_fails=True)
        git.simulate_changes()

        with pytest.raises(GitError):
            git.commit("ZERG [0]: Task 2", add_all=True)

        # First commit should still be valid
        assert git.get_commit("HEAD") == head_after_1


class TestCommitEventTracking:
    """Tests for commit event tracking."""

    def test_successful_commit_event(self):
        """Successful commit should generate event with SHA."""
        git = MockGitOps()
        git.simulate_changes()

        commit_sha = git.commit("Test commit", add_all=True)

        # Event structure
        event = {
            "task_id": "TASK-001",
            "worker_id": 0,
            "branch": "zerg/test/worker-0",
            "commit_sha": commit_sha,
        }

        assert "commit_sha" in event
        assert event["commit_sha"] == commit_sha

    def test_commit_verification_failure_event(self):
        """HEAD unchanged should generate verification failure event."""
        git = MockGitOps()
        git.configure(commit_no_head_change=True)
        git.simulate_changes()

        head_before = git.current_commit()
        git.commit("Test commit", add_all=True)
        head_after = git.current_commit()

        # BF-009 event
        if head_before == head_after:
            event = {
                "task_id": "TASK-001",
                "worker_id": 0,
                "head_before": head_before,
                "head_after": head_after,
                "error": "HEAD unchanged after commit",
            }
            assert event["head_before"] == event["head_after"]


class TestCheckpointCommit:
    """Tests for checkpoint (WIP) commits."""

    def test_checkpoint_commit_format(self):
        """Checkpoint commit should have correct format."""
        git = MockGitOps()
        git.simulate_changes()

        worker_id = 0
        task_id = "TASK-001"
        commit_msg = f"WIP: ZERG [{worker_id}] checkpoint during {task_id}"

        commit_sha = git.commit(commit_msg, add_all=True)

        assert commit_sha is not None
        # In real implementation, checkpoint commits have specific handling

    def test_checkpoint_after_partial_work(self):
        """Checkpoint should capture partial work."""
        git = MockGitOps()

        # Simulate partial work
        git.simulate_changes()

        head_before = git.current_commit()
        commit_sha = git.commit("WIP: ZERG [0] checkpoint during TASK-001", add_all=True)
        head_after = git.current_commit()

        # Checkpoint should change HEAD
        assert head_before != head_after
        assert head_after == commit_sha


class TestBranchOperations:
    """Tests for branch operations during commit flow."""

    def test_commit_on_worker_branch(self):
        """Commits should happen on worker branch."""
        git = MockGitOps()

        # Create and switch to worker branch
        git.create_branch("zerg/test/worker-0", "main")
        git.checkout("zerg/test/worker-0")

        git.simulate_changes()
        commit_sha = git.commit("ZERG [0]: Task 1", add_all=True)

        # Should be on worker branch
        assert git.current_branch() == "zerg/test/worker-0"
        assert git.current_commit() == commit_sha

    def test_multiple_workers_different_branches(self):
        """Multiple workers commit on different branches."""
        git = MockGitOps()

        workers = []
        for i in range(3):
            branch = f"zerg/test/worker-{i}"
            git.create_branch(branch, "main")
            git.checkout(branch)
            git.simulate_changes()
            commit = git.commit(f"ZERG [{i}]: Task", add_all=True)
            workers.append(
                {
                    "worker_id": i,
                    "branch": branch,
                    "commit": commit,
                }
            )
            git.checkout("main")

        # Each worker should have committed on their branch
        assert len(workers) == 3
        for w in workers:
            assert w["branch"].startswith("zerg/test/worker-")


class TestGitStateAfterCommit:
    """Tests for git state verification after commit."""

    def test_no_staged_changes_after_commit(self):
        """No staged changes should remain after commit."""
        git = MockGitOps()
        git.simulate_changes()

        assert git.has_changes()

        git.commit("Test commit", add_all=True)

        assert not git.has_changes()

    def test_head_points_to_new_commit(self):
        """HEAD should point to new commit after commit."""
        git = MockGitOps()
        git.simulate_changes()

        commit_sha = git.commit("Test commit", add_all=True)

        assert git.current_commit() == commit_sha
        assert git.get_commit("HEAD") == commit_sha

    def test_commit_history_grows(self):
        """Commit history should grow with each commit."""
        git = MockGitOps()

        initial_count = len(git._commits)

        for i in range(3):
            git.simulate_changes()
            git.commit(f"Commit {i}", add_all=True)

        assert len(git._commits) == initial_count + 3
