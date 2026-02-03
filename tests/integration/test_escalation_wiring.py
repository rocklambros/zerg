"""Integration tests for escalation wiring into orchestrator."""

from pathlib import Path

from zerg.escalation import EscalationMonitor, EscalationWriter
from zerg.progress_reporter import ProgressReporter


class TestEscalationWriterMonitorWiring:
    """Test escalation writer -> monitor roundtrip."""

    def test_writer_creates_monitor_reads(self, tmp_path: Path) -> None:
        writer = EscalationWriter(worker_id=1, state_dir=tmp_path)
        writer.escalate(
            task_id="TASK-001",
            category="ambiguous_spec",
            message="What auth errors?",
            context={"attempted": ["TypeError", "Exception"]},
        )

        monitor = EscalationMonitor(state_dir=tmp_path)
        unresolved = monitor.get_unresolved()
        assert len(unresolved) == 1
        assert unresolved[0].category == "ambiguous_spec"
        assert unresolved[0].message == "What auth errors?"

    def test_multiple_workers_escalate(self, tmp_path: Path) -> None:
        for wid in [1, 2]:
            writer = EscalationWriter(worker_id=wid, state_dir=tmp_path)
            writer.escalate(f"TASK-{wid}", "dependency_missing", f"msg-{wid}")

        monitor = EscalationMonitor(state_dir=tmp_path)
        all_esc = monitor.read_all()
        assert len(all_esc) == 2

    def test_resolve_clears_unresolved(self, tmp_path: Path) -> None:
        writer = EscalationWriter(worker_id=1, state_dir=tmp_path)
        writer.escalate("TASK-001", "ambiguous_spec", "msg")

        monitor = EscalationMonitor(state_dir=tmp_path)
        assert len(monitor.get_unresolved()) == 1

        monitor.resolve("TASK-001", 1)
        assert len(monitor.get_unresolved()) == 0
        assert len(monitor.read_all()) == 1  # still in list, just resolved


class TestProgressReporterWiring:
    """Test progress reporter writer -> reader roundtrip with tier results."""

    def test_progress_with_tiers(self, tmp_path: Path) -> None:
        reporter = ProgressReporter(worker_id=1, state_dir=tmp_path)
        reporter.update(current_task="TASK-001", tasks_total=5, tasks_completed=1)
        reporter.add_tier_result(1, "syntax", True)
        reporter.add_tier_result(2, "correctness", False, retry=1)

        # Read back
        wp = ProgressReporter.read(1, state_dir=tmp_path)
        assert wp is not None
        assert wp.current_task == "TASK-001"
        assert wp.tasks_completed == 1
        assert len(wp.tier_results) == 2
        assert wp.tier_results[0].success is True
        assert wp.tier_results[1].success is False
        assert wp.tier_results[1].retry == 1

    def test_read_all_multiple_workers(self, tmp_path: Path) -> None:
        for wid in [1, 2, 3]:
            reporter = ProgressReporter(worker_id=wid, state_dir=tmp_path)
            reporter.update(tasks_total=5, tasks_completed=wid)

        all_progress = ProgressReporter.read_all(state_dir=tmp_path)
        assert len(all_progress) == 3
        assert all_progress[2].tasks_completed == 2
