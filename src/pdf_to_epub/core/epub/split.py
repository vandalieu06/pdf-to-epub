"""Split an intermediate DOCX into EPUB chapters and render their XHTML."""

from __future__ import annotations

import html as html_lib
import re
from typing import Any, cast

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
_CHAPTER_NUMBER_RE = re.compile(
    r"(?:cap[ií]tulo|chapter|cap\.?)\s*0*(\d+)",
    re.IGNORECASE,
)
_MAX_CHAPTER_TITLE_LEN = 100
_SENTENCE_END = (".", ",", ";", ":", "!", "?")
_DOT_LEADER_RE = re.compile(r"\.{4,}")
_LEADING_QUOTES = "«»\"'“”‘’ \t"
_H1_RE = re.compile(r"^\s*<h1\b.*?</h1>", re.IGNORECASE | re.DOTALL)
_STUB_MAX_CHARS = 1000
_STUB_RATIO = 5


def chapter_title(text: str) -> str | None:
    """Return the normalized text when it looks like a chapter heading."""
    raw = normalize_text(text)
    if not raw or _DOT_LEADER_RE.search(raw):
        return None
    candidate = raw.lstrip(_LEADING_QUOTES)
    if (
        not candidate
        or len(candidate) > _MAX_CHAPTER_TITLE_LEN
        or not _CHAPTER_RE.match(candidate)
    ):
        return None
    if candidate.endswith(_SENTENCE_END) and not _NUMBERED_CHAPTER_RE.match(candidate):
        return None
    return raw


def chapter_number(title: str) -> int | None:
    """Extract the chapter number from a title (`Capítulo 01` -> 1)."""
    match = _CHAPTER_NUMBER_RE.search(title)
    if match is None:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def resolve_split_mode(mode: str, headings: int) -> str:
    """Resolve `auto` to `webnovel` or `book` from the detected heading count."""
    if mode in ("book", "webnovel"):
        return mode
    return "webnovel" if headings >= 20 else "book"


def _chapter_body(chapter: object) -> str:
    html = getattr(chapter, "html", None)
    if isinstance(html, str):
        return re.sub(r"<[^>]+>", " ", _H1_RE.sub("", html, count=1))
    paragraphs = getattr(chapter, "paragraphs", None)
    if isinstance(paragraphs, list):
        return "\n".join(str(paragraph) for paragraph in paragraphs)
    return ""


def _chapter_has_body(chapter: object) -> bool:
    if _chapter_body(chapter).strip():
        return True
    html = getattr(chapter, "html", None)
    return isinstance(html, str) and ("<img" in html or "<table" in html)


def _chapter_size(chapter: object) -> int:
    return len(_chapter_body(chapter).strip())


def _renumber(chapters: list[Any]) -> None:
    for index, chapter in enumerate(chapters):
        chapter.order = index  # type: ignore[attr-defined]
        if hasattr(chapter, "file_name"):
            chapter.file_name = f"chapter_{index:04d}.xhtml"  # type: ignore[attr-defined]


def normalize_chapters(chapters: list[Any], *, mode: str = "auto") -> list[Any]:
    """Apply the book/webnovel chapter strategy and renumber the result."""
    resolved = mode
    if resolved == "auto":
        resolved = "webnovel" if len(chapters) >= 20 else "book"
    if resolved != "webnovel":
        _renumber(chapters)
        return chapters

    kept = [chapter for chapter in chapters if _chapter_has_body(chapter)]
    if not kept:
        kept = list(chapters)

    merged: list[Any] = []
    for chapter in kept:
        number = chapter_number(getattr(chapter, "title", ""))
        if merged and number is not None:
            previous = merged[-1]
            previous_number = chapter_number(getattr(previous, "title", ""))
            if previous_number == number:
                previous_size = _chapter_size(previous)
                current_size = _chapter_size(chapter)
                small, large = sorted((previous_size, current_size))
                if small < _STUB_MAX_CHARS and small * _STUB_RATIO < large:
                    if current_size > previous_size:
                        merged[-1] = chapter
                    continue
        merged.append(chapter)
    if not merged:
        merged = kept
    _renumber(merged)
    return merged


def heading_level(paragraph: Paragraph) -> int:
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
    return 1 if chapter_title(paragraph.text) is not None else 0


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
    mode: str = "auto",
) -> list[Chapter]:
    """Split a DOCX into chapters, rendering each body to XHTML.

    `skip_rel_ids` lists image relationships that must not be rendered inline (for
    example, the cover, which is promoted to the EPUB cover page). `mode` selects the
    chapter strategy (`auto`, `book` or `webnovel`).
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
            level = heading_level(item)
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
    return cast(list[Chapter], normalize_chapters(chapters, mode=mode))
