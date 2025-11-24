# SYSTEM_GLUE.md

# System Glue for cell_OS

This document explains how the major components of cell_OS interact. It is not a design pitch. It is a wiring diagram that shows who calls what, who depends on what, and who must stay ignorant of what.

The goal is simple: keep the OS modular without losing its spine.

---

# 1. The Big Picture

The loop has five pillars:

1. Campaign
2. World Model
3. Assay Selection
4. Acquisition
5. Execution (Simulation or Real)

Every iteration flows in the same direction:

**campaign → selector → acquisition → execution → modeling → campaign**

Think of it as a circulatory system with one valve at each step.

---

# 2. Component Responsibilities and Boundaries

Each component has a strict contract.

---

## 2.1 Campaign (`src/campaign.py`)

Campaign holds:

* budget
* iteration count
* experiment history
* stop conditions

Campaign does not:

* know GP math
* know plate formats
* know UnitOps
* know how experiments are executed

Campaign only cares about:

* whether a proposal is feasible
* how much it costs
* what the result was

**Exports**

* `budget_remaining`
* `update(result)`
* `record_experiment(record)`
* `exhausted()`

**Imports**

* cost from execution
* record from execution
* proposals from selector

Campaign is the boss of the loop.

---

## 2.2 World Model (`src/core/world_model.py`)

The world model stores:

* cell line metadata
* reagent metadata
* vessel metadata
* dose grids
* allowed operations
* available assays

It is the static backbone.

World model does not:

* update based on results (that is modeling)
* track cost or budget (campaign)

**Exports**

* domain knowledge (cell lines, compounds, vessels)
* assay templates
* constraints
* allowed combinations

**Imports**

* configuration

World model is the “rules of the world.”

---

## 2.3 Modeling (`src/modeling.py`)

Modeling holds the GP posterior over dose response curves.

It handles:

* training data ingestion
* GP update
* uncertainty calculations
* generating predictions for acquisition

Modeling does not:

* know what an experiment *costs*
* know what the campaign budget is
* know UnitOps
* know automation scoring

**Exports**

* `predict(x)`
* `posterior_mean`
* `posterior_std`
* `update(record)`

**Imports**

* training records from execution
* dose grid from world model

Modeling is the “brainstem.”

---

## 2.4 Assay Selector (`src/assay_selector.py`)

Selector decides which *area of the space* to explore next.

Inputs:

* campaign budget
* world model (allowed cell lines, compounds, ranges)
* current GP state (optional)

Outputs:

* a set of candidate assays for acquisition

Selector does not:

* compute EI
* generate doses
* interact with UnitOps
* execute any experiments

Selector is a “map reader.”

---

## 2.5 Acquisition (`src/acquisition.py`)

Acquisition converts a selected assay into specific experiments.

Inputs:

* GP model predictions
* candidate assay from selector
* cost estimates via UnitOps
* automation scoring
* reward config

Outputs:

* ProposedExperiment objects with dose, replicates, vessel, expected cost, expected info gain

Acquisition does not:

* execute experiments
* update budget
* write logs

Acquisition is the “decision maker.”

---

## 2.6 Execution (`src/simulation.py` or real runner)

Execution takes proposed experiments and performs them.

Simulation does:

* generate measurements
* inject noise
* compute cost
* compute automation score
* return ExperimentalRecord objects

Real execution would:

* use POSH, wet lab, or robotics
* read from LIMS
* timestamp runs
* attach metadata

Execution does not:

* choose what to run
* perform GP updates
* manage budget

Execution is the “hands.”

---

# 3. Data and Control Flow

A single loop iteration flows as follows:

```
campaign
    → selector
        → acquisition
            → execution
                → modeling
                    → campaign
```

### 1. Campaign selects allowed region

Campaign gives selector current budget and progress.

### 2. Selector proposes an assay

Selector picks a cell line, compound, and region of dose space.

### 3. Acquisition chooses exact doses

Acquisition computes reward, costs, automation fit, EI, and picks a batch.

### 4. Execution runs proposals

Simulation or real lab returns ExperimentalRecords.

### 5. Modeling updates GP

Posterior tightens, uncertainty drops.

### 6. Campaign updates budget and history

Budget reduces. History grows. Loop continues.

---

# 4. What Connects to What

This matrix keeps the system clean.

| Component   | Campaign | World Model | Selector | Acquisition | Execution | Modeling |
| ----------- | -------- | ----------- | -------- | ----------- | --------- | -------- |
| Campaign    | X        | R           | R        | R           | R         | R        |
| World Model | R        | X           | R        | R           | R         | R        |
| Selector    | R        | R           | X        | R           |           | R        |
| Acquisition | R        | R           | R        | X           | R         | R        |
| Execution   | R        | R           |          | R           | X         | R        |
| Modeling    | R        | R           | R        | R           | R         | X        |

R means “reads”.

No component writes to another except:

* Execution writes to Modeling
* Modeling writes to itself
* Campaign writes to itself
* Execution writes records to Campaign
* Acquisition writes proposals to Execution

Nothing else crosses boundaries.

---

# 5. Files Involved

Core modules:

```
src/
    campaign.py
    assay_selector.py
    acquisition.py
    simulation.py
    modeling.py
    inventory.py
    unit_ops.py
    core/world_model.py
```

These are the canonical entry points for the loop.

Everything else is supporting machinery.

---

# 6. Entry Points

Execution of the loop should be anchored in:

```
run_loop.py
```

This file should orchestrate:

* loading config
* instantiating campaign
* creating world model
* calling selector
* calling acquisition
* calling execution
* calling modeling
* saving logs

This is the only script allowed to call every component.

---

# 7. Invariants

To keep the glue clean:

1. GP models never call cost or automation code.
2. Campaign never calls GP internals.
3. Selector does not know UnitOps or pricing.
4. Acquisition does not know LIMS or plate hardware.
5. Execution does not make decisions.
6. World model never mutates after initialization.

If any module starts crossing boundaries, the system becomes opaque and the loop stops being predictable.
