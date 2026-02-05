# Tutorial: Building "Minerals Store" with ZERG

This tutorial walks through every ZERG phase using a complete example: building a Starcraft 2 themed ecommerce store with parallel Claude Code workers.

**What you'll learn:**
- Complete ZERG workflow from brainstorming to shipping
- All major commands with real examples
- Devcontainer setup for containerized execution
- Security rules and quality gates integration

---

## Prerequisites

Before starting, verify your environment:

| Requirement | Check Command | Purpose |
|-------------|---------------|---------|
| Python 3.12+ | `python --version` | ZERG runtime |
| Git 2.x+ | `git --version` | Worktrees, branching |
| Claude Code CLI | `claude --version` | Worker instances |
| Docker 20.x+ | `docker info` | Container mode (optional) |
| API Key | `echo $ANTHROPIC_API_KEY` | Claude API authentication |

Install ZERG:

```bash
git clone https://github.com/rocklambros/zerg.git
cd zerg && pip install -e ".[dev]"
zerg --help
```

---

## Step 1: Initialize Project

Create an empty project directory and initialize ZERG:

```bash
mkdir minerals-store && cd minerals-store
```

Inside Claude Code, run:

```
/zerg:init --security standard
```

**What happens:**
1. **Inception Mode** activates (empty directory detected)
2. Interactive wizard gathers project details
3. Technology stack recommendation generated
4. Project scaffold created
5. **Discovery Mode** runs automatically:
   - Creates `.zerg/config.yaml`
   - Generates `.devcontainer/` configuration
   - Fetches security rules for detected stack
   - Updates `CLAUDE.md` with security rule summary

**Expected output:**

```
ZERG Init - Inception Mode
Empty directory detected. Starting new project wizard...

Project name: minerals-store
Description: Starcraft 2 themed ecommerce API
Platforms: api, web
Architecture: monolith

+-- Recommended Stack ----------------------------------------+
| Backend: Python 3.12, FastAPI, SQLAlchemy async, PostgreSQL |
| Frontend: Vanilla JS, Vite, Tailwind CSS                    |
| Testing: pytest, Playwright                                 |
+------------------------------------------------------------+

Accept? [Y/n]: y

OK Created 8 scaffold files
OK Created .gsd/PROJECT.md
OK Initialized git repository
OK Created initial commit

Continuing to Discovery Mode...

OK Created .zerg/config.yaml
OK Created .devcontainer/
OK Fetched security rules: owasp-2025.md, python.md, javascript.md
OK Updated CLAUDE.md

ZERG initialized!
```

**Files created:**

```
minerals-store/
+-- minerals_store/          # Backend package
+-- frontend/                # Web UI (Vite project)
+-- tests/                   # Test directory
+-- .zerg/config.yaml        # ZERG configuration
+-- .gsd/PROJECT.md          # Project documentation
+-- .devcontainer/           # Container configs
+-- .claude/rules/security/  # Auto-fetched security rules
+-- CLAUDE.md                # Updated with security summary
+-- pyproject.toml           # Python project config
```

---

## Step 2: Brainstorm (Optional)

If requirements are unclear, use brainstorming to discover what to build:

```
/zerg:brainstorm --socratic
```

**What happens:**
- Socratic discovery mode asks probing questions
- Three rounds: Problem Space, Solution Space, Implementation Space
- Synthesizes answers into structured insights
- Outputs to `.gsd/specs/brainstorm-session.md`

**Example questions:**

```
ROUND 1: PROBLEM SPACE

Q1: What specific problem does this solve?
> Players need a marketplace for trading minerals and vespene gas

Q2: Who are the primary users?
> Three factions: Protoss, Terran, Zerg - each with resource preferences

Q3: How will we know when it's solved?
> Users can browse, add to cart, see faction discounts, checkout
```

Use `--domain api` or `--domain web` to focus brainstorming on specific areas.

---

## Step 3: Plan Feature

Capture requirements for the feature:

```
/zerg:plan minerals-store
```

**What happens:**
1. Interactive questioning captures requirements
2. Generates `.gsd/specs/minerals-store/requirements.md`
3. Status set to `DRAFT` pending approval

**Key prompts to answer:**

- **Ideal solution**: Full-stack app with FastAPI backend, themed web UI
- **Non-negotiables**: Faction discounts, bcrypt passwords, parameterized queries
- **Explicit non-goals**: Real payments, email notifications, admin dashboard
- **Verification approach**: Unit tests, integration tests, E2E with Playwright

**After planning, approve requirements:**

```bash
# Edit .gsd/specs/minerals-store/requirements.md
# Change "Status: DRAFT" to "Status: APPROVED"
```

Workers will not execute until requirements are approved.

---

## Step 4: Design Architecture

Generate technical architecture and task graph:

```
/zerg:design --feature minerals-store
```

**What happens:**
1. Reads approved requirements
2. Analyzes existing codebase
3. Generates architecture document
4. Creates task graph with dependency levels

**Generated files:**

| File | Purpose |
|------|---------|
| `design.md` | Architecture doc with components, data models, APIs |
| `task-graph.json` | Atomic tasks with file ownership and verification |

