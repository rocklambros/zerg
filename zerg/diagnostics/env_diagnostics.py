"""Enhanced environment diagnostics for Python, Docker, resources, and config validation."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from zerg.diagnostics.types import Evidence
from zerg.logging import get_logger

__all__ = [
    "ConfigValidator",
    "DockerDiagnostics",
    "EnvDiagnosticsEngine",
    "PythonEnvDiagnostics",
    "ResourceDiagnostics",
]

logger = get_logger("diagnostics.env")


class PythonEnvDiagnostics:
    """Diagnostics for the Python environment."""

    SUBPROCESS_TIMEOUT = 5

    def _run_cmd(self, cmd: list[str]) -> tuple[str, bool]:
        """Run a command with timeout, return (stdout, success)."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.SUBPROCESS_TIMEOUT,
            )
            return result.stdout.strip(), result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            logger.warning(f"Command failed: {cmd!r}: {e}")
            return "", False

    def check_venv(self) -> dict[str, Any]:
        """Check virtual environment status."""
        return {
            "active": sys.prefix != sys.base_prefix,
            "path": sys.prefix,
            "python_version": sys.version,
            "executable": sys.executable,
        }

    def check_packages(self, required: list[str] | None = None) -> dict[str, Any]:
        """Check installed Python packages and optionally verify required ones."""
        result: dict[str, Any] = {
            "installed": [],
            "missing": [],
            "count": 0,
        }

        stdout, ok = self._run_cmd([sys.executable, "-m", "pip", "list", "--format=json"])
        if not ok:
            logger.warning("Failed to list pip packages")
            return result

        try:
            packages = json.loads(stdout)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Failed to parse pip list output")
            return result

        installed_list: list[dict[str, str]] = [
            {"name": pkg.get("name", ""), "version": pkg.get("version", "")} for pkg in packages
        ]
        result["installed"] = installed_list
        result["count"] = len(installed_list)

        if required:
            installed_names = {pkg["name"].lower() for pkg in installed_list}
            result["missing"] = [name for name in required if name.lower() not in installed_names]

        return result

    def check_imports(self, modules: list[str]) -> dict[str, Any]:
        """Check whether Python modules can be imported."""
        success: list[str] = []
        failed: list[dict[str, str]] = []

        for module in modules:
            stdout, ok = self._run_cmd([sys.executable, "-c", f"import {module}"])
            if ok:
                success.append(module)
            else:
                failed.append({"module": module, "error": stdout or "import failed"})

        return {"success": success, "failed": failed}


