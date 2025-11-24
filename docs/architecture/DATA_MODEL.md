# DATA_MODEL.md

# cell_OS Data Model

This document defines the canonical data structures used by cell_OS. The goal is simple: a single source of truth for how experiments, assays, unit operations, costs, metadata, and model outputs are represented.

The loop only works when every component speaks the same language. This is that language.

---

# 1. Experimental Record Schema

An experimental record is a single outcome from a proposed experiment. It is the atomic unit of learning for the OS.

| Field              | Type      | Description                                                         |
| ------------------ | --------- | ------------------------------------------------------------------- |
| `experiment_id`    | str       | Unique ID for this run. Format: `exp_{timestamp}_{uuid4}`.          |
| `campaign_id`      | str       | ID linking to the campaign that generated this record.              |
| `cell_line`        | str       | Name of the cell line (U2OS, HepG2, ARPE19, etc).                   |
| `compound`         | str       | Stressor or perturbation.                                           |
| `dose`             | float     | Dose in micromolar. Must be positive.                               |
| `time_h`           | float     | Duration of exposure in hours.                                      |
| `replicate`        | int       | Replicate index within the same experimental proposal.              |
| `viability`        | float     | Observed viability. Range 0 to 1.                                   |
| `raw_signal`       | float     | Optional raw measurement (for debugging and multi readouts).        |
| `noise_estimate`   | float     | Estimated assay noise for this measurement.                         |
| `cost_usd`         | float     | Actual cost of this experiment. Derived from UnitOps and inventory. |
| `unit_ops_used`    | list[str] | Names of UnitOps executed.                                          |
| `automation_score` | float     | Score from 0 to 1. Fraction of the procedure that was automatable.  |
| `timestamp`        | str       | ISO8601 time of execution or simulation.                            |
| `source`           | str       | “simulation”, “wetlab”, or “external”.                              |

The experiment record is written to `results/experiment_history.csv` or an equivalent Parquet file.

---

# 2. Proposed Experiment Schema

The acquisition function outputs a proposal. It is a structured input to the execution engine.

| Field                | Type      | Description                         |
| -------------------- | --------- | ----------------------------------- |
| `proposal_id`        | str       | Unique ID.                          |
| `cell_line`          | str       | Target cell line.                   |
| `compound`           | str       | Compound or stressor.               |
| `dose`               | float     | Proposed dose.                      |
| `time_h`             | float     | Exposure time.                      |
| `plate_format`       | str       | Vessel from the vessel library.     |
| `n_replicates`       | int       | Number of replicates requested.     |
| `expected_cost_usd`  | float     | Cost estimate before execution.     |
| `expected_info_gain` | float     | Acquisition score at proposal time. |
| `unit_ops`           | list[str] | Planned operations for execution.   |

Execution transforms a proposal into an experimental record or a batch of records if there are replicates.

---

# 3. World Model Schema

The world model stores the current state of knowledge. It is updated at each loop iteration.

## 3.1 GP Model State

| Field                | Type        | Description                               |
| -------------------- | ----------- | ----------------------------------------- |
| `cell_line`          | str         | Which GP this model applies to.           |
| `compound`           | str         | Stressor.                                 |
| `kernel_params`      | dict        | Length scales, outputs, jitter.           |
| `training_doses`     | list[float] | Dose values seen so far.                  |
| `training_viability` | list[float] | Observed viability values.                |
| `training_noise`     | list[float] | Noise estimates.                          |
| `posterior_mean`     | ndarray     | Posterior function mean across dose grid. |
| `posterior_std`      | ndarray     | Posterior uncertainty.                    |

Stored in memory during the run and optionally serialized in `results/model_snapshots/`.

## 3.2 Campaign State

Tracks run progress.

| Field              | Type  | Description                    |
| ------------------ | ----- | ------------------------------ |
| `campaign_id`      | str   | Unique campaign identifier.    |
| `budget_remaining` | float | Current wallet.                |
| `total_cost`       | float | Sum of all experiment costs.   |
| `iteration`        | int   | Loop index.                    |
| `history_file`     | str   | Pointer to the experiment log. |

The campaign state can be serialized with `json` or kept ephemeral.

---

# 4. Cost Model Schema

Each experiment cost is computed bottom up from UnitOps. The UnitOps world model contains the static portion of this.

## 4.1 UnitOp Representation

| Field                 | Type  | Description                               |
| --------------------- | ----- | ----------------------------------------- |
| `op_id`               | str   | Operation name or identifier.             |
| `material_cost_usd`   | float | Cost of consumables and reagents.         |
| `instrument_cost_usd` | float | Instrument time cost prorated.            |
| `labor_cost_usd`      | float | Human labor required.                     |
| `automation_fit`      | float | Automation fitness score from 0 to 1.     |
| `time_score`          | float | Estimated operation duration.             |
| `staff_attention`     | float | Continuous measure of manual involvement. |

This is sourced from the upstream files in `data/raw/unit_op_world_model.csv` and populated by `src/unit_ops.py`.

---

# 5. Metadata Layers

These layers enrich the record and feed into assay selectors, recipe optimizers, and workflow planners.

## 5.1 Cell Line Metadata

From `src/cell_line_database.py`.

| Field                      | Description                  |
| -------------------------- | ---------------------------- |
| `doubling_time_h`          | Growth rate.                 |
| `seeding_density`          | Standard seeding density.    |
| `dissociation_method`      | trypsin, accutase, scraping. |
| `preferred_plate_format`   | From vessel library.         |
| `stress_tolerance_profile` | Sensitivity to stressors.    |

## 5.2 Vessel Metadata

From `data/raw/vessels.yaml`.

| Field            | Description                             |
| ---------------- | --------------------------------------- |
| `name`           | Vessel type.                            |
| `volume_ul`      | Working volume.                         |
| `dimensions`     | Physical dimensions for automation.     |
| `compatible_ops` | Which UnitOps are valid on this vessel. |

## 5.3 Pricing Metadata

From `data/raw/pricing.yaml`.

| Field            | Description       |
| ---------------- | ----------------- |
| `reagent`        | Name.             |
| `vendor`         | Cost source.      |
| `pack_size`      | Volume or units.  |
| `unit_price_usd` | Normalized price. |

---

# 6. File Locations

The data model touches these files:

* Experiment log
  `results/experiment_history.csv`

* World model exports
  `results/model_snapshots/` (optional)

* Pricing and costs
  `data/raw/pricing.yaml`
  `data/raw/unit_op_world_model.csv`

* Process metadata
  `data/raw/vessels.yaml`
  `data/raw/resources.csv`
  `data/raw/cell_world_model_export.csv`

---

# 7. Compatibility Contract

For any component to work inside the loop, it must accept and emit structures matching this document.

The contract is:

1. Acquisition consumes GP state and experiment history.
2. Acquisition emits a Proposed Experiment.
3. Execution consumes a Proposed Experiment.
4. Execution emits Experimental Records.
5. Modeling consumes Experimental Records and updates GP state.
6. Campaign consumes cost and maintains budget.

If a module produces data that cannot be expressed in this schema, the schema wins and the module must adapt.

