# Troubleshooting

This page covers common issues, diagnostic commands, and recovery procedures for ZERG.

---

## Quick Decision Tree

```
Problem occurs
    |
    +-- Workers not starting?
    |       --> Check Docker, API keys, ports (Section 1.1)
    |
    +-- Tasks failing?
    |       --> Check verification commands, file ownership (Section 1.2)
    |
    +-- Merge conflicts?
    |       --> Check file ownership, worktree state (Section 1.3)
    |
    +-- State corruption?
    |       --> Use Task system as source of truth (Section 1.4)
    |
    +-- Container issues?
    |       --> Check auth, resources, image (Section 1.5)
    |
    +-- Unknown error?
            --> Run /zerg:debug --deep --env (Section 2)
```

---

## 1. Common Issues

### 1.1 Workers Not Starting

**Symptoms:**
- `/zerg:rush` hangs without spawning workers
- "Failed to spawn worker" errors
- Workers spawn but immediately exit

**Diagnostic Steps:**

```bash
# 1. Check Docker is running (container mode)
docker info

# 2. Verify API key is set
echo $ANTHROPIC_API_KEY | head -c 10

# 3. Check port availability (ZERG uses ports 49152+)
lsof -i :49152-49200

# 4. Check disk space
df -h .

# 5. Full environment diagnostics
/zerg:debug --env
```

**Common Causes & Solutions:**

