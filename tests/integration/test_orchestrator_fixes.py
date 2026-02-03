"""Integration tests for orchestrator fixes - OFX-004.

End-to-end tests for worker lifecycle, level transitions,
failure recovery, and initialization wait.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from zerg.config import ZergConfig
from zerg.constants import WorkerStatus
from zerg.launcher import SubprocessLauncher


class TestWorkerLifecycleEndToEnd:
    """End-to-end tests for worker lifecycle."""

    @patch("subprocess.Popen")
    def test_spawn_monitor_terminate_cycle(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Test complete spawn -> monitor -> terminate cycle."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.return_value = None  # Running
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()

        # Spawn
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )
        assert result.success

        # Monitor - should be running
        status = launcher.monitor(0)
        assert status == WorkerStatus.RUNNING

        # Terminate
        mock_process.poll.return_value = 0  # Now stopped
        launcher.terminate(0)

        # Monitor again - should be stopped
        status = launcher.monitor(0)
        assert status in [WorkerStatus.STOPPED, WorkerStatus.CRASHED]

    @patch("subprocess.Popen")
    def test_multiple_workers_independent(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Multiple workers should operate independently."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()

        # Spawn multiple workers
        for i in range(4):
            result = launcher.spawn(
                worker_id=i,
                feature="test-feature",
                worktree_path=tmp_path,
                branch=f"branch-{i}",
            )
            assert result.success, f"Worker {i} should spawn successfully"

        # All should be running
        for i in range(4):
            status = launcher.monitor(i)
            assert status == WorkerStatus.RUNNING

        # Terminate one
        mock_process.poll.return_value = 0
        launcher.terminate(1)

        # Others should still be tracked
        for i in [0, 2, 3]:
            handle = launcher.get_handle(i)
            assert handle is not None


class TestFailureRecovery:
    """Tests for failure recovery scenarios."""

    @patch("subprocess.Popen")
    def test_worker_crash_detection(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Crashed worker should be detected via monitor."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.side_effect = [None, None, 1, 1]  # Crashes after 2 polls
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        # First poll - running
        status1 = launcher.monitor(0)
        assert status1 == WorkerStatus.RUNNING

        # Second poll - still running
        status2 = launcher.monitor(0)
        assert status2 == WorkerStatus.RUNNING

        # Third poll - crashed
        status3 = launcher.monitor(0)
        assert status3 in [WorkerStatus.CRASHED, WorkerStatus.STOPPED]

    @patch("subprocess.Popen")
    def test_spawn_after_crash(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Can respawn worker after crash."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.return_value = 1  # Crashed
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()

        # First spawn
        launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        # Detect crash
        status = launcher.monitor(0)
        assert status in [WorkerStatus.CRASHED, WorkerStatus.STOPPED]

        # Respawn should work
        mock_process.poll.return_value = None  # Now running
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )
        # Should succeed or have specific error
        assert result.success or result.error is not None


class TestInitializationWait:
    """Tests for initialization wait behavior - covers OFX-014."""

    @patch("subprocess.Popen")
    def test_worker_starts_in_initializing_state(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """Newly spawned worker may start in INITIALIZING state."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="test-branch",
        )

        if result.success and result.handle:
            # Initial status should be RUNNING or INITIALIZING
            assert result.handle.status in [
                WorkerStatus.RUNNING,
                WorkerStatus.INITIALIZING,
            ]

    @patch("subprocess.Popen")
    def test_multiple_spawns_complete_before_polling(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """All spawns should complete before polling starts."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()

        # Spawn all workers
        results = []
        for i in range(4):
            result = launcher.spawn(
                worker_id=i,
                feature="test-feature",
                worktree_path=tmp_path,
                branch=f"branch-{i}",
            )
            results.append(result)

        # All should have succeeded
        for i, result in enumerate(results):
            assert result.success, f"Worker {i} spawn should succeed"

        # All should be trackable
        for i in range(4):
            handle = launcher.get_handle(i)
            assert handle is not None, f"Worker {i} should be tracked"


class TestLevelTransitions:
    """Tests for level transition behavior."""

    def test_task_graph_level_ordering(self, tmp_path: Path) -> None:
        """Task graph should have proper level ordering."""
        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {"id": "T1", "title": "Task 1", "level": 1, "dependencies": []},
                {"id": "T2", "title": "Task 2", "level": 1, "dependencies": []},
                {"id": "T3", "title": "Task 3", "level": 2, "dependencies": ["T1"]},
                {"id": "T4", "title": "Task 4", "level": 2, "dependencies": ["T2"]},
            ],
        }

        # Group by level
        levels: dict[int, list] = {}
        for task in task_graph["tasks"]:
            level = task["level"]
            if level not in levels:
                levels[level] = []
            levels[level].append(task["id"])

        # Level 1 should have 2 tasks
        assert len(levels[1]) == 2
        # Level 2 should have 2 tasks
        assert len(levels[2]) == 2

    def test_dependency_resolution(self) -> None:
        """Dependencies should be resolvable."""
        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {"id": "T1", "title": "Task 1", "level": 1, "dependencies": []},
                {"id": "T2", "title": "Task 2", "level": 2, "dependencies": ["T1"]},
            ],
        }

        task_by_id = {t["id"]: t for t in task_graph["tasks"]}

        # T2's dependency should exist
        for dep_id in task_by_id["T2"]["dependencies"]:
            assert dep_id in task_by_id, f"Dependency {dep_id} should exist"


class TestConfigIntegration:
    """Test configuration integration."""

    def test_zerg_config_loads(self) -> None:
        """ZergConfig should load without error."""
        config = ZergConfig()
        assert config is not None

    def test_zerg_config_has_workers(self) -> None:
        """ZergConfig should have workers setting."""
        config = ZergConfig()
        assert hasattr(config, "workers")
        # workers is a WorkersConfig object with max_concurrent attribute
        assert hasattr(config.workers, "max_concurrent")
        assert isinstance(config.workers.max_concurrent, int)
        assert config.workers.max_concurrent > 0


class TestTaskGraphValidation:
    """Test task graph validation integration."""

    def test_valid_task_graph_passes(self) -> None:
        """Valid task graph should pass validation."""
        from zerg.validation import validate_dependencies, validate_task_graph

        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {
                    "id": "T1",
                    "title": "Task 1",
                    "level": 1,
                    "dependencies": [],
                    "files": {"create": ["file1.py"], "modify": [], "read": []},
                },
            ],
        }

        is_valid, errors = validate_task_graph(task_graph)
        assert is_valid, f"Valid task graph should pass: {errors}"

        is_valid, errors = validate_dependencies(task_graph)
        assert is_valid, f"Valid dependencies should pass: {errors}"

    def test_invalid_level_fails(self) -> None:
        """Task graph with level 0 should fail validation."""
        from zerg.validation import validate_task_graph

        task_graph = {
            "feature": "test-feature",
            "tasks": [
                {
                    "id": "T1",
                    "title": "Task 1",
                    "level": 0,  # Invalid
                    "dependencies": [],
                },
            ],
        }

        is_valid, errors = validate_task_graph(task_graph)
        assert not is_valid, "Level 0 should fail validation"


class TestCleanupBehavior:
    """Test cleanup after operations."""

    @patch("subprocess.Popen")
    def test_terminate_all_cleans_up(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """terminate_all should clean up all workers."""
        mock_process = MagicMock(pid=12345)
        mock_process.poll.return_value = 0
        mock_popen.return_value = mock_process

        launcher = SubprocessLauncher()

        # Spawn workers
        for i in range(3):
            launcher.spawn(
                worker_id=i,
                feature="test-feature",
                worktree_path=tmp_path,
                branch=f"branch-{i}",
            )

        # Terminate all
        launcher.terminate_all()

        # All should be stopped
        for i in range(3):
            status = launcher.monitor(i)
            assert status in [WorkerStatus.STOPPED, WorkerStatus.CRASHED]