class DockerDiagnostics:
    """Diagnostics for Docker environment."""

    SUBPROCESS_TIMEOUT = 5

    def _run_cmd(self, cmd: list[str]) -> tuple[str, bool]:
        """Run a command with timeout, return (stdout, success)."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.SUBPROCESS_TIMEOUT,
            )
            return result.stdout.strip(), result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            logger.warning(f"Command failed: {cmd!r}: {e}")
            return "", False

    def check_health(self) -> dict[str, Any] | None:
        """Check Docker daemon health. Returns None if Docker is unavailable."""
        _, ok = self._run_cmd(["docker", "info"])
        if not ok:
            return None

        version = ""
        stdout, ok = self._run_cmd(["docker", "version", "--format", "{{.Server.Version}}"])
        if ok:
            version = stdout

        disk_usage = ""
        stdout, ok = self._run_cmd(["docker", "system", "df"])
        if ok:
            disk_usage = stdout

        return {
            "running": True,
            "version": version,
            "disk_usage": disk_usage,
        }

    def check_containers(self, label: str = "zerg") -> dict[str, Any]:
        """Check Docker containers, optionally filtered by label."""
        result: dict[str, Any] = {
            "running": 0,
            "stopped": 0,
            "containers": [],
        }

        # Running containers
        fmt = "{{.ID}}\t{{.Names}}\t{{.Status}}"
        stdout, ok = self._run_cmd(["docker", "ps", "--filter", f"label={label}", "--format", fmt])
        if ok and stdout:
            for line in stdout.splitlines():
                parts = line.split("\t")
                if len(parts) >= 3:
                    result["containers"].append({"id": parts[0], "name": parts[1], "status": parts[2]})
                    result["running"] += 1

        # Stopped containers
        stdout, ok = self._run_cmd(
            ["docker", "ps", "-a", "--filter", f"label={label}", "--filter", "status=exited", "--format", fmt]
        )
        if ok and stdout:
            for line in stdout.splitlines():
                parts = line.split("\t")
                if len(parts) >= 3:
                    result["containers"].append({"id": parts[0], "name": parts[1], "status": parts[2]})
                    result["stopped"] += 1

        return result

    def check_images(self) -> dict[str, Any]:
        """Check Docker images."""
        result: dict[str, Any] = {
            "total": 0,
            "dangling": 0,
            "images": [],
        }

        stdout, ok = self._run_cmd(["docker", "images", "--format", "{{.Repository}}\t{{.Tag}}\t{{.Size}}"])
        if ok and stdout:
            for line in stdout.splitlines():
                parts = line.split("\t")
                if len(parts) >= 3:
                    result["images"].append({"repository": parts[0], "tag": parts[1], "size": parts[2]})
            result["total"] = len(result["images"])

        stdout, ok = self._run_cmd(["docker", "images", "--filter", "dangling=true", "-q"])
        if ok and stdout:
            result["dangling"] = len([ln for ln in stdout.splitlines() if ln.strip()])

        return result


class ResourceDiagnostics:
    """Diagnostics for system resources (memory, CPU, file descriptors, disk)."""

    SUBPROCESS_TIMEOUT = 5

    def _run_cmd(self, cmd: list[str]) -> tuple[str, bool]:
        """Run a command with timeout, return (stdout, success)."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.SUBPROCESS_TIMEOUT,
            )
            return result.stdout.strip(), result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            logger.warning(f"Command failed: {cmd!r}: {e}")
            return "", False

    def check_memory(self) -> dict[str, Any]:
        """Check system memory usage."""
        result: dict[str, Any] = {
            "total_gb": 0.0,
            "available_gb": 0.0,
            "used_percent": 0.0,
        }

        if sys.platform == "darwin":
            # macOS: get total via sysctl
            stdout, ok = self._run_cmd(["sysctl", "-n", "hw.memsize"])
            if ok:
                try:
                    total_bytes = int(stdout)
                    result["total_gb"] = round(total_bytes / (1024**3), 2)
                except ValueError:
                    pass

            # macOS: approximate available from vm_stat
            stdout, ok = self._run_cmd(["vm_stat"])
            if ok:
                try:
                    pages_free = 0
                    page_size = 4096  # default macOS page size
                    for line in stdout.splitlines():
                        if "page size of" in line:
                            parts = line.split()
                            for part in parts:
                                if part.isdigit():
                                    page_size = int(part)
                        if "Pages free" in line:
                            val = line.split(":")[1].strip().rstrip(".")
                            pages_free += int(val)
                        if "Pages speculative" in line:
                            val = line.split(":")[1].strip().rstrip(".")
                            pages_free += int(val)
                    available_bytes = pages_free * page_size
                    result["available_gb"] = round(available_bytes / (1024**3), 2)
                except (ValueError, IndexError):
                    pass

        elif sys.platform == "linux":
            # Linux: read /proc/meminfo
            try:
                meminfo = Path("/proc/meminfo").read_text()
                for line in meminfo.splitlines():
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        result["total_gb"] = round(kb / (1024**2), 2)
                    elif line.startswith("MemAvailable:"):
                        kb = int(line.split()[1])
                        result["available_gb"] = round(kb / (1024**2), 2)
            except (OSError, ValueError, IndexError) as e:
                logger.warning(f"Failed to read /proc/meminfo: {e}")

        # Calculate used percent
        if result["total_gb"] > 0:
            used = result["total_gb"] - result["available_gb"]
            result["used_percent"] = round((used / result["total_gb"]) * 100, 1)

        return result

    def check_cpu(self) -> dict[str, Any]:
        """Check CPU load and count."""
        try:
            load = os.getloadavg()
            load_1, load_5, load_15 = load
        except OSError:
            load_1, load_5, load_15 = 0.0, 0.0, 0.0

        return {
            "load_avg_1m": round(load_1, 2),
            "load_avg_5m": round(load_5, 2),
            "load_avg_15m": round(load_15, 2),
            "cpu_count": os.cpu_count() or 1,
        }

    def check_file_descriptors(self) -> dict[str, Any]:
        """Check file descriptor limits."""
        result: dict[str, Any] = {
            "soft_limit": 0,
            "hard_limit": 0,
        }
        try:
            import resource  # noqa: PLC0415

            soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
            result["soft_limit"] = soft
            result["hard_limit"] = hard
        except (ImportError, OSError) as e:
            logger.warning(f"Failed to check file descriptors: {e}")

        return result

    def check_disk_detailed(self) -> dict[str, Any]:
        """Check detailed disk usage for the current directory."""
        try:
            usage = shutil.disk_usage(".")
            total_gb = usage.total / (1024**3)
            used_gb = usage.used / (1024**3)
            free_gb = usage.free / (1024**3)
            used_percent = (usage.used / usage.total) * 100 if usage.total > 0 else 0.0
            return {
                "total_gb": round(total_gb, 2),
                "used_gb": round(used_gb, 2),
                "free_gb": round(free_gb, 2),
                "used_percent": round(used_percent, 1),
            }
        except OSError as e:
            logger.warning(f"Failed to check disk usage: {e}")
            return {
                "total_gb": 0.0,
                "used_gb": 0.0,
                "free_gb": 0.0,
                "used_percent": 0.0,
            }


