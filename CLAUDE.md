# ZERG

Parallel Claude Code execution system. Overwhelm features with coordinated zergling instances.

## Quick Start

These are Claude Code slash commands. Use them inside a Claude Code session:

```claude
/zerg:init               # Set up project infrastructure
/zerg:plan user-auth     # Plan a feature
/zerg:design             # Design architecture (after approval)
/zerg:rush --workers=5   # Launch the swarm (after approval)
/zerg:status             # Monitor progress
```

## How It Works

1. **Plan**: You describe what to build. ZERG captures requirements.
2. **Design**: ZERG creates architecture and breaks work into atomic tasks with exclusive file ownership.
3. **Rush**: Multiple Claude Code instances execute tasks in parallel, organized by dependency levels.
4. **Merge**: Orchestrator merges branches after each level, runs quality gates.

## Key Concepts

**Levels**: Tasks grouped by dependencies. All zerglings finish Level 1 before any start Level 2.

**File Ownership**: Each task owns specific files. No conflicts possible.

**Spec as Memory**: Zerglings read spec files, not conversation history. Stateless and restartable.

**Verification**: Every task has an automated verification command. Pass or fail, no subjectivity.

## Claude Code Task Ecosystem (MANDATORY — READ THIS FIRST)

> **This section has been rearchitected before due to drift. Pay close attention.**

**The Claude Code Task system is the authoritative backbone for all ZERG task state.** Every ZERG command MUST use Claude Code Tasks (TaskCreate, TaskUpdate, TaskList, TaskGet) for tracking work. This is non-negotiable.

### Core Rules

1. **Tasks are the source of truth.** State JSON files (`.zerg/state/`) are supplementary. If Task system and state JSON disagree, the Task system wins.
2. **Every command tracks itself.** All `/zerg:*` commands must TaskCreate on start, TaskUpdate to `in_progress`, and TaskUpdate to `completed` on finish.
3. **Workers claim via Tasks.** Before executing a ZERG task, workers MUST call TaskUpdate with `status: "in_progress"`. After completion or failure, update accordingly.
4. **Dependencies use Task fields.** Use `blocks`/`blockedBy` via TaskUpdate — not just task-graph.json.
5. **Sessions share via CLAUDE_CODE_TASK_LIST_ID.** Workers inherit the orchestrator's `CLAUDE_CODE_TASK_LIST_ID` by default. If the orchestrator has no value set, workers use the same default task list. Teams can explicitly `export CLAUDE_CODE_TASK_LIST_ID=feature` before starting Claude Code for feature-scoped lists.
6. **Tasks persist in `~/.claude/tasks/`.** They survive session restarts. They are the coordination mechanism between parallel Claude Code instances.
7. **Resume checks existing Tasks.** `/zerg:rush --resume` calls TaskList first and only creates tasks that don't already exist.

### Task Subject Convention

All ZERG tasks use bracketed prefixes for discoverability:
- `[Plan] Capture requirements: {feature}`
- `[Design] Architecture for {feature}`
- `[L{level}] {task title}` — execution tasks from task-graph.json
- `[Init]`, `[Cleanup]`, `[Review]`, `[Build]`, `[Test]`, `[Security]`, etc. — utility commands

### Why This Matters

Without Task ecosystem integration, parallel workers can't coordinate, sessions lose state on restart, and `/zerg:status` has no authoritative data source. The Task system IS the project management layer for ZERG.

### Anti-Drift Rules

**This system has drifted before. These rules exist to prevent it from happening again.**

1. **Never remove Task tool calls from command files.** If a command file references TaskCreate, TaskUpdate, TaskList, or TaskGet, those references are load-bearing. Do not remove, comment out, or "simplify" them.

2. **Every command file MUST contain Task tool calls.** All 19 command files in `zerg/data/commands/` are required to have Task ecosystem integration. There are zero exceptions. The minimum pattern for any command is:
   ```
   On invocation:  TaskCreate (subject with bracketed prefix)
   Immediately:    TaskUpdate status "in_progress"
   On completion:  TaskUpdate status "completed"
   ```

3. **Backbone commands have additional requirements.** These 5 files have deeper integration beyond the minimum pattern. Do not reduce them to the minimum:
   - `worker.md` — TaskUpdate to claim tasks, TaskUpdate for failures/checkpoints, TaskList at completion
   - `status.md` — TaskList as primary data source, cross-reference with state JSON, flag mismatches
   - `merge.md` — TaskUpdate after quality gates per level, TaskList verification at finalize
   - `stop.md` — TaskUpdate with PAUSED/FORCE STOPPED annotations
   - `retry.md` — TaskGet to read state, TaskUpdate to reset to pending, TaskUpdate on reassignment

4. **State JSON is the fallback, not the primary.** If you find yourself writing code that reads `.zerg/state/` without also consulting TaskList, you are drifting. State JSON supplements Tasks, not the other way around.

5. **New commands get Task integration on creation.** If you create a new `/zerg:*` command file, it MUST include the minimum Task tracking pattern before it is considered complete.

### Drift Detection Checklist

Run this check when modifying any ZERG command file. If any check fails, fix it before committing.

