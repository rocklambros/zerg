"""E2E test that simulates building the plugin system via ZERG mock pipeline.

Dogfooding scenario: uses the ZERG orchestration harness to build ZERG's own
plugin system, verifying the full pipeline handles a realistic multi-level
task graph with file creation, modification, and cross-level dependencies.
"""

from __future__ import annotations

from tests.e2e.harness import E2EHarness


def _plugin_task_graph() -> list[dict]:
    """Build a task graph that mimics the plugin system feature build.

    Returns:
        List of 8 task dicts across 4 levels representing the plugin
        system implementation lifecycle.
    """
    return [
        # Level 1: Foundation (3 tasks)
        {
            "id": "P1.1",
            "title": "Create plugin registry",
            "description": "Create the core plugin registry with discovery and loading.",
            "phase": "implementation",
            "level": 1,
            "dependencies": [],
            "files": {
                "create": ["zerg/plugins.py"],
                "modify": [],
                "read": [],
            },
            "verification": {
                "command": "python -c \"import zerg.plugins\"",
                "timeout_seconds": 30,
            },
        },
        {
            "id": "P1.2",
            "title": "Create plugin configuration",
            "description": "Create configuration schema and loader for plugins.",
            "phase": "implementation",
            "level": 1,
            "dependencies": [],
            "files": {
                "create": ["zerg/plugin_config.py"],
                "modify": [],
                "read": [],
            },
            "verification": {
                "command": "python -c \"import zerg.plugin_config\"",
                "timeout_seconds": 30,
            },
        },
        {
            "id": "P1.3",
            "title": "Add plugin constants",
            "description": "Add plugin-related constants to the shared constants module.",
            "phase": "implementation",
            "level": 1,
            "dependencies": [],
            "files": {
                "create": ["zerg/plugin_constants.py"],
                "modify": [],
                "read": [],
            },
            "verification": {
                "command": "python -c \"import zerg.plugin_constants\"",
                "timeout_seconds": 30,
            },
        },
        # Level 2: Testing and integration (2 tasks)
        {
            "id": "P2.1",
            "title": "Create plugin test suite",
            "description": "Write unit tests for plugin registry and configuration.",
            "phase": "testing",
            "level": 2,
            "dependencies": ["P1.1", "P1.2"],
            "files": {
                "create": ["tests/test_plugins.py"],
                "modify": [],
                "read": ["zerg/plugins.py", "zerg/plugin_config.py"],
            },
            "verification": {
                "command": "python -m pytest tests/test_plugins.py",
                "timeout_seconds": 60,
            },
        },
        {
            "id": "P2.2",
            "title": "Integrate config with registry",
            "description": "Wire plugin configuration into the registry loader.",
            "phase": "implementation",
            "level": 2,
            "dependencies": ["P1.2", "P1.3"],
            "files": {
                "create": [],
                "modify": ["zerg/plugins.py"],
                "read": ["zerg/plugin_config.py", "zerg/plugin_constants.py"],
            },
            "verification": {
                "command": "python -c \"import zerg.plugins\"",
                "timeout_seconds": 30,
            },
        },
        # Level 3: System integration (2 tasks)
        {
            "id": "P3.1",
            "title": "Integrate into orchestrator",
            "description": "Add plugin hooks into the ZERG orchestrator lifecycle.",
            "phase": "integration",
            "level": 3,
            "dependencies": ["P2.1", "P2.2"],
            "files": {
                "create": ["zerg/plugin_hooks.py"],
                "modify": ["zerg/plugins.py"],
                "read": ["zerg/plugin_config.py"],
            },
            "verification": {
                "command": "python -c \"import zerg.plugin_hooks\"",
                "timeout_seconds": 30,
            },
        },
        {
            "id": "P3.2",
            "title": "Integrate into quality gates",
            "description": "Allow plugins to register custom quality gate checks.",
            "phase": "integration",
            "level": 3,
            "dependencies": ["P2.1", "P2.2"],
            "files": {
                "create": ["zerg/plugin_gates.py"],
                "modify": ["zerg/plugins.py"],
                "read": ["zerg/plugin_constants.py"],
            },
            "verification": {
                "command": "python -c \"import zerg.plugin_gates\"",
                "timeout_seconds": 30,
            },
        },
        # Level 4: Documentation (1 task)
        {
            "id": "P4.1",
            "title": "Create plugin documentation",
            "description": "Write developer guide for creating and registering plugins.",
            "phase": "documentation",
            "level": 4,
            "dependencies": ["P3.1", "P3.2"],
            "files": {
                "create": ["docs/plugins.md"],
                "modify": [],
                "read": [
                    "zerg/plugins.py",
                    "zerg/plugin_config.py",
                    "zerg/plugin_hooks.py",
                    "zerg/plugin_gates.py",
                ],
            },
            "verification": {
                "command": "test -f docs/plugins.md",
                "timeout_seconds": 10,
            },
        },
    ]


class TestDogfoodPlugin:
    """E2E tests that dogfood the plugin system build through the ZERG pipeline."""

    def test_plugin_system_builds_via_zerg(self, e2e_harness: E2EHarness) -> None:
        """Full plugin build completes all 8 tasks across 4 levels."""
        e2e_harness.setup_task_graph(_plugin_task_graph())
        result = e2e_harness.run(workers=5)

        assert result.success is True
        assert result.tasks_completed == 8
        assert result.levels_completed == 4

    def test_all_plugin_files_created(self, e2e_harness: E2EHarness) -> None:
        """Mock workers create the core plugin module files in the repo."""
        e2e_harness.setup_task_graph(_plugin_task_graph())
        e2e_harness.run(workers=5)

        repo = e2e_harness.repo_path
        assert (repo / "zerg/plugins.py").exists()
        assert (repo / "zerg/plugin_config.py").exists()

    def test_all_levels_merge(self, e2e_harness: E2EHarness) -> None:
        """Each of the 4 levels produces a merge commit record."""
        e2e_harness.setup_task_graph(_plugin_task_graph())
        result = e2e_harness.run(workers=5)

        assert len(result.merge_commits) == 4
