"""Architecture compliance quality gate plugin.

Runs architecture validation as a quality gate at ship/merge time.
Respects gates_at_ship_only setting - does not run between levels.
"""

from __future__ import annotations

import time
from pathlib import Path

from zerg.architecture import (
    ArchitectureChecker,
    ArchitectureConfig,
    Violation,
    format_violations,
    load_architecture_config,
)
from zerg.ast_cache import ASTCache
from zerg.constants import GateResult
from zerg.plugins import GateContext, QualityGatePlugin
from zerg.types import GateRunResult


class ArchitectureGate(QualityGatePlugin):
    """Quality gate for architecture compliance.

    Checks Python files against configured layer definitions,
    import rules, and naming conventions. Runs at ship/merge time
    as part of the quality gate pipeline.
    """

    def __init__(self) -> None:
        """Initialize gate with AST cache for performance."""
        self._cache = ASTCache()
        self._config: ArchitectureConfig | None = None

    @property
    def name(self) -> str:
        """Unique name identifying this quality gate."""
        return "architecture"

    def run(self, ctx: GateContext) -> GateRunResult:
        """Execute architecture validation.

        Args:
            ctx: Gate context with cwd, feature, level, config

        Returns:
            GateRunResult with pass/fail status and details
        """
        start_time = time.time()

        # Load architecture config
        config = self._load_config(ctx.cwd)

        if not config.enabled:
            return GateRunResult(
                gate_name=self.name,
                result=GateResult.SKIP,
                command="architecture-check",
                exit_code=0,
                stdout="Architecture checking disabled in config",
                duration_ms=int((time.time() - start_time) * 1000),
            )

        # Run architecture checks
        checker = ArchitectureChecker(config, self._cache)
        violations = checker.check_directory(ctx.cwd)

        duration_ms = int((time.time() - start_time) * 1000)

        # Count errors vs warnings
        errors = [v for v in violations if v.severity == "error"]
        warnings = [v for v in violations if v.severity == "warning"]

        if errors:
            return GateRunResult(
                gate_name=self.name,
                result=GateResult.FAIL,
                command="architecture-check",
                exit_code=1,
                stderr=format_violations(violations),
                duration_ms=duration_ms,
            )

        # Warnings don't fail the gate
        if warnings:
            return GateRunResult(
                gate_name=self.name,
                result=GateResult.PASS,
                command="architecture-check",
                exit_code=0,
                stdout=f"Architecture check passed with {len(warnings)} warnings",
                stderr=format_violations(warnings),
                duration_ms=duration_ms,
            )

        # Count files checked
        file_count = sum(1 for _ in ctx.cwd.glob("**/*.py") if not self._should_skip(ctx.cwd, _))

        return GateRunResult(
            gate_name=self.name,
            result=GateResult.PASS,
            command="architecture-check",
            exit_code=0,
            stdout=f"Architecture check passed: {file_count} files validated, 0 violations",
            duration_ms=duration_ms,
        )

    def _load_config(self, cwd: Path) -> ArchitectureConfig:
        """Load architecture config from project directory."""
        if self._config is not None:
            return self._config

        config_path = cwd / ".zerg" / "config.yaml"
        self._config = load_architecture_config(config_path)
        return self._config

    def _should_skip(self, root: Path, path: Path) -> bool:
        """Check if path should be skipped."""
        try:
            rel = path.relative_to(root)
            return any(part.startswith(".") or part == "__pycache__" for part in rel.parts)
        except ValueError:
            return True


def check_files(files: list[Path], root: Path | None = None) -> list[Violation]:
    """Check specific files for architecture violations.

    Convenience function for checking a subset of files,
    useful for diff-aware validation.

    Args:
        files: List of file paths to check
        root: Project root directory

    Returns:
        List of violations found
    """
    root = root or Path.cwd()
    config = load_architecture_config(root / ".zerg" / "config.yaml")

    if not config.enabled:
        return []

    cache = ASTCache()
    checker = ArchitectureChecker(config, cache)

    violations: list[Violation] = []
    for file_path in files:
        if file_path.suffix == ".py" and file_path.exists():
            violations.extend(checker.check_file(file_path, root=root))

    return violations


def main() -> int:
    """CLI entry point for architecture checking.

    Returns:
        Exit code (0 for success, 1 for violations)
    """
    import argparse

    parser = argparse.ArgumentParser(description="Check architecture compliance")
    parser.add_argument("--check", action="store_true", help="Run architecture check")
    parser.add_argument("--dir", type=Path, default=Path.cwd(), help="Directory to check")
    parser.add_argument("--config", type=Path, help="Config file path")
    args = parser.parse_args()

    if args.config:
        config = load_architecture_config(args.config)
    else:
        config = load_architecture_config(args.dir / ".zerg" / "config.yaml")

    if not config.enabled:
        print("Architecture checking disabled")
        return 0

    cache = ASTCache()
    checker = ArchitectureChecker(config, cache)
    violations = checker.check_directory(args.dir)

    print(format_violations(violations))

    errors = [v for v in violations if v.severity == "error"]
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
