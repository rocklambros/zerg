"""Tests for ZERG v2 Build Command."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestBuildSystem:
    """Tests for build system enumeration."""

    def test_systems_exist(self):
        """Test build systems are defined."""
        from build import BuildSystem

        assert hasattr(BuildSystem, "NPM")
        assert hasattr(BuildSystem, "CARGO")
        assert hasattr(BuildSystem, "MAKE")
        assert hasattr(BuildSystem, "GRADLE")
        assert hasattr(BuildSystem, "GO")


class TestBuildConfig:
    """Tests for build configuration."""

    def test_config_defaults(self):
        """Test BuildConfig has sensible defaults."""
        from build import BuildConfig

        config = BuildConfig()
        assert config.mode == "dev"
        assert config.clean is False

    def test_config_custom(self):
        """Test BuildConfig with custom values."""
        from build import BuildConfig

        config = BuildConfig(mode="prod", clean=True, watch=True)
        assert config.mode == "prod"
        assert config.clean is True


class TestBuildResult:
    """Tests for build results."""

    def test_result_creation(self):
        """Test BuildResult can be created."""
        from build import BuildResult

        result = BuildResult(
            success=True,
            duration_seconds=10.5,
            artifacts=[],
        )
        assert result.success is True

    def test_result_with_errors(self):
        """Test BuildResult with errors."""
        from build import BuildResult

        result = BuildResult(
            success=False,
            duration_seconds=5.0,
            artifacts=[],
            errors=["Missing dependency"],
        )
        assert result.success is False
        assert len(result.errors) == 1


class TestErrorCategory:
    """Tests for error categories."""

    def test_categories_exist(self):
        """Test error categories are defined."""
        from build import ErrorCategory

        assert hasattr(ErrorCategory, "MISSING_DEPENDENCY")
        assert hasattr(ErrorCategory, "TYPE_ERROR")
        assert hasattr(ErrorCategory, "RESOURCE_EXHAUSTION")
        assert hasattr(ErrorCategory, "NETWORK_TIMEOUT")


class TestBuildDetector:
    """Tests for build system detection."""

    def test_detector_creation(self):
        """Test BuildDetector can be created."""
        from build import BuildDetector

        detector = BuildDetector()
        assert detector is not None

    def test_detector_returns_list(self):
        """Test detector returns list of systems."""
        from build import BuildDetector

        detector = BuildDetector()
        systems = detector.detect(Path("."))
        assert isinstance(systems, list)


class TestErrorRecovery:
    """Tests for error recovery."""

    def test_recovery_creation(self):
        """Test ErrorRecovery can be created."""
        from build import ErrorRecovery

        recovery = ErrorRecovery()
        assert recovery is not None

    def test_classify_error(self):
        """Test classifying errors."""
        from build import ErrorCategory, ErrorRecovery

        recovery = ErrorRecovery()
        category = recovery.classify("ModuleNotFoundError: No module named 'xyz'")
        assert category == ErrorCategory.MISSING_DEPENDENCY


class TestBuildCommand:
    """Tests for BuildCommand class."""

    def test_command_creation(self):
        """Test BuildCommand can be created."""
        from build import BuildCommand

        cmd = BuildCommand()
        assert cmd is not None

    def test_command_supported_systems(self):
        """Test listing supported build systems."""
        from build import BuildCommand

        cmd = BuildCommand()
        systems = cmd.supported_systems()
        assert "npm" in systems
        assert "cargo" in systems

    def test_command_run_returns_result(self):
        """Test run returns BuildResult."""
        from build import BuildCommand, BuildResult

        cmd = BuildCommand()
        result = cmd.run(dry_run=True)
        assert isinstance(result, BuildResult)

    def test_command_format_text(self):
        """Test text output format."""
        from build import BuildCommand, BuildResult

        cmd = BuildCommand()
        result = BuildResult(
            success=True,
            duration_seconds=5.0,
            artifacts=["dist/app.js"],
        )
        output = cmd.format_result(result, format="text")
        assert "Build" in output

    def test_command_format_json(self):
        """Test JSON output format."""
        import json

        from build import BuildCommand, BuildResult

        cmd = BuildCommand()
        result = BuildResult(
            success=True,
            duration_seconds=5.0,
            artifacts=[],
        )
        output = cmd.format_result(result, format="json")
        data = json.loads(output)
        assert data["success"] is True
