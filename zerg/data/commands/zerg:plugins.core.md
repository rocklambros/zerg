# ZERG Plugin System

Extend ZERG with custom quality gates, lifecycle hooks, and worker launchers.

## Overview

The ZERG plugin system provides three extension points:

1. **Quality Gate Plugins** — Custom validation after merges (lint, security scans, benchmarks)
2. **Lifecycle Hook Plugins** — React to events (task starts/completes, level finishes, merges)
3. **Launcher Plugins** — Custom worker execution environments (Kubernetes, SSH clusters, cloud VMs)

All plugins are **additive only** — they cannot mutate orchestrator state, only observe and react. Plugin failures never crash the orchestrator; they are logged and execution continues.

## Plugin Types

### QualityGatePlugin

Validates code quality after each level merge. Runs sequentially after built-in gates.

**Abstract Base Class** (`zerg/plugins.py:51-62`):

```python
from zerg.plugins import QualityGatePlugin, GateContext
from zerg.types import GateRunResult
from zerg.constants import GateResult

class MyCustomGate(QualityGatePlugin):
    @property
    def name(self) -> str:
        return "my-custom-gate"

    def run(self, ctx: GateContext) -> GateRunResult:
        # ctx.feature: str — feature name
        # ctx.level: int — level just merged
        # ctx.cwd: Path — working directory
        # ctx.config: ZergConfig — full config

        # Run validation logic...

        return GateRunResult(
            gate_name=self.name,
            result=GateResult.PASS,  # PASS | FAIL | SKIP | TIMEOUT | ERROR
            command="my-custom-check",
            exit_code=0,
            stdout="All checks passed",
            stderr="",
        )
```

**Execution flow**: Built-in gates (lint, build, test) → Plugin gates (registered order) → Merge completes

**Security**:
- Read-only access to config and filesystem
- 5-minute timeout enforced (configurable via YAML)
- Exceptions caught and logged as ERROR result

### LifecycleHookPlugin

Observes ZERG lifecycle events without blocking execution.

**Abstract Base Class** (`zerg/plugins.py:64-74`):

```python
from zerg.plugins import LifecycleHookPlugin, LifecycleEvent

class MyNotificationHook(LifecycleHookPlugin):
    @property
    def name(self) -> str:
        return "slack-notifier"

    def on_event(self, event: LifecycleEvent) -> None:
        # event.event_type: str — from PluginHookEvent enum
        # event.data: dict — event-specific payload
        # event.timestamp: datetime — when event occurred

        if event.event_type == "task_completed":
            task_id = event.data["task_id"]
            # Send Slack notification...
```

**Available events** (from `zerg/constants.py:143-149`):

| Event Type | Emitted When | Data Payload |
|------------|-------------|--------------|
| `task_started` | Worker begins task execution | `task_id`, `worker_id`, `level` |
| `task_completed` | Task verification passes | `task_id`, `worker_id`, `duration`, `output` |
| `level_complete` | All tasks in level finish | `level`, `task_count`, `elapsed_time` |
| `merge_complete` | Level branches merged | `level`, `branch_count`, `conflicts` |
| `worker_spawned` | New worker starts | `worker_id`, `port`, `mode` |
| `quality_gate_run` | Gate executes | `gate_name`, `result`, `level` |
| `rush_started` | `/zerg:rush` begins | `feature`, `workers`, `config` |
| `rush_finished` | All levels complete | `feature`, `total_time`, `tasks_completed` |

**Security**:
- Hooks never block execution — failures are logged
- Per-hook try/except isolation
- No access to mutable orchestrator state

### LauncherPlugin

Provides custom worker execution environments beyond `subprocess` and `container`.

**Abstract Base Class** (`zerg/plugins.py:77-87`):

```python
from zerg.plugins import LauncherPlugin
from zerg.launcher import WorkerLauncher

class K8sLauncherPlugin(LauncherPlugin):
    @property
    def name(self) -> str:
        return "kubernetes"

    def create_launcher(self, config: Any) -> WorkerLauncher:
        # Return a WorkerLauncher subclass instance
        return K8sWorkerLauncher(config)
```

**Execution flow**: Check launcher plugins → Fallback to built-in (`subprocess` | `container`)

**Security**:
- Launchers inherit from `WorkerLauncher` ABC
- Must implement `launch()`, `wait()`, `cleanup()` methods
- No direct orchestrator access

## Configuration

### YAML Hooks (Simple)

For simple shell commands triggered by lifecycle events:

```yaml
# .zerg/config.yaml

plugins:
  enabled: true

  hooks:
    - event: task_completed
      command: echo "Task completed at $(date)"
      timeout: 60

    - event: level_complete
      command: ./scripts/notify-slack.sh "Level {level} done"
      timeout: 120

    - event: merge_complete
      command: |
        python scripts/generate_report.py \
          --level {level} \
          --feature {feature}
      timeout: 180
```

**Fields**:
- `event` — From `PluginHookEvent` enum (see lifecycle event table)
- `command` — Shell command (parsed with `shlex.split`, no shell=True)
- `timeout` — Max execution time in seconds (1-600, default: 60)

**Variable substitution**: `{level}`, `{feature}`, `{task_id}`, `{worker_id}` — replaced from event data

**Execution**: Commands run in subprocess with no shell, isolated per-hook with try/except

### YAML Gates (Simple)

For custom quality gates via shell commands:

```yaml
plugins:
  quality_gates:
    - name: security-scan
      command: bandit -r src/ --severity medium
      required: false
      timeout: 300

    - name: complexity-check
      command: radon cc src/ --min B
      required: true
      timeout: 120
```

**Fields**:
- `name` — Unique gate identifier
- `command` — Shell command to execute
- `required` — If `true`, gate failure blocks merge (default: `false`)
- `timeout` — Max execution time in seconds (1-3600, default: 300)

### Python Entry Points (Advanced)

For complex plugins with custom logic, authentication, or API calls — see `zerg:plugins.details.md` for full examples.

## TaskCreate/TaskUpdate Integration

All plugin management commands must integrate with the Claude Code Task system per ZERG conventions.

### Creating Plugin-Related Tasks

When registering or managing plugins:

```python
# Create task for plugin operations
task_id = TaskCreate(
    subject="[Plugins] Register custom quality gates",
    status="pending",
    metadata={"feature": feature_name, "command": "zerg:plugins"}
)

# Mark in progress
TaskUpdate(task_id=task_id, status="in_progress")

# On completion
TaskUpdate(task_id=task_id, status="completed")
```

### Task Subject Conventions

Use bracketed prefixes for plugin-related tasks:

- `[Plugins] Register {name}` — Plugin registration
- `[Gate] Run {gate_name}` — Quality gate execution
- `[Hook] Process {event_type}` — Lifecycle hook invocation
- `[Launcher] Spawn {worker_id}` — Custom launcher execution

### State Tracking

Plugin operations should write state to both:

1. **Task system** (authoritative) — via `TaskCreate`/`TaskUpdate`
2. **State JSON** (supplementary) — `.zerg/state/plugins.json`

If Task system and state JSON disagree, Task system wins.
