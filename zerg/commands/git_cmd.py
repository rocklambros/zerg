"""ZERG git command - intelligent git operations."""

import contextlib
import re
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from zerg.exceptions import GitError, MergeConflictError
from zerg.git_ops import GitOps
from zerg.logging import get_logger

console = Console()
logger = get_logger("git")


# Conventional commit type patterns
COMMIT_TYPE_PATTERNS = {
    "feat": [r"add\s+", r"implement\s+", r"create\s+", r"new\s+", r"feature"],
    "fix": [r"fix\s+", r"bug\s*fix", r"resolve\s+", r"correct\s+", r"patch"],
    "docs": [r"doc[s]?\s+", r"readme", r"comment", r"documentation"],
    "style": [r"format", r"style", r"lint", r"whitespace", r"prettier"],
    "refactor": [r"refactor", r"restructure", r"reorganize", r"clean\s*up"],
    "test": [r"test", r"spec", r"coverage"],
    "chore": [r"chore", r"build", r"ci", r"deps", r"bump", r"update.*dep"],
}


def detect_commit_type(diff: str, files: list[str]) -> str:
    """Detect conventional commit type from diff and files."""
    diff_lower = diff.lower()
    files_str = " ".join(files).lower()
    combined = diff_lower + " " + files_str

    # Check file patterns first
    if any("test" in f for f in files):
        return "test"
    if any(f.endswith(".md") or "readme" in f.lower() for f in files):
        return "docs"

    # Check diff content
    for commit_type, patterns in COMMIT_TYPE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                return commit_type

    return "chore"


def generate_commit_message(diff: str, files: list[str]) -> str:
    """Generate a conventional commit message from diff."""
    commit_type = detect_commit_type(diff, files)

    # Generate summary based on files
    if len(files) == 1:
        filename = Path(files[0]).stem
        summary = f"update {filename}"
    elif len(files) <= 3:
        summary = f"update {', '.join(Path(f).stem for f in files[:3])}"
    else:
        # Group by directory
        dirs = {Path(f).parent.name for f in files if Path(f).parent.name}
        if dirs:
            summary = f"update {', '.join(list(dirs)[:2])} files"
        else:
            summary = f"update {len(files)} files"

    return f"{commit_type}: {summary}"


def action_commit(git: GitOps, push: bool, mode: str | None = None) -> int:
    """Perform commit action.

    When mode is provided, delegates to CommitEngine for advanced workflow.
    Otherwise uses the inline commit logic.
    """
    if mode:
        from zerg.git.commit_engine import CommitEngine
        from zerg.git.config import GitConfig

        config = GitConfig()
        engine = CommitEngine(git, config)
        result = engine.run(mode=mode)
        if result == 0 and push:
            git.push(set_upstream=True)
        return result

    if not git.has_changes():
        console.print("[yellow]No changes to commit[/yellow]")
        return 0

    # Get status
    status_result = git._run("status", "--short")
    console.print("\n[bold]Changes to commit:[/bold]")
    console.print(status_result.stdout)

    # Get changed files
    files_result = git._run("diff", "--name-only", "--cached", check=False)
    unstaged_result = git._run("diff", "--name-only", check=False)

    staged_files = files_result.stdout.strip().split("\n") if files_result.stdout.strip() else []
    unstaged_files = unstaged_result.stdout.strip().split("\n") if unstaged_result.stdout.strip() else []
    all_files = staged_files + unstaged_files

    # Stage all if nothing staged
    if not staged_files and unstaged_files:
        console.print("\n[dim]Staging all changes...[/dim]")
        git._run("add", "-A")
        all_files = unstaged_files

    # Get diff for message generation
    diff_result = git._run("diff", "--cached", "--stat", check=False)
    diff_content = diff_result.stdout if diff_result.stdout else ""

    # Generate commit message
    suggested_message = generate_commit_message(diff_content, all_files)
    console.print(f"\n[cyan]Suggested message:[/cyan] {suggested_message}")

    # Let user edit or accept
    message = Prompt.ask("Commit message", default=suggested_message)

    # Commit
    try:
        commit_sha = git.commit(message)
        console.print(f"\n[green]\u2713[/green] Created commit: {commit_sha[:8]}")

        if push:
            console.print("[dim]Pushing...[/dim]")
            git.push(set_upstream=True)
            console.print("[green]\u2713[/green] Pushed to remote")

        return 0
    except GitError as e:
        console.print(f"[red]Commit failed:[/red] {e}")
        return 1