**Task graph structure:**

```json
{
  "feature": "minerals-store",
  "total_tasks": 19,
  "max_parallelization": 4,
  "levels": {
    "1": {
      "name": "foundation",
      "tasks": ["MINE-L1-001", "MINE-L1-002", "MINE-L1-003"]
    },
    "2": {
      "name": "services",
      "tasks": ["MINE-L2-001", "MINE-L2-002", "MINE-L2-003", "MINE-L2-004"]
    }
  }
}
```

**Understanding file ownership:**

Each task declares exclusive ownership:

```json
{
  "id": "MINE-L2-003",
  "title": "Cart service",
  "files": {
    "create": ["minerals_store/services/cart.py"],
    "modify": ["minerals_store/services/__init__.py"],
    "read": ["minerals_store/models.py"]
  },
  "verification": {
    "command": "pytest tests/unit/test_cart_service.py -v"
  }
}
```

- `create`: This task creates these files exclusively
- `modify`: This task modifies these files (no overlap within level)
- `read`: Read-only access (multiple tasks can read)

**Validate before rushing:**

```
/zerg:design --validate-only
```

Checks for orphan tasks, dependency cycles, file ownership conflicts.

---

## Step 5: Rush (Execute)

Launch parallel workers to execute the task graph:

### Preview first (recommended):

```
/zerg:rush --dry-run --workers 4
```

Shows execution plan without starting workers.

### Launch the swarm:

```
/zerg:rush --workers 4
```

**Execution modes:**

| Mode | Command | Use Case |
|------|---------|----------|
| subprocess | `--mode subprocess` | Development, no Docker |
| container | `--mode container` | Production, full isolation |
| task | `--mode task` | Claude Code slash commands |

Auto-detection picks the best mode if not specified.

**What happens:**

1. Creates git worktrees for each worker
2. Workers claim tasks via Claude Code Task system
3. Level 1 executes in parallel
4. Quality gates run after level completes
5. Branches merge to staging, then main
6. Workers rebase and proceed to Level 2
7. Repeat until all levels complete

**Example output:**

```
ZERG Rush

Feature: minerals-store
Workers: 4
Mode: subprocess

Creating worktrees...
  OK .zerg/worktrees/minerals-store-worker-0
  OK .zerg/worktrees/minerals-store-worker-1

=================== LEVEL 1: FOUNDATION ===================

Worker 0: MINE-L1-001 (Data models)           RUNNING
Worker 1: MINE-L1-002 (Configuration)         RUNNING
Worker 2: MINE-L1-003 (Types and enums)       RUNNING
Worker 3:                                     IDLE

[10:52:15] Worker 2 completed MINE-L1-003     OK
[10:55:18] Worker 0 completed MINE-L1-001     OK
[10:55:42] Worker 1 completed MINE-L1-002     OK

Level 1 complete! (3/3 tasks)

Running quality gates...
  OK ruff check . (0 issues)
  OK pytest (3 passed)

Merging Level 1...
  OK Merged all branches to staging
  OK Merged staging to main

=================== LEVEL 2: SERVICES =====================
```

---

## Step 6: Monitor Progress

### Real-time status:

```
/zerg:status --watch --interval 2
```

**Output:**

```
=================== ZERG Status: minerals-store ===================

Progress: ############------------ 60% (9/15 tasks)

Level 2 of 4 | Workers: 4 active | Elapsed: 23m 15s

+--------+---------------------------------+----------+---------+
| Worker | Current Task                    | Progress | Status  |
+--------+---------------------------------+----------+---------+
| W-0    | MINE-L2-001: Auth service       | ######## | VERIFY  |
| W-1    | MINE-L2-002: Product service    | ######## | DONE    |
| W-2    | MINE-L2-003: Cart service       | ######-- | RUNNING |
| W-3    | MINE-L2-004: Order service      | ######## | DONE    |
+--------+---------------------------------+----------+---------+
```

### View logs:

```
/zerg:logs --tail 50              # Recent logs
/zerg:logs --worker 2 --level debug  # Specific worker
/zerg:logs --follow               # Stream in real-time
/zerg:logs --aggregate            # All workers sorted by time
/zerg:logs --artifacts MINE-L2-003   # Task artifacts
```

### JSON output for scripting:

```
/zerg:status --json
```

---

## Step 7: Quality Gates

Quality gates run automatically after each level. Configure in `.zerg/config.yaml`:

```yaml
quality_gates:
  lint:
    command: "ruff check ."
    required: true    # Merge fails if this fails
  typecheck:
    command: "mypy ."
    required: false   # Warning only
  test:
    command: "pytest"
    required: true
```

### Manual quality commands:

**Code review:**

```
/zerg:review --mode full
```

Two-stage review: spec compliance + code quality.

**Run tests:**

```
/zerg:test --coverage
/zerg:test --unit
/zerg:test --e2e
```

**Static analysis:**

```
/zerg:analyze
/zerg:analyze --check lint
/zerg:analyze --check complexity
```

**Security scanning:**

```
/zerg:security --preset owasp
```

