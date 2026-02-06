"""Tests for LogAnalyzer and LogPattern."""

from __future__ import annotations

from pathlib import Path

from zerg.diagnostics.log_analyzer import LogAnalyzer, LogPattern


class TestLogPattern:
    def test_to_dict(self) -> None:
        pat = LogPattern(
            pattern="RuntimeError: fail",
            count=3,
            first_seen="5",
            last_seen="20",
            sample_lines=["line1", "line2"],
            worker_ids=[1, 2],
        )
        d = pat.to_dict()
        assert d["pattern"] == "RuntimeError: fail"
        assert d["count"] == 3
        assert d["worker_ids"] == [1, 2]


class TestLogAnalyzer:
    def test_strip_ansi(self) -> None:
        analyzer = LogAnalyzer()
        result = analyzer._strip_ansi("\x1b[31mError\x1b[0m")
        assert result == "Error"

    def test_parse_worker_id(self) -> None:
        analyzer = LogAnalyzer()
        assert analyzer._parse_worker_id("worker-3.stderr.log") == 3
        assert analyzer._parse_worker_id("random.log") is None

    def test_scan_worker_logs_no_dir(self, tmp_path: Path) -> None:
        analyzer = LogAnalyzer(logs_dir=tmp_path / "nonexistent")
        assert analyzer.scan_worker_logs() == []

    def test_scan_worker_logs_finds_errors(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "worker-1.stderr.log").write_text("Starting up\nRuntimeError: something failed\nmore context\n")
        analyzer = LogAnalyzer(logs_dir=logs_dir)
        patterns = analyzer.scan_worker_logs()
        assert len(patterns) == 1
        assert "RuntimeError" in patterns[0].pattern
        assert 1 in patterns[0].worker_ids

    def test_scan_worker_logs_groups_same_error(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "worker-1.stderr.log").write_text("Error: connection refused\nok\nError: connection refused\n")
        analyzer = LogAnalyzer(logs_dir=logs_dir)
        patterns = analyzer.scan_worker_logs()
        assert len(patterns) == 1
        assert patterns[0].count == 2

    def test_scan_worker_logs_multiple_workers(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "worker-1.stderr.log").write_text("Error: shared issue\n")
        (logs_dir / "worker-2.stderr.log").write_text("Error: shared issue\n")
        analyzer = LogAnalyzer(logs_dir=logs_dir)
        patterns = analyzer.scan_worker_logs()
        assert len(patterns) == 1
        assert sorted(patterns[0].worker_ids) == [1, 2]

    def test_scan_worker_logs_sorted_by_count(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "worker-1.stderr.log").write_text("Error: rare\nError: common\nError: common\nError: common\n")
        analyzer = LogAnalyzer(logs_dir=logs_dir)
        patterns = analyzer.scan_worker_logs()
        assert len(patterns) == 2
        assert patterns[0].count >= patterns[1].count

    def test_get_error_timeline(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "worker-1.stderr.log").write_text("ok\nError: first\n")
        (logs_dir / "worker-2.stderr.log").write_text("Error: second\n")
        analyzer = LogAnalyzer(logs_dir=logs_dir)
        timeline = analyzer.get_error_timeline()
        assert len(timeline) == 2
        assert "error_line" in timeline[0]

    def test_find_correlated_errors(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "worker-1.stderr.log").write_text("Error: shared\n")
        (logs_dir / "worker-2.stderr.log").write_text("Error: shared\n")
        analyzer = LogAnalyzer(logs_dir=logs_dir)
        correlated = analyzer.find_correlated_errors()
        assert len(correlated) == 1
        assert "shared" in correlated[0][0]
