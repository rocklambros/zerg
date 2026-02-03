"""Comprehensive unit tests for security_rules.py - 100% coverage target."""

import json
import subprocess
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
    _update_claude_md,
    detect_project_stack,
    fetch_rules,
    generate_claude_md_section,
    get_required_rules,
    integrate_security_rules,
)


class TestProjectStack:
    """Tests for ProjectStack dataclass."""

    def test_creation_empty(self) -> None:
        """Test creating empty stack."""
        stack = ProjectStack()

        assert len(stack.languages) == 0
        assert len(stack.frameworks) == 0
        assert len(stack.databases) == 0
        assert len(stack.infrastructure) == 0
        assert stack.ai_ml is False
        assert stack.rag is False

    def test_creation_with_values(self) -> None:
        """Test creating stack with values."""
        stack = ProjectStack(
            languages={"python", "javascript"},
            frameworks={"fastapi", "react"},
            databases={"postgresql"},
            infrastructure={"docker"},
            ai_ml=True,
            rag=True,
        )

        assert "python" in stack.languages
        assert "react" in stack.frameworks
        assert "postgresql" in stack.databases
        assert "docker" in stack.infrastructure
        assert stack.ai_ml is True
        assert stack.rag is True

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

    def test_to_dict_empty(self) -> None:
        """Test to_dict with empty stack."""
        stack = ProjectStack()
        data = stack.to_dict()

        assert data["languages"] == []
        assert data["frameworks"] == []
        assert data["databases"] == []
        assert data["infrastructure"] == []
        assert data["ai_ml"] is False
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

    def test_detect_python_by_requirements(self, tmp_path: Path) -> None:
        """Test detecting Python by requirements.txt."""
        (tmp_path / "requirements.txt").write_text("flask==2.0.0")

        stack = detect_project_stack(tmp_path)

        assert "python" in stack.languages

    def test_detect_python_by_pipfile(self, tmp_path: Path) -> None:
        """Test detecting Python by Pipfile."""
        (tmp_path / "Pipfile").write_text("[packages]\nflask = '*'")

        stack = detect_project_stack(tmp_path)

        assert "python" in stack.languages

    def test_detect_python_by_setup_py(self, tmp_path: Path) -> None:
        """Test detecting Python by setup.py."""
        (tmp_path / "setup.py").write_text("from setuptools import setup")

        stack = detect_project_stack(tmp_path)

        assert "python" in stack.languages

    def test_detect_javascript(self, tmp_path: Path) -> None:
        """Test detecting JavaScript."""
        (tmp_path / "app.js").write_text("console.log('hello')")

        stack = detect_project_stack(tmp_path)

        assert "javascript" in stack.languages

    def test_detect_javascript_mjs(self, tmp_path: Path) -> None:
        """Test detecting JavaScript by .mjs files."""
        (tmp_path / "module.mjs").write_text("export default {}")

        stack = detect_project_stack(tmp_path)

        assert "javascript" in stack.languages

    def test_detect_javascript_by_package_json(self, tmp_path: Path) -> None:
        """Test detecting JavaScript by package.json."""
        (tmp_path / "package.json").write_text('{"name": "test"}')

        stack = detect_project_stack(tmp_path)

        assert "javascript" in stack.languages

    def test_detect_typescript(self, tmp_path: Path) -> None:
        """Test detecting TypeScript."""
        (tmp_path / "tsconfig.json").write_text("{}")

        stack = detect_project_stack(tmp_path)

        assert "typescript" in stack.languages

    def test_detect_typescript_by_ts_file(self, tmp_path: Path) -> None:
        """Test detecting TypeScript by .ts files."""
        (tmp_path / "app.ts").write_text("const x: number = 1;")

        stack = detect_project_stack(tmp_path)

        assert "typescript" in stack.languages

    def test_detect_typescript_by_tsx_file(self, tmp_path: Path) -> None:
        """Test detecting TypeScript by .tsx files."""
        (tmp_path / "App.tsx").write_text("const App: React.FC = () => <div />;")

        stack = detect_project_stack(tmp_path)

        assert "typescript" in stack.languages

    def test_detect_go(self, tmp_path: Path) -> None:
        """Test detecting Go."""
        (tmp_path / "go.mod").write_text("module test")

        stack = detect_project_stack(tmp_path)

        assert "go" in stack.languages

    def test_detect_go_by_go_file(self, tmp_path: Path) -> None:
        """Test detecting Go by .go files."""
        (tmp_path / "main.go").write_text("package main")

        stack = detect_project_stack(tmp_path)

        assert "go" in stack.languages

    def test_detect_rust(self, tmp_path: Path) -> None:
        """Test detecting Rust."""
        (tmp_path / "Cargo.toml").write_text("[package]\nname = 'test'")

        stack = detect_project_stack(tmp_path)

        assert "rust" in stack.languages

    def test_detect_rust_by_rs_file(self, tmp_path: Path) -> None:
        """Test detecting Rust by .rs files."""
        (tmp_path / "main.rs").write_text("fn main() {}")

        stack = detect_project_stack(tmp_path)

        assert "rust" in stack.languages

    def test_detect_java(self, tmp_path: Path) -> None:
        """Test detecting Java."""
        (tmp_path / "Main.java").write_text("public class Main {}")

        stack = detect_project_stack(tmp_path)

        assert "java" in stack.languages

    def test_detect_java_by_pom(self, tmp_path: Path) -> None:
        """Test detecting Java by pom.xml."""
        (tmp_path / "pom.xml").write_text("<project></project>")

        stack = detect_project_stack(tmp_path)

        assert "java" in stack.languages

    def test_detect_java_by_gradle(self, tmp_path: Path) -> None:
        """Test detecting Java by build.gradle."""
        (tmp_path / "build.gradle").write_text("apply plugin: 'java'")

        stack = detect_project_stack(tmp_path)

        assert "java" in stack.languages

    def test_detect_csharp(self, tmp_path: Path) -> None:
        """Test detecting C#."""
        (tmp_path / "Program.cs").write_text("class Program {}")

        stack = detect_project_stack(tmp_path)

        assert "csharp" in stack.languages

    def test_detect_csharp_by_csproj(self, tmp_path: Path) -> None:
        """Test detecting C# by .csproj."""
        (tmp_path / "project.csproj").write_text("<Project></Project>")

        stack = detect_project_stack(tmp_path)

        assert "csharp" in stack.languages

    def test_detect_ruby(self, tmp_path: Path) -> None:
        """Test detecting Ruby."""
        (tmp_path / "app.rb").write_text("puts 'hello'")

        stack = detect_project_stack(tmp_path)

        assert "ruby" in stack.languages

    def test_detect_ruby_by_gemfile(self, tmp_path: Path) -> None:
        """Test detecting Ruby by Gemfile."""
        (tmp_path / "Gemfile").write_text("gem 'rails'")

        stack = detect_project_stack(tmp_path)

        assert "ruby" in stack.languages

    def test_detect_cpp(self, tmp_path: Path) -> None:
        """Test detecting C++."""
        (tmp_path / "main.cpp").write_text("int main() {}")

        stack = detect_project_stack(tmp_path)

        assert "cpp" in stack.languages

    def test_detect_cpp_by_cc(self, tmp_path: Path) -> None:
        """Test detecting C++ by .cc files."""
        (tmp_path / "main.cc").write_text("int main() {}")

        stack = detect_project_stack(tmp_path)

        assert "cpp" in stack.languages

    def test_detect_cpp_by_hpp(self, tmp_path: Path) -> None:
        """Test detecting C++ by .hpp files."""
        (tmp_path / "header.hpp").write_text("#pragma once")

        stack = detect_project_stack(tmp_path)

        assert "cpp" in stack.languages

    def test_detect_cpp_by_cmake(self, tmp_path: Path) -> None:
        """Test detecting C++ by CMakeLists.txt."""
        (tmp_path / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.0)")

        stack = detect_project_stack(tmp_path)

        assert "cpp" in stack.languages

    def test_detect_r_lowercase(self, tmp_path: Path) -> None:
        """Test detecting R by .r files."""
        (tmp_path / "script.r").write_text("print('hello')")

        stack = detect_project_stack(tmp_path)

        assert "r" in stack.languages

    def test_detect_r_uppercase(self, tmp_path: Path) -> None:
        """Test detecting R by .R files."""
        (tmp_path / "script.R").write_text("print('hello')")

        stack = detect_project_stack(tmp_path)

        assert "r" in stack.languages

    def test_detect_julia(self, tmp_path: Path) -> None:
        """Test detecting Julia."""
        (tmp_path / "script.jl").write_text('println("hello")')

        stack = detect_project_stack(tmp_path)

        assert "julia" in stack.languages

    def test_detect_sql(self, tmp_path: Path) -> None:
        """Test detecting SQL."""
        (tmp_path / "schema.sql").write_text("CREATE TABLE test (id INT);")

        stack = detect_project_stack(tmp_path)

        assert "sql" in stack.languages

    def test_detect_multiple_languages(self, tmp_path: Path) -> None:
        """Test detecting multiple languages."""
        (tmp_path / "app.py").write_text("print('hello')")
        (tmp_path / "app.js").write_text("console.log('hello')")
        (tmp_path / "go.mod").write_text("module test")

        stack = detect_project_stack(tmp_path)

        assert "python" in stack.languages
        assert "javascript" in stack.languages
        assert "go" in stack.languages


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

    def test_detect_flask(self, tmp_path: Path) -> None:
        """Test detecting Flask."""
        (tmp_path / "requirements.txt").write_text("flask>=2.0")

        stack = ProjectStack()
        _detect_python_frameworks(tmp_path, stack)

        assert "flask" in stack.frameworks

    def test_detect_langchain(self, tmp_path: Path) -> None:
        """Test detecting LangChain."""
        (tmp_path / "requirements.txt").write_text("langchain>=0.1.0")

        stack = ProjectStack()
        _detect_python_frameworks(tmp_path, stack)

        assert "langchain" in stack.frameworks

    def test_detect_llamaindex(self, tmp_path: Path) -> None:
        """Test detecting LlamaIndex."""
        (tmp_path / "requirements.txt").write_text("llama-index>=0.9.0")

        stack = ProjectStack()
        _detect_python_frameworks(tmp_path, stack)

        assert "llamaindex" in stack.frameworks

    def test_detect_pytorch(self, tmp_path: Path) -> None:
        """Test detecting PyTorch."""
        (tmp_path / "requirements.txt").write_text("torch>=2.0")

        stack = ProjectStack()
        _detect_python_frameworks(tmp_path, stack)

        assert "pytorch" in stack.frameworks

    def test_detect_tensorflow(self, tmp_path: Path) -> None:
        """Test detecting TensorFlow."""
        (tmp_path / "requirements.txt").write_text("tensorflow>=2.0")

        stack = ProjectStack()
        _detect_python_frameworks(tmp_path, stack)

        assert "tensorflow" in stack.frameworks

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

    def test_detect_database_client_chromadb(self, tmp_path: Path) -> None:
        """Test detecting chromadb database client."""
        (tmp_path / "requirements.txt").write_text("chromadb>=0.4.0")

        stack = ProjectStack()
        _detect_python_frameworks(tmp_path, stack)

        assert "chroma" in stack.databases

    def test_detect_database_client_pinecone(self, tmp_path: Path) -> None:
        """Test detecting Pinecone database client."""
        (tmp_path / "requirements.txt").write_text("pinecone-client>=2.0")

        stack = ProjectStack()
        _detect_python_frameworks(tmp_path, stack)

        assert "pinecone" in stack.databases

    def test_detect_database_client_postgresql(self, tmp_path: Path) -> None:
        """Test detecting PostgreSQL client."""
        (tmp_path / "requirements.txt").write_text("psycopg2>=2.9")

        stack = ProjectStack()
        _detect_python_frameworks(tmp_path, stack)

        assert "postgresql" in stack.databases

    def test_detect_database_client_asyncpg(self, tmp_path: Path) -> None:
        """Test detecting asyncpg client."""
        (tmp_path / "requirements.txt").write_text("asyncpg>=0.27")

        stack = ProjectStack()
        _detect_python_frameworks(tmp_path, stack)

        assert "postgresql" in stack.databases

    def test_skip_comments_in_requirements(self, tmp_path: Path) -> None:
        """Test skipping comments in requirements.txt."""
        (tmp_path / "requirements.txt").write_text("""
# This is a comment
fastapi>=0.100.0
# Another comment
""")

        stack = ProjectStack()
        _detect_python_frameworks(tmp_path, stack)

        assert "fastapi" in stack.frameworks

    def test_handle_version_specifiers(self, tmp_path: Path) -> None:
        """Test handling various version specifiers."""
        (tmp_path / "requirements.txt").write_text("""
fastapi==0.100.0
django>=4.0
flask<=2.0
sqlalchemy[postgresql]>=2.0
""")

        stack = ProjectStack()
        _detect_python_frameworks(tmp_path, stack)

        assert "fastapi" in stack.frameworks
        assert "django" in stack.frameworks
        assert "flask" in stack.frameworks

    def test_no_requirements_file(self, tmp_path: Path) -> None:
        """Test when no requirements file exists."""
        stack = ProjectStack()
        _detect_python_frameworks(tmp_path, stack)

        assert len(stack.frameworks) == 0

    def test_empty_requirements_file(self, tmp_path: Path) -> None:
        """Test with empty requirements file."""
        (tmp_path / "requirements.txt").write_text("")

        stack = ProjectStack()
        _detect_python_frameworks(tmp_path, stack)

        assert len(stack.frameworks) == 0


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

    def test_detect_vue(self, tmp_path: Path) -> None:
        """Test detecting Vue."""
        package_json = tmp_path / "package.json"
        package_json.write_text(json.dumps({"dependencies": {"vue": "^3.0.0"}}))

        stack = ProjectStack()
        _detect_js_frameworks(tmp_path, stack)

        assert "vue" in stack.frameworks

    def test_detect_angular(self, tmp_path: Path) -> None:
        """Test detecting Angular."""
        package_json = tmp_path / "package.json"
        package_json.write_text(json.dumps({"dependencies": {"@angular/core": "^17.0.0"}}))

        stack = ProjectStack()
        _detect_js_frameworks(tmp_path, stack)

        assert "angular" in stack.frameworks

    def test_detect_svelte(self, tmp_path: Path) -> None:
        """Test detecting Svelte."""
        package_json = tmp_path / "package.json"
        package_json.write_text(json.dumps({"dependencies": {"svelte": "^4.0.0"}}))

        stack = ProjectStack()
        _detect_js_frameworks(tmp_path, stack)

        assert "svelte" in stack.frameworks

    def test_detect_express(self, tmp_path: Path) -> None:
        """Test detecting Express."""
        package_json = tmp_path / "package.json"
        package_json.write_text(json.dumps({"dependencies": {"express": "^4.18.0"}}))

        stack = ProjectStack()
        _detect_js_frameworks(tmp_path, stack)

        assert "express" in stack.frameworks

    def test_detect_nestjs(self, tmp_path: Path) -> None:
        """Test detecting NestJS."""
        package_json = tmp_path / "package.json"
        package_json.write_text(json.dumps({"dependencies": {"@nestjs/core": "^10.0.0"}}))

        stack = ProjectStack()
        _detect_js_frameworks(tmp_path, stack)

        assert "nestjs" in stack.frameworks

    def test_detect_fastify(self, tmp_path: Path) -> None:
        """Test detecting Fastify."""
        package_json = tmp_path / "package.json"
        package_json.write_text(json.dumps({"dependencies": {"fastify": "^4.0.0"}}))

        stack = ProjectStack()
        _detect_js_frameworks(tmp_path, stack)

        assert "fastify" in stack.frameworks

    def test_detect_from_devdeps(self, tmp_path: Path) -> None:
        """Test detecting from devDependencies."""
        package_json = tmp_path / "package.json"
        package_json.write_text(json.dumps({"devDependencies": {"@nestjs/core": "^10.0.0"}}))

        stack = ProjectStack()
        _detect_js_frameworks(tmp_path, stack)

        assert "nestjs" in stack.frameworks

    def test_detect_database_from_js(self, tmp_path: Path) -> None:
        """Test detecting database client from JS project."""
        package_json = tmp_path / "package.json"
        package_json.write_text(json.dumps({"dependencies": {"mongodb": "^6.0.0"}}))

        stack = ProjectStack()
        _detect_js_frameworks(tmp_path, stack)

        assert "mongodb" in stack.databases

    def test_no_package_json(self, tmp_path: Path) -> None:
        """Test when no package.json exists."""
        stack = ProjectStack()
        _detect_js_frameworks(tmp_path, stack)

        assert len(stack.frameworks) == 0

    def test_invalid_package_json(self, tmp_path: Path) -> None:
        """Test handling invalid package.json."""
        package_json = tmp_path / "package.json"
        package_json.write_text("invalid json {{{")

        stack = ProjectStack()
        _detect_js_frameworks(tmp_path, stack)

        assert len(stack.frameworks) == 0

    def test_package_json_without_dependencies(self, tmp_path: Path) -> None:
        """Test package.json without dependencies."""
        package_json = tmp_path / "package.json"
        package_json.write_text(json.dumps({"name": "test", "version": "1.0.0"}))

        stack = ProjectStack()
        _detect_js_frameworks(tmp_path, stack)

        assert len(stack.frameworks) == 0


