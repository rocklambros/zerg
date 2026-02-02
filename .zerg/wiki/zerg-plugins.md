# /zerg:plugins

Extend ZERG with custom quality gates, lifecycle hooks, and worker launchers.

## Synopsis

This command covers the ZERG plugin system configuration and management. Plugins are configured in `.zerg/config.yaml`.

## Description

The ZERG plugin system provides three extension points for customizing the build and orchestration pipeline. All plugins are additive only -- they cannot mutate orchestrator state, only observe and react. Plugin failures never crash the orchestrator; they are logged and execution continues.

### Plugin Types

**QualityGatePlugin** -- Custom validation that runs after each level merge, following the built-in gates (lint, build, test). Quality gates can be configured as required (blocking merge on failure) or optional.

**LifecycleHookPlugin** -- Observes ZERG lifecycle events without blocking execution. Useful for notifications, metrics collection, and external system integration.

**LauncherPlugin** -- Provides custom worker execution environments beyond the built-in `subprocess` and `container` modes (e.g., Kubernetes, SSH clusters, cloud VMs).

### Quality Gate Plugin

Subclass `QualityGatePlugin` from `zerg/plugins.py` and implement the `name` property and `run` method:

```python
from zerg.plugins import QualityGatePlugin, GateContext
from zerg.types import GateRunResult
from zerg.constants import GateResult

class MyCustomGate(QualityGatePlugin):
    @property
    def name(self) -> str:
        return "my-custom-gate"

    def run(self, ctx: GateContext) -> GateRunResult:
        # ctx.feature, ctx.level, ctx.cwd, ctx.config
        return GateRunResult(
            gate_name=self.name,
            result=GateResult.PASS,
            command="my-custom-check",
            exit_code=0,
            stdout="All checks passed",
            stderr="",
        )
```

Gate results use the `GateResult` enum: `PASS`, `FAIL`, `SKIP`, `TIMEOUT`, or `ERROR`.

Security constraints:

- Read-only access to config and filesystem.
- 5-minute timeout enforced (configurable via YAML).
- Exceptions are caught and logged as an `ERROR` result.

### Lifecycle Hook Plugin

Subclass `LifecycleHookPlugin` and implement the `name` property and `on_event` method:

```python
from zerg.plugins import LifecycleHookPlugin, LifecycleEvent

class SlackNotifier(LifecycleHookPlugin):
    @property
    def name(self) -> str:
        return "slack-notifier"

    def on_event(self, event: LifecycleEvent) -> None:
        # event.event_type, event.data, event.timestamp
        if event.event_type == "task_completed":
            send_notification(event.data["task_id"])
```

Available lifecycle events:

| Event Type | Emitted When | Data Payload |
|------------|-------------|--------------|
| `task_started` | Worker begins task execution | `task_id`, `worker_id`, `level` |
| `task_completed` | Task verification passes | `task_id`, `worker_id`, `duration`, `output` |
| `level_complete` | All tasks in a level finish | `level`, `task_count`, `elapsed_time` |
| `merge_complete` | Level branches merged | `level`, `branch_count`, `conflicts` |
| `worker_spawned` | New worker starts | `worker_id`, `port`, `mode` |
| `quality_gate_run` | Gate executes | `gate_name`, `result`, `level` |
| `rush_started` | `/zerg:rush` begins | `feature`, `workers`, `config` |
| `rush_finished` | All levels complete | `feature`, `total_time`, `tasks_completed` |

Security constraints:

- Hooks never block execution; failures are logged.
- Per-hook try/except isolation.
- No access to mutable orchestrator state.

### Launcher Plugin

Subclass `LauncherPlugin` and implement `create_launcher` to return a `WorkerLauncher` instance:

```python
from zerg.plugins import LauncherPlugin
from zerg.launcher import WorkerLauncher

class K8sLauncherPlugin(LauncherPlugin):
    @property
    def name(self) -> str:
        return "kubernetes"

    def create_launcher(self, config) -> WorkerLauncher:
        return K8sWorkerLauncher(config)
```

The returned launcher must implement `launch()`, `wait()`, and `cleanup()`.

## Options

Plugins are configured in `.zerg/config.yaml`, not via command-line flags.

### YAML Hooks (Simple)

```yaml
plugins:
  enabled: true
  hooks:
    - event: task_completed
      command: echo "Task completed at $(date)"
      timeout: 60
    - event: level_complete
      command: ./scripts/notify-slack.sh "Level {level} done"
      timeout: 120
```

| Field | Description |
|-------|-------------|
| `event` | Lifecycle event name from the table above. |
| `command` | Shell command (parsed with `shlex.split`, no `shell=True`). |
| `timeout` | Maximum execution time in seconds (1--600, default: 60). |

Variable substitution is available using `{level}`, `{feature}`, `{task_id}`, and `{worker_id}`.

### YAML Quality Gates (Simple)

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

| Field | Default | Description |
|-------|---------|-------------|
| `name` | (required) | Unique gate identifier. |
| `command` | (required) | Shell command to execute. |
| `required` | `false` | If `true`, gate failure blocks the merge. |
| `timeout` | `300` | Maximum execution time in seconds (1--3600). |

### Python Entry Points (Advanced)

For complex plugins with custom logic, authentication, or API calls, use Python entry points. See `zerg:plugins.details.md` for full examples and registration instructions.

## Examples

Enable plugins with a custom hook and gate in `.zerg/config.yaml`:

```yaml
plugins:
  enabled: true
  hooks:
    - event: rush_finished
      command: ./scripts/notify-slack.sh "Feature {feature} complete"
      timeout: 60
  quality_gates:
    - name: security-scan
      command: bandit -r src/ --severity medium
      required: false
      timeout: 300
```

## Task Tracking

Plugin management operations create Claude Code Tasks with the subject prefix `[Plugins]`. Task subject conventions for plugin subsystems:

| Prefix | Usage |
|--------|-------|
| `[Plugins]` | Plugin registration and management |
| `[Gate]` | Quality gate execution |
| `[Hook]` | Lifecycle hook invocation |
| `[Launcher]` | Custom launcher execution |

State is tracked in both the Task system (authoritative) and `.zerg/state/plugins.json` (supplementary). If they disagree, the Task system wins.

## See Also

- [[zerg-worker]] -- Worker execution that triggers lifecycle events
- [[zerg-debug]] -- Diagnose plugin failures
- [[zerg-security]] -- Security scanning as a built-in quality gate
- [[zerg-analyze]] -- Analysis checks that can complement custom gates
