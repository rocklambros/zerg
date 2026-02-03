"""Formatters for performance analysis report output."""

from __future__ import annotations

import json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from zerg.performance.types import (
    PerformanceReport,
    Severity,
)

__all__ = [
    "format_json",
    "format_markdown",
    "format_rich",
    "format_sarif",
]

_SEVERITY_ORDER = [
    Severity.CRITICAL,
    Severity.HIGH,
    Severity.MEDIUM,
    Severity.LOW,
    Severity.INFO,
]

_SARIF_LEVEL_MAP: dict[Severity, str] = {
    Severity.CRITICAL: "error",
    Severity.HIGH: "error",
    Severity.MEDIUM: "warning",
    Severity.LOW: "note",
    Severity.INFO: "note",
}

_MAX_FINDINGS_PER_CATEGORY = 10


def _score_style(score: float | None) -> str:
    """Return a Rich style string based on score value."""
    if score is None:
        return "dim"
    if score > 80:
        return "bold green"
    if score > 60:
        return "bold yellow"
    return "bold red"


def _severity_style(severity: Severity) -> str:
    """Return a Rich style string for a severity level."""
    styles: dict[Severity, str] = {
        Severity.CRITICAL: "bold red",
        Severity.HIGH: "red",
        Severity.MEDIUM: "yellow",
        Severity.LOW: "cyan",
        Severity.INFO: "dim",
    }
    return styles.get(severity, "")


def _sort_by_severity(findings: list) -> list:
    """Sort findings by severity weight, highest first."""
    return sorted(
        findings,
        key=lambda f: Severity.weight(f.severity),
        reverse=True,
    )


# ---------------------------------------------------------------------------
# Rich console output
# ---------------------------------------------------------------------------


def format_rich(report: PerformanceReport, console: Console) -> None:
    """Render the performance report to a Rich console.

    Args:
        report: The performance report to render.
        console: Rich Console instance for output.
    """
    # -- Overall score header --
    score_display = f"{report.overall_score:.0f}/100" if report.overall_score is not None else "N/A"
    style = _score_style(report.overall_score)
    header = Text(f"Performance Score: {score_display}", style=style)
    console.print(Panel(header, title="ZERG Performance Analysis", border_style=style))

    # -- Tool availability panel --
    tool_table = Table(title="Tool Availability", show_lines=False)
    tool_table.add_column("Tool", style="cyan")
    tool_table.add_column("Status")
    tool_table.add_column("Version", style="dim")
    tool_table.add_column("Factors", justify="right")

    for ts in report.tool_statuses:
        status_text = "[green]available[/green]" if ts.available else "[red]missing[/red]"
        tool_table.add_row(ts.name, status_text, ts.version or "-", str(ts.factors_covered))

    console.print(tool_table)
    console.print()

    # -- Per-category sections --
    for cat in report.categories:
        cat_score = f"{cat.score:.0f}/100" if cat.score is not None else "N/A"
        cat_style = _score_style(cat.score)
        console.print(Text(f"{cat.category}  ", style="bold") + Text(cat_score, style=cat_style))

        if not cat.findings:
            console.print("  No findings.\n")
            continue

        findings_table = Table(show_header=True, header_style="bold", pad_edge=False)
        findings_table.add_column("File", style="cyan", no_wrap=True)
        findings_table.add_column("Line", justify="right")
        findings_table.add_column("Severity")
        findings_table.add_column("Message")

        sorted_findings = _sort_by_severity(cat.findings)
        shown = sorted_findings[:_MAX_FINDINGS_PER_CATEGORY]
        remaining = len(sorted_findings) - len(shown)

        for f in shown:
            sev_text = Text(f.severity.value.upper(), style=_severity_style(f.severity))
            findings_table.add_row(
                f.file or "-",
                str(f.line) if f.line else "-",
                sev_text,
                f.message,
            )

        console.print(findings_table)
        if remaining > 0:
            console.print(f"  [dim]... and {remaining} more[/dim]")
        console.print()

    # -- Summary footer --
    total = len(report.findings)
    ratio = f"{report.factors_checked}/{report.factors_total}"
    console.print(
        Panel(
            f"Total findings: {total}  |  Factors coverage: {ratio}",
            title="Summary",
            border_style="dim",
        )
    )


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------


