---
code: "15"
title: "Match DOCX drawings to PDF images by displayed size"
status: completed
version: "0.1.0"
project: "pdf-to-epub"
date: 2026-09-18
tags: [spec, sdd]
affected_files:
  - src/pdf_to_epub/core/pdf/images.py
  - src/pdf_to_epub/core/docx/images.py
  - src/pdf_to_epub/core/pipeline.py
  - tests/core/pdf/test_images.py
  - tests/core/docx/test_images.py
---

# 15 — Match DOCX drawings to PDF images by displayed size

## Purpose

Make the substitution with original PDF images work even when pdf2docx does not emit exactly
one part per PDF image (dropped pages, re-encodings), and use the match to identify banners.

## Context

`apply_pdf_images` only substituted when the DOCX and PDF unique-image counts were equal and
relied on document order. For `Kanojo ga Harem o Susumete Kuru. 3` the counts differ (page 4
fails in pdf2docx), so no substitution happened: the EPUB kept pdf2docx's page-aspect rasters
(2382×3368) instead of the originals (1805×2589, …), and one recurring footer image slipped
through.

## Proposed change

- `core/pdf/images.py`: `PdfImage.display_sizes: list[tuple[float, float]]` records the
  placement bbox width/height (in points) of each image.
- `core/docx/images.py`: match each DOCX asset to the PDF image whose display size (converted
  from EMU/pixels to points: `px * 0.75`) is closest by
  `|log(w_doc/w_pdf)| + |log(h_doc/h_pdf)|`, with the first-appearance order as tie-breaker.
- On a match: replace the asset bytes/media type/file name with the PDF original; if the
  matched image is a margin repeat, drop the asset instead (spec 11/14).
- If no PDF images are available, keep the DOCX assets unchanged.

## Technical decision

- Displayed size is available in both pipelines (DOCX `wp:extent`, PDF placement bbox) and is
  unaffected by pdf2docx's raster re-encoding, so it is a stable matching key.
- The logarithmic distance compares scale and aspect at once and is cheap.

## Affected files

- `src/pdf_to_epub/core/pdf/images.py`, `core/docx/images.py`, `core/pipeline.py`.
- `tests/core/pdf/test_images.py`, `tests/core/docx/test_images.py`.

## Tests

- Matching maps a DOCX asset to the PDF image with the same displayed size when counts differ.
- The matched asset gets the original bytes/media type; unmatched assets are kept.
- A matched margin-repeat image is dropped.

## Acceptance criteria

- Validation novel: EPUB illustrations use the original sizes (e.g. 1805×2589), not page
  rasters; no wrong-image swaps.
- `pytest -q` and `ruff check .` pass.
