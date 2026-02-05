# Configuration

Complete reference for configuring ZERG, covering the config file structure, all configuration sections, environment variables, and tuning recommendations.

## Overview

ZERG uses a YAML configuration file at `.zerg/config.yaml` to control worker behavior, quality gates, plugins, and cross-cutting capabilities. The file is created automatically by `/zerg:init` with sensible defaults.

## Configuration File

**Location**: `.zerg/config.yaml`

### Minimal Example

```yaml
project:
  name: my-project

workers:
  max_concurrent: 5
  timeout_minutes: 60

quality_gates:
  - name: lint
    command: ruff check .
    required: true
  - name: test
    command: pytest
    required: true
```

### Full Example

```yaml
version: "1.0"
project_type: python

project:
  name: my-project
  description: My awesome project

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
  - name: test
    command: pytest tests/
    required: true
    timeout: 180

security:
  level: standard
  pre_commit_hooks: true
  audit_logging: true
  network_isolation: true
  filesystem_sandbox: true

plugins:
  enabled: true
  context_engineering:
    enabled: true

mcp_servers:
  - filesystem
  - github
```

## Configuration Sections

### Workers

Controls zergling behavior and resource allocation.

```yaml
workers:
  max_concurrent: 5              # Max concurrent workers (1-10)
  timeout_minutes: 60            # Max time per worker session
  retry_attempts: 2              # Retries before marking task blocked
  context_threshold_percent: 70  # Checkpoint at this context usage
  launcher_type: subprocess      # Worker launch mode
  backoff_strategy: exponential  # Retry backoff strategy
  backoff_base_seconds: 30       # Initial backoff delay
  backoff_max_seconds: 300       # Maximum backoff delay
```

| Setting | Range | Default | Description |
|---------|-------|---------|-------------|
| `max_concurrent` | 1-10 | 5 | Maximum concurrent workers |
| `timeout_minutes` | 1-1440 | 60 | Kill worker after this time |
| `retry_attempts` | 1-10 | 2 | Retries before blocking task |
| `context_threshold_percent` | 10-100 | 70 | Context usage checkpoint trigger |
| `launcher_type` | subprocess/container/task | subprocess | Worker launch mechanism |
| `backoff_strategy` | linear/exponential | exponential | Retry timing strategy |
| `backoff_base_seconds` | 1-300 | 30 | Initial retry delay |
| `backoff_max_seconds` | 30-3600 | 300 | Maximum retry delay |

### Quality Gates

Quality gates run after each level merge to validate merged code.

```yaml
quality_gates:
  - name: lint
    command: ruff check .
    required: true
    timeout: 300
  - name: test
    command: pytest tests/unit/ -x
    required: true
    timeout: 180
  - name: typecheck
    command: mypy . --ignore-missing-imports
    required: false
    timeout: 180
  - name: coverage
    command: pytest --cov=src --cov-fail-under=80
    required: false
    timeout: 300
    coverage_threshold: 80
  - name: security
    command: bandit -r src/
    required: false
    timeout: 60
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | Required | Gate identifier |
| `command` | string | Required | Shell command to run |
| `required` | boolean | true | Failure blocks merge if true |
| `timeout` | integer | 300 | Command timeout in seconds |
| `coverage_threshold` | integer | - | Optional coverage percentage |

**Gate Results**:
- `pass`: Exit code 0, continue to next level
- `fail`: Non-zero exit, blocks if `required: true`
- `timeout`: Exceeded limit, treated as failure
- `error`: Could not run, pauses for intervention

### Plugins

Configure hooks and custom quality gates.

```yaml
plugins:
  enabled: true

  hooks:
    - event: task_completed
      command: echo "Task {task_id} done"
      timeout: 60
    - event: level_complete
      command: ./scripts/notify.sh "Level {level} done"
      timeout: 120

  quality_gates:
    - name: security-scan
      command: bandit -r src/ --severity medium
      required: false
      timeout: 300

  context_engineering:
    enabled: true
    command_splitting: true
    security_rule_filtering: true
    task_context_budget_tokens: 4000
    fallback_to_full: true
