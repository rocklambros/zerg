"""Technology stack selection for Inception Mode.

This module handles technology recommendations and interactive selection
for new projects during the Inception Mode workflow.
"""

from dataclasses import dataclass, field
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from zerg.charter import ProjectCharter
from zerg.logging import get_logger

console = Console()
logger = get_logger(__name__)


# Supported primary languages with their ecosystems
SUPPORTED_LANGUAGES = {
    "python": {
        "name": "Python",
        "version": "3.12",
        "package_manager": "uv",
        "test_framework": "pytest",
        "linter": "ruff",
        "formatter": "ruff",
        "type_checker": "mypy",
    },
    "typescript": {
        "name": "TypeScript",
        "version": "5.x",
        "package_manager": "pnpm",
        "test_framework": "vitest",
        "linter": "eslint",
        "formatter": "prettier",
        "type_checker": "tsc",
    },
    "go": {
        "name": "Go",
        "version": "1.22",
        "package_manager": "go mod",
        "test_framework": "go test",
        "linter": "golangci-lint",
        "formatter": "gofmt",
        "type_checker": "go vet",
    },
    "rust": {
        "name": "Rust",
        "version": "stable",
        "package_manager": "cargo",
        "test_framework": "cargo test",
        "linter": "clippy",
        "formatter": "rustfmt",
        "type_checker": "cargo check",
    },
}


# Framework recommendations based on platform and language
FRAMEWORK_RECOMMENDATIONS: dict[str, dict[str, list[str]]] = {
    "python": {
        "api": ["fastapi", "flask", "django-rest"],
        "web": ["django", "flask", "fastapi"],
        "cli": ["typer", "click", "argparse"],
        "library": ["none"],
    },
    "typescript": {
        "api": ["fastify", "express", "nestjs", "hono"],
        "web": ["nextjs", "remix", "sveltekit"],
        "cli": ["commander", "oclif"],
        "library": ["none"],
    },
    "go": {
        "api": ["gin", "echo", "fiber", "chi"],
        "web": ["gin", "echo"],
        "cli": ["cobra", "urfave/cli"],
        "library": ["none"],
    },
    "rust": {
        "api": ["axum", "actix-web", "rocket"],
        "web": ["axum", "actix-web"],
        "cli": ["clap", "structopt"],
        "library": ["none"],
    },
}


# Default frameworks per platform (first recommendation)
DEFAULT_FRAMEWORKS: dict[str, dict[str, str]] = {
    "python": {"api": "fastapi", "web": "django", "cli": "typer", "library": ""},
    "typescript": {"api": "fastify", "web": "nextjs", "cli": "commander", "library": ""},
    "go": {"api": "gin", "web": "gin", "cli": "cobra", "library": ""},
    "rust": {"api": "axum", "web": "axum", "cli": "clap", "library": ""},
}


