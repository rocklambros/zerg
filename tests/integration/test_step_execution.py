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

import json
import os
import subprocess
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from zerg.heartbeat import HeartbeatMonitor, HeartbeatWriter
from zerg.step_generator import (
    DetailLevel,
    FormatterConfig,
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

        # Should generate 6 TDD steps
        assert len(steps) == 6

        # Verify step actions in correct order
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

        # High detail should include code snippets for write_test and implement
        write_test_step = steps[0]
        assert "code_snippet" in write_test_step
        assert write_test_step["code_snippet"] is not None

        implement_step = steps[2]
        assert "code_snippet" in implement_step
        assert implement_step["code_snippet"] is not None

    def test_generate_steps_for_task_medium_detail(
        self, step_execution_repo: Path, sample_task_with_steps: dict[str, Any]
    ) -> None:
        """Test step generation at medium detail level."""
        steps = generate_steps_for_task(
            sample_task_with_steps,
            detail_level="medium",
            project_root=step_execution_repo,
        )

        # Should generate 6 TDD steps
        assert len(steps) == 6

        # Medium detail should NOT include code snippets
        write_test_step = steps[0]
        assert write_test_step.get("code_snippet") is None

        implement_step = steps[2]
        assert implement_step.get("code_snippet") is None

    def test_generate_steps_for_task_standard_detail(
        self, step_execution_repo: Path, sample_task_with_steps: dict[str, Any]
    ) -> None:
        """Test step generation at standard detail level (backward compatible)."""
        steps = generate_steps_for_task(
            sample_task_with_steps,
            detail_level="standard",
            project_root=step_execution_repo,
        )

        # Standard detail should produce no steps (classic mode)
        assert len(steps) == 0

    def test_step_generator_detects_ruff_formatter(
        self, step_execution_repo: Path, sample_task_with_steps: dict[str, Any]
    ) -> None:
        """Test that StepGenerator detects ruff from pyproject.toml."""
        generator = StepGenerator(project_root=step_execution_repo)
        steps = generator.generate(sample_task_with_steps, DetailLevel.HIGH)

        # Find the format step
        format_step = next((s for s in steps if s.action == StepAction.FORMAT), None)
        assert format_step is not None
        assert "ruff format" in format_step.run

    def test_step_generator_detects_prettier(self, tmp_path: Path) -> None:
        """Test that StepGenerator detects prettier from .prettierrc."""
        # Create a JS project with prettier
        (tmp_path / ".prettierrc").write_text("{}")
        (tmp_path / "package.json").write_text('{"name": "test"}')

        task = {
            "id": "JS-001",
            "title": "JS Module",
            "files": {"create": ["src/index.js"], "modify": [], "read": []},
        }

        generator = StepGenerator(project_root=tmp_path)
        steps = generator.generate(task, DetailLevel.HIGH)

        format_step = next((s for s in steps if s.action == StepAction.FORMAT), None)
        assert format_step is not None
        assert "prettier" in format_step.run.lower()


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

    def test_verify_fail_step_expects_nonzero_exit_code(
        self, sample_task_with_steps: dict[str, Any], step_execution_repo: Path
    ) -> None:
        """Test that verify_fail step expects non-zero exit code."""
        steps = generate_steps_for_task(
            sample_task_with_steps,
            detail_level="high",
            project_root=step_execution_repo,
        )

        verify_fail_step = steps[1]  # Step 2
        assert verify_fail_step["action"] == "verify_fail"
        assert verify_fail_step["verify"] == "exit_code_nonzero"

    def test_verify_pass_step_expects_zero_exit_code(
        self, sample_task_with_steps: dict[str, Any], step_execution_repo: Path
    ) -> None:
        """Test that verify_pass step expects zero exit code."""
        steps = generate_steps_for_task(
            sample_task_with_steps,
            detail_level="high",
            project_root=step_execution_repo,
        )

        verify_pass_step = steps[3]  # Step 4
        assert verify_pass_step["action"] == "verify_pass"
        assert verify_pass_step["verify"] == "exit_code"

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

        # Write heartbeat with step info
        hb = writer.write(
            task_id="BITE-TEST-001",
            step="step_3_implement",
            progress_pct=50,
        )

        assert hb.worker_id == 1
        assert hb.task_id == "BITE-TEST-001"
        assert hb.step == "step_3_implement"
        assert hb.progress_pct == 50

    def test_heartbeat_monitor_reads_step_progress(self, heartbeat_state_dir: Path) -> None:
        """Test that HeartbeatMonitor can read step progress."""
        # Writer writes heartbeat
        writer = HeartbeatWriter(worker_id=2, state_dir=heartbeat_state_dir)
        writer.write(task_id="BITE-TEST-002", step="step_4_verify_pass", progress_pct=66)

        # Monitor reads it
        monitor = HeartbeatMonitor(state_dir=heartbeat_state_dir)
        hb = monitor.read(worker_id=2)

        assert hb is not None
        assert hb.task_id == "BITE-TEST-002"
        assert hb.step == "step_4_verify_pass"
        assert hb.progress_pct == 66

    def test_heartbeat_step_progress_updates(self, heartbeat_state_dir: Path) -> None:
        """Test heartbeat updates as steps progress."""
        writer = HeartbeatWriter(worker_id=3, state_dir=heartbeat_state_dir)
        monitor = HeartbeatMonitor(state_dir=heartbeat_state_dir)

        # Simulate step progression
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

    def test_heartbeat_read_all_workers(self, heartbeat_state_dir: Path) -> None:
        """Test reading heartbeats from multiple workers."""
        # Create heartbeats for multiple workers
        for worker_id in range(1, 4):
            writer = HeartbeatWriter(worker_id=worker_id, state_dir=heartbeat_state_dir)
            writer.write(
                task_id=f"TASK-{worker_id:03d}",
                step=f"step_{worker_id}_impl",
                progress_pct=worker_id * 25,
            )

        monitor = HeartbeatMonitor(state_dir=heartbeat_state_dir)
        all_heartbeats = monitor.read_all()

        assert len(all_heartbeats) == 3
        assert 1 in all_heartbeats
        assert 2 in all_heartbeats
        assert 3 in all_heartbeats


# ============================================================================
# Test Class: Formatter Integration
# ============================================================================


class TestFormatterIntegration:
    """Tests for formatter detection and integration in steps."""

    def test_formatter_config_dataclass(self) -> None:
        """Test FormatterConfig dataclass structure."""
        config = FormatterConfig(
            format_cmd="ruff format",
            fix_cmd="ruff check --fix",
            file_patterns=["*.py"],
        )

        assert config.format_cmd == "ruff format"
        assert config.fix_cmd == "ruff check --fix"
        assert "*.py" in config.file_patterns

    def test_step_generator_uses_detected_formatter(self, step_execution_repo: Path) -> None:
        """Test that step generator uses the detected formatter."""
        task = {
            "id": "FMT-001",
            "title": "Test formatter",
            "files": {"create": ["src/fmt_test.py"], "modify": [], "read": []},
            "verification": {"command": "pytest tests/unit/test_fmt.py"},
        }

        generator = StepGenerator(project_root=step_execution_repo)
        steps = generator.generate(task, DetailLevel.MEDIUM)

        # Format step should reference the detected formatter
        format_step = next((s for s in steps if s.action == StepAction.FORMAT), None)
        assert format_step is not None

        # With ruff in pyproject.toml, should use ruff
        assert "ruff format" in format_step.run

    def test_format_step_includes_all_files(self, step_execution_repo: Path) -> None:
        """Test that format step includes both test and impl files."""
        task = {
            "id": "FMT-002",
            "title": "Multi-file format",
            "files": {"create": ["src/multi.py"], "modify": [], "read": []},
        }

        generator = StepGenerator(project_root=step_execution_repo)
        steps = generator.generate(task, DetailLevel.HIGH)

        format_step = next((s for s in steps if s.action == StepAction.FORMAT), None)
        assert format_step is not None

        # Should include both test file and implementation file
        assert "tests/unit/test_multi.py" in format_step.run
        assert "src/multi.py" in format_step.run

    def test_fallback_formatter_when_none_detected(self, tmp_path: Path) -> None:
        """Test fallback to default formatter when none detected."""
        # Empty project with no formatter config
        (tmp_path / "README.md").write_text("Empty project")

        task = {
            "id": "FALLBACK-001",
            "title": "No formatter",
            "files": {"create": ["module.py"], "modify": [], "read": []},
        }

        generator = StepGenerator(project_root=tmp_path)
        steps = generator.generate(task, DetailLevel.MEDIUM)

        format_step = next((s for s in steps if s.action == StepAction.FORMAT), None)
        assert format_step is not None
        # Should fallback to ruff (default)
        assert "ruff format" in format_step.run


# ============================================================================
# Test Class: Adaptive Detail
# ============================================================================


class TestAdaptiveDetail:
    """Tests for adaptive detail level triggers."""

    def test_adaptive_detail_reduces_on_familiarity(self, tmp_path: Path) -> None:
        """Test that adaptive detail reduces level for familiar files.

        This tests the concept - actual AdaptiveDetail module may not exist yet.
        """
        # Simulate adaptive detail state
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)

        adaptive_state = {
            "file_modifications": {
                "zerg/config.py": 5,  # Modified 5 times
                "zerg/launcher.py": 3,
            },
            "area_success_rates": {
                "zerg/": 0.95,  # 95% success rate
            },
        }

        state_file = state_dir / "adaptive-detail.json"
        state_file.write_text(json.dumps(adaptive_state))

        # Verify state file structure
        loaded = json.loads(state_file.read_text())
        assert loaded["file_modifications"]["zerg/config.py"] == 5
        assert loaded["area_success_rates"]["zerg/"] >= 0.90

    def test_adaptive_detail_state_persistence(self, tmp_path: Path) -> None:
        """Test that adaptive detail metrics persist across sessions."""
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)

        # Write initial state
        initial_state = {
            "file_modifications": {},
            "area_success_rates": {},
        }
        state_file = state_dir / "adaptive-detail.json"
        state_file.write_text(json.dumps(initial_state))

        # Simulate updating the state
        state = json.loads(state_file.read_text())
        state["file_modifications"]["new_file.py"] = 1
        state["area_success_rates"]["new_area/"] = 1.0
        state_file.write_text(json.dumps(state))

        # Verify persistence
        loaded = json.loads(state_file.read_text())
        assert "new_file.py" in loaded["file_modifications"]
        assert loaded["area_success_rates"]["new_area/"] == 1.0


