---
code: "07"
title: "Cover first in reading order"
status: completed
version: "0.1.0"
project: "pdf-to-epub"
date: 2026-09-18
tags: [spec, sdd]
affected_files:
  - src/pdf_to_epub/core/docx/images.py
  - src/pdf_to_epub/core/epub/builder.py
  - tests/core/docx/test_images.py
  - tests/core/epub/test_builder.py
  - docs/arquitectura.md
  - docs/uso.md
  - docs/features.md
---

# 07 — Cover first in reading order

## Purpose

Make the cover the first page readers see, and treat the first image of the PDF as the
cover by default, matching the convention for light novels.

## Context

In v0.1.0 the spine was built as `["nav"] + chapters`, so the first page was the table of
contents and `cover.xhtml` (created by `ebooklib.epub.set_cover`) was left out of the
spine entirely — present in the manifest but unreachable in the reading order. Readers
that honor the spine opened the book on the TOC instead of the cover.

Separately, cover selection used a size heuristic (first image with a side ≥ 300 px).
Validation showed the first extracted image is the cover in practice, so the heuristic is
unnecessary and can pick a later image when an early plate is smaller.

## Proposed change

### Cover selection

- `docx/images.py: select_cover(assets)` now returns **the first image in reading order**
  (`assets[0]`), regardless of size, or `None` when there are no images.
- An explicit `--cover PATH` still overrides the automatic choice.
- Decorative small images are still filtered by `--min-image-px` during extraction, so the
  first *kept* image is used.

### Reading order

`epub/builder.py` builds the spine as `[cover_page, "nav", *chapters]`:

- Use `book.set_cover(cover_file, data, create_page=False)` so the image carries the
  `cover-image` manifest property and the `<meta name="cover">` entry, but we own the
  cover page.
- Create the page ourselves to control language and styling:

  ```html
  <div class="cover"><img src="images/..." alt="Portada"/></div>
  ```

  with `lang` set to the book language (previously the generated page was `lang="en"`).
- Add it as the first spine item, before `nav`.

Result: **cover → nav/TOC → front matter → chapters**.

### CSS

Add a `.cover` rule (centered, no margins, image scaled to the viewport) to the default
stylesheet.

## Technical decision

- Keeping `set_cover(create_page=False)` preserves ebooklib's cover metadata and the
  `cover-image` property while letting us generate a language-correct page.
- "First image is the cover" is the documented convention for this corpus; the size
  heuristic caused more ambiguity than it removed, and `--cover` remains for exceptions.
- The cover page is intentionally not added to the TOC.

## Affected files

- `src/pdf_to_epub/core/docx/images.py` — `select_cover` semantics.
- `src/pdf_to_epub/core/epub/builder.py` — cover page + spine order + CSS.
- `tests/core/docx/test_images.py` — `select_cover` tests.
- `tests/core/epub/test_builder.py` — spine/cover assertions.
- `docs/arquitectura.md`, `docs/uso.md`, `docs/features.md`.

## Tests

- `select_cover` returns the first asset even when a later asset is larger; returns `None`
  for an empty list.
- Building an EPUB with an auto cover: the first spine item is the cover page (not `nav`),
  the cover page's XHTML references the cover image, its `lang` equals the book language,
  and the image carries `properties="cover-image"`.
- Building with `--cover`: the external image is the cover and appears first in the spine.
- No duplicate cover items/files in the manifest.

## Acceptance criteria

- First page of the reading order is the cover.
- The cover image is the first extracted image (unless `--cover` overrides).
- Cover metadata (`cover-image`, `meta name="cover"`) is preserved.
- `pytest -q` and `ruff check .` pass.
