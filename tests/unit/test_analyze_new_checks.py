"""Unit tests for new analyze checker classes — thinned Phase 4/5."""

from unittest.mock import MagicMock, patch

from zerg.commands.analyze import (
    AnalysisResult,
    AnalyzeCommand,
    AnalyzeConfig,
    CheckType,
    ContextEngineeringChecker,
    ConventionsChecker,
    CrossFileChecker,
    DeadCodeChecker,
    ImportChainChecker,
    WiringChecker,
)


class TestDeadCodeChecker:
    def test_no_files_returns_passed(self):
        result = DeadCodeChecker(min_confidence=80).check([])
        assert result.passed is True and result.check_type == CheckType.DEAD_CODE

    def test_vulture_not_installed(self):
        checker = DeadCodeChecker(min_confidence=80)
        with patch.object(checker, "_executor") as mock_exec:
            mock_exec.sanitize_paths.return_value = ["test.py"]
            mock_exec.execute.side_effect = FileNotFoundError("vulture not found")
            result = checker.check(["test.py"])
        assert result.passed is True
        assert any("vulture not installed" in i for i in result.issues)

    def test_vulture_finds_dead_code(self):
        checker = DeadCodeChecker(min_confidence=80)
        mock_result = MagicMock(success=False)
        mock_result.stdout = (
            "test.py:10: unused function 'foo' (80% confidence)\ntest.py:20: unused import 'bar' (90% confidence)"
        )
        with patch.object(checker, "_executor") as mock_exec:
            mock_exec.sanitize_paths.return_value = ["test.py"]
            mock_exec.execute.return_value = mock_result
            result = checker.check(["test.py"])
        assert result.passed is False and len(result.issues) == 2


class TestWiringChecker:
    def test_wiring_passed(self):
        with patch("zerg.validate_commands.validate_module_wiring", return_value=(True, [])):
            result = WiringChecker(strict=False).check([])
        assert result.passed is True and result.check_type == CheckType.WIRING

    def test_wiring_failed(self):
        with patch("zerg.validate_commands.validate_module_wiring", return_value=(False, ["orphaned: foo.py"])):
            result = WiringChecker(strict=True).check([])
        assert result.passed is False and len(result.issues) == 1


class TestConventionsChecker:
    def test_snake_case_valid(self):
        result = ConventionsChecker().check(["zerg/foo_bar.py", "zerg/baz.py"])
        assert len([i for i in result.issues if "Naming violation" in i]) == 0

    def test_snake_case_invalid(self):
        result = ConventionsChecker().check(["zerg/FooBar.py"])
        assert len([i for i in result.issues if "Naming violation" in i]) == 1

    def test_file_organization_test_outside_tests_dir(self):
        result = ConventionsChecker(require_task_prefixes=False).check(["zerg/test_something.py"])
        assert len([i for i in result.issues if "File organization" in i]) == 1


class TestCrossFileChecker:
    def test_nonexistent_scope_returns_passed(self):
        result = CrossFileChecker(scope="nonexistent_dir_xyz/").check([])
        assert result.passed is True and result.check_type == CheckType.CROSS_FILE


class TestImportChainChecker:
    def test_default_max_depth(self):
        checker = ImportChainChecker()
        assert checker.max_depth == 10
        assert checker.check([]).check_type == CheckType.IMPORT_CHAIN


class TestContextEngineeringChecker:
    def test_passed(self):
        with patch("zerg.validate_commands.validate_all", return_value=(True, [])):
            result = ContextEngineeringChecker(auto_split=False).check([])
        assert result.passed is True and result.check_type == CheckType.CONTEXT_ENGINEERING

    def test_failed(self):
        with patch("zerg.validate_commands.validate_all", return_value=(False, ["missing task refs", "bad split"])):
            result = ContextEngineeringChecker(auto_split=False).check([])
        assert result.passed is False and len(result.issues) == 2


class TestAnalyzeCommandCheckerRegistration:
    def test_all_11_checkers_registered(self):
        cmd = AnalyzeCommand()
        assert len(cmd.checkers) == 11

    def test_check_all_runs_everything(self):
        cmd = AnalyzeCommand()
        for checker in cmd.checkers.values():
            checker.check = MagicMock(
                return_value=AnalysisResult(check_type=CheckType.LINT, passed=True, issues=[], score=100.0)
            )
        assert len(cmd.run(["all"], [])) == 11

    def test_config_propagated(self):
        config = AnalyzeConfig(dead_code_min_confidence=95, wiring_strict=True, import_chain_max_depth=5)
        cmd = AnalyzeCommand(config=config)
        assert cmd.checkers["dead-code"].min_confidence == 95
        assert cmd.checkers["wiring"].strict is True
        assert cmd.checkers["import-chain"].max_depth == 5
