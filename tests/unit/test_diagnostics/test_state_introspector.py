"""Tests for ZergStateIntrospector and ZergHealthReport."""

from __future__ import annotations

import json
from pathlib import Path

from zerg.diagnostics.state_introspector import ZergHealthReport, ZergStateIntrospector


class TestZergHealthReport:
    """Tests for ZergHealthReport dataclass."""

    def test_default_values(self) -> None:
        report = ZergHealthReport(feature="test", state_exists=True, total_tasks=0)
        assert report.feature == "test"
        assert report.task_summary == {}
        assert report.worker_summary == {}
        assert report.failed_tasks == []
        assert report.stale_tasks == []
        assert report.recent_errors == []
        assert report.current_level == 0
        assert report.is_paused is False
        assert report.global_error is None

    def test_to_dict(self) -> None:
        report = ZergHealthReport(
            feature="auth",
            state_exists=True,
            total_tasks=5,
            task_summary={"complete": 3, "failed": 2},
            current_level=2,
        )
        d = report.to_dict()
        assert d["feature"] == "auth"
        assert d["total_tasks"] == 5
        assert d["task_summary"] == {"complete": 3, "failed": 2}
        assert d["current_level"] == 2

    def test_to_dict_with_global_error(self) -> None:
        report = ZergHealthReport(
            feature="x",
            state_exists=True,
            total_tasks=0,
            global_error="Crash",
        )
        d = report.to_dict()
        assert d["global_error"] == "Crash"


