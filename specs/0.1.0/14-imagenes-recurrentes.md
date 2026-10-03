---
code: "14"
title: "Drop recurring images by DOCX reference count"
status: completed
version: "0.1.0"
project: "pdf-to-epub"
date: 2026-09-18
tags: [spec, sdd]
affected_files:
  - src/pdf_to_epub/core/docx/images.py
  - src/pdf_to_epub/core/pipeline.py
  - src/pdf_to_epub/core/models.py
  - src/pdf_to_epub/cli.py
  - tests/core/docx/test_images.py
---

# 14 — Drop recurring images by DOCX reference count

## Purpose

Remove decorative images that repeat on most pages (headers, footers, scan banners) even
when the PDF→DOCX mapping fails or pdf2docx distorts them.

## Context

In `Kanojo ga Harem o Susumete Kuru. 3`, four margin images (a 158×74 header and three
footer logos) appear on all 132 pages (528 placements). The PDF detection flags them, but
`apply_pdf_images` could not drop them because:

- the DOCX/PDF image counts did not match (page 4 failed in pdf2docx), so no order mapping
  was built, and
- the pixel-size fallback missed the one pdf2docx **stretched** (512×135 instead of
  226×94/189×94).

The result: `img_0005` was inserted **121 times** in the EPUB. The report also counted PDF
placements (`528 margin images removed`) rather than the images actually dropped.

## Proposed change

In `core/docx/images.py`:

- `count_image_references(document) -> dict[str, int]` counts how many times each image
  `rel_id` is referenced.
- `apply_pdf_images(..., page_count)` drops any asset whose `rel_id` is referenced at least
  `max(3, ceil(page_count * 0.25))` times (recurring image), in addition to the PDF margin
  flags.
- `ConversionReport.header_footer_images` reflects the assets **actually dropped**, and the
  CLI summary uses that value.

## Technical decision

- Reference count is independent of image distortion and of DOCX↔PDF ordering, so it is the
  most robust signal for recurring page furniture.
- The threshold (`25 %` of pages, minimum 3) avoids dropping a genuinely repeated ornament
  used a handful of times while catching per-page headers/footers.

## Affected files

- `src/pdf_to_epub/core/docx/images.py`, `core/pipeline.py`, `core/models.py`, `core/cli.py`.
- `tests/core/docx/test_images.py`.

## Tests

- A DOCX asset referenced many times is dropped; a one-off asset is kept.
- The report count equals the number of dropped assets' placements.

## Acceptance criteria

- The validation novel's recurring footer image is absent from the EPUB (0 references).
- Real illustrations are not dropped.
- `pytest -q` and `ruff check .` pass.
