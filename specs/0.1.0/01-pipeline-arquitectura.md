---
code: "01"
title: "Conversion pipeline architecture"
status: completed
version: "0.1.0"
project: "pdf-to-epub"
date: 2026-09-18
tags: [spec, sdd]
affected_files:
  - pyproject.toml
  - .python-version
  - src/pdf_to_epub/**
  - tests/**
  - docs/arquitectura.md
  - specs/0.1.0/00-changelog.md
---

# 01 — Conversion pipeline architecture

## Purpose

Define the end-to-end architecture of the `pdf-to-epub` CLI: a faithful, inspectable
pipeline that turns a light-novel PDF into an EPUB, using DOCX as the editable
intermediate format for cleaning PDF noise and correcting the result by hand.

## Context

Light novels are distributed as PDFs that carry per-page headers/footers, page numbers,
and embedded illustrations. `ebook-convert` (Calibre) was tried and produced poor results,
so we build our own Python pipeline. PDF stores positioned glyphs, not document structure,
so any converter reconstructs by heuristics; perfection is not a goal — the EPUB must be a
good starting point that the user can edit.

The chosen route is `pdf -> clean.pdf -> docx -> epub`:

- The **DOCX** is the intervention point: Word styles enable chapter splitting and TOC
  generation, and images become reusable embedded objects.
- **Header/footer removal happens at the PDF stage** (geometry is available there) and is
  reinforced by a DOCX cleanup pass as a safety net.
- The **EPUB** is generated in pure Python (`ebooklib`), with metadata ported from the PDF.

## Proposed change

Introduce a Python package `pdf_to_epub` with a layered pipeline:

```
input.pdf
  │
  ├─[1] inspect   (pymupdf)      → PdfMetadata + page/text-block geometry
  ├─[2] clean     (pymupdf)      → detect repeated margin text, redact → input.clean.pdf
  ├─[3] to_docx   (pdf2docx)     → input.docx
  ├─[4] docx_clean(python-docx)  → drop headers/footers, normalize styles, split chapters
  └─[5] build_epub(ebooklib)     → input.epub + metadata + images + TOC
```

Each stage is a pure function/class with explicit input/output types, no global state, and
no direct `print` (progress via callbacks or the CLI layer). Stages are individually
testable without network access.

### Package layout

```
src/pdf_to_epub/
  __init__.py
  cli.py                     # Typer app + entrypoint
  core/
    __init__.py
    models.py                # PdfMetadata, Chapter, ImageAsset, ConversionReport
    config.py                # ConversionOptions (pydantic)
    pipeline.py              # orchestrates stages 1-5
    pdf/
      __init__.py
      inspect.py             # open PDF, read metadata, page blocks
      headers_footers.py     # detection + redaction
    docx/
      __init__.py
      convert.py             # pdf2docx wrapper
      clean.py               # header/footer removal, style normalization
      images.py              # extract embedded images
    epub/
      __init__.py
      builder.py             # assemble EPUB3
      metadata.py            # map PdfMetadata -> Dublin Core
      split.py               # chapter/TOC heuristics
```

### Stage contracts

- `pdf.inspect.inspect_pdf(path) -> PdfDocument` — metadata + per-page blocks.
- `pdf.headers_footers.clean_pdf(doc, options) -> Path` — writes `<name>.clean.pdf`.
- `docx.convert.to_docx(clean_pdf, out_docx) -> Path`.
- `docx.clean.clean_document(docx_path, options) -> CleanedDocx` — removes
  `section.header`/`section.footer` content and repeated boundary paragraphs.
- `docx.images.extract_images(docx) -> list[ImageAsset]`.
- `epub.split.split_chapters(docx) -> list[Chapter]`.
- `epub.builder.build_epub(metadata, chapters, images, out_epub) -> Path`.
- `pipeline.run(options) -> ConversionReport` — ties stages together.

## Technical decision

- **Python** pinned to `>=3.12,<3.14` (3.13 target). Python 3.14 is excluded because
  `pdf2docx` depends on `opencv-python-headless`, whose numpy pin historically conflicts
  with 3.14 (`numpy<2.3` has no 3.14 wheels).
- **`pymupdf`** for PDF parsing, metadata, and redaction.
- **`pdf2docx`** for PDF → DOCX (layout, paragraphs, images) despite being frozen upstream;
  it is pinned and wrapped behind `docx/convert.py` so it can be replaced.
- **`python-docx`** for reading/editing the intermediate DOCX.
- **`ebooklib`** for EPUB3 generation in pure Python — no external binaries.
- **`typer` + `rich`** for the CLI and progress output.
- Intermediate artifacts (`*.clean.pdf`, `*.docx`) are created next to the output (or in
  the workdir) and **removed on success** by default; `--keep-intermediate` keeps them (see
  specs 05 and 13).
- Domain models use `@dataclass`; configuration uses pydantic; interfaces use
  `typing.Protocol` where useful. All modules use `from __future__ import annotations`.

## Affected files

- `pyproject.toml` — project metadata, dependencies, entrypoint, ruff/pytest config.
- `.python-version` — `3.13`.
- `src/pdf_to_epub/**` — new package (all modules above).
- `tests/**` — new test suite.
- `docs/arquitectura.md` — updated with the final module map.
- `specs/0.1.0/00-changelog.md` — registered.

## Tests

- Unit test per stage with programmatically generated PDF/DOCX fixtures (via PyMuPDF),
  no network, no external binaries.
- `pipeline.run` end-to-end test on a synthetic light-novel PDF (cover image, repeated
  header/footer, 2–3 headings) asserting: output EPUB exists, reopens with `ebooklib`,
  contains expected chapters and images, and metadata fields are populated.
- Concrete assertions live in specs 02–05.

## Acceptance criteria

- `pdf-to-epub convert sample.pdf -o sample.epub` produces a valid, reopenable EPUB.
- Repeated headers/footers are absent from the EPUB.
- PDF title/author/language are reflected in EPUB metadata with documented fallbacks.
- Illustrations appear in the EPUB.
- `pytest -q` and `ruff check .` pass.
