"""Integration tests for claim enforcement in task claiming.

Tests OCF-L2-001 and OCF-L2-002:
- Level enforcement: Workers can only claim tasks for current level
- Dependency enforcement: Workers cannot claim tasks with incomplete dependencies
- Protocol-state integration: claim_next_task_async passes current_level correctly
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import Mock

from zerg.constants import TaskStatus
from zerg.dependency_checker import DependencyChecker
from zerg.state import StateManager


class TestLevelEnforcement:
    """Tests for level enforcement in claim_task."""

    def test_claim_task_respects_level(self, tmp_path: Path) -> None:
        """claim_task with current_level should reject tasks at different levels."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()

        # Set up tasks with level info
        state.set_task_status("TASK-L1-001", TaskStatus.PENDING)
        state.set_task_status("TASK-L2-001", TaskStatus.PENDING)

        # Manually set level info (set_task_status doesn't set level)
        state._persistence._state["tasks"]["TASK-L1-001"]["level"] = 1
        state._persistence._state["tasks"]["TASK-L2-001"]["level"] = 2
        state.save()

        # Reload to ensure file persistence
        state.load()

        # Trying to claim level 2 task when current level is 1 should fail
        result = state.claim_task("TASK-L2-001", worker_id=0, current_level=1)
        assert result is False

        # Claiming level 1 task when current level is 1 should succeed
        result = state.claim_task("TASK-L1-001", worker_id=0, current_level=1)
        assert result is True

    def test_claim_task_without_level_enforcement(self, tmp_path: Path) -> None:
        """claim_task without current_level should allow any task."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()

        state.set_task_status("TASK-L2-001", TaskStatus.PENDING)
        state._persistence._state["tasks"]["TASK-L2-001"]["level"] = 2
        state.save()
        state.load()

        # Without current_level parameter, should be able to claim any task
        result = state.claim_task("TASK-L2-001", worker_id=0)
        assert result is True

    def test_claim_task_level_none_skips_check(self, tmp_path: Path) -> None:
        """claim_task with current_level=None should skip level enforcement."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()

        state.set_task_status("TASK-L3-001", TaskStatus.PENDING)
        state._persistence._state["tasks"]["TASK-L3-001"]["level"] = 3
        state.save()
        state.load()

        # Explicit None should skip level check
        result = state.claim_task("TASK-L3-001", worker_id=0, current_level=None)
        assert result is True


