---
code: "08"
title: "Do not duplicate the cover in the body"
status: completed
version: "0.1.0"
project: "pdf-to-epub"
date: 2026-09-18
tags: [spec, sdd]
affected_files:
  - src/pdf_to_epub/core/pipeline.py
  - src/pdf_to_epub/core/epub/split.py
  - src/pdf_to_epub/core/epub/builder.py
  - tests/core/epub/test_split.py
  - tests/core/epub/test_builder.py
  - docs/arquitectura.md
  - docs/features.md
---

# 08 — Do not duplicate the cover in the body

## Purpose

Show the cover only once. The first image extracted from the DOCX *is* the cover, so it
must be promoted to the EPUB cover page and removed from the document body (where
`pdf2docx` originally placed it as the first page's image).

## Context

The source PDF's first page is the cover; `pdf2docx` maps it into the DOCX body as an
ordinary picture. `split.py` rendered that picture inline in the front-matter chapter, and
`build_epub` also used it as the cover, so the same image was displayed twice while the
underlying PNG was stored once:

```
cover.xhtml:        images/img_0000.png   (cover page)
chapter_0000.xhtml: images/img_0000.png   (front matter)
```

The user's convention is that the first image of a light-novel PDF is always the cover, so
the external `--cover` is not needed for the normal case; it remains only as an override.

## Proposed change

Treat the first extracted image as the canonical cover and never render it in the body.

- `core/pipeline.py`: `cover_asset = assets[0] if assets else None`; pass
  `skip_rel_ids={cover_asset.rel_id}` to `split_chapters`.
- `core/epub/split.py`: `split_chapters(..., skip_rel_ids: set[str] | None = None)`; the
  skipped relationship ids are left out of `rel_to_file`, so `_render_paragraph` emits no
  `<img>` for them.
- `core/epub/builder.py`: always exclude the first image (`images[0]`) from the regular
  image items (it is either the cover or has been replaced), and use it as the cover unless
  `--cover` provides an external image. When `--cover` is given, the first image is dropped
  entirely so two covers are never shown (option 1).
- Assign `uid="cover"` to the generated cover page for clearer manifest ids.

Result with the validation novel:

```
cover.xhtml         → img_0000 (cover)          single occurrence
chapter_0000.xhtml  → img_0001, img_0002, ...   body starts at the first plate
manifest            → one cover-img item
```

## Technical decision

- Excluding the cover at split time (via `skip_rel_ids`) is preferred over post-processing
  the generated HTML: it avoids leaving empty image paragraphs and keeps the concern in one
  place.
- The first image is always the cover (spec 07 convention). `--cover` overrides the
  displayed cover and, per the confirmed behaviour, the original first image is discarded
  rather than shown twice.
- Non-cover illustrations continue to be embedded normally.

## Affected files

- `src/pdf_to_epub/core/pipeline.py` — compute and pass the cover's `rel_id`.
- `src/pdf_to_epub/core/epub/split.py` — `skip_rel_ids`.
- `src/pdf_to_epub/core/epub/builder.py` — exclude first image, `uid="cover"`.
- `tests/core/epub/test_split.py`, `tests/core/epub/test_builder.py` — cover dedup tests.
- `docs/arquitectura.md`, `docs/features.md`.

## Tests

- The cover image is referenced only by `cover.xhtml`; no chapter XHTML references it.
- The cover file appears once in the zip and once in the manifest.
- Non-cover illustrations remain referenced in chapters.
- With `--cover`, the external image is the cover and the original first image is not in
  the manifest nor referenced in the body.
- `split_chapters(..., skip_rel_ids=...)` omits the image while keeping the surrounding
  text.

## Acceptance criteria

- No page other than the cover page references the cover image.
- The body keeps every illustration except the cover.
- `--cover` shows a single cover.
- `pytest -q` and `ruff check .` pass.
