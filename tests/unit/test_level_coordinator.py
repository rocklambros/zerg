"""Tests for LevelCoordinator and GatePipeline components."""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.config import QualityGate, ZergConfig
from zerg.constants import GateResult, LevelMergeStatus
from zerg.gates import GateRunner
from zerg.level_coordinator import GatePipeline, LevelCoordinator
from zerg.levels import LevelController
from zerg.merge import MergeCoordinator, MergeFlowResult
from zerg.parser import TaskParser
from zerg.plugins import PluginRegistry
from zerg.state import StateManager
from zerg.task_sync import TaskSyncBridge
from zerg.types import GateRunResult, WorkerState


@pytest.fixture
def mock_config():
    config = MagicMock(spec=ZergConfig)
    config.merge_timeout_seconds = 10
    config.merge_max_retries = 2
    # Set rush config for immediate merge behavior (tests expect this)
    rush_config = MagicMock()
    rush_config.defer_merge_to_ship = False
    rush_config.gates_at_ship_only = False
    config.rush = rush_config
    return config


@pytest.fixture
def mock_deps(mock_config):
    """Create all LevelCoordinator dependencies."""
    state = MagicMock(spec=StateManager)
    levels = MagicMock(spec=LevelController)
    levels.start_level.return_value = ["TASK-001", "TASK-002"]

    parser = MagicMock(spec=TaskParser)
    parser.get_task.side_effect = lambda tid: {"id": tid, "title": f"Task {tid}"}

    merger = MagicMock(spec=MergeCoordinator)
    task_sync = MagicMock(spec=TaskSyncBridge)
    plugin_registry = MagicMock(spec=PluginRegistry)
    workers: dict[int, WorkerState] = {}

    return {
        "feature": "test-feature",
        "config": mock_config,
        "state": state,
        "levels": levels,
        "parser": parser,
        "merger": merger,
        "task_sync": task_sync,
        "plugin_registry": plugin_registry,
        "workers": workers,
        "on_level_complete_callbacks": [],
    }


@pytest.fixture
def coordinator(mock_deps):
    return LevelCoordinator(**mock_deps)


def _add_worker(mock_deps, worker_id=0, branch="zerg/test/worker-0"):
    """Helper to add a worker with a branch to mock_deps."""
    ws = MagicMock()
    ws.branch = branch
    mock_deps["workers"][worker_id] = ws
    return ws


class TestStartLevel:
    """Tests for start_level."""

    def test_initializes_state_and_creates_tasks(self, coordinator, mock_deps):
        """start_level sets level state and creates Claude Tasks."""
        coordinator.start_level(1)

        mock_deps["levels"].start_level.assert_called_once_with(1)
        mock_deps["state"].set_current_level.assert_called_once_with(1)
        mock_deps["state"].set_level_status.assert_called_once_with(1, "running")
        mock_deps["task_sync"].create_level_tasks.assert_called_once()

    def test_assigns_tasks_with_assigner(self, mock_deps):
        """Tasks are assigned to workers when assigner is present."""
        assigner = MagicMock()
        assigner.get_task_worker.return_value = 0
        mock_deps["assigner"] = assigner

        coord = LevelCoordinator(**mock_deps)
        coord.start_level(1)

        assert mock_deps["state"].set_task_status.call_count == 2

    def test_skips_claude_tasks_when_parser_returns_none(self, mock_deps):
        """No Claude Tasks created when parser returns None for all tasks."""
        mock_deps["parser"].get_task.side_effect = lambda _: None

        coord = LevelCoordinator(**mock_deps)
        coord.start_level(1)

        mock_deps["task_sync"].create_level_tasks.assert_not_called()

    def test_registers_level_with_backpressure(self, mock_deps):
        """start_level registers the level with backpressure controller."""
        bp = MagicMock()
        mock_deps["backpressure"] = bp

        coord = LevelCoordinator(**mock_deps)
        coord.start_level(1)

        bp.register_level.assert_called_once_with(1, 2)  # 2 task_ids

    def test_emits_structured_log_on_start(self, mock_deps):
        """start_level emits structured log when writer is present."""
        writer = MagicMock()
        mock_deps["structured_writer"] = writer

        coord = LevelCoordinator(**mock_deps)
        coord.start_level(1)

        writer.emit.assert_called_once()
        call_args = writer.emit.call_args
        assert call_args[0][0] == "info"
        assert "Level 1 started" in call_args[0][1]

    def test_plugin_emit_exception_does_not_block(self, mock_deps):
        """Plugin event emission failure does not block start_level."""
        mock_deps["plugin_registry"].emit_event.side_effect = RuntimeError("plugin fail")

        coord = LevelCoordinator(**mock_deps)
        # Should not raise
        coord.start_level(1)

        # Level still started successfully
        mock_deps["state"].set_current_level.assert_called_once_with(1)

    @patch("zerg.level_coordinator.load_design_manifest")
    def test_logs_design_manifest_found(self, mock_load_manifest, mock_deps):
        """start_level logs when design manifest is found."""
        mock_load_manifest.return_value = [{"id": "TASK-001"}, {"id": "TASK-002"}]

        coord = LevelCoordinator(**mock_deps)
        coord.start_level(1)

        mock_load_manifest.assert_called_once()
        # No assertion on log output, just verifying the code path executes


