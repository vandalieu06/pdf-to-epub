"""Extract embedded images from the intermediate DOCX.

`pdf2docx` places PDF artwork as DrawingML (or VML) pictures, which we read here so
they can be re-embedded in the EPUB.
"""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from dataclasses import dataclass, field, replace
from pathlib import Path

import pymupdf
from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from ..models import ImageAsset
from ..pdf.images import PdfImage

EMU_PER_PX = 9525.0

_DRAWING = qn("w:drawing")
_PICT = qn("w:pict")
_BLIP = qn("a:blip")
_EMBED = qn("r:embed")
_LINK = qn("r:link")
_IMAGEDATA = "{urn:schemas-microsoft-com:vml}imagedata"
_RID = qn("r:id")
_EXTENT = qn("wp:extent")

_EXTENSION_BY_TYPE = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}


def extension_for(media_type: str) -> str:
    """Return a safe file extension for a media type."""
    return _EXTENSION_BY_TYPE.get(media_type.lower(), ".img")


def image_pixel_dimensions(data: bytes) -> tuple[int, int] | None:
    """Return (width, height) for a PNG or JPEG byte string, else None."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        import struct

        return struct.unpack(">II", data[16:24])
    if data[:2] == b"\xff\xd8":
        import struct

        index = 2
        while index < len(data) - 9:
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3):
                height, width = struct.unpack(">HH", data[index + 5 : index + 9])
                return width, height
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                index += 2
                continue
            index += 2 + ((data[index + 2] << 8) + data[index + 3])
    return None


@dataclass(slots=True)
class ImageExtraction:
    """Result of scanning a DOCX for images."""

    assets: list[ImageAsset] = field(default_factory=list)
    found: int = 0
    dropped: int = 0


def _iter_paragraphs(document: object) -> list[Paragraph]:
    paragraphs: list[Paragraph] = []
    for item in document.iter_inner_content():
        if isinstance(item, Paragraph):
            paragraphs.append(item)
        elif isinstance(item, Table):
            for row in item.rows:
                for cell in row.cells:
                    paragraphs.extend(cell.paragraphs)
    return paragraphs


def _picture_references(node: object) -> list[tuple[str, float | None, float | None]]:
    """Return (relationship_id, width_px, height_px) for a drawing/pict node."""
    references: list[tuple[str, float | None, float | None]] = []
    blip = node.find(".//" + _BLIP)
    if blip is not None:
        rid = blip.get(_EMBED) or blip.get(_LINK)
        if rid:
            width = height = None
            extent = node.find(".//" + _EXTENT)
            if extent is not None:
                cx = extent.get("cx")
                cy = extent.get("cy")
                if cx:
                    width = int(cx) / EMU_PER_PX
                if cy:
                    height = int(cy) / EMU_PER_PX
            references.append((rid, width, height))
    imgdata = node.find(".//" + _IMAGEDATA)
    if imgdata is not None:
        rid = imgdata.get(_RID)
        if rid:
            references.append((rid, None, None))
    return references


def extract_images(
    document: Document,
    *,
    min_px: int = 24,
    keep_all: bool = False,
) -> ImageExtraction:
    """Extract unique images from a DOCX in document order.

    Identical images (same bytes) are kept once; images smaller than `min_px` on
    their shortest side are dropped unless `keep_all` is set.
    """
    extraction = ImageExtraction()
    seen_hashes: set[str] = set()
    index = 0

    for paragraph in _iter_paragraphs(document):
        for node in paragraph._p.iter():
            if node.tag not in (_DRAWING, _PICT):
                continue
            for rid, width, height in _picture_references(node):
                rel = document.part.rels.get(rid)
                if rel is None or rel.is_external:
                    continue
                extraction.found += 1
                data: bytes = rel.target_part.blob
                media_type = rel.target_part.content_type
                digest = hashlib.sha256(data).hexdigest()
                if digest in seen_hashes:
                    extraction.dropped += 1
                    continue
                if (
                    not keep_all
                    and width is not None
                    and height is not None
                    and min(width, height) < min_px
                ):
                    extraction.dropped += 1
                    continue
                seen_hashes.add(digest)
                file_name = f"images/img_{index:04d}{extension_for(media_type)}"
                extraction.assets.append(
                    ImageAsset(
                        uid=f"img_{index:04d}",
                        file_name=file_name,
                        media_type=media_type,
                        data=data,
                        width=width,
                        height=height,
                        position_index=index,
                        sha256=digest,
                        rel_id=rid,
                    )
                )
                index += 1

    return extraction


def picture_rids(node: object) -> list[str]:
    """Return the image relationship ids referenced by a drawing/VML node."""
    return [rid for rid, _width, _height in _picture_references(node)]


def _optimize_asset(asset: ImageAsset, quality: int) -> ImageAsset:
    """Re-encode an opaque image to JPEG when that makes it smaller."""
    try:
        pixmap = pymupdf.Pixmap(asset.data)
    except Exception:  # noqa: BLE001 - unknown/unsupported image format
        return asset
    if pixmap.alpha:
        return asset
    try:
        data = pixmap.tobytes("jpeg", jpg_quality=quality)
    except Exception:  # noqa: BLE001
        return asset
    if len(data) >= len(asset.data):
        return asset
    file_name = str(Path(asset.file_name).with_suffix(".jpg"))
    return replace(asset, file_name=file_name, media_type="image/jpeg", data=data)


def optimize_images(assets: list[ImageAsset], *, quality: int = 85) -> list[ImageAsset]:
    """Return assets with opaque images re-encoded to JPEG (smaller) where possible."""
    return [_optimize_asset(asset, quality) for asset in assets]


def select_cover(assets: list[ImageAsset]) -> ImageAsset | None:
    """Return the cover: the first image in reading order.

    Light novels always place the cover as the first image of the document. An explicit
    `--cover` overrides this at the EPUB-building stage.
    """
    return assets[0] if assets else None


@dataclass(slots=True)
class ImagePart:
    """A unique image part of the DOCX, in first-appearance order."""

    rel_id: str
    media_type: str
    data: bytes


def unique_image_parts(document: Document) -> list[ImagePart]:
    """Return the DOCX image parts in first-appearance order (unique by rel_id)."""
    seen: set[str] = set()
    parts: list[ImagePart] = []
    for paragraph in _iter_paragraphs(document):
        for node in paragraph._p.iter():
            if node.tag not in (_DRAWING, _PICT):
                continue
            for rid, _width, _height in _picture_references(node):
                if rid in seen:
                    continue
                rel = document.part.rels.get(rid)
                if rel is None or rel.is_external:
                    continue
                seen.add(rid)
                parts.append(
                    ImagePart(
                        rel_id=rid,
                        media_type=rel.target_part.content_type,
                        data=rel.target_part.blob,
                    )
                )
    return parts


def count_image_references(document: Document) -> dict[str, int]:
    """Count how many times each image `rel_id` is referenced in the document."""
    counts: dict[str, int] = defaultdict(int)
    for paragraph in _iter_paragraphs(document):
        for node in paragraph._p.iter():
            if node.tag not in (_DRAWING, _PICT):
                continue
            for rid, _width, _height in _picture_references(node):
                rel = document.part.rels.get(rid)
                if rel is None or rel.is_external:
                    continue
                counts[rid] += 1
    return dict(counts)


_PX_TO_PT = 0.75
_MAX_SIZE_DISTANCE = 0.8


def _display_size_distance(asset: ImageAsset, pdf_image: PdfImage) -> float | None:
    """Distance between a DOCX asset's displayed size and a PDF image placement."""
    if asset.width is None or asset.height is None:
        return None
    doc_width = asset.width * _PX_TO_PT
    doc_height = asset.height * _PX_TO_PT
    if doc_width <= 0 or doc_height <= 0:
        return None
    best: float | None = None
    for pdf_width, pdf_height in pdf_image.display_sizes:
        if pdf_width <= 0 or pdf_height <= 0:
            continue
        distance = abs(math.log(doc_width / pdf_width)) + abs(
            math.log(doc_height / pdf_height)
        )
        if best is None or distance < best:
            best = distance
    return best


