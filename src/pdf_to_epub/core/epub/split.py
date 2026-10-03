"""Split an intermediate DOCX into EPUB chapters and render their XHTML."""

from __future__ import annotations

import html as html_lib
import re

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from ..docx.images import picture_rids
from ..models import Chapter, ImageAsset
from ..text import normalize_text

_CHAPTER_RE = re.compile(
    r"^(chapter|prologue|epilogue|interlude|part|volume|afterword|foreword"
    r"|cap[ií]tulo|pr[oó]logo|ep[ií]logo|parte|volumen|interludio)\b"
    r"|^cap(?:\.?\s*\d+|\b)",
    re.IGNORECASE,
)
_NUMBERED_CHAPTER_RE = re.compile(
    r"^(?:cap\.?\s*\d+|cap[ií]tulo\s*\d+|chapter\s*\d+)",
    re.IGNORECASE,
)
_MAX_CHAPTER_TITLE_LEN = 100
_SENTENCE_END = (".", ",", ";", ":", "!", "?")
_DOT_LEADER_RE = re.compile(r"\.{4,}")
_LEADING_QUOTES = "«»\"'“”‘’ \t"


def _heading_level(paragraph: Paragraph) -> int:
    """Return the heading level (0 = body paragraph)."""
    style_name = ""
    if paragraph.style is not None and paragraph.style.name:
        style_name = paragraph.style.name
    if style_name.startswith("Heading"):
        tail = style_name.split()[-1]
        try:
            return max(1, min(6, int(tail)))
        except ValueError:
            return 1
    if style_name == "Title":
        return 1
    raw = normalize_text(paragraph.text)
    if not raw or _DOT_LEADER_RE.search(raw):
        return 0
    text = raw.lstrip(_LEADING_QUOTES)
    if not text or len(text) > _MAX_CHAPTER_TITLE_LEN or not _CHAPTER_RE.match(text):
        return 0
    if text.endswith(_SENTENCE_END) and not _NUMBERED_CHAPTER_RE.match(text):
        return 0
    return 1


def _render_paragraph(paragraph: Paragraph, rel_to_file: dict[str, str]) -> str:
    pieces: list[str] = []
    for run in paragraph.runs:
        for rid in picture_rids(run._element):
            file_name = rel_to_file.get(rid)
            if file_name:
                pieces.append(f'<img src="{file_name}" alt=""/>')
        text = run.text
        if not text:
            continue
        escaped = html_lib.escape(text)
        if run.italic:
            escaped = f"<em>{escaped}</em>"
        if run.bold:
            escaped = f"<strong>{escaped}</strong>"
        pieces.append(escaped)
    content = "".join(pieces).strip()
    if not content:
        return ""
    return f"<p>{content}</p>"


def _render_table(table: Table, rel_to_file: dict[str, str]) -> str:
    rows: list[str] = []
    for row in table.rows:
        cells: list[str] = []
        for cell in row.cells:
            content = " ".join(
                _render_paragraph(p, rel_to_file) for p in cell.paragraphs
            ).strip()
            cells.append(f"<td>{content}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    if not rows:
        return ""
    return "<table>" + "".join(rows) + "</table>"


def split_chapters(
    document: Document,
    assets: list[ImageAsset],
    *,
    fallback_title: str = "Book",
    skip_rel_ids: set[str] | None = None,
) -> list[Chapter]:
    """Split a DOCX into chapters, rendering each body to XHTML.

    `skip_rel_ids` lists image relationships that must not be rendered inline (for
    example, the cover, which is promoted to the EPUB cover page).
    """
    skip = skip_rel_ids or set()
    rel_to_file = {
        a.rel_id: a.file_name for a in assets if a.rel_id and a.rel_id not in skip
    }
    chapters: list[Chapter] = []
    order = 0
    current_title: str | None = None
    body: list[str] = []

    def flush() -> None:
        nonlocal order, current_title, body
        if current_title is None and not body:
            return
        title = current_title or fallback_title
        html = "\n".join(body).strip()
        chapters.append(
            Chapter(
                title=title,
                html=html or f"<h1>{html_lib.escape(title)}</h1>",
                file_name=f"chapter_{order:04d}.xhtml",
                order=order,
            )
        )
        order += 1

    for item in document.iter_inner_content():
        if isinstance(item, Paragraph):
            level = _heading_level(item)
            if level == 1:
                flush()
                current_title = normalize_text(item.text) or fallback_title
                body = [f"<h1>{html_lib.escape(current_title)}</h1>"]
                continue
            if level >= 2:
                heading = normalize_text(item.text)
                if heading:
                    body.append(f"<h{level}>{html_lib.escape(heading)}</h{level}>")
                continue
            rendered = _render_paragraph(item, rel_to_file)
            if rendered:
                body.append(rendered)
        elif isinstance(item, Table):
            rendered_table = _render_table(item, rel_to_file)
            if rendered_table:
                body.append(rendered_table)

    flush()
    return chapters
