# L0-TASK-002: State Persistence Layer

## Objective

Implement JSON-based state persistence for execution state, checkpoints, and task tracking.

## Context

This is a **root task** with no dependencies. The state layer provides durable storage for ZERG execution, enabling resume after restart.

## Files to Create

```
.zerg/
├── state.py                      # State management classes
└── schemas/
    ├── state.schema.json         # ExecutionState schema
    ├── task.schema.json          # TaskState schema
    └── checkpoint.schema.json    # Checkpoint schema
```

## Implementation Requirements

### ExecutionState Class

```python
@dataclass
class ExecutionState:
    """Persistent execution state."""
    
    feature: str
    started_at: datetime
    current_level: int
    tasks: dict[str, TaskState]
    workers: dict[str, WorkerState]
    checkpoints: list[str]
    
    def save(self, path: str = ".zerg/state.json") -> None:
        """Atomically save state to disk."""
        # Write to temp file, then rename (atomic on POSIX)
        
    @classmethod
    def load(cls, path: str = ".zerg/state.json") -> "ExecutionState":
        """Load state from disk, validate against schema."""
        
    @classmethod
    def create(cls, feature: str) -> "ExecutionState":
        """Create new execution state for feature."""
```

### TaskState Enum

```python
class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    BLOCKED = "blocked"
```

### Checkpoint Structure

```python
@dataclass
class Checkpoint:
    """Worker checkpoint for context threshold recovery."""
    
    task_id: str
    worker_id: str
    timestamp: datetime
    files_created: list[str]
    files_modified: list[str]
    current_step: int
    state_data: dict
```

### Schema Validation

Use `jsonschema` library for validation:

```python
def validate_state(data: dict) -> bool:
    """Validate state against JSON schema."""
    schema = load_schema("state.schema.json")
    validate(instance=data, schema=schema)
    return True
```

### Atomic Writes

```python
def atomic_write(path: str, data: str) -> None:
    """Write atomically using temp file + rename."""
    temp_path = f"{path}.tmp.{os.getpid()}"
    with open(temp_path, 'w') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.rename(temp_path, path)
```

## Acceptance Criteria

- [ ] ExecutionState class with save/load methods
- [ ] TaskState tracking (pending, running, complete, failed, blocked)
- [ ] Checkpoint serialization/deserialization
- [ ] Schema validation with jsonschema
- [ ] Atomic writes (write to temp, rename)
- [ ] Handle missing state file gracefully

## Verification

```bash
cd .zerg && python -c "
from state import ExecutionState, TaskStatus, Checkpoint

# Test create and save
s = ExecutionState.create('test-feature')
s.save()

# Test load
s2 = ExecutionState.load()
assert s2.feature == 'test-feature'
assert s2.current_level == 0

# Test checkpoint
cp = Checkpoint(
    task_id='TASK-001',
    worker_id='worker-1',
    timestamp=None,
    files_created=['test.py'],
    files_modified=[],
    current_step=3,
    state_data={}
)

print('OK: State persistence works')
"
```

## JSON Schemas

### state.schema.json

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["feature", "started_at", "current_level", "tasks"],
  "properties": {
    "feature": {"type": "string"},
    "started_at": {"type": "string", "format": "date-time"},
    "current_level": {"type": "integer", "minimum": 0},
    "tasks": {
      "type": "object",
      "additionalProperties": {"$ref": "#/definitions/task"}
    }
  },
  "definitions": {
    "task": {
      "type": "object",
      "required": ["id", "status"],
      "properties": {
        "id": {"type": "string"},
        "status": {"enum": ["pending", "running", "complete", "failed", "blocked"]},
        "worker_id": {"type": ["string", "null"]},
        "started_at": {"type": ["string", "null"]},
        "completed_at": {"type": ["string", "null"]},
        "error": {"type": ["string", "null"]}
      }
    }
  }
}
```

## Test Cases

```python
# .zerg/tests/test_state.py
import pytest
import os
from state import ExecutionState, TaskStatus

def test_create_state():
    s = ExecutionState.create('my-feature')
    assert s.feature == 'my-feature'
    assert s.current_level == 0

def test_save_load_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    s = ExecutionState.create('test')
    s.save(str(path))
    
    s2 = ExecutionState.load(str(path))
    assert s2.feature == s.feature

def test_atomic_write_on_crash(tmp_path):
    # Verify no partial writes on simulated crash
    pass

def test_schema_validation_rejects_invalid():
    # Verify invalid data raises ValidationError
    pass
```

## Definition of Done

1. All acceptance criteria checked
2. Verification command passes
3. Unit tests pass: `pytest .zerg/tests/test_state.py`
4. Schemas validate correctly: `python -c "import jsonschema; ..."`
