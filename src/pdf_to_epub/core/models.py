"""Domain models shared across pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class PdfMetadata:
    """Normalized metadata read from the source PDF."""

    title: str | None = None
    authors: list[str] = field(default_factory=list)
    subject: str | None = None
    keywords: list[str] = field(default_factory=list)
    creator: str | None = None
    producer: str | None = None
    creation_date: datetime | None = None
    mod_date: datetime | None = None
    language: str | None = None
    page_count: int = 0


@dataclass(slots=True)
class TextBlock:
    """A text block with its position on a page."""

    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    text: str


@dataclass(slots=True)
class HeaderFooterCandidate:
    """A repeated (or page-number-like) block found in a page margin band."""

    text: str
    kind: str
    pages: list[int] = field(default_factory=list)


@dataclass(slots=True)
class HeaderFooterReport:
    """Outcome of the header/footer detection and redaction pass."""

    applied: bool = False
    clean_pdf: Path | None = None
    header_margin: float = 0.0
    footer_margin: float = 0.0
    candidates: list[HeaderFooterCandidate] = field(default_factory=list)
    redacted_pages: list[int] = field(default_factory=list)

    @property
    def removal_count(self) -> int:
        return sum(len(c.pages) for c in self.candidates)


@dataclass(slots=True)
class ImageAsset:
    """An image extracted from the intermediate DOCX."""

    uid: str
    file_name: str
    media_type: str
    data: bytes
    width: float | None = None
    height: float | None = None
    position_index: int = 0
    is_cover: bool = False
    sha256: str = ""
    rel_id: str = ""


@dataclass(slots=True)
class Chapter:
    """A chapter of the generated EPUB."""

    title: str
    html: str
    file_name: str
    order: int = 0


@dataclass(slots=True)
class DocxCleanReport:
    """Outcome of the DOCX cleanup pass."""

    cleared_headers_footers: int = 0
    removed_paragraphs: int = 0
    repaired_tables: int = 0
    split_paragraphs: int = 0
    merged_paragraphs: int = 0


@dataclass(slots=True)
class ReflowReport:
    """Outcome of the paragraph reflow pass."""

    split_paragraphs: int = 0
    merged_paragraphs: int = 0


@dataclass(slots=True)
class ConversionReport:
    """Summary reported at the end of a conversion run."""

    input_pdf: Path
    output_epub: Path | None = None
    docx_path: Path | None = None
    clean_pdf_path: Path | None = None
    title: str | None = None
    author: str | None = None
    language: str | None = None
    chapters: int = 0
    images_extracted: int = 0
    images_embedded: int = 0
    images_dropped: int = 0
    images_from_pdf: int = 0
    ignored_pages: list[int] = field(default_factory=list)
    header_footer_removals: int = 0
    header_footer_images: int = 0
    cleared_headers_footers: int = 0
    removed_paragraphs: int = 0
    repaired_tables: int = 0
    split_paragraphs: int = 0
    merged_paragraphs: int = 0
    elapsed_s: float = 0.0
