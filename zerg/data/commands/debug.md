
# ZERG Debug: $ARGUMENTS

Deep diagnostic investigation for ZERG execution issues with error intelligence, log correlation, Bayesian hypothesis testing, code-aware recovery, and environment diagnostics.

## Flags

- `--feature <name>` or `-f`: Feature to investigate (auto-detected if omitted)
- `--worker <id>` or `-w`: Focus on specific worker
- `--deep`: Run system-level diagnostics (git, disk, docker, ports, worktrees)
- `--fix`: Generate and execute recovery plan (with confirmation)
- `--error <msg>` or `-e`: Specific error message to analyze
- `--stacktrace <path>` or `-s`: Path to stack trace file
- `--env`: Run comprehensive environment diagnostics (Python venv, packages, Docker, resources, config validation)
- `--interactive` or `-i`: Interactive debugging wizard mode (placeholder for guided step-by-step diagnosis)
- `--report <path>`: Write full diagnostic markdown report to file at the specified path

## Pre-Flight

```
FEATURE="$ARGUMENTS"

# If no explicit feature, detect from state
if [ -z "$FEATURE" ]; then
  # Check .gsd/.current-feature
  if [ -f ".gsd/.current-feature" ]; then
    FEATURE=$(cat .gsd/.current-feature)
  fi
fi

# Verify .zerg/ directory exists
if [ ! -d ".zerg" ]; then
  echo "WARNING: No .zerg/ directory found. Limited diagnostics available."
fi

# If $ARGUMENTS is plain text (not a flag), treat as problem description
# e.g., /zerg:debug workers keep crashing
```

Detect active feature from `.gsd/.current-feature` or `--feature` flag.
If `$ARGUMENTS` contains no flags, treat entire string as problem description.

---

## Workflow Overview

Execute phases sequentially. See `debug.details.md` for full templates, evidence checklists, and examples.

1. **Phase 1: Context Gathering** — Read ZERG state, logs, task-graph, design doc, and git state in parallel. Output a CONTEXT SNAPSHOT.
2. **Phase 1.5: Error Intelligence** — Multi-language error parsing, fingerprinting, chain analysis, semantic classification.
3. **Phase 2: Symptom Classification** — Classify into ONE category: `WORKER_FAILURE`, `TASK_FAILURE`, `STATE_CORRUPTION`, `INFRASTRUCTURE`, `CODE_ERROR`, `DEPENDENCY`, `MERGE_CONFLICT`, or `UNKNOWN`.
4. **Phase 2.5: Log Correlation** — Timeline reconstruction, temporal clustering, cross-worker correlation, error evolution tracking.
5. **Phase 3: Evidence Collection** — Category-specific evidence checklists (see details file).
6. **Phase 4: Hypothesis Testing** — Bayesian probability scoring with max 3 hypotheses, automated test commands.
7. **Phase 5: Root Cause Determination** — Synthesize findings into root cause statement with confidence level.
8. **Phase 6: Recovery Plan** — Code-aware fix suggestions with risk levels (`[SAFE]`, `[MODERATE]`, `[DESTRUCTIVE]`). If `--fix`, execute with per-step confirmation.
9. **Phase 6.5: Design Escalation Check** — If issues require architectural changes, recommend `/zerg:design`.
10. **Phase 7: Report & Integration** — Save report to `claudedocs/debug-<timestamp>.md` (or `--report <path>`).
11. **Phase 7.5: Environment Diagnostics** — When `--env` is set, run Python, Docker, system resources, and config validation checks.

---

## Task Tracking

On invocation, create a Claude Code Task to track this command:

Call TaskCreate:
  - subject: "[Debug] Diagnose {category}" (append " → DESIGN ESCALATION" if design escalation detected)
  - description: "Debugging {feature}. Problem: {arguments_or_description}. Design escalation: {yes/no — reason}."
  - activeForm: "Debugging {feature}"

Immediately call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "in_progress"

On completion (after report is saved), call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "completed"

## Output Format

Always output findings using the structured templates in the details file.
Be specific: include file paths, line numbers, task IDs, worker IDs.
Quantify: "3 of 12 tasks failed" not "some tasks failed".
Prioritize: address the root cause, not symptoms.

## Help

When `--help` is passed in `$ARGUMENTS`, display usage and exit:

```
/zerg:debug — Deep diagnostic investigation for ZERG execution issues.

Flags:
  -f, --feature <name>
                      Feature to investigate (auto-detected if omitted)
  -w, --worker <id>   Focus on specific worker
  --deep              Run system-level diagnostics
  --fix               Generate and execute recovery plan (with confirmation)
  -e, --error <msg>   Specific error message to analyze
  -s, --stacktrace <path>
                      Path to stack trace file
  --env               Run comprehensive environment diagnostics
  -i, --interactive   Interactive debugging wizard mode
  --report <path>     Write full diagnostic markdown report to file
  --help              Show this help message
```
