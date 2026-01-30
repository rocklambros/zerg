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
- `--interactive` or `-i`: Interactive troubleshooting wizard mode (placeholder for guided step-by-step diagnosis)
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

## Phase 1.5: Error Intelligence

After gathering context, run the error intelligence engine on all collected error text:

**Multi-Language Error Parsing**: Automatically detect and parse errors from Python, JavaScript/TypeScript, Go, Rust, Java, and C++. Each language has dedicated regex patterns for extracting file locations, line numbers, error types, and messages.

**Error Fingerprinting**: Each parsed error is hashed into an `ErrorFingerprint` containing:
- Error type and message
- File path and line number
- A stable hash for deduplication across workers and runs

**Error Chain Analysis**: Traverse "caused by" chains in stack traces to identify root errors vs. downstream effects. This is critical for multi-layer errors where the surface exception hides the real cause.

**Semantic Classification**: Every error is classified into an `ErrorCategory` (e.g., `IMPORT_ERROR`, `SYNTAX_ERROR`, `RUNTIME_ERROR`, `TIMEOUT`, `INFRASTRUCTURE`) and assigned an `ErrorSeverity` (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) to prioritize investigation.

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

## Phase 2.5: Log Correlation

After classification, correlate logs across workers:

**Timeline Reconstruction**: Parse timestamps from all worker logs (ISO 8601, epoch, and relative formats) and build a unified timeline of events across workers. Events are sorted chronologically to reveal execution ordering.

**Temporal Clustering**: Group events that occur within a configurable time window into clusters. Simultaneous errors across multiple workers often indicate a shared root cause (e.g., infrastructure failure) rather than independent bugs.

**Cross-Worker Error Correlation**: Compare error messages across workers using Jaccard similarity on tokenized text. Workers producing similar errors (similarity > 0.6) are flagged as likely sharing the same underlying problem.

**Error Evolution Tracking**: Track how errors evolve over time within and across workers. Identifies trending patterns -- errors that are increasing in frequency signal a worsening condition, while decreasing errors suggest partial self-recovery.

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

For each hypothesis (max 3), the engine uses **Bayesian probability scoring**:

- **Prior probabilities** are drawn from a knowledge base of 30+ known failure patterns spanning Python, JavaScript, Go, Rust, Docker, Git, and ZERG-specific issues. Each pattern carries a calibrated prior probability.
- **Posterior calculation**: `posterior = prior * product((1 + confidence * 0.5) for supporting evidence) * product((1 - confidence * 0.5) for contradicting evidence)`, clamped to [0.01, 0.99].
- **Hypothesis chaining**: When a hypothesis is confirmed, its result adjusts the priors of related hypotheses (e.g., confirming "missing package" boosts "import error" and reduces "syntax error").
- **Automated testing**: Each hypothesis has a test command that is executed with safety gates (read-only or easily reversible commands only). Results are captured and parsed automatically.

```
HYPOTHESIS <N>: <description>
─────────────────────────────
Prior:       <probability from knowledge base>
Posterior:   <updated probability after evidence>

Evidence FOR:
  - <supporting evidence> (confidence: <0-1>)
  - <supporting evidence> (confidence: <0-1>)

Evidence AGAINST:
  - <contradicting evidence> (confidence: <0-1>)

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

Generate executable recovery steps with **code-aware fix suggestions**:

- **Dependency analysis**: For import/module errors, the engine traces the full import chain using AST parsing, identifies missing dependencies, and suggests exact `pip install` commands.
- **Git context**: Uses `git blame` to identify who last changed error-causing lines and `git bisect` suggestions to pinpoint the commit that introduced the regression.
- **Import chain analysis**: For dependency errors, traces which files import the problematic module to assess blast radius and suggest targeted fixes.
- **Fix templates**: Known patterns from the knowledge base include templated fix commands that are populated with error-specific details (file paths, module names, line numbers).

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

Write diagnostic report to `claudedocs/debug-<timestamp>.md` (or to `--report <path>` if specified):

```markdown
# Debug Report: <feature>
Date: <ISO timestamp>
Feature: <feature>
Category: <classification>