class TestDependencyEnforcement:
    """Tests for dependency enforcement in claim_task."""

    def test_claim_task_checks_dependencies(self, tmp_path: Path) -> None:
        """claim_task with dependency_checker should verify dependencies."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()

        # Set up: TASK-001 complete, TASK-002 depends on it
        state.set_task_status("TASK-001", TaskStatus.COMPLETE)
        state.set_task_status("TASK-002", TaskStatus.PENDING)

        parser = Mock()
        parser.get_dependencies.side_effect = lambda tid: ["TASK-001"] if tid == "TASK-002" else []

        checker = DependencyChecker(parser, state)

        # With TASK-001 complete, TASK-002 should be claimable
        result = state.claim_task("TASK-002", worker_id=0, dependency_checker=checker)
        assert result is True

    def test_claim_task_rejects_incomplete_dependencies(self, tmp_path: Path) -> None:
        """claim_task should reject tasks with incomplete dependencies."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()

        # Set up: both pending, TASK-002 depends on TASK-001
        state.set_task_status("TASK-001", TaskStatus.PENDING)
        state.set_task_status("TASK-002", TaskStatus.PENDING)

        parser = Mock()
        parser.get_dependencies.side_effect = lambda tid: ["TASK-001"] if tid == "TASK-002" else []

        checker = DependencyChecker(parser, state)

        # With TASK-001 pending, TASK-002 should NOT be claimable
        result = state.claim_task("TASK-002", worker_id=0, dependency_checker=checker)
        assert result is False
        assert state.get_task_status("TASK-002") == TaskStatus.PENDING.value

    def test_claim_task_without_dependency_checker(self, tmp_path: Path) -> None:
        """claim_task without dependency_checker should skip dependency check."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()

        # Set up: TASK-001 not complete
        state.set_task_status("TASK-001", TaskStatus.PENDING)
        state.set_task_status("TASK-002", TaskStatus.PENDING)

        # Without dependency_checker, should be able to claim regardless
        result = state.claim_task("TASK-002", worker_id=0)
        assert result is True


class TestCombinedEnforcement:
    """Tests for combined level and dependency enforcement."""

    def test_both_level_and_dependency_enforced(self, tmp_path: Path) -> None:
        """Both level and dependency must pass for successful claim."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()

        # Set up: L1-001 complete, L2-001 depends on it
        state.set_task_status("TASK-L1-001", TaskStatus.COMPLETE)
        state.set_task_status("TASK-L2-001", TaskStatus.PENDING)
        state._persistence._state["tasks"]["TASK-L1-001"]["level"] = 1
        state._persistence._state["tasks"]["TASK-L2-001"]["level"] = 2
        state.save()
        state.load()

        parser = Mock()
        parser.get_dependencies.side_effect = lambda tid: ["TASK-L1-001"] if tid == "TASK-L2-001" else []

        checker = DependencyChecker(parser, state)

        # Wrong level (1), right dependencies -> should fail
        result = state.claim_task(
            "TASK-L2-001",
            worker_id=0,
            current_level=1,
            dependency_checker=checker,
        )
        assert result is False

        # Right level (2), right dependencies -> should succeed
        result = state.claim_task(
            "TASK-L2-001",
            worker_id=0,
            current_level=2,
            dependency_checker=checker,
        )
        assert result is True

    def test_level_check_happens_before_dependency_check(self, tmp_path: Path) -> None:
        """Level check should happen first for efficiency."""
        state = StateManager("test-feature", state_dir=tmp_path)
        state.load()

        state.set_task_status("TASK-002", TaskStatus.PENDING)
        state._persistence._state["tasks"]["TASK-002"]["level"] = 2
        state.save()
        state.load()

        parser = Mock()
        parser.get_dependencies.return_value = []
        checker = DependencyChecker(parser, state)

        # Wrong level should fail without even checking dependencies
        result = state.claim_task(
            "TASK-002",
            worker_id=0,
            current_level=1,
            dependency_checker=checker,
        )
        assert result is False


class TestWorkerProtocolIntegration:
    """Integration tests for WorkerProtocol with DependencyChecker."""

    def test_worker_protocol_creates_dependency_checker(self, tmp_path: Path, monkeypatch) -> None:
        """WorkerProtocol should create DependencyChecker when task parser exists."""
        from zerg.protocol_state import WorkerProtocol

        # Create a minimal task graph
        task_graph = {
            "feature": "test-feature",
            "version": "2.0",
            "tasks": [
                {"id": "TASK-001", "title": "First task", "level": 1, "dependencies": []},
                {"id": "TASK-002", "title": "Second task", "level": 2, "dependencies": ["TASK-001"]},
            ],
            "levels": {
                "1": {"name": "foundation", "tasks": ["TASK-001"]},
                "2": {"name": "core", "tasks": ["TASK-002"]},
            },
        }

        task_graph_path = tmp_path / "task-graph.json"
        task_graph_path.write_text(json.dumps(task_graph))

        # Create a fake git repo
        (tmp_path / ".git").mkdir()

        # Set up environment
        monkeypatch.setenv("ZERG_WORKER_ID", "0")
        monkeypatch.setenv("ZERG_FEATURE", "test-feature")
        monkeypatch.setenv("ZERG_WORKTREE", str(tmp_path))
        monkeypatch.setenv("ZERG_STATE_DIR", str(tmp_path))
        monkeypatch.setenv("ZERG_TASK_GRAPH", str(task_graph_path))

        # Create WorkerProtocol
        protocol = WorkerProtocol()

        # Should have initialized dependency_checker
        assert protocol.dependency_checker is not None
        assert isinstance(protocol.dependency_checker, DependencyChecker)

        # Check that it has the right dependencies
        deps = protocol.dependency_checker.get_incomplete_dependencies("TASK-002")
        # TASK-001 should be incomplete since it was never completed
        assert "TASK-001" in deps


