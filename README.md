# ZERG

Parallel Claude Code execution for spec-driven development.

> "Zerg rush your codebase." — overwhelm features with parallel Claude instances.

## What It Does

ZERG combines three approaches:
1. **GSD methodology**: Spec-first development, fresh agents per task, max 3 tasks per context
2. **Claude Code's native Tasks**: Persistent task coordination across sessions
3. **Devcontainers**: Isolated parallel execution environments

You write specs. ZERG spawns multiple Claude Code instances. They build your feature in parallel.

## Requirements

- Python 3.11+
- Docker
- Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)
- Git
- `ANTHROPIC_API_KEY` environment variable

## Installation

### As a Python Package (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourname/zerg.git
cd zerg

# Install in development mode
pip install -e .

# Verify installation
python -m zerg --help
```

### In Your Project

```bash
cd your-project
git clone https://github.com/yourname/zerg.git /tmp/zerg
bash /tmp/zerg/install.sh
```

Or manually copy:
- `.claude/commands/` → your project
- `.zerg/` → your project
- `.devcontainer/` → your project

## Usage

```bash
claude

# Initialize project infrastructure
> /zerg:init

# Plan a feature
> /zerg:plan user-authentication

# After approval, design the implementation
> /zerg:design

# After approval, launch the swarm
> /zerg:rush --workers=5

# Monitor progress
> /zerg:status
```

## Commands

### Slash Commands (in Claude Code)

| Command | Description |
|---------|-------------|
| `/zerg:init` | Detect project, capture infrastructure, generate devcontainer |
| `/zerg:plan {feature}` | Elicit requirements, generate spec, get approval |
| `/zerg:design` | Generate architecture and task graph, get approval |
| `/zerg:rush` | Launch parallel workers (default 5, max 10) |
| `/zerg:status` | Show progress across all workers and tasks |
| `/zerg:worker` | Enter worker execution mode (used by containers) |
| `/zerg:logs` | View worker logs with filtering |
| `/zerg:stop` | Stop workers gracefully or forcefully |
| `/zerg:cleanup` | Remove ZERG artifacts (worktrees, branches, containers) |

### CLI Commands

```bash
# Initialize ZERG in a project
python -m zerg init

# Launch workers
python -m zerg rush --feature=myfeature --workers=5

# Check status
python -m zerg status --feature=myfeature

# View logs
python -m zerg logs --worker=0

# Stop workers
python -m zerg stop --feature=myfeature

# Retry failed tasks
python -m zerg retry TASK-001

# Cleanup after completion
python -m zerg cleanup --feature=myfeature
```

## How It Works

### Phase 1: Init
Analyzes your codebase. Asks about runtimes, databases, MCP servers. Generates devcontainer configuration.

### Phase 2: Plan
Captures requirements in `requirements.md`. Problem statement, user stories, acceptance criteria, scope boundaries. You approve before proceeding.

### Phase 3: Design
Generates architecture in `design.md`. Breaks implementation into a task graph with:
- Dependency levels (foundation → core → integration → testing → quality)
- Exclusive file ownership (no conflicts)
- Automated verification commands

You approve before proceeding.

### Phase 4: Rush
Creates git worktrees for each worker. Spawns N containers. Each worker:
- Picks tasks at current level
- Implements and verifies
- Commits to its branch
- Waits for level merge
- Continues to next level

### Phase 5: Orchestration
The orchestrator manages:
- Worker health monitoring
- Level synchronization
- Branch merging with quality gates
- Conflict resolution

## Directory Structure

```
.zerg/
  config.yaml           # ZERG configuration
  orchestrator.py       # Python orchestrator

.devcontainer/
  devcontainer.json     # Container definition
  Dockerfile            # Worker image
  docker-compose.yaml   # Multi-container setup

.claude/commands/
  zerg:init.md         # /zerg:init command
  zerg:plan.md         # /zerg:plan command
  zerg:design.md       # /zerg:design command
  zerg:rush.md         # /zerg:rush command
  zerg:worker.md       # /zerg:worker command
  zerg:status.md       # /zerg:status command

.gsd/specs/{feature}/
  requirements.md       # What to build
  design.md            # How to build it
  task-graph.json      # Atomic work units
```

## Configuration

Edit `.zerg/config.yaml`:

```yaml
workers:
  min: 1
  max: 10
  default: 5

timeouts:
  task_seconds: 1800
  level_seconds: 7200

quality_gates:
  - npm run lint
  - npm run typecheck
  - npm run test
  - npm run build
```

## Scaling Guidelines

| Workers | Use Case |
|---------|----------|
| 1-2 | Small features, learning the system |
| 3-5 | Medium features, balanced throughput |
| 6-10 | Large features, maximum parallelism |

Diminishing returns beyond the widest level's parallelizable tasks.

## Troubleshooting

**Workers not starting**
- Check Docker is running
- Verify `ANTHROPIC_API_KEY` is set
- Check port availability in 49152-65535 range

**Tasks failing verification**
- Review the verification command in task-graph.json
- Check worker logs in `.zerg/logs/`

**Merge conflicts**
- Should not happen with exclusive file ownership
- If they do, re-run affected tasks on merged base

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system design.

## License

MIT