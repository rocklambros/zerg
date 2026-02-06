"""Unit tests for TDD enforcement protocol — thinned to essentials."""

from datetime import datetime

import pytest
from click.testing import CliRunner

from zerg.cli import cli
from zerg.config import TDDConfig, ZergConfig
from zerg.tdd import (
    TDDAntiPattern,
    TDDCycleResult,
    TDDPhase,
    TDDProtocol,
    TDDReport,
    TestFirstValidator,
)

# ── Enum Tests ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "member,value",
    [("RED", "red"), ("GREEN", "green"), ("REFACTOR", "refactor")],
)
def test_tdd_phase_values(member: str, value: str) -> None:
    assert TDDPhase[member].value == value
    assert len(TDDPhase) == 3


@pytest.mark.parametrize(
    "member,value",
    [
        ("MOCK_HEAVY", "mock_heavy"),
        ("TESTING_IMPL", "testing_impl"),
        ("NO_ASSERTIONS", "no_assertions"),
        ("LARGE_TESTS", "large_tests"),
        ("NO_ARRANGE_ACT_ASSERT", "no_arrange_act_assert"),
    ],
)
def test_anti_pattern_values(member: str, value: str) -> None:
    assert TDDAntiPattern[member].value == value
    assert len(TDDAntiPattern) == 5


# ── TDDCycleResult Tests ────────────────────────────────────────────


class TestTDDCycleResult:
    def test_creation_and_defaults(self) -> None:
        result = TDDCycleResult(
            phase=TDDPhase.RED,
            test_file="test_foo.py",
            implementation_file=None,
            tests_passing=False,
        )
        assert result.phase == TDDPhase.RED
        assert result.anti_patterns_found == []
        assert result.notes == ""
        assert isinstance(result.timestamp, datetime)

    def test_to_dict(self) -> None:
        ts = datetime(2026, 1, 15, 10, 30, 0)
        result = TDDCycleResult(
            phase=TDDPhase.RED,
            test_file="test_x.py",
            implementation_file="x.py",
            tests_passing=False,
            anti_patterns_found=[TDDAntiPattern.NO_ASSERTIONS],
            timestamp=ts,
            notes="note",
        )
        d = result.to_dict()
        assert d["phase"] == "red"
        assert d["anti_patterns"] == ["no_assertions"]
        assert d["timestamp"] == ts.isoformat()


# ── TDDReport Tests ─────────────────────────────────────────────────


class TestTDDReport:
    def test_to_dict_with_cycles(self) -> None:
        cycle = TDDCycleResult(
            phase=TDDPhase.RED,
            test_file="t.py",
            implementation_file=None,
            tests_passing=False,
        )
        report = TDDReport(
            cycles=[cycle],
            compliant=False,
            red_green_enforced=False,
            anti_patterns_total=1,
            total_cycles=1,
        )
        d = report.to_dict()
        assert d["compliant"] is False
        assert len(d["cycles"]) == 1
        assert d["cycles"][0]["phase"] == "red"


# ── TestFirstValidator Tests ────────────────────────────────────────


