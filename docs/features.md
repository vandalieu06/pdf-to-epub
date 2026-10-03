# Features

Estado de las funcionalidades de `pdf-to-epub` (v0.1.0).

## Implementadas

- **CLI `pdf-to-epub convert`** con opciones de metadatos, portada, márgenes, imágenes y
  control de intermedios (ver `docs/uso.md`).
- **Pipeline `pdf -> clean.pdf -> docx -> epub`** con etapas desacopladas y testeables.
- **Lectura de metadatos del PDF** (título, autor, descripción, palabras clave, fechas,
  procedencia) y mapeo a Dublin Core en el EPUB, con fallbacks (UUID4, `es`, nombre de
  archivo).
- **Eliminación de cabeceras/pies/pies de página** en dos pasadas: redacción geométrica en
  el PDF (huella con dígitos enmascarados) y limpieza de `section.header/footer` en el
  DOCX.
- **Preservación de imágenes** PDF -> DOCX -> EPUB, con deduplicación por hash, filtro de
  decorativas y portada (la primera imagen del PDF, o `--cover`).
- **Uso de las imágenes originales del PDF** en vez de los rasters de página de pdf2docx
  (conserva aspecto/resolución); `--keep-docx-images` lo desactiva.
- **Eliminación de banners/logos repetidos** en los márgenes (p. ej. el logo de un scan),
  por detección en el PDF y por número de referencias en el DOCX.
- **Optimización de imágenes** a JPEG (`--image-quality`, por defecto 85) para reducir el
  peso del EPUB (~32 MB -> ~6 MB en la novela de validación); `--keep-original-images`
  conserva los originales.
- **Portada al inicio del orden de lectura** (portada → índice → capítulos), sin duplicarla
  en el cuerpo.
- **Detección de capítulos** por estilos Word y por marcadores de texto
  (`Capítulo`/`CAP N`/`Prólogo`/`Interludio`/`Epílogo`/...), con TOC en el EPUB.
- **Aviso de páginas ignoradas** por pdf2docx (`warning: pdf2docx ignored pages …`).
- **Reparación de tablas falsas** de una fila (palabra por celda) que `pdf2docx` genera en
  líneas justificadas, para que el texto se copie como prosa; `--keep-tables` lo desactiva.
- **Reflujo de párrafos**: separa diálogos que `pdf2docx` había pegado con saltos de línea o
  en la misma línea (comilla de cierre + comilla de apertura) y une frases cortadas por
  saltos de página; `--no-reflow` lo desactiva.
- **Manejo de errores** con códigos de salida documentados (1-6).

## Limitaciones

- Se asume que la primera imagen del PDF es la portada; si no lo es, se usará como portada
  y se quitará del cuerpo (`--cover` no evita ese descarte).
- La detección de cabeceras/pies, capítulos y el reflujo de párrafos son heurísticos; el
  `.docx` intermedio está pensado para corregirlos a mano.

## Pendientes / ideas

- `--json` para salida legible por máquinas.
- Ajuste fino de estilos CSS y metadatos EPUB por plantilla.
- Detección de cabeceras/pies con clustering cuando la heurística de huella no basta.
- OCR para PDFs escaneados.
- Modo por lotes (varios PDFs).
