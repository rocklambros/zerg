"""Shared utilities for ZERG CLI commands."""

import os
import re
import time
from pathlib import Path

from zerg.constants import GSD_DIR, STATE_DIR

# --- Private constants ---

_FEATURE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
MAX_PID = 4_194_304  # Linux kernel max PID


# --- Private helpers ---


def _validate_feature_name(feature: str) -> None:
    """Raise ValueError if feature name contains path traversal characters.

    Rejects names containing '/', '\\', '..', empty strings, or names that
    don't match the allowed pattern (alphanumeric start, then alphanumeric,
    dots, hyphens, underscores).

    Args:
        feature: Feature name to validate.

    Raises:
        ValueError: If the feature name is invalid.
    """
    if not feature or ".." in feature or "/" in feature or "\\" in feature:
        raise ValueError(f"Invalid feature name: {feature!r}")
    if not _FEATURE_NAME_RE.match(feature):
        raise ValueError(f"Invalid feature name: {feature!r}")


def _safe_read_text(path: Path) -> str | None:
    """Read text from path, returning None on any OS or encoding error.

    Args:
        path: File path to read.

    Returns:
        Stripped file content, or None if the file cannot be read.
    """
    try:
        return path.read_text().strip()
    except (OSError, UnicodeDecodeError):
        return None


def _parse_lock_content(content: str) -> tuple[int, float] | None:
    """Parse 'pid:timestamp' lock content with bounds checking.

    Args:
        content: Raw lock file content (already stripped).

    Returns:
        Tuple of (pid, timestamp) if valid, or None if corrupt/out-of-bounds.
    """
    try:
        pid_str, ts_str = content.split(":", 1)
        pid = int(pid_str)
        ts = float(ts_str)
    except (ValueError, TypeError):
        return None
    if pid < 1 or pid > MAX_PID:
        return None
    if ts <= 0 or ts > time.time() + 86400:
        return None
    return (pid, ts)


# --- Public API ---


def detect_feature() -> str | None:
    """Detect active feature from project state.

    Priority order:
    1. ZERG_FEATURE env var (terminal-session-scoped, multi-epic safe)
    2. .gsd/.current-feature (explicit user intent from /zerg:plan)
    3. .zerg/state/*.json (most recently modified state file)

    The ZERG_FEATURE env var allows terminal-scoped feature isolation,
    enabling multiple epics to run concurrently in separate terminals.

    The .gsd/.current-feature file is written by /zerg:plan and reflects the
    feature the user is actively working on. State JSON files may be stale
    from previous runs, so they serve as a fallback.

    Returns:
        Feature name or None if no active feature can be detected.
    """
    # Primary: env var (terminal-scoped, multi-epic safe)
    env_feature = os.environ.get("ZERG_FEATURE", "").strip()
    if env_feature:
        return env_feature

    # Secondary: explicit feature set by /zerg:plan
    current_feature = Path(GSD_DIR) / ".current-feature"
    if current_feature.exists():
        name = _safe_read_text(current_feature)
        if name:
            return name

    # Fallback: most recently modified state file
    state_dir = Path(STATE_DIR)
    if state_dir.exists():
        state_files = list(state_dir.glob("*.json"))
        if state_files:
            state_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return state_files[0].stem

    return None


def acquire_feature_lock(feature: str, gsd_dir: str = ".gsd") -> bool:
    """Create advisory lock for a feature.

    Returns True if lock acquired, False if another session holds it.
    Locks older than 2 hours are considered stale and automatically removed.

    Uses atomic file creation (O_CREAT|O_EXCL) to prevent TOCTOU races
    between concurrent processes.

    Args:
        feature: Feature name to lock.
        gsd_dir: Path to the GSD directory.

    Returns:
        True if the lock was acquired, False if an active lock exists.

    Raises:
        ValueError: If the feature name is invalid (path traversal).
    """
    _validate_feature_name(feature)

    lock_path = Path(gsd_dir) / "specs" / feature / ".lock"

    # Check for existing lock
    if lock_path.exists():
        content = _safe_read_text(lock_path)
        if content is not None:
            parsed = _parse_lock_content(content)
            if parsed is not None:
                _pid, ts = parsed
                if time.time() - ts > 7200:  # Stale if > 2 hours
                    try:
                        lock_path.unlink()
                    except OSError:
                        pass  # Best-effort file cleanup
                else:
                    return False  # Active lock
            else:
                # Corrupt lock content, remove
                try:
                    lock_path.unlink()
                except OSError:
                    pass  # Best-effort file cleanup
        else:
            # Unreadable lock file, remove
            try:
                lock_path.unlink()
            except OSError:
                pass  # Best-effort file cleanup

    # Ensure parent directory exists
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    # Atomic lock creation — O_CREAT|O_EXCL guarantees no TOCTOU race
    lock_content = f"{os.getpid()}:{time.time()}"
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False  # Another process won the race
    try:
        os.write(fd, lock_content.encode())
    finally:
        os.close(fd)

    return True


def release_feature_lock(feature: str, gsd_dir: str = ".gsd") -> None:
    """Release advisory lock for a feature.

    Only deletes the lock if it is owned by the current process (PID matches).
    Corrupt or unreadable locks are deleted as a fallback cleanup mechanism.
    Locks owned by other processes are left intact.

    Args:
        feature: Feature name to unlock.
        gsd_dir: Path to the GSD directory.

    Raises:
        ValueError: If the feature name is invalid (path traversal).
    """
    _validate_feature_name(feature)

    lock_path = Path(gsd_dir) / "specs" / feature / ".lock"
    if not lock_path.exists():
        return

    # Read and parse lock content for ownership check
    content = _safe_read_text(lock_path)
    if content is not None:
        parsed = _parse_lock_content(content)
        if parsed is not None:
            pid, _ts = parsed
            if pid != os.getpid():
                return  # Not our lock, leave it
    # If content is None (unreadable) or parsed is None (corrupt),
    # fall through to delete as cleanup.

    try:
        lock_path.unlink(missing_ok=True)
    except OSError:
        pass  # Best-effort file cleanup


def check_feature_lock(feature: str, gsd_dir: str = ".gsd") -> dict[str, float | int] | None:
    """Check if a feature is locked.

    Returns lock info dict if an active lock exists, or None if unlocked
    or the lock is stale (older than 2 hours).

    Args:
        feature: Feature name to check.
        gsd_dir: Path to the GSD directory.

    Returns:
        Dict with pid, timestamp, and age_seconds if locked; None otherwise.

    Raises:
        ValueError: If the feature name is invalid (path traversal).
    """
    _validate_feature_name(feature)

    lock_path = Path(gsd_dir) / "specs" / feature / ".lock"
    if not lock_path.exists():
        return None

    content = _safe_read_text(lock_path)
    if content is None:
        return None

    parsed = _parse_lock_content(content)
    if parsed is None:
        return None

    pid, ts = parsed
    if time.time() - ts > 7200:
        return None  # Stale

    return {"pid": pid, "timestamp": ts, "age_seconds": time.time() - ts}
