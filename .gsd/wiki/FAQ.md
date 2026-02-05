# Frequently Asked Questions

Common questions about ZERG, organized by topic. Each answer provides context, rationale, and cross-references to help you understand not just the "what" but the "why" behind ZERG's design.

---

## Getting Started

### What is ZERG and how is it different from regular Claude Code?

ZERG (Zero-Effort Rapid Growth) is a parallel execution system that coordinates multiple Claude Code instances to build features simultaneously. While regular Claude Code runs as a single agent working sequentially through tasks, ZERG fundamentally changes the development model by introducing parallelism, isolation, and spec-driven coordination.

The key insight behind ZERG is that most software features can be decomposed into independent work units that share no files within a given phase. By enforcing exclusive file ownership and organizing tasks into dependency levels, ZERG eliminates merge conflicts while maximizing parallel throughput. A single Claude Code instance might take 2 hours to implement a feature with 20 tasks; a ZERG swarm of 5 workers can complete the same work in 20-30 minutes by executing tasks concurrently within each level.

Unlike regular Claude Code, ZERG workers are stateless. They read specification documents fresh each time rather than relying on conversation history. This design enables crash recovery, restartability, and true parallelism since workers share no state. The orchestrator coordinates everything through the Claude Code Task system, which serves as the authoritative backbone for tracking progress across all workers.

This architecture also enables ZERG to auto-fetch security rules based on your detected tech stack and engineer context per worker to minimize token usage. Each worker receives only the instructions and context relevant to its assigned task, reducing per-worker token consumption by 30-50%.

For more details on system layers and module responsibilities, see [Architecture](Architecture).

### How do I install ZERG?

ZERG installation involves two steps: installing the Python package and installing the slash commands into your project. The package provides the core orchestration logic, while the slash commands integrate ZERG into your Claude Code workflow.

```bash
# Clone and install the package
git clone https://github.com/rocklambros/zerg.git
cd zerg
pip install -e ".[dev]"
pre-commit install

# Install slash commands into your project
cd /path/to/your/project
zerg install

# Verify installation
zerg --help
```

The `zerg install` command copies command files into your project's `.claude/commands/` directory, making them available as `/zerg:*` commands within Claude Code sessions. This approach keeps command definitions version-controlled with your project and allows customization.

Prerequisites include Python 3.12+, the Claude Code CLI (installed and authenticated), and Git. Docker is optional but required for container mode execution, which provides full worker isolation. If you plan to use container mode, ensure Docker is running and your user has permission to run containers.

After installation, run `/zerg:init` inside a Claude Code session to create the `.zerg/` directory structure, generate the default configuration file, and fetch security rules for your detected tech stack.

For complete installation instructions and first-run guidance, see [Home](Home).

### What's the minimum setup needed to start using ZERG?

The minimum setup to go from zero to a working ZERG swarm involves five commands, each representing a distinct phase of the ZERG workflow. Understanding what each phase does helps you use ZERG effectively.

1. **`zerg install`** (in terminal): Installs slash commands into your project, making `/zerg:*` commands available
2. **`/zerg:init`** (in Claude Code): Creates ZERG infrastructure (`.zerg/` directory, config file, security rules)
3. **`/zerg:plan my-feature`**: Captures requirements through interactive dialogue, generating `requirements.md`
4. **`/zerg:design`**: Analyzes requirements to produce architecture documentation and a task graph with dependency levels
5. **`/zerg:rush --workers=3`**: Launches workers to execute the task graph in parallel

ZERG auto-detects your tech stack from files like `pyproject.toml`, `package.json`, and `Dockerfile`, then fetches appropriate security rules. It also creates a sensible default configuration file that works for most projects.

After your first successful run, subsequent features only require the plan-design-rush cycle. The infrastructure setup (`init`) is a one-time operation per project.

For a complete walkthrough of building your first feature, see [Tutorial](Tutorial).

---

## Execution Modes

### What's the difference between task, subprocess, and container modes?

ZERG supports three worker execution modes, each with different isolation characteristics, resource requirements, and use cases. Understanding these trade-offs helps you choose the right mode for your situation.

