# Plugins

Extend ZERG with custom quality gates, lifecycle hooks, and worker launchers.

---

## Why Extend ZERG?

ZERG handles parallel task execution beautifully out of the box. But every team has unique needs. Maybe you need to integrate with tools your organization already uses, or enforce policies specific to your codebase. The plugin system exists precisely for these real-world scenarios.

### Real-World Use Cases

**"My team uses SonarQube for code quality - I want ZERG to run it automatically"**

Your organization has invested in SonarQube for code analysis. Rather than running it manually after ZERG completes, you can create a quality gate plugin that checks SonarQube status after every merge. If the quality gate fails, ZERG stops before broken code propagates further.

**"We need Slack notifications when workers finish"**

Your distributed team wants visibility into build progress. A lifecycle hook can send Slack messages when levels complete, when quality gates pass or fail, or when the entire rush finishes. Everyone stays informed without watching terminals.

**"Our CI requires specific test commands"**

Your project has custom test infrastructure - maybe integration tests that hit staging databases, or performance benchmarks that run on dedicated hardware. Quality gate plugins let you wire in whatever validation commands your workflow requires.

**"We run workers on Kubernetes, not local Docker"**

Your infrastructure team manages a Kubernetes cluster for builds. A launcher plugin lets ZERG spawn workers as Kubernetes pods instead of local containers, giving you the scaling and resource management you already have in place.

---

## Understanding Plugin Types

ZERG provides three extension points. Each serves a distinct purpose, and choosing the right one depends on what you're trying to accomplish.

### Quality Gates: Validating Code After Merges

**What they are**: Quality gates run after ZERG merges completed tasks from a level. They're your checkpoint to verify the merged code meets your standards before workers start the next level.

**Why they matter**: Without quality gates, a bug in Level 1 could propagate through Levels 2, 3, and 4 before anyone notices. Quality gates catch problems early, when they're cheapest to fix.

**When to use them**:
- Running static analysis tools (linters, type checkers, security scanners)
- Checking code coverage thresholds
- Validating API contracts or schema migrations
- Enforcing style guides or complexity limits

**How they work**: After ZERG merges all branches from a level, it runs quality gates in order: built-in gates (lint, build, test) first, then your custom gates. If a required gate fails, the rush stops. If an optional gate fails, ZERG logs a warning and continues.

### Lifecycle Hooks: Observing Events

**What they are**: Lifecycle hooks get notified when things happen in ZERG - a task starts, a worker spawns, a level completes. They observe without blocking.

**Why they matter**: Visibility is crucial for distributed systems. When five workers are running in parallel, you need ways to track progress, collect metrics, and alert on problems.

**When to use them**:
- Sending notifications (Slack, email, PagerDuty)
- Collecting metrics (Datadog, Prometheus, StatsD)
- Logging to external systems (Splunk, ELK)
- Triggering downstream workflows

**How they work**: ZERG emits events at key moments. Your hook receives the event and does something with it - send a message, increment a counter, write a log. The hook should be fast and never throw exceptions.

### Custom Launchers: Running Workers Your Way

**What they are**: Launchers control how ZERG spawns worker processes. The built-in launchers use subprocesses or Docker containers. Custom launchers let you use anything else.

**Why they matter**: Different environments have different constraints. A local development machine runs workers differently than a production Kubernetes cluster or a fleet of EC2 instances.

**When to use them**:
- Running workers on Kubernetes
- Spawning workers on remote SSH hosts
- Using cloud-specific compute (AWS Batch, GCP Cloud Run)
- Integrating with job schedulers (SLURM, PBS)

**How they work**: When ZERG needs a new worker, it asks the launcher to create one. Your launcher handles the specifics - spinning up a pod, SSHing to a host, whatever your infrastructure requires.

---

## Your First Plugin: A Step-by-Step Tutorial

Let's build a simple quality gate plugin together. We'll create a plugin that checks for TODO comments in code - a common "don't ship this" indicator.

### Step 1: Create the Plugin File