class TestHandleLevelComplete:
    """Tests for handle_level_complete."""

    @patch("time.sleep")
    def test_succeeds_with_merge(self, mock_sleep, coordinator, mock_deps):
        """Level completion succeeds when merge passes."""
        merge_result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["b1"],
            target_branch="main",
            merge_commit="abc123",
        )
        mock_deps["merger"].full_merge_flow.return_value = merge_result

        # Add a worker with a branch so merge is called
        _add_worker(mock_deps)

        result = coordinator.handle_level_complete(1)

        assert result is True
        mock_deps["state"].set_level_status.assert_any_call(1, "complete", merge_commit="abc123")
        mock_deps["state"].set_level_merge_status.assert_any_call(1, LevelMergeStatus.COMPLETE)

    @patch("time.sleep")
    def test_fails_with_merge_failure(self, mock_sleep, coordinator, mock_deps):
        """Level completion fails when merge fails."""
        merge_result = MergeFlowResult(
            success=False,
            level=1,
            source_branches=["b1"],
            target_branch="main",
            error="Pre-merge gate failed",
        )
        mock_deps["merger"].full_merge_flow.return_value = merge_result

        _add_worker(mock_deps)

        result = coordinator.handle_level_complete(1)

        assert result is False
        mock_deps["state"].set_level_merge_status.assert_any_call(1, LevelMergeStatus.FAILED)

    @patch("time.sleep")
    def test_conflict_pauses_for_intervention(self, mock_sleep, coordinator, mock_deps):
        """Merge conflict triggers pause for intervention."""
        merge_result = MergeFlowResult(
            success=False,
            level=1,
            source_branches=["b1"],
            target_branch="main",
            error="CONFLICT in file.py",
        )
        mock_deps["merger"].full_merge_flow.return_value = merge_result

        _add_worker(mock_deps)

        coordinator.handle_level_complete(1)

        assert coordinator.paused is True
        mock_deps["state"].set_level_merge_status.assert_any_call(
            1, LevelMergeStatus.CONFLICT, details={"error": "CONFLICT in file.py"}
        )

    def test_defer_merge_to_ship(self, mock_deps):
        """handle_level_complete defers merge when defer_merge_to_ship is True."""
        mock_deps["config"].rush.defer_merge_to_ship = True
        callback = MagicMock()
        mock_deps["on_level_complete_callbacks"].append(callback)

        coord = LevelCoordinator(**mock_deps)
        result = coord.handle_level_complete(1)

        assert result is True
        mock_deps["state"].set_level_status.assert_called_with(1, "complete")
        mock_deps["state"].set_level_merge_status.assert_called_with(1, LevelMergeStatus.PENDING)
        callback.assert_called_once_with(1)
        # Merger should not have been called
        mock_deps["merger"].full_merge_flow.assert_not_called()

    @patch("time.sleep")
    def test_merge_timeout_creates_failure_result(self, mock_sleep, mock_deps):
        """Merge timeout produces a MergeFlowResult with error message."""
        import concurrent.futures

        _add_worker(mock_deps)

        # Make the executor.submit(...).result() raise TimeoutError
        mock_deps["merger"].full_merge_flow.side_effect = concurrent.futures.TimeoutError()

        coord = LevelCoordinator(**mock_deps)
        result = coord.handle_level_complete(1)

        assert result is False

    @patch("time.sleep")
    def test_backpressure_records_success(self, mock_sleep, mock_deps):
        """Backpressure controller records success on successful merge."""
        bp = MagicMock()
        mock_deps["backpressure"] = bp

        merge_result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["b1"],
            target_branch="main",
            merge_commit="def456",
        )
        mock_deps["merger"].full_merge_flow.return_value = merge_result
        _add_worker(mock_deps)

        coord = LevelCoordinator(**mock_deps)
        result = coord.handle_level_complete(1)

        assert result is True
        bp.record_success.assert_called_once_with(1)

    @patch("time.sleep")
    def test_structured_writer_emits_on_merge_complete(self, mock_sleep, mock_deps):
        """Structured writer emits events on successful level complete."""
        writer = MagicMock()
        mock_deps["structured_writer"] = writer

        merge_result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["b1"],
            target_branch="main",
            merge_commit="xyz789",
        )
        mock_deps["merger"].full_merge_flow.return_value = merge_result
        _add_worker(mock_deps)

        coord = LevelCoordinator(**mock_deps)
        coord.handle_level_complete(1)

        # Should have been called 3 times: merge start + merge complete + level complete
        assert writer.emit.call_count == 3

    @patch("time.sleep")
    def test_metrics_exception_does_not_block(self, mock_sleep, mock_deps):
        """Metrics computation failure does not block level completion."""
        merge_result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["b1"],
            target_branch="main",
            merge_commit="abc",
        )
        mock_deps["merger"].full_merge_flow.return_value = merge_result
        _add_worker(mock_deps)

        coord = LevelCoordinator(**mock_deps)

        with patch("zerg.level_coordinator.MetricsCollector") as mock_mc:
            mock_mc.side_effect = RuntimeError("metrics broken")
            result = coord.handle_level_complete(1)

        assert result is True

    @patch("time.sleep")
    def test_plugin_emit_exception_on_complete_does_not_block(self, mock_sleep, mock_deps):
        """Plugin event emission failure on level complete does not block."""
        merge_result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["b1"],
            target_branch="main",
            merge_commit="abc",
        )
        mock_deps["merger"].full_merge_flow.return_value = merge_result
        _add_worker(mock_deps)

        # Make plugin emit fail
        mock_deps["plugin_registry"].emit_event.side_effect = RuntimeError("plugin error")

        coord = LevelCoordinator(**mock_deps)
        result = coord.handle_level_complete(1)

        assert result is True

    @patch("time.sleep")
    def test_generate_state_md_oserror_does_not_block(self, mock_sleep, mock_deps):
        """OSError in generate_state_md does not block level completion."""
        merge_result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["b1"],
            target_branch="main",
            merge_commit="abc",
        )
        mock_deps["merger"].full_merge_flow.return_value = merge_result
        _add_worker(mock_deps)
        mock_deps["state"].generate_state_md.side_effect = OSError("disk full")

        coord = LevelCoordinator(**mock_deps)
        result = coord.handle_level_complete(1)

        assert result is True

    @patch("time.sleep")
    def test_on_level_complete_callbacks_invoked(self, mock_sleep, mock_deps):
        """Callbacks are invoked on successful level completion."""
        callback = MagicMock()
        mock_deps["on_level_complete_callbacks"].append(callback)

        merge_result = MergeFlowResult(
            success=True,
            level=2,
            source_branches=["b1"],
            target_branch="main",
            merge_commit="abc",
        )
        mock_deps["merger"].full_merge_flow.return_value = merge_result
        _add_worker(mock_deps)

        coord = LevelCoordinator(**mock_deps)
        coord.handle_level_complete(2)

        callback.assert_called_once_with(2)

    @patch("time.sleep")
    def test_backpressure_records_failure_and_pauses(self, mock_sleep, mock_deps):
        """Backpressure controller records failure and pauses when threshold exceeded."""
        bp = MagicMock()
        bp.should_pause.return_value = True
        bp.get_failure_rate.return_value = 0.75
        mock_deps["backpressure"] = bp

        merge_result = MergeFlowResult(
            success=False,
            level=1,
            source_branches=["b1"],
            target_branch="main",
            error="some error",
        )
        mock_deps["merger"].full_merge_flow.return_value = merge_result
        _add_worker(mock_deps)

        coord = LevelCoordinator(**mock_deps)
        result = coord.handle_level_complete(1)

        assert result is False
        bp.record_failure.assert_called_once_with(1)
        bp.should_pause.assert_called_once_with(1)
        bp.pause_level.assert_called_once_with(1)


