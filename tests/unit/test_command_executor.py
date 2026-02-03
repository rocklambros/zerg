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

    def test_creation(self) -> None:
        """Test result creation."""
        result = CommandResult(
            command=["echo", "test"],
            exit_code=0,
            stdout="test\n",
            stderr="",
            duration_ms=10,
            success=True,
            category=CommandCategory.SYSTEM,
        )

        assert result.command == ["echo", "test"]
        assert result.success is True
        assert result.category == CommandCategory.SYSTEM

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        result = CommandResult(
            command=["pytest"],
            exit_code=0,
            stdout="passed",
            stderr="",
            duration_ms=100,
            success=True,
            category=CommandCategory.TESTING,
        )

        data = result.to_dict()

        assert data["command"] == ["pytest"]
        assert data["exit_code"] == 0
        assert data["success"] is True
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
        """Test custom initialization."""
        executor = CommandExecutor(
            working_dir=tmp_path,
            allow_unlisted=True,
            timeout=60,
            audit_log=False,
        )

        assert executor.working_dir == tmp_path
        assert executor.allow_unlisted is True
        assert executor.timeout == 60
        assert executor.audit_log is False

    def test_init_with_custom_allowlist(self) -> None:
        """Test initialization with custom allowlist."""
        custom = {"my-tool": CommandCategory.CUSTOM}
        executor = CommandExecutor(custom_allowlist=custom)

        assert "my-tool" in executor.allowlist


class TestValidateCommand:
    """Tests for command validation."""

    def test_validate_allowed_command(self) -> None:
        """Test validating allowed command."""
        executor = CommandExecutor()

        is_valid, reason, category = executor.validate_command("pytest tests/")

        assert is_valid is True
        assert category == CommandCategory.TESTING

    def test_validate_empty_command(self) -> None:
        """Test validating empty command."""
        executor = CommandExecutor()

        is_valid, reason, category = executor.validate_command("")

        assert is_valid is False
        assert "empty" in reason.lower()

    def test_validate_dangerous_semicolon(self) -> None:
        """Test blocking command chaining with semicolon."""
        executor = CommandExecutor()

        is_valid, reason, _ = executor.validate_command("echo test; rm -rf /")

        assert is_valid is False
        assert "dangerous" in reason.lower()

    def test_validate_dangerous_pipe(self) -> None:
        """Test blocking piped commands."""
        executor = CommandExecutor()

        is_valid, reason, _ = executor.validate_command("cat file | bash")

        assert is_valid is False

    def test_validate_dangerous_and(self) -> None:
        """Test blocking && chaining."""
        executor = CommandExecutor()

        is_valid, reason, _ = executor.validate_command("echo test && rm -rf /")

        assert is_valid is False

    def test_validate_dangerous_backtick(self) -> None:
        """Test blocking command substitution."""
        executor = CommandExecutor()

        is_valid, reason, _ = executor.validate_command("echo `whoami`")

        assert is_valid is False

    def test_validate_dangerous_dollar_paren(self) -> None:
        """Test blocking $() substitution."""
        executor = CommandExecutor()

        is_valid, reason, _ = executor.validate_command("echo $(id)")

        assert is_valid is False

    def test_validate_dangerous_redirect(self) -> None:
        """Test blocking output redirection."""
        executor = CommandExecutor()

        is_valid, reason, _ = executor.validate_command("echo test > file")

        assert is_valid is False

    def test_validate_unlisted_blocked(self) -> None:
        """Test unlisted commands are blocked by default."""
        executor = CommandExecutor()

        is_valid, reason, _ = executor.validate_command("custom-tool arg")

        assert is_valid is False
        assert "not in allowlist" in reason.lower()

    def test_validate_unlisted_allowed(self) -> None:
        """Test unlisted commands allowed when enabled."""
        executor = CommandExecutor(allow_unlisted=True)

        is_valid, reason, category = executor.validate_command("custom-tool arg")

        assert is_valid is True
        assert category == CommandCategory.CUSTOM


