# Phase 1: Synthesis and Migration Path

**Date**: January 25, 2026
**Status**: Complete
**Update**: Integrated Claude Native Tasks as coordination layer

## Executive Summary

ZERG's scope is narrower than initially assessed. Claude's native Tasks feature handles state persistence, cross-agent memory, and coordination primitives. ZERG becomes a **parallel execution orchestration layer** that adds: level-based dependency ordering, git worktree isolation, exclusive file ownership, and merge gates. The orchestrator implementation simplifies significantly.

---

## What Claude Native Tasks Provides

| Capability | How It Works | ZERG Integration |
|------------|--------------|------------------|
| **Persistent state** | Tasks survive sessions | Workers resume from task state |
| **Cross-agent memory** | All instances see same Tasks | No custom IPC needed |
| **Task status** | Built-in progress tracking | Orchestrator polls for level completion |
| **Coordination** | Tasks act as shared record | Level gates check task completion |

**Key Insight**: ZERG doesn't build a distributed system. ZERG orchestrates Claude instances that already share state via Tasks.

---

## What ZERG Uniquely Provides

| Capability | Why Tasks Don't Cover | ZERG Implementation |
|------------|----------------------|---------------------|
| **Level synchronization** | Tasks don't enforce execution order | Orchestrator blocks level N+1 until N complete |
| **Git worktree isolation** | Tasks don't manage git | Create worktree per worker branch |
| **Exclusive file ownership** | Tasks don't prevent conflicts | Assign files at decomposition time |
| **Merge gates** | Tasks don't validate quality | Run verification before merge |
| **Task decomposition** | Tasks don't generate subtasks | Parse spec into parallel tasks |

---

## Converging Patterns

### 1. Spec-Based Task Generation (Not State Sharing)

**Previous Understanding**: Workers share state via spec files
**Revised Understanding**: Claude Tasks handles state. Specs define *what* to decompose, not *how* to communicate.

**ZERG Role**: Parse spec → generate Tasks with levels and file assignments

### 2. Git Worktrees for Isolation

**Sources**: ZERG design, packnplay, superpowers
**ZERG Role**: Create worktree per worker, merge on level completion

### 3. Level-Based Execution (ZERG Unique)

**No External Source Provides This**

ZERG's level synchronization remains unique. Claude Tasks tracks completion but doesn't enforce ordering. ZERG adds the orchestration logic:

```
Level 0: foundation tasks
    ↓ (all complete)
Level 1: core tasks  
    ↓ (all complete)
Level 2: integration tasks
    ↓ (all complete)
Level 3: testing tasks
    ↓ (all complete)
Level 4: quality tasks
```

---

## Simplified Architecture

### Before (Building Everything)

```
┌─────────────────────────────────────────────┐
│              ZERG Orchestrator              │
├─────────────────────────────────────────────┤
│ • State persistence      ← Build this       │
│ • Cross-agent memory     ← Build this       │
│ • Status aggregation     ← Build this       │
│ • Task coordination      ← Build this       │
│ • Level synchronization  ← Build this       │
│ • Git worktrees          ← Build this       │
│ • Merge gates            ← Build this       │
│ • Task decomposition     ← Build this       │
└─────────────────────────────────────────────┘
```

### After (Using Claude Tasks)

```
┌─────────────────────────────────────────────┐
│           Claude Native Tasks               │
├─────────────────────────────────────────────┤
│ • State persistence      ✅ Provided        │
│ • Cross-agent memory     ✅ Provided        │
│ • Status tracking        ✅ Provided        │
│ • Task coordination      ✅ Provided        │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│              ZERG Orchestrator              │
├─────────────────────────────────────────────┤
│ • Level synchronization  ← Build this       │
│ • Git worktrees          ← Build this       │
│ • Merge gates            ← Build this       │
│ • Task decomposition     ← Build this       │
│ • File ownership         ← Build this       │
└─────────────────────────────────────────────┘
```

**Reduction**: 8 components → 5 components (37% less to build)

---

## Migration Path

### Phase 1: Task Decomposition (Week 1)

**Goal**: Spec → Claude Tasks with levels

**Implementation**:
1. Parse SPEC.md into task list
2. Detect dependencies, assign levels
3. Assign exclusive files per task
4. Create Claude Tasks via native API

**Validation**:
- Input: SPEC.md with 10 features
- Output: 10 Claude Tasks with levels 0-4, file assignments

### Phase 2: Worker Isolation (Week 2)

**Goal**: Workers execute in worktrees

**Implementation**:
1. Worker reads assigned Task
2. Create git worktree for worker branch
3. Execute task in worktree
4. Mark Task complete

**Validation**:
- Worker starts, reads Task
- Worktree created at correct path
- Work committed to branch
- Task marked complete in Claude Tasks

### Phase 3: Level Gates (Week 3)

**Goal**: Levels execute in order with quality gates

**Implementation**:
1. Orchestrator polls Tasks for level completion
2. Block level N+1 start until level N complete
3. Run merge gate verification
4. Merge worktrees to main

**Validation**:
- Level 1 tasks don't start until level 0 complete
- Merge gate runs verification command
- Failed verification blocks merge

### Phase 4: Hardening (Week 4)

**Goal**: Production reliability

**Implementation**:
1. Retry failed tasks
2. Timeout stuck workers
3. Security rule integration
4. Cost tracking

**Validation**:
- Failed task retries automatically
- Stuck worker detected and restarted
- Generated code passes security rules

---

## Architecture Decisions

### AD-001: Use Claude Tasks for State
Claude Tasks provides persistent state, cross-agent memory, and coordination. ZERG does not implement custom state management.

### AD-002: ZERG Owns Execution Ordering
Claude Tasks tracks completion but doesn't enforce order. ZERG implements level-based synchronization by monitoring Tasks and gating level transitions.

### AD-003: Preserve Level Synchronization
Level-based execution is unique to ZERG and provides dependency ordering without complex scheduling.

### AD-004: Preserve Exclusive File Ownership
File assignments happen at decomposition time, stored in Task metadata. Workers check assignments before modifying files.

### AD-005: Git Worktrees for Isolation
Each worker gets a worktree. Merge happens at level completion after gate verification.

### AD-006: Adopt superpowers Task Format
Task decomposition follows superpowers' writing-plans pattern: 2-5 minute tasks, explicit file paths, verification commands.

---

## Removed Scope

These items were in the original plan but are now handled by Claude Tasks:

| Item | Original Plan | New Status |
|------|---------------|------------|
| State persistence | Build spec file sync | Use Tasks |
| Worker communication | Build IPC via files | Use Tasks |
| Status aggregation | Build status command | Use Tasks |
| Session continuity | Build handoff logic | Use Tasks |
| Progress reporting | Build dashboard | Use Tasks UI |

---

## Risk Assessment

### Reduced Risks

| Risk | Previous | Now |
|------|----------|-----|
| State sync bugs | High | Eliminated (Tasks handles) |
| IPC complexity | High | Eliminated (Tasks handles) |
| Session loss | Medium | Eliminated (Tasks persists) |

### Remaining Risks

| Risk | Mitigation |
|------|------------|
| Tasks API changes | Abstract behind interface |
| Level logic bugs | Comprehensive testing |
| Worktree conflicts | Verify file ownership |
| Merge failures | Gate verification |

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
