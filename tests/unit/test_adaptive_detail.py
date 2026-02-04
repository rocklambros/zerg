"""Unit tests for adaptive detail management."""

import tempfile
from pathlib import Path

import pytest

from zerg.adaptive_detail import (
    AdaptiveDetailManager,
    AdaptiveMetrics,
    DirectoryMetrics,
    FileMetrics,
)
from zerg.config import PlanningConfig


class TestFileMetrics:
    """Tests for FileMetrics model."""

    def test_default_values(self) -> None:
        """Test default file metrics values."""
        metrics = FileMetrics()
        assert metrics.modification_count == 0
        assert metrics.last_modified == ""
        assert metrics.success_count == 0
        assert metrics.failure_count == 0

    def test_custom_values(self) -> None:
        """Test custom file metrics values."""
        metrics = FileMetrics(
            modification_count=5,
            last_modified="2025-01-01T12:00:00",
            success_count=3,
            failure_count=1,
        )
        assert metrics.modification_count == 5
        assert metrics.success_count == 3
        assert metrics.failure_count == 1


class TestDirectoryMetrics:
    """Tests for DirectoryMetrics model."""

    def test_default_values(self) -> None:
        """Test default directory metrics values."""
        metrics = DirectoryMetrics()
        assert metrics.task_count == 0
        assert metrics.success_count == 0
        assert metrics.failure_count == 0
        assert metrics.last_task_at == ""

    def test_success_rate_empty(self) -> None:
        """Test success rate with no tasks."""
        metrics = DirectoryMetrics()
        assert metrics.success_rate == 0.0

    def test_success_rate_all_success(self) -> None:
        """Test success rate with all successes."""
        metrics = DirectoryMetrics(success_count=5, failure_count=0)
        assert metrics.success_rate == 1.0

    def test_success_rate_all_failure(self) -> None:
        """Test success rate with all failures."""
        metrics = DirectoryMetrics(success_count=0, failure_count=5)
        assert metrics.success_rate == 0.0

    def test_success_rate_mixed(self) -> None:
        """Test success rate with mixed results."""
        metrics = DirectoryMetrics(success_count=8, failure_count=2)
        assert metrics.success_rate == 0.8


class TestAdaptiveMetrics:
    """Tests for AdaptiveMetrics model."""

    def test_default_values(self) -> None:
        """Test default adaptive metrics values."""
        metrics = AdaptiveMetrics()
        assert metrics.files == {}
        assert metrics.directories == {}
        assert metrics.last_updated == ""

    def test_with_data(self) -> None:
        """Test adaptive metrics with data."""
        metrics = AdaptiveMetrics(
            files={"src/main.py": FileMetrics(modification_count=3)},
            directories={"src": DirectoryMetrics(success_count=5)},
            last_updated="2025-01-01T12:00:00",
        )
        assert len(metrics.files) == 1
        assert len(metrics.directories) == 1


