# L0-TASK-003: Task Graph Parser

## Objective

Implement task graph loading, validation, and dependency resolution.

## Context

**Depends on**: L0-TASK-002 (State Persistence)

The task graph defines work breakdown: tasks, dependencies, file ownership, and level assignments. This parser loads, validates, and computes execution order.

## Files to Create

```
.zerg/
├── task_graph.py                 # TaskGraph class
└── schemas/
    └── task-graph.schema.json    # Task graph schema
```

## Implementation Requirements

### TaskGraph Class

```python
@dataclass
class Task:
    """Individual task definition."""
    id: str
    title: str
    description: str
    level: int
    dependencies: list[str]
    files: TaskFiles
    acceptance_criteria: list[str]
    verification: VerificationConfig
    agents_required: list[str]

@dataclass
class TaskFiles:
    """File ownership for a task."""
    create: list[str]
    modify: list[str]
    read: list[str]

class TaskGraph:
    """Manages task dependencies and execution order."""
    
    def __init__(self, tasks: list[Task]):
        self.tasks = {t.id: t for t in tasks}
        self._build_dag()
    
    @classmethod
    def from_file(cls, path: str) -> "TaskGraph":
        """Load and validate task graph from JSON."""
        
    def get_level_tasks(self, level: int) -> list[Task]:
        """Get all tasks at specified level."""
        
    def get_ready_tasks(self, completed: set[str]) -> list[Task]:
        """Get tasks whose dependencies are satisfied."""
        
    def validate_file_ownership(self) -> list[str]:
        """Check for file ownership conflicts. Return errors."""
        
    @property
    def level_count(self) -> int:
        """Total number of levels in graph."""
```

### Dependency Resolution

```python
def _build_dag(self) -> None:
    """Build directed acyclic graph from dependencies."""
    # Detect circular dependencies
    # Compute topological order
    # Assign levels based on dependency depth
    
def _detect_cycles(self) -> list[list[str]]:
    """Return list of cycles if any exist."""
    # Use DFS with color marking
    # WHITE = unvisited, GRAY = in progress, BLACK = complete
```

### File Ownership Validation

```python
def validate_file_ownership(self) -> list[str]:
    """Ensure no two tasks modify the same file."""
    errors = []
    file_owners: dict[str, str] = {}
    
    for task in self.tasks.values():
        for f in task.files.create + task.files.modify:
            if f in file_owners:
                errors.append(
                    f"File '{f}' owned by both {file_owners[f]} and {task.id}"
                )
            file_owners[f] = task.id
    
    return errors
```

## Acceptance Criteria

- [ ] Load task-graph.json from specs directory
- [ ] Validate against JSON schema
- [ ] Build dependency DAG
- [ ] Compute level assignments automatically
- [ ] Detect circular dependencies (raise error)
- [ ] Validate exclusive file ownership

## Verification

```bash
cd .zerg && python -c "
from task_graph import TaskGraph

# Create test fixture
import json
test_graph = {
    'tasks': [
        {
            'id': 'TASK-001',
            'title': 'Create types',
            'level': 0,
            'dependencies': [],
            'files': {'create': ['types.py'], 'modify': [], 'read': []},
            'acceptance_criteria': ['Types defined'],
            'verification': {'command': 'python -c \"import types\"'}
        },
        {
            'id': 'TASK-002', 
            'title': 'Use types',
            'level': 1,
            'dependencies': ['TASK-001'],
            'files': {'create': ['main.py'], 'modify': [], 'read': ['types.py']},
            'acceptance_criteria': ['Main uses types'],
            'verification': {'command': 'python main.py'}
        }
    ]
}

with open('/tmp/test-graph.json', 'w') as f:
    json.dump(test_graph, f)

g = TaskGraph.from_file('/tmp/test-graph.json')
assert g.level_count == 2
assert len(g.get_level_tasks(0)) == 1
assert len(g.get_level_tasks(1)) == 1
assert g.validate_file_ownership() == []

print(f'OK: TaskGraph works, {g.level_count} levels')
"
```

## JSON Schema

### task-graph.schema.json

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["tasks"],
  "properties": {
    "feature": {"type": "string"},
    "created_at": {"type": "string", "format": "date-time"},
    "tasks": {
      "type": "array",
      "items": {"$ref": "#/definitions/task"}
    }
  },
  "definitions": {
    "task": {
      "type": "object",
      "required": ["id", "title", "level", "dependencies", "files"],
      "properties": {
        "id": {"type": "string", "pattern": "^[A-Z]+-[0-9]+$"},
        "title": {"type": "string"},
        "description": {"type": "string"},
        "level": {"type": "integer", "minimum": 0},
        "dependencies": {
          "type": "array",
          "items": {"type": "string"}
        },
        "files": {
          "type": "object",
          "required": ["create", "modify", "read"],
          "properties": {
            "create": {"type": "array", "items": {"type": "string"}},
            "modify": {"type": "array", "items": {"type": "string"}},
            "read": {"type": "array", "items": {"type": "string"}}
          }
        },
        "acceptance_criteria": {
          "type": "array",
          "items": {"type": "string"}
        },
        "verification": {
          "type": "object",
          "required": ["command"],
          "properties": {
            "command": {"type": "string"},
            "timeout_seconds": {"type": "integer", "default": 60}
          }
        },
        "agents_required": {
          "type": "array",
          "items": {"type": "string"}
        }
      }
    }
  }
}
```

## Test Cases

```python
# .zerg/tests/test_task_graph.py
import pytest
from task_graph import TaskGraph, Task

def test_load_valid_graph():
    g = TaskGraph.from_file('test/fixtures/valid-graph.json')
    assert g.level_count > 0

def test_detect_circular_dependency():
    # A -> B -> C -> A should raise
    with pytest.raises(ValueError, match="circular"):
        TaskGraph.from_file('test/fixtures/circular-graph.json')

def test_file_ownership_conflict():
    g = TaskGraph.from_file('test/fixtures/conflict-graph.json')
    errors = g.validate_file_ownership()
    assert len(errors) > 0

def test_get_ready_tasks():
    g = TaskGraph.from_file('test/fixtures/valid-graph.json')
    ready = g.get_ready_tasks(completed=set())
    assert all(t.level == 0 for t in ready)
```

## Definition of Done

1. All acceptance criteria checked
2. Verification command passes
3. Unit tests pass: `pytest .zerg/tests/test_task_graph.py`
4. Circular dependency detection works
5. File ownership validation catches conflicts
