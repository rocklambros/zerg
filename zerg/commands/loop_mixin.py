"""Click options mixin for iterative improvement loops."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

import click


def loop_options(f: Callable[..., Any]) -> Callable[..., Any]:
    """Add loop-related Click options to a command.

    Adds --loop, --iterations, and --convergence options.

    Usage:
        @click.command()
        @loop_options
        def my_command(loop, iterations, convergence, **kwargs):
            ...
    """

    @click.option("--loop", is_flag=True, help="Enable iterative improvement mode")
    @click.option(
        "--iterations",
        type=int,
        default=None,
        help="Maximum improvement iterations (default: from config)",
    )
    @click.option(
        "--convergence",
        type=float,
        default=None,
        help="Convergence threshold (default: from config)",
    )
    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return f(*args, **kwargs)

    return wrapper
