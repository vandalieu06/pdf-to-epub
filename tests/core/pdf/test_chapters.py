"""Tests for chapter detection directly in the PDF."""

from __future__ import annotations

from pathlib import Path

import pymupdf

from pdf_to_epub.core.pdf.chapters import read_pdf_chapters


def _pdf_with_outline(path: Path) -> Path:
    doc = pymupdf.open()
    for _ in range(3):
        page = doc.new_page()
        page.insert_text((72, 72), "Body paragraph", fontsize=12)
    doc.set_toc([[1, "Capítulo 1", 1], [1, "Capítulo 2", 3]])
    doc.save(str(path))
    doc.close()
    return path


def test_outline_wins(tmp_path: Path) -> None:
    chapters = read_pdf_chapters(_pdf_with_outline(tmp_path / "outline.pdf"))
    assert [(chapter.page, chapter.title) for chapter in chapters] == [
        (1, "Capítulo 1"),
        (3, "Capítulo 2"),
    ]
    assert all(chapter.source == "outline" for chapter in chapters)


def test_outline_skips_front_matter_and_duplicate_pages(tmp_path: Path) -> None:
    doc = pymupdf.open()
    for _ in range(3):
        page = doc.new_page()
        page.insert_text((72, 72), "Body paragraph", fontsize=12)
    doc.set_toc(
        [
            [1, "Cover", 1],
            [1, "Table of Contents", 1],
            [1, "Capítulo 1", 2],
            [1, "Capítulo 1 bis", 2],
            [1, "Capítulo 2", 3],
        ]
    )
    path = tmp_path / "outline-skip.pdf"
    doc.save(str(path))
    doc.close()

    chapters = read_pdf_chapters(path)
    assert [(chapter.page, chapter.title) for chapter in chapters] == [
        (2, "Capítulo 1"),
        (3, "Capítulo 2"),
    ]


def test_hidden_heading_under_image(tmp_path: Path, png_file: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Capítulo 1", fontsize=20)
    page.insert_image(
        pymupdf.Rect(60, 80, 300, 140),
        filename=str(png_file),
        keep_proportion=False,
    )
    page.insert_text((72, 200), "Body paragraph", fontsize=12)
    path = tmp_path / "hidden.pdf"
    doc.save(str(path))
    doc.close()

    chapters = read_pdf_chapters(path)
    assert len(chapters) == 1
    assert chapters[0].page == 1
    assert chapters[0].title == "Capítulo 1"
    assert chapters[0].source == "hidden"


def test_hidden_detection_can_be_disabled(tmp_path: Path, png_file: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Capítulo 1", fontsize=20)
    page.insert_image(
        pymupdf.Rect(60, 80, 300, 140),
        filename=str(png_file),
        keep_proportion=False,
    )
    path = tmp_path / "hidden-off.pdf"
    doc.save(str(path))
    doc.close()

    assert read_pdf_chapters(path, allow_hidden=False) == []


def test_no_outline_and_no_hidden_yields_empty(tmp_path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Only body text", fontsize=12)
    path = tmp_path / "plain.pdf"
    doc.save(str(path))
    doc.close()

    assert read_pdf_chapters(path) == []