def format_json(report: PerformanceReport) -> str:
    """Serialize the performance report to a JSON string.

    Args:
        report: The performance report to serialize.

    Returns:
        A pretty-printed JSON string.
    """
    return json.dumps(report.to_dict(), indent=2)


# ---------------------------------------------------------------------------
# SARIF 2.1.0 output
# ---------------------------------------------------------------------------


def format_sarif(report: PerformanceReport) -> str:
    """Serialize the performance report to SARIF 2.1.0 format.

    Args:
        report: The performance report to serialize.

    Returns:
        A SARIF JSON string.
    """
    # Collect unique rules keyed by factor_id
    rules_map: dict[int, dict[str, str]] = {}
    for finding in report.findings:
        if finding.factor_id not in rules_map:
            rules_map[finding.factor_id] = {
                "id": f"PERF-{finding.factor_id}",
                "shortDescription": {"text": finding.factor_name},
            }

    # Build results
    results: list[dict] = []
    for finding in report.findings:
        entry: dict = {
            "ruleId": f"PERF-{finding.factor_id}",
            "level": _SARIF_LEVEL_MAP.get(finding.severity, "note"),
            "message": {"text": finding.message},
        }
        if finding.file:
            location: dict = {
                "physicalLocation": {
                    "artifactLocation": {"uri": finding.file},
                }
            }
            if finding.line:
                location["physicalLocation"]["region"] = {"startLine": finding.line}
            entry["locations"] = [location]
        results.append(entry)

    sarif = {
        "$schema": ("https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json"),
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "zerg-performance",
                        "version": "1.0",
                        "rules": list(rules_map.values()),
                    }
                },
                "results": results,
            }
        ],
    }

    return json.dumps(sarif, indent=2)


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------


def format_markdown(report: PerformanceReport) -> str:
    """Serialize the performance report to a Markdown string.

    Args:
        report: The performance report to serialize.

    Returns:
        A Markdown-formatted report.
    """
    lines: list[str] = []

    # Header
    score_display = f"{report.overall_score:.0f}" if report.overall_score is not None else "N/A"
    lines.append("# Performance Analysis Report")
    lines.append("")
    lines.append(
        f"**Overall Score**: {score_display}/100 | **Factors Checked**: {report.factors_checked}/{report.factors_total}"
    )
    lines.append("")

    # Tool availability
    lines.append("## Tool Availability")
    lines.append("| Tool | Status | Version |")
    lines.append("|------|--------|---------|")
    for ts in report.tool_statuses:
        status = "Available" if ts.available else "Missing"
        version = ts.version or "-"
        lines.append(f"| {ts.name} | {status} | {version} |")
    lines.append("")

    # Per-category sections
    for cat in report.categories:
        cat_score = f"{cat.score:.0f}" if cat.score is not None else "N/A"
        lines.append(f"## {cat.category} (Score: {cat_score}/100)")
        if cat.findings:
            lines.append("| Severity | File | Line | Message |")
            lines.append("|----------|------|------|---------|")
            sorted_findings = _sort_by_severity(cat.findings)
            for f in sorted_findings:
                sev = f.severity.value.upper()
                file_col = f.file or "-"
                line_col = str(f.line) if f.line else "-"
                lines.append(f"| {sev} | {file_col} | {line_col} | {f.message} |")
        else:
            lines.append("No findings.")
        lines.append("")

    # Summary
    severity_counts: dict[Severity, int] = dict.fromkeys(_SEVERITY_ORDER, 0)
    for f in report.findings:
        severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

    tools_used = [ts.name for ts in report.tool_statuses if ts.available]
    stack = report.detected_stack

    lines.append("## Summary")
    lines.append(f"- Total findings: {len(report.findings)}")
    lines.append(
        f"- Critical: {severity_counts[Severity.CRITICAL]}, "
        f"High: {severity_counts[Severity.HIGH]}, "
        f"Medium: {severity_counts[Severity.MEDIUM]}, "
        f"Low: {severity_counts[Severity.LOW]}, "
        f"Info: {severity_counts[Severity.INFO]}"
    )
    lines.append(f"- Tools used: {', '.join(tools_used) if tools_used else 'none'}")
    langs = ", ".join(stack.languages) if stack.languages else "none"
    fws = ", ".join(stack.frameworks) if stack.frameworks else "none"
    lines.append(f"- Detected stack: {langs}, {fws}")
    lines.append("")

    return "\n".join(lines)
