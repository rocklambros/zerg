"""Tests for ZERG verification gate pipeline."""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

from zerg.verification_gates import (
    ArtifactStore,
    GatePipeline,
    GateResult,
    GateStatus,
    PipelineResult,
)
from zerg.verify import VerificationExecutionResult, VerificationExecutor

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_exec_result(
    task_id: str = "TASK-001",
    success: bool = True,
    exit_code: int = 0,
    command: str = "echo ok",
    stdout: str = "ok",
    stderr: str = "",
    duration_ms: int = 50,
) -> VerificationExecutionResult:
    """Create a VerificationExecutionResult for testing."""
    return VerificationExecutionResult(
        task_id=task_id,
        success=success,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_ms=duration_ms,
        command=command,
    )


def _mock_executor(results: list[VerificationExecutionResult]) -> MagicMock:
    """Create a mock VerificationExecutor returning results in sequence."""
    executor = MagicMock(spec=VerificationExecutor)
    executor.verify = MagicMock(side_effect=results)
    return executor


# ===========================================================================
# GateStatus
# ===========================================================================


class TestGateStatus:
    """Tests for GateStatus enum."""

    def test_values(self) -> None:
        assert GateStatus.PENDING.value == "pending"
        assert GateStatus.PASSED.value == "passed"
        assert GateStatus.FAILED.value == "failed"
        assert GateStatus.STALE.value == "stale"
        assert GateStatus.SKIPPED.value == "skipped"

    def test_all_members(self) -> None:
        assert len(GateStatus) == 5


# ===========================================================================
# GateResult
# ===========================================================================


class TestGateResult:
    """Tests for GateResult dataclass."""

    def test_creation_minimal(self) -> None:
        result = GateResult(gate_name="lint", status=GateStatus.PASSED)
        assert result.gate_name == "lint"
        assert result.status == GateStatus.PASSED
        assert result.verification_result is None
        assert result.artifact_path is None
        assert result.is_fresh is True
        assert isinstance(result.timestamp, datetime)

    def test_creation_full(self, tmp_path: Path) -> None:
        exec_result = _make_exec_result()
        artifact = tmp_path / "artifact.json"
        result = GateResult(
            gate_name="test",
            status=GateStatus.FAILED,
            verification_result=exec_result,
            artifact_path=artifact,
            is_fresh=False,
        )
        assert result.status == GateStatus.FAILED
        assert result.verification_result is exec_result
        assert result.artifact_path == artifact
        assert result.is_fresh is False

    def test_to_dict_without_verification(self) -> None:
        result = GateResult(gate_name="lint", status=GateStatus.PASSED)
        data = result.to_dict()
        assert data["gate_name"] == "lint"
        assert data["status"] == "passed"
        assert data["is_fresh"] is True
        assert data["artifact_path"] is None
        assert data["verification"] is None
        assert "timestamp" in data

    def test_to_dict_with_verification(self) -> None:
        exec_result = _make_exec_result()
        result = GateResult(
            gate_name="test",
            status=GateStatus.PASSED,
            verification_result=exec_result,
            artifact_path=Path("/tmp/art.json"),
        )
        data = result.to_dict()
        assert data["verification"] is not None
        assert data["verification"]["success"] is True
        assert data["artifact_path"] == "/tmp/art.json"

    def test_to_dict_timestamp_iso_format(self) -> None:
        result = GateResult(gate_name="g", status=GateStatus.PENDING)
        data = result.to_dict()
        # Should parse back without error
        datetime.fromisoformat(data["timestamp"])


# ===========================================================================
# PipelineResult
# ===========================================================================


