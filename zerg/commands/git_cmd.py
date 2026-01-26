"""ZERG git command - intelligent git operations."""

import re
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table

from zerg.git_ops import GitOps, BranchInfo
from zerg.exceptions import GitError, MergeConflict
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
        dirs = set(Path(f).parent.name for f in files if Path(f).parent.name)
        if dirs:
            summary = f"update {', '.join(list(dirs)[:2])} files"
        else:
            summary = f"update {len(files)} files"

    return f"{commit_type}: {summary}"


def action_commit(git: GitOps, push: bool) -> int:
    """Perform commit action."""
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
        console.print(f"\n[green]✓[/green] Created commit: {commit_sha[:8]}")

        if push:
            console.print("[dim]Pushing...[/dim]")
            git.push(set_upstream=True)
            console.print("[green]✓[/green] Pushed to remote")

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
            current = "✓" if branch.is_current else ""
            table.add_row(branch.name, branch.commit[:8], current)

        console.print(table)
        return 0

    # Create branch
    if git.branch_exists(name):
        console.print(f"[yellow]Branch {name} already exists[/yellow]")
        return 1

    try:
        git.create_branch(name, base)
        console.print(f"[green]✓[/green] Created branch: {name}")

        if Confirm.ask("Switch to new branch?", default=True):
            git.checkout(name)
            console.print(f"[green]✓[/green] Switched to {name}")

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
            console.print(f"[green]✓[/green] Squash merged {branch}")
            console.print("[dim]Changes staged, commit manually or use --action commit[/dim]")
        elif strategy == "rebase":
            # Rebase
            git.rebase(branch)
            console.print(f"[green]✓[/green] Rebased onto {branch}")
        else:
            # Regular merge
            git.merge(branch)
            console.print(f"[green]✓[/green] Merged {branch}")

        return 0
    except MergeConflict as e:
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
            console.print("  [green]✓[/green] Pulled latest changes")
        except GitError:
            pass

        # Rebase onto base if different
        if current != base:
            console.print(f"  Rebasing onto {base}...")
            try:
                git.rebase(f"origin/{base}")
                console.print(f"  [green]✓[/green] Rebased onto {base}")
            except MergeConflict as e:
                console.print(f"  [red]Rebase conflict[/red]")
                return 1
            except GitError:
                pass

        console.print("\n[green]✓[/green] Branch is up to date")
        return 0
    except GitError as e:
        console.print(f"[red]Sync failed:[/red] {e}")
        return 1


def action_history(git: GitOps, since: str | None) -> int:
    """Show commit history."""
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
        try:
            git._run("pull", "--rebase", check=False)
        except GitError:
            pass

        console.print(f"[dim]Merging {current}...[/dim]")
        try:
            git._run("merge", "--squash", current)
            # Generate message
            diff_result = git._run("diff", "--cached", "--stat", check=False)
            suggested = f"feat: merge {current}"
            message = Prompt.ask("Commit message", default=suggested)
            git.commit(message)
            console.print(f"[green]✓[/green] Merged {current} into {base}")

            if push or Confirm.ask("Push to remote?", default=True):
                git.push()
                console.print("[green]✓[/green] Pushed")

            if Confirm.ask(f"Delete branch {current}?", default=True):
                git.delete_branch(current, force=True)
                console.print(f"[green]✓[/green] Deleted {current}")

        except MergeConflict as e:
            console.print(f"[red]Merge conflict:[/red]")
            for f in e.conflicting_files:
                console.print(f"  - {f}")
            git.checkout(current)
            return 1

    elif choice == "pr":
        # Push branch
        if push or Confirm.ask("Push branch to remote?", default=True):
            git.push(set_upstream=True)
            console.print("[green]✓[/green] Pushed branch")
        console.print(f"\n[cyan]Create PR manually: {current} -> {base}[/cyan]")

    elif choice == "keep":
        if push or Confirm.ask("Push branch?", default=True):
            git.push(set_upstream=True)
            console.print("[green]✓[/green] Pushed branch")

    elif choice == "discard":
        if Confirm.ask(f"[red]Discard all changes in {current}?[/red]", default=False):
            git.checkout(base)
            git.delete_branch(current, force=True)
            console.print(f"[green]✓[/green] Discarded {current}")

    return 0


@click.command("git")
@click.option(
    "--action",
    "-a",
    type=click.Choice(["commit", "branch", "merge", "sync", "history", "finish"]),
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
) -> None:
    """Git operations with intelligent commits and finish workflow.

    Supports intelligent commit message generation, branch management,
    merge operations, sync, history analysis, and completion workflow.

    Examples:

        zerg git --action commit --push

        zerg git --action branch --name feature/auth

        zerg git --action finish --base main
    """
    try:
        console.print("\n[bold cyan]ZERG Git[/bold cyan]\n")

        git = GitOps()
        current = git.current_branch()
        console.print(f"Current branch: [cyan]{current}[/cyan]")

        if action == "commit":
            exit_code = action_commit(git, push)
        elif action == "branch":
            exit_code = action_branch(git, name, base)
        elif action == "merge":
            exit_code = action_merge(git, branch, strategy, base)
        elif action == "sync":
            exit_code = action_sync(git, base)
        elif action == "history":
            exit_code = action_history(git, since)
        elif action == "finish":
            exit_code = action_finish(git, base, push)
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
