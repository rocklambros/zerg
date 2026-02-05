# Frequently Asked Questions

Common questions about ZERG, organized by topic. For detailed documentation, see the linked wiki pages.

---

## Getting Started

### What is ZERG and how is it different from regular Claude Code?

ZERG (Zero-Effort Rapid Growth) is a parallel execution system that coordinates multiple Claude Code instances to build features simultaneously. While regular Claude Code runs as a single agent working sequentially through tasks, ZERG:

- **Breaks work into atomic tasks** with exclusive file ownership
- **Launches multiple workers** (called "zerglings") to execute tasks in parallel
- **Organizes tasks by dependency levels** so workers complete Level 1 before starting Level 2
- **Auto-fetches security rules** based on your detected tech stack
- **Engineers context per worker** to minimize token usage

A feature that takes one Claude Code instance 2 hours might take a ZERG swarm 20 minutes.

### How do I install ZERG?

```bash
# Clone and install
git clone https://github.com/rocklambros/zerg.git
cd zerg
pip install -e ".[dev]"
pre-commit install

# Install slash commands into your project
zerg install

# Verify
zerg --help
```

**Prerequisites**: Python 3.12+, Claude Code CLI, Git. Docker is optional (required for container mode).

See [Home](Home) for complete installation instructions.

### What's the minimum setup needed to start using ZERG?

1. Run `zerg install` in your project to install slash commands
2. Inside Claude Code: `/zerg:init` to initialize ZERG infrastructure
3. `/zerg:plan my-feature` to capture requirements
4. `/zerg:design` to generate architecture and tasks
5. `/zerg:rush --workers=3` to launch workers

That's it. ZERG auto-detects your tech stack, fetches security rules, and creates the configuration file.

---

## Execution Modes

### What's the difference between task, subprocess, and container modes?

ZERG supports three worker execution modes:

| Mode | Description | Best For |
|------|-------------|----------|
| `task` | Claude Code Task sub-agents running within your session | Running from slash commands inside Claude Code (default) |
| `subprocess` | Local Python subprocesses | Development, testing, no Docker needed |
| `container` | Isolated Docker containers | Production, full isolation, maximum security |

**Auto-detection**: If `--mode` is not specified, ZERG picks the best option:
1. If running inside Claude Code slash command context: `task`
2. If `.devcontainer/` exists and Docker is available: `container`
3. Otherwise: `subprocess`

### When should I use container mode?

Use container mode (`--mode container`) when you need:

- **Full isolation**: Each worker runs in its own container with network isolation
- **Security boundaries**: Filesystem sandboxing, read-only root, dropped capabilities
- **Reproducible environments**: Consistent execution regardless of host machine state
- **Production deployments**: When you want workers isolated from each other and the host

Container mode requires Docker and will use authentication from `~/.claude` (OAuth) or `ANTHROPIC_API_KEY` (API key).

### How many workers should I use?

| Workers | Use Case |
|---------|----------|
| 1-2 | Small features, learning ZERG, testing |
| 3-5 | Medium features, balanced throughput |
| 6-10 | Large features with many parallelizable tasks |

**Key insight**: Diminishing returns occur beyond the widest level's parallelizable task count. If Level 2 has only 3 tasks, using 10 workers won't help Level 2 complete faster.

Check your task graph with `/zerg:status` to see tasks per level before choosing worker count.

---

## Git & Branching

### How does ZERG handle git branches?

ZERG uses a structured branching model:

1. **Worker branches**: Each worker gets its own branch: `zerg/{feature}/worker-{N}`
2. **Staging branch**: `zerg/{feature}/staging` for level merges
3. **Main branch**: Final destination after all levels complete

**Per-level flow**:
1. Workers commit to their branches during task execution
2. After all Level N tasks complete, orchestrator merges all worker branches into staging
3. Quality gates run on staging
4. Staging merges to main (or next level continues)

Workers never commit directly to main. The orchestrator controls all merges.

