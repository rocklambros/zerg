"""Behavioral mode system for ZERG -- auto-detect and manage execution modes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class BehavioralMode(Enum):
    """Behavioral execution modes."""

    PRECISION = "precision"  # Default: careful, thorough
    SPEED = "speed"  # Fast iteration, less verification
    EXPLORATION = "exploration"  # Discovery, broad search
    REFACTOR = "refactor"  # Code transformation focus
    DEBUG = "debug"  # Diagnostic, verbose logging

    @property
    def description(self) -> str:
        """Human-readable description of this mode."""
        descriptions = {
            BehavioralMode.PRECISION: "Careful, thorough execution with full verification",
            BehavioralMode.SPEED: "Fast iteration with minimal overhead",
            BehavioralMode.EXPLORATION: "Broad discovery and analysis",
            BehavioralMode.REFACTOR: "Code transformation and restructuring",
            BehavioralMode.DEBUG: "Diagnostic mode with verbose logging",
        }
        return descriptions[self]

    @property
    def verification_level(self) -> str:
        """Verification stringency for this mode."""
        levels = {
            BehavioralMode.PRECISION: "full",
            BehavioralMode.SPEED: "minimal",
            BehavioralMode.EXPLORATION: "none",
            BehavioralMode.REFACTOR: "full",
            BehavioralMode.DEBUG: "verbose",
        }
        return levels[self]


@dataclass
class ModeContext:
    """Context for the active behavioral mode."""

    mode: BehavioralMode
    auto_detected: bool
    detection_reason: str
    depth_tier: str | None = None  # From depth tiers system
    efficiency_zone: str | None = None  # From efficiency system

    def to_dict(self) -> dict[str, Any]:
        """Serialize mode context to dictionary.

        Returns:
            Dictionary representation of this context.
        """
        return {
            "mode": self.mode.value,
            "auto_detected": self.auto_detected,
            "detection_reason": self.detection_reason,
            "depth_tier": self.depth_tier,
            "efficiency_zone": self.efficiency_zone,
        }


class ModeDetector:
    """Detect appropriate behavioral mode from task context."""

    # Keywords mapped to modes
    MODE_KEYWORDS: dict[BehavioralMode, list[str]] = {
        BehavioralMode.SPEED: [
            "quick",
            "fast",
            "prototype",
            "spike",
            "poc",
            "draft",
        ],
        BehavioralMode.EXPLORATION: [
            "explore",
            "discover",
            "research",
            "investigate",
            "brainstorm",
            "analyze",
        ],
        BehavioralMode.REFACTOR: [
            "refactor",
            "restructure",
            "reorganize",
            "clean up",
            "migrate",
            "rename",
            "extract",
            "move",
        ],
        BehavioralMode.DEBUG: [
            "debug",
            "diagnose",
            "troubleshoot",
            "fix",
            "bug",
            "error",
            "failing",
            "broken",
        ],
    }

    def __init__(
        self,
        auto_detect: bool = True,
        default_mode: BehavioralMode = BehavioralMode.PRECISION,
        log_transitions: bool = True,
    ) -> None:
        """Initialize mode detector.

        Args:
            auto_detect: Whether to auto-detect mode from context.
            default_mode: Default mode when detection finds no match.
            log_transitions: Whether to record mode transitions.
        """
        self.auto_detect = auto_detect
        self.default_mode = default_mode
        self.log_transitions = log_transitions
        self._current_mode: BehavioralMode | None = None
        self._transitions: list[dict[str, Any]] = []

    def detect(
        self,
        description: str | None = None,
        explicit_mode: BehavioralMode | None = None,
        depth_tier: str | None = None,
        efficiency_zone: str | None = None,
    ) -> ModeContext:
        """Detect the appropriate behavioral mode.

        Priority: explicit > description keywords > zone-based > depth-based > default

        Args:
            description: Task description for keyword matching.
            explicit_mode: Explicitly requested mode (overrides auto-detection).
            depth_tier: Current depth tier name from depth tiers system.
            efficiency_zone: Current efficiency zone from efficiency system.

        Returns:
            ModeContext for the detected mode.
        """
        if explicit_mode is not None:
            context = ModeContext(
                mode=explicit_mode,
                auto_detected=False,
                detection_reason="explicit",
                depth_tier=depth_tier,
                efficiency_zone=efficiency_zone,
            )
            self._record_transition(context)
            return context

        if not self.auto_detect:
            return ModeContext(
                mode=self.default_mode,
                auto_detected=False,
                detection_reason="auto-detect disabled",
                depth_tier=depth_tier,
                efficiency_zone=efficiency_zone,
            )

        # Try keyword detection
        if description:
            mode = self._detect_from_keywords(description)
            if mode:
                context = ModeContext(
                    mode=mode,
                    auto_detected=True,
                    detection_reason=f"keyword match in: {description[:50]}",
                    depth_tier=depth_tier,
                    efficiency_zone=efficiency_zone,
                )
                self._record_transition(context)
                return context

        # Zone-based detection
        if efficiency_zone == "red":
            context = ModeContext(
                mode=BehavioralMode.SPEED,
                auto_detected=True,
                detection_reason="efficiency zone red -> speed mode",
                depth_tier=depth_tier,
                efficiency_zone=efficiency_zone,
            )
            self._record_transition(context)
            return context

        # Depth-based detection
        if depth_tier in ("ultrathink", "think-hard"):
            context = ModeContext(
                mode=BehavioralMode.PRECISION,
                auto_detected=True,
                detection_reason=f"depth tier {depth_tier} -> precision mode",
                depth_tier=depth_tier,
                efficiency_zone=efficiency_zone,
            )
            self._record_transition(context)
            return context

        return ModeContext(
            mode=self.default_mode,
            auto_detected=False,
            detection_reason="default",
            depth_tier=depth_tier,
            efficiency_zone=efficiency_zone,
        )

    def _detect_from_keywords(self, description: str) -> BehavioralMode | None:
        """Detect mode from description keywords.

        Checks from most specific to least specific mode.

        Args:
            description: Task description text.

        Returns:
            Detected BehavioralMode or None if no match.
        """
        desc_lower = description.lower()
        # Check from most specific to least
        for mode in [
            BehavioralMode.DEBUG,
            BehavioralMode.REFACTOR,
            BehavioralMode.EXPLORATION,
            BehavioralMode.SPEED,
        ]:
            keywords = self.MODE_KEYWORDS.get(mode, [])
            if any(kw in desc_lower for kw in keywords):
                return mode
        return None

    def _record_transition(self, context: ModeContext) -> None:
        """Record a mode transition for logging.

        Args:
            context: The new mode context being transitioned to.
        """
        if self.log_transitions:
            from_mode = self._current_mode.value if self._current_mode else "none"
            self._transitions.append(
                {
                    "from": from_mode,
                    "to": context.mode.value,
                    "reason": context.detection_reason,
                    "auto": context.auto_detected,
                }
            )
        self._current_mode = context.mode

    @property
    def current_mode(self) -> BehavioralMode | None:
        """Get the current active mode, or None if no detection has run."""
        return self._current_mode

    @property
    def transitions(self) -> list[dict[str, Any]]:
        """Get a copy of all recorded mode transitions."""
        return self._transitions.copy()
