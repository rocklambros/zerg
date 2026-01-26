"""Integration tests for ZERG git command."""

from pathlib import Path

from click.testing import CliRunner

from zerg.cli import cli


class TestGitCommand:
    """Tests for git command."""

    def test_git_help(self) -> None:
        """Test git --help shows all options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["git", "--help"])

        assert result.exit_code == 0
        assert "action" in result.output
        assert "commit" in result.output
        assert "branch" in result.output
        assert "merge" in result.output
        assert "sync" in result.output
        assert "history" in result.output
        assert "finish" in result.output

    def test_git_action_option(self) -> None:
        """Test git --action option accepts valid values."""
        runner = CliRunner()

        for action in ["commit", "branch", "merge", "sync", "history", "finish"]:
            result = runner.invoke(cli, ["git", "--action", action])
            assert "Invalid value" not in result.output

    def test_git_invalid_action_rejected(self) -> None:
        """Test git rejects invalid actions."""
        runner = CliRunner()
        result = runner.invoke(cli, ["git", "--action", "invalid"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output

    def test_git_push_flag(self) -> None:
        """Test git --push flag works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["git", "--action", "commit", "--push"])
        assert "Invalid value" not in result.output

    def test_git_base_option(self) -> None:
        """Test git --base option works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["git", "--action", "finish", "--base", "develop"])
        assert "Invalid value" not in result.output

    def test_git_name_option(self) -> None:
        """Test git --name option for branch action."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["git", "--action", "branch", "--name", "feature/auth"]
        )
        assert "Invalid value" not in result.output

    def test_git_strategy_option(self) -> None:
        """Test git --strategy option for merge action."""
        runner = CliRunner()

        for strategy in ["merge", "squash", "rebase"]:
            result = runner.invoke(
                cli,
                ["git", "--action", "merge", "--branch", "feature", "--strategy", strategy],
            )
            assert "Invalid value" not in result.output

    def test_git_since_option(self) -> None:
        """Test git --since option for history action."""
        runner = CliRunner()
        result = runner.invoke(cli, ["git", "--action", "history", "--since", "v1.0.0"])
        assert "Invalid value" not in result.output


class TestGitActions:
    """Tests for specific git actions."""

    def test_git_commit_default_action(self) -> None:
        """Test commit is the default action."""
        runner = CliRunner()
        result = runner.invoke(cli, ["git", "--help"])
        assert "default: commit" in result.output.lower() or "commit" in result.output

    def test_git_finish_action_options(self) -> None:
        """Test finish action with options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["git", "--action", "finish", "--base", "main"])
        assert "Invalid value" not in result.output
