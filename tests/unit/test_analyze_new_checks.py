"""Unit tests for new analyze checker classes."""

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
        checker = DeadCodeChecker(min_confidence=80)
        result = checker.check([])
        assert result.passed is True
        assert result.check_type == CheckType.DEAD_CODE
        assert result.score == 100.0

    def test_vulture_not_installed_file_not_found(self):
        checker = DeadCodeChecker(min_confidence=80)
        with patch.object(checker, "_executor") as mock_exec:
            mock_exec.sanitize_paths.return_value = ["test.py"]
            mock_exec.execute.side_effect = FileNotFoundError("vulture not found")
            result = checker.check(["test.py"])
        assert result.passed is True
        assert any("vulture not installed" in i for i in result.issues)

    def test_vulture_not_installed_command_validation_error(self):
        from zerg.command_executor import CommandValidationError

        checker = DeadCodeChecker(min_confidence=80)
        with patch.object(checker, "_executor") as mock_exec:
            mock_exec.sanitize_paths.return_value = ["test.py"]
            mock_exec.execute.side_effect = CommandValidationError("not found")
            result = checker.check(["test.py"])
        assert result.passed is True
        assert any("vulture not installed" in i for i in result.issues)

    def test_min_confidence_stored(self):
        checker = DeadCodeChecker(min_confidence=90)
        assert checker.min_confidence == 90

    def test_vulture_success(self):
        checker = DeadCodeChecker(min_confidence=80)
        mock_result = MagicMock()
        mock_result.success = True
        with patch.object(checker, "_executor") as mock_exec:
            mock_exec.sanitize_paths.return_value = ["test.py"]
            mock_exec.execute.return_value = mock_result
            result = checker.check(["test.py"])
        assert result.passed is True
        assert result.score == 100.0

    def test_vulture_finds_dead_code(self):
        checker = DeadCodeChecker(min_confidence=80)
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.stdout = (
            "test.py:10: unused function 'foo' (80% confidence)\ntest.py:20: unused import 'bar' (90% confidence)"
        )
        with patch.object(checker, "_executor") as mock_exec:
            mock_exec.sanitize_paths.return_value = ["test.py"]
            mock_exec.execute.return_value = mock_result
            result = checker.check(["test.py"])
        assert result.passed is False
        assert len(result.issues) == 2
        assert result.score == 90.0  # 100 - 2*5

    def test_generic_exception(self):
        checker = DeadCodeChecker(min_confidence=80)
        with patch.object(checker, "_executor") as mock_exec:
            mock_exec.sanitize_paths.return_value = ["test.py"]
            mock_exec.execute.side_effect = RuntimeError("unexpected")
            result = checker.check(["test.py"])
        assert result.passed is False
        assert result.score == 0.0


class TestWiringChecker:
    def test_wiring_passed(self):
        checker = WiringChecker(strict=False)
        with patch(
            "zerg.validate_commands.validate_module_wiring",
            return_value=(True, []),
        ):
            result = checker.check([])
        assert result.passed is True
        assert result.check_type == CheckType.WIRING
        assert result.score == 100.0

    def test_wiring_failed(self):
        checker = WiringChecker(strict=True)
        with patch(
            "zerg.validate_commands.validate_module_wiring",
            return_value=(False, ["orphaned: foo.py"]),
        ):
            result = checker.check([])
        assert result.passed is False
        assert len(result.issues) == 1
        assert result.score == 90.0  # 100 - 1*10

    def test_import_error_handled(self):
        checker = WiringChecker()
        with patch.dict("sys.modules", {"zerg.validate_commands": None}):
            result = checker.check([])
        assert result.passed is False
        assert any("Could not import" in i for i in result.issues)

    def test_generic_exception_handled(self):
        checker = WiringChecker()
        with patch(
            "zerg.validate_commands.validate_module_wiring",
            side_effect=RuntimeError("boom"),
        ):
            result = checker.check([])
        assert result.passed is False
        assert any("Wiring check error" in i for i in result.issues)

    def test_default_strict_false(self):
        checker = WiringChecker()
        assert checker.strict is False


class TestConventionsChecker:
    def test_snake_case_valid(self):
        checker = ConventionsChecker()
        result = checker.check(["zerg/foo_bar.py", "zerg/baz.py"])
        snake_issues = [i for i in result.issues if "Naming violation" in i]
        assert len(snake_issues) == 0

    def test_snake_case_invalid_camel_case(self):
        checker = ConventionsChecker()
        result = checker.check(["zerg/FooBar.py"])
        snake_issues = [i for i in result.issues if "Naming violation" in i]
        assert len(snake_issues) == 1

    def test_snake_case_invalid_hyphenated(self):
        checker = ConventionsChecker()
        result = checker.check(["zerg/my-module.py"])
        snake_issues = [i for i in result.issues if "Naming violation" in i]
        assert len(snake_issues) == 1

    def test_dunder_files_skipped(self):
        checker = ConventionsChecker()
        result = checker.check(["zerg/__init__.py", "zerg/__main__.py"])
        snake_issues = [i for i in result.issues if "Naming violation" in i]
        assert len(snake_issues) == 0

    def test_non_python_files_ignored(self):
        checker = ConventionsChecker()
        result = checker.check(["zerg/FooBar.js", "zerg/CamelCase.ts"])
        snake_issues = [i for i in result.issues if "Naming violation" in i]
        assert len(snake_issues) == 0

    def test_check_type(self):
        checker = ConventionsChecker()
        result = checker.check([])
        assert result.check_type == CheckType.CONVENTIONS

    def test_file_organization_test_outside_tests_dir(self):
        checker = ConventionsChecker(require_task_prefixes=False)
        result = checker.check(["zerg/test_something.py"])
        org_issues = [i for i in result.issues if "File organization" in i]
        assert len(org_issues) == 1

    def test_file_organization_test_in_tests_dir(self):
        checker = ConventionsChecker(require_task_prefixes=False)
        result = checker.check(["tests/unit/test_something.py"])
        org_issues = [i for i in result.issues if "File organization" in i]
        assert len(org_issues) == 0

    def test_score_degrades_with_issues(self):
        checker = ConventionsChecker(require_task_prefixes=False)
        result = checker.check(["zerg/FooBar.py", "zerg/BazQux.py"])
        assert result.score < 100.0
        assert result.passed is False