```

**Hook Event Types**:
| Event | When Triggered |
|-------|----------------|
| `task_started` | Worker begins task |
| `task_completed` | Task passes verification |
| `level_complete` | All tasks in level done |
| `merge_complete` | Level branches merged |
| `worker_spawned` | New worker starts |
| `quality_gate_run` | Gate runs |
| `rush_started` | `/zerg:rush` begins |
| `rush_finished` | All levels complete |

**Variable Substitution**: Hook commands support `{level}`, `{feature}`, `{task_id}`, `{worker_id}`.

### Resilience / Error Recovery

Configure circuit breakers and backpressure handling.

```yaml
error_recovery:
  circuit_breaker:
    enabled: true
    failure_threshold: 3         # Failures before tripping
    cooldown_seconds: 60         # Recovery wait time
  backpressure:
    enabled: true
    failure_rate_threshold: 0.5  # Rate to trigger throttling
    window_size: 10              # Rolling window size
```

| Setting | Range | Default | Description |
|---------|-------|---------|-------------|
| `failure_threshold` | 1-20 | 3 | Failures to trip circuit |
| `cooldown_seconds` | 5-600 | 60 | Wait before retry |
| `failure_rate_threshold` | 0.1-1.0 | 0.5 | Rate to trigger throttle |
| `window_size` | 3-100 | 10 | Rolling window for rate calc |

### Efficiency / Token Optimization

Control automatic token efficiency features.

```yaml
efficiency:
  auto_compact_threshold: 0.75  # Context % to trigger compact mode
  symbol_system: true           # Use symbols for indicators
  abbreviations: true           # Abbreviate common terms
```

### MCP Routing

Configure MCP server auto-routing for workers.

```yaml
mcp_routing:
  auto_detect: true              # Capability-based server matching
  available_servers:
    - sequential
    - context7
    - playwright
    - morphllm
    - magic
    - serena
  cost_aware: true               # Optimize for lower-cost servers
  telemetry: true                # Record routing decisions
  max_servers: 3                 # Max servers per task
```

### Verification Gates

Configure verification behavior and artifact storage.

```yaml
verification:
  require_before_completion: true       # Require verification first
  staleness_threshold_seconds: 300      # Re-run if older than this
  store_artifacts: true                 # Store results as JSON
  artifact_dir: ".zerg/artifacts"       # Storage directory
```

**Three-Tier Verification**:
```yaml
verification_tiers:
  tier1_blocking: true           # Tier 1 (syntax) blocks on failure
  tier1_command: null            # Custom lint/typecheck command
  tier2_blocking: true           # Tier 2 (correctness) blocks
  tier2_command: null            # Custom test command
  tier3_blocking: false          # Tier 3 (quality) warns only
  tier3_command: null            # Custom quality command
```

### TDD Enforcement

Configure test-driven development enforcement.

```yaml
tdd:
  enabled: false                 # Master switch (off by default)
  enforce_red_green: true        # Require red->green->refactor
  anti_patterns:
    - mock_heavy
    - testing_impl
    - no_assertions
```

### Improvement Loops

Configure iterative improvement behavior.

```yaml
improvement_loops:
  enabled: true
  max_iterations: 5              # Max loop iterations
  plateau_threshold: 2           # No-improvement rounds to stop
  rollback_on_regression: true   # Revert if score decreases
  convergence_threshold: 0.02    # Min improvement for progress
```

### Behavioral Modes

Configure automatic mode detection.

```yaml
behavioral_modes:
  auto_detect: true              # Auto-detect from keywords
  default_mode: precision        # Default when not detected
  log_transitions: true          # Log mode changes
```

Available modes: `precision`, `speed`, `exploration`, `refactor`, `debug`.

### Heartbeat Monitoring

Configure worker health monitoring.

```yaml
heartbeat:
  interval_seconds: 15           # Heartbeat write interval
  stall_timeout_seconds: 120     # Seconds before stall detection
  max_restarts: 2                # Auto-restarts before reassign
```

### Security

Configure security boundaries.

```yaml
security:
  level: standard                # Security level
  pre_commit_hooks: true         # Install pre-commit hooks
  audit_logging: true            # Enable audit logs
  network_isolation: true        # Isolate worker networks
  filesystem_sandbox: true       # Sandbox filesystem access
  container_readonly: true       # Read-only container root
  secrets_scanning: true         # Scan for secrets
