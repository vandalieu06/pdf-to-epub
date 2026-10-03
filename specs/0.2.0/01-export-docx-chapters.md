---
code: "01"
title: "Export DOCX chapters as plain text and expose cover"
project: "pdf-to-epub"
status: in-progress
version: "0.2.0"
date: 2026-10-03
tags: [spec, sdd]
affected_files:
  - src/pdf_to_epub/core/export.py
  - src/pdf_to_epub/core/models.py
  - src/pdf_to_epub/core/pipeline.py
  - src/pdf_to_epub/core/epub/split.py
  - pyproject.toml
  - docs/arquitectura.md
  - docs/features.md
  - tests/core/test_export.py
  - tests/core/test_pipeline.py
---

# 01 — Export DOCX chapters as plain text and expose cover

## Purpose

Exponer como API pública de pdf-to-epub la extracción de capítulos en **texto plano**
desde el DOCX intermedio, y la portada extraída del PDF, para que translate_novels los
reutilice sin duplicar la detección de capítulos. De paso, permitir instalar pdf-to-epub
en Python 3.14.

## Context

translate_novels va a importar PDFs: necesita (a) los capítulos como párrafos planos para
traducirlos y generar el EPUB traducido, y (b) la portada para su biblioteca. El pipeline
actual (`run()`) hace todo internamente y el `ConversionReport` no expone los capítulos ni
la portada. La detección de límites (`_heading_level`, `_CHAPTER_RE` en `epub/split.py`)
ya está afinada y no debe duplicarse. Además, pdf-to-epub declara
`requires-python >=3.12,<3.14`, mientras translate_novels usa Python 3.14; las dependencias
(pdf2docx 0.5.13, pymupdf 1.28.2, python-docx 1.2.0) instalan correctamente en CPython 3.14.6.

## Proposed change (antes → después)

- **Antes:** `run()` devuelve un EPUB y un report sin capítulos ni cover; la detección de
  capítulos vive en `epub/split.py` produciendo XHTML; Python máximo 3.13.
- **Después:**
  1. Nuevo `core/export.py::extract_docx_chapters(docx_path, *, fallback_title="Book") -> list[TextChapter]`
     con `TextChapter(title, paragraphs: list[str], order)` (dataclass en `core/models.py`).
     Reutiliza la detección de títulos de `epub/split.py` (refactor menor a función
     compartida) y devuelve párrafos de texto plano: concatena los `run.text`, aplana las
     tablas a texto y **ignora las imágenes**.
  2. `ConversionReport.cover_path: Path | None` (nuevo): durante `run()`, si hay asset de
     portada, se escribe `workdir/cover.<ext>` y se apunta desde el report.
  3. `pyproject.toml`: `requires-python = ">=3.12,<3.15"`.

## Technical decision

- Reutilizar el detector de capítulos existente en lugar de reimplementarlo: garantiza que
  el EPUB rico (pdf-to-epub) y el export plano coincidan en límites de capítulo.
- Cover expuesta como archivo en el workdir (report) en vez de bytes en memoria: encaja con
  el patrón de archivos intermedios ya existente (`docx_path`, `clean_pdf_path`).
- Python 3.14: se sube el límite y se valida con la suite completa en 3.14. Si algo fallara
  en runtime, fallback documentado: fijar translate_novels a 3.13.

## Affected files

- `src/pdf_to_epub/core/export.py` (nuevo)
- `src/pdf_to_epub/core/models.py` (`TextChapter`, `ConversionReport.cover_path`)
- `src/pdf_to_epub/core/pipeline.py` (escribir cover; exponer docx/export)
- `src/pdf_to_epub/core/epub/split.py` (refactor menor: detector reutilizable)
- `pyproject.toml` (requires-python)
- `docs/arquitectura.md`, `docs/features.md`
- `tests/core/test_export.py` (nuevo), `tests/core/test_pipeline.py`

## Tests

- Unit `test_export.py`: DOCX sintético → capítulos con párrafos planos; títulos detectados;
  tablas aplanadas a texto; imágenes ignoradas; sin párrafos huérfanos.
- Pipeline: con un PDF sintético con portada, `report.cover_path` apunta a un archivo que
  existe y es una imagen válida.
- Suite completa de pdf-to-epub ejecutada en Python 3.14.

## Acceptance criteria

- `extract_docx_chapters` devuelve capítulos con párrafos planos consistentes con la
  detección de capítulos actual.
- `report.cover_path` apunta a un cover válido cuando el PDF tiene portada; `None` si no.
- pdf-to-epub instala y pasa su suite completa en Python 3.14.