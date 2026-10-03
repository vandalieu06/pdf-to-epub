"""Orchestrate the pdf -> docx -> epub pipeline."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from docx import Document

from .config import ConversionOptions
from .docx.clean import clean_document
from .docx.convert import DocxConversionError, to_docx
from .docx.images import apply_pdf_images, extract_images, optimize_images
from .epub.builder import build_epub
from .epub.split import split_chapters
from .errors import DocxStageError, EpubStageError, PdfStageError, ValidationError
from .models import ConversionReport
from .pdf.headers_footers import clean_pdf
from .pdf.images import extract_pdf_images
from .pdf.inspect import read_metadata

ProgressCallback = Callable[[str], None]


def _validate(options: ConversionOptions) -> None:
    pdf = options.input_pdf
    if not pdf.exists() or not pdf.is_file():
        raise ValidationError(f"input PDF not found: {pdf}")
    if pdf.suffix.lower() != ".pdf":
        raise ValidationError(f"input is not a PDF: {pdf}")
    output = options.resolved_output()
    if output.exists() and not options.force:
        raise ValidationError(f"output already exists: {output} (use --force to overwrite)")


def _cleanup(paths: list[Path | None]) -> None:
    for path in paths:
        if path is not None and path.exists():
            try:
                path.unlink()
            except OSError:
                pass


def run(
    options: ConversionOptions,
    *,
    progress: ProgressCallback | None = None,
) -> ConversionReport:
    """Run the full pipeline and return a conversion report."""
    start = time.monotonic()
    _validate(options)

    input_pdf = options.input_pdf
    workdir = options.resolved_workdir()
    try:
        workdir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ValidationError(f"cannot create workdir {workdir}: {exc}") from exc

    report = ConversionReport(input_pdf=input_pdf)

    # Stage 1: read metadata.
    try:
        metadata = read_metadata(input_pdf)
    except Exception as exc:  # noqa: BLE001
        raise PdfStageError(f"cannot read PDF metadata from {input_pdf}: {exc}") from exc

    report.title = options.title or metadata.title
    report.author = options.author or (metadata.authors[0] if metadata.authors else None)
    report.language = options.language or metadata.language

    # Stage 2: clean headers/footers in the PDF.
    clean_path = input_pdf
    if options.clean_headers_footers:
        try:
            clean_path, hf_report = clean_pdf(
                input_pdf,
                clean_path=workdir / (input_pdf.stem + ".clean.pdf"),
                header_margin=options.header_margin,
                footer_margin=options.footer_margin,
                min_ratio=options.min_header_ratio,
                progress=progress,
            )
        except Exception as exc:  # noqa: BLE001
            raise PdfStageError(f"failed to clean headers/footers: {exc}") from exc
        report.header_footer_removals = hf_report.removal_count
        if clean_path != input_pdf:
            report.clean_pdf_path = clean_path

    # Stage 3: PDF -> DOCX.
    docx_path = workdir / (input_pdf.stem + ".docx")
    try:
        conversion = to_docx(clean_path, docx_path, progress=progress)
    except DocxConversionError as exc:
        raise DocxStageError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise DocxStageError(f"failed to convert to DOCX: {exc}") from exc
    report.docx_path = docx_path
    report.ignored_pages = conversion.ignored_pages

    # Stage 4: clean DOCX, extract images, split chapters.
    try:
        clean_report = clean_document(
            docx_path,
            repair_tables=not options.keep_tables,
            reflow=options.reflow_paragraphs,
            progress=progress,
        )
        document = Document(str(docx_path))
        extraction = extract_images(
            document,
            min_px=options.min_image_px,
            keep_all=options.keep_all_images,
        )
        banner_rel_ids: set[str] = set()
        if options.use_pdf_images:
            try:
                pdf_images = extract_pdf_images(clean_path)
            except Exception:  # noqa: BLE001 - best effort
                pdf_images = []
            if pdf_images:
                (
                    extraction.assets,
                    banner_rel_ids,
                    substituted,
                    dropped_references,
                ) = apply_pdf_images(
                    extraction.assets,
                    document,
                    pdf_images,
                    page_count=metadata.page_count,
                    min_image_px=options.min_image_px,
                )
                report.header_footer_images = dropped_references
                report.images_from_pdf = substituted
        if not options.keep_original_images:
            if progress:
                progress("Optimizing images")
            extraction.assets = optimize_images(
                extraction.assets, quality=options.image_quality
            )
        fallback_title = options.title or metadata.title or input_pdf.stem
        cover_rel_ids = (
            {extraction.assets[0].rel_id}
            if extraction.assets and extraction.assets[0].rel_id
            else set()
        )
        chapters = split_chapters(
            document,
            extraction.assets,
            fallback_title=fallback_title,
            skip_rel_ids=cover_rel_ids | banner_rel_ids,
        )
    except Exception as exc:  # noqa: BLE001
        raise DocxStageError(f"failed to process DOCX: {exc}") from exc

    report.cleared_headers_footers = clean_report.cleared_headers_footers
    report.removed_paragraphs = clean_report.removed_paragraphs
    report.repaired_tables = clean_report.repaired_tables
    report.split_paragraphs = clean_report.split_paragraphs
    report.merged_paragraphs = clean_report.merged_paragraphs
    report.images_extracted = extraction.found
    report.images_dropped = extraction.dropped
    report.images_embedded = len(extraction.assets)
    report.chapters = len(chapters)

    # Stage 5: DOCX -> EPUB.
    try:
        output = build_epub(
            chapters, extraction.assets, metadata, options, progress=progress
        )
    except Exception as exc:  # noqa: BLE001
        raise EpubStageError(f"failed to build EPUB: {exc}") from exc
    report.output_epub = output
    report.elapsed_s = time.monotonic() - start

    if not options.keep_intermediate:
        _cleanup(
            [
                report.clean_pdf_path,
                docx_path,
            ]
        )

    return report
