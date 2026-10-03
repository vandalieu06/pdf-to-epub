"""Validated configuration for a conversion run."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class ConversionOptions(BaseModel):
    """All knobs that drive the pdf -> docx -> epub pipeline."""

    input_pdf: Path
    output_epub: Path | None = None
    workdir: Path | None = None
    keep_intermediate: bool = False
    force: bool = False

    clean_headers_footers: bool = True
    header_margin: float | None = None
    footer_margin: float | None = None
    min_header_ratio: float = Field(default=0.5, ge=0.0, le=1.0)
    keep_tables: bool = False
    reflow_paragraphs: bool = True

    title: str | None = None
    author: str | None = None
    language: str = "es"
    identifier: str | None = None
    cover: Path | None = None

    keep_all_images: bool = False
    min_image_px: int = Field(default=24, ge=0)
    image_quality: int = Field(default=85, ge=1, le=100)
    keep_original_images: bool = False
    use_pdf_images: bool = True

    verbose: bool = False
    quiet: bool = False

    def resolved_output(self) -> Path:
        """Return the EPUB output path, defaulting to the input stem."""
        if self.output_epub is not None:
            return self.output_epub
        return self.input_pdf.with_name(self.input_pdf.stem + ".epub")

    def resolved_workdir(self) -> Path:
        """Return the directory used for intermediate artifacts."""
        if self.workdir is not None:
            return self.workdir
        return self.input_pdf.parent
