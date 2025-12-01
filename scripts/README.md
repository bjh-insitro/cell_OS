# Scripts Directory

The `scripts/` folder is organized by purpose so it is easier to find the right helper:

- `demos/` – end-to-end walkthroughs and CLI entry points (`run_loop_v2.py`, imaging demos, POSH demos, etc.).
- `migrations/` – database/data migration helpers (campaigns, pricing, simulation parameters, YAML → DB).
- `debugging/` – targeted investigation utilities (recipe/workflow debuggers, optimizer diagnostics, synthetic embedding generators, DB consistency checks).
- `visualization/` – comparison & plotting helpers for personalities/profiles and POSH score landscapes.
- `testing/` – smoketests and harnesses for imaging + QC experiments.

Add new scripts to the appropriate subfolder and document their usage inline so other developers can discover them quickly.
