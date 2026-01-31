# ZERG Initialize

Initialize ZERG for a project. Operates in two modes based on directory state.

## Two Modes

### Inception Mode (Empty Directory)
When run in an empty directory, ZERG starts the **Inception Mode** wizard:
1. **Requirements Gathering** - Interactive prompts to capture project goals
2. **Technology Selection** - Recommends and confirms language/framework
3. **Project Scaffolding** - Generates complete project structure
4. **Git Initialization** - Creates initial commit

### Discovery Mode (Existing Project)
When run in a directory with existing code, ZERG runs **Discovery Mode**:
1. **Language Detection** - Identifies languages and frameworks
2. **Infrastructure Analysis** - Understands existing setup
3. **Configuration Generation** - Creates .zerg/ and .devcontainer/

## Quick Start

```bash
# Empty directory - starts Inception Mode wizard
mkdir my-new-project && cd my-new-project
zerg init

# Existing project - runs Discovery Mode
cd my-existing-project
zerg init

# Specify settings
zerg init --workers 3 --security strict

# Skip security rules
zerg init --no-security-rules

# Build devcontainer image after init
zerg init --with-containers
```

## Inception Mode Details

When starting a new project from scratch:

```bash
$ mkdir my-api && cd my-api
$ zerg init

ZERG Init - Inception Mode
Empty directory detected. Starting new project wizard...

┌─ New Project ─────────────────────────────┐
│ Let's gather some information about your  │
│ new project.                              │
└───────────────────────────────────────────┘

Project name: my-api
Brief description: A REST API for user management
Target platforms: api
Architecture style: monolith
...

┌─ Tech Stack ──────────────────────────────┐
│ Based on your requirements, here's our    │
│ recommendation.                           │
└───────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│ Component       │ Recommendation         │
├─────────────────┼────────────────────────┤
│ Language        │ python (3.12)          │
│ Framework       │ fastapi                │
│ Test Framework  │ pytest                 │
└──────────────────────────────────────────┘

Primary language: python
Framework: fastapi

✓ Created 6 scaffold files
✓ Created .gsd/PROJECT.md
✓ Initialized git repository
✓ Created initial commit

✓ Inception complete!
```

### Supported Languages

| Language | Package Manager | Default Framework |
|----------|-----------------|-------------------|
| Python | uv | FastAPI / Typer |
| TypeScript | pnpm | Fastify / Commander |
| Go | go mod | Gin / Cobra |
| Rust | cargo | Axum / Clap |

### Generated Structure (Python Example)

```
my-api/
├── my_api/
│   ├── __init__.py
│   └── main.py
├── tests/
│   ├── __init__.py
│   └── test_main.py
├── .gsd/
│   └── PROJECT.md
├── pyproject.toml
├── README.md
├── .gitignore
└── .git/
```

## Multi-Language Detection

ZERG automatically detects **all languages** in your project and generates a multi-language devcontainer:

```bash
# Example output for a Python + TypeScript project
$ zerg init
Detected languages: javascript, python, typescript
Detected frameworks: fastapi, react
```

### Devcontainer Features

Multi-language projects use devcontainer "features" to add runtimes:

| Language | Feature | Default Version |
|----------|---------|-----------------|
| Python | `ghcr.io/devcontainers/features/python:1` | 3.12 |
| JavaScript/TypeScript | `ghcr.io/devcontainers/features/node:1` | 20 |
| Go | `ghcr.io/devcontainers/features/go:1` | 1.22 |
| Rust | `ghcr.io/devcontainers/features/rust:1` | latest |
| Java | `ghcr.io/devcontainers/features/java:1` | 21 |
| Ruby | `ghcr.io/devcontainers/features/ruby:1` | latest |
| C#/.NET | `ghcr.io/devcontainers/features/dotnet:1` | 8.0 |

### Custom Language Support

Languages without official features use `postCreateCommand`:
- **R**: `apt-get install r-base`
- **Julia**: Official installer
- **C++**: `build-essential cmake`

### Single vs Multi-Language

- **Single language**: Uses optimized pre-built image (faster startup)
- **Multiple languages**: Uses base Ubuntu + features (flexible)

## Pre-Flight Checks

```bash
# Verify we're in a git repository
git rev-parse --git-dir > /dev/null 2>&1 || {
  echo "ERROR: Not in a git repository"
  exit 1
}

# Create factory directories if they don't exist
mkdir -p .zerg .devcontainer/mcp-servers .claude/commands .claude/agents .gsd/specs
```

## Phase 1: Project Discovery

Analyze the existing project to understand:

1. **Language Detection**
   - Check for `package.json` (Node.js)
   - Check for `requirements.txt`, `pyproject.toml`, `setup.py` (Python)
   - Check for `go.mod` (Go)
   - Check for `Cargo.toml` (Rust)
   - Check for `pom.xml`, `build.gradle` (Java)

2. **Framework Detection**
   - React, Next.js, Vue, Angular (frontend)
   - Express, Fastify, Flask, Django, FastAPI (backend)
   - Testing frameworks (Jest, Pytest, etc.)

3. **Existing Infrastructure**
   - Docker/docker-compose files
   - CI/CD configurations
   - Existing devcontainer

## Task Tracking

On invocation, create a Claude Code Task to track this command:

Call TaskCreate:
  - subject: "[Init] Initialize {project_name}"
  - description: "ZERG initialization for {project_name}. Mode: {inception|discovery}."
  - activeForm: "Initializing ZERG"

Immediately call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "in_progress"

On completion (after output summary), call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "completed"
