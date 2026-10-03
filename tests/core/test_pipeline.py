from __future__ import annotations

from pathlib import Path

import pytest
from ebooklib import epub

from pdf_to_epub.core.config import ConversionOptions
from pdf_to_epub.core.errors import ValidationError
from pdf_to_epub.core.pipeline import run


def test_validate_missing_input(tmp_path: Path) -> None:
    options = ConversionOptions(input_pdf=tmp_path / "missing.pdf")
    with pytest.raises(ValidationError):
        run(options)


def test_validate_refuses_overwrite(tmp_path: Path, repeated_pdf: Path) -> None:
    output = tmp_path / "exists.epub"
    output.write_bytes(b"x")
    options = ConversionOptions(input_pdf=repeated_pdf, output_epub=output)
    with pytest.raises(ValidationError):
        run(options)


def test_end_to_end(tmp_path: Path, pdf_with_image: Path) -> None:
    output = tmp_path / "book.epub"
    options = ConversionOptions(input_pdf=pdf_with_image, output_epub=output)
    report = run(options)

    assert report.output_epub == output
    assert output.exists()
    assert report.chapters >= 1
    assert report.images_embedded >= 1

    book = epub.read_epub(str(output))
    assert book.get_metadata("DC", "title")


def test_default_removes_intermediates(tmp_path: Path, repeated_pdf: Path) -> None:
    output = tmp_path / "book.epub"
    options = ConversionOptions(
        input_pdf=repeated_pdf,
        output_epub=output,
        workdir=tmp_path / "work",
    )
    report = run(options)

    assert output.exists()
    assert report.docx_path is not None
    assert not report.docx_path.exists()
    assert report.clean_pdf_path is None or not report.clean_pdf_path.exists()


def test_keep_intermediate(tmp_path: Path, repeated_pdf: Path) -> None:
    output = tmp_path / "book.epub"
    options = ConversionOptions(
        input_pdf=repeated_pdf,
        output_epub=output,
        workdir=tmp_path / "work",
        keep_intermediate=True,
    )
    report = run(options)

    assert report.docx_path is not None and report.docx_path.exists()
    assert report.clean_pdf_path is not None and report.clean_pdf_path.exists()
