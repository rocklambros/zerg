"""Tests for ZERG heartbeat module."""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from zerg.heartbeat import Heartbeat, HeartbeatMonitor, HeartbeatWriter


class TestHeartbeat:
    """Tests for Heartbeat dataclass."""

    def test_creation(self) -> None:
        hb = Heartbeat(
            worker_id=1,
            timestamp="2026-02-02T10:00:00+00:00",
            task_id="TASK-001",
            step="implementing",
            progress_pct=50,
        )
        assert hb.worker_id == 1
        assert hb.task_id == "TASK-001"
        assert hb.step == "implementing"
        assert hb.progress_pct == 50

    def test_to_dict(self) -> None:
        hb = Heartbeat(
            worker_id=1,
            timestamp="2026-02-02T10:00:00+00:00",
            task_id=None,
            step="idle",
            progress_pct=0,
        )
        d = hb.to_dict()
        assert d["worker_id"] == 1
        assert d["task_id"] is None
        assert d["step"] == "idle"

    def test_from_dict(self) -> None:
        data = {
            "worker_id": 2,
            "timestamp": "2026-02-02T10:00:00+00:00",
            "task_id": "TASK-002",
            "step": "verifying_tier1",
            "progress_pct": 75,
        }
        hb = Heartbeat.from_dict(data)
        assert hb.worker_id == 2
        assert hb.task_id == "TASK-002"
        assert hb.progress_pct == 75

    def test_is_stale_true(self) -> None:
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=200)).isoformat()
        hb = Heartbeat(worker_id=1, timestamp=old_time, task_id=None, step="idle", progress_pct=0)
        assert hb.is_stale(120) is True

    def test_is_stale_false(self) -> None:
        recent = datetime.now(timezone.utc).isoformat()
        hb = Heartbeat(worker_id=1, timestamp=recent, task_id=None, step="idle", progress_pct=0)
        assert hb.is_stale(120) is False

    def test_is_stale_invalid_timestamp(self) -> None:
        hb = Heartbeat(worker_id=1, timestamp="invalid", task_id=None, step="idle", progress_pct=0)
        assert hb.is_stale(120) is True


class TestHeartbeatWriter:
    """Tests for HeartbeatWriter."""

    def test_write(self, tmp_path: Path) -> None:
        writer = HeartbeatWriter(worker_id=1, state_dir=tmp_path)
        hb = writer.write(task_id="TASK-001", step="implementing", progress_pct=50)
        assert hb.worker_id == 1
        assert hb.task_id == "TASK-001"

        # File should exist
        path = tmp_path / "heartbeat-1.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["worker_id"] == 1
        assert data["task_id"] == "TASK-001"

    def test_write_clamps_progress(self, tmp_path: Path) -> None:
        writer = HeartbeatWriter(worker_id=1, state_dir=tmp_path)
        hb = writer.write(progress_pct=150)
        assert hb.progress_pct == 100

        hb = writer.write(progress_pct=-10)
        assert hb.progress_pct == 0

    def test_cleanup(self, tmp_path: Path) -> None:
        writer = HeartbeatWriter(worker_id=1, state_dir=tmp_path)
        writer.write()
        assert writer.heartbeat_path.exists()
        writer.cleanup()
        assert not writer.heartbeat_path.exists()


