"""Tests for zerg.diagnostics.env_diagnostics module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from zerg.diagnostics.env_diagnostics import (
    ConfigValidator,
    DockerDiagnostics,
    EnvDiagnosticsEngine,
    PythonEnvDiagnostics,
    ResourceDiagnostics,
)


# ---------------------------------------------------------------------------
# TestPythonEnvDiagnostics
# ---------------------------------------------------------------------------
class TestPythonEnvDiagnostics:
    """Tests for PythonEnvDiagnostics."""

    def test_check_venv(self) -> None:
        """check_venv returns dict with expected keys."""
        diag = PythonEnvDiagnostics()
        result = diag.check_venv()

        assert "active" in result
        assert "path" in result
        assert "python_version" in result
        assert "executable" in result
        assert isinstance(result["active"], bool)

    def test_check_packages(self) -> None:
        """Mocked pip list returns installed packages with count."""
        packages = [
            {"name": "requests", "version": "2.28.0"},
            {"name": "pytest", "version": "7.4.0"},
        ]
        mock_result = MagicMock(stdout=json.dumps(packages), returncode=0)

        diag = PythonEnvDiagnostics()
        with patch("subprocess.run", return_value=mock_result):
            result = diag.check_packages()

        assert "installed" in result
        assert "count" in result
        assert result["count"] == 2

    def test_check_packages_failure(self) -> None:
        """Subprocess failure returns graceful empty result."""
        mock_result = MagicMock(stdout="", returncode=1)

        diag = PythonEnvDiagnostics()
        with patch("subprocess.run", return_value=mock_result):
            result = diag.check_packages()

        assert result["installed"] == []
        assert result["count"] == 0

    def test_check_imports(self) -> None:
        """Mocked import check returns success and failed lists."""
        diag = PythonEnvDiagnostics()

        def side_effect(cmd, **kwargs):
            # Simulate: 'os' succeeds, 'nonexistent' fails
            module = cmd[-1].replace("import ", "")
            if module == "os":
                return MagicMock(stdout="", returncode=0)
            return MagicMock(stdout="import failed", returncode=1)

        with patch("subprocess.run", side_effect=side_effect):
            result = diag.check_imports(["os", "nonexistent"])

        assert "success" in result
        assert "failed" in result
        assert "os" in result["success"]
        assert len(result["failed"]) == 1
        assert result["failed"][0]["module"] == "nonexistent"


# ---------------------------------------------------------------------------
# TestDockerDiagnostics
# ---------------------------------------------------------------------------
class TestDockerDiagnostics:
    """Tests for DockerDiagnostics."""

    def test_check_health_docker_available(self) -> None:
        """Docker available returns dict with 'running': True."""
        diag = DockerDiagnostics()

        def side_effect(cmd, **kwargs):
            if cmd == ["docker", "info"]:
                return MagicMock(stdout="", returncode=0)
            if cmd[0:2] == ["docker", "version"]:
                return MagicMock(stdout="24.0.0", returncode=0)
            if cmd[0:2] == ["docker", "system"]:
                return MagicMock(stdout="TYPE  TOTAL", returncode=0)
            return MagicMock(stdout="", returncode=0)

        with patch("subprocess.run", side_effect=side_effect):
            result = diag.check_health()

        assert result is not None
        assert result["running"] is True

    def test_check_health_docker_unavailable(self) -> None:
        """Docker unavailable returns None."""
        diag = DockerDiagnostics()
        mock_result = MagicMock(stdout="", returncode=1)

        with patch("subprocess.run", return_value=mock_result):
            result = diag.check_health()

        assert result is None

    def test_check_containers(self) -> None:
        """Mocked docker ps output returns container list."""
        diag = DockerDiagnostics()

        call_count = 0

        def side_effect(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            # First call: running containers
            if call_count == 1:
                return MagicMock(
                    stdout="abc123\tzerg-worker-1\tUp 5 minutes",
                    returncode=0,
                )
            # Second call: stopped containers
            return MagicMock(stdout="", returncode=0)

        with patch("subprocess.run", side_effect=side_effect):
            result = diag.check_containers()

        assert "containers" in result
        assert result["running"] == 1
        assert len(result["containers"]) >= 1
        assert result["containers"][0]["name"] == "zerg-worker-1"


# ---------------------------------------------------------------------------
# TestResourceDiagnostics
# ---------------------------------------------------------------------------
class TestResourceDiagnostics:
    """Tests for ResourceDiagnostics."""

    def test_check_cpu(self) -> None:
        """check_cpu returns dict with load_avg and cpu_count keys."""
        diag = ResourceDiagnostics()

        with patch("os.getloadavg", return_value=(1.5, 1.2, 0.9)):
            with patch("os.cpu_count", return_value=8):
                result = diag.check_cpu()

        assert "load_avg_1m" in result
        assert "cpu_count" in result
        assert isinstance(result["load_avg_1m"], float)
        assert isinstance(result["cpu_count"], int)
        assert result["cpu_count"] == 8

    def test_check_disk_detailed(self) -> None:
        """check_disk_detailed returns dict with total_gb, free_gb, used_percent."""
        diag = ResourceDiagnostics()

        mock_usage = MagicMock(
            total=500 * (1024**3),
            used=200 * (1024**3),
            free=300 * (1024**3),
        )
        with patch("shutil.disk_usage", return_value=mock_usage):
            result = diag.check_disk_detailed()

        assert "total_gb" in result
        assert "free_gb" in result
        assert "used_percent" in result
        assert result["total_gb"] == 500.0
        assert result["free_gb"] == 300.0

    def test_check_memory(self) -> None:
        """check_memory returns dict with expected keys (mocked for macOS)."""
        diag = ResourceDiagnostics()

        sysctl_result = MagicMock(stdout="17179869184", returncode=0)  # 16 GB
        vm_stat_output = (
            "Mach Virtual Memory Statistics: (page size of 4096 bytes)\n"
            "Pages free:                              500000.\n"
            "Pages speculative:                       100000.\n"
        )
        vm_stat_result = MagicMock(stdout=vm_stat_output, returncode=0)

        def side_effect(cmd, **kwargs):
            if "sysctl" in cmd:
                return sysctl_result
            if "vm_stat" in cmd:
                return vm_stat_result
            return MagicMock(stdout="", returncode=1)

        with patch("sys.platform", "darwin"):
            with patch("subprocess.run", side_effect=side_effect):
                result = diag.check_memory()

        assert "total_gb" in result
        assert "available_gb" in result
        assert "used_percent" in result

    def test_check_file_descriptors(self) -> None:
        """check_file_descriptors returns dict with limits."""
        diag = ResourceDiagnostics()
        result = diag.check_file_descriptors()

        assert "soft_limit" in result
        assert "hard_limit" in result
        # On macOS/Linux these should be positive integers
        assert isinstance(result["soft_limit"], int)
        assert isinstance(result["hard_limit"], int)


# ---------------------------------------------------------------------------
# TestConfigValidator
# ---------------------------------------------------------------------------
class TestConfigValidator:
    """Tests for ConfigValidator."""

    def test_validate_missing_file(self) -> None:
        """Non-existent config returns list with 'not found' message."""
        validator = ConfigValidator()
        issues = validator.validate(Path("/nonexistent/config.yaml"))

        assert len(issues) >= 1
        assert any("not found" in issue.lower() for issue in issues)

    def test_validate_existing_file(self, tmp_path: Path) -> None:
        """Existing yaml-like file returns a list (possibly with issues)."""
        config = tmp_path / "config.yaml"
        config.write_text("workers: 5\ntimeouts:\n  default: 30\n")

        validator = ConfigValidator()
        issues = validator.validate(config)

        assert isinstance(issues, list)


# ---------------------------------------------------------------------------
# TestEnvDiagnosticsEngine
# ---------------------------------------------------------------------------
class TestEnvDiagnosticsEngine:
    """Tests for EnvDiagnosticsEngine facade."""

    def test_run_all(self, tmp_path: Path) -> None:
        """run_all returns dict with python, docker, resources, config, evidence keys."""
        # Create a minimal config to avoid file-not-found noise
        config_path = tmp_path / "config.yaml"
        config_path.write_text("workers: 3\n")

        engine = EnvDiagnosticsEngine()

        # Mock all subprocess calls to avoid real docker/pip/sysctl execution
        mock_result = MagicMock(stdout="", returncode=1)

        with patch("subprocess.run", return_value=mock_result):
            result = engine.run_all(config_path=config_path)

        assert "python" in result
        assert "docker" in result
        assert "resources" in result
        assert "config" in result
        assert "evidence" in result
        assert isinstance(result["evidence"], list)
