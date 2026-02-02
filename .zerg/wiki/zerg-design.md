# /zerg:design

Generate technical architecture and a task graph for parallel execution.

## Synopsis

```
/zerg:design
```

## Description

`/zerg:design` reads the approved requirements for the active feature and produces two key artifacts: a technical design document (`design.md`) and a task graph (`task-graph.json`). Together, these define the architecture and break the work into parallelizable tasks with exclusive file ownership.

The command requires that `/zerg:plan` has been run and that the resulting `requirements.md` has been marked as `APPROVED`.

### Design Phases

The command proceeds through six phases:

1. **Architecture Design** -- Analyzes functional requirements, maps data flow, defines component interfaces, and documents key architectural decisions with rationale.

2. **Implementation Plan** -- Breaks the architecture into dependency levels that enable parallel execution:
   - **Level 1 (Foundation):** Types, interfaces, schemas, configuration. No dependencies.
   - **Level 2 (Core):** Business logic services, data access, utilities. Depends on Level 1.
   - **Level 3 (Integration):** API routes, event handlers, middleware. Depends on Level 2.
   - **Level 4 (Testing):** Unit, integration, and E2E tests. Depends on Level 3.
   - **Level 5 (Quality):** Documentation, type coverage, lint fixes. Depends on Level 4.

3. **Task Graph Generation** -- Produces `task-graph.json` containing every task with its ID, title, description, level, dependencies, file ownership (create/modify/read), verification command, and time estimate.

4. **Generate design.md** -- Writes the full design document including overview, architecture diagrams, data models, API design, database schema, key decisions, implementation plan, file ownership matrix, risk assessment, and testing strategy.

5. **Task Graph Validation** -- Checks for circular dependencies, exclusive file ownership, and valid verification commands.

6. **User Approval** -- Presents the design for review. The user responds with `approved` or `changes needed`.

### File Ownership

Each file in the project is assigned to exactly one task. This eliminates merge conflicts during parallel execution. The ownership is recorded in both `design.md` and `task-graph.json`.

### Task Graph Schema

Each task in `task-graph.json` includes:

| Field | Description |
|-------|-------------|
| `id` | Unique task identifier (e.g., `TASK-001`) |
| `title` | Short description of the task |
| `description` | Detailed instructions for the worker |
| `phase` | Named phase (foundation, core, integration, testing, quality) |
| `level` | Numeric dependency level (1-5) |
| `dependencies` | List of task IDs that must complete first |
| `files.create` | Files this task creates |
| `files.modify` | Files this task modifies |
| `files.read` | Files this task reads (no ownership claim) |
| `verification.command` | Shell command to verify task completion |
| `verification.timeout_seconds` | Maximum time for verification |
| `estimate_minutes` | Estimated completion time |

## Options

This command takes no options. It operates on the active feature detected from `.gsd/.current-feature`.

## Prerequisites

- `/zerg:init` must have been run
- `/zerg:plan <feature>` must have been run
- `requirements.md` must exist with `Status: APPROVED`

## Examples

```bash
# Generate design for the active feature
/zerg:design
```

## Output

On completion, the following files are created or updated:

```
.gsd/specs/<feature>/
  design.md               # Technical design document
  task-graph.json          # Machine-readable task graph
```

Tasks are also registered in the Claude Code Task system with subjects following the pattern `[L<level>] <title>` and with dependency chains wired via `blockedBy` relationships.

## Completion Criteria

- `design.md` exists with `Status: APPROVED`
- `task-graph.json` is valid JSON with no circular dependencies
- All tasks have verification commands
- File ownership is exclusive (no two tasks modify the same file)
- User has explicitly approved the design
- Claude Code Tasks are created for all tasks with correct dependencies

## See Also

- [[zerg-plan]] -- Must complete before design
- [[zerg-rush]] -- Next step after design is approved
- [[zerg-Reference]] -- Full command index
