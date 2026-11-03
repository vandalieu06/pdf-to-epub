---
code: "02"
title: "Modos de capítulos: libro vs webnovel y recuperación de headings"
project: "pdf-to-epub"
status: completed
version: "0.2.0"
date: 2026-11-02
tags: [spec, sdd]
affected_files:
  - src/pdf_to_epub/core/config.py
  - src/pdf_to_epub/core/models.py
  - src/pdf_to_epub/core/pdf/chapters.py
  - src/pdf_to_epub/core/docx/headings.py
  - src/pdf_to_epub/core/epub/split.py
  - src/pdf_to_epub/core/export.py
  - src/pdf_to_epub/core/pipeline.py
  - src/pdf_to_epub/cli.py
  - docs/arquitectura.md
  - docs/uso.md
  - docs/features.md
  - tests/core/pdf/test_chapters.py
  - tests/core/docx/test_headings.py
  - tests/core/epub/test_split.py
  - tests/core/test_export.py
  - tests/core/test_pipeline.py
---

# 02 — Modos de capítulos: libro vs webnovel y recuperación de headings

## Purpose

Permitir que pdf-to-epub elija la estrategia de troceado según el tipo de PDF
(`book` / `webnovel` / `auto`), de forma que:

- las **webnovels** no generen capítulos vacíos por las líneas de TOC/breadcrumb que
  repiten el título antes del heading real;
- las **light novels** recuperen capítulos cuyos headings están renderizados como imagen
  (texto oculto tras la ilustración), que `pdf2docx` descarta del DOCX.

## Context

Hoy `epub/split.py::heading_level()` usa una única heurística de texto: cualquier párrafo
que empiece por `chapter`, `capítulo`, `cap`, `prologue`, etc. es H1. No hay noción de tipo
de documento, deduplicación ni descarte de capítulos vacíos.

Casos reales de `translate_novels`:

- `I Married the Dragon I Killed` (webnovel, 1149 páginas, 78 capítulos reales según el
  outline del PDF): produce **124 capítulos**, de los cuales **45 están vacíos** y uno es
  un stub. Cada página de capítulo empieza con la línea del outline
  (`Capítulo 1: Matando a Mi Prometido`) y justo después el título real
  (`Capítulo 01: Matando a Mi Prometida`); ambas se detectan como H1.
- `source` (light novel, 262 páginas, 4 capítulos): produce **1 capítulo** de 259 KB. Los
  headings `Capítulo 1..4` están dentro de una imagen (páginas 7, 84, 173 y 218) con una
  capa de texto oculta detrás; `pdf2docx` no los incluye en el DOCX y no hay nada que
  detectar.
- `Haburare Rune Tsukai no Isekai Boukentan` (light novel): 7 capítulos correctos porque
  los headings son texto real.

## Proposed change (antes → después)

- **Antes:** `ConversionOptions` no tiene modo de troceado; `split_chapters` y
  `extract_docx_chapters` aplican la misma heurística a todo.
- **Después:**
  1. `core/config.py`: `ConversionOptions.split_mode: Literal["auto", "book", "webnovel"]
     = "auto"`.
  2. Nuevo `core/pdf/chapters.py`:
     - `PdfChapterStart(page: int, title: str)` (dataclass en `core/models.py`).
     - `read_pdf_chapters(pdf_path) -> list[PdfChapterStart]`:
       - primero el outline (`doc.get_toc()`, nivel 1);
       - si no hay outline, bloques de texto que parezcan capítulo
         (`Capítulo N`, `Chapter N`, `CAP N`, `Prólogo`, `Epílogo`, `Parte N`), incluidos
         los bloques **tapados por una imagen** (intersección de bbox > 50 %);
       - deduplicado por página.
  3. `core/epub/split.py`:
     - `chapter_number(title) -> int | None` (normaliza `01` y `1`).
     - `normalize_chapters(chapters, *, mode)` compartida por el EPUB rico y el export
       plano:
       - `webnovel`: descartar capítulos sin cuerpo; colapsar headings consecutivos con
         el mismo número conservando el de cuerpo real cuando el otro es un stub
         (< 1.000 caracteres y < 20 % del cuerpo del grande).
       - `book`: conservar todos los headings; sin deduplicación agresiva.
       - `auto`: resolver a `webnovel` si hay ≥ 20 headings H1 en el DOCX; a `book` si
         hay ≤ 10 headings y el PDF aporta capítulos; en el resto, `book`.
     - `split_chapters(..., mode="auto")` aplica la normalización antes de devolver.
  4. `core/export.py`: `extract_docx_chapters(..., mode="auto")` aplica **la misma**
     normalización, para que `raw/` y el EPUB original coincidan.
  5. `core/pipeline.py`:
     - resolver el modo antes de trocear;
     - en `book`/`auto` con pocos headings, inyectar un párrafo con estilo `Heading 1`
       al inicio de la página de cada capítulo detectado en el PDF (mapeo página PDF →
       sección DOCX mediante `w:sectPr`; `pdf2docx` genera una sección por página);
     - no inyectar si la página ya empieza por un heading;
     - añadir `ConversionReport.split_mode: str` y `ConversionReport.pdf_chapters: int`.
  6. `cli.py`: `--split-mode [auto|book|webnovel]` (default `auto`).

