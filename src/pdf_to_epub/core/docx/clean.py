"""Post-processing of the intermediate DOCX.

`pdf2docx` maps page content into normal paragraphs, so headers/footers that
survived the PDF pass can still appear here. This module clears Word header/footer
parts, drops standalone page-number paragraphs, and repairs false-positive tables
as a safety net.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from ..models import DocxCleanReport
from ..text import is_page_number, normalize_text
from .reflow import reflow_document

MIN_TABLE_COLUMNS = 3


def _clear_container(container: object) -> int:
    """Remove every child element from a header/footer container."""
    element = getattr(container, "_element", None)
    if element is None:
        return 0
    children = list(element)
    for child in children:
        element.remove(child)
    return len(children)


def _iter_header_footer_parts(section: object) -> list[object]:
    names = (
        "header",
        "footer",
        "first_page_header",
        "first_page_footer",
        "even_page_header",
        "even_page_footer",
    )
    parts: list[object] = []
    for name in names:
        try:
            part = getattr(section, name)
        except Exception:  # noqa: BLE001 - not all documents expose every part
            continue
        parts.append(part)
    return parts


def _word_grid_text(table: object) -> str | None:
    """Return the joined text if `table` is a one-row, word-per-cell false positive."""
    rows = table.rows  # type: ignore[attr-defined]
    if len(rows) != 1:
        return None
    cells = [cell.text.strip() for cell in rows[0].cells]
    non_empty = [cell for cell in cells if cell]
    if len(non_empty) < MIN_TABLE_COLUMNS:
        return None
    return " ".join(non_empty)


def _replace_table_with_paragraph(table: object, text: str) -> None:
    element = table._tbl  # type: ignore[attr-defined]
    paragraph = OxmlElement("w:p")
    run = OxmlElement("w:r")
    node = OxmlElement("w:t")
    node.set(qn("xml:space"), "preserve")
    node.text = text
    run.append(node)
    paragraph.append(run)
    element.addprevious(paragraph)
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)


def repair_false_tables(document: Document) -> int:
    """Convert one-row word-grid tables back into paragraphs; return the count."""
    repaired = 0
    for table in list(document.tables):
        text = _word_grid_text(table)
        if text is None:
            continue
        _replace_table_with_paragraph(table, text)
        repaired += 1
    return repaired


def clean_document(
    docx_path: Path,
    *,
    remove_page_numbers: bool = True,
    repair_tables: bool = True,
    reflow: bool = True,
    progress: Callable[[str], None] | None = None,
) -> DocxCleanReport:
    """Clean headers/footers, stray page numbers, false tables and paragraphs in-place."""
    if progress:
        progress("Cleaning DOCX")
    document = Document(str(docx_path))
    report = DocxCleanReport()

    for section in document.sections:
        for part in _iter_header_footer_parts(section):
            if getattr(part, "is_linked_to_previous", False):
                continue
            if _clear_container(part):
                report.cleared_headers_footers += 1

    if remove_page_numbers:
        for paragraph in list(document.paragraphs):
            text = normalize_text(paragraph.text)
            if text and is_page_number(text):
                element = paragraph._element
                parent = element.getparent()
                if parent is not None:
                    parent.remove(element)
                    report.removed_paragraphs += 1

    if repair_tables:
        report.repaired_tables = repair_false_tables(document)

    if reflow:
        reflow_report = reflow_document(document)
        report.split_paragraphs = reflow_report.split_paragraphs
        report.merged_paragraphs = reflow_report.merged_paragraphs

    document.save(str(docx_path))
    return report
