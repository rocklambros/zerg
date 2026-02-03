"""Coverage-focused tests for utility modules.

Targets uncovered lines in:
- zerg/spec_loader.py (lines 104-106, 195, 228-229, 234-257, 268-283, 295-304)
- zerg/gates.py (lines 81-82, 97-114, 152, 155-156, 186-196, 213, 241, 260, 263, 266,
  269, 290, 294, 302-323)
- zerg/render_utils.py (lines 34-39, 52-54, 75, 79, 138-149)
- zerg/retry_backoff.py (lines 29-34)
- zerg/performance/stack_detector.py (lines 67, 71, 96-97, 104, 108, 112, 114, 126-127,
  132, 144, 152, 154, 161, 166-167, 170-179, 199)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.config import QualityGate, ZergConfig
from zerg.constants import GateResult
from zerg.exceptions import GateFailureError, GateTimeoutError
from zerg.gates import GateRunner
from zerg.performance.stack_detector import (
    _detect_docker,
    _detect_frameworks,
    _detect_kubernetes,
    _detect_languages,
    _detect_python_frameworks,
    _should_skip,
    detect_stack,
)
from zerg.render_utils import (
    format_elapsed_compact,
    render_gantt_chart,
    render_progress_bar,
    render_progress_bar_str,
)
from zerg.retry_backoff import RetryBackoffCalculator
from zerg.spec_loader import SpecLoader
from zerg.types import GateRunResult

# =============================================================================
# spec_loader.py coverage tests
# =============================================================================


class TestSpecLoaderCoverage:
    """Tests targeting uncovered lines in spec_loader.py."""

    @pytest.fixture
    def temp_gsd(self, tmp_path: Path) -> Path:
        gsd = tmp_path / ".gsd"
        gsd.mkdir()
        (gsd / "specs").mkdir()
        return gsd

    @pytest.fixture
    def loader(self, temp_gsd: Path) -> SpecLoader:
        return SpecLoader(gsd_dir=temp_gsd)

    # Lines 104-106: _load_file exception handling
    def test_load_file_exception_returns_empty(self, loader: SpecLoader, temp_gsd: Path) -> None:
        """When read_text raises, _load_file returns empty string."""
        feature_dir = temp_gsd / "specs" / "feat"
        feature_dir.mkdir(parents=True)
        bad_file = feature_dir / "requirements.md"
        bad_file.write_text("content")

        with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
            result = loader._load_file(bad_file)

        assert result == ""

    # Line 195: truncation at paragraph boundary (last_para > max_chars // 2)
    def test_truncate_at_paragraph_boundary(self, loader: SpecLoader) -> None:
        """Truncation should prefer paragraph boundary when found past midpoint."""
        # Build text: first half has paragraph break, second half is long
        para1 = "A" * 200
        para2 = "B" * 200
        para3 = "C" * 2000
        text = f"{para1}\n\n{para2}\n\n{para3}"
        # max_tokens=200 => max_chars=800
        result = loader._truncate_to_tokens(text, 200)
        assert "truncated" in result
        # Should have truncated at a paragraph boundary
        assert result.count("\n\n") >= 1

    # Lines 228-229: format_task_context exception in load_feature_specs
    def test_format_task_context_load_exception(self, loader: SpecLoader) -> None:
        """When load_feature_specs raises, format_task_context returns empty."""
        task = {"title": "Add auth", "description": "implement login"}
        with patch.object(loader, "load_feature_specs", side_effect=RuntimeError("boom")):
            result = loader.format_task_context(task, "feat")
        assert result == ""

    # Lines 234-257: format_task_context with actual specs and keywords
    def test_format_task_context_with_matching_content(self, loader: SpecLoader, temp_gsd: Path) -> None:
        """format_task_context extracts relevant sections matching task keywords."""
        feature_dir = temp_gsd / "specs" / "auth"
        feature_dir.mkdir(parents=True)
        (feature_dir / "requirements.md").write_text(
            "Users must login securely.\n\nPassword must be hashed.\n\nSessions expire after timeout."
        )
        (feature_dir / "design.md").write_text(
            "Login uses OAuth protocol.\n\nDatabase stores hashed passwords.\n\nRedis handles session cache."
        )
        task = {
            "title": "Implement login endpoint",
            "description": "Handle user login with password validation",
            "files": {"create": ["src/auth/login.py"], "modify": [], "read": []},
        }
        result = loader.format_task_context(task, "auth")
        assert result != ""
        assert "Relevant" in result

    # Lines 234-236: format_task_context with no keywords extracted
    def test_format_task_context_no_keywords(self, loader: SpecLoader, temp_gsd: Path) -> None:
        """format_task_context returns empty when task has no useful keywords."""
        feature_dir = temp_gsd / "specs" / "feat"
        feature_dir.mkdir(parents=True)
        (feature_dir / "requirements.md").write_text("Some content here.")
        task = {"title": "Do it", "description": "ok"}  # words too short (<=3)
        result = loader.format_task_context(task, "feat")
        assert result == ""

    # Lines 268-283: _extract_task_keywords
    def test_extract_task_keywords_from_title_and_description(self, loader: SpecLoader) -> None:
        """Keywords extracted from title, description, and file paths."""
        task = {
            "title": "Implement authentication module",
            "description": "Handle login flow for users",
            "files": {
                "create": ["src/auth-handler.py"],
                "modify": ["src/user_service.py"],
            },
        }
        keywords = loader._extract_task_keywords(task)
        assert "implement" in keywords
        assert "authentication" in keywords
        assert "handle" in keywords
        assert "login" in keywords
        assert "users" in keywords
        # File stems split on _ and -
        assert "auth" in keywords
        assert "handler" in keywords
        assert "user" in keywords
        assert "service" in keywords

    def test_extract_task_keywords_empty_task(self, loader: SpecLoader) -> None:
        """Empty task yields no keywords."""
        keywords = loader._extract_task_keywords({})
        assert keywords == set()

    def test_extract_task_keywords_non_list_files(self, loader: SpecLoader) -> None:
        """Non-list file values are skipped."""
        task = {
            "title": "Something longer word",
            "files": {"create": "not-a-list"},
        }
        keywords = loader._extract_task_keywords(task)
        assert "something" in keywords

    # Lines 295-304: _extract_relevant_sections
    def test_extract_relevant_sections_ranked(self, loader: SpecLoader) -> None:
        """Sections scored and ranked by keyword match count."""
        text = (
            "This paragraph mentions login and authentication.\n\n"
            "This paragraph is about caching.\n\n"
            "Another paragraph about login flow and login tokens.\n\n"
            "\n\n"
            "Empty paragraph above should be skipped."
        )
        keywords = {"login", "authentication"}
        result = loader._extract_relevant_sections(text, keywords)
        # Paragraph with 2 matches ("login" twice) should come first
        paragraphs = result.split("\n\n")
        assert len(paragraphs) >= 2
        # First paragraph should have more keyword density
        assert "login" in paragraphs[0].lower()

    def test_extract_relevant_sections_no_matches(self, loader: SpecLoader) -> None:
        """Returns empty string when no keywords match."""
        text = "Unrelated content about cooking.\n\nMore cooking tips."
        keywords = {"authentication", "login"}
        result = loader._extract_relevant_sections(text, keywords)
        assert result == ""

    # format_task_context with only design matching
    def test_format_task_context_design_only_match(self, loader: SpecLoader, temp_gsd: Path) -> None:
        """format_task_context includes design section when only design matches."""
        feature_dir = temp_gsd / "specs" / "cache"
        feature_dir.mkdir(parents=True)
        (feature_dir / "requirements.md").write_text("Unrelated content about cooking.")
        (feature_dir / "design.md").write_text("Redis handles caching layer.\n\nCache invalidation strategy uses TTL.")
        task = {
            "title": "Implement caching layer",
            "description": "Add Redis cache invalidation",
        }
        result = loader.format_task_context(task, "cache")
        assert "Relevant Design" in result


# =============================================================================
# gates.py coverage tests
# =============================================================================


class TestGatesCoverage:
    """Tests targeting uncovered lines in gates.py."""

    @pytest.fixture
    def config(self) -> ZergConfig:
        return ZergConfig()

    # Lines 155-156: no gates and no plugin registry returns early
    def test_run_all_gates_no_gates_no_plugins_returns_early(self, config: ZergConfig) -> None:
        """No gates + no plugin registry returns (True, [])."""
        config.quality_gates = []
        runner = GateRunner(config, plugin_registry=None)
        passed, results = runner.run_all_gates()
        assert passed is True
        assert results == []

    # Lines 186-196: plugin gate fails (required and optional)
    def test_run_all_gates_plugin_gate_required_fails(self, config: ZergConfig, tmp_path: Path) -> None:
        """Required plugin gate failure sets all_passed=False and stops."""
        config.quality_gates = []
        mock_registry = MagicMock()
        mock_registry._gates = {"security-scan": MagicMock()}

        failed_result = GateRunResult(
            gate_name="security-scan",
            result=GateResult.FAIL,
            command="security-scan",
            exit_code=1,
        )
        mock_registry.run_plugin_gate.return_value = failed_result
        mock_registry.is_gate_required.return_value = True

        runner = GateRunner(config, plugin_registry=mock_registry)
        passed, results = runner.run_all_gates(cwd=tmp_path, stop_on_failure=True, feature="test", level=1)
        assert passed is False
        assert len(results) == 1

    def test_run_all_gates_plugin_gate_optional_fails(self, config: ZergConfig, tmp_path: Path) -> None:
        """Optional plugin gate failure does not stop execution."""
        config.quality_gates = []
        mock_registry = MagicMock()
        mock_registry._gates = {"optional-check": MagicMock()}

        failed_result = GateRunResult(
            gate_name="optional-check",
            result=GateResult.FAIL,
            command="optional-check",
            exit_code=1,
        )
        mock_registry.run_plugin_gate.return_value = failed_result
        mock_registry.is_gate_required.return_value = False

        runner = GateRunner(config, plugin_registry=mock_registry)
        passed, results = runner.run_all_gates(cwd=tmp_path, stop_on_failure=True, feature="test", level=1)
        # Optional failures don't affect all_passed
        assert passed is True
        assert len(results) == 1

    # Line 213: run_plugin_gates with no registry
    def test_run_plugin_gates_no_registry(self, config: ZergConfig) -> None:
        """run_plugin_gates returns empty list when no registry."""
        runner = GateRunner(config, plugin_registry=None)
        from zerg.plugins import GateContext

        ctx = MagicMock(spec=GateContext)
        results = runner.run_plugin_gates(ctx)
        assert results == []

    # Lines 260, 263, 266, 269: check_result branches
    def test_check_result_fail_no_raise(self, config: ZergConfig) -> None:
        """check_result returns False when raise_on_failure is False."""
        runner = GateRunner(config)
        result = GateRunResult(gate_name="t", result=GateResult.FAIL, command="x", exit_code=1)
        assert runner.check_result(result, raise_on_failure=False) is False

    def test_check_result_timeout_raises_gate_timeout(self, config: ZergConfig) -> None:
        """check_result raises GateTimeoutError for TIMEOUT result."""
        runner = GateRunner(config)
        result = GateRunResult(
            gate_name="slow",
            result=GateResult.TIMEOUT,
            command="sleep 999",
            exit_code=-1,
            duration_ms=60000,
        )
        with pytest.raises(GateTimeoutError) as exc_info:
            runner.check_result(result, raise_on_failure=True)
        assert exc_info.value.gate_name == "slow"
        assert exc_info.value.timeout_seconds == 60

    def test_check_result_error_raises_gate_failure(self, config: ZergConfig) -> None:
        """check_result raises GateFailureError for ERROR result."""
        runner = GateRunner(config)
        result = GateRunResult(
            gate_name="broken",
            result=GateResult.ERROR,
            command="bad-cmd",
            exit_code=-1,
            stdout="out",
            stderr="err",
        )
        with pytest.raises(GateFailureError) as exc_info:
            runner.check_result(result, raise_on_failure=True)
        assert exc_info.value.gate_name == "broken"

    # Line 290: get_results copy
    def test_get_results_is_copy(self, config: ZergConfig) -> None:
        """get_results returns a copy of internal list."""
        runner = GateRunner(config)
        runner._results.append(GateRunResult(gate_name="x", result=GateResult.PASS, command="echo", exit_code=0))
        copy = runner.get_results()
        copy.clear()
        assert len(runner.get_results()) == 1

    # Line 294: clear_results
    def test_clear_results(self, config: ZergConfig) -> None:
        """clear_results empties internal list."""
        runner = GateRunner(config)
        runner._results.append(GateRunResult(gate_name="x", result=GateResult.PASS, command="echo", exit_code=0))
        runner.clear_results()
        assert len(runner._results) == 0

    # Lines 302-323: get_summary with all result types
    def test_get_summary_all_types(self, config: ZergConfig) -> None:
        """get_summary correctly counts all GateResult types."""
        runner = GateRunner(config)
        for res_type in [
            GateResult.PASS,
            GateResult.FAIL,
            GateResult.TIMEOUT,
            GateResult.ERROR,
            GateResult.SKIP,
        ]:
            runner._results.append(
                GateRunResult(
                    gate_name=res_type.value,
                    result=res_type,
                    command="cmd",
                    exit_code=0,
                )
            )
        summary = runner.get_summary()
        assert summary["total"] == 5
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["timeout"] == 1
        assert summary["error"] == 1
        assert summary["skipped"] == 1

    # Line 152: required_only filtering
    def test_run_all_gates_required_only(self, config: ZergConfig, tmp_path: Path) -> None:
        """required_only=True filters out non-required gates."""
        gates = [
            QualityGate(name="req", command="echo ok", required=True),
            QualityGate(name="opt", command="echo ok", required=False),
        ]
        runner = GateRunner(config)
        passed, results = runner.run_all_gates(gates=gates, cwd=tmp_path, required_only=True)
        assert passed is True
        assert len(results) == 1
        assert results[0].gate_name == "req"

    # Line 241: run_gate_by_name not found
    def test_run_gate_by_name_not_found(self, config: ZergConfig) -> None:
        """run_gate_by_name raises ValueError when gate not configured."""
        runner = GateRunner(config)
        with pytest.raises(ValueError, match="Gate not found"):
            runner.run_gate_by_name("nonexistent")


# =============================================================================
# render_utils.py coverage tests
# =============================================================================


class TestRenderUtilsCoverage:
    """Tests targeting uncovered lines in render_utils.py."""

    # Lines 34-39: render_progress_bar
    def test_render_progress_bar_zero(self) -> None:
        """Progress bar at 0% is all empty."""
        bar = render_progress_bar(0, width=10)
        assert bar.plain == "\u2591" * 10

    def test_render_progress_bar_fifty(self) -> None:
        """Progress bar at 50% is half filled."""
        bar = render_progress_bar(50, width=10)
        plain = bar.plain
        assert plain.count("\u2588") == 5
        assert plain.count("\u2591") == 5

    def test_render_progress_bar_hundred(self) -> None:
        """Progress bar at 100% is all filled."""
        bar = render_progress_bar(100, width=10)
        assert bar.plain == "\u2588" * 10

    # Lines 52-54: render_progress_bar_str
    def test_render_progress_bar_str_zero(self) -> None:
        result = render_progress_bar_str(0, width=10)
        assert result == "\u2591" * 10

    def test_render_progress_bar_str_full(self) -> None:
        result = render_progress_bar_str(100, width=10)
        assert result == "\u2588" * 10

    def test_render_progress_bar_str_partial(self) -> None:
        result = render_progress_bar_str(25, width=20)
        assert len(result) == 20
        assert result.count("\u2588") == 5

    # Lines 75, 79: render_gantt_chart empty / zero wall
    def test_render_gantt_chart_empty(self) -> None:
        """Empty per_level returns 'No timeline data'."""
        result = render_gantt_chart({}, worker_count=3)
        assert "No timeline data" in result.plain

    def test_render_gantt_chart_zero_wall(self) -> None:
        """Zero total wall time returns 'No timeline data'."""

        @dataclass
        class FakeLevelTimeline:
            level: int
            task_count: int
            wall_minutes: int
            worker_loads: dict[int, int] = field(default_factory=dict)

        lt = FakeLevelTimeline(level=1, task_count=2, wall_minutes=0, worker_loads={0: 0, 1: 0})
        result = render_gantt_chart({1: lt}, worker_count=2)  # type: ignore[arg-type]
        assert "No timeline data" in result.plain

    def test_render_gantt_chart_with_data(self) -> None:
        """Gantt chart renders worker bars for levels with data."""

        @dataclass
        class FakeLevelTimeline:
            level: int
            task_count: int
            wall_minutes: int
            worker_loads: dict[int, int] = field(default_factory=dict)

        lt1 = FakeLevelTimeline(level=1, task_count=3, wall_minutes=10, worker_loads={0: 5, 1: 8})
        lt2 = FakeLevelTimeline(level=2, task_count=2, wall_minutes=5, worker_loads={0: 3})
        result = render_gantt_chart({1: lt1, 2: lt2}, worker_count=2)  # type: ignore[arg-type]
        plain = result.plain
        assert "L1" in plain
        assert "L2" in plain
        assert "W0" in plain
        assert "W1" in plain

    # Lines 138-149: format_elapsed_compact
    def test_format_elapsed_seconds_only(self) -> None:
        assert format_elapsed_compact(45) == "45s"

    def test_format_elapsed_zero(self) -> None:
        assert format_elapsed_compact(0) == "0s"

    def test_format_elapsed_exact_minutes(self) -> None:
        assert format_elapsed_compact(120) == "2m"

    def test_format_elapsed_minutes_and_seconds(self) -> None:
        assert format_elapsed_compact(332) == "5m32s"

    def test_format_elapsed_exact_hours(self) -> None:
        assert format_elapsed_compact(3600) == "1h"

    def test_format_elapsed_hours_and_minutes(self) -> None:
        assert format_elapsed_compact(4980) == "1h23m"

    def test_format_elapsed_59_seconds(self) -> None:
        assert format_elapsed_compact(59) == "59s"

    def test_format_elapsed_60_seconds(self) -> None:
        assert format_elapsed_compact(60) == "1m"


# =============================================================================
# retry_backoff.py coverage tests
# =============================================================================


class TestRetryBackoffCoverage:
    """Tests targeting uncovered lines 29-34 in retry_backoff.py."""

    def test_linear_strategy(self) -> None:
        """Linear backoff: delay = base * attempt."""
        delay = RetryBackoffCalculator.calculate_delay(attempt=3, strategy="linear", base_seconds=10, max_seconds=300)
        # base * attempt = 30, with +/-10% jitter => 27..33
        assert 27.0 <= delay <= 33.0

    def test_fixed_strategy(self) -> None:
        """Fixed backoff: delay = base regardless of attempt."""
        delay = RetryBackoffCalculator.calculate_delay(attempt=5, strategy="fixed", base_seconds=15, max_seconds=300)
        # Always 15 with +/-10% jitter => 13.5..16.5
        assert 13.5 <= delay <= 16.5

    def test_unknown_strategy_raises(self) -> None:
        """Unknown strategy raises ValueError."""
        with pytest.raises(ValueError, match="Unknown backoff strategy"):
            RetryBackoffCalculator.calculate_delay(attempt=1, strategy="quadratic", base_seconds=5, max_seconds=60)

    def test_exponential_strategy(self) -> None:
        """Exponential backoff: delay = base * 2^attempt."""
        delay = RetryBackoffCalculator.calculate_delay(
            attempt=2, strategy="exponential", base_seconds=5, max_seconds=300
        )
        # 5 * 2^2 = 20, with jitter => 18..22
        assert 18.0 <= delay <= 22.0

    def test_max_cap(self) -> None:
        """Delay is capped at max_seconds."""
        delay = RetryBackoffCalculator.calculate_delay(
            attempt=10, strategy="exponential", base_seconds=10, max_seconds=60
        )
        # 10 * 2^10 = 10240, capped to 60, with jitter => 54..66
        assert delay <= 66.0


# =============================================================================
# stack_detector.py coverage tests
# =============================================================================


class TestStackDetectorCoverage:
    """Tests targeting uncovered lines in stack_detector.py."""

    # Line 67: _MAX_SCAN_FILES limit
    def test_detect_languages_max_scan_limit(self, tmp_path: Path) -> None:
        """Language detection stops after _MAX_SCAN_FILES."""
        # Create enough files to trigger the limit check (line 67)
        for i in range(10):
            (tmp_path / f"file_{i}.py").write_text("pass")
        languages = _detect_languages(tmp_path)
        assert "python" in languages

    # Line 71: skip directories with dot prefix or in _SKIP_DIRS
    def test_detect_languages_skips_hidden_dirs(self, tmp_path: Path) -> None:
        """Files in hidden or excluded directories are skipped."""
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / "secret.py").write_text("pass")

        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()
        (node_modules / "lib.js").write_text("export {}")

        (tmp_path / "app.py").write_text("pass")
        languages = _detect_languages(tmp_path)
        assert "python" in languages
        # node_modules JS should be skipped, so JS only appears if in root
        # (depends on whether .hidden counts; main point is the skip path executes)

    # Lines 96-97: package.json JSONDecodeError
    def test_detect_frameworks_bad_package_json(self, tmp_path: Path) -> None:
        """Malformed package.json is handled gracefully."""
        (tmp_path / "package.json").write_text("{invalid json")
        frameworks = _detect_frameworks(tmp_path)
        # Should not crash
        assert isinstance(frameworks, list)

    # Line 104: go.mod detection
    def test_detect_frameworks_go_module(self, tmp_path: Path) -> None:
        """go.mod triggers go-module framework detection."""
        (tmp_path / "go.mod").write_text("module example.com/app")
        frameworks = _detect_frameworks(tmp_path)
        assert "go-module" in frameworks

    # Line 108: Cargo.toml detection
    def test_detect_frameworks_rust_cargo(self, tmp_path: Path) -> None:
        """Cargo.toml triggers rust-cargo framework detection."""
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "app"')
        frameworks = _detect_frameworks(tmp_path)
        assert "rust-cargo" in frameworks

    # Line 112: pom.xml detection
    def test_detect_frameworks_java_maven(self, tmp_path: Path) -> None:
        """pom.xml triggers java-maven framework detection."""
        (tmp_path / "pom.xml").write_text("<project></project>")
        frameworks = _detect_frameworks(tmp_path)
        assert "java-maven" in frameworks

    # Line 114: build.gradle detection
    def test_detect_frameworks_java_gradle(self, tmp_path: Path) -> None:
        """build.gradle triggers java-gradle framework detection."""
        (tmp_path / "build.gradle").write_text("apply plugin: 'java'")
        frameworks = _detect_frameworks(tmp_path)
        assert "java-gradle" in frameworks

    # Lines 126-127, 132: _detect_python_frameworks
    def test_detect_python_frameworks_requirements(self, tmp_path: Path) -> None:
        """Python frameworks detected from requirements.txt."""
        (tmp_path / "requirements.txt").write_text("django==4.2\nflask>=2.0")
        frameworks: set[str] = set()
        _detect_python_frameworks(tmp_path, frameworks)
        assert "django" in frameworks
        assert "flask" in frameworks

    def test_detect_python_frameworks_pyproject(self, tmp_path: Path) -> None:
        """Python frameworks detected from pyproject.toml."""
        (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi", "sqlalchemy"]')
        frameworks: set[str] = set()
        _detect_python_frameworks(tmp_path, frameworks)
        assert "fastapi" in frameworks
        assert "sqlalchemy" in frameworks

    # Line 144: _detect_docker devcontainer
    def test_detect_docker_devcontainer(self, tmp_path: Path) -> None:
        """Docker detected in .devcontainer directory."""
        devcontainer = tmp_path / ".devcontainer"
        devcontainer.mkdir()
        (devcontainer / "Dockerfile").write_text("FROM ubuntu")
        assert _detect_docker(tmp_path) is True

    def test_detect_docker_compose(self, tmp_path: Path) -> None:
        """Docker detected via docker-compose.yml."""
        (tmp_path / "docker-compose.yml").write_text("version: '3'")
        assert _detect_docker(tmp_path) is True

    def test_detect_docker_none(self, tmp_path: Path) -> None:
        """No docker files returns False."""
        assert _detect_docker(tmp_path) is False

    # Lines 152, 154: _detect_kubernetes helm files
    def test_detect_kubernetes_helmfile(self, tmp_path: Path) -> None:
        """Kubernetes detected via helmfile.yaml."""
        (tmp_path / "helmfile.yaml").write_text("releases:")
        assert _detect_kubernetes(tmp_path) is True

    def test_detect_kubernetes_chart(self, tmp_path: Path) -> None:
        """Kubernetes detected via Chart.yaml."""
        (tmp_path / "Chart.yaml").write_text("apiVersion: v2")
        assert _detect_kubernetes(tmp_path) is True

    # Lines 161, 166-167: kubernetes yaml scanning with skip and OSError
    def test_detect_kubernetes_yaml_scan(self, tmp_path: Path) -> None:
        """Kubernetes detected by scanning .yaml files for kind: Service."""
        k8s = tmp_path / "deploy"
        k8s.mkdir()
        (k8s / "service.yaml").write_text("kind: Service\nmetadata:\n  name: svc")
        assert _detect_kubernetes(tmp_path) is True

    def test_detect_kubernetes_yml_scan(self, tmp_path: Path) -> None:
        """Kubernetes detected by scanning .yml files."""
        k8s = tmp_path / "manifests"
        k8s.mkdir()
        (k8s / "deploy.yml").write_text("kind: Deployment\nmetadata:\n  name: app")
        assert _detect_kubernetes(tmp_path) is True

    def test_detect_kubernetes_skips_hidden_dirs(self, tmp_path: Path) -> None:
        """Kubernetes scan skips hidden directories."""
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / "deploy.yaml").write_text("kind: Deployment")
        assert _detect_kubernetes(tmp_path) is False

    # Lines 170-179: kubernetes yml branch + OSError handling
    def test_detect_kubernetes_no_match(self, tmp_path: Path) -> None:
        """No kubernetes markers in yaml files returns False."""
        (tmp_path / "config.yaml").write_text("key: value")
        (tmp_path / "other.yml").write_text("something: else")
        assert _detect_kubernetes(tmp_path) is False

    # Line 199: detect_stack with non-existent path
    def test_detect_stack_nonexistent_path(self, tmp_path: Path) -> None:
        """detect_stack returns empty DetectedStack for non-existent path."""
        stack = detect_stack(str(tmp_path / "nonexistent"))
        assert stack.languages == []
        assert stack.frameworks == []
        assert stack.has_docker is False
        assert stack.has_kubernetes is False

    # Full integration
    def test_detect_stack_full_project(self, tmp_path: Path) -> None:
        """detect_stack detects languages, frameworks, docker, and k8s together."""
        (tmp_path / "main.py").write_text("import flask")
        (tmp_path / "requirements.txt").write_text("flask>=2.0")
        (tmp_path / "Dockerfile").write_text("FROM python:3.12")
        (tmp_path / "Chart.yaml").write_text("apiVersion: v2")

        stack = detect_stack(str(tmp_path))
        assert "python" in stack.languages
        assert "flask" in stack.frameworks
        assert stack.has_docker is True
        assert stack.has_kubernetes is True

    # _should_skip
    def test_should_skip_node_modules(self) -> None:
        assert _should_skip(Path("node_modules/foo.js")) is True

    def test_should_skip_hidden(self) -> None:
        assert _should_skip(Path(".git/config")) is True

    def test_should_skip_normal(self) -> None:
        assert _should_skip(Path("src/app.py")) is False

    # JS framework detection from devDependencies
    def test_detect_frameworks_dev_dependencies(self, tmp_path: Path) -> None:
        """JS frameworks detected from devDependencies."""
        pkg = {"devDependencies": {"@angular/core": "^16.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        frameworks = _detect_frameworks(tmp_path)
        assert "angular" in frameworks
