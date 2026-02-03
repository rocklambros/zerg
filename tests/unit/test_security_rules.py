"""Tests for ZERG security rules module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    """Tests for ProjectStack dataclass."""

    def test_creation_empty(self) -> None:
        """Test creating empty stack."""
        stack = ProjectStack()

        assert len(stack.languages) == 0
        assert len(stack.frameworks) == 0
        assert len(stack.databases) == 0
        assert stack.ai_ml is False
        assert stack.rag is False

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        stack = ProjectStack(
            languages={"python", "javascript"},
            frameworks={"fastapi", "react"},
            databases={"postgresql"},
            infrastructure={"docker"},
            ai_ml=True,
            rag=False,
        )

        data = stack.to_dict()

        assert data["languages"] == ["javascript", "python"]  # Sorted
        assert data["frameworks"] == ["fastapi", "react"]
        assert data["databases"] == ["postgresql"]
        assert data["infrastructure"] == ["docker"]
        assert data["ai_ml"] is True
        assert data["rag"] is False


class TestLanguageDetection:
    """Tests for language detection."""

    def test_detect_python_by_file(self, tmp_path: Path) -> None:
        """Test detecting Python by .py files."""
        (tmp_path / "app.py").write_text("print('hello')")

        stack = detect_project_stack(tmp_path)

        assert "python" in stack.languages

    def test_detect_python_by_pyproject(self, tmp_path: Path) -> None:
        """Test detecting Python by pyproject.toml."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")

        stack = detect_project_stack(tmp_path)

        assert "python" in stack.languages

    def test_detect_javascript(self, tmp_path: Path) -> None:
        """Test detecting JavaScript."""
        (tmp_path / "app.js").write_text("console.log('hello')")

        stack = detect_project_stack(tmp_path)

        assert "javascript" in stack.languages

    def test_detect_typescript(self, tmp_path: Path) -> None:
        """Test detecting TypeScript."""
        (tmp_path / "tsconfig.json").write_text("{}")

        stack = detect_project_stack(tmp_path)

        assert "typescript" in stack.languages

    def test_detect_go(self, tmp_path: Path) -> None:
        """Test detecting Go."""
        (tmp_path / "go.mod").write_text("module test")

        stack = detect_project_stack(tmp_path)

        assert "go" in stack.languages

    def test_detect_rust(self, tmp_path: Path) -> None:
        """Test detecting Rust."""
        (tmp_path / "Cargo.toml").write_text("[package]\nname = 'test'")

        stack = detect_project_stack(tmp_path)

        assert "rust" in stack.languages


class TestPythonFrameworkDetection:
    """Tests for Python framework detection."""

    def test_detect_fastapi(self, tmp_path: Path) -> None:
        """Test detecting FastAPI."""
        (tmp_path / "requirements.txt").write_text("fastapi>=0.100.0")

        stack = ProjectStack()
        _detect_python_frameworks(tmp_path, stack)

        assert "fastapi" in stack.frameworks

    def test_detect_django(self, tmp_path: Path) -> None:
        """Test detecting Django."""
        (tmp_path / "requirements.txt").write_text("django==4.0")

        stack = ProjectStack()
        _detect_python_frameworks(tmp_path, stack)

        assert "django" in stack.frameworks

    def test_detect_langchain(self, tmp_path: Path) -> None:
        """Test detecting LangChain."""
        (tmp_path / "requirements.txt").write_text("langchain>=0.1.0")

        stack = ProjectStack()
        _detect_python_frameworks(tmp_path, stack)

        assert "langchain" in stack.frameworks

    def test_detect_from_pyproject(self, tmp_path: Path) -> None:
        """Test detecting from pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
dependencies = ["flask", "sqlalchemy"]
""")

        stack = ProjectStack()
        _detect_python_frameworks(tmp_path, stack)

        assert "flask" in stack.frameworks

    def test_detect_database_client(self, tmp_path: Path) -> None:
        """Test detecting database clients."""
        (tmp_path / "requirements.txt").write_text("chromadb>=0.4.0")

        stack = ProjectStack()
        _detect_python_frameworks(tmp_path, stack)

        assert "chroma" in stack.databases


class TestJSFrameworkDetection:
    """Tests for JavaScript framework detection."""

    def test_detect_react(self, tmp_path: Path) -> None:
        """Test detecting React."""
        package_json = tmp_path / "package.json"
        package_json.write_text(json.dumps({"dependencies": {"react": "^18.0.0"}}))

        stack = ProjectStack()
        _detect_js_frameworks(tmp_path, stack)

        assert "react" in stack.frameworks

    def test_detect_nextjs(self, tmp_path: Path) -> None:
        """Test detecting Next.js."""
        package_json = tmp_path / "package.json"
        package_json.write_text(json.dumps({"dependencies": {"next": "^14.0.0"}}))

        stack = ProjectStack()
        _detect_js_frameworks(tmp_path, stack)

        assert "nextjs" in stack.frameworks

    def test_detect_from_devdeps(self, tmp_path: Path) -> None:
        """Test detecting from devDependencies."""
        package_json = tmp_path / "package.json"
        package_json.write_text(json.dumps({"devDependencies": {"@nestjs/core": "^10.0.0"}}))

        stack = ProjectStack()
        _detect_js_frameworks(tmp_path, stack)

        assert "nestjs" in stack.frameworks


