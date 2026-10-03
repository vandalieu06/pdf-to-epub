from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from ebooklib import epub

from pdf_to_epub.core.config import ConversionOptions
from pdf_to_epub.core.epub.metadata import apply_metadata
from pdf_to_epub.core.models import PdfMetadata


def _options(tmp_path: Path, **overrides: object) -> ConversionOptions:
    return ConversionOptions(input_pdf=tmp_path / "poison-king.pdf", **overrides)


def _apply(pdf_metadata: PdfMetadata, options: ConversionOptions) -> epub.EpubBook:
    book = epub.EpubBook()
    apply_metadata(book, pdf_metadata, options)
    return book


def test_maps_full_metadata(tmp_path: Path) -> None:
    metadata = PdfMetadata(
        title="The Poison King",
        authors=["Jane Austen", "John Smith"],
        subject="A light novel",
        keywords=["fantasy", "harem"],
        creator="WriterApp",
        producer="PDFLib",
        creation_date=datetime(2024, 1, 2, 12, 34, 56),
        page_count=100,
    )
    book = _apply(metadata, _options(tmp_path))

    assert book.get_metadata("DC", "title")[0][0] == "The Poison King"
    assert book.get_metadata("DC", "language")[0][0] == "es"
    assert [value for value, _ in book.get_metadata("DC", "creator")] == [
        "Jane Austen",
        "John Smith",
    ]
    assert book.get_metadata("DC", "description")[0][0] == "A light novel"
    assert [value for value, _ in book.get_metadata("DC", "subject")] == [
        "fantasy",
        "harem",
    ]
    assert book.get_metadata("DC", "date")[0][0] == "2024-01-02"
    assert book.get_metadata(None, "meta")  # provenance + version


def test_fallbacks_when_pdf_metadata_missing(tmp_path: Path) -> None:
    book = _apply(PdfMetadata(), _options(tmp_path))
    assert book.get_metadata("DC", "title")[0][0] == "poison-king"
    assert book.get_metadata("DC", "language")[0][0] == "es"
    uuid.UUID(book.uid)  # raises if not a valid UUID
    assert book.get_metadata("DC", "description") == []
    assert book.get_metadata("DC", "subject") == []


def test_cli_overrides_win(tmp_path: Path) -> None:
    metadata = PdfMetadata(title="Original", authors=["Original Author"])
    options = _options(
        tmp_path,
        title="Override",
        author="Other",
        language="en",
        identifier="urn:isbn:123",
    )
    book = _apply(metadata, options)
    assert book.get_metadata("DC", "title")[0][0] == "Override"
    assert book.get_metadata("DC", "language")[0][0] == "en"
    assert book.uid == "urn:isbn:123"
    assert [value for value, _ in book.get_metadata("DC", "creator")] == ["Other"]
