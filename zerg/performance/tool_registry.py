"""Tool registry for the ZERG performance analysis system.

Manages discovery and availability checking of external CLI tools
used by the performance analysis adapters.
"""

from __future__ import annotations

import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from zerg.performance.types import ToolStatus


@dataclass
class ToolSpec:
    """Specification for an external CLI tool."""

    name: str
    check_cmd: str
    version_flag: str
    install_hint: str


class ToolRegistry:
    """Registry of external CLI tools used by the performance analysis system.

    Provides parallel availability checking and advisory output for missing tools.
    """

    TOOL_SPECS: dict[str, ToolSpec] = {
        "semgrep": ToolSpec(
            name="semgrep",
            check_cmd="semgrep",
            version_flag="--version",
            install_hint="pip install semgrep",
        ),
        "radon": ToolSpec(
            name="radon",
            check_cmd="radon",
            version_flag="--version",
            install_hint="pip install radon",
        ),
        "lizard": ToolSpec(
            name="lizard",
            check_cmd="lizard",
            version_flag="--version",
            install_hint="pip install lizard",
        ),
        "vulture": ToolSpec(
            name="vulture",
            check_cmd="vulture",
            version_flag="--version",
            install_hint="pip install vulture",
        ),
        "jscpd": ToolSpec(
            name="jscpd",
            check_cmd="jscpd",
            version_flag="--version",
            install_hint="npm install -g jscpd",
        ),
        "deptry": ToolSpec(
            name="deptry",
            check_cmd="deptry",
            version_flag="--version",
            install_hint="pip install deptry",
        ),
        "pipdeptree": ToolSpec(
            name="pipdeptree",
            check_cmd="pipdeptree",
            version_flag="--version",
            install_hint="pip install pipdeptree",
        ),
        "dive": ToolSpec(
            name="dive",
            check_cmd="dive",
            version_flag="version",
            install_hint="brew install dive / go install github.com/wagoodman/dive@latest",
        ),
        "hadolint": ToolSpec(
            name="hadolint",
            check_cmd="hadolint",
            version_flag="--version",
            install_hint="brew install hadolint",
        ),
        "trivy": ToolSpec(
            name="trivy",
            check_cmd="trivy",
            version_flag="version",
            install_hint="brew install trivy",
        ),
        "cloc": ToolSpec(
            name="cloc",
            check_cmd="cloc",
            version_flag="--version",
            install_hint="brew install cloc / pip install cloc",
        ),
    }

    def _check_tool(self, spec: ToolSpec) -> ToolStatus:
        """Check availability and version of a single tool."""
        path = shutil.which(spec.check_cmd)
        if path is None:
            return ToolStatus(name=spec.name, available=False)

        version = ""
        try:
            result = subprocess.run(
                [path, spec.version_flag],
                capture_output=True,
                text=True,
                timeout=5,
            )
            raw = result.stdout.strip() or result.stderr.strip()
            # Take first non-empty line as version string
            for line in raw.splitlines():
                line = line.strip()
                if line:
                    version = line
                    break
        except (subprocess.TimeoutExpired, OSError):
            # Binary exists but version check failed; still mark available
            pass

        return ToolStatus(name=spec.name, available=True, version=version)

    def check_availability(self) -> list[ToolStatus]:
        """Check all registered tools for availability in parallel.

        Returns a list of ToolStatus for every tool in the registry.
        """
        specs = list(self.TOOL_SPECS.values())
        with ThreadPoolExecutor(max_workers=8) as executor:
            statuses = list(executor.map(self._check_tool, specs))
        return statuses

    def get_available(self) -> list[str]:
        """Return names of tools that are currently available on the system."""
        return [status.name for status in self.check_availability() if status.available]

    def print_advisory(self, console: Console, missing: list[ToolStatus]) -> None:
        """Print a Rich panel advising on missing tools and how to install them.

        Args:
            console: Rich Console instance for output.
            missing: List of ToolStatus entries for tools that are not available.
        """
        if not missing:
            return

        table = Table(show_header=True, header_style="bold yellow")
        table.add_column("Tool", style="cyan", no_wrap=True)
        table.add_column("Install Command", style="green")
        table.add_column("Factors Covered", justify="right", style="magenta")

        for status in missing:
            spec = self.TOOL_SPECS.get(status.name)
            hint = spec.install_hint if spec else "unknown"
            table.add_row(
                status.name,
                hint,
                str(status.factors_covered) if status.factors_covered else "-",
            )

        panel = Panel(
            table,
            title=f"[bold red]{len(missing)} Missing Tool(s)[/bold red]",
            subtitle="Install these tools for more comprehensive analysis",
            border_style="yellow",
        )
        console.print(panel)
