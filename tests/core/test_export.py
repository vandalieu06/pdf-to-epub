from __future__ import annotations

from pathlib import Path

from docx import Document

from pdf_to_epub.core.export import extract_docx_chapters


def _chapters(doc: Document, tmp_path: Path, *, fallback_title: str = "Book") -> list[object]:
    path = tmp_path / "sample.docx"
    doc.save(str(path))
    return extract_docx_chapters(path, fallback_title=fallback_title)


def test_splits_on_heading_styles(tmp_path: Path) -> None:
    doc = Document()
    doc.add_heading("Chapter 1", level=1)
    doc.add_paragraph("First body.")
    doc.add_heading("Chapter 2", level=1)
    doc.add_paragraph("Second body.")

    chapters = _chapters(doc, tmp_path)
    assert [c.title for c in chapters] == ["Chapter 1", "Chapter 2"]
    assert chapters[0].paragraphs == ["First body."]
    assert chapters[1].paragraphs == ["Second body."]


def test_splits_on_keyword_paragraph(tmp_path: Path) -> None:
    doc = Document()
    doc.add_paragraph("Some front matter.")
    doc.add_paragraph("Prologue")
    doc.add_paragraph("Prologue body.")

    chapters = _chapters(doc, tmp_path)
    assert [c.title for c in chapters] == ["Book", "Prologue"]
    assert "Some front matter." in chapters[0].paragraphs
    assert "Prologue body." in chapters[1].paragraphs


def test_splits_on_guillemet_chapter_markers(tmp_path: Path) -> None:
    doc = Document()
    doc.add_paragraph("«Prólogo»")
    doc.add_paragraph("Prologue body.")
    doc.add_paragraph("«Capítulo 1» El niño maldito")
    doc.add_paragraph("Chapter body.")

    chapters = _chapters(doc, tmp_path)
    assert [c.title for c in chapters] == ["«Prólogo»", "«Capítulo 1» El niño maldito"]
    assert "Prologue body." in chapters[0].paragraphs
    assert "Chapter body." in chapters[1].paragraphs


def test_toc_dot_leaders_are_not_chapters(tmp_path: Path) -> None:
    doc = Document()
    doc.add_paragraph("Some body.")
    doc.add_paragraph("«Prólogo» .......................... 6")

    chapters = _chapters(doc, tmp_path)
    assert len(chapters) == 1


def test_no_headings_yields_single_chapter(tmp_path: Path) -> None:
    doc = Document()
    doc.add_paragraph("Only body.")
    doc.add_paragraph("More body.")

    chapters = _chapters(doc, tmp_path, fallback_title="My Book")
    assert len(chapters) == 1
    assert chapters[0].title == "My Book"
    assert chapters[0].paragraphs == ["Only body.", "More body."]


def test_table_is_flattened_to_text(tmp_path: Path) -> None:
    doc = Document()
    doc.add_paragraph("Before.")
    table = doc.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "uno"
    table.rows[0].cells[1].text = "dos"
    table.rows[1].cells[0].text = "tres"
    table.rows[1].cells[1].text = "cuatro"

    chapters = _chapters(doc, tmp_path)
    assert "uno" in chapters[0].paragraphs
    assert "dos" in chapters[0].paragraphs
    assert "tres" in chapters[0].paragraphs
    assert "cuatro" in chapters[0].paragraphs


def test_bold_italic_runs_are_flattened(tmp_path: Path) -> None:
    doc = Document()
    doc.add_heading("Capítulo 1", level=1)
    paragraph = doc.add_paragraph()
    paragraph.add_run("normal ")
    bold = paragraph.add_run("negrita")
    bold.bold = True
    paragraph.add_run(" más")

    chapters = _chapters(doc, tmp_path)
    assert chapters[0].paragraphs == ["normal negrita más"]


def test_paragraphs_are_stripped_of_blank_lines(tmp_path: Path) -> None:
    doc = Document()
    doc.add_heading("Capítulo 1", level=1)
    doc.add_paragraph("   ")
    doc.add_paragraph("Texto real.")

    chapters = _chapters(doc, tmp_path)
    assert chapters[0].paragraphs == ["Texto real."]