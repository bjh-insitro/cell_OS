# Guides Index

This directory contains the active guides for cell_OS contributors and operators. Use the catalog below to jump to the doc you need; historical guides live under `../archive/`.

## How to Use These Guides
1. Start with the **User Guide** if you are new to the platform.
2. Pick a domain-specific guide (analytics, inventory, campaign design, etc.) for deeper dives.
3. Cross-link to architecture docs when you need implementation details.

## Guide Catalog
- **[USER_GUIDE.md](USER_GUIDE.md)** – End-to-end orientation for the autonomous operating system.
- **[POSH_SYSTEM_OVERVIEW.md](POSH_SYSTEM_OVERVIEW.md)** – Components and data flow for the POSH screening ecosystem.
- **[campaign.md](campaign.md)** – How the autonomous dose-response engine orchestrates campaigns.
- **[workflow_execution.md](workflow_execution.md)** – Execution + persistence architecture (WorkflowExecutor, JobQueue, data stores).
- **[analytics_and_queue.md](analytics_and_queue.md)** – Analytics dashboards and job queue monitoring pipeline.
- **[acquisition_profiles.md](acquisition_profiles.md)** – Tuning the AI scientist’s acquisition behavior and scoring knobs.
- **[inventory_and_campaigns.md](inventory_and_campaigns.md)** – Inventory management, campaign scheduling, and restock logic.
- **[cell_line_inspector.md](cell_line_inspector.md)** – Using the inspector tools to explore and validate cell-line metadata.
- **[guide_design_usage.md](guide_design_usage.md)** – Integrating the `guide_design_v2` solver for library design.
- **[simulation_and_synthetic_data.md](simulation_and_synthetic_data.md)** – Generating realistic synthetic datasets with the BiologicalVirtualMachine.
- **[COST_AWARE_DECISION_SUPPORT.md](COST_AWARE_DECISION_SUPPORT.md)** – Decision-support tooling for reagent and workflow cost optimization.
- **[CLEANUP_RECOMMENDATIONS.md](CLEANUP_RECOMMENDATIONS.md)** – Active cleanup plan for code and documentation debt.
- **[REWARD_FUNCTIONS.md](REWARD_FUNCTIONS.md)** – Reference for reward modeling inside the autonomous loop.

Looking for historical summaries (e.g., automation or reagent pricing reports)? Check `../archive/migrations/` or `../MIGRATION_HISTORY.md`.
