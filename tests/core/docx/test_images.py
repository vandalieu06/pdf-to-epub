from __future__ import annotations

import random
from pathlib import Path

import pymupdf
from docx import Document

from pdf_to_epub.core.docx.images import (
    apply_pdf_images,
    count_image_references,
    extension_for,
    extract_images,
    image_pixel_dimensions,
    optimize_images,
    picture_rids,
    select_cover,
    unique_image_parts,
)
from pdf_to_epub.core.models import ImageAsset
from pdf_to_epub.core.pdf.images import PdfImage
from tests.conftest import make_png


def _noisy_png_bytes(size: int = 96) -> bytes:
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, size, size), False)
    rnd = random.Random(1234)
    for y in range(size):
        for x in range(size):
            pixmap.set_pixel(
                x, y, (rnd.randint(0, 255), rnd.randint(0, 255), rnd.randint(0, 255))
            )
    return pixmap.tobytes("png")


def _asset_from(data: bytes, file_name: str = "images/img_0000.png") -> ImageAsset:
    return ImageAsset(
        uid="img_0000",
        file_name=file_name,
        media_type="image/png",
        data=data,
        rel_id="rId1",
        position_index=3,
    )


def test_extension_for() -> None:
    assert extension_for("image/jpeg") == ".jpg"
    assert extension_for("application/octet-stream") == ".img"


def test_extract_single_image(docx_with_image: Path) -> None:
    document = Document(str(docx_with_image))
    result = extract_images(document)
    assert result.found == 1
    assert result.dropped == 0
    assert len(result.assets) == 1
    asset = result.assets[0]
    assert asset.media_type == "image/png"
    assert asset.data
    assert asset.rel_id
    assert asset.file_name == "images/img_0000.png"
    assert asset.width and asset.height


def test_extract_deduplicates(tmp_path: Path, png_file: Path) -> None:
    document = Document()
    document.add_picture(str(png_file))
    document.add_picture(str(png_file))
    path = tmp_path / "dupes.docx"
    document.save(str(path))

    result = extract_images(Document(str(path)))
    assert result.found == 2
    assert len(result.assets) == 1
    assert result.dropped == 1


def test_extract_filters_small_images(tmp_path: Path) -> None:
    small = tmp_path / "small.png"
    doc = pymupdf.open()
    page = doc.new_page(width=8, height=8)
    page.draw_rect(pymupdf.Rect(0, 0, 8, 8), color=(0, 0, 0), fill=(0, 0, 0))
    page.get_pixmap().save(str(small))
    doc.close()

    document = Document()
    document.add_picture(str(small))
    path = tmp_path / "small.docx"
    document.save(str(path))

    filtered = extract_images(Document(str(path)), min_px=24)
    assert filtered.assets == []
    assert filtered.dropped == 1

    kept = extract_images(Document(str(path)), min_px=24, keep_all=True)
    assert len(kept.assets) == 1


def test_picture_rids(docx_with_image: Path) -> None:
    document = Document(str(docx_with_image))
    rids: list[str] = []
    for paragraph in document.paragraphs:
        for run in paragraph.runs:
            rids.extend(picture_rids(run._element))
    assert len(rids) == 1


def test_select_cover_returns_first_image() -> None:
    large = ImageAsset(uid="b", file_name="images/img_0001.png", media_type="image/png",
                       data=b"", width=2000, height=3000)
    first = ImageAsset(uid="a", file_name="images/img_0000.png", media_type="image/png",
                       data=b"", width=100, height=120)
    assert select_cover([first, large]) is first
    assert select_cover([]) is None


def test_optimize_images_converts_opaque_png_to_jpeg() -> None:
    asset = _asset_from(_noisy_png_bytes())

    optimized = optimize_images([asset], quality=85)[0]

    assert optimized.media_type == "image/jpeg"
    assert optimized.file_name == "images/img_0000.jpg"
    assert optimized.rel_id == "rId1"
    assert optimized.uid == "img_0000"
    assert optimized.position_index == 3
    assert optimized.data[:2] == b"\xff\xd8"
    assert len(optimized.data) < len(asset.data)


def test_optimize_keeps_alpha_image() -> None:
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 64, 64), True)
    asset = _asset_from(pixmap.tobytes("png"))

    optimized = optimize_images([asset])[0]

    assert optimized is asset
    assert optimized.media_type == "image/png"


def test_optimize_keeps_original_when_not_smaller(tmp_path: Path) -> None:
    tiny = tmp_path / "tiny.png"
    doc = pymupdf.open()
    page = doc.new_page(width=4, height=4)
    page.draw_rect(pymupdf.Rect(0, 0, 4, 4), color=(0, 0, 0), fill=(0, 0, 0))
    page.get_pixmap().save(str(tiny))
    doc.close()
    asset = _asset_from(tiny.read_bytes())

    optimized = optimize_images([asset], quality=85)[0]

    assert optimized is asset
    assert optimized.media_type == "image/png"


def test_image_pixel_dimensions() -> None:
    png = _noisy_png_bytes(32)
    assert image_pixel_dimensions(png) == (32, 32)


def test_unique_image_parts_in_order(tmp_path: Path) -> None:
    first = make_png(tmp_path / "a.png", color=(1.0, 0.0, 0.0))
    second = make_png(tmp_path / "b.png", color=(0.0, 0.0, 1.0))
    doc = Document()
    doc.add_picture(str(first))
    doc.add_picture(str(second))
    path = tmp_path / "two.docx"
    doc.save(str(path))

    parts = unique_image_parts(Document(str(path)))

    assert len(parts) == 2
    assert parts[0].media_type == "image/png"