def action_branch(git: GitOps, name: str | None, base: str) -> int:
    """Perform branch action."""
    if not name:
        # List branches
        branches = git.list_branches()
        table = Table(title="Branches")
        table.add_column("Branch")
        table.add_column("Commit")
        table.add_column("Current")

        for branch in branches:
            current = "\u2713" if branch.is_current else ""
            table.add_row(branch.name, branch.commit[:8], current)

        console.print(table)
        return 0

    # Create branch
    if git.branch_exists(name):
        console.print(f"[yellow]Branch {name} already exists[/yellow]")
        return 1

    try:
        git.create_branch(name, base)
        console.print(f"[green]\u2713[/green] Created branch: {name}")

        if Confirm.ask("Switch to new branch?", default=True):
            git.checkout(name)
            console.print(f"[green]\u2713[/green] Switched to {name}")

        return 0
    except GitError as e:
        console.print(f"[red]Failed to create branch:[/red] {e}")
        return 1


def action_merge(git: GitOps, branch: str | None, strategy: str, base: str) -> int:
    """Perform merge action."""
    if not branch:
        console.print("[red]Error:[/red] --branch is required for merge action")
        return 1

    if not git.branch_exists(branch):
        console.print(f"[red]Branch {branch} does not exist[/red]")
        return 1

    try:
        if strategy == "squash":
            # Squash merge
            git._run("merge", "--squash", branch)
            console.print(f"[green]\u2713[/green] Squash merged {branch}")
            console.print("[dim]Changes staged, commit manually or use --action commit[/dim]")
        elif strategy == "rebase":
            # Rebase
            git.rebase(branch)
            console.print(f"[green]\u2713[/green] Rebased onto {branch}")
        else:
            # Regular merge
            git.merge(branch)
            console.print(f"[green]\u2713[/green] Merged {branch}")

        return 0
    except MergeConflictError as e:
        console.print(f"[red]Merge conflict:[/red] {e}")
        console.print("Conflicting files:")
        for f in e.conflicting_files:
            console.print(f"  - {f}")
        return 1
    except GitError as e:
        console.print(f"[red]Merge failed:[/red] {e}")
        return 1


def action_sync(git: GitOps, base: str) -> int:
    """Sync current branch with remote and base."""
    try:
        current = git.current_branch()
        console.print(f"[dim]Syncing {current}...[/dim]")

        # Fetch
        console.print("  Fetching from origin...")
        git.fetch()

        # Pull if tracking remote
        try:
            git._run("pull", "--rebase", check=False)
            console.print("  [green]\u2713[/green] Pulled latest changes")
        except GitError:
            pass

        # Rebase onto base if different
        if current != base:
            console.print(f"  Rebasing onto {base}...")
            try:
                git.rebase(f"origin/{base}")
                console.print(f"  [green]\u2713[/green] Rebased onto {base}")
            except MergeConflictError:
                console.print("  [red]Rebase conflict[/red]")
                return 1
            except GitError:
                pass

        console.print("\n[green]\u2713[/green] Branch is up to date")
        return 0
    except GitError as e:
        console.print(f"[red]Sync failed:[/red] {e}")
        return 1


