# Configuration

This guide explains every ZERG configuration option with practical scenarios for when and why you would change each setting. Understanding these options helps you tune ZERG for your specific workflow, hardware, and project requirements.

## Overview

ZERG uses a YAML configuration file at `.zerg/config.yaml` to control worker behavior, quality gates, plugins, and cross-cutting capabilities. The file is created automatically by `/zerg:init` with sensible defaults.

**Location**: `.zerg/config.yaml`

## Quick Start Configuration

If you are new to ZERG, start with this minimal configuration and expand as needed:

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

This gives you parallel execution with basic quality enforcement. Read on to understand each option and when to customize it.

---

## Workers

The workers section controls how ZERG spawns and manages Claude Code instances.

### max_concurrent

**What it does:** Limits how many Claude Code instances ZERG can spawn simultaneously.

**Default:** `5` — Balances speed with resource usage. Most development machines can handle 5 workers without memory pressure or API rate limiting issues.

**When to change it:**
- Increase to 8-10 if you have 32GB+ RAM and your task graph has many independent tasks at the same level
- Decrease to 2-3 on laptops, when running other heavy processes, or if you hit API rate limits
- Match your task graph's max parallelization (visible in `/zerg:status`)

**Example:**
```yaml
workers:
  max_concurrent: 8  # High-memory workstation with wide task graph
```

---

### timeout_minutes

**What it does:** Kills a worker if it runs longer than this limit. Prevents hung workers from blocking progress indefinitely.

**Default:** `60` — One hour is enough for most tasks. Complex refactoring or large file operations may need more.

**When to change it:**
- Increase to 90-120 for tasks involving large codebases or complex multi-file changes
- Decrease to 30 for small, focused tasks where you want faster failure detection
- Set higher when workers need to run extensive test suites as part of verification

**Example:**
```yaml
workers:
  timeout_minutes: 120  # Large feature with complex tasks
```

---

### retry_attempts

**What it does:** Number of times ZERG retries a failed task before marking it as blocked and escalating.

**Default:** `2` — Two retries catches transient failures (network hiccups, temporary file locks) without wasting time on truly broken tasks.

**When to change it:**
- Increase to 3-5 for flaky environments or tasks with intermittent external dependencies
- Decrease to 1 when you want faster feedback on failures during development
- Keep at 2 for CI/CD where you want reliability without excessive retries

**Example:**
```yaml
workers:
  retry_attempts: 5  # Flaky external API dependencies
```

---

### context_threshold_percent

**What it does:** When a worker's context usage reaches this percentage, ZERG triggers a checkpoint to preserve progress before context exhaustion.

**Default:** `70` — Leaves 30% headroom for the checkpoint operation itself and any final work.

**When to change it:**
- Increase to 80-85 if your tasks are nearly complete when hitting the threshold (wastes less context on checkpoints)
- Decrease to 50-60 for tasks that tend to balloon in complexity and need more checkpoint buffer
- Lower for tasks with verbose output (test results, logs) that fill context quickly

**Example:**
```yaml
workers:
  context_threshold_percent: 60  # Tasks with verbose logging
```

---

### launcher_type

**What it does:** How ZERG spawns worker processes.

**Default:** `subprocess` — Runs Claude Code directly on your machine. Simple, fast startup, shares your environment.

**When to change it:**
- Use `container` for isolated execution with Docker (recommended for untrusted code or security-sensitive projects)
- Use `task` for Claude Code's built-in Task Tool Mode (the implicit default for `/zerg:rush`)
- Stick with `subprocess` for local development where you trust the code

| Mode | Isolation | Startup Time | Use Case |
|------|-----------|--------------|----------|
| `subprocess` | None | Fast | Local dev, trusted code |
| `container` | Full | Slower | CI/CD, untrusted code, security |
| `task` | None | Fast | Claude Code native parallelism |

**Example:**
```yaml
workers:
  launcher_type: container  # CI/CD with untrusted PRs
```

---

### backoff_strategy

**What it does:** Controls how retry delays increase between attempts.

