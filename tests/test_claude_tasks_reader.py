"""Tests for ClaudeTasksReader — reading Claude Code Tasks from disk."""

import json

from zerg.claude_tasks_reader import ClaudeTasksReader
from zerg.constants import TaskStatus


def _write_task(task_dir, task_id, subject, status="pending", description="", blocked_by=None):
    """Helper to write a task JSON file."""
    data = {
        "id": str(task_id),
        "subject": subject,
        "description": description,
        "status": status,
        "activeForm": "Working",
        "blocks": [],
        "blockedBy": blocked_by or [],
    }
    path = task_dir / f"{task_id}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class TestFindFeatureTaskList:
    def test_discovers_zerg_tasks(self, tmp_path):
        task_list = tmp_path / "uuid-abc"
        task_list.mkdir()
        _write_task(task_list, 1, "[L1] Create types", description="Feature: my-feature")
        _write_task(task_list, 2, "[L1] Create schema", description="Feature: my-feature")
        _write_task(task_list, 3, "[L2] Build service", description="Feature: my-feature")

        reader = ClaudeTasksReader(tasks_dir=tmp_path)
        result = reader.find_feature_task_list("my-feature")
        assert result == task_list

    def test_no_match_returns_none(self, tmp_path):
        task_list = tmp_path / "uuid-abc"
        task_list.mkdir()
        # No [L{n}] tasks
        _write_task(task_list, 1, "[Debug] Some debug task")

        reader = ClaudeTasksReader(tasks_dir=tmp_path)
        result = reader.find_feature_task_list("my-feature")
        assert result is None

    def test_empty_dir_returns_none(self, tmp_path):
        reader = ClaudeTasksReader(tasks_dir=tmp_path)
        result = reader.find_feature_task_list("my-feature")
        assert result is None

    def test_nonexistent_dir_returns_none(self, tmp_path):
        reader = ClaudeTasksReader(tasks_dir=tmp_path / "nonexistent")
        result = reader.find_feature_task_list("my-feature")
        assert result is None

    def test_prefers_feature_match(self, tmp_path):
        # Dir with ZERG tasks but no feature match
        unrelated = tmp_path / "uuid-unrelated"
        unrelated.mkdir()
        _write_task(unrelated, 1, "[L1] Task A", description="Feature: other-feature")
        _write_task(unrelated, 2, "[L1] Task B", description="Feature: other-feature")
        _write_task(unrelated, 3, "[L2] Task C", description="Feature: other-feature")

        # Dir with ZERG tasks AND feature match
        matching = tmp_path / "uuid-matching"
        matching.mkdir()
        _write_task(matching, 1, "[L1] Task X", description="Feature: my-feature")
        _write_task(matching, 2, "[L1] Task Y", description="Feature: my-feature")
        _write_task(matching, 3, "[L2] Task Z", description="Feature: my-feature")

        # Touch matching dir to make it newest
        (matching / ".lock").touch()

        reader = ClaudeTasksReader(tasks_dir=tmp_path)
        result = reader.find_feature_task_list("my-feature")
        assert result == matching

    def test_fallback_to_any_zerg_tasks(self, tmp_path):
        """Falls back to any ZERG task list when no feature match."""
        task_list = tmp_path / "uuid-abc"
        task_list.mkdir()
        _write_task(task_list, 1, "[L1] Task A")
        _write_task(task_list, 2, "[L1] Task B")
        _write_task(task_list, 3, "[L2] Task C")

        reader = ClaudeTasksReader(tasks_dir=tmp_path)
        result = reader.find_feature_task_list("nonexistent-feature")
        assert result == task_list

    def test_caches_result(self, tmp_path):
        task_list = tmp_path / "uuid-abc"
        task_list.mkdir()
        _write_task(task_list, 1, "[L1] Task A", description="Feature: test")
        _write_task(task_list, 2, "[L1] Task B", description="Feature: test")
        _write_task(task_list, 3, "[L2] Task C", description="Feature: test")

        reader = ClaudeTasksReader(tasks_dir=tmp_path)
        result1 = reader.find_feature_task_list("test")
        result2 = reader.find_feature_task_list("test")
        assert result1 == result2 == task_list


