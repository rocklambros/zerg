# Installation

This page covers everything needed to install ZERG and verify that it works. The process takes approximately 5 to 10 minutes.

---

## Table of Contents

- [Requirements](#requirements)
- [Install ZERG](#install-zerg)
- [Claude Code Setup](#claude-code-setup)
- [Docker Setup (Container Mode)](#docker-setup-container-mode)
- [Verify Installation](#verify-installation)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting-installation)

---

## Requirements

| Requirement | Minimum Version | Check Command |
|-------------|----------------|---------------|
| Python | 3.10+ | `python3 --version` |
| Git | 2.20+ | `git --version` |
| Claude Code | Latest | `claude --version` |
| Docker (optional) | 20.10+ | `docker --version` |
| jq | 1.6+ | `jq --version` |

**Operating systems:** macOS, Linux. Windows is supported through WSL2.

---

## Install ZERG

### From Source (Recommended for Development)

```bash
git clone https://github.com/your-org/zerg.git
cd zerg
pip install -e .
```

### Verify the CLI

```bash
zerg --help
```

You should see output listing available commands including `init`, `plan`, `rush`, and `status`.

---

## Claude Code Setup

ZERG runs as a set of slash commands inside Claude Code. After installing the ZERG package, the commands become available automatically when you open Claude Code in a project that has been initialized with `/zerg:init`.

### Authentication

ZERG workers need to authenticate with Anthropic's API. There are two methods:

**Method 1: OAuth (Claude Pro/Team)**

If you use Claude Code with a Pro or Team account, you are already authenticated via OAuth. No additional setup is needed. Workers inherit your session credentials.

**Method 2: API Key**

If you use an API key, set the environment variable before launching Claude Code:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
claude
```

Workers launched by `/zerg:rush` inherit this environment variable automatically.

### Slash Commands

ZERG registers its commands in the `.claude/commands/` directory. After running `/zerg:init`, you can use any `/zerg:*` command inside a Claude Code session:

```
/zerg:brainstorm <topic>   Discover features (optional)
/zerg:plan <feature>       Plan a feature
/zerg:design               Design architecture
/zerg:rush                 Launch workers
/zerg:status               Check progress
```

---

## Docker Setup (Container Mode)

Container mode is optional but recommended for production use. It provides isolated environments for each worker and prevents workers from interfering with each other or with your host system.

### Install Docker

**macOS:**

```bash
brew install --cask docker
```

**Linux (Ubuntu/Debian):**

```bash
sudo apt-get update
sudo apt-get install docker.io docker-compose-plugin
sudo usermod -aG docker $USER
# Log out and back in for group changes to take effect
```

### Build the Devcontainer Image

After running `/zerg:init`, ZERG generates a `.devcontainer/` directory with a Dockerfile and docker-compose configuration. Build the image:

```bash
docker compose -f .devcontainer/docker-compose.yaml build
```

### Container Authentication

**OAuth method** -- Mount your Claude credentials into the container:

```bash
# This happens automatically when using --mode container
# ZERG mounts ~/.claude into the container
```

**API key method** -- Pass the key as an environment variable:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
/zerg:rush --workers=5 --mode container
```

### Verify Container Setup

```bash
# Check Docker is running
docker info > /dev/null 2>&1 && echo "Docker OK" || echo "Docker not running"

# Check the devcontainer image exists
docker images | grep devcontainer
```

---

## Verify Installation

Run these checks to confirm everything is working.

### Step 1: Check Prerequisites

```bash
python3 --version          # 3.10+
git --version              # 2.20+
claude --version           # Latest
jq --version               # 1.6+
docker --version           # 20.10+ (optional)
```

### Step 2: Initialize a Test Project

```bash
mkdir /tmp/zerg-test && cd /tmp/zerg-test
git init
claude
```

Inside Claude Code:

```
/zerg:init
```

You should see ZERG create the `.zerg/` directory structure and generate configuration files.

### Step 3: Verify Directory Structure

After initialization, your project should contain:

```
.zerg/
  config.yaml              # Worker limits, quality gates, resources
  state/                   # Runtime state files
  logs/                    # Worker log output
.devcontainer/             # Docker configuration (if containers enabled)
  docker-compose.yaml
  Dockerfile
.claude/
  commands/                # Slash command files
.gsd/
  PROJECT.md               # Project metadata
  INFRASTRUCTURE.md        # Infrastructure details
  specs/                   # Feature specs (created per feature)
```

### Step 4: Clean Up

```bash
rm -rf /tmp/zerg-test
```

---

## Configuration

ZERG stores its configuration in `.zerg/config.yaml`. The file is generated during `/zerg:init` with sensible defaults. You can edit it at any time.

### Key Settings

```yaml
workers:
  max_concurrent: 5          # Maximum parallel workers
  timeout_minutes: 60        # Per-task timeout
  retry_attempts: 2          # Retries before marking a task as failed
  launcher_type: subprocess  # "subprocess" or "container"

quality_gates:
  - name: lint
    command: ruff check .
    required: true
    timeout: 300
  - name: typecheck
    command: mypy . --strict --ignore-missing-imports
    required: true
    timeout: 300
  - name: test
    command: pytest tests/unit/ -x --timeout=30
    required: true
    timeout: 600

resources:
  cpu_cores: 2
  memory_gb: 4
  container_memory_limit: "4g"
  container_cpu_limit: 2.0
```

See the Configuration reference page for the full list of options.

---

## Troubleshooting Installation

### "Command not found: zerg"

The ZERG package is not on your PATH. If you installed from source with `pip install -e .`, make sure your Python bin directory is in PATH:

```bash
python3 -m site --user-base
# Add the bin subdirectory to your PATH
```

### "No active feature" when running commands

You need to run `/zerg:plan <feature>` before other commands. ZERG tracks the current feature in `.gsd/.current-feature`.

### Docker permission denied

On Linux, your user needs to be in the `docker` group:

```bash
sudo usermod -aG docker $USER
# Log out and back in
```

### Claude Code does not recognize `/zerg:*` commands

Run `/zerg:init` first. This creates the command files in `.claude/commands/`. If the commands still do not appear, check that the files exist:

```bash
ls .claude/commands/zerg:*.md
```

---

## Next Steps

- [[Quick Start]] -- Run through the full ZERG workflow.
- [[Your First Feature]] -- Build something real with ZERG.
- [[Getting Started]] -- Understand the core concepts.
