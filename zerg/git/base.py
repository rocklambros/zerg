"""GitRunner base class -- low-level git command execution."""

import subprocess
from pathlib import Path

from zerg.exceptions import GitError
from zerg.logging import get_logger

logger = get_logger("git.base")


class GitRunner:
    """Low-level git command runner with repository validation.

    Provides the foundational subprocess execution layer and basic
    read-only queries (current_branch, current_commit, has_changes).
    Higher-level operations live in GitOps which inherits this class.
    """

    def __init__(self, repo_path: str | Path = ".") -> None:
        """Initialize git runner.

        Args:
            repo_path: Path to the git repository

        Raises:
            GitError: If the path is not a git repository
        """
        self.repo_path = Path(repo_path).resolve()
        self._validate_repo()

    def _validate_repo(self) -> None:
        """Validate that repo_path is a git repository."""
        git_dir = self.repo_path / ".git"
        if not git_dir.exists():
            # Could be a worktree where .git is a file
            git_file = self.repo_path / ".git"
            if not git_file.is_file():
                raise GitError(
                    f"Not a git repository: {self.repo_path}",
                    details={"path": str(self.repo_path)},
                )

    def _run(
        self,
        *args: str,
        check: bool = True,
        capture: bool = True,
        timeout: int = 60,
    ) -> subprocess.CompletedProcess[str]:
        """Run a git command.

        Args:
            *args: Git command arguments
            check: Whether to raise on non-zero exit
            capture: Whether to capture output
            timeout: Timeout in seconds

        Returns:
            Completed process result

        Raises:
            GitError: If the command fails (when check=True) or times out
        """
        cmd = ["git", "-C", str(self.repo_path), *args]
        logger.debug(f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=capture,
                text=True,
                check=check,
                timeout=timeout,
            )
            return result
        except subprocess.TimeoutExpired as e:
            raise GitError(
                f"Git command timed out after {timeout}s: {' '.join(args)}",
                command=" ".join(cmd),
                exit_code=-1,
            ) from e
        except subprocess.CalledProcessError as e:
            raise GitError(
                f"Git command failed: {e.stderr.strip() if e.stderr else str(e)}",
                command=" ".join(cmd),
                exit_code=e.returncode,
            ) from e

    def current_branch(self) -> str:
        """Get the current branch name.

        Returns:
            Current branch name
        """
        result = self._run("rev-parse", "--abbrev-ref", "HEAD")
        return result.stdout.strip()

    def current_commit(self) -> str:
        """Get the current commit SHA.

        Returns:
            Full 40-character commit SHA
        """
        result = self._run("rev-parse", "HEAD")
        return result.stdout.strip()

    def has_changes(self) -> bool:
        """Check if there are uncommitted changes.

        Returns:
            True if there are uncommitted changes
        """
        result = self._run("status", "--porcelain")
        return bool(result.stdout.strip())