**Default:** `exponential` — Delays grow exponentially (30s, 60s, 120s...). Gives external systems time to recover while not waiting forever.

**When to change it:**
- Use `linear` if failures are usually quick to resolve and you want predictable retry timing
- Stick with `exponential` when failures might be rate limits or overloaded services that need increasing cool-down time

**Example:**
```yaml
workers:
  backoff_strategy: linear  # Predictable retry intervals
```

---

### backoff_base_seconds / backoff_max_seconds

**What it does:** Base delay for the first retry and maximum delay cap.

**Defaults:** `30` / `300` — Start with 30 seconds, never wait more than 5 minutes.

**When to change it:**
- Decrease base to 5-10 for fast-recovering failures (local file locks)
- Increase base to 60+ when dealing with rate-limited APIs that need longer cool-down
- Increase max when external services have known recovery times (database failovers, API maintenance windows)

**Example:**
```yaml
workers:
  backoff_base_seconds: 10   # Fast local failures
  backoff_max_seconds: 120   # Don't wait more than 2 min
```

---

## Ports

Port configuration for worker communication. Only relevant when workers need network ports (rare).

### range_start / range_end

**What it does:** Defines the port range ZERG can allocate to workers.

**Default:** `49152` / `65535` — The IANA dynamic/private port range, avoiding conflicts with well-known services.

**When to change it:**
- Narrow the range if your firewall only allows specific ports
- Avoid overlap if other services claim parts of this range
- Generally leave alone unless you have specific networking requirements

**Example:**
```yaml
ports:
  range_start: 50000
  range_end: 51000  # Firewall-approved range only
```

---

### ports_per_worker

**What it does:** Number of ports allocated to each worker.

**Default:** `10` — Provides headroom for workers that spawn multiple listening services.

**When to change it:**
- Decrease to 1-2 if workers only need a single port each
- Increase if tasks involve complex multi-service setups
- Rarely needs adjustment

**Example:**
```yaml
ports:
  ports_per_worker: 2  # Simple single-service workers
```

---

## Quality Gates

Quality gates run after each level merge to validate the combined code. They are your automated safety net.

### Understanding Gate Structure

Each gate has:

```yaml
quality_gates:
  - name: lint           # Identifier shown in status output
    command: ruff check . # Shell command to execute
    required: true        # If true, failure blocks merge
    timeout: 300          # Seconds before killing the command
```

### name

**What it does:** Human-readable identifier for the gate.

**Why it matters:** Appears in `/zerg:status` output and error messages. Use descriptive names so you know what failed.

**Example:**
```yaml
- name: python-lint      # Better than just "lint"
- name: unit-tests       # Better than just "test"
- name: security-scan    # Clear purpose
```

---

### command

**What it does:** The shell command ZERG executes to run this gate.

**Why it matters:** This is where you define what "passing" means for your project.

**When to customize:**
- Match your project's actual tooling (ruff vs flake8, pytest vs unittest)
- Add flags for specific behavior (`-x` for fail-fast, `--cov` for coverage)
- Scope to relevant directories to speed up execution

**Example:**
```yaml
quality_gates:
  - name: lint
    command: ruff check . --select ALL --ignore E501  # Your project's lint config
  - name: test
    command: pytest tests/unit/ -x --timeout=30      # Fast-fail with timeout
  - name: typecheck
    command: mypy src/ --strict                       # Type checking
```

---

### required

**What it does:** If `true`, a failing gate blocks the merge. If `false`, failures are warnings only.

**Default:** `true` — Gates exist to catch problems; defaulting to required makes them effective.

**When to change it:**
- Set `required: false` for advisory gates (style checks, non-critical coverage targets)
- Keep `required: true` for critical gates (tests, linting, security scans)
- Start with all gates required, loosen only after understanding failure patterns

**Example:**
```yaml
quality_gates:
  - name: test
    required: true       # Must pass, non-negotiable
  - name: coverage
    required: false      # Nice to have, but don't block
  - name: style
    required: false      # Advisory only
```

---

### timeout

**What it does:** Kills the gate command if it exceeds this many seconds.

