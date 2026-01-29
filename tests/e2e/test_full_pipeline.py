"""End-to-end tests for the full ZERG mock pipeline.

Tests the complete orchestration flow through the E2EHarness, verifying
task completion, file creation, level merging, state consistency, and
failure handling.
"""

from __future__ import annotations

import pytest

from tests.e2e.harness import E2EHarness
from tests.e2e.mock_worker import MockWorker


class TestFullPipeline:
    """Full pipeline E2E tests using mock workers."""

    def test_mock_pipeline_completes(
        self,
        e2e_harness: E2EHarness,
        sample_e2e_task_graph: list[dict],
    ) -> None:
        """Test that a mock pipeline run completes all 4 tasks successfully."""
        e2e_harness.setup_task_graph(sample_e2e_task_graph)
        result = e2e_harness.run(workers=5)

        assert result.success is True
        assert result.tasks_completed == 4
        assert result.tasks_failed == 0

    def test_mock_pipeline_creates_files(
        self,
        e2e_harness: E2EHarness,
        sample_e2e_task_graph: list[dict],
    ) -> None:
        """Test that mock workers create all expected files in the repo."""
        e2e_harness.setup_task_graph(sample_e2e_task_graph)
        e2e_harness.run(workers=5)

        repo = e2e_harness.repo_path
        assert (repo / "src/hello.py").exists()
        assert (repo / "src/utils.py").exists()
        assert (repo / "tests/test_hello.py").exists()
        assert (repo / "README.md").exists()

    def test_mock_pipeline_merges_levels(
        self,
        e2e_harness: E2EHarness,
        sample_e2e_task_graph: list[dict],
    ) -> None:
        """Test that both levels are merged with commit records."""
        e2e_harness.setup_task_graph(sample_e2e_task_graph)
        result = e2e_harness.run(workers=5)

        assert result.levels_completed == 2
        assert len(result.merge_commits) == 2

    def test_mock_pipeline_state_consistent(
        self,
        e2e_harness: E2EHarness,
        sample_e2e_task_graph: list[dict],
    ) -> None:
        """Test that completed + failed tasks account for all tasks."""
        e2e_harness.setup_task_graph(sample_e2e_task_graph)
        result = e2e_harness.run(workers=5)

        assert result.tasks_completed + result.tasks_failed == 4
        assert result.duration_s >= 0

    def test_mock_pipeline_handles_task_failure(
        self,
        e2e_harness: E2EHarness,
        sample_e2e_task_graph: list[dict],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that a failing task causes the pipeline to report failure."""
        e2e_harness.setup_task_graph(sample_e2e_task_graph)

        # Patch MockWorker inside the harness module so run() creates a
        # worker that will fail task T1.1.
        failing_worker_cls = _make_failing_worker_factory(fail_tasks={"T1.1"})
        monkeypatch.setattr(
            "tests.e2e.mock_worker.MockWorker", failing_worker_cls
        )

        result = e2e_harness.run(workers=5)

        assert result.success is False
        assert result.tasks_failed >= 1


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
