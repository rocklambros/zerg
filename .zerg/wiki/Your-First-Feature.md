# Your First Feature

This tutorial walks through building a health check endpoint for an existing Python/FastAPI project using ZERG. The example is intentionally small (5 tasks across 3 levels) so you can complete it quickly and understand the mechanics before tackling larger features.

**Time estimate:** 20 to 30 minutes.

**Prerequisites:**
- ZERG installed and project initialized (see [[Installation]])
- A Python project with FastAPI (or adapt the example to your stack)
- Familiarity with the [[Quick Start]] workflow

---

## Table of Contents

- [The Feature](#the-feature)
- [Phase 1: Plan the Feature](#phase-1-plan-the-feature)
- [Phase 2: Review the Design](#phase-2-review-the-design)
- [Phase 3: Launch the Rush](#phase-3-launch-the-rush)
- [Phase 4: Monitor and Merge](#phase-4-monitor-and-merge)
- [Phase 5: Integrate the Result](#phase-5-integrate-the-result)
- [What You Built](#what-you-built)
- [Tips for Your Next Feature](#tips-for-your-next-feature)

---

## The Feature

We will build a health check system with these requirements:

- A `GET /health` endpoint that returns the application's health status.
- The endpoint checks database connectivity and returns component-level status.
- A health check service that aggregates checks from multiple subsystems.
- Unit tests for the service and integration tests for the endpoint.

This is a good first feature because it touches multiple layers (types, service, route, tests) without being too large.

---

## Phase 1: Plan the Feature

Open Claude Code in your project directory and start the planning phase.

```
/zerg:plan health-check
```

ZERG will explore your codebase and ask questions. Here is an example interaction:

```
Planning: health-check

I've analyzed your project structure. A few questions:

1. Should the health check include database connectivity verification?
2. Do you need separate liveness and readiness probes (Kubernetes-style),
   or a single combined endpoint?
3. Should the endpoint be authenticated or public?
4. What response format do you prefer? (simple JSON, detailed component status)
```

**Your answers:**

```
1. Yes, check database connectivity.
2. Single combined endpoint is fine for now.
3. Public, no authentication required.
4. Detailed component status with overall status and per-component breakdown.
```

ZERG generates the requirements document and presents it for review.

```
Requirements generated: .gsd/specs/health-check/requirements.md

Summary:
- GET /health endpoint (public, no auth)
- Returns overall status + per-component status
- Checks: database connectivity
- Response format: { status, components: { db: { status, latency_ms } } }

Reply with "APPROVED" to proceed.
```

Review the requirements. If they look correct:

```
APPROVED
```

**Checkpoint.** At this point you should have:

```bash
ls .gsd/specs/health-check/
# requirements.md
```

---

## Phase 2: Review the Design

Generate the architecture and task graph.

```
/zerg:design
```

ZERG reads the requirements, analyzes your codebase for existing patterns, and produces a technical design. For this feature, expect something like:

```
DESIGN READY FOR REVIEW

Feature: health-check

Architecture:
  - 3 components: HealthStatus types, HealthService, health route
  - 1 key decision: Use dependency injection for check functions

Task Graph:
  - 5 total tasks across 3 levels
  - Max parallelization: 2 workers
  - Estimated duration: 45min (single) -> 20min (2 workers)

Files to Create:
  .gsd/specs/health-check/design.md
  .gsd/specs/health-check/task-graph.json
```

### Understanding the Task Graph

Before approving, examine the task graph to understand what ZERG will build:

```bash
jq '.tasks[] | {id, title, level, files}' .gsd/specs/health-check/task-graph.json
```

Expected output (simplified):

```json
{
  "id": "TASK-001",
  "title": "Create health check types",
  "level": 1,
  "files": { "create": ["src/health/types.py"], "modify": [], "read": [] }
}
{
  "id": "TASK-002",
  "title": "Create health check configuration",
  "level": 1,
  "files": { "create": ["src/health/config.py"], "modify": [], "read": [] }
}
{
  "id": "TASK-003",
  "title": "Implement health check service",
  "level": 2,
  "files": { "create": ["src/health/service.py"], "modify": [], "read": ["src/health/types.py", "src/health/config.py"] }
}
{
  "id": "TASK-004",
  "title": "Create health check route",
  "level": 2,
  "files": { "create": ["src/health/routes.py"], "modify": ["src/main.py"], "read": ["src/health/types.py", "src/health/service.py"] }
}
{
  "id": "TASK-005",
  "title": "Add health check tests",
  "level": 3,
  "files": { "create": ["tests/test_health.py"], "modify": [], "read": ["src/health/service.py", "src/health/routes.py"] }
}
```

### What to Check

Run through this checklist before approving:

| Check | What to Look For |
|-------|-----------------|
| File ownership | No file appears in the `create` or `modify` list of more than one task |
| Level assignments | Level 1 tasks have no dependencies. Level 2 tasks depend only on Level 1. |
| Verification commands | Each task has a command that actually tests the implementation |
| Read dependencies | Tasks read files from earlier levels, not from the same or later levels |

If everything looks correct:

```
approved
```

**Checkpoint.** You should now have:

```bash
ls .gsd/specs/health-check/
# requirements.md  design.md  task-graph.json
```

---

## Phase 3: Launch the Rush

Start parallel execution with 2 workers (matching the max parallelization for this task graph).

```
/zerg:rush --workers=2
```

**What happens behind the scenes:**

1. ZERG creates git worktrees -- one per worker, each on its own branch.
2. Two Claude Code instances launch.
3. **Level 1:** Worker 0 gets TASK-001 (types). Worker 1 gets TASK-002 (config). Both run in parallel.
4. After both complete, the orchestrator merges their branches and runs quality gates.
5. **Level 2:** Worker 0 gets TASK-003 (service). Worker 1 gets TASK-004 (route). Both run in parallel.
6. Merge and quality gates again.
7. **Level 3:** One worker gets TASK-005 (tests). Only one task, so only one worker is active.
8. Final merge and quality gates.

```
Launching ZERG Rush: health-check

Task graph: 5 tasks across 3 levels
Workers: 2

Launching Worker 0 on port 49152...
Launching Worker 1 on port 49153...

Orchestrator running (PID: 54321).

Monitor progress in a separate terminal:
  zerg status --dashboard
```

---

## Phase 4: Monitor and Merge

Open a second terminal and monitor progress.

```bash
zerg status --watch --interval 5
```

You will see progress advance through the levels:

```
FACTORY STATUS

Feature:      health-check
Phase:        EXECUTING
Elapsed:      00:04:12

Level 1 (Foundation):   [====================] COMPLETE (2/2 tasks)
Level 2 (Core):         [==========>         ] IN PROGRESS (1/2 tasks)
Level 3 (Testing):      [                    ] PENDING (0/1 tasks)
```

### If a Quality Gate Fails

Suppose the lint gate fails after Level 2 merges:

```
Quality gates failed: lint

ruff check .
src/health/routes.py:15:1: E302 expected 2 blank lines, found 1
```

You have two options:

**Option A: Fix manually.** Check out the staging branch, fix the issue, and re-run the merge.

```bash
# In the main project directory
git checkout zerg/health-check/staging
# Fix the lint issue
git add -A && git commit -m "Fix lint issue in health routes"
```

Then in Claude Code:

```
/zerg:merge
```

**Option B: Retry the task.** If the issue is in the worker's output, retry the task so the worker produces corrected code.

```
/zerg:retry TASK-004
```

### When Everything Passes

Once all levels complete and quality gates pass:

```
FACTORY STATUS

Feature:      health-check
Phase:        COMPLETE
Elapsed:      00:18:42

Level 1 (Foundation):   [====================] COMPLETE (2/2)
Level 2 (Core):         [====================] COMPLETE (2/2)
Level 3 (Testing):      [====================] COMPLETE (1/1)

All tasks complete. Code on branch: zerg/health-check/base
```

---

## Phase 5: Integrate the Result

The finished code is on the `zerg/health-check/base` branch. Integrate it into your main branch.

```bash
# Review what changed
git log main..zerg/health-check/base --oneline

# Merge into main
git checkout main
git merge zerg/health-check/base -m "feat: add health check endpoint"
```

Verify the feature works:

```bash
# Run the tests that ZERG created
pytest tests/test_health.py -v

# Start the app and test manually
python -m uvicorn src.main:app --reload &
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "healthy",
  "components": {
    "database": {
      "status": "healthy",
      "latency_ms": 2.3
    }
  }
}
```

### Clean Up

Remove ZERG's working artifacts:

```
/zerg:cleanup
```

This removes worktrees, worker branches, and temporary state files. The spec files in `.gsd/specs/health-check/` are preserved for reference.

---

## What You Built

Here is a summary of what ZERG produced:

| File | Task | Purpose |
|------|------|---------|
| `src/health/types.py` | TASK-001 | Type definitions for health status |
| `src/health/config.py` | TASK-002 | Configuration for health checks |
| `src/health/service.py` | TASK-003 | Health check service with DB check |
| `src/health/routes.py` | TASK-004 | FastAPI route handler |
| `src/main.py` (modified) | TASK-004 | Router registration |
| `tests/test_health.py` | TASK-005 | Unit and integration tests |

The work was distributed across 2 workers and 3 levels. Level 1 and Level 2 each ran two tasks in parallel, reducing the total wall-clock time compared to serial execution.

---

## Tips for Your Next Feature

### Right-Size Your Features

ZERG works best with features that decompose into 5 to 15 tasks. Smaller features (1 to 3 tasks) have more coordination overhead than benefit. Larger features (20+ tasks) work but are harder to review at the design stage.

### Write Clear Requirements

The quality of ZERG's output depends directly on the quality of the requirements. During the planning phase:

- Be specific about data formats, error handling, and edge cases.
- Call out what is out of scope explicitly.
- Mention any existing patterns or conventions the implementation should follow.

### Review the Design Carefully

The design phase is your last chance to influence the architecture before workers start building. Pay attention to:

- **File ownership conflicts** -- The single most common source of merge failures.
- **Verification commands** -- Weak verification means tasks can "pass" without actually working.
- **Level assignments** -- Incorrect levels force unnecessary serialization or cause dependency errors.

### Use Brainstorm for Discovery

If you are starting a new project and do not have a clear feature list, try `/zerg:brainstorm` before planning. It conducts competitive research and structured questioning to help you identify and prioritize features. The output includes GitHub issues that you can feed directly into `/zerg:plan`.

### Start with Fewer Workers

For your first few features, use 2 to 3 workers. This makes the execution easier to follow and debug. Scale up to 5 to 10 workers once you are comfortable with the workflow.

### Use the Dashboard

The TUI dashboard (`zerg status --dashboard`) gives you real-time visibility into what each worker is doing. It is significantly more useful than the one-shot `/zerg:status` command during a rush.

---

## Next Steps

- [[Getting Started]] -- Review core concepts in depth.
- Command Reference -- Full documentation for all 26 `/zerg:*` commands.
- Configuration -- Customize quality gates, worker limits, and resource constraints.
- Troubleshooting -- Solutions for common problems.
