from __future__ import annotations

from pathlib import Path

from pdf_to_epub.core.pdf.images import extract_pdf_images
from tests.conftest import make_pdf, make_png


def test_extract_pdf_images_flags_margin_repeat(tmp_path: Path) -> None:
    banner = make_png(tmp_path / "banner.png", color=(1.0, 0.0, 0.0))
    art = make_png(tmp_path / "art.png", color=(0.0, 0.0, 1.0))
    pdf = make_pdf(
        tmp_path / "in.pdf",
        pages=3,
        header=None,
        footer=None,
        footer_image=banner,
        image_path=art,
    )

    images = extract_pdf_images(pdf)

    banners = [image for image in images if image.is_margin_repeat]
    arts = [image for image in images if not image.is_margin_repeat]
    assert len(banners) == 1
    assert banners[0].media_type == "image/png"
    assert (banners[0].width, banners[0].height) == (200, 300)
    assert banners[0].placements == 3
    assert any((image.width, image.height) == (200, 300) for image in arts)


def test_extract_pdf_images_preserves_order_and_data(tmp_path: Path) -> None:
    banner = make_png(tmp_path / "banner.png", color=(1.0, 0.0, 0.0))
    pdf = make_pdf(
        tmp_path / "in.pdf",
        pages=3,
        header=None,
        footer=None,
        footer_image=banner,
    )

    images = extract_pdf_images(pdf)

    assert len(images) == 1
    assert images[0].data.startswith(b"\x89PNG")
    assert images[0].is_margin_repeat is True
