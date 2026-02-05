"""Backward compatibility -- imports redirect to protocol_state and protocol_handler."""

from zerg.protocol_handler import ProtocolHandler
from zerg.protocol_state import WorkerProtocol, run_worker
from zerg.protocol_types import (
    _SENTINEL,
    CLAUDE_CLI_COMMAND,
    CLAUDE_CLI_DEFAULT_TIMEOUT,
    ClaudeInvocationResult,
    WorkerContext,
)

__all__ = [
    "ClaudeInvocationResult",
    "CLAUDE_CLI_COMMAND",
    "CLAUDE_CLI_DEFAULT_TIMEOUT",
    "ProtocolHandler",
    "WorkerContext",
    "WorkerProtocol",
    "_SENTINEL",
    "run_worker",
]
