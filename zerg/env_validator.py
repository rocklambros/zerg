"""Environment variable validation for ZERG workers.

Provides allowlists, blocklists, and validation logic for environment
variables passed to worker processes and containers.
"""

from __future__ import annotations

from zerg.logging import get_logger

logger = get_logger("env_validator")

# Allowlisted environment variables that can be set from config
ALLOWED_ENV_VARS = {
    # ZERG-specific
    "ZERG_WORKER_ID",
    "ZERG_FEATURE",
    "ZERG_WORKTREE",
    "ZERG_BRANCH",
    "ZERG_TASK_ID",
    "ZERG_SPEC_DIR",
    "ZERG_STATE_DIR",
    "ZERG_REPO_PATH",
    "ZERG_LOG_LEVEL",
    "ZERG_DEBUG",
    "ZERG_ANALYSIS_DEPTH",
    "ZERG_COMPACT_MODE",
    "ZERG_MCP_HINT",
    "ZERG_TOKEN_BUDGET",
    "ZERG_BEHAVIORAL_MODE",
    "ZERG_TDD_MODE",
    "ZERG_RULES_ENABLED",
    "ZERG_LOOP_ENABLED",
    "ZERG_LOOP_ITERATIONS",
    "ZERG_VERIFICATION_GATES",
    "ZERG_STALENESS_THRESHOLD",
    # Claude Code cross-session coordination
    "CLAUDE_CODE_TASK_LIST_ID",
    # Common development env vars
    "CI",
    "DEBUG",
    "LOG_LEVEL",
    "VERBOSE",
    "TERM",
    "COLORTERM",
    "NO_COLOR",
    # API keys (user-provided)
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    # Build/test env vars
    "NODE_ENV",
    "PYTHON_ENV",
    "RUST_BACKTRACE",
    "PYTEST_CURRENT_TEST",
}

# Dangerous environment variables that should NEVER be overridden
DANGEROUS_ENV_VARS = {
    "LD_PRELOAD",
    "LD_LIBRARY_PATH",
    "DYLD_INSERT_LIBRARIES",
    "DYLD_LIBRARY_PATH",
    "PATH",
    "PYTHONPATH",
    "NODE_PATH",
    "HOME",
    "USER",
    "SHELL",
    "TMPDIR",
    "TMP",
    "TEMP",
}

# Container path constants
CONTAINER_HOME_DIR = "/home/worker"
CONTAINER_HEALTH_FILE = "/tmp/.zerg-alive"


def validate_env_vars(env: dict[str, str]) -> dict[str, str]:
    """Validate and filter environment variables.

    Args:
        env: Environment variables to validate

    Returns:
        Validated environment variables
    """
    validated = {}

    for key, value in env.items():
        # Check for dangerous vars
        if key.upper() in DANGEROUS_ENV_VARS:
            logger.warning(f"Blocked dangerous environment variable: {key}")
            continue

        # Check if in allowlist or is a ZERG_ prefixed var
        if key.upper() in ALLOWED_ENV_VARS or key.upper().startswith("ZERG_"):
            # Validate value doesn't contain shell metacharacters
            if any(c in value for c in [";", "|", "&", "`", "$", "(", ")", "<", ">"]):
                logger.warning(f"Blocked env var with shell metacharacters: {key}")
                continue

            validated[key] = value
        else:
            logger.debug(f"Skipping unlisted environment variable: {key}")

    return validated
