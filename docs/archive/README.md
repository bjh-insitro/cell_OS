# Documentation Archive

All historical documentation now lives here, separated from the active docs for clarity. Files are renamed with `YYYY-MM-DD-description.md` so their chronology is obvious at a glance.

## Layout
- `sessions/` – Session summaries (engineering sprints, migrations, VM work). Example: `2025-11-30-complete-refactoring-session.md`.
- `migrations/` – Migration/milestone write-ups, validation packets, and audit reports. These are summarized in `../MIGRATION_HISTORY.md`.
- `refactorings/` – Completed refactor plans and retrospectives.
- `status/` – Legacy status, progress, and next-step reports (replaced by the root `STATUS.md`).

## How to Use
1. Start with `../MIGRATION_HISTORY.md` or `../../STATUS.md` to understand the latest state.
2. Jump into the relevant subdirectory for full detail (e.g., `migrations/` for validation packets).
3. When archiving a new document:
   - Move it into the appropriate subdirectory.
   - Rename it `YYYY-MM-DD-short-description.md`.
   - Update any indices (`docs/README.md`, `docs/guides/README.md`, `docs/MIGRATION_HISTORY.md`) that referenced the active doc.

## Adding More Archives
Need another category? Add a new subdirectory here, document it in this README, and update the main docs index so contributors know where to find it.
