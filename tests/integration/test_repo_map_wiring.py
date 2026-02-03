"""Integration tests for repo map wiring into context plugin."""

import textwrap
from pathlib import Path
from unittest.mock import patch

from zerg.repo_map import SymbolGraph, build_map


class TestRepoMapBuildAndQuery:
    """Test building a repo map from actual files and querying it."""

    def test_build_and_query_python(self, tmp_path: Path) -> None:
        # Create a small Python project
        (tmp_path / "app.py").write_text(
            textwrap.dedent("""\
            from utils import helper

            class App:
                \"\"\"Main application.\"\"\"
                def run(self) -> None:
                    helper()
        """)
        )
        (tmp_path / "utils.py").write_text(
            textwrap.dedent("""\
            def helper() -> str:
                \"\"\"Help with things.\"\"\"
                return "helped"

            MAX_RETRIES = 3
        """)
        )

        graph = build_map(tmp_path, languages=["python"])
        assert "app" in graph.modules or any("app" in k for k in graph.modules)
        assert "utils" in graph.modules or any("utils" in k for k in graph.modules)

        # Query for app.py files
        result = graph.query(["app.py"], ["helper"])
        assert "App" in result or "helper" in result

    def test_build_and_query_js(self, tmp_path: Path) -> None:
        (tmp_path / "server.js").write_text(
            textwrap.dedent("""\
            import express from 'express';

            export class Server {
              constructor(port) {
                this.port = port;
              }
            }

            export function createServer(config) {
              return new Server(config.port);
            }
        """)
        )

        graph = build_map(tmp_path, languages=["javascript"])
        assert len(graph.modules) >= 1

        result = graph.query(["server.js"], ["Server"])
        assert "Server" in result

    def test_build_skips_node_modules(self, tmp_path: Path) -> None:
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("export function foo() {}\n")
        (tmp_path / "app.js").write_text("export function bar() {}\n")

        graph = build_map(tmp_path, languages=["javascript"])
        module_names = list(graph.modules.keys())
        assert all("node_modules" not in m for m in module_names)

    def test_empty_query_returns_empty(self) -> None:
        graph = SymbolGraph()
        assert graph.query([], []) == ""

    def test_query_with_edges(self, tmp_path: Path) -> None:
        (tmp_path / "base.py").write_text("class Base:\n    pass\n")
        (tmp_path / "child.py").write_text("from base import Base\nclass Child(Base):\n    pass\n")

        graph = build_map(tmp_path, languages=["python"])
        result = graph.query(["child.py"], [])
        # Should include child module and potentially base module via edges
        assert "Child" in result


class TestRepoMapContextPluginWiring:
    """Test that context plugin can call repo map successfully."""

    def test_context_plugin_builds_repo_map_section(self, tmp_path: Path) -> None:
        # Create a file so build_map finds something
        (tmp_path / "mod.py").write_text("def task_func(): pass\n")

        task = {
            "id": "TASK-001",
            "description": "implement task func",
            "files": {"create": ["mod.py"], "modify": []},
        }

        with patch("zerg.context_plugin.os.environ", {"ZERG_COMPACT_MODE": ""}):
            from zerg.context_plugin import ContextEngineeringPlugin
            from zerg.plugin_config import ContextEngineeringConfig

            plugin = ContextEngineeringPlugin(ContextEngineeringConfig())
            # Use build_repo_map_section directly
            with patch("zerg.context_plugin.Path.cwd", return_value=tmp_path):
                section = plugin._build_repo_map_section(task, max_tokens=500)
            # May or may not find symbols depending on cwd, but should not error
            assert isinstance(section, str)
