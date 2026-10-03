# AGENTS.md

Python CLI (`pdf-to-epub`) that converts light novels from PDF to EPUB via DOCX as an
intermediate format (`pdf -> docx -> epub`). The DOCX is the intervention point for
cleaning headers, footers, and other PDF noise before generating the EPUB. Documentation
lives in `docs/` (authoritative) and the versioned plan lives in `specs/`.

## Flujo Spec-Driven Development (SDD) — Obligatorio

1. **Regla de oro:** prohibido crear o modificar código fuente sin una spec APROBADA por el
   usuario. Si llega un cambio sin documentar, el primer paso es escribir/actualizar su spec
   y confirmarla antes de implementar.

2. **Creación de spec:** crea `specs/<version>/NN-tema.md` con este frontmatter YAML (es la
   **fuente de verdad** del estado):

   ```yaml
   ---
   code: "NN"
   title: "Título conciso"
   project: "<nombre>"
   status: proposed          # proposed | approved | in-progress | completed
   version: "<version>"
   date: YYYY-MM-DD
   tags: [spec, sdd]
   affected_files:
     - src/pdf_to_epub/...
   ---
   ```

   El cuerpo usa estas secciones: Purpose / Context / Proposed change / Technical decision /
   Affected files / Tests / Acceptance criteria. La spec describe **un** cambio; si supera
   ~300 líneas, divídela en varias specs. El estado completo del sistema vive en `docs/`.

3. **Pausa dura (human-in-the-loop):** al dejar la spec en `status: proposed`, DETÉN la
   ejecución, muestra un resumen y espera confirmación explícita. No pases a `in-progress`
   ni toques código hasta que el usuario apruebe.

4. **Implementación:** con la aprobación, cambia la spec a `status: in-progress` e implementa
   el código y los tests descritos en ella.

5. **Cierre:** cuando los Acceptance criteria estén cumplidos, cambia la spec a
   `status: completed`, actualiza la documentación viva en `docs/` (`arquitectura.md` =
   referencia técnica del pipeline pdf → docx → epub, `uso.md` = guía de usuario,
   `features.md`) y anota el cambio y el hash del commit en `specs/<version>/00-changelog.md`.

Los specs se organizan por versión en `specs/<version>/`; los cambios nuevos se registran en
la versión actual (`00-changelog.md`) y al liberar un conjunto se sube la versión de specs.
`docs/` es la referencia autoritativa del estado actual; `specs/` es el contrato/plan por
versión. El estado de cada spec se consulta desde Obsidian (vault `docs`, vista
`Dev/Projects/pdf-to-epub/specs.base`); el bloque canónico para replicar este flujo en otros
proyectos está en `Dev/Prompts/sdd-base.md`.

Plantilla de `specs/<version>/00-changelog.md`:

```markdown
# Changelog — <version>

| Fecha | Spec | Cambio | Commit |
| ----- | ---- | ------ | ------ |
| YYYY-MM-DD | NN | Resumen del cambio | <hash> |
```

## Verificación

- Tests: `uv run pytest -q`
- Lint: `uv run ruff check .`