_GAP_PENALTY = 1.0


def align_assets_to_pdf(
    assets: list[ImageAsset], pdf_images: list[PdfImage]
) -> dict[int, PdfImage]:
    """Assign at most one PDF image to each asset (and vice versa), preserving order.

    With equal counts the mapping is by document order. Otherwise a monotonic
    Needleman-Wunsch alignment fills the gaps (dropped pages, filtered images) using the
    displayed size only to validate that a pairing is plausible.
    """
    if not assets or not pdf_images:
        return {}
    if len(assets) == len(pdf_images):
        return {index: pdf_images[index] for index in range(len(assets))}

    asset_count = len(assets)
    image_count = len(pdf_images)
    costs: list[list[float | None]] = [
        [
            _display_size_distance(assets[i], pdf_images[j])
            for j in range(image_count)
        ]
        for i in range(asset_count)
    ]

    infinity = float("inf")
    dp = [[infinity] * (image_count + 1) for _ in range(asset_count + 1)]
    for i in range(asset_count + 1):
        dp[i][0] = i * _GAP_PENALTY
    for j in range(image_count + 1):
        dp[0][j] = j * _GAP_PENALTY

    for i in range(1, asset_count + 1):
        for j in range(1, image_count + 1):
            best = min(
                dp[i - 1][j] + _GAP_PENALTY,
                dp[i][j - 1] + _GAP_PENALTY,
            )
            distance = costs[i - 1][j - 1]
            if distance is not None and distance <= _MAX_SIZE_DISTANCE:
                best = min(best, dp[i - 1][j - 1] + distance)
            dp[i][j] = best

    mapping: dict[int, PdfImage] = {}
    i, j = asset_count, image_count
    while i > 0 and j > 0:
        if dp[i][j - 1] + _GAP_PENALTY == dp[i][j]:
            j -= 1
            continue
        if dp[i - 1][j] + _GAP_PENALTY == dp[i][j]:
            i -= 1
            continue
        distance = costs[i - 1][j - 1]
        if (
            distance is not None
            and distance <= _MAX_SIZE_DISTANCE
            and dp[i][j] == dp[i - 1][j - 1] + distance
        ):
            mapping[i - 1] = pdf_images[j - 1]
            i -= 1
            j -= 1
        else:
            i -= 1
    return mapping


