"""Integration tests for ZERG pre-commit hook.

These tests verify the full hook execution against a real git repository.
"""

import os
import shutil
import stat
import subprocess
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture
def hook_test_repo(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary git repo with ZERG hook installed.

    Yields:
        Path to the temporary repository
    """
    orig_dir = os.getcwd()

    # Initialize git repo
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
    )

    # Create initial commit
    readme = tmp_path / "README.md"
    readme.write_text("# Test Repo\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "Initial commit"],
        cwd=tmp_path,
        check=True,
    )

    # Copy and install pre-commit hook
    hook_src = Path(__file__).parent.parent.parent / ".zerg" / "hooks" / "pre-commit"
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_dest = hooks_dir / "pre-commit"

    shutil.copy(hook_src, hook_dest)
    hook_dest.chmod(hook_dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(orig_dir)


class TestPrecommitHookIntegration:
    """Integration tests for the pre-commit hook."""

    @staticmethod
    def get_output(result: subprocess.CompletedProcess) -> str:
        """Get combined stdout and stderr for checking."""
        return result.stdout + result.stderr

    def test_clean_commit_passes(self, hook_test_repo: Path) -> None:
        """Clean commits should pass all checks."""
        clean_file = hook_test_repo / "clean.py"
        clean_file.write_text('"""Clean module."""\n\n\ndef main() -> None:\n    pass\n')

        subprocess.run(["git", "add", "clean.py"], cwd=hook_test_repo, check=True)
        result = subprocess.run(
            ["git", "commit", "-m", "test: add clean file"],
            cwd=hook_test_repo,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Clean commit should pass: {result.stderr}"

    def test_aws_key_blocks(self, hook_test_repo: Path) -> None:
        """AWS access key should block commit."""
        bad_file = hook_test_repo / "config.py"
        bad_file.write_text('AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n')

        subprocess.run(["git", "add", "config.py"], cwd=hook_test_repo, check=True)
        result = subprocess.run(
            ["git", "commit", "-m", "test: add config"],
            cwd=hook_test_repo,
            capture_output=True,
            text=True,
        )
        output = self.get_output(result)
        assert result.returncode != 0, "AWS key should block commit"
        assert "AWS Access Key" in output or "BLOCKED" in output

    def test_github_pat_blocks(self, hook_test_repo: Path) -> None:
        """GitHub PAT should block commit."""
        bad_file = hook_test_repo / "auth.py"
        bad_file.write_text('GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"\n')

        subprocess.run(["git", "add", "auth.py"], cwd=hook_test_repo, check=True)
        result = subprocess.run(
            ["git", "commit", "-m", "test: add auth"],
            cwd=hook_test_repo,
            capture_output=True,
            text=True,
        )
        output = self.get_output(result)
        assert result.returncode != 0, "GitHub PAT should block commit"
        assert "GitHub" in output or "BLOCKED" in output

    def test_private_key_blocks(self, hook_test_repo: Path) -> None:
        """Private key should block commit."""
        bad_file = hook_test_repo / "key.py"
        # Use proper multi-line private key format so grep can find the header
        bad_file.write_text(
            'KEY = """\n-----BEGIN RSA PRIVATE KEY-----\nMIIBogIBAAJBAKj34GkxFhD\n-----END RSA PRIVATE KEY-----\n"""\n'
        )

        subprocess.run(["git", "add", "key.py"], cwd=hook_test_repo, check=True)
        result = subprocess.run(
            ["git", "commit", "-m", "test: add key"],
            cwd=hook_test_repo,
            capture_output=True,
            text=True,
        )
        output = self.get_output(result)
        assert result.returncode != 0, f"Private key should block commit: {output}"
        assert "Private key" in output or "BLOCKED" in output

    def test_shell_true_blocks(self, hook_test_repo: Path) -> None:
        """shell=True should block commit."""
        bad_file = hook_test_repo / "cmd.py"
        bad_file.write_text('import subprocess\nsubprocess.run("ls", shell=True)\n')

        subprocess.run(["git", "add", "cmd.py"], cwd=hook_test_repo, check=True)
        result = subprocess.run(
            ["git", "commit", "-m", "test: add cmd"],
            cwd=hook_test_repo,
            capture_output=True,
            text=True,
        )
        output = self.get_output(result)
        assert result.returncode != 0, "shell=True should block commit"
        assert "Shell injection" in output or "shell" in output.lower()

    def test_eval_blocks(self, hook_test_repo: Path) -> None:
        """eval() should block commit."""
        bad_file = hook_test_repo / "dynamic.py"
        bad_file.write_text("result = eval(user_input)\n")

        subprocess.run(["git", "add", "dynamic.py"], cwd=hook_test_repo, check=True)
        result = subprocess.run(
            ["git", "commit", "-m", "test: add dynamic"],
            cwd=hook_test_repo,
            capture_output=True,
            text=True,
        )
        output = self.get_output(result)
        assert result.returncode != 0, "eval() should block commit"
        assert "Code injection" in output or "eval" in output.lower()

    def test_env_file_blocks(self, hook_test_repo: Path) -> None:
        """Sensitive files should block commit."""
        env_file = hook_test_repo / ".env"
        env_file.write_text("DATABASE_URL=postgres://...\n")

        subprocess.run(["git", "add", ".env"], cwd=hook_test_repo, check=True)
        result = subprocess.run(
            ["git", "commit", "-m", "test: add env"],
            cwd=hook_test_repo,
            capture_output=True,
            text=True,
        )
        output = self.get_output(result)
        assert result.returncode != 0, ".env should block commit"
        assert "Sensitive file" in output or ".env" in output

    def test_debugger_warns(self, hook_test_repo: Path) -> None:
        """Debugger statements should warn but not block."""
        debug_file = hook_test_repo / "debug.py"
        debug_file.write_text("def foo():\n    breakpoint()\n    return 1\n")

        subprocess.run(["git", "add", "debug.py"], cwd=hook_test_repo, check=True)
        result = subprocess.run(
            ["git", "commit", "-m", "test: add debug"],
            cwd=hook_test_repo,
            capture_output=True,
            text=True,
        )
        output = self.get_output(result)
        # Should pass with warning (quality check, not security)
        assert result.returncode == 0, f"Debugger should warn, not block: {result.stderr}"
        assert "WARNING" in output or "Debugger" in output

    def test_merge_marker_warns(self, hook_test_repo: Path) -> None:
        """Merge conflict markers should warn."""
        conflict_file = hook_test_repo / "conflict.py"
        conflict_file.write_text("x = 1\n<<<<<<< HEAD\nx = 2\n=======\nx = 3\n>>>>>>> branch\n")

        subprocess.run(["git", "add", "conflict.py"], cwd=hook_test_repo, check=True)
        result = subprocess.run(
            ["git", "commit", "-m", "test: add conflict"],
            cwd=hook_test_repo,
            capture_output=True,
            text=True,
        )
        output = self.get_output(result)
        # Should pass with warning
        assert result.returncode == 0, f"Merge marker should warn: {result.stderr}"
        assert "WARNING" in output or "Merge" in output

    def test_test_files_exempt(self, hook_test_repo: Path) -> None:
        """Test files should be exempt from certain checks."""
        # Create tests directory
        tests_dir = hook_test_repo / "tests"
        tests_dir.mkdir()

        # Test file with patterns that would normally block
        test_file = tests_dir / "test_example.py"
        test_file.write_text(
            "def test_something():\n"
            "    # Testing shell command\n"
            "    import subprocess\n"
            '    subprocess.run("ls", shell=True)  # OK in tests\n'
        )

        subprocess.run(["git", "add", "tests/test_example.py"], cwd=hook_test_repo, check=True)
        result = subprocess.run(
            ["git", "commit", "-m", "test: add test file"],
            cwd=hook_test_repo,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Test files should be exempt: {result.stderr}"


class TestPrecommitHookZergSpecific:
    """ZERG-specific hook tests."""

    @staticmethod
    def get_output(result: subprocess.CompletedProcess) -> str:
        """Get combined stdout and stderr for checking."""
        return result.stdout + result.stderr

    def test_zerg_branch_naming_valid(self, hook_test_repo: Path) -> None:
        """Valid ZERG branch names should pass."""
        # Create and checkout a valid ZERG branch
        subprocess.run(
            ["git", "checkout", "-b", "zerg/feature/worker-1"],
            cwd=hook_test_repo,
            check=True,
        )

        clean_file = hook_test_repo / "worker.py"
        clean_file.write_text('"""Worker code."""\n')

        subprocess.run(["git", "add", "worker.py"], cwd=hook_test_repo, check=True)
        result = subprocess.run(
            ["git", "commit", "-m", "feat: worker code"],
            cwd=hook_test_repo,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Valid ZERG branch should pass: {result.stderr}"

    def test_zerg_branch_naming_invalid_warns(self, hook_test_repo: Path) -> None:
        """Invalid ZERG branch names should warn."""
        # Create and checkout an invalid ZERG branch
        subprocess.run(
            ["git", "checkout", "-b", "zerg/feature"],  # Missing worker suffix
            cwd=hook_test_repo,
            check=True,
        )

        clean_file = hook_test_repo / "code.py"
        clean_file.write_text('"""Code."""\n')

        subprocess.run(["git", "add", "code.py"], cwd=hook_test_repo, check=True)
        result = subprocess.run(
            ["git", "commit", "-m", "feat: code"],
            cwd=hook_test_repo,
            capture_output=True,
            text=True,
        )
        output = self.get_output(result)
        # Should pass with warning (ZERG naming is a warning, not a block)
        assert result.returncode == 0, f"Invalid ZERG branch should warn: {result.stderr}"
        assert "WARNING" in output or "zerg/{feature}/worker-{N}" in output

    def test_print_in_zerg_dir_warns(self, hook_test_repo: Path) -> None:
        """Print statements in zerg/ directory should warn."""
        # Create zerg directory
        zerg_dir = hook_test_repo / "zerg"
        zerg_dir.mkdir()

        zerg_file = zerg_dir / "module.py"
        zerg_file.write_text('def foo():\n    print("debug")\n')

        subprocess.run(["git", "add", "zerg/module.py"], cwd=hook_test_repo, check=True)
        result = subprocess.run(
            ["git", "commit", "-m", "feat: zerg module"],
            cwd=hook_test_repo,
            capture_output=True,
            text=True,
        )
        output = self.get_output(result)
        # Should pass with warning
        assert result.returncode == 0, f"Print in zerg/ should warn: {result.stderr}"
        assert "WARNING" in output or "print" in output.lower()

    def test_print_outside_zerg_allowed(self, hook_test_repo: Path) -> None:
        """Print statements outside zerg/ should be allowed."""
        other_file = hook_test_repo / "script.py"
        other_file.write_text('print("hello")\n')

        subprocess.run(["git", "add", "script.py"], cwd=hook_test_repo, check=True)
        result = subprocess.run(
            ["git", "commit", "-m", "feat: script"],
            cwd=hook_test_repo,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Print outside zerg/ should pass: {result.stderr}"