Scans for vulnerabilities using auto-fetched security rules.

---

## Step 8: Ship

After all levels complete and quality gates pass:

### Smart commit:

```
/zerg:git commit
```

Analyzes changes and generates meaningful commit message.

### Create PR:

```
/zerg:git --action pr
```

### Ship to main:

```
/zerg:git --action ship
```

Merges feature branch to main after final verification.

### Full workflow:

```
/zerg:git --action finish
```

Combines commit, PR creation, and merge.

---

## Devcontainer Setup

For full worker isolation, use container mode.

### Initialize with containers:

```
/zerg:init --with-containers
```

Creates:

```
.devcontainer/
+-- devcontainer.json    # Container config
+-- Dockerfile           # Multi-stage image
+-- post-create.sh       # Dependency installation
+-- mcp-servers/         # MCP server configs
    +-- config.json
```

### Build the image:

```bash
devcontainer build --workspace-folder .
```

### Rush in container mode:

```
/zerg:rush --mode container --workers 5
```

### Authentication methods:

| Method | Configuration | Best For |
|--------|---------------|----------|
| OAuth | Mount `~/.claude` into container | Claude Pro/Team |
| API Key | Pass `ANTHROPIC_API_KEY` env var | API authentication |

Both methods are supported automatically.

---

## Security Rules Integration

ZERG auto-fetches security rules based on detected stack.

### What gets installed:

```
.claude/rules/security/
+-- _core/owasp-2025.md           # OWASP Top 10 2025
+-- languages/python/CLAUDE.md    # Python-specific rules
+-- languages/javascript/CLAUDE.md # JavaScript rules
+-- containers/docker/CLAUDE.md   # Docker hardening
```

### Coverage:

| Category | Rules |
|----------|-------|
| OWASP Top 10 2025 | Broken Access Control, Injection, Crypto Failures, etc. |
| Python | Deserialization, subprocess safety, path traversal |
| JavaScript | Prototype pollution, XSS, command injection |
| Docker | Minimal images, non-root, multi-stage builds |

### Management commands:

```bash
zerg security-rules detect       # Show detected stack
zerg security-rules list         # Show active rules
zerg security-rules fetch        # Download rules
```

Rules are automatically filtered per task based on file extensions (context engineering).

---

## Handling Issues

### Task fails verification:

```
/zerg:debug --error "AssertionError: Expected 85.0"
/zerg:retry MINE-L2-003
/zerg:retry MINE-L2-003 --reset   # Fresh implementation
```

### Worker hits context limit:

```
/zerg:rush --resume
```

Workers checkpoint automatically; resume continues from checkpoint.

### Need to stop:

```
/zerg:stop                # Graceful (checkpoints)
/zerg:stop --force        # Immediate termination
```

### Multiple failures:

```
/zerg:debug --deep        # Cross-worker analysis
/zerg:retry --all         # Retry all failed tasks
```

---

## Cleanup

Remove ZERG artifacts after completion:

```
/zerg:cleanup --feature minerals-store
```

**Removes:**
- Git worktrees (`.zerg/worktrees/`)
- Worker branches (`zerg/minerals-store/*`)
- State files (`.zerg/state/`)

**Preserves:**
- Merged code on main
- Spec files (`.gsd/specs/`)
- ZERG configuration

Use `--dry-run` to preview what would be removed.

---

## Quick Reference

### Command Summary

| Phase | Command | Purpose |
|-------|---------|---------|
| Setup | `/zerg:init` | Initialize project |
| Discover | `/zerg:brainstorm --socratic` | Feature discovery |
| Plan | `/zerg:plan <feature>` | Capture requirements |
| Design | `/zerg:design` | Generate architecture |
| Execute | `/zerg:rush --workers N` | Launch parallel workers |
| Monitor | `/zerg:status --watch` | Track progress |
| Logs | `/zerg:logs --follow` | Stream worker output |
| Quality | `/zerg:review`, `/zerg:test`, `/zerg:security` | Verify quality |
| Ship | `/zerg:git --action ship` | Merge to main |
| Cleanup | `/zerg:cleanup` | Remove artifacts |

### Key Flags

| Flag | Purpose |
|------|---------|
| `--dry-run` | Preview without executing |
| `--resume` | Continue from checkpoint |
| `--watch` | Continuous updates |
| `--workers N` | Set worker count |
| `--mode container` | Use Docker isolation |
| `--socratic` | Enhanced discovery questioning |
| `--json` | Machine-readable output |

### Troubleshooting

| Problem | Solution |
|---------|----------|
| "No active feature" | Run `/zerg:plan <feature>` |
| "Task graph not found" | Run `/zerg:design` |
| Workers not starting | Check Docker, API key, ports |
| Task stuck | `/zerg:debug`, `/zerg:retry` |
| Context limit | `/zerg:rush --resume` |
| Merge conflict | Check file ownership in task-graph.json |

---

## Next Steps

- [Command Reference](Command-Reference.md) - Complete documentation for all commands
- [Configuration](Configuration.md) - Config files and tuning options
- Full tutorial with code examples: `docs/tutorial-minerals-store.md`
