"""Tests for ZERG verification gate pipeline."""

import json
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
# GateStatus + GateResult + PipelineResult
# ===========================================================================


class TestGateStatus:
    """Tests for GateStatus enum."""

    def test_all_values(self) -> None:
        """GateStatus must have exactly 5 members with correct values."""
        assert len(GateStatus) == 5
        assert GateStatus.PENDING.value == "pending"
        assert GateStatus.PASSED.value == "passed"
        assert GateStatus.FAILED.value == "failed"


class TestGateResult:
    """Tests for GateResult dataclass."""

    def test_creation_and_defaults(self) -> None:
        """GateResult with minimal args has correct defaults."""
        result = GateResult(gate_name="lint", status=GateStatus.PASSED)
        assert result.gate_name == "lint"
        assert result.verification_result is None
        assert result.is_fresh is True
        assert isinstance(result.timestamp, datetime)

    def test_to_dict(self) -> None:
        """GateResult.to_dict includes all fields."""
        exec_result = _make_exec_result()
        result = GateResult(
            gate_name="test",
            status=GateStatus.PASSED,
            verification_result=exec_result,
            artifact_path=Path("/tmp/art.json"),
        )
        data = result.to_dict()
        assert data["gate_name"] == "test"
        assert data["verification"]["success"] is True
        assert data["artifact_path"] == "/tmp/art.json"
        datetime.fromisoformat(data["timestamp"])  # must parse


class TestPipelineResult:
    """Tests for PipelineResult dataclass."""

    def test_to_dict(self) -> None:
        """PipelineResult.to_dict serializes gate results."""
        gate_results = [GateResult(gate_name="lint", status=GateStatus.PASSED)]
        pr = PipelineResult(gate_results=gate_results, all_passed=True, required_passed=True, total_duration_ms=100)
        data = pr.to_dict()
        assert data["all_passed"] is True
        assert len(data["gates"]) == 1


# ===========================================================================
# ArtifactStore
# ===========================================================================


class TestArtifactStore:
    """Tests for ArtifactStore."""

    def test_store_and_retrieve(self, tmp_path: Path) -> None:
        """Store creates artifact file; get_latest retrieves it."""
        store = ArtifactStore(base_dir=tmp_path)
        result = _make_exec_result(task_id="T1")
        path = store.store("lint", "T1", result)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["gate_name"] == "lint"

    def test_get_latest_returns_none_when_empty(self, tmp_path: Path) -> None:
        """get_latest returns None when no artifacts exist."""
        store = ArtifactStore(base_dir=tmp_path)
        assert store.get_latest("lint", "T1") is None

    def test_is_fresh_recent_vs_stale(self, tmp_path: Path) -> None:
        """is_fresh returns True for recent, False for old artifacts."""
        store = ArtifactStore(base_dir=tmp_path)
        result = _make_exec_result()
        path = store.store("lint", "T1", result)
        assert store.is_fresh("lint", "T1", max_age_seconds=300) is True

        # Age the artifact
        data = json.loads(path.read_text())
        data["stored_at"] = (datetime.now() - timedelta(seconds=600)).isoformat()
        path.write_text(json.dumps(data))
        assert store.is_fresh("lint", "T1", max_age_seconds=300) is False


# ===========================================================================
# GatePipeline — run_gate
# ===========================================================================


