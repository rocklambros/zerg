"""Integration tests for bite-sized step execution.

Tests end-to-end flow for step-based task execution:
- Design command generating steps with --detail high
- Step order enforcement during execution
- Heartbeat step tracking
- Formatter integration
- Adaptive detail triggers

These tests validate BITE-L4-002 acceptance criteria.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from zerg.heartbeat import HeartbeatMonitor, HeartbeatWriter
from zerg.step_generator import (
    DetailLevel,
    Step,
    StepAction,
    StepGenerator,
    VerifyMode,
    generate_steps_for_task,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def step_execution_repo(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary git repository for step execution tests.

    Sets up a Python project with pyproject.toml for formatter detection.
    """
    orig_dir = os.getcwd()

    # Initialize git repo
    subprocess.run(
        ["git", "init", "-q", "-b", "main"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )

    # Create project structure
    (tmp_path / "pyproject.toml").write_text("""[project]
name = "test-project"
version = "0.1.0"

[tool.ruff]
line-length = 88
""")

    (tmp_path / "README.md").write_text("# Test Project")
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "unit").mkdir()

    # Initial commit
    subprocess.run(
        ["git", "add", "-A"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "Initial commit"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )

    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(orig_dir)


@pytest.fixture
def sample_task_with_steps() -> dict[str, Any]:
    """Create a sample task definition for step testing."""
    return {
        "id": "BITE-TEST-001",
        "title": "Create formatter detector",
        "description": "Implement formatter auto-detection",
        "level": 1,
        "dependencies": [],
        "files": {
            "create": ["zerg/formatter_detector.py"],
            "modify": [],
            "read": [],
        },
        "verification": {
            "command": "pytest tests/unit/test_formatter_detector.py -v --tb=short",
            "timeout_seconds": 120,
        },
        "estimate_minutes": 15,
    }


@pytest.fixture
def task_graph_with_steps(tmp_path: Path) -> dict[str, Any]:
    """Create a task graph with steps generated at high detail."""
    return {
        "feature": "step-test",
        "version": "2.0",
        "generated": "2026-02-04T10:00:00Z",
        "total_tasks": 2,
        "estimated_duration_minutes": 30,
        "max_parallelization": 2,
        "tasks": [
            {
                "id": "STEP-L1-001",
                "title": "Create module A",
                "description": "First module",
                "level": 1,
                "dependencies": [],
                "files": {
                    "create": ["src/module_a.py"],
                    "modify": [],
                    "read": [],
                },
                "verification": {
                    "command": "python -c 'from src.module_a import *'",
                    "timeout_seconds": 60,
                },
                "estimate_minutes": 10,
                "steps": [
                    {"step": 1, "action": "write_test", "file": "tests/unit/test_module_a.py", "verify": "none"},
                    {
                        "step": 2,
                        "action": "verify_fail",
                        "run": "pytest tests/unit/test_module_a.py -v",
                        "verify": "exit_code_nonzero",
                    },
                    {"step": 3, "action": "implement", "file": "src/module_a.py", "verify": "none"},
                    {
                        "step": 4,
                        "action": "verify_pass",
                        "run": "pytest tests/unit/test_module_a.py -v",
                        "verify": "exit_code",
                    },
                    {
                        "step": 5,
                        "action": "format",
                        "run": "ruff format tests/unit/test_module_a.py src/module_a.py",
                        "verify": "exit_code",
                    },
                    {
                        "step": 6,
                        "action": "commit",
                        "run": "git add -A && git commit -m 'feat(STEP-L1-001): Create module A'",
                        "verify": "exit_code",
                    },
                ],
            },
            {
                "id": "STEP-L1-002",
                "title": "Create module B",
                "description": "Second module",
                "level": 1,
                "dependencies": [],
                "files": {
                    "create": ["src/module_b.py"],
                    "modify": [],
                    "read": [],
                },
                "verification": {
                    "command": "python -c 'from src.module_b import *'",
                    "timeout_seconds": 60,
                },
                "estimate_minutes": 10,
                # No steps - classic mode
            },
        ],
        "levels": {
            "1": {
                "name": "foundation",
                "tasks": ["STEP-L1-001", "STEP-L1-002"],
                "parallel": True,
                "estimated_minutes": 10,
            },
        },
    }


@pytest.fixture
def heartbeat_state_dir(tmp_path: Path) -> Path:
    """Create a temporary state directory for heartbeat files."""
    state_dir = tmp_path / ".zerg" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


# ============================================================================
# Test Class: Step Generation Integration
# ============================================================================


class TestStepGenerationIntegration:
    """Integration tests for step generation within design flow."""

    def test_generate_steps_for_task_high_detail(
        self, step_execution_repo: Path, sample_task_with_steps: dict[str, Any]
    ) -> None:
        """Test step generation at high detail level."""
        steps = generate_steps_for_task(
            sample_task_with_steps,
            detail_level="high",
            project_root=step_execution_repo,
        )

        assert len(steps) == 6

        actions = [s["action"] for s in steps]
        expected_actions = [
            "write_test",
            "verify_fail",
            "implement",
            "verify_pass",
            "format",
            "commit",
        ]
        assert actions == expected_actions

        write_test_step = steps[0]
        assert "code_snippet" in write_test_step
        assert write_test_step["code_snippet"] is not None

        implement_step = steps[2]
        assert "code_snippet" in implement_step
        assert implement_step["code_snippet"] is not None

    def test_generate_steps_for_task_standard_detail(
        self, step_execution_repo: Path, sample_task_with_steps: dict[str, Any]
    ) -> None:
        """Test step generation at standard detail level (backward compatible)."""
        steps = generate_steps_for_task(
            sample_task_with_steps,
            detail_level="standard",
            project_root=step_execution_repo,
        )

        assert len(steps) == 0

    def test_step_generator_detects_ruff_formatter(
        self, step_execution_repo: Path, sample_task_with_steps: dict[str, Any]
    ) -> None:
        """Test that StepGenerator detects ruff from pyproject.toml."""
        generator = StepGenerator(project_root=step_execution_repo)
        steps = generator.generate_steps(sample_task_with_steps, DetailLevel.HIGH)

        format_step = next((s for s in steps if s.action == StepAction.FORMAT), None)
        assert format_step is not None
        assert "ruff format" in format_step.run


# ============================================================================
# Test Class: Step Order Enforcement
# ============================================================================


class TestStepOrderEnforcement:
    """Tests for strict step order during execution."""

    def test_steps_have_sequential_numbers(
        self, sample_task_with_steps: dict[str, Any], step_execution_repo: Path
    ) -> None:
        """Test that generated steps have sequential step numbers."""
        steps = generate_steps_for_task(
            sample_task_with_steps,
            detail_level="high",
            project_root=step_execution_repo,
        )

        step_numbers = [s["step"] for s in steps]
        assert step_numbers == [1, 2, 3, 4, 5, 6]

    def test_step_verification_modes_are_valid(
        self, sample_task_with_steps: dict[str, Any], step_execution_repo: Path
    ) -> None:
        """Test that all steps have valid verification modes."""
        steps = generate_steps_for_task(
            sample_task_with_steps,
            detail_level="high",
            project_root=step_execution_repo,
        )

        valid_verify_modes = {"exit_code", "exit_code_nonzero", "none"}
        for step in steps:
            assert step["verify"] in valid_verify_modes


# ============================================================================
# Test Class: Heartbeat Step Tracking
# ============================================================================


class TestHeartbeatStepTracking:
    """Tests for heartbeat updates during step execution."""

    def test_heartbeat_writer_tracks_step(self, heartbeat_state_dir: Path) -> None:
        """Test that HeartbeatWriter can track current step."""
        writer = HeartbeatWriter(worker_id=1, state_dir=heartbeat_state_dir)

        hb = writer.write(
            task_id="BITE-TEST-001",
            step="step_3_implement",
            progress_pct=50,
        )

        assert hb.worker_id == 1
        assert hb.task_id == "BITE-TEST-001"
        assert hb.step == "step_3_implement"
        assert hb.progress_pct == 50

    def test_heartbeat_step_progress_updates(self, heartbeat_state_dir: Path) -> None:
        """Test heartbeat updates as steps progress."""
        writer = HeartbeatWriter(worker_id=3, state_dir=heartbeat_state_dir)
        monitor = HeartbeatMonitor(state_dir=heartbeat_state_dir)

        step_states = [
            ("step_1_write_test", 16),
            ("step_2_verify_fail", 33),
            ("step_3_implement", 50),
            ("step_4_verify_pass", 66),
            ("step_5_format", 83),
            ("step_6_commit", 100),
        ]

        for step_name, progress in step_states:
            writer.write(task_id="BITE-TEST-003", step=step_name, progress_pct=progress)
            hb = monitor.read(worker_id=3)
            assert hb is not None
            assert hb.step == step_name
            assert hb.progress_pct == progress


# ============================================================================
# Test Class: Formatter Integration
# ============================================================================


class TestFormatterIntegration:
    """Tests for formatter detection and integration in steps."""

    def test_step_generator_uses_detected_formatter(self, step_execution_repo: Path) -> None:
        """Test that step generator uses the detected formatter."""
        task = {
            "id": "FMT-001",
            "title": "Test formatter",
            "files": {"create": ["src/fmt_test.py"], "modify": [], "read": []},
            "verification": {"command": "pytest tests/unit/test_fmt.py"},
        }

        generator = StepGenerator(project_root=step_execution_repo)
        steps = generator.generate_steps(task, DetailLevel.MEDIUM)

        format_step = next((s for s in steps if s.action == StepAction.FORMAT), None)
        assert format_step is not None
        assert "ruff format" in format_step.run


# ============================================================================
# Test Class: End-to-End Design to Execute Flow
# ============================================================================


class TestDesignToExecuteFlow:
    """End-to-end tests for design -> execute flow with steps."""

    def test_task_graph_with_steps_structure(self, task_graph_with_steps: dict[str, Any]) -> None:
        """Test that task graph with steps has correct structure."""
        tasks = task_graph_with_steps["tasks"]

        task_with_steps = tasks[0]
        assert "steps" in task_with_steps
        assert len(task_with_steps["steps"]) == 6

        task_without_steps = tasks[1]
        assert "steps" not in task_without_steps

    def test_step_execution_simulation(self, task_graph_with_steps: dict[str, Any], heartbeat_state_dir: Path) -> None:
        """Simulate step execution with heartbeat tracking."""
        task = task_graph_with_steps["tasks"][0]
        steps = task["steps"]
        task_id = task["id"]

        writer = HeartbeatWriter(worker_id=1, state_dir=heartbeat_state_dir)
        monitor = HeartbeatMonitor(state_dir=heartbeat_state_dir)

        for i, step in enumerate(steps):
            step_name = f"step_{step['step']}_{step['action']}"
            progress = int(((i + 1) / len(steps)) * 100)

            writer.write(task_id=task_id, step=step_name, progress_pct=progress)

            hb = monitor.read(worker_id=1)
            assert hb is not None
            assert hb.task_id == task_id
            assert hb.step == step_name

        final_hb = monitor.read(worker_id=1)
        assert final_hb is not None
        assert final_hb.progress_pct == 100


# ============================================================================
# Test Class: Error Handling
# ============================================================================


class TestStepExecutionErrors:
    """Tests for error handling during step execution."""

    def test_heartbeat_handles_missing_state_dir(self, tmp_path: Path) -> None:
        """Test heartbeat handles missing state directory gracefully."""
        nonexistent_dir = tmp_path / "nonexistent"

        writer = HeartbeatWriter(worker_id=1, state_dir=nonexistent_dir)
        hb = writer.write(task_id="TEST", step="test", progress_pct=0)

        assert hb is not None
        assert nonexistent_dir.exists()

    def test_heartbeat_monitor_handles_missing_file(self, heartbeat_state_dir: Path) -> None:
        """Test heartbeat monitor handles missing heartbeat file."""
        monitor = HeartbeatMonitor(state_dir=heartbeat_state_dir)

        hb = monitor.read(worker_id=999)
        assert hb is None


# ============================================================================
# Test Class: Step Verification
# ============================================================================


class TestStepVerification:
    """Tests for step verification behavior."""

    def test_step_to_dict_serialization(self) -> None:
        """Test Step dataclass serialization to dict."""
        step = Step(
            step=1,
            action=StepAction.WRITE_TEST,
            file="tests/test_foo.py",
            code_snippet="def test_foo(): pass",
            run=None,
            verify=VerifyMode.NONE,
        )

        d = step.to_dict()

        assert d["step"] == 1
        assert d["action"] == "write_test"
        assert d["file"] == "tests/test_foo.py"
        assert d["code_snippet"] == "def test_foo(): pass"
        assert d["verify"] == "none"
        assert "run" not in d

    def test_verify_mode_enum_values(self) -> None:
        """Test VerifyMode enum has expected members."""
        assert VerifyMode.EXIT_CODE.value == "exit_code"
        assert VerifyMode.EXIT_CODE_NONZERO.value == "exit_code_nonzero"
        assert VerifyMode.NONE.value == "none"

    def test_step_action_enum_values(self) -> None:
        """Test StepAction enum has expected members."""
        expected = {
            "WRITE_TEST": "write_test",
            "VERIFY_FAIL": "verify_fail",
            "IMPLEMENT": "implement",
            "VERIFY_PASS": "verify_pass",
            "FORMAT": "format",
            "COMMIT": "commit",
        }
        for name, value in expected.items():
            assert getattr(StepAction, name).value == value
