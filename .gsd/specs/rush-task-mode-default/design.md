# Technical Design: rush-task-mode-default

## Metadata
- **Feature**: rush-task-mode-default
- **Status**: IMPLEMENTED
- **Created**: 2026-02-04
- **Author**: ZERG Design Mode

---

## 1. Overview

### 1.1 Summary

Restructure `rush.core.md` and `rush.md` to make Task Tool Mode the default execution path when `/zerg:rush` is invoked as a slash command. Container and subprocess modes become conditional paths triggered only by explicit `--mode` flags.

### 1.2 Goals
- Task Tool Mode executes by default (no flags needed)
- Container/subprocess modes remain available via explicit `--mode`
- Level execution loop is complete and actionable
- Resume support works in Task Tool Mode
- Documentation is clear and consistent

### 1.3 Non-Goals
- Changes to Python CLI (`zerg/commands/rush.py`)
- Changes to Orchestrator (`zerg/orchestrator.py`)
- Changes to launcher infrastructure
- New Python code

---

## 2. Architecture

### 2.1 High-Level Design

```
┌──────────────────────────────────────────────────────────────┐
│                     /zerg:rush invoked                       │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                    Mode Detection                            │
│  IF --mode container → CONTAINER_MODE                        │
│  IF --mode subprocess → SUBPROCESS_MODE                      │
│  ELSE → TASK_MODE (default)                                  │
└──────────────────────────────────────────────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           ▼                  ▼                  ▼
    ┌─────────────┐   ┌─────────────┐   ┌──────────────┐
    │ TASK_MODE   │   │CONTAINER_   │   │ SUBPROCESS_  │
    │ (Default)   │   │ MODE        │   │ MODE         │
    └─────────────┘   └─────────────┘   └──────────────┘
           │                  │                  │
           ▼                  └────────┬─────────┘
    ┌─────────────┐                    ▼
    │ Level Loop  │            ┌──────────────┐
    │ via Task    │            │ Python       │
    │ tool calls  │            │ Orchestrator │
    └─────────────┘            └──────────────┘
           │
           ▼
    ┌─────────────────────────────────────────────────────────┐
    │ FOR each level:                                         │
    │   1. Collect tasks at level                             │
    │   2. Batch by WORKERS count                             │
    │   3. Launch parallel Task tool calls                    │
    │   4. Wait for all to return                             │
    │   5. Handle failures (retry once)                       │
    │   6. Run quality gates                                  │
    │   7. Proceed to next level                              │
    └─────────────────────────────────────────────────────────┘
```

### 2.2 Component Breakdown

| Component | Responsibility | Files |
|-----------|---------------|-------|
| Mode Detection | Parse $ARGUMENTS, determine execution mode | `rush.core.md` (new Step 1) |
| Task Tool Loop | Execute tasks via parallel Task tool calls | `rush.core.md` (new Step 2-6) |
| Subagent Prompt | Template for each Task tool invocation | `rush.core.md` (references details) |
| Container Fallback | Invoke Python Orchestrator when explicit | `rush.core.md` (conditional section) |
| Subprocess Fallback | Same as container but subprocess mode | `rush.core.md` (conditional section) |

### 2.3 Data Flow

**Task Tool Mode:**
```
task-graph.json → Parse levels → FOR each level:
  → Batch tasks → Launch Task tools (parallel)
  → Wait for returns → Record results
  → Handle failures → Run quality gates
  → Next level
```

**Container/Subprocess Mode:**
```
$ARGUMENTS → Detect --mode → Invoke Python:
  from zerg.orchestrator import Orchestrator
  orch = Orchestrator(feature=FEATURE, launcher_mode=MODE)
  orch.start(...)
```

---

## 3. Detailed Design

### 3.1 File Structure Changes

```
zerg/data/commands/
├── rush.md           # MODIFY: Add mode detection, Task Tool as default
├── rush.core.md      # MODIFY: Restructure completely
└── rush.details.md   # NO CHANGE: Already documents Task Tool Mode correctly
```

### 3.2 rush.core.md New Structure

