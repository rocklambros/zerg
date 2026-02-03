"""Token efficiency mode for ZERG -- compressed output and context optimization."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class EfficiencyZone(Enum):
    """Context usage zones determining efficiency behavior."""

    GREEN = "green"  # 0-75%: Full capabilities, normal verbosity
    YELLOW = "yellow"  # 75-85%: Activate efficiency mode, reduce verbosity
    RED = "red"  # 85%+: Essential operations only, minimal output

    @property
    def threshold(self) -> float:
        """Lower threshold for this zone as percentage."""
        thresholds = {
            EfficiencyZone.GREEN: 0.0,
            EfficiencyZone.YELLOW: 75.0,
            EfficiencyZone.RED: 85.0,
        }
        return thresholds[self]

    @property
    def description(self) -> str:
        """Zone description."""
        descriptions = {
            EfficiencyZone.GREEN: "Full capabilities, normal output",
            EfficiencyZone.YELLOW: "Efficiency mode, reduced verbosity",
            EfficiencyZone.RED: "Essential operations only, minimal output",
        }
        return descriptions[self]


class ZoneDetector:
    """Detect current efficiency zone from context usage."""

    def __init__(
        self,
        yellow_threshold: float = 75.0,
        red_threshold: float = 85.0,
    ) -> None:
        """Initialize zone detector.

        Args:
            yellow_threshold: Percentage threshold for yellow zone.
            red_threshold: Percentage threshold for red zone.
        """
        self.yellow_threshold = yellow_threshold
        self.red_threshold = red_threshold

    def detect(self, usage_percent: float) -> EfficiencyZone:
        """Detect zone from usage percentage.

        Args:
            usage_percent: Current context usage as percentage (0-100).

        Returns:
            Current EfficiencyZone.
        """
        if usage_percent >= self.red_threshold:
            return EfficiencyZone.RED
        elif usage_percent >= self.yellow_threshold:
            return EfficiencyZone.YELLOW
        return EfficiencyZone.GREEN

    def get_mode_hint(self, usage_percent: float) -> str | None:
        """Suggest behavioral mode based on efficiency zone.

        Args:
            usage_percent: Current context usage percentage.

        Returns:
            Suggested mode name or None.
        """
        zone = self.detect(usage_percent)
        if zone == EfficiencyZone.RED:
            return "speed"
        if zone == EfficiencyZone.YELLOW:
            return "speed"
        return None

    def should_compact(self, usage_percent: float, force_compact: bool = False) -> bool:
        """Determine if compact mode should be active.

        Args:
            usage_percent: Current context usage percentage.
            force_compact: If True, always compact (--uc flag).

        Returns:
            True if compact mode should be active.
        """
        if force_compact:
            return True
        return self.detect(usage_percent) != EfficiencyZone.GREEN


# Symbol mappings for compact output
SYMBOLS: dict[str, str] = {
    # Status
    "completed": "\u2705",
    "failed": "\u274c",
    "warning": "\u26a0\ufe0f",
    "in_progress": "\U0001f504",
    "pending": "\u23f3",
    "critical": "\U0001f6a8",
    # Technical domains
    "performance": "\u26a1",
    "analysis": "\U0001f50d",
    "configuration": "\U0001f527",
    "security": "\U0001f6e1\ufe0f",
    "deployment": "\U0001f4e6",
    "design": "\U0001f3a8",
    "architecture": "\U0001f3d7\ufe0f",
    # Logic
    "leads_to": "\u2192",
    "transforms": "\u21d2",
    "rollback": "\u2190",
    "bidirectional": "\u21c4",
    "therefore": "\u2234",
    "because": "\u2235",
    "sequence": "\u00bb",
}

# Abbreviation mappings
ABBREVIATIONS: dict[str, str] = {
    "configuration": "cfg",
    "implementation": "impl",
    "architecture": "arch",
    "performance": "perf",
    "operations": "ops",
    "environment": "env",
    "requirements": "req",
    "dependencies": "deps",
    "validation": "val",
    "documentation": "docs",
    "standards": "std",
    "security": "sec",
    "optimization": "opt",
}


@dataclass
class CompactFormatter:
    """Formats output for token efficiency."""

    use_symbols: bool = True
    use_abbreviations: bool = True
    max_line_length: int = 80

    def format_status(self, status: str) -> str:
        """Format status with symbol prefix.

        Args:
            status: Status string (e.g., "completed", "failed").

        Returns:
            Formatted status string.
        """
        if not self.use_symbols:
            return status
        symbol = SYMBOLS.get(status, "")
        return f"{symbol} {status}" if symbol else status

    def abbreviate(self, text: str) -> str:
        """Apply abbreviations to text.

        Args:
            text: Input text.

        Returns:
            Abbreviated text.
        """
        if not self.use_abbreviations:
            return text
        result = text
        for full, abbrev in ABBREVIATIONS.items():
            result = result.replace(full, abbrev)
        return result

    def compact_summary(self, data: dict[str, Any]) -> str:
        """Create compact summary from data dict.

        Args:
            data: Key-value pairs to summarize.

        Returns:
            Compact single-line or multi-line summary.
        """
        parts = []
        for key, value in data.items():
            short_key = self.abbreviate(key) if self.use_abbreviations else key
            if isinstance(value, bool):
                parts.append(f"{short_key}={'Y' if value else 'N'}")
            elif isinstance(value, int | float):
                parts.append(f"{short_key}={value}")
            else:
                short_val = self.abbreviate(str(value)) if self.use_abbreviations else str(value)
                parts.append(f"{short_key}={short_val}")

        line = " | ".join(parts)
        if len(line) > self.max_line_length:
            return "\n".join(parts)
        return line

    def compact_list(self, items: list[str], separator: str = " | ") -> str:
        """Compact a list into a single line.

        Args:
            items: List of strings.
            separator: Separator between items.

        Returns:
            Compacted string.
        """
        compacted = [self.abbreviate(item) for item in items]
        return separator.join(compacted)
