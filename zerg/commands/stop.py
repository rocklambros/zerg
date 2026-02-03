"""ZERG stop command - stop execution gracefully or forcefully."""

import time
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from zerg.config import ZergConfig
from zerg.constants import WorkerStatus
from zerg.containers import ContainerManager
from zerg.logging import get_logger
from zerg.state import StateManager

console = Console()
logger = get_logger("stop")


@click.command()
@click.option("--feature", "-f", help="Feature to stop")
@click.option("--worker", "-w", "worker_id", type=int, help="Stop specific worker")
@click.option("--force", is_flag=True, help="Force immediate termination")
@click.option("--timeout", default=30, type=int, help="Graceful shutdown timeout (seconds)")
@click.pass_context
def stop(
    ctx: click.Context,
    feature: str | None,
    worker_id: int | None,
    force: bool,
    timeout: int,
) -> None:
    """Stop execution gracefully or forcefully.

    By default, sends checkpoint signal for graceful shutdown.
    Use --force for immediate termination.

    Examples:

        zerg stop

        zerg stop --feature user-auth

        zerg stop --worker 3 --force
    """
    try:
        # Auto-detect feature
        if not feature:
            feature = detect_feature()

        if not feature:
            console.print("[red]Error:[/red] No active feature found")
            console.print("Specify a feature with [cyan]--feature[/cyan]")
            raise SystemExit(1)

        console.print(f"\n[bold cyan]ZERG Stop[/bold cyan] - {feature}\n")

        # Load state
        state = StateManager(feature)
        if not state.exists():
            console.print(f"[red]Error:[/red] No state found for feature '{feature}'")
            raise SystemExit(1)

        state.load()

        # Load config
        config = ZergConfig.load()

        # Get workers to stop
        workers = state.get_all_workers()

        if not workers:
            console.print("[yellow]No workers running[/yellow]")
            return

        # Filter to specific worker if requested
        if worker_id is not None:
            if worker_id not in workers:
                console.print(f"[red]Error:[/red] Worker {worker_id} not found")
                raise SystemExit(1)
            workers = {worker_id: workers[worker_id]}

        # Show what will be stopped
        show_workers_to_stop(workers, force)

        # Confirm if not forcing
        if not force and not click.confirm("\nProceed with graceful shutdown?", default=True):
            console.print("[yellow]Aborted[/yellow]")
            return

        # Stop workers
        if force:
            stop_workers_force(workers, state, config)
        else:
            stop_workers_graceful(workers, state, config, timeout)

        console.print("\n[green]✓[/green] Stop complete")

    except KeyboardInterrupt:
        console.print("\n[yellow]Aborted[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        raise SystemExit(1) from None


def detect_feature() -> str | None:
    """Detect active feature. Re-exported from shared utility.

    See :func:`zerg.commands._utils.detect_feature` for details.
    """
    from zerg.commands._utils import detect_feature as _detect

    return _detect()


def show_workers_to_stop(workers: dict[int, Any], force: bool) -> None:
    """Show workers that will be stopped.

    Args:
        workers: Workers dictionary
        force: Whether force mode
    """
    action = "[red]FORCE KILL[/red]" if force else "[yellow]CHECKPOINT[/yellow]"

    table = Table(title=f"Workers to Stop ({action})")
    table.add_column("Worker", justify="center")
    table.add_column("Status")
    table.add_column("Current Task")
    table.add_column("Action")

    for worker_id, worker in sorted(workers.items()):
        status_display = worker.status.value.upper()
        if worker.status == WorkerStatus.RUNNING:
            status_display = f"[green]{status_display}[/green]"
        elif worker.status == WorkerStatus.IDLE:
            status_display = f"[dim]{status_display}[/dim]"

        table.add_row(
            f"worker-{worker_id}",
            status_display,
            worker.current_task or "-",
            action,
        )

    console.print(table)


def stop_workers_graceful(
    workers: dict[int, Any],
    state: StateManager,
    config: ZergConfig,
    timeout: int,
) -> None:
    """Stop workers gracefully with checkpoint.

    Args:
        workers: Workers to stop
        state: State manager
        config: Configuration
        timeout: Graceful timeout
    """
    console.print("\n[bold]Sending checkpoint signals...[/bold]")

    # Create container manager
    container_mgr = ContainerManager(config)

    # Send checkpoint signal to each worker
    for worker_id, worker in workers.items():
        if worker.status != WorkerStatus.RUNNING:
            console.print(f"  worker-{worker_id}: [dim]skipped (not running)[/dim]")
            continue

        try:
            # Stop worker gracefully
            container_mgr.stop_worker(worker_id, timeout=timeout)
            console.print(f"  worker-{worker_id}: [yellow]checkpoint signal sent[/yellow]")

            # Update state
            worker_state = state.get_worker_state(worker_id)
            if worker_state:
                worker_state.status = WorkerStatus.STOPPING
                state.set_worker_state(worker_state)

        except Exception as e:
            logger.warning(f"Failed to signal worker {worker_id}: {e}")
            console.print(f"  worker-{worker_id}: [red]signal failed[/red]")

    # Wait for graceful shutdown
    console.print(f"\n[bold]Waiting up to {timeout}s for graceful shutdown...[/bold]")

    start = time.time()
    while time.time() - start < timeout:
        # Reload state
        state.load()
        workers = state.get_all_workers()

        # Check if all stopped
        still_running = [wid for wid, w in workers.items() if w.status in (WorkerStatus.RUNNING, WorkerStatus.STOPPING)]

        if not still_running:
            console.print("[green]All workers stopped gracefully[/green]")
            return

        console.print(f"  Still running: {len(still_running)} workers...")
        time.sleep(2)

    # Timeout - force remaining
    console.print("[yellow]Timeout reached, forcing remaining workers...[/yellow]")
    state.load()
    remaining = {
        wid: w
        for wid, w in state.get_all_workers().items()
        if w.status in (WorkerStatus.RUNNING, WorkerStatus.STOPPING)
    }

    if remaining:
        stop_workers_force(remaining, state, config)


def stop_workers_force(
    workers: dict[int, Any],
    state: StateManager,
    config: ZergConfig,
) -> None:
    """Force stop workers immediately.

    Args:
        workers: Workers to stop
        state: State manager
        config: Configuration
    """
    console.print("\n[bold red]Force stopping workers...[/bold red]")

    container_mgr = ContainerManager(config)

    for worker_id, _worker in workers.items():
        try:
            # Kill the container
            container_mgr.stop_worker(worker_id, timeout=5, force=True)
            console.print(f"  worker-{worker_id}: [red]killed[/red]")

            # Update state
            worker_state = state.get_worker_state(worker_id)
            if worker_state:
                worker_state.status = WorkerStatus.STOPPED
                state.set_worker_state(worker_state)

            # Log event
            state.append_event(
                "worker_killed",
                {
                    "worker_id": worker_id,
                    "force": True,
                },
            )

        except Exception as e:
            logger.error(f"Failed to kill worker {worker_id}: {e}")
            console.print(f"  worker-{worker_id}: [red]kill failed: {e}[/red]")

    # Set paused state
    state.set_paused(True)
    console.print("\n[yellow]Execution paused[/yellow]")
