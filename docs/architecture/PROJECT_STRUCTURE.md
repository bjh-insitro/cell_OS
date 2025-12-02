# Project Structure — cell_OS

**Last Updated:** 2025-12-01

This guide explains how the repository is organized today so you can quickly find code, documentation, and operational tooling.

---

## 🗂️ Root Overview

| Path | Purpose |
|------|---------|
| `README.md` | High-level overview + quick start. |
| `STATUS.md` | Current deliverables, validation snapshot, and next focus. |
| `Documentation_Housekeeping_Plan.md` | Historical record of the doc cleanup project. |
| `pyproject.toml`, `requirements.txt`, `Makefile` | Packaging, dependency, and workflow automation. |
| `PRICING_YAML_DEPRECATED.md` | Notes for the legacy YAML pricing catalog (superseded by SQLite DBs). |
| `verify_install.py` | Environment/installation validator. |
| `audit_entire_platform.py`, `audit_inventory.py`, `sync_inventory.py` | Operational scripts kept at the root for quick invocation. |

Key directories you will touch most often:

```
cell_OS/
├── dashboard_app/          # Streamlit UI
├── docs/                   # All documentation (with archive/)
├── src/                    # Source code (pip-installable package)
├── scripts/                # Operational scripts (demos, migrations, seeding)
├── config/                 # Example YAML configs
├── data/                   # SQLite databases + raw assets
├── tests/                  # Unit + integration suites
├── examples/               # Usage samples + notebooks
└── tools/, design/, notebooks/, etc.
```

---

## 📚 Documentation (`docs/`)

- **`docs/README.md`** — Documentation index + getting-started pointers.
- **`docs/MIGRATION_HISTORY.md`** — Digest of migrations, refactors, and validation packets.
- **`docs/QUICK_WINS.md`** — Low-effort improvements backlog with status.
- **`docs/REFACTORING_OPPORTUNITIES.md`** — Active refactor plan.
- **`docs/architecture/`** — Architecture, ontology, and structure docs (this file).
- **`docs/guides/README.md`** — Catalog of all active guides (POSH overview, workflow execution, simulation, analytics, etc.).
- **`docs/protocols/`** — Lab SOPs (POSH, upstream, QC).
- **`docs/refactor_plans/`** — In-flight engineering plans (e.g., BOM tracking).
- **`docs/system/`** — Deep dives on lab world models and acquisition systems.
- **`docs/archive/`** — Historical documents moved out of active circulation. See `docs/archive/README.md` for layout (sessions/, migrations/, refactorings/, status/).

Whenever you retire a document, move it into the appropriate archive subdirectory with a `YYYY-MM-DD-` prefix and update `docs/MIGRATION_HISTORY.md` so the digest stays accurate.

---

## 🖥️ Dashboard (`dashboard_app/`)

- **`app.py`** — Streamlit entry point. Launch via `streamlit run dashboard_app/app.py`.
- **`config.py`** — Page registry (categories, ordering, metadata).
- **`pages/`** — 20+ tab implementations (Mission Control, Science, Economics, Workflow Visualizer, POSH tools, BOM audits, facility planning, MCB/WCB sims, etc.).
- **`components/`** — Shared UI widgets.
- **`test_refactoring.py`** — Smoke tests to ensure every registered page renders.
- **Supporting docs**: `README.md`, `MIGRATION.md`, `BEFORE_AFTER.md`, `ARCHITECTURE.txt`, `IMPROVEMENTS.md`, `QUICK_REFERENCE.md`.

---

## 🧠 Source Code (`src/`)

`src/` contains the pip-installable package used by both the CLI (`cell-os-run`) and the dashboard.

