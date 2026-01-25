# Project: ZERG

## Overview
Parallel Claude Code execution system that coordinates multiple worker instances to build features concurrently using spec-driven development.

## Tech Stack
- **Runtime**: Python 3.12 (orchestrator), Node.js 20 (workers, MCP servers)
- **Isolation**: Docker devcontainers, git worktrees
- **Coordination**: Claude Code native Tasks, level-based synchronization
- **Infrastructure**: Docker Compose, volume mounts

## Repository Structure
```
.
├── .claude/
│   ├── commands/           # Slash commands (init, plan, design, rush, status)
│   └── agents/             # Agent definitions
├── .devcontainer/
│   ├── devcontainer.json   # Container definition
│   ├── Dockerfile          # Worker image
│   ├── docker-compose.yaml # Multi-container setup
│   ├── post-create.sh      # Setup script
│   ├── post-start.sh       # Startup script
│   └── mcp-servers/        # MCP configuration
├── .gsd/
│   ├── specs/              # Feature specifications
│   ├── PROJECT.md          # This file
│   └── INFRASTRUCTURE.md   # Infrastructure requirements
├── .zerg/
│   ├── config.yaml         # ZERG configuration
│   ├── orchestrator.py     # Fleet manager (to be created)
│   └── logs/               # Worker logs
├── zerg/                   # Python orchestrator package (to be created)
├── ARCHITECTURE.md         # System design
├── CLAUDE.md               # Project instructions
└── README.md               # User documentation
```

## Commands
- `/init` - Initialize factory infrastructure
- `/plan {feature}` - Capture requirements
- `/design` - Create architecture and task breakdown
- `/rush [--workers=N]` - Launch parallel execution
- `/status` - Monitor progress

## Configuration
Edit `.zerg/config.yaml` to customize:
- Worker limits and timeouts
- Quality gate commands
- MCP server availability
- Resource limits