class TestGoFrameworkDetection:
    """Tests for Go framework detection."""

    def test_detect_gin(self, tmp_path: Path) -> None:
        """Test detecting Gin framework."""
        go_mod = tmp_path / "go.mod"
        go_mod.write_text("module test\nrequire github.com/gin-gonic/gin v1.9.0")

        stack = ProjectStack()
        _detect_go_frameworks(tmp_path, stack)

        assert "gin" in stack.frameworks


class TestRustFrameworkDetection:
    """Tests for Rust framework detection."""

    def test_detect_actix(self, tmp_path: Path) -> None:
        """Test detecting Actix framework."""
        cargo = tmp_path / "Cargo.toml"
        cargo.write_text('[dependencies]\nactix-web = "4.0"')

        stack = ProjectStack()
        _detect_rust_frameworks(tmp_path, stack)

        assert "actix" in stack.frameworks


class TestInfrastructureDetection:
    """Tests for infrastructure detection."""

    def test_detect_docker(self, tmp_path: Path) -> None:
        """Test detecting Docker."""
        (tmp_path / "Dockerfile").write_text("FROM python:3.11")

        stack = detect_project_stack(tmp_path)

        assert "docker" in stack.infrastructure

    def test_detect_docker_compose(self, tmp_path: Path) -> None:
        """Test detecting Docker Compose."""
        (tmp_path / "docker-compose.yaml").write_text("version: '3'")

        stack = detect_project_stack(tmp_path)

        assert "docker" in stack.infrastructure

    def test_detect_terraform(self, tmp_path: Path) -> None:
        """Test detecting Terraform."""
        (tmp_path / "main.tf").write_text('provider "aws" {}')

        stack = detect_project_stack(tmp_path)

        assert "terraform" in stack.infrastructure


class TestGetRequiredRules:
    """Tests for getting required rules."""

    def test_always_includes_core(self) -> None:
        """Test core rules always included."""
        stack = ProjectStack()

        rules = get_required_rules(stack)

        assert any("owasp" in r.lower() for r in rules)

    def test_includes_language_rules(self) -> None:
        """Test language rules included."""
        stack = ProjectStack(languages={"python"})

        rules = get_required_rules(stack)

        assert any("python" in r for r in rules)

    def test_includes_framework_rules(self) -> None:
        """Test framework rules included."""
        stack = ProjectStack(frameworks={"fastapi"})

        rules = get_required_rules(stack)

        assert any("fastapi" in r for r in rules)

    def test_includes_ai_ml_rules(self) -> None:
        """Test AI/ML rules included when flag set."""
        stack = ProjectStack(ai_ml=True)

        rules = get_required_rules(stack)

        assert any("ai" in r.lower() for r in rules)

    def test_includes_rag_rules(self) -> None:
        """Test RAG rules included when flag set."""
        stack = ProjectStack(rag=True)

        rules = get_required_rules(stack)

        assert any("rag" in r.lower() for r in rules)


