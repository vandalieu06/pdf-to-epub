"""Extract chapters from a DOCX as plain paragraphs (no XHTML, no images).

Used by consumers that need the text of a converted PDF for translation or
analysis, reusing the same heading detection as the EPUB splitter so chapter
boundaries always match the rich EPUB output.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from .epub.split import heading_level
from .models import TextChapter
from .text import normalize_text


def _paragraph_text(paragraph: Paragraph) -> str:
    """Plain text of a paragraph (concatenated runs, no markup)."""
    return normalize_text("".join(run.text for run in paragraph.runs))


def _table_text(table: Table) -> list[str]:
    """Flatten a table into paragraph texts (cell contents, reading order)."""
    lines: list[str] = []
    for row in table.rows:
        for cell in row.cells:
            text = " ".join(_paragraph_text(p) for p in cell.paragraphs).strip()
            if text:
                lines.append(text)
    return lines


def extract_docx_chapters(
    docx_path: str | Path,
    *,
    fallback_title: str = "Book",
) -> list[TextChapter]:
    """Split a DOCX into chapters as plain paragraphs.

    Images are ignored; tables are flattened to text. The heading detection is
    shared with ``epub.split.split_chapters`` so chapter boundaries stay in
    sync with the rich EPUB output.
    """
    document = Document(str(docx_path))
    chapters: list[TextChapter] = []
    order = 0
    current_title: str | None = None
    paragraphs: list[str] = []

    def flush() -> None:
        nonlocal order, current_title, paragraphs
        if current_title is None and not paragraphs:
            return
        title = current_title or fallback_title
        chapters.append(TextChapter(title=title, paragraphs=paragraphs, order=order))
        order += 1

    for item in document.iter_inner_content():
        if isinstance(item, Paragraph):
            level = heading_level(item)
            if level == 1:
                flush()
                current_title = normalize_text(item.text) or fallback_title
                paragraphs = []
                continue
            if level >= 2:
                heading = normalize_text(item.text)
                if heading:
                    paragraphs.append(heading)
                continue
            text = _paragraph_text(item)
            if text:
                paragraphs.append(text)
        elif isinstance(item, Table):
            paragraphs.extend(_table_text(item))

    flush()
    return chapters