from __future__ import annotations

from pathlib import Path

import pymupdf

from pdf_to_epub.core.pdf.headers_footers import (
    PageGeometry,
    clean_pdf,
    detect_headers_footers,
)

PAGE_W = 595.0
PAGE_H = 842.0


def _page(index: int, blocks: list[tuple[float, float, float, float, str]]) -> PageGeometry:
    return PageGeometry(index=index, width=PAGE_W, height=PAGE_H, blocks=blocks)


def test_detect_repeated_header_and_footer() -> None:
    pages = [
        _page(
            i,
            [
                (72, 30, 300, 48, "The Book"),
                (72, 120, 400, 140, f"Body {i}"),
                (72, 800, 200, 820, "Confidential"),
            ],
        )
        for i in range(3)
    ]
    result = detect_headers_footers(pages)
    texts = {candidate.text for candidate in result.candidates}
    assert "The Book" in texts
    assert "Confidential" in texts
    assert len(result.removals) == 6


def test_detect_page_numbers_vary() -> None:
    pages = [
        _page(i, [(300, 800, 320, 820, str(i + 1)), (72, 120, 400, 140, f"Body {i}")])
        for i in range(3)
    ]
    result = detect_headers_footers(pages)
    assert len(result.candidates) == 1
    assert result.candidates[0].kind == "footer"
    assert len(result.removals) == 3


def test_detect_below_ratio_not_removed() -> None:
    pages = [
        _page(i, [(72, 30, 300, 48, name), (72, 120, 400, 140, f"Body {i}")])
        for i, name in enumerate(["Alpha", "Beta", "Gamma"])
    ]
    result = detect_headers_footers(pages)
    assert result.candidates == []
    assert result.removals == []


def test_detect_numbered_footer_with_label() -> None:
    pages = [
        _page(i, [(240, 800, 360, 820, f"{i + 1} | P a g i n a"), (72, 120, 400, 140, f"Body {i}")])
        for i in range(3)
    ]
    result = detect_headers_footers(pages)
    assert len(result.removals) == 3


def test_detect_oversized_block_is_skipped() -> None:
    big = (0.0, 0.0, PAGE_W, 130.0, "x" * 400)
    pages = [_page(i, [big, (72, 120, 400, 200, f"Body {i}")]) for i in range(3)]
    result = detect_headers_footers(pages)
    assert result.removals == []


def test_clean_pdf_removes_noise_and_keeps_body(repeated_pdf: Path) -> None:
    clean_path, report = clean_pdf(repeated_pdf)
    assert report.applied is True
    assert clean_path != repeated_pdf
    assert clean_path.exists()
    assert report.removal_count >= 6

    with pymupdf.open(clean_path) as doc:
        text = "\n".join(page.get_text() for page in doc)
    assert "The Book" not in text
    assert "Confidential" not in text
    assert "Body paragraph 1" in text


def test_clean_pdf_removes_page_numbers(page_number_pdf: Path) -> None:
    clean_path, report = clean_pdf(page_number_pdf)
    assert report.applied is True
    with pymupdf.open(clean_path) as doc:
        text = "\n".join(page.get_text() for page in doc)
    assert "Body paragraph 1" in text
    for number in ("1", "2", "3"):
        assert f"\n{number}\n" not in f"\n{text}\n"


def test_clean_pdf_without_noise_is_untouched(clean_pdf_noise: Path) -> None:
    clean_path, report = clean_pdf(clean_pdf_noise)
    assert report.applied is False
    assert clean_path == clean_pdf_noise