class TestMergeLevel:
    """Tests for merge_level."""

    def test_collects_worker_branches(self, coordinator, mock_deps):
        """merge_level passes worker branches to merger."""
        _add_worker(mock_deps)

        merge_result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["zerg/test/worker-0"],
            target_branch="main",
        )
        mock_deps["merger"].full_merge_flow.return_value = merge_result

        result = coordinator.merge_level(1)

        mock_deps["merger"].full_merge_flow.assert_called_once_with(
            level=1,
            worker_branches=["zerg/test/worker-0"],
            target_branch="main",
            skip_gates=False,
        )
        assert result.success is True

    def test_handles_no_worker_branches(self, coordinator, mock_deps):
        """merge_level returns success with no branches to merge."""
        # No workers in dict
        result = coordinator.merge_level(1)

        assert result.success is True
        mock_deps["merger"].full_merge_flow.assert_not_called()

    def test_structured_writer_emits_on_merge_start(self, mock_deps):
        """merge_level emits structured log for merge start."""
        writer = MagicMock()
        mock_deps["structured_writer"] = writer
        _add_worker(mock_deps)

        merge_result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["b1"],
            target_branch="main",
        )
        mock_deps["merger"].full_merge_flow.return_value = merge_result

        coord = LevelCoordinator(**mock_deps)
        coord.merge_level(1)

        writer.emit.assert_called_once()
        assert "Merge started" in writer.emit.call_args[0][1]

    def test_skip_gates_when_configured(self, mock_deps):
        """merge_level passes skip_gates=True when gates_at_ship_only is set."""
        mock_deps["config"].rush.gates_at_ship_only = True
        _add_worker(mock_deps)

        merge_result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["b1"],
            target_branch="main",
        )
        mock_deps["merger"].full_merge_flow.return_value = merge_result

        coord = LevelCoordinator(**mock_deps)
        coord.merge_level(1)

        mock_deps["merger"].full_merge_flow.assert_called_once_with(
            level=1,
            worker_branches=["zerg/test/worker-0"],
            target_branch="main",
            skip_gates=True,
        )

    def test_stores_last_merge_result(self, mock_deps):
        """merge_level stores the result in last_merge_result."""
        _add_worker(mock_deps)

        merge_result = MergeFlowResult(
            success=True,
            level=1,
            source_branches=["b1"],
            target_branch="main",
        )
        mock_deps["merger"].full_merge_flow.return_value = merge_result

        coord = LevelCoordinator(**mock_deps)
        assert coord.last_merge_result is None
        coord.merge_level(1)
        assert coord.last_merge_result is merge_result