First, create a directory structure for your plugins. This keeps them organized and makes packaging easier later.

```bash
mkdir -p my_zerg_plugins
touch my_zerg_plugins/__init__.py
touch my_zerg_plugins/gates.py
```

**Why this structure?** Python packages need an `__init__.py` file. Putting gates in their own module keeps things organized as you add more plugins.

### Step 2: Write the Plugin Class

Open `my_zerg_plugins/gates.py` and add:

```python
"""Custom quality gate that checks for TODO comments."""

import subprocess
from zerg.plugins import QualityGatePlugin, GateContext
from zerg.types import GateRunResult
from zerg.constants import GateResult


class TodoCheckGate(QualityGatePlugin):
    """Fail the build if TODO comments exist in Python files."""

    @property
    def name(self) -> str:
        """Return a unique identifier for this gate.

        This name appears in logs and status output.
        Choose something descriptive and kebab-case.
        """
        return "todo-check"

    def run(self, ctx: GateContext) -> GateRunResult:
        """Execute the quality gate check.

        Args:
            ctx: Context with feature name, level, working directory, and config.

        Returns:
            GateRunResult indicating pass, fail, or other status.
        """
        # Use grep to find TODO comments in Python files
        result = subprocess.run(
            ["grep", "-r", "--include=*.py", "TODO", str(ctx.cwd)],
            capture_output=True,
            text=True
        )

        # grep returns 0 if matches found, 1 if no matches, 2 on error
        if result.returncode == 1:
            # No TODOs found - that's what we want!
            return GateRunResult(
                gate_name=self.name,
                result=GateResult.PASS,
                command="grep -r --include=*.py TODO",
                exit_code=0,
                stdout="No TODO comments found",
                stderr="",
            )
        elif result.returncode == 0:
            # TODOs found - fail the gate
            return GateRunResult(
                gate_name=self.name,
                result=GateResult.FAIL,
                command="grep -r --include=*.py TODO",
                exit_code=1,
                stdout=result.stdout,
                stderr="TODO comments must be resolved before merge",
            )
        else:
            # grep error
            return GateRunResult(
                gate_name=self.name,
                result=GateResult.ERROR,
                command="grep -r --include=*.py TODO",
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
```

**Understanding the code**:

- `QualityGatePlugin` is the base class your plugin extends
- `name` property gives your plugin a unique identifier
- `run()` method does the actual work and returns a `GateRunResult`
- `GateContext` provides information about the current state (feature name, level, working directory)
- `GateResult` enum has five states: `PASS`, `FAIL`, `SKIP`, `TIMEOUT`, `ERROR`

### Step 3: Register the Plugin

ZERG discovers plugins through Python entry points. Create a `pyproject.toml` in your plugin directory:

```toml
[build-system]
requires = ["setuptools>=45"]
build-backend = "setuptools.build_meta"

[project]
name = "my-zerg-plugins"
version = "0.1.0"
description = "Custom ZERG plugins for my team"
requires-python = ">=3.10"
dependencies = ["zerg"]

[project.entry-points."zerg.plugins"]
todo-check = "my_zerg_plugins.gates:TodoCheckGate"
```

**Why entry points?** Entry points let Python packages advertise functionality. When ZERG starts, it scans for packages that registered plugins under `"zerg.plugins"`. This means you can install plugins from anywhere - local directories, private PyPI servers, public packages.

### Step 4: Install and Test

Install your plugin in development mode so changes take effect immediately:

```bash
pip install -e ./my_zerg_plugins
```

Now test it! Create a test file with a TODO:

```bash
echo "# TODO: remove this before shipping" > /tmp/test_todo.py
cd /tmp
grep -r --include=*.py TODO .  # Should find the TODO
```

Run ZERG on a feature. Your gate will run after each level merge.

**Verifying it works**:
1. Check ZERG startup logs - you should see your plugin discovered
2. After a level merge, look for `todo-check` in the gate execution output
3. If TODOs exist in the merged code, your gate should fail

