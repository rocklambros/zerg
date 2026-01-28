# ZERG Troubleshoot: $ARGUMENTS

Deep diagnostic investigation for ZERG execution issues.

## Flags

- `--feature <name>` or `-f`: Feature to investigate (auto-detected if omitted)
- `--worker <id>` or `-w`: Focus on specific worker
- `--deep`: Run system-level diagnostics (git, disk, docker, ports, worktrees)
- `--fix`: Generate and execute recovery plan (with confirmation)
- `--error <msg>` or `-e`: Specific error message to analyze
- `--stacktrace <path>` or `-s`: Path to stack trace file

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
# e.g., /zerg:troubleshoot workers keep crashing
```

Detect active feature from `.gsd/.current-feature` or `--feature` flag.
If `$ARGUMENTS` contains no flags, treat entire string as problem description.

---

## Phase 1: Context Gathering

Read all available context in parallel:

**ZERG State** (read in parallel):
- `.zerg/state/<feature>.json` - Task states, worker states, errors
- `.zerg/logs/worker-*.stderr.log` - Last 50 lines from each worker
- `.gsd/specs/<feature>/task-graph.json` - Task definitions and dependencies
- `.gsd/specs/<feature>/design.md` - Architecture context

**Git State** (read in parallel):
- `git status --porcelain` - Working tree state
- `git log --oneline -5` - Recent commits
- `git worktree list` - Active worktrees

Output a CONTEXT SNAPSHOT:

```
CONTEXT SNAPSHOT
================
Feature:        <feature-name>
State File:     <exists|missing|corrupt>
Current Level:  <N>
Paused:         <yes|no>

Tasks:
  Total:        <N>
  Complete:     <N>
  Failed:       <N>
  In Progress:  <N>
  Pending:      <N>

Workers:
  <id>: <status> (task: <task-id>)
  ...

Recent Errors (deduped):
  1. <error summary>
  2. <error summary>

Git:
  Branch: <branch>
  Clean:  <yes|no>
  Worktrees: <N>
```

---

## Phase 2: Symptom Classification

Classify the problem into exactly ONE primary category:

| Category | Indicators |
|----------|-----------|
| `WORKER_FAILURE` | Worker crashed, stopped unexpectedly, timeout |
| `TASK_FAILURE` | Task verification failed, code error in task |
| `STATE_CORRUPTION` | JSON parse error, orphaned tasks, inconsistent state |
| `INFRASTRUCTURE` | Docker down, disk full, port conflict, worktree issue |
| `CODE_ERROR` | Import error, syntax error, runtime exception in generated code |
| `DEPENDENCY` | Missing package, version conflict, incompatible module |
| `MERGE_CONFLICT` | Git merge failure, file ownership violation |
| `UNKNOWN` | Cannot determine from available evidence |

Output:

```
CLASSIFICATION: <CATEGORY>
Confidence: <high|medium|low>
Basis: <1-2 sentence explanation>
```

---

## Phase 3: Evidence Collection

Gather category-specific evidence. Each category has a checklist:

### WORKER_FAILURE
- [ ] Read worker stderr log (last 100 lines)
- [ ] Check worker stdout log for last task output
- [ ] Check worktree exists: `.zerg/worktrees/worker-<id>/`
- [ ] Check worker branch: `git -C .zerg/worktrees/worker-<id> log -1`
- [ ] Check if worker process is still running
- [ ] Look for OOM, timeout, or signal-based termination

### TASK_FAILURE
- [ ] Read task definition from task-graph.json
- [ ] Read task's owned files (check if they exist)
- [ ] Run task's verification command manually
- [ ] Check task's error field in state
- [ ] Check retry count
- [ ] Read worker log around task execution time

### STATE_CORRUPTION
- [ ] Compare tasks in state vs tasks in task-graph
- [ ] Check for orphaned tasks (in state but not in graph)
- [ ] Check for missing tasks (in graph but not in state)
- [ ] Validate JSON structure of state file
- [ ] Check for .json.bak backup file
- [ ] Check file permissions on state directory

### INFRASTRUCTURE
- [ ] `docker info` - Docker daemon status
- [ ] `df -h .` - Disk space
- [ ] Check port range for conflicts (socket connect test)
- [ ] `git worktree list --porcelain` - Worktree health
- [ ] Check for orphaned worktrees (path doesn't exist)
- [ ] Check `.zerg/config.yaml` for misconfigurations

### CODE_ERROR
- [ ] Read the error file and line from stack trace
- [ ] `git blame` on the error location
- [ ] Check imports and dependencies
- [ ] Read surrounding code context (10 lines before/after)
- [ ] Check if file is in task's owned files list

### DEPENDENCY
- [ ] Read `pyproject.toml` / `requirements.txt`
- [ ] Check installed packages: `pip list | grep <module>`
- [ ] Check import chain from error
- [ ] Verify virtual environment is active

### MERGE_CONFLICT
- [ ] `git status` in affected worktree
- [ ] Check file ownership in task-graph.json
- [ ] Look for duplicate file ownership across tasks
- [ ] Check level merge state

---

## Phase 4: Hypothesis Testing

For each hypothesis (max 3):

```
HYPOTHESIS <N>: <description>
─────────────────────────────
Evidence FOR:
  - <supporting evidence>
  - <supporting evidence>

