"""Map PDF metadata onto an EPUB book (Dublin Core + OPF)."""

from __future__ import annotations

import uuid

from ebooklib import epub

from ... import __version__
from ..config import ConversionOptions
from ..models import PdfMetadata


def apply_metadata(
    book: epub.EpubBook,
    pdf_metadata: PdfMetadata,
    options: ConversionOptions,
) -> None:
    """Populate `book` metadata from the PDF, applying documented fallbacks."""
    title = options.title or pdf_metadata.title or options.input_pdf.stem
    identifier = options.identifier or str(uuid.uuid4())
    language = options.language or pdf_metadata.language or "es"

    book.set_identifier(identifier)
    book.set_title(title)
    book.set_language(language)

    authors = [options.author] if options.author else pdf_metadata.authors
    for author in authors:
        if author:
            book.add_author(author)

    if pdf_metadata.subject:
        book.add_metadata("DC", "description", pdf_metadata.subject)
    for keyword in pdf_metadata.keywords:
        book.add_metadata("DC", "subject", keyword)
    if pdf_metadata.creation_date:
        book.add_metadata("DC", "date", pdf_metadata.creation_date.strftime("%Y-%m-%d"))

    book.add_metadata("DC", "source", options.input_pdf.name)

    provenance = " / ".join(
        part for part in (pdf_metadata.creator, pdf_metadata.producer) if part
    )
    if provenance:
        book.add_metadata(None, "meta", "", {"name": "pdf-provenance", "content": provenance})
    book.add_metadata(
        None, "meta", "", {"name": "pdf-to-epub-version", "content": __version__}
    )
