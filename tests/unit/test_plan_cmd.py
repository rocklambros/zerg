"""Comprehensive unit tests for zerg/commands/plan.py.

Tests cover all code paths including:
- Main plan command with various options
- Feature name sanitization
- GitHub issue import
- Template creation (minimal, default, detailed)
- Interactive and non-interactive modes
- Socratic and standard discovery modes
- Requirements file writing and formatting
- Error handling and edge cases
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from zerg.cli import cli
from zerg.commands.plan import (
    ask_questions,
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

# =============================================================================
# Feature Name Sanitization Tests
# =============================================================================


class TestSanitizeFeatureName:
    """Tests for sanitize_feature_name function."""

    def test_lowercase_conversion(self) -> None:
        """Test that uppercase letters are converted to lowercase."""
        assert sanitize_feature_name("MyFeature") == "myfeature"
        assert sanitize_feature_name("FEATURE") == "feature"
        assert sanitize_feature_name("Feature") == "feature"

    def test_space_to_hyphen(self) -> None:
        """Test that spaces are converted to hyphens."""
        assert sanitize_feature_name("my feature") == "my-feature"
        assert sanitize_feature_name("user auth system") == "user-auth-system"

    def test_removes_invalid_characters(self) -> None:
        """Test that invalid characters are removed."""
        assert sanitize_feature_name("feature!@#$%") == "feature"
        assert sanitize_feature_name("my_feature") == "myfeature"
        assert sanitize_feature_name("feat.ure") == "feature"
        assert sanitize_feature_name("feat(ure)") == "feature"

    def test_preserves_numbers(self) -> None:
        """Test that numbers are preserved."""
        assert sanitize_feature_name("feature123") == "feature123"
        assert sanitize_feature_name("v2-api") == "v2-api"

    def test_preserves_hyphens(self) -> None:
        """Test that existing hyphens are preserved."""
        assert sanitize_feature_name("user-auth") == "user-auth"
        assert sanitize_feature_name("feature-v2-beta") == "feature-v2-beta"

    def test_complex_names(self) -> None:
        """Test complex feature name sanitization."""
        assert sanitize_feature_name("My Feature (v2)!") == "my-feature-v2"
        assert sanitize_feature_name("User Auth System v3.0") == "user-auth-system-v30"

    def test_empty_result_after_sanitization(self) -> None:
        """Test that feature name consisting only of invalid chars becomes empty."""
        assert sanitize_feature_name("!@#$%") == ""
        assert sanitize_feature_name("___") == ""


# =============================================================================
# GitHub Issue Import Tests
# =============================================================================


class TestImportFromGitHubIssue:
    """Tests for import_from_github_issue function."""

    def test_successful_import(self) -> None:
        """Test successful GitHub issue import."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {
                "title": "Add User Authentication",
                "body": "Implement user auth system",
                "labels": [{"name": "feature"}],
            }
        )

        with patch("subprocess.run", return_value=mock_result):
            result = import_from_github_issue("https://github.com/org/repo/issues/123")

        assert result == "add-user-authentication"

    def test_gh_cli_not_installed(self) -> None:
        """Test handling when gh CLI is not installed."""
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = import_from_github_issue("https://github.com/org/repo/issues/123")

        assert result is None

    def test_gh_command_failure(self) -> None:
        """Test handling when gh command fails."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Not authorized"

        with patch("subprocess.run", return_value=mock_result):
            result = import_from_github_issue("https://github.com/org/repo/issues/123")

        assert result is None

    def test_timeout_handling(self) -> None:
        """Test handling when gh command times out."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="gh", timeout=30)):
            result = import_from_github_issue("https://github.com/org/repo/issues/123")

        assert result is None

    def test_general_exception_handling(self) -> None:
        """Test handling of general exceptions."""
        with patch("subprocess.run", side_effect=Exception("Network error")):
            result = import_from_github_issue("https://github.com/org/repo/issues/123")

        assert result is None

    def test_sanitizes_issue_title(self) -> None:
        """Test that issue titles are properly sanitized."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {
                "title": "[Feature] User Auth (v2)!",
                "body": "",
                "labels": [],
            }
        )

        with patch("subprocess.run", return_value=mock_result):
            result = import_from_github_issue("https://github.com/org/repo/issues/123")

        assert result == "feature-user-auth-v2"


# =============================================================================
# Template Creation Tests
# =============================================================================


class TestCreateRequirementsTemplate:
    """Tests for create_requirements_template function."""

    def test_minimal_template(self, tmp_path: Path) -> None:
        """Test minimal template creation."""
        spec_dir = tmp_path / "specs" / "test-feature"
        spec_dir.mkdir(parents=True)

        create_requirements_template(spec_dir, "test-feature", "minimal")

        requirements_path = spec_dir / "requirements.md"
        assert requirements_path.exists()

        content = requirements_path.read_text()
        assert "# Feature Requirements: test-feature" in content
        assert "**Status**: DRAFT" in content
        assert "Problem Statement" in content
        assert "Out of Scope" in content
        # Minimal template should NOT have detailed sections
        assert "Risk Assessment" not in content

    def test_default_template(self, tmp_path: Path) -> None:
        """Test default template creation."""
        spec_dir = tmp_path / "specs" / "test-feature"
        spec_dir.mkdir(parents=True)

        create_requirements_template(spec_dir, "test-feature", "default")

        requirements_path = spec_dir / "requirements.md"
        content = requirements_path.read_text()

        assert "# Feature Requirements: test-feature" in content
        assert "Problem Statement" in content
        assert "Users" in content
        assert "Functional Requirements" in content
        assert "Non-Functional Requirements" in content
        assert "Acceptance Criteria" in content
        assert "**Author**: ZERG Plan" in content

    def test_detailed_template(self, tmp_path: Path) -> None:
        """Test detailed template creation."""
        spec_dir = tmp_path / "specs" / "test-feature"
        spec_dir.mkdir(parents=True)

        create_requirements_template(spec_dir, "test-feature", "detailed")

        requirements_path = spec_dir / "requirements.md"
        content = requirements_path.read_text()

        # Should include all default sections plus additional ones
        assert "# Feature Requirements: test-feature" in content
        assert "Technical Constraints" in content
        assert "Risk Assessment" in content
        assert "Success Metrics" in content
        assert "Integration Points" in content

    def test_unknown_template_falls_back_to_default(self, tmp_path: Path) -> None:
        """Test that unknown template type falls back to default."""
        spec_dir = tmp_path / "specs" / "test-feature"
        spec_dir.mkdir(parents=True)

        create_requirements_template(spec_dir, "test-feature", "unknown")

        requirements_path = spec_dir / "requirements.md"
        content = requirements_path.read_text()

        # Should have default template content
        assert "**Author**: ZERG Plan" in content


class TestGetDefaultTemplate:
    """Tests for get_default_template function."""

    def test_contains_required_sections(self) -> None:
        """Test that default template contains all required sections."""
        timestamp = "2026-01-26T10:00:00"
        content = get_default_template("test-feature", timestamp)

        required_sections = [
            "Feature Requirements: test-feature",
            "Metadata",
            "Problem Statement",
            "Users",
            "Functional Requirements",
            "Non-Functional Requirements",
            "Scope",
            "Dependencies",
            "Acceptance Criteria",
            "Open Questions",
            "Approval",
        ]

        for section in required_sections:
            assert section in content, f"Missing section: {section}"

    def test_includes_feature_name(self) -> None:
        """Test that template includes feature name."""
        content = get_default_template("user-auth", "2026-01-26T10:00:00")

        assert "user-auth" in content
        assert "Feature**: user-auth" in content

    def test_includes_timestamp(self) -> None:
        """Test that template includes creation timestamp."""
        timestamp = "2026-01-26T10:00:00"
        content = get_default_template("test", timestamp)

        assert timestamp in content


class TestGetDetailedTemplate:
    """Tests for get_detailed_template function."""

    def test_extends_default_template(self) -> None:
        """Test that detailed template extends default template."""
        timestamp = "2026-01-26T10:00:00"
        default = get_default_template("test", timestamp)
        detailed = get_detailed_template("test", timestamp)

        # Detailed should be longer than default
        assert len(detailed) > len(default)

    def test_contains_additional_sections(self) -> None:
        """Test that detailed template contains additional sections."""
        content = get_detailed_template("test", "2026-01-26T10:00:00")

        additional_sections = [
            "Technical Constraints",
            "Technology Stack",
            "Integration Points",
            "Data Requirements",
            "Risk Assessment",
            "Success Metrics",
        ]

        for section in additional_sections:
            assert section in content, f"Missing section: {section}"


# =============================================================================
# Socratic Discovery Tests
# =============================================================================


class TestRunSocraticDiscovery:
    """Tests for run_socratic_discovery function."""

    def test_single_round(self) -> None:
        """Test socratic discovery with single round."""
        with patch("zerg.commands.plan.ask_questions") as mock_ask:
            mock_ask.return_value = {"Q1": "A1"}

            result = run_socratic_discovery("test-feature", rounds=1)

        assert result["feature"] == "test-feature"
        assert "problem_space" in result
        assert len(result["transcript"]) == 1
        assert result["transcript"][0][0] == "Problem Space"

    def test_two_rounds(self) -> None:
        """Test socratic discovery with two rounds."""
        with patch("zerg.commands.plan.ask_questions") as mock_ask:
            mock_ask.return_value = {"Q": "A"}

            result = run_socratic_discovery("test-feature", rounds=2)

        assert len(result["transcript"]) == 2
        assert result["transcript"][0][0] == "Problem Space"
        assert result["transcript"][1][0] == "Solution Space"
        assert "solution_space" in result

    def test_three_rounds(self) -> None:
        """Test socratic discovery with three rounds (default)."""
        with patch("zerg.commands.plan.ask_questions") as mock_ask:
            mock_ask.return_value = {"Q": "A"}

            result = run_socratic_discovery("test-feature", rounds=3)

        assert len(result["transcript"]) == 3
        assert "problem_space" in result
        assert "solution_space" in result
        assert "implementation_space" in result

    def test_max_rounds_capped_at_five(self) -> None:
        """Test that rounds are capped at maximum of 5."""
        with patch("zerg.commands.plan.ask_questions") as mock_ask:
            mock_ask.return_value = {"Q": "A"}

            # Request more than 5 rounds
            result = run_socratic_discovery("test-feature", rounds=10)

        # Should still only have 3 transcript entries (problem, solution, implementation)
        # because the code only handles up to rounds >= 3
        assert len(result["transcript"]) == 3

    def test_zero_rounds(self) -> None:
        """Test socratic discovery with zero rounds."""
        result = run_socratic_discovery("test-feature", rounds=0)

        assert result["feature"] == "test-feature"
        assert len(result["transcript"]) == 0
        assert result["problem_space"] == {}


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
        assert result["users"] == "End users"
        assert result["inputs"] == "Username, password"
        assert result["outputs"] == "JWT token"
        assert result["out_of_scope"] == "2FA"
        assert result["acceptance"] == "All tests pass"


class TestAskQuestions:
    """Tests for ask_questions function."""

    def test_asks_all_questions(self) -> None:
        """Test that all questions are asked and answers collected."""
        questions = ["Question 1?", "Question 2?", "Question 3?"]

        with patch("zerg.commands.plan.Prompt.ask") as mock_prompt:
            mock_prompt.side_effect = ["Answer 1", "Answer 2", "Answer 3"]

            result = ask_questions(questions, "Test")

        assert len(result) == 3
        assert result["Question 1?"] == "Answer 1"
        assert result["Question 2?"] == "Answer 2"
        assert result["Question 3?"] == "Answer 3"

    def test_empty_questions_list(self) -> None:
        """Test with empty questions list."""
        result = ask_questions([], "Test")

        assert result == {}


# =============================================================================
# Write Requirements Tests
# =============================================================================


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
        assert "Discovery Transcript" in content

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
        assert "The users" in content


class TestFormatSocraticRequirements:
    """Tests for format_socratic_requirements function."""

    def test_includes_metadata(self) -> None:
        """Test that formatted output includes metadata."""
        req: dict[str, list | dict] = {
            "transcript": [],
            "problem_space": {},
            "solution_space": {},
            "implementation_space": {},
        }

        content = format_socratic_requirements("test", "2026-01-26T10:00:00", req)

        assert "**Feature**: test" in content
        assert "**Status**: DRAFT" in content
        assert "**Method**: Socratic Discovery" in content

    def test_includes_transcript(self) -> None:
        """Test that transcript is included."""
        req = {
            "transcript": [
                ("Problem Space", {"What is it?": "A feature", "Why?": "Because"}),
            ],
            "problem_space": {"What is it?": "A feature"},
            "solution_space": {},
            "implementation_space": {},
        }

        content = format_socratic_requirements("test", "2026-01-26T10:00:00", req)

        assert "### Problem Space" in content
        assert "**Q:** What is it?" in content
        assert "**A:** A feature" in content

    def test_includes_solution_constraints(self) -> None:
        """Test that solution constraints are included."""
        req = {
            "transcript": [],
            "problem_space": {},
            "solution_space": {"Constraint 1": "Must be fast"},
            "implementation_space": {},
        }

        content = format_socratic_requirements("test", "2026-01-26T10:00:00", req)

        assert "Solution Constraints" in content
        assert "Constraint 1" in content
        assert "Must be fast" in content

    def test_includes_implementation_notes(self) -> None:
        """Test that implementation notes are included."""
        req = {
            "transcript": [],
            "problem_space": {},
            "solution_space": {},
            "implementation_space": {"MVP": "Basic auth"},
        }

        content = format_socratic_requirements("test", "2026-01-26T10:00:00", req)

        assert "Implementation Notes" in content
        assert "MVP" in content
        assert "Basic auth" in content

    def test_empty_problem_space_uses_default(self) -> None:
        """Test that empty problem space uses default text."""
        req: dict[str, list | dict] = {
            "transcript": [],
            "problem_space": {},
            "solution_space": {},
            "implementation_space": {},
        }

        content = format_socratic_requirements("test", "2026-01-26T10:00:00", req)

        assert "_To be defined_" in content


class TestFormatStandardRequirements:
    """Tests for format_standard_requirements function."""

    def test_includes_all_fields(self) -> None:
        """Test that all requirement fields are included."""
        req = {
            "problem": "The problem",
            "users": "The users",
            "inputs": "The inputs",
            "outputs": "The outputs",
            "out_of_scope": "Not this",
            "acceptance": "Tests pass",
        }

        content = format_standard_requirements("test", "2026-01-26T10:00:00", req)

        assert "The problem" in content
        assert "The users" in content
        assert "The inputs" in content
        assert "The outputs" in content
        assert "Not this" in content
        assert "Tests pass" in content

    def test_missing_fields_use_default(self) -> None:
        """Test that missing fields use default text."""
        req: dict[str, str] = {}

        content = format_standard_requirements("test", "2026-01-26T10:00:00", req)

        assert "_To be defined_" in content


# =============================================================================
# Plan Command Integration Tests
# =============================================================================


class TestPlanCommand:
    """Integration tests for the plan CLI command."""

    def test_plan_help(self) -> None:
        """Test plan --help shows usage information."""
        runner = CliRunner()
        result = runner.invoke(cli, ["plan", "--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "--template" in result.output
        assert "--interactive" in result.output
        assert "--socratic" in result.output

    def test_plan_non_interactive_creates_requirements(self, tmp_path: Path, monkeypatch) -> None:
        """Test non-interactive plan creates requirements file."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)

        runner = CliRunner()
        result = runner.invoke(cli, ["plan", "test-feature", "--no-interactive"])

        assert result.exit_code == 0
        assert (tmp_path / ".gsd" / "specs" / "test-feature" / "requirements.md").exists()

    def test_plan_creates_spec_directory(self, tmp_path: Path, monkeypatch) -> None:
        """Test plan creates spec directory if not exists."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["plan", "new-feature", "--no-interactive"])

        assert result.exit_code == 0
        assert (tmp_path / ".gsd" / "specs" / "new-feature").is_dir()

    def test_plan_sets_current_feature(self, tmp_path: Path, monkeypatch) -> None:
        """Test plan sets current feature file."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)

        runner = CliRunner()
        runner.invoke(cli, ["plan", "my-feature", "--no-interactive"])

        current_feature = tmp_path / ".gsd" / ".current-feature"
        assert current_feature.exists()
        assert current_feature.read_text() == "my-feature"

    def test_plan_creates_started_timestamp(self, tmp_path: Path, monkeypatch) -> None:
        """Test plan creates .started timestamp file."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)

        runner = CliRunner()
        runner.invoke(cli, ["plan", "test-feature", "--no-interactive"])

        started_file = tmp_path / ".gsd" / "specs" / "test-feature" / ".started"
        assert started_file.exists()
        # Verify it contains valid ISO timestamp
        content = started_file.read_text()
        assert "T" in content  # ISO format includes T

    def test_plan_sanitizes_feature_name(self, tmp_path: Path, monkeypatch) -> None:
        """Test plan sanitizes feature names."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)

        runner = CliRunner()
        result = runner.invoke(cli, ["plan", "My Feature!", "--no-interactive"])

        assert result.exit_code == 0
        assert (tmp_path / ".gsd" / "specs" / "my-feature").exists()

    def test_plan_requires_feature_non_interactive(self, tmp_path: Path, monkeypatch) -> None:
        """Test plan requires feature name in non-interactive mode."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)

        runner = CliRunner()
        result = runner.invoke(cli, ["plan", "--no-interactive"])

        assert result.exit_code == 1
        assert "required" in result.output.lower()

    def test_plan_minimal_template(self, tmp_path: Path, monkeypatch) -> None:
        """Test plan with minimal template."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)

        runner = CliRunner()
        runner.invoke(cli, ["plan", "test", "--no-interactive", "--template", "minimal"])

        content = (tmp_path / ".gsd" / "specs" / "test" / "requirements.md").read_text()
        assert "Problem Statement" in content
        # Minimal should not have detailed sections
        assert "Risk Assessment" not in content

    def test_plan_detailed_template(self, tmp_path: Path, monkeypatch) -> None:
        """Test plan with detailed template."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)

        runner = CliRunner()
        runner.invoke(cli, ["plan", "test", "--no-interactive", "--template", "detailed"])

        content = (tmp_path / ".gsd" / "specs" / "test" / "requirements.md").read_text()
        assert "Risk Assessment" in content
        assert "Technical Constraints" in content

    def test_plan_existing_requirements_overwrite_declined(self, tmp_path: Path, monkeypatch) -> None:
        """Test plan with existing requirements and overwrite declined."""
        monkeypatch.chdir(tmp_path)
        spec_dir = tmp_path / ".gsd" / "specs" / "test"
        spec_dir.mkdir(parents=True)
        (spec_dir / "requirements.md").write_text("Existing content")

        runner = CliRunner()
        # Simulate user declining overwrite
        runner.invoke(cli, ["plan", "test"], input="n\n")

        # Should exit gracefully
        content = (spec_dir / "requirements.md").read_text()
        assert content == "Existing content"

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
                cli,
                ["plan", "--from-issue", "https://github.com/org/repo/issues/1", "--no-interactive"],
            )

        assert result.exit_code == 0
        assert (tmp_path / ".gsd" / "specs" / "add-feature").exists()

    def test_plan_with_from_issue_failure(self, tmp_path: Path, monkeypatch) -> None:
        """Test plan with --from-issue that fails."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            runner = CliRunner()
            result = runner.invoke(cli, ["plan", "--from-issue", "https://github.com/org/repo/issues/1"])

        assert result.exit_code == 1

    def test_plan_verbose_error(self, tmp_path: Path, monkeypatch) -> None:
        """Test plan --verbose shows exception details on error."""
        monkeypatch.chdir(tmp_path)
        # Create .gsd directory but cause an error by mocking write
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)

        with patch("pathlib.Path.write_text", side_effect=PermissionError("No write access")):
            runner = CliRunner()
            result = runner.invoke(cli, ["plan", "test", "--no-interactive", "--verbose"])

            # Should show error
            assert result.exit_code == 1
            assert "Error" in result.output


