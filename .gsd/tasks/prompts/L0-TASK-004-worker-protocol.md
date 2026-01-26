# L0-TASK-004: Worker Protocol Base

## Objective

Define the worker communication protocol and message types for orchestrator-worker coordination.

## Context

**Depends on**: L0-TASK-002 (State Persistence)

Workers communicate with the orchestrator through a defined protocol. This task establishes message types, state machine, and signaling mechanisms.

## Files to Create

```
.zerg/
├── protocol.py      # WorkerProtocol class and state machine
└── messages.py      # Message type definitions
```

## Implementation Requirements

### Message Types

```python
# messages.py
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from datetime import datetime

class MessageType(Enum):
    ASSIGN = "assign"           # Orchestrator -> Worker: assign task
    HEARTBEAT = "heartbeat"     # Worker -> Orchestrator: I'm alive
    PROGRESS = "progress"       # Worker -> Orchestrator: status update
    COMPLETE = "complete"       # Worker -> Orchestrator: task done
    FAILED = "failed"           # Worker -> Orchestrator: task failed
    BLOCKED = "blocked"         # Worker -> Orchestrator: need help
    CONTEXT_THRESHOLD = "context_threshold"  # Worker -> Orchestrator: 70% context

@dataclass
class Message:
    """Base message structure."""
    type: MessageType
    worker_id: str
    timestamp: datetime
    payload: dict

@dataclass
class AssignMessage(Message):
    """Task assignment from orchestrator."""
    task_id: str
    spec_path: str
    worktree_path: str
    timeout_seconds: int

@dataclass
class HeartbeatMessage(Message):
    """Worker health check."""
    context_usage: float  # 0.0 - 1.0
    current_step: Optional[str]

@dataclass  
class CompleteMessage(Message):
    """Task completion report."""
    task_id: str
    files_created: list[str]
    files_modified: list[str]
    verification_passed: bool
    verification_output: str

@dataclass
class FailedMessage(Message):
    """Task failure report."""
    task_id: str
    error: str
    recoverable: bool
    checkpoint_path: Optional[str]
```

### Worker State Machine

```python
# protocol.py
from enum import Enum

class WorkerState(Enum):
    IDLE = "idle"
    ASSIGNED = "assigned"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    SELF_REVIEW = "self_review"
    COMPLETE = "complete"
    FAILED = "failed"
    BLOCKED = "blocked"
    WAITING = "waiting"  # Context threshold reached

class WorkerProtocol:
    """Manages worker state transitions."""
    
    VALID_TRANSITIONS = {
        WorkerState.IDLE: [WorkerState.ASSIGNED],
        WorkerState.ASSIGNED: [WorkerState.EXECUTING],
        WorkerState.EXECUTING: [
            WorkerState.VERIFYING,
            WorkerState.BLOCKED,
            WorkerState.WAITING,
            WorkerState.FAILED
        ],
        WorkerState.VERIFYING: [
            WorkerState.SELF_REVIEW,
            WorkerState.FAILED
        ],
        WorkerState.SELF_REVIEW: [
            WorkerState.COMPLETE,
            WorkerState.EXECUTING  # Revision needed
        ],
        WorkerState.BLOCKED: [WorkerState.EXECUTING],
        WorkerState.WAITING: [WorkerState.IDLE],  # Fresh worker takes over
        WorkerState.COMPLETE: [WorkerState.IDLE],
        WorkerState.FAILED: [WorkerState.IDLE]
    }
    
    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self.state = WorkerState.IDLE
        self.current_task: Optional[str] = None
        
    def transition(self, new_state: WorkerState) -> bool:
        """Attempt state transition. Returns success."""
        if new_state in self.VALID_TRANSITIONS.get(self.state, []):
            self.state = new_state
            return True
        return False
    
    def can_accept_task(self) -> bool:
        """Check if worker can receive new task."""
        return self.state == WorkerState.IDLE
```

### Context Threshold Handling

```python
CONTEXT_THRESHOLD = 0.70  # 70%

def check_context_threshold(context_usage: float) -> bool:
    """Check if worker should checkpoint and exit."""
    return context_usage >= CONTEXT_THRESHOLD

def create_checkpoint_signal(
    task_id: str,
    worker_id: str,
    current_step: int,
    files_created: list[str],
    files_modified: list[str]
) -> Message:
    """Create context threshold message with checkpoint data."""
    return Message(
        type=MessageType.CONTEXT_THRESHOLD,
        worker_id=worker_id,
        timestamp=datetime.now(),
        payload={
            'task_id': task_id,
            'current_step': current_step,
            'files_created': files_created,
            'files_modified': files_modified,
            'checkpoint_ready': True
        }
    )
```

## Acceptance Criteria

- [ ] Message types defined: ASSIGN, HEARTBEAT, PROGRESS, COMPLETE, FAILED, BLOCKED, CONTEXT_THRESHOLD
- [ ] Worker state machine with valid transitions
- [ ] State enum: IDLE → ASSIGNED → EXECUTING → VERIFYING → SELF_REVIEW → COMPLETE
- [ ] Signal handling for context threshold (70%)
- [ ] Checkpoint trigger creates proper message

## Verification

```bash
cd .zerg && python -c "
from protocol import WorkerProtocol, WorkerState
from messages import MessageType, AssignMessage, CompleteMessage

# Test state machine
wp = WorkerProtocol('worker-1')
assert wp.state == WorkerState.IDLE
assert wp.can_accept_task()

# Valid transition
assert wp.transition(WorkerState.ASSIGNED)
assert wp.state == WorkerState.ASSIGNED

# Invalid transition (can't go from ASSIGNED to COMPLETE directly)
assert not wp.transition(WorkerState.COMPLETE)

# Continue valid path
assert wp.transition(WorkerState.EXECUTING)
assert wp.transition(WorkerState.VERIFYING)
assert wp.transition(WorkerState.SELF_REVIEW)
assert wp.transition(WorkerState.COMPLETE)

print('OK: Protocol and messages work correctly')
"
```

## Test Cases

```python
# .zerg/tests/test_protocol.py
import pytest
from protocol import WorkerProtocol, WorkerState, CONTEXT_THRESHOLD
from messages import MessageType, Message

def test_initial_state():
    wp = WorkerProtocol('w1')
    assert wp.state == WorkerState.IDLE

def test_valid_transition_path():
    wp = WorkerProtocol('w1')
    path = [
        WorkerState.ASSIGNED,
        WorkerState.EXECUTING,
        WorkerState.VERIFYING,
        WorkerState.SELF_REVIEW,
        WorkerState.COMPLETE
    ]
    for state in path:
        assert wp.transition(state)

def test_invalid_transition():
    wp = WorkerProtocol('w1')
    # Can't skip ASSIGNED
    assert not wp.transition(WorkerState.EXECUTING)

def test_context_threshold():
    assert check_context_threshold(0.69) == False
    assert check_context_threshold(0.70) == True
    assert check_context_threshold(0.85) == True

def test_blocked_recovery():
    wp = WorkerProtocol('w1')
    wp.transition(WorkerState.ASSIGNED)
    wp.transition(WorkerState.EXECUTING)
    wp.transition(WorkerState.BLOCKED)
    # Can recover from blocked
    assert wp.transition(WorkerState.EXECUTING)
```

## Definition of Done

1. All acceptance criteria checked
2. Verification command passes
3. Unit tests pass: `pytest .zerg/tests/test_protocol.py`
4. State machine prevents invalid transitions