@dataclass
class TechStack:
    """Selected technology stack for a new project.

    Contains all technology choices needed to scaffold a complete project.
    """

    # Primary language and version
    language: str = ""
    language_version: str = ""

    # Package management
    package_manager: str = ""

    # Frameworks
    primary_framework: str = ""
    additional_frameworks: list[str] = field(default_factory=list)

    # Development tools
    test_framework: str = ""
    linter: str = ""
    formatter: str = ""
    type_checker: str = ""

    # Optional components
    database_driver: str = ""
    orm: str = ""
    http_client: str = ""

    # DevOps
    dockerfile: bool = True
    ci_provider: str = "github-actions"  # github-actions, gitlab-ci, none

    def to_dict(self) -> dict[str, Any]:
        """Convert tech stack to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "language": self.language,
            "language_version": self.language_version,
            "package_manager": self.package_manager,
            "primary_framework": self.primary_framework,
            "additional_frameworks": self.additional_frameworks,
            "test_framework": self.test_framework,
            "linter": self.linter,
            "formatter": self.formatter,
            "type_checker": self.type_checker,
            "database_driver": self.database_driver,
            "orm": self.orm,
            "http_client": self.http_client,
            "dockerfile": self.dockerfile,
            "ci_provider": self.ci_provider,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TechStack":
        """Create tech stack from dictionary.

        Args:
            data: Dictionary with tech stack data.

        Returns:
            TechStack instance.
        """
        return cls(
            language=data.get("language", ""),
            language_version=data.get("language_version", ""),
            package_manager=data.get("package_manager", ""),
            primary_framework=data.get("primary_framework", ""),
            additional_frameworks=data.get("additional_frameworks", []),
            test_framework=data.get("test_framework", ""),
            linter=data.get("linter", ""),
            formatter=data.get("formatter", ""),
            type_checker=data.get("type_checker", ""),
            database_driver=data.get("database_driver", ""),
            orm=data.get("orm", ""),
            http_client=data.get("http_client", ""),
            dockerfile=data.get("dockerfile", True),
            ci_provider=data.get("ci_provider", "github-actions"),
        )


def recommend_stack(charter: ProjectCharter) -> TechStack:
    """Generate technology stack recommendation based on project charter.

    Analyzes the project requirements and recommends an optimal tech stack.

    Args:
        charter: Project charter with gathered requirements.

    Returns:
        Recommended TechStack based on requirements.
    """
    stack = TechStack()

    # If language already specified in charter, use it
    if charter.primary_language and charter.primary_language in SUPPORTED_LANGUAGES:
        lang = charter.primary_language
    else:
        # Recommend based on platform and requirements
        lang = _recommend_language(charter)

    stack.language = lang
    lang_info = SUPPORTED_LANGUAGES.get(lang, SUPPORTED_LANGUAGES["python"])

    # Set language ecosystem defaults
    stack.language_version = lang_info["version"]
    stack.package_manager = lang_info["package_manager"]
    stack.test_framework = lang_info["test_framework"]
    stack.linter = lang_info["linter"]
    stack.formatter = lang_info["formatter"]
    stack.type_checker = lang_info["type_checker"]

    # Recommend framework based on platform
    primary_platform = charter.target_platforms[0] if charter.target_platforms else "api"
    stack.primary_framework = _recommend_framework(lang, primary_platform)

    # Set database/ORM if needed
    if charter.data_storage:
        stack.database_driver, stack.orm = _recommend_database_tools(lang, charter.data_storage)

    # DevOps settings
    stack.dockerfile = charter.containerized
    stack.ci_provider = "github-actions" if charter.ci_cd_needed else "none"

    logger.info(f"Recommended stack: {stack.language} with {stack.primary_framework}")
    return stack


def _recommend_language(charter: ProjectCharter) -> str:
    """Recommend primary language based on project requirements.

    Args:
        charter: Project charter.

    Returns:
        Recommended language key.
    """
    platforms = set(charter.target_platforms)

    # Performance-critical: prefer Go or Rust
    if charter.performance_needs == "high":
        if "cli" in platforms:
            return "go"
        return "rust"

    # API/web focus: Python is most versatile
    if platforms & {"api", "web"}:
        return "python"

    # CLI tools: Go or Python
    if "cli" in platforms:
        return "go"

    # Library/general: Python as default
    return "python"


def _recommend_framework(language: str, platform: str) -> str:
    """Recommend framework for language and platform.

    Args:
        language: Selected language.
        platform: Target platform.

    Returns:
        Recommended framework name.
    """
    defaults = DEFAULT_FRAMEWORKS.get(language, {})
    return defaults.get(platform, defaults.get("api", ""))


def _recommend_database_tools(language: str, storage: list[str]) -> tuple[str, str]:
    """Recommend database driver and ORM.

    Args:
        language: Selected language.
        storage: List of storage systems.

    Returns:
        Tuple of (driver, orm).
    """
    # Map storage to driver/ORM recommendations
    db_tools = {
        "python": {
            "postgresql": ("asyncpg", "sqlalchemy"),
            "mysql": ("aiomysql", "sqlalchemy"),
            "sqlite": ("aiosqlite", "sqlalchemy"),
            "mongodb": ("motor", ""),
            "redis": ("redis", ""),
        },
        "typescript": {
            "postgresql": ("pg", "prisma"),
            "mysql": ("mysql2", "prisma"),
            "sqlite": ("better-sqlite3", "prisma"),
            "mongodb": ("mongodb", "prisma"),
            "redis": ("ioredis", ""),
        },
        "go": {
            "postgresql": ("pgx", "sqlc"),
            "mysql": ("go-sql-driver/mysql", "sqlc"),
            "sqlite": ("mattn/go-sqlite3", ""),
            "mongodb": ("mongo-driver", ""),
            "redis": ("go-redis", ""),
        },
        "rust": {
            "postgresql": ("sqlx", "diesel"),
            "mysql": ("sqlx", "diesel"),
            "sqlite": ("sqlx", "diesel"),
            "mongodb": ("mongodb", ""),
            "redis": ("redis-rs", ""),
        },
    }

    lang_tools = db_tools.get(language, {})

    # Use first storage system for recommendation
    if storage:
        primary_db = storage[0].lower()
        tools = lang_tools.get(primary_db, ("", ""))
        return tools

    return ("", "")


def select_technology(charter: ProjectCharter) -> TechStack:
    """Interactively select technology stack with user confirmation.

    Shows recommendations and allows the user to modify selections.

    Args:
        charter: Project charter with requirements.

    Returns:
        Final selected TechStack.
    """
    # Get recommendations first
    recommended = recommend_stack(charter)

    console.print()
    console.print(
        Panel(
            "[bold cyan]Technology Stack Selection[/bold cyan]\n\n"
            "Based on your requirements, here's our recommendation.\n"
            "You can accept or modify each choice.",
            title="🔧 Tech Stack",
            border_style="cyan",
        )
    )
    console.print()

    # Show recommendation table
    table = Table(title="Recommended Stack", show_header=True, header_style="bold cyan")
    table.add_column("Component", style="dim")
    table.add_column("Recommendation", style="green")

    table.add_row("Language", f"{recommended.language} ({recommended.language_version})")
    table.add_row("Package Manager", recommended.package_manager)
    table.add_row("Framework", recommended.primary_framework or "none")
    table.add_row("Test Framework", recommended.test_framework)
    table.add_row("Linter", recommended.linter)
    table.add_row("Formatter", recommended.formatter)
    if recommended.orm:
        table.add_row("ORM", recommended.orm)
    if recommended.database_driver:
        table.add_row("Database Driver", recommended.database_driver)

    console.print(table)
    console.print()

    # Ask for language selection
    lang_choices = ", ".join(SUPPORTED_LANGUAGES.keys())
    console.print(f"[dim]Available languages: {lang_choices}[/dim]")

    selected_lang = Prompt.ask(
        "[bold]Primary language[/bold]",
        default=recommended.language,
    )

    # Validate language choice
    if selected_lang not in SUPPORTED_LANGUAGES:
        console.print(f"[yellow]Unknown language '{selected_lang}', using Python.[/yellow]")
        selected_lang = "python"

    # Update charter and regenerate if language changed
    if selected_lang != recommended.language:
        charter.primary_language = selected_lang
        recommended = recommend_stack(charter)

    # Ask for framework selection
    primary_platform = charter.target_platforms[0] if charter.target_platforms else "api"
    framework_options = FRAMEWORK_RECOMMENDATIONS.get(selected_lang, {}).get(primary_platform, [])

    if framework_options:
        opts = ", ".join(framework_options)
        console.print(f"\n[dim]Framework options for {primary_platform}: {opts}[/dim]")

    selected_framework = Prompt.ask(
        "[bold]Framework[/bold]",
        default=recommended.primary_framework or "none",
    )

    if selected_framework.lower() == "none":
        selected_framework = ""

    # Build final stack
    final_stack = TechStack(
        language=selected_lang,
        language_version=SUPPORTED_LANGUAGES[selected_lang]["version"],
        package_manager=SUPPORTED_LANGUAGES[selected_lang]["package_manager"],
        primary_framework=selected_framework,
        test_framework=SUPPORTED_LANGUAGES[selected_lang]["test_framework"],
        linter=SUPPORTED_LANGUAGES[selected_lang]["linter"],
        formatter=SUPPORTED_LANGUAGES[selected_lang]["formatter"],
        type_checker=SUPPORTED_LANGUAGES[selected_lang]["type_checker"],
        database_driver=recommended.database_driver,
        orm=recommended.orm,
        dockerfile=charter.containerized,
        ci_provider="github-actions" if charter.ci_cd_needed else "none",
    )

    # Update charter with final selections
    charter.primary_language = final_stack.language
    if final_stack.primary_framework:
        charter.frameworks = [final_stack.primary_framework]

    logger.info(f"Selected stack: {final_stack.language} with {final_stack.primary_framework}")
    return final_stack
