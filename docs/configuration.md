# ZERG Configuration Guide

Complete reference for configuring ZERG — config files, environment variables, quality gates, logging, plugins, and tuning.

---

## Table of Contents

- [Configuration File](#configuration-file)
- [Workers](#workers)
- [Quality Gates](#quality-gates)
- [Pre-commit Hooks](#pre-commit-hooks)
- [Logging](#logging)
- [Plugins](#plugins)
- [Context Engineering](#context-engineering)
- [Security](#security)
- [MCP Servers](#mcp-servers)
- [Environment Variables](#environment-variables)
- [Container Mode](#container-mode)
- [Tuning Guide](#tuning-guide)

---

## Configuration File

Location: `.zerg/config.yaml`

Created automatically by `zerg init`. All settings have sensible defaults.

### Full Example

```yaml
version: "1.0"
project_type: python

workers:
  default_count: 5
  max_count: 10
  context_threshold: 0.7
  timeout_seconds: 3600
  retry_attempts: 3

security:
  network_isolation: true
  filesystem_sandbox: true
  secrets_scanning: true

quality_gates:
  lint:
    command: "ruff check ."
    required: true
  typecheck:
    command: "mypy ."
    required: false
  test:
    command: "pytest"
    required: true

hooks:
  pre_commit:
    enabled: true
    security_checks:
      secrets_detection: true
      shell_injection: true
      block_on_violation: true
    quality_checks:
      ruff_lint: true
      warn_on_violation: true

plugins:
  enabled: true
  hooks:
    - event: level_complete
      command: echo "Level {level} done"
      timeout: 60
  quality_gates:
    - name: security-scan
      command: bandit -r src/
      required: false
      timeout: 300

mcp_servers:
  - name: filesystem
    command: npx
    args: ["-y", "@anthropic/mcp-filesystem"]
```

---

## Workers

Control zergling behavior and resource allocation.

```yaml
workers:
  default_count: 5        # Default workers for /zerg:rush
  max_count: 10           # Hard limit on concurrent workers
  context_threshold: 0.7  # Checkpoint at this context usage (0.0-1.0)
  timeout_seconds: 3600   # Max time per worker session
  retry_attempts: 3       # Max retries per task before marking blocked
```

| Setting | Range | Default | Description |
|---------|-------|---------|-------------|
| `default_count` | 1-10 | 5 | Workers spawned when count not specified |
| `max_count` | 1-10 | 10 | Never exceed this many concurrent workers |
| `context_threshold` | 0.1-1.0 | 0.7 | Workers checkpoint at this context usage |
| `timeout_seconds` | 60-86400 | 3600 | Kill worker after this many seconds |
| `retry_attempts` | 1-10 | 3 | Retries before marking a task blocked |

### Worker Count Guidelines

| Workers | Best For |
|---------|----------|
| 1-2 | Small features, learning ZERG |
| 3-5 | Medium features, balanced throughput |
| 6-10 | Large features, maximum parallelism |

Diminishing returns beyond the widest level's parallelizable tasks.

---

## Quality Gates

Quality gates run after each level merge. They validate the merged code before workers proceed to the next level.

```yaml
quality_gates:
  lint:
    command: "ruff check ."
    required: true
  typecheck:
    command: "mypy . --ignore-missing-imports"
    required: false
  test:
    command: "pytest tests/ -v --tb=short"
    required: true
```

| Field | Description | Default |
|-------|-------------|---------|
| `command` | Shell command to run | Required |
| `required` | If `true`, failure blocks the merge | `true` |

### Gate Results

| Result | Meaning | Action |
|--------|---------|--------|
| `pass` | Exit code 0 | Continue to next level |
| `fail` | Non-zero exit | Block merge if `required: true` |
| `timeout` | Exceeded limit | Treated as failure |
| `error` | Could not run | Pause for intervention |

### Adding Custom Gates

Via YAML (simple shell commands):

```yaml
plugins:
  quality_gates:
    - name: security-scan
      command: bandit -r src/ --severity medium
      required: false
      timeout: 300
```

Via Python entry points (complex logic): See [Plugin System](plugins.md).

---

## Pre-commit Hooks

ZERG installs comprehensive pre-commit hooks at `.zerg/hooks/pre-commit`.

```yaml
hooks:
  pre_commit:
    enabled: true
    security_checks:
      secrets_detection: true
      shell_injection: true
      block_on_violation: true
    quality_checks:
      ruff_lint: true
      warn_on_violation: true
```

### Security Checks (Block Commit)

These patterns cause commits to be rejected:

| Check | Description |
|-------|-------------|
| AWS Keys | AWS Access Key IDs |
| GitHub PATs | Personal Access Tokens |
| OpenAI Keys | OpenAI API Keys |
| Anthropic Keys | Anthropic API Keys |
| Private Keys | PEM key file headers |
| Dangerous shell patterns | Unsafe subprocess usage |
| Dynamic code patterns | Unsafe dynamic code patterns |
| Unsafe deserialization | Unsafe deserialization patterns |
| Sensitive Files | `.env`, `credentials.json` |

### Quality Checks (Warn Only)

| Check | Description |
|-------|-------------|
| Ruff Lint | Style issues in Python files |
| Debugger statements | Debug breakpoints left in code |
| Merge Markers | Unresolved conflict markers |
| Large Files | Files over 5MB |

### ZERG-Specific Checks (Warn Only)

| Check | Validation |
|-------|------------|
| Branch Naming | `zerg/{feature}/worker-{N}` format |
| Print Statements | `print` calls in `zerg/` directory |
| Hardcoded URLs | `localhost:PORT` outside tests |

### Exempt Paths

Tests and fixtures are exempt: `tests/`, `fixtures/`, `*_test.py`, `test_*.py`, `conftest.py`

---

## Logging

ZERG uses structured JSONL logging with per-worker and per-task output.

### Log Locations

| Type | Path | Format |
|------|------|--------|
| Worker logs | `.zerg/logs/workers/worker-{id}.jsonl` | Structured JSONL |
| Orchestrator | `.zerg/logs/orchestrator.jsonl` | Structured JSONL |
| Task execution | `.zerg/logs/tasks/{TASK-ID}/execution.jsonl` | Structured JSONL |
| Claude output | `.zerg/logs/tasks/{TASK-ID}/claude_output.txt` | Plain text |
| Verification | `.zerg/logs/tasks/{TASK-ID}/verification_output.txt` | Plain text |
| Git diff | `.zerg/logs/tasks/{TASK-ID}/git_diff.patch` | Patch format |

### JSONL Entry Format

```json
{
  "ts": "2026-01-28T10:30:45.123Z",
  "level": "info",
  "worker_id": 0,
  "feature": "user-auth",
  "message": "Task T1.1 started",
  "task_id": "T1.1",
  "phase": "execute",
  "event": "task_started",
  "data": {},
  "duration_ms": null
}
```

### Log Rotation

Worker logs auto-rotate at 50 MB (renamed to `.jsonl.1`).

### Aggregation

`LogAggregator` merges JSONL files by timestamp at query time. No pre-built aggregate file exists on disk. Use `zerg logs --aggregate` to query across all workers.

---

## Plugins

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
```

See the [Plugin System](plugins.md) documentation for Python entry point plugins, the security model, and examples.

### Context Engineering Plugin

The context engineering plugin minimizes token usage across workers. See [Context Engineering](context-engineering.md) for full details.

```yaml
plugins:
  context_engineering:
    enabled: true                    # Master switch
    command_splitting: true          # Split large commands into core/details
    security_rule_filtering: true    # Filter security rules by task file types
    task_context_budget_tokens: 4000 # Max tokens per task context
    fallback_to_full: true           # Fall back to full context on errors
```

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | `true` | Enable/disable all context engineering |
| `command_splitting` | `true` | Split commands into .core.md and .details.md |
| `security_rule_filtering` | `true` | Filter security rules by task file types |
| `task_context_budget_tokens` | `4000` | Maximum tokens for task-scoped context |
| `fallback_to_full` | `true` | If context engineering fails, load full context |

### Hook Event Types

| Event | When |
|-------|------|
| `task_started` | Worker begins task |
| `task_completed` | Task passes verification |
| `level_complete` | All tasks in level done |
| `merge_complete` | Level branches merged |
| `worker_spawned` | New worker starts |
| `quality_gate_run` | Gate runs |
| `rush_started` | `/zerg:rush` begins |
| `rush_finished` | All levels complete |

### Variable Substitution

Hook commands support: `{level}`, `{feature}`, `{task_id}`, `{worker_id}`

---

## Security

```yaml
security:
  network_isolation: true
  filesystem_sandbox: true
  secrets_scanning: true
```

### Environment Variable Filtering

ZERG controls which environment variables are passed to workers:

**Allowed**:
- `ZERG_WORKER_ID`, `ZERG_FEATURE`, `ZERG_WORKTREE`
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`
- `CI`, `DEBUG`, `LOG_LEVEL`

**Blocked**:
- `LD_PRELOAD`, `DYLD_INSERT_LIBRARIES`
- `PYTHONPATH`, `HOME`, `USER`, `SHELL`

### Command Safety

| Protection | Implementation |
|------------|----------------|
| No shell=True | Commands parsed with shlex |
| Allowlist | Commands checked against config |
| Timeout | Every command has max duration |
| Output capture | Separate stdout/stderr |

### Task ID Validation

Task IDs are validated against: `[A-Za-z][A-Za-z0-9_-]{0,63}`

Rejects shell metacharacters, path traversal, and IDs longer than 64 chars.

---

## MCP Servers

Configure MCP servers available to workers:

```yaml
mcp_servers:
  - name: filesystem
    command: npx
    args: ["-y", "@anthropic/mcp-filesystem", "/workspace"]
  - name: github
    command: npx
    args: ["-y", "@anthropic/mcp-github"]
```

MCP server configuration is copied to worker containers at `.devcontainer/mcp-servers/config.json`.

---

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
| `CLAUDE_CODE_TASK_LIST_ID` | Shared task list for coordination |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Logging verbosity | `info` |
| `DEBUG` | Enable debug output | `false` |
| `CI` | CI environment flag | unset |

---

## Container Mode

### Setup

```bash
# 1. Initialize with container support
zerg init --with-containers

# 2. Build the devcontainer image
devcontainer build --workspace-folder .

# 3. Run with container mode
zerg rush --mode container --workers 5
```

### Authentication

Container workers authenticate via two methods:

| Method | How | Best For |
|--------|-----|----------|
| **OAuth** | Mount `~/.claude` into container | Claude Pro/Team accounts |
| **API Key** | Pass `ANTHROPIC_API_KEY` env var | API key authentication |

### Container Configuration

The devcontainer is configured at `.devcontainer/devcontainer.json`:

```json
{
  "name": "project-zerg",
  "build": {
    "dockerfile": "Dockerfile",
    "context": ".."
  },
  "mounts": [
    "source=${localWorkspaceFolder},target=/workspace,type=bind",
    "source=zerg-claude-tasks,target=/root/.claude/tasks,type=volume"
  ],
  "containerEnv": {
    "CLAUDE_CODE_TASK_LIST_ID": "${localEnv:ZERG_FEATURE}",
    "ZERG_WORKER_ID": "${localEnv:ZERG_WORKER_ID:-0}"
  }
}
```

### Docker Network

Container mode creates a `zerg-internal` Docker network for worker isolation. Workers communicate via state files mounted from the host.

---

## Tuning Guide

### For Speed

```yaml
workers:
  default_count: 8       # More workers
  timeout_seconds: 1800  # Shorter timeout
  context_threshold: 0.8 # Use more context before checkpoint
```

### For Reliability

```yaml
workers:
  default_count: 3          # Fewer workers, less contention
  retry_attempts: 5         # More retries
  context_threshold: 0.6    # Checkpoint earlier

quality_gates:
  lint:
    required: true
  typecheck:
    required: true
  test:
    required: true
```

### For Large Features

```yaml
workers:
  default_count: 10
  max_count: 10
  timeout_seconds: 7200  # 2 hours per worker
```

### For CI/CD

```yaml
workers:
  default_count: 5
  timeout_seconds: 3600

quality_gates:
  lint:
    command: "ruff check . --select ALL"
    required: true
  test:
    command: "pytest --cov --cov-fail-under=80"
    required: true
  security:
    command: "bandit -r src/"
    required: true
```

---

## Directory Structure Reference

```
.zerg/
├── config.yaml              # Main configuration file
├── hooks/
│   └── pre-commit           # Pre-commit hook script
├── state/
│   └── {feature}.json       # Runtime state per feature
└── logs/
    ├── workers/
    │   └── worker-{id}.jsonl  # Structured per-worker logs
    ├── tasks/
    │   └── {TASK-ID}/         # Per-task artifacts
    │       ├── execution.jsonl
    │       ├── claude_output.txt
    │       ├── verification_output.txt
    │       └── git_diff.patch
    └── orchestrator.jsonl     # Orchestrator log
```
