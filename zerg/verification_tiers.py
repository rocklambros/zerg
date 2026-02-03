"""Three-tier verification executor for ZERG tasks."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any

from zerg.command_executor import CommandExecutor, CommandValidationError
from zerg.config import VerificationTiersConfig
from zerg.logging import get_logger

logger = get_logger("verification_tiers")


@dataclass
class TierResult:
    """Result of a single verification tier."""

    tier: int  # 1, 2, or 3
    name: str  # "syntax", "correctness", "quality"
    success: bool
    blocking: bool
    command: str
    stdout: str
    stderr: str
    duration_ms: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TieredVerificationResult:
    """Aggregate result of all verification tiers for a task."""

    task_id: str
    tiers: list[TierResult] = field(default_factory=list)

    @property
    def overall_pass(self) -> bool:
        """All blocking tiers passed."""
        return all(t.success for t in self.tiers if t.blocking)

    @property
    def overall_quality(self) -> bool:
        """All tiers including non-blocking passed."""
        return all(t.success for t in self.tiers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "tiers": [t.to_dict() for t in self.tiers],
            "overall_pass": self.overall_pass,
            "overall_quality": self.overall_quality,
        }


# Default tier definitions
TIER_DEFINITIONS = [
    {"tier": 1, "name": "syntax", "config_blocking": "tier1_blocking", "config_command": "tier1_command"},
    {"tier": 2, "name": "correctness", "config_blocking": "tier2_blocking", "config_command": "tier2_command"},
    {"tier": 3, "name": "quality", "config_blocking": "tier3_blocking", "config_command": "tier3_command"},
]


class VerificationTiers:
    """Execute task verification in three tiers with escalation for ambiguous failures.

    Tier 1 (syntax): Fast checks — linting, type checking, import validation.
    Tier 2 (correctness): Functional checks — unit tests, verification commands.
    Tier 3 (quality): Non-blocking — code quality, coverage, style.
    """

    def __init__(
        self,
        config: VerificationTiersConfig | None = None,
        default_timeout: int = 30,
    ) -> None:
        self._config = config or VerificationTiersConfig()
        self._default_timeout = default_timeout

    def execute(
        self,
        task: dict,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> TieredVerificationResult:
        """Run all configured verification tiers for a task.

        Falls back to the task's own verification command for tier 2
        if no explicit tier commands are configured.
        """
        task_id = task.get("id", "unknown")
        result = TieredVerificationResult(task_id=task_id)

        # Build tier commands — use task verification as tier 2 fallback
        task_verification = task.get("verification", {})
        task_cmd = task_verification.get("command", "")
        task_timeout = task_verification.get("timeout_seconds", self._default_timeout)

        tier_commands = self._resolve_tier_commands(task_cmd)

        for tier_def in TIER_DEFINITIONS:
            tier_num = tier_def["tier"]
            tier_name = tier_def["name"]
            blocking = getattr(self._config, tier_def["config_blocking"])
            command = tier_commands.get(tier_num)

            if not command:
                continue

            tier_result = self._run_tier(
                tier=tier_num,
                name=tier_name,
                command=command,
                blocking=blocking,
                cwd=cwd,
                env=env,
                timeout=task_timeout if tier_num == 2 else self._default_timeout,
            )
            result.tiers.append(tier_result)

            # Stop on blocking tier failure
            if not tier_result.success and tier_result.blocking:
                logger.warning(
                    "Task %s failed blocking tier %d (%s)",
                    task_id,
                    tier_num,
                    tier_name,
                )
                break

        return result

    def _resolve_tier_commands(self, task_command: str) -> dict[int, str]:
        """Resolve which command to run at each tier."""
        commands: dict[int, str] = {}

        if self._config.tier1_command:
            commands[1] = self._config.tier1_command
        if self._config.tier2_command:
            commands[2] = self._config.tier2_command
        elif task_command:
            # Fall back to task's own verification command for tier 2
            commands[2] = task_command
        if self._config.tier3_command:
            commands[3] = self._config.tier3_command

        return commands

    def _run_tier(
        self,
        tier: int,
        name: str,
        command: str,
        blocking: bool,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> TierResult:
        """Execute a single verification tier."""
        timeout = timeout or self._default_timeout
        logger.info("Running tier %d (%s): %s", tier, name, command)
        start = time.time()

        try:
            from pathlib import Path

            executor = CommandExecutor(
                working_dir=Path(cwd) if cwd else None,
                allow_unlisted=True,
                timeout=timeout,
                trust_commands=False,
            )
            result = executor.execute(command, timeout=timeout, env=env)
            duration_ms = int((time.time() - start) * 1000)

            return TierResult(
                tier=tier,
                name=name,
                success=result.success,
                blocking=blocking,
                command=command,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=duration_ms,
            )
        except CommandValidationError as e:
            duration_ms = int((time.time() - start) * 1000)
            return TierResult(
                tier=tier,
                name=name,
                success=False,
                blocking=blocking,
                command=command,
                stdout="",
                stderr=f"Command validation failed: {e}",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            return TierResult(
                tier=tier,
                name=name,
                success=False,
                blocking=blocking,
                command=command,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
            )