| Mode | Description | Isolation Level | Resource Overhead |
|------|-------------|-----------------|-------------------|
| `task` | Claude Code Task sub-agents running within your session | Shared process | Minimal |
| `subprocess` | Local Python subprocesses | Separate processes | Low |
| `container` | Isolated Docker containers | Full OS-level isolation | Moderate |

**Task mode** is the default when running from Claude Code slash commands. Workers execute as Task sub-agents within your Claude Code session, sharing the same process space. This mode has minimal overhead and is ideal for typical development workflows. However, workers share filesystem access with the parent session.

**Subprocess mode** spawns separate Python processes for each worker. Each worker runs `zerg.worker_main` in its own process, providing memory isolation between workers. This mode requires no Docker but still shares the host filesystem. It's useful for development, testing, and environments where Docker isn't available.

**Container mode** provides maximum isolation by running each worker in its own Docker container. Workers have sandboxed filesystems, network isolation, and resource limits (CPU, memory). The host worktree is mounted into each container, and workers authenticate via OAuth (`~/.claude` mount) or API key (`ANTHROPIC_API_KEY` environment variable). This mode is recommended for production deployments and security-sensitive work.

If `--mode` is not specified, ZERG auto-detects the best option based on your environment: task mode inside Claude Code sessions, container mode if Docker is available with a devcontainer configuration, otherwise subprocess mode.

For container configuration options and security settings, see [Configuration](Configuration).

### When should I use container mode?

Container mode is designed for scenarios where isolation, security, and reproducibility matter more than minimal overhead. Consider container mode when you need any of the following guarantees.

**Full process and filesystem isolation**: Each worker runs in its own container with an independent filesystem. One worker cannot read or write files outside its mounted worktree. If a worker somehow behaves unexpectedly, it cannot affect other workers or the host system beyond its designated scope.

**Security boundaries**: Containers run with dropped capabilities, read-only root filesystems, and optional network isolation. This defense-in-depth approach limits the blast radius of any potential security issue. Workers cannot install packages, modify system files, or access host resources outside explicit mounts.

**Reproducible environments**: Container images provide consistent execution environments regardless of host machine state. Workers always run in the same environment, eliminating "works on my machine" issues and ensuring predictable behavior across development, CI, and production.

**Production deployments**: When running ZERG in CI/CD pipelines or automated systems, container mode provides the isolation and resource limits necessary for safe multi-tenant execution.

Container mode does require Docker to be installed and running. Workers authenticate using either OAuth (by mounting `~/.claude` read-only into containers) or API key (by passing `ANTHROPIC_API_KEY` as an environment variable). Both authentication methods are implemented in the launcher and work transparently.

For container resource limits and security configuration, see [Configuration](Configuration).

### How many workers should I use?

Choosing the right worker count involves understanding your task graph's parallelization potential and balancing speedup against resource consumption. ZERG reports a "max parallelization" value during design—this is the maximum number of workers that can ever be simultaneously busy at any dependency level.

| Workers | Use Case | When to Choose |
|---------|----------|----------------|
| 1-2 | Small features, learning ZERG, testing | When you want to observe behavior or have < 5 tasks |
| 3-5 | Medium features, balanced throughput | Most common choice, good for 10-30 task features |
| 6-10 | Large features with many parallelizable tasks | When your task graph has wide levels (8+ tasks per level) |

**Understanding diminishing returns**: If Level 2 of your task graph has only 3 parallelizable tasks, using 10 workers means 7 workers sit idle during that level. The speedup is limited by the narrowest level, not by how many workers you deploy. Check your task graph with `/zerg:status` before choosing worker count—it shows tasks per level.

**Start conservative and scale up**: For your first few features, start with 4 workers. Use `/zerg:status` during execution to see if workers are frequently waiting for dependencies. If all workers stay busy throughout, try adding more. If workers often idle, reduce the count to avoid wasted resources.

