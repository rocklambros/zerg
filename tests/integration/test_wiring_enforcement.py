"""Integration tests for wiring enforcement.

End-to-end tests proving:
- validate_module_wiring() detects real orphaned modules in zerg/
- task-graph.json with consumers/integration_test fields parses correctly
- CI workflow YAML is valid
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from zerg.validate_commands import (
    WIRING_EXEMPT_NAMES,
    validate_module_wiring,
)

ZERG_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = ZERG_ROOT / "zerg"
TESTS_DIR = ZERG_ROOT / "tests"
SPEC_DIR = ZERG_ROOT / ".gsd" / "specs" / "integration-wiring-enforcement"


class TestModuleWiringEndToEnd:
    """End-to-end tests running validate_module_wiring against the real zerg/ package."""

    def test_detects_orphaned_modules(self) -> None:
        """validate_module_wiring must detect at least one orphaned module in zerg/."""
        passed, messages = validate_module_wiring(
            package_dir=PACKAGE_DIR,
            tests_dir=TESTS_DIR,
            strict=False,
        )
        # Warning mode always passes
        assert passed is True
        # There are known orphaned modules (cross-cutting capabilities not yet wired)
        assert len(messages) > 0, "Expected at least one orphaned module warning"
        for msg in messages:
            assert "orphaned module" in msg

    def test_strict_mode_fails_on_orphans(self) -> None:
        """In strict mode, orphaned modules must cause failure."""
        passed, messages = validate_module_wiring(
            package_dir=PACKAGE_DIR,
            tests_dir=TESTS_DIR,
            strict=True,
        )
        assert passed is False
        assert len(messages) > 0

    def test_exempt_files_not_flagged(self) -> None:
        """__init__.py, __main__.py, conftest.py must never appear in warnings."""
        _, messages = validate_module_wiring(
            package_dir=PACKAGE_DIR,
            tests_dir=TESTS_DIR,
        )
        for msg in messages:
            for exempt_name in WIRING_EXEMPT_NAMES:
                assert exempt_name not in msg, f"Exempt file {exempt_name} should not be flagged: {msg}"

    def test_entry_points_not_flagged(self) -> None:
        """Files with 'if __name__' guard must not be flagged."""
        _, messages = validate_module_wiring(
            package_dir=PACKAGE_DIR,
            tests_dir=TESTS_DIR,
        )
        flagged_files = [msg.split(":")[0] for msg in messages]
        for flagged in flagged_files:
            file_path = PACKAGE_DIR / flagged
            if file_path.exists():
                content = file_path.read_text()
                assert "if __name__" not in content, f"{flagged} has __name__ guard but was still flagged"


class TestTaskGraphSchema:
    """Tests that the task-graph.json with consumers/integration_test fields parses correctly."""

    @pytest.fixture()
    def task_graph(self) -> dict:
        graph_path = SPEC_DIR / "task-graph.json"
        if not graph_path.exists():
            pytest.skip("task-graph.json not found (feature spec not present)")
        return json.loads(graph_path.read_text())

    def test_task_graph_has_consumers_field(self, task_graph: dict) -> None:
        """Every task in task-graph.json must have a consumers field."""
        for task in task_graph["tasks"]:
            assert "consumers" in task, f"{task['id']} missing 'consumers' field"
            assert isinstance(task["consumers"], list)

    def test_task_graph_has_integration_test_field(self, task_graph: dict) -> None:
        """Every task in task-graph.json must have an integration_test field."""
        for task in task_graph["tasks"]:
            assert "integration_test" in task, f"{task['id']} missing 'integration_test' field"

    def test_consumer_references_valid(self, task_graph: dict) -> None:
        """Consumer references must point to real task IDs in the graph."""
        task_ids = {t["id"] for t in task_graph["tasks"]}
        for task in task_graph["tasks"]:
            for consumer_id in task.get("consumers", []):
                assert consumer_id in task_ids, (
                    f"{task['id']} references consumer {consumer_id} which does not exist in the task graph"
                )

    def test_integration_test_when_consumers_nonempty(self, task_graph: dict) -> None:
        """Tasks with non-empty consumers should have an integration_test path."""
        for task in task_graph["tasks"]:
            if task.get("consumers"):
                assert task.get("integration_test") is not None, (
                    f"{task['id']} has consumers {task['consumers']} but no integration_test"
                )


class TestCIWorkflow:
    """Tests that the CI pytest workflow YAML is valid."""

    @pytest.fixture()
    def workflow(self) -> dict:
        workflow_path = ZERG_ROOT / ".github" / "workflows" / "pytest.yml"
        if not workflow_path.exists():
            pytest.skip("pytest.yml workflow not found")
        return yaml.safe_load(workflow_path.read_text())

    def test_workflow_valid_yaml(self, workflow: dict) -> None:
        """The pytest.yml workflow must parse as valid YAML."""
        assert isinstance(workflow, dict)
        assert "name" in workflow
        assert "jobs" in workflow

    def _triggers(self, workflow: dict) -> dict:
        """Get workflow triggers, handling YAML 'on:' parsed as True key."""
        return workflow.get("on", workflow.get(True, {}))

    def test_workflow_has_test_job(self, workflow: dict) -> None:
        """Workflow must have a test job."""
        assert "test" in workflow["jobs"]

    def test_workflow_runs_pytest(self, workflow: dict) -> None:
        """Test job must run pytest."""
        steps = workflow["jobs"]["test"]["steps"]
        step_runs = [s.get("run", "") for s in steps]
        has_pytest = any("pytest" in run for run in step_runs)
        assert has_pytest, "Workflow must run pytest"

    def test_workflow_runs_validate_commands(self, workflow: dict) -> None:
        """Test job must run validate_commands."""
        steps = workflow["jobs"]["test"]["steps"]
        step_runs = [s.get("run", "") for s in steps]
        has_validate = any("validate_commands" in run for run in step_runs)
        assert has_validate, "Workflow must run validate_commands"

    def test_workflow_triggers_on_pr(self, workflow: dict) -> None:
        """Workflow must trigger on pull requests."""
        triggers = self._triggers(workflow)
        assert "pull_request" in triggers, "Workflow must trigger on pull_request"
