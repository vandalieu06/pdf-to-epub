"""Typer command-line interface for pdf-to-epub."""

from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console

from . import __version__
from .core.config import ConversionOptions
from .core.errors import (
    DocxStageError,
    EpubStageError,
    PdfStageError,
    PipelineError,
    ValidationError,
)
from .core.pipeline import run

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Convert light-novel PDFs to EPUB via an editable DOCX intermediate format.",
)
console = Console()
err_console = Console(stderr=True)

_EXIT_CODES: dict[type[PipelineError], int] = {
    ValidationError: 1,
    PdfStageError: 3,
    DocxStageError: 4,
    EpubStageError: 5,
}


def _parse_margin(value: str | None, option: str) -> float | None:
    if value is None:
        return None
    text = value.strip().lower()
    if text == "auto":
        return None
    try:
        margin = float(text)
    except ValueError as exc:
        raise typer.BadParameter(f"{option} must be a number or 'auto'") from exc
    if not 0.0 <= margin < 1.0:
        raise typer.BadParameter(f"{option} must be in [0, 1)")
    return margin


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"pdf-to-epub {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """pdf-to-epub command-line interface."""


@app.command()
def convert(
    input_pdf: Path = typer.Argument(..., help="Input PDF file."),
    output: Path | None = typer.Option(
        None, "-o", "--output", help="Output EPUB path (default: input with .epub)."
    ),
    workdir: Path | None = typer.Option(
        None, "--workdir", help="Directory for intermediate files (default: input's dir)."
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing output."),
    keep_intermediate: bool = typer.Option(
        False,
        "--keep-intermediate/--clean-intermediate",
        help="Keep the .clean.pdf and .docx intermediates (default: remove on success).",
    ),
    no_clean: bool = typer.Option(
        False, "--no-clean", help="Disable header/footer removal."
    ),
    keep_tables: bool = typer.Option(
        False, "--keep-tables", help="Do not repair false-positive one-row tables."
    ),
    no_reflow: bool = typer.Option(
        False, "--no-reflow", help="Do not split/merge paragraphs."
    ),
    header_margin: str | None = typer.Option(
        None, "--header-margin", help="Top margin band as a fraction, or 'auto'."
    ),
    footer_margin: str | None = typer.Option(
        None, "--footer-margin", help="Bottom margin band as a fraction, or 'auto'."
    ),
    min_header_ratio: float = typer.Option(
        0.5, "--min-header-ratio", help="Fraction of pages a repeated line must appear on."
    ),
    title: str | None = typer.Option(None, "--title", help="Override the EPUB title."),
    author: str | None = typer.Option(None, "--author", help="Override the EPUB author."),
    language: str = typer.Option("es", "--language", help="EPUB language code."),
    identifier: str | None = typer.Option(
        None, "--identifier", help="Override the EPUB identifier."
    ),
    cover: Path | None = typer.Option(None, "--cover", help="Image file to use as cover."),
    keep_all_images: bool = typer.Option(
        False, "--keep-all-images", help="Do not filter small/decorative images."
    ),
    min_image_px: int = typer.Option(
        24, "--min-image-px", help="Minimum image side to keep (pixels)."
    ),
    image_quality: int = typer.Option(
        85, "--image-quality", help="JPEG quality for opaque images (1-100)."
    ),
    keep_original_images: bool = typer.Option(
        False, "--keep-original-images", help="Do not re-encode images (keep originals)."
    ),
    keep_docx_images: bool = typer.Option(
        False, "--keep-docx-images", help="Do not use the original PDF images."
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Only print errors."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Debug logging."),
) -> None:
    """Convert INPUT_PDF to EPUB."""
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARNING)

    options = ConversionOptions(
        input_pdf=input_pdf,
        output_epub=output,
        workdir=workdir,
        force=force,
        keep_intermediate=keep_intermediate,
        clean_headers_footers=not no_clean,
        keep_tables=keep_tables,
        reflow_paragraphs=not no_reflow,
        header_margin=_parse_margin(header_margin, "--header-margin"),
        footer_margin=_parse_margin(footer_margin, "--footer-margin"),
        min_header_ratio=min_header_ratio,
        title=title,
        author=author,
        language=language,
        identifier=identifier,
        cover=cover,
        keep_all_images=keep_all_images,
        min_image_px=min_image_px,
        image_quality=image_quality,
        keep_original_images=keep_original_images,
        use_pdf_images=not keep_docx_images,
        verbose=verbose,
        quiet=quiet,
    )

    def progress(message: str) -> None:
        if not quiet:
            console.print(f"[dim]… {message}[/dim]")

    try:
        report = run(options, progress=progress)
    except PipelineError as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(_EXIT_CODES.get(type(exc), 1)) from exc
    except OSError as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(6) from exc

    if quiet:
        return

    console.print(f"[green]✓[/green] {report.output_epub}")
    parts = [
        f"{report.chapters} chapters",
        f"{report.images_embedded} images",
        f"{report.header_footer_removals} header/footer lines removed",
    ]
    if report.repaired_tables:
        parts.append(f"{report.repaired_tables} false-positive tables repaired")
    if report.header_footer_images:
        parts.append(f"{report.header_footer_images} margin images removed")
    if report.split_paragraphs or report.merged_paragraphs:
        parts.append(
            f"{report.split_paragraphs} paragraphs split, "
            f"{report.merged_paragraphs} merged"
        )
    parts.append(f"{report.elapsed_s:.1f}s")
    console.print(" · ".join(parts))

    if report.ignored_pages:
        pages = ", ".join(str(page) for page in report.ignored_pages)
        console.print(f"[yellow]warning:[/yellow] pdf2docx ignored pages {pages}")

    if options.keep_intermediate:
        for path in (report.clean_pdf_path, report.docx_path):
            if path is not None and path.exists():
                console.print(f"[dim]kept: {path}[/dim]")
    else:
        console.print(
            "[dim]intermediates removed (use --keep-intermediate to keep them)[/dim]"
        )


if __name__ == "__main__":  # pragma: no cover
    app()
