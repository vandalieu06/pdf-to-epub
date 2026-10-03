---
code: "11"
title: "Remove repeated margin images (banners/logos)"
status: completed
version: "0.1.0"
project: "pdf-to-epub"
date: 2026-09-18
tags: [spec, sdd]
affected_files:
  - src/pdf_to_epub/core/pdf/images.py
  - src/pdf_to_epub/core/docx/images.py
  - src/pdf_to_epub/core/pipeline.py
  - src/pdf_to_epub/core/models.py
  - src/pdf_to_epub/cli.py
  - tests/core/pdf/test_images.py
  - tests/core/docx/test_images.py
  - docs/arquitectura.md
  - docs/uso.md
  - docs/features.md
---

# 11 — Remove repeated margin images (banners/logos)

## Purpose

Remove decorative header/footer **images** (publisher logos, scan banners) that repeat on
every page, so they are not treated as illustrations and inserted hundreds of times in the
EPUB.

## Context

The validation novel (`Haburare Rune Tsukai`) has a 696×230 "Ichijou Translations" banner
image placed in the bottom margin of **all 203 pages** (`get_image_info` rectangle
`(3,718,214,788)` on a 612×792 page, centre y ≈ 753 → bottom band). The header/footer pass
only detected **text**, so the banner survived and `pdf2docx` inserted it as an
illustration: the first EPUB referenced that image **188 times** and weighed 8.5 MB.

## Proposed change

Detect recurring margin images from the PDF and **drop them from the EPUB** (not by
redacting the PDF, see the technical decision):

- `core/pdf/images.py: extract_pdf_images` groups image placements by digest; an image whose
  placement centre falls in a margin band on at least `min_ratio` of the pages is marked
  `is_margin_repeat` (and counts its `placements`).
- `core/docx/images.py: apply_pdf_images` drops the matching DOCX asset (identified by the
  order mapping from spec 12, with a pixel-size fallback) and returns its `rel_id`, which is
  excluded from chapter rendering.
- `ConversionReport.header_footer_images` reports the number of banner **placements**
  removed; shown in the CLI summary.

## Technical decision

- **Do not redact the banner in the PDF.** The banner overlaps the illustration on the same
  page; `apply_redactions(images=PDF_REDACT_IMAGE_REMOVE)` removes any intersecting image and
  destroyed every illustration in the first attempt (EPUB fell to 1 image). Dropping the
  asset at the EPUB stage is safe and precise.
- Images are identified by `digest` (not xref) so repeated placements compare equal, and
  matched to DOCX parts through the spec 12 order mapping.

## Affected files

- `src/pdf_to_epub/core/pdf/images.py` (new), `core/docx/images.py`, `core/pipeline.py`,
  `core/models.py`, `core/cli.py`.
- `tests/core/pdf/test_images.py`, `tests/core/docx/test_images.py`.
- `docs/arquitectura.md`, `docs/uso.md`, `docs/features.md`.

## Tests

- A repeated image in the bottom band is flagged `is_margin_repeat` with its placement count.
- A body image (same size, different digest) is not flagged.
- `apply_pdf_images` drops the banner asset and keeps the illustration.
- The validation novel's EPUB has 0 references to the banner.

## Acceptance criteria

- The validation novel's banner is absent from the EPUB (0 references); illustrations remain.
- Real illustrations are never removed.
- `pytest -q` and `ruff check .` pass.
