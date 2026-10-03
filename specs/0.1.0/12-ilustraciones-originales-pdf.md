---
code: "12"
title: "Use the original PDF images instead of pdf2docx page rasters"
status: completed
version: "0.1.0"
project: "pdf-to-epub"
date: 2026-09-18
tags: [spec, sdd]
affected_files:
  - src/pdf_to_epub/core/pdf/images.py
  - src/pdf_to_epub/core/docx/images.py
  - src/pdf_to_epub/core/config.py
  - src/pdf_to_epub/core/pipeline.py
  - src/pdf_to_epub/cli.py
  - src/pdf_to_epub/core/models.py
  - tests/core/pdf/test_images.py
  - tests/core/docx/test_images.py
  - tests/core/test_pipeline.py
  - docs/arquitectura.md
  - docs/uso.md
  - docs/features.md
---

# 12 — Use the original PDF images instead of pdf2docx page rasters

## Purpose

Preserve the original illustrations (pixels, aspect ratio, format) instead of the
re-rasterised, distorted copies `pdf2docx` produces.

## Context

For the validation novel, `pdf2docx` emits **page-sized rasters** for illustration pages
instead of the embedded images:

| PDF embedded | PDF placement aspect | DOCX/EPUB | DOCX aspect |
|--------------|----------------------|-----------|-------------|
| 1360×1920 | 0.708 | 2223×2870 | 0.774 |
| 1903×1352 | 1.407 | 3090×2371 | 1.303 (landscape page 792×612 = 1.294) |

`2223×2870` at 72 pt/inch ≈ **260 DPI** and its aspect equals the **page**, not the
embedded image: `pdf2docx` re-renders the page region, stretching/cropping the illustration
and multiplying its pixel count ~5×. This is what "junta las imágenes y estropea las
ilustraciones".

## Proposed change

After cleaning the PDF (spec 11 removes the recurring banner) and converting to DOCX,
replace the DOCX image bytes with the **original embedded images from the PDF**:

- New `core/pdf/images.py`:
  - `PdfImage(xref, media_type, data, width, height)`.
  - `extract_pdf_images(path) -> list[PdfImage]`: unique embedded images in first-placement
    order (`page.get_image_info(xrefs=True)` → `doc.extract_image(xref)`), preserving the
    original bytes/format.
- `core/docx/images.py`:
  - `unique_image_parts(document) -> list[ImagePart]` in first-appearance order (rel_id,
    media_type, data).
  - `substitute_with_pdf_images(assets, docx_parts, pdf_images) -> int`: if both unique
    lists have the **same length**, replace each asset's `data`, `media_type` and file
    extension with the corresponding PDF original; otherwise skip (best effort) and report.
- `core/pipeline.py`: run the substitution after `extract_images` (using the clean PDF that
  was actually converted) and before `optimize_images`, so the JPEG optimisation and the
  `<img src>` names use the originals.
- Option `use_pdf_images: bool = True` (CLI `--keep-docx-images` to disable). The count is
  reported.

## Technical decision

- Order-based matching (first appearance) is used because both pipelines emit images in page
  order; counts must match exactly or the substitution is skipped to avoid swapping wrong
  pictures.
- The **EPUB** is the target (assets are replaced in memory); the intermediate DOCX is left
  untouched, avoiding OOXML surgery on a 68 MB file.
- Preserves aspect ratio and resolution, removes the ~5× upscaling, and keeps the existing
  JPEG optimisation (spec 09) working on clean originals.

## Affected files

- `src/pdf_to_epub/core/pdf/images.py` (new), `core/docx/images.py`, `core/config.py`,
  `core/pipeline.py`, `core/cli.py`, `core/models.py`.
- `tests/core/pdf/test_images.py`, `tests/core/docx/test_images.py`, `tests/core/test_pipeline.py`.
- `docs/arquitectura.md`, `docs/uso.md`, `docs/features.md`.

## Tests

- `extract_pdf_images` returns the embedded images with their original dimensions/formats.
- Substitution with matching counts replaces data/media type and keeps `rel_id`/order.
- Mismatched counts leave assets untouched and return 0.
- `--keep-docx-images` disables substitution.

## Acceptance criteria

- For the validation novel, EPUB illustration dimensions/aspect match the PDF originals
  (no page-aspect rasters).
- No wrong-image swaps; fallback is safe.
- `pytest -q` and `ruff check .` pass.
