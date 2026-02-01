# ZERG Git (Core)

Git operations with intelligent commits, PR creation, releases, rescue, review, and bisect.

## Usage

```bash
/zerg:git --action commit|branch|merge|sync|history|finish|pr|release|review|rescue|bisect|ship
          [options...]
```

## Actions

| Action | Description | Key Flags |
|--------|------------|-----------|
| commit | Smart commit with conventional messages | --push, --mode |
| branch | Branch management | --name |
| merge | Merge with conflict detection | --branch, --strategy |
| sync | Sync with remote | --base |
| history | Commit history / cleanup | --since, --cleanup |
| finish | Complete feature branch | --base, --push |
| pr | Create PR with full context | --draft, --reviewer |
| release | Semver release workflow | --bump, --dry-run |
| review | Pre-review context assembly | --focus |
| rescue | Undo/recovery operations | --list-ops, --undo, --restore, --recover-branch |
| bisect | AI-powered bug bisection | --symptom, --test-cmd, --good |
| ship | Commit, push, PR, merge, cleanup in one shot | --base, --draft, --reviewer, --no-merge |

## Flags Reference

```
--action, -a ACTION    Git action to perform (default: commit)
--push, -p             Push after commit/finish
--base, -b BRANCH      Base branch (default: main)
--name, -n NAME        Branch name (for branch action)
--branch BRANCH        Branch to merge (for merge action)
--strategy STRATEGY    merge|squash|rebase (default: squash)
--since TAG            Starting point for history
--mode MODE            auto|confirm|suggest (commit mode override)
--cleanup              Run history cleanup
--draft                Create draft PR
--reviewer USER        PR reviewer username
--focus DOMAIN         security|performance|quality|architecture
--bump TYPE            auto|major|minor|patch (default: auto)
--dry-run              Preview release without executing
--symptom TEXT         Bug symptom description (for bisect)
--test-cmd CMD         Test command for bisect
--good REF             Known good commit/tag (for bisect)
--list-ops             List rescue operations
--undo                 Undo last operation (rescue)
--restore TAG          Restore snapshot tag (rescue)
--recover-branch NAME  Recover deleted branch (rescue)
--no-merge             Stop after PR creation (skip merge+cleanup)
```

## Task Tracking

On invocation, create a Claude Code Task to track this command:

Call TaskCreate:
  - subject: "[Git] {action} operation"
  - description: "Git {action} operation."
  - activeForm: "Running git {action}"

Immediately call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "in_progress"

On completion, call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "completed"

## Exit Codes

- 0: Success
- 1: Failure
