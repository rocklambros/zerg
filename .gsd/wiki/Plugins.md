# Plugins

Extend ZERG with custom quality gates, lifecycle hooks, and worker launchers.

---

## Overview

The ZERG plugin system provides three extension points for customizing parallel execution workflows:

| Plugin Type | Purpose | Use Case |
|-------------|---------|----------|
| **QualityGatePlugin** | Custom validation after merges | Lint, security scans, benchmarks, compliance checks |
| **LifecycleHookPlugin** | React to events | Notifications, metrics, logging, integrations |
| **LauncherPlugin** | Custom worker environments | Kubernetes, SSH clusters, cloud VMs |

**Design Principles**:
- **Additive only** - Plugins cannot mutate orchestrator state, only observe and react
- **Fault-tolerant** - Plugin failures never crash the orchestrator; they are logged and execution continues
- **Isolated** - Each plugin invocation is wrapped in try/except for exception isolation

---

## Plugin Types

### QualityGatePlugin

Validates code quality after each level merge. Runs sequentially after built-in gates (lint, build, test).

```python
from zerg.plugins import QualityGatePlugin, GateContext
from zerg.types import GateRunResult
from zerg.constants import GateResult

class MyCustomGate(QualityGatePlugin):
    @property
    def name(self) -> str:
        return "my-custom-gate"

    def run(self, ctx: GateContext) -> GateRunResult:
        """
        Execute the quality gate check.

        Context attributes:
          - ctx.feature: str - feature name
          - ctx.level: int - level just merged
          - ctx.cwd: Path - working directory
          - ctx.config: ZergConfig - full configuration
        """
        # Run your validation logic...

        return GateRunResult(
            gate_name=self.name,
            result=GateResult.PASS,  # PASS | FAIL | SKIP | TIMEOUT | ERROR
            command="my-custom-check",
            exit_code=0,
            stdout="All checks passed",
            stderr="",
        )
```

**Gate Results**:
| Result | Meaning |
|--------|---------|
| `PASS` | Gate passed, continue execution |
| `FAIL` | Gate failed; blocks merge if `required: true` |
| `SKIP` | Gate not applicable to this level |
| `TIMEOUT` | Gate exceeded time limit |
| `ERROR` | Gate threw an exception |

**Execution Flow**: Built-in gates (lint, build, test) → Plugin gates (registered order) → Merge completes

### LifecycleHookPlugin

Observes ZERG lifecycle events without blocking execution. Ideal for notifications, metrics collection, and external integrations.

```python
from zerg.plugins import LifecycleHookPlugin, LifecycleEvent

class MyNotificationHook(LifecycleHookPlugin):
    @property
    def name(self) -> str:
        return "slack-notifier"

    def on_event(self, event: LifecycleEvent) -> None:
        """
        Handle a lifecycle event.

        Event attributes:
          - event.event_type: str - from PluginHookEvent enum
          - event.data: dict - event-specific payload
          - event.timestamp: datetime - when event occurred
        """
        if event.event_type == "task_completed":
            task_id = event.data["task_id"]
            # Send notification...
```

**Available Lifecycle Events**:

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

Provides custom worker execution environments beyond the built-in `subprocess` and `container` modes.

```python
from zerg.plugins import LauncherPlugin
from zerg.launcher import WorkerLauncher

class K8sLauncherPlugin(LauncherPlugin):
    @property
    def name(self) -> str:
        return "kubernetes"

    def create_launcher(self, config) -> WorkerLauncher:
        """
        Create and return a WorkerLauncher instance.

        The returned launcher must implement:
          - launch(worker_id, task_id) -> dict
          - wait(launch_info) -> int
          - cleanup(launch_info) -> None
        """
        return K8sWorkerLauncher(config)
```

**Execution Flow**: Check launcher plugins → Fallback to built-in (`subprocess` | `container`)

---

## Configuration

### YAML Configuration in `.zerg/config.yaml`

ZERG supports two simple configuration methods for plugins without writing Python code.

#### YAML Hooks

