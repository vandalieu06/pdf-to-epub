"""Inject chapter headings into the intermediate DOCX.

`pdf2docx` writes one section per PDF page (`w:sectPr`). When a light novel renders
its chapter titles as images, the text layer is dropped and the DOCX has no heading.
This module maps a PDF page to its DOCX section and inserts a `Heading 1` paragraph
before the first content of that page.
"""

from __future__ import annotations

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from ..epub.split import chapter_title, heading_level
from ..models import PdfChapterStart

_W_P = qn("w:p")
_W_SECTPR = qn("w:sectPr")


def count_heading_paragraphs(document: Document) -> int:
    """Return the number of level-1 headings in the document."""
    return sum(1 for paragraph in document.paragraphs if heading_level(paragraph) == 1)


def _pages(document: Document) -> dict[int, list[object]]:
    """Group body children by PDF page using the per-page section breaks."""
    pages: dict[int, list[object]] = {}
    page = 1
    for child in document.element.body.iterchildren():
        pages.setdefault(page, []).append(child)
        if child.tag == _W_P and child.find(".//" + _W_SECTPR) is not None:
            page += 1
    return pages


def _has_heading(document: Document, children: list[object]) -> bool:
    for child in children:
        if child.tag != _W_P:
            continue
        if heading_level(Paragraph(child, document)) == 1:
            return True
    return False


def _heading_style_id(document: Document) -> str | None:
    try:
        return document.styles["Heading 1"].style_id
    except KeyError:
        return None


def _heading_paragraph(title: str, style_id: str | None) -> object:
    paragraph = OxmlElement("w:p")
    if style_id is not None:
        properties = OxmlElement("w:pPr")
        style = OxmlElement("w:pStyle")
        style.set(qn("w:val"), style_id)
        properties.append(style)
        paragraph.append(properties)
    run = OxmlElement("w:r")
    text = OxmlElement("w:t")
    text.set(qn("xml:space"), "preserve")
    text.text = title
    run.append(text)
    paragraph.append(run)
    return paragraph


def inject_missing_headings(
    document: Document, chapters: list[PdfChapterStart]
) -> int:
    """Insert headings for pages that have none; return the number injected."""
    pages = _pages(document)
    style_id = _heading_style_id(document)
    injected = 0
    for chapter in chapters:
        children = pages.get(chapter.page)
        if not children or _has_heading(document, children):
            continue
        title = chapter.title
        if style_id is None and chapter_title(title) is None:
            title = f"Chapter: {title}"
        children[0].addprevious(_heading_paragraph(title, style_id))
        injected += 1
    return injected
