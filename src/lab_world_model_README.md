# `lab_world_model`

*A minimal real-world state representation for `cell_OS`*
**Last updated:** 2025-11-24

## Overview

`LabWorldModel` is the shared memory structure for everything in `cell_OS` that cares about the real world: what experiments have happened, what campaigns exist, what prices things cost, and what the models currently believe.

It is intentionally dumb.
It does not simulate.
It does not optimize.
It does not fit models.

It holds facts.
And it holds them in one place so Phase 0 (modeling) and Phase 1 (acquisition) can talk without stepping on each other.

## What it stores

The world model splits lab reality into three buckets:

### 1. Static knowledge

Things that do not change unless you re-load them:

* `cell_lines` — metadata for each line (from your `cell_line_database`)
* `assays` — assay definitions, detection limits, etc
* `workflows` — workflow catalog (graphs of UOs)
* `pricing` — reagent and vessel pricing (from `pricing.yaml`)

### 2. Dynamic state

Things that *evolve* with the lab:

* `campaigns` — logical R&D goals
* `experiments` — every experimental well ever logged
  Each row is a canonicalized single-well record, normalized through `_canonicalize_experiment_frame`.

### 3. Beliefs

Outputs of inference:

* `posteriors` — e.g. `DoseResponsePosterior` objects keyed by `campaign_id`

The model never fits them.
It only stores them.

## Why canonicalization matters

All experiment tables go through `_canonicalize_experiment_frame` before being stored.
This gives you stable columns:

* `campaign_id`
* `workflow_id`
* `cell_line`
* `compound`
* `dose_uM`
* `time_h`
* `viability`
* `replicate`
* plus optional metadata (`plate_id`, `well_id`, `timestamp`, etc)

This means downstream code can assume a consistent schema even if the upstream log was chaotic.

## Main entry points

### Build an empty world

```python
world = LabWorldModel.empty()
```

### Build from static tables

```python
world = LabWorldModel.from_static_tables(
    cell_lines=df_cells,
    assays=df_assays,
    workflows=df_workflows,
    pricing=df_pricing,
)
```

### Build from an experiment CSV

```python
world = LabWorldModel.from_experiment_csv("results/experiment_history.csv")
```

### Append experiments

```python
world.add_experiments(new_measurements_df)
```

### Work with campaigns

```python
world.add_campaign(Campaign(
    id="PHASE0_SANDBOX",
    name="Phase 0 Sandbox",
    objective="Learn viability curves",
    primary_readout="viability",
    workflows=["WF_PHASE0_DR_V1"]
))

sandbox = world.get_campaign("PHASE0_SANDBOX")
```

### Query slices of the experiment table

```python
df = world.get_slice(
    campaign_id="PHASE0_SANDBOX",
    cell_line="HepG2",
    compound="TBHP",
    time_h=24,
)
```

### Attach or retrieve a posterior

```python
posterior = world.build_dose_response_posterior("PHASE0_SANDBOX")
retrieved = world.get_posterior("PHASE0_SANDBOX")
```

## Typical workflow in the `cell_OS` loop

1. Experiments are logged into CSVs or directly fed into `world.add_experiments`.
2. Phase 0 models read slices via `get_slice` and produce updated posteriors.
3. Phase 1 acquisition logic queries posteriors and experiment history to propose next experiments.
4. Newly executed experiments get added back into the world.
5. Repeat.

The world model is the spine of the loop.

## Design philosophy

* *Minimal, not magical* — the world model never guesses intent.
* *Forgiving on input, strict on output* — canonicalization creates order from chaos.
* *Separation of concerns* — reality lives here; inference lives in `posteriors.py`; planning lives in `acquisition.py`.
* *Round-trip stable* — if you dump and reload experiments, nothing changes.

## Future extensions

Things that logically belong here later, if you need them:

* versioned experiment logs
* explicit `Experiment` dataclass for type-safety
* links to raw plate images or POSH tiles
* richer cost/performance models tied to workflows

For now: keep it lean.