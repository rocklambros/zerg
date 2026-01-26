# ZERG v2 Implementation Meta-Prompt

You are implementing the ZERG v2.0 orchestration system. Your task prompts are in `.gsd/tasks/prompts/`. Work through them systematically following the dependency order.

## Operating Mode

Execute tasks autonomously. After completing each task:
1. Run the verification command
2. Commit changes with conventional message: `feat(zerg): <description> [TASK-ID]`
3. Update progress tracking
4. Proceed to the next eligible task

Stop only when:
- A verification command fails (report the failure and await guidance)
- All tasks in the current session are complete
- You hit context threshold (70%)

## Task Selection

Read `.gsd/tasks/prompts/README.md` for execution order and dependencies.

**Dependency Rules:**
- L0 tasks have no dependencies, start with these
- L1 tasks require their L0 dependencies complete
- Higher levels require lower level dependencies
- Parallel tasks within a level can execute in any order

## Per-Task Protocol

For each task:

1. **Read the prompt file** completely
2. **Check dependencies** are satisfied
3. **Follow TDD** for code tasks:
   - Write failing test first
   - Run test (must fail)
   - Write implementation
   - Run test (must pass)
4. **Run verification command** before claiming done
5. **Self-review**: All acceptance criteria met?
6. **Commit** with task ID in message

## Progress Tracking

After each task, update `.gsd/tasks/PROGRESS.md`:

```markdown
## Completed Tasks
- [x] L0-TASK-001: Orchestrator Core (2024-01-25)
- [x] L0-TASK-002: State Persistence (2024-01-25)

## In Progress
- [ ] L0-TASK-003: Task Graph

## Blocked
(none)

## Session Log
| Date | Tasks Completed | Notes |
|------|-----------------|-------|
| 2024-01-25 | L0-001, L0-002 | Foundation complete |
```

## Context Management

Monitor your context usage. When approaching 70%:
1. Complete current task if close
2. Commit all changes
3. Update progress tracking
4. Create checkpoint note for next session

## Forbidden Actions

- Do NOT skip verification
- Do NOT modify files outside task scope
- Do NOT claim completion without test evidence
- Do NOT use phrases: "should work", "probably passes", "looks good"

## Starting a Session

```
1. Read .gsd/tasks/PROGRESS.md
2. Identify next eligible task (dependencies met)
3. Read task prompt from .gsd/tasks/prompts/
4. Execute task following protocol
5. Repeat until session limit or context threshold
```

## Example Session Start

```
> Read .gsd/tasks/prompts/README.md for overview
> Read .gsd/tasks/PROGRESS.md for current state
> Identify: L0-TASK-001 is next (no dependencies)
> Read .gsd/tasks/prompts/L0-TASK-001-orchestrator-core.md
> Execute task...
```

Begin by reading the README and PROGRESS files to determine your starting point.