```bash
# 1. All 19 command files must reference Task tools (exclude .core.md/.details.md)
grep -rL "TaskCreate\|TaskUpdate\|TaskList\|TaskGet" zerg/data/commands/*.md | grep -v '\.core\.md\|\.details\.md'
# Expected output: (empty — no files missing Task references)

# 2. Backbone files must have deeper integration
for f in worker status merge stop retry; do
  count=$(grep -c "TaskUpdate\|TaskList\|TaskGet" "zerg/data/commands/$f.md")
  echo "$f.md — $count Task references (expect ≥3)"
done

# 3. No command file should reference state JSON without also referencing TaskList
for f in zerg/data/commands/*.md; do
  has_state=$(grep -c "state.*json\|STATE_FILE\|\.zerg/state" "$f")
  has_tasks=$(grep -c "TaskList\|TaskGet" "$f")
  if [ "$has_state" -gt 0 ] && [ "$has_tasks" -eq 0 ]; then
    echo "DRIFT: $f reads state JSON but has no TaskList/TaskGet"
  fi
done

# 4. CLAUDE_CODE_TASK_LIST_ID in launcher allowlist
grep -q "CLAUDE_CODE_TASK_LIST_ID" zerg/launcher.py || echo "DRIFT: missing from ALLOWED_ENV_VARS"

# 5. All spawn methods conditionally inject CLAUDE_CODE_TASK_LIST_ID
count=$(grep -c "CLAUDE_CODE_TASK_LIST_ID" zerg/launcher.py)
echo "launcher.py — $count CLAUDE_CODE_TASK_LIST_ID refs (expect ≥4)"
```

### What Drift Looks Like

Watch for these patterns — they are symptoms of drift:

- **"Simplified" commands** — Someone removes Task calls to make a command file shorter or "cleaner." The Task calls are not boilerplate; they are coordination infrastructure.
- **State JSON as primary** — Code that reads/writes `.zerg/state/` and skips the Task system entirely. State JSON is a cache, not the source of truth.
- **Missing subject prefixes** — Tasks created without `[Bracketed]` prefixes break discoverability for `/zerg:status` and `/zerg:cleanup`.
- **Workers not claiming tasks** — If workers execute tasks without calling TaskUpdate(in_progress), other workers and the orchestrator have no visibility.
- **New commands without tracking** — A new `/zerg:*` command that lacks TaskCreate/TaskUpdate is incomplete, even if it "works."
- **TaskCreate without lifecycle** — Creating a task but never updating it to in_progress or completed is worse than not creating it (it pollutes the task list with stale entries).

**If you are modifying any ZERG command file and it lacks Task tool calls, add them.** Do not create or modify ZERG commands without Task ecosystem integration.

## Container Execution (Non-Negotiable)

When a user specifies `--mode container` or says "containerize", workers MUST run in Docker containers. Never substitute with manual edits or subprocess mode. Container mode is a first-class execution path, not a fallback.

### Authentication Methods

Container workers authenticate via two methods:

- **OAuth**: Mount `~/.claude` into container (Claude Pro/Team accounts)
- **API Key**: Pass `ANTHROPIC_API_KEY` env var into container

Both are implemented in `zerg/launcher.py:684-819`. This is settled infrastructure — do not reimplement or bypass.

## Configuration

Edit `.zerg/config.yaml` for:
- Zergling limits
- Timeouts
- Quality gate commands
- MCP servers
- Resource limits

## Context Engineering

ZERG includes a context engineering plugin that minimizes token usage across workers through three subsystems:

### Command Splitting

Large command files (>300 lines) are split into `.core.md` (essential instructions, ~30%) and `.details.md` (reference material, ~70%). The original file retains core content for backward compatibility.

Split files: init, design, rush, plugins, debug, plan, worker, merge, status.

### Task-Scoped Context

Each task in task-graph.json can include a `context` field with scoped content:
- Security rules filtered by file extension (.py → Python rules, .js → JavaScript rules)
- Spec excerpts relevant to the task's description and files
- Dependency context from upstream tasks

Workers use task-scoped context instead of loading full spec files, saving ~2000-5000 tokens per task.

### Configuration

```yaml
# .zerg/config.yaml
plugins:
  context_engineering:
    enabled: true
    command_splitting: true
    security_rule_filtering: true
    task_context_budget_tokens: 4000
    fallback_to_full: true
```

### Monitoring

Use `/zerg:status` to view the CONTEXT BUDGET section showing:
- Split command count and token savings
- Per-task context population rate
- Security rule filtering stats

## Troubleshooting

Zerglings not starting? Check Docker, ANTHROPIC_API_KEY, and port availability.

Tasks failing? Check verification commands in task-graph.json.

Need to restart? ZERG is crash-safe. Run `/zerg:rush` again to resume.

<!-- SECURITY_RULES_START -->
# Security Rules

Auto-generated from [TikiTribe/claude-secure-coding-rules](https://github.com/TikiTribe/claude-secure-coding-rules)

## Detected Stack

- **Languages**: javascript, python
- **Infrastructure**: docker

## Fetched Rules

- `_core/owasp-2025.md`
- `containers/docker/CLAUDE.md`
- `languages/javascript/CLAUDE.md`
- `languages/python/CLAUDE.md`

<!-- SECURITY_RULES_END -->
