"""Unit tests for zerg/commands/plan.py.

Thinned from 65 tests to cover unique code paths:
- Feature name sanitization (parametrized)
- GitHub issue import (happy + error)
- Template creation (1 per type + fallback)
- Socratic/interactive discovery (key paths)
- Requirements writing/formatting
- CLI command (help, basic, errors)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from zerg.cli import cli
from zerg.commands.plan import (
    create_requirements_template,
    format_socratic_requirements,
    format_standard_requirements,
    get_default_template,
    get_detailed_template,
    import_from_github_issue,
    run_interactive_discovery,
    run_socratic_discovery,
    sanitize_feature_name,
    write_requirements,
)


class TestSanitizeFeatureName:
    """Tests for sanitize_feature_name function."""

    @pytest.mark.parametrize(
        "input_name,expected",
        [
            ("MyFeature", "myfeature"),
            ("my feature", "my-feature"),
            ("feature!@#$%", "feature"),
            ("feature123", "feature123"),
            ("user-auth", "user-auth"),
            ("My Feature (v2)!", "my-feature-v2"),
            ("!@#$%", ""),
        ],
    )
    def test_sanitize_feature_name(self, input_name: str, expected: str) -> None:
        """Test feature name sanitization handles various inputs."""
        assert sanitize_feature_name(input_name) == expected


class TestImportFromGitHubIssue:
    """Tests for import_from_github_issue function."""

    def test_successful_import(self) -> None:
        """Test successful GitHub issue import."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {"title": "Add User Authentication", "body": "Implement user auth system", "labels": [{"name": "feature"}]}
        )

        with patch("subprocess.run", return_value=mock_result):
            result = import_from_github_issue("https://github.com/org/repo/issues/123")

        assert result == "add-user-authentication"

    @pytest.mark.parametrize(
        "side_effect",
        [FileNotFoundError(), Exception("Network error")],
    )
    def test_import_failure_returns_none(self, side_effect: Exception) -> None:
        """Test handling of various import failures."""
        with patch("subprocess.run", side_effect=side_effect):
            result = import_from_github_issue("https://github.com/org/repo/issues/123")
        assert result is None


class TestCreateRequirementsTemplate:
    """Tests for create_requirements_template function."""

    @pytest.mark.parametrize(
        "template_type,should_contain,should_not_contain",
        [
            ("minimal", ["Problem Statement", "Out of Scope"], ["Risk Assessment"]),
            ("default", ["Functional Requirements", "Acceptance Criteria"], []),
            ("detailed", ["Technical Constraints", "Risk Assessment", "Success Metrics"], []),
            ("unknown", ["**Author**: ZERG Plan"], []),
        ],
    )
    def test_template_creation(
        self, tmp_path: Path, template_type: str, should_contain: list[str], should_not_contain: list[str]
    ) -> None:
        """Test template creation for all template types."""
        spec_dir = tmp_path / "specs" / "test-feature"
        spec_dir.mkdir(parents=True)
        create_requirements_template(spec_dir, "test-feature", template_type)
        content = (spec_dir / "requirements.md").read_text()
        assert "# Feature Requirements: test-feature" in content
        for text in should_contain:
            assert text in content, f"Missing: {text}"
        for text in should_not_contain:
            assert text not in content, f"Unexpected: {text}"


class TestGetTemplates:
    """Tests for get_default_template and get_detailed_template."""

    def test_default_template_contains_required_sections(self) -> None:
        """Test that default template contains all required sections."""
        content = get_default_template("test-feature", "2026-01-26T10:00:00")
        for section in ["Feature Requirements", "Problem Statement", "Functional Requirements", "Acceptance Criteria"]:
            assert section in content, f"Missing section: {section}"

    def test_detailed_extends_default(self) -> None:
        """Test that detailed template extends default with additional sections."""
        ts = "2026-01-26T10:00:00"
        default = get_default_template("test", ts)
        detailed = get_detailed_template("test", ts)
        assert len(detailed) > len(default)
        for section in ["Technical Constraints", "Risk Assessment", "Success Metrics"]:
            assert section in detailed


class TestRunSocraticDiscovery:
    """Tests for run_socratic_discovery function."""

    def test_three_rounds(self) -> None:
        """Test socratic discovery with three rounds (default)."""
        with patch("zerg.commands.plan.ask_questions") as mock_ask:
            mock_ask.return_value = {"Q": "A"}
            result = run_socratic_discovery("test-feature", rounds=3)

        assert len(result["transcript"]) == 3
        assert "problem_space" in result
        assert "solution_space" in result
        assert "implementation_space" in result

    def test_zero_rounds(self) -> None:
        """Test socratic discovery with zero rounds."""
        result = run_socratic_discovery("test-feature", rounds=0)
        assert result["feature"] == "test-feature"
        assert len(result["transcript"]) == 0


class TestRunInteractiveDiscovery:
    """Tests for run_interactive_discovery function."""

    def test_collects_all_answers(self) -> None:
        """Test that interactive discovery collects all required answers."""
        with patch("zerg.commands.plan.Prompt.ask") as mock_prompt:
            mock_prompt.side_effect = [
                "Solve user login",
                "End users",
                "Username, password",
                "JWT token",
                "2FA",
                "All tests pass",
            ]
            result = run_interactive_discovery("auth", "default")

        assert result["feature"] == "auth"
        assert result["problem"] == "Solve user login"
        assert result["acceptance"] == "All tests pass"


