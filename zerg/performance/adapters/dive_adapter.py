"""Dive adapter for container image analysis via Dockerfile static inspection."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from zerg.performance.adapters.base import BaseToolAdapter
from zerg.performance.types import DetectedStack, PerformanceFinding, Severity

logger = logging.getLogger(__name__)

# Pattern: multiple consecutive RUN instructions that could be merged
_CONSECUTIVE_RUN_RE = re.compile(r"^RUN\s+", re.MULTILINE)


class DiveAdapter(BaseToolAdapter):
    """Adapter that statically analyses Dockerfiles for image-size anti-patterns.

    Because ``dive`` requires a pre-built image, this adapter instead performs
    lightweight Dockerfile parsing to detect common anti-patterns that lead to
    bloated or inefficient container images.
    """

    name: str = "dive"
    tool_name: str = "dive"
    # Factor IDs: Container Image category (image size, layer efficiency)
    factors_covered: list[int] = [19, 20]

    def is_applicable(self, stack: DetectedStack) -> bool:
        """Only applicable when the project uses Docker."""
        return stack.has_docker

    def run(
        self,
        files: list[str],
        project_path: str,
        stack: DetectedStack,
    ) -> list[PerformanceFinding]:
        """Analyse Dockerfiles found under *project_path* for anti-patterns."""
        findings: list[PerformanceFinding] = []
        try:
            dockerfiles = self._find_dockerfiles(project_path)
            for dockerfile in dockerfiles:
                findings.extend(self._analyse_dockerfile(dockerfile))
        except OSError:
            logger.debug("dive adapter failed to scan project path", exc_info=True)
        return findings

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_dockerfiles(project_path: str) -> list[Path]:
        """Return all Dockerfile-like files under *project_path*."""
        root = Path(project_path)
        results: list[Path] = []
        # Standard Dockerfile
        default = root / "Dockerfile"
        if default.is_file():
            results.append(default)
        # *.Dockerfile variants
        results.extend(sorted(root.rglob("*.Dockerfile")))
        # Dockerfile.* variants (e.g. Dockerfile.dev)
        results.extend(sorted(root.rglob("Dockerfile.*")))
        # Deduplicate while preserving order
        seen: set[Path] = set()
        unique: list[Path] = []
        for p in results:
            resolved = p.resolve()
            if resolved not in seen:
                seen.add(resolved)
                unique.append(p)
        return unique

    def _analyse_dockerfile(self, dockerfile: Path) -> list[PerformanceFinding]:
        """Run anti-pattern checks on a single Dockerfile."""
        try:
            content = dockerfile.read_text(encoding="utf-8", errors="replace")
        except OSError:
            logger.debug("Could not read %s", dockerfile, exc_info=True)
            return []

        findings: list[PerformanceFinding] = []
        rel_path = str(dockerfile)

        # Check 1: No multi-stage build
        if not self._has_multi_stage(content):
            findings.append(
                PerformanceFinding(
                    factor_id=19,
                    factor_name="Container image size",
                    category="Container Image",
                    severity=Severity.MEDIUM,
                    message="Dockerfile does not use multi-stage builds",
                    file=rel_path,
                    line=1,
                    tool=self.name,
                    rule_id="dive-no-multistage",
                    suggestion=("Use multi-stage builds to separate build dependencies from the final runtime image"),
                )
            )

        # Check 2: Multiple consecutive RUN commands that could be merged
        mergeable_lines = self._find_mergeable_runs(content)
        if mergeable_lines:
            findings.append(
                PerformanceFinding(
                    factor_id=20,
                    factor_name="Layer efficiency",
                    category="Container Image",
                    severity=Severity.LOW,
                    message=(f"Found {len(mergeable_lines)} RUN instructions that could be combined to reduce layers"),
                    file=rel_path,
                    line=mergeable_lines[0] if mergeable_lines else 0,
                    tool=self.name,
                    rule_id="dive-mergeable-runs",
                    suggestion=("Combine consecutive RUN instructions using '&&' to reduce the number of image layers"),
                )
            )

        # Check 3: COPY . before dependency install
        copy_all_line = self._find_early_copy_all(content)
        if copy_all_line:
            findings.append(
                PerformanceFinding(
                    factor_id=20,
                    factor_name="Layer efficiency",
                    category="Container Image",
                    severity=Severity.MEDIUM,
                    message=(
                        "COPY of entire context appears before dependency install, "
                        "which busts the layer cache on every code change"
                    ),
                    file=rel_path,
                    line=copy_all_line,
                    tool=self.name,
                    rule_id="dive-early-copy-all",
                    suggestion=(
                        "Copy dependency manifests first (e.g. requirements.txt, "
                        "package.json), install dependencies, then copy application code"
                    ),
                )
            )

        return findings

    # ------------------------------------------------------------------
    # Pattern detectors
    # ------------------------------------------------------------------

    @staticmethod
    def _has_multi_stage(content: str) -> bool:
        """Return True if the Dockerfile contains more than one FROM instruction."""
        from_count = sum(1 for line in content.splitlines() if re.match(r"^\s*FROM\s+", line, re.IGNORECASE))
        return from_count >= 2

    @staticmethod
    def _find_mergeable_runs(content: str) -> list[int]:
        """Return line numbers of RUN instructions that appear consecutively."""
        lines = content.splitlines()
        run_line_numbers: list[int] = []
        prev_was_run = False
        mergeable: list[int] = []

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            # Skip blank lines and comments when checking consecutive
            if not stripped or stripped.startswith("#"):
                continue
            is_run = bool(re.match(r"^RUN\s+", stripped, re.IGNORECASE))
            if is_run:
                run_line_numbers.append(idx)
                if prev_was_run:
                    if not mergeable:
                        # Also include the previous RUN
                        mergeable.append(run_line_numbers[-2])
                    mergeable.append(idx)
            prev_was_run = is_run

        return mergeable

    @staticmethod
    def _find_early_copy_all(content: str) -> int | None:
        """Return the line number of ``COPY .`` that appears before an install command."""
        install_patterns = re.compile(
            r"^\s*RUN\s+.*(pip install|npm install|yarn install|apt-get install|apk add)",
            re.IGNORECASE,
        )
        lines = content.splitlines()
        copy_all_line: int | None = None

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if re.match(r"^COPY\s+\.\s", stripped, re.IGNORECASE):
                copy_all_line = idx
            elif install_patterns.match(stripped):
                # If we already saw COPY . before the first install, flag it
                if copy_all_line is not None:
                    return copy_all_line
                # Install found before COPY . — no issue
                return None

        return None
