---
code: "03"
title: "Metadata mapping (PDF → EPUB)"
status: completed
version: "0.1.0"
project: "pdf-to-epub"
date: 2026-09-18
tags: [spec, sdd]
affected_files:
  - src/pdf_to_epub/core/pdf/inspect.py
  - src/pdf_to_epub/core/models.py
  - src/pdf_to_epub/core/epub/metadata.py
  - src/pdf_to_epub/core/config.py
  - tests/core/pdf/test_inspect.py
  - tests/core/epub/test_metadata.py
  - tests/fixtures/
  - docs/uso.md
---

# 03 — Metadata mapping (PDF → EPUB)

## Purpose

Preserve the original PDF metadata (title, author, subject, keywords, dates, producer) in
the generated EPUB, mapping it to Dublin Core and OPF fields, with sensible fallbacks when
a field is missing.

## Context

PDF metadata is exposed by PyMuPDF as `doc.metadata`:

```
{
  "format": "PDF 1.7",
  "title": "...", "author": "...", "subject": "...", "keywords": "...",
  "creator": "...", "producer": "...",
  "creationDate": "D:YYYYMMDD...", "modDate": "D:YYYYMMDD...",
  "encryption": "..."
}
```

EPUB 3 requires `dc:identifier`, `dc:title`, and `dc:language`. `dc:language` is frequently
absent from PDFs, so a fallback is mandatory. Light novels are typically Spanish here, so
the default fallback language is `es`, overridable.

## Proposed change

### `core/pdf/inspect.py`

Read `doc.metadata` and normalize into a `PdfMetadata` dataclass:

- `title: str | None`
- `author: str | None` — the PDF `author` field, possibly a list separated by `;`/`,`.
- `subject: str | None` → description.
- `keywords: str | None` — split on `,`/`;` into a list of subjects.
- `creator: str | None`, `producer: str | None` — kept as provenance, not DC fields.
- `creation_date: datetime | None`, `mod_date: datetime | None` — parse PDF `D:` format.
- `language: str | None` — best-effort (never present in `doc.metadata`); may be inferred
  from surrounding options or left `None`.
- `page_count: int`.

### `core/epub/metadata.py`

Map `PdfMetadata` → `ebooklib.epub.EpubBook`:

| EPUB (DC/OPF) | Source | Fallback |
|---------------|--------|----------|
| `dc:identifier` | `--identifier` option | generated UUID4 (stable per run) |
| `dc:title` | PDF `title` | input file stem |
| `dc:creator` | PDF `author` (split) | none |
| `dc:language` | `--language` option | inferred | `es` |
| `dc:description` | PDF `subject` | none |
| `dc:subject` | PDF `keywords` (split) | none |
| `dc:date` | `creation_date` | none |
| `dc:publisher` | none | none |
| `dc:source` | input PDF path/name | none |
| `meta` (provenance) | `creator`/`producer` | none |

Rules:

- Only add non-empty values (never create empty DC elements).
- Title/author are trimmed; author strings are split on `;` only. A comma is **not** a
  separator (`Lastname, Firstname` is a single author); users with multiple authors pass
  `--author` explicitly.
- Dates are normalized to ISO-8601 (`YYYY-MM-DD`, or full timestamp when available).
- The generator is tagged in OPF metadata (`meta name="generator"`) with the app version.
- An explicit `--title`/`--author`/`--language` CLI override always wins over PDF values.

## Technical decision

- PDF metadata is the source of truth, but EPUB's required fields must never be empty, so
  deterministic fallbacks are applied.
- `dc:language` defaults to `es` (configurable) rather than `en`, matching the primary use
  case; document this clearly.
- Identifier: uuid4 generated and reported, so the EPUB is valid; users needing an ISBN can
  pass `--identifier`.
- Keep `creator`/`producer` as provenance metadata (`meta`) instead of misusing DC fields.

## Affected files

- `src/pdf_to_epub/core/pdf/inspect.py` — metadata read/parse.
- `src/pdf_to_epub/core/models.py` — `PdfMetadata` dataclass.
- `src/pdf_to_epub/core/epub/metadata.py` — mapping and fallbacks.
- `src/pdf_to_epub/core/config.py` — override options.
- `tests/core/pdf/test_inspect.py`, `tests/core/epub/test_metadata.py` — new.
- `tests/fixtures/` — PDF fixture with known metadata.
- `docs/uso.md` — document overrides and defaults.

## Tests

- Fixture PDF with title/author/subject/keywords/dates set: assert all map to the expected
  DC fields and dates are ISO-8601.
- Fixture PDF with only a title: assert identifier is a UUID, language is `es`, no empty
  tags are emitted.
- Malformed/absent `author` string: assert it is not split into garbage.
- CLI override (`--title`, `--author`, `--language`) wins over PDF values.
- Read back the built EPUB with `ebooklib` and assert `book.get_metadata("DC", ...)`.

## Acceptance criteria

- EPUB metadata reflects the PDF when present and is always valid (identifier, title,
  language non-empty).
- No empty DC elements are written.
- Overrides work and are covered by tests.