### What are worktrees and why are they used?

Git worktrees allow ZERG to have multiple working directories from the same repository, each with its own branch. Each worker operates in its own worktree:

```
.zerg-worktrees/{feature}-worker-0/  ->  branch: zerg/{feature}/worker-0
.zerg-worktrees/{feature}-worker-1/  ->  branch: zerg/{feature}/worker-1
```

**Benefits**:
- Workers can edit files simultaneously without filesystem conflicts
- Each worker has independent git state (staging area, index)
- Workers commit independently, orchestrator merges
- Worktrees are gitignored and auto-cleaned

Worktrees are managed automatically by `/zerg:rush` and cleaned by `/zerg:cleanup`.

### How do I resolve merge conflicts?

ZERG's exclusive file ownership model prevents most merge conflicts. Each task declares which files it creates/modifies, and the design phase ensures no overlap within a level.

However, conflicts can occur when:
- Two tasks modify the same file across different levels
- Manual edits conflict with worker changes

**Resolution**:
1. ZERG pauses on merge conflict
2. Run `/zerg:status` to see which branches conflict
3. Manually resolve conflicts in the staging branch
4. Run `/zerg:merge --continue` to proceed

To prevent conflicts: ensure task file ownership is exclusive in `task-graph.json`.

---

## Quality Gates

### What quality gates run automatically?

Quality gates run after each level merge. Default gates (configurable in `.zerg/config.yaml`):

| Gate | Command | Required |
|------|---------|----------|
| `lint` | `ruff check .` | Yes |
| `test` | `pytest` | Yes |
| `typecheck` | `mypy .` | No |

**Results**:
- `pass`: Exit code 0, continue to next level
- `fail`: Non-zero exit, blocks merge if `required: true`
- `timeout`: Exceeded time limit, treated as failure

See [Configuration](Configuration) for gate configuration options.

### How do I add custom quality gates?

Add gates in `.zerg/config.yaml`:

```yaml
quality_gates:
  - name: security-scan
    command: bandit -r src/ --severity medium
    required: false
    timeout: 300
  - name: coverage
    command: pytest --cov=src --cov-fail-under=80
    required: true
    timeout: 180
```

For complex gates, use Python plugins. See [Plugins](Plugins) for the `QualityGatePlugin` API.

### Can I skip quality gates?

Yes, but not recommended for production:

```bash
/zerg:merge --skip-gates        # Skip all gates
/zerg:merge --skip-gate lint    # Skip specific gate
```

You can also make gates non-blocking by setting `required: false` in config. Non-blocking gates warn but don't stop merges.

---

## Containers

### How does container authentication work?

ZERG containers authenticate via two methods:

| Method | How | Best For |
|--------|-----|----------|
| **OAuth** | Mount `~/.claude` into container | Claude Pro/Team accounts |
| **API Key** | Pass `ANTHROPIC_API_KEY` env var | API key authentication |

The orchestrator auto-detects which method to use based on available credentials.

For OAuth, your `~/.claude` directory is mounted read-only into containers.

### What resources do containers get?

Default container resources (configurable in `.zerg/config.yaml`):

```yaml
resources:
  container_memory_limit: "4g"
  container_cpu_limit: 2.0
```

Additional container settings:
- Read-only root filesystem
- All capabilities dropped
- Network isolation (optional)
- 10 ports per worker (range 49152-65535)

### How do I troubleshoot container issues?

Common container problems:

| Issue | Diagnosis | Solution |
|-------|-----------|----------|
| Containers not starting | `docker info` fails | Start Docker daemon |
| Authentication errors | Missing credentials | Set `ANTHROPIC_API_KEY` or ensure `~/.claude` exists |
| Out of memory | Container OOM killed | Increase `container_memory_limit` |
| Permission denied | Mount issues | Check `~/.claude` permissions |

Debug commands:
```bash
/zerg:debug --env              # Check environment
/zerg:logs --worker 0          # View specific worker logs
docker ps -a                   # List all containers
docker logs zerg-worker-0      # View container logs
```

