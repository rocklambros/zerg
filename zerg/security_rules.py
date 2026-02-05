"""Secure coding rules integration from TikiTribe/claude-secure-coding-rules.

This module provides intelligent fetching of security rules based on
detected project languages and frameworks.
"""

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from zerg.logging import get_logger

logger = get_logger(__name__)

# GitHub repository for secure coding rules
RULES_REPO = "TikiTribe/claude-secure-coding-rules"
RULES_RAW_URL = f"https://raw.githubusercontent.com/{RULES_REPO}/main"


@dataclass
class ProjectStack:
    """Detected project technology stack."""

    languages: set[str] = field(default_factory=set)
    frameworks: set[str] = field(default_factory=set)
    databases: set[str] = field(default_factory=set)
    infrastructure: set[str] = field(default_factory=set)
    ai_ml: bool = False
    rag: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "languages": sorted(self.languages),
            "frameworks": sorted(self.frameworks),
            "databases": sorted(self.databases),
            "infrastructure": sorted(self.infrastructure),
            "ai_ml": self.ai_ml,
            "rag": self.rag,
        }


# Mapping of file patterns to languages
LANGUAGE_DETECTION: dict[str, str] = {
    "*.py": "python",
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "setup.py": "python",
    "Pipfile": "python",
    "*.js": "javascript",
    "*.mjs": "javascript",
    "*.ts": "typescript",
    "*.tsx": "typescript",
    "package.json": "javascript",  # Could be JS or TS
    "tsconfig.json": "typescript",
    "*.go": "go",
    "go.mod": "go",
    "*.rs": "rust",
    "Cargo.toml": "rust",
    "*.java": "java",
    "pom.xml": "java",
    "build.gradle": "java",
    "*.cs": "csharp",
    "*.csproj": "csharp",
    "*.rb": "ruby",
    "Gemfile": "ruby",
    "*.r": "r",
    "*.R": "r",
    "*.cpp": "cpp",
    "*.cc": "cpp",
    "*.hpp": "cpp",
    "CMakeLists.txt": "cpp",
    "*.jl": "julia",
    "*.sql": "sql",
}

# Mapping of package/import patterns to frameworks
FRAMEWORK_DETECTION: dict[str, tuple[str, str]] = {
    # Python frameworks
    "fastapi": ("python", "fastapi"),
    "django": ("python", "django"),
    "flask": ("python", "flask"),
    "langchain": ("python", "langchain"),
    "llama_index": ("python", "llamaindex"),
    "llama-index": ("python", "llamaindex"),
    "crewai": ("python", "crewai"),
    "autogen": ("python", "autogen"),
    "transformers": ("python", "transformers"),
    "torch": ("python", "pytorch"),
    "tensorflow": ("python", "tensorflow"),
    "mlflow": ("python", "mlflow"),
    "bentoml": ("python", "bentoml"),
    "ray": ("python", "ray"),
    # JavaScript/TypeScript frameworks
    "react": ("javascript", "react"),
    "next": ("javascript", "nextjs"),
    "vue": ("javascript", "vue"),
    "angular": ("typescript", "angular"),
    "svelte": ("javascript", "svelte"),
    "express": ("javascript", "express"),
    "nestjs": ("typescript", "nestjs"),
    "@nestjs": ("typescript", "nestjs"),
    "fastify": ("javascript", "fastify"),
    # Databases
    "pinecone": ("database", "pinecone"),
    "weaviate": ("database", "weaviate"),
    "chromadb": ("database", "chroma"),
    "qdrant": ("database", "qdrant"),
    "milvus": ("database", "milvus"),
    "pgvector": ("database", "pgvector"),
    "neo4j": ("database", "neo4j"),
    "mongodb": ("database", "mongodb"),
    "psycopg": ("database", "postgresql"),
    "asyncpg": ("database", "postgresql"),
    "sqlalchemy": ("database", "sql"),
}