**Default:** `300` (5 minutes) — Reasonable for most lint/test operations.

**When to change it:**
- Decrease to 60-120 for fast operations (linting, type checking)
- Increase to 600+ for slow test suites or security scans
- Set based on your actual gate runtime plus some buffer

**Example:**
```yaml
quality_gates:
  - name: lint
    timeout: 60          # Linting should be fast
  - name: test
    timeout: 180         # Unit tests need more time
  - name: e2e
    timeout: 900         # End-to-end tests are slow
```

---

### coverage_threshold

**What it does:** For coverage gates, the minimum coverage percentage required to pass.

**When to use it:**
- Add to coverage gates to enforce minimum coverage
- Start low (60-70%) and raise as coverage improves
- Combine with `required: false` initially to gather baseline data

**Example:**
```yaml
quality_gates:
  - name: coverage
    command: pytest --cov=src --cov-fail-under=80
    required: true
    coverage_threshold: 80  # Enforce 80% minimum
```

---

### Gate Result Meanings

| Result | What Happened | Impact |
|--------|---------------|--------|
| `pass` | Exit code 0 | Continue to next level |
| `fail` | Non-zero exit | Blocks merge if `required: true` |
| `timeout` | Exceeded limit | Treated as failure |
| `error` | Could not run | Pauses for human intervention |

---

## Plugins

Plugins extend ZERG with hooks, custom gates, and context engineering features.

### enabled

**What it does:** Master switch for the plugin system.

**Default:** `true` — Plugins are a core ZERG feature.

**When to disable:**
- Debugging plugin-related issues
- Minimal setups where you want pure ZERG behavior
- Temporary troubleshooting

---

### hooks

**What it does:** Commands that run at specific lifecycle events.

**Why use them:**
- Send notifications when tasks complete
- Log progress to external systems
- Trigger downstream processes

**Example:**
```yaml
plugins:
  hooks:
    - event: task_completed
      command: echo "Task {task_id} done" >> progress.log
      timeout: 60
    - event: level_complete
      command: ./scripts/notify-slack.sh "Level {level} complete"
      timeout: 120
    - event: rush_finished
      command: ./scripts/report-metrics.sh {feature}
      timeout: 300
```

**Available Events:**

| Event | When Triggered | Use Case |
|-------|----------------|----------|
| `task_started` | Worker begins task | Start timing, log assignment |
| `task_completed` | Task passes verification | Progress tracking |
| `level_complete` | All tasks in level done | Milestone notifications |
| `merge_complete` | Level branches merged | Integration alerts |
| `worker_spawned` | New worker starts | Resource monitoring |
| `quality_gate_run` | Gate executes | Audit logging |
| `rush_started` | `/zerg:rush` begins | Session start |
| `rush_finished` | All levels complete | Final notification |

**Variable substitution:** Use `{level}`, `{feature}`, `{task_id}`, `{worker_id}` in commands.

---

### context_engineering

**What it does:** Optimizes token usage by splitting large command files and filtering context per task.

**Default:** `enabled: true` — Token efficiency is valuable for all projects.

**When to customize:**

```yaml
plugins:
  context_engineering:
    enabled: true
    command_splitting: true              # Split large commands
    security_rule_filtering: true        # Filter rules by file type
    task_context_budget_tokens: 4000     # Max context per task
    fallback_to_full: true               # Use full context if filtering fails
```

- Increase `task_context_budget_tokens` to 6000-8000 for complex tasks needing more context
- Decrease to 2000-3000 for simple, focused tasks to save tokens
- Disable `command_splitting` if you need full command file content always

---

## Error Recovery

ZERG includes automatic error recovery to handle transient failures gracefully.

### circuit_breaker

**What it does:** Stops spawning new workers temporarily when too many fail, preventing cascading failures.

**Default:** `enabled: true`, `failure_threshold: 3`, `cooldown_seconds: 60`

**When to change it:**
- Increase `failure_threshold` to 5-10 for flaky environments where occasional failures are normal
- Decrease `cooldown_seconds` to 30 when failures typically recover quickly
- Disable during debugging when you expect many failures

