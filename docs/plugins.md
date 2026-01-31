# ZERG Plugin System

Extend ZERG with custom quality gates, lifecycle hooks, and worker launchers.

---

## Overview

The ZERG plugin system provides three extension points:

1. **Quality Gate Plugins** — Custom validation after merges (lint, security scans, benchmarks)
2. **Lifecycle Hook Plugins** — React to events (task starts/completes, level finishes, merges)
3. **Launcher Plugins** — Custom worker execution environments (Kubernetes, SSH clusters, cloud VMs)

All plugins are **additive only** — they cannot mutate orchestrator state, only observe and react. Plugin failures never crash the orchestrator; they are logged and execution continues.

---

## Quick Start

### Simple: YAML Hooks

Add shell commands triggered by lifecycle events in `.zerg/config.yaml`:

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

### Simple: YAML Quality Gates

Add custom quality gate commands:

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

### Advanced: Python Entry Points

For complex logic, authentication, or API calls, create Python plugin classes:

```python
# my_zerg_plugins/gates.py
from zerg.plugins import QualityGatePlugin, GateContext
from zerg.types import GateRunResult
from zerg.constants import GateResult

class SonarQubeGate(QualityGatePlugin):
    @property
    def name(self) -> str:
        return "sonarqube"

    def run(self, ctx: GateContext) -> GateRunResult:
        # ctx.feature, ctx.level, ctx.cwd, ctx.config available
        return GateRunResult(
            gate_name=self.name,
            result=GateResult.PASS,
            command="sonarqube-api",
            exit_code=0,
            stdout="Quality gate passed",
        )
```

Register in `pyproject.toml`:

```toml
[project.entry-points."zerg.plugins"]
sonarqube = "my_zerg_plugins.gates:SonarQubeGate"
```

Install and run:

```bash
pip install -e .
/zerg:rush  # Plugins auto-discovered via entry points
```

---

## Plugin Types

### QualityGatePlugin

Validates code quality after each level merge. Runs sequentially after built-in gates.

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

### LifecycleHookPlugin

Observes ZERG lifecycle events without blocking execution.

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
            # Send notification...
```

**Available events**:

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

### LauncherPlugin

Provides custom worker execution environments beyond `subprocess` and `container`.

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

The returned `WorkerLauncher` subclass must implement `launch()`, `wait()`, and `cleanup()`.

---

## Configuration

### YAML Hooks

```yaml
plugins:
  hooks:
    - event: task_completed
      command: echo "Task completed at $(date)"
      timeout: 60
```

| Field | Description | Default |
|-------|-------------|---------|
| `event` | Event type from the lifecycle event table | Required |
| `command` | Shell command (parsed with `shlex.split`, no `shell=True`) | Required |
| `timeout` | Max execution time in seconds (1-600) | 60 |

**Variable substitution**: `{level}`, `{feature}`, `{task_id}`, `{worker_id}` are replaced from event data.

### YAML Quality Gates

```yaml
plugins:
  quality_gates:
    - name: security-scan
      command: bandit -r src/ --severity medium
      required: false
      timeout: 300
```

| Field | Description | Default |
|-------|-------------|---------|
| `name` | Unique gate identifier | Required |
| `command` | Shell command to execute | Required |
| `required` | If `true`, failure blocks merge | `false` |
| `timeout` | Max execution time in seconds (1-3600) | 300 |

### Python Entry Points

Register plugin classes in your package's `pyproject.toml`:

```toml
[project.entry-points."zerg.plugins"]
sonarqube = "my_zerg_plugins.gates:SonarQubeGate"
k8s-launcher = "my_zerg_plugins.launchers:K8sLauncherPlugin"
slack-hooks = "my_zerg_plugins.hooks:SlackNotificationHook"
```

Discovery happens automatically via `PluginRegistry.load_entry_points("zerg.plugins")` on orchestrator startup.

---

## Security Model

### Read-Only State Access

Plugins receive immutable views of orchestrator state:
- `GateContext` — read-only with `feature`, `level`, `cwd`, `config`
- `LifecycleEvent` — read-only with `event_type`, `data`, `timestamp`
- No access to `Orchestrator._state`, `_workers`, or `_task_queue`

### Timeout Enforcement

- YAML hooks: 1-600 seconds (default: 60)
- YAML gates: 1-3600 seconds (default: 300)
- Python plugins: Must complete within timeout or killed

### Exception Isolation

Each plugin invocation is individually wrapped in try/except. A failing plugin never crashes the orchestrator.

### No Shell Injection

YAML commands are parsed with `shlex.split` and executed via `subprocess.run(shell=False)`.

---

## Examples

### Slack Notifications

**YAML**:
```yaml
plugins:
  hooks:
    - event: level_complete
      command: |
        curl -X POST https://hooks.slack.com/services/YOUR/WEBHOOK/URL \
          -H 'Content-Type: application/json' \
          -d '{"text":"Level {level} completed for feature {feature}"}'
      timeout: 30
