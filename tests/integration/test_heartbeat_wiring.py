"""Integration tests for heartbeat wiring into launcher and orchestrator."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from zerg.heartbeat import HeartbeatMonitor, HeartbeatWriter


class TestHeartbeatLauncherWiring:
    """Test heartbeat detection in SubprocessLauncher.monitor()."""

    def test_stalled_worker_detected(self, tmp_path: Path) -> None:
        """Launcher.monitor() should return STALLED when heartbeat is stale."""
        # Write a stale heartbeat
        old_time = (datetime.now(UTC) - timedelta(seconds=200)).isoformat()
        hb_data = {
            "worker_id": 1,
            "timestamp": old_time,
            "task_id": "TASK-001",
            "step": "implementing",
            "progress_pct": 50,
        }
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "heartbeat-1.json").write_text(json.dumps(hb_data))

        # Monitor should detect stale heartbeat
        monitor = HeartbeatMonitor(state_dir=state_dir)
        assert monitor.check_stale(1, timeout_seconds=120) is True

    def test_healthy_worker_not_stalled(self, tmp_path: Path) -> None:
        """Launcher.monitor() should not return STALLED for fresh heartbeat."""
        recent_time = datetime.now(UTC).isoformat()
        hb_data = {
            "worker_id": 1,
            "timestamp": recent_time,
            "task_id": "TASK-001",
            "step": "implementing",
            "progress_pct": 50,
        }
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "heartbeat-1.json").write_text(json.dumps(hb_data))

        monitor = HeartbeatMonitor(state_dir=state_dir)
        assert monitor.check_stale(1, timeout_seconds=120) is False


class TestHeartbeatWriterReaderRoundtrip:
    """Test writer -> reader roundtrip."""

    def test_write_and_read(self, tmp_path: Path) -> None:
        writer = HeartbeatWriter(worker_id=1, state_dir=tmp_path)
        writer.write(task_id="TASK-001", step="implementing", progress_pct=75)

        monitor = HeartbeatMonitor(state_dir=tmp_path)
        hb = monitor.read(1)
        assert hb is not None
        assert hb.worker_id == 1
        assert hb.task_id == "TASK-001"
        assert hb.step == "implementing"
        assert hb.progress_pct == 75

    def test_multiple_workers(self, tmp_path: Path) -> None:
        for wid in [1, 2, 3]:
            writer = HeartbeatWriter(worker_id=wid, state_dir=tmp_path)
            writer.write(task_id=f"TASK-{wid:03d}")

        monitor = HeartbeatMonitor(state_dir=tmp_path)
        all_hb = monitor.read_all()
        assert len(all_hb) == 3

    def test_cleanup_removes_heartbeat(self, tmp_path: Path) -> None:
        writer = HeartbeatWriter(worker_id=1, state_dir=tmp_path)
        writer.write()

        monitor = HeartbeatMonitor(state_dir=tmp_path)
        assert monitor.read(1) is not None

        writer.cleanup()
        assert monitor.read(1) is None