### Step 5: Make It Configurable (Optional Enhancement)

Real plugins often need configuration. Let's make our TODO checker configurable:

```python
class TodoCheckGate(QualityGatePlugin):
    @property
    def name(self) -> str:
        return "todo-check"

    def run(self, ctx: GateContext) -> GateRunResult:
        # Read configuration with sensible defaults
        extensions = ctx.config.get("todo_check_extensions", ["*.py", "*.js", "*.ts"])
        ignore_dirs = ctx.config.get("todo_check_ignore", ["tests", "vendor"])

        # Build grep command
        cmd = ["grep", "-r"]
        for ext in extensions:
            cmd.extend(["--include", ext])
        for ignore in ignore_dirs:
            cmd.extend(["--exclude-dir", ignore])
        cmd.extend(["TODO", str(ctx.cwd)])

        # ... rest of the method
```

Now users can configure the plugin in `.zerg/config.yaml`:

```yaml
todo_check_extensions:
  - "*.py"
  - "*.go"
todo_check_ignore:
  - "tests"
  - "third_party"
```

---

## YAML Configuration: The Simple Path

Not every plugin needs Python code. For straightforward shell commands, ZERG supports YAML-based configuration. This is often the fastest way to integrate existing tools.

### YAML Quality Gates

Add custom quality checks directly in `.zerg/config.yaml`:

```yaml
plugins:
  enabled: true

  quality_gates:
    # Security scanning with Bandit
    - name: security-scan
      command: bandit -r src/ --severity medium
      required: false  # Warn but don't block
      timeout: 300

    # Complexity checking with Radon
    - name: complexity-check
      command: radon cc src/ --min B
      required: true   # Block if too complex
      timeout: 120

    # Type checking with mypy
    - name: type-check
      command: mypy src/ --strict
      required: true
      timeout: 180
```

**Understanding the fields**:

| Field | What it means | Example |
|-------|---------------|---------|
| `name` | Unique identifier for logs and status | `security-scan` |
| `command` | Shell command to run | `bandit -r src/` |
| `required` | If `true`, failure blocks the merge | `true` or `false` |
| `timeout` | Maximum seconds to run | `300` |

**When to use YAML gates**: When your check is a single command with a pass/fail exit code. If you need custom logic, API calls, or complex result parsing, use a Python plugin instead.

### YAML Lifecycle Hooks

Trigger shell commands when events happen:

```yaml
plugins:
  hooks:
    # Log task completions to a file
    - event: task_completed
      command: echo "Task {task_id} completed at $(date)" >> /var/log/zerg.log
      timeout: 10

    # Notify team when levels complete
    - event: level_complete
      command: ./scripts/notify-slack.sh "Level {level} done for {feature}"
      timeout: 30

    # Generate reports after merges
    - event: merge_complete
      command: python scripts/generate_report.py --level {level} --feature {feature}
      timeout: 120
```

**Variable substitution**: ZERG replaces `{variable}` placeholders with values from the event. Available variables depend on the event type:

| Event | Available Variables |
|-------|---------------------|
| `task_started` | `{task_id}`, `{worker_id}`, `{level}` |
| `task_completed` | `{task_id}`, `{worker_id}`, `{duration}` |
| `level_complete` | `{level}`, `{task_count}`, `{elapsed_time}` |
| `merge_complete` | `{level}`, `{feature}`, `{branch_count}` |
| `rush_started` | `{feature}`, `{workers}` |
| `rush_finished` | `{feature}`, `{total_time}`, `{tasks_completed}` |

---

## Complete Examples

These examples show real-world plugin patterns you can adapt for your needs.

### Example 1: Slack Notifications

**The story**: Your team uses Slack for communication. You want automatic updates in a `#builds` channel when ZERG makes progress.

**Simple version (YAML with webhook)**:

```yaml
plugins:
  hooks:
    - event: level_complete
      command: |
        curl -X POST https://hooks.slack.com/services/YOUR/WEBHOOK/URL \
          -H 'Content-Type: application/json' \
          -d '{"text":"Level {level} completed for feature {feature}"}'
      timeout: 30

    - event: rush_finished
      command: |
        curl -X POST https://hooks.slack.com/services/YOUR/WEBHOOK/URL \
          -H 'Content-Type: application/json' \
          -d '{"text":"Rush complete! {tasks_completed} tasks finished."}'
      timeout: 30
```

**Full-featured version (Python with Slack SDK)**:

```python
"""Slack notification hook with rich formatting and OAuth."""

from zerg.plugins import LifecycleHookPlugin, LifecycleEvent
from slack_sdk import WebClient
import os


class SlackNotifier(LifecycleHookPlugin):
    """Send formatted Slack messages for ZERG events."""

    def __init__(self):
        # Initialize Slack client with bot token from environment
        self.client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))
        self.channel = os.getenv("SLACK_CHANNEL", "#zerg-builds")

    @property
    def name(self) -> str:
        return "slack-notifier"

    def on_event(self, event: LifecycleEvent) -> None:
        """Handle lifecycle events and send appropriate notifications."""

        if event.event_type == "level_complete":
            self._notify_level_complete(event)
        elif event.event_type == "quality_gate_run":
            self._notify_gate_result(event)
        elif event.event_type == "rush_finished":
            self._notify_rush_complete(event)

    def _notify_level_complete(self, event: LifecycleEvent) -> None:
        """Send level completion notification."""
        level = event.data["level"]
        elapsed = event.data["elapsed_time"]
        tasks = event.data["task_count"]

        self.client.chat_postMessage(
            channel=self.channel,
            text=f"Level {level} completed",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":white_check_mark: *Level {level} Complete*\n"
                                f"{tasks} tasks finished in {elapsed:.1f}s"
                    }
                }
            ]
        )

    def _notify_gate_result(self, event: LifecycleEvent) -> None:
        """Send notification only for failed gates."""
        if event.data["result"] != "FAIL":
            return

        gate_name = event.data["gate_name"]
        self.client.chat_postMessage(
            channel=self.channel,
            text=f"Quality gate {gate_name} failed",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":x: *Quality Gate Failed*\n"
                                f"Gate `{gate_name}` failed at level {event.data['level']}"
                    }
                }
            ]
        )

    def _notify_rush_complete(self, event: LifecycleEvent) -> None:
        """Send rush completion summary."""
        feature = event.data["feature"]
        total_time = event.data["total_time"]
        tasks = event.data["tasks_completed"]

        self.client.chat_postMessage(
            channel=self.channel,
            text=f"Feature {feature} complete!",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":tada: *Rush Complete: {feature}*\n"
                                f"{tasks} tasks completed in {total_time:.1f}s"
                    }
                }
            ]
        )
```

### Example 2: SonarQube Integration

**The story**: Your organization uses SonarQube for code analysis. You want ZERG to check the quality gate status and block merges if SonarQube says the code isn't ready.