class TestReadTasks:
    def test_synthesizes_state(self, tmp_path):
        task_list = tmp_path / "uuid-abc"
        task_list.mkdir()
        _write_task(task_list, 1, "[L1] Create types", status="completed")
        _write_task(task_list, 2, "[L1] Create schema", status="completed")
        _write_task(task_list, 3, "[L2] Build service", status="in_progress")
        _write_task(task_list, 4, "[L2] Build routes", status="pending")

        reader = ClaudeTasksReader(tasks_dir=tmp_path)
        state = reader.read_tasks(task_list)

        assert "tasks" in state
        assert "workers" in state
        assert "levels" in state
        assert "execution_log" in state
        assert len(state["tasks"]) == 4
        assert state["workers"] == {}

    def test_status_mapping_pending(self, tmp_path):
        task_list = tmp_path / "uuid-abc"
        task_list.mkdir()
        _write_task(task_list, 1, "[L1] Task", status="pending")

        reader = ClaudeTasksReader(tasks_dir=tmp_path)
        state = reader.read_tasks(task_list)
        task = state["tasks"]["TASK-1"]
        assert task["status"] == TaskStatus.PENDING.value

    def test_status_mapping_in_progress(self, tmp_path):
        task_list = tmp_path / "uuid-abc"
        task_list.mkdir()
        _write_task(task_list, 1, "[L1] Task", status="in_progress")

        reader = ClaudeTasksReader(tasks_dir=tmp_path)
        state = reader.read_tasks(task_list)
        task = state["tasks"]["TASK-1"]
        assert task["status"] == TaskStatus.IN_PROGRESS.value

    def test_status_mapping_completed(self, tmp_path):
        task_list = tmp_path / "uuid-abc"
        task_list.mkdir()
        _write_task(task_list, 1, "[L1] Task", status="completed")

        reader = ClaudeTasksReader(tasks_dir=tmp_path)
        state = reader.read_tasks(task_list)
        task = state["tasks"]["TASK-1"]
        assert task["status"] == TaskStatus.COMPLETE.value

    def test_status_mapping_blocked(self, tmp_path):
        task_list = tmp_path / "uuid-abc"
        task_list.mkdir()
        _write_task(task_list, 1, "[L1] Task", status="pending", blocked_by=["2", "3"])

        reader = ClaudeTasksReader(tasks_dir=tmp_path)
        state = reader.read_tasks(task_list)
        task = state["tasks"]["TASK-1"]
        assert task["status"] == TaskStatus.BLOCKED.value

    def test_level_extraction(self, tmp_path):
        task_list = tmp_path / "uuid-abc"
        task_list.mkdir()
        _write_task(task_list, 1, "[L1] Foundation task")
        _write_task(task_list, 2, "[L2] Core task")
        _write_task(task_list, 3, "[L3] Integration task")

        reader = ClaudeTasksReader(tasks_dir=tmp_path)
        state = reader.read_tasks(task_list)

        assert state["tasks"]["TASK-1"]["level"] == 1
        assert state["tasks"]["TASK-2"]["level"] == 2
        assert state["tasks"]["TASK-3"]["level"] == 3

    def test_levels_dict_built(self, tmp_path):
        task_list = tmp_path / "uuid-abc"
        task_list.mkdir()
        _write_task(task_list, 1, "[L1] Task A", status="completed")
        _write_task(task_list, 2, "[L1] Task B", status="completed")
        _write_task(task_list, 3, "[L2] Task C", status="in_progress")

        reader = ClaudeTasksReader(tasks_dir=tmp_path)
        state = reader.read_tasks(task_list)

        assert "1" in state["levels"]
        assert "2" in state["levels"]
        assert state["levels"]["1"]["status"] == "complete"
        assert state["levels"]["2"]["status"] == "running"

    def test_corrupted_json_skipped(self, tmp_path):
        task_list = tmp_path / "uuid-abc"
        task_list.mkdir()
        _write_task(task_list, 1, "[L1] Good task", status="completed")

        # Write corrupted JSON
        bad_path = task_list / "2.json"
        bad_path.write_text("{invalid json", encoding="utf-8")

        reader = ClaudeTasksReader(tasks_dir=tmp_path)
        state = reader.read_tasks(task_list)

        # Should have the good task and skip the bad one
        assert len(state["tasks"]) == 1
        assert "TASK-1" in state["tasks"]

    def test_non_level_tasks_skipped(self, tmp_path):
        task_list = tmp_path / "uuid-abc"
        task_list.mkdir()
        _write_task(task_list, 1, "[L1] Execution task")
        _write_task(task_list, 2, "[Plan] Planning task")
        _write_task(task_list, 3, "[Design] Design task")
        _write_task(task_list, 4, "[Debug] Debug task")

        reader = ClaudeTasksReader(tasks_dir=tmp_path)
        state = reader.read_tasks(task_list)

        # Only the [L1] task should be included
        assert len(state["tasks"]) == 1
        assert "TASK-1" in state["tasks"]

    def test_empty_dir_returns_empty_state(self, tmp_path):
        task_list = tmp_path / "uuid-abc"
        task_list.mkdir()

        reader = ClaudeTasksReader(tasks_dir=tmp_path)
        state = reader.read_tasks(task_list)

        assert state["tasks"] == {}
        assert state["workers"] == {}

    def test_current_level_detection(self, tmp_path):
        task_list = tmp_path / "uuid-abc"
        task_list.mkdir()
        _write_task(task_list, 1, "[L1] Task A", status="completed")
        _write_task(task_list, 2, "[L1] Task B", status="completed")
        _write_task(task_list, 3, "[L2] Task C", status="in_progress")
        _write_task(task_list, 4, "[L3] Task D", status="pending")

        reader = ClaudeTasksReader(tasks_dir=tmp_path)
        state = reader.read_tasks(task_list)

        assert state["current_level"] == 2


class TestMapStatus:
    def test_pending_no_blockers(self):
        assert ClaudeTasksReader._map_status("pending", []) == TaskStatus.PENDING.value

    def test_pending_with_blockers(self):
        assert ClaudeTasksReader._map_status("pending", ["1", "2"]) == TaskStatus.BLOCKED.value

    def test_in_progress(self):
        assert ClaudeTasksReader._map_status("in_progress", []) == TaskStatus.IN_PROGRESS.value

    def test_completed(self):
        assert ClaudeTasksReader._map_status("completed", []) == TaskStatus.COMPLETE.value

    def test_unknown_status_defaults_to_pending(self):
        assert ClaudeTasksReader._map_status("weird_status", []) == TaskStatus.PENDING.value
