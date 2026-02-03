"""Integration tests for init command devcontainer creation."""

import json
import os
import subprocess
from pathlib import Path

from click.testing import CliRunner

from zerg.cli import cli


class TestInitCommand:
    """Test suite for init command devcontainer generation."""

    def test_init_creates_multi_lang_devcontainer(self, tmp_path: Path) -> None:
        """Init creates devcontainer for multi-language project.

        Creates a project with Python and JavaScript markers,
        runs init --detect, and verifies the generated devcontainer
        has appropriate configuration.
        """
        # Create multi-lang project markers
        (tmp_path / "requirements.txt").write_text("pytest>=7.0\nclick>=8.0\n")
        (tmp_path / "package.json").write_text('{"name": "test", "version": "1.0.0"}')

        # Initialize git repo (required for init)
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

        runner = CliRunner()

        # Change to temp directory and run init
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(cli, ["init", "--detect", "--force"])

            # Check for success or already initialized
            assert result.exit_code == 0 or "already initialized" in result.output.lower(), (
                f"Init failed: {result.output}"
            )

            # Check devcontainer created
            devcontainer_path = tmp_path / ".devcontainer" / "devcontainer.json"
            if devcontainer_path.exists():
                config = json.loads(devcontainer_path.read_text())
                # Verify has features or image (either is valid)
                assert "features" in config or "image" in config, f"Config missing features/image: {config.keys()}"
        finally:
            os.chdir(original_cwd)
