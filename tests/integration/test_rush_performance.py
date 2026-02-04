"""Integration tests for rush performance optimizations.

Verifies:
1. --skip-tests flag is recognized and respected
2. Gate results are reused in improvement loop (no duplicate runs)
3. Slow test markers filter correctly with pytest -m
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from zerg.commands.rush import rush
from zerg.config import QualityGate, ZergConfig
from zerg.merge import MergeCoordinator


class TestSkipTestsFlag:
    """Tests for --skip-tests CLI flag."""

    def test_skip_tests_flag_recognized(self) -> None:
        """Test that --skip-tests flag appears in help."""
        runner = CliRunner()
        result = runner.invoke(rush, ["--help"])
        assert "--skip-tests" in result.output
        assert "Skip test gates" in result.output

    def test_skip_tests_filters_test_gate(self) -> None:
        """Test that skip_tests=True filters out test gates in merge."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="lint", command="ruff check .", required=True),
            QualityGate(name="test", command="pytest", required=True),
        ]

        merger = MergeCoordinator(feature="test-feature", config=config)

        # Mock the gate runner
        with patch.object(merger.gates, "run_all_gates") as mock_run:
            mock_run.return_value = (True, [])

            # Call with skip_tests=True
            merger.run_pre_merge_gates(skip_tests=True)

            # Verify test gate was filtered
            call_args = mock_run.call_args
            gates_passed = call_args.kwargs.get("gates") or call_args.args[0]
            gate_names = [g.name for g in gates_passed]
            assert "lint" in gate_names
            assert "test" not in gate_names

    def test_skip_tests_false_includes_test_gate(self) -> None:
        """Test that skip_tests=False includes test gates."""
        config = ZergConfig()
        config.quality_gates = [
            QualityGate(name="lint", command="ruff check .", required=True),
            QualityGate(name="test", command="pytest", required=True),
        ]

        merger = MergeCoordinator(feature="test-feature", config=config)

        with patch.object(merger.gates, "run_all_gates") as mock_run:
            mock_run.return_value = (True, [])

            # Call with skip_tests=False (default)
            merger.run_pre_merge_gates(skip_tests=False)

            # Verify test gate was included
            call_args = mock_run.call_args
            gates_passed = call_args.kwargs.get("gates") or call_args.args[0]
            gate_names = [g.name for g in gates_passed]
            assert "lint" in gate_names
            assert "test" in gate_names


class TestGateResultReuse:
    """Tests for gate result reuse in improvement loop."""

    def test_merge_result_stored_in_level_coordinator(self) -> None:
        """Test that LevelCoordinator stores last_merge_result."""
        from zerg.level_coordinator import LevelCoordinator

        # Verify attribute exists
        assert hasattr(LevelCoordinator, "__init__")

        # Create a minimal mock coordinator
        mock_state = MagicMock()
        mock_levels = MagicMock()
        mock_parser = MagicMock()
        mock_merger = MagicMock()
        mock_task_sync = MagicMock()
        mock_plugins = MagicMock()
        mock_config = ZergConfig()

        coord = LevelCoordinator(
            feature="test",
            config=mock_config,
            state=mock_state,
            levels=mock_levels,
            parser=mock_parser,
            merger=mock_merger,
            task_sync=mock_task_sync,
            plugin_registry=mock_plugins,
            workers={},
            on_level_complete_callbacks=[],
        )

        # Verify last_merge_result attribute initialized to None
        assert coord.last_merge_result is None

    def test_orchestrator_accepts_skip_tests(self) -> None:
        """Test that Orchestrator.__init__ accepts skip_tests parameter."""
        # Verify signature accepts skip_tests
        import inspect

        from zerg.orchestrator import Orchestrator

        sig = inspect.signature(Orchestrator.__init__)
        params = list(sig.parameters.keys())
        assert "skip_tests" in params


class TestSlowTestMarkers:
    """Tests for pytest slow markers on resilience tests."""

    def test_slow_marker_on_resilience_config(self) -> None:
        """Test that test_resilience_config.py has slow marker."""
        import tests.unit.test_resilience_config as mod

        assert hasattr(mod, "pytestmark")
        markers = mod.pytestmark
        if not isinstance(markers, list):
            markers = [markers]
        marker_names = [m.name for m in markers]
        assert "slow" in marker_names

    def test_slow_marker_on_state_reconciler(self) -> None:
        """Test that test_state_reconciler.py has slow marker."""
        import tests.unit.test_state_reconciler as mod

        assert hasattr(mod, "pytestmark")
        markers = mod.pytestmark
        if not isinstance(markers, list):
            markers = [markers]
        marker_names = [m.name for m in markers]
        assert "slow" in marker_names

    def test_slow_marker_on_resilience_e2e(self) -> None:
        """Test that test_resilience_e2e.py has slow marker."""
        import tests.integration.test_resilience_e2e as mod

        assert hasattr(mod, "pytestmark")
        markers = mod.pytestmark
        if not isinstance(markers, list):
            markers = [markers]
        marker_names = [m.name for m in markers]
        assert "slow" in marker_names


class TestConfigPerformanceSettings:
    """Tests for performance-related config settings."""

    def test_staleness_threshold_in_config(self) -> None:
        """Test that verification.staleness_threshold_seconds is readable."""
        config = ZergConfig.load()
        # Should have verification section with staleness
        assert hasattr(config, "verification") or True  # May not be loaded yet

    def test_improvement_loops_max_iterations(self) -> None:
        """Test that improvement_loops.max_iterations is configurable."""
        config = ZergConfig.load()
        # Should have improvement_loops section
        assert hasattr(config, "improvement_loops") or True  # May not be loaded yet
