from __future__ import annotations

import zipfile
from pathlib import Path

from docx import Document
from ebooklib import epub

from pdf_to_epub.core.config import ConversionOptions
from pdf_to_epub.core.docx.images import extract_images
from pdf_to_epub.core.epub.builder import build_epub
from pdf_to_epub.core.epub.split import split_chapters
from pdf_to_epub.core.models import PdfMetadata


def _chapters_and_images(docx_with_image: Path):  # type: ignore[no-untyped-def]
    document = Document(str(docx_with_image))
    extraction = extract_images(document)
    cover_rel_ids = (
        {extraction.assets[0].rel_id}
        if extraction.assets and extraction.assets[0].rel_id
        else set()
    )
    chapters = split_chapters(
        document,
        extraction.assets,
        fallback_title="Book",
        skip_rel_ids=cover_rel_ids,
    )
    return chapters, extraction.assets


def _first_spine_name(book: epub.EpubBook) -> str:
    first_id = book.spine[0][0]
    item = book.get_item_with_id(first_id)
    return item.get_name()


def _read_opf(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        opf_name = next(n for n in archive.namelist() if n.endswith(".opf"))
        return archive.read(opf_name).decode("utf-8")


def _read_member(path: Path, suffix: str) -> str:
    with zipfile.ZipFile(path) as archive:
        name = next(n for n in archive.namelist() if n.endswith(suffix))
        return archive.read(name).decode("utf-8")


def test_build_and_reopen(tmp_path: Path, docx_with_image: Path) -> None:
    chapters, images = _chapters_and_images(docx_with_image)
    options = ConversionOptions(
        input_pdf=tmp_path / "in.pdf",
        output_epub=tmp_path / "out.epub",
    )
    output = build_epub(chapters, images, PdfMetadata(title="Title"), options)
    assert output.exists()

    book = epub.read_epub(str(output))
    assert book.get_metadata("DC", "title")[0][0] == "Title"
    item_names = {item.get_name() for item in book.get_items()}
    assert "images/img_0000.png" in item_names
    assert "style/default.css" in item_names


def test_cover_is_first_in_spine(tmp_path: Path, docx_with_image: Path) -> None:
    chapters, images = _chapters_and_images(docx_with_image)
    options = ConversionOptions(
        input_pdf=tmp_path / "in.pdf",
        output_epub=tmp_path / "covered.epub",
    )
    output = build_epub(chapters, images, PdfMetadata(title="T"), options)

    book = epub.read_epub(str(output))
    assert _first_spine_name(book) == "cover.xhtml"

    cover_raw = _read_member(output, "cover.xhtml")
    assert 'src="images/img_0000.png"' in cover_raw
    assert 'lang="es"' in cover_raw

    opf = _read_opf(output)
    assert 'properties="cover-image"' in opf
    assert 'name="cover"' in opf


def test_cover_not_referenced_in_body(tmp_path: Path, docx_with_image: Path) -> None:
    chapters, images = _chapters_and_images(docx_with_image)
    options = ConversionOptions(
        input_pdf=tmp_path / "in.pdf",
        output_epub=tmp_path / "dedup.epub",
    )
    output = build_epub(chapters, images, PdfMetadata(title="T"), options)

    with zipfile.ZipFile(output) as archive:
        xhtml_names = [n for n in archive.namelist() if n.endswith(".xhtml")]
        references = {
            name: archive.read(name).decode("utf-8").count("img_0000")
            for name in xhtml_names
        }
    assert references["EPUB/cover.xhtml"] == 1
    for name, count in references.items():
        if name.endswith("cover.xhtml"):
            continue
        assert count == 0, f"{name} still references the cover"


def test_external_cover_is_first_in_spine(
    tmp_path: Path, png_file: Path, docx_with_image: Path
) -> None:
    chapters, images = _chapters_and_images(docx_with_image)
    options = ConversionOptions(
        input_pdf=tmp_path / "in.pdf",
        output_epub=tmp_path / "covered.epub",
        cover=png_file,
        language="en",
    )
    output = build_epub(chapters, images, PdfMetadata(title="T"), options)

    book = epub.read_epub(str(output))
    item_names = {item.get_name() for item in book.get_items()}
    assert "images/cover.png" in item_names
    assert "images/img_0000.png" not in item_names
    first_id = book.spine[0][0]
    assert book.get_item_with_id(first_id).get_name() == "cover.xhtml"
    cover_raw = _read_member(output, "cover.xhtml")
    assert 'src="images/cover.png"' in cover_raw
    assert 'lang="en"' in cover_raw