class TestGatePipelineRunGate:
    """Tests for GatePipeline.run_gate."""

    def test_run_gate_success(self, tmp_path: Path) -> None:
        """Successful gate stores artifact and returns PASSED."""
        exec_result = _make_exec_result(success=True)
        executor = _mock_executor([exec_result])
        store = ArtifactStore(base_dir=tmp_path)
        pipeline = GatePipeline(executor=executor, artifact_store=store)
        gate = pipeline.run_gate("lint", "echo ok", "T1", cwd=tmp_path)
        assert gate.status == GateStatus.PASSED
        assert gate.artifact_path is not None and gate.artifact_path.exists()

    def test_run_gate_failure(self, tmp_path: Path) -> None:
        """Failed gate returns FAILED status."""
        exec_result = _make_exec_result(success=False, exit_code=1)
        executor = _mock_executor([exec_result])
        store = ArtifactStore(base_dir=tmp_path)
        pipeline = GatePipeline(executor=executor, artifact_store=store)
        gate = pipeline.run_gate("test", "pytest", "T1", cwd=tmp_path)
        assert gate.status == GateStatus.FAILED

    def test_run_gate_uses_cached_fresh_result(self, tmp_path: Path) -> None:
        """When a fresh passing artifact exists, skip execution."""
        store = ArtifactStore(base_dir=tmp_path)
        store.store("lint", "T1", _make_exec_result(success=True, task_id="T1"))
        executor = _mock_executor([])
        pipeline = GatePipeline(executor=executor, artifact_store=store, staleness_threshold_seconds=300)
        gate = pipeline.run_gate("lint", "echo ok", "T1")
        assert gate.status == GateStatus.PASSED
        executor.verify.assert_not_called()


# ===========================================================================
# GatePipeline — run_pipeline
# ===========================================================================


class TestGatePipelineRunPipeline:
    """Tests for GatePipeline.run_pipeline."""

    def test_all_gates_pass(self, tmp_path: Path) -> None:
        """All passing gates yield all_passed=True."""
        results = [_make_exec_result(success=True), _make_exec_result(success=True)]
        executor = _mock_executor(results)
        store = ArtifactStore(base_dir=tmp_path)
        pipeline = GatePipeline(executor=executor, artifact_store=store)
        gates = [{"name": "lint", "command": "c1"}, {"name": "test", "command": "c2"}]
        pr = pipeline.run_pipeline(gates, "T1", cwd=tmp_path)
        assert pr.all_passed is True
        assert len(pr.gate_results) == 2

    def test_required_failure_stops_pipeline(self, tmp_path: Path) -> None:
        """Required gate failure stops the pipeline."""
        results = [_make_exec_result(success=False, exit_code=1)]
        executor = _mock_executor(results)
        store = ArtifactStore(base_dir=tmp_path)
        pipeline = GatePipeline(executor=executor, artifact_store=store)
        gates = [
            {"name": "lint", "command": "c1", "required": True},
            {"name": "test", "command": "c2"},
        ]
        pr = pipeline.run_pipeline(gates, "T1", cwd=tmp_path)
        assert pr.required_passed is False
        assert len(pr.gate_results) == 1

    def test_optional_failure_continues(self, tmp_path: Path) -> None:
        """Optional gate failure allows pipeline to continue."""
        results = [_make_exec_result(success=False, exit_code=1), _make_exec_result(success=True)]
        executor = _mock_executor(results)
        store = ArtifactStore(base_dir=tmp_path)
        pipeline = GatePipeline(executor=executor, artifact_store=store)
        gates = [
            {"name": "lint", "command": "c1", "required": False},
            {"name": "test", "command": "c2", "required": True},
        ]
        pr = pipeline.run_pipeline(gates, "T1", cwd=tmp_path)
        assert pr.all_passed is False
        assert pr.required_passed is True
        assert len(pr.gate_results) == 2


# ===========================================================================
# GatePipeline — init + staleness
# ===========================================================================


class TestGatePipelineInit:
    """Tests for GatePipeline initialization and staleness."""

    def test_default_values(self) -> None:
        """GatePipeline defaults are sensible."""
        pipeline = GatePipeline()
        assert isinstance(pipeline.executor, VerificationExecutor)
        assert pipeline.staleness_threshold == 300
        assert pipeline.store_artifacts is True

    def test_check_staleness(self, tmp_path: Path) -> None:
        """check_staleness returns True when no artifact, False when fresh."""
        store = ArtifactStore(base_dir=tmp_path)
        pipeline = GatePipeline(artifact_store=store, staleness_threshold_seconds=300)
        assert pipeline.check_staleness("lint", "T1") is True
        store.store("lint", "T1", _make_exec_result())
        assert pipeline.check_staleness("lint", "T1") is False