def apply_pdf_images(
    assets: list[ImageAsset],
    document: Document,
    pdf_images: list[PdfImage],
    *,
    page_count: int = 0,
    min_image_px: int = 24,
) -> tuple[list[ImageAsset], set[str], int, int]:
    """Replace DOCX images with the PDF originals and drop recurring margin banners.

    Returns the updated assets, the dropped banner rel_ids, the number of substituted
    images and the number of references removed with the banners.
    """
    references = count_image_references(document)
    threshold = max(3, math.ceil(page_count * 0.25)) if page_count else 3

    candidates = [
        image
        for image in pdf_images
        if not image.is_margin_repeat and min(image.width, image.height) >= min_image_px
    ]
    kept_assets = [
        asset
        for asset in assets
        if references.get(asset.rel_id, 0) < threshold
    ]
    mapping = align_assets_to_pdf(kept_assets, candidates)
    kept_index = {id(asset): index for index, asset in enumerate(kept_assets)}

    updated: list[ImageAsset] = []
    banner_rel_ids: set[str] = set()
    substituted = 0
    dropped_references = 0

    for asset in assets:
        if references.get(asset.rel_id, 0) >= threshold:
            banner_rel_ids.add(asset.rel_id)
            dropped_references += references.get(asset.rel_id, 0)
            continue
        match = mapping.get(kept_index.get(id(asset), -1))
        if match is not None:
            new_name = str(
                Path(asset.file_name).with_suffix(extension_for(match.media_type))
            )
            asset = replace(
                asset,
                data=match.data,
                media_type=match.media_type,
                file_name=new_name,
                width=float(match.width),
                height=float(match.height),
            )
            substituted += 1
        updated.append(asset)

    return updated, banner_rel_ids, substituted, dropped_references


def write_images_to_dir(assets: list[ImageAsset], directory: Path) -> None:
    """Debug helper: dump extracted images to a directory."""
    directory.mkdir(parents=True, exist_ok=True)
    for asset in assets:
        (directory / Path(asset.file_name).name).write_bytes(asset.data)
