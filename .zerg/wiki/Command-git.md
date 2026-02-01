# /zerg:git

Git operations with intelligent commits, PR creation, releases, rescue, review, bisect, and ship.

## Synopsis

```
/zerg:git --action commit|branch|merge|sync|history|finish|pr|release|review|rescue|bisect|ship
          [--push]
          [--base main]
          [--mode auto|confirm|suggest]
          [--draft] [--reviewer USER]
          [--bump auto|major|minor|patch] [--dry-run]
          [--focus security|performance|quality|architecture]
          [--symptom TEXT] [--test-cmd CMD] [--good REF]
          [--list-ops] [--undo] [--restore TAG] [--recover-branch NAME]
          [--no-merge]
```

## Description

The `git` command wraps common Git operations with ZERG-aware intelligence. It auto-generates conventional commit messages from staged changes, manages branches, performs merges with conflict detection, provides a structured finish workflow, creates pull requests with full context assembly, automates semver releases, assembles pre-review context filtered by security rules, offers triple-layer undo/recovery, and runs AI-powered bug bisection.

### Actions

**commit** -- Stage and commit changes with an auto-generated conventional commit message. Supports multiple modes for different workflows. Optionally push to the remote.

```
/zerg:git --action commit [--push] [--mode auto|confirm|suggest]
```

**branch** -- Create and switch to a new branch, or list existing branches.

```
/zerg:git --action branch --name feature/auth [--base main]
```

**merge** -- Merge a branch with intelligent conflict detection and configurable strategy.

```
/zerg:git --action merge --branch feature/auth --strategy squash
```

**sync** -- Synchronize the local branch with its remote tracking branch. Fetches, pulls with rebase, and optionally rebases onto the base branch.

```
/zerg:git --action sync [--base main]
```

**history** -- Analyze commit history and generate a changelog from a given starting point. Optionally run history cleanup.

```
/zerg:git --action history --since v1.0.0 [--cleanup] [--base main]
```

**finish** -- Complete a development branch with a structured set of options. This action presents an interactive menu:

```
Implementation complete. All tests passing. What would you like to do?

1. Merge back to main locally
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)
4. Discard this work

Which option?
```

**pr** -- Create a pull request with full context assembly. The PREngine gathers commits, linked issues, and project spec files to generate a structured PR title, body, labels, and reviewers. Supports draft PRs and reviewer assignment.

```
/zerg:git --action pr --base main [--draft] [--reviewer octocat]
```

**release** -- Automated semver release workflow. Calculates the version bump from conventional commits (or accepts a manual override), generates a changelog entry, updates version files, commits, tags, pushes, and creates a GitHub release. Use `--dry-run` to preview without executing.

```
/zerg:git --action release [--bump auto|major|minor|patch] [--dry-run]
```

**review** -- Assemble pre-review context for Claude Code AI analysis. Prepares scoped diffs filtered by security rules per file extension and highlights areas matching the chosen focus domain.

```
/zerg:git --action review --base main [--focus security|performance|quality|architecture]
```

**rescue** -- Triple-layer undo/recovery system. List recent git operations, undo the last change, restore repository state from snapshot tags, or recover deleted branches from the reflog.

```
/zerg:git --action rescue --list-ops
/zerg:git --action rescue --undo
/zerg:git --action rescue --restore zerg-snapshot-20260201
/zerg:git --action rescue --recover-branch feature/auth
```

**bisect** -- AI-powered bug bisection. Ranks commits by likelihood using file overlap and semantic analysis, then runs `git bisect` with test validation to pinpoint the commit that introduced a bug.

```
/zerg:git --action bisect --symptom "login returns 500" --test-cmd "pytest tests/auth/" [--good v1.2.0]
```

**ship** -- Full delivery pipeline: commit, push, create PR, merge, and cleanup in one shot. Non-interactive. Uses auto mode for commit generation. Tries regular merge first, falls back to admin merge if blocked by branch protection.

```
/zerg:git --action ship [--base main] [--draft] [--reviewer USER] [--no-merge]
```

### Conventional Commit Types

Auto-generated commit messages follow the conventional commits specification:

