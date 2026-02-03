"""Verification gate pipeline for ZERG."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from zerg.verify import VerificationExecutionResult, VerificationExecutor


class GateStatus(Enum):
    """Status of a verification gate."""

    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    STALE = "stale"
    SKIPPED = "skipped"


@dataclass
class GateResult:
    """Result of running a single verification gate."""

    gate_name: str
    status: GateStatus
    verification_result: VerificationExecutionResult | None = None
    artifact_path: Path | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    is_fresh: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "gate_name": self.gate_name,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "is_fresh": self.is_fresh,
            "artifact_path": str(self.artifact_path) if self.artifact_path else None,
            "verification": (self.verification_result.to_dict() if self.verification_result else None),
        }


@dataclass
class PipelineResult:
    """Result of running the full gate pipeline."""

    gate_results: list[GateResult]
    all_passed: bool
    required_passed: bool
    total_duration_ms: int
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "all_passed": self.all_passed,
            "required_passed": self.required_passed,
            "total_duration_ms": self.total_duration_ms,
            "timestamp": self.timestamp.isoformat(),
            "gates": [g.to_dict() for g in self.gate_results],
        }


class ArtifactStore:
    """Store and retrieve verification artifacts."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path(".zerg/artifacts")

    def store(
        self,
        gate_name: str,
        task_id: str,
        result: VerificationExecutionResult,
    ) -> Path:
        """Store verification artifact. Returns artifact path."""
        artifact_dir = self.base_dir / task_id / gate_name
        artifact_dir.mkdir(parents=True, exist_ok=True)

        artifact_path = artifact_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        artifact_data = {
            "gate_name": gate_name,
            "task_id": task_id,
            "result": result.to_dict(),
            "stored_at": datetime.now().isoformat(),
        }
        artifact_path.write_text(json.dumps(artifact_data, indent=2))
        return artifact_path

    def get_latest(self, gate_name: str, task_id: str) -> dict | None:
        """Get most recent artifact for a gate/task combo."""
        artifact_dir = self.base_dir / task_id / gate_name
        if not artifact_dir.exists():
            return None
        artifacts = sorted(artifact_dir.glob("*.json"), reverse=True)
        if not artifacts:
            return None
        return json.loads(artifacts[0].read_text())

    def is_fresh(self, gate_name: str, task_id: str, max_age_seconds: int = 300) -> bool:
        """Check if the latest artifact is still fresh."""
        latest = self.get_latest(gate_name, task_id)
        if not latest:
            return False
        stored_at = datetime.fromisoformat(latest["stored_at"])
        age = (datetime.now() - stored_at).total_seconds()
        return age < max_age_seconds


class GatePipeline:
    """Run verification gates in sequence with artifact storage."""

    def __init__(
        self,
        executor: VerificationExecutor | None = None,
        artifact_store: ArtifactStore | None = None,
        staleness_threshold_seconds: int = 300,
        require_before_completion: bool = True,
        store_artifacts: bool = True,
    ) -> None:
        self.executor = executor or VerificationExecutor()
        self.artifact_store = artifact_store or ArtifactStore()
        self.staleness_threshold = staleness_threshold_seconds
        self.require_before_completion = require_before_completion
        self.store_artifacts = store_artifacts

    def run_gate(
        self,
        gate_name: str,
        command: str,
        task_id: str,
        required: bool = False,
        timeout: int = 300,
        cwd: str | Path | None = None,
    ) -> GateResult:
        """Run a single verification gate."""
        # Check freshness first
        if self.artifact_store.is_fresh(gate_name, task_id, self.staleness_threshold):
            latest = self.artifact_store.get_latest(gate_name, task_id)
            if latest and latest["result"]["success"]:
                return GateResult(
                    gate_name=gate_name,
                    status=GateStatus.PASSED,
                    is_fresh=True,
                )

        result = self.executor.verify(command, task_id, timeout=timeout, cwd=cwd)

        artifact_path = None
        if self.store_artifacts:
            artifact_path = self.artifact_store.store(gate_name, task_id, result)

        status = GateStatus.PASSED if result.success else GateStatus.FAILED

        return GateResult(
            gate_name=gate_name,
            status=status,
            verification_result=result,
            artifact_path=artifact_path,
        )

    def run_pipeline(
        self,
        gates: list[dict[str, Any]],
        task_id: str,
        cwd: str | Path | None = None,
        stop_on_required_failure: bool = True,
    ) -> PipelineResult:
        """Run all gates in sequence.

        Args:
            gates: List of gate dicts with keys: name, command, required, timeout
            task_id: Task being verified
            cwd: Working directory
            stop_on_required_failure: Stop pipeline if a required gate fails
        """
        results: list[GateResult] = []
        start = time.time()

        for gate in gates:
            gate_result = self.run_gate(
                gate_name=gate["name"],
                command=gate["command"],
                task_id=task_id,
                required=gate.get("required", False),
                timeout=gate.get("timeout", 300),
                cwd=cwd,
            )
            results.append(gate_result)

            if stop_on_required_failure and gate.get("required", False) and gate_result.status == GateStatus.FAILED:
                # Skip remaining gates
                break

        total_ms = int((time.time() - start) * 1000)
        all_passed = all(r.status == GateStatus.PASSED for r in results)
        required_passed = all(r.status == GateStatus.PASSED for r, g in zip(results, gates) if g.get("required", False))

        return PipelineResult(
            gate_results=results,
            all_passed=all_passed,
            required_passed=required_passed,
            total_duration_ms=total_ms,
        )

    def check_staleness(self, gate_name: str, task_id: str) -> bool:
        """Check if a gate result is stale and needs re-running."""
        return not self.artifact_store.is_fresh(gate_name, task_id, self.staleness_threshold)