class TestFetchRules:
    """Tests for rule fetching."""

    def test_fetch_uses_cache(self, tmp_path: Path) -> None:
        """Test fetching uses cached files."""
        # Create cached file
        cached = tmp_path / "_core" / "owasp-2025.md"
        cached.parent.mkdir(parents=True)
        cached.write_text("# OWASP Rules")

        with patch("subprocess.run") as mock_run:
            result = fetch_rules(
                ["rules/_core/owasp-2025.md"],
                tmp_path,
                use_cache=True,
            )

        # Should not have called subprocess (used cache)
        mock_run.assert_not_called()
        assert "rules/_core/owasp-2025.md" in result

    def test_fetch_downloads_missing(self, tmp_path: Path) -> None:
        """Test fetching downloads missing files."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "# Downloaded content"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = fetch_rules(
                ["rules/languages/python/CLAUDE.md"],
                tmp_path,
                use_cache=True,
            )

        mock_run.assert_called_once()
        assert "rules/languages/python/CLAUDE.md" in result


class TestGenerateClaudeMdSection:
    """Tests for CLAUDE.md section generation."""

    def test_generate_basic_section(self, tmp_path: Path) -> None:
        """Test generating basic section."""
        stack = ProjectStack(languages={"python"})

        section = generate_claude_md_section(stack, tmp_path)

        assert "# Security Rules" in section
        assert "python" in section
        assert "TikiTribe" in section

    def test_generate_with_all_components(self, tmp_path: Path) -> None:
        """Test generating section with all components."""
        stack = ProjectStack(
            languages={"python", "javascript"},
            frameworks={"fastapi"},
            databases={"postgresql"},
            infrastructure={"docker"},
            ai_ml=True,
            rag=True,
        )

        section = generate_claude_md_section(stack, tmp_path)

        assert "**Languages**:" in section
        assert "**Frameworks**:" in section
        assert "**Databases**:" in section
        assert "**Infrastructure**:" in section
        assert "**AI/ML**: Yes" in section
        assert "**RAG**: Yes" in section


class TestIntegrateSecurityRules:
    """Tests for full integration."""

    def test_integration_detects_and_fetches(self, tmp_path: Path) -> None:
        """Test full integration workflow."""
        # Create a Python project
        (tmp_path / "app.py").write_text("print('hello')")

        with patch("zerg.security_rules.fetch_rules") as mock_fetch:
            mock_fetch.return_value = {}

            result = integrate_security_rules(
                tmp_path,
                output_dir=tmp_path / ".claude" / "rules" / "security",
                update_claude_md=False,
            )

        assert "python" in result["stack"]["languages"]
        mock_fetch.assert_called_once()


class TestRulePaths:
    """Tests for rule path definitions."""

    def test_core_rules_defined(self) -> None:
        """Test core rules are defined."""
        assert "_core" in RULE_PATHS
        assert len(RULE_PATHS["_core"]) > 0

    def test_language_rules_defined(self) -> None:
        """Test language rules are defined."""
        assert "python" in RULE_PATHS
        assert "javascript" in RULE_PATHS
        assert "typescript" in RULE_PATHS

    def test_framework_rules_defined(self) -> None:
        """Test framework rules are defined."""
        assert "fastapi" in RULE_PATHS
        assert "django" in RULE_PATHS
        assert "react" in RULE_PATHS


class TestDetectionMappings:
    """Tests for detection mapping definitions."""

    def test_language_detection_populated(self) -> None:
        """Test language detection mapping is populated."""
        assert "*.py" in LANGUAGE_DETECTION
        assert "*.js" in LANGUAGE_DETECTION
        assert "go.mod" in LANGUAGE_DETECTION

    def test_framework_detection_populated(self) -> None:
        """Test framework detection mapping is populated."""
        assert "fastapi" in FRAMEWORK_DETECTION
        assert "react" in FRAMEWORK_DETECTION

    def test_infrastructure_detection_populated(self) -> None:
        """Test infrastructure detection mapping is populated."""
        assert "Dockerfile" in INFRASTRUCTURE_DETECTION
        assert "*.tf" in INFRASTRUCTURE_DETECTION


class TestFilterRulesForFiles:
    """Tests for filter_rules_for_files function."""

    def test_filter_rules_for_files_python(self, tmp_path: Path) -> None:
        """Test that .py files trigger python security rules."""
        rules_dir = tmp_path / "security"
        core_dir = rules_dir / "_core"
        core_dir.mkdir(parents=True)
        (core_dir / "owasp-2025.md").write_text("# OWASP core rules")

        py_dir = rules_dir / "languages" / "python"
        py_dir.mkdir(parents=True)
        (py_dir / "CLAUDE.md").write_text("# Python security rules")

        js_dir = rules_dir / "languages" / "javascript"
        js_dir.mkdir(parents=True)
        (js_dir / "CLAUDE.md").write_text("# JS security rules")

        result = filter_rules_for_files(
            ["src/app.py", "src/models.py"],
            rules_dir=rules_dir,
        )

        # Should include core and python, but NOT javascript
        result_strs = [str(p) for p in result]
        assert any("owasp-2025.md" in s for s in result_strs)
        assert any("python" in s for s in result_strs)
        assert not any("javascript" in s for s in result_strs)


class TestSummarizeRules:
    """Tests for summarize_rules function."""

    def test_summarize_rules_within_budget(self, tmp_path: Path) -> None:
        """Test that summarize_rules stays within the token budget."""
        # Create a rule file with known content
        rule_file = tmp_path / "test_rules.md"
        rule_content = (
            "## Rule: Prevent SQL Injection\n"
            "**Level**: `strict`\n"
            "**When**: Constructing database queries.\n"
            "```python\n"
            "cursor.execute('SELECT * FROM users WHERE id = %s', (uid,))\n"
            "```\n"
            "## Rule: Use HTTPS\n"
            "**Level**: `warning`\n"
            "**When**: Making HTTP requests.\n"
        )
        rule_file.write_text(rule_content)

        # Use a small budget: 50 tokens = ~200 chars
        result = summarize_rules([rule_file], max_tokens=50)

        # Result should not exceed budget in characters (~50 * 4 = 200 chars)
        assert len(result) <= 50 * 4
        # Code blocks should be excluded from the summary
        assert "cursor.execute" not in result
