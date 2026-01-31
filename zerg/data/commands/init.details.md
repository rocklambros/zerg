<!-- SPLIT: details, parent: init.md -->
# init — Detailed Reference

This file contains extended examples, templates, and edge cases.
Core instructions are in `init.core.md`.

## Phase 2: Interactive Requirements Gathering

Ask the user about their environment needs:

```markdown
## Infrastructure Requirements

I'll help you configure the factory. Please answer these questions:

### Runtime Environment
1. What are your primary language(s) and version(s)?
   - Example: Node.js 20, Python 3.12

2. What package manager(s) do you use?
   - Example: pnpm, pip, uv

### Services
3. What databases or caches does this project need?
   - Example: PostgreSQL 16, Redis 7, MongoDB

4. What external APIs does this project integrate with?
   - Example: Stripe, AWS S3, OpenAI

### Claude Code Setup
5. What MCP servers would be helpful?
   - filesystem (default: yes)
   - github (for PR operations)
   - postgres (for database queries)
   - fetch (for web requests)
   - Custom servers?

6. What Claude Code plugins should be installed?
   - ralph-loop (for execution loops)
   - typescript-lsp (for type checking)
   - Other plugins?

### Secrets
7. What environment variables does this project require?
   - List any API keys, database URLs, etc.
   - (We won't store values, just names for the template)
```

## Phase 3: Generate INFRASTRUCTURE.md

Based on discovery and user input, generate:

```markdown
# Infrastructure Requirements

## Project: {project_name}
## Generated: {timestamp}

---

## Runtime Environment

| Component | Version | Purpose |
|-----------|---------|---------|
| Node.js | 20.x | Primary runtime |
| Python | 3.12 | Scripting and tools |
| pnpm | 8.x | Package manager |

---

## Services

### Databases
| Service | Version | Purpose | Port |
|---------|---------|---------|------|
| PostgreSQL | 16 | Primary data store | 5432 |
| Redis | 7 | Caching, sessions | 6379 |

### External APIs
| Service | Purpose | Environment Variable |
|---------|---------|---------------------|
| Stripe | Payments | STRIPE_SECRET_KEY |
| SendGrid | Email | SENDGRID_API_KEY |

---

## Claude Code Configuration

### MCP Servers
| Server | Purpose | Credentials |
|--------|---------|-------------|
| filesystem | File operations | None |
| github | PR management | GITHUB_TOKEN |
| postgres | Database queries | DATABASE_URL |

### Plugins
| Plugin | Source | Purpose |
|--------|--------|---------|
| ralph-loop | anthropic/claude-code | Execution loops |

---

## Environment Variables

### Required
| Variable | Description | Example |
|----------|-------------|---------|
| DATABASE_URL | Postgres connection | postgres://user:pass@localhost:5432/db |
| GITHUB_TOKEN | GitHub API access | ghp_xxxxxxxxxxxx |

### Optional
| Variable | Description | Default |
|----------|-------------|---------|
| LOG_LEVEL | Logging verbosity | info |

---

## Resource Requirements

| Resource | Per Worker | Total (10 workers) |
|----------|------------|-------------------|
| CPU | 2 cores | 20 cores |
| Memory | 4 GB | 40 GB |
| Disk | 10 GB | 100 GB |

---

## Parallelization Notes

- Maximum recommended workers: {N}
- Bottleneck: {identified_bottleneck}
- Estimated speedup: {N}x over single worker
```

## Phase 4: Generate Devcontainer

Create `.devcontainer/devcontainer.json`:

```json
{
  "name": "${project_name}-factory",
  "build": {
    "dockerfile": "Dockerfile",
    "context": "..",
    "args": {
      "NODE_VERSION": "${node_version}",
      "PYTHON_VERSION": "${python_version}"
    }
  },
  "features": {
    "ghcr.io/devcontainers/features/git:1": {},
    "ghcr.io/devcontainers/features/github-cli:1": {},
    "ghcr.io/devcontainers/features/node:1": {
      "version": "${node_version}"
    },
    "ghcr.io/devcontainers/features/python:1": {
      "version": "${python_version}"
    },
    "ghcr.io/devcontainers/features/docker-in-docker:2": {}
  },
  "mounts": [
    "source=${localWorkspaceFolder},target=/workspace,type=bind,consistency=cached",
    "source=factory-claude-tasks,target=/root/.claude/tasks,type=volume",
    "source=factory-claude-config,target=/root/.claude,type=volume"
  ],
  "containerEnv": {
    "CLAUDE_CODE_TASK_LIST_ID": "${localEnv:ZERG_FEATURE}",
    "ZERG_WORKER_ID": "${localEnv:ZERG_WORKER_ID:-0}",
    "ZERG_BRANCH": "${localEnv:ZERG_BRANCH:-main}"
  },
  "postCreateCommand": "bash .devcontainer/post-create.sh",
  "postStartCommand": "bash .devcontainer/post-start.sh",
  "forwardPorts": [],
  "runArgs": [
    "--init",
    "--privileged"
  ],
  "remoteUser": "root"
}
```