---

## Context & Tokens

### How does context engineering reduce token usage?

ZERG uses three subsystems to minimize per-worker token usage by 30-50%:

1. **Command Splitting**: Large command files (>300 lines) are split into `.core.md` (~30% essential) and `.details.md` (~70% reference). Workers load core by default.

2. **Security Rule Filtering**: Instead of loading all security rules, ZERG filters by file extension. A worker editing `.py` files gets Python rules only.

3. **Task-Scoped Context**: Each task gets a `context` field with relevant spec excerpts, not the full spec files.

See [Context-Engineering](Context-Engineering) for configuration details.

### What's the token budget per task?

Default: 4000 tokens per task context (configurable).

```yaml
plugins:
  context_engineering:
    task_context_budget_tokens: 4000
```

This budget covers:
- Relevant spec excerpts from `requirements.md` and `design.md`
- Dependency context from upstream tasks
- Filtered security rules matching task file types

If context engineering fails, workers fall back to full files (if `fallback_to_full: true`).

### How is command splitting different from task context?

| Feature | Command Splitting | Task Context |
|---------|------------------|--------------|
| **What** | Splits command instruction files | Scopes spec content per task |
| **When** | Worker loads command | Worker loads task assignment |
| **Savings** | ~2,000-5,000 tokens/worker | ~2,000-5,000 tokens/task |
| **Scope** | 9 large commands split | Every task in task-graph |

Both work together: a worker loads the `.core.md` command file and its task's scoped context, rather than full command files and full spec files.

---

## Plugins

### What plugin types are supported?

ZERG supports three plugin types:

| Type | Purpose | Example Use Case |
|------|---------|------------------|
| **Quality Gate** | Custom validation after merges | SonarQube scans, security gates, license checks |
| **Lifecycle Hook** | React to events (non-blocking) | Slack notifications, metrics collection, CI triggers |
| **Launcher** | Custom worker execution environments | Kubernetes pods, SSH clusters, cloud VMs |

Plugins can be YAML-configured (shell commands) or Python classes (entry points).

### How do I create a custom plugin?

**YAML Hook** (simple):
```yaml
plugins:
  hooks:
    - event: level_complete
      command: ./scripts/notify.sh "Level {level} done"
      timeout: 60
```

**Python Plugin** (advanced):
```python
from zerg.plugins import QualityGatePlugin, GateContext
from zerg.types import GateRunResult
from zerg.constants import GateResult

class SonarQubeGate(QualityGatePlugin):
    @property
    def name(self) -> str:
        return "sonarqube"

    def run(self, ctx: GateContext) -> GateRunResult:
        # Your validation logic
        return GateRunResult(
            gate_name=self.name,
            result=GateResult.PASS,
            command="sonar-scanner",
            exit_code=0,
            stdout="Quality gate passed"
        )
```

See [Plugins](Plugins) for the complete API reference.

### Where are plugins configured?

Plugins are configured in `.zerg/config.yaml` under the `plugins` section:

```yaml
plugins:
  enabled: true

  hooks:
    - event: task_completed
      command: echo "Task done"

  quality_gates:
    - name: custom-gate
      command: ./scripts/validate.sh
      required: true

  context_engineering:
    enabled: true
```

Python plugins are discovered via `importlib.metadata` entry points (group: `zerg.plugins`). Add them to your `pyproject.toml`:

```toml
[project.entry-points."zerg.plugins"]
my-gate = "my_package.gates:MyGatePlugin"
```

---

## See Also

- [Home](Home) - Project overview and quick start
- [Command-Reference](Command-Reference) - All 26 commands with flags and examples
- [Configuration](Configuration) - Complete config file reference
- [Architecture](Architecture) - System design and module reference
- [Troubleshooting](Troubleshooting) - Common issues and diagnostics
- [Plugins](Plugins) - Plugin development guide
