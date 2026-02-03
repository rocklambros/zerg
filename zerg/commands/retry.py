"""ZERG retry command - retry failed or blocked tasks."""

import click
from rich.console import Console
from rich.table import Table

from zerg.constants import TaskStatus
from zerg.logging import get_logger
from zerg.orchestrator import Orchestrator
from zerg.state import StateManager

console = Console()
logger = get_logger("retry")


@click.command()
@click.argument("task_id", required=False)
@click.option("--feature", "-f", help="Feature name")
@click.option("--all-failed", is_flag=True, help="Retry all failed tasks")
@click.option("--reset", is_flag=True, help="Reset task to fresh state")
@click.option("--worker", "-w", "worker_id", type=int, help="Assign to specific worker")
@click.pass_context
def retry(
    ctx: click.Context,
    task_id: str | None,
    feature: str | None,
    all_failed: bool,
    reset: bool,
    worker_id: int | None,
) -> None:
    """Retry failed or blocked tasks.

    Re-queues tasks for execution by resetting their status.

    Examples:

        zerg retry TASK-001

        zerg retry --all-failed

        zerg retry TASK-001 --reset --worker 2
    """
    try:
        # Validate arguments
        if not task_id and not all_failed:
            console.print("[red]Error:[/red] Specify a task ID or use --all-failed")
            raise SystemExit(1)

        # Auto-detect feature
        if not feature:
            feature = detect_feature()

        if not feature:
            console.print("[red]Error:[/red] No active feature found")
            console.print("Specify a feature with [cyan]--feature[/cyan]")
            raise SystemExit(1)

        console.print(f"\n[bold cyan]ZERG Retry[/bold cyan] - {feature}\n")

        # Load state
        state = StateManager(feature)
        if not state.exists():
            console.print(f"[red]Error:[/red] No state found for feature '{feature}'")
            raise SystemExit(1)

        state.load()

        # Get tasks to retry
        tasks_to_retry = get_failed_tasks(state) if all_failed else [task_id] if task_id else []

        if not tasks_to_retry:
            console.print("[yellow]No tasks to retry[/yellow]")
            return

        # Show tasks to retry
        show_retry_plan(state, tasks_to_retry, reset, worker_id)

        # Confirm
        if not click.confirm("\nProceed with retry?", default=True):
            console.print("[yellow]Aborted[/yellow]")
            return

        # Retry tasks
        retry_count = 0
        for tid in tasks_to_retry:
            success = retry_task(state, tid, reset, worker_id)
            if success:
                retry_count += 1
                console.print(f"  [green]✓[/green] {tid} queued for retry")
            else:
                console.print(f"  [red]✗[/red] {tid} failed to queue")

        console.print(f"\n[green]✓[/green] {retry_count} task(s) queued for retry")

        # Unpause if paused
        if state.is_paused():
            state.set_paused(False)
            console.print("[dim]Execution unpaused[/dim]")

    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        raise SystemExit(1) from e


def detect_feature() -> str | None:
    """Detect active feature. Re-exported from shared utility.

    See :func:`zerg.commands._utils.detect_feature` for details.
    """
    from zerg.commands._utils import detect_feature as _detect

    return _detect()


def get_failed_tasks(state: StateManager) -> list[str]:
    """Get all failed tasks.

    Args:
        state: State manager

    Returns:
        List of failed task IDs
    """
    failed = state.get_tasks_by_status(TaskStatus.FAILED)
    blocked = state.get_tasks_by_status(TaskStatus.BLOCKED)
    return list(failed) + list(blocked)


def show_retry_plan(
    state: StateManager,
    task_ids: list[str],
    reset: bool,
    worker_id: int | None,
) -> None:
    """Show tasks that will be retried.

    Args:
        state: State manager
        task_ids: Task IDs to retry
        reset: Whether to reset
        worker_id: Target worker
    """
    table = Table(title="Tasks to Retry")
    table.add_column("Task", style="cyan")
    table.add_column("Current Status")
    table.add_column("Action")
    table.add_column("Target Worker")

    for task_id in task_ids:
        # Get current status
        tasks = state._state.get("tasks", {})
        task_data = tasks.get(task_id, {})
        current_status = task_data.get("status", "unknown")

        if current_status == TaskStatus.FAILED.value:
            status_display = f"[red]{current_status}[/red]"
        elif current_status == TaskStatus.BLOCKED.value:
            status_display = f"[yellow]{current_status}[/yellow]"
        else:
            status_display = current_status

        action = "RESET & QUEUE" if reset else "QUEUE"
        target = str(worker_id) if worker_id else "auto"

        table.add_row(task_id, status_display, action, target)

    console.print(table)


def retry_task(
    state: StateManager,
    task_id: str,
    reset: bool,
    worker_id: int | None,
    orchestrator: Orchestrator | None = None,
) -> bool:
    """Retry a single task.

    Uses orchestrator's retry method if available for proper retry count handling.

    Args:
        state: State manager
        task_id: Task ID
        reset: Whether to reset
        worker_id: Target worker
        orchestrator: Optional orchestrator for enhanced retry logic

    Returns:
        True if successful
    """
    try:
        # Use orchestrator retry method if available (handles retry counts)
        if orchestrator and not reset:
            success = orchestrator.retry_task(task_id)
            if not success:
                # Fall back to manual retry
                logger.warning(f"Orchestrator retry failed for {task_id}, using manual")
            else:
                # Assign to worker if specified
                if worker_id is not None:
                    state.claim_task(task_id, worker_id)
                return True

        # Manual retry path
        if reset:
            # Full reset - clear retry count and status
            state.reset_task_retry(task_id)
            state.set_task_status(task_id, TaskStatus.PENDING, worker_id=None, error=None)
        else:
            # Simple requeue
            state.set_task_status(task_id, TaskStatus.PENDING)

        # Assign to specific worker if requested
        if worker_id is not None:
            state.claim_task(task_id, worker_id)

        # Log event
        state.append_event(
            "task_retry",
            {
                "task_id": task_id,
                "reset": reset,
                "worker_id": worker_id,
            },
        )

        return True

    except Exception as e:
        logger.error(f"Failed to retry task {task_id}: {e}")
        return False


def retry_all_failed_tasks(
    feature: str,
    reset: bool = False,
) -> tuple[int, list[str]]:
    """Retry all failed tasks using orchestrator.

    Args:
        feature: Feature name
        reset: Whether to reset retry counts

    Returns:
        Tuple of (count retried, list of failed task IDs)
    """
    try:
        orchestrator = Orchestrator(feature)

        if reset:
            # Manual reset of all failed tasks
            state = StateManager(feature)
            state.load()
            failed_tasks = get_failed_tasks(state)
            retried = []

            for task_id in failed_tasks:
                if retry_task(state, task_id, reset=True, worker_id=None):
                    retried.append(task_id)

            return len(retried), retried
        else:
            # Use orchestrator's retry_all_failed
            retried = orchestrator.retry_all_failed()
            return len(retried), retried

    except Exception as e:
        logger.error(f"Failed to retry all failed tasks: {e}")
        return 0, []
