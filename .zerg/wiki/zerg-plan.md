# /zerg:plan

Capture complete requirements for a feature through interactive discovery.

## Synopsis

```
/zerg:plan <feature-name> [OPTIONS]
```

## Description

`/zerg:plan` starts an interactive requirements gathering session for the named feature. It creates a spec directory at `.gsd/specs/<feature>/`, explores the existing codebase for context, asks clarifying questions, and produces a `requirements.md` document for user approval.

The command follows a five-phase workflow:

1. **Context Gathering** -- Reads `PROJECT.md`, `INFRASTRUCTURE.md`, and explores the codebase to understand existing patterns and technology stack.

2. **Requirements Elicitation** -- Asks grouped clarifying questions covering problem space, functional requirements, non-functional requirements, scope boundaries, dependencies, and acceptance criteria.

3. **Generate requirements.md** -- Writes a comprehensive requirements document to `.gsd/specs/<feature>/requirements.md`.

4. **Infrastructure Requirements** -- Identifies any additional infrastructure needs (services, environment variables, MCP servers) and updates `.gsd/INFRASTRUCTURE.md` if needed.

5. **User Approval** -- Presents the requirements for review. The user responds with `APPROVED`, `REJECTED`, or specific change requests.

The feature name is sanitized to lowercase with hyphens only (`a-z`, `0-9`, `-`).

### Socratic Mode

With `--socratic`, the command uses a structured multi-round discovery process instead of a single question pass. Each round builds on the previous answers to deepen understanding.

### Status Markers

The requirements document progresses through these states:

| Status | Meaning |
|--------|---------|
| DRAFT | Still gathering requirements |
| REVIEW | Requirements complete, awaiting user approval |
| APPROVED | User approved, ready for design |
| REJECTED | Requirements need revision |

## Options

| Option | Description |
|--------|-------------|
| `<feature-name>` | **Required.** Name of the feature to plan |
| `-s`, `--socratic` | Use structured multi-round discovery mode |
| `--rounds N` | Number of discovery rounds in Socratic mode (default: 3, max: 5) |

## Examples

```bash
# Plan a feature
/zerg:plan user-auth

# Plan with Socratic discovery
/zerg:plan user-auth --socratic

# Socratic mode with 5 rounds
/zerg:plan payment-api --socratic --rounds 5
```

## Output

On completion, the following files are created:

```
.gsd/
  .current-feature          # Set to the feature name
  specs/<feature>/
    requirements.md         # The requirements document
    .started                # Timestamp of when planning began
```

## Completion Criteria

- `requirements.md` exists with `Status: APPROVED`
- All open questions are resolved or accepted
- User has explicitly replied with "APPROVED"
- Infrastructure needs are identified and documented

## See Also

- [[zerg-init]] -- Must be run before planning
- [[zerg-design]] -- Next step after requirements are approved
- [[zerg-Reference]] -- Full command index
