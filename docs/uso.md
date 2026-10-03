# Uso

Guía de usuario de `pdf-to-epub`.

## Instalación

Requiere Python 3.12 o 3.13 y [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Conversión básica

```bash
uv run pdf-to-epub convert "novela.pdf" -o "novela.epub"
```

Si omites `-o`, el EPUB se escribe junto al PDF con la misma base (`novela.epub`).

Al terminar, por defecto **solo queda el EPUB**: los intermedios se eliminan tras una
conversión correcta. Usa `--keep-intermediate` para conservarlos (junto al PDF o en
`--workdir`):

- `novela.clean.pdf` — PDF con cabeceras, pies y números de página redactados.
- `novela.docx` — documento editable para corregir a mano.

Si algo no queda perfecto, repite la conversión con `--keep-intermediate`, abre el `.docx`,
ajústalo y vuelve a generar el EPUB (el EPUB final también es editable).

## Portada

La **primera imagen del PDF se usa como portada** y se coloca al inicio del orden de
lectura (portada → índice → capítulos). Esa imagen se quita del cuerpo, así que no se ve
dos veces. El resto de ilustraciones se mantienen donde estaban.

`--cover PATH` sustituye la portada por una imagen externa; en ese caso la primera imagen
del PDF se descarta (no se muestra en el cuerpo). La portada no aparece en el índice.

## Imágenes y peso del EPUB

`pdf2docx` suele convertir las imágenes del PDF a PNG sin pérdida, lo que infla el EPUB. Por
eso, al extraerlas, las imágenes **opacas se re-codifican a JPEG** con `--image-quality`
(por defecto `85`). Las imágenes con transparencia (alpha) se conservan en PNG, y si el JPEG
resultante no es más pequeño que el original, se mantiene el original. El `.docx`
intermedio no se modifica.

En una novela ligera de 198 páginas esto redujo el EPUB de ~32 MB a ~6 MB sin cambiar la
resolución. Usa `--keep-original-images` para desactivar la optimización.

Además, la herramienta **usa las imágenes originales del PDF** en lugar de las copias
rasterizadas que produce pdf2docx (que cambian el aspecto y estropean las ilustraciones), y
**elimina los banners/logos repetidos** en los márgenes (p. ej. el logo de un scan que
aparece en todas las páginas), que de otro modo se insertarían cientos de veces.
`--keep-docx-images` desactiva el uso de las imágenes del PDF.

## Párrafos

`pdf2docx` comete dos errores de párrafo que se corrigen automáticamente (desactivable con
`--no-reflow`):

- **Diálogos pegados**: varias líneas en un mismo párrafo separadas por saltos de línea. Si
  la línea anterior termina en puntuación (`. ! ? … : ; " » )`) o la siguiente empieza por
  comilla o guion (`" ' “ ‘ « - —`), se separan en párrafos distintos; si no, el salto se
  convierte en un espacio (era un salto de línea de maquetación).
- **Frases cortadas por salto de página**: si un párrafo no termina en puntuación y el
  siguiente empieza en minúscula, se unen (ignorando párrafos vacíos intermedios).

Las ilustraciones y los títulos actúan de barrera: nunca se une texto a través de ellos.

## Opciones

| Opción | Descripción | Defecto |
|--------|-------------|---------|
| `-o, --output PATH` | Ruta del EPUB | `<input>.epub` |
| `--workdir PATH` | Directorio de intermedios | junto al PDF |
| `--force` | Sobrescribe un EPUB existente | no |
| `--keep-intermediate / --clean-intermediate` | Conserva o borra `.clean.pdf`/`.docx` | borra |
| `--no-clean` | Desactiva la limpieza de cabeceras/pies | — |
| `--keep-tables` | No repara tablas falsas de una fila generadas por pdf2docx | repara |
| `--no-reflow` | No separa/une párrafos automáticamente | refluye |
| `--header-margin FLOAT\|auto` | Banda superior como fracción de la altura (`auto` = banda por defecto, 0.08) | `auto` (0.08) |
| `--footer-margin FLOAT\|auto` | Banda inferior como fracción (`auto` = banda por defecto, 0.08) | `auto` (0.08) |
| `--min-header-ratio FLOAT` | Fracción de páginas para considerar una línea repetida | `0.5` |
| `--title TEXT` | Sobrescribe el título | del PDF |
| `--author TEXT` | Sobrescribe el autor | del PDF |
| `--language CODE` | Idioma del EPUB | `es` |
| `--identifier TEXT` | Identificador único del EPUB | UUID4 |
| `--cover PATH` | Imagen de portada | la primera imagen del PDF |
| `--keep-all-images` | No filtra imágenes pequeñas/decorativas | — |
| `--min-image-px INT` | Lado mínimo para conservar una imagen | `24` |
| `--image-quality INT` | Calidad JPEG de las imágenes opacas (1-100) | `85` |
| `--keep-original-images` | No re-codifica las imágenes (conserva PNG) | — |
| `--keep-docx-images` | No usa las imágenes originales del PDF | usa las del PDF |
| `-q, --quiet` | Solo muestra errores | — |
| `-v, --verbose` | Log de depuración | — |
| `--version` | Muestra la versión | — |

## Ejemplos

```bash
# Convertir conservando intermedios (el .docx editable) en ./work
uv run pdf-to-epub convert novela.pdf -o novela.epub --workdir ./work --keep-intermediate

# Forzar título/autor/idioma y portada
uv run pdf-to-epub convert novela.pdf \
  --title "El Rey del Veneno" \
  --author "LeonarD" \
  --language es \
  --cover portada.jpg

# Un PDF sin cabeceras/pies repetidos
uv run pdf-to-epub convert limpio.pdf --no-clean

# EPUB más ligero (más compresión) o conservar las imágenes originales
uv run pdf-to-epub convert novela.pdf --image-quality 75
uv run pdf-to-epub convert novela.pdf --keep-original-images
```

## Códigos de salida

| Código | Significado |
|--------|-------------|
| `0` | Éxito |
| `1` | Validación (no existe el PDF, no es PDF, salida existente sin `--force`) |
| `2` | Error de uso de la CLI (argumentos faltantes/incorrectos) |
| `3` | Error en la etapa PDF |
| `4` | Error en la etapa DOCX |
| `5` | Error al construir el EPUB |
| `6` | Error de E/S |

## Limitaciones conocidas

- La detección de cabeceras/pies es heurística. Si el PDF varía el formato entre páginas,
  revisa el `.docx` y edítalo.
- El texto en varias columnas puede desordenarse.
- Si el PDF no trae idioma, se usa `es`; cámbialo con `--language`.
- Se asume que **la primera imagen es la portada**: si un PDF empieza con una ilustración
  que no es portada, esa imagen se usará como portada y se quitará del cuerpo. Usa
  `--cover` para fijar otra portada (la primera imagen seguirá descartándose del cuerpo).
- `pdf2docx` puede **ignorar páginas** que no consigue parsear; en ese caso se muestra
  `warning: pdf2docx ignored pages …` y conviene revisar el EPUB.
- pdf2docx a veces pega palabras (p. ej. `DEAOI`); revisa el `.docx` con
  `--keep-intermediate` si necesitas corregirlo.