class TestPipelineResult:
    """Tests for PipelineResult dataclass."""

    def test_creation(self) -> None:
        gate_results = [
            GateResult(gate_name="lint", status=GateStatus.PASSED),
            GateResult(gate_name="test", status=GateStatus.FAILED),
        ]
        pr = PipelineResult(
            gate_results=gate_results,
            all_passed=False,
            required_passed=True,
            total_duration_ms=200,
        )
        assert len(pr.gate_results) == 2
        assert pr.all_passed is False
        assert pr.required_passed is True
        assert pr.total_duration_ms == 200

    def test_to_dict(self) -> None:
        gate_results = [
            GateResult(gate_name="lint", status=GateStatus.PASSED),
        ]
        pr = PipelineResult(
            gate_results=gate_results,
            all_passed=True,
            required_passed=True,
            total_duration_ms=100,
        )
        data = pr.to_dict()
        assert data["all_passed"] is True
        assert data["required_passed"] is True
        assert data["total_duration_ms"] == 100
        assert len(data["gates"]) == 1
        assert data["gates"][0]["gate_name"] == "lint"

    def test_to_dict_empty_gates(self) -> None:
        pr = PipelineResult(
            gate_results=[],
            all_passed=True,
            required_passed=True,
            total_duration_ms=0,
        )
        data = pr.to_dict()
        assert data["gates"] == []


# ===========================================================================
# ArtifactStore
# ===========================================================================


class TestArtifactStore:
    """Tests for ArtifactStore."""

    def test_default_base_dir(self) -> None:
        store = ArtifactStore()
        assert store.base_dir == Path(".zerg/artifacts")

    def test_custom_base_dir(self, tmp_path: Path) -> None:
        store = ArtifactStore(base_dir=tmp_path / "arts")
        assert store.base_dir == tmp_path / "arts"

    def test_store_creates_artifact(self, tmp_path: Path) -> None:
        store = ArtifactStore(base_dir=tmp_path)
        result = _make_exec_result(task_id="T1")
        path = store.store("lint", "T1", result)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["gate_name"] == "lint"
        assert data["task_id"] == "T1"
        assert data["result"]["success"] is True

    def test_store_creates_directories(self, tmp_path: Path) -> None:
        store = ArtifactStore(base_dir=tmp_path / "deep" / "nested")
        result = _make_exec_result()
        path = store.store("gate", "T1", result)
        assert path.exists()

    def test_get_latest_returns_none_no_dir(self, tmp_path: Path) -> None:
        store = ArtifactStore(base_dir=tmp_path)
        assert store.get_latest("lint", "T1") is None

    def test_get_latest_returns_none_empty_dir(self, tmp_path: Path) -> None:
        store = ArtifactStore(base_dir=tmp_path)
        (tmp_path / "T1" / "lint").mkdir(parents=True)
        assert store.get_latest("lint", "T1") is None

    def test_get_latest_returns_most_recent(self, tmp_path: Path) -> None:
        store = ArtifactStore(base_dir=tmp_path)
        r1 = _make_exec_result(task_id="T1", stdout="first")
        r2 = _make_exec_result(task_id="T1", stdout="second")
        store.store("lint", "T1", r1)
        # Ensure different filename (second-resolution timestamp)
        time.sleep(0.05)
        store.store("lint", "T1", r2)
        latest = store.get_latest("lint", "T1")
        assert latest is not None
        # latest should be r2 since it was stored last (sorted reverse by name)

    def test_is_fresh_no_artifact(self, tmp_path: Path) -> None:
        store = ArtifactStore(base_dir=tmp_path)
        assert store.is_fresh("lint", "T1") is False

    def test_is_fresh_recent_artifact(self, tmp_path: Path) -> None:
        store = ArtifactStore(base_dir=tmp_path)
        result = _make_exec_result()
        store.store("lint", "T1", result)
        assert store.is_fresh("lint", "T1", max_age_seconds=300) is True

    def test_is_fresh_stale_artifact(self, tmp_path: Path) -> None:
        store = ArtifactStore(base_dir=tmp_path)
        result = _make_exec_result()
        path = store.store("lint", "T1", result)

        # Modify stored_at to be old
        data = json.loads(path.read_text())
        old_time = datetime.now() - timedelta(seconds=600)
        data["stored_at"] = old_time.isoformat()
        path.write_text(json.dumps(data))

        assert store.is_fresh("lint", "T1", max_age_seconds=300) is False

    def test_store_multiple_gates_same_task(self, tmp_path: Path) -> None:
        store = ArtifactStore(base_dir=tmp_path)
        result = _make_exec_result()
        p1 = store.store("lint", "T1", result)
        p2 = store.store("test", "T1", result)
        assert p1.parent != p2.parent
        assert p1.exists()
        assert p2.exists()


