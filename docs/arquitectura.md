# Arquitectura

Referencia técnica del pipeline `pdf -> clean.pdf -> docx -> epub` de `pdf-to-epub`.

## Visión general

Un PDF no almacena estructura, solo glifos posicionados. Por eso cada conversión es una
reconstrucción heurística. El flujo elegido separa las etapas para que cada una sea
inspeccionable y reemplazable:

```
input.pdf
  │
  ├─[1] inspect    (PyMuPDF)     lee metadatos + geometría de bloques
  ├─[2] clean      (PyMuPDF)     detecta cabeceras/pies repetidos y los redacta → .clean.pdf
  ├─[3] to_docx    (pdf2docx)    reconstruye párrafos, tablas e imágenes → .docx
  ├─[4] docx_clean (python-docx) vacía cabeceras/pies de Word, quita nº de página sueltos
  └─[5] build_epub (ebooklib)    EPUB 3 + metadatos DC + imágenes + portada + TOC
```

Cada etapa recibe y devuelve tipos explícitos y no imprime nada: el progreso viaja por un
callback (`Callable[[str], None]`) que el CLI conecta a `rich`. `core/` no importa
`typer`/`rich` (hay un test que lo verifica).

## Mapa de módulos

```
src/pdf_to_epub/
  cli.py                     Typer app; mapea excepciones a exit codes
  core/
    models.py                PdfMetadata, TextBlock, ImageAsset, Chapter, ...
    config.py                ConversionOptions (pydantic)
    pipeline.py              orquesta las etapas 1-5
    errors.py                ValidationError, PdfStageError, DocxStageError, EpubStageError
    text.py                  normalize_text / is_page_number compartidos
    pdf/
      inspect.py             metadatos + parseo de fechas/autor/palabras clave
      headers_footers.py     PageGeometry, detect_headers_footers, clean_pdf
    docx/
      convert.py             wrapper de pdf2docx (DocxConversionError)
      clean.py               limpieza de cabeceras/pies y nº de página
      images.py              extracción/dedup de imágenes, select_cover
    epub/
      metadata.py            PdfMetadata -> Dublin Core
      split.py               DOCX -> capítulos (XHTML)
      builder.py             ensamblado del EPUB
```

## Detección de cabeceras y pies

En `pdf/headers_footers.py`:

1. Se toman los bloques de texto (`page.get_text("blocks")`) cuya **línea central** cae en
   la banda superior o inferior (por defecto 8 % de la altura, configurable).
2. Se descartan bloques que ocupan más del 15 % del área de la página (guardarraíl para no
   borrar contenido real con poco texto).
3. Cada bloque se reduce a una **huella** (`fingerprint`): texto normalizado con las
   secuencias de dígitos sustituidas por `#` y en minúsculas. Así `"12 | Página"` y
   `"13 | Página"` comparten huella.
4. Se agrupa por huella; si aparece en al menos `min_ratio` de las páginas (por defecto
   0.5, mínimo 2 páginas) es candidato.
5. Los rectángulos candidatos se redactan (`add_redact_annot` + `apply_redactions`, sin
   tocar imágenes ni vectores) y se guarda `.clean.pdf`.

Si no hay candidatos se usa el PDF original sin copiarlo. `clean.py` es la red de
seguridad: vacía `section.header`/`section.footer` y elimina párrafos que son solo un
número de página.

## Reparación de tablas falsas

`pdf2docx` a veces interpreta los huecos de una línea justificada como columnas y genera
una tabla de **una fila con una palabra por celda** (habitualmente la primera línea de una
página). `docx/clean.py` detecta esas tablas (`1 fila`, `>= 3` celdas con texto) y las
convierte de nuevo en un párrafo uniendo las celdas con espacios, antes de generar el EPUB.
Las tablas reales (2+ filas) se conservan. `--keep-tables` desactiva esta reparación.

## Metadatos

`pdf/inspect.py` lee `doc.metadata`; `epub/metadata.py` lo mapea a Dublin Core:
título, autor(es), descripción (`subject`), materias (`keywords`), fecha
(`creationDate`) y `dc:source`. Fallbacks: `identifier` = UUID4, `language` = `es`,
título = nombre del archivo. `creator`/`producer` del PDF se conservan como metadato de
procedencia. Los flags `--title/--author/--language/--identifier` tienen prioridad.

## Imágenes

`docx/images.py` recorre los párrafos en orden, localiza DrawingML (`a:blip`) y VML
(`v:imagedata`), resuelve la relación del paquete OOXML y obtiene los bytes. Deduplica por
SHA-256 y descarta imágenes menores que `--min-image-px` (salvo `--keep-all-images`). La
portada es **la primera imagen en orden de lectura** (convención de las novelas ligeras);
`--cover` la sobrescribe.

