"""Tests for ZERG security rules module."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from zerg.security_rules import (
    FRAMEWORK_DETECTION,
    INFRASTRUCTURE_DETECTION,
    LANGUAGE_DETECTION,
    RULE_PATHS,
    ProjectStack,
    _detect_go_frameworks,
    _detect_js_frameworks,
    _detect_python_frameworks,
    _detect_rust_frameworks,
    detect_project_stack,
    fetch_rules,
    filter_rules_for_files,
    generate_claude_md_section,
    get_required_rules,
    integrate_security_rules,
    summarize_rules,
)


class TestProjectStack:
    def test_creation_and_to_dict(self) -> None:
        stack = ProjectStack(
            languages={"python", "javascript"},
            frameworks={"fastapi", "react"},
            databases={"postgresql"},
            infrastructure={"docker"},
            ai_ml=True,
            rag=False,
        )
        data = stack.to_dict()
        assert data["languages"] == ["javascript", "python"]
        assert data["ai_ml"] is True
        empty = ProjectStack()
        assert len(empty.languages) == 0
        assert empty.ai_ml is False


class TestLanguageDetection:
    @pytest.mark.parametrize(
        "filename,content,expected_lang",
        [
            ("app.py", "print('hello')", "python"),
            ("pyproject.toml", "[project]\nname = 'test'", "python"),
            ("app.js", "console.log('hello')", "javascript"),
            ("tsconfig.json", "{}", "typescript"),
            ("go.mod", "module test", "go"),
            ("Cargo.toml", "[package]\nname = 'test'", "rust"),
        ],
        ids=["py_file", "pyproject", "js", "ts", "go", "rust"],
    )
    def test_detect_language(self, tmp_path: Path, filename: str, content: str, expected_lang: str) -> None:
        (tmp_path / filename).write_text(content)
        stack = detect_project_stack(tmp_path)
        assert expected_lang in stack.languages


class TestFrameworkDetection:
    @pytest.mark.parametrize(
        "detector,filename,content,expected_framework",
        [
            (_detect_python_frameworks, "requirements.txt", "fastapi>=0.100.0", "fastapi"),
            (_detect_python_frameworks, "requirements.txt", "django==4.0", "django"),
            (_detect_python_frameworks, "requirements.txt", "langchain>=0.1.0", "langchain"),
        ],
        ids=["fastapi", "django", "langchain"],
    )
    def test_python_frameworks(
        self, tmp_path: Path, detector, filename: str, content: str, expected_framework: str
    ) -> None:
        (tmp_path / filename).write_text(content)
        stack = ProjectStack()
        detector(tmp_path, stack)
        assert expected_framework in stack.frameworks

    def test_js_react(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"react": "^18.0.0"}}))
        stack = ProjectStack()
        _detect_js_frameworks(tmp_path, stack)
        assert "react" in stack.frameworks

    def test_go_gin(self, tmp_path: Path) -> None:
        (tmp_path / "go.mod").write_text("module test\nrequire github.com/gin-gonic/gin v1.9.0")
        stack = ProjectStack()
        _detect_go_frameworks(tmp_path, stack)
        assert "gin" in stack.frameworks

    def test_rust_actix(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text('[dependencies]\nactix-web = "4.0"')
        stack = ProjectStack()
        _detect_rust_frameworks(tmp_path, stack)
        assert "actix" in stack.frameworks


class TestInfrastructureDetection:
    def test_detect_docker(self, tmp_path: Path) -> None:
        (tmp_path / "Dockerfile").write_text("FROM python:3.11")
        stack = detect_project_stack(tmp_path)
        assert "docker" in stack.infrastructure


class TestGetRequiredRules:
    def test_always_includes_core(self) -> None:
        rules = get_required_rules(ProjectStack())
        assert any("owasp" in r.lower() for r in rules)

    def test_includes_language_and_special_rules(self) -> None:
        stack = ProjectStack(languages={"python"}, ai_ml=True, rag=True)
        rules = get_required_rules(stack)
        assert any("python" in r for r in rules)
        assert any("ai" in r.lower() for r in rules)
        assert any("rag" in r.lower() for r in rules)


class TestFetchRules:
    def test_fetch_uses_cache(self, tmp_path: Path) -> None:
        cached = tmp_path / "_core" / "owasp-2025.md"
        cached.parent.mkdir(parents=True)
        cached.write_text("# OWASP Rules")
        with patch("subprocess.run") as mock_run:
            result = fetch_rules(["rules/_core/owasp-2025.md"], tmp_path, use_cache=True)
        mock_run.assert_not_called()
        assert "rules/_core/owasp-2025.md" in result


class TestGenerateClaudeMdSection:
    def test_generate_with_all_components(self, tmp_path: Path) -> None:
        stack = ProjectStack(
            languages={"python", "javascript"},
            frameworks={"fastapi"},
            databases={"postgresql"},
            infrastructure={"docker"},
            ai_ml=True,
            rag=True,
        )
        section = generate_claude_md_section(stack, tmp_path)
        assert "# Security Rules" in section
        assert "**Languages**:" in section
        assert "**AI/ML**: Yes" in section


class TestIntegrateSecurityRules:
    def test_integration_detects_and_fetches(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("print('hello')")
        with patch("zerg.security_rules.fetch_rules") as mock_fetch:
            mock_fetch.return_value = {}
            result = integrate_security_rules(
                tmp_path, output_dir=tmp_path / ".claude" / "rules" / "security", update_claude_md=False
            )
        assert "python" in result["stack"]["languages"]


class TestDetectionMappings:
    def test_mappings_populated(self) -> None:
        assert "*.py" in LANGUAGE_DETECTION
        assert "fastapi" in FRAMEWORK_DETECTION
        assert "Dockerfile" in INFRASTRUCTURE_DETECTION
        assert "_core" in RULE_PATHS
        assert "python" in RULE_PATHS


class TestFilterRulesForFiles:
    def test_filter_rules_for_python_files(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / "security"
        (rules_dir / "_core").mkdir(parents=True)
        (rules_dir / "_core" / "owasp-2025.md").write_text("# OWASP core rules")
        (rules_dir / "languages" / "python").mkdir(parents=True)
        (rules_dir / "languages" / "python" / "CLAUDE.md").write_text("# Python security rules")
        (rules_dir / "languages" / "javascript").mkdir(parents=True)
        (rules_dir / "languages" / "javascript" / "CLAUDE.md").write_text("# JS security rules")
        result = filter_rules_for_files(["src/app.py", "src/models.py"], rules_dir=rules_dir)
        result_strs = [str(p) for p in result]
        assert any("python" in s for s in result_strs)
        assert not any("javascript" in s for s in result_strs)


class TestSummarizeRules:
    def test_summarize_within_budget(self, tmp_path: Path) -> None:
        rule_file = tmp_path / "test_rules.md"
        rule_file.write_text(
            "## Rule: Prevent SQL Injection\n**Level**: `strict`\n"
            "```python\ncursor.execute('SELECT * FROM users WHERE id = %s', (uid,))\n```\n"
        )
        result = summarize_rules([rule_file], max_tokens=50)
        assert len(result) <= 50 * 4
        assert "cursor.execute" not in result
