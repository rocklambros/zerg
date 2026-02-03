"""Tests for zerg.diagnostics.log_correlator."""

from __future__ import annotations

import json
from pathlib import Path

from zerg.diagnostics.log_analyzer import LogPattern
from zerg.diagnostics.log_correlator import (
    CrossWorkerCorrelator,
    ErrorEvolutionTracker,
    LogCorrelationEngine,
    TemporalClusterer,
    TimelineBuilder,
)
from zerg.diagnostics.types import TimelineEvent


# ---------------------------------------------------------------------------
# TestTimelineBuilder
# ---------------------------------------------------------------------------
class TestTimelineBuilder:
    """Tests for TimelineBuilder."""

    def test_build_empty_dir(self, tmp_path: Path) -> None:
        """Empty logs directory returns empty list."""
        builder = TimelineBuilder()
        assert builder.build(tmp_path) == []

    def test_build_nonexistent_dir(self, tmp_path: Path) -> None:
        """Nonexistent directory returns empty list."""
        missing = tmp_path / "does_not_exist"
        builder = TimelineBuilder()
        assert builder.build(missing) == []

    def test_build_plaintext_logs(self, tmp_path: Path) -> None:
        """Plaintext logs with error lines produce TimelineEvent objects."""
        log = tmp_path / "worker-0.stderr.log"
        log.write_text(
            "2026-01-30T10:00:00 error: something failed\n"
            "2026-01-30T10:00:01 info: all good\n"
            "2026-01-30T10:00:02 fatal crash detected\n",
        )
        builder = TimelineBuilder()
        events = builder.build(tmp_path)

        assert len(events) == 3
        assert all(isinstance(e, TimelineEvent) for e in events)
        assert events[0].worker_id == 0
        # First and third lines should be classified as errors
        assert events[0].event_type == "error"
        assert events[2].event_type == "error"

    def test_build_jsonl_logs(self, tmp_path: Path) -> None:
        """JSONL-formatted log lines are parsed correctly."""
        records = [
            {"timestamp": "2026-01-30T10:00:00", "level": "error", "message": "fail"},
            {"timestamp": "2026-01-30T10:00:01", "level": "info", "message": "ok"},
        ]
        log = tmp_path / "worker-0.stderr.log"
        log.write_text("\n".join(json.dumps(r) for r in records) + "\n")

        builder = TimelineBuilder()
        events = builder.build(tmp_path)

        assert len(events) == 2
        assert events[0].event_type == "error"
        assert events[0].message == "fail"
        assert events[1].event_type == "info"
        assert events[1].message == "ok"

    def test_build_multiple_workers(self, tmp_path: Path) -> None:
        """Events from multiple worker logs are all present."""
        (tmp_path / "worker-0.stderr.log").write_text("2026-01-30T09:00:00 error from worker 0\n")
        (tmp_path / "worker-1.stderr.log").write_text("2026-01-30T09:00:01 error from worker 1\n")

        builder = TimelineBuilder()
        events = builder.build(tmp_path)

        worker_ids = {e.worker_id for e in events}
        assert worker_ids == {0, 1}
        assert len(events) == 2

    def test_build_sorted_output(self, tmp_path: Path) -> None:
        """Returned events are sorted by timestamp."""
        # Write worker-1 with earlier timestamp, worker-0 with later
        (tmp_path / "worker-0.stderr.log").write_text("2026-01-30T12:00:00 late error\n")
        (tmp_path / "worker-1.stderr.log").write_text("2026-01-30T08:00:00 early error\n")

        builder = TimelineBuilder()
        events = builder.build(tmp_path)

        timestamps = [e.timestamp for e in events]
        assert timestamps == sorted(timestamps)
        assert events[0].worker_id == 1  # earlier timestamp


