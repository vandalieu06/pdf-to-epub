---
code: "09"
title: "Optimize image size (JPEG)"
status: completed
version: "0.1.0"
project: "pdf-to-epub"
date: 2026-09-18
tags: [spec, sdd]
affected_files:
  - src/pdf_to_epub/core/docx/images.py
  - src/pdf_to_epub/core/config.py
  - src/pdf_to_epub/core/pipeline.py
  - src/pdf_to_epub/cli.py
  - tests/core/docx/test_images.py
  - tests/core/test_pipeline.py
  - docs/uso.md
  - docs/arquitectura.md
  - docs/features.md
---

# 09 — Optimize image size (JPEG)

## Purpose

Shrink the generated EPUB, which is ~99 % images, by re-encoding the opaque pictures
`pdf2docx` extracts as PNG into JPEG. Optionally leave images untouched.

## Context

A validation conversion of a 198-page light novel produced a 32.1 MB EPUB: 32.0 MB of
images and 0.35 MB of text. The source PDF stores its 14 illustrations as **JPEG**
(16.2 MB total), but `pdf2docx` re-encodes them to **lossless PNG**, roughly doubling the
size. Re-encoding those images to JPEG at the same resolution measures:

| Encoding | EPUB images |
|----------|-------------|
| PNG (current) | 32.0 MB |
| JPEG q90 | 7.3 MB |
| JPEG q85 | 6.0 MB |
| JPEG q80 | 5.2 MB |

Resolution is not the problem (1400×1942 is fine); the codec is.

## Proposed change

Add an image optimization step right after extraction and before chapter splitting, so
file names, extensions and `<img src>` references stay consistent.

`core/docx/images.py`:

- `optimize_images(assets, *, quality=85) -> list[ImageAsset]`:
  - Decode each image with PyMuPDF (`pymupdf.Pixmap(data)`).
  - If the image **has alpha**, keep it unchanged (JPEG would drop transparency).
  - Otherwise encode as JPEG (`pix.tobytes("jpeg", jpg_quality=quality)`), update
    `media_type` to `image/jpeg`, change the file extension to `.jpg`, and keep `uid`,
    `rel_id`, `position_index` and `is_cover`.
  - If the JPEG is not smaller than the original, or decoding fails, keep the original.
- Runs by default in `core/pipeline.py` unless `--keep-original-images`.

New options (`core/config.py`, `core/cli.py`):

- `--image-quality INT` (0–100, default `85`).
- `--keep-original-images` to skip optimization.

The intermediate DOCX is left untouched (it is the manual editing artifact).

## Technical decision

- Use **PyMuPDF** for encoding; no new dependency (Pillow would be needed only for finer
  resizing or WebP, which are out of scope since resizing is disabled).
- Alpha images stay PNG to avoid a black background.
- The "only replace if smaller" guard prevents regressions on already-efficient images.
- Optimizing new `ImageAsset`s (instead of mutating) keeps the extraction stage pure.

## Affected files

- `src/pdf_to_epub/core/docx/images.py` — `optimize_images`.
- `src/pdf_to_epub/core/config.py` — `image_quality`, `keep_original_images`.
- `src/pdf_to_epub/core/pipeline.py` — apply optimization after extraction.
- `src/pdf_to_epub/cli.py` — `--image-quality`, `--keep-original-images`.
- `tests/core/docx/test_images.py`, `tests/core/test_pipeline.py`.
- `docs/uso.md`, `docs/arquitectura.md`, `docs/features.md`.

## Tests

- An opaque PNG asset becomes JPEG: `media_type == "image/jpeg"`, `file_name` ends in
  `.jpg`, `rel_id`/`uid`/`position_index` preserved, and `data` is valid JPEG.
- An image whose JPEG encoding would be larger keeps its original bytes/format.
- Alpha images are left unchanged (PNG with alpha preserved).
- `--keep-original-images` leaves all assets untouched end to end.

## Acceptance criteria

- The validation novel's EPUB drops from ~32 MB to roughly 6 MB at `--image-quality 85`
  without resizing.
- Non-optimizable images are preserved and never corrupted.
- `pytest -q` and `ruff check .` pass.
