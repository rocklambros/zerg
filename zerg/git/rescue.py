"""Git rescue system -- triple-layer undo/recovery.

Provides snapshot creation, operation logging, and recovery mechanisms
for safe undo of git operations performed by ZERG workers.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from zerg.exceptions import GitError
from zerg.git.base import GitRunner
from zerg.git.config import GitConfig, GitRescueConfig
from zerg.git.types import RescueSnapshot
from zerg.logging import get_logger

logger = get_logger("git.rescue")

# Validation pattern for tag and branch names: alphanumeric, hyphens, slashes, dots
_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._/-]*$")


def _validate_name(name: str, kind: str = "name") -> None:
    """Validate a git ref name against allowed characters.

    Args:
        name: The name to validate
        kind: Label for error messages (e.g. "tag", "branch")

    Raises:
        ValueError: If name contains disallowed characters
    """
    if not name or not _NAME_PATTERN.match(name):
        raise ValueError(
            f"Invalid {kind}: {name!r}. Only alphanumeric characters, hyphens, slashes, and dots are allowed."
        )


def _validate_path_within_project(path: Path, project_root: Path) -> Path:
    """Validate that a path resolves within the project root.

    Args:
        path: Path to validate
        project_root: Project root directory

    Returns:
        Resolved absolute path

    Raises:
        ValueError: If path escapes project root
    """
    resolved = path.resolve()
    if not resolved.is_relative_to(project_root.resolve()):
        raise ValueError(f"Path {resolved} is outside project root {project_root}")
    return resolved


class OperationLogger:
    """Append-only JSON-lines logger for git operations.

    Each line in the ops log is a JSON object with timestamp, operation,
    branch, commit, and description fields.
    """

    def __init__(self, ops_log_path: str | Path, project_root: Path | None = None) -> None:
        """Initialize operation logger.

        Args:
            ops_log_path: Path to the operations log file
            project_root: Project root for path validation. If None, uses
                          the parent of the ops_log_path's containing directory.
        """
        raw_path = Path(ops_log_path)
        if project_root is not None:
            self._path = _validate_path_within_project(raw_path, project_root)
        else:
            self._path = raw_path.resolve()

    def log_operation(
        self,
        operation: str,
        branch: str,
        commit: str,
        description: str,
    ) -> None:
        """Append an operation entry to the log.

        Args:
            operation: Operation name (e.g. "merge", "snapshot")
            branch: Branch name at time of operation
            commit: Commit SHA at time of operation
            description: Human-readable description
        """
        entry = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "operation": operation,
            "branch": branch,
            "commit": commit,
            "description": description,
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        logger.debug(f"Logged operation: {operation} on {branch}")

    def get_recent(self, count: int = 20) -> list[dict]:
        """Read the most recent N operations from the log.

        Args:
            count: Number of recent entries to return

        Returns:
            List of operation dicts, most recent last
        """
        if not self._path.exists():
            return []

        entries: list[dict] = []
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning(f"Skipping malformed log line: {line[:80]}")
                    continue

        return entries[-count:]


class SnapshotManager:
    """Manages lightweight git tag snapshots for recovery.

    Snapshots are created as tags named ``zerg-snapshot-{timestamp}``
    and can be listed, restored, or pruned.
    """

    TAG_PREFIX = "zerg-snapshot-"

    def __init__(self, runner: GitRunner, config: GitRescueConfig) -> None:
        """Initialize snapshot manager.

        Args:
            runner: GitRunner for executing git commands
            config: Rescue configuration
        """
        self._runner = runner
        self._config = config

    def create_snapshot(self, operation: str, description: str) -> RescueSnapshot:
        """Create a lightweight tag snapshot of the current state.

        Args:
            operation: Name of the operation being protected
            description: Human-readable description

        Returns:
            RescueSnapshot with tag and commit info
        """
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        tag = f"{self.TAG_PREFIX}{timestamp}"
        branch = self._runner.current_branch()
        commit = self._runner.current_commit()

        self._runner._run("tag", tag, commit)
        logger.info(f"Created snapshot {tag} at {commit[:8]} on {branch}")

        return RescueSnapshot(
            timestamp=timestamp,
            branch=branch,
            commit=commit,
            operation=operation,
            tag=tag,
            description=description,
        )

    def list_snapshots(self) -> list[RescueSnapshot]:
        """List all zerg-snapshot-* tags.

        Returns:
            List of RescueSnapshot objects sorted by timestamp
        """
        result = self._runner._run("tag", "--list", f"{self.TAG_PREFIX}*", check=False)
        tags = [t.strip() for t in result.stdout.strip().split("\n") if t.strip()]

        snapshots: list[RescueSnapshot] = []
        for tag in sorted(tags):
            _validate_name(tag, "tag")
            try:
                # Get the commit the tag points to
                commit_result = self._runner._run("rev-list", "-1", tag)
                commit = commit_result.stdout.strip()

                # Extract timestamp from tag name
                timestamp = tag.removeprefix(self.TAG_PREFIX)

                snapshots.append(
                    RescueSnapshot(
                        timestamp=timestamp,
                        branch="",  # branch info not stored in lightweight tags
                        commit=commit,
                        operation="",
                        tag=tag,
                        description="",
                    )
                )
            except GitError:
                logger.warning(f"Could not resolve snapshot tag: {tag}")
                continue

        return snapshots

    def restore_snapshot(self, tag: str) -> None:
        """Checkout the commit pointed to by a snapshot tag.

        Args:
            tag: Snapshot tag name to restore

        Raises:
            ValueError: If tag name is invalid
            GitError: If checkout fails
        """
        _validate_name(tag, "tag")
        if not tag.startswith(self.TAG_PREFIX):
            raise ValueError(f"Not a zerg snapshot tag: {tag}")

        self._runner._run("checkout", tag)
        logger.info(f"Restored snapshot: {tag}")

    def prune_snapshots(self) -> int:
        """Delete oldest snapshots beyond max_snapshots.

        Returns:
            Number of snapshots deleted
        """
        snapshots = self.list_snapshots()
        if len(snapshots) <= self._config.max_snapshots:
            return 0

        to_delete = snapshots[: len(snapshots) - self._config.max_snapshots]
        deleted = 0
        for snap in to_delete:
            try:
                self._runner._run("tag", "-d", snap.tag)
                deleted += 1
                logger.debug(f"Pruned snapshot: {snap.tag}")
            except GitError:
                logger.warning(f"Failed to delete snapshot tag: {snap.tag}")

        logger.info(f"Pruned {deleted} snapshot(s)")
        return deleted


class RescueEngine:
    """Main entry point for git rescue operations.

    Coordinates OperationLogger and SnapshotManager to provide
    auto-snapshot, undo, restore, and branch recovery capabilities.
    """

    def __init__(self, runner: GitRunner, config: GitConfig) -> None:
        """Initialize rescue engine.

        Args:
            runner: GitRunner for executing git commands
            config: Top-level git configuration
        """
        self._runner = runner
        self._config = config
        self._rescue_config = config.rescue

        ops_log_path = runner.repo_path / self._rescue_config.ops_log
        self._logger = OperationLogger(ops_log_path, project_root=runner.repo_path)
        self._snapshots = SnapshotManager(runner, self._rescue_config)

    def auto_snapshot(self, operation: str) -> RescueSnapshot | None:
        """Create a snapshot if auto_snapshot is enabled.

        Args:
            operation: Name of the operation being protected

        Returns:
            RescueSnapshot if created, None if auto_snapshot is disabled
        """
        if not self._rescue_config.auto_snapshot:
            return None

        snapshot = self._snapshots.create_snapshot(
            operation=operation,
            description=f"Auto-snapshot before {operation}",
        )
        self._logger.log_operation(
            operation="snapshot",
            branch=snapshot.branch,
            commit=snapshot.commit,
            description=f"Auto-snapshot before {operation}",
        )
        return snapshot

    def list_operations(self, count: int = 20) -> list[dict]:
        """Show recent operations from the ops log.

        Args:
            count: Number of operations to return

        Returns:
            List of operation dicts
        """
        return self._logger.get_recent(count)

    def undo_last(self) -> bool:
        """Revert the last operation using the most recent snapshot.

        Finds the most recent snapshot and restores it. Logs the undo
        operation to the ops log.

        Returns:
            True if undo succeeded, False if no snapshot available
        """
        snapshots = self._snapshots.list_snapshots()
        if not snapshots:
            logger.warning("No snapshots available for undo")
            return False

        latest = snapshots[-1]
        try:
            branch = self._runner.current_branch()
            # Reset the current branch to the snapshot commit
            self._runner._run("reset", "--hard", latest.commit)
            self._logger.log_operation(
                operation="undo",
                branch=branch,
                commit=latest.commit,
                description=f"Undo to snapshot {latest.tag}",
            )
            logger.info(f"Undo successful: restored to {latest.tag}")
            return True
        except GitError as exc:
            logger.error(f"Undo failed: {exc}")
            return False

    def restore(self, snapshot_tag: str) -> bool:
        """Restore a specific snapshot by tag name.

        Args:
            snapshot_tag: Tag name of the snapshot to restore

        Returns:
            True if restore succeeded, False otherwise
        """
        try:
            _validate_name(snapshot_tag, "tag")
            self._snapshots.restore_snapshot(snapshot_tag)
            self._logger.log_operation(
                operation="restore",
                branch="(detached)",
                commit="",
                description=f"Restored snapshot {snapshot_tag}",
            )
            return True
        except (ValueError, GitError) as exc:
            logger.error(f"Restore failed: {exc}")
            return False

    def recover_branch(self, branch_name: str) -> bool:
        """Recover a deleted branch from the reflog.

        Searches the reflog for the last commit on the named branch
        and re-creates it.

        Args:
            branch_name: Name of the branch to recover

        Returns:
            True if recovery succeeded, False otherwise
        """
        _validate_name(branch_name, "branch")
        try:
            # Search reflog for the branch
            result = self._runner._run(
                "reflog",
                "show",
                "--format=%H %gs",
                "--all",
                check=False,
            )
            target_commit: str | None = None
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                if branch_name in line:
                    parts = line.strip().split(" ", 1)
                    if parts:
                        target_commit = parts[0]
                        break

            if not target_commit:
                logger.warning(f"Could not find branch {branch_name} in reflog")
                return False

            self._runner._run("branch", branch_name, target_commit)
            self._logger.log_operation(
                operation="recover-branch",
                branch=branch_name,
                commit=target_commit,
                description=f"Recovered branch {branch_name} from reflog",
            )
            logger.info(f"Recovered branch {branch_name} at {target_commit[:8]}")
            return True
        except GitError as exc:
            logger.error(f"Branch recovery failed: {exc}")
            return False

    def run(self, action: str, **kwargs: object) -> int:
        """Dispatch to rescue sub-commands.

        Args:
            action: One of "list", "undo", "restore", "recover-branch"
            **kwargs: Action-specific arguments

        Returns:
            Exit code (0 = success, 1 = failure)
        """
        if action == "list":
            count = int(kwargs.get("count", 20))  # type: ignore[arg-type]
            ops = self.list_operations(count)
            for op in ops:
                print(f"[{op.get('timestamp', '?')}] {op.get('operation', '?')}: {op.get('description', '')}")
            return 0

        if action == "undo":
            return 0 if self.undo_last() else 1

        if action == "restore":
            tag = str(kwargs.get("snapshot_tag", ""))
            if not tag:
                logger.error("restore requires snapshot_tag argument")
                return 1
            return 0 if self.restore(tag) else 1

        if action == "recover-branch":
            branch = str(kwargs.get("branch_name", ""))
            if not branch:
                logger.error("recover-branch requires branch_name argument")
                return 1
            return 0 if self.recover_branch(branch) else 1

        logger.error(f"Unknown rescue action: {action}")
        return 1
