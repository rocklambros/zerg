# /zerg:init

Initialize ZERG for a project. Detects the project state and operates in one of two modes.

## Synopsis

```
/zerg:init [OPTIONS]
```

## Description

`/zerg:init` prepares a project for ZERG by creating the `.zerg/` directory structure, detecting languages and frameworks, and generating configuration files.

The command operates in two modes depending on whether the current directory contains existing code:

### Inception Mode (Empty Directory)

When run in an empty directory, ZERG launches an interactive wizard that:

1. Gathers project requirements through prompts (name, description, target platform, architecture style).
2. Recommends and confirms a technology stack (language, framework, test framework).
3. Scaffolds the project structure with starter files.
4. Initializes a git repository and creates an initial commit.

Supported languages for scaffolding:

| Language | Package Manager | Default Framework |
|----------|-----------------|-------------------|
| Python | uv | FastAPI / Typer |
| TypeScript | pnpm | Fastify / Commander |
| Go | go mod | Gin / Cobra |
| Rust | cargo | Axum / Clap |

### Discovery Mode (Existing Project)

When run in a directory with existing code, ZERG analyzes the project:

1. Detects languages by checking for `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, and similar markers.
2. Identifies frameworks (React, FastAPI, Express, Django, and others).
3. Detects existing infrastructure (Docker, CI/CD, devcontainers).
4. Generates `.zerg/`, `.devcontainer/`, and `.claude/` configuration directories.

For multi-language projects, ZERG generates a devcontainer configuration with appropriate runtime features for each detected language.

## Options

| Option | Description |
|--------|-------------|
| `--workers N` | Set default worker count for this project |
| `--security strict` | Enable strict security rule enforcement |
| `--no-security-rules` | Skip security rule generation |
| `--with-containers` | Build the devcontainer image after initialization |

## Examples

```bash
# Initialize a new project from scratch (Inception Mode)
mkdir my-api && cd my-api
/zerg:init

# Initialize an existing project (Discovery Mode)
cd my-existing-project
/zerg:init

# Initialize with custom settings
/zerg:init --workers 3 --security strict

# Skip security rules
/zerg:init --no-security-rules

# Build devcontainer image after init
/zerg:init --with-containers
```

## Generated Structure

After running `/zerg:init` on an existing project, the following directories are created:

```
project/
  .zerg/           # ZERG runtime state and configuration
  .devcontainer/   # Container configuration for workers
    mcp-servers/
  .claude/
    commands/      # Slash command files
    agents/
  .gsd/
    specs/         # Feature specifications
    PROJECT.md     # Project metadata
```

For Inception Mode with Python selected:

```
my-api/
  my_api/
    __init__.py
    main.py
  tests/
    __init__.py
    test_main.py
  .gsd/
    PROJECT.md
  pyproject.toml
  README.md
  .gitignore
  .git/
```

## See Also

- [[zerg-plan]] -- Next step after initialization: capture feature requirements
- [[zerg-Reference]] -- Full command index
