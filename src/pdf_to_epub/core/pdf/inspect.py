"""Read and normalize PDF metadata using PyMuPDF."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pymupdf

from ..models import PdfMetadata, TextBlock

_PDF_DATE_RE = re.compile(r"D:(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?")


def parse_pdf_date(value: str | None) -> datetime | None:
    """Parse a PDF `D:YYYYMMDD...` date string into a datetime (best effort)."""
    if not value:
        return None
    match = _PDF_DATE_RE.search(value)
    if match is None:
        return None
    year_s, month_s, day_s, hour_s, minute_s, second_s = match.groups()
    try:
        return datetime(
            int(year_s),
            int(month_s) if month_s else 1,
            int(day_s) if day_s else 1,
            int(hour_s) if hour_s else 0,
            int(minute_s) if minute_s else 0,
            int(second_s) if second_s else 0,
        )
    except ValueError:
        return None


def split_authors(value: str | None) -> list[str]:
    """Split a PDF author string into individual names.

    Only `;` is used as a separator. A comma is not treated as a separator because
    "Austen, Jane" is a single author in `Lastname, Firstname` form; users with
    multiple authors can pass `--author` explicitly.
    """
    if not value:
        return []
    parts = value.split(";")
    return [part.strip() for part in parts if part.strip()]


def split_keywords(value: str | None) -> list[str]:
    """Split a PDF keywords string into a list of subjects."""
    if not value:
        return []
    parts = re.split(r"[;,]", value)
    return [part.strip() for part in parts if part.strip()]


def read_metadata(path: Path) -> PdfMetadata:
    """Open a PDF and return its normalized metadata."""
    with pymupdf.open(path) as doc:
        raw = doc.metadata or {}
        return PdfMetadata(
            title=(raw.get("title") or "").strip() or None,
            authors=split_authors(raw.get("author")),
            subject=(raw.get("subject") or "").strip() or None,
            keywords=split_keywords(raw.get("keywords")),
            creator=(raw.get("creator") or "").strip() or None,
            producer=(raw.get("producer") or "").strip() or None,
            creation_date=parse_pdf_date(raw.get("creationDate")),
            mod_date=parse_pdf_date(raw.get("modDate")),
            page_count=doc.page_count,
        )


def iter_text_blocks(doc: pymupdf.Document) -> list[TextBlock]:
    """Return all text blocks of a document with page-relative coordinates."""
    blocks: list[TextBlock] = []
    for page_index, page in enumerate(doc):
        for block in page.get_text("blocks"):
            x0, y0, x1, y1, text, _block_no, block_type = block
            if block_type != 0:
                continue
            if not text.strip():
                continue
            blocks.append(
                TextBlock(page=page_index, x0=x0, y0=y0, x1=x1, y1=y1, text=text)
            )
    return blocks
