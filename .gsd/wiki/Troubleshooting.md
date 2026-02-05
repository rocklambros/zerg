# Troubleshooting

This guide helps you diagnose and resolve ZERG issues. Each section explains not just *what* to do, but *why* problems occur and how to prevent them in the future.

---

## Quick Diagnostic Guide

When something goes wrong, start here to identify your problem category:

```
What's happening?
    |
    +-- Workers won't start or exit immediately?
    |       --> Section 1.1: Usually Docker, API keys, or ports
    |
    +-- Tasks keep failing?
    |       --> Section 1.2: Verification commands or dependencies
    |
    +-- Git merge errors?
    |       --> Section 1.3: File ownership conflicts between tasks
    |
    +-- Status shows weird data?
    |       --> Section 1.4: State file out of sync with Task system
    |
    +-- Container authentication issues?
    |       --> Section 1.5: OAuth mount or API key configuration
    |
    +-- No idea what's wrong?
            --> Run /zerg:debug --deep --env for full analysis
```

---

## 1. Common Issues

### 1.1 Workers Not Starting

**Symptoms:**
- `/zerg:rush` hangs without spawning workers
- "Failed to spawn worker" errors in output
- Workers spawn but immediately exit with no logs

**Why This Happens:**

Workers are Claude Code instances that need several things to function:

1. **Container environment** (in container mode) — Docker must be running and accessible
2. **API access** — Either OAuth credentials or an `ANTHROPIC_API_KEY`
3. **Available ports** — ZERG uses ports 49152+ for worker communication
4. **Disk space** — Each worker creates a git worktree (~500MB overhead)

When any of these prerequisites is missing or misconfigured, workers either fail to start or exit immediately because they can't establish the environment they need to execute tasks.

**How to Fix:**

Start by identifying which prerequisite is failing:

```bash
# 1. Check Docker is running (container mode only)
docker info
# If this fails: Start Docker Desktop or run `systemctl start docker`

# 2. Verify your API key is set
echo $ANTHROPIC_API_KEY | head -c 10
# Should show something like "sk-ant-api"

# 3. Check that ZERG's port range is available
lsof -i :49152-49200
# If ports are busy: Kill the processes or reconfigure port range

# 4. Check available disk space
df -h .
# Need at least 500MB per worker for worktrees

# 5. Run comprehensive environment diagnostics
/zerg:debug --env
# This checks everything automatically
```

**Common causes and their solutions:**

