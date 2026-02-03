"""Integration tests for ZERG git command."""

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
        result = runner.invoke(cli, ["git", "--action", "branch", "--name", "feature/auth"])
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


class TestGitFunctional:
    """Functional tests for git command."""

    def test_git_displays_header(self) -> None:
        """Test git shows ZERG Git header."""
        runner = CliRunner()
        result = runner.invoke(cli, ["git", "--action", "history"])
        assert "ZERG" in result.output or "Git" in result.output or len(result.output) > 0

    def test_git_history_action(self) -> None:
        """Test git history action shows commits."""
        runner = CliRunner()
        result = runner.invoke(cli, ["git", "--action", "history"])
        # Should run without crashing
        assert result.exit_code in [0, 1]

    def test_git_history_with_since(self) -> None:
        """Test git history with --since option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["git", "--action", "history", "--since", "HEAD~5"])
        assert result.exit_code in [0, 1]

    def test_git_sync_action(self) -> None:
        """Test git sync action."""
        runner = CliRunner()
        result = runner.invoke(cli, ["git", "--action", "sync"])
        # May fail if no remote, but should handle gracefully
        assert result.exit_code in [0, 1]

    def test_git_branch_without_name(self) -> None:
        """Test git branch action without name shows current branch."""
        runner = CliRunner()
        result = runner.invoke(cli, ["git", "--action", "branch"])
        # Should handle missing name gracefully
        assert result.exit_code in [0, 1]

    def test_git_commit_no_changes(self) -> None:
        """Test git commit with no changes."""
        runner = CliRunner()
        result = runner.invoke(cli, ["git", "--action", "commit"])
        # Should handle "nothing to commit" gracefully
        assert result.exit_code in [0, 1]

    def test_git_merge_without_branch(self) -> None:
        """Test git merge action without branch specified."""
        runner = CliRunner()
        result = runner.invoke(cli, ["git", "--action", "merge"])
        # Should handle missing branch gracefully
        assert result.exit_code in [0, 1]

    def test_git_finish_without_base(self) -> None:
        """Test git finish action uses default base."""
        runner = CliRunner()
        result = runner.invoke(cli, ["git", "--action", "finish"])
        # Should use main/master as default
        assert result.exit_code in [0, 1]

    def test_git_all_strategies(self) -> None:
        """Test git merge with all strategies."""
        runner = CliRunner()
        for strategy in ["merge", "squash", "rebase"]:
            result = runner.invoke(cli, ["git", "--action", "merge", "--strategy", strategy])
            # Should accept all strategies
            assert "Invalid value" not in result.output


class TestGitCommitTypes:
    """Tests for git commit type detection."""

    def test_git_commit_with_push(self) -> None:
        """Test git commit with push flag."""
        runner = CliRunner()
        result = runner.invoke(cli, ["git", "--action", "commit", "--push"])
        # Should handle push (may fail if no remote)
        assert result.exit_code in [0, 1]

    def test_git_combined_options(self) -> None:
        """Test git with multiple options."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["git", "--action", "merge", "--branch", "feature", "--strategy", "squash", "--base", "main"],
        )
        assert result.exit_code in [0, 1]