```

### Resources

Configure resource limits for containers.

```yaml
resources:
  cpu_cores: 2
  memory_gb: 4
  disk_gb: 10
  container_memory_limit: "4g"
  container_cpu_limit: 2.0
```

### Logging

Configure logging behavior.

```yaml
logging:
  level: info                    # Log level
  directory: .zerg/logs          # Log directory
  retain_days: 7                 # Log retention period
```

## Environment Variables

### Required

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Claude API key (for container/subprocess modes) |

### ZERG-Specific (Set by Orchestrator)

| Variable | Description |
|----------|-------------|
| `ZERG_WORKER_ID` | Worker identifier (0-N) |
| `ZERG_FEATURE` | Current feature name |
| `ZERG_BRANCH` | Worker's git branch |
| `ZERG_WORKTREE` | Worker's git worktree path |
| `ZERG_ANALYSIS_DEPTH` | Analysis tier (quick/standard/think/think_hard/ultrathink) |
| `ZERG_COMPACT_MODE` | Compact output mode (true/false) |
| `ZERG_MCP_HINT` | Recommended MCP servers for task |
| `CLAUDE_CODE_TASK_LIST_ID` | Shared task list for coordination |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `info` | Logging verbosity |
| `DEBUG` | `false` | Enable debug output |
| `CI` | unset | CI environment flag |

### Environment Variable Filtering

ZERG controls which variables pass to workers:

**Allowed**:
- `ZERG_WORKER_ID`, `ZERG_FEATURE`, `ZERG_WORKTREE`
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`
- `CI`, `DEBUG`, `LOG_LEVEL`

**Blocked** (security):
- `LD_PRELOAD`, `DYLD_INSERT_LIBRARIES`
- `PYTHONPATH`, `HOME`, `USER`, `SHELL`

## Tuning Recommendations

### Worker Count Guidelines

| Workers | Best For |
|---------|----------|
| 1-2 | Small features, learning ZERG |
| 3-5 | Medium features, balanced throughput |
| 6-10 | Large features, maximum parallelism |

Diminishing returns beyond the widest level's parallelizable tasks.

### For Speed

```yaml
workers:
  max_concurrent: 8
  timeout_minutes: 30
  context_threshold_percent: 80

quality_gates:
  - name: lint
    required: true
  - name: test
    required: true
    timeout: 120
```

### For Reliability

```yaml
workers:
  max_concurrent: 3
  retry_attempts: 5
  context_threshold_percent: 60

quality_gates:
  - name: lint
    required: true
  - name: typecheck
    required: true
  - name: test
    required: true
```

### For Large Features

```yaml
workers:
  max_concurrent: 10
  timeout_minutes: 120

improvement_loops:
  max_iterations: 3
```

### For CI/CD

```yaml
workers:
  max_concurrent: 5
  timeout_minutes: 60

quality_gates:
  - name: lint
    command: "ruff check . --select ALL"
    required: true
  - name: test
    command: "pytest --cov --cov-fail-under=80"
    required: true
  - name: security
    command: "bandit -r src/"
    required: true
```

### Resource Tuning

| Scenario | CPU Cores | Memory | Workers |
|----------|-----------|--------|---------|
| Local dev | 2 | 4 GB | 3 |
| CI runner | 4 | 8 GB | 5 |
| Dedicated | 8 | 16 GB | 10 |

## Directory Structure

```
.zerg/
├── config.yaml              # Main configuration file
├── hooks/
│   └── pre-commit           # Pre-commit hook script
├── state/
│   ├── {feature}.json       # Runtime state per feature
│   ├── heartbeat-{id}.json  # Per-worker heartbeat
│   ├── progress-{id}.json   # Per-worker progress
│   └── escalations.json     # Shared escalation file
├── artifacts/
│   └── {task-id}/           # Verification artifacts
├── logs/
│   ├── workers/
│   │   └── worker-{id}.jsonl
│   ├── tasks/
│   │   └── {TASK-ID}/
│   │       ├── execution.jsonl
│   │       ├── claude_output.txt
│   │       ├── verification_output.txt
│   │       └── git_diff.patch
│   └── orchestrator.jsonl
└── rules/                   # Custom engineering rules
```

## See Also

- [Getting Started](Getting-Started.md) - Initial setup
- [Commands](Commands.md) - CLI reference
- [Plugins](Plugins.md) - Plugin development