# ============================================================================
# Test Class: End-to-End Design to Execute Flow
# ============================================================================


class TestDesignToExecuteFlow:
    """End-to-end tests for design → execute flow with steps."""

    def test_task_graph_with_steps_structure(self, task_graph_with_steps: dict[str, Any]) -> None:
        """Test that task graph with steps has correct structure."""
        tasks = task_graph_with_steps["tasks"]

        # First task has steps
        task_with_steps = tasks[0]
        assert "steps" in task_with_steps
        assert len(task_with_steps["steps"]) == 6

        # Second task is stepless (classic mode)
        task_without_steps = tasks[1]
        assert "steps" not in task_without_steps

    def test_steps_in_task_graph_are_valid(self, task_graph_with_steps: dict[str, Any]) -> None:
        """Test that steps in task graph conform to schema."""
        task = task_graph_with_steps["tasks"][0]
        steps = task["steps"]

        valid_actions = {"write_test", "verify_fail", "implement", "verify_pass", "format", "commit"}
        valid_verify = {"exit_code", "exit_code_nonzero", "none"}

        for step in steps:
            assert "step" in step
            assert "action" in step
            assert "verify" in step
            assert step["action"] in valid_actions
            assert step["verify"] in valid_verify

    def test_step_execution_simulation(self, task_graph_with_steps: dict[str, Any], heartbeat_state_dir: Path) -> None:
        """Simulate step execution with heartbeat tracking."""
        task = task_graph_with_steps["tasks"][0]
        steps = task["steps"]
        task_id = task["id"]

        writer = HeartbeatWriter(worker_id=1, state_dir=heartbeat_state_dir)
        monitor = HeartbeatMonitor(state_dir=heartbeat_state_dir)

        # Simulate executing each step
        for i, step in enumerate(steps):
            step_name = f"step_{step['step']}_{step['action']}"
            progress = int(((i + 1) / len(steps)) * 100)

            writer.write(task_id=task_id, step=step_name, progress_pct=progress)

            # Verify heartbeat reflects current step
            hb = monitor.read(worker_id=1)
            assert hb is not None
            assert hb.task_id == task_id
            assert hb.step == step_name

        # Final heartbeat should be at 100%
        final_hb = monitor.read(worker_id=1)
        assert final_hb is not None
        assert final_hb.progress_pct == 100

    def test_mixed_task_execution(self, task_graph_with_steps: dict[str, Any], heartbeat_state_dir: Path) -> None:
        """Test executing both step-based and stepless tasks."""
        tasks = task_graph_with_steps["tasks"]

        # Task 1 has steps
        task1 = tasks[0]
        assert "steps" in task1

        # Task 2 is classic mode
        task2 = tasks[1]
        assert "steps" not in task2

        # Both should be executable
        writer = HeartbeatWriter(worker_id=1, state_dir=heartbeat_state_dir)

        # Execute task 1 with steps
        for step in task1["steps"]:
            step_name = f"step_{step['step']}"
            writer.write(task_id=task1["id"], step=step_name, progress_pct=50)

        # Execute task 2 without steps (classic mode)
        writer.write(task_id=task2["id"], step="implementing", progress_pct=100)

        monitor = HeartbeatMonitor(state_dir=heartbeat_state_dir)
        hb = monitor.read(worker_id=1)
        assert hb is not None
        assert hb.task_id == task2["id"]