## Context
<context snapshot from Phase 1>

## Error Intelligence
<parsed errors, fingerprints, and chain analysis from Phase 1.5>

## Classification
<from Phase 2>

## Log Correlation
<timeline, clusters, and cross-worker analysis from Phase 2.5>

## Evidence
<collected evidence from Phase 3>

## Hypotheses
<Bayesian-scored hypothesis testing results from Phase 4>

## Root Cause
<from Phase 5>

## Recovery
<code-aware plan from Phase 6>

## Environment
<environment diagnostics from Phase 7.5, if --env was used>

## Status
<what was done, what remains>
```

### Create Claude Task

Create a Claude Task summarizing the diagnosis:

```
Subject: "Debug: <root cause summary>"
Description: "<category> - <root cause> - <recommendation>"
```

---

## Phase 7.5: Environment Diagnostics

When `--env` flag is set (or when infrastructure issues are suspected), run comprehensive environment checks:

**Python Environment**:
- Virtual environment status (active, path, Python version, executable)
- Installed packages inventory with version numbers
- Verify required packages are present (cross-reference with pyproject.toml)
- Test critical imports succeed at runtime

**Docker Health**:
- Docker daemon reachability (`docker info`)
- Running containers count and status
- Available images relevant to ZERG
- Docker resource allocation (memory, CPU limits)

**System Resources**:
- CPU usage and load averages
- Memory utilization (total, available, percent used)
- Disk space on project partition
- Open file descriptor count vs. system limits

**Configuration Validation**:
- Parse and validate `.zerg/config.yaml` against expected schema
- Check for missing required fields
- Validate numeric ranges (worker counts, timeouts, port ranges)
- Flag deprecated or unrecognized configuration keys

Output:

```
ENVIRONMENT DIAGNOSTICS
=======================
Python:
  venv active:    <yes|no>
  Python version: <version>
  Packages:       <N> installed, <N> missing
  Critical:       <all OK | list issues>

Docker:
  Daemon:         <running|stopped|not installed>
  Containers:     <N> running
  Images:         <N> available

Resources:
  CPU:            <usage%>
  Memory:         <used>/<total> (<percent>%)
  Disk:           <used>/<total> (<percent>%)
  File descriptors: <open>/<limit>

Config:
  Valid:          <yes|no>
  Issues:         <list of issues or "none">
```

---

## Quick Reference

### Common Issues & Fast Paths

**Workers not starting:**
1. Check `.zerg/config.yaml` exists
2. Check `ANTHROPIC_API_KEY` is set
3. Check port availability
4. Check disk space
5. Run `--env` to check Docker daemon and system resources

**Tasks failing verification:**
1. Read task verification command from task-graph
2. Run verification manually
3. Check task's owned files exist
4. Check worker log for task execution
5. Use error intelligence to parse multi-language stack traces

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

**Cross-worker failures:**
1. Run log correlation to build unified timeline
2. Check temporal clusters for simultaneous errors
3. Use Jaccard similarity to find workers with same root cause
4. Track error evolution to identify worsening trends

**Dependency / import errors:**
1. Run `--env` to check venv and packages
2. Error intelligence parses import chains automatically
3. Code fixer suggests exact `pip install` commands
4. Import chain analysis shows blast radius

**Unknown errors:**
1. Run with `--deep --env` for full system and environment scan
2. Error intelligence auto-detects language and parses stack traces
3. Bayesian hypothesis engine ranks possible causes by probability
4. Use `--report diag.md` to capture full diagnostic output for review

---

## Task Tracking

On invocation, create a Claude Code Task to track this command:

Call TaskCreate:
  - subject: "[Debug] Diagnose {category}"
  - description: "Debuging {feature}. Problem: {arguments_or_description}."
  - activeForm: "Debuging {feature}"

Immediately call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "in_progress"

On completion (after report is saved), call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "completed"

## Output Format

Always output findings using the structured templates above.
Be specific: include file paths, line numbers, task IDs, worker IDs.
Quantify: "3 of 12 tasks failed" not "some tasks failed".
Prioritize: address the root cause, not symptoms.
