# Reference Tone

**Terse, table-driven documentation for quick lookup.**

Preserves the current `/zerg:document` default behavior. API signatures, parameter tables, return types. Minimal prose — just the facts.

## When to Use

- Experienced users who know the concepts and need quick reference
- API documentation for developers integrating with ZERG
- Configuration reference pages
- Changelog and release notes

## Style Guidelines

- Lead with a one-line summary, no more
- Use tables for parameters, options, return values, and enums
- Use inline code for all identifiers, paths, and values
- No analogies, no narrative, no diagrams unless structurally necessary
- Group by category (public API, internals, configuration)
- Alphabetize within groups when practical

## Required Sections

### Summary

One sentence. What it is, what it does.

### API Table

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|

### Return Value

Type and brief description.

### Examples

Minimal code showing primary usage. No explanation — the code speaks.

## Output Structure Template

```markdown
# {Component Title}

{One-sentence summary.}

## Public API

### `{function_name}({args}) -> {return_type}`

{One-line description.}

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `{param}` | `{type}` | `{default}` | {description} |

**Returns**: `{type}` — {description}

**Raises**: `{exception}` — {when}

### `{class_name}`

{One-line description.}

| Method | Signature | Description |
|--------|-----------|-------------|
| `{method}` | `({args}) -> {ret}` | {description} |

## Configuration

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `{key}` | `{type}` | `{default}` | {description} |

## Examples

```python
{minimal usage example}
```
```

## Example Output

```markdown
# zerg.launcher

Spawns and manages parallel Claude Code worker processes.

## Public API

### `Launcher(config: ZergConfig)`

Process manager for ZERG worker instances.

| Method | Signature | Description |
|--------|-----------|-------------|
| `spawn` | `(task: Task, mode: str) -> Worker` | Spawn a worker for a task |
| `stop` | `(worker_id: str) -> None` | Stop a running worker |
| `status` | `() -> list[WorkerStatus]` | Get status of all workers |

### `spawn(task, mode) -> Worker`

Spawn a single worker process.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `task` | `Task` | — | Task from task-graph.json |
| `mode` | `str` | `"task"` | Execution mode: task, subprocess, container |

**Returns**: `Worker` — Handle to the spawned worker process.

**Raises**: `LaunchError` — If worker fails to start.

## Examples

```python
from zerg.launcher import Launcher
launcher = Launcher(config)
worker = launcher.spawn(task, mode="subprocess")
```
```
