# L1-TASK-005: Metrics Collector

## Objective

Implement metrics collection for execution monitoring and cost tracking.

## Context

**Depends on**: L0-TASK-002 (State Persistence)

Metrics provide visibility into execution performance, enabling optimization and cost projection.

## Files to Create

```
.zerg/
├── metrics.py        # MetricsCollector class
└── metrics/          # Metrics output directory
```

## Implementation Requirements

### MetricsCollector Class

```python
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json

@dataclass
class TaskMetrics:
    """Metrics for a single task."""
    task_id: str
    worker_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    context_usage: float = 0.0
    token_count: int = 0
    status: str = "running"

@dataclass
class LevelMetrics:
    """Metrics for a level."""
    level: int
    tasks: list[TaskMetrics] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    @property
    def duration_seconds(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

class MetricsCollector:
    """Collects and exports execution metrics."""
    
    METRICS_DIR = Path(".zerg/metrics")
    
    def __init__(self):
        self.tasks: dict[str, TaskMetrics] = {}
        self.levels: dict[int, LevelMetrics] = {}
        self.execution_id: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.METRICS_DIR.mkdir(parents=True, exist_ok=True)
    
    def record_task_start(self, task_id: str, worker_id: str) -> None:
        """Record task start."""
        self.tasks[task_id] = TaskMetrics(
            task_id=task_id,
            worker_id=worker_id,
            started_at=datetime.now()
        )
    
    def record_task_end(
        self, 
        task_id: str, 
        status: str = "complete",
        context_usage: float = 0.0,
        token_count: int = 0
    ) -> None:
        """Record task completion."""
        if task_id not in self.tasks:
            return
        
        task = self.tasks[task_id]
        task.completed_at = datetime.now()
        task.duration_seconds = (task.completed_at - task.started_at).total_seconds()
        task.status = status
        task.context_usage = context_usage
        task.token_count = token_count
    
    def record_level_start(self, level: int) -> None:
        """Record level start."""
        self.levels[level] = LevelMetrics(
            level=level,
            started_at=datetime.now()
        )
    
    def record_level_end(self, level: int) -> None:
        """Record level completion."""
        if level not in self.levels:
            return
        self.levels[level].completed_at = datetime.now()
    
    def get_summary(self) -> dict:
        """Get execution summary."""
        total_duration = sum(t.duration_seconds or 0 for t in self.tasks.values())
        total_tokens = sum(t.token_count for t in self.tasks.values())
        
        return {
            'execution_id': self.execution_id,
            'total_tasks': len(self.tasks),
            'completed_tasks': sum(1 for t in self.tasks.values() if t.status == 'complete'),
            'failed_tasks': sum(1 for t in self.tasks.values() if t.status == 'failed'),
            'total_duration_seconds': total_duration,
            'total_tokens': total_tokens,
            'estimated_cost_usd': self._estimate_cost(total_tokens),
            'avg_task_duration': total_duration / len(self.tasks) if self.tasks else 0,
            'levels': len(self.levels)
        }
    
    def _estimate_cost(self, tokens: int) -> float:
        """Estimate API cost (rough calculation)."""
        # Assumes Claude Sonnet pricing (~$3/1M input, $15/1M output)
        # Rough average: $9/1M tokens
        return (tokens / 1_000_000) * 9.0
    
    def export(self, path: Path = None) -> Path:
        """Export metrics to JSON."""
        path = path or self.METRICS_DIR / f"metrics_{self.execution_id}.json"
        
        data = {
            'summary': self.get_summary(),
            'tasks': [
                {
                    'task_id': t.task_id,
                    'worker_id': t.worker_id,
                    'started_at': t.started_at.isoformat(),
                    'completed_at': t.completed_at.isoformat() if t.completed_at else None,
                    'duration_seconds': t.duration_seconds,
                    'context_usage': t.context_usage,
                    'token_count': t.token_count,
                    'status': t.status
                }
                for t in self.tasks.values()
            ],
            'levels': [
                {
                    'level': lv.level,
                    'started_at': lv.started_at.isoformat() if lv.started_at else None,
                    'completed_at': lv.completed_at.isoformat() if lv.completed_at else None,
                    'duration_seconds': lv.duration_seconds,
                    'task_count': len(lv.tasks)
                }
                for lv in self.levels.values()
            ]
        }
        
        path.write_text(json.dumps(data, indent=2))
        return path
```

## Acceptance Criteria

- [ ] Track task duration and worker utilization
- [ ] Context usage monitoring per task
- [ ] Token count estimation
- [ ] Cost projection (rough API cost)
- [ ] Export to JSON in `.zerg/metrics/`
- [ ] Summary statistics (total, avg, by level)

## Verification

```bash
cd .zerg && python -c "
from metrics import MetricsCollector
import time

mc = MetricsCollector()

# Record tasks
mc.record_level_start(0)
mc.record_task_start('TASK-001', 'worker-1')
time.sleep(0.1)
mc.record_task_end('TASK-001', token_count=1000)

mc.record_task_start('TASK-002', 'worker-2')
time.sleep(0.1)
mc.record_task_end('TASK-002', status='failed')
mc.record_level_end(0)

# Get summary
summary = mc.get_summary()
assert summary['total_tasks'] == 2
assert summary['completed_tasks'] == 1
assert summary['failed_tasks'] == 1

# Export
path = mc.export()
assert path.exists()

print('OK: Metrics collector works')
print(f'Summary: {summary}')
"
```

## Test Cases

```python
# .zerg/tests/test_metrics.py
import pytest
from metrics import MetricsCollector

def test_record_task():
    mc = MetricsCollector()
    mc.record_task_start('T1', 'W1')
    mc.record_task_end('T1')
    assert mc.tasks['T1'].status == 'complete'

def test_duration_tracking():
    mc = MetricsCollector()
    mc.record_task_start('T1', 'W1')
    time.sleep(0.1)
    mc.record_task_end('T1')
    assert mc.tasks['T1'].duration_seconds >= 0.1

def test_summary():
    mc = MetricsCollector()
    mc.record_task_start('T1', 'W1')
    mc.record_task_end('T1', token_count=500)
    summary = mc.get_summary()
    assert summary['total_tokens'] == 500

def test_export(tmp_path):
    mc = MetricsCollector()
    mc.record_task_start('T1', 'W1')
    mc.record_task_end('T1')
    path = mc.export(tmp_path / 'metrics.json')
    assert path.exists()
```

## Definition of Done

1. All acceptance criteria checked
2. Verification command passes
3. Unit tests pass: `pytest .zerg/tests/test_metrics.py`
4. `.zerg/metrics/` directory created