class TestWriteRequirements:
    """Tests for write_requirements function."""

    def test_writes_socratic_format(self, tmp_path: Path) -> None:
        """Test writing socratic discovery results."""
        spec_dir = tmp_path / "specs" / "test"
        spec_dir.mkdir(parents=True)
        requirements = {
            "feature": "test",
            "transcript": [("Problem Space", {"Q1": "A1"})],
            "problem_space": {"Q1": "A1"},
            "solution_space": {},
            "implementation_space": {},
        }
        write_requirements(spec_dir, "test", requirements)
        content = (spec_dir / "requirements.md").read_text()
        assert "**Method**: Socratic Discovery" in content

    def test_writes_standard_format(self, tmp_path: Path) -> None:
        """Test writing standard discovery results."""
        spec_dir = tmp_path / "specs" / "test"
        spec_dir.mkdir(parents=True)
        requirements = {
            "feature": "test",
            "problem": "The problem",
            "users": "The users",
            "inputs": "The inputs",
            "outputs": "The outputs",
            "out_of_scope": "Not this",
            "acceptance": "Tests pass",
        }
        write_requirements(spec_dir, "test", requirements)
        content = (spec_dir / "requirements.md").read_text()
        assert "**Author**: ZERG Plan" in content
        assert "The problem" in content


class TestFormatRequirements:
    """Tests for format_socratic_requirements and format_standard_requirements."""

    def test_socratic_includes_transcript(self) -> None:
        """Test that transcript is included in socratic format."""
        req = {
            "transcript": [("Problem Space", {"What is it?": "A feature"})],
            "problem_space": {"What is it?": "A feature"},
            "solution_space": {},
            "implementation_space": {},
        }
        content = format_socratic_requirements("test", "2026-01-26T10:00:00", req)
        assert "### Problem Space" in content
        assert "**Q:** What is it?" in content

    def test_standard_includes_all_fields(self) -> None:
        """Test that all requirement fields are included in standard format."""
        req = {
            "problem": "The problem",
            "users": "The users",
            "inputs": "I",
            "outputs": "O",
            "out_of_scope": "N",
            "acceptance": "T",
        }
        content = format_standard_requirements("test", "2026-01-26T10:00:00", req)
        assert "The problem" in content
        assert "The users" in content

    def test_standard_missing_fields_use_default(self) -> None:
        """Test that missing fields use default text."""
        content = format_standard_requirements("test", "2026-01-26T10:00:00", {})
        assert "_To be defined_" in content


class TestPlanCommand:
    """Tests for the plan CLI command."""

    def test_plan_help(self) -> None:
        """Test plan --help shows usage information."""
        runner = CliRunner()
        result = runner.invoke(cli, ["plan", "--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "--template" in result.output

    def test_plan_non_interactive_creates_requirements(self, tmp_path: Path, monkeypatch) -> None:
        """Test non-interactive plan creates requirements file."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)
        runner = CliRunner()
        result = runner.invoke(cli, ["plan", "test-feature", "--no-interactive"])
        assert result.exit_code == 0
        assert (tmp_path / ".gsd" / "specs" / "test-feature" / "requirements.md").exists()

    def test_plan_requires_feature_non_interactive(self, tmp_path: Path, monkeypatch) -> None:
        """Test plan requires feature name in non-interactive mode."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)
        runner = CliRunner()
        result = runner.invoke(cli, ["plan", "--no-interactive"])
        assert result.exit_code == 1
        assert "required" in result.output.lower()

    def test_plan_with_from_issue_success(self, tmp_path: Path, monkeypatch) -> None:
        """Test plan with --from-issue flag."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"title": "Add Feature", "body": "", "labels": []})
        with patch("subprocess.run", return_value=mock_result):
            runner = CliRunner()
            result = runner.invoke(
                cli, ["plan", "--from-issue", "https://github.com/org/repo/issues/1", "--no-interactive"]
            )
        assert result.exit_code == 0

    def test_plan_keyboard_interrupt(self, tmp_path: Path, monkeypatch) -> None:
        """Test that keyboard interrupt is handled gracefully."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)
        with patch("zerg.commands.plan.run_interactive_discovery", side_effect=KeyboardInterrupt()):
            runner = CliRunner()
            result = runner.invoke(cli, ["plan", "test"])
            assert result.exit_code == 130

    def test_plan_general_exception(self, tmp_path: Path, monkeypatch) -> None:
        """Test that general exceptions are handled."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)
        with (
            patch("zerg.commands.plan.write_requirements", side_effect=OSError("Disk full")),
            patch("zerg.commands.plan.run_interactive_discovery") as mock_discovery,
        ):
            mock_discovery.return_value = {"feature": "test", "problem": "p"}
            runner = CliRunner()
            result = runner.invoke(cli, ["plan", "test"])
            assert result.exit_code == 1
            assert "Error" in result.output