Create `.devcontainer/Dockerfile`:

```dockerfile
FROM mcr.microsoft.com/devcontainers/base:ubuntu

ARG NODE_VERSION=20
ARG PYTHON_VERSION=3.12

# System dependencies
RUN apt-get update && apt-get install -y \
    curl wget git jq netcat-openbsd \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create directories
RUN mkdir -p /root/.claude/tasks /workspace

WORKDIR /workspace

# NOTE: Node.js and npm are installed by devcontainer features AFTER
# the Dockerfile build. All npm-dependent installs (Claude Code CLI,
# MCP servers) go in post-create.sh instead.
```

Create `.devcontainer/post-create.sh`:

```bash
#!/bin/bash
set -e

echo "═══════════════════════════════════════════════════"
echo "  ZERG Worker Post-Create Setup"
echo "═══════════════════════════════════════════════════"

# Configure npm global path
export NPM_CONFIG_PREFIX=/root/.npm-global
export PATH=$NPM_CONFIG_PREFIX/bin:$PATH

# Install Claude Code CLI and MCP servers
echo "Installing Claude Code CLI..."
npm install -g @anthropic-ai/claude-code
npm install -g \
    @anthropic-ai/mcp-server-filesystem \
    @anthropic-ai/mcp-server-github

# Install project dependencies
if [ -f "package.json" ]; then
  echo "Installing Node.js dependencies..."
  npm install 2>/dev/null || pnpm install 2>/dev/null || yarn install 2>/dev/null
fi

if [ -f "requirements.txt" ]; then
  echo "Installing Python dependencies..."
  pip install -r requirements.txt
fi

if [ -f "pyproject.toml" ]; then
  echo "Installing Python project..."
  pip install -e .
fi

# Copy MCP server configuration
if [ -f ".devcontainer/mcp-servers/config.json" ]; then
  cp .devcontainer/mcp-servers/config.json /root/.claude/mcp_servers.json
fi

# Setup git identity for commits
git config --global user.email "factory-worker@agentic.local"
git config --global user.name "ZERG Worker ${ZERG_WORKER_ID:-0}"

echo "Post-create setup complete"
```

Create `.devcontainer/post-start.sh`:

```bash
#!/bin/bash

WORKER_ID=${ZERG_WORKER_ID:-0}
FEATURE=${ZERG_FEATURE:-unknown}
BRANCH=${ZERG_BRANCH:-main}

echo "═══════════════════════════════════════════════════"
echo "  ZERG Worker Starting"
echo "  Worker ID: $WORKER_ID"
echo "  Feature: $FEATURE"
echo "  Branch: $BRANCH"
echo "  Task List: $CLAUDE_CODE_TASK_LIST_ID"
echo "═══════════════════════════════════════════════════"

# Checkout the assigned branch
if [ "$BRANCH" != "main" ]; then
  git fetch origin 2>/dev/null || true
  git checkout "$BRANCH" 2>/dev/null || git checkout -b "$BRANCH"
fi

# Wait for any services to be ready
if [ -f ".devcontainer/wait-for-services.sh" ]; then
  bash .devcontainer/wait-for-services.sh
fi

echo "Worker $WORKER_ID ready for tasks"
```

## Phase 5: Generate MCP Configuration

Create `.devcontainer/mcp-servers/config.json`:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-server-filesystem", "/workspace"]
    }
  }
}
```

Create `.devcontainer/mcp-servers/credentials.env.example`:

```bash
# Copy this to credentials.env and fill in values
# DO NOT commit credentials.env to git

# GitHub (for github MCP server)
GITHUB_TOKEN=

# Database (for postgres MCP server)
DATABASE_URL=

