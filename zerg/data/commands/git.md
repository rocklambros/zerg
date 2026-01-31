# ZERG Git

Git operations with intelligent commits and finish workflow.

## Usage

```bash
/zerg:git --action commit|branch|merge|sync|history|finish
          [--push]
          [--base main]
```

## Actions

### commit
Intelligent commit with auto-generated conventional message:
```bash
/zerg:git --action commit [--push]
```

### branch
Branch management:
```bash
/zerg:git --action branch --name feature/auth
```

### merge
Intelligent merge with conflict detection:
```bash
/zerg:git --action merge --branch feature/auth --strategy squash
```

### sync
Synchronize with remote:
```bash
/zerg:git --action sync
```

### history
Analyze and generate changelog:
```bash
/zerg:git --action history --since v1.0.0
```

### finish (CRITICAL)
Complete development branch with structured options:

```bash
/zerg:git --action finish [--base main]
```

**Finish Workflow:**
```
Implementation complete. All tests passing. What would you like to do?

1. Merge back to main locally
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)
4. Discard this work

Which option?
```

## Conventional Commits

Auto-generated commit types:
- `feat`: New features
- `fix`: Bug fixes
- `docs`: Documentation
- `style`: Formatting
- `refactor`: Code restructuring
- `test`: Tests
- `chore`: Maintenance

## Task Tracking

On invocation, create a Claude Code Task to track this command:

Call TaskCreate:
  - subject: "[Git] {action} operation"
  - description: "Git {action} operation. Push: {push}. Base: {base}."
  - activeForm: "Running git {action}"

Immediately call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "in_progress"

On completion, call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "completed"

## Exit Codes

- 0: Operation successful
- 1: Operation failed
- 2: Tests must pass (for finish)

## Help

When `--help` is passed in `$ARGUMENTS`, display usage and exit:

```
/zerg:git — Git operations with intelligent commits and finish workflow.

Flags:
  --action commit|branch|merge|sync|history|finish
                    Git action to perform (required)
  --push            Push after operation
  --base main       Base branch for finish/merge (default: main)
  --name NAME       Branch name (for branch action)
  --branch BRANCH   Branch to merge (for merge action)
  --strategy STRATEGY
                    Merge strategy (for merge action)
  --since TAG       Starting point (for history action)
  --help            Show this help message
```
