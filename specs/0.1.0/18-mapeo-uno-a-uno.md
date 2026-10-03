---
code: "18"
title: "One-to-one monotonic image matching"
status: completed
version: "0.1.0"
project: "pdf-to-epub"
date: 2026-09-18
tags: [spec, sdd]
affected_files:
  - src/pdf_to_epub/core/docx/images.py
  - src/pdf_to_epub/core/pipeline.py
  - tests/core/docx/test_images.py
  - docs/arquitectura.md
  - specs/0.1.0/00-changelog.md
---

# 18 — One-to-one monotonic image matching

## Purpose

Fix the illustrations regression introduced by spec 15: the "nearest displayed size" match
was many-to-one, so several DOCX drawings could map to the same PDF image, duplicating some
illustrations and dropping others.

## Context

For `Yuri Elf to Norowareta Hime` the PDF has 19 distinct illustrations, but the EPUB has
only 15 distinct contents (4 duplicate pairs), so 4 illustrations are missing. The cause:
`_best_pdf_match` chose the closest PDF image per DOCX asset without tracking what was
already used. Because almost every plate has the same size (1055×1498, displayed
≈596×844 pt), the match collapsed.

EPUBs generated before spec 15 (order-based mapping) are correct; only those generated with
spec 15 (Kanojo, Yuri, Koroshiya) are affected.

## Proposed change

Replace `_best_pdf_match` with `_align_assets_to_pdf`, which assigns **at most one PDF image
per DOCX asset and vice versa, preserving document order**:

- Candidates `B` = PDF images excluding margin repeats (spec 11) and images whose shortest
  pixel side is below `min_image_px` (invisible artifacts), in first-placement order.
- If `len(assets) == len(candidates)`, map by order (`i ↔ i`) — the common, exact case.
- Otherwise run a small dynamic-programming alignment (Needleman-Wunsch) between the asset
  sequence and the candidate sequence: match cost = displayed-size distance
  (`|log(w/w')| + |log(h/h')|`), only allowed below `_MAX_SIZE_DISTANCE`; gaps for skipped
  pages/images. Each index is used at most once.
- Matched assets get the PDF original bytes/media type/file name; unmatched assets keep the
  DOCX image.

`apply_pdf_images` gains `min_image_px` (passed from the pipeline) and still drops recurring
banners by reference count first.

## Technical decision

- Document order is the most reliable signal (both pipelines emit images in page order), so
  it is the backbone; size only validates and never overrides order.
- The DP only runs when counts differ (e.g. a page dropped by pdf2docx), keeping the common
  path trivial and deterministic.
- Excluding tiny PDF images from candidates keeps the two sequences aligned with the DOCX
  extraction, which already filters them.

## Affected files

- `src/pdf_to_epub/core/docx/images.py`, `core/pipeline.py`.
- `tests/core/docx/test_images.py`.
- `docs/arquitectura.md`, `specs/0.1.0/00-changelog.md`.

## Tests

- Two DOCX assets with the same displayed size and two PDF images with the same displayed
  size map to **different** PDF images (no reuse), in order.
- Counts differing by one: the asset maps to the first candidate; the extra candidate is
  unused; no image is reused.
- Recurring-banner and substitution tests still pass.

## Acceptance criteria

- Validation books produce as many distinct EPUB images as distinct PDF illustrations
  (Yuri 19, Poison 14, Haburare 15, Kanojo 10).
- `pytest -q` and `ruff check .` pass.