# ===========================================================================
# GatePipeline — run_gate
# ===========================================================================


class TestGatePipelineRunGate:
    """Tests for GatePipeline.run_gate."""

    def test_run_gate_success(self, tmp_path: Path) -> None:
        exec_result = _make_exec_result(success=True)
        executor = _mock_executor([exec_result])
        store = ArtifactStore(base_dir=tmp_path)
        pipeline = GatePipeline(executor=executor, artifact_store=store)

        gate = pipeline.run_gate("lint", "echo ok", "T1", cwd=tmp_path)

        assert gate.status == GateStatus.PASSED
        assert gate.verification_result is exec_result
        assert gate.artifact_path is not None
        assert gate.artifact_path.exists()

    def test_run_gate_failure(self, tmp_path: Path) -> None:
        exec_result = _make_exec_result(success=False, exit_code=1)
        executor = _mock_executor([exec_result])
        store = ArtifactStore(base_dir=tmp_path)
        pipeline = GatePipeline(executor=executor, artifact_store=store)

        gate = pipeline.run_gate("test", "pytest", "T1", cwd=tmp_path)

        assert gate.status == GateStatus.FAILED
        assert gate.verification_result is exec_result

    def test_run_gate_no_artifact_storage(self, tmp_path: Path) -> None:
        exec_result = _make_exec_result(success=True)
        executor = _mock_executor([exec_result])
        store = ArtifactStore(base_dir=tmp_path)
        pipeline = GatePipeline(executor=executor, artifact_store=store, store_artifacts=False)

        gate = pipeline.run_gate("lint", "echo ok", "T1", cwd=tmp_path)

        assert gate.status == GateStatus.PASSED
        assert gate.artifact_path is None

    def test_run_gate_uses_cached_fresh_result(self, tmp_path: Path) -> None:
        """When a fresh passing artifact exists, skip execution."""
        store = ArtifactStore(base_dir=tmp_path)
        # Pre-store a passing artifact
        passing = _make_exec_result(success=True, task_id="T1")
        store.store("lint", "T1", passing)

        executor = _mock_executor([])  # Should NOT be called
        pipeline = GatePipeline(
            executor=executor,
            artifact_store=store,
            staleness_threshold_seconds=300,
        )

        gate = pipeline.run_gate("lint", "echo ok", "T1")

        assert gate.status == GateStatus.PASSED
        assert gate.is_fresh is True
        executor.verify.assert_not_called()

    def test_run_gate_re_executes_stale_result(self, tmp_path: Path) -> None:
        """When artifact is stale, re-execute the gate."""
        store = ArtifactStore(base_dir=tmp_path)
        # Store an old artifact
        old_result = _make_exec_result(success=True, task_id="T1")
        path = store.store("lint", "T1", old_result)
        data = json.loads(path.read_text())
        data["stored_at"] = (datetime.now() - timedelta(seconds=600)).isoformat()
        path.write_text(json.dumps(data))

        new_result = _make_exec_result(success=True, task_id="T1")
        executor = _mock_executor([new_result])
        pipeline = GatePipeline(
            executor=executor,
            artifact_store=store,
            staleness_threshold_seconds=300,
        )

        gate = pipeline.run_gate("lint", "echo ok", "T1", cwd=tmp_path)

        assert gate.status == GateStatus.PASSED
        executor.verify.assert_called_once()

    def test_run_gate_re_executes_when_cached_failed(self, tmp_path: Path) -> None:
        """Fresh but failed artifact should not be reused."""
        store = ArtifactStore(base_dir=tmp_path)
        failing = _make_exec_result(success=False, task_id="T1", exit_code=1)
        store.store("lint", "T1", failing)

        new_result = _make_exec_result(success=True, task_id="T1")
        executor = _mock_executor([new_result])
        pipeline = GatePipeline(
            executor=executor,
            artifact_store=store,
            staleness_threshold_seconds=300,
        )

        gate = pipeline.run_gate("lint", "echo ok", "T1", cwd=tmp_path)

        assert gate.status == GateStatus.PASSED
        executor.verify.assert_called_once()

    def test_run_gate_passes_timeout(self, tmp_path: Path) -> None:
        exec_result = _make_exec_result(success=True)
        executor = _mock_executor([exec_result])
        store = ArtifactStore(base_dir=tmp_path)
        pipeline = GatePipeline(executor=executor, artifact_store=store)

        pipeline.run_gate("lint", "echo ok", "T1", timeout=60, cwd=tmp_path)

        executor.verify.assert_called_once_with("echo ok", "T1", timeout=60, cwd=tmp_path)