class TestGoFrameworkDetection:
    """Tests for Go framework detection."""

    def test_detect_gin(self, tmp_path: Path) -> None:
        """Test detecting Gin framework."""
        go_mod = tmp_path / "go.mod"
        go_mod.write_text("module test\nrequire github.com/gin-gonic/gin v1.9.0")

        stack = ProjectStack()
        _detect_go_frameworks(tmp_path, stack)

        assert "gin" in stack.frameworks

    def test_detect_echo(self, tmp_path: Path) -> None:
        """Test detecting Echo framework."""
        go_mod = tmp_path / "go.mod"
        go_mod.write_text("module test\nrequire github.com/labstack/echo v4.0.0")

        stack = ProjectStack()
        _detect_go_frameworks(tmp_path, stack)

        assert "echo" in stack.frameworks

    def test_no_go_mod(self, tmp_path: Path) -> None:
        """Test when no go.mod exists."""
        stack = ProjectStack()
        _detect_go_frameworks(tmp_path, stack)

        assert len(stack.frameworks) == 0


class TestRustFrameworkDetection:
    """Tests for Rust framework detection."""

    def test_detect_actix(self, tmp_path: Path) -> None:
        """Test detecting Actix framework."""
        cargo = tmp_path / "Cargo.toml"
        cargo.write_text('[dependencies]\nactix-web = "4.0"')

        stack = ProjectStack()
        _detect_rust_frameworks(tmp_path, stack)

        assert "actix" in stack.frameworks

    def test_detect_axum(self, tmp_path: Path) -> None:
        """Test detecting Axum framework."""
        cargo = tmp_path / "Cargo.toml"
        cargo.write_text('[dependencies]\naxum = "0.6"')

        stack = ProjectStack()
        _detect_rust_frameworks(tmp_path, stack)

        assert "axum" in stack.frameworks

    def test_detect_rocket(self, tmp_path: Path) -> None:
        """Test detecting Rocket framework."""
        cargo = tmp_path / "Cargo.toml"
        cargo.write_text('[dependencies]\nrocket = "0.5"')

        stack = ProjectStack()
        _detect_rust_frameworks(tmp_path, stack)

        assert "rocket" in stack.frameworks

    def test_no_cargo_toml(self, tmp_path: Path) -> None:
        """Test when no Cargo.toml exists."""
        stack = ProjectStack()
        _detect_rust_frameworks(tmp_path, stack)

        assert len(stack.frameworks) == 0


