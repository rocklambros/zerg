# ZERG v2.0 Implementation Prompts

**Version**: 1.0.0
**Created**: January 25, 2026
**Total Tasks**: 32
**Estimated Sessions**: 15-20

---

## Quick Start

1. Open Claude Code in your ZERG project directory
2. Start with L0 tasks (no dependencies)
3. Copy the task prompt into Claude Code
4. Follow TDD and verification protocols
5. Mark task complete in `ZERG_V2_BACKLOG.md`

---

## Prompt Files

| File | Tasks | Focus |
|------|-------|-------|
| `L0-TASK-001-orchestrator-core.md` | 1 | Central orchestrator |
| `L0-TASK-002-state-persistence.md` | 1 | State and checkpoints |
| `L0-TASK-003-task-graph.md` | 1 | Task graph parser |
| `L0-TASK-004-worker-protocol.md` | 1 | Protocol and messages |
| `L1-TASK-001-worktree-manager.md` | 1 | Git worktree isolation |
| `L1-TASK-002-port-allocator.md` | 1 | Port management |
| `L1-TASK-003-container-launcher.md` | 1 | Docker containers |
| `L1-TASK-004-prompt-templates.md` | 1 | Worker/reviewer templates |
| `L1-TASK-005-metrics-collector.md` | 1 | Metrics and cost tracking |
| `L2-core-commands.md` | 6 | Init, rush, worker, status, plan, design |
| `L3-quality-commands.md` | 7 | Gates, analyze, test, security, refactor, review, troubleshoot |
| `L4-advanced-commands.md` | 6 | Git, build, session, index, document, purge |
| `L5-meta-commands.md` | 4 | Explain, research, estimate, spawn |

---

## Execution Order

### Phase 1: Foundation (Sessions 1-4)

Start with L0 tasks. These can be worked in parallel:

```
Session 1: L0-TASK-001 (Orchestrator Core) - CRITICAL PATH
Session 2: L0-TASK-002 (State Persistence)
Session 2: L0-TASK-004 (Worker Protocol) - parallel with L0-TASK-002
Session 3: L0-TASK-003 (Task Graph) - after L0-TASK-002
```

### Phase 2: Infrastructure (Sessions 4-7)

L1 tasks build on L0:

```
Session 4: L1-TASK-001 (Worktree Manager) - CRITICAL PATH
Session 4: L1-TASK-002 (Port Allocator) - parallel
Session 5: L1-TASK-003 (Container Launcher) - after L1-TASK-002
Session 5: L1-TASK-004 (Prompt Templates) - parallel
Session 6: L1-TASK-005 (Metrics Collector) - parallel
```

### Phase 3: Core Commands (Sessions 7-10)

Update existing commands:

```
Session 7: L2-TASK-001 (Init Update)
Session 7: L2-TASK-002 (Rush Update) - CRITICAL PATH
Session 8: L2-TASK-003 (Worker Update)
Session 8: L2-TASK-004 (Status Update)
Session 9: L2-TASK-005 (Plan Update)
Session 9: L2-TASK-006 (Design Update)
```

### Phase 4: Quality (Sessions 10-14)

Add quality commands:

```
Session 10: L3-TASK-001 (Quality Gates) - CRITICAL PATH
Session 11: L3-TASK-002 (Analyze)
Session 11: L3-TASK-003 (Test)
Session 12: L3-TASK-004 (Security)
Session 12: L3-TASK-005 (Refactor)
Session 13: L3-TASK-006 (Review)
Session 13: L3-TASK-007 (Troubleshoot)
```

### Phase 5: Advanced (Sessions 14-17)

Add advanced commands:

```
Session 14: L4-TASK-001 (Git with Finish)
Session 14: L4-TASK-002 (Build)
Session 15: L4-TASK-003 (Session)
Session 15: L4-TASK-004 (Index)
Session 16: L4-TASK-005 (Document)
Session 16: L4-TASK-006 (Purge)
```

### Phase 6: Meta (Sessions 17-20)

Add meta-orchestration:

```
Session 17: L5-TASK-001 (Explain)
Session 18: L5-TASK-002 (Research)
Session 19: L5-TASK-003 (Estimate)
Session 20: L5-TASK-004 (Spawn)
```

---

## Critical Path

These tasks block the most downstream work:

1. **L0-TASK-001**: Orchestrator Core → Everything depends on this
2. **L1-TASK-001**: Worktree Manager → Worker isolation
3. **L2-TASK-002**: Rush Update → Main execution command
4. **L3-TASK-001**: Quality Gates → Code quality enforcement

Complete these first to unblock parallel work.

---

## Using the Prompts

### In Claude Code

```bash
# Open Claude Code
claude

# Reference the prompt file
> Read /path/to/prompts/L0-TASK-001-orchestrator-core.md and implement it
```

### Verification Protocol

Each prompt includes a verification command. Run it BEFORE claiming completion:

```bash
# Example
cd .zerg && python -c "from orchestrator import Orchestrator; o = Orchestrator(); print('OK')"
```

### TDD Protocol

For code tasks, follow red-green-refactor:

1. Write failing test
2. Run test → MUST FAIL
3. Write minimal implementation
4. Run test → MUST PASS
5. Refactor if needed

### Completion Checklist

Before marking a task complete:

- [ ] All acceptance criteria met
- [ ] Verification command passes
- [ ] Unit tests pass
- [ ] No linting errors
- [ ] Code committed with conventional message

---

## Tracking Progress

Update `ZERG_V2_BACKLOG.md` after each session:

1. Mark tasks complete: `- [x]`
2. Log session in Session Log table
3. Add any blockers to Blockers table
4. Update completion tracking counts

---

## Dependencies Reference

```
L0-TASK-001 (Orchestrator)
├── L1-TASK-001 (Worktree)
│   ├── L2-TASK-002 (Rush)
│   ├── L4-TASK-001 (Git)
│   └── L4-TASK-006 (Purge)
├── L1-TASK-002 (Ports)
│   └── L1-TASK-003 (Container)
└── L1-TASK-005 (Metrics)
    └── L2-TASK-004 (Status)

L0-TASK-002 (State)
├── L0-TASK-003 (Task Graph)
│   ├── L2-TASK-006 (Design)
│   ├── L3-TASK-001 (Gates)
│   └── L5-TASK-003 (Estimate)
├── L1-TASK-005 (Metrics)
├── L4-TASK-003 (Session)
└── L4-TASK-004 (Index)

L0-TASK-004 (Protocol)
├── L1-TASK-004 (Templates)
│   └── L2-TASK-003 (Worker)
└── L3-TASK-006 (Review)
```

---

## Notes

- Tasks are designed for exclusive file ownership
- Each task should take 0.5-2 sessions
- Use Python 3.11+ features (dataclasses, type hints)
- Follow existing ZERG code patterns
- Update ARCHITECTURE.md if design changes
