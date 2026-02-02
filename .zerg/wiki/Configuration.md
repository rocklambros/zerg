# Configuration Reference

ZERG is configured through `.zerg/config.yaml` at the project root. This page documents every configuration option, its default value, and usage examples.

For performance tuning guidance, see [[Tuning Guide]]. For plugin configuration, see [[Plugin System]].

---

## Configuration File Location

```
your-project/
  .zerg/
    config.yaml       <-- Primary configuration file
    state/            <-- Runtime state (managed by ZERG)
    logs/             <-- Worker and orchestrator logs
```

ZERG reads `.zerg/config.yaml` on every command invocation. Changes take effect on the next command run -- no restart is required.

---

## Full Configuration Schema

### project

Project metadata used in task subjects and log output.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `name` | string | `""` | Project name for display and task tracking |
| `description` | string | `""` | Short project description |

```yaml
project:
  name: my-service
  description: REST API for user management
```

### workers

Controls how many parallel Claude Code instances run and how they behave.

| Option | Type | Default | Range | Description |
|--------|------|---------|-------|-------------|
| `max_concurrent` | int | `5` | 1-15 | Maximum workers running simultaneously |
| `timeout_minutes` | int | `60` | 5-180 | Per-task timeout before forced termination |
| `retry_attempts` | int | `2` | 0-5 | Number of retries for failed tasks |
| `context_threshold_percent` | float | `70` | 50-95 | Context usage percentage that triggers worker checkpoint |
| `launcher_type` | string | `"subprocess"` | subprocess, container | Worker execution environment |
| `backoff_strategy` | string | `"exponential"` | exponential, linear, fixed | Retry backoff strategy |
| `backoff_base_seconds` | int | `30` | 5-300 | Initial backoff duration for retries |
| `backoff_max_seconds` | int | `300` | 30-3600 | Maximum backoff duration |

```yaml
workers:
  max_concurrent: 5
  timeout_minutes: 60
  retry_attempts: 2
  context_threshold_percent: 70
  launcher_type: subprocess
  backoff_strategy: exponential
  backoff_base_seconds: 30
  backoff_max_seconds: 300
```

### ports

Port allocation for worker processes. Each worker reserves a contiguous block of ports from the configured range.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `range_start` | int | `49152` | Start of the ephemeral port range |
| `range_end` | int | `65535` | End of the ephemeral port range |
| `ports_per_worker` | int | `10` | Number of ports reserved per worker |

```yaml
ports:
  range_start: 49152
  range_end: 65535
  ports_per_worker: 10
```

The total number of workers you can run simultaneously is constrained by `(range_end - range_start) / ports_per_worker`. With the defaults, this allows up to 1638 workers (far above any practical limit).

### quality_gates

Ordered list of validation commands that run after each level merge. Gates execute sequentially in the order listed. See [[Plugin System]] for adding custom gates via plugins.

Each gate entry has these fields:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | required | Unique identifier for the gate |
| `command` | string | required | Shell command to execute |
| `required` | bool | `true` | If true, failure blocks the merge |
| `timeout` | int | `300` | Maximum execution time in seconds (1-3600) |
| `coverage_threshold` | int | none | Optional coverage percentage for coverage gates |

```yaml
quality_gates:
  - name: lint
    command: ruff check .
    required: true
    timeout: 300

  - name: typecheck
    command: mypy . --strict --ignore-missing-imports
    required: true
    timeout: 300

  - name: test
    command: pytest tests/unit/ -x --timeout=30
    required: true
    timeout: 600

  - name: coverage
    command: pytest tests/unit/ --cov=zerg --cov-fail-under=80 -q --timeout=30
    required: false
    timeout: 600
    coverage_threshold: 80

  - name: security
    command: ruff check . --select S
    required: false
    timeout: 120
```

**Gate results.** Each gate produces one of five results: `PASS`, `FAIL`, `SKIP`, `TIMEOUT`, or `ERROR`. Required gates that produce `FAIL` or `ERROR` block the merge. Non-required gates log warnings but do not block.

### mcp_servers

List of MCP (Model Context Protocol) servers to make available to worker instances.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `mcp_servers` | list[string] | `[]` | MCP server names to enable |

```yaml
mcp_servers:
  - filesystem
  - github
  - fetch
```

Workers launched in container mode receive these as `--mcp-server` flags. Subprocess workers inherit MCP servers from the parent Claude Code session.

### resources

Resource limits for worker instances. These apply primarily to container mode but also inform subprocess resource monitoring.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `cpu_cores` | int | `2` | CPU cores allocated per worker |
| `memory_gb` | int | `4` | Memory in GB allocated per worker |
| `disk_gb` | int | `10` | Disk space in GB allocated per worker |
| `container_memory_limit` | string | `"4g"` | Docker memory limit flag value |
| `container_cpu_limit` | float | `2.0` | Docker CPU limit flag value |

```yaml
resources:
  cpu_cores: 2
  memory_gb: 4
  disk_gb: 10
  container_memory_limit: "4g"
  container_cpu_limit: 2.0
```

