"""Adaptive detail level management for bite-sized planning.

Tracks file modification counts and task success rates to automatically
reduce detail level when developers demonstrate familiarity with certain
areas of the codebase.
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from zerg.config import PlanningConfig, ZergConfig
from zerg.logging import get_logger

logger = get_logger("adaptive_detail")

# Default state file location
DEFAULT_STATE_FILE = Path(".zerg/state/adaptive-detail.json")


class FileMetrics(BaseModel):
    """Metrics for a single file."""

    modification_count: int = Field(default=0, ge=0)
    last_modified: str = Field(default="")
    success_count: int = Field(default=0, ge=0)
    failure_count: int = Field(default=0, ge=0)


class DirectoryMetrics(BaseModel):
    """Aggregated metrics for a directory."""

    task_count: int = Field(default=0, ge=0)
    success_count: int = Field(default=0, ge=0)
    failure_count: int = Field(default=0, ge=0)
    last_task_at: str = Field(default="")

    @property
    def success_rate(self) -> float:
        """Calculate success rate for the directory.

        Returns:
            Success rate as float between 0.0 and 1.0
        """
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.success_count / total


class AdaptiveMetrics(BaseModel):
    """Complete adaptive detail metrics state."""

    files: dict[str, FileMetrics] = Field(default_factory=dict)
    directories: dict[str, DirectoryMetrics] = Field(default_factory=dict)
    last_updated: str = Field(default="")


class AdaptiveDetailManager:
    """Manages adaptive detail level based on developer familiarity metrics.

    Tracks:
    - File modification counts: How many times each file has been modified
    - Task success rates: Success/failure rates per directory

    Uses these metrics to determine when to reduce detail level for tasks,
    following the configured thresholds from PlanningConfig.
    """

    def __init__(
        self,
        state_file: Path | str | None = None,
        config: PlanningConfig | None = None,
    ) -> None:
        """Initialize adaptive detail manager.

        Args:
            state_file: Path to state file (defaults to .zerg/state/adaptive-detail.json)
            config: Planning configuration (loads from ZergConfig if not provided)
        """
        self._state_file = Path(state_file) if state_file else DEFAULT_STATE_FILE
        self._lock = threading.RLock()
        self._metrics: AdaptiveMetrics = AdaptiveMetrics()

        # Load or use provided config
        if config is None:
            try:
                zerg_config = ZergConfig.load()
                self._config = zerg_config.planning
            except Exception:
                # Use defaults if config can't be loaded
                self._config = PlanningConfig()
        else:
            self._config = config

        # Load existing metrics if available
        self._load()

    def _ensure_dir(self) -> None:
        """Ensure state directory exists."""
        self._state_file.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> None:
        """Load metrics from state file."""
        with self._lock:
            if not self._state_file.exists():
                self._metrics = AdaptiveMetrics()
                return

            try:
                with open(self._state_file) as f:
                    data = json.load(f)
                self._metrics = AdaptiveMetrics.model_validate(data)
                logger.debug(f"Loaded adaptive metrics from {self._state_file}")
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Failed to load adaptive metrics: {e}")
                self._metrics = AdaptiveMetrics()

    def _save(self) -> None:
        """Save metrics to state file."""
        with self._lock:
            self._ensure_dir()
            self._metrics.last_updated = datetime.now().isoformat()

            try:
                with open(self._state_file, "w") as f:
                    json.dump(self._metrics.model_dump(), f, indent=2)
                logger.debug(f"Saved adaptive metrics to {self._state_file}")
            except OSError as e:
                logger.error(f"Failed to save adaptive metrics: {e}")

    def record_file_modification(self, file_path: str | Path) -> None:
        """Record that a file was modified.

        Increments the modification count for the file.

        Args:
            file_path: Path to the modified file
        """
        file_key = str(Path(file_path))

        with self._lock:
            if file_key not in self._metrics.files:
                self._metrics.files[file_key] = FileMetrics()

            file_metrics = self._metrics.files[file_key]
            file_metrics.modification_count += 1
            file_metrics.last_modified = datetime.now().isoformat()

            logger.debug(f"File {file_key} modification count: {file_metrics.modification_count}")
            self._save()

    def record_task_result(
        self,
        task_files: list[str | Path],
        success: bool,
    ) -> None:
        """Record task completion result.

        Updates both file-level success counts and directory-level metrics.

        Args:
            task_files: Files involved in the task
            success: Whether the task succeeded
        """
        now = datetime.now().isoformat()
        directories_updated: set[str] = set()

        with self._lock:
            for file_path in task_files:
                file_key = str(Path(file_path))

                # Update file metrics
                if file_key not in self._metrics.files:
                    self._metrics.files[file_key] = FileMetrics()

                file_metrics = self._metrics.files[file_key]
                if success:
                    file_metrics.success_count += 1
                else:
                    file_metrics.failure_count += 1

                # Track directory for aggregate update
                dir_key = str(Path(file_path).parent)
                directories_updated.add(dir_key)

            # Update directory metrics
            for dir_key in directories_updated:
                if dir_key not in self._metrics.directories:
                    self._metrics.directories[dir_key] = DirectoryMetrics()

                dir_metrics = self._metrics.directories[dir_key]
                dir_metrics.task_count += 1
                dir_metrics.last_task_at = now
                if success:
                    dir_metrics.success_count += 1
                else:
                    dir_metrics.failure_count += 1

                logger.debug(f"Directory {dir_key} success rate: {dir_metrics.success_rate:.2f}")

            self._save()

    def get_file_modification_count(self, file_path: str | Path) -> int:
        """Get modification count for a file.

        Args:
            file_path: Path to the file

        Returns:
            Number of times the file has been modified
        """
        file_key = str(Path(file_path))

        with self._lock:
            file_metrics = self._metrics.files.get(file_key)
            return file_metrics.modification_count if file_metrics else 0

    def get_directory_success_rate(self, dir_path: str | Path) -> float:
        """Get success rate for a directory.

        Args:
            dir_path: Path to the directory

        Returns:
            Success rate as float between 0.0 and 1.0
        """
        dir_key = str(Path(dir_path))

        with self._lock:
            dir_metrics = self._metrics.directories.get(dir_key)
            return dir_metrics.success_rate if dir_metrics else 0.0

    def should_reduce_detail(
        self,
        task_files: list[str | Path],
    ) -> bool:
        """Determine if detail level should be reduced for a task.

        Checks both familiarity (modification count) and success rate thresholds.

        A task's detail should be reduced if:
        1. Adaptive detail is enabled in config
        2. AND either:
           a. Any file in the task has been modified >= familiarity_threshold times
           b. OR the directory has success rate >= success_threshold

        Args:
            task_files: Files involved in the task

        Returns:
            True if detail level should be reduced
        """
        if not self._config.adaptive_detail:
            return False

        if not task_files:
            return False

        familiarity_threshold = self._config.adaptive_familiarity_threshold
        success_threshold = self._config.adaptive_success_threshold

        with self._lock:
            # Check file familiarity
            for file_path in task_files:
                file_key = str(Path(file_path))
                file_metrics = self._metrics.files.get(file_key)

                if file_metrics:
                    if file_metrics.modification_count >= familiarity_threshold:
                        logger.debug(
                            f"Reducing detail: file {file_key} modified "
                            f"{file_metrics.modification_count} times "
                            f"(threshold: {familiarity_threshold})"
                        )
                        return True

            # Check directory success rate
            directories_checked: set[str] = set()
            for file_path in task_files:
                dir_key = str(Path(file_path).parent)
                if dir_key in directories_checked:
                    continue
                directories_checked.add(dir_key)

                dir_metrics = self._metrics.directories.get(dir_key)
                if dir_metrics:
                    if dir_metrics.success_rate >= success_threshold:
                        logger.debug(
                            f"Reducing detail: directory {dir_key} success rate "
                            f"{dir_metrics.success_rate:.2f} "
                            f"(threshold: {success_threshold})"
                        )
                        return True

            return False

    def get_recommended_detail_level(
        self,
        task_files: list[str | Path],
        requested_level: str = "high",
    ) -> str:
        """Get recommended detail level for a task.

        Based on familiarity metrics, may reduce the requested level.

        Args:
            task_files: Files involved in the task
            requested_level: Originally requested detail level

        Returns:
            Recommended detail level: "standard", "medium", or "high"
        """
        # Valid detail levels in order of increasing detail
        levels = ["standard", "medium", "high"]

        if requested_level not in levels:
            requested_level = "high"

        if not self._config.adaptive_detail:
            return requested_level

        if self.should_reduce_detail(task_files):
            current_idx = levels.index(requested_level)
            if current_idx > 0:
                reduced = levels[current_idx - 1]
                logger.info(f"Adaptive detail: reducing from '{requested_level}' to '{reduced}'")
                return reduced

        return requested_level

    def get_metrics_summary(self) -> dict[str, Any]:
        """Get summary of current adaptive metrics.

        Returns:
            Dictionary with metrics summary
        """
        with self._lock:
            total_files = len(self._metrics.files)
            total_dirs = len(self._metrics.directories)
            total_modifications = sum(f.modification_count for f in self._metrics.files.values())

            # Calculate average success rate across directories
            success_rates = [d.success_rate for d in self._metrics.directories.values() if d.task_count > 0]
            avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 0.0

            # Count files above familiarity threshold
            familiar_files = sum(
                1
                for f in self._metrics.files.values()
                if f.modification_count >= self._config.adaptive_familiarity_threshold
            )

            return {
                "total_files_tracked": total_files,
                "total_directories_tracked": total_dirs,
                "total_modifications": total_modifications,
                "familiar_files": familiar_files,
                "average_success_rate": round(avg_success_rate, 2),
                "familiarity_threshold": self._config.adaptive_familiarity_threshold,
                "success_threshold": self._config.adaptive_success_threshold,
                "adaptive_detail_enabled": self._config.adaptive_detail,
                "last_updated": self._metrics.last_updated,
            }

    def reset_metrics(self) -> None:
        """Reset all metrics to initial state."""
        with self._lock:
            self._metrics = AdaptiveMetrics()
            self._save()
            logger.info("Reset adaptive detail metrics")

    def get_file_metrics(self, file_path: str | Path) -> FileMetrics | None:
        """Get detailed metrics for a specific file.

        Args:
            file_path: Path to the file

        Returns:
            FileMetrics or None if not tracked
        """
        file_key = str(Path(file_path))
        with self._lock:
            return self._metrics.files.get(file_key)

    def get_directory_metrics(self, dir_path: str | Path) -> DirectoryMetrics | None:
        """Get detailed metrics for a specific directory.

        Args:
            dir_path: Path to the directory

        Returns:
            DirectoryMetrics or None if not tracked
        """
        dir_key = str(Path(dir_path))
        with self._lock:
            return self._metrics.directories.get(dir_key)
