# Infrastructure Requirements

## Project: ZERG
## Generated: 2026-01-25

---

## Runtime Environment

| Component | Version | Purpose |
|-----------|---------|---------|
| Node.js | 20.x | Claude Code CLI, MCP servers, target projects |
| Python | 3.12 | Orchestrator, scripts, automation |
| npm | 10.x | Package management |

---

## Services

### Core (Always Available)
| Service | Purpose | Notes |
|---------|---------|-------|
| Docker | Container runtime | Required for devcontainers |
| Git | Version control | Worktrees for isolation |

### Optional (Profile-Based)
| Service | Version | Purpose | Docker Profile |
|---------|---------|---------|----------------|
| PostgreSQL | 16 | Task persistence (optional) | `with-postgres` |
| Redis | 7 | Coordination (optional) | `with-redis` |

---

## Claude Code Configuration

### MCP Servers
| Server | Purpose | Required Credentials |
|--------|---------|---------------------|
| filesystem | File operations in /workspace | None |
| github | PR/issue management | GITHUB_TOKEN |
| fetch | HTTP requests | None |

---

## Environment Variables

### Required
| Variable | Description | Example |
|----------|-------------|---------|
| ANTHROPIC_API_KEY | Claude API access | sk-ant-... |

### Optional
| Variable | Description | Default |
|----------|-------------|---------|
| GITHUB_TOKEN | GitHub API access | (none) |
| ZERG_FEATURE | Current feature name | unknown |
| ZERG_WORKER_ID | Worker instance ID | 0 |
| ZERG_BRANCH | Git branch to use | main |

---

## Resource Requirements

| Resource | Per Worker | Total (5 workers) |
|----------|------------|-------------------|
| CPU | 2 cores | 10 cores |
| Memory | 4 GB | 20 GB |
| Disk | 10 GB | 50 GB |

---

## Parallelization Notes

- **Max workers**: 5 (configurable in .zerg/config.yaml)
- **Bottleneck**: Task graph width at each level
- **Isolation**: Git worktrees per worker, no filesystem conflicts
- **Coordination**: Claude Code native Tasks + level synchronization
