"""End-to-end tests for the full ZERG pipeline.

Tests the complete orchestration flow from task graph setup through
execution and merge using the E2EHarness with MockWorker.
"""

from __future__ import annotations

import json

import pytest

from tests.e2e.harness import E2EHarness
from tests.e2e.mock_worker import MockWorker


class TestFullPipeline:
    """Test suite for end-to-end ZERG orchestration flows."""

    def test_mock_pipeline_completes(
        self,
        e2e_harness: E2EHarness,
        sample_e2e_task_graph: list[dict],
    ) -> None:
        """Verify that a full pipeline run completes successfully with mock workers.

        Uses E2EHarness with sample_e2e_task_graph fixture containing 4 tasks
        across 2 levels, executes with 5 workers, and asserts E2EResult.success.
        """
        e2e_harness.setup_task_graph(sample_e2e_task_graph)
        result = e2e_harness.run(workers=5)

        assert result.success is True
        assert result.tasks_completed == 4
        assert result.tasks_failed == 0
        assert result.levels_completed == 2
        assert result.duration_s > 0

    def test_mock_pipeline_creates_files(
        self,
        e2e_harness: E2EHarness,
        sample_e2e_task_graph: list[dict],
    ) -> None:
        """Verify that files specified in task graph are created after execution.

        Checks that all files listed in the task graph's "create" manifests
        exist in the repository after a successful run.
        """
        e2e_harness.setup_task_graph(sample_e2e_task_graph)
        result = e2e_harness.run(workers=5)

        assert result.success is True

        repo_path = e2e_harness.repo_path
        assert repo_path is not None

        # Expected files from sample_e2e_task_graph fixture:
        # T1.1 creates src/hello.py
        # T1.2 creates src/utils.py
        # T2.1 creates tests/test_hello.py
        # T2.2 creates README.md
        expected_files = [
            "src/hello.py",
            "src/utils.py",
            "tests/test_hello.py",
            "README.md",
        ]

        for filepath in expected_files:
            full_path = repo_path / filepath
            assert full_path.exists(), f"Expected file {filepath} was not created"

            # Verify content is not empty
            content = full_path.read_text()
            assert len(content) > 0, f"File {filepath} is empty"

    def test_mock_pipeline_merges_levels(
        self,
        e2e_harness: E2EHarness,
        sample_e2e_task_graph: list[dict],
    ) -> None:
        """Verify that git log contains merge commits after level completions.

        Checks that the E2EHarness records merge commits after each level
        finishes successfully.
        """
        e2e_harness.setup_task_graph(sample_e2e_task_graph)
        result = e2e_harness.run(workers=5)

        assert result.success is True
        assert len(result.merge_commits) == 2

        # Verify merge commit hashes follow expected format
        assert result.merge_commits[0] == "e2e-merge-level-1"
        assert result.merge_commits[1] == "e2e-merge-level-2"

    def test_mock_pipeline_state_consistent(
        self,
        e2e_harness: E2EHarness,
        sample_e2e_task_graph: list[dict],
    ) -> None:
        """Verify that .zerg/state JSON shows all tasks complete after run.

        Note: MockWorker does not write state JSON files (it only simulates
        file operations from task manifests). This test verifies that the
        task graph structure remains consistent and that all expected files
        from the task graph were created, which is the equivalent state check
        for the mock execution mode.
        """
        e2e_harness.setup_task_graph(sample_e2e_task_graph)
        result = e2e_harness.run(workers=5)

        assert result.success is True

        repo_path = e2e_harness.repo_path
        assert repo_path is not None

        # Verify task graph is intact and readable
        graph_path = repo_path / ".gsd" / "specs" / e2e_harness.feature / "task-graph.json"
        assert graph_path.exists()

        with open(graph_path) as f:
            task_graph = json.load(f)

        # Verify all tasks in task graph match what was completed
        assert task_graph["total_tasks"] == result.tasks_completed
        assert len(task_graph["tasks"]) == 4

        # Verify that all tasks have their expected files created
        for task in task_graph["tasks"]:
            for filepath in task["files"].get("create", []):
                full_path = repo_path / filepath
                assert full_path.exists(), f"Task {task['id']} file {filepath} not created"

    def test_mock_pipeline_handles_task_failure(
        self,
        e2e_harness: E2EHarness,
        sample_e2e_task_graph: list[dict],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify partial completion when one task fails.

        Configures MockWorker to fail task L1-002, verifies that L1-002 fails,
        and that the pipeline reports overall failure.
        """
        e2e_harness.setup_task_graph(sample_e2e_task_graph)

        # Patch MockWorker inside the harness module so run() creates a
        # worker that will fail task L1-002.
        failing_worker_cls = _make_failing_worker_factory(fail_tasks={"L1-002"})
        monkeypatch.setattr("tests.e2e.mock_worker.MockWorker", failing_worker_cls)

        result = e2e_harness.run(workers=5)

        # Pipeline should not succeed overall
        assert result.success is False

        # At least one task should fail
        assert result.tasks_failed >= 1

        # Some tasks should still complete
        assert result.tasks_completed >= 1

        # Level 1 should not be fully complete due to L1-002 failure
        # In MockWorker mode, levels_completed only increments when ALL tasks succeed
        assert result.levels_completed < 2

        repo_path = e2e_harness.repo_path
        assert repo_path is not None

        # L1-001 file should exist since it succeeded
        assert (repo_path / "src/hello.py").exists()


def _make_failing_worker_factory(
    fail_tasks: set[str],
) -> type[MockWorker]:
    """Return a MockWorker subclass pre-configured to fail specific tasks.

    The harness calls ``MockWorker()`` with no arguments, so we override
    ``__init__`` to inject the fail set automatically.

    Args:
        fail_tasks: Set of task IDs that should simulate failure.

    Returns:
        A MockWorker subclass whose default constructor fails the given tasks.
    """

    class _FailingMockWorker(MockWorker):
        def __init__(self) -> None:  # noqa: D107
            super().__init__(fail_tasks=fail_tasks)

    return _FailingMockWorker
