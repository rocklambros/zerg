# ZERG

Parallel Claude Code execution system. Overwhelm features with coordinated worker instances.

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

**Levels**: Tasks grouped by dependencies. All workers finish Level 1 before any start Level 2.

**File Ownership**: Each task owns specific files. No conflicts possible.

**Spec as Memory**: Workers read spec files, not conversation history. Stateless and restartable.

**Verification**: Every task has an automated verification command. Pass or fail, no subjectivity.

## Configuration

Edit `.zerg/config.yaml` for:
- Worker limits
- Timeouts
- Quality gate commands
- MCP servers
- Resource limits

## Troubleshooting

Workers not starting? Check Docker, ANTHROPIC_API_KEY, and port availability.

Tasks failing? Check verification commands in task-graph.json.

Need to restart? ZERG is crash-safe. Run `/zerg:rush` again to resume.

<!-- SECURITY_RULES_START -->
# Security Rules

Auto-generated from [TikiTribe/claude-secure-coding-rules](https://github.com/TikiTribe/claude-secure-coding-rules)

## Detected Stack

- **Languages**: python

## Imported Rules

@security-rules/_core/owasp-2025.md

<!-- SECURITY_RULES_END -->