# Infrastructure detection patterns
INFRASTRUCTURE_DETECTION: dict[str, str] = {
    "Dockerfile": "docker",
    ".devcontainer/Dockerfile": "docker",
    "docker-compose.yml": "docker",
    "docker-compose.yaml": "docker",
    "kubernetes": "kubernetes",
    "k8s": "kubernetes",
    "*.tf": "terraform",
    "terraform": "terraform",
    "Pulumi.yaml": "pulumi",
    ".github/workflows": "github-actions",
    ".gitlab-ci.yml": "gitlab-ci",
}

# Mapping of detected tech to rule paths in the upstream repository.
# Core rules are flat .md files; everything else uses {category}/{name}/CLAUDE.md.
RULE_PATHS: dict[str, list[str]] = {
    # Core rules (always included)
    "_core": [
        "rules/_core/owasp-2025.md",
    ],
    # AI/ML core rules
    "ai_ml": [
        "rules/_core/ai-security.md",
        "rules/_core/agent-security.md",
    ],
    # RAG core rules
    "rag": [
        "rules/_core/rag-security.md",
    ],
    # Languages
    "python": ["rules/languages/python/CLAUDE.md"],
    "javascript": ["rules/languages/javascript/CLAUDE.md"],
    "typescript": ["rules/languages/typescript/CLAUDE.md"],
    "go": ["rules/languages/go/CLAUDE.md"],
    "rust": ["rules/languages/rust/CLAUDE.md"],
    "java": ["rules/languages/java/CLAUDE.md"],
    "csharp": ["rules/languages/csharp/CLAUDE.md"],
    "ruby": ["rules/languages/ruby/CLAUDE.md"],
    "r": ["rules/languages/r/CLAUDE.md"],
    "cpp": ["rules/languages/cpp/CLAUDE.md"],
    "julia": ["rules/languages/julia/CLAUDE.md"],
    "sql": ["rules/languages/sql/CLAUDE.md"],
    # Backend frameworks
    "fastapi": ["rules/backend/fastapi/CLAUDE.md"],
    "django": ["rules/backend/django/CLAUDE.md"],
    "flask": ["rules/backend/flask/CLAUDE.md"],
    "express": ["rules/backend/express/CLAUDE.md"],
    "nestjs": ["rules/backend/nestjs/CLAUDE.md"],
    "langchain": ["rules/backend/langchain/CLAUDE.md"],
    "crewai": ["rules/backend/crewai/CLAUDE.md"],
    "autogen": ["rules/backend/autogen/CLAUDE.md"],
    "transformers": ["rules/backend/transformers/CLAUDE.md"],
    "mlflow": ["rules/backend/mlflow/CLAUDE.md"],
    "bentoml": ["rules/backend/bentoml/CLAUDE.md"],
    "ray": ["rules/backend/ray-serve/CLAUDE.md"],
    # Frontend frameworks
    "react": ["rules/frontend/react/CLAUDE.md"],
    "nextjs": ["rules/frontend/nextjs/CLAUDE.md"],
    "vue": ["rules/frontend/vue/CLAUDE.md"],
    "angular": ["rules/frontend/angular/CLAUDE.md"],
    "svelte": ["rules/frontend/svelte/CLAUDE.md"],
    # RAG tools
    "llamaindex": ["rules/rag/orchestration/llamaindex/CLAUDE.md"],
    "pinecone": ["rules/rag/vector-managed/pinecone/CLAUDE.md"],
    "weaviate": ["rules/rag/vector-selfhosted/weaviate/CLAUDE.md"],
    "chroma": ["rules/rag/vector-selfhosted/chroma/CLAUDE.md"],
    "qdrant": ["rules/rag/vector-selfhosted/qdrant/CLAUDE.md"],
    "milvus": ["rules/rag/vector-selfhosted/milvus/CLAUDE.md"],
    "pgvector": ["rules/rag/vector-selfhosted/pgvector/CLAUDE.md"],
    "neo4j": ["rules/rag/graph/neo4j/CLAUDE.md"],
    # Infrastructure
    "docker": ["rules/containers/docker/CLAUDE.md"],
    "kubernetes": ["rules/containers/kubernetes/CLAUDE.md"],
    "terraform": ["rules/iac/terraform/CLAUDE.md"],
    "pulumi": ["rules/iac/pulumi/CLAUDE.md"],
    "github-actions": ["rules/cicd/github-actions/CLAUDE.md"],
    "gitlab-ci": ["rules/cicd/gitlab-ci/CLAUDE.md"],
}