def test_count_image_references(tmp_path: Path) -> None:
    png = make_png(tmp_path / "a.png", color=(1.0, 0.0, 0.0))
    doc = Document()
    doc.add_picture(str(png))
    doc.add_picture(str(png))
    doc.add_paragraph("text")
    doc.add_picture(str(png))
    path = tmp_path / "refs.docx"
    doc.save(str(path))

    document = Document(str(path))
    counts = count_image_references(document)

    assert sum(counts.values()) == 3
    assert len(counts) == 1


def test_apply_pdf_images_drops_recurring_by_reference_count(tmp_path: Path) -> None:
    png = make_png(tmp_path / "banner.png", color=(1.0, 0.0, 0.0))
    doc = Document()
    for _ in range(5):
        doc.add_picture(str(png))
    path = tmp_path / "banner.docx"
    doc.save(str(path))

    document = Document(str(path))
    assets = extract_images(document).assets

    updated, banner_rel_ids, substituted, dropped = apply_pdf_images(
        assets, document, [], page_count=10
    )

    assert updated == []
    assert banner_rel_ids == {assets[0].rel_id}
    assert substituted == 0
    assert dropped == 5


def test_apply_pdf_images_matches_by_display_size(tmp_path: Path) -> None:
    art_png = make_png(tmp_path / "art.png", color=(0.0, 0.0, 1.0))
    doc = Document()
    doc.add_picture(str(art_png))
    path = tmp_path / "art.docx"
    doc.save(str(path))

    document = Document(str(path))
    asset = extract_images(document).assets[0]
    jpeg = b"\xff\xd8\xff\xe0" + b"0" * 100 + b"\xff\xd9"
    pdf_image = PdfImage(
        xref=2,
        media_type="image/jpeg",
        data=jpeg,
        width=1360,
        height=1920,
        digest="art",
        display_sizes=[(asset.width * 0.75, asset.height * 0.75)],
    )

    updated, banner_rel_ids, substituted, _dropped = apply_pdf_images(
        [asset], document, [pdf_image], page_count=100
    )

    assert banner_rel_ids == set()
    assert substituted == 1
    assert updated[0].media_type == "image/jpeg"
    assert updated[0].file_name.endswith(".jpg")
    assert (updated[0].width, updated[0].height) == (1360, 1920)


def test_apply_pdf_images_excludes_margin_repeat_from_matching(tmp_path: Path) -> None:
    png = make_png(tmp_path / "banner.png", color=(1.0, 0.0, 0.0))
    doc = Document()
    doc.add_picture(str(png))
    path = tmp_path / "banner.docx"
    doc.save(str(path))

    document = Document(str(path))
    asset = extract_images(document).assets[0]
    banner = PdfImage(
        xref=1,
        media_type="image/png",
        data=asset.data,
        width=158,
        height=74,
        digest="banner",
        is_margin_repeat=True,
        display_sizes=[(asset.width * 0.75, asset.height * 0.75)],
    )

    updated, banner_rel_ids, substituted, _dropped = apply_pdf_images(
        [asset], document, [banner], page_count=100
    )

    assert len(updated) == 1
    assert banner_rel_ids == set()
    assert substituted == 0


def test_aligns_same_size_images_one_to_one(tmp_path: Path) -> None:
    first = make_png(tmp_path / "a.png", color=(1.0, 0.0, 0.0))
    second = make_png(tmp_path / "b.png", color=(0.0, 0.0, 1.0))
    doc = Document()
    doc.add_picture(str(first))
    doc.add_picture(str(second))
    path = tmp_path / "two.docx"
    doc.save(str(path))

    document = Document(str(path))
    assets = extract_images(document).assets
    assert len(assets) == 2
    size0 = (assets[0].width * 0.75, assets[0].height * 0.75)
    size1 = (assets[1].width * 0.75, assets[1].height * 0.75)
    jpeg_a = b"\xff\xd8\xff\xe0" + b"A" * 80 + b"\xff\xd9"
    jpeg_b = b"\xff\xd8\xff\xe0" + b"B" * 80 + b"\xff\xd9"
    pdf_images = [
        PdfImage(1, "image/jpeg", jpeg_a, 100, 150, "a", display_sizes=[size0, size1]),
        PdfImage(2, "image/jpeg", jpeg_b, 100, 150, "b", display_sizes=[size0, size1]),
    ]

    updated, _banners, substituted, _dropped = apply_pdf_images(
        assets, document, pdf_images, page_count=100
    )

    assert substituted == 2
    assert updated[0].data == jpeg_a
    assert updated[1].data == jpeg_b


def test_aligns_without_reuse_when_counts_differ(tmp_path: Path) -> None:
    art = make_png(tmp_path / "art.png", color=(0.0, 0.0, 1.0))
    doc = Document()
    doc.add_picture(str(art))
    path = tmp_path / "one.docx"
    doc.save(str(path))

    document = Document(str(path))
    asset = extract_images(document).assets[0]
    size = (asset.width * 0.75, asset.height * 0.75)
    first = PdfImage(
        1, "image/jpeg", b"\xff\xd8first\xff\xd9", 100, 150, "a", display_sizes=[size]
    )
    second = PdfImage(
        2, "image/jpeg", b"\xff\xd8second\xff\xd9", 100, 150, "b", display_sizes=[size]
    )

    updated, _banners, substituted, _dropped = apply_pdf_images(
        [asset], document, [first, second], page_count=100
    )

    assert substituted == 1
    assert updated[0].data == first.data