| What's Wrong | How You Know | Solution |
|--------------|--------------|----------|
| Docker not running | `docker info` fails | Start Docker Desktop or daemon |
| API key missing | `echo $ANTHROPIC_API_KEY` is empty | Add `export ANTHROPIC_API_KEY=sk-...` to shell profile |
| Ports blocked | `lsof` shows processes on 49152+ | Kill those processes or change port range in config |
| Low disk space | `df -h` shows <500MB free | Clean up or expand storage |
| Claude CLI missing | `claude --version` fails | Install from [docs.anthropic.com](https://docs.anthropic.com/en/docs/claude-code) |

**For Container Mode Specifically:**

The devcontainer image must exist and have enough resources allocated:

```bash
# Check if your devcontainer image exists
docker images | grep devcontainer
# If missing, rebuild it:
devcontainer build --workspace-folder .

# Verify Docker has enough resources allocated
# In Docker Desktop: Settings > Resources
# Recommended: 4GB+ RAM, 2+ CPUs per worker
```

**Prevention:**

Add environment checks to your shell profile so prerequisites are always verified:

```bash
# Add to ~/.bashrc or ~/.zshrc
if ! docker info &>/dev/null; then
  echo "Warning: Docker not running"
fi
if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "Warning: ANTHROPIC_API_KEY not set"
fi
```

Run `/zerg:debug --env` before starting a multi-hour rush to catch issues early.

---

### 1.2 Tasks Failing

**Symptoms:**
- Tasks stuck in `failed` status
- Verification commands returning non-zero exit codes
- Workers complete execution but tasks aren't marked complete

**Why This Happens:**

Each task in ZERG has a verification command that must pass for the task to be considered complete. Task failures usually stem from one of these root causes:

1. **Verification command issues** — The command itself has wrong paths, missing dependencies, or incorrect assumptions about the environment
2. **Dependency ordering** — The task depends on files created by tasks in a previous level that haven't merged yet
3. **Code errors** — The worker generated code that doesn't compile, has syntax errors, or fails tests
4. **File ownership conflicts** — Two tasks in the same level both try to modify the same file

Understanding *which* cause applies to your failure is essential for choosing the right fix.

**How to Fix:**

First, identify which task failed and why:

```bash
# 1. List all failed tasks with their details
jq '.tasks | to_entries[] | select(.value.status == "failed")' \
  .zerg/state/$FEATURE.json

# 2. Get the verification command for a specific failed task
jq '.tasks[] | select(.id == "TASK-001") | .verification' \
  .gsd/specs/$FEATURE/task-graph.json

# 3. Run that verification command manually to see the actual error
# (Copy the command from step 2 and run it yourself)

# 4. Check what artifacts the task produced
ls .zerg/logs/tasks/TASK-001/

# 5. Search worker logs for context about the failure
grep "TASK-001" .zerg/logs/worker-*.log
```

**Match the error to the cause:**

| Error Pattern | Likely Cause | Solution |
|---------------|--------------|----------|
| "File not found" in verification | Wrong path in task-graph.json | Fix the path — it should be relative to project root |
| Import/module errors | Missing dependency | Task depends on code from an earlier level; check dependencies |
| Test failures | Code bug | Run `/zerg:debug --error "error message"` for analysis |
| "File already exists" | Ownership conflict | Two tasks at same level own the file; fix in task-graph.json |
| Timeout | Task took too long | Increase timeout or split into smaller tasks |

**Once you've fixed the underlying issue:**

```bash
# Retry a specific task
/zerg:retry TASK-001

# Retry all failed tasks in a level
/zerg:retry --level 2

# Force retry if you've hit the retry limit
/zerg:retry --force TASK-001
```

**Prevention:**

Before running `/zerg:rush`:

1. **Validate the task graph:** Run `/zerg:design --validate` to check for dependency issues and file ownership conflicts
2. **Review verification commands:** Ensure they're testing the right thing and use correct paths
3. **Check dependency ordering:** Tasks that depend on other tasks' output should be in later levels

---

### 1.3 Merge Conflicts

**Symptoms:**
- `/zerg:merge` fails with git conflict errors
- Workers report they can't pull the latest changes
- Warnings about "file modified by multiple tasks"

**Why This Happens:**

ZERG's parallel execution model depends on **exclusive file ownership**. Each task owns specific files, and tasks at the same level execute simultaneously. Merge conflicts occur when this isolation breaks down:

1. **Duplicate file ownership** — Two tasks at the same level both claim ownership of the same file. When they both modify it, git can't automatically merge their changes.

2. **Worktree branch divergence** — A worker's git worktree got out of sync with the main branch, perhaps from a previous interrupted run.

3. **Uncommitted changes** — Manual changes were made in a worktree directory that weren't committed, blocking the merge.

The ZERG design phase is supposed to prevent (1), but mistakes happen, especially with complex features.

**How to Fix:**

First, diagnose which type of conflict you have:

```bash
# 1. Check status in the main worktree
git status
# Look for "both modified" files — these are actual conflicts

# 2. List all worktrees and their status
git worktree list
# Orphaned entries indicate cleanup is needed

# 3. Check status in a specific worker's worktree
git -C .zerg/worktrees/worker-0 status
# Uncommitted changes here can block merges

# 4. Identify file ownership overlaps in task graph
jq '.tasks[] | {id: .id, level: .level, files: .files}' \
  .gsd/specs/$FEATURE/task-graph.json
# Look for the same file appearing in multiple same-level tasks
```

**Solutions by cause:**

| Cause | Solution |
|-------|----------|
| Duplicate ownership | Edit task-graph.json to give each file a single owner at each level |
| Diverged worktree | `git -C .zerg/worktrees/worker-N reset --hard origin/main` |
| Orphaned worktree | `git worktree prune` cleans up stale references |
| Uncommitted changes | `git -C .zerg/worktrees/worker-N stash` or discard them |

**If things are really broken, do a full recovery:**

```bash
# 1. Abort any in-progress merge
git merge --abort

# 2. Clean up all worktrees
git worktree prune
rm -rf .zerg/worktrees/*

# 3. Resume — ZERG will recreate worktrees as needed
/zerg:rush --resume
```

**Prevention:**

The key is catching ownership conflicts before execution begins:

```bash
# Always validate before rushing
/zerg:design --validate

# This command specifically checks for:
# - Files owned by multiple tasks at the same level
# - Circular dependencies
# - Tasks with missing file specifications
```

If you're manually editing task-graph.json, use this command to find duplicate ownership:

```bash
jq -r '.tasks[] | .files.create[]?, .files.modify[]?' \
  .gsd/specs/$FEATURE/task-graph.json | sort | uniq -d
```

Any output means you have duplicates that will cause merge conflicts.

---

### 1.4 State Corruption

**Symptoms:**
- "Invalid JSON" errors when ZERG reads state files
- `/zerg:status` shows different data than you expect
- Tasks appear "stuck" in states that don't match reality
- Orphaned tasks that don't exist in the task-graph

**Why This Happens:**

ZERG maintains state in two places:

1. **Claude Code Task system** (authoritative) — The real source of truth, stored in `~/.claude/tasks/`
2. **State JSON files** (supplementary) — Local cache in `.zerg/state/`, used for fast lookups

Corruption happens when these get out of sync, typically from:

- **Interrupted operations** — A crash or force-quit while state was being written
- **Manual editing** — Editing state files directly and making syntax errors
- **Race conditions** — Multiple workers trying to update state simultaneously (rare, but possible)

The good news: because the Task system is authoritative, true data loss is rare. The state JSON is just a cache that can be rebuilt.

**How to Fix:**

First, determine what's actually wrong:

```bash
# 1. Check if the state JSON is valid syntax
python -m json.tool .zerg/state/$FEATURE.json
# Syntax errors will be reported here

# 2. Look for backups
ls -la .zerg/state/$FEATURE.json*
# .bak files are created before risky operations

# 3. Compare state file tasks vs task-graph tasks
jq '.tasks | keys' .zerg/state/$FEATURE.json > /tmp/state_tasks.txt
jq '.tasks[].id' .gsd/specs/$FEATURE/task-graph.json > /tmp/graph_tasks.txt
diff /tmp/state_tasks.txt /tmp/graph_tasks.txt
# Differences indicate orphaned or missing tasks
```

**Recovery options (in order of preference):**

```bash
# Option 1: Restore from backup (if available)
cp .zerg/state/$FEATURE.json.bak .zerg/state/$FEATURE.json

# Option 2: Let ZERG rebuild from the authoritative Task system
# The Task system has the real state — this reconciles them:
/zerg:status  # Reads from Tasks and updates state file

# Option 3: Full state reset (starts fresh but preserves completed work)
rm .zerg/state/$FEATURE.json
/zerg:rush --resume
# This rebuilds state from task-graph + Task system
```

**Recognizing state/Task mismatches:**

When `/zerg:status` shows something like:

```
State file: 5 completed, 2 failed
Task system: 3 completed, 1 in_progress, 3 pending
```

**Trust the Task system**. The state file is stale. Run `/zerg:debug` to reconcile them — it uses `TaskList`/`TaskGet` as the authoritative source.

**Prevention:**

1. **Never manually edit state JSON files** — Use ZERG commands instead
2. **Don't force-quit during operations** — Use `/zerg:stop` for clean shutdown
3. **Run `/zerg:status`** regularly during long runs — it detects and reports mismatches

---

### 1.5 Container Issues

**Symptoms:**
- Container workers fail with authentication errors
- Workers exit immediately citing resource problems
- "Permission denied" errors inside the container
- Network connectivity failures (can't reach API)

**Why This Happens:**

Container mode runs Claude Code inside Docker containers for isolation. This introduces additional layers where things can go wrong:

1. **Authentication** — Containers need access to your Claude credentials, either via mounted OAuth tokens or API key environment variables
2. **Resources** — Containers have memory/CPU limits that may be too low for Claude Code
3. **Permissions** — Files mounted into containers may have ownership/permission mismatches
4. **Networking** — Container network configuration may block outbound API calls

**How to Fix:**

Diagnose by checking each layer:

```bash
# 1. Check container logs for the actual error
docker logs <container-id>
# Look for authentication failures, OOM kills, or network errors

# 2. Monitor resource usage in real-time
docker stats
# If memory/CPU maxed out, containers need more resources

# 3. Test authentication manually
docker run -it --rm \
  -v ~/.claude:/root/.claude:ro \
  -e ANTHROPIC_API_KEY \
  your-devcontainer-image \
  claude --version
# Should print version — any error indicates auth issues

# 4. Test network connectivity
docker run --rm your-devcontainer-image \
  ping -c 1 api.anthropic.com
# Failure means container networking is broken
```

**Authentication setup:**

ZERG supports two authentication methods:

| Method | How It Works | Best For |
|--------|--------------|----------|
| OAuth | Mounts `~/.claude` directory into container | Claude Pro/Team accounts |
| API Key | Passes `ANTHROPIC_API_KEY` as environment variable | Direct API access |

**OAuth setup:**

```bash
# First, ensure you're authenticated on the host
claude auth status
# If not authenticated, run: claude auth login

# Container mode automatically mounts ~/.claude
/zerg:rush --mode container --workers=5
```

**API key setup:**

```bash
# Set in your environment
export ANTHROPIC_API_KEY=sk-ant-...

# Or specify in config for all container runs
# .zerg/config.yaml:
workers:
  container:
    env:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
```

**Resource limit adjustments:**

If workers are getting killed for using too much memory:

```yaml
# .zerg/config.yaml
workers:
  container:
    memory: "4g"      # Increase if seeing OOM errors
    cpus: "2.0"       # Increase if workers are slow
    shm_size: "2g"    # Shared memory for large model operations
```

**Prevention:**

Before starting container-mode execution:

1. Run `claude auth status` to verify authentication works
2. Check Docker has enough resources allocated (Docker Desktop > Settings > Resources)
3. Test one container manually before launching the full swarm

---

## 2. Diagnostic Commands

### 2.1 `/zerg:debug` — Deep Diagnostics

This is your primary troubleshooting tool. It uses Bayesian hypothesis testing to identify the most likely cause of issues, with multi-language error parsing and code-aware recovery suggestions.

**Why it exists:** Instead of manually checking logs, state files, and system conditions, `/zerg:debug` analyzes everything automatically and tells you what's probably wrong and how to fix it.

**Basic usage:**

```bash
# Auto-detect and diagnose current issues
/zerg:debug

# Diagnose a specific error message
/zerg:debug --error "ModuleNotFoundError: No module named 'requests'"

# Focus analysis on a specific worker
/zerg:debug --worker 2

# Run comprehensive system-level checks
/zerg:debug --deep --env

# Generate recovery plan and execute it (with confirmation prompts)
/zerg:debug --fix

# Save a detailed report for sharing or later reference
/zerg:debug --report diagnostics.md
```

**Available flags:**

| Flag | What It Does |
|------|--------------|
| `-f, --feature <name>` | Investigate a specific feature (auto-detected if omitted) |
| `-w, --worker <id>` | Focus on one worker's logs and state |
| `--deep` | Include system-level checks: git, disk, docker, ports, worktrees |
| `--fix` | Generate and execute a recovery plan (asks for confirmation first) |
| `-e, --error <msg>` | Parse and analyze a specific error message |
| `-s, --stacktrace <path>` | Analyze a stack trace from a file |
| `--env` | Comprehensive environment diagnostics |
| `-i, --interactive` | Step-by-step debugging wizard |
| `--report <path>` | Write findings to a markdown file |

**What it analyzes:**

1. **Error Intelligence** — Parses errors from Python, JavaScript, Go, Rust, Java, and C++
2. **Log Correlation** — Reconstructs timeline across workers, clusters related events
3. **Bayesian Hypothesis Testing** — Scores 30+ known failure patterns by probability
4. **Code-Aware Recovery** — Analyzes import chains, git blame context, suggests specific fixes

**Output categories:**

- `WORKER_FAILURE` — Crashed, timed out, or exited unexpectedly
- `TASK_FAILURE` — Verification failed or code errors
- `STATE_CORRUPTION` — JSON parse errors or inconsistent state
- `INFRASTRUCTURE` — Docker, disk, port, or worktree issues
- `CODE_ERROR` — Import, syntax, or runtime errors
- `DEPENDENCY` — Missing packages or version conflicts
- `MERGE_CONFLICT` — Git merge failures or file ownership violations

---

### 2.2 `/zerg:status` — Progress Monitoring

**Why it exists:** During a rush, you need visibility into what's happening across workers without digging through logs. Status provides a real-time dashboard.

**Usage:**

```bash
# One-time status check
/zerg:status

# Watch mode — refreshes automatically
/zerg:status --watch

# Include detailed task-by-task information
/zerg:status --verbose
```

**What the sections mean:**

- **PROGRESS** — Overall completion percentage and current level
- **WORKERS** — Which workers are alive, what they're working on, last heartbeat time
- **TASKS** — Counts by status (pending, in_progress, completed, failed)
- **CONTEXT BUDGET** — Token usage stats and savings from context engineering
- **TOKEN USAGE** — Per-worker token consumption (helps identify expensive tasks)

---

### 2.3 `/zerg:logs` — Worker Output

**Why it exists:** When you need to see exactly what a worker did, logs provide the detailed execution trace.

**Usage:**

```bash
# Stream all worker logs (combined)
/zerg:logs

# View one specific worker's output
/zerg:logs --worker 2

# Filter to logs mentioning a specific task
/zerg:logs --task TASK-001

# Aggregate and summarize across all workers
/zerg:logs --aggregate

# Show only error-level messages
/zerg:logs --level error

# View artifacts a task produced
/zerg:logs --artifacts TASK-001
```

**Log directory structure:**

```
.zerg/logs/
  workers/
    worker-0.log          # Main output from worker 0
    worker-0.stderr.log   # Errors and warnings
    worker-1.log
    ...
  tasks/
    TASK-001/
      stdout.log          # Task-specific stdout
      stderr.log          # Task-specific stderr
      artifacts/          # Files the task produced
    ...
  monitor.log             # Orchestrator-level events
```

---

### 2.4 Git Diagnostic Commands

When merge or worktree issues occur, these git commands help identify the problem:

```bash
# List all worktrees and their branches
git worktree list
git worktree list --porcelain  # Machine-parseable format

# Check status in a specific worktree
git -C .zerg/worktrees/worker-0 status
git -C .zerg/worktrees/worker-0 log -3 --oneline

# Clean up orphaned worktrees (references to deleted directories)
git worktree prune

# See how far a branch has diverged from main
git log main..worker-0-branch --oneline
```

---

### 2.5 Docker Diagnostic Commands

For container-mode issues, these Docker commands reveal what's happening:

```bash
# Verify Docker is working
docker info
docker version

# List ZERG-related containers
docker ps -a --filter "name=zerg"

# Check resource usage across containers
docker stats --no-stream

# View recent logs from a container
docker logs <container-id> --tail 100

# Check disk usage by Docker
docker system df

# Clean up to free resources
docker system prune -f
docker volume prune -f
```

---

## 3. Recovery Procedures

### 3.1 Resume After Crash

**Why this works:** ZERG is designed to be crash-safe. State is preserved in the Claude Code Task system (authoritative) and `.zerg/state/` (cache). You can always pick up where you left off.

```bash
# Resume from the last known state
/zerg:rush --resume
```

**What `--resume` does internally:**

1. Queries Claude Tasks via `TaskList` to get authoritative task states
2. Cross-references with `.zerg/state/` for any additional context
3. Identifies tasks that are pending or were in-progress when the crash happened
4. Spawns workers for those tasks only
5. Skips tasks already marked completed
6. Continues level-by-level execution from where it stopped

No data is lost in a crash — you just resume.

---

### 3.2 Retry Failed Tasks

**Why you'd need this:** Sometimes tasks fail due to transient issues (network blips, race conditions) or fixable problems (wrong verification command). After addressing the root cause, retry re-executes the failed tasks.

```bash
# Retry all failed tasks
/zerg:retry

# Retry one specific task
/zerg:retry TASK-001

# Retry all failed tasks in a specific level
/zerg:retry --level 2

# Force retry even if retry limit is exceeded
/zerg:retry --force TASK-001

# Reset all retry counters to zero
/zerg:retry --reset

# Preview what would be retried without doing it
/zerg:retry --dry-run
```

**Retry limits:**

By default, each task can be retried 3 times. After that, you need `--force`. Configure in `.zerg/config.yaml`:

```yaml
workers:
  retry_attempts: 3  # Increase if tasks are flaky
```

---

### 3.3 Cleanup Stale State

**Why you'd need this:** After completing a feature or abandoning one, cleanup removes ZERG artifacts so they don't interfere with future work.

```bash
# Full cleanup of all ZERG artifacts
/zerg:cleanup

# Cleanup just one feature's artifacts
/zerg:cleanup --feature user-auth

# Cleanup only worktrees (keep logs and state)
/zerg:cleanup --worktrees

# Cleanup only logs (keep worktrees and state)
/zerg:cleanup --logs

# Preview what would be deleted
/zerg:cleanup --dry-run
```

**What gets removed:**

- `.zerg/state/<feature>.json` — State cache
- `.zerg/worktrees/` — Git worktree directories
- `.zerg/logs/` — Worker and task logs
- Worker branches in git (branches starting with `zerg-`)
- Claude Tasks with ZERG prefixes (`[L*]`, `[Plan]`, etc.)

---

### 3.4 Manual Recovery Steps

When automated recovery doesn't work, these manual steps get you back to a clean state.

**Complete state reset (nuclear option):**

```bash
# 1. Stop all workers gracefully (or forcefully)
/zerg:stop --force

# 2. Clean up all worktrees
git worktree prune
rm -rf .zerg/worktrees/*

# 3. Remove the state file
rm .zerg/state/$FEATURE.json

# 4. Delete all ZERG branches
git branch | grep "^  zerg-" | xargs git branch -D

# 5. Reset to clean main
git checkout main
git reset --hard origin/main

# 6. Start fresh
/zerg:rush
```

**Recover a specific stuck worker:**

```bash
# 1. Find which worker is stuck
/zerg:status --verbose

# 2. Kill its process if still running
pkill -f "claude.*worker-N"

# 3. Remove its worktree
rm -rf .zerg/worktrees/worker-N
git worktree prune

# 4. Mark its task as failed
# (Use TaskUpdate in your Claude Code session)

# 5. Resume — ZERG will reassign the task
/zerg:rush --resume
```

**Fix a corrupted task graph:**

```bash
# 1. Validate JSON syntax
python -m json.tool .gsd/specs/$FEATURE/task-graph.json
# Fix any syntax errors reported

# 2. Find duplicate file ownership
jq -r '.tasks[] | .files.create[]?, .files.modify[]?' \
  .gsd/specs/$FEATURE/task-graph.json | sort | uniq -d
# Edit task-graph.json to remove duplicates

# 3. If task-graph is beyond repair, regenerate from design
/zerg:design --regenerate
```

---

## 4. Configuration Reference

These settings control ZERG's resilience and recovery behavior.

### Resilience Settings

```yaml
# .zerg/config.yaml
resilience:
  enabled: true  # Master toggle for resilience features

workers:
  # How many times to retry spawning a worker
  spawn_retry_attempts: 3
  spawn_backoff_strategy: exponential  # or "linear"
  spawn_backoff_base_seconds: 2
  spawn_backoff_max_seconds: 30

  # How long before a task is considered stale
  task_stale_timeout_seconds: 600  # 10 minutes

  # Heartbeat monitoring
  heartbeat_interval_seconds: 30    # How often workers check in
  heartbeat_stale_threshold: 120    # Seconds before worker is considered dead

  # Automatic recovery
  auto_respawn: true                # Restart dead workers automatically
  max_respawn_attempts: 5           # Per worker, per run
  retry_attempts: 3                 # Per task
```

### Logging Settings

```yaml
logging:
  level: INFO                # DEBUG, INFO, WARNING, ERROR
  format: json               # "json" for structured, "text" for human-readable
  max_file_size_mb: 10       # Rotate logs after this size
  max_files: 5               # Keep this many rotated log files
  worker_stderr: true        # Capture stderr separately from stdout
```

---

## 5. Getting Help

If you've tried the above and are still stuck:

1. **Run full diagnostics:** `/zerg:debug --deep --env --report debug-report.md`
2. **Check the [FAQ](FAQ)** for answers to common questions
3. **Search existing issues:** [GitHub Issues](https://github.com/rocklambros/zerg/issues)
4. **Open a new issue** including:
   - ZERG version (`zerg --version`)
   - The full command that failed
   - The diagnostic report from step 1
   - Relevant log snippets from `.zerg/logs/`

Good bug reports include the error message, what you expected to happen, and what actually happened.

---

## See Also

- [Command-Reference](Command-Reference) — Full documentation of all ZERG commands
- [Configuration](Configuration) — Complete config file reference
- [Architecture](Architecture) — How ZERG works internally
- [FAQ](FAQ) — Frequently asked questions and quick answers