def detect_project_stack(project_path: Path) -> ProjectStack:
    """Detect the technology stack of a project.

    Uses single-pass directory traversal for performance.

    Args:
        project_path: Path to the project root

    Returns:
        ProjectStack with detected technologies
    """
    stack = ProjectStack()
    project_path = Path(project_path)

    # Single traversal - collect and classify all files
    files_by_ext: dict[str, list[Path]] = {}  # "*.py" -> [files...]
    exact_files: set[str] = set()  # exact filenames found (e.g., "Dockerfile")

    for filepath in project_path.rglob("*"):
        if not filepath.is_file():
            continue

        name = filepath.name
        exact_files.add(name)

        # Build extension pattern (e.g., "*.py" from "foo.py")
        if "." in name:
            ext = name.rsplit(".", 1)[-1]
            ext_pattern = f"*.{ext}"
            files_by_ext.setdefault(ext_pattern, []).append(filepath)

    # Detect languages from collected file data
    for pattern, language in LANGUAGE_DETECTION.items():
        if pattern.startswith("*"):
            # Glob pattern - check our collected extension map
            if pattern in files_by_ext and files_by_ext[pattern]:
                stack.languages.add(language)
        else:
            # Exact file match - check our collected filenames
            if pattern in exact_files:
                stack.languages.add(language)

    # Detect frameworks from dependency files
    _detect_python_frameworks(project_path, stack)
    _detect_js_frameworks(project_path, stack)
    _detect_go_frameworks(project_path, stack)
    _detect_rust_frameworks(project_path, stack)

    # Detect infrastructure from collected file data
    for pattern, infra in INFRASTRUCTURE_DETECTION.items():
        if pattern.startswith("*"):
            # Glob pattern - check our collected extension map
            if pattern in files_by_ext and files_by_ext[pattern]:
                stack.infrastructure.add(infra)
        elif "/" in pattern:
            # Path-based check (e.g., ".github/workflows")
            if (project_path / pattern).exists():
                stack.infrastructure.add(infra)
        else:
            # Exact file match - check our collected filenames
            if pattern in exact_files:
                stack.infrastructure.add(infra)

    # Set AI/ML and RAG flags based on detected frameworks
    ai_ml_frameworks = {
        "langchain",
        "llamaindex",
        "crewai",
        "autogen",
        "transformers",
        "pytorch",
        "tensorflow",
        "mlflow",
        "bentoml",
        "ray",
    }
    rag_frameworks = {
        "langchain",
        "llamaindex",
        "pinecone",
        "weaviate",
        "chroma",
        "qdrant",
        "milvus",
        "pgvector",
        "neo4j",
    }

    stack.ai_ml = bool(stack.frameworks & ai_ml_frameworks)
    stack.rag = bool(stack.frameworks & rag_frameworks) or bool(stack.databases & rag_frameworks)

    logger.info(f"Detected stack: {stack.to_dict()}")
    return stack


