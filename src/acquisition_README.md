# **README — Acquisition Module**

**Last updated: 2025-11-24 16:45 PST**

This module defines how Phase 1 experiments are chosen in **cell_OS**.
It is responsible for turning a model state (GP or world model) into a ranked set of proposed wells you can actually run.

It does three things:

1. **Score candidate doses**
2. **Apply constraints (budget, assay slice, repeat penalties)**
3. **Assign plate/well positions for execution**

Everything else is implementation detail.

---

# **Core Concepts**

### **1. Inputs**

The acquisition module takes one of two inputs:

#### **A. A single DoseResponseGP**

Used for 1D acquisition:

* Generate a dose grid
* Predict mean + std
* Score each dose
* Return the top‐N most informative

#### **B. A Phase0WorldModel**

Contains multiple GP slices indexed by `(cell_line, compound, time_h)`.
Acquisition can filter by a specific “assay” (cell/compound/time).
Useful when you are running multi-slice campaigns.

---

### **2. Scoring Logic**

Every candidate dose receives a **priority_score** based on:

```
score = (uncertainty - repeat_penalty)
```

Or, if configured:

```
score = (uncertainty - repeat_penalty) / cost
```

Where:

* **uncertainty** = GP predictive standard deviation
* **repeat_penalty** = discourages re-running the same dose
* **cost** = cost_per_well_usd from reward_config

This prevents hammering the same dose six times “because uncertainty is high.”

---

### **3. Budget Constraint**

If a budget is provided:

```
max_experiments = floor(budget / cost_per_well)
```

`n_experiments` is capped automatically.
If your budget is zero or negative, you get an empty DataFrame.
No magic spending.

---

### **4. Plate Assignment**

Experiments are assigned to a 96-well plate layout:

* Plate ID via `reward_config["plate_id"]` (default: `"Phase1_Batch1"`)
* Wells in row-major order (A01 → H12)

Future-proof: plate ID and plate format can be extended via config.

---

# **Public API**

## **AcquisitionFunction**

Main class for selecting experiments.

### **`propose(model, assay, budget=None, n_experiments=8)`**

Handles both single-GP and world-model acquisition.

Returns a DataFrame with:

| column             | meaning           |
| ------------------ | ----------------- |
| cell_line          | slice cell line   |
| compound           | slice compound    |
| dose_uM            | proposed dose     |
| time_h             | exposure time     |
| priority_score     | acquisition score |
| expected_cost_usd  | cost per well     |
| expected_info_gain | predictive std    |
| unit_ops           | list of unit ops  |
| plate_id           | assigned plate    |
| well_id            | assigned well     |

---

## **Reward Configuration**

Optional dict passed at initialization:

```python
reward_config = {
    "dose_grid_size": 50,
    "dose_min": 0.001,
    "dose_max": 10.0,
    "cost_per_well_usd": 1.0,
    "repeat_penalty": 0.02,
    "repeat_tol_fraction": 0.05,
    "plate_id": "Phase1_Batch1",
    "mode": "max_uncertainty"   # or "ig_per_cost"
}
```

---

## **Legacy Function**

### **`propose_next_experiments(world_model, ...)`**

Thin wrapper maintained for backward compatibility.

Calls the new acquisition engine under the hood and returns:

```
selected, df_candidates
```

---

# **File Structure**

```
acquisition.py
↓
class AcquisitionFunction
    - propose(...)
    - _propose_from_world(...)
    - _score_candidate(...)
    - _compute_repeat_penalty_for_gp(...)
    - _assign_plate_and_wells(...)

legacy entry: propose_next_experiments(...)
```

The module does not assume:

* plate format beyond 96-well
* fixed cost
* fixed unit ops
* fixed campaign structure

All of those can be changed via config.

---

# **FAQ**

### **Q: What happens if my world model has no GPs?**

Fallback: one default experiment (`dose = 1.0 uM`).

### **Q: What if the GP throws errors?**

Logged via Python `logging` (no more `print` statements).

### **Q: Does this schedule cross-cell or cross-compound batches?**

Yes, unless you filter via `assay`.

### **Q: Is scoring deterministic?**

Yes, deterministic over the GP predictions.

---

# **Summary**

The acquisition module now behaves like something you can actually use in an autonomous loop:

* consistent
* debuggable
* configurable
* aware of cost
* aware of history
* supports both single-slice and multi-slice design

It’s clean enough that you could plug it into a real loop tomorrow.