def action_history(git: GitOps, since: str | None, cleanup: bool = False, base: str = "main") -> int:
    """Show commit history or run cleanup."""
    if cleanup:
        from zerg.git.config import GitConfig
        from zerg.git.history_engine import HistoryEngine

        config = GitConfig()
        engine = HistoryEngine(git, config)
        return engine.run(action="cleanup", base_branch=base)

    args = ["log", "--oneline", "-20"]
    if since:
        args.append(f"{since}..HEAD")

    result = git._run(*args, check=False)
    if result.stdout:
        console.print("\n[bold]Recent commits:[/bold]")
        for line in result.stdout.strip().split("\n"):
            if line:
                sha, *msg_parts = line.split(" ", 1)
                msg = msg_parts[0] if msg_parts else ""
                console.print(f"  [cyan]{sha}[/cyan] {msg}")
    else:
        console.print("[yellow]No commits found[/yellow]")

    return 0


def action_finish(git: GitOps, base: str, push: bool) -> int:
    """Interactive finish workflow for feature branches."""
    current = git.current_branch()

    if current == base:
        console.print(f"[yellow]Already on {base}, nothing to finish[/yellow]")
        return 0

    console.print(
        Panel(
            f"Finishing branch: [cyan]{current}[/cyan]\nTarget: [cyan]{base}[/cyan]",
            title="ZERG Git Finish",
        )
    )

    # Show commits
    log_result = git._run("log", "--oneline", f"{base}..HEAD", check=False)
    if log_result.stdout:
        console.print("\n[bold]Commits to include:[/bold]")
        console.print(log_result.stdout)

    # Choose action
    console.print("\n[bold]Choose finish action:[/bold]")
    console.print("  1. [cyan]merge[/cyan] - Merge into base branch")
    console.print("  2. [cyan]pr[/cyan] - Push and open PR (manual)")
    console.print("  3. [cyan]keep[/cyan] - Keep branch, push only")
    console.print("  4. [cyan]discard[/cyan] - Discard branch changes")

    choice = Prompt.ask("Action", choices=["merge", "pr", "keep", "discard"], default="merge")

    if choice == "merge":
        # Squash merge into base
        console.print(f"\n[dim]Switching to {base}...[/dim]")
        git.checkout(base)
        git.fetch()
        with contextlib.suppress(GitError):
            git._run("pull", "--rebase", check=False)

        console.print(f"[dim]Merging {current}...[/dim]")
        try:
            git._run("merge", "--squash", current)
            # Generate message
            git._run("diff", "--cached", "--stat", check=False)
            suggested = f"feat: merge {current}"
            message = Prompt.ask("Commit message", default=suggested)
            git.commit(message)
            console.print(f"[green]\u2713[/green] Merged {current} into {base}")

            if push or Confirm.ask("Push to remote?", default=True):
                git.push()
                console.print("[green]\u2713[/green] Pushed")

            if Confirm.ask(f"Delete branch {current}?", default=True):
                git.delete_branch(current, force=True)
                console.print(f"[green]\u2713[/green] Deleted {current}")

        except MergeConflictError as e:
            console.print("[red]Merge conflict:[/red]")
            for f in e.conflicting_files:
                console.print(f"  - {f}")
            git.checkout(current)
            return 1

    elif choice == "pr":
        # Push branch
        if push or Confirm.ask("Push branch to remote?", default=True):
            git.push(set_upstream=True)
            console.print("[green]\u2713[/green] Pushed branch")
        console.print(f"\n[cyan]Create PR manually: {current} -> {base}[/cyan]")

    elif choice == "keep":
        if push or Confirm.ask("Push branch?", default=True):
            git.push(set_upstream=True)
            console.print("[green]\u2713[/green] Pushed branch")

    elif choice == "discard":
        if Confirm.ask(f"[red]Discard all changes in {current}?[/red]", default=False):
            git.checkout(base)
            git.delete_branch(current, force=True)
            console.print(f"[green]\u2713[/green] Discarded {current}")

    return 0


# =========================================================================
# New action handlers for engines
# =========================================================================


def action_pr(git: GitOps, base: str, draft: bool, reviewer: str | None) -> int:
    """Create a pull request with full context."""
    from zerg.git.config import GitConfig
    from zerg.git.pr_engine import PREngine

    config = GitConfig()
    engine = PREngine(git, config)
    return engine.run(base_branch=base, draft=draft, reviewer=reviewer)


