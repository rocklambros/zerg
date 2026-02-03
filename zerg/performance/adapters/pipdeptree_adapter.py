"""pipdeptree adapter for transitive dependency analysis."""

from __future__ import annotations

import json
import logging
import subprocess

from zerg.performance.adapters.base import BaseToolAdapter
from zerg.performance.types import DetectedStack, PerformanceFinding, Severity

logger = logging.getLogger(__name__)


class PipdeptreeAdapter(BaseToolAdapter):
    """Adapter for pipdeptree transitive dependency analysis."""

    name: str = "pipdeptree"
    tool_name: str = "pipdeptree"
    # Factor 80 = Transitive dependency blindness (Dependencies)
    factors_covered: list[int] = [80]

    def is_applicable(self, stack: DetectedStack) -> bool:
        """pipdeptree only works on Python projects."""
        return "python" in stack.languages

    def run(
        self,
        files: list[str],
        project_path: str,
        stack: DetectedStack,
    ) -> list[PerformanceFinding]:
        """Run pipdeptree and analyze the dependency tree."""
        try:
            result = subprocess.run(
                ["pipdeptree", "--json"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            data = json.loads(result.stdout)
        except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
            logger.debug("pipdeptree failed or produced unparseable output", exc_info=True)
            return []

        if not isinstance(data, list):
            logger.debug("pipdeptree output is not a JSON array")
            return []

        return self._analyze_tree(data, result.stderr or "")

    def _analyze_tree(self, packages: list[object], stderr: str) -> list[PerformanceFinding]:
        """Analyze the dependency tree for depth, size, and conflicts."""
        findings: list[PerformanceFinding] = []

        # Count total transitive dependencies
        total_transitive = 0
        max_depth = 0
        for pkg in packages:
            if not isinstance(pkg, dict):
                continue
            deps = pkg.get("dependencies", [])
            if isinstance(deps, list):
                depth, count = self._measure_deps(deps)
                total_transitive += count
                max_depth = max(max_depth, depth)

        # Total transitive dependency count findings
        if total_transitive > 200:
            findings.append(
                PerformanceFinding(
                    factor_id=80,
                    factor_name="Transitive dependency blindness",
                    category="Dependencies",
                    severity=Severity.HIGH,
                    message=(f"Very large transitive dependency tree: {total_transitive} transitive dependencies"),
                    tool=self.name,
                    rule_id="transitive-count-high",
                    suggestion=("Audit dependencies and remove unnecessary packages to reduce supply-chain risk"),
                )
            )
        elif total_transitive > 100:
            findings.append(
                PerformanceFinding(
                    factor_id=80,
                    factor_name="Transitive dependency blindness",
                    category="Dependencies",
                    severity=Severity.MEDIUM,
                    message=(f"Large transitive dependency tree: {total_transitive} transitive dependencies"),
                    tool=self.name,
                    rule_id="transitive-count-medium",
                    suggestion="Review dependency tree for redundant or replaceable packages",
                )
            )

        # Max depth findings
        if max_depth > 10:
            findings.append(
                PerformanceFinding(
                    factor_id=80,
                    factor_name="Transitive dependency blindness",
                    category="Dependencies",
                    severity=Severity.HIGH,
                    message=f"Very deep dependency chain: max depth {max_depth}",
                    tool=self.name,
                    rule_id="depth-high",
                    suggestion=(
                        "Deep dependency chains increase fragility;"
                        " consider flattening or replacing"
                        " deeply-nested packages"
                    ),
                )
            )
        elif max_depth > 5:
            findings.append(
                PerformanceFinding(
                    factor_id=80,
                    factor_name="Transitive dependency blindness",
                    category="Dependencies",
                    severity=Severity.MEDIUM,
                    message=f"Deep dependency chain: max depth {max_depth}",
                    tool=self.name,
                    rule_id="depth-medium",
                    suggestion=("Review deeply-nested dependency chains for potential simplification"),
                )
            )

        # Check stderr for conflict warnings
        if "conflict" in stderr.lower():
            findings.append(
                PerformanceFinding(
                    factor_id=80,
                    factor_name="Transitive dependency blindness",
                    category="Dependencies",
                    severity=Severity.HIGH,
                    message="Dependency version conflicts detected by pipdeptree",
                    tool=self.name,
                    rule_id="version-conflict",
                    suggestion="Resolve version conflicts to prevent runtime errors",
                )
            )

        return findings

    def _measure_deps(self, deps: list[object], depth: int = 1) -> tuple[int, int]:
        """Recursively measure depth and count of a dependency list.

        Returns ``(max_depth, total_count)`` for the subtree.
        """
        total = 0
        current_max = depth
        for dep in deps:
            if not isinstance(dep, dict):
                continue
            total += 1
            children = dep.get("dependencies", [])
            if isinstance(children, list) and children:
                child_depth, child_count = self._measure_deps(children, depth + 1)
                current_max = max(current_max, child_depth)
                total += child_count
        return current_max, total
