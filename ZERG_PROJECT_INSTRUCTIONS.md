# ZERG Development

You are developing ZERG, a system for parallel Claude Code execution. Your role is to improve, harden, and extend it.

## Architecture

ZERG combines GSD methodology (spec-driven, fresh agents per task), Claude Code's native Tasks (persistent coordination), and devcontainers (isolated parallel execution).

Key components:
- `.zerg/orchestrator.py`: Python script managing worker fleet
- `.claude/commands/`: Slash command definitions (init, plan, design, rush, worker, status)
- `.devcontainer/`: Container configuration for workers
- `ARCHITECTURE.md`: Design decisions and rationale

## Design Decisions (Intentional)

Understand these before proposing changes:

- **Git worktrees**: Each worker gets own branch. Prevents conflicts without locking.
- **Levels**: Tasks execute in waves. All workers complete level N before any start N+1.
- **Exclusive file ownership**: No two tasks modify same file. Enforced at design time.
- **Spec as memory**: Workers share spec files, not conversation context. Stateless, restartable.
- **Native Tasks**: Status in Claude Code's Tasks via shared Docker volume.
- **Random ports**: Workers pick from 49152-65535. Orchestrator tracks assignments.

## Current Gaps

- No production testing
- Basic error recovery
- No monitoring dashboard
- No integration tests
- No cost tracking
- No remote execution

## Development Standards

<investigate_before_changing>
Read existing code thoroughly. Understand why decisions were made. Check ARCHITECTURE.md for rationale. Match existing patterns.
</investigate_before_changing>

<avoid_overengineering>
Make only requested changes. No speculative features or abstractions. Simpler is better. Remove complexity when possible.
</avoid_overengineering>

<use_parallel_tool_calls>
Execute independent tool calls simultaneously. Read multiple files in parallel. Sequence only when outputs feed inputs.
</use_parallel_tool_calls>

<default_to_action>
Implement changes directly. Fix bugs, don't describe fixes. Use tools to discover context rather than asking.
</default_to_action>

## Testing Changes

1. Manual test in a real project
2. Consider edge cases: zero tasks, one worker, ten workers, failures
3. Update docs if behavior changed
4. Preserve backwards compatibility

## Improvement Areas

**Orchestrator**: Error handling, health checks, merge conflict resolution, metrics
**Commands**: Prompt tuning, edge case handling, better examples
**Devcontainer**: Layer caching, MCP config, GPU support
**Docs**: Troubleshooting, contribution guide

## Output Style

Flowing prose, not bullets. Concise updates on what changed and why. After changes, summarize and indicate what to test.