## Technical decision

- **El troceado pertenece a pdf-to-epub:** así el EPUB rico (`split_chapters`) y el texto
  plano (`extract_docx_chapters`) comparten detector y normalización por construcción, sin
  duplicar lógica en translate_novels.
- **Inyección de headings en el DOCX** en lugar de reconstruir el EPUB después: el DOCX es
  el punto de intervención documentado del pipeline y permite reutilizar el renderizador
  XHTML y la extracción de imágenes existentes.
- **Detección de headings ocultos** solo cuando hay pocos headings en el DOCX, para no
  duplicar capítulos ya detectados.
- **Regla conservadora de deduplicación:** solo se colapsan capítulos consecutivos con el
  mismo número cuando uno es claramente un stub; evita fusionar numeraciones que se
  reinician por volumen.
- `auto` es el default para no romper PDFs que ya funcionan (`haburare`) y detectar los
  dos casos problemáticos sin obligar al usuario a elegir.

## Affected files

- `src/pdf_to_epub/core/config.py`
- `src/pdf_to_epub/core/models.py`
- `src/pdf_to_epub/core/pdf/chapters.py` (nuevo)
- `src/pdf_to_epub/core/epub/split.py`
- `src/pdf_to_epub/core/export.py`
- `src/pdf_to_epub/core/pipeline.py`
- `src/pdf_to_epub/cli.py`
- `docs/arquitectura.md`, `docs/uso.md`, `docs/features.md`
- `tests/core/pdf/test_chapters.py` (nuevo), `tests/core/epub/test_split.py`,
  `tests/core/test_export.py`, `tests/core/test_pipeline.py`

## Tests

- `test_chapters.py`: PDF sintético con outline; PDF sin outline con heading tapado por
  imagen; deduplicación por página; PDF sin capítulos → lista vacía.
- `test_split.py`: capítulos vacíos descartados en `webnovel`; duplicados `01`/`1`
  colapsados conservando el de cuerpo real; `book` no descarta headings legítimos;
  `auto` resuelve webnovel con muchos headings y book con pocos.
- `test_export.py`: `extract_docx_chapters(mode="webnovel")` devuelve el mismo número de
  capítulos que `split_chapters`.
- `test_pipeline.py`: DOCX sintético con heading inyectado en la página correcta; no se
  inyecta si la página ya tiene heading; `report.split_mode` y `report.pdf_chapters`.

## Acceptance criteria

- `I Married the Dragon I Killed` pasa de 124 a **78 capítulos** (sin vacíos).
- `source` pasa de 1 a **4 capítulos de texto** (`Capítulo 1..4`), detectados por
  texto oculto; el EPUB rico conserva además un capítulo de front matter con las
  ilustraciones previas al capítulo 1.
- `Haburare Rune Tsukai no Isekai Boukentan` se mantiene en **7 capítulos**.
- `--split-mode book|webnovel` fuerza el modo; `auto` acierta en los tres casos.
- `split_chapters` y `extract_docx_chapters` coinciden en los capítulos de texto
  (el front matter solo-imágenes solo existe en el EPUB rico).
- Portada, imágenes y tablas se conservan intactas.
- `uv run pytest -q` y `uv run ruff check .` pasan.
