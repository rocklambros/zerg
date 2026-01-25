# Phase 1: Capability Matrix

**Date**: January 25, 2026
**Status**: Complete
**Update**: Added Claude Native Tasks as capability source

## Critical Update: Claude Native Tasks

Claude Code's native Tasks feature provides several capabilities that external repositories implement from scratch. This significantly reduces ZERG's implementation burden.

### What Claude Native Tasks Provides

| Capability | Description | ZERG Impact |
|------------|-------------|-------------|
| Persistent state | Tasks survive session boundaries | No custom persistence needed |
| Cross-instance memory | Agents share context via Tasks | No spec file synchronization needed |
| Task tracking | Built-in status, progress | Reduced orchestrator complexity |
| Coordination | Tasks visible to all instances | No custom IPC mechanism |
| Conversation continuity | Context preserved | Workers can resume |

### What ZERG Still Needs to Implement

| Capability | Rationale |
|------------|-----------|
| Level synchronization | Tasks don't enforce execution order |
| Git worktree management | Tasks don't create branches |
| Merge gates | Tasks don't validate code quality |
| Task decomposition | Tasks don't generate subtasks from specs |
| Exclusive file assignment | Tasks don't prevent conflicts |

---

## Repository Comparison Matrix

### Implementation Status

| Capability | Claude Tasks | ZERG | goose | packnplay | superpowers | SuperClaude |
|------------|--------------|------|-------|-----------|-------------|-------------|
| **State & Coordination** |
| Persistent state | ✅ Native | ❌ Design | ❌ | ❌ | ❌ PLAN.md | ✅ Session |
| Cross-agent memory | ✅ Native | ❌ Design | ❌ | ❌ | ❌ | ✅ Reflexion |
| Task status tracking | ✅ Native | ❌ Design | ❌ | ❌ | ❌ | ✅ |
| **Orchestration** |
| Level synchronization | ❌ | ❌ Design | ❌ | ❌ | ❌ | ❌ |
| Task decomposition | ❌ | ❌ Design | ❌ Recipes | ❌ | ✅ writing-plans | ✅ /sc:spawn |
| Worker health | ❌ | ❌ Design | ❌ | ❌ | ❌ | ❌ |
| **Isolation** |
| Git worktrees | ❌ | ❌ Design | ❌ | ✅ | ✅ | ❌ |
| Devcontainers | ❌ | ✅ Config | ❌ | ✅ | ❌ | ❌ |
| Port management | ❌ | ❌ Design | ❌ | ❌ | ❌ | ❌ |
| **Quality** |
| Verification commands | ❌ | ✅ Schema | ❌ | ❌ | ✅ | ✅ |
| Two-stage review | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| Merge gates | ❌ | ❌ Design | ❌ | ❌ | ❌ | ❌ |
| **Security** |
| Secure code rules | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Runtime protection | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

**Legend**: ✅ Implemented | ❌ Not implemented | Design = Documented but no code

---

## Capability Coverage

### Provided by Claude Native Tasks (No Implementation Needed)

| Capability | Previous Plan | New Status |
|------------|---------------|------------|
| State persistence | Build custom spec sync | Use Tasks |
| Inter-agent communication | Build via spec files | Use Tasks |
| Status aggregation | Build orchestrator feature | Use Tasks |
| Session continuity | Build handoff logic | Use Tasks |
| Progress tracking | Build status command | Use Tasks |

### Still Requires Implementation

| Capability | Source | Why Tasks Don't Cover |
|------------|--------|----------------------|
| Level synchronization | ZERG unique | Tasks don't enforce execution order |
| Git worktree creation | packnplay | Tasks don't manage git |
| Merge conflict detection | ZERG unique | Tasks don't validate git state |
| Task decomposition | superpowers | Tasks don't generate subtasks |
| Verification execution | superpowers | Tasks don't run commands |
| Quality gates | superpowers | Tasks don't block on quality |
| Port allocation | ZERG unique | Tasks don't manage networking |
| Security rules | claude-secure | Tasks don't enforce code patterns |

---

## Simplified Architecture

### Before (Without Tasks)

```
orchestrator.py
├── State management (persistence, sync)
├── Worker communication (IPC, messages)
├── Status aggregation (polling, combining)
├── Level synchronization
├── Git worktree management
├── Merge gates
└── Task decomposition
```

### After (With Tasks)

```
orchestrator.py
├── Level synchronization          ← Still needed
├── Git worktree management        ← Still needed
├── Merge gates                    ← Still needed
├── Task decomposition             ← Still needed
└── Verification execution         ← Still needed

Claude Tasks handles:
├── State persistence
├── Cross-agent memory
├── Status tracking
└── Coordination primitives
```

---

## Implementation Priority

| Priority | Capability | Rationale |
|----------|------------|-----------|
| P0 | Task decomposition | Cannot parallelize without subtasks |
| P0 | Git worktree creation | Cannot isolate without worktrees |
| P0 | Level synchronization | Cannot order without levels |
| P1 | Verification execution | Cannot validate without running commands |
| P1 | Merge gates | Cannot combine without quality checks |
| P2 | Port allocation | Needed for services, not critical path |
| P2 | Security rules | Important but not blocking |

---

## ZERG's Unique Value

With Claude Tasks providing state/coordination, ZERG's value proposition:

| What Tasks Provides | What ZERG Adds |
|---------------------|----------------|
| Persistent state | Level-based execution ordering |
| Cross-agent memory | Exclusive file ownership |
| Task tracking | Git worktree isolation |
| Coordination | Merge gates between levels |
| | Devcontainer-based execution |
| | Task decomposition from specs |

ZERG is not a state management system. ZERG is a **parallel execution orchestration layer** that uses Claude Tasks for state while adding:
1. Dependency-aware ordering (levels)
2. Conflict-free parallelism (worktrees + file ownership)
3. Quality enforcement (merge gates)

---

## External Repository Reference

| Repository | URL | Primary Value |
|------------|-----|---------------|
| block/goose | github.com/block/goose | Rust agent architecture |
| obra/packnplay | github.com/obra/packnplay | Worktree + devcontainer |
| obra/superpowers | github.com/obra/superpowers | Task decomposition |
| SuperClaude | github.com/SuperClaude-Org/SuperClaude_Framework | Command library |
| claude-secure | github.com/TikiTribe/claude-secure-coding-rules | Security rules |
| nova-protector | github.com/fr0gger/nova-claude-code-protector | Runtime protection |