class TestInfrastructureDetection:
    """Tests for infrastructure detection."""

    def test_detect_docker(self, tmp_path: Path) -> None:
        """Test detecting Docker."""
        (tmp_path / "Dockerfile").write_text("FROM python:3.11")

        stack = detect_project_stack(tmp_path)

        assert "docker" in stack.infrastructure

    def test_detect_docker_compose_yaml(self, tmp_path: Path) -> None:
        """Test detecting Docker Compose with .yaml."""
        (tmp_path / "docker-compose.yaml").write_text("version: '3'")

        stack = detect_project_stack(tmp_path)

        assert "docker" in stack.infrastructure

    def test_detect_docker_compose_yml(self, tmp_path: Path) -> None:
        """Test detecting Docker Compose with .yml."""
        (tmp_path / "docker-compose.yml").write_text("version: '3'")

        stack = detect_project_stack(tmp_path)

        assert "docker" in stack.infrastructure

    def test_detect_terraform(self, tmp_path: Path) -> None:
        """Test detecting Terraform."""
        (tmp_path / "main.tf").write_text('provider "aws" {}')

        stack = detect_project_stack(tmp_path)

        assert "terraform" in stack.infrastructure

    def test_detect_pulumi(self, tmp_path: Path) -> None:
        """Test detecting Pulumi."""
        (tmp_path / "Pulumi.yaml").write_text("name: test")

        stack = detect_project_stack(tmp_path)

        assert "pulumi" in stack.infrastructure

    def test_detect_github_actions(self, tmp_path: Path) -> None:
        """Test detecting GitHub Actions."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "ci.yml").write_text("name: CI")

        stack = detect_project_stack(tmp_path)

        assert "github-actions" in stack.infrastructure

    def test_detect_gitlab_ci(self, tmp_path: Path) -> None:
        """Test detecting GitLab CI."""
        (tmp_path / ".gitlab-ci.yml").write_text("stages: [test]")

        stack = detect_project_stack(tmp_path)

        assert "gitlab-ci" in stack.infrastructure


class TestAIMLFlagDetection:
    """Tests for AI/ML and RAG flag detection."""

    def test_ai_ml_flag_langchain(self, tmp_path: Path) -> None:
        """Test AI/ML flag set for LangChain."""
        (tmp_path / "requirements.txt").write_text("langchain>=0.1.0")

        stack = detect_project_stack(tmp_path)

        assert stack.ai_ml is True

    def test_ai_ml_flag_pytorch(self, tmp_path: Path) -> None:
        """Test AI/ML flag set for PyTorch."""
        (tmp_path / "requirements.txt").write_text("torch>=2.0")

        stack = detect_project_stack(tmp_path)

        assert stack.ai_ml is True

    def test_ai_ml_flag_tensorflow(self, tmp_path: Path) -> None:
        """Test AI/ML flag set for TensorFlow."""
        (tmp_path / "requirements.txt").write_text("tensorflow>=2.0")

        stack = detect_project_stack(tmp_path)

        assert stack.ai_ml is True

    def test_rag_flag_with_vector_db(self, tmp_path: Path) -> None:
        """Test RAG flag set with vector database."""
        (tmp_path / "requirements.txt").write_text("chromadb>=0.4.0")

        stack = detect_project_stack(tmp_path)

        assert stack.rag is True

    def test_rag_flag_with_langchain(self, tmp_path: Path) -> None:
        """Test RAG flag set with LangChain."""
        (tmp_path / "requirements.txt").write_text("langchain>=0.1.0")

        stack = detect_project_stack(tmp_path)

        assert stack.rag is True

    def test_no_ai_ml_flag(self, tmp_path: Path) -> None:
        """Test AI/ML flag not set for regular project."""
        (tmp_path / "requirements.txt").write_text("fastapi>=0.100.0")

        stack = detect_project_stack(tmp_path)

        assert stack.ai_ml is False
        assert stack.rag is False


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

    def test_includes_database_rules(self) -> None:
        """Test database rules included."""
        stack = ProjectStack(databases={"postgresql"})

        rules = get_required_rules(stack)

        # postgresql doesn't have specific rules, but sql does
        assert len(rules) > 0

    def test_includes_infrastructure_rules(self) -> None:
        """Test infrastructure rules included."""
        stack = ProjectStack(infrastructure={"docker"})

        rules = get_required_rules(stack)

        assert any("docker" in r for r in rules)

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

    def test_rules_sorted(self) -> None:
        """Test rules are returned sorted."""
        stack = ProjectStack(
            languages={"python", "javascript"},
            frameworks={"fastapi", "react"},
        )

        rules = get_required_rules(stack)

        assert rules == sorted(rules)

    def test_rules_deduplicated(self) -> None:
        """Test rules are deduplicated."""
        stack = ProjectStack(
            languages={"python"},
            frameworks={"fastapi"},
        )

        rules = get_required_rules(stack)

        assert len(rules) == len(set(rules))


class TestFetchRules:
    """Tests for rule fetching."""

    def test_fetch_uses_cache(self, tmp_path: Path) -> None:
        """Test fetching uses cached files."""
        cached = tmp_path / "_core" / "owasp-2025.md"
        cached.parent.mkdir(parents=True)
        cached.write_text("# OWASP Rules")

        with patch("subprocess.run") as mock_run:
            result = fetch_rules(
                ["rules/_core/owasp-2025.md"],
                tmp_path,
                use_cache=True,
            )

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

    def test_fetch_no_cache(self, tmp_path: Path) -> None:
        """Test fetching without cache."""
        # Create cached file
        cached = tmp_path / "_core" / "owasp-2025.md"
        cached.parent.mkdir(parents=True)
        cached.write_text("# Cached")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "# New content"

        with patch("subprocess.run", return_value=mock_result):
            fetch_rules(
                ["rules/_core/owasp-2025.md"],
                tmp_path,
                use_cache=False,
            )

        # Should have fetched new content
        assert cached.read_text() == "# New content"

    def test_fetch_handles_failure(self, tmp_path: Path) -> None:
        """Test fetching handles failed downloads."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Not found"

        with patch("subprocess.run", return_value=mock_result):
            result = fetch_rules(
                ["rules/nonexistent.md"],
                tmp_path,
                use_cache=True,
            )

        assert "rules/nonexistent.md" not in result

    def test_fetch_handles_timeout(self, tmp_path: Path) -> None:
        """Test fetching handles timeout."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("curl", 30)):
            result = fetch_rules(
                ["rules/languages/python/CLAUDE.md"],
                tmp_path,
                use_cache=True,
            )

        assert "rules/languages/python/CLAUDE.md" not in result

    def test_fetch_handles_generic_exception(self, tmp_path: Path) -> None:
        """Test fetching handles generic exceptions."""
        with patch("subprocess.run", side_effect=Exception("Network error")):
            result = fetch_rules(
                ["rules/languages/python/CLAUDE.md"],
                tmp_path,
                use_cache=True,
            )

        assert "rules/languages/python/CLAUDE.md" not in result

    def test_fetch_creates_directories(self, tmp_path: Path) -> None:
        """Test fetching creates necessary directories."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "# Content"

        with patch("subprocess.run", return_value=mock_result):
            fetch_rules(
                ["rules/deep/nested/path.md"],
                tmp_path,
                use_cache=True,
            )

        assert (tmp_path / "deep" / "nested").exists()


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

    def test_generate_without_optional_components(self, tmp_path: Path) -> None:
        """Test generating section without optional components."""
        stack = ProjectStack(languages={"python"})

        section = generate_claude_md_section(stack, tmp_path)

        assert "**Languages**:" in section
        assert "**Frameworks**:" not in section
        assert "**Databases**:" not in section
        assert "**AI/ML**: Yes" not in section

    def test_generate_lists_rule_files(self, tmp_path: Path) -> None:
        """Test generating section lists rule files."""
        # Create some rule files
        rules_dir = tmp_path
        (rules_dir / "python.md").write_text("# Python rules")
        (rules_dir / "nested").mkdir()
        (rules_dir / "nested" / "security.md").write_text("# Security")

        stack = ProjectStack(languages={"python"})

        section = generate_claude_md_section(stack, rules_dir)

        assert "- `" in section  # Rule file listings (no @-imports)
        assert "Fetched Rules" in section


