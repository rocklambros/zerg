"""Secure command execution with validation and allowlisting.

This module provides secure command execution by:
1. Using shell=False for all subprocess calls
2. Validating commands against an allowlist
3. Sanitizing file paths and arguments
4. Logging all command executions for audit
"""

import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from zerg.logging import get_logger

logger = get_logger(__name__)


class CommandCategory(Enum):
    """Categories of allowed commands."""

    TESTING = "testing"
    LINTING = "linting"
    BUILDING = "building"
    GIT = "git"
    SYSTEM = "system"
    CUSTOM = "custom"


@dataclass
class CommandResult:
    """Result of command execution."""

    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    success: bool
    category: CommandCategory | None = None
    validated: bool = True
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout": self.stdout[:2000] if len(self.stdout) > 2000 else self.stdout,
            "stderr": self.stderr[:2000] if len(self.stderr) > 2000 else self.stderr,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "category": self.category.value if self.category else None,
            "validated": self.validated,
            "timestamp": self.timestamp.isoformat(),
        }


# Command allowlist - prefix patterns that are permitted
ALLOWED_COMMAND_PREFIXES: dict[str, CommandCategory] = {
    # Testing
    "pytest": CommandCategory.TESTING,
    "python -m pytest": CommandCategory.TESTING,
    "python3 -m pytest": CommandCategory.TESTING,
    "unittest": CommandCategory.TESTING,
    "nose": CommandCategory.TESTING,
    "tox": CommandCategory.TESTING,
    # Linting
    "ruff": CommandCategory.LINTING,
    "flake8": CommandCategory.LINTING,
    "pylint": CommandCategory.LINTING,
    "mypy": CommandCategory.LINTING,
    "pyright": CommandCategory.LINTING,
    "black": CommandCategory.LINTING,
    "isort": CommandCategory.LINTING,
    "autopep8": CommandCategory.LINTING,
    "bandit": CommandCategory.LINTING,
    "safety": CommandCategory.LINTING,
    # JavaScript/Node
    "npm test": CommandCategory.TESTING,
    "npm run test": CommandCategory.TESTING,
    "npm run lint": CommandCategory.LINTING,
    "npm run build": CommandCategory.BUILDING,
    "npx": CommandCategory.SYSTEM,
    "yarn test": CommandCategory.TESTING,
    "yarn lint": CommandCategory.LINTING,
    "yarn build": CommandCategory.BUILDING,
    "jest": CommandCategory.TESTING,
    "eslint": CommandCategory.LINTING,
    "prettier": CommandCategory.LINTING,
    "tsc": CommandCategory.BUILDING,
    # Building
    "make": CommandCategory.BUILDING,
    "cmake": CommandCategory.BUILDING,
    "cargo": CommandCategory.BUILDING,
    "go build": CommandCategory.BUILDING,
    "go test": CommandCategory.TESTING,
    "gradle": CommandCategory.BUILDING,
    "mvn": CommandCategory.BUILDING,
    "pip install": CommandCategory.BUILDING,
    "poetry": CommandCategory.BUILDING,
    # Git (read-only operations)
    "git status": CommandCategory.GIT,
    "git diff": CommandCategory.GIT,
    "git log": CommandCategory.GIT,
    "git show": CommandCategory.GIT,
    "git branch": CommandCategory.GIT,
    "git rev-parse": CommandCategory.GIT,
    "git ls-files": CommandCategory.GIT,
    "git add": CommandCategory.GIT,
    "git commit": CommandCategory.GIT,
    "git checkout": CommandCategory.GIT,
    "git switch": CommandCategory.GIT,
    "git merge": CommandCategory.GIT,
    "git rebase": CommandCategory.GIT,
    "git push": CommandCategory.GIT,
    "git pull": CommandCategory.GIT,
    "git fetch": CommandCategory.GIT,
    "git worktree": CommandCategory.GIT,
    # System utilities (safe subset)
    "echo": CommandCategory.SYSTEM,
    "cat": CommandCategory.SYSTEM,
    "ls": CommandCategory.SYSTEM,
    "pwd": CommandCategory.SYSTEM,
    "which": CommandCategory.SYSTEM,
    "env": CommandCategory.SYSTEM,
    "true": CommandCategory.SYSTEM,
    "false": CommandCategory.SYSTEM,
    # Python
    "python -c": CommandCategory.SYSTEM,
    "python3 -c": CommandCategory.SYSTEM,
    "python -m": CommandCategory.SYSTEM,
    "python3 -m": CommandCategory.SYSTEM,
}

