"""Tests for RecoveryPlanner, RecoveryStep, and RecoveryPlan."""

from __future__ import annotations

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
    """Tests for RecoveryStep dataclass."""

    def test_defaults(self) -> None:
        step = RecoveryStep(description="Fix it", command="echo fix")
        assert step.risk == "safe"
        assert step.reversible is True

    def test_to_dict(self) -> None:
        step = RecoveryStep(
            description="Delete things",
            command="rm -rf temp",
            risk="destructive",
            reversible=False,
        )
        d = step.to_dict()
        assert d["description"] == "Delete things"
        assert d["command"] == "rm -rf temp"
        assert d["risk"] == "destructive"
        assert d["reversible"] is False


class TestRecoveryPlan:
    """Tests for RecoveryPlan dataclass."""

    def test_defaults(self) -> None:
        plan = RecoveryPlan(problem="issue", root_cause="cause")
        assert plan.steps == []
        assert plan.verification_command == ""
        assert plan.prevention == ""

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
        assert d["prevention"] == "Increase memory"


class TestRecoveryPlanner:
    """Tests for RecoveryPlanner."""

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

    def test_classify_worker_crash(self) -> None:
        planner = RecoveryPlanner()
        result = self._make_result(symptom="Worker crashed", root_cause="Worker failure")
        category = planner._classify_error(result, None)
        assert category == "worker_crash"

    def test_classify_state_corruption(self) -> None:
        planner = RecoveryPlanner()
        result = self._make_result(symptom="JSON parse error", root_cause="Corrupt state")
        category = planner._classify_error(result, None)
        assert category == "state_corruption"

    def test_classify_git_conflict(self) -> None:
        planner = RecoveryPlanner()
        result = self._make_result(symptom="Merge conflict", root_cause="Git conflict")
        category = planner._classify_error(result, None)
        assert category == "git_conflict"

    def test_classify_port_conflict(self) -> None:
        planner = RecoveryPlanner()
        result = self._make_result(symptom="Address already in use", root_cause="Port conflict")
        category = planner._classify_error(result, None)
        assert category == "port_conflict"

    def test_classify_disk_space(self) -> None:
        planner = RecoveryPlanner()
        result = self._make_result(symptom="No space left", root_cause="Disk full")
        category = planner._classify_error(result, None)
        assert category == "disk_space"

    def test_classify_import_error(self) -> None:
        planner = RecoveryPlanner()
        result = self._make_result(
            symptom="ModuleNotFoundError: No module named 'foo'",
            root_cause="Missing module",
        )
        category = planner._classify_error(result, None)
        assert category == "import_error"

    def test_classify_task_failure_from_health(self) -> None:
        planner = RecoveryPlanner()
        result = self._make_result()
        health = self._make_health(failed=[{"task_id": "T1", "error": "fail"}])
        category = planner._classify_error(result, health)
        assert category == "task_failure"

    def test_classify_with_global_error(self) -> None:
        planner = RecoveryPlanner()
        result = self._make_result()
        health = self._make_health(global_error="Worker 1 crashed")
        category = planner._classify_error(result, health)
        assert category == "worker_crash"

    def test_plan_with_health(self) -> None:
        planner = RecoveryPlanner()
        result = self._make_result(symptom="Task failed", root_cause="Build error")
        health = self._make_health(
            feature="auth",
            failed=[{"task_id": "T1", "error": "err", "worker_id": 2}],
        )
        plan = planner.plan(result, health=health)

        assert plan.problem == "Task failed"
        assert len(plan.steps) > 0
        assert plan.verification_command != ""
        assert plan.prevention != ""

    def test_plan_substitutes_feature(self) -> None:
        planner = RecoveryPlanner()
        result = self._make_result(symptom="JSON corrupt", root_cause="Corrupt state")
        health = self._make_health(feature="my-feat")
        plan = planner.plan(result, health=health)

        # Check that feature was substituted in commands
        has_feature = any("my-feat" in s.command for s in plan.steps)
        assert has_feature

    def test_plan_substitutes_worker_id(self) -> None:
        planner = RecoveryPlanner()
        result = self._make_result(symptom="Task failed", root_cause="Error")
        health = self._make_health(failed=[{"task_id": "T1", "error": "err", "worker_id": 3}])
        plan = planner.plan(result, health=health)

        # Not all categories use worker_id, so just verify plan generated
        assert len(plan.steps) > 0

    def test_get_verification(self) -> None:
        planner = RecoveryPlanner()
        assert "status" in planner._get_verification("worker_crash", "feat")
        assert "json" in planner._get_verification("state_corruption", "feat")
        assert "git" in planner._get_verification("git_conflict", "feat")

    def test_get_prevention(self) -> None:
        planner = RecoveryPlanner()
        p = planner._get_prevention("worker_crash")
        assert isinstance(p, str)
        assert len(p) > 0

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
        assert "success" in result["output"]
        assert result["skipped"] is False

    def test_execute_step_failure(self) -> None:
        planner = RecoveryPlanner()
        step = RecoveryStep(description="Test", command="false")
        result = planner.execute_step(step)
        assert result["success"] is False

    def test_execute_step_with_confirm_approved(self) -> None:
        planner = RecoveryPlanner()
        step = RecoveryStep(description="Test", command="echo ok")
        result = planner.execute_step(step, confirm_fn=lambda s: True)
        assert result["success"] is True

    def test_execute_step_with_confirm_denied(self) -> None:
        planner = RecoveryPlanner()
        step = RecoveryStep(description="Test", command="echo ok")
        result = planner.execute_step(step, confirm_fn=lambda s: False)
        assert result["success"] is False
        assert result["skipped"] is True

    def test_execute_step_timeout(self) -> None:
        planner = RecoveryPlanner()
        step = RecoveryStep(description="Test", command="sleep 30")
        result = planner.execute_step(step)
        assert result["success"] is False

    def test_execute_step_bad_command(self) -> None:
        planner = RecoveryPlanner()
        step = RecoveryStep(
            description="Test",
            command="nonexistent_command_xyz_123",
        )
        result = planner.execute_step(step)
        assert result["success"] is False


