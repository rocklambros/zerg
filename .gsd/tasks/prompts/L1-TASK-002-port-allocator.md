# L1-TASK-002: Port Allocator

## Objective

Implement ephemeral port allocation (49152-65535) for worker isolation.

## Context

**Depends on**: L0-TASK-001 (Orchestrator Core)

Each worker needs a unique port for its MCP server. The port allocator manages the ephemeral range and tracks assignments.

## Files to Create

```
.zerg/
└── ports.py          # PortAllocator class
```

## Implementation Requirements

### PortAllocator Class

```python
import socket
import random
from dataclasses import dataclass
from typing import Optional

@dataclass
class PortAssignment:
    """Represents a port assignment."""
    port: int
    worker_id: str
    assigned_at: datetime

class PortAllocator:
    """Manages port allocation for workers."""
    
    EPHEMERAL_START = 49152
    EPHEMERAL_END = 65535
    
    def __init__(self):
        self.assignments: dict[str, PortAssignment] = {}
        self.used_ports: set[int] = set()
    
    def allocate(self, worker_id: str) -> int:
        """Allocate a port for a worker."""
        if worker_id in self.assignments:
            return self.assignments[worker_id].port
        
        port = self._find_available_port()
        assignment = PortAssignment(
            port=port,
            worker_id=worker_id,
            assigned_at=datetime.now()
        )
        self.assignments[worker_id] = assignment
        self.used_ports.add(port)
        return port
    
    def release(self, worker_id: str) -> None:
        """Release a worker's port."""
        if worker_id in self.assignments:
            port = self.assignments[worker_id].port
            self.used_ports.discard(port)
            del self.assignments[worker_id]
    
    def _find_available_port(self) -> int:
        """Find an available port in the ephemeral range."""
        max_attempts = 100
        
        for _ in range(max_attempts):
            port = random.randint(self.EPHEMERAL_START, self.EPHEMERAL_END)
            if port not in self.used_ports and self._is_port_available(port):
                return port
        
        raise RuntimeError("No available ports in ephemeral range")
    
    def _is_port_available(self, port: int) -> bool:
        """Check if port is available on the system."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return True
        except OSError:
            return False
    
    def get_assignment(self, worker_id: str) -> Optional[PortAssignment]:
        """Get port assignment for a worker."""
        return self.assignments.get(worker_id)
```

## Acceptance Criteria

- [ ] Allocate ports in range 49152-65535
- [ ] Track assignments per worker
- [ ] Verify port availability before assignment
- [ ] Release ports on worker completion
- [ ] Handle concurrent allocation requests

## Verification

```bash
cd .zerg && python -c "
from ports import PortAllocator

pa = PortAllocator()

# Allocate ports
p1 = pa.allocate('worker-1')
p2 = pa.allocate('worker-2')

assert 49152 <= p1 <= 65535
assert 49152 <= p2 <= 65535
assert p1 != p2

# Same worker gets same port
assert pa.allocate('worker-1') == p1

# Release and verify
pa.release('worker-1')
assert pa.get_assignment('worker-1') is None

print(f'OK: Ports allocated: {p1}, {p2}')
"
```

## Test Cases

```python
# .zerg/tests/test_ports.py
import pytest
from ports import PortAllocator

def test_allocate_unique():
    pa = PortAllocator()
    ports = [pa.allocate(f'w{i}') for i in range(10)]
    assert len(set(ports)) == 10

def test_same_worker_same_port():
    pa = PortAllocator()
    p1 = pa.allocate('w1')
    p2 = pa.allocate('w1')
    assert p1 == p2

def test_release():
    pa = PortAllocator()
    pa.allocate('w1')
    pa.release('w1')
    assert pa.get_assignment('w1') is None

def test_port_in_range():
    pa = PortAllocator()
    port = pa.allocate('w1')
    assert 49152 <= port <= 65535
```

## Definition of Done

1. All acceptance criteria checked
2. Verification command passes
3. Unit tests pass: `pytest .zerg/tests/test_ports.py`
