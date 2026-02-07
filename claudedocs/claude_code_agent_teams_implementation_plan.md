# ZERG + Claude Code Agent Teams: Implementation Analysis

> Full sequential thinking analysis from brainstorm session on 2026-02-07.
> 13-dimension deep analysis using sequential-thinking MCP server.
> Source: `/Users/klambros/.claude/plans/drifting-beaming-pinwheel.md`

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Sequential Thinking Analysis](#sequential-thinking-analysis)
   - [Dimension 1: Worker Spawning & Lifecycle](#dimension-1-worker-spawning--lifecycle)
   - [Dimension 2: Inter-Agent Communication](#dimension-2-inter-agent-communication)
   - [Dimension 3: Task Coordination & Claiming](#dimension-3-task-coordination--claiming)
   - [Dimension 4: Context Engineering & Token Efficiency](#dimension-4-context-engineering--token-efficiency)
   - [Dimension 5: Quality Gates & Hooks](#dimension-5-quality-gates--hooks)
   - [Dimension 6: Plan Approval Workflow](#dimension-6-plan-approval-workflow)
   - [Dimension 7: Display & Observability](#dimension-7-display--observability)
   - [Dimension 8: New Command Opportunities](#dimension-8-new-command-opportunities)
   - [Dimension 9: Migration Strategy & Architecture](#dimension-9-migration-strategy--architecture)
   - [Dimension 10: Risks, Limitations & Mitigations](#dimension-10-risks-limitations--mitigations)
   - [Dimension 11: Synthesis — The Big Picture](#dimension-11-synthesis--the-big-picture)
3. [Implementation Plan](#implementation-plan)
4. [GitHub Issues](#github-issues)
5. [Unresolved Questions](#unresolved-questions)

---

## Executive Summary

ZERG was built before Claude Code Agent Teams existed. It reimplemented, from scratch, many primitives that Agent Teams now provides natively: worker spawning, task coordination, state management, and quality gates. But ZERG also has capabilities Agent Teams does NOT provide: intelligent task decomposition, context engineering for token efficiency, file ownership models, architectural guardrails, multi-mode execution (subprocess, container, CI/CD), crash-safe resume, and workflow orchestration.

**The strategic opportunity**: ZERG becomes a **higher-level orchestration framework** that uses Agent Teams as its execution runtime (when available), while maintaining its own execution runtimes for headless/CI/container scenarios.

Think of it as:
- **Agent Teams** = low-level runtime (like a JVM or Docker)
- **ZERG** = application framework (like Spring Boot or Kubernetes)

**Key architectural alignment**: Agent Teams uses the **same Claude Code Task system** (`TaskCreate`/`TaskUpdate`/`TaskList`/`TaskGet`) that ZERG already mandates as its authoritative source of truth. They are built for each other.

---

## Sequential Thinking Analysis

### Dimension 1: Worker Spawning & Lifecycle

#### Current ZERG Architecture
- `launcher.py` handles spawning via subprocess or Docker
- Workers get `ANTHROPIC_API_KEY`, `CLAUDE_CODE_TASK_LIST_ID`, and other env vars
- Workers are launched with `claude --print -p "prompt"` (headless mode)
- No interactive communication after spawn — fire and forget
- Worker lifecycle: spawn → execute spec → write results → exit
- Crash recovery: `/zerg:rush --resume` re-reads task states

#### Agent Teams Model
- Native teammate spawning from the lead session
- Teammates are full interactive Claude Code sessions
- Teammates can be messaged, redirected, shut down gracefully
- Teammates auto-load CLAUDE.md, MCP servers, skills
- Lead can require plan approval before implementation
- Shutdown: lead sends request, teammate can approve/reject

#### Opportunity

Replace launcher.py subprocess spawning with native Agent Teams teammate spawning via a new `AgentTeamLauncher`. This gives us:

1. **Interactive communication** — redirect workers mid-task
2. **Graceful shutdown** — instead of kill signals
3. **Plan approval per worker** — quality gate before implementation
4. **Automatic context loading** — no more custom context injection
5. **Split-pane visibility** — into worker progress (vs. opaque subprocess)

#### Approach

Adapter pattern: `AgentTeamLauncher` alongside `SubprocessLauncher` and `ContainerLauncher`. All implement the same `WorkerLauncher` ABC.

| ABC Method | AgentTeamLauncher Implementation |
|------------|----------------------------------|
| `spawn()` | Spawn teammate with task-scoped spawn prompt |
| `monitor()` | Check teammate status via task list / mailbox |
| `terminate()` | Send graceful shutdown request |
| `get_output()` | Read teammate session output / messages |

**Key concern**: Agent Teams says "no nested teams" — teammates can't spawn their own teams. This is fine since ZERG workers are leaf nodes.

---

### Dimension 2: Inter-Agent Communication

#### Current State
- Workers are completely isolated from each other
- Communication is strictly hierarchical: orchestrator → worker (via spec files)
- Worker → orchestrator (via file output, TaskUpdate status)
- No worker-to-worker communication at all
- Cross-task dependencies handled by LEVEL system: L1 completes fully before L2 starts

#### Agent Teams Capability
- Direct peer-to-peer messaging between teammates
- Broadcast to all teammates
- Automatic message delivery (no polling)
- Idle notifications to lead
- Shared task list visible to all

#### Opportunity — MASSIVE

This is the single most transformative capability Agent Teams adds to ZERG:

1. **Intra-level collaboration**: Workers within the same level could coordinate on interface boundaries. Worker building the API endpoint could message worker building the frontend component: "Hey, I changed the response shape to X." Currently this requires spec precision + level boundary + merge.

2. **Streaming dependency resolution**: Instead of rigid level boundaries, workers could signal "my output file X is ready" and unblock individual downstream workers. This breaks the all-or-nothing level barrier.

3. **Debugging hypothesis mode**: The Agent Teams doc explicitly calls out "competing hypotheses" as a use case. `/zerg:debug` could spawn multiple investigators that debate root causes.

4. **Review panels**: `/zerg:review` could spawn specialized reviewers (security, performance, test coverage) that challenge each other's findings.

5. **Design collaboration**: During `/zerg:design`, architect teammates could debate trade-offs before the task graph is finalized.

#### Risk

More communication = more tokens. ZERG's isolation is token-efficient. Need a communication budget or opt-in model.

---

### Dimension 3: Task Coordination & Claiming

#### Current State
- Task graph defined upfront during `/zerg:design`
- Tasks have explicit levels (L1, L2, L3...)
- File ownership is pre-assigned per task (exclusive)
- Workers claim tasks via `TaskUpdate(status: "in_progress")`
- Level-based barrier: ALL level N tasks must complete before level N+1 starts
- Orchestrator manages level transitions and triggers merge/quality gates between levels

#### Agent Teams Capability
- Shared task list with self-coordination
- Task claiming uses **file locking** (prevents race conditions)
- Tasks have dependencies (`blocks`/`blockedBy`) that auto-unblock
- Teammates self-claim next available task when done
- No concept of "levels" — just dependency DAG

#### Opportunity: From Levels to DAG

ZERG could evolve from rigid LEVELS to a true dependency DAG:

```
Current:  L1=[A,B,C] → barrier → L2=[D,E] → barrier → L3=[F]
Proposed: A→D, B→D, C→E, D→F, E→F (fine-grained deps)
```

Worker finishes task A → task D immediately unblocks → any available worker claims D. No waiting for B and C to finish (unless D actually depends on them).

**Impact**: Potentially massive throughput improvement. If L1 has 5 tasks and L2 has 3 tasks, currently we wait for all 5 to finish before starting any of the 3. With DAG-based deps, L2 tasks that only depend on completed L1 tasks can start immediately.

**Migration path**: task-graph.json already has dependency information. The "level" concept is a flattening of the DAG. We could:
1. Keep levels as a PLANNING concept (human-readable grouping)
2. Use fine-grained task deps for EXECUTION
3. Agent Teams handles unblocking automatically

**Open question**: Merge/quality gates currently run at level boundaries. With DAG execution, when do gates run?
- After each task completes (too frequent) → Use TaskCompleted hook
- After "conceptual level" groups complete (need virtual barriers)
- Only at the end (too late)
- Compromise: configurable checkpoints in task graph

---

### Dimension 4: Context Engineering & Token Efficiency

#### Current State
- Custom context engineering plugin with 3 subsystems:
  - Command splitting: `core.md` (~30%) + `details.md` (~70%)
  - Task-scoped context: security rules filtered by extension, spec excerpts, dependency context
  - Budget tracking: 4000 token budget per task
- Workers get minimal prompts with task-scoped content
- Fallback-to-full if scoped context is insufficient
- Token savings of 2000-5000 per task

#### Agent Teams Reality
- Teammates auto-load CLAUDE.md, MCP servers, and skills
- Teammates get spawn prompt from lead (no conversation history)
- Each teammate has own context window
- "Token usage scales with number of active teammates"
- Doc warns: "use significantly more tokens than single session"

#### Tension and Resolution

Agent Teams is inherently MORE token-hungry because teammates are full interactive sessions. ZERG's context engineering is designed to MINIMIZE tokens. These seem to be in opposition.

**Resolution**: ZERG's context engineering becomes MORE valuable with Agent Teams, not less.

- Agent Teams teammates load full CLAUDE.md → ZERG's task-scoped context should be injected via the **spawn prompt** instead
- Spawn prompt is the key lever: "Review auth module at src/auth/. Here are the relevant security rules for Python files: [filtered rules]. Here's the spec excerpt for your task: [scoped content]"
- ZERG's context engineering plugin generates optimized spawn prompts
- Command splitting still applies for the lead/orchestrator session

#### Hybrid Approach

1. Lead session uses command splitting (`core.md` for orchestration)
2. Worker spawn prompts use task-scoped context (filtered rules, scoped specs)
3. Inter-worker messages carry minimal context updates (delta information)
4. Token budget monitoring via `/zerg:status` tracks per-teammate usage

**New capability**: Since teammates can MESSAGE each other, the lead could broadcast context updates: "Spec change: API endpoint renamed from /users to /accounts." This is impossible in current ZERG where workers are isolated.

---

### Dimension 5: Quality Gates & Hooks

#### Current State
- Quality gates run at level boundaries during `/zerg:merge`
- Gates include: lint, typecheck, test, build
- Configurable in `.zerg/config.yaml`
- Merge process: branch per task → merge to feature branch → run gates → proceed to next level
- If gate fails: task marked failed, can retry

#### Agent Teams Capability
- **TeammateIdle hook**: Runs when teammate is about to go idle. Exit code 2 sends feedback and keeps them working.
- **TaskCompleted hook**: Runs when task is being marked complete. Exit code 2 prevents completion with feedback.
- Hooks are shell commands configured in settings

#### Opportunity — Self-Healing Quality Gates

This is a natural integration point:

**1. TaskCompleted hook → ZERG gate runner (per-task)**

When worker marks task complete → hook runs lint/typecheck on modified files → if gate fails → exit code 2 → worker gets feedback → worker fixes → re-marks complete.

This is **self-healing**: workers fix their own gate failures instead of the orchestrator retrying. The feedback loop shrinks from:
```
OLD: level complete → merge → gate → FAIL → retry entire task (cold start, new process)
NEW: task done → gate → FAIL → worker fixes immediately (warm context, same session)
```

**2. TeammateIdle hook → work reassignment**

When worker goes idle → hook checks if there are unfinished tasks → if yes → send worker to claim next task (keep workers busy) → if no → allow idle (level complete).

**3. Custom hooks for ZERG-specific gates**:
- File ownership verification: ensure worker only modified files in its ownership set
- Spec compliance check: verify output matches spec requirements
- Integration smoke test: run integration tests for the modified subsystem

**Migration**: ZERG's current quality gate config in `.zerg/config.yaml` generates hook configurations for Agent Teams. The hook script is a thin wrapper that invokes ZERG's gate runner with the task context.

---

### Dimension 6: Plan Approval Workflow

#### Current State
- Sequential phases: `/zerg:plan` → user approves → `/zerg:design` → user approves → `/zerg:rush`
- Plan approval is at the FEATURE level (approve the whole plan)
- Design approval is at the ARCHITECTURE level (approve the task graph)
- Workers don't have individual plan approval — they just execute their assigned task
- No mid-execution plan review

#### Agent Teams Capability
- Per-teammate plan approval: "Require plan approval before they make any changes"
- Teammate works in read-only plan mode → sends plan to lead → lead approves/rejects
- Rejected plans get feedback → teammate revises → resubmits
- Lead makes approval decisions autonomously based on criteria

#### Opportunity: Multi-Level Plan Approval

**1. Task-level plan approval**: Before a worker starts writing code, it first analyzes its task and proposes an approach. The lead (orchestrator) reviews for:
- Consistency with overall architecture
- No file ownership violations
- Approach aligns with spec
- No conflicting assumptions with other workers

**2. Lead as architectural guardian**: The lead can enforce architectural rules:
- "Only approve plans that follow the existing patterns in the codebase"
- "Reject plans that add new dependencies without justification"
- "Ensure every plan includes tests"

**3. Cross-worker plan coordination**: When worker B's plan would conflict with worker A's approach, the lead detects this during approval and sends B back with feedback referencing A's approved plan.

This addresses a current ZERG weakness: workers sometimes interpret specs differently and produce incompatible implementations. Plan approval adds a lightweight consensus check.

#### Configuration

Make plan approval opt-in per complexity tier:
- `--quick`: no plan approval (simple tasks)
- `--think`: plan approval for L1 tasks only
- `--think-hard` / `--ultrathink`: plan approval for all tasks

---

### Dimension 7: Display & Observability

#### Current State
- `/zerg:status` reads TaskList + state JSON + log files
- Workers are opaque subprocesses — you see their output only after completion
- Logs stored in `.zerg/logs/`
- No real-time visibility into worker progress
- Status is polled, not pushed

#### Agent Teams Capability
- In-process mode: Shift+Up/Down to select and view teammates
- Split-pane mode: each teammate gets own tmux/iTerm2 pane
- Real-time visibility into every worker's activity
- Can interact with individual workers during execution
- Automatic idle notifications

#### Opportunity: From "Launch and Pray" to "Live Orchestra"

1. **Split-pane dashboard**: During `/zerg:rush`, each worker gets a visible pane. The user can watch workers in real-time, see what files they're editing, what tests they're running.

2. **Interactive steering**: If a worker is going off-track, the user (or lead) can message it directly: "Stop — you're modifying files outside your ownership set. Focus on src/auth/ only."

3. **Live status**: Instead of polling `/zerg:status`, the lead receives automatic notifications when workers finish tasks, encounter errors, or go idle.

4. **Worker health monitoring**: If a worker is stuck (spending too long on a task), the lead can proactively check in or reassign the work.

5. **/zerg:status upgrade**: Instead of reading static state files, `/zerg:status` could show live teammate sessions, their current task, elapsed time, and recent activity.

#### Critical Constraint

Split-pane mode requires tmux or iTerm2. ZERG currently works in any terminal. Need graceful degradation:
- tmux/iTerm2 available → split-pane mode
- Neither available → in-process mode (still interactive, just tabbed)
- `--headless` flag → current subprocess mode (CI/CD compatibility)

**ZERG must not LOSE the headless/CI mode.** Agent Teams is designed for interactive use. ZERG must support BOTH modes.

---

### Dimension 8: New Command Opportunities

With Agent Teams, ZERG could introduce or transform several commands:

#### /zerg:debate (NEW)
- Spawn adversarial teammates to debate a design decision
- Each teammate advocates for a different approach
- Lead synthesizes findings into a recommendation
- Use case: "Should we use REST or GraphQL for this API?"
- Maps directly to Agent Teams' "competing hypotheses" pattern

#### /zerg:pair (NEW)
- Two-agent pair programming
- One writes code, other reviews in real-time
- Continuous feedback loop
- Low overhead, high quality

#### /zerg:review (ENHANCED)
- Currently: single-pass review
- With teams: spawn specialized reviewers (security, perf, tests, architecture)
- Reviewers challenge each other's findings
- Lead produces comprehensive review report
- Maps to Agent Teams' "parallel code review" use case

#### /zerg:debug (ENHANCED)
- Currently: single-threaded investigation
- With teams: spawn investigators with different hypotheses
- Investigators share evidence and disprove each other
- Faster convergence on root cause
- Maps to Agent Teams' "competing hypotheses" use case

#### /zerg:brainstorm (ENHANCED)
- Currently: single-session brainstorming
- With teams: multiple perspectives exploring simultaneously
- UX researcher + technical architect + devil's advocate pattern
- Richer exploration of problem space

#### /zerg:rush (TRANSFORMED)
- Currently: subprocess launcher with opaque workers
- With teams: interactive teammates with live visibility
- Plan approval before implementation
- Self-healing quality gates via hooks
- DAG-based execution instead of rigid levels

---

### Dimension 9: Migration Strategy & Architecture

Given everything above, the right approach is a **layered migration**, not a rip-and-replace.

#### Phase 1: Adapter Layer (Low risk, high value)
- Add `AgentTeamLauncher` alongside existing `SubprocessLauncher` and `ContainerLauncher`
- `--mode` flag gets new option: `--mode team` (alongside `subprocess` and `container`)
- `AgentTeamLauncher` translates ZERG's task-graph into Agent Teams task list
- Spawn prompt generated from task-scoped context (reuse context engineering)
- Existing commands work unchanged — just a new execution backend

#### Phase 2: Hook Integration (Medium risk, high value)
- Implement `TaskCompleted` hook for per-task quality gates
- Implement `TeammateIdle` hook for work reassignment
- Configure hooks in `.zerg/config.yaml`
- Hook scripts wrap ZERG's existing gate runner
- Self-healing: workers fix their own gate failures

#### Phase 3: Plan Approval (Medium risk, high value)
- Enable Agent Teams plan approval for workers
- Lead reviews plans against design spec, file ownership, cross-task consistency
- Configurable by depth tier
- Rejection feedback includes specific violations

#### Phase 4: DAG Execution (Medium risk, very high value)
- Move from level-based barriers to fine-grained dependency DAG
- task-graph.json already has dependency info — use it directly
- Agent Teams handles unblocking automatically
- Keep levels as planning concept, use deps for execution
- Merge/quality gates run at configurable checkpoints

#### Phase 5: Communication & New Commands (High complexity, transformative)
- Enable worker-to-worker messaging for coordination
- New commands: `/zerg:debate`, `/zerg:pair`
- Enhanced: `/zerg:review`, `/zerg:debug`
- Communication budget tracking
- Spawn prompt optimization
- Live dashboard
- Delegate mode

#### Key Architectural Decisions

1. Keep `launcher.py` as an abstraction layer with multiple backends
2. `AgentTeamLauncher` implements the same interface as other launchers
3. ZERG's Task system maps 1:1 to Agent Teams' shared task list
4. Context engineering generates spawn prompts instead of spec files
5. Headless/CI mode preserved via subprocess backend
6. Agent Teams mode is opt-in, not default (until stable)

#### File Changes Summary

| Phase | New Files | Modified Files |
|-------|-----------|----------------|
| 1 | `zerg/launchers/agent_team_launcher.py` | `launcher_types.py`, `launcher_configurator.py`, `cli.py`, `orchestrator.py`, `context_plugin.py` |
| 2 | Hook scripts in `.claude/hooks/`, `zerg/hooks/` | `gates.py`, `level_coordinator.py`, `worker_manager.py`, `state/manager.py` |
| 3 | — | `context_plugin.py`, `capability_resolver.py`, `rush.core.md` |
| 4 | `zerg/dag_executor.py` (or rearchitect `level_coordinator.py`) | `merge.py`, `task_sync.py`, `orchestrator.py`, `config.py` |
| 5 | `zerg/messaging.py`, `debate.md`, `pair.md` | `context_plugin.py`, `capability_resolver.py`, `spec_loader.py`, `status.core.md`, `review.md`, `debug.core.md` |

---

### Dimension 10: Risks, Limitations & Mitigations

#### Risk Matrix

| Risk | Severity | Probability | Mitigation |
|------|----------|-------------|------------|
| Agent Teams experimental, API may change | High | Medium | `AgentTeamLauncher` behind stable ABC. Changes isolated to one file. Subprocess/container unchanged |
| Token cost explosion | High | High | ZERG's context engineering as efficiency layer. Task-scoped prompts (4000 tokens). Communication budgets |
| No session resumption | Medium | Certain | ZERG's spec-as-memory works. Crash recovery respawns from task state. NEW teammates for incomplete tasks |
| One team per session | Low | Certain | ZERG already sequential. Natural alignment |
| No nested teams | Low | Certain | Workers are leaf nodes — no sub-teams needed |
| Lead is fixed | Low | Certain | ZERG's orchestrator IS the lead. Natural alignment |
| Permissions inherit from lead | Medium | Certain | ZERG assumes `--dangerously-skip-permissions`. File ownership enforced by convention + gates |
| Split-pane not everywhere | Low | Certain | In-process mode works in any terminal. Split-pane is bonus |
| Merge complexity with DAG | High | Medium | Phase 4 is last. Start with level barriers in team mode (Phases 1-3), evolve |
| Programmatic control unknown | High | Unknown | **Must investigate before Phase 1**: can Python spawn teammates? |

#### Critical Limitation to Address

Agent Teams teammates load CLAUDE.md automatically. ZERG's CLAUDE.md is large and contains security rules, command documentation, etc. This is GOOD (teammates get all project context) but means higher baseline token usage per teammate.

#### Key Alignment Discovery

Re-reading the Agent Teams doc: "Shared task list: all agents can see task status and claim available work" stored at `~/.claude/tasks/{team-name}/` — this IS the Claude Code Task system. Agent Teams USES `TaskCreate`/`TaskUpdate`/`TaskList`/`TaskGet`. This is PERFECT alignment with ZERG's existing Task ecosystem requirement. ZERG already mandates Claude Code Tasks as source of truth. Agent Teams uses the same system. They're built for each other.

---

### Dimension 11: Synthesis — The Big Picture

ZERG was built before Agent Teams existed. It reimplemented many primitives. But ZERG also has capabilities Agent Teams DOESN'T:

| ZERG-Only Capability | Why It Matters |
|----------------------|----------------|
| Task graph generation from specs | Agent Teams gives you teammates. ZERG tells you WHAT tasks to give them |
| Context engineering for token efficiency | Agent Teams loads full context. ZERG injects task-scoped context |
| File ownership model | Agent Teams lets teammates do anything. ZERG enforces file boundaries |
| Level-based execution with merge gates | Agent Teams has no merge concept. ZERG manages branch integration |
| Container execution mode | Agent Teams is interactive only. ZERG works in Docker |
| Cross-cutting capabilities (TDD, security, loops) | Agent Teams has no concept of behavioral modes |
| Crash-safe resume | Agent Teams can't resume teammates. ZERG respawns from state |
| CLI interface for non-interactive use | Agent Teams requires interactive terminal |

#### ZERG's Unique Value WITH Agent Teams

1. **Intelligent task decomposition**: Agent Teams gives you teammates. ZERG tells you WHAT tasks to give them and in what order.
2. **Optimized context**: Agent Teams loads full context. ZERG injects task-scoped context for efficiency.
3. **Architectural guardrails**: Agent Teams lets teammates do anything. ZERG enforces file ownership, quality gates, spec compliance.
4. **Workflow orchestration**: Agent Teams coordinates one team. ZERG orchestrates plan → design → execute → merge → verify.
5. **Multi-mode execution**: Agent Teams = interactive only. ZERG = interactive, headless, container, CI/CD.

#### Summary of All Improvements

| # | Improvement | Phase | Impact | Complexity |
|---|-------------|-------|--------|------------|
| 1 | AgentTeamLauncher (--mode team) | 1 | Foundation | Medium |
| 2 | TaskCompleted hook (self-healing gates) | 2 | Very High | Medium |
| 3 | TeammateIdle hook (work redistribution) | 2 | High | Low-Medium |
| 4 | Plan approval (architectural consistency) | 3 | High | Medium |
| 5 | DAG execution (break level barriers) | 4 | Very High | High |
| 6 | Inter-agent communication | 5 | Transformative | High |
| 7 | /zerg:debate (adversarial design) | 5 | Medium | Medium |
| 8 | /zerg:pair (pair programming) | 5 | Medium | Medium |
| 9 | Enhanced /zerg:review (reviewer panels) | 5 | High | Medium |
| 10 | Enhanced /zerg:debug (competing hypotheses) | 5 | High | Medium |
| 11 | Spawn prompt optimization | 5 | High | Medium |
| 12 | Live observability dashboard | 5 | Medium | Low |
| 13 | Delegate mode for lead | 5 | Low | Low |

This positions ZERG as the premier orchestration framework for Claude Code, with Agent Teams as a native execution backend alongside subprocess and container modes.

---

## Implementation Plan

### Phased Roadmap

```
Phase 1: AgentTeamLauncher ─────────────────── --mode team works
    │
Phase 2: Hook Integration ─────────────────── self-healing gates + work redistribution
    │        ├── TaskCompleted hook
    │        └── TeammateIdle hook
    │
Phase 3: Plan Approval ────────────────────── architectural guardrails
    │
Phase 4: DAG Execution ────────────────────── break level barriers (20-40% throughput gain)
    │
Phase 5: Communication + New Commands ─────── debate, pair, enhanced review/debug
             ├── Inter-agent communication
             ├── New commands (debate, pair)
             ├── Enhanced commands (review, debug)
             ├── Spawn prompt optimization
             ├── Live dashboard
             └── Delegate mode
```

Each phase is independently valuable. Phase 1 is prerequisite for all others. Phases 2-3 work with existing level system. Phase 4 is the largest architectural change. Phase 5 requires inter-agent messaging.

**Critical constraint**: `--mode subprocess` and `--mode container` remain unchanged throughout. Agent Teams mode is opt-in, never default.

---

## GitHub Issues

All issues created with full specifications, cross-references, and phase labels:

| Issue | Title | Phase | Labels |
|-------|-------|-------|--------|
| #167 | AgentTeamLauncher — new execution backend | Phase 1 | `phase:1-foundation` |
| #168 | TaskCompleted hook — per-task quality gates | Phase 2 | `phase:2-hooks` |
| #169 | TeammateIdle hook — automatic work redistribution | Phase 2 | `phase:2-hooks` |
| #170 | Plan approval — architectural consistency | Phase 3 | `phase:3-guardrails` |
| #171 | Fine-grained DAG execution | Phase 4 | `phase:4-throughput` |
| #172 | Inter-agent communication channels | Phase 5 | `phase:5-communication` |
| #173 | New commands (debate, pair, enhanced review & debug) | Phase 5 | `phase:5-communication` |
| #174 | Spawn prompt optimization | Phase 5 | `phase:5-communication` |
| #175 | Live observability dashboard | Phase 5 | `phase:5-communication` |
| #176 | Delegate mode for orchestrator lead | Phase 5 | `phase:5-communication` |
| #177 | Epic: Agent Teams integration (tracking issue) | All | `agent-teams` |

### Dependency Graph

```
#167 AgentTeamLauncher (FOUNDATION — everything depends on this)
 ├──→ #168 TaskCompleted Hook
 │     └──→ #171 DAG Execution
 ├──→ #169 TeammateIdle Hook
 ├──→ #170 Plan Approval
 ├──→ #172 Inter-Agent Communication
 │     └──→ #173 New Commands
 ├──→ #174 Spawn Prompt Optimization
 ├──→ #175 Live Dashboard
 └──→ #176 Delegate Mode
```

---

## Unresolved Questions

These must be answered before implementation begins:

### Critical (Block Phase 1)

1. **Programmatic spawning**: Can ZERG's Python orchestrator programmatically spawn Agent Teams teammates? Or must the lead session do this via natural language prompts? This determines whether `AgentTeamLauncher` can implement the full `WorkerLauncher` interface.

2. **Task list ID scoping**: Agent Teams uses `~/.claude/tasks/{team-name}/`. ZERG uses `CLAUDE_CODE_TASK_LIST_ID`. How do these interact? Can ZERG control which task list the team uses?

### Important (Block Phase 2)

3. **Hook execution environment**: Where do `TaskCompleted`/`TeammateIdle` hooks run? In the lead's process? As separate scripts? Can they access `.zerg/state/` and invoke `GateRunner`?

4. **Hook metadata format**: What metadata do hooks receive? Task ID? Subject? Modified files? This determines what the hook script can do.

### Valuable (Block Phase 2-3)

5. **Teammate context persistence**: When a teammate picks up a new task via `TeammateIdle` hook, does it retain context from the previous task? If yes → major advantage over subprocess respawning.

6. **Delegate mode activation**: Can delegate mode be enabled programmatically, or only via user interaction (Shift+Tab)?

### Strategic (Block Phase 4-5)

7. **Quality gate timing with DAG**: When levels are abolished, when should merge gates run? Per-task? Per-cluster? Configurable checkpoints?

8. **Branch strategy in team mode**: Must `--mode team` use branch-per-task? Or can teammates share a branch since they can coordinate?

9. **Agent Teams API stability timeline**: When does experimental graduate to stable? What breaking changes expected?

10. **Token measurement across teammates**: Agent Teams has no built-in cross-teammate token tracking. How does ZERG's `TokenTracker` extend?