**Example:**
```yaml
error_recovery:
  circuit_breaker:
    enabled: true
    failure_threshold: 5   # More tolerance for flaky tests
    cooldown_seconds: 30   # Quick recovery expected
```

---

### backpressure

**What it does:** Slows down work spawning when failure rate exceeds threshold, preventing overload.

**Default:** `enabled: true`, `failure_rate_threshold: 0.5`, `window_size: 10`

**When to change it:**
- Lower `failure_rate_threshold` to 0.3 for stricter quality (slow down with fewer failures)
- Raise to 0.7 for aggressive execution (keep going despite failures)
- Increase `window_size` to 20-50 for smoother averaging over more samples

**Example:**
```yaml
error_recovery:
  backpressure:
    enabled: true
    failure_rate_threshold: 0.3  # Slow down at 30% failure rate
    window_size: 20              # Average over more samples
```

---

## Efficiency / Token Optimization

Controls automatic token-saving features.

### auto_compact_threshold

**What it does:** When context usage exceeds this percentage, ZERG switches to compact output mode.

**Default:** `0.75` — At 75% context usage, start conserving tokens.

**When to change it:**
- Lower to 0.5-0.6 for aggressive token savings from the start
- Raise to 0.85-0.9 to maintain verbose output longer
- Set to 1.0 to disable automatic compaction

**Example:**
```yaml
efficiency:
  auto_compact_threshold: 0.60  # Conserve tokens earlier
```

---

### symbol_system / abbreviations

**What it does:** Use symbols and abbreviations in output to reduce token usage.

**Defaults:** Both `true` — Every token saved extends how much work fits in context.

**When to disable:**
- When output clarity is more important than token savings
- During debugging when you need verbose human-readable output
- For documentation or reporting where symbols may confuse readers

**Example:**
```yaml
efficiency:
  symbol_system: false      # Human-readable status
  abbreviations: false      # Full words in output
```

---

## MCP Routing

Configure how ZERG selects MCP servers for workers.

### auto_detect

**What it does:** Automatically matches MCP servers to tasks based on their capabilities.

**Default:** `true` — Lets ZERG pick the best tools for each task type.

**When to disable:**
- When you want explicit control over which servers workers use
- Debugging MCP server issues
- Testing specific server configurations

---

### available_servers

**What it does:** List of MCP servers ZERG can route to.

**Default:** Common useful servers. Add or remove based on what you have installed.

**Example:**
```yaml
mcp_routing:
  available_servers:
    - sequential       # Multi-step reasoning
    - context7         # Documentation lookup
    - playwright       # Browser testing
    - morphllm         # Bulk edits
```

---

### cost_aware / max_servers

**What it does:** `cost_aware` optimizes for cheaper servers when possible. `max_servers` limits servers per task.

**Defaults:** `cost_aware: true`, `max_servers: 3`

**When to change:**
- Disable `cost_aware` when you prioritize capability over cost
- Reduce `max_servers` to 1-2 for simpler tasks
- Increase to 5 for complex tasks needing many capabilities

---

## Verification

Controls the verification system that validates task completion.

### require_before_completion

**What it does:** Tasks must pass verification before being marked complete.

**Default:** `true` — Ensures all tasks meet their verification criteria.

**When to disable:**
- During initial development when verification commands are not yet defined
- For exploratory tasks where pass/fail is subjective
- Temporarily when debugging verification issues

---

### staleness_threshold_seconds

**What it does:** Re-runs verification if the last result is older than this.

**Default:** `300` (5 minutes) — Cached results are valid for 5 minutes.

**When to change it:**
- Increase to 1800-3600 (30-60 min) for slow verification commands to avoid re-running
- Decrease to 60-120 for fast verification where freshness matters more
- Set to 0 to always re-verify (slowest but most accurate)

**Example:**
```yaml
verification:
  staleness_threshold_seconds: 1800  # 30 min cache for slow tests
```

---

### store_artifacts / artifact_dir

