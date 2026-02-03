"""Project charter for Inception Mode - requirements gathering and documentation.

This module handles conversational requirements gathering and PROJECT.md generation
for the Inception Mode workflow when starting a new project from scratch.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from zerg.logging import get_logger

console = Console()
logger = get_logger(__name__)


@dataclass
class ProjectCharter:
    """Project charter containing gathered requirements and project metadata.

    This dataclass captures all information needed to bootstrap a new project,
    gathered through conversational prompts during Inception Mode.
    """

    # Core identity
    name: str = ""
    description: str = ""
    purpose: str = ""  # What problem does this solve?

    # Technical requirements
    primary_language: str = ""
    target_platforms: list[str] = field(default_factory=list)  # web, cli, api, mobile
    frameworks: list[str] = field(default_factory=list)

    # Architecture
    architecture_style: str = ""  # monolith, microservices, serverless
    data_storage: list[str] = field(default_factory=list)  # postgresql, redis, etc.

    # Non-functional requirements
    performance_needs: str = ""  # low, medium, high
    security_level: str = "standard"  # minimal, standard, strict
    scalability: str = ""  # single-user, team, enterprise

    # Development preferences
    testing_strategy: str = ""  # minimal, standard, comprehensive
    ci_cd_needed: bool = True
    containerized: bool = True

    # Additional context
    constraints: list[str] = field(default_factory=list)
    integrations: list[str] = field(default_factory=list)  # external systems
    notes: str = ""

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    created_by: str = "zerg-inception"

    def to_dict(self) -> dict[str, Any]:
        """Convert charter to dictionary for serialization.

        Returns:
            Dictionary representation of the charter.
        """
        return {
            "name": self.name,
            "description": self.description,
            "purpose": self.purpose,
            "primary_language": self.primary_language,
            "target_platforms": self.target_platforms,
            "frameworks": self.frameworks,
            "architecture_style": self.architecture_style,
            "data_storage": self.data_storage,
            "performance_needs": self.performance_needs,
            "security_level": self.security_level,
            "scalability": self.scalability,
            "testing_strategy": self.testing_strategy,
            "ci_cd_needed": self.ci_cd_needed,
            "containerized": self.containerized,
            "constraints": self.constraints,
            "integrations": self.integrations,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectCharter":
        """Create charter from dictionary.

        Args:
            data: Dictionary with charter data.

        Returns:
            ProjectCharter instance.
        """
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            purpose=data.get("purpose", ""),
            primary_language=data.get("primary_language", ""),
            target_platforms=data.get("target_platforms", []),
            frameworks=data.get("frameworks", []),
            architecture_style=data.get("architecture_style", ""),
            data_storage=data.get("data_storage", []),
            performance_needs=data.get("performance_needs", ""),
            security_level=data.get("security_level", "standard"),
            scalability=data.get("scalability", ""),
            testing_strategy=data.get("testing_strategy", ""),
            ci_cd_needed=data.get("ci_cd_needed", True),
            containerized=data.get("containerized", True),
            constraints=data.get("constraints", []),
            integrations=data.get("integrations", []),
            notes=data.get("notes", ""),
            created_at=created_at,
            created_by=data.get("created_by", "zerg-inception"),
        )


def gather_requirements() -> ProjectCharter:
    """Interactively gather project requirements through Rich prompts.

    Guides the user through a conversational flow to capture all necessary
    information for project scaffolding.

    Returns:
        Populated ProjectCharter with user's requirements.
    """
    charter = ProjectCharter()

    console.print()
    console.print(
        Panel(
            "[bold cyan]ZERG Inception Mode[/bold cyan]\n\n"
            "Let's gather some information about your new project.\n"
            "Press Enter to use defaults, or type your answers.",
            title="🥚 New Project",
            border_style="cyan",
        )
    )
    console.print()

    # Core identity
    charter.name = Prompt.ask(
        "[bold]Project name[/bold]",
        default=Path.cwd().name or "my-project",
    )

    charter.description = Prompt.ask(
        "[bold]Brief description[/bold]",
        default="A new project created with ZERG",
    )

    charter.purpose = Prompt.ask(
        "[bold]What problem does this solve?[/bold]",
        default="",
    )

    # Target platform
    console.print("\n[dim]Target platforms (comma-separated): web, api, cli, mobile, library[/dim]")
    platforms_input = Prompt.ask(
        "[bold]Target platforms[/bold]",
        default="api",
    )
    charter.target_platforms = [p.strip() for p in platforms_input.split(",") if p.strip()]

    # Architecture
    console.print("\n[dim]Architecture: monolith, microservices, serverless, library[/dim]")
    charter.architecture_style = Prompt.ask(
        "[bold]Architecture style[/bold]",
        default="monolith",
    )

    # Data storage
    console.print("\n[dim]Data storage (comma-separated): postgresql, mysql, sqlite, mongodb, redis, none[/dim]")
    storage_input = Prompt.ask(
        "[bold]Data storage[/bold]",
        default="none",
    )
    if storage_input.lower() != "none":
        charter.data_storage = [s.strip() for s in storage_input.split(",") if s.strip()]

    # Non-functional requirements
    console.print("\n[dim]Performance needs: low, medium, high[/dim]")
    charter.performance_needs = Prompt.ask(
        "[bold]Performance needs[/bold]",
        default="medium",
    )

    console.print("\n[dim]Security level: minimal, standard, strict[/dim]")
    charter.security_level = Prompt.ask(
        "[bold]Security level[/bold]",
        default="standard",
    )

    console.print("\n[dim]Scalability: single-user, team, enterprise[/dim]")
    charter.scalability = Prompt.ask(
        "[bold]Expected scale[/bold]",
        default="team",
    )

    # Development preferences
    console.print("\n[dim]Testing strategy: minimal, standard, comprehensive[/dim]")
    charter.testing_strategy = Prompt.ask(
        "[bold]Testing strategy[/bold]",
        default="standard",
    )

    charter.ci_cd_needed = Confirm.ask(
        "[bold]Include CI/CD configuration?[/bold]",
        default=True,
    )

    charter.containerized = Confirm.ask(
        "[bold]Include Docker/container support?[/bold]",
        default=True,
    )

    # External integrations
    console.print("\n[dim]External integrations (comma-separated, or 'none')[/dim]")
    integrations_input = Prompt.ask(
        "[bold]External integrations[/bold]",
        default="none",
    )
    if integrations_input.lower() != "none":
        charter.integrations = [i.strip() for i in integrations_input.split(",") if i.strip()]

    # Additional notes
    charter.notes = Prompt.ask(
        "[bold]Any additional notes or constraints?[/bold]",
        default="",
    )

    logger.info(f"Requirements gathered for project: {charter.name}")
    return charter


def write_project_md(charter: ProjectCharter, output_dir: Path | None = None) -> Path:
    """Generate PROJECT.md from the charter.

    Creates a comprehensive project documentation file in .gsd/PROJECT.md
    that serves as the single source of truth for project requirements.

    Args:
        charter: Populated ProjectCharter with requirements.
        output_dir: Directory to write PROJECT.md. Defaults to .gsd/

    Returns:
        Path to the created PROJECT.md file.
    """
    output_dir = output_dir or Path(".gsd")
    output_dir.mkdir(parents=True, exist_ok=True)

    project_md_path = output_dir / "PROJECT.md"

    # Build the markdown content
    lines = [
        f"# {charter.name}",
        "",
        f"> {charter.description}",
        "",
        "## Overview",
        "",
    ]

    if charter.purpose:
        lines.extend(
            [
                "### Problem Statement",
                "",
                charter.purpose,
                "",
            ]
        )

    # Technical specifications
    lines.extend(
        [
            "## Technical Specifications",
            "",
            f"- **Primary Language**: {charter.primary_language or 'TBD'}",
        ]
    )

    if charter.target_platforms:
        lines.append(f"- **Target Platforms**: {', '.join(charter.target_platforms)}")

    if charter.frameworks:
        lines.append(f"- **Frameworks**: {', '.join(charter.frameworks)}")

    lines.append(f"- **Architecture**: {charter.architecture_style or 'TBD'}")

    if charter.data_storage:
        lines.append(f"- **Data Storage**: {', '.join(charter.data_storage)}")

    lines.append("")

    # Non-functional requirements
    lines.extend(
        [
            "## Non-Functional Requirements",
            "",
            f"- **Performance**: {charter.performance_needs or 'medium'}",
            f"- **Security Level**: {charter.security_level}",
            f"- **Scalability**: {charter.scalability or 'team'}",
            "",
        ]
    )

    # Development configuration
    lines.extend(
        [
            "## Development Configuration",
            "",
            f"- **Testing Strategy**: {charter.testing_strategy or 'standard'}",
            f"- **CI/CD**: {'Yes' if charter.ci_cd_needed else 'No'}",
            f"- **Containerized**: {'Yes' if charter.containerized else 'No'}",
            "",
        ]
    )

    # Integrations
    if charter.integrations:
        lines.extend(
            [
                "## External Integrations",
                "",
            ]
        )
        for integration in charter.integrations:
            lines.append(f"- {integration}")
        lines.append("")

    # Constraints
    if charter.constraints:
        lines.extend(
            [
                "## Constraints",
                "",
            ]
        )
        for constraint in charter.constraints:
            lines.append(f"- {constraint}")
        lines.append("")

    # Notes
    if charter.notes:
        lines.extend(
            [
                "## Additional Notes",
                "",
                charter.notes,
                "",
            ]
        )

    # Metadata
    lines.extend(
        [
            "---",
            "",
            f"*Generated by ZERG Inception Mode on {charter.created_at.strftime('%Y-%m-%d %H:%M')}*",
            "",
        ]
    )

    # Write the file
    content = "\n".join(lines)
    project_md_path.write_text(content)

    logger.info(f"Created PROJECT.md at {project_md_path}")
    return project_md_path