```python
"""SonarQube quality gate integration."""

from zerg.plugins import QualityGatePlugin, GateContext
from zerg.types import GateRunResult
from zerg.constants import GateResult
import requests
import os


class SonarQubeGate(QualityGatePlugin):
    """Check SonarQube quality gate status after merges."""

    @property
    def name(self) -> str:
        return "sonarqube"

    def run(self, ctx: GateContext) -> GateRunResult:
        """Query SonarQube API for project quality gate status."""

        # Get configuration from environment
        token = os.getenv("SONAR_TOKEN")
        server = os.getenv("SONAR_URL", "http://localhost:9000")

        # Project key can be configured or default to feature name
        project = ctx.config.get("sonar_project", ctx.feature)

        if not token:
            return GateRunResult(
                gate_name=self.name,
                result=GateResult.SKIP,
                command="sonarqube-api",
                exit_code=0,
                stdout="Skipped: SONAR_TOKEN not configured",
                stderr="",
            )

        try:
            # Query SonarQube quality gate status
            response = requests.get(
                f"{server}/api/qualitygates/project_status",
                params={"projectKey": project},
                auth=(token, ""),  # SonarQube uses token as username
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            status = data.get("projectStatus", {}).get("status", "ERROR")

            # Map SonarQube status to gate result
            if status == "OK":
                return GateRunResult(
                    gate_name=self.name,
                    result=GateResult.PASS,
                    command=f"sonarqube project_status {project}",
                    exit_code=0,
                    stdout=f"SonarQube quality gate: {status}",
                    stderr="",
                )
            else:
                # Include condition details in output for debugging
                conditions = data.get("projectStatus", {}).get("conditions", [])
                failures = [c for c in conditions if c.get("status") != "OK"]
                details = "\n".join(
                    f"  - {c['metricKey']}: {c.get('actualValue', 'N/A')} "
                    f"(threshold: {c.get('errorThreshold', 'N/A')})"
                    for c in failures
                )

                return GateRunResult(
                    gate_name=self.name,
                    result=GateResult.FAIL,
                    command=f"sonarqube project_status {project}",
                    exit_code=1,
                    stdout=f"SonarQube quality gate: {status}\nFailed conditions:\n{details}",
                    stderr="",
                )

        except requests.RequestException as e:
            return GateRunResult(
                gate_name=self.name,
                result=GateResult.ERROR,
                command=f"sonarqube project_status {project}",
                exit_code=1,
                stdout="",
                stderr=f"Failed to connect to SonarQube: {e}",
            )
```

### Example 3: Metrics Collection

**The story**: Your team tracks build metrics in Datadog. You want to see task durations, success rates, and gate results in your dashboards.

```python
"""Metrics collection hook for observability platforms."""

from zerg.plugins import LifecycleHookPlugin, LifecycleEvent
import statsd
import os


class MetricsHook(LifecycleHookPlugin):
    """Send ZERG metrics to StatsD (compatible with Datadog, Prometheus, etc)."""

    def __init__(self):
        self.client = statsd.StatsClient(
            host=os.getenv("STATSD_HOST", "localhost"),
            port=int(os.getenv("STATSD_PORT", 8125)),
            prefix="zerg"  # All metrics prefixed with "zerg."
        )

    @property
    def name(self) -> str:
        return "metrics"

    def on_event(self, event: LifecycleEvent) -> None:
        """Route events to appropriate metric handlers."""

        handlers = {
            "task_completed": self._record_task_metrics,
            "level_complete": self._record_level_metrics,
            "quality_gate_run": self._record_gate_metrics,
            "rush_finished": self._record_rush_metrics,
        }

        handler = handlers.get(event.event_type)
        if handler:
            handler(event)

    def _record_task_metrics(self, event: LifecycleEvent) -> None:
        """Record task duration and completion count."""
        duration_ms = event.data["duration"] * 1000
        self.client.timing("task.duration", duration_ms)
        self.client.incr("task.completed")

    def _record_level_metrics(self, event: LifecycleEvent) -> None:
        """Record level completion time and task count."""
        level = event.data["level"]
        self.client.timing(f"level.{level}.duration", event.data["elapsed_time"] * 1000)
        self.client.gauge(f"level.{level}.tasks", event.data["task_count"])

    def _record_gate_metrics(self, event: LifecycleEvent) -> None:
        """Record quality gate results."""
        gate_name = event.data["gate_name"]
        result = event.data["result"].lower()
        self.client.incr(f"gate.{gate_name}.{result}")

    def _record_rush_metrics(self, event: LifecycleEvent) -> None:
        """Record overall rush metrics."""
        self.client.timing("rush.total_time", event.data["total_time"] * 1000)
        self.client.gauge("rush.tasks_completed", event.data["tasks_completed"])
```

### Example 4: Kubernetes Launcher

**The story**: Your team runs builds on Kubernetes. You want ZERG workers to run as pods in your cluster, with proper resource limits and cleanup.