class TestHeartbeatMonitor:
    """Tests for HeartbeatMonitor."""

    def test_read_existing(self, tmp_path: Path) -> None:
        # Write a heartbeat manually
        data = {
            "worker_id": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_id": "TASK-001",
            "step": "implementing",
            "progress_pct": 50,
        }
        (tmp_path / "heartbeat-1.json").write_text(json.dumps(data))

        monitor = HeartbeatMonitor(state_dir=tmp_path)
        hb = monitor.read(1)
        assert hb is not None
        assert hb.worker_id == 1
        assert hb.task_id == "TASK-001"

    def test_read_nonexistent(self, tmp_path: Path) -> None:
        monitor = HeartbeatMonitor(state_dir=tmp_path)
        assert monitor.read(99) is None

    def test_read_all(self, tmp_path: Path) -> None:
        now = datetime.now(timezone.utc).isoformat()
        for wid in [1, 2, 3]:
            data = {"worker_id": wid, "timestamp": now, "task_id": None, "step": "idle", "progress_pct": 0}
            (tmp_path / f"heartbeat-{wid}.json").write_text(json.dumps(data))

        monitor = HeartbeatMonitor(state_dir=tmp_path)
        all_hb = monitor.read_all()
        assert len(all_hb) == 3
        assert set(all_hb.keys()) == {1, 2, 3}

    def test_check_stale(self, tmp_path: Path) -> None:
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=200)).isoformat()
        data = {"worker_id": 1, "timestamp": old_time, "task_id": None, "step": "idle", "progress_pct": 0}
        (tmp_path / "heartbeat-1.json").write_text(json.dumps(data))

        monitor = HeartbeatMonitor(state_dir=tmp_path)
        assert monitor.check_stale(1, timeout_seconds=120) is True

    def test_get_stalled_workers(self, tmp_path: Path) -> None:
        now = datetime.now(timezone.utc)
        old_time = (now - timedelta(seconds=200)).isoformat()
        recent_time = now.isoformat()

        data1 = {"worker_id": 1, "timestamp": old_time, "task_id": None, "step": "idle", "progress_pct": 0}
        data2 = {"worker_id": 2, "timestamp": recent_time, "task_id": None, "step": "idle", "progress_pct": 0}
        (tmp_path / "heartbeat-1.json").write_text(json.dumps(data1))
        (tmp_path / "heartbeat-2.json").write_text(json.dumps(data2))

        monitor = HeartbeatMonitor(state_dir=tmp_path)
        stalled = monitor.get_stalled_workers([1, 2], timeout_seconds=120)
        assert stalled == [1]

    def test_init_with_custom_stale_timeout(self, tmp_path: Path) -> None:
        """Test HeartbeatMonitor with custom stale timeout."""
        monitor = HeartbeatMonitor(state_dir=tmp_path, stale_timeout_seconds=60)
        assert monitor.stale_timeout_seconds == 60

    def test_init_default_stale_timeout(self, tmp_path: Path) -> None:
        """Test HeartbeatMonitor uses default stale timeout."""
        monitor = HeartbeatMonitor(state_dir=tmp_path)
        assert monitor.stale_timeout_seconds == HeartbeatMonitor.DEFAULT_STALE_TIMEOUT_SECONDS
        assert monitor.stale_timeout_seconds == 120

    def test_check_stale_uses_configured_timeout(self, tmp_path: Path) -> None:
        """Test check_stale uses configured timeout when not provided."""
        # Heartbeat 150 seconds old
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=150)).isoformat()
        data = {"worker_id": 1, "timestamp": old_time, "task_id": None, "step": "idle", "progress_pct": 0}
        (tmp_path / "heartbeat-1.json").write_text(json.dumps(data))

        # With 120s timeout (default) - should be stale
        monitor_120 = HeartbeatMonitor(state_dir=tmp_path, stale_timeout_seconds=120)
        assert monitor_120.check_stale(1) is True

        # With 200s timeout - should NOT be stale
        monitor_200 = HeartbeatMonitor(state_dir=tmp_path, stale_timeout_seconds=200)
        assert monitor_200.check_stale(1) is False

    def test_check_stale_explicit_override(self, tmp_path: Path) -> None:
        """Test check_stale explicit timeout_seconds overrides configured."""
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=150)).isoformat()
        data = {"worker_id": 1, "timestamp": old_time, "task_id": None, "step": "idle", "progress_pct": 0}
        (tmp_path / "heartbeat-1.json").write_text(json.dumps(data))

        # Configured for 200s (not stale), but override with 100s (stale)
        monitor = HeartbeatMonitor(state_dir=tmp_path, stale_timeout_seconds=200)
        assert monitor.check_stale(1) is False  # Using configured
        assert monitor.check_stale(1, timeout_seconds=100) is True  # Override

    def test_get_stalled_workers_uses_configured_timeout(self, tmp_path: Path) -> None:
        """Test get_stalled_workers uses configured timeout when not provided."""
        now = datetime.now(timezone.utc)
        # Worker 1: 150s old (stale at 120s, not stale at 200s)
        # Worker 2: fresh
        old_time = (now - timedelta(seconds=150)).isoformat()
        recent_time = now.isoformat()

        data1 = {"worker_id": 1, "timestamp": old_time, "task_id": None, "step": "idle", "progress_pct": 0}
        data2 = {"worker_id": 2, "timestamp": recent_time, "task_id": None, "step": "idle", "progress_pct": 0}
        (tmp_path / "heartbeat-1.json").write_text(json.dumps(data1))
        (tmp_path / "heartbeat-2.json").write_text(json.dumps(data2))

        # With 120s timeout - worker 1 is stale
        monitor_120 = HeartbeatMonitor(state_dir=tmp_path, stale_timeout_seconds=120)
        assert monitor_120.get_stalled_workers([1, 2]) == [1]

        # With 200s timeout - no workers are stale
        monitor_200 = HeartbeatMonitor(state_dir=tmp_path, stale_timeout_seconds=200)
        assert monitor_200.get_stalled_workers([1, 2]) == []

    def test_from_config(self, tmp_path: Path) -> None:
        """Test HeartbeatMonitor.from_config factory method."""
        from zerg.config import HeartbeatConfig

        config = HeartbeatConfig(stall_timeout_seconds=90)
        monitor = HeartbeatMonitor.from_config(config, state_dir=tmp_path)
        assert monitor.stale_timeout_seconds == 90
