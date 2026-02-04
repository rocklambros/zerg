"""ZERG design command - generate architecture and task graph."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from zerg.backlog import generate_backlog_markdown
from zerg.logging import get_logger
from zerg.step_generator import StepGenerator

console = Console()
logger = get_logger("design")

# Valid detail levels for CLI
DETAIL_LEVELS = ("standard", "medium", "high")


@click.command()
@click.option("--feature", "-f", help="Feature name (uses current if not specified)")
@click.option("--max-task-minutes", default=30, type=int, help="Maximum minutes per task")
@click.option("--min-task-minutes", default=5, type=int, help="Minimum minutes per task")
@click.option("--validate-only", is_flag=True, help="Validate existing task graph only")
@click.option("--update-backlog", is_flag=True, help="Regenerate backlog from existing task graph")
@click.option(
    "--detail",
    "-d",
    type=click.Choice(DETAIL_LEVELS, case_sensitive=False),
    default="standard",
    help="Detail level for step generation: standard (no steps), medium (TDD steps), high (TDD with code snippets)",
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.pass_context
def design(
    ctx: click.Context,
    feature: str | None,
    max_task_minutes: int,
    min_task_minutes: int,
    validate_only: bool,
    update_backlog: bool,
    detail: str,
    verbose: bool,
) -> None:
    """Generate architecture and task graph.

    Creates .gsd/specs/{feature}/design.md and task-graph.json

    Reads requirements from .gsd/specs/{feature}/requirements.md
    and generates a task graph for parallel execution.

    The --detail option controls step generation:

    \b
    - standard: No steps generated (backward compatible, classic mode)
    - medium:   TDD sequence steps (write_test -> verify_fail -> implement -> verify_pass -> format -> commit)
    - high:     TDD steps with code snippets from AST analysis

    Examples:

        zerg design

        zerg design --feature user-auth

        zerg design --detail medium

        zerg design --detail high --feature complex-feature

        zerg design --validate-only

        zerg design --max-task-minutes 45 --min-task-minutes 10
    """
    try:
        console.print("\n[bold cyan]ZERG Design[/bold cyan]\n")

        # Print task list ID for coordination visibility
        task_list_id = os.environ.get("CLAUDE_CODE_TASK_LIST_ID")
        if task_list_id:
            console.print(f"Task List ID: {task_list_id}")
        else:
            console.print("Task List ID: (default)")

        # Get feature name
        if not feature:
            feature = get_current_feature()
            if not feature:
                console.print("[red]Error:[/red] No active feature")
                console.print("Run [cyan]zerg plan <feature>[/cyan] first")
                raise SystemExit(1)

        console.print(f"Feature: [cyan]{feature}[/cyan]\n")

        # Get spec directory
        spec_dir = Path(f".gsd/specs/{feature}")
        if not spec_dir.exists():
            console.print(f"[red]Error:[/red] Spec directory not found: {spec_dir}")
            console.print("Run [cyan]zerg plan {feature}[/cyan] first")
            raise SystemExit(1)

        # Check for requirements
        requirements_path = spec_dir / "requirements.md"
        if not requirements_path.exists():
            console.print(f"[red]Error:[/red] Requirements not found: {requirements_path}")
            console.print("Run [cyan]zerg plan {feature}[/cyan] first")
            raise SystemExit(1)

        # Check approval status - look for Status line containing APPROVED
        requirements_content = requirements_path.read_text()
        is_approved = any("APPROVED" in line and "Status" in line for line in requirements_content.splitlines())
        if not is_approved:
            console.print("[yellow]Warning:[/yellow] Requirements not marked as APPROVED")
            if not click.confirm("Continue anyway?", default=True):
                console.print("[dim]Aborted[/dim]")
                return

        # Validate-only mode
        if validate_only:
            task_graph_path = spec_dir / "task-graph.json"
            if not task_graph_path.exists():
                console.print(f"[red]Error:[/red] No task graph found: {task_graph_path}")
                raise SystemExit(1)

            validate_task_graph(task_graph_path, detail_level=detail)

            task_data = _load_task_graph(task_graph_path)
            manifest = _build_design_manifest(feature, task_data)
            manifest_path = spec_dir / "design-tasks-manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2))
            click.echo(f"  ✓ Created {manifest_path}")
            return

        # Update-backlog mode
        if update_backlog:
            task_graph_path = spec_dir / "task-graph.json"
            if not task_graph_path.exists():
                console.print(f"[red]Error:[/red] No task graph found: {task_graph_path}")
                raise SystemExit(1)

            task_data = _load_task_graph(task_graph_path)
            backlog_path = generate_backlog_markdown(
                task_data=task_data,
                feature=feature,
            )
            console.print(f"[green]✓[/green] Regenerated {backlog_path}")

            manifest = _build_design_manifest(feature, task_data)
            manifest_path = spec_dir / "design-tasks-manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2))
            click.echo(f"  ✓ Created {manifest_path}")
            return

        # Generate design artifacts
        console.print("[bold]Generating design artifacts...[/bold]\n")

        # Create design.md template
        design_path = spec_dir / "design.md"
        create_design_template(design_path, feature)
        console.print(f"  [green]✓[/green] Created {design_path}")

        # Create task-graph.json template
        task_graph_path = spec_dir / "task-graph.json"
        create_task_graph_template(
            task_graph_path,
            feature,
            max_minutes=max_task_minutes,
            detail_level=detail,
        )
        console.print(f"  [green]✓[/green] Created {task_graph_path}")

        # Generate backlog markdown
        backlog_path = generate_backlog_markdown(
            task_data=_load_task_graph(task_graph_path),
            feature=feature,
        )
        console.print(f"  [green]✓[/green] Created {backlog_path}")

        # Generate design tasks manifest
        task_data = _load_task_graph(task_graph_path)
        manifest = _build_design_manifest(feature, task_data)
        manifest_path = spec_dir / "design-tasks-manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))
        click.echo(f"  ✓ Created {manifest_path}")

        # Show summary
        show_design_summary(spec_dir, feature, detail_level=detail)

        console.print("\n[green]✓[/green] Design artifacts created!")
        console.print("\nNext steps:")
        console.print("  1. Edit design.md with architecture details")
        console.print("  2. Populate task-graph.json with specific tasks")
        console.print("  3. Run [cyan]zerg design --validate-only[/cyan] to check")
        console.print("  4. Run [cyan]zerg rush[/cyan] to start execution")

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        raise SystemExit(130) from None
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        if verbose:
            console.print_exception()
        raise SystemExit(1) from e


def get_current_feature() -> str | None:
    """Get the current active feature.

    Returns:
        Feature name or None
    """
    current_feature_file = Path(".gsd/.current-feature")
    if current_feature_file.exists():
        return current_feature_file.read_text().strip()
    return None


def create_design_template(path: Path, feature: str) -> None:
    """Create design.md template.

    Args:
        path: Output path
        feature: Feature name
    """
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")

    content = f"""# Technical Design: {feature}

