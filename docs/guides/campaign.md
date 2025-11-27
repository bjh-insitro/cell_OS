# `cell_OS` — Autonomous Dose Response Engine

**Updated: 2025-11-24**

`cell_OS` is a small, focused autonomous experimentation loop for viability-based dose response. It models each `(cell_line, compound)` slice with a Gaussian Process, selects experiments via uncertainty, and evaluates scientific goals like potency and selectivity through campaign logic.

This is a Phase-0 prototype. It’s intentionally simple. But it has structure and the core mechanics of an automated scientific loop.

---

## What the system does right now

### 1. **Ingest experimental measurements**

You provide CSV rows like:

* `cell_line`
* `compound`
* `dose_uM`
* `time_h`
* `viability_norm`

`Phase0WorldModel` builds Gaussian Processes for each `(cell_line, compound)`.

### 2. **Model dose response with a GP**

Every slice gets a `DoseResponseGP`, using:

* RBF kernel in log₁₀(dose)
* White noise for replicate variance
* Posterior mean and standard deviation across doses

This gives the world model its “belief state”.

### 3. **Propose new experiments**

`propose_next_experiments`:

* Samples candidate doses on a grid
* Computes GP posterior uncertainty
* Selects the most uncertain points
* Returns a batch of next experiments

This is the epistemic-gain loop: run experiments that reduce uncertainty fastest.

### 4. **Run campaign logic (new)**

`campaign.py` adds:

* Scientific goals (**Potency**, **Selectivity**)
* Cycle manager (`Campaign`)
* IC50 estimation from the GP
* Portfolio summarization across all slices

This turns your dose loop into an **actual autonomous campaign** with a goal, cycles, and stopping criteria.

---

## The new `Campaign` layer

### **PotencyGoal**

Find any compound with IC50 below a threshold for a cell line.

```python
PotencyGoal(cell_line="A549", ic50_threshold_uM=1.0)
```

### **SelectivityGoal**

Find compounds potent on the target cell but safe on the reference.

```python
SelectivityGoal("A549", "U2OS", potency_threshold_uM=1.0, safety_threshold_uM=5.0)
```

### **Campaign**

Runs cycles until the goal is met or max cycles reached.

```python
campaign = Campaign(goal, max_cycles=5)
cycle_df = campaign.run_cycle(world_model, n_experiments=8)
campaign.check_goal(world_model)
```

Each cycle:

1. Proposes new experiments
2. Logs decisions
3. Lets you update the world model
4. Stops when goal is achieved

---

## IC50 estimation

`estimate_ic50_from_gp()` sweeps doses on a log grid, finds the first viability crossing through 0.5, and interpolates. Simple. Fast. Good enough for Phase-0.

---

## Portfolio view

`summary = summarize_portfolio(world_model)` returns:

| cell_line | compound | ic50_uM |
| --------- | -------- | ------- |
| A549      | CMP1     | 0.83    |
| U2OS      | CMP1     | 6.1     |
| A549      | CMP2     | None    |

Useful when checking selectivity.

---

## Minimal end-to-end example

```python
from src.schema import Phase0WorldModel
from src.campaign import Campaign, SelectivityGoal, summarize_portfolio

# Build world model from initial data
world_model = Phase0WorldModel.from_csv("results/experiment_history.csv")

# Define scientific goal
goal = SelectivityGoal(
    target_cell="A549",
    safe_cell="U2OS",
    potency_threshold_uM=1.0,
    safety_threshold_uM=5.0,
)

campaign = Campaign(goal, max_cycles=10)

while not campaign.is_complete:
    proposals = campaign.run_cycle(world_model, n_experiments=8)

    # send `proposals` to lab or simulator
    # ingest new results → world_model.update_with_data(new_data)

    campaign.check_goal(world_model)

print("Campaign success:", campaign.success)
print(summarize_portfolio(world_model))
print(campaign.history)
```

---

## Directory structure (current)

```
cell_OS/
│
├── src/
│   ├── acquisition.py         # propose_next_experiments
│   ├── campaign.py            # campaign manager + goals + IC50
│   ├── modeling.py            # Gaussian Process fits
│   ├── schema.py              # Phase0WorldModel, SliceKey
│   └── unit_ops/              # unrelated, future automation scaffolding
│
├── data/
│   ├── raw/
│   └── results/
│
├── tests/
│
└── README.md
```

---

## Future directions (logical next steps)

These are natural and small:

* add **confidence intervals** around IC50
* goal = “stop when IC50 CI width < X”
* add Bayesian optimization for dose selection
* incorporate plate drift model into GP
* combine multiple assays (ROS, apoptosis, etc)
* unify experimental metadata under `LabWorldModel`

Right now you have a solid spine: world model → acquisition → campaign.

Everything else grows from this.