**What it does:** Saves verification results to disk for debugging and auditing.

**Defaults:** `store_artifacts: true`, `artifact_dir: ".zerg/artifacts"`

**When to change:**
- Disable `store_artifacts` to save disk space in CI environments
- Change `artifact_dir` to a shared location for team access
- Keep enabled for debugging failed verifications

---

### verification_tiers

**What it does:** Three-tier verification with configurable blocking behavior.

**Defaults:** Tier 1 and 2 block, Tier 3 warns only.

| Tier | Purpose | Default Blocking |
|------|---------|------------------|
| Tier 1 | Syntax (lint, typecheck) | Yes |
| Tier 2 | Correctness (tests) | Yes |
| Tier 3 | Quality (coverage, style) | No |

**Example:**
```yaml
verification_tiers:
  tier1_blocking: true
  tier1_command: "ruff check ."
  tier2_blocking: true
  tier2_command: "pytest tests/unit/"
  tier3_blocking: false
  tier3_command: "pytest --cov --cov-fail-under=80"
```

---

## TDD Enforcement

Enforces test-driven development practices when enabled.

### enabled

**What it does:** Master switch for TDD enforcement.

**Default:** `false` — TDD is opt-in since not all projects follow this methodology.

**When to enable:**
- Teams committed to TDD workflow
- New projects starting with TDD discipline
- Specific features where you want strict test-first development

**Example:**
```yaml
tdd:
  enabled: true
  enforce_red_green: true    # Require test failure before implementation
  anti_patterns:
    - mock_heavy             # Flag excessive mocking
    - testing_impl           # Flag testing implementation details
    - no_assertions          # Flag tests without assertions
```

---

## Improvement Loops

Controls iterative improvement cycles for refining work.

### enabled

**What it does:** Enables automatic improvement iterations.

**Default:** `true` — Improvement loops refine work quality.

---

### max_iterations

**What it does:** Maximum number of improvement cycles before stopping.

**Default:** `5` — Prevents infinite refinement loops.

**When to change it:**
- Decrease to 1-2 for quick tasks where iteration is unnecessary
- Increase to 8-10 for complex tasks benefiting from multiple refinement passes
- Set to 1 for CI/CD where you want single-pass execution

**Example:**
```yaml
improvement_loops:
  max_iterations: 1  # Single pass in CI
```

---

### plateau_threshold

**What it does:** Stops iterating when this many rounds show no improvement.

**Default:** `2` — Two rounds without improvement means further iteration is unlikely to help.

**When to change it:**
- Increase to 3-4 if improvements are sporadic and you want more chances
- Decrease to 1 for fast failure when first plateau is likely final

---

### rollback_on_regression

**What it does:** Reverts changes if an iteration makes things worse.

**Default:** `true` — Protects against iterations that decrease quality.

**When to disable:**
- When you prefer to see all iteration attempts, even regressions
- During exploratory work where "worse" is subjective
- Keep enabled for production quality assurance

---

### convergence_threshold

**What it does:** Minimum improvement required to count as "progress."

**Default:** `0.02` — 2% improvement is the minimum meaningful progress.

**When to change it:**
- Increase to 0.05-0.10 for stricter "real improvement" definition
- Decrease to 0.01 for more sensitive progress detection

---

## Behavioral Modes

Controls automatic mode detection for different task types.

### auto_detect

**What it does:** Automatically detects optimal mode from task keywords.

**Default:** `true` — Lets ZERG adapt behavior to task requirements.

---

### default_mode

**What it does:** Mode to use when auto-detection is inconclusive.

**Default:** `precision` — Careful, accurate work is the safest default.

**Available modes:**

| Mode | Behavior | Best For |
|------|----------|----------|
| `precision` | Careful, accurate | Critical code, security-sensitive |
| `speed` | Fast, efficient | Simple tasks, time-pressure |
| `exploration` | Creative, broad | Research, prototyping |
| `refactor` | Systematic, safe | Restructuring existing code |
| `debug` | Analytical, thorough | Bug investigation |