def action_release(git: GitOps, bump: str, dry_run: bool) -> int:
    """Run release workflow."""
    from zerg.git.config import GitConfig
    from zerg.git.release_engine import ReleaseEngine

    config = GitConfig()
    engine = ReleaseEngine(git, config)
    bump_arg = bump if bump != "auto" else None
    return engine.run(bump=bump_arg, dry_run=dry_run)


def action_review(git: GitOps, base: str, focus: str | None) -> int:
    """Run pre-review context assembly."""
    from zerg.git.config import GitConfig
    from zerg.git.prereview import PreReviewEngine

    config = GitConfig()
    engine = PreReviewEngine(git, config)
    return engine.run(base_branch=base, focus=focus)


def action_rescue(
    git: GitOps,
    list_ops: bool,
    undo: bool,
    restore: str | None,
    recover_branch: str | None,
) -> int:
    """Git rescue operations."""
    from zerg.git.config import GitConfig
    from zerg.git.rescue import RescueEngine

    config = GitConfig()
    engine = RescueEngine(git, config)
    if list_ops:
        return engine.run("list")
    if undo:
        return engine.run("undo")
    if restore:
        return engine.run("restore", snapshot_tag=restore)
    if recover_branch:
        return engine.run("recover-branch", branch_name=recover_branch)
    console.print("[yellow]Specify --list-ops, --undo, --restore, or --recover-branch[/yellow]")
    return 1


def action_bisect(
    git: GitOps,
    symptom: str | None,
    test_cmd: str | None,
    good: str | None,
    base: str,
) -> int:
    """Run AI-powered bisect."""
    from zerg.git.bisect_engine import BisectEngine
    from zerg.git.config import GitConfig

    config = GitConfig()
    engine = BisectEngine(git, config)
    return engine.run(symptom=symptom or "", test_cmd=test_cmd, good=good, bad="HEAD")