**Resource considerations**: Each worker consumes memory, API tokens, and (in container mode) CPU allocation. More workers mean faster completion but higher concurrent resource usage. In CI environments with limited resources, fewer workers with longer timeouts may be more reliable than many workers competing for resources.

For worker configuration options and resource tuning recommendations, see [Configuration](Configuration).

---

## Git & Branching

### How does ZERG handle git branches?

ZERG uses a structured branching model that isolates worker changes while enabling clean, conflict-free merges. Understanding this model helps you reason about where your code lives and how it flows toward integration.

The branching hierarchy consists of three levels:

1. **Worker branches**: Each worker operates on its own branch named `zerg/{feature}/worker-{N}`. Workers commit their changes here during task execution, isolated from each other.

2. **Staging branch**: `zerg/{feature}/staging` serves as the integration point. After all workers complete a level, the orchestrator merges all worker branches into staging, runs quality gates, and resolves any cross-level conflicts.

3. **Main branch**: The final destination. After all levels complete and pass quality gates, the staging branch merges to main (or your designated target branch).

**Per-level merge flow**:
1. Workers commit to their individual branches as they complete tasks
2. When all Level N tasks complete, the orchestrator merges all worker branches into staging
3. Quality gates (lint, typecheck, test) run on the merged staging code
4. If gates pass, staging becomes the base for Level N+1 worker branches
5. Workers rebase onto the new staging state before starting the next level

Workers never commit directly to main. The orchestrator controls all merges, ensuring quality gates run on the integrated code before it reaches main. This model prevents half-finished work from reaching main while allowing parallel development.

For details on the merge process and quality gates, see [Architecture](Architecture).

### What are worktrees and why are they used?

Git worktrees are a feature that allows multiple working directories from the same repository, each checked out to a different branch. ZERG uses worktrees to give each worker its own isolated filesystem while sharing the underlying git repository.

```
.zerg-worktrees/{feature}-worker-0/  ->  branch: zerg/{feature}/worker-0
.zerg-worktrees/{feature}-worker-1/  ->  branch: zerg/{feature}/worker-1
```

**Why worktrees instead of separate clones?** Worktrees share the repository's object database, meaning git operations (commits, pushes, fetches) don't require network access to sync between workers. Creating a worktree is instant compared to cloning. And disk usage is minimal since object storage is shared.

**Isolation benefits**: Each worktree has its own working directory, staging area, and index. Worker 0 can stage and commit files without affecting Worker 1's state. Workers can edit the same file in different levels (since they work sequentially across levels, not concurrently on the same file).

**Lifecycle**: Worktrees are created automatically by `/zerg:rush` at the start of execution. Each worker operates entirely within its worktree directory. After execution completes, `/zerg:cleanup` removes worktrees to free disk space. The `.zerg-worktrees/` directory is gitignored, so worktrees are never committed.

**Debugging tip**: If you need to inspect a worker's state during execution, you can `cd` into its worktree directory and use standard git commands (`git status`, `git log`, `git diff`) to see exactly what that worker has done.

For more on worktree management and the cleanup process, see [Architecture](Architecture).

### How do I resolve merge conflicts?

ZERG's exclusive file ownership model is specifically designed to prevent merge conflicts. Each task in `task-graph.json` declares which files it creates and modifies, and the design phase ensures no two tasks at the same level touch the same file. This eliminates within-level conflicts entirely.

However, conflicts can still occur in two scenarios:

1. **Cross-level modifications**: Task A at Level 2 modifies `config.py`, and Task B at Level 3 also modifies `config.py`. These don't conflict during parallel execution (they're in different levels), but the merged result might have conflicts if both modified the same section.

2. **External changes**: You make manual edits on the staging branch while workers are executing, and those edits conflict with worker changes.

**When ZERG detects a conflict**, it pauses execution and reports the conflicting files and branches. To resolve:

1. Run `/zerg:status` to see which branches conflict and which files are affected
2. Check out the staging branch: `git checkout zerg/{feature}/staging`
3. Manually resolve conflicts using your preferred merge tool
4. Commit the resolution: `git add . && git commit -m "Resolve merge conflicts"`
5. Run `/zerg:merge --continue` to resume the merge process

