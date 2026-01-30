"""Quality gate execution for ZERG."""

import time
from pathlib import Path

from zerg.command_executor import CommandExecutor, CommandValidationError
from zerg.config import QualityGate, ZergConfig
from zerg.constants import GateResult
from zerg.exceptions import GateFailureError, GateTimeoutError
from zerg.logging import get_logger
from zerg.plugins import GateContext, PluginRegistry
from zerg.types import GateRunResult

logger = get_logger("gates")


class GateRunner:
    """Execute quality gates and capture results."""

    def __init__(
        self,
        config: ZergConfig | None = None,
        plugin_registry: PluginRegistry | None = None,
    ) -> None:
        """Initialize gate runner.

        Args:
            config: ZERG configuration (loads default if not provided)
            plugin_registry: Optional plugin registry for plugin gates
        """
        self.config = config or ZergConfig.load()
        self._results: list[GateRunResult] = []
        self._plugin_registry = plugin_registry

    def _get_executor(self, cwd: Path | None = None, timeout: int = 60) -> CommandExecutor:
        """Get command executor for gate execution."""
        return CommandExecutor(
            working_dir=cwd,
            allow_unlisted=True,  # Allow custom gate commands with warning
            timeout=timeout,
        )

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
        cwd_path = Path(cwd) if cwd else Path.cwd()

        logger.info(f"Running gate: {gate.name}")
        logger.debug(f"Command: {gate.command}")

        try:
            # Use secure command executor - no shell=True
            executor = self._get_executor(cwd_path, timeout=gate.timeout)
            result = executor.execute(
                gate.command,
                timeout=gate.timeout,
                env=env,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            if result.success:
                gate_result = GateResult.PASS
                logger.info(f"Gate {gate.name} passed ({duration_ms}ms)")
            elif "timed out" in result.stderr.lower():
                # CommandExecutor returns timeout info in stderr
                gate_result = GateResult.TIMEOUT
                logger.warning(f"Gate {gate.name} timed out")
            else:
                gate_result = GateResult.FAIL
                logger.warning(f"Gate {gate.name} failed with exit code {result.exit_code}")

            run_result = GateRunResult(
                gate_name=gate.name,
                result=gate_result,
                command=gate.command,
                exit_code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=duration_ms,
            )

        except CommandValidationError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Gate {gate.name} command validation failed: {e}")

            run_result = GateRunResult(
                gate_name=gate.name,
                result=GateResult.ERROR,
                command=gate.command,
                exit_code=-1,
                stderr=f"Command validation failed: {e}",
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
        feature: str = "",
        level: int = 0,
    ) -> tuple[bool, list[GateRunResult]]:
        """Run all quality gates.

        Args:
            gates: List of gates to run (uses config gates if not provided)
            cwd: Working directory
            stop_on_failure: Stop on first failure
            required_only: Only run required gates
            feature: Feature name for plugin gate context
            level: Level number for plugin gate context

        Returns:
            Tuple of (all_passed, list of results)
        """
        if gates is None:
            gates = self.config.quality_gates

        if required_only:
            gates = [g for g in gates if g.required]

        if not gates and not self._plugin_registry:
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

        # Run plugin gates if registry is available
        if self._plugin_registry:
            plugin_results = self.run_plugin_gates(GateContext(
                feature=feature,
                level=level,
                cwd=Path(cwd) if cwd else Path.cwd(),
                config=self.config,
            ))
            for result in plugin_results:
                results.append(result)
                if result.result not in (GateResult.PASS, GateResult.SKIP):
                    # Check if this plugin gate is required
                    is_required = self._plugin_registry.is_gate_required(result.gate_name)
                    if is_required:
                        all_passed = False
                        if stop_on_failure:
                            logger.error(f"Stopping: required plugin gate {result.gate_name} failed")
                            break
                    else:
                        logger.warning(f"Optional plugin gate {result.gate_name} failed (continuing)")

        return all_passed, results

    def run_plugin_gates(self, ctx: GateContext) -> list[GateRunResult]:
        """Run all registered plugin gates.

        Args:
            ctx: Gate context with feature, level, cwd, config

        Returns:
            List of GateRunResult from plugin gates
        """
        if not self._plugin_registry:
            return []

        results = []
        for name in list(self._plugin_registry._gates.keys()):
            result = self._plugin_registry.run_plugin_gate(name, ctx)
            results.append(result)
            self._results.append(result)
        return results

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
            GateFailureError: If gate failed and raise_on_failure is True
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

        raise GateFailureError(
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