Trigger shell commands on lifecycle events:

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

    - event: merge_complete
      command: |
        python scripts/generate_report.py \
          --level {level} \
          --feature {feature}
      timeout: 180
```

**Hook Configuration Fields**:

| Field | Description | Default |
|-------|-------------|---------|
| `event` | Event type from lifecycle event table | Required |
| `command` | Shell command (parsed with `shlex.split`, no `shell=True`) | Required |
| `timeout` | Max execution time in seconds (1-600) | 60 |

**Variable Substitution**: `{level}`, `{feature}`, `{task_id}`, `{worker_id}` are replaced from event data.

#### YAML Quality Gates

Add custom quality checks:

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

    - name: type-check
      command: mypy src/ --strict
      required: true
      timeout: 180
```

**Gate Configuration Fields**:

| Field | Description | Default |
|-------|-------------|---------|
| `name` | Unique gate identifier | Required |
| `command` | Shell command to execute | Required |
| `required` | If `true`, failure blocks merge | `false` |
| `timeout` | Max execution time in seconds (1-3600) | 300 |

---

## Python Entry Points

For complex plugins requiring custom logic, authentication, or API calls, register Python classes via entry points.

### Registration via `pyproject.toml`

```toml
[project.entry-points."zerg.plugins"]
sonarqube = "my_zerg_plugins.gates:SonarQubeGate"
k8s-launcher = "my_zerg_plugins.launchers:K8sLauncherPlugin"
slack-hooks = "my_zerg_plugins.hooks:SlackNotificationHook"
```

### Registration via `setup.py`

```python
from setuptools import setup

setup(
    name="my-zerg-plugins",
    entry_points={
        "zerg.plugins": [
            "sonarqube = my_zerg_plugins.gates:SonarQubeGate",
            "k8s-launcher = my_zerg_plugins.launchers:K8sLauncherPlugin",
            "slack-hooks = my_zerg_plugins.hooks:SlackNotificationHook",
        ],
    },
)
```

### Installation and Discovery

```bash
# Install your plugin package
pip install -e ./my-zerg-plugins

# Plugins are auto-discovered on orchestrator startup via:
# PluginRegistry.load_entry_points("zerg.plugins")

# Run ZERG - plugins are automatically loaded
/zerg:rush --workers=5
```

---

## Built-in Plugins

### Context Engineering Plugin

ZERG includes a built-in context engineering plugin that minimizes token usage across workers.

```yaml
# .zerg/config.yaml
plugins:
  context_engineering:
    enabled: true
    command_splitting: true
    security_rule_filtering: true
    task_context_budget_tokens: 4000
    fallback_to_full: true
```

**Features**:
- **Command Splitting** - Large command files split into `.core.md` (essential) and `.details.md` (reference)
- **Task-Scoped Context** - Each task receives filtered context relevant to its files and description
- **Security Rule Filtering** - Rules filtered by file extension (.py → Python rules, .js → JavaScript rules)

**Monitoring**: Use `/zerg:status` to view context budget statistics and token savings.

---

## Examples

### Example 1: Slack Notifications

**YAML (Simple)**:
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

**Python (With OAuth)**:
```python
from zerg.plugins import LifecycleHookPlugin, LifecycleEvent
from slack_sdk import WebClient
import os

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
                text=f"Level {event.data['level']} completed in {event.data['elapsed_time']}s",
            )
        elif event.event_type == "rush_finished":
            self.client.chat_postMessage(
                channel="#zerg-builds",
                text=f"Feature {event.data['feature']} complete! {event.data['tasks_completed']} tasks in {event.data['total_time']}s",
            )
```

