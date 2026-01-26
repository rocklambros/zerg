"""Quality gate execution for ZERG."""

import subprocess
import time
from pathlib import Path

from zerg.config import QualityGate, ZergConfig
from zerg.constants import GateResult
from zerg.exceptions import GateFailure, GateTimeoutError
from zerg.logging import get_logger
from zerg.types import GateRunResult

logger = get_logger("gates")


class GateRunner:
    """Execute quality gates and capture results."""

    def __init__(self, config: ZergConfig | None = None) -> None:
        """Initialize gate runner.

        Args:
            config: ZERG configuration (loads default if not provided)
        """
        self.config = config or ZergConfig.load()
        self._results: list[GateRunResult] = []

    def run_gate(
        self,
        gate: QualityGate,
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
    ) -> GateRunResult:
        """Run a single quality gate.

        Args:
            gate: Gate configuration
            cwd: Working directory
            env: Environment variables

        Returns:
            GateRunResult with execution details
        """
        start_time = time.time()
        cwd = Path(cwd) if cwd else Path.cwd()

        logger.info(f"Running gate: {gate.name}")
        logger.debug(f"Command: {gate.command}")

        try:
            result = subprocess.run(
                gate.command,
                shell=True,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=gate.timeout,
                env=env,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            if result.returncode == 0:
                gate_result = GateResult.PASS
                logger.info(f"Gate {gate.name} passed ({duration_ms}ms)")
            else:
                gate_result = GateResult.FAIL
                logger.warning(f"Gate {gate.name} failed with exit code {result.returncode}")

            run_result = GateRunResult(
                gate_name=gate.name,
                result=gate_result,
                command=gate.command,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=duration_ms,
            )

        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Gate {gate.name} timed out after {gate.timeout}s")

            run_result = GateRunResult(
                gate_name=gate.name,
                result=GateResult.TIMEOUT,
                command=gate.command,
                exit_code=-1,
                stderr=f"Timeout after {gate.timeout}s",
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Gate {gate.name} error: {e}")

            run_result = GateRunResult(
                gate_name=gate.name,
                result=GateResult.ERROR,
                command=gate.command,
                exit_code=-1,
                stderr=str(e),
                duration_ms=duration_ms,
            )

        self._results.append(run_result)
        return run_result

    def run_all_gates(
        self,
        gates: list[QualityGate] | None = None,
        cwd: str | Path | None = None,
        stop_on_failure: bool = True,
        required_only: bool = False,
    ) -> tuple[bool, list[GateRunResult]]:
        """Run all quality gates.

        Args:
            gates: List of gates to run (uses config gates if not provided)
            cwd: Working directory
            stop_on_failure: Stop on first failure
            required_only: Only run required gates

        Returns:
            Tuple of (all_passed, list of results)
        """
        if gates is None:
            gates = self.config.quality_gates

        if required_only:
            gates = [g for g in gates if g.required]

        if not gates:
            logger.info("No gates to run")
            return True, []

        results = []
        all_passed = True

        for gate in gates:
            result = self.run_gate(gate, cwd=cwd)
            results.append(result)

            if result.result not in (GateResult.PASS, GateResult.SKIP):
                if gate.required:
                    all_passed = False
                    if stop_on_failure:
                        logger.error(f"Stopping: required gate {gate.name} failed")
                        break
                else:
                    logger.warning(f"Optional gate {gate.name} failed (continuing)")

        return all_passed, results

    def run_gate_by_name(
        self,
        name: str,
        cwd: str | Path | None = None,
    ) -> GateRunResult:
        """Run a gate by name from configuration.

        Args:
            name: Gate name
            cwd: Working directory

        Returns:
            GateRunResult

        Raises:
            ValueError: If gate not found
        """
        gate = self.config.get_gate(name)
        if not gate:
            raise ValueError(f"Gate not found: {name}")

        return self.run_gate(gate, cwd=cwd)

    def check_result(self, result: GateRunResult, raise_on_failure: bool = True) -> bool:
        """Check a gate result and optionally raise on failure.

        Args:
            result: Gate run result
            raise_on_failure: Raise exception on failure

        Returns:
            True if gate passed

        Raises:
            GateFailure: If gate failed and raise_on_failure is True
            GateTimeoutError: If gate timed out and raise_on_failure is True
        """
        if result.result == GateResult.PASS:
            return True

        if result.result == GateResult.SKIP:
            return True

        if not raise_on_failure:
            return False

        if result.result == GateResult.TIMEOUT:
            raise GateTimeoutError(
                f"Gate {result.gate_name} timed out",
                gate_name=result.gate_name,
                timeout_seconds=result.duration_ms // 1000,
            )

        raise GateFailure(
            f"Gate {result.gate_name} failed",
            gate_name=result.gate_name,
            command=result.command,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    def get_results(self) -> list[GateRunResult]:
        """Get all gate results from this session.

        Returns:
            List of GateRunResult
        """
        return self._results.copy()

    def clear_results(self) -> None:
        """Clear stored results."""
        self._results.clear()

    def get_summary(self) -> dict[str, int]:
        """Get summary of gate results.

        Returns:
            Dictionary with result counts
        """
        summary = {
            "total": len(self._results),
            "passed": 0,
            "failed": 0,
            "timeout": 0,
            "error": 0,
            "skipped": 0,
        }

        for result in self._results:
            if result.result == GateResult.PASS:
                summary["passed"] += 1
            elif result.result == GateResult.FAIL:
                summary["failed"] += 1
            elif result.result == GateResult.TIMEOUT:
                summary["timeout"] += 1
            elif result.result == GateResult.ERROR:
                summary["error"] += 1
            elif result.result == GateResult.SKIP:
                summary["skipped"] += 1

        return summary
