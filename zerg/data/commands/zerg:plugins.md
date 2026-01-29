# ZERG Plugins

Manage and inspect the ZERG plugin system.

## Overview

ZERG supports three plugin types:
- **Quality Gate Plugins** — Custom lint/test/check gates after merge
- **Lifecycle Hook Plugins** — React to task, level, merge, and rush events
- **Launcher Plugins** — Custom worker launchers (K8s, SSH, cloud VMs)

## Usage

```bash
# List all registered plugins
zerg plugins

# Show details for a specific plugin
zerg plugins my-gate

# List only quality gate plugins
zerg plugins --type gate

# List only lifecycle hook plugins
zerg plugins --type hook

# List only launcher plugins
zerg plugins --type launcher

# Validate plugin configuration
zerg plugins --validate
```

## CLI Flags

```
zerg plugins [PLUGIN_NAME] [OPTIONS]

Arguments:
  PLUGIN_NAME            Optional plugin name to inspect

Options:
  -f, --feature TEXT     Feature name (auto-detected)
  -t, --type TYPE        Filter by plugin type: gate|hook|launcher
  --validate             Validate plugin configuration and entry points
  --json                 Output raw JSON format
```

## Configuration

Configure plugins in `.zerg/config.yaml`:

```yaml
plugins:
  enabled: true
  hooks:
    - event: task_completed
      command: "echo task done"
      timeout: 60
    - event: level_complete
      command: "./scripts/notify-slack.sh"
      timeout: 120
  quality_gates:
    - name: custom-lint
      command: "mypy src/"
      required: true
      timeout: 300
  launchers:
    - name: k8s
      entry_point: "mypackage.launchers:K8sLauncher"
```

## Plugin Types

### Quality Gate Plugin

Quality gates run after merge and determine whether a level passes or fails.

```python
from zerg.plugins import QualityGatePlugin, GateContext
from zerg.types import GateRunResult
from zerg.constants import GateResult

class MyGate(QualityGatePlugin):
    @property
    def name(self) -> str:
        return "my-gate"

    def run(self, ctx: GateContext) -> GateRunResult:
        # Run your gate logic
        return GateRunResult(
            gate_name=self.name,
            result=GateResult.PASS,
            command="my-check",
            exit_code=0,
        )
```

### Lifecycle Hook Plugin

Lifecycle hooks react to events during rush execution. They are strictly observational and cannot modify core state.

```python
from zerg.plugins import LifecycleHookPlugin, LifecycleEvent

class MyHook(LifecycleHookPlugin):
    @property
    def name(self) -> str:
        return "my-hook"

    def on_event(self, event: LifecycleEvent) -> None:
        print(f"Event: {event.event_type}, Data: {event.data}")
```

### Launcher Plugin

Launcher plugins provide custom worker launch strategies beyond the default local process launcher.

```python
from zerg.plugins import LauncherPlugin

class MyLauncher(LauncherPlugin):
    @property
    def name(self) -> str:
        return "k8s"

    def create_launcher(self, config):
        return K8sWorkerLauncher(config)
```

## Entry Points

Register plugins via Python entry points in `pyproject.toml`:

```toml
[project.entry-points."zerg.plugins"]
my-gate = "mypackage.gates:MyGate"
my-hook = "mypackage.hooks:MyHook"
k8s = "mypackage.launchers:K8sLauncher"
```

## Lifecycle Events

| Event | When | Data |
|-------|------|------|
| task_started | Worker starts a task | task_id, worker_id, feature |
| task_completed | Task finishes (success or fail) | task_id, worker_id, success |
| level_complete | All tasks in level done | level |
| merge_complete | Level merge finished | level, merge_commit |
| rush_finished | Rush execution ends | feature |
| quality_gate_run | Gate executed | gate_name, result |
| worker_spawned | Worker process started | worker_id, feature |
| worker_exited | Worker process ended | worker_id, feature |

## Security Model

- Plugins are strictly additive — cannot modify core logic
- State views are read-only (dataclass snapshots)
- Shell hooks use `shlex.split()` (no `shell=True`)
- Timeout enforcement on all plugin and hook executions
- Plugin exceptions are caught and logged, never crash the orchestrator

## Task Tracking

On invocation, create a Claude Code Task to track this command:

Call TaskCreate:
  - subject: "[Plugins] Inspect plugin system"
  - description: "Viewing plugin configuration and registered plugins."
  - activeForm: "Inspecting plugins"

Immediately call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "in_progress"

On completion, call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "completed"

## Integration with Other Commands

```bash
# Validate plugins before starting a rush
zerg plugins --validate && zerg rush --workers=5

# Check which gates will run during merge
zerg plugins --type gate

# Inspect a specific hook configuration
zerg plugins my-hook

# Export plugin info as JSON for scripting
zerg plugins --json

# View plugin execution in logs
zerg logs --aggregate --event quality_gate_run
```