### logging

Log output configuration.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `level` | string | `"info"` | Log level: debug, info, warning, error |
| `directory` | string | `".zerg/logs"` | Directory for log files |
| `retain_days` | int | `7` | Days to keep log files before cleanup |

```yaml
logging:
  level: info
  directory: .zerg/logs
  retain_days: 7
```

### security

Security settings for worker execution and audit trail.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `level` | string | `"standard"` | Security level: minimal, standard, strict |
| `pre_commit_hooks` | bool | `true` | Run pre-commit hooks on worker commits |
| `audit_logging` | bool | `true` | Log security-relevant events |
| `container_readonly` | bool | `true` | Mount container filesystem as read-only |

```yaml
security:
  level: standard
  pre_commit_hooks: true
  audit_logging: true
  container_readonly: true
```

### plugins

Plugin system configuration. See [[Plugin System]] and [[Plugin API Reference]] for details.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | bool | `true` | Master switch for the plugin system |
| `hooks` | list | `[]` | Lifecycle hook definitions |
| `quality_gates` | list | `[]` | Plugin quality gate definitions |
| `launchers` | list | `[]` | Custom launcher plugin definitions |
| `context_engineering` | object | see below | Context engineering settings |

```yaml
plugins:
  enabled: true

  hooks:
    - event: task_completed
      command: echo "Task done"
      timeout: 60

  quality_gates:
    - name: security-scan
      command: bandit -r src/
      required: false
      timeout: 300

  context_engineering:
    enabled: true
    command_splitting: true
    security_rule_filtering: true
    task_context_budget_tokens: 4000
    fallback_to_full: true
```

For `context_engineering` options, see [[Context Engineering]].

### rules

Engineering rules injected into worker context based on file extensions.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | bool | `true` | Master switch for rule injection |
| `base_rules` | bool | `true` | Include built-in safety/quality/efficiency rules |
| `custom_rules` | bool | `true` | Include project-specific custom rules |
| `disabled_rules` | list | `[]` | Rule IDs to disable |
| `inject_into_workers` | bool | `true` | Inject rules into worker context |

```yaml
rules:
  enabled: true
  base_rules: true
  custom_rules: true
  disabled_rules: []
  inject_into_workers: true
```

### efficiency

Token efficiency settings for automatic compact mode activation.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `auto_compact_threshold` | float | `0.75` | Context usage % to trigger compact mode (0.5-1.0) |
| `symbol_system` | bool | `true` | Use symbols for status indicators |
| `abbreviations` | bool | `true` | Abbreviate common terms |

```yaml
efficiency:
  auto_compact_threshold: 0.75
  symbol_system: true
  abbreviations: true
```

### improvement_loops

Iterative improvement loop configuration.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_iterations` | int | `5` | Maximum loop iterations (1-10) |
| `plateau_threshold` | int | `2` | No-improvement rounds before stopping (1-5) |
| `rollback_on_regression` | bool | `true` | Revert if score decreases |
| `convergence_threshold` | float | `0.02` | Minimum improvement to continue (0.001-0.5) |

```yaml
improvement_loops:
  max_iterations: 5
  plateau_threshold: 2
  rollback_on_regression: true
  convergence_threshold: 0.02
```

### verification

Verification gate pipeline settings.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `require_before_completion` | bool | `true` | Require verification before marking done |
| `staleness_threshold_seconds` | int | `300` | Re-run if older than this (10-3600) |
| `store_artifacts` | bool | `true` | Store verification results |
| `artifact_dir` | string | `".zerg/artifacts"` | Artifact storage path |

```yaml
verification:
  require_before_completion: true
  staleness_threshold_seconds: 300
  store_artifacts: true
  artifact_dir: ".zerg/artifacts"
```

### behavioral_modes

Behavioral mode auto-detection and defaults.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `auto_detect` | bool | `true` | Auto-detect mode from task keywords |
| `default_mode` | string | `"precision"` | Default mode (precision/speed/exploration/refactor/debug) |
| `log_transitions` | bool | `true` | Log mode changes |

```yaml
behavioral_modes:
  auto_detect: true
  default_mode: precision
  log_transitions: true
```

### mcp_routing

MCP auto-routing configuration.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `auto_detect` | bool | `true` | Enable capability-based server matching |
| `available_servers` | list | `[sequential, context7, playwright, morphllm, magic, serena]` | Servers to consider |
| `cost_aware` | bool | `true` | Prefer lower-cost servers |
| `telemetry` | bool | `true` | Record routing decisions |
| `max_servers` | int | `3` | Maximum servers per task (1-6) |

```yaml
mcp_routing:
  auto_detect: true
  available_servers:
    - sequential
    - context7
    - playwright
    - morphllm
    - magic
    - serena
  cost_aware: true
  telemetry: true
  max_servers: 3
