"""Inception Mode orchestration - scaffold new projects from scratch.

This module coordinates the full Inception Mode workflow: requirements gathering,
technology selection, and project scaffolding.
"""

import re
import subprocess
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel

from zerg.charter import ProjectCharter, gather_requirements, write_project_md
from zerg.logging import get_logger
from zerg.tech_selector import TechStack, select_technology

console = Console()
logger = get_logger(__name__)

# Path to scaffold templates
SCAFFOLDS_DIR = Path(__file__).parent / "scaffolds"


def scaffold_project(
    charter: ProjectCharter,
    stack: TechStack,
    output_dir: Path | None = None,
) -> dict[str, Path]:
    """Generate project scaffold from templates.

    Renders all template files for the selected language/framework,
    substituting project-specific values.

    Args:
        charter: Project charter with requirements.
        stack: Selected technology stack.
        output_dir: Output directory. Defaults to current directory.

    Returns:
        Dictionary mapping relative paths to created file paths.
    """
    output_dir = output_dir or Path(".")
    output_dir = output_dir.resolve()

    language = stack.language
    template_dir = SCAFFOLDS_DIR / language

    if not template_dir.exists():
        logger.warning(f"No scaffolds found for language: {language}")
        return {}

    # Prepare template context
    context = _build_template_context(charter, stack)

    created_files: dict[str, Path] = {}

    # Process all template files
    for template_path in template_dir.glob("*.template"):
        # Determine output filename (remove .template suffix)
        output_name = template_path.stem

        # Handle special cases
        if output_name == "gitignore":
            output_name = ".gitignore"

        # Determine output path
        if output_name in ("main.py", "__init__.py"):
            # Python source files go in package directory
            pkg_dir = output_dir / context["project_name_snake"]
            pkg_dir.mkdir(parents=True, exist_ok=True)
            output_path = pkg_dir / output_name
        elif output_name.startswith("test_"):
            # Test files go in tests directory
            tests_dir = output_dir / "tests"
            tests_dir.mkdir(parents=True, exist_ok=True)
            output_path = tests_dir / output_name
            # Also create tests/__init__.py
            (tests_dir / "__init__.py").write_text("")
        elif output_name in ("index.ts", "index.test.ts"):
            # TypeScript source files go in src directory
            src_dir = output_dir / "src"
            src_dir.mkdir(parents=True, exist_ok=True)
            output_path = src_dir / output_name
        elif output_name in ("main.go", "main_test.go"):
            # Go files stay at root
            output_path = output_dir / output_name
        elif output_name == "main.rs":
            # Rust source files go in src directory
            src_dir = output_dir / "src"
            src_dir.mkdir(parents=True, exist_ok=True)
            output_path = src_dir / output_name
        else:
            # Config files stay at root
            output_path = output_dir / output_name

        # Read and render template
        template_content = template_path.read_text()
        rendered_content = _render_template(template_content, context)

        # Write rendered file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered_content)

        rel_path = str(output_path.relative_to(output_dir))
        created_files[rel_path] = output_path
        logger.debug(f"Created: {rel_path}")

    console.print(f"  [green]✓[/green] Created {len(created_files)} scaffold files")

    return created_files


def _build_template_context(charter: ProjectCharter, stack: TechStack) -> dict[str, Any]:
    """Build template rendering context from charter and stack.

    Args:
        charter: Project charter.
        stack: Technology stack.

    Returns:
        Dictionary of template variables.
    """
    # Convert project name to various formats
    project_name = charter.name
    project_name_snake = _to_snake_case(project_name)
    project_name_kebab = _to_kebab_case(project_name)

    return {
        # Project identity
        "project_name": project_name,
        "project_name_snake": project_name_snake,
        "project_name_kebab": project_name_kebab,
        "description": charter.description,
        "purpose": charter.purpose,
        # Technology
        "language": stack.language,
        "language_version": stack.language_version,
        "framework": stack.primary_framework,
        "test_framework": stack.test_framework,
        "linter": stack.linter,
        "formatter": stack.formatter,
        # Database
        "database_driver": stack.database_driver,
        "orm": stack.orm,
        # DevOps
        "dockerfile": stack.dockerfile,
        "ci_provider": stack.ci_provider,
        # Charter details
        "security_level": charter.security_level,
        "testing_strategy": charter.testing_strategy,
    }


