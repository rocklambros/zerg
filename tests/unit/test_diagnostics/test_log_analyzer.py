"""Tests for LogAnalyzer and LogPattern."""

from __future__ import annotations

from pathlib import Path

from zerg.diagnostics.log_analyzer import LogAnalyzer, LogPattern


class TestLogPattern:
    """Tests for LogPattern dataclass."""

    def test_default_values(self) -> None:
        pat = LogPattern(pattern="error", count=1, first_seen="1", last_seen="1")
        assert pat.sample_lines == []
        assert pat.worker_ids == []

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
    """Tests for LogAnalyzer."""

    def test_strip_ansi(self) -> None:
        analyzer = LogAnalyzer()
        result = analyzer._strip_ansi("\x1b[31mError\x1b[0m")
        assert result == "Error"

    def test_parse_worker_id(self) -> None:
        analyzer = LogAnalyzer()
        assert analyzer._parse_worker_id("worker-3.stderr.log") == 3
        assert analyzer._parse_worker_id("worker-10.stdout.log") == 10
        assert analyzer._parse_worker_id("random.log") is None

    def test_scan_worker_logs_no_dir(self, tmp_path: Path) -> None:
        analyzer = LogAnalyzer(logs_dir=tmp_path / "nonexistent")
        assert analyzer.scan_worker_logs() == []

    def test_scan_worker_logs_empty_dir(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        analyzer = LogAnalyzer(logs_dir=logs_dir)
        assert analyzer.scan_worker_logs() == []

    def test_scan_worker_logs_no_errors(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "worker-1.stderr.log").write_text("all good\nno issues\n")
        analyzer = LogAnalyzer(logs_dir=logs_dir)
        patterns = analyzer.scan_worker_logs()
        assert patterns == []

    def test_scan_worker_logs_finds_errors(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "worker-1.stderr.log").write_text("Starting up\nRuntimeError: something failed\nmore context\n")
        analyzer = LogAnalyzer(logs_dir=logs_dir)
        patterns = analyzer.scan_worker_logs()

        assert len(patterns) == 1
        assert "RuntimeError" in patterns[0].pattern
        assert patterns[0].count == 1
        assert 1 in patterns[0].worker_ids

    def test_scan_worker_logs_groups_same_error(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "worker-1.stderr.log").write_text("Error: connection refused\nok\nError: connection refused\n")
        analyzer = LogAnalyzer(logs_dir=logs_dir)
        patterns = analyzer.scan_worker_logs()

        assert len(patterns) == 1
        assert patterns[0].count == 2

    def test_scan_worker_logs_specific_worker(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "worker-1.stderr.log").write_text("Error: w1\n")
        (logs_dir / "worker-2.stderr.log").write_text("Error: w2\n")
        analyzer = LogAnalyzer(logs_dir=logs_dir)
        patterns = analyzer.scan_worker_logs(worker_id=1)

        assert len(patterns) == 1
        assert "w1" in patterns[0].pattern

    def test_scan_worker_logs_multiple_workers(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "worker-1.stderr.log").write_text("Error: shared issue\n")
        (logs_dir / "worker-2.stderr.log").write_text("Error: shared issue\n")
        analyzer = LogAnalyzer(logs_dir=logs_dir)
        patterns = analyzer.scan_worker_logs()

        assert len(patterns) == 1
        assert sorted(patterns[0].worker_ids) == [1, 2]

    def test_scan_worker_logs_sample_limit(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        content = "\n".join(f"Error: repeated line {i}" for i in range(10))
        (logs_dir / "worker-1.stderr.log").write_text(content)
        analyzer = LogAnalyzer(logs_dir=logs_dir)
        patterns = analyzer.scan_worker_logs()

        # Each unique pattern gets max 3 samples
        for pat in patterns:
            assert len(pat.sample_lines) <= 3

    def test_scan_worker_logs_strips_ansi(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "worker-1.stderr.log").write_text("\x1b[31mError: colored\x1b[0m\n")
        analyzer = LogAnalyzer(logs_dir=logs_dir)
        patterns = analyzer.scan_worker_logs()

        assert len(patterns) == 1
        assert "\x1b" not in patterns[0].pattern

    def test_scan_worker_logs_sorted_by_count(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "worker-1.stderr.log").write_text("Error: rare\nError: common\nError: common\nError: common\n")
        analyzer = LogAnalyzer(logs_dir=logs_dir)
        patterns = analyzer.scan_worker_logs()

        assert len(patterns) == 2
        assert patterns[0].count >= patterns[1].count

    def test_get_error_timeline_no_dir(self, tmp_path: Path) -> None:
        analyzer = LogAnalyzer(logs_dir=tmp_path / "missing")
        assert analyzer.get_error_timeline() == []

    def test_get_error_timeline(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "worker-1.stderr.log").write_text("ok\nError: first\n")
        (logs_dir / "worker-2.stderr.log").write_text("Error: second\n")
        analyzer = LogAnalyzer(logs_dir=logs_dir)
        timeline = analyzer.get_error_timeline()

        assert len(timeline) == 2
        assert timeline[0]["worker_id"] in (1, 2)
        assert "error_line" in timeline[0]

    def test_find_correlated_errors_none(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "worker-1.stderr.log").write_text("Error: unique\n")
        analyzer = LogAnalyzer(logs_dir=logs_dir)
        correlated = analyzer.find_correlated_errors()
        assert correlated == []

    def test_find_correlated_errors(self, tmp_path: Path) -> None:
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "worker-1.stderr.log").write_text("Error: shared\n")
        (logs_dir / "worker-2.stderr.log").write_text("Error: shared\n")
        analyzer = LogAnalyzer(logs_dir=logs_dir)
        correlated = analyzer.find_correlated_errors()

        assert len(correlated) == 1
        assert "shared" in correlated[0][0]
        assert "1" in correlated[0][1]
        assert "2" in correlated[0][1]