class TestParseCommand:
    """Tests for command parsing."""

    def test_parse_simple_command(self) -> None:
        """Test parsing simple command."""
        executor = CommandExecutor()

        args = executor.parse_command("echo hello world")

        assert args == ["echo", "hello", "world"]

    def test_parse_quoted_command(self) -> None:
        """Test parsing command with quotes."""
        executor = CommandExecutor()

        args = executor.parse_command('echo "hello world"')

        assert args == ["echo", "hello world"]

    def test_parse_invalid_quotes(self) -> None:
        """Test parsing with invalid quotes."""
        executor = CommandExecutor()

        with pytest.raises(CommandValidationError):
            executor.parse_command('echo "unclosed')


class TestSanitizePath:
    """Tests for path sanitization."""

    def test_sanitize_simple_path(self, tmp_path: Path) -> None:
        """Test sanitizing simple path."""
        executor = CommandExecutor()

        # Create a real file to resolve
        test_file = tmp_path / "test.txt"
        test_file.touch()

        sanitized = executor.sanitize_path(str(test_file))

        # Should resolve to absolute path
        assert sanitized == str(test_file.resolve())

    def test_sanitize_relative_path(self) -> None:
        """Test sanitizing relative path resolves to absolute."""
        executor = CommandExecutor()

        sanitized = executor.sanitize_path("test.txt")

        # Should be absolute
        assert Path(sanitized).is_absolute()

    def test_sanitize_paths_list(self) -> None:
        """Test sanitizing multiple paths."""
        executor = CommandExecutor()

        sanitized = executor.sanitize_paths(["/tmp/a.txt", "/tmp/b.txt"])

        assert len(sanitized) == 2
        assert all(isinstance(p, str) for p in sanitized)


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

        result = executor.execute("python -c 'exit(1)'")

        assert result.success is False
        assert result.exit_code == 1

    def test_execute_invalid_command_raises(self) -> None:
        """Test invalid command raises exception."""
        executor = CommandExecutor()

        with pytest.raises(CommandValidationError):
            executor.execute("dangerous; command")

    def test_execute_command_not_found(self, tmp_path: Path) -> None:
        """Test command not found."""
        executor = CommandExecutor(working_dir=tmp_path, allow_unlisted=True)

        result = executor.execute("nonexistent-command-xyz")

        assert result.success is False
        assert "not found" in result.stderr.lower()

    def test_execute_with_env(self, tmp_path: Path) -> None:
        """Test execution with environment variables."""
        # Use allow_unlisted to test custom scripts
        executor = CommandExecutor(working_dir=tmp_path, allow_unlisted=True)

        # Create a script to read env var (avoids semicolons in command)
        script = tmp_path / "test_env.py"
        script.write_text('import os\nprint(os.environ.get("ZERG_TEST_VAR", ""))')

        result = executor.execute(
            f"python {script}",
            env={"ZERG_TEST_VAR": "test_value"},
        )

        assert result.success is True
        assert "test_value" in result.stdout

    def test_execute_with_cwd(self, tmp_path: Path) -> None:
        """Test execution with custom working directory."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        executor = CommandExecutor()

        result = executor.execute("pwd", cwd=subdir)

        assert result.success is True
        assert str(subdir) in result.stdout

    def test_execute_list_args(self, tmp_path: Path) -> None:
        """Test execution with list arguments."""
        executor = CommandExecutor(working_dir=tmp_path)

        result = executor.execute(["echo", "hello", "world"])

        assert result.success is True
        assert "hello world" in result.stdout

    def test_execute_records_history(self, tmp_path: Path) -> None:
        """Test execution records to history."""
        executor = CommandExecutor(working_dir=tmp_path)

        executor.execute("echo one")
        executor.execute("echo two")

        history = executor.get_history()
        assert len(history) == 2

    def test_execute_history_disabled(self, tmp_path: Path) -> None:
        """Test history disabled."""
        executor = CommandExecutor(working_dir=tmp_path, audit_log=False)

        executor.execute("echo test")

        assert len(executor.get_history()) == 0


class TestValidateEnvVars:
    """Tests for environment variable validation."""

    def test_validate_safe_env(self) -> None:
        """Test safe environment variables pass."""
        executor = CommandExecutor()

        validated = executor._validate_env_vars({"MY_VAR": "value"})

        assert "MY_VAR" in validated

    def test_validate_dangerous_env_blocked(self) -> None:
        """Test dangerous environment variables are blocked."""
        executor = CommandExecutor()

        validated = executor._validate_env_vars(
            {
                "LD_PRELOAD": "/evil.so",
                "SAFE_VAR": "ok",
            }
        )

        assert "LD_PRELOAD" not in validated
        assert "SAFE_VAR" in validated

    def test_validate_env_with_shell_chars(self) -> None:
        """Test env vars with shell chars are blocked."""
        executor = CommandExecutor()

        validated = executor._validate_env_vars(
            {
                "BAD_VAR": "value; rm -rf /",
                "GOOD_VAR": "safe_value",
            }
        )

        assert "BAD_VAR" not in validated
        assert "GOOD_VAR" in validated


class TestExecuteGit:
    """Tests for git command execution."""

    def test_execute_git(self, tmp_repo: Path) -> None:
        """Test git command execution."""
        executor = CommandExecutor(working_dir=tmp_repo)

        result = executor.execute_git("status")

        assert result.success is True
        assert "branch" in result.stdout.lower() or "main" in result.stdout.lower()

    def test_execute_git_with_args(self, tmp_repo: Path) -> None:
        """Test git command with arguments."""
        executor = CommandExecutor(working_dir=tmp_repo)

        result = executor.execute_git("log", "--oneline", "-1")

        assert result.success is True


class TestExecutePython:
    """Tests for Python command execution."""

    def test_execute_python(self, tmp_path: Path) -> None:
        """Test Python command execution."""
        executor = CommandExecutor(working_dir=tmp_path)

        result = executor.execute_python("-c", "print('hello')")

        assert result.success is True
        assert "hello" in result.stdout


class TestModuleFunctions:
    """Tests for module-level functions."""

    def test_get_executor_default(self) -> None:
        """Test getting default executor."""
        executor = get_executor()

        assert isinstance(executor, CommandExecutor)

    def test_get_executor_with_args(self, tmp_path: Path) -> None:
        """Test getting executor with custom args."""
        executor = get_executor(working_dir=tmp_path, allow_unlisted=True)

        assert executor.working_dir == tmp_path
        assert executor.allow_unlisted is True

    def test_execute_safe(self, tmp_path: Path, monkeypatch) -> None:
        """Test safe execution function."""
        monkeypatch.chdir(tmp_path)

        result = execute_safe("echo test")

        assert result.success is True


class TestAllowedCommands:
    """Tests for the command allowlist."""

    def test_pytest_allowed(self) -> None:
        """Test pytest is in allowlist."""
        assert "pytest" in ALLOWED_COMMAND_PREFIXES

    def test_git_commands_allowed(self) -> None:
        """Test git commands are allowed."""
        assert "git status" in ALLOWED_COMMAND_PREFIXES
        assert "git diff" in ALLOWED_COMMAND_PREFIXES
        assert "git commit" in ALLOWED_COMMAND_PREFIXES

    def test_linting_commands_allowed(self) -> None:
        """Test linting commands are allowed."""
        assert "ruff" in ALLOWED_COMMAND_PREFIXES
        assert "mypy" in ALLOWED_COMMAND_PREFIXES
        assert "flake8" in ALLOWED_COMMAND_PREFIXES

    def test_categories_assigned(self) -> None:
        """Test categories are properly assigned."""
        assert ALLOWED_COMMAND_PREFIXES["pytest"] == CommandCategory.TESTING
        assert ALLOWED_COMMAND_PREFIXES["ruff"] == CommandCategory.LINTING
        assert ALLOWED_COMMAND_PREFIXES["git status"] == CommandCategory.GIT