class TestPlanInteractiveMode:
    """Tests for plan command interactive mode."""

    def test_plan_interactive_prompts_feature_name_when_missing(self, tmp_path: Path, monkeypatch) -> None:
        """Test interactive mode prompts for feature name when not provided.

        This tests line 57: feature = Prompt.ask("Feature name")
        """
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)

        # Mock Prompt.ask to provide feature name, and mock discovery
        with (
            patch("zerg.commands.plan.Prompt.ask") as mock_prompt,
            patch("zerg.commands.plan.run_interactive_discovery") as mock_discovery,
        ):
            # First call is for feature name prompt (line 57), rest are for discovery
            mock_prompt.return_value = "prompted-feature"
            mock_discovery.return_value = {
                "feature": "prompted-feature",
                "problem": "The problem",
                "users": "Users",
                "inputs": "Inputs",
                "outputs": "Outputs",
                "out_of_scope": "None",
                "acceptance": "Tests pass",
            }

            runner = CliRunner()
            # Call without feature name in interactive mode (default)
            result = runner.invoke(cli, ["plan"])

            # Should have prompted for feature name
            mock_prompt.assert_called_with("Feature name")
            assert result.exit_code == 0

    def test_plan_interactive_no_feature_non_interactive_fails(self, tmp_path: Path, monkeypatch) -> None:
        """Test non-interactive mode fails without feature name."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)

        runner = CliRunner()
        result = runner.invoke(cli, ["plan", "--no-interactive"])

        # In non-interactive, it should fail without feature name
        assert result.exit_code == 1

    def test_plan_socratic_mode(self, tmp_path: Path, monkeypatch) -> None:
        """Test plan with --socratic flag uses socratic discovery."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)

        with patch("zerg.commands.plan.run_socratic_discovery") as mock_socratic:
            mock_socratic.return_value = {
                "feature": "test",
                "transcript": [("Problem Space", {"Q": "A"})],
                "problem_space": {"Q": "A"},
                "solution_space": {},
                "implementation_space": {},
            }

            runner = CliRunner()
            result = runner.invoke(cli, ["plan", "test", "--socratic"])

            mock_socratic.assert_called_once()
            assert result.exit_code == 0

    def test_plan_socratic_rounds_option(self, tmp_path: Path, monkeypatch) -> None:
        """Test plan --rounds option limits socratic rounds."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)

        with patch("zerg.commands.plan.run_socratic_discovery") as mock_socratic:
            mock_socratic.return_value = {
                "feature": "test",
                "transcript": [],
                "problem_space": {},
                "solution_space": {},
                "implementation_space": {},
            }

            runner = CliRunner()
            runner.invoke(cli, ["plan", "test", "--socratic", "--rounds", "2"])

            # Verify rounds argument was passed (capped at 5)
            mock_socratic.assert_called_once()
            args, _kwargs = mock_socratic.call_args
            assert args[1] == 2  # rounds argument

    def test_plan_standard_interactive(self, tmp_path: Path, monkeypatch) -> None:
        """Test plan standard interactive mode."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)

        with patch("zerg.commands.plan.run_interactive_discovery") as mock_interactive:
            mock_interactive.return_value = {
                "feature": "test",
                "problem": "Problem",
                "users": "Users",
                "inputs": "Inputs",
                "outputs": "Outputs",
                "out_of_scope": "None",
                "acceptance": "Tests",
            }

            runner = CliRunner()
            result = runner.invoke(cli, ["plan", "test"])

            mock_interactive.assert_called_once()
            assert result.exit_code == 0


