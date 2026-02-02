# /zerg:estimate

Full-lifecycle effort estimation with PERT confidence intervals, post-execution comparison, and historical calibration.

## Synopsis

```
/zerg:estimate [<feature>] [--pre] [--post] [--calibrate]
                           [--workers N]
                           [--format text|json|md]
                           [--verbose] [--history] [--no-calibration]
```

## Description

The `estimate` command provides effort estimation at every stage of the ZERG workflow. It operates in three modes depending on the current state of the feature or the flags provided.

### Pre-Execution Mode

Before `/zerg:rush` has been run, `estimate` analyzes the task graph and produces time and cost projections:

1. **Task complexity scoring** — Reads `task-graph.json` and scores each task by file count, dependency depth, and description complexity.
2. **PERT estimation** — Calculates optimistic, most likely, and pessimistic durations per task using weighted averages.
3. **Wall-clock projection** — Given `--workers N`, simulates parallel execution across levels to estimate total wall-clock time.
4. **API cost projection** — Estimates token usage and Anthropic API cost based on task complexity and historical averages.

### Post-Execution Mode

After tasks have completed, `estimate --post` compares actual execution data against the original estimates:

1. Reads worker logs and task completion timestamps.
2. Computes actual duration, token usage, and cost per task.
3. Generates a comparison table showing estimated vs actual values.
4. Calculates accuracy percentage and bias direction (over/under-estimate).

### Calibration Mode

`estimate --calibrate` analyzes historical estimation accuracy across all features:

1. Reads all estimate files from `.gsd/estimates/`.
2. Computes per-task-type bias factors (e.g., "test tasks are consistently underestimated by 30%").
3. Stores calibration data for automatic bias correction in future estimates.

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `<feature>` | auto-detect | Feature to estimate. Defaults to `.gsd/.current-feature`. |
| `--pre` | auto | Force pre-execution estimation mode. |
| `--post` | auto | Force post-execution comparison mode. |
| `--calibrate` | off | Show historical accuracy and compute bias factors. |
| `--workers N` | config default | Worker count for wall-clock projection. |
| `--format` | `text` | Output format: `text`, `json`, or `md`. |
| `--verbose` | off | Show per-task breakdown instead of level summaries. |
| `--history` | off | Show past estimates for this feature. |
| `--no-calibration` | off | Skip applying calibration bias to estimates. |

## Examples

Estimate effort before launching workers:

```
/zerg:estimate user-auth
```

Compare actual vs estimated after execution:

```
/zerg:estimate user-auth --post
```

View per-task breakdown:

```
/zerg:estimate --verbose
```

Calibrate based on all historical data:

```
/zerg:estimate --calibrate
```

Output as JSON for tooling:

```
/zerg:estimate --format json
```

## Error Handling

- If no task graph exists, the command reports an error and suggests running `/zerg:design` first.
- If `--post` is used before any tasks have completed, the command reports that no execution data is available.
- If `--calibrate` finds no historical data, it reports that at least one completed feature is required.

## Task Tracking

This command creates a Claude Code Task with the subject prefix `[Estimate]` on invocation, updates it to `in_progress` immediately, and marks it `completed` on success.

## See Also

- [[zerg-design]] -- Generates the task graph that estimate analyzes
- [[zerg-rush]] -- Execute tasks that estimate projects
- [[zerg-status]] -- Real-time progress during execution
