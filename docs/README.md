# cell_OS Documentation Index

Welcome! This directory hosts all written artifacts for the platform. Use this index to jump to the right area and to understand how we separate active docs from archives.

## Core Index Files
- **[README.md](README.md)** *(this file)* – Documentation map.
- **[MIGRATION_HISTORY.md](MIGRATION_HISTORY.md)** – Consolidated history of migrations, validation packets, and implementation summaries.
- **[REFACTORING_OPPORTUNITIES.md](REFACTORING_OPPORTUNITIES.md)** – Active engineering backlog for structural work.
- **[../STATUS.md](../STATUS.md)** – Cross-cutting program status and next steps.

## Active Categories
- **Architecture (`architecture/`)** – System design, ontology, and directory overviews. Start with `ARCHITECTURE.md`, `ONTOLOGY.md`, and `PROJECT_STRUCTURE.md`.
- **Guides (`guides/`)** – User and operator guides. See `guides/README.md` for the per-guide index (POSH overview, cost-aware decision support, cleanup recommendations, etc.).
- **Protocols (`protocols/`)** – Wet-lab SOPs such as `upstream_protocol.md`.
- **Refactor Plans (`refactor_plans/`)** – Active technical plans (e.g., `BOM_TRACKING_REFACTOR.md`).
- **System Docs (`system/`)** – Lab world model and acquisition system references.
- **Meta (`meta/`)** – Todos, planning notes, and historical artifacts not yet archived.

## Archive Layout
All completed or historical docs now live under `archive/`:
- `archive/sessions/` – Session summaries renamed with `YYYY-MM-DD-*.md`.
- `archive/migrations/` – Legacy migration + validation packets referenced by `MIGRATION_HISTORY.md`.
- `archive/refactorings/` – Completed refactor logs and summaries.
- `archive/status/` – Prior status, progress, and next-step reports (see `STATUS.md` for the latest).

## Getting Started
1. Read the root [README](../README.md) for the project overview.
2. Skim [`MIGRATION_HISTORY.md`](MIGRATION_HISTORY.md) to understand the latest platform upgrades.
3. Consult [`../STATUS.md`](../STATUS.md) for current priorities.
4. Dive into [`architecture/`](architecture/) or [`guides/`](guides/) depending on whether you need system internals or usage guides.

## Contributing Docs
- Keep active plans or references in the category directories above.
- When a document becomes historical, move it into the appropriate `archive/` subdirectory with a `YYYY-MM-DD` prefix.
- Update both this index and any relevant sub-index (e.g., `guides/README.md`) when you add or relocate files.

Need help finding something? Search within `docs/archive/` for the original artifact and check `MIGRATION_HISTORY.md` for the digest before reading the full report.
