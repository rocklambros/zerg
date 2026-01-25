"""Git worktree management for ZERG worker isolation."""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from zerg.constants import WORKTREES_DIR
from zerg.exceptions import WorktreeError
from zerg.logging import get_logger

logger = get_logger("worktree")


@dataclass
class WorktreeInfo:
    """Information about a git worktree."""

    path: Path
    branch: str
    commit: str
    is_bare: bool = False
    is_detached: bool = False

    @property
    def name(self) -> str:
        """Get the worktree name from path."""
        return self.path.name


class WorktreeManager:
    """Manage git worktrees for ZERG workers."""

    def __init__(self, repo_path: str | Path = ".") -> None:
        """Initialize worktree manager.

        Args:
            repo_path: Path to the git repository
        """
        self.repo_path = Path(repo_path).resolve()
        self._validate_repo()

    def _validate_repo(self) -> None:
        """Validate that repo_path is a git repository."""
        git_dir = self.repo_path / ".git"
        if not git_dir.exists():
            raise WorktreeError(
                f"Not a git repository: {self.repo_path}",
                worktree_path=str(self.repo_path),
            )

    def _run_git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        """Run a git command.

        Args:
            *args: Git command arguments
            check: Whether to raise on non-zero exit

        Returns:
            Completed process result
        """
        cmd = ["git", "-C", str(self.repo_path), *args]
        logger.debug(f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=check,
            )
            return result
        except subprocess.CalledProcessError as e:
            raise WorktreeError(
                f"Git command failed: {e.stderr.strip()}",
                details={"command": " ".join(cmd), "exit_code": e.returncode},
            )

    def list_worktrees(self) -> list[WorktreeInfo]:
        """List all worktrees in the repository.

        Returns:
            List of WorktreeInfo objects
        """
        result = self._run_git("worktree", "list", "--porcelain")
        worktrees = []
        current: dict[str, str] = {}

        for line in result.stdout.strip().split("\n"):
            if not line:
                if current:
                    worktrees.append(self._parse_worktree_info(current))
                    current = {}
                continue

            if line.startswith("worktree "):
                current["path"] = line[9:]
            elif line.startswith("HEAD "):
                current["commit"] = line[5:]
            elif line.startswith("branch "):
                current["branch"] = line[7:]
            elif line == "bare":
                current["bare"] = "true"
            elif line == "detached":
                current["detached"] = "true"

        if current:
            worktrees.append(self._parse_worktree_info(current))

        return worktrees

    def _parse_worktree_info(self, data: dict[str, str]) -> WorktreeInfo:
        """Parse worktree data into WorktreeInfo.

        Args:
            data: Dictionary of worktree data

        Returns:
            WorktreeInfo object
        """
        branch = data.get("branch", "")
        if branch.startswith("refs/heads/"):
            branch = branch[11:]

        return WorktreeInfo(
            path=Path(data["path"]),
            branch=branch,
            commit=data.get("commit", ""),
            is_bare=data.get("bare") == "true",
            is_detached=data.get("detached") == "true",
        )

    def exists(self, path: str | Path) -> bool:
        """Check if a worktree exists at the given path.

        Args:
            path: Path to check

        Returns:
            True if worktree exists
        """
        path = Path(path).resolve()
        for wt in self.list_worktrees():
            if wt.path == path:
                return True
        return False

    def get_branch_name(self, feature: str, worker_id: int) -> str:
        """Generate branch name for a worker.

        Args:
            feature: Feature name
            worker_id: Worker ID

        Returns:
            Branch name
        """
        return f"zerg/{feature}/worker-{worker_id}"

    def get_worktree_path(self, feature: str, worker_id: int) -> Path:
        """Generate worktree path for a worker.

        Args:
            feature: Feature name
            worker_id: Worker ID

        Returns:
            Path to worktree
        """
        return self.repo_path / WORKTREES_DIR / feature / f"worker-{worker_id}"

    def create(
        self,
        feature: str,
        worker_id: int,
        base_branch: str = "main",
    ) -> WorktreeInfo:
        """Create a worktree for a worker.

        Args:
            feature: Feature name
            worker_id: Worker ID
            base_branch: Branch to base the worktree on

        Returns:
            WorktreeInfo for the created worktree
        """
        branch = self.get_branch_name(feature, worker_id)
        path = self.get_worktree_path(feature, worker_id)

        # Create parent directory
        path.parent.mkdir(parents=True, exist_ok=True)

        # Remove if already exists
        if self.exists(path):
            self.delete(path)

        # Create branch if it doesn't exist
        result = self._run_git("branch", "--list", branch, check=False)
        if not result.stdout.strip():
            self._run_git("branch", branch, base_branch)

        # Create worktree
        self._run_git("worktree", "add", str(path), branch)

        logger.info(f"Created worktree at {path} on branch {branch}")

        return WorktreeInfo(
            path=path,
            branch=branch,
            commit=self._get_head_commit(path),
        )

    def _get_head_commit(self, worktree_path: Path) -> str:
        """Get HEAD commit of a worktree.

        Args:
            worktree_path: Path to worktree

        Returns:
            Commit SHA
        """
        result = subprocess.run(
            ["git", "-C", str(worktree_path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def delete(self, path: str | Path, force: bool = False) -> None:
        """Delete a worktree.

        Args:
            path: Path to worktree
            force: Force removal even if dirty
        """
        path = Path(path).resolve()

        args = ["worktree", "remove", str(path)]
        if force:
            args.append("--force")

        try:
            self._run_git(*args)
            logger.info(f"Removed worktree at {path}")
        except WorktreeError:
            if force:
                # If force removal failed, try pruning
                self._run_git("worktree", "prune")
                if path.exists():
                    import shutil

                    shutil.rmtree(path)
                logger.info(f"Force removed worktree at {path}")
            else:
                raise

    def delete_all(self, feature: str, force: bool = True) -> int:
        """Delete all worktrees for a feature.

        Args:
            feature: Feature name
            force: Force removal

        Returns:
            Number of worktrees deleted
        """
        feature_dir = self.repo_path / WORKTREES_DIR / feature
        count = 0

        for wt in self.list_worktrees():
            if str(wt.path).startswith(str(feature_dir)):
                self.delete(wt.path, force=force)
                count += 1

        # Clean up empty feature directory
        if feature_dir.exists() and not any(feature_dir.iterdir()):
            feature_dir.rmdir()

        return count

    def prune(self) -> None:
        """Prune stale worktree references."""
        self._run_git("worktree", "prune")
        logger.info("Pruned stale worktree references")

    def get_worktree(self, path: str | Path) -> WorktreeInfo | None:
        """Get worktree info by path.

        Args:
            path: Path to worktree

        Returns:
            WorktreeInfo or None if not found
        """
        path = Path(path).resolve()
        for wt in self.list_worktrees():
            if wt.path == path:
                return wt
        return None

    def sync_with_base(self, path: str | Path, base_branch: str = "main") -> None:
        """Rebase worktree on base branch.

        Args:
            path: Path to worktree
            base_branch: Branch to rebase onto
        """
        path = Path(path).resolve()

        subprocess.run(
            ["git", "-C", str(path), "fetch", "origin", base_branch],
            capture_output=True,
            text=True,
            check=True,
        )

        subprocess.run(
            ["git", "-C", str(path), "rebase", f"origin/{base_branch}"],
            capture_output=True,
            text=True,
            check=True,
        )

        logger.info(f"Synced worktree {path} with {base_branch}")
