"""Tests for SystemDiagnostics and SystemHealthReport."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from zerg.diagnostics.system_diagnostics import (
    SystemDiagnostics,
    SystemHealthReport,
)


class TestSystemHealthReport:
    """Tests for SystemHealthReport dataclass."""

    def test_default_values(self) -> None:
        report = SystemHealthReport()
        assert report.git_clean is True
        assert report.git_branch == ""
        assert report.git_uncommitted_files == 0
        assert report.disk_free_gb == 0.0
        assert report.docker_running is None
        assert report.docker_containers is None
        assert report.port_conflicts == []
        assert report.worktree_count == 0
        assert report.orphaned_worktrees == []

    def test_to_dict(self) -> None:
        report = SystemHealthReport(
            git_clean=False,
            git_branch="main",
            git_uncommitted_files=3,
            disk_free_gb=50.1234,
            docker_running=True,
            docker_containers=2,
            port_conflicts=[9500],
            worktree_count=4,
            orphaned_worktrees=["/tmp/orphan"],
        )
        d = report.to_dict()
        assert d["git_clean"] is False
        assert d["git_branch"] == "main"
        assert d["disk_free_gb"] == 50.12  # rounded
        assert d["docker_running"] is True
        assert d["port_conflicts"] == [9500]
        assert d["orphaned_worktrees"] == ["/tmp/orphan"]


class TestSystemDiagnostics:
    """Tests for SystemDiagnostics."""

    def test_init_no_config(self) -> None:
        diag = SystemDiagnostics()
        assert diag.config is None

    def test_run_cmd_success(self) -> None:
        diag = SystemDiagnostics()
        stdout, ok = diag._run_cmd(["echo", "hello"])
        assert ok is True
        assert "hello" in stdout

    def test_run_cmd_failure(self) -> None:
        diag = SystemDiagnostics()
        stdout, ok = diag._run_cmd(["false"])
        assert ok is False

    def test_run_cmd_not_found(self) -> None:
        diag = SystemDiagnostics()
        stdout, ok = diag._run_cmd(["nonexistent_command_xyz"])
        assert ok is False
        assert stdout == ""

    @patch.object(SystemDiagnostics, "_run_cmd")
    def test_check_git_state_clean(self, mock_cmd: MagicMock) -> None:
        mock_cmd.side_effect = [
            ("", True),  # git status --porcelain (clean)
            ("main", True),  # git branch --show-current
        ]
        diag = SystemDiagnostics()
        result = diag.check_git_state()
        assert result["clean"] is True
        assert result["branch"] == "main"
        assert result["uncommitted_files"] == 0

    @patch.object(SystemDiagnostics, "_run_cmd")
    def test_check_git_state_dirty(self, mock_cmd: MagicMock) -> None:
        mock_cmd.side_effect = [
            ("M file1.py\nM file2.py\n?? new.py", True),
            ("feature/test", True),
        ]
        diag = SystemDiagnostics()
        result = diag.check_git_state()
        assert result["clean"] is False
        assert result["uncommitted_files"] == 3
        assert result["branch"] == "feature/test"

    def test_check_disk_space(self) -> None:
        diag = SystemDiagnostics()
        free_gb = diag.check_disk_space()
        assert free_gb > 0

    @patch.object(SystemDiagnostics, "_run_cmd")
    def test_check_docker_not_available(self, mock_cmd: MagicMock) -> None:
        mock_cmd.return_value = ("", False)
        diag = SystemDiagnostics()
        result = diag.check_docker()
        assert result is None

    @patch.object(SystemDiagnostics, "_run_cmd")
    def test_check_docker_running(self, mock_cmd: MagicMock) -> None:
        mock_cmd.side_effect = [
            ("Docker info output", True),  # docker info
            ("abc123\ndef456", True),  # docker ps -q
        ]
        diag = SystemDiagnostics()
        result = diag.check_docker()
        assert result is not None
        assert result["running"] is True
        assert result["containers"] == 2

    @patch.object(SystemDiagnostics, "_run_cmd")
    def test_check_docker_no_containers(self, mock_cmd: MagicMock) -> None:
        mock_cmd.side_effect = [
            ("Docker info", True),
            ("", True),
        ]
        diag = SystemDiagnostics()
        result = diag.check_docker()
        assert result["containers"] == 0

    def test_check_ports_no_conflicts(self) -> None:
        diag = SystemDiagnostics()
        # Use a high port range unlikely to be in use
        conflicts = diag.check_ports(60000, 60002)
        # Can't guarantee no conflicts, just verify it runs
        assert isinstance(conflicts, list)

    @patch.object(SystemDiagnostics, "_run_cmd")
    def test_check_worktrees_none(self, mock_cmd: MagicMock) -> None:
        mock_cmd.return_value = ("", False)
        diag = SystemDiagnostics()
        result = diag.check_worktrees()
        assert result["count"] == 0
        assert result["orphaned"] == []

    @patch.object(SystemDiagnostics, "_run_cmd")
    def test_check_worktrees_with_entries(self, mock_cmd: MagicMock) -> None:
        mock_cmd.return_value = (
            "worktree /Users/test/project\nHEAD abc123\nbranch refs/heads/main\n\n"
            "worktree /tmp/nonexistent\nHEAD def456\n",
            True,
        )
        diag = SystemDiagnostics()
        result = diag.check_worktrees()
        assert result["count"] == 2
        # /tmp/nonexistent should be orphaned
        assert "/tmp/nonexistent" in result["orphaned"]

    @patch.object(SystemDiagnostics, "_run_cmd")
    def test_run_all(self, mock_cmd: MagicMock) -> None:
        mock_cmd.side_effect = [
            ("", True),  # git status
            ("main", True),  # git branch
            ("Docker info", True),  # docker info
            ("", True),  # docker ps
            ("worktree /project\n", True),  # git worktree list
        ]
        diag = SystemDiagnostics()
        with (
            patch.object(diag, "check_disk_space", return_value=100.0),
            patch.object(diag, "check_ports", return_value=[]),
        ):
            report = diag.run_all()

        assert isinstance(report, SystemHealthReport)
        assert report.git_clean is True
        assert report.git_branch == "main"
        assert report.disk_free_gb == 100.0

    @patch.object(SystemDiagnostics, "_run_cmd")
    def test_run_all_with_config(self, mock_cmd: MagicMock) -> None:
        mock_config = MagicMock()
        mock_config.ports.range_start = 8000
        mock_config.ports.range_end = 8010

        mock_cmd.side_effect = [
            ("", True),  # git status
            ("main", True),  # git branch
            ("", False),  # docker info (not available)
            ("", True),  # git worktree list
        ]
        diag = SystemDiagnostics(config=mock_config)
        with (
            patch.object(diag, "check_disk_space", return_value=50.0),
            patch.object(diag, "check_ports", return_value=[]) as mock_ports,
        ):
            report = diag.run_all()
            mock_ports.assert_called_once_with(8000, 8010)

        assert report.docker_running is None
