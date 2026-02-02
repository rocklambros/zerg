# /zerg:debug

Deep diagnostic investigation for ZERG execution issues with error intelligence, log correlation, hypothesis testing, and code-aware recovery.

## Synopsis

```
/zerg:debug [PROBLEM_DESCRIPTION]
            [--feature <name>] [-f <name>]
            [--worker <id>] [-w <id>]
            [--deep]
            [--fix]
            [--error <msg>] [-e <msg>]
            [--stacktrace <path>] [-s <path>]
            [--env]
            [--interactive] [-i]
            [--report <path>]
```

## Description

The `debug` command performs systematic diagnosis of ZERG execution failures. It follows a multi-phase investigation pipeline that gathers context, classifies symptoms, collects evidence, tests hypotheses using Bayesian probability scoring, determines root causes, and generates recovery plans.

If `PROBLEM_DESCRIPTION` is provided as plain text (without flags), it is treated as a free-form description of the problem to investigate.

### Investigation Phases

1. **Context Gathering** -- Read ZERG state, logs, task graph, design documents, and git state in parallel.
2. **Error Intelligence** -- Multi-language error parsing, fingerprinting, chain analysis, and semantic classification.
3. **Symptom Classification** -- Classify into one category: `WORKER_FAILURE`, `TASK_FAILURE`, `STATE_CORRUPTION`, `INFRASTRUCTURE`, `CODE_ERROR`, `DEPENDENCY`, `MERGE_CONFLICT`, or `UNKNOWN`.
4. **Log Correlation** -- Timeline reconstruction, temporal clustering, cross-worker correlation, and error evolution tracking.
5. **Evidence Collection** -- Category-specific evidence checklists.
6. **Hypothesis Testing** -- Bayesian probability scoring with a maximum of 3 hypotheses and automated test commands.
7. **Root Cause Determination** -- Synthesize findings into a root cause statement with a confidence level.
8. **Recovery Plan** -- Code-aware fix suggestions with risk levels: `[SAFE]`, `[MODERATE]`, or `[DESTRUCTIVE]`. When `--fix` is used, each step requires confirmation before execution.
9. **Design Escalation Check** -- If issues require architectural changes, recommend running `/zerg:design`.
10. **Report** -- Save a diagnostic report to `claudedocs/debug-<timestamp>.md` or the path specified by `--report`.
11. **Environment Diagnostics** -- When `--env` is set, run Python, Docker, system resource, and config validation checks.

### Feature Detection

If `--feature` is not provided, the command auto-detects the active feature from `.gsd/.current-feature`.

## Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--feature` | `-f` | auto-detected | Feature name to investigate. |
| `--worker` | `-w` | all | Focus investigation on a specific worker ID. |
| `--deep` | -- | off | Run system-level diagnostics including git, disk, Docker, ports, and worktrees. |
| `--fix` | -- | off | Generate and execute a recovery plan with per-step confirmation. |
| `--error` | `-e` | -- | A specific error message to analyze. |
| `--stacktrace` | `-s` | -- | Path to a stack trace file to include in analysis. |
| `--env` | -- | off | Run comprehensive environment diagnostics (Python venv, packages, Docker, resources, config validation). |
| `--interactive` | `-i` | off | Interactive debugging wizard mode for guided step-by-step diagnosis. |
| `--report` | -- | `claudedocs/debug-<timestamp>.md` | Write the full diagnostic report to the specified path. |

## Examples

Investigate a general problem described in plain text:

```
/zerg:debug workers keep crashing
```

Debug a specific feature:

```
/zerg:debug --feature user-auth
```

Focus on a single worker:

```
/zerg:debug --worker 3
```

Run deep system-level diagnostics:

```
/zerg:debug --deep
```

Diagnose and attempt recovery:

```
/zerg:debug --fix
```

Analyze a specific error message:

```
/zerg:debug --error "ModuleNotFoundError: No module named 'zerg.launcher'"
```

Run environment diagnostics:

```
/zerg:debug --env
```

Save the report to a custom path:

```
/zerg:debug --report claudedocs/auth-debug.md
```

## Symptom Categories

| Category | Description |
|----------|-------------|
| `WORKER_FAILURE` | Worker process crashed or exited unexpectedly. |
| `TASK_FAILURE` | Task verification command failed. |
| `STATE_CORRUPTION` | Inconsistency between task system and state JSON. |
| `INFRASTRUCTURE` | Docker, port, disk, or network issues. |
| `CODE_ERROR` | Syntax, import, or runtime errors in generated code. |
| `DEPENDENCY` | Missing or incompatible dependency. |
| `MERGE_CONFLICT` | Git merge conflicts between worker branches. |
| `UNKNOWN` | Cannot classify; requires manual investigation. |

## Recovery Risk Levels

| Level | Meaning |
|-------|---------|
| `[SAFE]` | No risk of data loss. Can be applied without concern. |
| `[MODERATE]` | Some risk. Review the suggested change before applying. |
| `[DESTRUCTIVE]` | Potential data loss. Requires explicit confirmation and a backup. |

## Task Tracking

This command creates a Claude Code Task with the subject prefix `[Debug]` on invocation. If a design escalation is detected, the suffix `DESIGN ESCALATION` is appended to the task subject. The task is updated to `in_progress` immediately and marked `completed` after the report is saved.

## See Also

- [[zerg-worker]] -- Worker execution protocol and failure handling
- [[zerg-plugins]] -- Plugin system for custom quality gates and hooks
- [[zerg-build]] -- Rebuild after applying fixes
- [[zerg-test]] -- Re-run tests to verify fixes
