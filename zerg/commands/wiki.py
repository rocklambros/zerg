"""ZERG wiki command - generate complete documentation wiki."""

from pathlib import Path

import click
from rich.console import Console

from zerg.logging import get_logger

console = Console()
logger = get_logger("wiki")

DEFAULT_OUTPUT = ".zerg/wiki"


@click.command()
@click.option(
    "--full",
    is_flag=True,
    help="Regenerate all pages from scratch (default: incremental)",
)
@click.option(
    "--push",
    is_flag=True,
    help="Push generated wiki to {repo}.wiki.git",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview what would be generated without writing files",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=DEFAULT_OUTPUT,
    help=f"Output directory for wiki pages (default: {DEFAULT_OUTPUT})",
)
@click.pass_context
def wiki(
    ctx: click.Context,
    full: bool,
    push: bool,
    dry_run: bool,
    output: str,
) -> None:
    """Generate a complete documentation wiki for the ZERG project.

    Scans the project, generates markdown pages for all components,
    and optionally pushes to the GitHub Wiki.

    Examples:

        zerg wiki --full

        zerg wiki --dry-run

        zerg wiki --full --push

        zerg wiki --output docs/wiki/
    """
    from zerg.doc_engine.crossref import CrossRefBuilder
    from zerg.doc_engine.dependencies import DependencyMapper
    from zerg.doc_engine.detector import ComponentDetector
    from zerg.doc_engine.extractor import SymbolExtractor
    from zerg.doc_engine.mermaid import MermaidGenerator
    from zerg.doc_engine.renderer import DocRenderer
    from zerg.doc_engine.sidebar import SidebarGenerator

    try:
        console.print("\n[bold cyan]ZERG Wiki Generator[/bold cyan]\n")

        output_dir = Path(output)
        mode = "full" if full else "incremental"
        console.print(f"Mode: [cyan]{mode}[/cyan]")
        console.print(f"Output: [cyan]{output_dir}[/cyan]")

        if dry_run:
            console.print("[yellow]Dry run mode - no files will be written[/yellow]\n")

        # Create output directory
        if not dry_run:
            output_dir.mkdir(parents=True, exist_ok=True)

        # Discover documentable components
        project_root = Path(".")
        ComponentDetector()
        SymbolExtractor()
        mapper = DependencyMapper()
        _mermaid = MermaidGenerator()
        renderer = DocRenderer()
        crossref = CrossRefBuilder()
        sidebar_gen = SidebarGenerator()

        # Build project-wide dependency map
        mapper.build(project_root / "zerg")

        # Find Python source files
        py_files = sorted((project_root / "zerg").rglob("*.py"))
        py_files = [f for f in py_files if not f.name.startswith("__")]

        pages: dict[str, str] = {}
        generated = 0

        for source_file in py_files:
            page_name = source_file.stem
            try:
                content = renderer.render(source_file)
                pages[page_name] = content
                generated += 1

                if not dry_run:
                    page_path = output_dir / f"{page_name}.md"
                    page_path.write_text(content)

            except Exception as e:
                logger.warning("Failed to generate page for %s: %s", source_file, e)
                continue

        console.print(f"Generated {generated} pages from {len(py_files)} source files")

        # Cross-references
        glossary = crossref.build_glossary(pages)
        if not dry_run and glossary:
            glossary_content = crossref.generate_glossary_page(glossary)
            (output_dir / "Glossary.md").write_text(glossary_content)
            pages["Glossary"] = glossary_content

        # Sidebar
        sidebar_pages = [{"name": name, "section": "Reference"} for name in sorted(pages.keys())]
        sidebar_content = sidebar_gen.generate(sidebar_pages)
        if not dry_run:
            (output_dir / "_Sidebar.md").write_text(sidebar_content)

        console.print(f"[green]Wiki generation complete: {len(pages)} pages[/green]")

        # Push if requested
        if push:
            from zerg.doc_engine.publisher import WikiPublisher

            publisher = WikiPublisher()
            # Detect repo URL from git remote
            import subprocess

            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                console.print("[red]Error:[/red] Could not detect git remote URL")
                raise SystemExit(1)

            repo_url = result.stdout.strip()
            # Convert to wiki URL
            if repo_url.endswith(".git"):
                wiki_url = repo_url[:-4] + ".wiki.git"
            else:
                wiki_url = repo_url + ".wiki.git"

            pub_result = publisher.publish(output_dir, wiki_url, dry_run=dry_run)
            if pub_result.success:
                console.print(f"[green]Pushed {pub_result.pages_copied} pages to wiki[/green]")
            else:
                console.print(f"[red]Push failed:[/red] {pub_result.error}")
                raise SystemExit(1)

    except SystemExit:
        raise
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        logger.exception("Wiki command failed")
        raise SystemExit(1) from e