| Cause | Solution |
|-------|----------|
| Docker daemon not running | `docker info` should succeed. Start Docker Desktop or `systemctl start docker` |
| `ANTHROPIC_API_KEY` not set | `export ANTHROPIC_API_KEY=sk-...` in your shell profile |
| Ports in use | Kill processes using ports 49152+ or change port range in config |
| Insufficient disk space | Need ~500MB per worker for worktrees. Clean with `git worktree prune` |
| Claude Code CLI not installed | Install from [docs.anthropic.com](https://docs.anthropic.com/en/docs/claude-code) |

**Container Mode Specific:**

```bash
# Check if devcontainer image exists
docker images | grep devcontainer

# Rebuild if needed
devcontainer build --workspace-folder .

# Check container resource limits in Docker settings
# Recommended: 4GB+ RAM, 2+ CPUs per worker
```

---

### 1.2 Tasks Failing

**Symptoms:**
- Tasks stuck in `failed` status
- Verification commands returning non-zero exit codes
- Workers completing but tasks not marked complete

**Diagnostic Steps:**

```bash
# 1. Check which tasks failed
jq '.tasks | to_entries[] | select(.value.status == "failed")' .zerg/state/$FEATURE.json

# 2. Get verification command for a specific task
jq '.tasks[] | select(.id == "TASK-001") | .verification' .gsd/specs/$FEATURE/task-graph.json

# 3. Run verification command manually
# (copy command from step 2 and run it)

# 4. Check task artifacts
ls .zerg/logs/tasks/TASK-001/

# 5. View worker logs for the task
grep "TASK-001" .zerg/logs/worker-*.log
```

**Common Causes & Solutions:**

| Cause | Solution |
|-------|----------|
| Verification command has wrong path | Check task-graph.json, ensure paths are relative to project root |
| Missing dependencies | Task depends on files from another level that haven't merged yet |
| Code error in generated files | Run `/zerg:debug --error "error message"` for analysis |
| File ownership conflict | Check that no two tasks in the same level own the same file |
| Test data not created | Ensure setup tasks run before dependent tasks |

**Retry After Fixing:**

```bash
# Retry specific task
/zerg:retry TASK-001

# Retry all failed tasks in a level
/zerg:retry --level 2

# Force retry (bypass retry limit)
/zerg:retry --force TASK-001
```

---

### 1.3 Merge Conflicts

**Symptoms:**
- `/zerg:merge` fails with git conflict errors
- Workers can't pull latest changes
- "File modified by multiple tasks" warnings

**Diagnostic Steps:**

```bash
# 1. Check git status in main worktree
git status

# 2. List all worktrees and their status
git worktree list

# 3. Check for conflicts in specific worktree
git -C .zerg/worktrees/worker-0 status

# 4. Check file ownership in task graph
jq '.tasks[] | {id: .id, level: .level, files: .files}' .gsd/specs/$FEATURE/task-graph.json
```

**Common Causes & Solutions:**

| Cause | Solution |
|-------|----------|
| Duplicate file ownership | Two tasks at same level own the same file. Fix in task-graph.json |
| Worktree branch diverged | `git -C .zerg/worktrees/worker-N reset --hard origin/main` |
| Orphaned worktree | `git worktree prune` to clean up |
| Uncommitted changes in worktree | `git -C .zerg/worktrees/worker-N stash` |

**Recovery Steps:**

```bash
# 1. Abort current merge if in progress
git merge --abort

# 2. Clean up worktrees
git worktree prune
rm -rf .zerg/worktrees/*

# 3. Reset state and resume
/zerg:rush --resume
```

**Prevention:**
- Review task-graph.json for file ownership overlaps before `/zerg:rush`
- Use `/zerg:design --validate` to check for ownership conflicts

---

### 1.4 State Corruption

**Symptoms:**
- "Invalid JSON" errors when reading state file
- Task system and state file disagree on task status
- Orphaned tasks that don't exist in task-graph
- `/zerg:status` shows inconsistent data

**Key Principle:** The Claude Code Task system is the **authoritative source of truth**. State JSON files (`.zerg/state/`) are supplementary.

**Diagnostic Steps:**

```bash
# 1. Validate state JSON syntax
python -m json.tool .zerg/state/$FEATURE.json

# 2. Compare Claude Tasks vs state file
# (run inside Claude Code session)
# TaskList shows authoritative state

# 3. Check for backup
ls -la .zerg/state/$FEATURE.json*

# 4. Compare tasks in state vs task-graph
jq '.tasks | keys' .zerg/state/$FEATURE.json > /tmp/state_tasks.txt
jq '.tasks[].id' .gsd/specs/$FEATURE/task-graph.json > /tmp/graph_tasks.txt
diff /tmp/state_tasks.txt /tmp/graph_tasks.txt
```

**Recovery Steps:**

```bash
# Option 1: Restore from backup
cp .zerg/state/$FEATURE.json.bak .zerg/state/$FEATURE.json

# Option 2: Rebuild from Claude Tasks
# The Task system has the real state. Run:
/zerg:status  # This reconciles state from Tasks

# Option 3: Reset and rebuild state from task-graph
rm .zerg/state/$FEATURE.json
/zerg:rush --resume  # Will recreate state from task-graph + Tasks
```

**Signs of State/Task Mismatch:**

```
/zerg:status output shows:
  State file: 5 completed, 2 failed
  Task system: 3 completed, 1 in_progress, 3 pending
```

When this happens, trust the Task system. Run `/zerg:debug` which will use `TaskList`/`TaskGet` as the authoritative source.

---

### 1.5 Container Issues

**Symptoms:**
- Container workers fail authentication
- Workers exit immediately with resource errors
- "Permission denied" errors inside container
- Container network connectivity issues

**Diagnostic Steps:**

```bash
# 1. Check container logs
docker logs <container-id>

# 2. Check container resource usage
docker stats

# 3. Test authentication manually
docker run -it --rm \
  -v ~/.claude:/root/.claude:ro \
  -e ANTHROPIC_API_KEY \
  your-devcontainer-image \
  claude --version

# 4. Check container network
docker run --rm your-devcontainer-image ping -c 1 api.anthropic.com
```

**Authentication Methods:**

| Method | Setup | Best For |
|--------|-------|----------|
| OAuth | Mount `~/.claude` into container | Claude Pro/Team accounts |
| API Key | Pass `ANTHROPIC_API_KEY` env var | API key authentication |

**OAuth Setup:**

```bash
# Ensure Claude is authenticated on host
claude auth status

# Container mode will mount ~/.claude automatically
/zerg:rush --mode container --workers=5
```

**API Key Setup:**

```bash
# Set in environment
export ANTHROPIC_API_KEY=sk-ant-...

# Or in .zerg/config.yaml
workers:
  container:
    env:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
```

**Resource Limit Issues:**

```yaml
# .zerg/config.yaml
workers:
  container:
    memory: "4g"      # Increase if OOM
    cpus: "2.0"       # Increase if slow
    shm_size: "2g"    # For large models
```

---

## 2. Diagnostic Commands

### 2.1 `/zerg:debug` — Deep Diagnostics

The primary diagnostic tool with Bayesian hypothesis testing, multi-language error parsing, and code-aware recovery plans.

**Basic Usage:**

```bash
# Auto-detect and diagnose current issues
/zerg:debug

# Diagnose specific error
/zerg:debug --error "ModuleNotFoundError: No module named 'requests'"

# Focus on specific worker
/zerg:debug --worker 2

# Full system diagnostics
/zerg:debug --deep --env

# Generate and execute recovery plan (with confirmation)
/zerg:debug --fix

# Save report to file
/zerg:debug --report diagnostics.md
```

**Flags Reference:**

| Flag | Description |
|------|-------------|
| `-f, --feature <name>` | Feature to investigate (auto-detected if omitted) |
| `-w, --worker <id>` | Focus on specific worker |
| `--deep` | Run system-level diagnostics (git, disk, docker, ports, worktrees) |
| `--fix` | Generate and execute recovery plan with confirmation prompts |
| `-e, --error <msg>` | Specific error message to analyze |
| `-s, --stacktrace <path>` | Path to stack trace file |
| `--env` | Comprehensive environment diagnostics |
| `-i, --interactive` | Interactive debugging wizard mode |
| `--report <path>` | Write diagnostic report to specified file |

**What `/zerg:debug` Analyzes:**

1. **Error Intelligence** — Multi-language parsing for Python, JavaScript, Go, Rust, Java, C++
2. **Log Correlation** — Timeline reconstruction across workers, temporal clustering
3. **Bayesian Hypothesis Testing** — 30+ known failure patterns with probability scoring
4. **Code-Aware Recovery** — Import chain analysis, git blame context, fix templates

**Output Categories:**

- `WORKER_FAILURE` — Crashed, timeout, unexpected exit
- `TASK_FAILURE` — Verification failed, code error
- `STATE_CORRUPTION` — JSON parse error, inconsistent state
- `INFRASTRUCTURE` — Docker, disk, port, worktree issues
- `CODE_ERROR` — Import, syntax, runtime errors
- `DEPENDENCY` — Missing package, version conflict
- `MERGE_CONFLICT` — Git merge failure, file ownership violation

---

### 2.2 `/zerg:status` — Progress Monitoring

Real-time view of execution progress, worker health, and task states.

```bash
# Basic status
/zerg:status

# Watch mode (auto-refresh)
/zerg:status --watch

# Show detailed task information
/zerg:status --verbose
```

**Key Sections:**

- **PROGRESS** — Overall completion percentage, level progress
- **WORKERS** — Health status, current task, heartbeat
- **TASKS** — Status breakdown (pending, in_progress, completed, failed)
- **CONTEXT BUDGET** — Token usage and savings from context engineering
- **TOKEN USAGE** — Per-worker token consumption

---

### 2.3 `/zerg:logs` — Worker Output

Access worker logs for detailed execution traces.

```bash
# Stream all worker logs
/zerg:logs

# Specific worker
/zerg:logs --worker 2

# Filter by task
/zerg:logs --task TASK-001

# Aggregate across workers
/zerg:logs --aggregate

# Show only errors
/zerg:logs --level error

# View task artifacts
/zerg:logs --artifacts TASK-001
```

**Log Locations:**

```
.zerg/logs/
  workers/
    worker-0.log
    worker-0.stderr.log
    worker-1.log
    ...
  tasks/
    TASK-001/
      stdout.log
      stderr.log
      artifacts/
    ...
  monitor.log         # Orchestrator events
```

---

### 2.4 Git Diagnostic Commands

```bash
# Check worktree status
git worktree list
git worktree list --porcelain  # Machine-readable

# Check specific worktree
git -C .zerg/worktrees/worker-0 status
git -C .zerg/worktrees/worker-0 log -3 --oneline

# Clean orphaned worktrees
git worktree prune

# Check branch divergence
git log main..worker-0-branch --oneline
```

---

### 2.5 Docker Diagnostic Commands

```bash
# Docker health
docker info
docker version

# Container status
docker ps -a --filter "name=zerg"
docker stats --no-stream

# Container logs
docker logs <container-id> --tail 100

# Resource usage
docker system df

# Clean up
docker system prune -f
docker volume prune -f
```

---

## 3. Recovery Procedures

### 3.1 Resume After Crash

ZERG is crash-safe. State is preserved in the Claude Code Task system and `.zerg/state/`.

```bash
# Resume from where you left off
/zerg:rush --resume
```

**What `--resume` Does:**
1. Reads existing task state from Claude Tasks (authoritative)
2. Cross-references with `.zerg/state/` (supplementary)
3. Re-spawns workers for pending/in_progress tasks
4. Skips already-completed tasks
5. Continues level-by-level execution

---

### 3.2 Retry Failed Tasks

```bash
# Retry all failed tasks
/zerg:retry

# Retry specific task
/zerg:retry TASK-001

# Retry all failed in a level
/zerg:retry --level 2

# Force retry (bypass limit)
/zerg:retry --force TASK-001

# Reset retry counters
/zerg:retry --reset

# Preview what would be retried
/zerg:retry --dry-run
```

**Retry Limits:**

Default: 3 retries per task. Configure in `.zerg/config.yaml`:

```yaml
workers:
  retry_attempts: 3
```

---

### 3.3 Cleanup Stale State

```bash
# Full cleanup of ZERG artifacts
/zerg:cleanup

# Cleanup specific feature
/zerg:cleanup --feature user-auth

# Cleanup only worktrees
/zerg:cleanup --worktrees

# Cleanup only logs
/zerg:cleanup --logs

# Preview cleanup
/zerg:cleanup --dry-run
```

**What Gets Cleaned:**
- `.zerg/state/<feature>.json`
- `.zerg/worktrees/`
- `.zerg/logs/`
- Worker branches in git
- Stale Claude Tasks (with `[L*]` prefix)

---

### 3.4 Manual Recovery Steps

When automated recovery fails, use these manual steps:

**Complete State Reset:**

```bash
# 1. Stop all workers
/zerg:stop --force

# 2. Clean up worktrees
git worktree prune
rm -rf .zerg/worktrees/*

# 3. Reset state file
rm .zerg/state/$FEATURE.json

# 4. Clean up branches
git branch | grep "^  zerg-" | xargs git branch -D

# 5. Reset to clean state
git checkout main
git reset --hard origin/main

# 6. Start fresh
/zerg:rush
```

**Recover Specific Worker:**

```bash
# 1. Identify stuck worker
/zerg:status --verbose

# 2. Kill worker process (if running)
pkill -f "claude.*worker-N"

# 3. Clean worker's worktree
rm -rf .zerg/worktrees/worker-N
git worktree prune

# 4. Mark worker's task as failed
# (done via TaskUpdate in Claude Code)

# 5. Resume
/zerg:rush --resume
```

**Fix Corrupted Task Graph:**

```bash
# 1. Validate JSON syntax
python -m json.tool .gsd/specs/$FEATURE/task-graph.json

# 2. Check for duplicate file ownership
jq -r '.tasks[] | .files.create[]?, .files.modify[]?' .gsd/specs/$FEATURE/task-graph.json | sort | uniq -d

# 3. If duplicates found, manually edit task-graph.json

# 4. Regenerate from design (if needed)
/zerg:design --regenerate
```

---

## 4. Configuration Reference

### Resilience Settings

```yaml
# .zerg/config.yaml
resilience:
  enabled: true                    # Master toggle

workers:
  # Spawn retry
  spawn_retry_attempts: 3
  spawn_backoff_strategy: exponential
  spawn_backoff_base_seconds: 2
  spawn_backoff_max_seconds: 30

  # Task timeout
  task_stale_timeout_seconds: 600  # 10 minutes

  # Heartbeat
  heartbeat_interval_seconds: 30
  heartbeat_stale_threshold: 120   # 2 minutes

  # Worker management
  auto_respawn: true
  max_respawn_attempts: 5
  retry_attempts: 3
```

### Logging Settings

```yaml
logging:
  level: INFO                      # DEBUG, INFO, WARNING, ERROR
  format: json                     # json or text
  max_file_size_mb: 10
  max_files: 5
  worker_stderr: true              # Capture worker stderr separately
```

---

## 5. Getting Help

If the above doesn't resolve your issue:

1. **Run full diagnostics:** `/zerg:debug --deep --env --report debug-report.md`
2. **Check the [FAQ](FAQ)** for additional answers
3. **Search existing issues:** [GitHub Issues](https://github.com/rocklambros/zerg/issues)
4. **Open a new issue** with:
   - ZERG version (`zerg --version`)
   - Full command that failed
   - Diagnostic report from step 1
   - Relevant log snippets

---

## See Also

- [Command-Reference](Command-Reference) — Full command documentation
- [Configuration](Configuration) — Config file reference
- [Architecture](Architecture) — System design and internals
- [FAQ](FAQ) — Frequently asked questions