**Example:**
```yaml
behavioral_modes:
  auto_detect: true
  default_mode: speed        # For a fast-paced development cycle
  log_transitions: true      # See mode changes in logs
```

---

## Heartbeat Monitoring

Controls worker health monitoring.

### interval_seconds

**What it does:** How often workers write heartbeat files.

**Default:** `15` — Frequent enough to detect stalls quickly, not so often it is wasteful.

**When to change it:**
- Decrease to 5-10 for faster stall detection in critical environments
- Increase to 30-60 for lower overhead in stable environments

---

### stall_timeout_seconds

**What it does:** Declares a worker stalled if no heartbeat for this long.

**Default:** `120` (2 minutes) — Long enough for legitimate pauses, short enough to detect real stalls.

**When to change it:**
- Increase to 300-600 for tasks with known long-running operations
- Decrease to 60 for fast tasks where any pause is suspicious

---

### max_restarts

**What it does:** Number of times to restart a stalled worker before reassigning its task.

**Default:** `2` — Gives workers a chance to recover, but not indefinitely.

**Example:**
```yaml
heartbeat:
  interval_seconds: 10
  stall_timeout_seconds: 60   # Detect stalls fast
  max_restarts: 1             # Quick reassignment
```

---

## Security

Configure security boundaries and protections.

### level

**What it does:** Overall security posture.

**Default:** `standard` — Balanced security for most projects.

**Options:**
- `minimal` — Fewer restrictions, faster execution (development only)
- `standard` — Default protections for normal development
- `strict` — Maximum restrictions for sensitive projects

---

### pre_commit_hooks

**What it does:** Installs git pre-commit hooks for security checks.

**Default:** `true` — Catches issues before they enter version control.

---

### audit_logging

**What it does:** Logs all ZERG actions for audit purposes.

**Default:** `true` — Provides accountability and debugging information.

---

### network_isolation

**What it does:** Isolates worker network access.

**Default:** `true` — Prevents workers from making unauthorized network calls.

**When to disable:**
- Tasks that legitimately need network access (API clients, web scrapers)
- Development environments where network restrictions are unnecessary

---

### filesystem_sandbox

**What it does:** Restricts worker filesystem access to project directory.

**Default:** `true` — Prevents workers from accessing files outside the project.

---

### container_readonly

**What it does:** Mounts container filesystem as read-only.

**Default:** `true` — Prevents container escape attacks.

**When to disable:**
- Tasks that need to write to specific directories
- Combined with explicit volume mounts for necessary writes

---

### secrets_scanning

**What it does:** Scans for accidentally committed secrets.

**Default:** `true` — Prevents credential leaks.

---

## Resources

Configure resource limits for container mode workers.

### cpu_cores / memory_gb / disk_gb

**What it does:** Resource limits for container workers.

**Defaults:** `cpu_cores: 2`, `memory_gb: 4`, `disk_gb: 10`

**When to change:**
- Increase for resource-intensive tasks (large compilations, test suites)
- Decrease for simple tasks to allow more concurrent workers
- Match your CI runner resources

**Example:**
```yaml
resources:
  cpu_cores: 4
  memory_gb: 8
  disk_gb: 20          # Large project with many dependencies
```

---

### container_memory_limit / container_cpu_limit

**What it does:** Docker-specific limits passed to container runtime.

**Defaults:** `container_memory_limit: "4g"`, `container_cpu_limit: 2.0`

**Example:**
```yaml
resources:
  container_memory_limit: "8g"
  container_cpu_limit: 4.0
```

---

## Logging

Configure ZERG logging behavior.

### level

**What it does:** Minimum log level to record.

**Default:** `info` — Captures important events without excessive noise.

**Options:** `debug`, `info`, `warning`, `error`

**When to change:**
- Use `debug` when troubleshooting ZERG issues
- Use `warning` for quieter production runs

---

### directory

**What it does:** Where log files are written.

**Default:** `.zerg/logs` — Keeps logs with other ZERG state.

---

### retain_days

**What it does:** Days to keep log files before automatic deletion.

**Default:** `7` — One week of history for debugging.