# Dangerous patterns that should never be allowed
DANGEROUS_PATTERNS = [
    r";\s*",  # Command chaining with semicolon
    r"\|\s*",  # Piping (can be dangerous)
    r"&&\s*",  # Command chaining with &&
    r"\|\|\s*",  # Command chaining with ||
    r"`",  # Command substitution
    r"\$\(",  # Command substitution
    r"\$\{",  # Variable expansion
    r">\s*",  # Output redirection
    r"<\s*",  # Input redirection
    r"&\s*$",  # Background execution
    r"eval\s+",  # Eval command
    r"exec\s+",  # Exec command
    r"source\s+",  # Source command
    r"\.\s+/",  # Dot source
    r"rm\s+-rf",  # Dangerous rm
    r"rm\s+-r",  # Dangerous rm
    r"dd\s+",  # dd command
    r"mkfs",  # Filesystem creation
    r"curl.*\|",  # Curl to pipe
    r"wget.*\|",  # Wget to pipe
]

# Compiled dangerous patterns
_DANGEROUS_REGEX = [re.compile(p) for p in DANGEROUS_PATTERNS]


class CommandValidationError(Exception):
    """Raised when command validation fails."""

    pass


class CommandExecutor:
    """Secure command executor with validation and allowlisting."""

    def __init__(
        self,
        working_dir: Path | str | None = None,
        allow_unlisted: bool = False,
        custom_allowlist: dict[str, CommandCategory] | None = None,
        timeout: int = 300,
        audit_log: bool = True,
        trust_commands: bool = False,
    ):
        """Initialize command executor.

        Args:
            working_dir: Working directory for command execution
            allow_unlisted: If True, allow commands not in allowlist (with warning)
            custom_allowlist: Additional allowed command prefixes
            timeout: Default timeout in seconds
            audit_log: Whether to log all command executions
            trust_commands: If True, skip dangerous pattern checks (for trusted
                sources like task-graph verification commands)
        """
        self.working_dir = Path(working_dir) if working_dir else Path.cwd()
        self.allow_unlisted = allow_unlisted
        self.timeout = timeout
        self.audit_log = audit_log
        self.trust_commands = trust_commands

        # Build allowlist
        self.allowlist = ALLOWED_COMMAND_PREFIXES.copy()
        if custom_allowlist:
            self.allowlist.update(custom_allowlist)

        # Execution history for audit
        self._history: list[CommandResult] = []

    def validate_command(self, command: str | list[str]) -> tuple[bool, str, CommandCategory | None]:
        """Validate a command against security rules.

        Args:
            command: Command string or argument list

        Returns:
            Tuple of (is_valid, reason, category)
        """
        # Convert to string for pattern matching
        cmd_str = command if isinstance(command, str) else " ".join(command)
        cmd_str = cmd_str.strip()

        if not cmd_str:
            return False, "Empty command", None

        # Check for dangerous patterns (skipped for trusted command sources
        # like task-graph.json verification commands).
        if not self.trust_commands:
            # Strip quoted strings first so patterns inside quotes (e.g., python -c
            # "import foo; print('OK')") don't trigger false positives.
            cmd_unquoted = re.sub(r'"[^"]*"', '""', cmd_str)
            cmd_unquoted = re.sub(r"'[^']*'", "''", cmd_unquoted)
            for pattern in _DANGEROUS_REGEX:
                if pattern.search(cmd_unquoted):
                    return False, f"Dangerous pattern detected: {pattern.pattern}", None

        # Check against allowlist
        for prefix, category in self.allowlist.items():
            if cmd_str.startswith(prefix):
                return True, "Allowed by prefix match", category

        # Not in allowlist
        if self.allow_unlisted:
            logger.warning(f"Executing unlisted command: {cmd_str[:100]}")
            return True, "Allowed (unlisted mode)", CommandCategory.CUSTOM
        else:
            return False, f"Command not in allowlist: {cmd_str.split()[0]}", None

    def parse_command(self, command: str) -> list[str]:
        """Parse command string into argument list safely.

        Args:
            command: Command string

        Returns:
            List of command arguments
        """
        try:
            return shlex.split(command)
        except ValueError as e:
            raise CommandValidationError(f"Failed to parse command: {e}") from e

    def sanitize_path(self, path: str | Path) -> str:
        """Sanitize a file path for safe use in commands.

        Args:
            path: File path to sanitize

        Returns:
            Sanitized path string
        """
        path_str = str(path)

        # Resolve to absolute path to prevent traversal
        try:
            resolved = Path(path_str).resolve()
            return str(resolved)
        except (OSError, ValueError):
            # If resolution fails, use shlex.quote for safety
            return shlex.quote(path_str)

    def sanitize_paths(self, paths: list[str | Path]) -> list[str]:
        """Sanitize multiple file paths.

        Args:
            paths: List of file paths

        Returns:
            List of sanitized path strings
        """
        return [self.sanitize_path(p) for p in paths]

    def execute(
        self,
        command: str | list[str],
        timeout: int | None = None,
        env: dict[str, str] | None = None,
        cwd: Path | str | None = None,
        capture_output: bool = True,
        check: bool = False,
    ) -> CommandResult:
        """Execute a command securely.

        Args:
            command: Command string or argument list
            timeout: Timeout in seconds (overrides default)
            env: Additional environment variables
            cwd: Working directory (overrides default)
            capture_output: Whether to capture stdout/stderr
            check: Whether to raise on non-zero exit

        Returns:
            CommandResult with execution details

        Raises:
            CommandValidationError: If command validation fails
            subprocess.CalledProcessError: If check=True and command fails
        """
        import time

        start_time = time.time()

        # Validate command
        is_valid, reason, category = self.validate_command(command)
        if not is_valid:
            raise CommandValidationError(f"Command validation failed: {reason}")

        # Parse command to argument list
        cmd_args = self.parse_command(command) if isinstance(command, str) else list(command)

        # Prepare environment
        exec_env = os.environ.copy()
        if env:
            # Validate environment variables
            validated_env = self._validate_env_vars(env)
            exec_env.update(validated_env)

        # Prepare working directory
        exec_cwd = Path(cwd) if cwd else self.working_dir

        # Detect if shell mode is needed (trusted commands with shell operators)
        cmd_str_raw = command if isinstance(command, str) else " ".join(command)
        _shell_operators = ("&&", "||", "|", ">", "<", "2>&1", ";", "$(", "`")
        needs_shell = self.trust_commands and any(op in cmd_str_raw for op in _shell_operators)

        # Execute command
        try:
            result = subprocess.run(
                cmd_str_raw if needs_shell else cmd_args,
                cwd=str(exec_cwd),
                env=exec_env,
                capture_output=capture_output,
                text=True,
                timeout=timeout or self.timeout,
                shell=needs_shell,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            cmd_result = CommandResult(
                command=cmd_args,
                exit_code=result.returncode,
                stdout=result.stdout if capture_output else "",
                stderr=result.stderr if capture_output else "",
                duration_ms=duration_ms,
                success=result.returncode == 0,
                category=category,
                validated=True,
            )

        except subprocess.TimeoutExpired as e:
            duration_ms = int((time.time() - start_time) * 1000)
            raw_stdout = getattr(e, "stdout", None)
            if isinstance(raw_stdout, bytes):
                timeout_stdout = raw_stdout.decode("utf-8", errors="replace")
            else:
                timeout_stdout = raw_stdout or ""
            cmd_result = CommandResult(
                command=cmd_args,
                exit_code=-1,
                stdout=timeout_stdout,
                stderr=f"Command timed out after {timeout or self.timeout}s",
                duration_ms=duration_ms,
                success=False,
                category=category,
                validated=True,
            )

        except FileNotFoundError:
            duration_ms = int((time.time() - start_time) * 1000)
            cmd_result = CommandResult(
                command=cmd_args,
                exit_code=-1,
                stdout="",
                stderr=f"Command not found: {cmd_args[0]}",
                duration_ms=duration_ms,
                success=False,
                category=category,
                validated=True,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            cmd_result = CommandResult(
                command=cmd_args,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
                success=False,
                category=category,
                validated=True,
            )

        # Audit log
        if self.audit_log:
            self._log_execution(cmd_result)
            self._history.append(cmd_result)

        # Check for errors if requested
        if check and not cmd_result.success:
            raise subprocess.CalledProcessError(
                cmd_result.exit_code,
                cmd_args,
                cmd_result.stdout,
                cmd_result.stderr,
            )

        return cmd_result

    def execute_git(
        self,
        *args: str,
        cwd: Path | str | None = None,
        timeout: int | None = None,
    ) -> CommandResult:
        """Execute a git command securely.

        Args:
            *args: Git command arguments (e.g., "status", "-s")
            cwd: Working directory
            timeout: Timeout in seconds

        Returns:
            CommandResult
        """
        cmd_args = ["git", *args]
        return self.execute(cmd_args, cwd=cwd, timeout=timeout)

    def execute_python(
        self,
        *args: str,
        cwd: Path | str | None = None,
        timeout: int | None = None,
    ) -> CommandResult:
        """Execute a Python command securely.

        Args:
            *args: Python command arguments
            cwd: Working directory
            timeout: Timeout in seconds

        Returns:
            CommandResult
        """
        cmd_args = ["python", *args]
        return self.execute(cmd_args, cwd=cwd, timeout=timeout)

    def _validate_env_vars(self, env: dict[str, str]) -> dict[str, str]:
        """Validate environment variables against security rules.

        Args:
            env: Environment variables to validate

        Returns:
            Validated environment variables
        """
        # Dangerous environment variables that should not be overridden
        dangerous_vars = {
            "LD_PRELOAD",
            "LD_LIBRARY_PATH",
            "DYLD_INSERT_LIBRARIES",
            "DYLD_LIBRARY_PATH",
            "PATH",  # Can be set but with validation
            "PYTHONPATH",
            "NODE_PATH",
            "HOME",
            "USER",
            "SHELL",
        }

        validated = {}
        for key, value in env.items():
            if key.upper() in dangerous_vars:
                logger.warning(f"Skipping dangerous environment variable: {key}")
                continue

            # Validate value doesn't contain shell metacharacters
            if any(c in value for c in [";", "|", "&", "`", "$", "(", ")", "<", ">"]):
                logger.warning(f"Skipping env var with shell metacharacters: {key}")
                continue

            validated[key] = value

        return validated

    def _log_execution(self, result: CommandResult) -> None:
        """Log command execution for audit.

        Args:
            result: Command execution result
        """
        cmd_preview = " ".join(result.command)[:100]
        if result.success:
            logger.debug(f"Command OK: {cmd_preview} (exit={result.exit_code}, {result.duration_ms}ms)")
        else:
            logger.warning(f"Command FAILED: {cmd_preview} (exit={result.exit_code})")

    def get_history(self) -> list[CommandResult]:
        """Get command execution history.

        Returns:
            List of CommandResult objects
        """
        return self._history.copy()

    def clear_history(self) -> None:
        """Clear command execution history."""
        self._history.clear()


# Global executor instance for convenience
_default_executor: CommandExecutor | None = None


def get_executor(
    working_dir: Path | str | None = None,
    **kwargs: Any,
) -> CommandExecutor:
    """Get or create a command executor.

    Args:
        working_dir: Working directory
        **kwargs: Additional CommandExecutor arguments

    Returns:
        CommandExecutor instance
    """
    global _default_executor

    if working_dir or kwargs:
        return CommandExecutor(working_dir=working_dir, **kwargs)

    if _default_executor is None:
        _default_executor = CommandExecutor()

    return _default_executor


def execute_safe(
    command: str | list[str],
    **kwargs: Any,
) -> CommandResult:
    """Execute a command safely using the default executor.

    Args:
        command: Command to execute
        **kwargs: Additional execution arguments

    Returns:
        CommandResult
    """
    executor = get_executor()
    return executor.execute(command, **kwargs)
