# L0-TASK-001: Orchestrator Core

## Objective

Implement the central orchestrator that manages worker fleet lifecycle, task distribution, and level synchronization.

## Context

This is a **root task** with no dependencies. The orchestrator is the heart of ZERG, coordinating parallel worker execution across git worktrees.

Read these files first:
- `ARCHITECTURE.md` - Overall system design
- `.zerg/config.yaml` - Current configuration schema

## Files to Create

```
.zerg/
├── __init__.py           # Package init with version
└── orchestrator.py       # Main orchestrator class
```

## Implementation Requirements

### Orchestrator Class

```python
class Orchestrator:
    """Manages worker fleet lifecycle and task distribution."""
    
    def __init__(self, config_path: str = ".zerg/config.yaml"):
        """Load configuration and initialize state."""
        
    def start(self, task_graph_path: str, workers: int = 5) -> None:
        """Begin execution with specified worker count."""
        
    def stop(self, force: bool = False) -> None:
        """Graceful or forced shutdown."""
        
    def get_status(self) -> dict:
        """Return current execution state."""
```

### Required Capabilities

1. **Worker Spawning**: Launch worker subprocesses with isolated environments
2. **Task Queue**: Level-based ordering (all L0 before any L1)
3. **Health Monitoring**: Heartbeat detection, timeout handling
4. **Level Barriers**: Block next level until current level completes
5. **Checkpointing**: Save state for resumption on restart

### Worker Lifecycle

```
spawn_worker(worker_id) → assign_task(worker_id, task) → monitor_health() → collect_result() → cleanup()
```

### Level Synchronization

```python
def execute_level(self, level: int) -> LevelResult:
    """Execute all tasks at a level, wait for completion."""
    tasks = self.task_graph.get_level_tasks(level)
    
    # Assign tasks to available workers
    for task in tasks:
        worker = self.get_available_worker()
        self.assign_task(worker, task)
    
    # Wait for all tasks to complete
    self.wait_for_level_completion(level)
    
    # Run quality gates between levels
    self.run_quality_gates(level)
    
    return LevelResult(...)
```

## Acceptance Criteria

- [ ] Orchestrator can spawn worker processes
- [ ] Task queue with level-based ordering
- [ ] Worker health monitoring (heartbeat every 30s)
- [ ] Graceful shutdown with checkpoint save
- [ ] Level barrier synchronization enforced
- [ ] Resume from checkpoint on restart

## Verification

Run this command to verify implementation:

```bash
cd .zerg && python -c "
from orchestrator import Orchestrator
o = Orchestrator()
assert hasattr(o, 'start')
assert hasattr(o, 'stop')
assert hasattr(o, 'get_status')
print('OK: Orchestrator instantiates correctly')
"
```

## Test Cases

Create `.zerg/tests/test_orchestrator.py`:

```python
import pytest
from orchestrator import Orchestrator

def test_orchestrator_init():
    o = Orchestrator()
    assert o is not None

def test_get_status_idle():
    o = Orchestrator()
    status = o.get_status()
    assert status['state'] == 'IDLE'

def test_graceful_shutdown():
    o = Orchestrator()
    o.stop()
    assert o.get_status()['state'] == 'STOPPED'
```

## Notes

- Use `subprocess` for worker processes initially (containers come in L1-TASK-003)
- Store state in `.zerg/state.json` (L0-TASK-002 will formalize schema)
- Log to `.zerg/logs/orchestrator.log`
- Respect `max_workers` from config.yaml

## Definition of Done

1. All acceptance criteria checked
2. Verification command passes
3. Unit tests pass: `pytest .zerg/tests/test_orchestrator.py`
4. No linting errors: `ruff check .zerg/orchestrator.py`
