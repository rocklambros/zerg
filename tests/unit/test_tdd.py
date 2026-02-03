"""Comprehensive tests for TDD enforcement protocol."""

from datetime import datetime

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


class TestTDDPhase:
    """Tests for TDDPhase enum."""

    def test_red_value(self) -> None:
        assert TDDPhase.RED.value == "red"

    def test_green_value(self) -> None:
        assert TDDPhase.GREEN.value == "green"

    def test_refactor_value(self) -> None:
        assert TDDPhase.REFACTOR.value == "refactor"

    def test_phase_count(self) -> None:
        assert len(TDDPhase) == 3


class TestTDDAntiPattern:
    """Tests for TDDAntiPattern enum."""

    def test_mock_heavy_value(self) -> None:
        assert TDDAntiPattern.MOCK_HEAVY.value == "mock_heavy"

    def test_testing_impl_value(self) -> None:
        assert TDDAntiPattern.TESTING_IMPL.value == "testing_impl"

    def test_no_assertions_value(self) -> None:
        assert TDDAntiPattern.NO_ASSERTIONS.value == "no_assertions"

    def test_large_tests_value(self) -> None:
        assert TDDAntiPattern.LARGE_TESTS.value == "large_tests"

    def test_no_arrange_act_assert_value(self) -> None:
        assert TDDAntiPattern.NO_ARRANGE_ACT_ASSERT.value == "no_arrange_act_assert"

    def test_anti_pattern_count(self) -> None:
        assert len(TDDAntiPattern) == 5


# ── TDDCycleResult Tests ────────────────────────────────────────────


class TestTDDCycleResult:
    """Tests for TDDCycleResult dataclass."""

    def test_creation_minimal(self) -> None:
        result = TDDCycleResult(
            phase=TDDPhase.RED,
            test_file="test_foo.py",
            implementation_file=None,
            tests_passing=False,
        )
        assert result.phase == TDDPhase.RED
        assert result.test_file == "test_foo.py"
        assert result.implementation_file is None
        assert result.tests_passing is False
        assert result.anti_patterns_found == []
        assert result.notes == ""
        assert isinstance(result.timestamp, datetime)

    def test_creation_full(self) -> None:
        ts = datetime(2026, 1, 15, 10, 30, 0)
        result = TDDCycleResult(
            phase=TDDPhase.GREEN,
            test_file="test_bar.py",
            implementation_file="bar.py",
            tests_passing=True,
            anti_patterns_found=[TDDAntiPattern.MOCK_HEAVY],
            timestamp=ts,
            notes="First pass",
        )
        assert result.phase == TDDPhase.GREEN
        assert result.implementation_file == "bar.py"
        assert result.tests_passing is True
        assert result.anti_patterns_found == [TDDAntiPattern.MOCK_HEAVY]
        assert result.timestamp == ts
        assert result.notes == "First pass"

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
        assert d["test_file"] == "test_x.py"
        assert d["implementation_file"] == "x.py"
        assert d["tests_passing"] is False
        assert d["anti_patterns"] == ["no_assertions"]
        assert d["timestamp"] == ts.isoformat()
        assert d["notes"] == "note"

    def test_to_dict_empty_anti_patterns(self) -> None:
        result = TDDCycleResult(
            phase=TDDPhase.REFACTOR,
            test_file="t.py",
            implementation_file=None,
            tests_passing=True,
        )
        d = result.to_dict()
        assert d["anti_patterns"] == []


# ── TDDReport Tests ─────────────────────────────────────────────────


class TestTDDReport:
    """Tests for TDDReport dataclass."""

    def test_creation(self) -> None:
        report = TDDReport(
            cycles=[],
            compliant=True,
            red_green_enforced=True,
            anti_patterns_total=0,
            total_cycles=0,
        )
        assert report.compliant is True
        assert report.total_cycles == 0

    def test_to_dict(self) -> None:
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
        assert d["red_green_enforced"] is False
        assert d["anti_patterns_total"] == 1
        assert d["total_cycles"] == 1
        assert len(d["cycles"]) == 1
        assert d["cycles"][0]["phase"] == "red"

    def test_to_dict_empty_cycles(self) -> None:
        report = TDDReport(
            cycles=[],
            compliant=True,
            red_green_enforced=True,
            anti_patterns_total=0,
            total_cycles=0,
        )
        d = report.to_dict()
        assert d["cycles"] == []


# ── TestFirstValidator Tests ────────────────────────────────────────