def _setup_protocol_for_level_tests(
    tmp_path: Path,
    monkeypatch: object,
    tasks: list[dict],
) -> object:
    """Create a WorkerProtocol with a task graph and state for level-aware tests.

    Args:
        tmp_path: Temporary directory for state and task graph files.
        monkeypatch: pytest monkeypatch fixture for environment variables.
        tasks: List of task dicts with id, title, level, dependencies.

    Returns:
        Configured WorkerProtocol instance with loaded state.
    """
    from zerg.protocol_state import WorkerProtocol

    # Build levels dict from tasks
    levels_dict: dict[str, dict] = {}
    for task in tasks:
        level_key = str(task["level"])
        if level_key not in levels_dict:
            levels_dict[level_key] = {"name": f"level-{level_key}", "tasks": []}
        levels_dict[level_key]["tasks"].append(task["id"])

    task_graph = {
        "feature": "test-feature",
        "version": "2.0",
        "tasks": tasks,
        "levels": levels_dict,
    }

    task_graph_path = tmp_path / "task-graph.json"
    task_graph_path.write_text(json.dumps(task_graph))

    # Create a fake git repo
    git_dir = tmp_path / ".git"
    if not git_dir.exists():
        git_dir.mkdir()

    # Set up environment
    monkeypatch.setenv("ZERG_WORKER_ID", "0")  # type: ignore[union-attr]
    monkeypatch.setenv("ZERG_FEATURE", "test-feature")  # type: ignore[union-attr]
    monkeypatch.setenv("ZERG_WORKTREE", str(tmp_path))  # type: ignore[union-attr]
    monkeypatch.setenv("ZERG_STATE_DIR", str(tmp_path))  # type: ignore[union-attr]
    monkeypatch.setenv("ZERG_TASK_GRAPH", str(task_graph_path))  # type: ignore[union-attr]

    return WorkerProtocol()