class TestRebaseAllWorkers:
    """Tests for rebase_all_workers."""

    def test_sets_rebasing_status(self, coordinator, mock_deps):
        """rebase_all_workers sets merge status to REBASING."""
        coordinator.rebase_all_workers(1)

        mock_deps["state"].set_level_merge_status.assert_called_with(1, LevelMergeStatus.REBASING)

    def test_skips_workers_without_branches(self, mock_deps):
        """Workers without branches are skipped during rebase."""
        ws_no_branch = MagicMock()
        ws_no_branch.branch = None
        mock_deps["workers"][0] = ws_no_branch

        ws_with_branch = MagicMock()
        ws_with_branch.branch = "zerg/test/worker-1"
        mock_deps["workers"][1] = ws_with_branch

        coord = LevelCoordinator(**mock_deps)
        # Should not raise, both paths exercised
        coord.rebase_all_workers(1)


class TestPauseAndError:
    """Tests for pause_for_intervention and set_recoverable_error."""

    def test_pause_for_intervention_sets_paused(self, coordinator, mock_deps):
        """pause_for_intervention sets paused state."""
        coordinator.pause_for_intervention("Merge conflict")

        assert coordinator.paused is True
        mock_deps["state"].set_paused.assert_called_with(True)
        mock_deps["state"].append_event.assert_called_with("paused_for_intervention", {"reason": "Merge conflict"})

    def test_set_recoverable_error_sets_paused(self, coordinator, mock_deps):
        """set_recoverable_error pauses and records error."""
        coordinator.set_recoverable_error("Merge failed after retries")

        assert coordinator.paused is True
        mock_deps["state"].set_error.assert_called_with("Merge failed after retries")
        mock_deps["state"].set_paused.assert_called_with(True)
        mock_deps["state"].append_event.assert_called_with("recoverable_error", {"error": "Merge failed after retries"})

    def test_paused_property_default(self, coordinator):
        """Paused property defaults to False."""
        assert coordinator.paused is False

    def test_paused_property_setter(self, coordinator):
        """Paused property can be set."""
        coordinator.paused = True
        assert coordinator.paused is True