Evidence AGAINST:
  - <contradicting evidence>

Test:
  Command: <specific command to run>
  Expected: <what confirms this hypothesis>

Result: CONFIRMED | REJECTED | INCONCLUSIVE
```

Run each test command. Record actual output vs expected.
Mark hypothesis as CONFIRMED, REJECTED, or INCONCLUSIVE.

---

## Phase 5: Root Cause Determination

Synthesize findings into a clear root cause statement:

```
ROOT CAUSE ANALYSIS
===================
Problem:     <what went wrong>
Root Cause:  <why it went wrong>
Evidence:    <chain of evidence supporting this>
Confidence:  <percentage> (<high|medium|low>)
Category:    <from Phase 2 classification>
```

If confidence is LOW, list what additional information would help.

---

## Phase 6: Recovery Plan

Generate executable recovery steps:

```
RECOVERY PLAN
=============
Problem:    <summary>
Root Cause: <summary>

Steps:
  1. [SAFE] <description>
     $ <command>

  2. [MODERATE] <description>
     $ <command>

  3. [SAFE] <description>
     $ <command>

Verification:
  $ <command to verify recovery>

Prevention:
  <what to change to avoid recurrence>
```

Risk levels:
- `[SAFE]` - Read-only or easily reversible
- `[MODERATE]` - Writes data but can be undone
- `[DESTRUCTIVE]` - Cannot be undone, requires explicit confirmation

If `--fix` flag is set:
1. Present the plan to the user
2. Ask for confirmation before EACH step
3. Execute confirmed steps
4. Report results after each step
5. Run verification command at the end

---

## Phase 7: Report & Integration

### Save Report

Write diagnostic report to `claudedocs/troubleshoot-<timestamp>.md`:

```markdown
# Troubleshoot Report: <feature>
Date: <ISO timestamp>
Feature: <feature>
Category: <classification>

## Context
<context snapshot from Phase 1>

## Classification
<from Phase 2>

## Evidence
<collected evidence from Phase 3>

## Hypotheses
<hypothesis testing results from Phase 4>

## Root Cause
<from Phase 5>

## Recovery
<plan from Phase 6>

## Status
<what was done, what remains>
```

### Create Claude Task

Create a Claude Task summarizing the diagnosis:

```
Subject: "Troubleshoot: <root cause summary>"
Description: "<category> - <root cause> - <recommendation>"
```

---

## Quick Reference

### Common Issues & Fast Paths

**Workers not starting:**
1. Check `.zerg/config.yaml` exists
2. Check `ANTHROPIC_API_KEY` is set
3. Check port availability
4. Check disk space

**Tasks failing verification:**
1. Read task verification command from task-graph
2. Run verification manually
3. Check task's owned files exist
4. Check worker log for task execution

**State file corrupt:**
1. Check `.zerg/state/<feature>.json.bak`
2. Restore from backup
3. If no backup, rebuild from task-graph

**Merge conflicts:**
1. Check file ownership in task-graph
2. Look for duplicate file assignments
3. Check level merge state
4. Abort merge, fix ownership, retry

**Disk space issues:**
1. `git worktree prune`
2. Remove `.zerg/worktrees/*/`
3. Clean docker: `docker system prune -f`

---

## Output Format

Always output findings using the structured templates above.
Be specific: include file paths, line numbers, task IDs, worker IDs.
Quantify: "3 of 12 tasks failed" not "some tasks failed".
Prioritize: address the root cause, not symptoms.