```

**Python** (for OAuth, custom formatting):
```python
from zerg.plugins import LifecycleHookPlugin, LifecycleEvent
from slack_sdk import WebClient

class SlackNotifier(LifecycleHookPlugin):
    def __init__(self):
        self.client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

    @property
    def name(self) -> str:
        return "slack-notifier"

    def on_event(self, event: LifecycleEvent) -> None:
        if event.event_type == "level_complete":
            self.client.chat_postMessage(
                channel="#zerg-builds",
                text=f"Level {event.data['level']} completed",
            )
```

### Security Gate (Trivy)

```python
from zerg.plugins import QualityGatePlugin, GateContext
from zerg.types import GateRunResult
from zerg.constants import GateResult
import subprocess

class TrivyScanGate(QualityGatePlugin):
    @property
    def name(self) -> str:
        return "trivy-scan"

    def run(self, ctx: GateContext) -> GateRunResult:
        result = subprocess.run(
            ["trivy", "fs", "--severity", "HIGH,CRITICAL", str(ctx.cwd)],
            capture_output=True, text=True, timeout=300
        )
        return GateRunResult(
            gate_name=self.name,
            result=GateResult.PASS if result.returncode == 0 else GateResult.FAIL,
            command="trivy fs",
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
```

### Kubernetes Launcher

```python
from zerg.plugins import LauncherPlugin
from zerg.launcher import WorkerLauncher
from kubernetes import client, config

class K8sLauncher(WorkerLauncher):
    def __init__(self, zerg_config):
        super().__init__(zerg_config)
        config.load_kube_config()
        self.api = client.CoreV1Api()

    def launch(self, worker_id: str, task_id: str) -> dict:
        pod = client.V1Pod(
            metadata=client.V1ObjectMeta(name=f"zerg-{worker_id}"),
            spec=client.V1PodSpec(
                containers=[client.V1Container(
                    name="worker",
                    image="claude-code:latest",
                    env=[{"name": "TASK_ID", "value": task_id}]
                )]
            )
        )
        self.api.create_namespaced_pod(namespace="zerg", body=pod)
        return {"pod_name": f"zerg-{worker_id}"}

    def wait(self, launch_info: dict) -> int:
        # Poll pod status...
        pass

    def cleanup(self, launch_info: dict) -> None:
        self.api.delete_namespaced_pod(
            name=launch_info["pod_name"], namespace="zerg"
        )

class K8sLauncherPlugin(LauncherPlugin):
    @property
    def name(self) -> str:
        return "kubernetes"

    def create_launcher(self, config):
        return K8sLauncher(config)
```

---

## Best Practices

### Quality Gates
- Return `GateResult.SKIP` for gates that don't apply to the current level
- Use `required: false` for informational gates (warnings only)
- Set realistic timeouts — allow 3x typical execution time
- Capture full output in `stdout`/`stderr` for debugging

### Lifecycle Hooks
- Keep hooks fast — they block event processing
- Use async operations for slow tasks (API calls, notifications)
- Never throw exceptions — return gracefully on errors

### Launchers
- Implement proper cleanup — delete pods, VMs, temp resources
- Handle partial failures — launcher crash shouldn't orphan workers
- Support resume — launchers should be idempotent on retry

### General
- Prefix all log messages with plugin name: `logger.info(f"[{self.name}] ...")`
- Version entry points for breaking changes: `sonarqube-v2 = "pkg:GateV2"`
- Test plugins with mock mode before production

---

## Troubleshooting

| Problem | Symptoms | Fix |
|---------|----------|-----|
| Plugin not loading | Not discovered on startup | Check entry point group: `[project.entry-points."zerg.plugins"]`, reinstall with `pip install -e .` |
| Hook exceptions | Exception in logs | Check timeout, verify command exists (`which <cmd>`), check permissions |
| Gate reports ERROR | `ERROR` instead of `PASS`/`FAIL` | Test gate command manually, check `GateRunResult` return value |
| Launcher ignored | Falls back to subprocess | Check launcher name matches config, verify `create_launcher()` returns `WorkerLauncher` |

---

## Code References

- **Plugin ABCs**: `zerg/plugins.py`
- **Plugin Registry**: `zerg/plugins.py`
- **Config Models**: `zerg/plugin_config.py`
- **Lifecycle Events**: `zerg/constants.py`
- **Integration Tests**: `tests/integration/test_plugin_lifecycle.py`
