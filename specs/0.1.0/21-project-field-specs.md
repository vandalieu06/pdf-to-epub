---
code: "21"
title: "Project field in spec frontmatter"
project: "pdf-to-epub"
status: completed
version: "0.1.0"
date: 2026-09-27
tags: [spec, sdd]
affected_files:
  - AGENTS.md
  - specs/0.1.0/*.md
---

# 21 — Project field in spec frontmatter

## Purpose

Add a `project` field to every spec so the shared Obsidian Bases view can filter and group
specs by project when more than one project is linked into the vault.

## Context

Specs are exposed to the vault through folder symlinks under `Dev/Projects/<project>/specs`
and listed by a single shared `Dev/Projects/Specs.base` filtered by `file.hasTag("spec")`.
The project is encoded in the symlinked path, but an explicit, stable key in the frontmatter
is simpler for filtering/grouping and survives a rename of the symlink folder.

## Proposed change

- Add `project: "<name>"` to the frontmatter of every spec.
- Include the field in the canonical SDD template (`AGENTS.md`, vault `sdd-base.md`) and in
  the project-onboarding prompt (`obsidian-projects-setup.md`).
- Update the shared `Specs.base` to show and group by `project`.

## Technical decision

- A scalar note property (`project`) instead of a folder filter (`file.inFolder(...)`) or a
  hierarchical tag: trivial Bases `filters`/`groupBy`, portable, and independent of where the
  project is linked.
- The value is the project/crate name (e.g. `pdf-to-epub`), matching the folder name under
  `Dev/Projects/`.

## Affected files

- `specs/0.1.0/*.md` — add `project` to frontmatter.
- `AGENTS.md` — template includes `project`.
- Vault: `Dev/Prompts/sdd-base.md`, `Dev/Prompts/obsidian-projects-setup.md`,
  `Dev/Projects/Specs.base`.

## Tests

- Every spec's frontmatter contains `project: "pdf-to-epub"`.
- `Specs.base` shows a `Project` column and groups by it.

## Acceptance criteria

- The shared Bases view can group/filter specs by `project`.
- New-project templates require the `project` field.