def _detect_python_frameworks(project_path: Path, stack: ProjectStack) -> None:
    """Detect Python frameworks from requirements/pyproject."""
    deps: set[str] = set()

    # Check requirements.txt
    req_file = project_path / "requirements.txt"
    if req_file.exists():
        content = req_file.read_text()
        for line in content.splitlines():
            line = line.strip().lower()
            if line and not line.startswith("#"):
                # Extract package name (before any version specifier)
                pkg = line.split("==")[0].split(">=")[0].split("<=")[0].split("[")[0]
                deps.add(pkg.replace("-", "_").replace(".", "_"))

    # Check pyproject.toml
    pyproject = project_path / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text().lower()
        for pkg in FRAMEWORK_DETECTION:
            if pkg.lower() in content:
                deps.add(pkg.replace("-", "_"))

    # Map dependencies to frameworks
    for dep in deps:
        for pattern, (lang, framework) in FRAMEWORK_DETECTION.items():
            if pattern.replace("-", "_") in dep or dep in pattern.replace("-", "_"):
                if lang == "python":
                    stack.frameworks.add(framework)
                elif lang == "database":
                    stack.databases.add(framework)


def _detect_js_frameworks(project_path: Path, stack: ProjectStack) -> None:
    """Detect JavaScript/TypeScript frameworks from package.json."""
    pkg_file = project_path / "package.json"
    if not pkg_file.exists():
        return

    try:
        content = json.loads(pkg_file.read_text())
        all_deps = set()
        all_deps.update(content.get("dependencies", {}).keys())
        all_deps.update(content.get("devDependencies", {}).keys())

        for dep in all_deps:
            dep_lower = dep.lower()
            for pattern, (lang, framework) in FRAMEWORK_DETECTION.items():
                if pattern in dep_lower:
                    if lang in ("javascript", "typescript"):
                        stack.frameworks.add(framework)
                    elif lang == "database":
                        stack.databases.add(framework)
    except (json.JSONDecodeError, OSError):
        pass


def _detect_go_frameworks(project_path: Path, stack: ProjectStack) -> None:
    """Detect Go frameworks from go.mod."""
    go_mod = project_path / "go.mod"
    if not go_mod.exists():
        return

    content = go_mod.read_text().lower()
    # Add Go-specific framework detection as needed
    if "gin-gonic" in content:
        stack.frameworks.add("gin")
    if "echo" in content:
        stack.frameworks.add("echo")


def _detect_rust_frameworks(project_path: Path, stack: ProjectStack) -> None:
    """Detect Rust frameworks from Cargo.toml."""
    cargo = project_path / "Cargo.toml"
    if not cargo.exists():
        return

    content = cargo.read_text().lower()
    if "actix" in content:
        stack.frameworks.add("actix")
    if "axum" in content:
        stack.frameworks.add("axum")
    if "rocket" in content:
        stack.frameworks.add("rocket")


def get_required_rules(stack: ProjectStack) -> list[str]:
    """Get list of rule paths needed for the detected stack.

    Args:
        stack: Detected project stack

    Returns:
        List of rule file paths to fetch
    """
    rules: set[str] = set()

    # Always include core OWASP rules
    rules.update(RULE_PATHS.get("_core", []))

    # Add AI/ML rules if applicable
    if stack.ai_ml:
        rules.update(RULE_PATHS.get("ai_ml", []))

    # Add RAG rules if applicable
    if stack.rag:
        rules.update(RULE_PATHS.get("rag", []))

    # Add language-specific rules
    for lang in stack.languages:
        rules.update(RULE_PATHS.get(lang, []))

    # Add framework rules
    for framework in stack.frameworks:
        rules.update(RULE_PATHS.get(framework, []))

    # Add database rules
    for db in stack.databases:
        rules.update(RULE_PATHS.get(db, []))

    # Add infrastructure rules
    for infra in stack.infrastructure:
        rules.update(RULE_PATHS.get(infra, []))

    return sorted(rules)


