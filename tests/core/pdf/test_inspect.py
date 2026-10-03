from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pdf_to_epub.core.pdf.inspect import (
    parse_pdf_date,
    read_metadata,
    split_authors,
    split_keywords,
)
from tests.conftest import make_pdf


def test_parse_pdf_date_full() -> None:
    assert parse_pdf_date("D:20240102123456") == datetime(2024, 1, 2, 12, 34, 56)


def test_parse_pdf_date_partial_and_invalid() -> None:
    assert parse_pdf_date("D:2024") == datetime(2024, 1, 1)
    assert parse_pdf_date("garbage") is None
    assert parse_pdf_date(None) is None


def test_split_authors_semicolon_only() -> None:
    assert split_authors("Jane Austen; John Smith") == ["Jane Austen", "John Smith"]


def test_split_authors_keeps_comma_name() -> None:
    assert split_authors("Austen, Jane") == ["Austen, Jane"]


def test_split_keywords() -> None:
    assert split_keywords("fantasy; romance, adventure") == [
        "fantasy",
        "romance",
        "adventure",
    ]
    assert split_keywords(None) == []


def test_read_metadata(tmp_path: Path) -> None:
    pdf = make_pdf(
        tmp_path / "meta.pdf",
        pages=2,
        metadata={
            "title": "The Poison King",
            "author": "Jane Austen; John Smith",
            "subject": "A light novel",
            "keywords": "fantasy; harem",
            "creationDate": "D:20240102123456",
        },
    )
    metadata = read_metadata(pdf)
    assert metadata.title == "The Poison King"
    assert metadata.authors == ["Jane Austen", "John Smith"]
    assert metadata.subject == "A light novel"
    assert metadata.keywords == ["fantasy", "harem"]
    assert metadata.creation_date == datetime(2024, 1, 2, 12, 34, 56)
    assert metadata.page_count == 2
