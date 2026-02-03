"""TDD enforcement protocol for ZERG."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TDDPhase(Enum):
    """TDD cycle phases."""

    RED = "red"  # Write failing test first
    GREEN = "green"  # Make test pass with minimal code
    REFACTOR = "refactor"  # Clean up while keeping tests green


class TDDAntiPattern(Enum):
    """Common TDD anti-patterns to detect."""

    MOCK_HEAVY = "mock_heavy"  # Over-reliance on mocks
    TESTING_IMPL = "testing_impl"  # Testing implementation, not behavior
    NO_ASSERTIONS = "no_assertions"  # Tests without meaningful assertions
    LARGE_TESTS = "large_tests"  # Tests doing too many things
    NO_ARRANGE_ACT_ASSERT = "no_arrange_act_assert"  # Missing AAA structure


@dataclass
class TDDCycleResult:
    """Result of a single TDD cycle."""

    phase: TDDPhase
    test_file: str
    implementation_file: str | None
    tests_passing: bool
    anti_patterns_found: list[TDDAntiPattern] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase.value,
            "test_file": self.test_file,
            "implementation_file": self.implementation_file,
            "tests_passing": self.tests_passing,
            "anti_patterns": [ap.value for ap in self.anti_patterns_found],
            "timestamp": self.timestamp.isoformat(),
            "notes": self.notes,
        }


@dataclass
class TDDReport:
    """Summary of TDD compliance."""

    cycles: list[TDDCycleResult]
    compliant: bool
    red_green_enforced: bool
    anti_patterns_total: int
    total_cycles: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "compliant": self.compliant,
            "red_green_enforced": self.red_green_enforced,
            "anti_patterns_total": self.anti_patterns_total,
            "total_cycles": self.total_cycles,
            "cycles": [c.to_dict() for c in self.cycles],
        }


class TestFirstValidator:
    """Validate test-first development compliance."""

    def __init__(
        self,
        enforce_red_green: bool = True,
        anti_patterns: list[str] | None = None,
    ) -> None:
        self.enforce_red_green = enforce_red_green
        self._anti_pattern_names = set(anti_patterns or [ap.value for ap in TDDAntiPattern])
        self._cycles: list[TDDCycleResult] = []

    def record_cycle(self, result: TDDCycleResult) -> None:
        """Record a TDD cycle result."""
        self._cycles.append(result)

    def validate_red_green_order(self) -> tuple[bool, list[str]]:
        """Validate that cycles follow red->green->refactor order.

        Returns:
            Tuple of (valid, list of violation messages).
        """
        errors: list[str] = []

        if not self._cycles:
            return True, []

        i = 0
        cycle_num = 0
        while i < len(self._cycles):
            cycle_num += 1

            # RED phase
            if i < len(self._cycles) and self._cycles[i].phase == TDDPhase.RED:
                if self._cycles[i].tests_passing:
                    errors.append(f"Cycle {cycle_num}: RED phase has passing tests (test should fail first)")
                i += 1
            else:
                if i < len(self._cycles):
                    errors.append(f"Cycle {cycle_num}: Expected RED phase, got {self._cycles[i].phase.value}")
                    i += 1
                continue

            # GREEN phase
            if i < len(self._cycles) and self._cycles[i].phase == TDDPhase.GREEN:
                if not self._cycles[i].tests_passing:
                    errors.append(
                        f"Cycle {cycle_num}: GREEN phase has failing tests (implementation should make tests pass)"
                    )
                i += 1
            else:
                if i < len(self._cycles):
                    errors.append(f"Cycle {cycle_num}: Expected GREEN phase, got {self._cycles[i].phase.value}")
                continue

            # REFACTOR phase (optional)
            if i < len(self._cycles) and self._cycles[i].phase == TDDPhase.REFACTOR:
                if not self._cycles[i].tests_passing:
                    errors.append(f"Cycle {cycle_num}: REFACTOR phase broke tests")
                i += 1

        return not errors, errors

    def detect_anti_patterns(self, test_content: str) -> list[TDDAntiPattern]:
        """Detect TDD anti-patterns in test code.

        Args:
            test_content: Test file content as string.

        Returns:
            List of detected anti-patterns.
        """
        detected: list[TDDAntiPattern] = []

        if TDDAntiPattern.MOCK_HEAVY.value in self._anti_pattern_names:
            mock_count = test_content.lower().count("mock")
            patch_count = test_content.lower().count("@patch")
            if mock_count + patch_count > 10:
                detected.append(TDDAntiPattern.MOCK_HEAVY)

        if TDDAntiPattern.NO_ASSERTIONS.value in self._anti_pattern_names:
            # Check for test methods without assertions
            lines = test_content.split("\n")
            in_test = False
            has_assert = False
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("def test_"):
                    if in_test and not has_assert:
                        detected.append(TDDAntiPattern.NO_ASSERTIONS)
                        break
                    in_test = True
                    has_assert = False
                elif in_test and ("assert" in stripped or "raises" in stripped):
                    has_assert = True

        if TDDAntiPattern.TESTING_IMPL.value in self._anti_pattern_names:
            impl_indicators = [
                "._private_method",
                ".__internal",
                ".called_with",
                ".call_count",
            ]
            indicator_count = sum(1 for ind in impl_indicators if ind in test_content)
            if indicator_count >= 3:
                detected.append(TDDAntiPattern.TESTING_IMPL)

        return detected

    def get_report(self) -> TDDReport:
        """Generate TDD compliance report."""
        valid, _ = self.validate_red_green_order()
        total_anti = sum(len(c.anti_patterns_found) for c in self._cycles)

        return TDDReport(
            cycles=self._cycles.copy(),
            compliant=valid and total_anti == 0,
            red_green_enforced=valid,
            anti_patterns_total=total_anti,
            total_cycles=len(self._cycles),
        )

    @property
    def cycles(self) -> list[TDDCycleResult]:
        return self._cycles.copy()

    def clear(self) -> None:
        self._cycles.clear()


class TDDProtocol:
    """High-level TDD protocol enforcement."""

    def __init__(
        self,
        enabled: bool = True,
        enforce_red_green: bool = True,
        anti_patterns: list[str] | None = None,
    ) -> None:
        self.enabled = enabled
        self.validator = TestFirstValidator(
            enforce_red_green=enforce_red_green,
            anti_patterns=anti_patterns,
        )
        self._current_phase: TDDPhase | None = None

    @property
    def current_phase(self) -> TDDPhase | None:
        return self._current_phase

    def start_cycle(self, test_file: str) -> TDDPhase:
        """Start a new TDD cycle. Always begins with RED."""
        self._current_phase = TDDPhase.RED
        return self._current_phase

    def advance_phase(self) -> TDDPhase | None:
        """Advance to next phase in the cycle."""
        if self._current_phase == TDDPhase.RED:
            self._current_phase = TDDPhase.GREEN
        elif self._current_phase == TDDPhase.GREEN:
            self._current_phase = TDDPhase.REFACTOR
        elif self._current_phase == TDDPhase.REFACTOR:
            self._current_phase = None  # Cycle complete
        return self._current_phase

    def record_result(
        self,
        test_file: str,
        tests_passing: bool,
        implementation_file: str | None = None,
        test_content: str | None = None,
        notes: str = "",
    ) -> TDDCycleResult:
        """Record current phase result and detect anti-patterns."""
        anti_patterns = []
        if test_content:
            anti_patterns = self.validator.detect_anti_patterns(test_content)

        result = TDDCycleResult(
            phase=self._current_phase or TDDPhase.RED,
            test_file=test_file,
            implementation_file=implementation_file,
            tests_passing=tests_passing,
            anti_patterns_found=anti_patterns,
            notes=notes,
        )
        self.validator.record_cycle(result)
        return result

    def get_report(self) -> TDDReport:
        return self.validator.get_report()

    def is_compliant(self) -> bool:
        if not self.enabled:
            return True
        return self.get_report().compliant