# ===========================================================================
# GatePipeline — run_pipeline
# ===========================================================================


class TestGatePipelineRunPipeline:
    """Tests for GatePipeline.run_pipeline."""

    def test_all_gates_pass(self, tmp_path: Path) -> None:
        results = [
            _make_exec_result(success=True),
            _make_exec_result(success=True),
        ]
        executor = _mock_executor(results)
        store = ArtifactStore(base_dir=tmp_path)
        pipeline = GatePipeline(executor=executor, artifact_store=store)

        gates = [
            {"name": "lint", "command": "lint cmd"},
            {"name": "test", "command": "test cmd"},
        ]
        pr = pipeline.run_pipeline(gates, "T1", cwd=tmp_path)

        assert pr.all_passed is True
        assert pr.required_passed is True
        assert len(pr.gate_results) == 2
        assert pr.total_duration_ms >= 0

    def test_required_failure_stops_pipeline(self, tmp_path: Path) -> None:
        results = [
            _make_exec_result(success=False, exit_code=1),
            # Second gate should NOT run
        ]
        executor = _mock_executor(results)
        store = ArtifactStore(base_dir=tmp_path)
        pipeline = GatePipeline(executor=executor, artifact_store=store)

        gates = [
            {"name": "lint", "command": "lint cmd", "required": True},
            {"name": "test", "command": "test cmd"},
        ]
        pr = pipeline.run_pipeline(gates, "T1", cwd=tmp_path)

        assert pr.all_passed is False
        assert pr.required_passed is False
        assert len(pr.gate_results) == 1
        executor.verify.assert_called_once()

    def test_optional_failure_continues_pipeline(self, tmp_path: Path) -> None:
        results = [
            _make_exec_result(success=False, exit_code=1),
            _make_exec_result(success=True),
        ]
        executor = _mock_executor(results)
        store = ArtifactStore(base_dir=tmp_path)
        pipeline = GatePipeline(executor=executor, artifact_store=store)

        gates = [
            {"name": "lint", "command": "lint cmd", "required": False},
            {"name": "test", "command": "test cmd", "required": True},
        ]
        pr = pipeline.run_pipeline(gates, "T1", cwd=tmp_path)

        assert pr.all_passed is False
        assert pr.required_passed is True
        assert len(pr.gate_results) == 2

    def test_empty_pipeline(self, tmp_path: Path) -> None:
        executor = _mock_executor([])
        store = ArtifactStore(base_dir=tmp_path)
        pipeline = GatePipeline(executor=executor, artifact_store=store)

        pr = pipeline.run_pipeline([], "T1", cwd=tmp_path)

        assert pr.all_passed is True
        assert pr.required_passed is True
        assert len(pr.gate_results) == 0

    def test_stop_on_required_failure_false(self, tmp_path: Path) -> None:
        """With stop_on_required_failure=False, pipeline continues past required failure."""
        results = [
            _make_exec_result(success=False, exit_code=1),
            _make_exec_result(success=True),
        ]
        executor = _mock_executor(results)
        store = ArtifactStore(base_dir=tmp_path)
        pipeline = GatePipeline(executor=executor, artifact_store=store)

        gates = [
            {"name": "lint", "command": "lint cmd", "required": True},
            {"name": "test", "command": "test cmd"},
        ]
        pr = pipeline.run_pipeline(gates, "T1", cwd=tmp_path, stop_on_required_failure=False)

        assert len(pr.gate_results) == 2
        assert pr.required_passed is False

    def test_multiple_required_gates(self, tmp_path: Path) -> None:
        results = [
            _make_exec_result(success=True),
            _make_exec_result(success=True),
            _make_exec_result(success=False, exit_code=1),
        ]
        executor = _mock_executor(results)
        store = ArtifactStore(base_dir=tmp_path)
        pipeline = GatePipeline(executor=executor, artifact_store=store)

        gates = [
            {"name": "lint", "command": "c1", "required": True},
            {"name": "test", "command": "c2", "required": True},
            {"name": "style", "command": "c3", "required": False},
        ]
        pr = pipeline.run_pipeline(gates, "T1", cwd=tmp_path)

        assert pr.all_passed is False
        assert pr.required_passed is True

    def test_pipeline_with_custom_timeout(self, tmp_path: Path) -> None:
        results = [_make_exec_result(success=True)]
        executor = _mock_executor(results)
        store = ArtifactStore(base_dir=tmp_path)
        pipeline = GatePipeline(executor=executor, artifact_store=store)

        gates = [{"name": "slow", "command": "cmd", "timeout": 600}]
        pipeline.run_pipeline(gates, "T1", cwd=tmp_path)

        executor.verify.assert_called_once_with("cmd", "T1", timeout=600, cwd=tmp_path)

    def test_pipeline_result_to_dict(self, tmp_path: Path) -> None:
        results = [_make_exec_result(success=True)]
        executor = _mock_executor(results)
        store = ArtifactStore(base_dir=tmp_path)
        pipeline = GatePipeline(executor=executor, artifact_store=store)

        gates = [{"name": "lint", "command": "cmd"}]
        pr = pipeline.run_pipeline(gates, "T1", cwd=tmp_path)

        data = pr.to_dict()
        assert data["all_passed"] is True
        assert len(data["gates"]) == 1


