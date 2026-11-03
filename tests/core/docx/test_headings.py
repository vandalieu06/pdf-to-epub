"""Tests for heading injection into the intermediate DOCX."""

from __future__ import annotations

from docx import Document
from docx.enum.section import WD_SECTION

from pdf_to_epub.core.docx.headings import (
    count_heading_paragraphs,
    inject_missing_headings,
)
from pdf_to_epub.core.models import PdfChapterStart


def _two_page_docx() -> Document:
    document = Document()
    document.add_paragraph("Page 1 body")
    document.add_section(WD_SECTION.NEW_PAGE)
    document.add_paragraph("Page 2 body")
    return document


def test_injects_heading_on_matching_page() -> None:
    document = _two_page_docx()
    injected = inject_missing_headings(
        document, [PdfChapterStart(page=2, title="Capítulo 1")]
    )

    assert injected == 1
    assert [paragraph.text for paragraph in document.paragraphs] == [
        "Page 1 body",
        "",
        "Capítulo 1",
        "Page 2 body",
    ]
    assert count_heading_paragraphs(document) == 1


def test_does_not_inject_when_page_already_has_heading() -> None:
    document = _two_page_docx()
    document.paragraphs[2].insert_paragraph_before("Capítulo 1").style = "Heading 1"

    injected = inject_missing_headings(
        document, [PdfChapterStart(page=2, title="Capítulo 1")]
    )

    assert injected == 0
    assert count_heading_paragraphs(document) == 1


def test_ignores_pages_outside_the_document() -> None:
    document = _two_page_docx()
    injected = inject_missing_headings(
        document, [PdfChapterStart(page=99, title="Capítulo 99")]
    )
    assert injected == 0
