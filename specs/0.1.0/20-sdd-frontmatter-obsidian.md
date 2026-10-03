---
code: "20"
title: "SDD frontmatter and Obsidian progress tracking"
status: in-progress
version: "0.1.0"
project: "pdf-to-epub"
date: 2026-09-27
tags: [spec, sdd]
affected_files:
  - AGENTS.md
  - specs/0.1.0/*.md
  - specs/0.1.0/00-changelog.md
---

# 20 — SDD frontmatter and Obsidian progress tracking

## Purpose

Add a single, machine-readable source of truth for the state of every spec and make the
specs visible in Obsidian for progress tracking, without introducing an external tool.

## Context

The SDD workflow in `AGENTS.md` already uses versioned specs, a mandatory human approval
pause and a changelog, but the state of a spec lived in two prose places (a `- **Status**`
bullet in each spec and a `Status` column in `00-changelog.md`), which can drift and is not
queryable. A comparison of `AGENTS.md` vs. LeanSpec concluded that the best move is to keep
`AGENTS.md` and borrow two LeanSpec practices: **YAML frontmatter** and a **rigid status
lifecycle**.

The Obsidian vault `/home/jhonnyc/Dev/docs` does not contain this project, so specs are not
visible there. Obsidian supports folder symlinks whose target is outside the vault (official
behavior since 0.11.1); Bases (core plugin) is enabled, Dataview is not.

## Proposed change

- **Frontmatter is the source of truth** for `status`, with the lifecycle
  `proposed | approved | in-progress | completed`.
- Backfill YAML frontmatter into every spec: `code`, `title`, `status`, `version`, `date`,
  `tags: [spec, sdd]` and `affected_files`.
- Remove the redundant `- **Status**` / `- **Version**` bullets from each spec.
- Remove the `Status` column from `00-changelog.md` (it becomes `Spec | Topic | Commit`).
- Rewrite the `AGENTS.md` SDD block with the frontmatter template, the status lifecycle, a
  hard pause at `proposed`, and a soft 300-line limit (split into several specs when
  exceeded). The block is mirrored, ready to paste, in the vault's
  `Dev/Prompts/sdd-base.md`.
- Expose the project to the vault with folder symlinks under
  `Dev/Projects/pdf-to-epub/{specs,docs}` and add `specs.base` (Bases view filtered by
  `file.hasTag("spec")`).

## Technical decision

- YAML frontmatter instead of a LeanSpec CLI/MCP: zero dependencies, works with any agent,
  and is directly queryable by Obsidian Bases.
- Bases instead of Dataview because Bases ships as a core plugin (already enabled) while
  Dataview is not installed.
- Symlink only `specs` and `docs` (not the whole project) to avoid indexing `.venv`, `.git`
  and `node_modules`.
- Specs describe **one** change and stay under 300 lines; the full current state lives in
  `docs/`.

## Affected files

- `AGENTS.md` — optimized SDD block.
- `specs/0.1.0/01..19-*.md` — frontmatter backfill.
- `specs/0.1.0/00-changelog.md` — drop the `Status` column.
- `specs/0.1.0/20-sdd-frontmatter-obsidian.md` — this spec.
- Vault: `Dev/Projects/pdf-to-epub/{specs,docs}` symlinks, `Dev/Projects/pdf-to-epub/specs.base`,
  `Dev/Prompts/sdd-base.md`.

## Tests

- Every spec opens with a valid YAML frontmatter block; `code`/`title`/`status`/`version`/
  `date` present.
- `tags` includes `spec` for all specs.
- `00-changelog.md` has three columns.
- Obsidian: after `obsidian reload`, `obsidian tags` lists `spec` and
  `obsidian base:query` returns the specs.
- `uv run pytest -q` and `uv run ruff check .` still pass (no code touched).

## Acceptance criteria

- Each spec's `status` lives only in its frontmatter.
- The vault shows the specs and the Bases view lists them with their state.
- `AGENTS.md` and `Dev/Prompts/sdd-base.md` describe the same canonical SDD block.
- `pytest -q` and `ruff check .` pass.
