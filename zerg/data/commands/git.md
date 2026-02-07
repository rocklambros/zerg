# ZERG Git

Git operations with intelligent commits, PR creation, releases, rescue, review, and bisect.

## Usage

```bash
/zerg:git --action commit|branch|merge|sync|history|finish|pr|release|review|rescue|bisect|ship|cleanup|issue
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
| ship | Commit, push, PR, merge, cleanup in one shot | --base, --draft, --reviewer, --no-merge, --admin |
| cleanup | Repository hygiene: prune branches, refs, worktrees, Docker | --dry-run, --no-docker, --include-stashes |
| issue | Create AI-optimized GitHub issues from scan or description | --scan, --title, --dry-run, --limit, --label, --priority |

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
--admin                Use admin merge directly (repo owner/admin, for ship)
--scan                 Auto-detect issues from codebase analysis (default for issue action)
--title TEXT           Issue title (for issue action, switches to description mode)
--no-docker            Skip Docker container/image cleanup (for cleanup action)
--include-stashes      Also clear git stashes (for cleanup action, off by default)
--limit N              Max issues to create (default: 10, for issue action)
--label LABEL          Add label to created issues (for issue action)
--priority P           Filter by priority: P0|P1|P2 (for issue action)
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

## Help

When `--help` is passed in `$ARGUMENTS`, display usage and exit:

```
/zerg:git -- Git operations with intelligent commits, PR creation, releases, and more.

Flags:
  --action commit|branch|merge|sync|history|finish|pr|release|review|rescue|bisect|ship|cleanup|issue
                    Git action to perform (required)
  --push            Push after operation
  --base main       Base branch (default: main)
  --name NAME       Branch name (for branch action)
  --branch BRANCH   Branch to merge (for merge action)
  --strategy STRATEGY
                    Merge strategy (for merge action)
  --since TAG       Starting point (for history action)
  --mode MODE       auto|confirm|suggest (commit mode)
  --cleanup         Run history cleanup
  --draft           Create draft PR
  --reviewer USER   PR reviewer username
  --focus DOMAIN    security|performance|quality|architecture
  --bump TYPE       auto|major|minor|patch (default: auto)
  --dry-run         Preview without executing (release, cleanup, issue)
  --symptom TEXT    Bug symptom (for bisect)
  --test-cmd CMD    Test command (for bisect)
  --good REF        Known good ref (for bisect)
  --list-ops        List rescue operations
  --undo            Undo last operation (rescue)
  --restore TAG     Restore snapshot (rescue)
  --recover-branch NAME
                    Recover branch (rescue)
  --no-merge        Stop after PR creation (skip merge+cleanup)
  --admin           Use admin merge directly (repo owner/admin, for ship)
  --scan            Auto-detect issues from codebase (issue action)
  --title TEXT      Issue title (issue action, description mode)
  --no-docker       Skip Docker cleanup (cleanup action)
  --include-stashes Clear git stashes (cleanup action)
  --limit N         Max issues to create (issue action, default: 10)
  --label LABEL     Add label to issues (issue action)
  --priority P      Filter by priority: P0|P1|P2 (issue action)
  --help            Show this help message
```