**When to change:**
- Increase to 30+ for compliance or audit requirements
- Decrease to 1-3 to save disk space in CI environments

---

## Environment Variables

### Required Variables

| Variable | Description | When Needed |
|----------|-------------|-------------|
| `ANTHROPIC_API_KEY` | Claude API key | Container and subprocess modes |

### ZERG-Set Variables

These are set automatically by the orchestrator. You do not configure them, but workers can read them:

| Variable | Description |
|----------|-------------|
| `ZERG_WORKER_ID` | Worker identifier (0-N) |
| `ZERG_FEATURE` | Current feature name |
| `ZERG_BRANCH` | Worker's git branch |
| `ZERG_WORKTREE` | Worker's git worktree path |
| `ZERG_ANALYSIS_DEPTH` | Analysis tier setting |
| `ZERG_COMPACT_MODE` | Compact output mode flag |
| `ZERG_MCP_HINT` | Recommended MCP servers |
| `CLAUDE_CODE_TASK_LIST_ID` | Shared task list for coordination |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `info` | Overrides config logging level |
| `DEBUG` | `false` | Enable verbose debug output |
| `CI` | unset | Signals CI environment |

### Security: Filtered Variables

ZERG intentionally blocks certain variables from passing to workers:

**Blocked (security risk):**
- `LD_PRELOAD`, `DYLD_INSERT_LIBRARIES` — Library injection
- `PYTHONPATH` — Code injection path
- `HOME`, `USER`, `SHELL` — Identity information

**Allowed:**
- `ZERG_*` — All ZERG-specific variables
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` — API credentials
- `CI`, `DEBUG`, `LOG_LEVEL` — Environment flags

---

## Profile Configurations

### For Speed (Fast Development)

Use when rapid iteration matters more than thorough validation:

```yaml
workers:
  max_concurrent: 8
  timeout_minutes: 30
  context_threshold_percent: 80

quality_gates:
  - name: lint
    command: ruff check .
    required: true
    timeout: 60
  - name: test
    command: pytest tests/unit/ -x --timeout=10
    required: true
    timeout: 120

improvement_loops:
  max_iterations: 1
```

### For Reliability (Production Quality)

Use when correctness and stability are paramount:

```yaml
workers:
  max_concurrent: 3
  retry_attempts: 5
  context_threshold_percent: 60

quality_gates:
  - name: lint
    command: ruff check . --select ALL
    required: true
  - name: typecheck
    command: mypy . --strict
    required: true
  - name: test
    command: pytest --cov --cov-fail-under=85
    required: true
  - name: security
    command: bandit -r src/
    required: true

error_recovery:
  circuit_breaker:
    failure_threshold: 5
    cooldown_seconds: 120
```

### For Large Features

Use for complex features with many interdependent tasks:

```yaml
workers:
  max_concurrent: 10
  timeout_minutes: 120

improvement_loops:
  max_iterations: 3
  plateau_threshold: 3

heartbeat:
  interval_seconds: 10
  stall_timeout_seconds: 180
```

### For CI/CD Pipelines

Use for automated, unattended execution:

```yaml
workers:
  max_concurrent: 5
  timeout_minutes: 60

quality_gates:
  - name: lint
    command: ruff check . --select ALL
    required: true
  - name: test
    command: pytest --cov --cov-fail-under=80 --junitxml=results.xml
    required: true
  - name: security
    command: bandit -r src/ -f json -o bandit-report.json
    required: true

logging:
  level: info
  retain_days: 30

improvement_loops:
  max_iterations: 1

verification:
  store_artifacts: true
```

---

## Directory Structure

ZERG maintains its state in the `.zerg/` directory:

```
.zerg/
├── config.yaml              # Main configuration file (you edit this)
├── hooks/
│   └── pre-commit           # Git pre-commit hook
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

---

## See Also

- [Getting Started](Getting-Started.md) — Initial setup and first run
- [Commands](Commands.md) — CLI reference for all ZERG commands
- [Plugins](Plugins.md) — Plugin development and hooks
