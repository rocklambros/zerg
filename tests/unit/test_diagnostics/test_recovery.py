"""Tests for RecoveryPlanner, RecoveryStep, and RecoveryPlan."""

from __future__ import annotations

import pytest

from zerg.commands.debug import DiagnosticResult
from zerg.diagnostics.recovery import (
    DESIGN_ESCALATION_TASK_THRESHOLD,
    RECOVERY_TEMPLATES,
    RecoveryPlan,
    RecoveryPlanner,
    RecoveryStep,
)
from zerg.diagnostics.state_introspector import ZergHealthReport


class TestRecoveryStep:
    def test_to_dict(self) -> None:
        step = RecoveryStep(
            description="Delete things",
            command="rm -rf temp",
            risk="destructive",
            reversible=False,
        )
        d = step.to_dict()
        assert d["description"] == "Delete things"
        assert d["risk"] == "destructive"
        assert d["reversible"] is False


class TestRecoveryPlan:
    def test_to_dict(self) -> None:
        plan = RecoveryPlan(
            problem="Workers crashed",
            root_cause="OOM",
            steps=[RecoveryStep(description="Restart", command="zerg rush")],
            verification_command="zerg status",
            prevention="Increase memory",
        )
        d = plan.to_dict()
        assert d["problem"] == "Workers crashed"
        assert len(d["steps"]) == 1
        assert d["verification_command"] == "zerg status"


class TestRecoveryPlanner:
    def _make_result(self, symptom: str = "Error", root_cause: str = "Unknown") -> DiagnosticResult:
        return DiagnosticResult(
            symptom=symptom,
            hypotheses=[],
            root_cause=root_cause,
            recommendation="Fix it",
        )

    def _make_health(
        self,
        feature: str = "test",
        failed: list[dict] | None = None,
        global_error: str | None = None,
    ) -> ZergHealthReport:
        return ZergHealthReport(
            feature=feature,
            state_exists=True,
            total_tasks=5,
            failed_tasks=failed or [],
            global_error=global_error,
        )

    def test_plan_basic(self) -> None:
        planner = RecoveryPlanner()
        result = self._make_result()
        plan = planner.plan(result)
        assert isinstance(plan, RecoveryPlan)
        assert plan.problem == "Error"
        assert len(plan.steps) > 0

    @pytest.mark.parametrize(
        "symptom,root_cause,expected",
        [
            ("Worker crashed", "Worker failure", "worker_crash"),
            ("JSON parse error", "Corrupt state", "state_corruption"),
            ("Merge conflict", "Git conflict", "git_conflict"),
            ("Address already in use", "Port conflict", "port_conflict"),
            ("No space left", "Disk full", "disk_space"),
            ("ModuleNotFoundError: No module named 'foo'", "Missing module", "import_error"),
        ],
    )
    def test_classify_error(self, symptom, root_cause, expected) -> None:
        planner = RecoveryPlanner()
        result = self._make_result(symptom=symptom, root_cause=root_cause)
        category = planner._classify_error(result, None)
        assert category == expected

    def test_classify_task_failure_from_health(self) -> None:
        planner = RecoveryPlanner()
        result = self._make_result()
        health = self._make_health(failed=[{"task_id": "T1", "error": "fail"}])
        category = planner._classify_error(result, health)
        assert category == "task_failure"

    def test_plan_with_health(self) -> None:
        planner = RecoveryPlanner()
        result = self._make_result(symptom="Task failed", root_cause="Build error")
        health = self._make_health(
            feature="auth",
            failed=[{"task_id": "T1", "error": "err", "worker_id": 2}],
        )
        plan = planner.plan(result, health=health)
        assert len(plan.steps) > 0
        assert plan.verification_command != ""

    def test_plan_substitutes_feature(self) -> None:
        planner = RecoveryPlanner()
        result = self._make_result(symptom="JSON corrupt", root_cause="Corrupt state")
        health = self._make_health(feature="my-feat")
        plan = planner.plan(result, health=health)
        has_feature = any("my-feat" in s.command for s in plan.steps)
        assert has_feature

    def test_all_template_categories_exist(self) -> None:
        expected = {
            "worker_crash",
            "state_corruption",
            "git_conflict",
            "port_conflict",
            "disk_space",
            "import_error",
            "task_failure",
        }
        assert set(RECOVERY_TEMPLATES.keys()) == expected

    def test_execute_step_success(self) -> None:
        planner = RecoveryPlanner()
        step = RecoveryStep(description="Test", command="echo success")
        result = planner.execute_step(step)
        assert result["success"] is True
        assert result["skipped"] is False

    def test_execute_step_failure(self) -> None:
        planner = RecoveryPlanner()
        step = RecoveryStep(description="Test", command="false")
        result = planner.execute_step(step)
        assert result["success"] is False


class TestDesignEscalation:
    def _make_result(
        self,
        symptom: str = "Error",
        root_cause: str = "Unknown",
        recommendation: str = "Fix it",
    ) -> DiagnosticResult:
        return DiagnosticResult(
            symptom=symptom,
            hypotheses=[],
            root_cause=root_cause,
            recommendation=recommendation,
        )

    def _make_health(
        self,
        feature: str = "test",
        failed: list[dict] | None = None,
        global_error: str | None = None,
    ) -> ZergHealthReport:
        return ZergHealthReport(
            feature=feature,
            state_exists=True,
            total_tasks=10,
            failed_tasks=failed or [],
            global_error=global_error,
        )

    def test_multi_task_failure_triggers_escalation(self) -> None:
        planner = RecoveryPlanner()
        result = self._make_result(symptom="Tasks failing")
        health = self._make_health(
            failed=[{"task_id": f"T{i}", "error": "fail", "level": 2} for i in range(DESIGN_ESCALATION_TASK_THRESHOLD)]
        )
        plan = planner.plan(result, health=health)
        assert plan.needs_design is True
        assert "level 2" in plan.design_reason

    def test_architectural_keywords_trigger_escalation(self) -> None:
        planner = RecoveryPlanner()
        result = self._make_result(
            root_cause="Need to refactor the auth module",
            recommendation="Refactor auth",
        )
        plan = planner.plan(result)
        assert plan.needs_design is True
        assert "refactor" in plan.design_reason

    def test_wide_blast_radius_triggers_escalation(self) -> None:
        planner = RecoveryPlanner()
        result = self._make_result(symptom="Tasks failing")
        health = self._make_health(
            failed=[
                {"task_id": "T1", "error": "fail", "owned_files": ["a.py", "b.py"]},
                {"task_id": "T2", "error": "fail", "owned_files": ["c.py"]},
            ]
        )
        plan = planner.plan(result, health=health)
        assert plan.needs_design is True
        assert "3 files" in plan.design_reason

    def test_simple_failure_does_not_trigger(self) -> None:
        planner = RecoveryPlanner()
        result = self._make_result(symptom="Task failed", root_cause="Build error")
        health = self._make_health(failed=[{"task_id": "T1", "error": "compile error", "level": 1}])
        plan = planner.plan(result, health=health)
        assert plan.needs_design is False

    def test_to_dict_serializes_design_fields(self) -> None:
        plan = RecoveryPlan(
            problem="p",
            root_cause="c",
            needs_design=True,
            design_reason="task graph flaw",
        )
        d = plan.to_dict()
        assert d["needs_design"] is True
        assert d["design_reason"] == "task graph flaw"