class TestCrossFileChecker:
    def test_nonexistent_scope_returns_passed(self):
        checker = CrossFileChecker(scope="nonexistent_dir_xyz/")
        result = checker.check([])
        assert result.passed is True
        assert result.score == 100.0

    def test_check_type(self):
        checker = CrossFileChecker(scope="nonexistent_dir_xyz/")
        result = checker.check([])
        assert result.check_type == CheckType.CROSS_FILE

    def test_scope_stored(self):
        checker = CrossFileChecker(scope="src/")
        assert checker.scope == "src/"


class TestImportChainChecker:
    def test_max_depth_stored(self):
        checker = ImportChainChecker(max_depth=15)
        assert checker.max_depth == 15

    def test_default_max_depth(self):
        checker = ImportChainChecker()
        assert checker.max_depth == 10

    def test_check_type_is_import_chain(self):
        checker = ImportChainChecker()
        result = checker.check([])
        assert result.check_type == CheckType.IMPORT_CHAIN


class TestContextEngineeringChecker:
    def test_passed(self):
        checker = ContextEngineeringChecker(auto_split=False)
        with patch(
            "zerg.validate_commands.validate_all",
            return_value=(True, []),
        ):
            result = checker.check([])
        assert result.passed is True
        assert result.check_type == CheckType.CONTEXT_ENGINEERING
        assert result.score == 100.0

    def test_failed(self):
        checker = ContextEngineeringChecker(auto_split=False)
        with patch(
            "zerg.validate_commands.validate_all",
            return_value=(False, ["missing task refs", "bad split"]),
        ):
            result = checker.check([])
        assert result.passed is False
        assert len(result.issues) == 2
        assert result.score == 80.0  # 100 - 2*10

    def test_import_error_handled(self):
        checker = ContextEngineeringChecker()
        with patch.dict("sys.modules", {"zerg.validate_commands": None}):
            result = checker.check([])
        assert result.passed is False
        assert any("Could not import" in i for i in result.issues)

    def test_generic_exception_handled(self):
        checker = ContextEngineeringChecker()
        with patch(
            "zerg.validate_commands.validate_all",
            side_effect=RuntimeError("boom"),
        ):
            result = checker.check([])
        assert result.passed is False
        assert any("Context engineering check error" in i for i in result.issues)

    def test_auto_split_stored(self):
        checker = ContextEngineeringChecker(auto_split=True)
        assert checker.auto_split is True


class TestAnalyzeCommandCheckerRegistration:
    def test_all_11_checkers_registered(self):
        cmd = AnalyzeCommand()
        assert len(cmd.checkers) == 11

    def test_expected_checker_names(self):
        cmd = AnalyzeCommand()
        expected = {
            "lint",
            "complexity",
            "coverage",
            "security",
            "performance",
            "dead-code",
            "wiring",
            "cross-file",
            "conventions",
            "import-chain",
            "context-engineering",
        }
        assert set(cmd.checkers.keys()) == expected

    def test_check_all_runs_everything(self):
        cmd = AnalyzeCommand()
        for _name, checker in cmd.checkers.items():
            checker.check = MagicMock(
                return_value=AnalysisResult(
                    check_type=CheckType.LINT,
                    passed=True,
                    issues=[],
                    score=100.0,
                )
            )
        results = cmd.run(["all"], [])
        assert len(results) == 11

    def test_individual_check(self):
        cmd = AnalyzeCommand()
        cmd.checkers["wiring"].check = MagicMock(
            return_value=AnalysisResult(
                check_type=CheckType.WIRING,
                passed=True,
                issues=[],
                score=100.0,
            )
        )
        results = cmd.run(["wiring"], [])
        assert len(results) == 1
        assert results[0].check_type == CheckType.WIRING

    def test_unknown_check_ignored(self):
        cmd = AnalyzeCommand()
        results = cmd.run(["nonexistent-check"], [])
        assert len(results) == 0

    def test_config_propagated(self):
        config = AnalyzeConfig(
            dead_code_min_confidence=95,
            wiring_strict=True,
            import_chain_max_depth=5,
        )
        cmd = AnalyzeCommand(config=config)
        assert cmd.checkers["dead-code"].min_confidence == 95
        assert cmd.checkers["wiring"].strict is True
        assert cmd.checkers["import-chain"].max_depth == 5