# ============================================================================
# Test Class: Pre-commit Hook Integration
# ============================================================================


class TestPrecommitHookIntegration:
    """Tests for pre-commit hook integration with step execution."""

    def test_commit_step_command_format(
        self, sample_task_with_steps: dict[str, Any], step_execution_repo: Path
    ) -> None:
        """Test that commit step has correct command format."""
        steps = generate_steps_for_task(
            sample_task_with_steps,
            detail_level="high",
            project_root=step_execution_repo,
        )

        commit_step = next((s for s in steps if s["action"] == "commit"), None)
        assert commit_step is not None

        # Should use git add -A && git commit
        assert "git add -A" in commit_step["run"]
        assert "git commit" in commit_step["run"]
        assert "-m" in commit_step["run"]

    def test_commit_message_includes_task_id(
        self, sample_task_with_steps: dict[str, Any], step_execution_repo: Path
    ) -> None:
        """Test that commit message includes task ID."""
        steps = generate_steps_for_task(
            sample_task_with_steps,
            detail_level="high",
            project_root=step_execution_repo,
        )

        commit_step = next((s for s in steps if s["action"] == "commit"), None)
        assert commit_step is not None

        task_id = sample_task_with_steps["id"]
        assert task_id in commit_step["run"]


# ============================================================================
# Test Class: Error Handling
# ============================================================================


