"""Detect and remove repeated headers/footers from a PDF via redaction.

A PDF has no semantic header/footer: they are ordinary text positioned in the top
and bottom bands of each page. We detect them because they repeat across pages at a
similar vertical position, and remove them with redaction annotations so the text is
gone before `pdf2docx` ever sees it.

Repeated *images* in the margins (logos, scan banners) are handled separately by
`core/pdf/images.py` and dropped from the EPUB, because redacting them in the PDF can
also remove illustrations that overlap the same band.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from ..models import HeaderFooterCandidate, HeaderFooterReport
from ..text import normalize_text

DEFAULT_MARGIN = 0.08
MAX_BLOCK_AREA_RATIO = 0.15

Block = tuple[float, float, float, float, str]


def fingerprint(text: str) -> str:
    """Normalize a margin line, masking digit runs so page numbers compare equal."""
    return re.sub(r"\d+", "#", normalize_text(text)).lower()


@dataclass(slots=True)
class PageGeometry:
    """The text blocks and dimensions of a single PDF page."""

    index: int
    width: float
    height: float
    blocks: list[Block] = field(default_factory=list)


@dataclass(slots=True)
class DetectionResult:
    """Candidate header/footer lines and the rectangles to redact."""

    candidates: list[HeaderFooterCandidate] = field(default_factory=list)
    removals: list[tuple[int, float, float, float, float]] = field(default_factory=list)


def detect_headers_footers(
    pages: list[PageGeometry],
    *,
    header_margin: float = DEFAULT_MARGIN,
    footer_margin: float = DEFAULT_MARGIN,
    min_ratio: float = 0.5,
    max_block_area_ratio: float = MAX_BLOCK_AREA_RATIO,
) -> DetectionResult:
    """Find repeated/page-number-like blocks inside the top and bottom margin bands."""
    page_count = len(pages)
    result = DetectionResult()
    if page_count == 0:
        return result

    min_pages = max(2, math.ceil(page_count * min_ratio))
    band_blocks: list[tuple[int, Block, str, str, str]] = []

    for page in pages:
        page_area = page.width * page.height
        top_limit = page.height * header_margin
        bottom_limit = page.height * (1.0 - footer_margin)
        for block in page.blocks:
            x0, y0, x1, y1, text = block
            normalized = normalize_text(text)
            if not normalized:
                continue
            center_y = (y0 + y1) / 2.0
            if center_y <= top_limit:
                kind = "header"
            elif center_y >= bottom_limit:
                kind = "footer"
            else:
                continue
            block_area = max(0.0, x1 - x0) * max(0.0, y1 - y0)
            if page_area > 0 and block_area / page_area > max_block_area_ratio:
                continue
            band_blocks.append(
                (page.index, block, normalized, kind, fingerprint(normalized))
            )

    occurrences: dict[str, list[tuple[int, Block, str, str]]] = defaultdict(list)
    for page_index, block, normalized, kind, key in band_blocks:
        occurrences[key].append((page_index, block, normalized, kind))

    for _key, entries in occurrences.items():
        pages_found = sorted({entry[0] for entry in entries})
        if len(pages_found) >= min_pages:
            result.candidates.append(
                HeaderFooterCandidate(text=entries[0][2], kind=entries[0][3], pages=pages_found)
            )
            result.removals.extend(_removal(entry[1], entry[0]) for entry in entries)

    return result


def _removal(block: Block, page_index: int) -> tuple[int, float, float, float, float]:
    x0, y0, x1, y1, _text = block
    return (page_index, x0, y0, x1, y1)


def _apply_redactions(page: pymupdf.Page) -> None:
    kwargs: dict[str, object] = {}
    images_mode = getattr(pymupdf, "PDF_REDACT_IMAGE_NONE", None)
    graphics_mode = getattr(pymupdf, "PDF_REDACT_LINE_ART_NONE", None)
    if images_mode is not None:
        kwargs["images"] = images_mode
    if graphics_mode is not None:
        kwargs["graphics"] = graphics_mode
    try:
        page.apply_redactions(**kwargs)
    except TypeError:  # pragma: no cover - older PyMuPDF signatures
        page.apply_redactions()


def clean_pdf(
    path: Path,
    *,
    clean_path: Path | None = None,
    header_margin: float | None = None,
    footer_margin: float | None = None,
    min_ratio: float = 0.5,
    progress: Callable[[str], None] | None = None,
) -> tuple[Path, HeaderFooterReport]:
    """Detect and redact repeated headers/footers.

    Returns the path to the cleaned PDF (or the original when nothing matched) and a
    report describing what was found and removed.
    """
    header_margin = DEFAULT_MARGIN if header_margin is None else header_margin
    footer_margin = DEFAULT_MARGIN if footer_margin is None else footer_margin
    report = HeaderFooterReport(header_margin=header_margin, footer_margin=footer_margin)

    if progress:
        progress("Detecting headers/footers")

    with pymupdf.open(path) as doc:
        pages: list[PageGeometry] = []
        for page_index, page in enumerate(doc):
            blocks: list[Block] = []
            for block in page.get_text("blocks"):
                x0, y0, x1, y1, text, _block_no, block_type = block
                if block_type != 0 or not text.strip():
                    continue
                blocks.append((x0, y0, x1, y1, text))
            pages.append(
                PageGeometry(
                    index=page_index,
                    width=page.rect.width,
                    height=page.rect.height,
                    blocks=blocks,
                )
            )

        detection = detect_headers_footers(
            pages,
            header_margin=header_margin,
            footer_margin=footer_margin,
            min_ratio=min_ratio,
        )

        if not detection.removals:
            report.clean_pdf = path
            return path, report

        unique: dict[tuple[int, int, int, int, int], tuple[int, float, float, float, float]] = {}
        for removal in detection.removals:
            page_index, x0, y0, x1, y1 = removal
            key = (page_index, round(x0), round(y0), round(x1), round(y1))
            unique.setdefault(key, removal)

        for page_index, x0, y0, x1, y1 in unique.values():
            doc[page_index].add_redact_annot(pymupdf.Rect(x0, y0, x1, y1))
        for page in doc:
            _apply_redactions(page)

        target = clean_path or path.with_name(path.stem + ".clean.pdf")
        target.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(target), garbage=3, deflate=True)

    report.applied = True
    report.clean_pdf = target
    report.candidates = detection.candidates
    report.redacted_pages = sorted({removal[0] for removal in unique.values()})
    return target, report