| Type | Description |
|------|-------------|
| `feat` | New features |
| `fix` | Bug fixes |
| `docs` | Documentation changes |
| `style` | Formatting (no logic changes) |
| `refactor` | Code restructuring |
| `test` | Test additions or modifications |
| `chore` | Maintenance tasks |

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--action`, `-a` | (required) | Git operation to perform. Accepts `commit`, `branch`, `merge`, `sync`, `history`, `finish`, `pr`, `release`, `review`, `rescue`, `bisect`, or `ship`. |
| `--push`, `-p` | off | Push to remote after committing, merging, or finishing. |
| `--base`, `-b` | `main` | Base branch for finish, sync, pr, review, and history workflows. |
| `--name`, `-n` | -- | Branch name for the `branch` action. |
| `--branch` | -- | Source branch for the `merge` action. |
| `--strategy` | `squash` | Merge strategy: `merge`, `squash`, or `rebase`. |
| `--since` | -- | Starting tag or commit for the `history` action. |
| `--mode` | -- | Commit mode override: `auto`, `confirm`, or `suggest`. |
| `--cleanup` | off | Run history cleanup (for `history` action). |
| `--draft` | off | Create a draft pull request (for `pr` action). |
| `--reviewer` | -- | GitHub username to assign as PR reviewer (for `pr` action). |
| `--focus` | -- | Focus domain for the `review` action: `security`, `performance`, `quality`, or `architecture`. |
| `--bump` | `auto` | Version bump type for `release`: `auto`, `major`, `minor`, or `patch`. |
| `--dry-run` | off | Preview the release without executing (for `release` action). |
| `--symptom` | -- | Bug symptom description (for `bisect` action). |
| `--test-cmd` | -- | Test command to validate each bisect step (for `bisect` action). |
| `--good` | -- | Known good commit or tag (for `bisect` action). |
| `--list-ops` | off | List recent git operations with timestamps (for `rescue` action). |
| `--undo` | off | Undo the last recorded operation (for `rescue` action). |
| `--restore` | -- | Restore repository state from a snapshot tag (for `rescue` action). |
| `--recover-branch` | -- | Recover a deleted branch from the reflog (for `rescue` action). |
| `--no-merge` | off | Stop after PR creation, skip merge and cleanup (for `ship` action). |

## Examples

Commit staged changes with an auto-generated message:

```
/zerg:git --action commit
```

Commit and push in one step:

```
/zerg:git --action commit --push
```

Auto-commit without confirmation:

```
/zerg:git --action commit --mode auto --push
```

Preview a suggested commit message without committing:

```
/zerg:git --action commit --mode suggest
```

Create a new feature branch:

```
/zerg:git --action branch --name feature/auth
```

Squash merge a feature branch:

```
/zerg:git --action merge --branch feature/auth --strategy squash
```

Complete the current branch with the finish workflow:

```
/zerg:git --action finish --base main
```

Generate a changelog since v1.0.0:

```
/zerg:git --action history --since v1.0.0
```

Run history cleanup:

```
/zerg:git --action history --cleanup --base main
```

Create a pull request against main:

```
/zerg:git --action pr --base main
```

Create a draft PR with a reviewer:

```
/zerg:git --action pr --draft --reviewer octocat
```

Auto-detect version bump and release:

```
/zerg:git --action release
```

Force a minor release:

```
/zerg:git --action release --bump minor
```

Preview a release without executing:

```
/zerg:git --action release --dry-run
```

Generate a security-focused review context:

```
/zerg:git --action review --focus security
```

Generate an architecture review against develop:

```
/zerg:git --action review --focus architecture --base develop
```

List recent rescue operations:

```
/zerg:git --action rescue --list-ops
```

Undo the last git operation:

```
/zerg:git --action rescue --undo
```

Restore from a snapshot tag:

```
/zerg:git --action rescue --restore zerg-snapshot-20260201
```

Recover a deleted branch:

```
/zerg:git --action rescue --recover-branch feature/auth
```

Bisect with a symptom and test command:

```
/zerg:git --action bisect --symptom "login returns 500" --test-cmd "pytest tests/auth/"
```

Bisect with a known good tag:

```
/zerg:git --action bisect --symptom "CSS broken" --good v1.2.0
```

Ship current branch (full pipeline):

```
/zerg:git --action ship
```

Ship with draft PR for team review:

```
/zerg:git --action ship --no-merge --draft --reviewer octocat
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Operation successful |
| 1 | Operation failed |
| 2 | Tests must pass (required for `finish`) |

## Task Tracking

This command creates a Claude Code Task with the subject prefix `[Git]` on invocation, updates it to `in_progress` immediately, and marks it `completed` on success.

## See Also

- [[Command-review]] -- Review code before committing or finishing
- [[Command-build]] -- Verify the build passes before finishing a branch
- [[Command-test]] -- Ensure tests pass before the finish workflow