# ---------------------------------------------------------------------------
# TestTemporalClusterer
# ---------------------------------------------------------------------------
class TestTemporalClusterer:
    """Tests for TemporalClusterer."""

    def test_cluster_empty(self) -> None:
        """Empty events list returns empty clusters."""
        clusterer = TemporalClusterer()
        assert clusterer.cluster([]) == []

    def test_cluster_single_event(self) -> None:
        """Single event returns one cluster with one event."""
        event = TimelineEvent(
            timestamp="2026-01-30T10:00:00",
            worker_id=0,
            event_type="error",
            message="boom",
        )
        clusterer = TemporalClusterer()
        clusters = clusterer.cluster([event])

        assert len(clusters) == 1
        assert len(clusters[0]) == 1
        assert clusters[0][0] is event

    def test_cluster_within_window(self) -> None:
        """Two events close together end up in one cluster."""
        e1 = TimelineEvent(
            timestamp="2026-01-30T10:00:00",
            worker_id=0,
            event_type="error",
            message="a",
        )
        e2 = TimelineEvent(
            timestamp="2026-01-30T10:00:03",
            worker_id=1,
            event_type="error",
            message="b",
        )
        clusterer = TemporalClusterer()
        clusters = clusterer.cluster([e1, e2], window_seconds=5.0)

        assert len(clusters) == 1
        assert len(clusters[0]) == 2

    def test_cluster_outside_window(self) -> None:
        """Two events far apart produce two clusters."""
        e1 = TimelineEvent(
            timestamp="2026-01-30T10:00:00",
            worker_id=0,
            event_type="error",
            message="a",
        )
        e2 = TimelineEvent(
            timestamp="2026-01-30T10:05:00",
            worker_id=1,
            event_type="error",
            message="b",
        )
        clusterer = TemporalClusterer()
        clusters = clusterer.cluster([e1, e2], window_seconds=5.0)

        assert len(clusters) == 2

    def test_cluster_synthetic_timestamps(self) -> None:
        """Events with line-based synthetic timestamps cluster by proximity."""
        e1 = TimelineEvent(
            timestamp="line:00000001",
            worker_id=0,
            event_type="error",
            message="a",
        )
        e2 = TimelineEvent(
            timestamp="line:00000005",
            worker_id=0,
            event_type="error",
            message="b",
        )
        e3 = TimelineEvent(
            timestamp="line:00000050",
            worker_id=0,
            event_type="error",
            message="c",
        )
        clusterer = TemporalClusterer()
        clusters = clusterer.cluster([e1, e2, e3])

        # e1 and e2 within 10 lines -> same cluster; e3 far away -> separate
        assert len(clusters) == 2
        assert len(clusters[0]) == 2
        assert len(clusters[1]) == 1


# ---------------------------------------------------------------------------
# TestCrossWorkerCorrelator
# ---------------------------------------------------------------------------
class TestCrossWorkerCorrelator:
    """Tests for CrossWorkerCorrelator."""

    def test_correlate_similar_errors(self) -> None:
        """Similar error messages across different workers are correlated."""
        e1 = TimelineEvent(
            timestamp="2026-01-30T10:00:00",
            worker_id=0,
            event_type="error",
            message="Connection refused to database server host",
        )
        e2 = TimelineEvent(
            timestamp="2026-01-30T10:00:01",
            worker_id=1,
            event_type="error",
            message="Connection refused to database server endpoint",
        )
        correlator = CrossWorkerCorrelator()
        results = correlator.correlate([e1, e2])

        assert len(results) >= 1
        ev_a, ev_b, sim = results[0]
        assert sim >= 0.5
        assert {ev_a.worker_id, ev_b.worker_id} == {0, 1}

    def test_correlate_different_errors(self) -> None:
        """Completely different error messages produce no correlations."""
        e1 = TimelineEvent(
            timestamp="2026-01-30T10:00:00",
            worker_id=0,
            event_type="error",
            message="alpha beta gamma delta",
        )
        e2 = TimelineEvent(
            timestamp="2026-01-30T10:00:01",
            worker_id=1,
            event_type="error",
            message="epsilon zeta eta theta",
        )
        correlator = CrossWorkerCorrelator()
        results = correlator.correlate([e1, e2])

        assert len(results) == 0

    def test_correlate_same_worker(self) -> None:
        """Events from the same worker are NOT correlated with each other."""
        e1 = TimelineEvent(
            timestamp="2026-01-30T10:00:00",
            worker_id=0,
            event_type="error",
            message="Connection refused to database server host",
        )
        e2 = TimelineEvent(
            timestamp="2026-01-30T10:00:01",
            worker_id=0,
            event_type="error",
            message="Connection refused to database server host",
        )
        correlator = CrossWorkerCorrelator()
        results = correlator.correlate([e1, e2])

        assert len(results) == 0

    def test_correlate_empty(self) -> None:
        """Empty events list returns empty correlations."""
        correlator = CrossWorkerCorrelator()
        assert correlator.correlate([]) == []


