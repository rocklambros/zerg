"""Tests for ZERG command executor module."""

from pathlib import Path

import pytest

from zerg.command_executor import (
    ALLOWED_COMMAND_PREFIXES,
    CommandCategory,
    CommandExecutor,
    CommandResult,
    CommandValidationError,
    execute_safe,
    get_executor,
)


class TestCommandResult:
    """Tests for CommandResult dataclass."""

    def test_creation_and_to_dict(self) -> None:
        """Test result creation and dictionary serialization."""
        result = CommandResult(
            command=["pytest"],
            exit_code=0,
            stdout="passed",
            stderr="",
            duration_ms=100,
            success=True,
            category=CommandCategory.TESTING,
        )

        assert result.success is True
        assert result.category == CommandCategory.TESTING

        data = result.to_dict()
        assert data["command"] == ["pytest"]
        assert data["exit_code"] == 0
        assert data["category"] == "testing"
        assert "timestamp" in data

    def test_to_dict_truncates_long_output(self) -> None:
        """Test that long output is truncated."""
        long_output = "x" * 3000
        result = CommandResult(
            command=["cmd"],
            exit_code=0,
            stdout=long_output,
            stderr=long_output,
            duration_ms=100,
            success=True,
        )
        data = result.to_dict()
        assert len(data["stdout"]) == 2000
        assert len(data["stderr"]) == 2000


class TestCommandExecutor:
    """Tests for CommandExecutor class."""

    def test_init_default(self) -> None:
        """Test default initialization."""
        executor = CommandExecutor()
        assert executor.working_dir == Path.cwd()
        assert executor.allow_unlisted is False
        assert executor.timeout == 300
        assert executor.audit_log is True

    def test_init_custom(self, tmp_path: Path) -> None:
        """Test custom initialization with all params."""
        custom = {"my-tool": CommandCategory.CUSTOM}
        executor = CommandExecutor(
            working_dir=tmp_path,
            allow_unlisted=True,
            timeout=60,
            audit_log=False,
            custom_allowlist=custom,
        )
        assert executor.working_dir == tmp_path
        assert executor.allow_unlisted is True
        assert "my-tool" in executor.allowlist


class TestValidateCommand:
    """Tests for command validation."""

    def test_validate_allowed_command(self) -> None:
        """Test validating allowed command."""
        executor = CommandExecutor()
        is_valid, _reason, category = executor.validate_command("pytest tests/")
        assert is_valid is True
        assert category == CommandCategory.TESTING

    def test_validate_empty_command(self) -> None:
        """Test validating empty command."""
        executor = CommandExecutor()
        is_valid, reason, _category = executor.validate_command("")
        assert is_valid is False
        assert "empty" in reason.lower()

    @pytest.mark.parametrize(
        "cmd",
        [
            "echo test; rm -rf /",
            "cat file | bash",
            "echo test && rm -rf /",
            "echo `whoami`",
            "echo $(id)",
            "echo test > file",
        ],
        ids=["semicolon", "pipe", "and-chain", "backtick", "dollar-paren", "redirect"],
    )
    def test_validate_dangerous_patterns(self, cmd: str) -> None:
        """Test blocking dangerous command patterns."""
        executor = CommandExecutor()
        is_valid, _reason, _ = executor.validate_command(cmd)
        assert is_valid is False

    def test_validate_unlisted_blocked_and_allowed(self) -> None:
        """Test unlisted commands blocked by default, allowed when enabled."""
        blocked = CommandExecutor()
        is_valid, reason, _ = blocked.validate_command("custom-tool arg")
        assert is_valid is False
        assert "not in allowlist" in reason.lower()

        allowed = CommandExecutor(allow_unlisted=True)
        is_valid, _reason, category = allowed.validate_command("custom-tool arg")
        assert is_valid is True
        assert category == CommandCategory.CUSTOM


class TestParseCommand:
    """Tests for command parsing."""

    def test_parse_simple_command(self) -> None:
        """Test parsing simple command."""
        executor = CommandExecutor()
        args = executor.parse_command("echo hello world")
        assert args == ["echo", "hello", "world"]

    def test_parse_invalid_quotes(self) -> None:
        """Test parsing with invalid quotes raises."""
        executor = CommandExecutor()
        with pytest.raises(CommandValidationError):
            executor.parse_command('echo "unclosed')


class TestExecute:
    """Tests for command execution."""

    def test_execute_success(self, tmp_path: Path) -> None:
        """Test successful command execution."""
        executor = CommandExecutor(working_dir=tmp_path)
        result = executor.execute("echo hello")
        assert result.success is True
        assert result.exit_code == 0
        assert "hello" in result.stdout

    def test_execute_failure(self, tmp_path: Path) -> None:
        """Test failed command execution."""
        executor = CommandExecutor(working_dir=tmp_path)
        result = executor.execute("false")
        assert result.success is False
        assert result.exit_code == 1

    def test_execute_invalid_command_raises(self) -> None:
        """Test invalid command raises exception."""
        executor = CommandExecutor()
        with pytest.raises(CommandValidationError):
            executor.execute("dangerous; command")

    def test_execute_with_cwd(self, tmp_path: Path) -> None:
        """Test execution with custom working directory."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        executor = CommandExecutor()
        result = executor.execute("pwd", cwd=subdir)
        assert result.success is True
        assert str(subdir) in result.stdout

    def test_execute_records_history(self, tmp_path: Path) -> None:
        """Test execution records to history."""
        executor = CommandExecutor(working_dir=tmp_path)
        executor.execute("echo one")
        executor.execute("echo two")
        assert len(executor.get_history()) == 2


class TestExecuteGit:
    """Tests for git command execution."""

    def test_execute_git(self, tmp_repo: Path) -> None:
        """Test git command execution."""
        executor = CommandExecutor(working_dir=tmp_repo)
        result = executor.execute_git("status")
        assert result.success is True


class TestExecutePython:
    """Tests for Python command execution."""

    def test_execute_python(self, tmp_path: Path) -> None:
        """Test Python -m command execution."""
        executor = CommandExecutor(working_dir=tmp_path)
        result = executor.execute_python("-m", "platform")
        assert result.success is True
        assert len(result.stdout) > 0


class TestModuleFunctions:
    """Tests for module-level functions."""

    def test_get_executor_default(self) -> None:
        """Test getting default executor."""
        executor = get_executor()
        assert isinstance(executor, CommandExecutor)

    def test_execute_safe(self, tmp_path: Path, monkeypatch) -> None:
        """Test safe execution function."""
        monkeypatch.chdir(tmp_path)
        result = execute_safe("echo test")
        assert result.success is True


class TestAllowedCommands:
    """Tests for the command allowlist."""

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            ("pytest", True),
            ("git status", True),
            ("ruff", True),
            ("mypy", True),
        ],
        ids=["pytest", "git-status", "ruff", "mypy"],
    )
    def test_commands_in_allowlist(self, cmd: str, expected: bool) -> None:
        """Test expected commands are in allowlist."""
        assert (cmd in ALLOWED_COMMAND_PREFIXES) is expected

    def test_categories_assigned(self) -> None:
        """Test categories are properly assigned."""
        assert ALLOWED_COMMAND_PREFIXES["pytest"] == CommandCategory.TESTING
        assert ALLOWED_COMMAND_PREFIXES["ruff"] == CommandCategory.LINTING
        assert ALLOWED_COMMAND_PREFIXES["git status"] == CommandCategory.GIT