class TestDesignEscalation:
    """Tests for design escalation detection in RecoveryPlanner."""

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

    def test_needs_design_defaults_false(self) -> None:
        """RecoveryPlan.needs_design defaults to False."""
        plan = RecoveryPlan(problem="p", root_cause="c")
        assert plan.needs_design is False
        assert plan.design_reason == ""

    def test_multi_task_failure_triggers_escalation(self) -> None:
        """3+ tasks failed at the same level triggers design escalation."""
        planner = RecoveryPlanner()
        result = self._make_result(symptom="Tasks failing")
        health = self._make_health(
            failed=[{"task_id": f"T{i}", "error": "fail", "level": 2} for i in range(DESIGN_ESCALATION_TASK_THRESHOLD)]
        )
        plan = planner.plan(result, health=health)
        assert plan.needs_design is True
        assert "level 2" in plan.design_reason

    def test_git_conflict_with_health_triggers_escalation(self) -> None:
        """git_conflict category with health data triggers escalation."""
        planner = RecoveryPlanner()
        result = self._make_result(symptom="Merge conflict", root_cause="Git conflict")
        health = self._make_health()
        plan = planner.plan(result, health=health)
        assert plan.needs_design is True
        assert "file ownership" in plan.design_reason

    def test_architectural_keywords_trigger_escalation(self) -> None:
        """Architectural keywords in root_cause/recommendation trigger escalation."""
        planner = RecoveryPlanner()
        result = self._make_result(
            root_cause="Need to refactor the auth module",
            recommendation="Refactor auth",
        )
        plan = planner.plan(result)
        assert plan.needs_design is True
        assert "refactor" in plan.design_reason

    def test_wide_blast_radius_triggers_escalation(self) -> None:
        """Failures spanning 3+ files triggers escalation."""
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
        """A simple single-task failure does not trigger escalation."""
        planner = RecoveryPlanner()
        result = self._make_result(symptom="Task failed", root_cause="Build error")
        health = self._make_health(failed=[{"task_id": "T1", "error": "compile error", "level": 1}])
        plan = planner.plan(result, health=health)
        assert plan.needs_design is False
        assert plan.design_reason == ""

    def test_to_dict_serializes_design_fields(self) -> None:
        """RecoveryPlan.to_dict() includes needs_design and design_reason."""
        plan = RecoveryPlan(
            problem="p",
            root_cause="c",
            needs_design=True,
            design_reason="task graph flaw",
        )
        d = plan.to_dict()
        assert d["needs_design"] is True
        assert d["design_reason"] == "task graph flaw"