class TestGatePipeline:
    """Tests for GatePipeline artifact storage and staleness checking."""

    @pytest.fixture
    def gate_runner(self):
        return MagicMock(spec=GateRunner)

    @pytest.fixture
    def pipeline(self, gate_runner, tmp_path):
        return GatePipeline(
            gate_runner=gate_runner,
            artifacts_dir=tmp_path / "artifacts",
            staleness_threshold_seconds=300,
        )

    @pytest.fixture
    def sample_gate(self):
        return QualityGate(name="lint", command="ruff check .")

    @pytest.fixture
    def sample_result(self):
        return GateRunResult(
            gate_name="lint",
            result=GateResult.PASS,
            command="ruff check .",
            exit_code=0,
            stdout="All checks passed",
            stderr="",
            duration_ms=150,
        )

    def test_init_default_artifacts_dir(self, gate_runner):
        """GatePipeline defaults to .zerg/artifacts when no dir provided."""
        pipeline = GatePipeline(gate_runner=gate_runner)
        assert pipeline._artifacts_dir == Path(".zerg/artifacts")
        assert pipeline._staleness_threshold == 300

    def test_init_custom_values(self, gate_runner, tmp_path):
        """GatePipeline accepts custom artifacts_dir and staleness threshold."""
        pipeline = GatePipeline(
            gate_runner=gate_runner,
            artifacts_dir=tmp_path / "custom",
            staleness_threshold_seconds=600,
        )
        assert pipeline._artifacts_dir == tmp_path / "custom"
        assert pipeline._staleness_threshold == 600

    def test_run_gates_executes_and_stores(self, pipeline, gate_runner, sample_gate, sample_result, tmp_path):
        """run_gates_for_level executes gates and stores artifacts."""
        gate_runner.run_gate.return_value = sample_result

        results = pipeline.run_gates_for_level(1, [sample_gate])

        assert len(results) == 1
        assert results[0].gate_name == "lint"
        assert results[0].result == GateResult.PASS
        gate_runner.run_gate.assert_called_once_with(sample_gate, cwd=None)

        # Verify artifact was stored
        artifact_path = tmp_path / "artifacts" / "1" / "lint.json"
        assert artifact_path.exists()
        data = json.loads(artifact_path.read_text())
        assert data["gate_name"] == "lint"
        assert data["result"]["result"] == "pass"

    def test_run_gates_uses_cache_when_fresh(self, pipeline, gate_runner, sample_gate, sample_result, tmp_path):
        """run_gates_for_level returns cached result when not stale."""
        gate_runner.run_gate.return_value = sample_result

        # First run: stores artifact
        pipeline.run_gates_for_level(1, [sample_gate])
        assert gate_runner.run_gate.call_count == 1

        # Second run: should use cached result
        results = pipeline.run_gates_for_level(1, [sample_gate])
        assert gate_runner.run_gate.call_count == 1  # Not called again
        assert len(results) == 1
        assert results[0].gate_name == "lint"

    def test_run_gates_reexecutes_when_stale(self, gate_runner, sample_gate, sample_result, tmp_path):
        """run_gates_for_level re-executes when cached result is stale."""
        pipeline = GatePipeline(
            gate_runner=gate_runner,
            artifacts_dir=tmp_path / "artifacts",
            staleness_threshold_seconds=0,  # Everything is immediately stale
        )
        gate_runner.run_gate.return_value = sample_result

        # First run
        pipeline.run_gates_for_level(1, [sample_gate])
        assert gate_runner.run_gate.call_count == 1

        # Second run: stale, should re-execute
        pipeline.run_gates_for_level(1, [sample_gate])
        assert gate_runner.run_gate.call_count == 2

    def test_load_cached_result_returns_none_when_missing(self, pipeline, tmp_path):
        """_load_cached_result returns None when artifact does not exist."""
        level_dir = tmp_path / "artifacts" / "1"
        level_dir.mkdir(parents=True)
        result = pipeline._load_cached_result(level_dir, "nonexistent")
        assert result is None

    def test_load_cached_result_returns_none_on_bad_json(self, pipeline, tmp_path):
        """_load_cached_result returns None on malformed JSON."""
        level_dir = tmp_path / "artifacts" / "1"
        level_dir.mkdir(parents=True)
        bad_file = level_dir / "broken.json"
        bad_file.write_text("not valid json {{{")

        result = pipeline._load_cached_result(level_dir, "broken")
        assert result is None

    def test_is_stale_returns_true_for_old_results(self, pipeline):
        """_is_stale returns True when timestamp is older than threshold."""
        old_cached = {"timestamp": time.time() - 600}  # 10 min ago, threshold is 300s
        assert pipeline._is_stale(old_cached) is True

    def test_is_stale_returns_false_for_fresh_results(self, pipeline):
        """_is_stale returns False when timestamp is within threshold."""
        fresh_cached = {"timestamp": time.time()}
        assert pipeline._is_stale(fresh_cached) is False

    def test_is_stale_returns_true_when_no_timestamp(self, pipeline):
        """_is_stale returns True when cached result has no timestamp."""
        no_ts = {}
        assert pipeline._is_stale(no_ts) is True

    def test_restore_result_with_valid_data(self, pipeline):
        """_restore_result reconstructs a GateRunResult from cached data."""
        gate = QualityGate(name="test", command="pytest")
        cached = {
            "result": {
                "name": "test",
                "result": "pass",
                "command": "pytest",
                "exit_code": 0,
                "stdout": "ok",
                "stderr": "",
                "duration_ms": 42,
            }
        }
        restored = pipeline._restore_result(cached, gate)
        assert restored.gate_name == "test"
        assert restored.result == GateResult.PASS
        assert restored.exit_code == 0
        assert restored.duration_ms == 42

    def test_restore_result_with_unknown_gate_result(self, pipeline):
        """_restore_result falls back to ERROR for unknown result values."""
        gate = QualityGate(name="test", command="pytest")
        cached = {
            "result": {
                "name": "test",
                "result": "nonexistent_status",
                "command": "pytest",
                "exit_code": 1,
            }
        }
        restored = pipeline._restore_result(cached, gate)
        assert restored.result == GateResult.ERROR

    def test_restore_result_with_empty_result_dict(self, pipeline):
        """_restore_result handles empty result sub-dict gracefully."""
        gate = QualityGate(name="fallback", command="echo hi")
        cached = {"result": {}}
        restored = pipeline._restore_result(cached, gate)
        assert restored.gate_name == "fallback"  # Falls back to gate.name
        assert restored.result == GateResult.ERROR  # "unknown" is not a valid GateResult

    def test_store_result_oserror_does_not_raise(self, gate_runner, tmp_path):
        """_store_result handles OSError gracefully without raising."""
        pipeline = GatePipeline(gate_runner=gate_runner, artifacts_dir=tmp_path / "artifacts")
        # Use a path that will fail to write
        level_dir = tmp_path / "artifacts" / "1"
        level_dir.mkdir(parents=True)

        result = GateRunResult(
            gate_name="lint",
            result=GateResult.PASS,
            command="ruff check .",
            exit_code=0,
        )

        # Make the file path a directory to cause OSError
        bad_path = level_dir / "lint.json"
        bad_path.mkdir()

        # Should not raise
        pipeline._store_result(level_dir, "lint", result)

    def test_run_gates_creates_level_dir(self, pipeline, gate_runner, sample_gate, sample_result, tmp_path):
        """run_gates_for_level creates the level directory if it doesn't exist."""
        gate_runner.run_gate.return_value = sample_result
        level_dir = tmp_path / "artifacts" / "5"
        assert not level_dir.exists()

        pipeline.run_gates_for_level(5, [sample_gate])
        assert level_dir.exists()

    def test_run_gates_multiple_gates(self, pipeline, gate_runner, tmp_path):
        """run_gates_for_level handles multiple gates correctly."""
        gate1 = QualityGate(name="lint", command="ruff check .")
        gate2 = QualityGate(name="typecheck", command="mypy .")

        result1 = GateRunResult(
            gate_name="lint",
            result=GateResult.PASS,
            command="ruff check .",
            exit_code=0,
        )
        result2 = GateRunResult(
            gate_name="typecheck",
            result=GateResult.FAIL,
            command="mypy .",
            exit_code=1,
            stderr="type error found",
        )
        gate_runner.run_gate.side_effect = [result1, result2]

        results = pipeline.run_gates_for_level(1, [gate1, gate2])

        assert len(results) == 2
        assert results[0].result == GateResult.PASS
        assert results[1].result == GateResult.FAIL