class TestProtocolStateLevelAwareClaiming:
    """Integration tests for level-aware claiming through the protocol_state layer.

    Verifies that claim_next_task_async correctly reads current_level from
    StateManager.get_current_level() and passes it to claim_task(), ensuring
    workers only claim tasks at the current execution level.
    """

    def test_claim_respects_current_level_via_protocol_state(self, tmp_path: Path, monkeypatch) -> None:
        """claim_next_task_async should only claim tasks at the current level.

        Sets up tasks at levels 1 and 2, sets current_level to 1, and verifies
        that only level-1 tasks are claimed through the protocol_state layer.
        """
        tasks = [
            {"id": "TASK-001", "title": "Level 1 task", "level": 1, "dependencies": []},
            {"id": "TASK-002", "title": "Level 2 task", "level": 2, "dependencies": []},
        ]
        protocol = _setup_protocol_for_level_tests(tmp_path, monkeypatch, tasks)

        # Register both tasks as PENDING and set current execution level.
        # Note: set_task_status and set_current_level use atomic_update() which
        # reloads from disk. Level metadata must be set AFTER all atomic ops
        # and persisted with a direct save() to avoid being overwritten.
        protocol.state.set_task_status("TASK-001", TaskStatus.PENDING)
        protocol.state.set_task_status("TASK-002", TaskStatus.PENDING)
        protocol.state.set_current_level(1)

        # Set level metadata after all atomic operations, then save directly
        protocol.state._persistence._state["tasks"]["TASK-001"]["level"] = 1
        protocol.state._persistence._state["tasks"]["TASK-002"]["level"] = 2
        protocol.state.save()

        # Claim through protocol_state — should use get_current_level() internally
        # Use max_wait=0 so it doesn't poll; just tries once and returns
        claimed = asyncio.run(protocol.claim_next_task_async(max_wait=0, poll_interval=0.01))

        # Should have claimed TASK-001 (level 1), not TASK-002 (level 2)
        assert claimed is not None
        assert claimed["id"] == "TASK-001"

        # Verify TASK-002 remains pending (not claimed)
        assert protocol.state.get_task_status("TASK-002") == TaskStatus.PENDING.value

    def test_claim_skips_higher_level_tasks(self, tmp_path: Path, monkeypatch) -> None:
        """When current_level is 1, level-2 tasks should remain pending.

        Creates tasks at levels 1 and 2. Sets current_level to 1. Claims
        the level-1 task, then verifies a second claim attempt returns None
        because the only remaining task is level 2.
        """
        tasks = [
            {"id": "TASK-A", "title": "Foundation task", "level": 1, "dependencies": []},
            {"id": "TASK-B", "title": "Core task", "level": 2, "dependencies": []},
        ]
        protocol = _setup_protocol_for_level_tests(tmp_path, monkeypatch, tasks)

        # Register tasks as PENDING and set current level via atomic operations.
        # Level metadata must be set after all atomic ops to avoid reload overwrite.
        protocol.state.set_task_status("TASK-A", TaskStatus.PENDING)
        protocol.state.set_task_status("TASK-B", TaskStatus.PENDING)
        protocol.state.set_current_level(1)

        # Set level metadata after all atomic operations, then save directly
        protocol.state._persistence._state["tasks"]["TASK-A"]["level"] = 1
        protocol.state._persistence._state["tasks"]["TASK-B"]["level"] = 2
        protocol.state.save()

        # First claim: should get TASK-A (level 1)
        first = asyncio.run(protocol.claim_next_task_async(max_wait=0, poll_interval=0.01))
        assert first is not None
        assert first["id"] == "TASK-A"

        # Second claim: TASK-B is level 2, current_level is still 1 -> no match
        second = asyncio.run(protocol.claim_next_task_async(max_wait=0, poll_interval=0.01))
        assert second is None

        # TASK-B should still be pending — never claimed
        assert protocol.state.get_task_status("TASK-B") == TaskStatus.PENDING.value

    def test_claim_allows_current_level_tasks_when_level_advances(self, tmp_path: Path, monkeypatch) -> None:
        """When current_level advances to 2, level-2 tasks become claimable.

        Creates tasks at levels 1 and 2. Completes level 1, advances
        current_level to 2, then verifies that level-2 tasks can be claimed.
        """
        tasks = [
            {"id": "TASK-X", "title": "Level 1 work", "level": 1, "dependencies": []},
            {"id": "TASK-Y", "title": "Level 2 work", "level": 2, "dependencies": []},
        ]
        protocol = _setup_protocol_for_level_tests(tmp_path, monkeypatch, tasks)

        # TASK-X already complete, TASK-Y still pending.
        # Level metadata must be set after all atomic ops to avoid reload overwrite.
        protocol.state.set_task_status("TASK-X", TaskStatus.COMPLETE)
        protocol.state.set_task_status("TASK-Y", TaskStatus.PENDING)
        protocol.state.set_current_level(2)

        # Set level metadata after all atomic operations, then save directly
        protocol.state._persistence._state["tasks"]["TASK-X"]["level"] = 1
        protocol.state._persistence._state["tasks"]["TASK-Y"]["level"] = 2
        protocol.state.save()

        # Claim through protocol_state — current_level is 2, TASK-Y is level 2
        claimed = asyncio.run(protocol.claim_next_task_async(max_wait=0, poll_interval=0.01))

        assert claimed is not None
        assert claimed["id"] == "TASK-Y"

        # TASK-X was already complete, should remain complete
        assert protocol.state.get_task_status("TASK-X") == TaskStatus.COMPLETE.value