class TestUpdateClaudeMd:
    """Tests for _update_claude_md function."""

    def test_update_creates_new_file(self, tmp_path: Path) -> None:
        """Test creating new CLAUDE.md."""
        claude_md = tmp_path / "CLAUDE.md"
        section = "# Security Rules\n\nTest content"

        _update_claude_md(claude_md, section)

        assert claude_md.exists()
        content = claude_md.read_text()
        assert "SECURITY_RULES_START" in content
        assert "SECURITY_RULES_END" in content
        assert "Test content" in content

    def test_update_appends_to_existing(self, tmp_path: Path) -> None:
        """Test appending to existing CLAUDE.md."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Existing Content\n\nSome text here.")

        section = "# Security Rules\n\nNew security content"
        _update_claude_md(claude_md, section)

        content = claude_md.read_text()
        assert "Existing Content" in content
        assert "SECURITY_RULES_START" in content
        assert "New security content" in content

    def test_update_replaces_existing_section(self, tmp_path: Path) -> None:
        """Test replacing existing security section."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("""# CLAUDE.md

<!-- SECURITY_RULES_START -->
# Old Rules
Old content
<!-- SECURITY_RULES_END -->

Other content
""")

        section = "# New Rules\n\nNew content"
        _update_claude_md(claude_md, section)

        content = claude_md.read_text()
        assert "Old Rules" not in content
        assert "Old content" not in content
        assert "New Rules" in content
        assert "New content" in content
        assert "Other content" in content

    def test_update_handles_markers_without_content(self, tmp_path: Path) -> None:
        """Test handling empty markers."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("""# CLAUDE.md