# ---------------------------------------------------------------------------
# TestErrorEvolutionTracker
# ---------------------------------------------------------------------------
class TestErrorEvolutionTracker:
    """Tests for ErrorEvolutionTracker."""

    def test_track_empty(self) -> None:
        """Empty patterns list returns empty evolution list."""
        tracker = ErrorEvolutionTracker()
        assert tracker.track([]) == []

    def test_track_single_pattern(self) -> None:
        """Single LogPattern returns one evolution entry with trending info."""
        pat = LogPattern(
            pattern="Error: foo",
            count=5,
            first_seen="1",
            last_seen="10",
            sample_lines=["Error: foo"],
            worker_ids=[0, 1],
        )
        tracker = ErrorEvolutionTracker()
        results = tracker.track([pat])

        assert len(results) == 1
        evo = results[0]
        assert evo["pattern"] == "Error: foo"
        assert evo["count"] == 5
        assert evo["workers_affected"] == 2
        assert evo["first_seen"] == "1"
        assert evo["last_seen"] == "10"
        assert "trending" in evo

    def test_track_multiple_patterns(self) -> None:
        """Multiple LogPatterns return multiple evolution entries."""
        patterns = [
            LogPattern(
                pattern="Error: alpha",
                count=3,
                first_seen="1",
                last_seen="5",
                sample_lines=["Error: alpha"],
                worker_ids=[0],
            ),
            LogPattern(
                pattern="Error: beta",
                count=10,
                first_seen="1",
                last_seen="50",
                sample_lines=["Error: beta"],
                worker_ids=[0, 1, 2],
            ),
        ]
        tracker = ErrorEvolutionTracker()
        results = tracker.track(patterns)

        assert len(results) == 2
        assert results[0]["pattern"] == "Error: alpha"
        assert results[1]["pattern"] == "Error: beta"
        # High count across 3+ workers should be increasing
        assert results[1]["trending"] == "increasing"


# ---------------------------------------------------------------------------
# TestLogCorrelationEngine
# ---------------------------------------------------------------------------
class TestLogCorrelationEngine:
    """Tests for LogCorrelationEngine."""

    def test_analyze_with_logs(self, tmp_path: Path) -> None:
        """Analyze with worker logs returns dict with expected keys."""
        (tmp_path / "worker-0.stderr.log").write_text(
            "2026-01-30T10:00:00 error: connection refused\n2026-01-30T10:00:01 info: retrying\n"
        )
        (tmp_path / "worker-1.stderr.log").write_text("2026-01-30T10:00:02 error: connection refused to host\n")

        engine = LogCorrelationEngine(logs_dir=tmp_path)
        result = engine.analyze()

        expected_keys = {"timeline", "clusters", "correlations", "evolution", "evidence"}
        assert set(result.keys()) == expected_keys
        assert len(result["timeline"]) >= 2

    def test_analyze_no_logs(self, tmp_path: Path) -> None:
        """Analyze with empty directory returns dict with empty lists."""
        engine = LogCorrelationEngine(logs_dir=tmp_path)
        result = engine.analyze()

        assert set(result.keys()) == {
            "timeline",
            "clusters",
            "correlations",
            "evolution",
            "evidence",
        }
        assert result["timeline"] == []
        assert result["clusters"] == []
        assert result["correlations"] == []

    def test_analyze_specific_worker(self, tmp_path: Path) -> None:
        """Analyze with worker_id filters results to that worker."""
        (tmp_path / "worker-0.stderr.log").write_text("2026-01-30T10:00:00 error: from worker 0\n")
        (tmp_path / "worker-1.stderr.log").write_text("2026-01-30T10:00:01 error: from worker 1\n")

        engine = LogCorrelationEngine(logs_dir=tmp_path)
        result = engine.analyze(worker_id=0)

        # Timeline should only have worker 0 events
        for event_dict in result["timeline"]:
            assert event_dict["worker_id"] == 0