### Example 2: Security Gate (Trivy)

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
        try:
            result = subprocess.run(
                ["trivy", "fs", "--severity", "HIGH,CRITICAL", str(ctx.cwd)],
                capture_output=True,
                text=True,
                timeout=300
            )
            return GateRunResult(
                gate_name=self.name,
                result=GateResult.PASS if result.returncode == 0 else GateResult.FAIL,
                command="trivy fs --severity HIGH,CRITICAL",
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        except subprocess.TimeoutExpired:
            return GateRunResult(
                gate_name=self.name,
                result=GateResult.TIMEOUT,
                command="trivy fs",
                exit_code=-1,
                stdout="",
                stderr="Scan timed out after 300 seconds",
            )
```

### Example 3: SonarQube Integration

```python
from zerg.plugins import QualityGatePlugin, GateContext
from zerg.types import GateRunResult
from zerg.constants import GateResult
import requests
import os

class SonarQubeGate(QualityGatePlugin):
    @property
    def name(self) -> str:
        return "sonarqube"

    def run(self, ctx: GateContext) -> GateRunResult:
        token = os.getenv("SONAR_TOKEN")
        server = os.getenv("SONAR_URL", "http://localhost:9000")
        project = ctx.config.get("sonar_project", ctx.feature)

        response = requests.get(
            f"{server}/api/qualitygates/project_status",
            params={"projectKey": project},
            auth=(token, ""),
            timeout=30
        )

        data = response.json()
        status = data.get("projectStatus", {}).get("status", "ERROR")

        return GateRunResult(
            gate_name=self.name,
            result=GateResult.PASS if status == "OK" else GateResult.FAIL,
            command=f"sonarqube-api project_status {project}",
            exit_code=0 if status == "OK" else 1,
            stdout=f"SonarQube status: {status}",
            stderr="",
        )
```

### Example 4: Kubernetes Launcher

```python
from zerg.plugins import LauncherPlugin
from zerg.launcher import WorkerLauncher
from kubernetes import client, config
import time

class K8sLauncher(WorkerLauncher):
    def __init__(self, zerg_config):
        super().__init__(zerg_config)
        config.load_kube_config()
        self.api = client.CoreV1Api()
        self.namespace = zerg_config.get("k8s_namespace", "zerg")

    def launch(self, worker_id: str, task_id: str) -> dict:
        pod = client.V1Pod(
            metadata=client.V1ObjectMeta(
                name=f"zerg-worker-{worker_id}",
                labels={"app": "zerg-worker", "task": task_id}
            ),
            spec=client.V1PodSpec(
                restart_policy="Never",
                containers=[client.V1Container(
                    name="worker",
                    image="claude-code:latest",
                    env=[
                        client.V1EnvVar(name="TASK_ID", value=task_id),
                        client.V1EnvVar(name="WORKER_ID", value=worker_id),
                    ],
                    resources=client.V1ResourceRequirements(
                        requests={"cpu": "500m", "memory": "512Mi"},
                        limits={"cpu": "2", "memory": "4Gi"}
                    )
                )]
            )
        )
        self.api.create_namespaced_pod(namespace=self.namespace, body=pod)
        return {"pod_name": f"zerg-worker-{worker_id}", "namespace": self.namespace}

    def wait(self, launch_info: dict) -> int:
        pod_name = launch_info["pod_name"]
        while True:
            pod = self.api.read_namespaced_pod(
                name=pod_name, namespace=launch_info["namespace"]
            )
            if pod.status.phase in ["Succeeded", "Failed"]:
                return 0 if pod.status.phase == "Succeeded" else 1
            time.sleep(5)

    def cleanup(self, launch_info: dict) -> None:
        self.api.delete_namespaced_pod(
            name=launch_info["pod_name"],
            namespace=launch_info["namespace"]
        )

class K8sLauncherPlugin(LauncherPlugin):
    @property
    def name(self) -> str:
        return "kubernetes"

    def create_launcher(self, config):
        return K8sLauncher(config)
```

**Configuration**:
```yaml
# .zerg/config.yaml
launcher:
  mode: kubernetes  # Use the K8s launcher plugin
  k8s_namespace: zerg-workers
```

### Example 5: Metrics Collection Hook

```python
from zerg.plugins import LifecycleHookPlugin, LifecycleEvent
import statsd
import os

class MetricsHook(LifecycleHookPlugin):
    def __init__(self):
        self.client = statsd.StatsClient(
            host=os.getenv("STATSD_HOST", "localhost"),
            port=int(os.getenv("STATSD_PORT", 8125)),
            prefix="zerg"
        )

    @property
    def name(self) -> str:
        return "metrics"

    def on_event(self, event: LifecycleEvent) -> None:
        if event.event_type == "task_completed":
            self.client.timing("task.duration", event.data["duration"] * 1000)
            self.client.incr("task.completed")
        elif event.event_type == "level_complete":
            self.client.timing("level.duration", event.data["elapsed_time"] * 1000)
            self.client.gauge("level.tasks", event.data["task_count"])
        elif event.event_type == "quality_gate_run":
            result = event.data["result"]
            self.client.incr(f"gate.{event.data['gate_name']}.{result}")
```

---

## Security Model

### Read-Only State Access

Plugins receive immutable views of orchestrator state:
- **GateContext** - Read-only with `feature`, `level`, `cwd`, `config`
- **LifecycleEvent** - Read-only with `event_type`, `data`, `timestamp`
- No access to `Orchestrator._state`, `_workers`, or `_task_queue`

### Timeout Enforcement

| Plugin Type | Timeout Range | Default |
|-------------|---------------|---------|
| YAML hooks | 1-600 seconds | 60s |
| YAML gates | 1-3600 seconds | 300s |
| Python plugins | Configurable | 300s |

Plugins exceeding timeout are terminated and report `TIMEOUT` result.

### Exception Isolation

Each plugin invocation is individually wrapped in try/except. A failing plugin never crashes the orchestrator.

### No Shell Injection

YAML commands are parsed with `shlex.split` and executed via `subprocess.run(shell=False)`. No shell metacharacter expansion.

---

## Best Practices

### Quality Gates

- Return `GateResult.SKIP` for gates that don't apply to the current level
- Use `required: false` for informational gates (warnings only)
- Set realistic timeouts - allow 3x typical execution time
- Capture full output in `stdout`/`stderr` for debugging
- Test gate commands manually before integration

### Lifecycle Hooks

- Keep hooks fast - they block event processing
- Use async operations for slow tasks (API calls, notifications)
- Never throw exceptions - return gracefully on errors
- Log errors internally rather than failing silently

### Launchers

- Implement proper cleanup - delete pods, VMs, temp resources
- Handle partial failures - launcher crash shouldn't orphan workers
- Support resume - launchers should be idempotent on retry
- Include health checks and liveness probes

### General

- Prefix all log messages with plugin name: `logger.info(f"[{self.name}] ...")`
- Version entry points for breaking changes: `sonarqube-v2 = "pkg:GateV2"`
- Test plugins with mock mode before production
- Document environment variables and configuration requirements

---

## Troubleshooting

| Problem | Symptoms | Fix |
|---------|----------|-----|
| Plugin not loading | Not discovered on startup | Check entry point group: `[project.entry-points."zerg.plugins"]`, reinstall with `pip install -e .` |
| Hook exceptions | Exception in logs | Check timeout, verify command exists (`which <cmd>`), check permissions |
| Gate reports ERROR | `ERROR` instead of `PASS`/`FAIL` | Test gate command manually, check `GateRunResult` return value |
| Launcher ignored | Falls back to subprocess | Check launcher name matches config `mode`, verify `create_launcher()` returns `WorkerLauncher` |
| Variable substitution fails | `{level}` not replaced | Ensure event type provides the variable in its data payload |
| Timeout too aggressive | Frequent `TIMEOUT` results | Increase timeout in YAML config or handle timeout in Python plugin |

---

## Code References

| Component | Location |
|-----------|----------|
| Plugin ABCs | `zerg/plugins.py` |
| Plugin Registry | `zerg/plugins.py` |
| Config Models | `zerg/plugin_config.py` |
| Lifecycle Events | `zerg/constants.py` |
| Integration Tests | `tests/integration/test_plugin_lifecycle.py` |

---

## See Also

- [[Configuration]] - Full config.yaml reference including plugin settings
- [[Command-Reference]] - `/zerg:plugins` command documentation
- [[Home]] - ZERG overview and quick start