class TestTestFirstValidator:
    def test_record_and_cycles_copy(self) -> None:
        v = TestFirstValidator()
        result = TDDCycleResult(
            phase=TDDPhase.RED,
            test_file="t.py",
            implementation_file=None,
            tests_passing=False,
        )
        v.record_cycle(result)
        assert len(v.cycles) == 1
        v.cycles.clear()
        assert len(v.cycles) == 1  # original unaffected

    def test_validate_correct_red_green_refactor(self) -> None:
        v = TestFirstValidator()
        for phase, passing in [
            (TDDPhase.RED, False),
            (TDDPhase.GREEN, True),
            (TDDPhase.REFACTOR, True),
        ]:
            v.record_cycle(
                TDDCycleResult(
                    phase=phase,
                    test_file="t.py",
                    implementation_file="impl.py" if phase != TDDPhase.RED else None,
                    tests_passing=passing,
                )
            )
        valid, errors = v.validate_red_green_order()
        assert valid is True and errors == []

    @pytest.mark.parametrize(
        "phases_passing,expected_error_fragment",
        [
            ([(TDDPhase.RED, True), (TDDPhase.GREEN, True)], "RED phase has passing tests"),
            ([(TDDPhase.RED, False), (TDDPhase.GREEN, False)], "GREEN phase has failing tests"),
            ([(TDDPhase.GREEN, True)], "Expected RED phase"),
        ],
    )
    def test_validate_failures(self, phases_passing, expected_error_fragment) -> None:
        v = TestFirstValidator()
        for phase, passing in phases_passing:
            v.record_cycle(
                TDDCycleResult(
                    phase=phase,
                    test_file="t.py",
                    implementation_file="impl.py" if phase != TDDPhase.RED else None,
                    tests_passing=passing,
                )
            )
        valid, errors = v.validate_red_green_order()
        assert valid is False
        assert any(expected_error_fragment in e for e in errors)

    def test_detect_anti_patterns(self) -> None:
        v = TestFirstValidator()
        mock_code = "\n".join([f"mock{i} = Mock()" for i in range(15)])
        assert TDDAntiPattern.MOCK_HEAVY in v.detect_anti_patterns(mock_code)
        no_assert_code = "def test_a():\n    x = 1\ndef test_b():\n    assert x == 2"
        assert TDDAntiPattern.NO_ASSERTIONS in v.detect_anti_patterns(no_assert_code)
        clean_code = "def test_a():\n    assert add(1,2) == 3"
        assert v.detect_anti_patterns(clean_code) == []

    def test_report_compliant_vs_non_compliant(self) -> None:
        v = TestFirstValidator()
        v.record_cycle(
            TDDCycleResult(
                phase=TDDPhase.RED,
                test_file="t.py",
                implementation_file=None,
                tests_passing=False,
            )
        )
        v.record_cycle(
            TDDCycleResult(
                phase=TDDPhase.GREEN,
                test_file="t.py",
                implementation_file="impl.py",
                tests_passing=True,
            )
        )
        report = v.get_report()
        assert report.compliant is True and report.anti_patterns_total == 0

    def test_clear_resets(self) -> None:
        v = TestFirstValidator()
        v.record_cycle(
            TDDCycleResult(
                phase=TDDPhase.RED,
                test_file="t.py",
                implementation_file=None,
                tests_passing=False,
            )
        )
        v.clear()
        assert len(v.cycles) == 0


# ── TDDProtocol Tests ───────────────────────────────────────────────


class TestTDDProtocol:
    def test_full_cycle_workflow(self) -> None:
        p = TDDProtocol()
        assert p.current_phase is None
        p.start_cycle("test_calc.py")
        assert p.current_phase == TDDPhase.RED
        p.record_result(test_file="test_calc.py", tests_passing=False)
        p.advance_phase()
        assert p.current_phase == TDDPhase.GREEN
        p.record_result(test_file="test_calc.py", tests_passing=True, implementation_file="calc.py")
        p.advance_phase()
        assert p.current_phase == TDDPhase.REFACTOR
        p.record_result(test_file="test_calc.py", tests_passing=True, implementation_file="calc.py")
        p.advance_phase()
        assert p.current_phase is None
        assert p.is_compliant() is True
        report = p.get_report()
        assert isinstance(report, TDDReport) and report.total_cycles == 3

    def test_disabled_always_compliant(self) -> None:
        p = TDDProtocol(enabled=False)
        p.start_cycle("t.py")
        p.record_result(test_file="t.py", tests_passing=True)
        assert p.is_compliant() is True

    def test_record_result_detects_anti_patterns(self) -> None:
        p = TDDProtocol()
        p.start_cycle("t.py")
        code = "\n".join([f"mock{i} = Mock()" for i in range(15)])
        result = p.record_result(test_file="t.py", tests_passing=False, test_content=code)
        assert TDDAntiPattern.MOCK_HEAVY in result.anti_patterns_found


# ── TDDConfig Tests ─────────────────────────────────────────────────


class TestTDDConfig:
    def test_defaults(self) -> None:
        config = TDDConfig()
        assert config.enabled is False
        assert config.enforce_red_green is True
        assert "mock_heavy" in config.anti_patterns

    def test_zerg_config_tdd_roundtrip(self) -> None:
        config = ZergConfig()
        config.tdd.enabled = True
        d = config.to_dict()
        loaded = ZergConfig.from_dict(d)
        assert loaded.tdd.enabled is True


# ── CLI --tdd Flag Tests ────────────────────────────────────────────


class TestCLITddFlag:
    def test_tdd_flag_accepted(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--tdd", "--help"])
        assert result.exit_code == 0
        assert "--tdd" in result.output