```python
"""Kubernetes launcher for running workers as pods."""

from zerg.plugins import LauncherPlugin
from zerg.launcher import WorkerLauncher
from kubernetes import client, config
import time


class K8sLauncher(WorkerLauncher):
    """Spawn ZERG workers as Kubernetes pods."""

    def __init__(self, zerg_config):
        super().__init__(zerg_config)
        # Load kubeconfig (works with in-cluster or local config)
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()

        self.api = client.CoreV1Api()
        self.namespace = zerg_config.get("k8s_namespace", "zerg")

    def launch(self, worker_id: str, task_id: str) -> dict:
        """Create a pod for the worker."""
        pod_name = f"zerg-worker-{worker_id}"

        pod = client.V1Pod(
            metadata=client.V1ObjectMeta(
                name=pod_name,
                labels={
                    "app": "zerg-worker",
                    "task": task_id,
                    "worker": worker_id
                }
            ),
            spec=client.V1PodSpec(
                restart_policy="Never",  # Workers run once
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
        return {"pod_name": pod_name, "namespace": self.namespace}

    def wait(self, launch_info: dict) -> int:
        """Wait for pod to complete and return exit code."""
        pod_name = launch_info["pod_name"]
        namespace = launch_info["namespace"]

        while True:
            pod = self.api.read_namespaced_pod(name=pod_name, namespace=namespace)

            if pod.status.phase == "Succeeded":
                return 0
            elif pod.status.phase == "Failed":
                return 1
            elif pod.status.phase in ["Unknown", "Error"]:
                return 1

            time.sleep(5)

    def cleanup(self, launch_info: dict) -> None:
        """Delete the pod after completion."""
        try:
            self.api.delete_namespaced_pod(
                name=launch_info["pod_name"],
                namespace=launch_info["namespace"]
            )
        except client.ApiException:
            pass  # Pod may already be deleted


class K8sLauncherPlugin(LauncherPlugin):
    """Plugin that provides Kubernetes launcher."""

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
  mode: kubernetes
  k8s_namespace: zerg-workers
```

---

## Advanced Patterns

Once you're comfortable with basic plugins, these patterns help build more sophisticated integrations.

### Combining Multiple Plugin Types

A complete integration often uses multiple plugin types together. For example, a CI/CD integration might:

1. **Lifecycle hook** - Start a CI build when rush begins
2. **Quality gate** - Check CI build status before allowing merge
3. **Lifecycle hook** - Update CI with merge results

```python
class CIBuildHook(LifecycleHookPlugin):
    """Start CI builds on rush start."""

    def on_event(self, event: LifecycleEvent) -> None:
        if event.event_type == "rush_started":
            # Start CI build, store build ID
            build_id = start_ci_build(event.data["feature"])
            # Store for the gate to check later
            self._store_build_id(event.data["feature"], build_id)


class CIStatusGate(QualityGatePlugin):
    """Check CI build status before merging."""

    def run(self, ctx: GateContext) -> GateRunResult:
        build_id = self._get_build_id(ctx.feature)
        status = check_ci_build(build_id)
        # Return appropriate result based on CI status
```

### Stateful Plugins

Plugins can maintain state across events within a single rush:

```python
class ProgressTracker(LifecycleHookPlugin):
    """Track progress for reporting."""

    def __init__(self):
        self.task_times = {}  # Store task durations
        self.failed_gates = []  # Track failures

    def on_event(self, event: LifecycleEvent) -> None:
        if event.event_type == "task_completed":
            task_id = event.data["task_id"]
            self.task_times[task_id] = event.data["duration"]

        elif event.event_type == "quality_gate_run":
            if event.data["result"] == "FAIL":
                self.failed_gates.append(event.data["gate_name"])

        elif event.event_type == "rush_finished":
            # Generate summary report using collected data
            self._generate_report()
```

### Conditional Gate Execution

Gates can skip levels where they don't apply:

```python
class PythonOnlyGate(QualityGatePlugin):
    """Only run on levels with Python changes."""

    def run(self, ctx: GateContext) -> GateRunResult:
        # Check if any Python files changed in this level
        python_files = list(ctx.cwd.glob("**/*.py"))
        if not python_files:
            return GateRunResult(
                gate_name=self.name,
                result=GateResult.SKIP,
                command="skipped",
                exit_code=0,
                stdout="No Python files in this level",
                stderr="",
            )

        # Run the actual check...
```

---

## Security Model

Understanding the security boundaries helps you write safe plugins.

### Read-Only State Access

Plugins cannot modify ZERG's internal state. They receive immutable views:

- **GateContext** - Read-only view of feature, level, working directory, and config
- **LifecycleEvent** - Read-only view of event type, data, and timestamp
- No access to orchestrator internals like task queues or worker pools

### Timeout Enforcement

| Plugin Type | Timeout Range | Default |
|-------------|---------------|---------|
| YAML hooks | 1-600 seconds | 60s |
| YAML gates | 1-3600 seconds | 300s |
| Python plugins | Configurable | 300s |

Plugins exceeding their timeout are terminated and report `TIMEOUT` status.

### Exception Isolation

Every plugin invocation is wrapped in try/except. A failing plugin never crashes the orchestrator - failures are logged and execution continues.

### Command Execution Safety

YAML commands are parsed with `shlex.split` and executed via `subprocess.run(shell=False)`. This prevents shell injection attacks. Your command is split into arguments, not interpreted by a shell.

---

## Best Practices

### Writing Quality Gates

- **Return `SKIP` for non-applicable checks** - If your gate only applies to Python files and there are none, return `SKIP` instead of `PASS`
- **Use `required: false` for advisory gates** - Security scans that find low-severity issues might warn but not block
- **Set realistic timeouts** - Allow 3x the typical execution time for buffer
- **Capture full output** - Include stdout/stderr in results for debugging
- **Test manually first** - Run your gate command by hand before integrating

### Writing Lifecycle Hooks

- **Keep hooks fast** - Hooks block event processing; use async for slow operations
- **Never throw exceptions** - Return gracefully; let ZERG continue
- **Log internally** - If something fails, log it; don't rely on ZERG to surface it
- **Be selective** - Only process events you care about

### Writing Launchers

- **Implement proper cleanup** - Delete pods, VMs, temp resources even on failure
- **Handle partial failures** - Launcher crash shouldn't orphan workers
- **Support idempotency** - Launchers should handle retry safely
- **Include health checks** - Know when workers are actually ready

### General Guidelines

- **Prefix log messages** - Use `logger.info(f"[{self.name}] ...")` for traceability
- **Version breaking changes** - Use `sonarqube-v2` entry point for incompatible updates
- **Test with mock mode** - Verify plugins work before production use
- **Document requirements** - Note environment variables and config options

---

## Troubleshooting

| Problem | What You See | How to Fix |
|---------|--------------|------------|
| Plugin not discovered | Not in startup logs | Check entry point group is `"zerg.plugins"`, reinstall with `pip install -e .` |
| Hook command fails | Exception in logs | Verify command exists with `which <cmd>`, check file permissions |
| Gate always returns ERROR | ERROR instead of PASS/FAIL | Test gate command manually, verify return value matches expected format |
| Custom launcher ignored | Falls back to subprocess | Check launcher name matches config `mode` exactly |
| Variables not replaced | `{level}` appears literally | Event type may not provide that variable; check available variables table |
| Frequent timeouts | TIMEOUT result | Increase timeout or optimize the command |

---

## Code References

| What | Where |
|------|-------|
| Plugin base classes | `zerg/plugins.py` |
| Plugin registry and discovery | `zerg/plugins.py` |
| Configuration models | `zerg/plugin_config.py` |
| Event type constants | `zerg/constants.py` |
| Integration tests | `tests/integration/test_plugin_lifecycle.py` |

---

## See Also

- [[Configuration]] - Full config.yaml reference including plugin settings
- [[Command-Reference]] - `/zerg:plugins` command documentation
- [[Home]] - ZERG overview and quick start
