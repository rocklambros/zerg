"""ZERG document command - generate documentation for individual components."""

from pathlib import Path

import click
from rich.console import Console

from zerg.logging import get_logger

console = Console()
logger = get_logger("document")


@click.command()
@click.argument("target", required=True)
@click.option(
    "--type",
    "component_type",
    type=click.Choice(["auto", "module", "command", "config", "api", "types"]),
    default="auto",
    help="Component type override (default: auto-detect)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output path for generated docs (default: stdout)",
)
@click.option(
    "--depth",
    type=click.Choice(["shallow", "standard", "deep"]),
    default="standard",
    help="Documentation depth level",
)
@click.option(
    "--update",
    is_flag=True,
    help="Update existing documentation in-place",
)
@click.pass_context
def document(
    ctx: click.Context,
    target: str,
    component_type: str,
    output: str | None,
    depth: str,
    update: bool,
) -> None:
    """Generate documentation for a specific component, module, or command.

    TARGET is the path to the file or module to document.

    Examples:

        zerg document zerg/launcher.py

        zerg document zerg/doc_engine/extractor.py --depth deep

        zerg document zerg/data/commands/rush.md --type command
    """
    from zerg.doc_engine.crossref import CrossRefBuilder
    from zerg.doc_engine.dependencies import DependencyMapper
    from zerg.doc_engine.detector import ComponentDetector
    from zerg.doc_engine.extractor import SymbolExtractor
    from zerg.doc_engine.mermaid import MermaidGenerator
    from zerg.doc_engine.renderer import DocRenderer

    try:
        target_path = Path(target)
        if not target_path.exists():
            console.print(f"[red]Error:[/red] File not found: {target}")
            raise SystemExit(1)

        console.print(f"\n[bold cyan]ZERG Document[/bold cyan] - {target}\n")

        # 1. Detect component type
        detector = ComponentDetector()
        if component_type == "auto":
            detected = detector.detect(target_path)
            console.print(f"Detected type: [cyan]{detected.value}[/cyan]")
        else:
            from zerg.doc_engine.detector import ComponentType

            detected = ComponentType(component_type)
            console.print(f"Using type: [cyan]{detected.value}[/cyan]")

        # 2. Extract symbols
        extractor = SymbolExtractor()
        symbols = extractor.extract(target_path)
        console.print(f"Extracted {len(symbols.classes)} classes, {len(symbols.functions)} functions")

        # 3. Map dependencies
        mapper = DependencyMapper()
        mapper.build(target_path.parent)

        # 4. Generate diagrams
        _mermaid = MermaidGenerator()

        # 5. Render documentation
        renderer = DocRenderer()
        content = renderer.render(target_path)

        # 6. Cross-reference (basic - no glossary in single-file mode)
        _crossref = CrossRefBuilder()

        # Output
        if output:
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content)
            console.print(f"\n[green]Documentation written to {output_path}[/green]")
        else:
            console.print("\n" + content)

    except SystemExit:
        raise
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        logger.exception("Document command failed")
        raise SystemExit(1) from e
