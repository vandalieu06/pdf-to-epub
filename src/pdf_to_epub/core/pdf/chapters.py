"""Detect chapter boundaries directly in the PDF.

Most PDFs expose chapter starts as a real outline (`doc.get_toc()`). Some light
novels render the chapter title as an image and keep an invisible text layer behind
it; `pdf2docx` drops that layer, so the DOCX has no heading. This module recovers
those boundaries from the PDF text blocks that overlap an image.
"""

from __future__ import annotations

import re
from pathlib import Path

import pymupdf

from ..epub.split import chapter_title
from ..models import PdfChapterStart
from ..text import normalize_text

_OUTLINE_SKIP_RE = re.compile(
    r"^(cover|title\s*page|table\s*of\s*contents|contents|copyright|dedication"
    r"|portada|índice|indice|créditos|creditos)\b",
    re.IGNORECASE,
)
_MIN_OVERLAP_RATIO = 0.5
_MIN_OUTLINE_ENTRIES = 2


def _read_outline(doc: pymupdf.Document) -> list[PdfChapterStart]:
    """Return level-1 outline entries, or an empty list when there is no useful TOC."""
    try:
        entries = doc.get_toc(simple=True)
    except Exception:  # noqa: BLE001 - broken outline should not break conversion
        return []
    chapters: list[PdfChapterStart] = []
    seen_pages: set[int] = set()
    for level, raw_title, page in entries:
        if level != 1:
            continue
        title = normalize_text(raw_title or "")
        if not title or _OUTLINE_SKIP_RE.match(title):
            continue
        if not isinstance(page, int) or page < 1 or page > doc.page_count:
            continue
        if page in seen_pages:
            continue
        seen_pages.add(page)
        chapters.append(PdfChapterStart(page=page, title=title, source="outline"))
    if len(chapters) < _MIN_OUTLINE_ENTRIES:
        return []
    return chapters


def _image_boxes(page: pymupdf.Page) -> list[tuple[float, float, float, float]]:
    boxes: list[tuple[float, float, float, float]] = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 1:
            continue
        x0, y0, x1, y1 = block["bbox"]
        boxes.append((x0, y0, x1, y1))
    return boxes


def _overlaps_image(
    box: tuple[float, float, float, float],
    image_boxes: list[tuple[float, float, float, float]],
) -> bool:
    x0, y0, x1, y1 = box
    area = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    if area <= 0:
        return False
    for ix0, iy0, ix1, iy1 in image_boxes:
        width = max(0.0, min(x1, ix1) - max(x0, ix0))
        height = max(0.0, min(y1, iy1) - max(y0, iy0))
        if width * height / area >= _MIN_OVERLAP_RATIO:
            return True
    return False


def _read_hidden(doc: pymupdf.Document) -> list[PdfChapterStart]:
    """Find chapter titles hidden behind an image (image-covered text layer)."""
    chapters: list[PdfChapterStart] = []
    for page_index, page in enumerate(doc, start=1):
        image_boxes = _image_boxes(page)
        if not image_boxes:
            continue
        for block in page.get_text("blocks"):
            x0, y0, x1, y1, raw_text, _block_no, block_type = block
            if block_type != 0:
                continue
            title = chapter_title(raw_text)
            if title is None:
                continue
            if not _overlaps_image((x0, y0, x1, y1), image_boxes):
                continue
            chapters.append(
                PdfChapterStart(page=page_index, title=title, source="hidden")
            )
            break
    return chapters


def read_pdf_chapters(
    pdf_path: str | Path, *, allow_hidden: bool = True
) -> list[PdfChapterStart]:
    """Return chapter starts detected in the PDF.

    The outline wins when it has at least two level-1 entries. Otherwise, and only
    when ``allow_hidden`` is true, image-covered text blocks are scanned.
    """
    try:
        with pymupdf.open(str(pdf_path)) as doc:
            outline = _read_outline(doc)
            if outline:
                return outline
            if not allow_hidden:
                return []
            return _read_hidden(doc)
    except Exception:  # noqa: BLE001 - best effort; conversion can continue without it
        return []