## Metadata
- **Feature**: {feature}
- **Status**: DRAFT
- **Created**: {timestamp}
- **Author**: ZERG Design

---

## 1. Overview

### 1.1 Summary
_One paragraph summary of the technical approach_

### 1.2 Goals
- Goal 1
- Goal 2

### 1.3 Non-Goals
- Non-goal 1
- Non-goal 2

---

## 2. Architecture

### 2.1 High-Level Design

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Input     │────▶│  Process    │────▶│   Output    │
└─────────────┘     └─────────────┘     └─────────────┘
```

### 2.2 Component Breakdown

| Component | Responsibility | Files |
|-----------|---------------|-------|
| | | |

### 2.3 Data Flow
_How data moves through the system_

---

## 3. Detailed Design

### 3.1 Data Models

```python
# Example data model
class Example:
    pass
```

### 3.2 API Design

```python
# Example API
def example_endpoint():
    pass
```

---

## 4. Key Decisions

### 4.1 Decision: _Title_

**Context**: _situation and problem_

**Options Considered**:
1. Option 1: pros/cons
2. Option 2: pros/cons

**Decision**: _chosen option_

**Rationale**: _why this option_

---

## 5. Implementation Plan

### 5.1 Phase Summary

| Phase | Tasks | Parallel | Est. Time |
|-------|-------|----------|-----------|
| Foundation | N | Yes | Xm |
| Core | N | Yes | Xm |
| Integration | N | Yes | Xm |
| Testing | N | Yes | Xm |

### 5.2 File Ownership

| File | Task ID | Operation |
|------|---------|-----------|
| | | create/modify |

### 5.3 Dependency Graph

```
TASK-001 ─┬─▶ TASK-003 ─▶ TASK-005
TASK-002 ─┘
```

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| | Low/Med/High | Low/Med/High | |

---

## 7. Testing Strategy

### 7.1 Unit Tests
_What will be unit tested_

### 7.2 Integration Tests
_What will be integration tested_

---

## 8. Parallel Execution Notes

### 8.1 Recommended Workers
- Minimum: N workers
- Optimal: N workers
- Maximum: N workers

### 8.2 Estimated Duration
- Single worker: Xm
- With N workers: Xm
- Speedup: Nx

---

## 9. Approval

| Role | Status |
|------|--------|
| Architecture | PENDING |
| Engineering | PENDING |
"""
    path.write_text(content)


def create_task_graph_template(
    path: Path,
    feature: str,
    max_minutes: int = 30,
    detail_level: str = "standard",
) -> None:
    """Create task-graph.json template.

    Args:
        path: Output path
        feature: Feature name
        max_minutes: Max minutes per task
        detail_level: Detail level for step generation (standard/medium/high)
    """
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Create template with example tasks
    task_graph = {
        "feature": feature,
        "version": "2.0",
        "generated": timestamp,
        "total_tasks": 6,
        "estimated_duration_minutes": 105,
        "max_parallelization": 3,
        "critical_path_minutes": 60,
        "tasks": [
            {
                "id": f"{feature.upper()[:4]}-L1-001",
                "title": "Define types and interfaces",
                "description": "Create TypeScript/Python types for the feature domain",
                "phase": "foundation",
                "level": 1,
                "dependencies": [],
                "files": {
                    "create": [f"src/{feature}/types.py"],
                    "modify": [],
                    "read": [],
                },
                "acceptance_criteria": [
                    "All domain types defined",
                    "Type hints complete",
                ],
                "verification": {
                    "command": f'python -c "from src.{feature}.types import *"',
                    "timeout_seconds": 60,
                },
                "estimate_minutes": 15,
                "critical_path": True,
            },
            {
                "id": f"{feature.upper()[:4]}-L1-002",
                "title": "Create configuration",
                "description": "Set up configuration and constants",
                "phase": "foundation",
                "level": 1,
                "dependencies": [],
                "files": {
                    "create": [f"src/{feature}/config.py"],
                    "modify": [],
                    "read": [],
                },
                "acceptance_criteria": [
                    "Configuration defined",
                    "Environment variables documented",
                ],
                "verification": {
                    "command": f'python -c "from src.{feature}.config import *"',
                    "timeout_seconds": 60,
                },
                "estimate_minutes": 10,
            },
            {
                "id": f"{feature.upper()[:4]}-L2-001",
                "title": "Implement core logic",
                "description": "Main business logic implementation",
                "phase": "core",
                "level": 2,
                "dependencies": [f"{feature.upper()[:4]}-L1-001", f"{feature.upper()[:4]}-L1-002"],
                "files": {
                    "create": [f"src/{feature}/service.py"],
                    "modify": [],
                    "read": [f"src/{feature}/types.py", f"src/{feature}/config.py"],
                },
                "acceptance_criteria": [
                    "Core functionality implemented",
                    "Error handling complete",
                ],
                "verification": {
                    "command": f"pytest tests/unit/test_{feature}_service.py -v",
                    "timeout_seconds": 120,
                },
                "estimate_minutes": 30,
                "critical_path": True,
            },
            {
                "id": f"{feature.upper()[:4]}-L3-001",
                "title": "Create API endpoints",
                "description": "HTTP API or CLI interface",
                "phase": "integration",
                "level": 3,
                "dependencies": [f"{feature.upper()[:4]}-L2-001"],
                "files": {
                    "create": [f"src/{feature}/api.py"],
                    "modify": [],
                    "read": [f"src/{feature}/service.py"],
                },
                "acceptance_criteria": [
                    "Endpoints implemented",
                    "Input validation complete",
                ],
                "verification": {
                    "command": f"pytest tests/integration/test_{feature}_api.py -v",
                    "timeout_seconds": 120,
                },
                "estimate_minutes": 20,
            },
            {
                "id": f"{feature.upper()[:4]}-L4-001",
                "title": "Write tests",
                "description": "Unit and integration tests",
                "phase": "testing",
                "level": 4,
                "dependencies": [f"{feature.upper()[:4]}-L3-001"],
                "files": {
                    "create": [
                        f"tests/unit/test_{feature}_service.py",
                        f"tests/integration/test_{feature}_api.py",
                    ],
                    "modify": [],
                    "read": [f"src/{feature}/"],
                },
                "acceptance_criteria": [
                    "Test coverage > 80%",
                    "All tests passing",
                ],
                "verification": {
                    "command": f"pytest tests/ -v --cov=src/{feature}",
                    "timeout_seconds": 180,
                },
                "estimate_minutes": 30,
                "critical_path": True,
            },
            {
                "id": f"{feature.upper()[:4]}-L5-001",
                "title": "Run quality analysis and create issues",
                "description": "Run /z:analyze --check all and create GitHub issues for findings",
                "phase": "quality",
                "level": 5,
                "dependencies": [f"{feature.upper()[:4]}-L4-001"],
                "files": {
                    "create": [],
                    "modify": ["CHANGELOG.md"],
                    "read": [],
                },
                "acceptance_criteria": [
                    "All analysis checks run",
                    "Issues created for failures",
                    "CHANGELOG updated",
                ],
                "verification": {
                    "command": "test -f .zerg/state/final-analysis.json",
                    "timeout_seconds": 300,
                },
                "estimate_minutes": 15,
            },
        ],
        "levels": {
            "1": {
                "name": "foundation",
                "tasks": [f"{feature.upper()[:4]}-L1-001", f"{feature.upper()[:4]}-L1-002"],
                "parallel": True,
                "estimated_minutes": 15,
            },
            "2": {
                "name": "core",
                "tasks": [f"{feature.upper()[:4]}-L2-001"],
                "parallel": True,
                "estimated_minutes": 30,
                "depends_on_levels": [1],
            },
            "3": {
                "name": "integration",
                "tasks": [f"{feature.upper()[:4]}-L3-001"],
                "parallel": True,
                "estimated_minutes": 20,
                "depends_on_levels": [2],
            },
            "4": {
                "name": "testing",
                "tasks": [f"{feature.upper()[:4]}-L4-001"],
                "parallel": True,
                "estimated_minutes": 30,
                "depends_on_levels": [3],
            },
            "5": {
                "name": "quality",
                "tasks": [f"{feature.upper()[:4]}-L5-001"],
                "parallel": False,
                "estimated_minutes": 15,
                "depends_on_levels": [4],
            },
        },
    }

    # Generate steps for each task if detail level is medium or high
    if detail_level in ("medium", "high"):
        step_generator = StepGenerator(project_root=path.parent.parent.parent)
        for task in task_graph["tasks"]:
            steps = step_generator.generate_steps_dict(task, detail_level=detail_level)
            if steps:
                task["steps"] = steps
        # Update metadata to reflect step generation
        task_graph["detail_level"] = detail_level
        step_count = sum(len(t.get("steps", [])) for t in task_graph["tasks"])
        console.print(f"  [dim]Generated {step_count} steps across {len(task_graph['tasks'])} tasks[/dim]")

    with open(path, "w") as f:
        json.dump(task_graph, f, indent=2)


def validate_task_graph(path: Path, detail_level: str = "standard") -> None:
    """Validate a task graph file.

    Args:
        path: Path to task-graph.json
        detail_level: Expected detail level (standard/medium/high).
                     When medium/high, validates step structure.
    """
    console.print(f"[bold]Validating {path}[/bold]\n")

    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        console.print(f"[red]Error:[/red] Invalid JSON: {e}")
        raise SystemExit(1) from e

    errors = []
    warnings = []

    # Check required fields
    required = ["tasks"]
    for field in required:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if errors:
        for error in errors:
            console.print(f"[red]✗[/red] {error}")
        raise SystemExit(1)

    tasks = data.get("tasks", [])
    task_ids = {t.get("id") for t in tasks}

    # Validate each task
    for task in tasks:
        task_id = task.get("id", "unknown")

        # Check required task fields
        task_required = ["id", "title", "level", "dependencies", "files"]
        for field in task_required:
            if field not in task:
                errors.append(f"Task {task_id}: missing '{field}'")

        # Check dependencies exist
        for dep in task.get("dependencies", []):
            if dep not in task_ids:
                errors.append(f"Task {task_id}: unknown dependency '{dep}'")

        # Check for circular dependencies
        if task_id in task.get("dependencies", []):
            errors.append(f"Task {task_id}: self-reference in dependencies")

        # Check files structure
        files = task.get("files", {})
        for file_type in ["create", "modify", "read"]:
            if file_type not in files:
                warnings.append(f"Task {task_id}: missing files.{file_type}")

        # Validate steps structure if detail level is medium/high
        if detail_level in ("medium", "high"):
            steps = task.get("steps", [])
            if not steps:
                warnings.append(f"Task {task_id}: expected steps for detail level '{detail_level}'")
            else:
                # Validate step structure
                valid_actions = {"write_test", "verify_fail", "implement", "verify_pass", "format", "commit"}
                valid_verify = {"exit_code", "exit_code_nonzero", "none"}
                for step in steps:
                    step_num = step.get("step", "?")
                    if "action" not in step:
                        errors.append(f"Task {task_id}, step {step_num}: missing 'action'")
                    elif step["action"] not in valid_actions:
                        errors.append(f"Task {task_id}, step {step_num}: invalid action '{step['action']}'")
                    if "verify" not in step:
                        errors.append(f"Task {task_id}, step {step_num}: missing 'verify'")
                    elif step["verify"] not in valid_verify:
                        errors.append(f"Task {task_id}, step {step_num}: invalid verify '{step['verify']}'")

    # Check file ownership conflicts
    file_owners: dict[tuple[Any, ...], Any] = {}
    for task in tasks:
        task_id = task.get("id")
        level = task.get("level", 0)

        for file in task.get("files", {}).get("create", []):
            key = (file, "create")
            if key in file_owners:
                owner = file_owners[key]
                errors.append(f"File conflict: {file} created by both {owner} and {task_id}")
            file_owners[key] = task_id

        for file in task.get("files", {}).get("modify", []):
            key = (file, "modify", level)  # type: ignore[assignment]
            if key in file_owners:
                owner = file_owners[key]
                msg = f"File conflict: {file} modified by {owner} and {task_id} at L{level}"
                errors.append(msg)
            file_owners[key] = task_id

    # Check for mandatory L5 final analysis task
    l5_tasks = [t for t in tasks if t.get("level") == 5]
    has_analysis = any(
        "analysis" in t.get("title", "").lower() or "quality" in t.get("title", "").lower() for t in l5_tasks
    )
    if not has_analysis:
        warnings.append("Missing mandatory L5 final analysis task (must include 'analysis' or 'quality' in title)")

    # Report results
    if errors:
        console.print("\n[red]Validation Failed[/red]\n")
        for error in errors:
            console.print(f"  [red]✗[/red] {error}")
        raise SystemExit(1)

    if warnings:
        console.print("\n[yellow]Warnings[/yellow]\n")
        for warning in warnings:
            console.print(f"  [yellow]![/yellow] {warning}")

    console.print("\n[green]✓[/green] Task graph is valid!")
    console.print(f"  Tasks: {len(tasks)}")
    console.print(f"  Levels: {len(data.get('levels', {}))}")

    # Show summary table
    table = Table(title="Task Summary")
    table.add_column("Level", style="cyan")
    table.add_column("Tasks", justify="right")
    table.add_column("Est. Time", justify="right")

    levels = data.get("levels", {})
    for level_num in sorted(levels.keys(), key=int):
        level = levels[level_num]
        table.add_row(
            f"L{level_num}: {level.get('name', '')}",
            str(len(level.get("tasks", []))),
            f"{level.get('estimated_minutes', '?')}m",
        )

    console.print()
    console.print(table)


def show_design_summary(spec_dir: Path, feature: str, detail_level: str = "standard") -> None:
    """Show design summary.

    Args:
        spec_dir: Spec directory
        feature: Feature name
        detail_level: Detail level used for step generation
    """
    console.print("\n[bold]Design Summary[/bold]\n")

    table = Table(show_header=False)
    table.add_column("Item", style="cyan")
    table.add_column("Value")

    table.add_row("Feature", feature)
    table.add_row("Spec Directory", str(spec_dir))
    table.add_row("Requirements", str(spec_dir / "requirements.md"))
    table.add_row("Design", str(spec_dir / "design.md"))
    table.add_row("Task Graph", str(spec_dir / "task-graph.json"))

    # Show detail level with description
    detail_desc = {
        "standard": "standard (no steps - classic mode)",
        "medium": "medium (TDD steps)",
        "high": "high (TDD steps with code snippets)",
    }
    table.add_row("Detail Level", detail_desc.get(detail_level, detail_level))

    console.print(table)


def _load_task_graph(path: Path) -> dict[str, Any]:
    """Load task graph JSON data."""
    import json

    with open(path) as f:
        result: dict[str, Any] = json.load(f)
        return result


def _build_design_manifest(feature: str, task_data: dict[str, Any]) -> dict[str, Any]:
    """Build a design task manifest from task graph data.

    Pure data transformer — no file I/O. Converts task-graph entries into
    a manifest format that mirrors Claude Task fields (subject, description,
    active_form, dependencies).

    Args:
        feature: Feature name.
        task_data: Parsed task-graph.json data containing a 'tasks' list.

    Returns:
        Dict with 'feature', 'generated' (ISO timestamp), and 'tasks' list.
    """
    manifest_tasks: list[dict[str, Any]] = []

    for task in task_data.get("tasks", []):
        level = task.get("level", 0)
        title = task.get("title", "Untitled")

        # Build file ownership summary
        files = task.get("files", {})
        ownership_parts: list[str] = []
        for op in ("create", "modify", "read"):
            file_list = files.get(op, [])
            if file_list:
                ownership_parts.append(f"{op}: {', '.join(file_list)}")
        file_summary = "Files — " + "; ".join(ownership_parts) if ownership_parts else ""

        # Build description from task description + file ownership + verification
        desc_parts: list[str] = []
        task_desc = task.get("description", "")
        if task_desc:
            desc_parts.append(task_desc)
        if file_summary:
            desc_parts.append(file_summary)
        verification = task.get("verification", {})
        verify_cmd = verification.get("command", "")
        if verify_cmd:
            desc_parts.append(f"Verify: {verify_cmd}")

        entry: dict[str, Any] = {
            "subject": f"[L{level}] {title}",
            "description": "\n".join(desc_parts),
            "active_form": f"Executing {title}",
            "dependencies": list(task.get("dependencies", [])),
        }
        manifest_tasks.append(entry)

    return {
        "feature": feature,
        "generated": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tasks": manifest_tasks,
    }
