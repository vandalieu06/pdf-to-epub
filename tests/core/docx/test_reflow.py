from __future__ import annotations

from pathlib import Path

from docx import Document

from pdf_to_epub.core.docx.clean import clean_document
from pdf_to_epub.core.docx.reflow import reflow_document


def _paragraph_with_break(*parts: str) -> Document:
    doc = Document()
    paragraph = doc.add_paragraph()
    for index, part in enumerate(parts):
        if index > 0:
            paragraph.add_run().add_break()
        paragraph.add_run(part)
    return doc


def test_splits_dialogue_break() -> None:
    doc = _paragraph_with_break("“¿Qué pasa?”", "“Nada”, dijo el anciano.")

    report = reflow_document(doc)

    assert report.split_paragraphs == 1
    assert [p.text for p in doc.paragraphs] == [
        "“¿Qué pasa?”",
        "“Nada”, dijo el anciano.",
    ]


def test_break_mid_sentence_becomes_space() -> None:
    doc = _paragraph_with_break("Lenka intentó consolar a Tea mientras se", "pellizcaba la nariz.")

    report = reflow_document(doc)

    assert report.split_paragraphs == 0
    assert len(doc.paragraphs) == 1
    assert doc.paragraphs[0].text == (
        "Lenka intentó consolar a Tea mientras se pellizcaba la nariz."
    )


def test_merges_continuation_paragraphs() -> None:
    doc = Document()
    doc.add_paragraph("un niño con cabello y ojos cenicientos, cuyo rostro")
    doc.add_paragraph("atractivo podría hacerlo irresistible.")

    report = reflow_document(doc)

    assert report.merged_paragraphs == 1
    assert [p.text for p in doc.paragraphs] == [
        "un niño con cabello y ojos cenicientos, cuyo rostro atractivo podría hacerlo irresistible."
    ]


def test_merges_across_empty_paragraphs() -> None:
    doc = Document()
    doc.add_paragraph("muchos médicos,")
    doc.add_paragraph("")
    doc.add_paragraph("boticarios y magos reales habían intentado salvarla.")

    report = reflow_document(doc)

    assert report.merged_paragraphs == 1
    texts = [p.text for p in doc.paragraphs if p.text.strip()]
    assert texts == [
        "muchos médicos, boticarios y magos reales habían intentado salvarla."
    ]


def test_does_not_merge_after_sentence_end() -> None:
    doc = Document()
    doc.add_paragraph("Terminó la frase.")
    doc.add_paragraph("seguía la siguiente.")

    report = reflow_document(doc)

    assert report.merged_paragraphs == 0
    assert len(doc.paragraphs) == 2


def test_image_blocks_merge(png_file: Path) -> None:
    doc = Document()
    doc.add_paragraph("cuyo rostro")
    doc.add_picture(str(png_file))
    doc.add_paragraph("atractivo irresistible.")

    report = reflow_document(doc)

    assert report.merged_paragraphs == 0
    assert len(doc.paragraphs) == 3


def test_headings_are_not_merged() -> None:
    doc = Document()
    doc.add_heading("Capítulo 1", level=1)
    doc.add_paragraph("continuación de texto en minúscula.")

    report = reflow_document(doc)

    assert report.merged_paragraphs == 0
    assert len(doc.paragraphs) == 2


def test_preserves_italic_runs() -> None:
    doc = Document()
    paragraph = doc.add_paragraph()
    paragraph.add_run("¿Qué pasa?")
    paragraph.add_run().add_break()
    italic = paragraph.add_run("Nada")
    italic.italic = True

    reflow_document(doc)

    assert doc.paragraphs[1].runs[0].italic is True
    assert doc.paragraphs[1].text == "Nada"


def test_splits_adjacent_dialogues() -> None:
    doc = Document()
    paragraph = doc.add_paragraph()
    paragraph.add_run("“Ah, sí dijeron que pasó toda su vida solo.” ")
    paragraph.add_run("“¿Así que se convirtió en un fantasma?” ")
    paragraph.add_run("Lenka y Tea hablaron.")

    report = reflow_document(doc)

    assert report.split_paragraphs >= 1
    assert [p.text for p in doc.paragraphs] == [
        "“Ah, sí dijeron que pasó toda su vida solo.”",
        "“¿Así que se convirtió en un fantasma?” Lenka y Tea hablaron.",
    ]


def test_splits_adjacent_dialogues_straight_and_single() -> None:
    doc = Document()
    paragraph = doc.add_paragraph()
    paragraph.add_run('"Uno." ')
    paragraph.add_run('"Dos."')

    single = Document()
    single_paragraph = single.add_paragraph()
    single_paragraph.add_run("’Uno.’ ")
    single_paragraph.add_run("‘Dos.’")

    reflow_document(doc)
    reflow_document(single)

    assert [p.text for p in doc.paragraphs] == ['"Uno."', '"Dos."']
    assert [p.text for p in single.paragraphs] == ["’Uno.’", "‘Dos.’"]


def test_splits_adjacent_dialogues_within_one_run() -> None:
    doc = Document()
    doc.add_paragraph("“Uno.” “Dos.”")

    reflow_document(doc)

    assert [p.text for p in doc.paragraphs] == ["“Uno.”", "“Dos.”"]


def test_does_not_split_lists_or_dashes() -> None:
    doc = Document()
    doc.add_paragraph("“A”, “B” y “C” están en la lista.")
    doc.add_paragraph("“A” — “B” tampoco se separa.")

    report = reflow_document(doc)

    assert report.split_paragraphs == 0
    assert len(doc.paragraphs) == 2


def test_preserves_italics_across_dialogue_split() -> None:
    doc = Document()
    paragraph = doc.add_paragraph()
    paragraph.add_run("“Uno.” ")
    italic = paragraph.add_run("“Dos?”")
    italic.italic = True

    reflow_document(doc)

    assert doc.paragraphs[1].text == "“Dos?”"
    assert doc.paragraphs[1].runs[0].italic is True


def test_clean_document_no_reflow(tmp_path: Path) -> None:
    doc = _paragraph_with_break("mientras se", "pellizcaba la nariz.")
    path = tmp_path / "break.docx"
    doc.save(str(path))

    report = clean_document(path, reflow=False)

    assert report.split_paragraphs == 0
    assert report.merged_paragraphs == 0
    assert len(Document(str(path)).paragraphs) == 1
