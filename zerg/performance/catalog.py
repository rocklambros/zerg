"""Factor catalog loader for the ZERG performance analysis system."""

from __future__ import annotations

import importlib.resources
import json
from collections import defaultdict

from zerg.performance.types import PerformanceFactor

__all__ = ["FactorCatalog"]

STATIC_TOOLS: list[str] = [
    "semgrep",
    "radon",
    "lizard",
    "vulture",
    "jscpd",
    "deptry",
    "pipdeptree",
    "dive",
    "hadolint",
    "trivy",
    "cloc",
]

RUNTIME_ONLY_TOOLS: list[str] = [
    "perf",
    "perf stat",
    "perf c2c",
    "async-profiler",
    "cachegrind",
    "strace",
    "ltrace",
    "tcpdump",
    "wrk",
    "ab",
    "k6",
    "hey",
    "vegeta",
    "pprof",
    "go tool pprof",
    "py-spy",
    "dtrace",
    "bpftrace",
    "valgrind",
    "iotop",
    "blktrace",
    "nethogs",
    "iftop",
    "ss",
    "lsof",
    "gcc -fopt-info-vec",
    "clang -Rpass=loop-vectorize",
    "helm",
    "kubectl",
    "kube-bench",
]


class FactorCatalog:
    """Loads and queries the performance evaluation factor catalog."""

    def __init__(self, factors: list[PerformanceFactor]) -> None:
        self.factors = factors

    @classmethod
    def load(cls) -> FactorCatalog:
        """Load factors from the bundled JSON file via importlib.resources."""
        text = importlib.resources.files("zerg.performance.data").joinpath("factors.json").read_text(encoding="utf-8")
        raw = json.loads(text)
        factors = [
            PerformanceFactor(
                id=entry["id"],
                category=entry["category"],
                factor=entry["factor"],
                description=entry["description"],
                cli_tools=entry["cli_tools"],
                security_note=entry.get("security_note"),
            )
            for entry in raw["performance_evaluation_factors"]
        ]
        return cls(factors)

    def filter_static_only(self) -> list[PerformanceFactor]:
        """Return factors where at least one cli_tool is a static analysis tool."""
        static_set = set(STATIC_TOOLS)
        return [f for f in self.factors if any(t in static_set for t in f.cli_tools)]

    def get_tool_factor_mapping(self) -> dict[str, list[int]]:
        """Map each static tool name to the factor IDs it covers."""
        static_set = set(STATIC_TOOLS)
        mapping: dict[str, list[int]] = defaultdict(list)
        for factor in self.factors:
            for tool in factor.cli_tools:
                if tool in static_set:
                    mapping[tool].append(factor.id)
        return dict(mapping)

    def get_factors_by_category(self) -> dict[str, list[PerformanceFactor]]:
        """Group all factors by their category."""
        grouped: dict[str, list[PerformanceFactor]] = defaultdict(list)
        for factor in self.factors:
            grouped[factor.category].append(factor)
        return dict(grouped)
