"""ZERG log analysis for pattern detection and error correlation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from zerg.logging import get_logger

logger = get_logger("diagnostics.logs")


@dataclass
class LogPattern:
    """A grouped error pattern found in worker logs."""

    pattern: str
    count: int
    first_seen: str
    last_seen: str
    sample_lines: list[str] = field(default_factory=list)
    worker_ids: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pattern": self.pattern,
            "count": self.count,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "sample_lines": self.sample_lines,
            "worker_ids": self.worker_ids,
        }


class LogAnalyzer:
    """Analyze worker logs for error patterns and correlations."""

    ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

    # Lines that indicate errors
    ERROR_INDICATORS = re.compile(r"(?i)(error|exception|traceback|failed|fatal|panic|abort|segfault)")

    def __init__(self, logs_dir: Path | str = Path(".zerg/logs")) -> None:
        self.logs_dir = Path(logs_dir)

    def _strip_ansi(self, text: str) -> str:
        """Remove ANSI escape codes from text."""
        return self.ANSI_RE.sub("", text)

    def _parse_worker_id(self, filename: str) -> int | None:
        """Extract worker ID from log filename."""
        match = re.search(r"worker-(\d+)", filename)
        if match:
            return int(match.group(1))
        return None

    def scan_worker_logs(self, worker_id: int | None = None) -> list[LogPattern]:
        """Scan worker stderr logs and group errors by first line."""
        if not self.logs_dir.exists():
            return []

        pattern_map: dict[str, LogPattern] = {}

        if worker_id is not None:
            log_files = list(self.logs_dir.glob(f"worker-{worker_id}.stderr.log"))
        else:
            log_files = sorted(self.logs_dir.glob("worker-*.stderr.log"))

        for log_file in log_files:
            wid = self._parse_worker_id(log_file.name)
            if wid is None:
                continue

            try:
                content = log_file.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                logger.warning(f"Failed to read {log_file}: {e}")
                continue

            content = self._strip_ansi(content)
            lines = content.splitlines()

            for i, line in enumerate(lines):
                stripped = line.strip()
                if not stripped or not self.ERROR_INDICATORS.search(stripped):
                    continue

                # Use first 100 chars as pattern key
                key = stripped[:100]

                if key not in pattern_map:
                    pattern_map[key] = LogPattern(
                        pattern=key,
                        count=0,
                        first_seen=str(i + 1),
                        last_seen=str(i + 1),
                        sample_lines=[],
                        worker_ids=[],
                    )

                pat = pattern_map[key]
                pat.count += 1
                pat.last_seen = str(i + 1)

                if wid not in pat.worker_ids:
                    pat.worker_ids.append(wid)

                # Keep up to 3 sample lines (with surrounding context)
                if len(pat.sample_lines) < 3:
                    context_start = max(0, i - 1)
                    context_end = min(len(lines), i + 3)
                    sample = "\n".join(lines[context_start:context_end])
                    pat.sample_lines.append(sample)

        return sorted(pattern_map.values(), key=lambda p: p.count, reverse=True)

    def get_error_timeline(self) -> list[dict[str, Any]]:
        """Build chronological list of errors across all workers."""
        if not self.logs_dir.exists():
            return []

        timeline: list[dict[str, Any]] = []
        log_files = sorted(self.logs_dir.glob("worker-*.stderr.log"))

        for log_file in log_files:
            wid = self._parse_worker_id(log_file.name)
            if wid is None:
                continue

            try:
                content = log_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            content = self._strip_ansi(content)
            for i, line in enumerate(content.splitlines()):
                stripped = line.strip()
                if stripped and self.ERROR_INDICATORS.search(stripped):
                    timeline.append(
                        {
                            "line_number": i + 1,
                            "worker_id": wid,
                            "error_line": stripped[:200],
                        }
                    )

        return timeline

    def find_correlated_errors(self) -> list[tuple[str, str]]:
        """Find errors appearing in 2+ workers."""
        patterns = self.scan_worker_logs()
        correlated: list[tuple[str, str]] = []

        for pat in patterns:
            if len(pat.worker_ids) >= 2:
                workers_str = ", ".join(str(w) for w in pat.worker_ids)
                correlated.append((pat.pattern, f"workers: {workers_str}"))

        return correlated