```markdown
# ZERG Launch (Core)

## Pre-Flight
[Keep existing: FEATURE, TASK_LIST, SPEC_DIR validation]

## Step 1: Mode Detection (NEW)
Parse $ARGUMENTS for --mode flag:
- "--mode container" → MODE=container
- "--mode subprocess" → MODE=subprocess
- Otherwise → MODE=task (DEFAULT)

## Step 2: Task Tool Mode (Default Path)
IF MODE == "task":
  [Level Execution Loop - pulled from rush.details.md]

## Step 3: Container/Subprocess Mode (Conditional)
IF MODE == "container" OR MODE == "subprocess":
  [Existing Steps 2-6 moved here, gated]
```

### 3.3 Mode Detection Logic

```
# Step 1: Mode Detection

MODE="task"  # Default

IF $ARGUMENTS contains "--mode container":
  MODE="container"
ELSE IF $ARGUMENTS contains "--mode subprocess":
  MODE="subprocess"
ELSE IF $ARGUMENTS contains "--mode task":
  MODE="task"
# No flag = task mode (default)
```

### 3.4 Task Tool Level Execution Loop

```markdown
## Step 2: Task Tool Mode (Default)

IF MODE == "task":

### 2.1: Register Tasks in Claude Task System

FOR each task in task-graph.json:
  Call TaskCreate:
    - subject: "[L{level}] {title}"
    - description: Full task details
    - activeForm: "Executing {title}"

Wire dependencies via TaskUpdate(addBlockedBy).

### 2.2: Level Execution Loop

FOR each level in task-graph.json (ascending order):

  1. Collect all tasks at this level
  2. IF tasks > WORKERS: split into batches of WORKERS
     ELSE: single batch = all tasks

  3. FOR each batch:
     - Mark tasks in_progress via TaskUpdate
     - Launch all tasks as parallel Task tool calls:

       Task(
         description: "Execute TASK-{id}",
         subagent_type: "general-purpose",
         prompt: [Subagent prompt template from rush.details.md:263-301]
       )

     - Wait for all to return
     - Record results (pass/fail) per task
     - Update Task statuses (completed/failed)

  4. Handle failures:
     - Retry each failed task ONCE (with error context)
     - If retry fails: mark blocked, warn, continue
     - If ALL tasks fail: ABORT

  5. Run quality gates:
     ```bash
     make lint && make typecheck
     ```
     If gates fail: ABORT with diagnostics

  6. Proceed to next level

END FOR

### 2.3: Completion

Print summary:
- Total tasks completed
- Any blocked tasks
- Time elapsed
```

### 3.5 Container/Subprocess Conditional Section

```markdown
## Step 3: Container/Subprocess Mode (Explicit Only)

IF MODE == "container" OR MODE == "subprocess":

> This mode requires explicit --mode flag.

### 3.1: Create Worker Branches
[Existing Step 2 content]

### 3.2: Partition Tasks
[Existing Step 3 content]

### 3.3: Create Native Tasks
[Existing Step 4 content]

### 3.4: Launch Workers

IF MODE == "container":
  [Existing Step 5: Docker containers]
ELSE IF MODE == "subprocess":
  ```python
  from zerg.orchestrator import Orchestrator
  orch = Orchestrator(feature=FEATURE, launcher_mode="subprocess")
  orch.start(task_graph_path=SPEC_DIR/task-graph.json, worker_count=WORKERS)
  ```

### 3.5: Start Orchestrator
[Existing Step 6 content]

END IF
```

---

## 4. Key Decisions

### 4.1 Task Tool Mode as Default

**Context**: Currently, `/zerg:rush` without flags delegates to Python CLI which auto-detects subprocess mode. Users expect Task Tool Mode when using slash commands.

**Options Considered**:
1. **Change Python CLI default**: Modify `zerg/commands/rush.py` to default to task mode
   - Pros: Single source of truth
   - Cons: Out of scope, requires Python changes, CLI behavior differs from slash command
2. **Make skill file authoritative**: Restructure rush.core.md to use Task Tool Mode by default
   - Pros: In scope, slash command controls its own behavior, no Python changes
   - Cons: Documentation-only change, CLI still defaults to subprocess
