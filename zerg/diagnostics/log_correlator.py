"""Cross-worker log correlation engine for timeline building and causal analysis."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from zerg.diagnostics.log_analyzer import LogAnalyzer, LogPattern
from zerg.diagnostics.types import Evidence, TimelineEvent
from zerg.logging import get_logger

__all__ = [
    "CrossWorkerCorrelator",
    "ErrorEvolutionTracker",
    "LogCorrelationEngine",
    "TemporalClusterer",
    "TimelineBuilder",
]

logger = get_logger("diagnostics.correlator")

# Timestamp patterns
_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?")
_EPOCH_RE = re.compile(r"^(\d{10,13})(?:\.\d+)?(?:\s|$)")
_RELATIVE_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*(?:s|ms|sec|seconds?)")

# Level classifiers for plaintext
_ERROR_RE = re.compile(r"(?i)\b(error|exception|traceback|fatal|panic|abort|segfault|failed)\b")
_WARNING_RE = re.compile(r"(?i)\b(warn(?:ing)?)\b")

# Tokenizer for similarity computation
_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


def _parse_worker_id(filename: str) -> int:
    """Extract worker ID from a log filename like worker-3.stderr.log."""
    match = re.search(r"worker-(\d+)", filename)
    return int(match.group(1)) if match else -1


def _extract_timestamp(line: str) -> str | None:
    """Try to extract a timestamp from the beginning of a line."""
    m = _ISO_RE.search(line[:60])
    if m:
        return m.group(0)
    m = _EPOCH_RE.match(line)
    if m:
        return m.group(1)
    m = _RELATIVE_RE.match(line)
    if m:
        return m.group(0)
    return None


def _classify_level(line: str) -> str:
    """Classify a plaintext line as error/warning/info."""
    if _ERROR_RE.search(line):
        return "error"
    if _WARNING_RE.search(line):
        return "warning"
    return "info"


def _tokenize(text: str) -> set[str]:
    """Tokenize a message into a set of lowercase tokens."""
    return {tok.lower() for tok in _TOKEN_RE.findall(text)}


def _jaccard(a: set[str], b: set[str]) -> float:
    """Compute Jaccard similarity between two token sets."""
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


class TimelineBuilder:
    """Build a chronological timeline of events from worker log files."""

    def build(self, logs_dir: Path) -> list[TimelineEvent]:
        """Read all worker log files and produce a sorted timeline.

        Args:
            logs_dir: Directory containing worker-*.stderr.log / worker-*.stdout.log.

        Returns:
            Sorted list of TimelineEvent objects.
        """
        if not logs_dir.exists():
            return []

        events: list[TimelineEvent] = []
        log_files = sorted(
            list(logs_dir.glob("worker-*.stderr.log")) + list(logs_dir.glob("worker-*.stdout.log")),
        )

        for log_file in log_files:
            wid = _parse_worker_id(log_file.name)
            if wid < 0:
                continue
            file_events = self._parse_file(log_file, wid)
            events.extend(file_events)

        # Sort by timestamp string (ISO sorts lexicographically)
        events.sort(key=lambda e: e.timestamp)
        return events

    def _parse_file(self, path: Path, worker_id: int) -> list[TimelineEvent]:
        """Parse a single log file into timeline events."""
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            return []

        lines = content.splitlines()
        if not lines:
            return []

        # Detect JSONL: check if the first non-empty line is valid JSON
        is_jsonl = False
        for line in lines:
            stripped = line.strip()
            if stripped:
                is_jsonl = stripped.startswith("{")
                break

        if is_jsonl:
            return self._parse_jsonl(lines, worker_id, str(path.name))
        return self._parse_plaintext(lines, worker_id, str(path.name))

    def _parse_jsonl(self, lines: list[str], worker_id: int, source: str) -> list[TimelineEvent]:
        """Parse JSONL formatted log lines."""
        events: list[TimelineEvent] = []
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                continue

            ts = record.get("timestamp") or record.get("ts") or record.get("time")
            ts = f"line:{idx:08d}" if ts is None else str(ts)

            level = str(record.get("level", "info")).lower()
            msg = str(record.get("message") or record.get("msg") or "")

            event_type = "info"
            if level in ("error", "fatal", "critical"):
                event_type = "error"
            elif level in ("warn", "warning"):
                event_type = "warning"

            events.append(
                TimelineEvent(
                    timestamp=ts,
                    worker_id=worker_id,
                    event_type=event_type,
                    message=msg,
                    source_file=source,
                    line_number=idx + 1,
                )
            )
        return events

    def _parse_plaintext(self, lines: list[str], worker_id: int, source: str) -> list[TimelineEvent]:
        """Parse plaintext log lines."""
        events: list[TimelineEvent] = []
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue

            ts = _extract_timestamp(stripped)
            if ts is None:
                ts = f"line:{idx:08d}"

            event_type = _classify_level(stripped)

            events.append(
                TimelineEvent(
                    timestamp=ts,
                    worker_id=worker_id,
                    event_type=event_type,
                    message=stripped[:500],
                    source_file=source,
                    line_number=idx + 1,
                )
            )
        return events


class TemporalClusterer:
    """Group timeline events into temporal clusters."""

    def cluster(
        self,
        events: list[TimelineEvent],
        window_seconds: float = 5.0,
    ) -> list[list[TimelineEvent]]:
        """Group events occurring within a time window.

        For events with real ISO timestamps, groups those within *window_seconds*.
        For synthetic line-based timestamps, groups events within 10 lines.

        Args:
            events: Sorted timeline events.
            window_seconds: Time window in seconds for real timestamps.

        Returns:
            List of clusters (each a list of events).
        """
        if not events:
            return []

        clusters: list[list[TimelineEvent]] = []
        current_cluster: list[TimelineEvent] = [events[0]]

        for event in events[1:]:
            prev = current_cluster[-1]
            if self._within_window(prev, event, window_seconds):
                current_cluster.append(event)
            else:
                clusters.append(current_cluster)
                current_cluster = [event]

        if current_cluster:
            clusters.append(current_cluster)

        return clusters

    @staticmethod
    def _within_window(a: TimelineEvent, b: TimelineEvent, window_seconds: float) -> bool:
        """Determine whether two events are within the clustering window."""
        a_synthetic = a.timestamp.startswith("line:")
        b_synthetic = b.timestamp.startswith("line:")

        # Both synthetic: use line proximity
        if a_synthetic and b_synthetic:
            try:
                a_line = int(a.timestamp.split(":")[1])
                b_line = int(b.timestamp.split(":")[1])
                return abs(b_line - a_line) <= 10
            except (ValueError, IndexError):
                return False

        # Mixed or both real: attempt ISO parse
        if a_synthetic or b_synthetic:
            return False

        a_iso = _ISO_RE.match(a.timestamp)
        b_iso = _ISO_RE.match(b.timestamp)
        if not a_iso or not b_iso:
            # Fall back to string comparison
            return a.timestamp == b.timestamp

        # Simple second-level comparison via string slicing (YYYY-MM-DDTHH:MM:SS)
        try:
            from datetime import datetime

            a_dt = datetime.fromisoformat(a.timestamp.replace("Z", "+00:00"))
            b_dt = datetime.fromisoformat(b.timestamp.replace("Z", "+00:00"))
            delta = abs((b_dt - a_dt).total_seconds())
            return delta <= window_seconds
        except (ValueError, TypeError):
            return a.timestamp == b.timestamp


class CrossWorkerCorrelator:
    """Find correlated error events across different workers."""

    def correlate(self, events: list[TimelineEvent]) -> list[tuple[TimelineEvent, TimelineEvent, float]]:
        """Find error events from different workers with similar messages.

        Similarity is computed as Jaccard similarity of tokenized messages.
        Only pairs with similarity >= 0.5 are returned.

        Args:
            events: Timeline events to correlate.

        Returns:
            List of (event1, event2, similarity_score) tuples.
        """
        error_events = [e for e in events if e.event_type == "error"]
        results: list[tuple[TimelineEvent, TimelineEvent, float]] = []

        # Pre-tokenize for efficiency
        tokenized: list[tuple[TimelineEvent, set[str]]] = [(e, _tokenize(e.message)) for e in error_events]

        for i in range(len(tokenized)):
            ev_a, tok_a = tokenized[i]
            for j in range(i + 1, len(tokenized)):
                ev_b, tok_b = tokenized[j]
                # Only cross-worker pairs
                if ev_a.worker_id == ev_b.worker_id:
                    continue
                sim = _jaccard(tok_a, tok_b)
                if sim >= 0.5:
                    results.append((ev_a, ev_b, sim))

        # Sort by similarity descending
        results.sort(key=lambda r: r[2], reverse=True)
        return results


class ErrorEvolutionTracker:
    """Track how error patterns evolve over time."""

    def track(self, patterns: list[LogPattern]) -> list[dict[str, Any]]:
        """Analyze evolution of error patterns.

        Args:
            patterns: LogPattern objects from LogAnalyzer.

        Returns:
            List of evolution dicts with pattern, count, workers_affected,
            first_seen, last_seen, and trending.
        """
        results: list[dict[str, Any]] = []

        for pat in patterns:
            trending = self._compute_trend(pat)
            results.append(
                {
                    "pattern": pat.pattern,
                    "count": pat.count,
                    "workers_affected": len(pat.worker_ids),
                    "first_seen": pat.first_seen,
                    "last_seen": pat.last_seen,
                    "trending": trending,
                }
            )

        return results

    @staticmethod
    def _compute_trend(pattern: LogPattern) -> str:
        """Determine the trend of a pattern based on available data.

        Uses the first_seen / last_seen positions and count to infer trend.
        """
        if pattern.count <= 1:
            return "stable"

        # If we have numeric first/last (line numbers), use spread vs count
        try:
            first = int(pattern.first_seen)
            last = int(pattern.last_seen)
            span = max(last - first, 1)
            density = pattern.count / span
            # High density at the end implies increasing
            if density > 0.5:
                return "increasing"
            if density < 0.1:
                return "decreasing"
        except (ValueError, TypeError):
            pass

        # Multiple workers affected suggests increasing
        if len(pattern.worker_ids) >= 3:
            return "increasing"

        return "stable"


class LogCorrelationEngine:
    """Facade for cross-worker log correlation analysis."""

    def __init__(self, logs_dir: Path | str = Path(".zerg/logs")) -> None:
        self.logs_dir = Path(logs_dir)
        self._timeline_builder = TimelineBuilder()
        self._clusterer = TemporalClusterer()
        self._correlator = CrossWorkerCorrelator()
        self._evolution_tracker = ErrorEvolutionTracker()
        self._log_analyzer = LogAnalyzer(self.logs_dir)

    def analyze(
        self,
        logs_dir: Path | None = None,
        worker_id: int | None = None,
    ) -> dict[str, Any]:
        """Run full correlation analysis on worker logs.

        Args:
            logs_dir: Override logs directory. Defaults to instance logs_dir.
            worker_id: If provided, filter to a specific worker's logs.

        Returns:
            Dict with keys: timeline, clusters, correlations, evolution, evidence.
        """
        target_dir = logs_dir or self.logs_dir

        # Build timeline
        all_events = self._timeline_builder.build(target_dir)
        if worker_id is not None:
            all_events = [e for e in all_events if e.worker_id == worker_id]

        # Cluster events
        clusters = self._clusterer.cluster(all_events)

        # Cross-worker correlations
        correlations = self._correlator.correlate(all_events)

        # Error evolution
        analyzer = LogAnalyzer(target_dir)
        patterns = analyzer.scan_worker_logs(worker_id=worker_id)
        evolution = self._evolution_tracker.track(patterns)

        # Build evidence from findings
        evidence = self._build_evidence(clusters, correlations, evolution)

        return {
            "timeline": [e.to_dict() for e in all_events],
            "clusters": [[e.to_dict() for e in cluster] for cluster in clusters],
            "correlations": [
                {
                    "event1": ev1.to_dict(),
                    "event2": ev2.to_dict(),
                    "similarity": round(sim, 3),
                }
                for ev1, ev2, sim in correlations
            ],
            "evolution": evolution,
            "evidence": [e.to_dict() for e in evidence],
        }

    @staticmethod
    def _build_evidence(
        clusters: list[list[TimelineEvent]],
        correlations: list[tuple[TimelineEvent, TimelineEvent, float]],
        evolution: list[dict[str, Any]],
    ) -> list[Evidence]:
        """Generate Evidence objects from analysis results."""
        evidence: list[Evidence] = []

        # Evidence from multi-worker clusters
        for cluster in clusters:
            worker_ids = {e.worker_id for e in cluster}
            error_events = [e for e in cluster if e.event_type == "error"]
            if len(worker_ids) >= 2 and error_events:
                evidence.append(
                    Evidence(
                        description=(
                            f"Error in {len(worker_ids)} workers within same "
                            f"time window: {error_events[0].message[:100]}"
                        ),
                        source="log",
                        confidence=min(0.9, 0.5 + 0.1 * len(worker_ids)),
                        data={
                            "worker_ids": sorted(worker_ids),
                            "event_count": len(cluster),
                            "error_count": len(error_events),
                        },
                    )
                )

        # Evidence from cross-worker correlations
        for ev1, ev2, sim in correlations[:5]:
            evidence.append(
                Evidence(
                    description=(
                        f"Similar error across workers {ev1.worker_id} and "
                        f"{ev2.worker_id} (similarity={sim:.2f}): "
                        f"{ev1.message[:80]}"
                    ),
                    source="log",
                    confidence=sim,
                    data={
                        "worker_1": ev1.worker_id,
                        "worker_2": ev2.worker_id,
                        "similarity": round(sim, 3),
                    },
                )
            )

        # Evidence from evolution trends
        for evo in evolution:
            if evo["trending"] == "increasing":
                evidence.append(
                    Evidence(
                        description=(
                            f"Error frequency increasing: {evo['pattern'][:80]} "
                            f"({evo['count']} occurrences across "
                            f"{evo['workers_affected']} workers)"
                        ),
                        source="log",
                        confidence=0.7,
                        data=evo,
                    )
                )

        return evidence
