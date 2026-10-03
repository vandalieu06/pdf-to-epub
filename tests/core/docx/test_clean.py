from __future__ import annotations

from pathlib import Path

from docx import Document

from pdf_to_epub.core.docx.clean import clean_document


def test_clear_headers_and_footers(docx_with_header_footer: Path) -> None:
    report = clean_document(docx_with_header_footer)
    assert report.cleared_headers_footers >= 1

    document = Document(str(docx_with_header_footer))
    for section in document.sections:
        header_text = "".join(p.text for p in section.header.paragraphs)
        footer_text = "".join(p.text for p in section.footer.paragraphs)
        assert header_text == ""
        assert footer_text == ""
    assert "Body paragraph one." in "\n".join(p.text for p in document.paragraphs)


def test_remove_page_number_paragraphs(tmp_path: Path) -> None:
    doc = Document()
    doc.add_paragraph("Real content.")
    doc.add_paragraph("12")
    doc.add_paragraph("- 13 -")
    path = tmp_path / "numbers.docx"
    doc.save(str(path))

    report = clean_document(path)
    assert report.removed_paragraphs == 2
    document = Document(str(path))
    texts = [p.text for p in document.paragraphs]
    assert "Real content." in texts
    assert "12" not in texts
    assert "- 13 -" not in texts


def _word_grid_docx(tmp_path: Path, words: list[str]) -> Path:
    doc = Document()
    doc.add_paragraph("Antes de la tabla.")
    table = doc.add_table(rows=1, cols=len(words))
    for cell, word in zip(table.rows[0].cells, words, strict=True):
        cell.text = word
    path = tmp_path / "word-grid.docx"
    doc.save(str(path))
    return path


def test_repairs_one_row_word_grid_table(tmp_path: Path) -> None:
    words = ["avergonzado", "por", "eso.", "Los", "cambios", "provocados", "por"]
    path = _word_grid_docx(tmp_path, words)

    report = clean_document(path)
    assert report.repaired_tables == 1

    document = Document(str(path))
    assert document.tables == []
    texts = [p.text for p in document.paragraphs]
    assert "avergonzado por eso. Los cambios provocados por" in texts


def test_keeps_real_table(tmp_path: Path) -> None:
    doc = Document()
    table = doc.add_table(rows=3, cols=2)
    for row_index, row in enumerate(table.rows):
        row.cells[0].text = f"key {row_index}"
        row.cells[1].text = f"value {row_index}"
    path = tmp_path / "real.docx"
    doc.save(str(path))

    report = clean_document(path)
    assert report.repaired_tables == 0
    assert len(Document(str(path)).tables) == 1


def test_keeps_narrow_one_row_table(tmp_path: Path) -> None:
    path = _word_grid_docx(tmp_path, ["A", "B"])

    report = clean_document(path)
    assert report.repaired_tables == 0
    assert len(Document(str(path)).tables) == 1


def test_keep_tables_option_preserves_word_grid(tmp_path: Path) -> None:
    path = _word_grid_docx(tmp_path, ["one", "two", "three", "four"])

    report = clean_document(path, repair_tables=False)
    assert report.repaired_tables == 0
    assert len(Document(str(path)).tables) == 1