3. **Remove Task Tool Mode**: Only support container/subprocess
   - Pros: Simpler
   - Cons: Loses native parallel execution, worse UX for slash commands

**Decision**: Option 2 - Make skill file authoritative

**Rationale**: The slash command should control its own behavior. Task Tool Mode is the natural execution model for slash commands (parallel Task tool calls). CLI users who want container/subprocess mode can use explicit flags.

**Consequences**:
- `/zerg:rush` (slash command) defaults to Task Tool Mode
- `zerg rush` (CLI) still defaults to auto-detect (subprocess) unless explicitly changed later
- Documentation clearly explains the difference

### 4.2 Level Execution Loop Location

**Context**: The level execution loop is documented in rush.details.md but never referenced from rush.core.md.

**Options Considered**:
1. **Inline full loop in rush.core.md**: Copy all loop logic into core
   - Pros: Self-contained, no file jumping
   - Cons: Duplication, drift risk, bloats core file
2. **Reference rush.details.md**: Keep loop in details, reference from core
   - Pros: DRY, details file is already authoritative for Task Tool Mode
   - Cons: Requires reading two files
3. **Hybrid**: Put essential loop structure in core, reference details for templates
   - Pros: Core is actionable, details provides depth
   - Cons: Requires careful split

**Decision**: Option 3 - Hybrid approach

**Rationale**: Core file should be executable without constantly jumping to details. Put the loop structure and essential logic in core, reference details only for the subagent prompt template.

**Consequences**:
- rush.core.md contains complete execution logic
- rush.details.md remains the reference for templates and examples
- No duplication of the subagent prompt template

---

## 5. Implementation Plan

### 5.1 Phase Summary

| Phase | Tasks | Parallel | Est. Time |
|-------|-------|----------|-----------|
| Foundation | 1 | No | 15 min |
| Quality | 1 | No | 10 min |

### 5.2 File Ownership

| File | Task ID | Operation |
|------|---------|-----------|
| `zerg/data/commands/rush.core.md` | TASK-001 | modify |
| `zerg/data/commands/rush.md` | TASK-002 | modify |

### 5.3 Dependency Graph

```
TASK-001 (rush.core.md restructure)
    │
    ▼
TASK-002 (rush.md sync)
```

TASK-002 depends on TASK-001 because rush.md must match the restructured core.

---

## 6. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Existing workflows break | Low | Medium | Container/subprocess modes still work with explicit --mode |
| Documentation unclear | Low | Low | Clear mode detection section at top |
| Task Tool loop incomplete | Low | High | Loop already documented in rush.details.md, just needs wiring |

---

## 7. Testing Strategy

### 7.1 Manual Verification

1. `/zerg:rush` without flags → Task Tool Mode executes
2. `/zerg:rush --mode container` → Python Orchestrator invoked
3. `/zerg:rush --mode subprocess` → Python Orchestrator invoked
4. `/zerg:rush --mode task` → Task Tool Mode (explicit)
5. Resume works in Task Tool Mode

### 7.2 Acceptance Criteria Validation

From requirements.md:
- [x] AC1: `/zerg:rush` without flags → Task Tool Mode
- [x] AC2: `--mode container` → Orchestrator with container launcher
- [x] AC3: `--mode subprocess` → Orchestrator with subprocess launcher
- [x] AC4: Task Tool Mode completes multi-level task graph
- [x] AC5: Resume works in Task Tool Mode
- [x] AC6: Documentation matches implementation

---

## 8. Parallel Execution Notes

### 8.1 Safe Parallelization
- Level 1 has 1 task (rush.core.md restructure)
- Level 2 has 1 task (rush.md sync)
- Total: 2 tasks, sequential due to dependency

### 8.2 Recommended Workers
- Minimum: 1 worker
- Optimal: 1 worker (tasks are sequential)
- Maximum: 1 worker

### 8.3 Estimated Duration
- Single worker: ~25 minutes
- Sequential execution required

---

## 9. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Architecture | | | PENDING |
| Engineering | | | PENDING |