class TestTestFirstValidator:
    """Tests for TestFirstValidator."""

    def test_record_cycle_adds_to_list(self) -> None:
        v = TestFirstValidator()
        result = TDDCycleResult(
            phase=TDDPhase.RED,
            test_file="t.py",
            implementation_file=None,
            tests_passing=False,
        )
        v.record_cycle(result)
        assert len(v.cycles) == 1
        assert v.cycles[0].phase == TDDPhase.RED

    def test_cycles_returns_copy(self) -> None:
        v = TestFirstValidator()
        result = TDDCycleResult(
            phase=TDDPhase.RED,
            test_file="t.py",
            implementation_file=None,
            tests_passing=False,
        )
        v.record_cycle(result)
        cycles = v.cycles
        cycles.clear()
        assert len(v.cycles) == 1  # original unaffected

    # ── validate_red_green_order ──

    def test_validate_empty_cycles_passes(self) -> None:
        v = TestFirstValidator()
        valid, errors = v.validate_red_green_order()
        assert valid is True
        assert errors == []

    def test_validate_correct_red_green_refactor(self) -> None:
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
        v.record_cycle(
            TDDCycleResult(
                phase=TDDPhase.REFACTOR,
                test_file="t.py",
                implementation_file="impl.py",
                tests_passing=True,
            )
        )
        valid, errors = v.validate_red_green_order()
        assert valid is True
        assert errors == []

    def test_validate_red_green_without_refactor(self) -> None:
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
        valid, errors = v.validate_red_green_order()
        assert valid is True
        assert errors == []

    def test_validate_red_with_passing_tests_fails(self) -> None:
        v = TestFirstValidator()
        v.record_cycle(
            TDDCycleResult(
                phase=TDDPhase.RED,
                test_file="t.py",
                implementation_file=None,
                tests_passing=True,
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
        valid, errors = v.validate_red_green_order()
        assert valid is False
        assert any("RED phase has passing tests" in e for e in errors)

    def test_validate_green_with_failing_tests_fails(self) -> None:
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
                tests_passing=False,
            )
        )
        valid, errors = v.validate_red_green_order()
        assert valid is False
        assert any("GREEN phase has failing tests" in e for e in errors)

    def test_validate_refactor_breaking_tests_fails(self) -> None:
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
        v.record_cycle(
            TDDCycleResult(
                phase=TDDPhase.REFACTOR,
                test_file="t.py",
                implementation_file="impl.py",
                tests_passing=False,
            )
        )
        valid, errors = v.validate_red_green_order()
        assert valid is False
        assert any("REFACTOR phase broke tests" in e for e in errors)

    def test_validate_wrong_phase_order_fails(self) -> None:
        v = TestFirstValidator()
        # Start with GREEN instead of RED
        v.record_cycle(
            TDDCycleResult(
                phase=TDDPhase.GREEN,
                test_file="t.py",
                implementation_file="impl.py",
                tests_passing=True,
            )
        )
        valid, errors = v.validate_red_green_order()
        assert valid is False
        assert any("Expected RED phase" in e for e in errors)

    def test_validate_multiple_complete_cycles(self) -> None:
        v = TestFirstValidator()
        # Cycle 1
        v.record_cycle(
            TDDCycleResult(
                phase=TDDPhase.RED,
                test_file="t1.py",
                implementation_file=None,
                tests_passing=False,
            )
        )
        v.record_cycle(
            TDDCycleResult(
                phase=TDDPhase.GREEN,
                test_file="t1.py",
                implementation_file="impl1.py",
                tests_passing=True,
            )
        )
        v.record_cycle(
            TDDCycleResult(
                phase=TDDPhase.REFACTOR,
                test_file="t1.py",
                implementation_file="impl1.py",
                tests_passing=True,
            )
        )
        # Cycle 2
        v.record_cycle(
            TDDCycleResult(
                phase=TDDPhase.RED,
                test_file="t2.py",
                implementation_file=None,
                tests_passing=False,
            )
        )
        v.record_cycle(
            TDDCycleResult(
                phase=TDDPhase.GREEN,
                test_file="t2.py",
                implementation_file="impl2.py",
                tests_passing=True,
            )
        )
        valid, errors = v.validate_red_green_order()
        assert valid is True
        assert errors == []

    # ── detect_anti_patterns ──

    def test_detect_mock_heavy(self) -> None:
        v = TestFirstValidator()
        code = "\n".join(
            [
                "from unittest.mock import Mock, patch",
                "mock1 = Mock()",
                "mock2 = Mock()",
                "mock3 = Mock()",
                "mock4 = Mock()",
                "mock5 = Mock()",
                "mock6 = Mock()",
            ]
        )
        # "mock" appears many times, "Mock" counts via lower()
        detected = v.detect_anti_patterns(code)
        assert TDDAntiPattern.MOCK_HEAVY in detected

    def test_detect_no_assertions(self) -> None:
        v = TestFirstValidator()
        code = "\n".join(
            [
                "def test_something():",
                "    x = 1 + 1",
                "def test_another():",
                "    assert x == 2",
            ]
        )
        detected = v.detect_anti_patterns(code)
        assert TDDAntiPattern.NO_ASSERTIONS in detected

    def test_detect_testing_impl(self) -> None:
        v = TestFirstValidator()
        code = "\n".join(
            [
                "obj._private_method()",
                "obj.__internal()",
                "mock.called_with(x)",
                "assert mock.call_count == 3",
            ]
        )
        detected = v.detect_anti_patterns(code)
        assert TDDAntiPattern.TESTING_IMPL in detected

    def test_detect_clean_code_returns_empty(self) -> None:
        v = TestFirstValidator()
        code = "\n".join(
            [
                "def test_addition():",
                "    result = add(1, 2)",
                "    assert result == 3",
            ]
        )
        detected = v.detect_anti_patterns(code)
        assert detected == []

    def test_detect_with_custom_filter(self) -> None:
        v = TestFirstValidator(anti_patterns=["mock_heavy"])
        code = "\n".join(
            [
                "def test_something():",
                "    x = 1 + 1",
                "def test_another():",
                "    assert x == 2",
            ]
        )
        detected = v.detect_anti_patterns(code)
        # no_assertions is not in the filter, so should not be detected
        assert TDDAntiPattern.NO_ASSERTIONS not in detected

    def test_detect_mock_heavy_below_threshold(self) -> None:
        v = TestFirstValidator()
        code = "mock1 = Mock()\nmock2 = Mock()"
        detected = v.detect_anti_patterns(code)
        assert TDDAntiPattern.MOCK_HEAVY not in detected

    # ── get_report ──

    def test_report_compliant_when_valid_no_anti_patterns(self) -> None:
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
        assert report.compliant is True
        assert report.red_green_enforced is True
        assert report.anti_patterns_total == 0
        assert report.total_cycles == 2

    def test_report_non_compliant_with_anti_patterns(self) -> None:
        v = TestFirstValidator()
        v.record_cycle(
            TDDCycleResult(
                phase=TDDPhase.RED,
                test_file="t.py",
                implementation_file=None,
                tests_passing=False,
                anti_patterns_found=[TDDAntiPattern.MOCK_HEAVY],
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
        assert report.compliant is False
        assert report.anti_patterns_total == 1

    def test_report_non_compliant_with_order_violation(self) -> None:
        v = TestFirstValidator()
        v.record_cycle(
            TDDCycleResult(
                phase=TDDPhase.GREEN,
                test_file="t.py",
                implementation_file="impl.py",
                tests_passing=True,
            )
        )
        report = v.get_report()
        assert report.compliant is False
        assert report.red_green_enforced is False

    # ── clear ──

    def test_clear_resets_state(self) -> None:
        v = TestFirstValidator()
        v.record_cycle(
            TDDCycleResult(
                phase=TDDPhase.RED,
                test_file="t.py",
                implementation_file=None,
                tests_passing=False,
            )
        )
        assert len(v.cycles) == 1
        v.clear()
        assert len(v.cycles) == 0


# ── TDDProtocol Tests ───────────────────────────────────────────────


class TestTDDProtocol:
    """Tests for TDDProtocol."""

    def test_start_cycle_returns_red(self) -> None:
        p = TDDProtocol()
        phase = p.start_cycle("test_foo.py")
        assert phase == TDDPhase.RED
        assert p.current_phase == TDDPhase.RED

    def test_advance_red_to_green(self) -> None:
        p = TDDProtocol()
        p.start_cycle("t.py")
        phase = p.advance_phase()
        assert phase == TDDPhase.GREEN

    def test_advance_green_to_refactor(self) -> None:
        p = TDDProtocol()
        p.start_cycle("t.py")
        p.advance_phase()  # -> GREEN
        phase = p.advance_phase()
        assert phase == TDDPhase.REFACTOR

    def test_advance_refactor_to_none(self) -> None:
        p = TDDProtocol()
        p.start_cycle("t.py")
        p.advance_phase()  # -> GREEN
        p.advance_phase()  # -> REFACTOR
        phase = p.advance_phase()
        assert phase is None
        assert p.current_phase is None

    def test_advance_from_none_returns_none(self) -> None:
        p = TDDProtocol()
        # No cycle started, current_phase is None
        phase = p.advance_phase()
        assert phase is None

    def test_record_result_creates_result(self) -> None:
        p = TDDProtocol()
        p.start_cycle("test_foo.py")
        result = p.record_result(
            test_file="test_foo.py",
            tests_passing=False,
            implementation_file=None,
            notes="initial red",
        )
        assert result.phase == TDDPhase.RED
        assert result.tests_passing is False
        assert result.notes == "initial red"

    def test_record_result_detects_anti_patterns(self) -> None:
        p = TDDProtocol()
        p.start_cycle("t.py")
        mock_heavy_code = "\n".join([f"mock{i} = Mock()" for i in range(15)])
        result = p.record_result(
            test_file="t.py",
            tests_passing=False,
            test_content=mock_heavy_code,
        )
        assert TDDAntiPattern.MOCK_HEAVY in result.anti_patterns_found

    def test_record_result_without_content(self) -> None:
        p = TDDProtocol()
        p.start_cycle("t.py")
        result = p.record_result(
            test_file="t.py",
            tests_passing=False,
        )
        assert result.anti_patterns_found == []

    def test_is_compliant_disabled_always_true(self) -> None:
        p = TDDProtocol(enabled=False)
        # Record bad order
        p.start_cycle("t.py")
        p.record_result(test_file="t.py", tests_passing=True)
        assert p.is_compliant() is True

    def test_is_compliant_reflects_validator_state(self) -> None:
        p = TDDProtocol(enabled=True)
        p.start_cycle("t.py")
        p.record_result(test_file="t.py", tests_passing=False)
        p.advance_phase()
        p.record_result(
            test_file="t.py",
            tests_passing=True,
            implementation_file="impl.py",
        )
        assert p.is_compliant() is True

    def test_is_compliant_false_with_bad_order(self) -> None:
        p = TDDProtocol(enabled=True)
        # Record RED with passing tests
        p.start_cycle("t.py")
        p.record_result(test_file="t.py", tests_passing=True)
        p.advance_phase()
        p.record_result(test_file="t.py", tests_passing=True)
        assert p.is_compliant() is False

    def test_get_report_returns_validator_report(self) -> None:
        p = TDDProtocol()
        p.start_cycle("t.py")
        p.record_result(test_file="t.py", tests_passing=False)
        report = p.get_report()
        assert isinstance(report, TDDReport)
        assert report.total_cycles == 1

    def test_current_phase_initially_none(self) -> None:
        p = TDDProtocol()
        assert p.current_phase is None

    def test_full_cycle_workflow(self) -> None:
        """Test a complete RED -> GREEN -> REFACTOR cycle."""
        p = TDDProtocol()

        # RED: write failing test
        p.start_cycle("test_calc.py")
        assert p.current_phase == TDDPhase.RED
        p.record_result(test_file="test_calc.py", tests_passing=False)

        # GREEN: make it pass
        p.advance_phase()
        assert p.current_phase == TDDPhase.GREEN
        p.record_result(
            test_file="test_calc.py",
            tests_passing=True,
            implementation_file="calc.py",
        )

        # REFACTOR: clean up
        p.advance_phase()
        assert p.current_phase == TDDPhase.REFACTOR
        p.record_result(
            test_file="test_calc.py",
            tests_passing=True,
            implementation_file="calc.py",
        )

        # Cycle complete
        p.advance_phase()
        assert p.current_phase is None
        assert p.is_compliant() is True


# ── TDDConfig Tests ─────────────────────────────────────────────────


class TestTDDConfig:
    """Tests for TDDConfig in config.py."""

    def test_default_values(self) -> None:
        config = TDDConfig()
        assert config.enabled is False
        assert config.enforce_red_green is True
        assert config.anti_patterns == [
            "mock_heavy",
            "testing_impl",
            "no_assertions",
        ]

    def test_custom_values(self) -> None:
        config = TDDConfig(
            enabled=True,
            enforce_red_green=False,
            anti_patterns=["mock_heavy"],
        )
        assert config.enabled is True
        assert config.enforce_red_green is False
        assert config.anti_patterns == ["mock_heavy"]

    def test_zerg_config_has_tdd(self) -> None:
        config = ZergConfig()
        assert hasattr(config, "tdd")
        assert isinstance(config.tdd, TDDConfig)
        assert config.tdd.enabled is False

    def test_zerg_config_tdd_from_dict(self) -> None:
        data = {"tdd": {"enabled": True, "enforce_red_green": False}}
        config = ZergConfig.from_dict(data)
        assert config.tdd.enabled is True
        assert config.tdd.enforce_red_green is False

    def test_zerg_config_tdd_roundtrip(self) -> None:
        config = ZergConfig()
        config.tdd.enabled = True
        d = config.to_dict()
        assert d["tdd"]["enabled"] is True
        loaded = ZergConfig.from_dict(d)
        assert loaded.tdd.enabled is True

    def test_empty_anti_patterns(self) -> None:
        config = TDDConfig(anti_patterns=[])
        assert config.anti_patterns == []


# ── CLI --tdd Flag Tests ────────────────────────────────────────────


class TestCLITddFlag:
    """Tests for --tdd CLI flag."""

    def test_tdd_flag_in_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "--tdd" in result.output

    def test_tdd_flag_accepted(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--tdd", "--help"])
        assert result.exit_code == 0
