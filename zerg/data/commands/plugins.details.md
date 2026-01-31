<!-- SPLIT: details, parent: plugins.md -->
# plugins — Detailed Reference

This file contains extended examples, templates, and edge cases.
Core instructions are in `plugins.core.md`.

# my_zerg_plugins/gates.py

from zerg.plugins import QualityGatePlugin, GateContext
from zerg.types import GateRunResult
from zerg.constants import GateResult

class SonarQubeGate(QualityGatePlugin):
    @property
    def name(self) -> str:
        return "sonarqube"

    def run(self, ctx: GateContext) -> GateRunResult:
        # Custom authentication, API calls, complex logic...
        api_key = os.getenv("SONARQUBE_TOKEN")
        result = requests.get(f"https://sonar.example.com/api/qualitygates/project_status?projectKey={ctx.feature}")

        if result.json()["projectStatus"]["status"] == "OK":
            return GateRunResult(
                gate_name=self.name,
                result=GateResult.PASS,
                command="sonarqube-api",
                exit_code=0,
                stdout=f"Quality gate passed: {result.json()}"
            )
        else:
            return GateRunResult(
                gate_name=self.name,
                result=GateResult.FAIL,
                command="sonarqube-api",
                exit_code=1,
                stderr=f"Quality gate failed: {result.json()}"
            )
```

**2. Register entry point** in `pyproject.toml`:

```toml
[project.entry-points."zerg.plugins"]
sonarqube = "my_zerg_plugins.gates:SonarQubeGate"
k8s-launcher = "my_zerg_plugins.launchers:K8sLauncherPlugin"
slack-hooks = "my_zerg_plugins.hooks:SlackNotificationHook"
```

**3. Install and run**:

```bash
pip install -e .  # Install your plugin package
/zerg:rush        # Plugins auto-discovered via entry points
```

**Discovery**: `PluginRegistry.load_entry_points("zerg.plugins")` runs on orchestrator startup

## Security Model

ZERG plugins are **strictly additive** and cannot compromise orchestrator integrity:

### Read-Only State Access

Plugins receive **immutable views** of orchestrator state:

- `GateContext` — read-only dataclass with `feature`, `level`, `cwd`, `config`
- `LifecycleEvent` — read-only dataclass with `event_type`, `data`, `timestamp`
- No access to `Orchestrator._state`, `_workers`, `_task_queue` internals

### Timeout Enforcement

- YAML hooks: 1-600 seconds (default: 60)
- YAML gates: 1-3600 seconds (default: 300)
- Python plugins: Must complete within timeout or killed

### Exception Isolation

Each plugin invocation is individually wrapped:

```python
# zerg/plugins.py:119-134
def emit_event(self, event: LifecycleEvent) -> None:
    for callback in self._hooks.get(event.event_type, []):
        try:
            callback(event)
        except Exception:
            logger.warning("Hook callback %r failed", callback, exc_info=True)
            # Execution continues — never crashes orchestrator
```

### No Shell Injection

YAML commands are parsed with `shlex.split` and executed via `subprocess.run(shell=False)`:

```python
# zerg/plugins.py:189-190
args = shlex.split(cmd)
subprocess.run(args, check=False, timeout=300)  # noqa: S603
```

### Principle of Least Privilege

- Plugins cannot modify task graph, worker state, or orchestrator decisions
- Hooks are **observers**, not **controllers**
- Gates can only report PASS/FAIL, not alter execution flow
- Launchers only spawn workers, cannot introspect orchestrator state

## Examples

### Example 1: Slack Notifications

**YAML approach**:

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

**Python approach** (for OAuth, custom formatting):

```python
# slack_plugin.py
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
                text=f"✅ Level {event.data['level']} completed",
                blocks=[{
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Feature*: {event.data['feature']}\n*Tasks*: {event.data['task_count']}\n*Time*: {event.data['elapsed_time']}s"}
                }]
            )
```

### Example 2: Custom Security Gate

```python
# security_gate.py
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
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            return GateRunResult(
                gate_name=self.name,
                result=GateResult.PASS,
                command="trivy fs",
                exit_code=0,
                stdout=result.stdout
            )
        else:
            return GateRunResult(
                gate_name=self.name,
                result=GateResult.FAIL,
                command="trivy fs",
                exit_code=result.returncode,
                stderr=result.stderr
            )
```

### Example 3: Kubernetes Launcher

```python
# k8s_launcher.py
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
        self.api.delete_namespaced_pod(name=launch_info["pod_name"], namespace="zerg")

class K8sLauncherPlugin(LauncherPlugin):
    @property
    def name(self) -> str:
        return "kubernetes"

    def create_launcher(self, config):
        return K8sLauncher(config)
```

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

## Troubleshooting

### Plugin Not Loading

**Symptoms**: Plugin registered in `pyproject.toml` but not discovered

**Fixes**:
1. Check entry point group name: `[project.entry-points."zerg.plugins"]`
2. Reinstall package: `pip install -e .`
3. Verify logs: `.zerg/logs/orchestrator.log` shows "Registered {type} plugin: {name}"

### Hook Exceptions

**Symptoms**: Hook callback fails with exception in logs

**Fixes**:
1. Check timeout — increase in YAML config
2. Verify command exists: `which <command>`
3. Check permissions — hooks run as orchestrator user
4. Review logs: `.zerg/logs/orchestrator.log` for full traceback

### Gate Failures

**Symptoms**: Quality gate reports `ERROR` instead of `PASS`/`FAIL`

**Fixes**:
1. Test gate command manually: `cd .zerg/merged && <gate_command>`
2. Check timeout — gates default to 5 minutes
3. Verify `GateRunResult` return value — must include all fields
4. Review logs: `.zerg/logs/gates/level-{N}.log`

### Launcher Plugins Ignored

**Symptoms**: `--mode {custom}` falls back to `subprocess`

**Fixes**:
1. Check launcher name matches config: `zerg_config.launcher.mode`
2. Verify `create_launcher()` returns `WorkerLauncher` subclass
3. Test plugin discovery: `python -c "from zerg.plugins import PluginRegistry; r = PluginRegistry(); r.load_entry_points(); print(r._launchers)"`

## Best Practices

### For Quality Gates

- Return `GateResult.SKIP` for gates that don't apply to current level
- Use `required: false` for informational gates (warnings only)
- Set realistic timeouts — allow 3x typical execution time
- Capture full output in `stdout`/`stderr` for debugging

### For Lifecycle Hooks

- Keep hooks fast — they block event processing
- Use async operations for slow tasks (API calls, notifications)
- Never throw exceptions — return gracefully on errors
- Log errors to plugin-specific files, not orchestrator logs

### For Launchers

- Implement proper cleanup — delete pods, VMs, temp resources
- Handle partial failures — launcher crash shouldn't orphan workers
- Support resume — launchers should be idempotent on retry
- Document authentication requirements in plugin README

### General

- Prefix all log messages with plugin name: `logger.info(f"[{self.name}] ...")`
- Expose plugin config via CLI: `--gate-config sonarqube.token=xxx`
- Version entry points: `sonarqube-v2 = "pkg:SonarQubeGateV2"` for breaking changes
- Test plugins with mock mode before production: `--mode mock`

## References

- **Plugin ABCs**: `zerg/plugins.py:51-87`
- **Plugin Registry**: `zerg/plugins.py:95-242`
- **Config Models**: `zerg/plugin_config.py:6-37`
- **Lifecycle Events**: `zerg/constants.py:143-149`
- **Example Integration**: `tests/integration/test_plugin_lifecycle.py`
- **Dogfooding E2E**: `tests/e2e/test_dogfood_plugin.py`