def filter_rules_for_files(
    file_paths: list[str],
    rules_dir: str | Path = ".claude/rules/security",
) -> list[Path]:
    """Filter security rule files relevant to specific task files.

    Maps file extensions to languages, returns matching security rule paths.
    Always includes _core/owasp-2025.md for code implementation tasks.
    """
    rules_path = Path(rules_dir)
    result: list[Path] = []

    # Always include core OWASP rules
    core = rules_path / "_core" / "owasp-2025.md"
    if core.exists():
        result.append(core)

    # Detect languages from file extensions
    detected_langs: set[str] = set()
    has_docker = False

    for fp in file_paths:
        p = Path(fp)
        ext = p.suffix.lower()
        name = p.name.lower()

        # Map extensions to languages
        if ext in (".py", ".pyx", ".pyi"):
            detected_langs.add("python")
        elif ext in (".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx"):
            detected_langs.add("javascript")

        # Check for Docker
        if "dockerfile" in name or name.startswith("docker-compose"):
            has_docker = True

    # Map languages to rule files
    for lang in detected_langs:
        lang_rule = rules_path / "languages" / lang / "CLAUDE.md"
        if lang_rule.exists():
            result.append(lang_rule)

    if has_docker:
        docker_rule = rules_path / "containers" / "docker" / "CLAUDE.md"
        if docker_rule.exists():
            result.append(docker_rule)

    return result


def summarize_rules(rule_paths: list[Path], max_tokens: int = 2000) -> str:
    """Read and summarize security rules within token budget.

    Extracts ## Rule headers and **Level** lines only, skipping code blocks.
    Returns markdown summary.
    """
    parts: list[str] = []
    chars_budget = max_tokens * 4  # ~4 chars per token
    chars_used = 0

    for rule_path in rule_paths:
        if not rule_path.exists():
            continue

        content = rule_path.read_text()
        in_code_block = False
        file_parts: list[str] = []

        for line in content.split("\n"):
            # Track code blocks
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            # Include rule headers and level indicators
            if line.startswith("## Rule:") or line.startswith("### Rule:"):
                file_parts.append(line)
            elif line.startswith("**Level**:") or line.startswith("**Level**"):
                file_parts.append(line)
            elif line.startswith("**When**:") or line.startswith("**When**"):
                file_parts.append(line)

        if file_parts:
            section = f"### {rule_path.parent.name}/{rule_path.name}\n" + "\n".join(file_parts)
            if chars_used + len(section) <= chars_budget:
                parts.append(section)
                chars_used += len(section)

    return "\n\n".join(parts)