<!-- SECURITY_RULES_START --><!-- SECURITY_RULES_END -->
""")

        section = "# Rules"
        _update_claude_md(claude_md, section)

        content = claude_md.read_text()
        assert "# Rules" in content


class TestIntegrateSecurityRules:
    """Tests for full integration."""

    def test_integration_detects_and_fetches(self, tmp_path: Path) -> None:
        """Test full integration workflow."""
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

    def test_integration_default_output_dir(self, tmp_path: Path) -> None:
        """Test integration with default output directory."""
        (tmp_path / "app.py").write_text("print('hello')")

        with patch("zerg.security_rules.fetch_rules") as mock_fetch:
            mock_fetch.return_value = {}

            result = integrate_security_rules(
                tmp_path,
                update_claude_md=False,
            )

        expected_dir = str(tmp_path / ".claude" / "rules" / "security")
        assert result["rules_dir"] == expected_dir

    def test_integration_updates_claude_md(self, tmp_path: Path) -> None:
        """Test integration updates CLAUDE.md."""
        (tmp_path / "app.py").write_text("print('hello')")

        with patch("zerg.security_rules.fetch_rules") as mock_fetch:
            mock_fetch.return_value = {}

            integrate_security_rules(
                tmp_path,
                output_dir=tmp_path / ".claude" / "rules" / "security",
                update_claude_md=True,
            )

        claude_md = tmp_path / "CLAUDE.md"
        assert claude_md.exists()
        content = claude_md.read_text()
        assert "SECURITY_RULES" in content

    def test_integration_returns_results(self, tmp_path: Path) -> None:
        """Test integration returns correct results."""
        (tmp_path / "app.py").write_text("print('hello')")
        (tmp_path / "requirements.txt").write_text("fastapi>=0.100.0")

        with patch("zerg.security_rules.fetch_rules") as mock_fetch:
            mock_fetch.return_value = {
                "rules/languages/python/CLAUDE.md": tmp_path / "python.md",
                "rules/backend/fastapi.md": tmp_path / "fastapi.md",
            }

            result = integrate_security_rules(
                tmp_path,
                update_claude_md=False,
            )

        assert "stack" in result
        assert "rules_fetched" in result
        assert result["rules_fetched"] == 2
        assert "rules_dir" in result
        assert "rule_paths" in result


class TestRulePaths:
    """Tests for rule path definitions."""

    def test_core_rules_defined(self) -> None:
        """Test core rules are defined."""
        assert "_core" in RULE_PATHS
        assert len(RULE_PATHS["_core"]) > 0

    def test_ai_ml_rules_defined(self) -> None:
        """Test AI/ML rules are defined."""
        assert "ai_ml" in RULE_PATHS
        assert len(RULE_PATHS["ai_ml"]) > 0

    def test_rag_rules_defined(self) -> None:
        """Test RAG rules are defined."""
        assert "rag" in RULE_PATHS
        assert len(RULE_PATHS["rag"]) > 0

    def test_language_rules_defined(self) -> None:
        """Test language rules are defined."""
        assert "python" in RULE_PATHS
        assert "javascript" in RULE_PATHS
        assert "typescript" in RULE_PATHS
        assert "go" in RULE_PATHS
        assert "rust" in RULE_PATHS
        assert "java" in RULE_PATHS

    def test_framework_rules_defined(self) -> None:
        """Test framework rules are defined."""
        assert "fastapi" in RULE_PATHS
        assert "django" in RULE_PATHS
        assert "react" in RULE_PATHS
        assert "nextjs" in RULE_PATHS

    def test_infrastructure_rules_defined(self) -> None:
        """Test infrastructure rules are defined."""
        assert "docker" in RULE_PATHS
        assert "kubernetes" in RULE_PATHS
        assert "terraform" in RULE_PATHS


class TestDetectionMappings:
    """Tests for detection mapping definitions."""

    def test_language_detection_populated(self) -> None:
        """Test language detection mapping is populated."""
        assert "*.py" in LANGUAGE_DETECTION
        assert "*.js" in LANGUAGE_DETECTION
        assert "go.mod" in LANGUAGE_DETECTION
        assert "Cargo.toml" in LANGUAGE_DETECTION

    def test_framework_detection_populated(self) -> None:
        """Test framework detection mapping is populated."""
        assert "fastapi" in FRAMEWORK_DETECTION
        assert "react" in FRAMEWORK_DETECTION
        assert "langchain" in FRAMEWORK_DETECTION

    def test_infrastructure_detection_populated(self) -> None:
        """Test infrastructure detection mapping is populated."""
        assert "Dockerfile" in INFRASTRUCTURE_DETECTION
        assert "*.tf" in INFRASTRUCTURE_DETECTION
        assert ".github/workflows" in INFRASTRUCTURE_DETECTION
