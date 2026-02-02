# /zerg:brainstorm

Open-ended feature discovery through competitive research, Socratic questioning, and automated GitHub issue creation.

## Synopsis

```
/zerg:brainstorm [domain-or-topic] [OPTIONS]
```

## Description

`/zerg:brainstorm` starts an interactive discovery session for exploring feature ideas. It optionally researches the competitive landscape via web search, conducts structured Socratic questioning to refine ideas, and creates prioritized GitHub issues from the results.

The command follows a multi-phase workflow:

1. **Research** -- Uses WebSearch to analyze competitors, market gaps, and user pain points (3-5 queries). Findings are cached in the session directory.

2. **Socratic Discovery** -- Conducts structured questions using AskUserQuestion. Operates in two modes:
   - **Batch mode** (default): Multiple questions per round, 3 rounds by default (override with `--rounds N`).
   - **Socratic mode** (`--socratic`): Single-question interactive mode with 6 domain-specific question trees (Auth, API, Data Pipeline, UI/Frontend, Infrastructure, General). Domain is auto-detected from topic keywords.

   Saturation detection automatically stops questioning when 2 consecutive answers introduce no new entities (concepts, constraints, or requirements). Minimum 3 questions before checking.

2.5. **Trade-off Exploration** -- Surfaces competing concerns (e.g., consistency vs. availability, simplicity vs. extensibility) and asks the user to rank or choose between them. Results are captured in `tradeoffs.md`.

2.6. **Design Validation** -- Replays the discovered requirements back to the user as a structured summary for confirmation. Produces `validated-design.md` with user-approved scope.

2.7. **YAGNI Gate** -- Reviews all captured ideas against the validated scope. Features that were discussed but not validated are moved to `deferred.md` with rationale, preventing scope creep before planning begins.

3. **Issue Generation** -- For each identified feature, creates a GitHub issue via `gh issue create` with title, problem statement, acceptance criteria, priority label, and competitive context.

4. **Handoff** -- Presents ranked recommendations, saves session artifacts, and suggests `/z:plan` for the top-priority feature.

The domain argument is optional. If omitted, brainstorming begins with open-ended discovery.

### Domain Question Trees

The Socratic Discovery phase uses domain-specific question trees to guide structured exploration. Six domains are supported:

| Domain | Focus Areas |
|--------|-------------|
| **Auth & Authorization** | Identity providers, role models, token strategy, session management, permission granularity, audit requirements |
| **API Design** | Resource modeling, versioning strategy, pagination, rate limiting, error contract, idempotency |
| **Data Pipeline** | Source systems, volume/velocity, transformation logic, delivery guarantees, schema evolution, monitoring |
| **UI/Frontend** | User personas, interaction patterns, responsive requirements, accessibility, state management, offline support |
| **Infrastructure** | Deployment targets, scaling strategy, observability, disaster recovery, cost constraints, compliance |
| **General** | Problem definition, user impact, success metrics, constraints, integration points, timeline |

The domain is auto-detected from the topic argument or can be influenced by the questions the user answers. When no domain matches, the **General** tree is used.

### Context Management

The command uses ZERG's context engineering system:

- **Command splitting** -- `.core.md` (~30%) and `.details.md` (~70%) for token efficiency.
- **Scoped loading** -- Loads `PROJECT.md` for research context; codebase structure only when needed.
- **Session resumability** -- State saved after each phase; `--resume` continues from last checkpoint.
- **Question batching** -- Groups 3-4 questions per AskUserQuestion call to reduce round-trips.

## Options

| Option | Description |
|--------|-------------|
| `[domain-or-topic]` | Optional. Domain or topic to brainstorm about |
| `--rounds N` | Number of Socratic discovery rounds (default: 3, max: 5) |
| `--socratic` | Enable single-question Socratic mode with domain question trees (default: off, uses batch mode) |
| `--skip-research` | Skip the web research phase |
| `--skip-issues` | Ideate only, don't create GitHub issues |
| `--dry-run` | Preview issues without creating them |
| `--resume` | Resume a previous brainstorm session from checkpoint |

## Examples

```bash
# Brainstorm features for a mobile app
/zerg:brainstorm mobile-app-features

# Skip research, just do Socratic ideation
/zerg:brainstorm --skip-research

# Extended discovery with 5 rounds, preview only
/zerg:brainstorm api-improvements --rounds 5 --dry-run

# Use Socratic mode with domain-aware question trees
/zerg:brainstorm authentication --socratic

# Combine socratic mode with dry-run for pure discovery
/zerg:brainstorm infrastructure --socratic --skip-issues
```

## Output

On completion, the following files are created:

```
.gsd/specs/brainstorm-{timestamp}/
  research.md         # Competitive analysis findings (unless --skip-research)
  brainstorm.md       # Session summary with all Q&A and recommendations
  validated-design.md # User-confirmed scope and requirements from Design Validation
  tradeoffs.md        # Trade-off decisions and rankings from exploration phase
  deferred.md         # Ideas deferred by YAGNI Gate with rationale
  issues.json         # Machine-readable manifest of created issues
```

## Completion Criteria

- Research findings saved (unless `--skip-research`)
- All Socratic rounds completed (or saturation detected: 2 consecutive answers with no new entities)
- Trade-off exploration surfaced and ranked competing concerns
- Design validation confirmed by user (`validated-design.md` produced)
- YAGNI Gate applied; deferred items captured in `deferred.md`
- `tradeoffs.md` saved with ranked trade-off decisions
- GitHub issues created (unless `--skip-issues` or `--dry-run`)
- Session artifacts saved to `.gsd/specs/brainstorm-{timestamp}/`

## See Also

- [[Command-plan]] -- Next step: capture detailed requirements for a specific feature
- [[Command-design]] -- After planning, generate architecture and task graph
- [[Command-Reference]] -- Full command index
