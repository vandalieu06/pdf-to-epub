"""Extract the original embedded images from a PDF.

`pdf2docx` re-rasterises illustration pages (page-aspect, ~260 DPI), distorting the
artwork. We read the **original** images with PyMuPDF so the EPUB can use them
unchanged, and we flag images that repeat in the margin bands (logos/scan banners) so
they can be dropped instead of being inserted on every page.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

DEFAULT_MARGIN = 0.08

_MEDIA_TYPES = {
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "tiff": "image/tiff",
    "webp": "image/webp",
}


@dataclass(slots=True)
class PdfImage:
    """An embedded PDF image, in first-placement order."""

    xref: int
    media_type: str
    data: bytes
    width: int
    height: int
    digest: str
    is_margin_repeat: bool = False
    placements: int = 0
    display_sizes: list[tuple[float, float]] = field(default_factory=list)


def _media_type(extension: str) -> str:
    return _MEDIA_TYPES.get(extension.lower(), f"image/{extension.lower()}")


def _digest(info: dict) -> str:
    raw = info.get("digest")
    if isinstance(raw, bytes):
        return raw.hex()
    if raw:
        return str(raw)
    return str(info.get("xref", ""))


def extract_pdf_images(
    path: Path,
    *,
    header_margin: float = DEFAULT_MARGIN,
    footer_margin: float = DEFAULT_MARGIN,
    min_ratio: float = 0.5,
) -> list[PdfImage]:
    """Return the unique embedded images, in first-placement order.

    `is_margin_repeat` marks images whose placement falls in a margin band on at least
    `min_ratio` of the pages (recurring banners/logos).
    """
    images: list[PdfImage] = []
    margin_pages: dict[str, set[int]] = defaultdict(set)
    placements: dict[str, int] = defaultdict(int)
    display_sizes: dict[str, list[tuple[float, float]]] = defaultdict(list)
    seen: set[int] = set()

    with pymupdf.open(path) as doc:
        page_count = doc.page_count
        min_pages = max(2, math.ceil(page_count * min_ratio))

        for page_index, page in enumerate(doc):
            height = page.rect.height
            top_limit = height * header_margin
            bottom_limit = height * (1.0 - footer_margin)
            for info in page.get_image_info(xrefs=True):
                xref = int(info.get("xref", 0))
                if xref == 0:
                    continue
                digest = _digest(info)
                placements[digest] += 1
                bbox = info["bbox"]
                display_sizes[digest].append((bbox[2] - bbox[0], bbox[3] - bbox[1]))
                center_y = (bbox[1] + bbox[3]) / 2.0
                if center_y <= top_limit or center_y >= bottom_limit:
                    margin_pages[digest].add(page_index)
                if xref in seen:
                    continue
                seen.add(xref)
                raw = doc.extract_image(xref)
                images.append(
                    PdfImage(
                        xref=xref,
                        media_type=_media_type(raw.get("ext", "png")),
                        data=raw["image"],
                        width=int(raw.get("width", 0)),
                        height=int(raw.get("height", 0)),
                        digest=digest,
                    )
                )

    for image in images:
        image.placements = placements.get(image.digest, 0)
        image.is_margin_repeat = len(margin_pages.get(image.digest, set())) >= min_pages
        image.display_sizes = display_sizes.get(image.digest, [])

    return images