class ConfigValidator:
    """Validate ZERG configuration files."""

    EXPECTED_KEYS = {"workers", "timeouts", "quality_gates", "mcp_servers"}

    def validate(self, config_path: Path = Path(".zerg/config.yaml")) -> list[str]:
        """Validate ZERG config file. Returns list of issues (empty = valid)."""
        issues: list[str] = []

        if not config_path.exists():
            return [f"Config file not found: {config_path}"]

        content = ""
        try:
            content = config_path.read_text()
        except OSError as e:
            return [f"Cannot read config file: {e}"]

        if not content.strip():
            return [f"Config file is empty: {config_path}"]

        try:
            import yaml  # type: ignore[import-untyped]  # noqa: PLC0415

            data = yaml.safe_load(content)
            if not isinstance(data, dict):
                issues.append("Config root must be a YAML mapping")
                return issues

            # Check for expected keys
            present_keys = set(data.keys())
            missing = self.EXPECTED_KEYS - present_keys
            for key in sorted(missing):
                issues.append(f"Missing expected key: '{key}'")

            # Basic type checks
            if "workers" in data and not isinstance(data["workers"], int | dict):
                issues.append("'workers' should be an integer or mapping")
            if "timeouts" in data and not isinstance(data["timeouts"], dict):
                issues.append("'timeouts' should be a mapping")

        except ImportError:
            # yaml not available - fallback to basic checks
            logger.info("PyYAML not installed, performing basic config validation")
            for key in sorted(self.EXPECTED_KEYS):
                if f"{key}:" not in content and f"{key} :" not in content:
                    issues.append(f"Expected key '{key}' not found (basic check)")

        except Exception as e:  # noqa: BLE001
            issues.append(f"YAML parse error: {e}")

        return issues


class EnvDiagnosticsEngine:
    """Facade that runs all environment diagnostics and collects evidence."""

    def __init__(self) -> None:
        self._python = PythonEnvDiagnostics()
        self._docker = DockerDiagnostics()
        self._resources = ResourceDiagnostics()
        self._config = ConfigValidator()

    def run_all(self, config_path: Path | None = None) -> dict[str, Any]:
        """Run all environment diagnostics and return consolidated results."""
        evidence: list[Evidence] = []

        # Python environment
        venv = self._python.check_venv()
        python_results: dict[str, Any] = {"venv": venv}

        if not venv["active"]:
            evidence.append(
                Evidence(
                    description="Virtual environment is not active",
                    source="system",
                    confidence=0.9,
                    data={"prefix": venv["path"]},
                )
            )

        # Docker
        docker_health = self._docker.check_health()
        docker_containers = self._docker.check_containers()
        docker_images = self._docker.check_images()
        docker_results: dict[str, Any] = {
            "health": docker_health,
            "containers": docker_containers,
            "images": docker_images,
        }

        if docker_health is None:
            evidence.append(
                Evidence(
                    description="Docker is not running or not installed",
                    source="system",
                    confidence=0.95,
                    data={},
                )
            )

        # Resources
        memory = self._resources.check_memory()
        cpu = self._resources.check_cpu()
        fds = self._resources.check_file_descriptors()
        disk = self._resources.check_disk_detailed()
        resource_results: dict[str, Any] = {
            "memory": memory,
            "cpu": cpu,
            "file_descriptors": fds,
            "disk": disk,
        }

        if memory["available_gb"] > 0 and memory["available_gb"] < 2.0:
            evidence.append(
                Evidence(
                    description=f"Low available memory: {memory['available_gb']}GB",
                    source="system",
                    confidence=0.85,
                    data=memory,
                )
            )

        if disk["used_percent"] > 90:
            evidence.append(
                Evidence(
                    description=f"High disk usage: {disk['used_percent']}%",
                    source="system",
                    confidence=0.9,
                    data=disk,
                )
            )

        # Config validation
        path = config_path or Path(".zerg/config.yaml")
        config_issues = self._config.validate(path)

        if config_issues:
            evidence.append(
                Evidence(
                    description=f"Config validation issues: {len(config_issues)} found",
                    source="system",
                    confidence=0.8,
                    data={"issues": config_issues},
                )
            )

        return {
            "python": python_results,
            "docker": docker_results,
            "resources": resource_results,
            "config": config_issues,
            "evidence": [e.to_dict() for e in evidence],
        }