```

### tdd

TDD enforcement configuration (off by default).

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | bool | `false` | Master switch for TDD mode |
| `enforce_red_green` | bool | `true` | Require red-green-refactor order |
| `anti_patterns` | list | `[mock_heavy, testing_impl, no_assertions]` | Anti-patterns to detect |

```yaml
tdd:
  enabled: false
  enforce_red_green: true
  anti_patterns:
    - mock_heavy
    - testing_impl
    - no_assertions
```

### error_recovery

Error recovery with circuit breaker and backpressure.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `circuit_breaker.enabled` | bool | `true` | Enable circuit breaker |
| `circuit_breaker.failure_threshold` | int | `3` | Failures before tripping (1-20) |
| `circuit_breaker.cooldown_seconds` | int | `60` | Recovery wait time (5-600) |
| `backpressure.enabled` | bool | `true` | Enable backpressure controller |
| `backpressure.failure_rate_threshold` | float | `0.5` | Rate to trigger throttling |
| `backpressure.window_size` | int | `10` | Rolling window size |

```yaml
error_recovery:
  circuit_breaker:
    enabled: true
    failure_threshold: 3
    cooldown_seconds: 60
  backpressure:
    enabled: true
    failure_rate_threshold: 0.5
    window_size: 10
```

---

## Complete Example

The following is the full default configuration with all options shown:

```yaml
project:
  name: my-project
  description: My project description

workers:
  max_concurrent: 5
  timeout_minutes: 60
  retry_attempts: 2
  context_threshold_percent: 70
  launcher_type: subprocess
  backoff_strategy: exponential
  backoff_base_seconds: 30
  backoff_max_seconds: 300

ports:
  range_start: 49152
  range_end: 65535
  ports_per_worker: 10

quality_gates:
  - name: lint
    command: ruff check .
    required: true
    timeout: 300
  - name: typecheck
    command: mypy . --strict --ignore-missing-imports
    required: true
    timeout: 300
  - name: test
    command: pytest tests/unit/ -x --timeout=30
    required: true
    timeout: 600

mcp_servers:
  - filesystem
  - github

resources:
  cpu_cores: 2
  memory_gb: 4
  disk_gb: 10
  container_memory_limit: "4g"
  container_cpu_limit: 2.0

logging:
  level: info
  directory: .zerg/logs
  retain_days: 7

security:
  level: standard
  pre_commit_hooks: true
  audit_logging: true
  container_readonly: true

plugins:
  enabled: true
  hooks: []
  quality_gates: []
  launchers: []
  context_engineering:
    enabled: true
    command_splitting: true
    security_rule_filtering: true
    task_context_budget_tokens: 4000
    fallback_to_full: true

rules:
  enabled: true
  base_rules: true
  custom_rules: true
  disabled_rules: []
  inject_into_workers: true

efficiency:
  auto_compact_threshold: 0.75
  symbol_system: true
  abbreviations: true

improvement_loops:
  max_iterations: 5
  plateau_threshold: 2
  rollback_on_regression: true
  convergence_threshold: 0.02

verification:
  require_before_completion: true
  staleness_threshold_seconds: 300
  store_artifacts: true
  artifact_dir: ".zerg/artifacts"

behavioral_modes:
  auto_detect: true
  default_mode: precision
  log_transitions: true

mcp_routing:
  auto_detect: true
  available_servers:
    - sequential
    - context7
    - playwright
    - morphllm
    - magic
    - serena
  cost_aware: true
  telemetry: true
  max_servers: 3

tdd:
  enabled: false
  enforce_red_green: true
  anti_patterns:
    - mock_heavy
    - testing_impl
    - no_assertions

error_recovery:
  circuit_breaker:
    enabled: true
    failure_threshold: 3
    cooldown_seconds: 60
  backpressure:
    enabled: true
    failure_rate_threshold: 0.5
    window_size: 10
```

---

## Environment Variables

Workers recognize specific environment variables for cross-session coordination. These are set automatically by the launcher and should not normally require manual configuration.

| Variable | Purpose |
|----------|---------|
| `CLAUDE_CODE_TASK_LIST_ID` | Shared task list ID for worker coordination |
| `ZERG_WORKER_ID` | Unique worker identifier |
| `ZERG_FEATURE` | Feature name being built |
| `ZERG_TASK_ID` | Current task identifier |
| `ZERG_WORKTREE` | Git worktree path for the worker |
| `ZERG_BRANCH` | Git branch name for the worker |
| `ZERG_ANALYSIS_DEPTH` | Analysis depth tier (quick/standard/think/think_hard/ultrathink) |
| `ZERG_COMPACT_MODE` | Compact output mode (true/false) |
| `ZERG_MCP_HINT` | Recommended MCP servers for the task |
| `ZERG_SPEC_DIR` | Path to feature spec files |
| `ZERG_STATE_DIR` | Path to ZERG state directory |
| `ZERG_REPO_PATH` | Path to the main repository |
| `ANTHROPIC_API_KEY` | API key for container mode authentication |

---

## See Also

- [[Tuning Guide]] -- When and how to adjust these values
- [[Plugin System]] -- Extending ZERG with custom gates, hooks, and launchers
- [[Context Engineering]] -- Token optimization configuration