def _render_template(template: str, context: dict[str, Any]) -> str:
    """Render a simple Jinja-like template.

    Supports:
    - {{ variable }} - variable substitution
    - {% if condition %}...{% endif %} - conditionals
    - {% elif condition %}...{% endif %} - elif
    - {% else %}...{% endif %} - else

    Args:
        template: Template string.
        context: Variables for substitution.

    Returns:
        Rendered string.
    """
    result = template

    # Process conditionals first (simple single-level)
    result = _process_conditionals(result, context)

    # Then substitute variables
    for key, value in context.items():
        placeholder = "{{ " + key + " }}"
        result = result.replace(placeholder, str(value) if value else "")

    # Replace any remaining unresolved variables with empty string
    result = re.sub(r"\{\{\s*\w+\s*\}\}", "", result)

    # Clean up empty lines from conditionals
    lines = result.split("\n")
    cleaned_lines = []
    for line in lines:
        # Skip lines that are just whitespace from removed conditionals
        if line.strip() or not line:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def _process_conditionals(template: str, context: dict[str, Any]) -> str:
    """Process {% if %}, {% elif %}, {% else %}, {% endif %} blocks.

    Args:
        template: Template with conditionals.
        context: Variables for evaluation.

    Returns:
        Template with conditionals resolved.
    """
    # Pattern to match if/elif/else/endif blocks
    # This handles nested structures properly
    result = template

    # Simple approach: process from innermost to outermost
    max_iterations = 100
    iteration = 0

    while iteration < max_iterations:
        # Find the innermost if block (one without nested ifs)
        pattern = r"\{%\s*if\s+(.+?)\s*%\}((?:(?!\{%\s*if).)*?)\{%\s*endif\s*%\}"
        match = re.search(pattern, result, re.DOTALL)

        if not match:
            break

        condition = match.group(1).strip()
        block_content = match.group(2)

        # Parse the block for elif/else
        resolved = _resolve_if_block(condition, block_content, context)

        # Replace the entire if block with resolved content
        result = result[: match.start()] + resolved + result[match.end() :]
        iteration += 1

    return result


def _resolve_if_block(condition: str, block_content: str, context: dict[str, Any]) -> str:
    """Resolve a single if/elif/else block.

    Args:
        condition: The if condition.
        block_content: Content between if and endif (may contain elif/else).
        context: Variables for evaluation.

    Returns:
        The appropriate content based on conditions.
    """
    # Split by elif and else
    parts = re.split(r"\{%\s*(?:elif|else)\s*", block_content)

    # First part is the if body
    if_body = parts[0] if parts else ""

    # Check if condition is true
    if _evaluate_condition(condition, context):
        return if_body.rstrip()

    # Process elif/else parts
    remaining = block_content[len(if_body) :]

    # Find elif conditions
    elif_pattern = r"\{%\s*elif\s+(.+?)\s*%\}((?:(?!\{%\s*(?:elif|else)).)*)"
    for match in re.finditer(elif_pattern, remaining, re.DOTALL):
        elif_condition = match.group(1).strip()
        elif_body = match.group(2)
        if _evaluate_condition(elif_condition, context):
            return elif_body.rstrip()

    # Check for else
    else_match = re.search(r"\{%\s*else\s*%\}(.*)$", remaining, re.DOTALL)
    if else_match:
        return else_match.group(1).rstrip()

    return ""


def _evaluate_condition(condition: str, context: dict[str, Any]) -> bool:
    """Evaluate a simple template condition.

    Supports:
    - variable (truthy check)
    - variable == 'value'
    - variable in ['a', 'b']

    Args:
        condition: Condition string.
        context: Variables.

    Returns:
        Boolean result.
    """
    condition = condition.strip()

    # Handle 'in' operator: variable in ['a', 'b']
    in_match = re.match(r"(\w+)\s+in\s+\[([^\]]+)\]", condition)
    if in_match:
        var_name = in_match.group(1)
        values_str = in_match.group(2)
        # Parse the list values
        values = [v.strip().strip("'\"") for v in values_str.split(",")]
        var_value = context.get(var_name, "")
        return str(var_value) in values

    # Handle equality: variable == 'value'
    eq_match = re.match(r"(\w+)\s*==\s*['\"](.+?)['\"]", condition)
    if eq_match:
        var_name = eq_match.group(1)
        expected = eq_match.group(2)
        return str(context.get(var_name, "")) == expected

    # Handle inequality: variable != 'value'
    neq_match = re.match(r"(\w+)\s*!=\s*['\"](.+?)['\"]", condition)
    if neq_match:
        var_name = neq_match.group(1)
        expected = neq_match.group(2)
        return str(context.get(var_name, "")) != expected

    # Simple truthy check
    value = context.get(condition, False)
    return bool(value)


def _to_snake_case(name: str) -> str:
    """Convert name to snake_case.

    Args:
        name: Input name.

    Returns:
        snake_case version.
    """
    # Replace hyphens and spaces with underscores
    result = re.sub(r"[-\s]+", "_", name)
    # Insert underscores before uppercase letters
    result = re.sub(r"([a-z])([A-Z])", r"\1_\2", result)
    return result.lower()