def action_ship(git: GitOps, base: str, draft: bool, reviewer: str | None, no_merge: bool) -> int:
    """Ship: commit -> push -> PR -> merge -> cleanup in one shot."""
    import subprocess as _subprocess

    from zerg.config import ZergConfig
    from zerg.merge import MergeCoordinator

    current = git.current_branch()
    if current == base:
        console.print(f"[yellow]Already on {base}, nothing to ship[/yellow]")
        return 0

    # Step 1: Commit + push
    console.print("\n[bold]Step 1/5: Commit & push[/bold]")
    if git.has_changes():
        rc = action_commit(git, push=True, mode="auto")
        if rc != 0:
            console.print("[red]Ship aborted: commit failed[/red]")
            return rc
    else:
        # No local changes but branch may have unpushed commits
        console.print("[dim]No uncommitted changes, pushing existing commits...[/dim]")
        try:
            git.push(set_upstream=True)
            console.print("[green]\u2713[/green] Pushed to remote")
        except GitError as e:
            console.print(f"[red]Push failed:[/red] {e}")
            return 1

    # Step 2: Create PR
    console.print("\n[bold]Step 2/5: Create PR[/bold]")
    rc = action_pr(git, base, draft, reviewer)
    if rc != 0:
        console.print("[red]Ship aborted: PR creation failed[/red]")
        return rc

    if no_merge:
        console.print(f"\n[green]\u2713[/green] PR created for {current} \u2192 {base} (--no-merge: stopping here)")
        return 0

    # Step 3: Merge PR
    console.print("\n[bold]Step 3/5: Merge PR[/bold]")

    # Check if we should use ZERG merge with gates
    config = ZergConfig.load()
    feature = _detect_zerg_feature(current)
    use_zerg_merge = feature is not None and config.rush.gates_at_ship_only

    if use_zerg_merge:
        console.print("[dim]Using ZERG merge coordinator with quality gates...[/dim]")
        try:
            merger = MergeCoordinator(feature, git, config)

            # Run full merge with gates enabled
            result = merger.full_merge_flow(
                level=0,  # Ship level (all levels combined)
                worker_branches=[current],
                target_branch=base,
                skip_gates=False,  # Always run gates at ship time
            )

            if not result.success:
                console.print(f"[red]ZERG merge failed:[/red] {result.error}")
                if result.gate_results:
                    for gr in result.gate_results:
                        if not gr.passed:
                            console.print(f"  [red]\u2717[/red] Gate '{gr.gate_name}' failed")
                return 1

            console.print(f"[green]\u2713[/green] Merged with commit {result.merge_commit}")
        except Exception as e:
            console.print(f"[yellow]ZERG merge failed, falling back to gh merge:[/yellow] {e}")
            use_zerg_merge = False

    if not use_zerg_merge:
        try:
            # Get PR number
            pr_result = _subprocess.run(
                ["gh", "pr", "view", "--json", "number", "-q", ".number"],
                capture_output=True,
                text=True,
                check=True,
            )
            pr_number = pr_result.stdout.strip()

            # Try regular merge first
            merge_result = _subprocess.run(
                ["gh", "pr", "merge", pr_number, "--squash", "--delete-branch"],
                capture_output=True,
                text=True,
            )
            if merge_result.returncode != 0:
                # Fall back to admin merge
                console.print("[dim]Regular merge blocked, trying with --admin...[/dim]")
                _subprocess.run(
                    ["gh", "pr", "merge", pr_number, "--squash", "--admin", "--delete-branch"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
            console.print(f"[green]\u2713[/green] Merged PR #{pr_number}")
        except _subprocess.CalledProcessError as e:
            console.print(f"[red]Merge failed:[/red] {e.stderr or e}")
            return 1

    # Step 4: Switch to base + pull
    console.print("\n[bold]Step 4/5: Update base[/bold]")
    git.checkout(base)
    git._run("pull", "--rebase")
    console.print(f"[green]\u2713[/green] Updated {base}")

    # Step 5: Cleanup local branch
    console.print("\n[bold]Step 5/5: Cleanup[/bold]")
    try:
        git.delete_branch(current, force=True)
        console.print(f"[green]\u2713[/green] Deleted local branch {current}")
    except GitError:
        console.print(f"[dim]Local branch {current} already deleted[/dim]")

    console.print(f"\n[bold green]\u2713 Shipped {current} \u2192 {base}[/bold green]")
    return 0


def _detect_zerg_feature(branch: str) -> str | None:
    """Detect ZERG feature name from branch name.

    Args:
        branch: Git branch name

    Returns:
        Feature name if this is a ZERG branch, None otherwise
    """
    # ZERG branches follow pattern: zerg/{feature}/worker-{n}
    if branch.startswith("zerg/"):
        parts = branch.split("/")
        if len(parts) >= 2:
            return parts[1]
    return None


@click.command("git")
@click.option(
    "--action",
    "-a",
    type=click.Choice(
        [
            "commit",
            "branch",
            "merge",
            "sync",
            "history",
            "finish",
            "pr",
            "release",
            "review",
            "rescue",
            "bisect",
            "ship",
        ]
    ),
    default="commit",
    help="Git action to perform",
)
@click.option("--push", "-p", is_flag=True, help="Push after commit")
@click.option("--base", "-b", default="main", help="Base branch for operations")
@click.option("--name", "-n", help="Branch name (for branch action)")
@click.option("--branch", help="Branch to merge (for merge action)")
@click.option(
    "--strategy",
    type=click.Choice(["merge", "squash", "rebase"]),
    default="squash",
    help="Merge strategy",
)
@click.option("--since", help="Starting point for history (tag or commit)")
@click.option("--symptom", help="Bug symptom description (for bisect)")
@click.option(
    "--bump",
    type=click.Choice(["auto", "major", "minor", "patch"]),
    default="auto",
    help="Version bump type (for release)",
)
@click.option("--draft", is_flag=True, help="Create draft PR")
@click.option("--reviewer", help="PR reviewer username")
@click.option(
    "--focus",
    type=click.Choice(["security", "performance", "quality", "architecture"]),
    help="Review focus domain",
)
@click.option("--dry-run", "dry_run", is_flag=True, help="Preview without executing (for release)")
@click.option(
    "--mode",
    type=click.Choice(["auto", "confirm", "suggest"]),
    help="Commit mode override",
)
@click.option("--list-ops", "list_ops", is_flag=True, help="List rescue operations")
@click.option("--undo", is_flag=True, help="Undo last operation (rescue)")
@click.option("--restore", help="Restore snapshot tag (rescue)")
@click.option("--recover-branch", "recover_branch", help="Recover deleted branch (rescue)")
@click.option("--cleanup", is_flag=True, help="Run history cleanup")
@click.option("--test-cmd", "test_cmd", help="Test command for bisect")
@click.option("--good", help="Known good commit/tag (for bisect)")
@click.option("--no-merge", "no_merge", is_flag=True, help="Stop after PR creation (skip merge+cleanup)")
@click.pass_context
def git_cmd(
    ctx: click.Context,
    action: str,
    push: bool,
    base: str,
    name: str | None,
    branch: str | None,
    strategy: str,
    since: str | None,
    symptom: str | None,
    bump: str,
    draft: bool,
    reviewer: str | None,
    focus: str | None,
    dry_run: bool,
    mode: str | None,
    list_ops: bool,
    undo: bool,
    restore: str | None,
    recover_branch: str | None,
    cleanup: bool,
    test_cmd: str | None,
    good: str | None,
    no_merge: bool,
) -> None:
    """Git operations with intelligent commits, PR creation, releases, and more.

    Supports intelligent commit message generation, branch management,
    merge operations, sync, history analysis, completion workflow,
    PR creation, release automation, pre-review, rescue, and bisect.

    Examples:

        zerg git --action commit --push

        zerg git --action branch --name feature/auth

        zerg git --action finish --base main

        zerg git --action pr --draft --reviewer octocat

        zerg git --action release --bump minor

        zerg git --action review --focus security

        zerg git --action rescue --list-ops

        zerg git --action bisect --symptom "login broken" --test-cmd "pytest tests/"

        zerg git --action ship --base main

        zerg git --action ship --base main --no-merge
    """
    try:
        console.print("\n[bold cyan]ZERG Git[/bold cyan]\n")

        git = GitOps()
        current = git.current_branch()
        console.print(f"Current branch: [cyan]{current}[/cyan]")

        if action == "commit":
            exit_code = action_commit(git, push, mode=mode)
        elif action == "branch":
            exit_code = action_branch(git, name, base)
        elif action == "merge":
            exit_code = action_merge(git, branch, strategy, base)
        elif action == "sync":
            exit_code = action_sync(git, base)
        elif action == "history":
            exit_code = action_history(git, since, cleanup=cleanup, base=base)
        elif action == "finish":
            exit_code = action_finish(git, base, push)
        elif action == "pr":
            exit_code = action_pr(git, base, draft, reviewer)
        elif action == "release":
            exit_code = action_release(git, bump, dry_run)
        elif action == "review":
            exit_code = action_review(git, base, focus)
        elif action == "rescue":
            exit_code = action_rescue(git, list_ops, undo, restore, recover_branch)
        elif action == "bisect":
            exit_code = action_bisect(git, symptom, test_cmd, good, base)
        elif action == "ship":
            exit_code = action_ship(git, base, draft, reviewer, no_merge)
        else:
            console.print(f"[red]Unknown action: {action}[/red]")
            exit_code = 1

        raise SystemExit(exit_code)

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        raise SystemExit(130) from None
    except SystemExit:
        raise
    except GitError as e:
        console.print(f"\n[red]Git error:[/red] {e}")
        raise SystemExit(1) from e
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        logger.exception("Git command failed")
        raise SystemExit(1) from e
