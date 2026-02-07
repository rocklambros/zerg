"""Integration tests for architecture compliance quality gate."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from zerg.architecture_gate import ArchitectureGate, check_files
from zerg.constants import GateResult
from zerg.plugins import GateContext


class TestArchitectureGate:
    """Integration tests for ArchitectureGate plugin."""

    @pytest.fixture
    def gate(self) -> ArchitectureGate:
        """Create gate instance."""
        return ArchitectureGate()

    @pytest.fixture
    def temp_project(self, tmp_path: Path) -> Path:
        """Create temporary project with config."""
        # Create .zerg directory
        zerg_dir = tmp_path / ".zerg"
        zerg_dir.mkdir()

        # Create src directory
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        return tmp_path

    def test_gate_name(self, gate: ArchitectureGate) -> None:
        """Gate has correct name."""
        assert gate.name == "architecture"

    def test_gate_skip_when_disabled(self, gate: ArchitectureGate, temp_project: Path) -> None:
        """Gate skips when architecture checking is disabled."""
        # Create config with disabled architecture
        config_path = temp_project / ".zerg" / "config.yaml"
        config_path.write_text("architecture:\n  enabled: false\n")

        ctx = GateContext(
            feature="test",
            level=0,
            cwd=temp_project,
            config=None,
        )

        result = gate.run(ctx)

        assert result.result == GateResult.SKIP
        assert "disabled" in result.stdout.lower()

    def test_gate_skip_when_no_config(self, gate: ArchitectureGate, temp_project: Path) -> None:
        """Gate skips when no architecture config exists."""
        # Create empty config
        config_path = temp_project / ".zerg" / "config.yaml"
        config_path.write_text("other:\n  key: value\n")

        ctx = GateContext(
            feature="test",
            level=0,
            cwd=temp_project,
            config=None,
        )

        result = gate.run(ctx)

        assert result.result == GateResult.SKIP

    def test_gate_passes_clean_project(self, gate: ArchitectureGate, temp_project: Path) -> None:
        """Gate passes on project with no violations."""
        # Create config
        config_path = temp_project / ".zerg" / "config.yaml"
        config_path.write_text(
            dedent(
                """\
            architecture:
              enabled: true
              import_rules:
                - directory: "src/"
                  deny: ["flask"]
            """
            )
        )

        # Create clean source file
        src_file = temp_project / "src" / "module.py"
        src_file.write_text("import json\n")

        ctx = GateContext(
            feature="test",
            level=0,
            cwd=temp_project,
            config=None,
        )

        result = gate.run(ctx)

        assert result.result == GateResult.PASS
        assert result.exit_code == 0

    def test_gate_fails_on_violation(self, gate: ArchitectureGate, temp_project: Path) -> None:
        """Gate fails when violations are found."""
        # Create config
        config_path = temp_project / ".zerg" / "config.yaml"
        config_path.write_text(
            dedent(
                """\
            architecture:
              enabled: true
              import_rules:
                - directory: "src/"
                  deny: ["flask"]
            """
            )
        )

        # Create violating source file
        src_file = temp_project / "src" / "module.py"
        src_file.write_text("import flask\n")

        ctx = GateContext(
            feature="test",
            level=0,
            cwd=temp_project,
            config=None,
        )

        result = gate.run(ctx)

        assert result.result == GateResult.FAIL
        assert result.exit_code == 1
        assert "flask" in result.stderr
        assert "denied" in result.stderr.lower()

    def test_gate_passes_with_warnings(self, gate: ArchitectureGate, temp_project: Path) -> None:
        """Gate passes when only warnings (not errors) are found."""
        # Create config with naming conventions (warnings)
        config_path = temp_project / ".zerg" / "config.yaml"
        config_path.write_text(
            dedent(
                """\
            architecture:
              enabled: true
              naming_conventions:
                - directory: "src/"
                  files: "snake_case"
            """
            )
        )

        # Create file with naming warning
        src_file = temp_project / "src" / "MyModule.py"
        src_file.write_text("x = 1\n")

        ctx = GateContext(
            feature="test",
            level=0,
            cwd=temp_project,
            config=None,
        )

        result = gate.run(ctx)

        assert result.result == GateResult.PASS
        assert "warning" in result.stdout.lower()

    def test_gate_reports_duration(self, gate: ArchitectureGate, temp_project: Path) -> None:
        """Gate reports execution duration."""
        config_path = temp_project / ".zerg" / "config.yaml"
        config_path.write_text("architecture:\n  enabled: true\n")

        ctx = GateContext(
            feature="test",
            level=0,
            cwd=temp_project,
            config=None,
        )

        result = gate.run(ctx)

        assert result.duration_ms >= 0

    def test_gate_clear_error_messages(self, gate: ArchitectureGate, temp_project: Path) -> None:
        """Gate produces clear, actionable error messages."""
        config_path = temp_project / ".zerg" / "config.yaml"
        config_path.write_text(
            dedent(
                """\
            architecture:
              enabled: true
              import_rules:
                - directory: "src/"
                  deny: ["flask", "django"]
            """
            )
        )

        src_file = temp_project / "src" / "web.py"
        src_file.write_text("import flask\nimport django\n")

        ctx = GateContext(
            feature="test",
            level=0,
            cwd=temp_project,
            config=None,
        )

        result = gate.run(ctx)

        # Check error message quality
        assert "IMPORT:" in result.stderr
        assert "src/web.py" in result.stderr
        assert "flask" in result.stderr
        assert "django" in result.stderr
        assert "exception" in result.stderr.lower()  # Shows how to add exception


class TestCheckFiles:
    """Tests for check_files convenience function."""

    def test_check_specific_files(self, tmp_path: Path) -> None:
        """Check specific files for violations."""
        # Create project structure
        zerg_dir = tmp_path / ".zerg"
        zerg_dir.mkdir()

        config_path = zerg_dir / "config.yaml"
        config_path.write_text(
            dedent(
                """\
            architecture:
              enabled: true
              import_rules:
                - directory: ""
                  deny: ["flask"]
            """
            )
        )

        # Create files
        good_file = tmp_path / "good.py"
        good_file.write_text("import json\n")

        bad_file = tmp_path / "bad.py"
        bad_file.write_text("import flask\n")

        # Check only good file
        violations = check_files([good_file], root=tmp_path)
        assert not violations

        # Check bad file
        violations = check_files([bad_file], root=tmp_path)
        assert len(violations) == 1

    def test_check_files_disabled(self, tmp_path: Path) -> None:
        """Returns empty when architecture checking is disabled."""
        zerg_dir = tmp_path / ".zerg"
        zerg_dir.mkdir()

        config_path = zerg_dir / "config.yaml"
        config_path.write_text("architecture:\n  enabled: false\n")

        file_path = tmp_path / "module.py"
        file_path.write_text("import flask\n")

        violations = check_files([file_path], root=tmp_path)
        assert not violations


class TestLayerIntegration:
    """Integration tests for layer boundary enforcement."""

    @pytest.fixture
    def layered_project(self, tmp_path: Path) -> Path:
        """Create project with layer structure."""
        # Create directories
        (tmp_path / ".zerg").mkdir()
        (tmp_path / "src" / "core").mkdir(parents=True)
        (tmp_path / "src" / "services").mkdir(parents=True)
        (tmp_path / "src" / "api").mkdir(parents=True)

        # Create config with layers
        config_path = tmp_path / ".zerg" / "config.yaml"
        config_path.write_text(
            dedent(
                """\
            architecture:
              enabled: true
              layers:
                - name: core
                  paths: ["src/core/*.py"]
                  allowed_imports: ["stdlib"]
                - name: services
                  paths: ["src/services/*.py"]
                  allowed_imports: ["stdlib", "core"]
                - name: api
                  paths: ["src/api/*.py"]
                  allowed_imports: ["stdlib", "core", "services"]
            """
            )
        )

        # Create module files
        (tmp_path / "src" / "core" / "config.py").write_text("CONFIG = {}\n")
        (tmp_path / "src" / "services" / "auth.py").write_text("import json\n")
        (tmp_path / "src" / "api" / "routes.py").write_text("import json\n")

        return tmp_path

    def test_layer_allowed_imports_pass(self, layered_project: Path) -> None:
        """Allowed layer imports pass validation."""
        gate = ArchitectureGate()
        ctx = GateContext(
            feature="test",
            level=0,
            cwd=layered_project,
            config=None,
        )

        result = gate.run(ctx)
        assert result.result == GateResult.PASS


class TestExceptionIntegration:
    """Integration tests for exception handling."""

    def test_file_exception_works(self, tmp_path: Path) -> None:
        """File exceptions exempt files from checking."""
        # Setup
        (tmp_path / ".zerg").mkdir()
        (tmp_path / "src").mkdir()

        config_path = tmp_path / ".zerg" / "config.yaml"
        config_path.write_text(
            dedent(
                """\
            architecture:
              enabled: true
              import_rules:
                - directory: "src/"
                  deny: ["flask"]
              exceptions:
                - file: "src/__init__.py"
                  reason: "Package init"
            """
            )
        )

        # Create exempt file with violation
        init_file = tmp_path / "src" / "__init__.py"
        init_file.write_text("import flask\n")

        # Create non-exempt file with violation
        module_file = tmp_path / "src" / "module.py"
        module_file.write_text("import flask\n")

        gate = ArchitectureGate()
        ctx = GateContext(feature="test", level=0, cwd=tmp_path, config=None)

        result = gate.run(ctx)

        # Should fail only for non-exempt file
        assert result.result == GateResult.FAIL
        assert "module.py" in result.stderr
        assert "__init__.py" not in result.stderr
