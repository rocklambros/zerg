# Phase 1 Checkpoint 2: Tier 1 External Repository Analysis

**Date**: January 25, 2026
**Status**: Complete

## Repositories Analyzed

### 1. block/goose

**Purpose**: Open-source AI agent for engineering task automation

**Architecture**:
- Language: Rust (multi-crate structure)
- Components: goose core, goose-cli, goose-server, goose-mcp, mcp-client/core/server
- Interfaces: CLI and Electron desktop app
- Configuration: Recipe system (goose-self-test.yaml)

**Key Patterns**:
- Multi-model configuration support
- MCP server integration as extension mechanism
- Recipe-based workflow automation
- Hermit for reproducible development environments

**Code Quality Principles**:
- Self-documenting code over comments
- Trust type system, avoid defensive code
- Clean logs over verbose output

**Delta from ZERG**: Production Rust implementation vs Python design, desktop UI, established testing framework

---

### 2. obra/packnplay

**Purpose**: Containerization wrapper launching coding agents in isolated Docker containers

**Architecture**:
- Language: Go
- 100% Microsoft devcontainer spec compliance
- XDG-compliant worktree storage (~/.local/share/packnplay/worktrees)

**Key Patterns**:
- **Smart User Detection**: Priority chain (devcontainer.json remoteUser → cached → runtime → root fallback)
- **Credential Management**: Interactive first-run setup, read-only mounts (git, SSH, GPG, npm), macOS Keychain integration
- **Host Path Preservation**: Identical paths in container (no /workspace abstraction)
- **Environment Configs**: Named profiles with variable substitution

**Agent Support**: First-class support for 7 agents: Claude Code, OpenCode, Codex, Gemini, Copilot, Qwen, Amp

**Delta from ZERG**: Production Go implementation, credential system, multi-agent support, path preservation

---

### 3. obra/superpowers

**Purpose**: Complete software development workflow via composable skills

**Architecture**:
- Plugin system for Claude Code marketplace
- 14 skills in skills/ directory
- Human-in-loop between major phases

**Workflow Sequence**:
1. brainstorming (Socratic design refinement)
2. using-git-worktrees (isolated workspace on new branch)
3. writing-plans (bite-sized tasks 2-5 min each)
4. subagent-driven-development / executing-plans
5. test-driven-development
6. requesting-code-review
7. finishing-a-development-branch

**Subagent Pattern**:
- Fresh subagent per task (stateless)
- Two-stage review: spec compliance first, then code quality
- Same-session execution
- Continuous progress tracking

**Delta from ZERG**: Skill-based vs command-based, marketplace integration, human-in-loop enforcement

---

### 4. SuperClaude-Org/SuperClaude_Framework

**Purpose**: Meta-programming framework transforming Claude Code into structured development platform

**Architecture**:
- Language: Python (pipx installable)
- 30 slash commands
- 16 specialized agents
- 7 behavioral modes
- 8 MCP server integrations

**Command Categories**: Planning/Design (4), Development (5), Testing/Quality (4), Documentation (2), Version Control (1), Project Management (3), Research/Analysis (2), Utilities (9)

**Behavioral Modes**: Brainstorming, Business Panel, Deep Research (multi-hop reasoning), Orchestration, Token-Efficiency (30-50% savings), Task Management, Introspection

**MCP Integration**: 8 servers (Tavily, Context7, Sequential-Thinking, Serena, Playwright, Magic, Morphllm-Fast-Apply, Chrome DevTools)

**Delta from ZERG**: Production Python implementation, extensive command library, 16 agents, behavioral modes

---

## Converging Patterns (3+ Sources)

### 1. Git Worktrees for Isolation
- **ZERG**: Design specifies worktrees per worker
- **packnplay**: XDG-compliant worktree management
- **superpowers**: using-git-worktrees skill
- **Consensus**: Standard approach for parallel AI agent work

### 2. MCP Server Integration
- **ZERG**: Config template references MCP
- **goose**: goose-mcp crate
- **packnplay**: Agent-specific MCP mounting
- **SuperClaude**: 8 MCP servers with CLI installation
- **Consensus**: MCP is the extension mechanism

### 3. Task Decomposition with Verification
- **ZERG**: verification_command per task
- **superpowers**: writing-plans (2-5 min tasks with verification)
- **SuperClaude**: /sc:spawn with decomposition
- **Consensus**: Tasks need verification commands

---

## Unique Innovations

| Repository | Innovation |
|------------|------------|
| ZERG | Level-based synchronization with merge gates |
| ZERG | Exclusive file ownership at design time |
| packnplay | Smart user detection with caching |
| packnplay | Host path preservation (no /workspace) |
| superpowers | Two-stage review (spec then code quality) |
| SuperClaude | 16 specialized agents with delegation |
| SuperClaude | Behavioral modes (7 modes) |

---

## Patterns to Adopt

| Source | Pattern | ZERG Application |
|--------|---------|------------------|
| packnplay | Git worktree management | Runtime implementation |
| packnplay | Smart user detection | Devcontainer integration |
| superpowers | Two-stage review | Quality gates |
| superpowers | Task specification format | Decomposition output |
| SuperClaude | Agent delegation | Future enhancement |