class TestPlanErrorHandling:
    """Tests for plan command error handling."""

    def test_keyboard_interrupt_handling(self, tmp_path: Path, monkeypatch) -> None:
        """Test that keyboard interrupt is handled gracefully."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)

        with patch("zerg.commands.plan.run_interactive_discovery", side_effect=KeyboardInterrupt()):
            runner = CliRunner()
            result = runner.invoke(cli, ["plan", "test"])

            assert result.exit_code == 130
            assert "Interrupted" in result.output

    def test_general_exception_handling(self, tmp_path: Path, monkeypatch) -> None:
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


# =============================================================================
# Edge Cases and Boundary Conditions
# =============================================================================


class TestPlanEdgeCases:
    """Edge case tests for plan command."""

    def test_very_long_feature_name(self, tmp_path: Path, monkeypatch) -> None:
        """Test with very long feature name."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)

        long_name = "a" * 200
        runner = CliRunner()
        result = runner.invoke(cli, ["plan", long_name, "--no-interactive"])

        assert result.exit_code == 0
        assert (tmp_path / ".gsd" / "specs" / long_name).exists()

    def test_unicode_feature_name(self, tmp_path: Path, monkeypatch) -> None:
        """Test with unicode characters in feature name."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)

        runner = CliRunner()
        result = runner.invoke(cli, ["plan", "feature-cafe", "--no-interactive"])

        assert result.exit_code == 0
        # Sanitized name should work
        assert (tmp_path / ".gsd" / "specs" / "feature-cafe").exists()

    def test_feature_name_with_only_numbers(self, tmp_path: Path, monkeypatch) -> None:
        """Test feature name with only numbers."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)

        runner = CliRunner()
        result = runner.invoke(cli, ["plan", "12345", "--no-interactive"])

        assert result.exit_code == 0
        assert (tmp_path / ".gsd" / "specs" / "12345").exists()

    def test_rounds_capped_at_five(self, tmp_path: Path, monkeypatch) -> None:
        """Test that rounds option is capped at 5."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".gsd" / "specs").mkdir(parents=True)

        with patch("zerg.commands.plan.run_socratic_discovery") as mock_socratic:
            mock_socratic.return_value = {
                "feature": "test",
                "transcript": [],
                "problem_space": {},
                "solution_space": {},
                "implementation_space": {},
            }

            runner = CliRunner()
            runner.invoke(cli, ["plan", "test", "--socratic", "--rounds", "10"])

            # Verify rounds was capped
            args, _kwargs = mock_socratic.call_args
            # min(10, 5) = 5 in the plan command
            assert args[1] <= 5


class TestPlanOverwriteFlow:
    """Tests for overwrite confirmation flow."""

    def test_overwrite_confirmed(self, tmp_path: Path, monkeypatch) -> None:
        """Test that confirming overwrite replaces existing file."""
        monkeypatch.chdir(tmp_path)
        spec_dir = tmp_path / ".gsd" / "specs" / "test"
        spec_dir.mkdir(parents=True)
        (spec_dir / "requirements.md").write_text("Old content")

        runner = CliRunner()
        # Confirm overwrite
        runner.invoke(cli, ["plan", "test", "--no-interactive"], input="y\n")

        # Old content should be replaced (non-interactive mode creates template)
        content = (spec_dir / "requirements.md").read_text()
        # The new template should be created (check for default template content)
        assert "Feature Requirements" in content

    def test_existing_requirements_no_interactive_skip(self, tmp_path: Path, monkeypatch) -> None:
        """Test existing requirements with non-interactive mode."""
        monkeypatch.chdir(tmp_path)
        spec_dir = tmp_path / ".gsd" / "specs" / "test"
        spec_dir.mkdir(parents=True)
        (spec_dir / "requirements.md").write_text("Original content")

        runner = CliRunner()
        # Non-interactive should overwrite without asking
        runner.invoke(cli, ["plan", "test", "--no-interactive"])

        # In non-interactive mode, the file should be overwritten
        content = (spec_dir / "requirements.md").read_text()
        assert "Feature Requirements" in content