def fetch_rules(
    rule_paths: list[str],
    output_dir: Path,
    use_cache: bool = True,
) -> dict[str, Path]:
    """Fetch security rules from GitHub.

    Args:
        rule_paths: List of rule file paths to fetch
        output_dir: Directory to save fetched rules
        use_cache: Skip fetching if file already exists

    Returns:
        Dictionary mapping rule path to local file path
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fetched: dict[str, Path] = {}

    for rule_path in rule_paths:
        # Create local path preserving directory structure
        local_path = output_dir / rule_path.replace("rules/", "")
        local_path.parent.mkdir(parents=True, exist_ok=True)

        if use_cache and local_path.exists():
            logger.debug(f"Using cached rule: {rule_path}")
            fetched[rule_path] = local_path
            continue

        # Fetch from GitHub
        url = f"{RULES_RAW_URL}/{rule_path}"
        try:
            result = subprocess.run(
                ["curl", "-fsSL", url],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                local_path.write_text(result.stdout)
                fetched[rule_path] = local_path
                logger.info(f"Fetched rule: {rule_path}")
            else:
                logger.warning(f"Failed to fetch {rule_path}: {result.stderr}")
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout fetching {rule_path}")
        except Exception as e:
            logger.warning(f"Error fetching {rule_path}: {e}")

    return fetched


def generate_claude_md_section(
    stack: ProjectStack,
    rules_dir: Path,
) -> str:
    """Generate CLAUDE.md security rules section.

    Args:
        stack: Detected project stack
        rules_dir: Directory containing fetched rules

    Returns:
        Markdown content for CLAUDE.md
    """
    lines = [
        "# Security Rules",
        "",
        f"Auto-generated from [TikiTribe/claude-secure-coding-rules](https://github.com/{RULES_REPO})",
        "",
        "## Detected Stack",
        "",
    ]

    if stack.languages:
        lines.append(f"- **Languages**: {', '.join(sorted(stack.languages))}")
    if stack.frameworks:
        lines.append(f"- **Frameworks**: {', '.join(sorted(stack.frameworks))}")
    if stack.databases:
        lines.append(f"- **Databases**: {', '.join(sorted(stack.databases))}")
    if stack.infrastructure:
        lines.append(f"- **Infrastructure**: {', '.join(sorted(stack.infrastructure))}")
    if stack.ai_ml:
        lines.append("- **AI/ML**: Yes")
    if stack.rag:
        lines.append("- **RAG**: Yes")

    lines.extend(["", "## Fetched Rules", ""])

    # List fetched rule files for reference (no @-imports needed;
    # Claude Code auto-loads everything under .claude/rules/).
    rules_dir = Path(rules_dir)
    if rules_dir.exists():
        for rule_file in sorted(rules_dir.rglob("*.md")):
            rel_path = rule_file.relative_to(rules_dir)
            lines.append(f"- `{rel_path}`")

    lines.append("")
    return "\n".join(lines)


def integrate_security_rules(
    project_path: Path,
    output_dir: Path | None = None,
    update_claude_md: bool = True,
) -> dict[str, Any]:
    """Full integration: detect, fetch, and integrate security rules.

    Args:
        project_path: Path to the project root
        output_dir: Where to store rules (default: .claude/rules/security)
        update_claude_md: Whether to update/create CLAUDE.md

    Returns:
        Dictionary with integration results
    """
    project_path = Path(project_path)
    output_dir = output_dir or project_path / ".claude" / "rules" / "security"

    # Step 1: Detect stack
    logger.info("Detecting project stack...")
    stack = detect_project_stack(project_path)

    # Step 2: Get required rules
    rule_paths = get_required_rules(stack)
    logger.info(f"Identified {len(rule_paths)} relevant rule files")

    # Step 3: Fetch rules
    logger.info("Fetching security rules...")
    fetched = fetch_rules(rule_paths, output_dir)

    # Step 4: Generate CLAUDE.md section
    claude_md_section = generate_claude_md_section(stack, output_dir)

    # Step 5: Update CLAUDE.md if requested
    if update_claude_md:
        claude_md_path = project_path / "CLAUDE.md"
        _update_claude_md(claude_md_path, claude_md_section)

    return {
        "stack": stack.to_dict(),
        "rules_fetched": len(fetched),
        "rules_dir": str(output_dir),
        "rule_paths": list(fetched.keys()),
    }


def _update_claude_md(claude_md_path: Path, security_section: str) -> None:
    """Update or create CLAUDE.md with security rules section.

    Args:
        claude_md_path: Path to CLAUDE.md
        security_section: Security rules section content
    """
    marker_start = "<!-- SECURITY_RULES_START -->"
    marker_end = "<!-- SECURITY_RULES_END -->"

    if claude_md_path.exists():
        content = claude_md_path.read_text()

        # Check if markers exist
        if marker_start in content and marker_end in content:
            # Replace existing section
            import re

            pattern = f"{re.escape(marker_start)}.*?{re.escape(marker_end)}"
            replacement = f"{marker_start}\n{security_section}\n{marker_end}"
            content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        else:
            # Append section
            content = f"{content}\n\n{marker_start}\n{security_section}\n{marker_end}\n"
    else:
        # Create new file
        content = f"{marker_start}\n{security_section}\n{marker_end}\n"

    claude_md_path.write_text(content)
    logger.info(f"Updated {claude_md_path}")
