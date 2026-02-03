"""Tests for ZERG escalation module."""

import json
from pathlib import Path

from zerg.escalation import Escalation, EscalationMonitor, EscalationWriter


class TestEscalation:
    """Tests for Escalation dataclass."""

    def test_creation(self) -> None:
        esc = Escalation(
            worker_id=1,
            task_id="TASK-001",
            timestamp="2026-02-02T10:00:00Z",
            category="ambiguous_spec",
            message="Unclear requirement",
        )
        assert esc.worker_id == 1
        assert esc.category == "ambiguous_spec"
        assert esc.resolved is False

    def test_to_dict(self) -> None:
        esc = Escalation(
            worker_id=1,
            task_id="TASK-001",
            timestamp="2026-02-02T10:00:00Z",
            category="dependency_missing",
            message="Missing lib",
            context={"attempted": ["pip install"]},
        )
        d = esc.to_dict()
        assert d["category"] == "dependency_missing"
        assert d["context"]["attempted"] == ["pip install"]

    def test_from_dict(self) -> None:
        data = {
            "worker_id": 2,
            "task_id": "TASK-003",
            "timestamp": "2026-02-02T10:00:00Z",
            "category": "verification_unclear",
            "message": "Test unclear",
            "context": {},
            "resolved": True,
        }
        esc = Escalation.from_dict(data)
        assert esc.worker_id == 2
        assert esc.resolved is True


class TestEscalationWriter:
    """Tests for EscalationWriter."""

    def test_escalate(self, tmp_path: Path) -> None:
        writer = EscalationWriter(worker_id=1, state_dir=tmp_path)
        esc = writer.escalate(
            task_id="TASK-001",
            category="ambiguous_spec",
            message="Unclear error types",
        )
        assert esc.worker_id == 1
        assert esc.category == "ambiguous_spec"

        # File should exist
        path = tmp_path / "escalations.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert len(data["escalations"]) == 1
        assert data["escalations"][0]["task_id"] == "TASK-001"

    def test_multiple_escalations(self, tmp_path: Path) -> None:
        writer1 = EscalationWriter(worker_id=1, state_dir=tmp_path)
        writer2 = EscalationWriter(worker_id=2, state_dir=tmp_path)

        writer1.escalate("TASK-001", "ambiguous_spec", "msg1")
        writer2.escalate("TASK-002", "dependency_missing", "msg2")

        data = json.loads((tmp_path / "escalations.json").read_text())
        assert len(data["escalations"]) == 2


class TestEscalationMonitor:
    """Tests for EscalationMonitor."""

    def _write_escalations(self, tmp_path: Path, escalations: list) -> None:
        (tmp_path / "escalations.json").write_text(json.dumps({"escalations": escalations}))

    def test_read_all(self, tmp_path: Path) -> None:
        self._write_escalations(
            tmp_path,
            [
                {
                    "worker_id": 1,
                    "task_id": "T1",
                    "timestamp": "",
                    "category": "ambiguous_spec",
                    "message": "msg",
                    "context": {},
                    "resolved": False,
                },
            ],
        )
        monitor = EscalationMonitor(state_dir=tmp_path)
        all_esc = monitor.read_all()
        assert len(all_esc) == 1

    def test_get_unresolved(self, tmp_path: Path) -> None:
        self._write_escalations(
            tmp_path,
            [
                {
                    "worker_id": 1,
                    "task_id": "T1",
                    "timestamp": "",
                    "category": "x",
                    "message": "msg",
                    "context": {},
                    "resolved": False,
                },
                {
                    "worker_id": 2,
                    "task_id": "T2",
                    "timestamp": "",
                    "category": "y",
                    "message": "msg",
                    "context": {},
                    "resolved": True,
                },
            ],
        )
        monitor = EscalationMonitor(state_dir=tmp_path)
        unresolved = monitor.get_unresolved()
        assert len(unresolved) == 1
        assert unresolved[0].task_id == "T1"

    def test_resolve(self, tmp_path: Path) -> None:
        self._write_escalations(
            tmp_path,
            [
                {
                    "worker_id": 1,
                    "task_id": "T1",
                    "timestamp": "",
                    "category": "x",
                    "message": "msg",
                    "context": {},
                    "resolved": False,
                },
            ],
        )
        monitor = EscalationMonitor(state_dir=tmp_path)
        result = monitor.resolve("T1", 1)
        assert result is True

        # Verify it's resolved on disk
        all_esc = monitor.read_all()
        assert all_esc[0].resolved is True

    def test_resolve_all(self, tmp_path: Path) -> None:
        self._write_escalations(
            tmp_path,
            [
                {
                    "worker_id": 1,
                    "task_id": "T1",
                    "timestamp": "",
                    "category": "x",
                    "message": "msg",
                    "context": {},
                    "resolved": False,
                },
                {
                    "worker_id": 2,
                    "task_id": "T2",
                    "timestamp": "",
                    "category": "y",
                    "message": "msg",
                    "context": {},
                    "resolved": False,
                },
            ],
        )
        monitor = EscalationMonitor(state_dir=tmp_path)
        count = monitor.resolve_all()
        assert count == 2
        assert len(monitor.get_unresolved()) == 0

    def test_read_empty(self, tmp_path: Path) -> None:
        monitor = EscalationMonitor(state_dir=tmp_path)
        assert monitor.read_all() == []
