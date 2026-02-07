"""Persistence layer for ZERG state — file I/O, locking, and serialization.

Handles all cross-process file locking (fcntl), atomic writes via temp files,
backup creation, and JSON serialization. Submodules receive a PersistenceLayer
instance and operate on the in-memory state dict it manages.
"""

import asyncio
import contextlib
import fcntl
import json
import tempfile
import threading
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from zerg.constants import STATE_DIR
from zerg.exceptions import StateError
from zerg.logging import get_logger

logger = get_logger("state.persistence")


class PersistenceLayer:
    """Low-level state persistence with cross-process file locking.

    Uses fcntl.flock for cross-process file locking to prevent race conditions
    when multiple container workers share the same state file via bind mounts.
    """

    def __init__(self, feature: str, state_dir: str | Path | None = None) -> None:
        """Initialize persistence layer.

        Args:
            feature: Feature name for state isolation
            state_dir: Directory for state files (defaults to .zerg/state)
        """
        self.feature = feature
        self.state_dir = Path(state_dir or STATE_DIR)
        self._state_file = self.state_dir / f"{feature}.json"
        self._lock = threading.RLock()  # In-process thread safety
        self._file_lock_depth = 0  # Reentrant counter for cross-process file lock
        self._state: dict[str, Any] = {}
        self._ensure_dir()

    @property
    def state(self) -> dict[str, Any]:
        """Access the in-memory state dict.

        Submodules use this to read/mutate state within an atomic_update context.
        """
        return self._state

    @state.setter
    def state(self, value: dict[str, Any]) -> None:
        """Set the in-memory state dict."""
        self._state = value

    @property
    def lock(self) -> threading.RLock:
        """Access the in-process reentrant lock for read-only operations."""
        return self._lock

    @property
    def state_file(self) -> Path:
        """Path to the state JSON file."""
        return self._state_file

    def _ensure_dir(self) -> None:
        """Ensure state directory exists."""
        self.state_dir.mkdir(parents=True, exist_ok=True)

    @contextlib.contextmanager
    def atomic_update(self) -> Iterator[None]:
        """Cross-process atomic read-modify-write.

        Acquires an exclusive file lock, reloads state from disk,
        yields for caller to mutate self._state, then saves to disk
        and releases the lock.

        Supports reentrant calls (nested atomic_update contexts skip
        reload/save -- the outermost context handles both).

        The in-process RLock (self._lock) is held for the entire duration
        including the yield, so threads sharing this PersistenceLayer instance
        are fully serialized. The RLock is reentrant, so nested calls from
        the same thread work correctly.
        """
        with self._lock:
            if self._file_lock_depth > 0:
                # Already holding file lock (nested/reentrant call)
                self._file_lock_depth += 1
                try:
                    yield
                finally:
                    self._file_lock_depth -= 1
                return

            lock_path = self._state_file.with_suffix(".lock")
            lock_fd = open(lock_path, "w")  # noqa: SIM115
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
                self._file_lock_depth = 1

                # Reload latest state from disk under lock
                if self._state_file.exists():
                    try:
                        with open(self._state_file) as f:
                            self._state = json.load(f)
                    except json.JSONDecodeError:
                        if not self._state:
                            self._state = self._create_initial_state()
                elif not self._state:
                    self._state = self._create_initial_state()

                yield

                # Save to disk under lock
                self._raw_save()
            finally:
                self._file_lock_depth = 0
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                except OSError as e:
                    logger.debug(f"Lock release failed: {e}")
                lock_fd.close()

    def _raw_save(self) -> None:
        """Write state to disk. Called under atomic_update file lock."""
        with self._lock:
            # Create backup if file already exists
            if self._state_file.exists():
                backup_path = self._state_file.with_suffix(".json.bak")
                existing_content = self._state_file.read_text()
                backup_path.write_text(existing_content)

            # Atomic write: write to temp file, then rename
            temp_fd, temp_path = tempfile.mkstemp(
                suffix=".tmp",
                prefix=f"{self.feature}_",
                dir=self.state_dir,
            )
            temp_file = Path(temp_path)
            try:
                with open(temp_fd, "w") as f:
                    json.dump(self._state, f, indent=2, default=str)
                # Atomic rename (on POSIX systems)
                temp_file.replace(self._state_file)
            except Exception:
                # Clean up temp file on failure
                if temp_file.exists():
                    temp_file.unlink()
                raise

            logger.debug(f"Saved state for feature {self.feature}")

    def load(self) -> dict[str, Any]:
        """Load state from file.

        Returns:
            State dictionary
        """
        # Use shared file lock to prevent reading during a write
        lock_path = self._state_file.with_suffix(".lock")
        lock_fd = open(lock_path, "w")  # noqa: SIM115
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_SH)
            with self._lock:
                if not self._state_file.exists():
                    self._state = self._create_initial_state()
                else:
                    try:
                        with open(self._state_file) as f:
                            self._state = json.load(f)
                    except json.JSONDecodeError as e:
                        raise StateError(f"Failed to parse state file: {e}") from e

                logger.debug(f"Loaded state for feature {self.feature}")
                return self._state.copy()
        finally:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except OSError as e:
                logger.debug(f"Lock release failed: {e}")
            lock_fd.close()

    def save(self) -> None:
        """Save state to file with cross-process locking.

        Public save method -- acquires file lock, writes, and releases.
        """
        lock_path = self._state_file.with_suffix(".lock")
        lock_fd = open(lock_path, "w")  # noqa: SIM115
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            self._raw_save()
        finally:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except OSError as e:
                logger.debug(f"Lock release failed: {e}")
            lock_fd.close()

    def inject_state(self, state_dict: dict[str, Any]) -> None:
        """Inject external state for read-only display (no disk write).

        Used by the dashboard to display state from Claude Code Tasks
        when the state JSON file has no task data.

        Args:
            state_dict: State dictionary to inject.
        """
        with self._lock:
            self._state = state_dict

    async def load_async(self) -> dict[str, Any]:
        """Async version of load() - wraps blocking file I/O in thread.

        Returns:
            State dictionary
        """
        return await asyncio.to_thread(self.load)

    async def save_async(self) -> None:
        """Async version of save() - wraps blocking file I/O in thread."""
        await asyncio.to_thread(self.save)

    def _create_initial_state(self) -> dict[str, Any]:
        """Create initial state structure.

        Returns:
            Initial state dictionary
        """
        return {
            "feature": self.feature,
            "started_at": datetime.now().isoformat(),
            "current_level": 0,
            "tasks": {},
            "workers": {},
            "levels": {},
            "execution_log": [],
            "metrics": None,
            "paused": False,
            "error": None,
        }

    def delete(self) -> None:
        """Delete state file."""
        if self._state_file.exists():
            self._state_file.unlink()
            logger.info(f"Deleted state for feature {self.feature}")

    def exists(self) -> bool:
        """Check if state file exists.

        Returns:
            True if state file exists
        """
        return self._state_file.exists()
