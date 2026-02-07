"""Hadolint adapter for Dockerfile best-practice linting."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from zerg.fs_utils import collect_files
from zerg.performance.adapters.base import BaseToolAdapter
from zerg.performance.types import DetectedStack, PerformanceFinding, Severity

logger = logging.getLogger(__name__)

# hadolint level -> Severity mapping
_LEVEL_SEVERITY: dict[str, Severity] = {
    "error": Severity.HIGH,
    "warning": Severity.MEDIUM,
    "info": Severity.LOW,
    "style": Severity.INFO,
}


class HadolintAdapter(BaseToolAdapter):
    """Adapter for hadolint Dockerfile linting."""

    name: str = "hadolint"
    tool_name: str = "hadolint"
    # Factor IDs: Container Image category (Dockerfile best practices)
    factors_covered: list[int] = [19, 20, 21]

    def is_applicable(self, stack: DetectedStack) -> bool:
        """Only applicable when the project uses Docker."""
        return stack.has_docker

    def run(
        self,
        files: list[str],
        project_path: str,
        stack: DetectedStack,
    ) -> list[PerformanceFinding]:
        """Run hadolint on all Dockerfiles found under *project_path*."""
        findings: list[PerformanceFinding] = []
        try:
            dockerfiles = self._find_dockerfiles(project_path)
            for dockerfile in dockerfiles:
                findings.extend(self._lint_dockerfile(dockerfile))
        except OSError:
            logger.debug("hadolint adapter failed to scan project path", exc_info=True)
        return findings

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_dockerfiles(project_path: str) -> list[Path]:
        """Return all Dockerfile-like files under *project_path*.

        Uses :func:`~zerg.fs_utils.collect_files` with the ``names``
        parameter instead of a raw rglob traversal.
        """
        root = Path(project_path)
        results: list[Path] = []
        default = root / "Dockerfile"
        if default.is_file():
            results.append(default)
        # Single traversal via collect_files — collect files whose name contains "Dockerfile"
        grouped = collect_files(root, names={"Dockerfile"})
        for p in grouped.get("_by_name", []):
            name = p.name
            # Match *.Dockerfile (e.g. prod.Dockerfile) and Dockerfile.* (e.g. Dockerfile.dev)
            if name.endswith(".Dockerfile") or (name.startswith("Dockerfile.") and name != "Dockerfile"):
                results.append(p)
        # Deduplicate while preserving order
        seen: set[Path] = set()
        unique: list[Path] = []
        for p in results:
            resolved = p.resolve()
            if resolved not in seen:
                seen.add(resolved)
                unique.append(p)
        return unique

    def _lint_dockerfile(self, dockerfile: Path) -> list[PerformanceFinding]:
        """Run ``hadolint --format json`` on a single Dockerfile."""
        try:
            result = subprocess.run(
                ["hadolint", "--format", "json", str(dockerfile)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            # hadolint exits non-zero when it finds issues — still parse stdout
            data = json.loads(result.stdout)
        except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
            logger.debug(
                "hadolint failed or produced unparseable output for %s",
                dockerfile,
                exc_info=True,
            )
            return []

        if not isinstance(data, list):
            return []

        findings: list[PerformanceFinding] = []
        rel_path = str(dockerfile)

        for item in data:
            if not isinstance(item, dict):
                continue

            level = item.get("level", "info")
            severity = _LEVEL_SEVERITY.get(level, Severity.LOW)
            code = item.get("code", "")
            message = item.get("message", "")
            line = item.get("line", 0)

            findings.append(
                PerformanceFinding(
                    factor_id=21,
                    factor_name="Dockerfile best practices",
                    category="Container Image",
                    severity=severity,
                    message=message,
                    file=rel_path,
                    line=line,
                    tool=self.name,
                    rule_id=str(code),
                    suggestion=f"Fix hadolint rule {code}: {message}",
                )
            )

        return findings
