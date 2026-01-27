"""Clean code sample with no security or quality violations."""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def process_file(filepath: str) -> dict:
    """Process a file safely.

    Args:
        filepath: Path to the file

    Returns:
        Processing result
    """
    path = Path(filepath)
    if not path.exists():
        logger.warning("File not found: %s", filepath)
        return {"error": "not_found"}

    # Safe subprocess usage (no shell=True)
    result = subprocess.run(
        ["wc", "-l", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )

    return {
        "path": str(path),
        "lines": result.stdout.strip(),
    }


def get_config() -> dict:
    """Get configuration from environment.

    Returns:
        Configuration dictionary
    """
    import os

    return {
        "debug": os.environ.get("DEBUG", "false").lower() == "true",
        "log_level": os.environ.get("LOG_LEVEL", "INFO"),
    }
