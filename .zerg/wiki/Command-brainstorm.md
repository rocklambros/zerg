# /zerg:brainstorm

Open-ended feature discovery through competitive research, Socratic questioning, and automated GitHub issue creation.

## Synopsis

```
/zerg:brainstorm [domain-or-topic] [OPTIONS]
```

## Description

`/zerg:brainstorm` starts an interactive discovery session for exploring feature ideas. It optionally researches the competitive landscape via web search, conducts structured Socratic questioning to refine ideas, and creates prioritized GitHub issues from the results.

The command follows a four-phase workflow:

1. **Research** -- Uses WebSearch to analyze competitors, market gaps, and user pain points (3-5 queries). Findings are cached in the session directory.

2. **Socratic Discovery** -- Conducts multiple rounds of structured questions using AskUserQuestion. Each round builds on previous answers: problem space, solution ideation, then prioritization.

3. **Issue Generation** -- For each identified feature, creates a GitHub issue via `gh issue create` with title, problem statement, acceptance criteria, priority label, and competitive context.

4. **Handoff** -- Presents ranked recommendations, saves session artifacts, and suggests `/z:plan` for the top-priority feature.

The domain argument is optional. If omitted, brainstorming begins with open-ended discovery.

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
```

## Output

On completion, the following files are created:

```
.gsd/specs/brainstorm-{timestamp}/
  research.md     # Competitive analysis findings (unless --skip-research)
  brainstorm.md   # Session summary with all Q&A and recommendations
  issues.json     # Machine-readable manifest of created issues
```

## Completion Criteria

- Research findings saved (unless `--skip-research`)
- All Socratic rounds completed
- GitHub issues created (unless `--skip-issues` or `--dry-run`)
- Session artifacts saved to `.gsd/specs/brainstorm-{timestamp}/`

## See Also

- [[Command-plan]] -- Next step: capture detailed requirements for a specific feature
- [[Command-design]] -- After planning, generate architecture and task graph
- [[Command-Reference]] -- Full command index
