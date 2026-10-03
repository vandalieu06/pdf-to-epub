"""Assemble the final EPUB 3 from cleaned chapters and embedded images."""

from __future__ import annotations

import mimetypes
import os
from collections.abc import Callable
from pathlib import Path

from ebooklib import epub

from ..config import ConversionOptions
from ..docx.images import extension_for, select_cover
from ..models import Chapter, ImageAsset, PdfMetadata
from .metadata import apply_metadata

_STYLE = """
body { font-family: serif; line-height: 1.5; margin: 1em; }
h1 { text-align: center; margin: 1.5em 0 1em; }
h2, h3, h4, h5, h6 { margin: 1.2em 0 0.5em; }
p { margin: 0 0 0.6em; text-indent: 1.2em; }
img { display: block; max-width: 100%; height: auto; margin: 1em auto; }
table { border-collapse: collapse; margin: 1em auto; }
td { border: 1px solid #999; padding: 0.3em 0.6em; }
.cover { margin: 0; padding: 0; text-align: center; }
.cover img { max-width: 100%; max-height: 100vh; margin: 0 auto; }
""".strip()


def _resolve_cover(
    options: ConversionOptions, images: list[ImageAsset]
) -> tuple[str, bytes] | None:
    """Return (file_name, data) for the cover, or None."""
    if options.cover is not None and options.cover.exists():
        media_type = mimetypes.guess_type(options.cover.name)[0] or "image/jpeg"
        return f"images/cover{extension_for(media_type)}", options.cover.read_bytes()

    auto_cover = select_cover(images)
    if auto_cover is not None:
        auto_cover.is_cover = True
        return auto_cover.file_name, auto_cover.data
    return None


def build_epub(
    chapters: list[Chapter],
    images: list[ImageAsset],
    metadata: PdfMetadata,
    options: ConversionOptions,
    *,
    progress: Callable[[str], None] | None = None,
) -> Path:
    """Build the EPUB and return its path."""
    if progress:
        progress("Building EPUB")

    book = epub.EpubBook()
    apply_metadata(book, metadata, options)

    style = epub.EpubItem(
        uid="style_default",
        file_name="style/default.css",
        media_type="text/css",
        content=_STYLE,
    )
    book.add_item(style)

    cover = _resolve_cover(options, images)
    cover_file = cover[0] if cover is not None else None
    first_image = images[0].file_name if images else None
    cover_page: epub.EpubHtml | None = None
    if cover is not None:
        book.set_cover(cover[0], cover[1], create_page=False)
        cover_page = epub.EpubHtml(
            uid="cover",
            title="Portada",
            file_name="cover.xhtml",
            lang=options.language or "es",
        )
        cover_page.content = (
            f'<div class="cover"><img src="{cover[0]}" alt="Portada"/></div>'
        )
        cover_page.add_item(style)
        book.add_item(cover_page)

    for asset in images:
        if asset.file_name == first_image or asset.file_name == cover_file:
            continue
        book.add_item(
            epub.EpubImage(
                uid=asset.uid,
                file_name=asset.file_name,
                media_type=asset.media_type,
                content=asset.data,
            )
        )

    spine: list[object] = []
    if cover_page is not None:
        spine.append(cover_page)
    spine.append("nav")

    toc: list[epub.EpubHtml] = []
    for chapter in chapters:
        item = epub.EpubHtml(
            title=chapter.title,
            file_name=chapter.file_name,
            lang=options.language or "es",
        )
        item.content = chapter.html
        item.add_item(style)
        book.add_item(item)
        spine.append(item)
        toc.append(item)

    book.toc = tuple(toc)
    book.spine = spine
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    output = options.resolved_output()
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(output.name + ".tmp")
    epub.write_epub(str(temp), book)
    os.replace(temp, output)
    return output