class TestAdaptiveDetailManager:
    """Tests for AdaptiveDetailManager class."""

    @pytest.fixture
    def temp_state_file(self) -> Path:
        """Create a temporary state file path."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            return Path(f.name)

    @pytest.fixture
    def config_high_thresholds(self) -> PlanningConfig:
        """Create config with high thresholds."""
        return PlanningConfig(
            adaptive_detail=True,
            adaptive_familiarity_threshold=5,
            adaptive_success_threshold=0.9,
        )

    @pytest.fixture
    def config_low_thresholds(self) -> PlanningConfig:
        """Create config with low thresholds."""
        return PlanningConfig(
            adaptive_detail=True,
            adaptive_familiarity_threshold=2,
            adaptive_success_threshold=0.5,
        )

    @pytest.fixture
    def config_disabled(self) -> PlanningConfig:
        """Create config with adaptive detail disabled."""
        return PlanningConfig(adaptive_detail=False)

    def test_init_creates_manager(self, temp_state_file: Path) -> None:
        """Test manager initialization."""
        manager = AdaptiveDetailManager(state_file=temp_state_file)
        assert manager._state_file == temp_state_file

    def test_init_with_config(self, temp_state_file: Path, config_high_thresholds: PlanningConfig) -> None:
        """Test manager initialization with custom config."""
        manager = AdaptiveDetailManager(
            state_file=temp_state_file,
            config=config_high_thresholds,
        )
        assert manager._config.adaptive_familiarity_threshold == 5

    def test_record_file_modification(self, temp_state_file: Path) -> None:
        """Test recording file modifications."""
        manager = AdaptiveDetailManager(state_file=temp_state_file)
        manager.record_file_modification("src/main.py")

        count = manager.get_file_modification_count("src/main.py")
        assert count == 1

    def test_record_multiple_modifications(self, temp_state_file: Path) -> None:
        """Test recording multiple modifications to same file."""
        manager = AdaptiveDetailManager(state_file=temp_state_file)

        for _ in range(5):
            manager.record_file_modification("src/main.py")

        count = manager.get_file_modification_count("src/main.py")
        assert count == 5

    def test_record_task_result_success(self, temp_state_file: Path) -> None:
        """Test recording successful task result."""
        manager = AdaptiveDetailManager(state_file=temp_state_file)
        manager.record_task_result(
            task_files=["src/main.py", "src/utils.py"],
            success=True,
        )

        file_metrics = manager.get_file_metrics("src/main.py")
        assert file_metrics is not None
        assert file_metrics.success_count == 1

        dir_metrics = manager.get_directory_metrics("src")
        assert dir_metrics is not None
        assert dir_metrics.success_count == 1
        assert dir_metrics.success_rate == 1.0

    def test_record_task_result_failure(self, temp_state_file: Path) -> None:
        """Test recording failed task result."""
        manager = AdaptiveDetailManager(state_file=temp_state_file)
        manager.record_task_result(
            task_files=["src/main.py"],
            success=False,
        )

        file_metrics = manager.get_file_metrics("src/main.py")
        assert file_metrics is not None
        assert file_metrics.failure_count == 1

        dir_metrics = manager.get_directory_metrics("src")
        assert dir_metrics is not None
        assert dir_metrics.failure_count == 1
        assert dir_metrics.success_rate == 0.0

    def test_record_task_result_mixed(self, temp_state_file: Path) -> None:
        """Test recording mixed task results."""
        manager = AdaptiveDetailManager(state_file=temp_state_file)

        # 4 successes, 1 failure
        for _ in range(4):
            manager.record_task_result(["src/main.py"], success=True)
        manager.record_task_result(["src/main.py"], success=False)

        dir_metrics = manager.get_directory_metrics("src")
        assert dir_metrics is not None
        assert dir_metrics.success_rate == 0.8

    def test_should_reduce_detail_disabled(self, temp_state_file: Path, config_disabled: PlanningConfig) -> None:
        """Test should_reduce_detail when adaptive detail is disabled."""
        manager = AdaptiveDetailManager(state_file=temp_state_file, config=config_disabled)

        # Even with high modification count, should not reduce
        for _ in range(10):
            manager.record_file_modification("src/main.py")

        result = manager.should_reduce_detail(["src/main.py"])
        assert result is False

    def test_should_reduce_detail_empty_files(self, temp_state_file: Path) -> None:
        """Test should_reduce_detail with empty file list."""
        manager = AdaptiveDetailManager(state_file=temp_state_file)
        result = manager.should_reduce_detail([])
        assert result is False

    def test_should_reduce_detail_by_familiarity(
        self, temp_state_file: Path, config_low_thresholds: PlanningConfig
    ) -> None:
        """Test should_reduce_detail based on familiarity threshold."""
        manager = AdaptiveDetailManager(state_file=temp_state_file, config=config_low_thresholds)

        # Threshold is 2, so after 2 modifications should reduce
        manager.record_file_modification("src/main.py")
        assert manager.should_reduce_detail(["src/main.py"]) is False

        manager.record_file_modification("src/main.py")
        assert manager.should_reduce_detail(["src/main.py"]) is True

    def test_should_reduce_detail_by_success_rate(
        self, temp_state_file: Path, config_low_thresholds: PlanningConfig
    ) -> None:
        """Test should_reduce_detail based on success rate threshold."""
        manager = AdaptiveDetailManager(state_file=temp_state_file, config=config_low_thresholds)

        # Threshold is 0.5, so need >= 50% success
        # First task: 100% success
        manager.record_task_result(["src/main.py"], success=True)
        assert manager.should_reduce_detail(["src/other.py"]) is True

    def test_should_reduce_detail_below_thresholds(
        self, temp_state_file: Path, config_high_thresholds: PlanningConfig
    ) -> None:
        """Test should_reduce_detail with values below thresholds."""
        manager = AdaptiveDetailManager(state_file=temp_state_file, config=config_high_thresholds)

        # Familiarity threshold is 5, success threshold is 0.9
        # Record 3 modifications (below threshold)
        for _ in range(3):
            manager.record_file_modification("src/main.py")

        # Record 3 success, 2 failure (60% success, below 90%)
        for _ in range(3):
            manager.record_task_result(["src/main.py"], success=True)
        for _ in range(2):
            manager.record_task_result(["src/main.py"], success=False)

        result = manager.should_reduce_detail(["src/main.py"])
        assert result is False

    def test_get_recommended_detail_level_no_reduction(self, temp_state_file: Path) -> None:
        """Test get_recommended_detail_level with no reduction needed."""
        manager = AdaptiveDetailManager(state_file=temp_state_file)

        level = manager.get_recommended_detail_level(["src/new_file.py"], "high")
        assert level == "high"

    def test_get_recommended_detail_level_with_reduction(
        self, temp_state_file: Path, config_low_thresholds: PlanningConfig
    ) -> None:
        """Test get_recommended_detail_level with reduction applied."""
        manager = AdaptiveDetailManager(state_file=temp_state_file, config=config_low_thresholds)

        # Meet familiarity threshold
        for _ in range(3):
            manager.record_file_modification("src/main.py")

        # Should reduce from high to medium
        level = manager.get_recommended_detail_level(["src/main.py"], "high")
        assert level == "medium"

    def test_get_recommended_detail_level_medium_to_standard(
        self, temp_state_file: Path, config_low_thresholds: PlanningConfig
    ) -> None:
        """Test reduction from medium to standard."""
        manager = AdaptiveDetailManager(state_file=temp_state_file, config=config_low_thresholds)

        # Meet familiarity threshold
        for _ in range(3):
            manager.record_file_modification("src/main.py")

        level = manager.get_recommended_detail_level(["src/main.py"], "medium")
        assert level == "standard"

    def test_get_recommended_detail_level_standard_no_change(
        self, temp_state_file: Path, config_low_thresholds: PlanningConfig
    ) -> None:
        """Test standard level cannot be reduced further."""
        manager = AdaptiveDetailManager(state_file=temp_state_file, config=config_low_thresholds)

        # Meet familiarity threshold
        for _ in range(3):
            manager.record_file_modification("src/main.py")

        level = manager.get_recommended_detail_level(["src/main.py"], "standard")
        assert level == "standard"

    def test_get_recommended_detail_level_disabled(
        self, temp_state_file: Path, config_disabled: PlanningConfig
    ) -> None:
        """Test get_recommended_detail_level when adaptive detail is disabled."""
        manager = AdaptiveDetailManager(state_file=temp_state_file, config=config_disabled)

        # Even with high modification count
        for _ in range(10):
            manager.record_file_modification("src/main.py")

        level = manager.get_recommended_detail_level(["src/main.py"], "high")
        assert level == "high"

    def test_persistence_across_instances(self, temp_state_file: Path) -> None:
        """Test that metrics persist across manager instances."""
        manager1 = AdaptiveDetailManager(state_file=temp_state_file)
        for _ in range(5):
            manager1.record_file_modification("src/main.py")

        # Create new manager with same state file
        manager2 = AdaptiveDetailManager(state_file=temp_state_file)
        count = manager2.get_file_modification_count("src/main.py")
        assert count == 5

    def test_get_metrics_summary(self, temp_state_file: Path, config_low_thresholds: PlanningConfig) -> None:
        """Test get_metrics_summary returns correct data."""
        manager = AdaptiveDetailManager(state_file=temp_state_file, config=config_low_thresholds)

        # Record some metrics
        for _ in range(3):
            manager.record_file_modification("src/main.py")
        manager.record_task_result(["src/main.py"], success=True)

        summary = manager.get_metrics_summary()

        assert summary["total_files_tracked"] == 1
        assert summary["total_directories_tracked"] == 1
        assert summary["total_modifications"] == 3
        assert summary["familiar_files"] == 1  # >= threshold of 2
        assert summary["average_success_rate"] == 1.0
        assert summary["familiarity_threshold"] == 2
        assert summary["success_threshold"] == 0.5
        assert summary["adaptive_detail_enabled"] is True

    def test_reset_metrics(self, temp_state_file: Path) -> None:
        """Test reset_metrics clears all data."""
        manager = AdaptiveDetailManager(state_file=temp_state_file)

        # Record some metrics
        for _ in range(5):
            manager.record_file_modification("src/main.py")
        manager.record_task_result(["src/main.py"], success=True)

        # Reset
        manager.reset_metrics()

        # Verify cleared
        assert manager.get_file_modification_count("src/main.py") == 0
        assert manager.get_file_metrics("src/main.py") is None
        assert manager.get_directory_metrics("src") is None

    def test_path_normalization(self, temp_state_file: Path) -> None:
        """Test that paths are normalized consistently."""
        manager = AdaptiveDetailManager(state_file=temp_state_file)

        # Use different path representations
        manager.record_file_modification("src/main.py")
        manager.record_file_modification(Path("src/main.py"))
        manager.record_file_modification("./src/main.py")

        # Should all count for same file
        count = manager.get_file_modification_count("src/main.py")
        assert count == 3

    def test_multiple_directories(self, temp_state_file: Path) -> None:
        """Test tracking across multiple directories."""
        manager = AdaptiveDetailManager(state_file=temp_state_file)

        manager.record_task_result(["src/main.py"], success=True)
        manager.record_task_result(["tests/test_main.py"], success=False)
        manager.record_task_result(["lib/utils.py"], success=True)

        src_metrics = manager.get_directory_metrics("src")
        tests_metrics = manager.get_directory_metrics("tests")
        lib_metrics = manager.get_directory_metrics("lib")

        assert src_metrics is not None and src_metrics.success_rate == 1.0
        assert tests_metrics is not None and tests_metrics.success_rate == 0.0
        assert lib_metrics is not None and lib_metrics.success_rate == 1.0

    def test_corrupted_state_file(self, temp_state_file: Path) -> None:
        """Test handling of corrupted state file."""
        # Write invalid JSON
        temp_state_file.write_text("invalid json {{{")

        # Should initialize with empty metrics instead of crashing
        manager = AdaptiveDetailManager(state_file=temp_state_file)
        summary = manager.get_metrics_summary()
        assert summary["total_files_tracked"] == 0

    def test_missing_parent_directory(self) -> None:
        """Test handling of missing parent directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "subdir" / "state.json"
            manager = AdaptiveDetailManager(state_file=state_file)

            # Should create directory when saving
            manager.record_file_modification("src/main.py")

            assert state_file.exists()

    def test_get_file_metrics_nonexistent(self, temp_state_file: Path) -> None:
        """Test get_file_metrics for nonexistent file."""
        manager = AdaptiveDetailManager(state_file=temp_state_file)
        metrics = manager.get_file_metrics("nonexistent.py")
        assert metrics is None

    def test_get_directory_metrics_nonexistent(self, temp_state_file: Path) -> None:
        """Test get_directory_metrics for nonexistent directory."""
        manager = AdaptiveDetailManager(state_file=temp_state_file)
        metrics = manager.get_directory_metrics("nonexistent")
        assert metrics is None

    def test_get_directory_success_rate_nonexistent(self, temp_state_file: Path) -> None:
        """Test get_directory_success_rate for nonexistent directory."""
        manager = AdaptiveDetailManager(state_file=temp_state_file)
        rate = manager.get_directory_success_rate("nonexistent")
        assert rate == 0.0

    def test_invalid_detail_level(self, temp_state_file: Path, config_low_thresholds: PlanningConfig) -> None:
        """Test handling of invalid detail level."""
        manager = AdaptiveDetailManager(state_file=temp_state_file, config=config_low_thresholds)

        # Invalid level should default to "high"
        level = manager.get_recommended_detail_level(["src/main.py"], "invalid")
        assert level == "high"

    def test_concurrent_modifications(self, temp_state_file: Path) -> None:
        """Test thread-safe modifications."""
        import threading

        manager = AdaptiveDetailManager(state_file=temp_state_file)
        threads: list[threading.Thread] = []

        def modify_files() -> None:
            for _ in range(100):
                manager.record_file_modification("src/main.py")

        # Create multiple threads
        for _ in range(5):
            t = threading.Thread(target=modify_files)
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Should have recorded all modifications
        count = manager.get_file_modification_count("src/main.py")
        assert count == 500