**Prevention is better than resolution**: When designing tasks, ensure file ownership is truly exclusive. If two tasks need to modify the same file, either combine them into one task, split the file into separate files, or place the tasks in the same level so one depends on the other.

For merge process details and the `--continue` flag behavior, see [Command-Reference](Command-Reference).

---

## Quality Gates

### What quality gates run automatically?

Quality gates are validation commands that run after each level merge to verify the integrated code meets quality standards. They provide automated checkpoints that catch issues before they propagate to subsequent levels or reach the main branch.

Default gates (configurable in `.zerg/config.yaml`):

| Gate | Command | Purpose | Default Required |
|------|---------|---------|------------------|
| `lint` | `ruff check .` | Code style and static analysis | Yes |
| `test` | `pytest` | Unit and integration tests | Yes |
| `typecheck` | `mypy .` | Static type checking | No |

**Gate execution and results**:
- **Pass** (exit code 0): Continue to next level or final merge
- **Fail** (non-zero exit): If `required: true`, blocks the merge and pauses execution
- **Timeout** (exceeded time limit): Treated as failure
- **Error** (command couldn't run): Pauses for manual intervention

When a required gate fails, ZERG pauses and reports the failure. You can inspect the gate output, fix the issues, and resume with `/zerg:merge --continue`. Non-required gates warn but don't block—useful for advisory checks like coverage thresholds.

**Why run gates after level merges?** Individual workers verify their own tasks, but that doesn't guarantee the combined changes work together. A Level 2 task might pass verification in isolation but break a Level 1 feature when merged. Level gates catch these integration issues early, before building on a broken foundation.

For gate configuration options and adding custom gates, see [Configuration](Configuration).

### How do I add custom quality gates?

Custom gates let you extend ZERG's validation beyond the defaults. You might add security scanning, coverage thresholds, documentation checks, or project-specific validations.

**YAML configuration** (simple shell commands):

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
  - name: docs-check
    command: mkdocs build --strict
    required: false
    timeout: 120
```

**Python plugins** (complex logic, external integrations):

```python
from zerg.plugins import QualityGatePlugin, GateContext
from zerg.types import GateRunResult
from zerg.constants import GateResult

class SonarQubeGate(QualityGatePlugin):
    @property
    def name(self) -> str:
        return "sonarqube"

    def run(self, ctx: GateContext) -> GateRunResult:
        # Call SonarQube API, parse results, decide pass/fail
        # Access ctx.feature, ctx.level, ctx.staging_branch
        return GateRunResult(
            gate_name=self.name,
            result=GateResult.PASS,
            command="sonar-scanner",
            exit_code=0,
            stdout="Quality gate passed"
        )
```

Python plugins are discovered via entry points (group: `zerg.plugins`). Add them to your `pyproject.toml`:

```toml
[project.entry-points."zerg.plugins"]
sonarqube-gate = "my_package.gates:SonarQubeGate"
```

**Choosing between YAML and Python**: Use YAML for simple shell commands that return pass/fail via exit codes. Use Python when you need to call APIs, parse complex output, maintain state, or implement conditional logic.

For the complete plugin API and hook event types, see [Plugins](Plugins).

### Can I skip quality gates?

Yes, but understand the implications before doing so. Skipping gates trades confidence for speed—acceptable during development or debugging, but risky for production code.

**Skipping all gates**:
```bash
/zerg:merge --skip-gates
```

**Skipping a specific gate**:
```bash
/zerg:merge --skip-gate lint
/zerg:merge --skip-gate typecheck
```

**Making gates non-blocking permanently**: Set `required: false` in your configuration. Non-blocking gates run and report results but don't stop merges on failure. This is useful for advisory checks where you want visibility but not enforcement.

```yaml
quality_gates:
  - name: coverage
    command: pytest --cov --cov-fail-under=80
    required: false  # Warn but don't block
```

**When skipping makes sense**:
- Debugging a stuck merge where you know the gate failure is unrelated
- Prototyping where you'll run gates manually later
- Temporary workaround for a flaky test while investigating root cause

**When skipping is dangerous**:
- Production deployments (skip gates, skip confidence)
- Team environments where others build on your merged code
- Any time you don't fully understand why the gate is failing

Remember: gates exist because integrated code can break in ways that individual task verification doesn't catch. Skipping gates means accepting that risk.

For gate configuration and the `--skip-gate` flag, see [Command-Reference](Command-Reference).

---

## Containers

### How does container authentication work?

Container workers need to authenticate with Claude's API to execute tasks. ZERG supports two authentication methods, automatically detecting which to use based on available credentials.

| Method | Mechanism | Best For | How It Works |
|--------|-----------|----------|--------------|
| **OAuth** | Mount `~/.claude` | Claude Pro/Team accounts | Your existing Claude Code credentials are shared with containers |
| **API Key** | `ANTHROPIC_API_KEY` env var | API key authentication | The API key is passed into containers as an environment variable |

**OAuth authentication**: Your `~/.claude` directory contains OAuth tokens from Claude Code authentication. ZERG mounts this directory read-only into containers at the same path, allowing workers to authenticate using your existing session. This is transparent—if you're authenticated in Claude Code, container workers inherit that authentication.

**API key authentication**: If `ANTHROPIC_API_KEY` is set in your environment, ZERG passes it into containers. This method works independently of OAuth and is useful for CI environments or when you want explicit API key control.

**Detection priority**: ZERG checks for OAuth credentials first (existence of `~/.claude` with valid tokens), then falls back to API key if available. If neither is available, container startup fails with a clear authentication error.

**Security considerations**: OAuth tokens in `~/.claude` are mounted read-only, preventing containers from modifying your credentials. API keys passed via environment variables are visible within the container but not logged by ZERG. For maximum security, use OAuth when possible since it doesn't expose raw credentials.

For environment variable handling and security configuration, see [Configuration](Configuration).

### What resources do containers get?

Container resource allocation controls how much CPU, memory, and network access each worker receives. Default settings work for most projects, but you may need to adjust them for resource-intensive tasks or constrained environments.

**Default resource limits** (configurable in `.zerg/config.yaml`):

```yaml
resources:
  container_memory_limit: "4g"   # 4 GB RAM per container
  container_cpu_limit: 2.0       # 2 CPU cores per container
```

**Additional container settings**:
- **Read-only root filesystem**: Containers cannot write to system directories, only to mounted volumes
- **All capabilities dropped**: No elevated privileges (CAP_SYS_ADMIN, etc.)
- **Network isolation** (optional): Containers can be isolated from the network except for API calls
- **Port allocation**: 10 ports per worker in the range 49152-65535 for any local services tasks might spawn

**Why these defaults?** 4GB memory accommodates Claude Code's working memory plus language server processes that might run during development tasks. 2 CPU cores allow parallel processing within a worker without starving other workers. These limits prevent any single worker from monopolizing host resources.

**Adjusting for your needs**:
- **Memory-intensive tasks** (large codebases, ML models): Increase `container_memory_limit` to "8g" or higher
- **Resource-constrained hosts**: Reduce limits and use fewer workers
- **Fast I/O needs**: Consider SSD-backed Docker storage drivers

Resource limits are enforced by Docker. If a container exceeds its memory limit, Docker kills it with an OOM (out-of-memory) error. ZERG detects this and marks the worker as failed, potentially retrying on another worker.

For all resource and container configuration options, see [Configuration](Configuration).

### How do I troubleshoot container issues?

Container problems typically fall into a few categories: Docker daemon issues, authentication failures, resource exhaustion, or permission errors. Systematic diagnosis helps identify the root cause quickly.

**Common issues and solutions**:

| Issue | Diagnosis | Solution |
|-------|-----------|----------|
| Containers not starting | `docker info` fails or errors | Start Docker daemon, check Docker installation |
| Authentication errors | Container logs show auth failures | Set `ANTHROPIC_API_KEY` or ensure `~/.claude` exists and contains valid tokens |
| Out of memory (OOM) | Container killed, exit code 137 | Increase `container_memory_limit` in config |
| Permission denied | Mount errors in container logs | Check permissions on `~/.claude` (should be readable) and project directory |
| Network timeout | API calls fail inside container | Check network isolation settings, verify host network access |

**Diagnostic commands**:

```bash
# Check ZERG's view of the environment
/zerg:debug --env

# View logs for a specific worker
/zerg:logs --worker 0

# List all ZERG containers (running and stopped)
docker ps -a | grep zerg

# View container logs directly
docker logs zerg-worker-0

# Inspect container configuration
docker inspect zerg-worker-0

# Check resource usage
docker stats zerg-worker-0
```

**Debugging workflow**:
1. Run `/zerg:debug --env` to verify ZERG sees Docker and credentials correctly
2. Check if containers started: `docker ps -a | grep zerg`
3. If containers exist but failed, check logs: `docker logs zerg-worker-N`
4. Look for specific errors: authentication, OOM, permission denied
5. Fix the identified issue and retry with `/zerg:rush --resume`

**When containers keep failing**: Sometimes the issue is in the task itself, not the container. Compare container logs with the task's verification command. If the task verification is failing, the problem is the generated code, not containerization.

For comprehensive troubleshooting guides, see [Troubleshooting](Troubleshooting).

---

## Context & Tokens

### How does context engineering reduce token usage?

Context engineering is ZERG's system for minimizing per-worker token consumption while preserving the information each task needs. When running 5-10 parallel workers, each one independently loads instructions and specifications—without optimization, this can consume 15,000-30,000 tokens per worker before any code is written.

ZERG addresses this through three coordinated subsystems:

**1. Command Splitting**: Large command files (>300 lines) are split into `.core.md` (~30% essential instructions) and `.details.md` (~70% reference material). Workers load only the core content by default, referencing details only when encountering situations that require them. This saves ~2,000-5,000 tokens per command file loaded.

**2. Security Rule Filtering**: Instead of loading all security rules (Python, JavaScript, Docker, OWASP core), ZERG analyzes each task's file extensions and loads only relevant rules. A task that only modifies `.py` files receives Python security rules and OWASP core, not Docker or JavaScript rules. This saves ~1,000-4,000 tokens per task depending on how many rule sets your project has.

**3. Task-Scoped Context**: Each task receives curated excerpts from `requirements.md` and `design.md` based on its title, description, and file list—not the entire specification documents. The context assembler identifies paragraphs that mention the task's files or topics and extracts them within a token budget. This saves ~2,000-5,000 tokens per task compared to loading full documents.

**Combined impact**:
| Without Optimization | With Optimization |
|---------------------|-------------------|
| ~25,000 tokens/worker | ~10,000 tokens/worker |

At 10 workers, that's 150,000 tokens saved per execution cycle. The savings compound across multiple levels and features.

For configuration options and monitoring metrics, see [Context-Engineering](Context-Engineering).

### What's the token budget per task?

The token budget controls how much context each task receives from specification documents and upstream task outputs. The default budget of 4,000 tokens (~16,000 characters) covers most tasks well while leaving room for the worker's actual code generation work.

```yaml
plugins:
  context_engineering:
    task_context_budget_tokens: 4000
```

**What fits in 4,000 tokens**:
- 2-4 paragraphs of specification excerpts (~2,000 tokens)
- Filtered security rules for the task's file types (~1,200 tokens)
- Dependency context from upstream tasks (~800 tokens)

**Budget allocation and prioritization**: The context assembler doesn't just truncate at 4,000 tokens—it prioritizes content:
1. Security rules (always included if relevant to file types)
2. Direct spec matches (paragraphs explicitly mentioning task files)
3. Topic-related content (semantic similarity to task description)
4. Dependency exports (interfaces and types from upstream tasks)

Lower-priority content is truncated first if the budget is exceeded.

**When to adjust the budget**:
- **Increase to 5,000-6,000**: Complex tasks with many dependencies, tasks touching multiple subsystems, tasks where workers consistently ask for clarification
- **Decrease to 2,500-3,000**: Simple tasks, maximum efficiency mode, when running many workers and minimizing total token usage is critical

**Fallback behavior**: If context engineering fails for any reason (missing files, parsing errors), workers fall back to loading full context if `fallback_to_full: true`. A worker with full context is better than a worker that fails to load instructions.

For tuning recommendations and troubleshooting low context rates, see [Context-Engineering](Context-Engineering).

### How is command splitting different from task context?

Command splitting and task context are complementary subsystems that optimize different aspects of worker token consumption. Understanding the distinction helps you monitor and troubleshoot each independently.

| Aspect | Command Splitting | Task Context |
|--------|------------------|--------------|
| **What it optimizes** | Command instruction files | Specification document loading |
| **When it applies** | Worker loads a command (e.g., `worker.md`) | Worker loads task assignment |
| **What gets split** | 10 large command files into `.core.md` + `.details.md` | `requirements.md`, `design.md` into task-specific excerpts |
| **Savings magnitude** | ~2,000-5,000 tokens per command file | ~2,000-5,000 tokens per task |
| **Scope** | Same split applies to all workers loading that command | Different excerpt for each task based on its files/topic |

**Command splitting** addresses the fact that command files contain both essential workflow instructions and detailed reference material (examples, edge cases, configuration tables). Workers rarely need the full reference during normal execution, so splitting allows them to load just the essentials.

**Task context** addresses the fact that specification documents describe the entire feature, but each task only needs the parts relevant to its specific scope. A task implementing the JWT auth service doesn't need to know about the email notification requirements—it needs the authentication specification sections.

**Both work together**: A worker executing task AUTH-L2-001 loads:
1. `worker.core.md` (essential command instructions, not full `worker.md`)
2. Task AUTH-L2-001's scoped context (relevant spec excerpts, not full `requirements.md` + `design.md`)
3. Filtered security rules (Python rules only if task creates `.py` files)

Monitoring both: `/zerg:status` shows command split statistics and task context population rates in the CONTEXT BUDGET section.

For implementation details and configuration, see [Context-Engineering](Context-Engineering).

---

## Plugins

### What plugin types are supported?

ZERG's plugin system supports three distinct plugin types, each serving a different role in the execution lifecycle. Understanding when to use each type helps you extend ZERG effectively.

| Type | Purpose | Execution Model | Example Use Cases |
|------|---------|-----------------|-------------------|
| **Quality Gate** | Custom validation after merges | Blocking—stops merge if required gate fails | SonarQube scans, license compliance, security audits, coverage enforcement |
| **Lifecycle Hook** | React to events | Non-blocking—runs and continues regardless of result | Slack notifications, metrics collection, CI triggers, audit logging |
| **Launcher** | Custom worker execution environments | Infrastructure—controls how workers spawn | Kubernetes pods, SSH to remote clusters, cloud VM provisioning |

**Quality Gate plugins** integrate with the merge process. After level merges, configured gates run sequentially. If a required gate fails, the merge blocks until you fix the issue and resume. Use gates when you need to enforce invariants on merged code.

**Lifecycle Hook plugins** respond to events throughout execution (task started, level completed, worker spawned, etc.) without blocking the workflow. Use hooks for observability, notifications, and side effects that shouldn't stop execution.

**Launcher plugins** control how workers execute. The built-in launchers (subprocess, container, task) cover most needs, but you might create custom launchers to run workers in Kubernetes pods, on remote servers via SSH, or in cloud VMs. Launchers are the most complex plugin type, requiring understanding of worker lifecycle and coordination protocols.

Plugins can be configured via YAML (shell commands) or implemented as Python classes (entry points). YAML is simpler for straightforward needs; Python provides full flexibility.

For the complete plugin API and entry point registration, see [Plugins](Plugins).

### How do I create a custom plugin?

Custom plugins let you extend ZERG's behavior without modifying core code. The approach differs based on plugin complexity and type.

**YAML-configured hooks** (simplest—shell commands triggered by events):

```yaml
plugins:
  hooks:
    - event: level_complete
      command: ./scripts/notify.sh "Level {level} done for {feature}"
      timeout: 60
    - event: task_completed
      command: echo "Task {task_id} completed" >> /tmp/zerg.log
      timeout: 10
```

Available event types: `task_started`, `task_completed`, `level_complete`, `merge_complete`, `worker_spawned`, `quality_gate_run`, `rush_started`, `rush_finished`. Commands support variable substitution for `{level}`, `{feature}`, `{task_id}`, `{worker_id}`.

**Python Quality Gate plugins** (full control over validation logic):

```python
from zerg.plugins import QualityGatePlugin, GateContext
from zerg.types import GateRunResult
from zerg.constants import GateResult

class LicenseCheckGate(QualityGatePlugin):
    @property
    def name(self) -> str:
        return "license-check"

    def run(self, ctx: GateContext) -> GateRunResult:
        # ctx provides: feature, level, staging_branch, config
        # Implement your validation logic
        violations = self.scan_for_license_violations(ctx.staging_branch)

        if violations:
            return GateRunResult(
                gate_name=self.name,
                result=GateResult.FAIL,
                command="license-scanner",
                exit_code=1,
                stdout=f"Found {len(violations)} license violations",
                stderr="\n".join(violations)
            )

        return GateRunResult(
            gate_name=self.name,
            result=GateResult.PASS,
            command="license-scanner",
            exit_code=0,
            stdout="No license violations found"
        )
```

**Registering Python plugins**: Add entry points to your `pyproject.toml`:

```toml
[project.entry-points."zerg.plugins"]
license-check = "my_package.gates:LicenseCheckGate"
my-notifier = "my_package.hooks:SlackNotifierHook"
```

ZERG discovers plugins via `importlib.metadata` at startup. Your plugin class is instantiated and called at the appropriate lifecycle point.

For complete API documentation, available context fields, and example implementations, see [Plugins](Plugins).

### Where are plugins configured?

All plugin configuration lives in `.zerg/config.yaml` under the `plugins` section. This centralizes plugin settings alongside other ZERG configuration, making it easy to see and modify plugin behavior.

```yaml
plugins:
  enabled: true                    # Master switch for all plugins

  hooks:                           # YAML-configured lifecycle hooks
    - event: task_completed
      command: echo "Task done: {task_id}"
      timeout: 30
    - event: rush_finished
      command: ./scripts/notify-completion.sh {feature}
      timeout: 120

  quality_gates:                   # YAML-configured shell command gates
    - name: custom-security
      command: ./scripts/security-scan.sh
      required: true
      timeout: 300

  context_engineering:             # Built-in context optimization plugin
    enabled: true
    command_splitting: true
    security_rule_filtering: true
    task_context_budget_tokens: 4000
    fallback_to_full: true
```

**Python plugins** are discovered via entry points, not configured in YAML (they're registered in `pyproject.toml`). However, you can pass configuration to Python plugins through custom config sections:

```yaml
plugins:
  sonarqube:                       # Custom section for SonarQubeGate plugin
    server_url: https://sonar.example.com
    project_key: my-project
    quality_gate_id: default
```

Your plugin reads this configuration via the `GateContext.config` dictionary.

**Configuration precedence**:
1. YAML-configured quality gates run in declaration order
2. Python quality gate plugins run after YAML gates
3. Lifecycle hooks fire immediately when events occur (non-blocking)
4. `plugins.enabled: false` disables all plugins system-wide

For the full configuration schema and all available options, see [Configuration](Configuration).

---

## See Also

- [Home](Home) - Project overview and quick start
- [Tutorial](Tutorial) - Step-by-step guide to building your first feature
- [Command-Reference](Command-Reference) - All 26 commands with flags and examples
- [Configuration](Configuration) - Complete config file reference
- [Architecture](Architecture) - System design and module reference
- [Context-Engineering](Context-Engineering) - Token optimization deep dive
- [Troubleshooting](Troubleshooting) - Common issues and diagnostics
- [Plugins](Plugins) - Plugin development guide
- [Security](Security) - Security model and rule configuration