def _to_kebab_case(name: str) -> str:
    """Convert name to kebab-case.

    Args:
        name: Input name.

    Returns:
        kebab-case version.
    """
    # Replace underscores and spaces with hyphens
    result = re.sub(r"[_\s]+", "-", name)
    # Insert hyphens before uppercase letters
    result = re.sub(r"([a-z])([A-Z])", r"\1-\2", result)
    return result.lower()


def run_inception_mode(security_level: str = "standard") -> bool:
    """Run the full Inception Mode workflow.

    Orchestrates:
    1. Requirements gathering (conversational)
    2. Technology selection (with recommendations)
    3. Project scaffolding (file generation)
    4. ZERG infrastructure setup
    5. Git initialization

    Args:
        security_level: Security level for ZERG config.

    Returns:
        True if inception completed successfully.
    """
    console.print()
    console.print(
        Panel(
            "[bold cyan]ZERG Inception Mode[/bold cyan]\n\n"
            "Starting a new project from scratch.\n"
            "I'll guide you through requirements and setup.",
            title="🥚 Inception",
            border_style="cyan",
        )
    )

    try:
        # Step 1: Gather requirements
        console.print("\n[bold]Step 1: Requirements Gathering[/bold]")
        charter = gather_requirements()

        # Step 2: Select technology
        console.print("\n[bold]Step 2: Technology Selection[/bold]")
        stack = select_technology(charter)

        # Step 3: Generate scaffold
        console.print("\n[bold]Step 3: Project Scaffolding[/bold]")
        created_files = scaffold_project(charter, stack)

        if not created_files:
            console.print("[yellow]Warning: No scaffold files created[/yellow]")

        # Step 4: Write PROJECT.md
        console.print("\n[bold]Step 4: Documentation[/bold]")
        project_md = write_project_md(charter)
        console.print(f"  [green]✓[/green] Created {project_md}")

        # Step 5: Initialize git if not already
        console.print("\n[bold]Step 5: Git Initialization[/bold]")
        _init_git_repo()

        # Step 6: Show summary
        _show_inception_summary(charter, stack, created_files)

        console.print("\n[green]✓[/green] Inception complete!")
        console.print("\nNext steps:")
        console.print(f"  1. Run [cyan]cd {charter.name}[/cyan] (if needed)")
        console.print("  2. Run [cyan]zerg plan <feature>[/cyan] to plan your first feature")
        console.print("  3. Run [cyan]zerg design[/cyan] to create the task graph")
        console.print("  4. Run [cyan]zerg rush[/cyan] to execute!")

        return True

    except KeyboardInterrupt:
        console.print("\n[yellow]Inception cancelled.[/yellow]")
        return False
    except Exception as e:
        console.print(f"\n[red]Error during inception:[/red] {e}")
        logger.exception("Inception failed")
        return False


def _init_git_repo() -> None:
    """Initialize git repository if not already initialized."""
    if Path(".git").exists():
        console.print("  [dim]Git already initialized[/dim]")
        return

    try:
        subprocess.run(
            ["git", "init", "-q"],
            capture_output=True,
            check=True,
        )
        console.print("  [green]✓[/green] Initialized git repository")

        # Create initial commit if there are files
        subprocess.run(
            ["git", "add", "-A"],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-q", "-m", "Initial commit (ZERG Inception)"],
            capture_output=True,
            check=True,
        )
        console.print("  [green]✓[/green] Created initial commit")
    except subprocess.CalledProcessError as e:
        logger.warning(f"Git initialization failed: {e}")
        console.print("  [yellow]⚠[/yellow] Could not initialize git")
    except FileNotFoundError:
        console.print("  [yellow]⚠[/yellow] Git not found")


def _show_inception_summary(
    charter: ProjectCharter,
    stack: TechStack,
    created_files: dict[str, Path],
) -> None:
    """Display summary of inception results.

    Args:
        charter: Project charter.
        stack: Selected technology stack.
        created_files: Files that were created.
    """
    from rich.table import Table

    console.print()

    table = Table(title=f"Project: {charter.name}", show_header=False)
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    table.add_row("Language", f"{stack.language} ({stack.language_version})")
    if stack.primary_framework:
        table.add_row("Framework", stack.primary_framework)
    table.add_row("Package Manager", stack.package_manager)
    table.add_row("Test Framework", stack.test_framework)
    table.add_row("Files Created", str(len(created_files)))

    if charter.target_platforms:
        table.add_row("Platforms", ", ".join(charter.target_platforms))

    console.print(table)
