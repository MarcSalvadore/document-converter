"""CLI Entry point for Document Converter Engine."""

import os
import sys
import time
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel

# Support execution both as package `python -m converter_engine.main` and direct `python main.py`
try:
    from converter_engine.core.router import DocumentRouter
except ImportError:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from converter_engine.core.router import DocumentRouter

app = typer.Typer(
    name="document-converter",
    help="Convert DOCX, PPTX, and PDF documents into semantically structured Markdown.",
    add_completion=False,
)
console = Console()


@app.command()
def convert(
    input_path: str = typer.Option(
        ...,
        "-i",
        "--input",
        help="Path to input document file (DOCX, PPTX, or PDF).",
    ),
    output_path: Optional[str] = typer.Option(
        None,
        "-o",
        "--output",
        help="Path to destination Markdown file (.md). If omitted, output is printed to console.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Display verbose execution status, detected format, and parse timing.",
    ),
):
    """Convert input document (DOCX, PPTX, PDF) to clean Markdown."""
    start_time = time.perf_counter()
    router = DocumentRouter()

    if not os.path.exists(input_path):
        console.print(f"[bold red]Error:[/bold red] File not found at '{input_path}'", sys.stderr)
        raise typer.Exit(code=1)

    try:
        if verbose:
            console.print(f"[cyan][INFO][/cyan] Ingesting file: [bold]{input_path}[/bold]")
            detected_type = router.detect_file_type(input_path)
            console.print(f"[cyan][INFO][/cyan] Detected document type: [bold uppercase]{detected_type}[/bold uppercase]")

        markdown_content = router.convert(input_path)
        elapsed = time.perf_counter() - start_time

        if verbose:
            console.print(f"[green][SUCCESS][/green] Conversion completed in [bold]{elapsed:.3f}s[/bold]")

        if output_path:
            # Ensure output parent directory exists
            parent_dir = os.path.dirname(output_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            console.print(
                f"[bold green]Converted successfully![/bold green] Output saved to: [underline]{output_path}[/underline]"
            )
        else:
            if verbose:
                console.print(Panel(markdown_content, title="Markdown Output", expand=False))
            else:
                sys.stdout.write(markdown_content)

    except Exception as e:
        console.print(f"[bold red]Conversion Error:[/bold red] {e}", sys.stderr)
        if verbose:
            console.print_exception()
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