class TestZergStateIntrospector:
    """Tests for ZergStateIntrospector."""

    def test_find_latest_feature_no_dir(self, tmp_path: Path) -> None:
        introspector = ZergStateIntrospector(state_dir=tmp_path / "nonexistent")
        assert introspector.find_latest_feature() is None

    def test_find_latest_feature_empty_dir(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        introspector = ZergStateIntrospector(state_dir=state_dir)
        assert introspector.find_latest_feature() is None

    def test_find_latest_feature(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "old-feature.json").write_text("{}")
        (state_dir / "new-feature.json").write_text("{}")
        introspector = ZergStateIntrospector(state_dir=state_dir)
        result = introspector.find_latest_feature()
        assert result is not None
        assert result in ("old-feature", "new-feature")

    def test_find_latest_feature_skips_backup(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "feat.json.bak").write_text("{}")
        introspector = ZergStateIntrospector(state_dir=state_dir)
        assert introspector.find_latest_feature() is None

    def test_get_health_report_missing_file(self, tmp_path: Path) -> None:
        introspector = ZergStateIntrospector(state_dir=tmp_path)
        report = introspector.get_health_report("missing")
        assert report.state_exists is False
        assert report.total_tasks == 0

    def test_get_health_report_corrupt_json(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "bad.json").write_text("{invalid json")
        introspector = ZergStateIntrospector(state_dir=state_dir)
        report = introspector.get_health_report("bad")
        assert report.state_exists is True
        assert "Corrupt" in (report.global_error or "")

    def test_get_health_report_basic(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        state = {
            "tasks": {
                "T1": {"status": "complete"},
                "T2": {"status": "complete"},
                "T3": {"status": "failed", "error": "build failed", "retry_count": 1},
            },
            "workers": {
                "1": {"status": "ready"},
                "2": {"status": "crashed"},
            },
            "current_level": 2,
            "paused": False,
        }
        (state_dir / "feat.json").write_text(json.dumps(state))
        introspector = ZergStateIntrospector(state_dir=state_dir)
        report = introspector.get_health_report("feat")

        assert report.state_exists is True
        assert report.total_tasks == 3
        assert report.task_summary == {"complete": 2, "failed": 1}
        assert len(report.failed_tasks) == 1
        assert report.failed_tasks[0]["task_id"] == "T3"
        assert report.failed_tasks[0]["error"] == "build failed"
        assert report.worker_summary == {"1": "ready", "2": "crashed"}
        assert report.current_level == 2
        assert report.is_paused is False

    def test_get_health_report_stale_tasks(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        state = {
            "tasks": {
                "T1": {"status": "in_progress", "worker_id": 1},
                "T2": {"status": "claimed", "worker_id": 2},
                "T3": {"status": "complete"},
            },
            "workers": {},
        }
        (state_dir / "feat.json").write_text(json.dumps(state))
        introspector = ZergStateIntrospector(state_dir=state_dir)
        report = introspector.get_health_report("feat")

        assert len(report.stale_tasks) == 2

    def test_get_health_report_deduped_errors(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        state = {
            "tasks": {
                "T1": {"status": "failed", "error": "same error"},
                "T2": {"status": "failed", "error": "same error"},
                "T3": {"status": "failed", "error": "different error"},
            },
            "workers": {},
        }
        (state_dir / "feat.json").write_text(json.dumps(state))
        introspector = ZergStateIntrospector(state_dir=state_dir)
        report = introspector.get_health_report("feat")

        assert len(report.recent_errors) == 2

    def test_get_health_report_global_error(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        state = {"tasks": {}, "workers": {}, "error": "Global crash"}
        (state_dir / "feat.json").write_text(json.dumps(state))
        introspector = ZergStateIntrospector(state_dir=state_dir)
        report = introspector.get_health_report("feat")

        assert report.global_error == "Global crash"

    def test_get_health_report_worker_string_status(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        state = {"tasks": {}, "workers": {"1": "running"}}
        (state_dir / "feat.json").write_text(json.dumps(state))
        introspector = ZergStateIntrospector(state_dir=state_dir)
        report = introspector.get_health_report("feat")

        assert report.worker_summary == {"1": "running"}

    def test_get_failed_task_details(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        state = {
            "tasks": {
                "T1": {"status": "failed", "error": "err1"},
                "T2": {"status": "complete"},
            },
            "workers": {},
        }
        (state_dir / "feat.json").write_text(json.dumps(state))
        introspector = ZergStateIntrospector(state_dir=state_dir)
        details = introspector.get_failed_task_details("feat")

        assert len(details) == 1
        assert details[0]["error"] == "err1"

    def test_get_worker_logs(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "worker-1.stdout.log").write_text("line1\nline2\nline3")
        (logs_dir / "worker-1.stderr.log").write_text("err1\nerr2")

        introspector = ZergStateIntrospector(state_dir=tmp_path, logs_dir=logs_dir)
        logs = introspector.get_worker_logs(1, lines=2)

        assert "line2" in logs["stdout"]
        assert "line3" in logs["stdout"]
        assert "err1" in logs["stderr"]

    def test_get_worker_logs_missing(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        introspector = ZergStateIntrospector(state_dir=tmp_path, logs_dir=logs_dir)
        logs = introspector.get_worker_logs(99)

        assert logs["stdout"] == ""
        assert logs["stderr"] == ""

    def test_detect_state_corruption_no_state(self, tmp_path: Path) -> None:
        introspector = ZergStateIntrospector(state_dir=tmp_path)
        issues = introspector.detect_state_corruption("missing")
        assert any("not found" in i.lower() for i in issues)

    def test_detect_state_corruption_corrupt_json(self, tmp_path: Path) -> None:
        (tmp_path / "bad.json").write_text("{{bad")
        introspector = ZergStateIntrospector(state_dir=tmp_path)
        issues = introspector.detect_state_corruption("bad")
        assert any("parse" in i.lower() for i in issues)

    def test_detect_state_corruption_no_graph(self, tmp_path: Path) -> None:
        (tmp_path / "feat.json").write_text(json.dumps({"tasks": {"T1": {}}}))
        introspector = ZergStateIntrospector(state_dir=tmp_path)
        issues = introspector.detect_state_corruption("feat")
        assert any("graph not found" in i.lower() for i in issues)

    def test_detect_state_corruption_with_graph(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "feat.json").write_text(json.dumps({"tasks": {"T1": {}, "T2": {}}}))

        # Create task graph in expected location
        graph_dir = Path(".gsd/specs/feat")
        graph_dir.mkdir(parents=True, exist_ok=True)
        graph_file = graph_dir / "task-graph.json"
        try:
            graph_file.write_text(json.dumps({"tasks": [{"id": "T1"}, {"id": "T3"}]}))
            introspector = ZergStateIntrospector(state_dir=state_dir)
            issues = introspector.detect_state_corruption("feat")

            # T2 in state but not graph, T3 in graph but not state
            assert any("T2" in i for i in issues)
            assert any("T3" in i for i in issues)
        finally:
            # Clean up
            if graph_file.exists():
                graph_file.unlink()
            if graph_dir.exists():
                import contextlib

                with contextlib.suppress(OSError):
                    graph_dir.rmdir()