- **`src/cell_os/`** — Primary package with:
  - **Execution & Scheduling**: `autonomous_executor.py`, `job_queue.py`, `workflow_execution/`, `workflow_executor.py`, `scheduler.py`.
  - **Simulation & Modeling**: `hardware/biological_virtual.py` (BiologicalVirtualMachine), `simulation_executor.py`, `mcb_crash.py`, `wcb_crash.py`, `facility_sim.py`, `modeling.py`.
  - **Databases & Persistence**: `database/`, `campaign_db.py`, `simulation_params_db.py`, `inventory_manager.py`.
  - **POSH & Campaign Planning**: `posh_*` modules, `campaign_manager.py`, `campaign.py`, `guide_design_v2.py`.
  - **Unit Operations & Protocols**: `unit_ops/`, `protocol_resolver.py`, `protocol_templates.py`, `upstream.py`.
  - **Analytics & Reporting**: `phenotype_clustering.py`, `plotly_reporter.py`, `reporting.py`, `html_reporter.py`.
  - **Utilities**: `config/`, `config_utils.py`, `notifications.py`, `schema.py`, `world_init.py`.
- **`src/core/`** — Lower-level infrastructure helpers.
- **`src/simulation/`, `src/economics/`, `src/protocols/`** — Additional domain-specific modules.
- **`src/run_scenario.py`** — CLI entry point for running scenarios outside the main loop.

Install the package locally with `pip install -e .` to expose the `cell-os-run` CLI and importable modules.

---

## 🛠️ Scripts & CLI

- **`cli/run_campaign.py`** — Thin wrapper that exercises the installed package; primarily used by the new CLI tooling.
- **`scripts/`** — Operational utilities grouped by purpose:
  - `demos/` (simulation + dashboard demos)
  - `migrations/` (data migrations, DB upgrades)
  - `debugging/`, `testing/`, `visualization/` helpers
  - Seeding utilities (`seed_cell_line_protocols.py`, `seed_simulation_params.py`)
  - Automation helpers (`update_inventory_bom.py`, `bootstrap_data.py`)
- Prefer running these scripts via `python -m scripts.<module>` or the `scripts/README.md` instructions so dependencies are loaded correctly.

---

## 🗃️ Configs & Data

- **`config/`** — Example YAML configs (`campaign_example.yaml`, `guide_design_template.yaml`, `sgRNA_repositories.yaml`). These are safe starting points for the CLI or dashboard demos.
- **`data/`** — SQLite databases (`cell_lines.db`, `simulation_params.db`, `inventory.db`, etc.), legacy raw YAML files, and backup assets. Treat as mutable runtime data; avoid checking in large generated files.
- **`PRICING_YAML_DEPRECATED.md`** — Describes the transition from YAML pricing catalogs to SQLite for pricing/inventory data.
- **`data/notifications.db`** — Dashboard-generated notifications log; ignored by git.

---

## ✅ Tests & Tooling

- **`tests/`** — Unit, integration, and smoke tests. Highlights:
  - `tests/integration/` for dashboard smoke tests, BOM validation, etc.
  - `tests/unit/` for core modules (VirtualMachine, inventory, unit ops).
- **`tools/`** — Supporting developer utilities.
- **`notebooks/`** — Exploratory analyses and demos (kept lightweight; heavy outputs should be ignored via `.gitignore`).
- **`design/`** — UX flows and diagrams.

Run `pytest` (or `make test`) from the repo root; the src-layout ensures Python can resolve imports without `PYTHONPATH` tweaks.

---

## 🔁 Historical Artifacts

- Legacy documents, validation packets, and refactor summaries now live exclusively in `docs/archive/**`.
- `docs/archive/README.md` documents the naming convention and where to file new archival docs.
- Active references (README, STATUS, guides) should point to `docs/MIGRATION_HISTORY.md` rather than individual archive files unless deep detail is required.

With this structure, new contributors can navigate from the root README → docs index → targeted module without chasing outdated file names (e.g., the dashboard entry point is `dashboard_app/app.py`, not `dashboard.py`). Keep this document up to date whenever directories move or new top-level capabilities are added.