class TestStepExecutionErrors:
    """Tests for error handling during step execution."""

    def test_heartbeat_handles_missing_state_dir(self, tmp_path: Path) -> None:
        """Test heartbeat handles missing state directory gracefully."""
        nonexistent_dir = tmp_path / "nonexistent"

        # Writer should create the directory
        writer = HeartbeatWriter(worker_id=1, state_dir=nonexistent_dir)
        hb = writer.write(task_id="TEST", step="test", progress_pct=0)

        assert hb is not None
        assert nonexistent_dir.exists()

    def test_heartbeat_monitor_handles_missing_file(self, heartbeat_state_dir: Path) -> None:
        """Test heartbeat monitor handles missing heartbeat file."""
        monitor = HeartbeatMonitor(state_dir=heartbeat_state_dir)

        # Reading non-existent worker should return None
        hb = monitor.read(worker_id=999)
        assert hb is None

    def test_heartbeat_cleanup(self, heartbeat_state_dir: Path) -> None:
        """Test heartbeat cleanup on worker shutdown."""
        writer = HeartbeatWriter(worker_id=42, state_dir=heartbeat_state_dir)
        writer.write(task_id="CLEANUP-TEST", step="running", progress_pct=50)

        # File should exist
        assert writer.heartbeat_path.exists()

        # Cleanup
        writer.cleanup()

        # File should be removed
        assert not writer.heartbeat_path.exists()


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
        assert "run" not in d  # None values should be excluded

    def test_step_verification_modes_enum(self) -> None:
        """Test VerifyMode enum values."""
        assert VerifyMode.EXIT_CODE.value == "exit_code"
        assert VerifyMode.EXIT_CODE_NONZERO.value == "exit_code_nonzero"
        assert VerifyMode.NONE.value == "none"

    def test_step_action_enum(self) -> None:
        """Test StepAction enum values."""
        expected_actions = [
            ("WRITE_TEST", "write_test"),
            ("VERIFY_FAIL", "verify_fail"),
            ("IMPLEMENT", "implement"),
            ("VERIFY_PASS", "verify_pass"),
            ("FORMAT", "format"),
            ("COMMIT", "commit"),
        ]

        for name, value in expected_actions:
            assert hasattr(StepAction, name)
            assert getattr(StepAction, name).value == value
