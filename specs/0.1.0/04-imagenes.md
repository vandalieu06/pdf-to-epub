---
code: "04"
title: "Image preservation (PDF → DOCX → EPUB)"
status: completed
version: "0.1.0"
project: "pdf-to-epub"
date: 2026-09-18
tags: [spec, sdd]
affected_files:
  - src/pdf_to_epub/core/docx/images.py
  - src/pdf_to_epub/core/epub/builder.py
  - src/pdf_to_epub/core/models.py
  - src/pdf_to_epub/core/config.py
  - tests/core/docx/test_images.py
  - tests/core/epub/test_images.py
  - tests/fixtures/
  - docs/uso.md
---

# 04 — Image preservation (PDF → DOCX → EPUB)

## Purpose

Ensure light-novel illustrations survive the whole pipeline and appear in the EPUB, in a
position consistent with the original PDF.

## Context

Light novels carry illustrations (cover, color plates, inline art). Choosing DOCX as the
intermediate matters here: `pdf2docx` extracts embedded images and places them as inline
(or floating) pictures in the DOCX, and `python-docx` can read those image parts and their
bytes. EPUB, being a ZIP of XHTML, can then embed those bytes as `EpubImage` items and
reference them from the chapter HTML.

Risks: images may be duplicated by `pdf2docx`, may be tiny decorations/spacers, may be
floating (anchored) rather than inline, and the cover may need to be identified
separately.

## Proposed change

### Extraction (`core/docx/images.py`)

- Iterate the document body in order (`doc.iter_inner_content()`), and for each run's
  drawing detect pictures with `Drawing.has_picture`.
- For each picture, read bytes via `drawing.image.blob`, its content type
  (`drawing.image.content_type`), and its displayed size from the drawing extent (EMU →
  px/pt).
- Also inspect `document.part.rels` for image parts not reachable through inline drawings
  (floating/anchored images, headers) to avoid silently dropping them.
- Return `ImageAsset(uid, filename, media_type, data, width, height, position_index,
  is_cover)`.

Rules:

- Deduplicate identical images by content hash (SHA-256). Keep the first occurrence's
  position; ignore later duplicate bytes that only repeat (e.g. decorative rules).
- Filter spacer/decorative images below a minimum area (default 24×24 px, configurable)
  unless `--keep-all-images`.
- Derive a stable filename per asset (`images/img_0001.<ext>`) from media type.
- Cover detection: a page-sized image near the start (or the first large image) is marked
  as the cover candidate; an explicit `--cover <path>` overrides it.

### Embedding (`core/epub/builder.py`)

- Add every `ImageAsset` as `ebooklib.epub.EpubImage` with matching `file_name`.
- Insert `<img src="..."/>` at the asset's position in the chapter XHTML, wrapped in a
  figure/paragraph consistent with the chapter flow.
- If a cover candidate exists, call `book.set_cover(filename, data)` (and keep it out of
  the normal chapter flow).
- Preserve aspect ratio; when width/height are known, emit CSS `max-width:100%` and a
  style hint rather than hard pixel sizes where possible.
- Report counts in `ConversionReport` (images extracted / embedded / dropped).

## Technical decision

- Extract images at the **DOCX** stage (not the PDF stage) because `pdf2docx` has already
  resolved embedded/vector artwork into image parts and placed them in reading order.
- Deduplicate by hash and filter tiny assets by default to avoid the EPUB being flooded
  with decorative separators; both behaviors are configurable.
- Store images in `images/` inside the EPUB and reference by relative path.
- Sanitize filenames and never trust the DOCX `file_name` for the EPUB path.

## Affected files

- `src/pdf_to_epub/core/docx/images.py` — new.
- `src/pdf_to_epub/core/epub/builder.py` — embed images and cover.
- `src/pdf_to_epub/core/models.py` — `ImageAsset`.
- `src/pdf_to_epub/core/config.py` — `min_image_px`, `keep_all_images`, `cover`.
- `tests/core/docx/test_images.py`, `tests/core/epub/test_images.py` — new.
- `tests/fixtures/` — DOCX/PDF fixture with images.
- `docs/uso.md` — document cover override and image options.

## Tests

- Synthetic PDF with two distinct images and one repeated decorative image: assert two
  unique `ImageAsset`s after dedup and that decorations under the threshold are dropped.
- DOCX fixture with an inline picture: assert bytes and media type are recovered.
- Build an EPUB from a DOCX with an image: reopen with `ebooklib`, assert the image item
  exists, its media type is correct, and the chapter XHTML references it.
- Cover: assert `set_cover` path is used when a cover is detected or provided.
- Floating/anchored image in a fixture is not silently omitted.

## Acceptance criteria

- Illustrations from the PDF are present in the final EPUB and referenced by XHTML.
- Duplicates and sub-threshold decorations are removed by default; options restore them.
- Cover image (auto-detected or `--cover`) is set as the EPUB cover.
- Image extraction/embedding is covered by unit and integration tests.