# Add project-specific credentials below
```

## Phase 6: Integrate Secure Coding Rules

Automatically fetch relevant security rules from [TikiTribe/claude-secure-coding-rules](https://github.com/TikiTribe/claude-secure-coding-rules) based on detected project stack.

### Step 1: Detect Project Stack

```bash
# Run stack detection
zerg security-rules detect --json-output
```

This detects:
- **Languages**: Python, JavaScript, TypeScript, Go, Rust, Java, C#, Ruby, etc.
- **Frameworks**: FastAPI, Django, React, Next.js, LangChain, etc.
- **Databases**: PostgreSQL, MongoDB, Pinecone, Chroma, Neo4j, etc.
- **Infrastructure**: Docker, Kubernetes, Terraform, GitHub Actions, etc.
- **AI/ML & RAG**: LangChain, LlamaIndex, vector databases, etc.

### Step 2: Fetch Relevant Rules Only

```bash
# List rules that will be fetched (based on detected stack)
zerg security-rules list

# Example output for Python + FastAPI project:
#   - rules/_core/owasp-2025.md
#   - rules/languages/python/CLAUDE.md
#   - rules/backend/fastapi/CLAUDE.md
```

### Step 3: Download Rules

```bash
# Fetch rules to .claude/rules/security/
zerg security-rules fetch
```

Rules are cached locally in `.claude/rules/security/` with directory structure:
```
.claude/rules/security/
├── _core/
│   └── owasp-2025.md
├── languages/
│   └── python/
│       └── CLAUDE.md
└── backend/
    └── fastapi/
        └── CLAUDE.md
```

Claude Code automatically loads all files under `.claude/rules/`, so no `@-imports` are needed.

### Step 4: Update CLAUDE.md

The integration updates `CLAUDE.md` with an informational section (no imports needed):

```markdown
<!-- SECURITY_RULES_START -->
# Security Rules

Auto-generated from TikiTribe/claude-secure-coding-rules

## Detected Stack
- **Languages**: python
- **Frameworks**: fastapi
- **AI/ML**: Yes

## Fetched Rules
- `_core/owasp-2025.md`
- `languages/python/CLAUDE.md`
- `backend/fastapi/CLAUDE.md`
<!-- SECURITY_RULES_END -->
```

### Skip Security Rules

To skip security rules integration:
```bash
zerg init --no-security-rules
```

### Update Rules Later

```bash
# Re-fetch rules (e.g., after adding new dependencies)
zerg security-rules integrate

# Force refresh (bypass cache)
zerg security-rules fetch --no-cache
```

## Phase 7: Generate PROJECT.md

Create `.gsd/PROJECT.md`:

```markdown
# Project: {project_name}

## Overview
{brief_description}

## Tech Stack
- **Runtime**: {languages}
- **Framework**: {frameworks}
- **Database**: {databases}
- **Infrastructure**: Docker, Devcontainers

## Repository Structure
{directory_tree}

## Development Commands
- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm test` - Run tests
- `npm run lint` - Run linter

## Factory Configuration
- **Max Workers**: {max_workers}
- **MCP Servers**: {mcp_servers}
- **Plugins**: {plugins}
```

## Output Summary

```
═══════════════════════════════════════════════════════════════
                 ZERG INITIALIZED
═══════════════════════════════════════════════════════════════

Project: {project_name}

Infrastructure:
  • Runtime: {runtime}
  • Services: {services}
  • MCP Servers: {mcp_servers}

Security Rules:
  • Detected Stack: {languages}, {frameworks}
  • Rules Fetched: {N} files
  • Location: .claude/rules/security/

Files Created:
  • .zerg/config.yaml              ✓
  • .devcontainer/devcontainer.json ✓
  • .devcontainer/Dockerfile        ✓
  • .devcontainer/post-create.sh    ✓
  • .devcontainer/post-start.sh     ✓
  • .devcontainer/mcp-servers/      ✓
  • .claude/rules/security/         ✓
  • .gsd/PROJECT.md                 ✓
  • .gsd/INFRASTRUCTURE.md          ✓
  • CLAUDE.md (updated)             ✓

───────────────────────────────────────────────────────────────

Build the devcontainer:
  devcontainer build --workspace-folder .

Test single worker:
  ZERG_WORKER_ID=0 devcontainer up --workspace-folder .

Next: Run /zerg:plan {feature-name} to start planning

═══════════════════════════════════════════════════════════════
```

<!-- Task Tracking section is in core file -->
