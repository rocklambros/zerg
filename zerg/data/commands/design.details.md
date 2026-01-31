<!-- SPLIT: details, parent: design.md -->
# design — Detailed Reference

This file contains extended examples, templates, and edge cases.
Core instructions are in `design.core.md`.

## Task Graph JSON Schema (v2.0)

The task-graph.json must conform to the v2.0 schema:

```json
{
  "feature": "string (required) - feature name",
  "version": "string (required) - schema version, use 2.0",
  "generated": "string (required) - ISO timestamp",
  "total_tasks": "number (required) - count of tasks",
  "estimated_duration_minutes": "number (required) - total minutes",
  "max_parallelization": "number (required) - max concurrent tasks",
  "critical_path_minutes": "number (optional) - longest path duration",

  "tasks": [
    {
      "id": "string (required) - unique task ID, format: FEATURE-LN-NNN",
      "title": "string (required) - short task title",
      "description": "string (required) - detailed description",
      "phase": "string (required) - foundation|core|integration|testing|quality",
      "level": "number (required) - 1-5",
      "dependencies": ["array of task IDs this depends on"],
      "files": {
        "create": ["files to create"],
        "modify": ["files to modify"],
        "read": ["files to read only"]
      },
      "acceptance_criteria": ["array (required) - list of criteria for task completion"],
      "verification": {
        "command": "string (required) - command to verify completion",
        "timeout_seconds": "number (default: 60)"
      },
      "estimate_minutes": "number (optional) - time estimate",
      "critical_path": "boolean (optional) - true if on critical path",
      "agents_required": ["optional agent types: coder, reviewer, tester"]
    }
  ],

  "levels": {
    "1": {
      "name": "string (required) - level name",
      "tasks": ["task IDs in this level"],
      "parallel": "boolean - can tasks run in parallel",
      "estimated_minutes": "number - level duration",
      "depends_on_levels": ["level numbers this depends on"]
    }
  }
}
```

## File Ownership Rules

1. **Exclusive Create**: Each file can only be created by ONE task
2. **Exclusive Modify**: Each file can only be modified by ONE task per level
3. **Read is Shared**: Multiple tasks can read the same file
4. **Level Boundaries**: A file modified in level N cannot be modified again until level N+1

## File Ownership Validation (v2.0)

Before finalizing the task graph, validate file ownership:

```bash
# Validate using Python task_graph module
cd .zerg && python -c "
from task_graph import TaskGraph
import json

graph = TaskGraph.from_file('../.gsd/specs/FEATURE/task-graph.json')

# Check for file ownership conflicts
conflicts = graph.validate_file_ownership()
if conflicts:
    print('FILE OWNERSHIP CONFLICTS:')
    for conflict in conflicts:
        print(f'  - {conflict}')
    exit(1)

print('OK: No file ownership conflicts')
print(f'Tasks: {len(graph.tasks)}')
print(f'Levels: {len(graph.get_levels())}')
"
```

### Conflict Types

| Conflict | Description | Resolution |
|----------|-------------|------------|
| Create-Create | Two tasks create same file | Merge into one task or split file |
| Create-Modify | Task A creates, Task B modifies at same level | Move modify to next level |
| Modify-Modify | Two tasks modify same file at same level | Merge tasks or sequence them |

### Validation Output

```
FILE OWNERSHIP VALIDATION
═════════════════════════

Files to Create: 8
Files to Modify: 3
Files Read-Only: 12

Ownership Matrix:
  src/auth/types.ts     → TASK-001 (create)
  src/auth/service.ts   → TASK-003 (create)
  src/auth/routes.ts    → TASK-005 (create)
  src/db/schema/user.ts → TASK-002 (create)

Conflicts: NONE ✓
```

## Level Criteria

| Level | Name | Characteristics |
|-------|------|-----------------|
| 1 | Foundation | No dependencies, types/schemas/config |
| 2 | Core | Depends on L1, business logic/services |
| 3 | Integration | Depends on L2, APIs/routes/handlers |
| 4 | Testing | Depends on L3, tests/validation |
| 5 | Quality | Depends on L4, docs/polish/final |
