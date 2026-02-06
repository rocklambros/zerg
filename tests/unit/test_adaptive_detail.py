"""Unit tests for adaptive detail management — thinned Phase 4/5."""

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
    def test_default_values(self) -> None:
        m = FileMetrics()
        assert m.modification_count == 0 and m.success_count == 0


class TestDirectoryMetrics:
    @pytest.mark.parametrize(
        "success,failure,expected_rate",
        [(0, 0, 0.0), (5, 0, 1.0), (0, 5, 0.0), (8, 2, 0.8)],
    )
    def test_success_rate(self, success: int, failure: int, expected_rate: float) -> None:
        assert DirectoryMetrics(success_count=success, failure_count=failure).success_rate == expected_rate


class TestAdaptiveMetrics:
    def test_default_values(self) -> None:
        m = AdaptiveMetrics()
        assert m.files == {} and m.directories == {}


class TestAdaptiveDetailManager:
    @pytest.fixture
    def temp_state_file(self) -> Path:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            return Path(f.name)

    @pytest.fixture
    def config_low(self) -> PlanningConfig:
        return PlanningConfig(adaptive_detail=True, adaptive_familiarity_threshold=2, adaptive_success_threshold=0.5)

    @pytest.fixture
    def config_disabled(self) -> PlanningConfig:
        return PlanningConfig(adaptive_detail=False)

    def test_init_creates_manager(self, temp_state_file: Path) -> None:
        manager = AdaptiveDetailManager(state_file=temp_state_file)
        assert manager._state_file == temp_state_file

    def test_record_file_modification(self, temp_state_file: Path) -> None:
        manager = AdaptiveDetailManager(state_file=temp_state_file)
        manager.record_file_modification("src/main.py")
        assert manager.get_file_modification_count("src/main.py") == 1

    def test_record_task_result_success(self, temp_state_file: Path) -> None:
        manager = AdaptiveDetailManager(state_file=temp_state_file)
        manager.record_task_result(task_files=["src/main.py"], success=True)
        assert manager.get_file_metrics("src/main.py").success_count == 1
        assert manager.get_directory_metrics("src").success_rate == 1.0

    def test_record_task_result_failure(self, temp_state_file: Path) -> None:
        manager = AdaptiveDetailManager(state_file=temp_state_file)
        manager.record_task_result(task_files=["src/main.py"], success=False)
        assert manager.get_file_metrics("src/main.py").failure_count == 1

    def test_should_reduce_detail_disabled(self, temp_state_file: Path, config_disabled: PlanningConfig) -> None:
        manager = AdaptiveDetailManager(state_file=temp_state_file, config=config_disabled)
        for _ in range(10):
            manager.record_file_modification("src/main.py")
        assert manager.should_reduce_detail(["src/main.py"]) is False

    def test_should_reduce_detail_by_familiarity(self, temp_state_file: Path, config_low: PlanningConfig) -> None:
        manager = AdaptiveDetailManager(state_file=temp_state_file, config=config_low)
        manager.record_file_modification("src/main.py")
        assert manager.should_reduce_detail(["src/main.py"]) is False
        manager.record_file_modification("src/main.py")
        assert manager.should_reduce_detail(["src/main.py"]) is True

    def test_get_recommended_detail_level_with_reduction(
        self, temp_state_file: Path, config_low: PlanningConfig
    ) -> None:
        manager = AdaptiveDetailManager(state_file=temp_state_file, config=config_low)
        for _ in range(3):
            manager.record_file_modification("src/main.py")
        assert manager.get_recommended_detail_level(["src/main.py"], "high") == "medium"
        assert manager.get_recommended_detail_level(["src/main.py"], "medium") == "standard"
        assert manager.get_recommended_detail_level(["src/main.py"], "standard") == "standard"

    def test_persistence_across_instances(self, temp_state_file: Path) -> None:
        m1 = AdaptiveDetailManager(state_file=temp_state_file)
        for _ in range(5):
            m1.record_file_modification("src/main.py")
        m2 = AdaptiveDetailManager(state_file=temp_state_file)
        assert m2.get_file_modification_count("src/main.py") == 5

    def test_get_metrics_summary(self, temp_state_file: Path, config_low: PlanningConfig) -> None:
        manager = AdaptiveDetailManager(state_file=temp_state_file, config=config_low)
        for _ in range(3):
            manager.record_file_modification("src/main.py")
        manager.record_task_result(["src/main.py"], success=True)
        summary = manager.get_metrics_summary()
        assert summary["total_files_tracked"] == 1
        assert summary["familiar_files"] == 1

    def test_reset_metrics(self, temp_state_file: Path) -> None:
        manager = AdaptiveDetailManager(state_file=temp_state_file)
        for _ in range(5):
            manager.record_file_modification("src/main.py")
        manager.reset_metrics()
        assert manager.get_file_modification_count("src/main.py") == 0

    def test_corrupted_state_file(self, temp_state_file: Path) -> None:
        temp_state_file.write_text("invalid json {{{")
        manager = AdaptiveDetailManager(state_file=temp_state_file)
        assert manager.get_metrics_summary()["total_files_tracked"] == 0

    def test_get_nonexistent_metrics(self, temp_state_file: Path) -> None:
        manager = AdaptiveDetailManager(state_file=temp_state_file)
        assert manager.get_file_metrics("nonexistent.py") is None
        assert manager.get_directory_metrics("nonexistent") is None
        assert manager.get_directory_success_rate("nonexistent") == 0.0