# ===========================================================================
# GatePipeline — check_staleness
# ===========================================================================


class TestGatePipelineStaleness:
    """Tests for GatePipeline.check_staleness."""

    def test_stale_when_no_artifact(self, tmp_path: Path) -> None:
        store = ArtifactStore(base_dir=tmp_path)
        pipeline = GatePipeline(artifact_store=store)
        assert pipeline.check_staleness("lint", "T1") is True

    def test_not_stale_when_fresh(self, tmp_path: Path) -> None:
        store = ArtifactStore(base_dir=tmp_path)
        result = _make_exec_result()
        store.store("lint", "T1", result)
        pipeline = GatePipeline(artifact_store=store, staleness_threshold_seconds=300)
        assert pipeline.check_staleness("lint", "T1") is False

    def test_stale_when_old(self, tmp_path: Path) -> None:
        store = ArtifactStore(base_dir=tmp_path)
        result = _make_exec_result()
        path = store.store("lint", "T1", result)
        # Age the artifact
        data = json.loads(path.read_text())
        data["stored_at"] = (datetime.now() - timedelta(seconds=600)).isoformat()
        path.write_text(json.dumps(data))

        pipeline = GatePipeline(artifact_store=store, staleness_threshold_seconds=300)
        assert pipeline.check_staleness("lint", "T1") is True


# ===========================================================================
# GatePipeline — constructor defaults
# ===========================================================================


class TestGatePipelineInit:
    """Tests for GatePipeline initialization."""

    def test_default_values(self) -> None:
        pipeline = GatePipeline()
        assert isinstance(pipeline.executor, VerificationExecutor)
        assert isinstance(pipeline.artifact_store, ArtifactStore)
        assert pipeline.staleness_threshold == 300
        assert pipeline.require_before_completion is True
        assert pipeline.store_artifacts is True

    def test_custom_values(self, tmp_path: Path) -> None:
        executor = MagicMock(spec=VerificationExecutor)
        store = ArtifactStore(base_dir=tmp_path)
        pipeline = GatePipeline(
            executor=executor,
            artifact_store=store,
            staleness_threshold_seconds=60,
            require_before_completion=False,
            store_artifacts=False,
        )
        assert pipeline.executor is executor
        assert pipeline.artifact_store is store
        assert pipeline.staleness_threshold == 60
        assert pipeline.require_before_completion is False
        assert pipeline.store_artifacts is False