Después de extraer, las imágenes opacas se re-codifican a **JPEG** con `--image-quality`
(por defecto 85) para evitar la inflación PNG de `pdf2docx` (en la novela de validación el
EPUB pasó de ~32 MB a ~6 MB). Las imágenes con canal alpha se conservan en PNG y, si el
JPEG resultante no es más pequeño, se mantiene el original. `--keep-original-images`
desactiva la optimización. El DOCX intermedio no se modifica.

### Imágenes originales del PDF (spec 12)

`pdf2docx` a veces emite **rasters de página completa** (aspecto de la página, ~260 DPI) en
lugar de la imagen embebida, deformándola. `core/pdf/images.py` extrae las imágenes
originales con PyMuPDF (`extract_image`) y su tamaño mostrado (bbox de colocación), y
`align_assets_to_pdf` empareja cada dibujo del DOCX con **una única** imagen del PDF
respetando el orden del documento (si los recuentos coinciden, mapeo directo por orden; si
no, alineamiento DP con huecos), usando el tamaño mostrado solo para validar
(`|log(w/w')| + |log(h/h')|`). Nunca reutiliza una imagen, por lo que no hay duplicados ni
láminas perdidas. Se conserva el aspecto/resolución y se elimina el reescalado.
`--keep-docx-images` lo desactiva.

### Banners/logos repetidos (specs 11/14)

Las imágenes que se repiten en las bandas superior/inferior en al menos `min_ratio` de las
páginas (logos de scan, banners) se marcan en `extract_pdf_images`. Además, cualquier imagen
referenciada en el DOCX en `max(3, 25 %)` de las páginas o más se considera mobiliario de
página y se descarta (`count_image_references`), lo que cubre el caso en que pdf2docx deforma
la imagen y el emparejamiento por tamaño falla. No se redactan en el PDF porque el banner se
solapa con la ilustración y la redacción eliminaría también la ilustración.

### Páginas ignoradas por pdf2docx (spec 17)

`docx/convert.py` captura los mensajes `Ignore page <n>` de pdf2docx y los devuelve en
`ConversionReport.ignored_pages`; el CLI avisa con un `warning` cuando hay páginas perdidas.

## Orden de lectura y portada

El spine se construye como **portada → índice (nav) → front matter → capítulos**. La
primera imagen extraída del DOCX es la portada: se promueve a `cover.xhtml` (creada con
`set_cover(..., create_page=False)`, que aporta `cover-image`/`meta name="cover"` y un
`lang` correcto) y **se omite del cuerpo** (`split_chapters(..., skip_rel_ids=...)`), de
modo que nunca se ve dos veces. El resto de ilustraciones siguen en el cuerpo. La portada
no aparece en el TOC; `--cover` sigue disponible como override (sustituye a la primera
imagen, que se descarta).

## Capítulos

`epub/split.py` recorre el cuerpo del DOCX en orden. Un párrafo inicia capítulo si su
estilo es `Heading 1`/`Title` o si su texto (sin comillas/guillemets iniciales) empieza por
`chapter|capítulo|prologue|prólogo|interlude|epilogue|epílogo|part|volume|...`. Se
excluyen líneas con puntos de relleno (índices). El contenido previo al primer capítulo
queda como capítulo inicial.

## Reflujo de párrafos

`core/docx/reflow.py` corrige dos artefactos de `pdf2docx` (activo por defecto):

- **Separar**: los `<w:br/>`/`<w:cr/>` internos se convierten en un nuevo párrafo cuando el
  texto anterior termina en puntuación o el siguiente empieza por comilla/guion; si no, en
  un espacio. Se preservan los runs (negrita/cursiva) y el `w:pPr`.
- **Separar diálogos adyacentes**: si una comilla de cierre (`" ” » ' ’`) va seguida de
  espacios y una comilla de apertura (`" “ « ' ‘`), se corta en un nuevo párrafo (regla
  textual, no depende de `w:br`). No corta listas con coma ni rayas.
- **Unir**: si un párrafo no termina en puntuación y el siguiente empieza en minúscula, se
  fusionan; los párrafos vacíos intermedios se eliminan. Títulos y párrafos con imagen son
  barreras.

`--no-reflow` lo desactiva; los contadores aparecen en el resumen.

## Decisiones

- **Python 3.12/3.13** (`>=3.12,<3.14`). Se excluye 3.14 por el conflicto histórico entre
  `pdf2docx` -> `opencv-python-headless` y numpy en esa versión.
- **pdf2docx** está congelado aguas arriba; se aísla en `docx/convert.py`.
- **Sin binarios externos**: `ebooklib` genera el EPUB en Python puro.
