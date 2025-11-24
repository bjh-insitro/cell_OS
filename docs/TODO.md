Good moment to pause and look at the beast.

Let me go item by item against that earlier plan.

---

## 1. Performance: ActiveLearner refitting

**Original:**
ActiveLearner re-fits all GPs from scratch every step.

**Current state:**

* Still refitting from scratch on every `update`.
* We did clean up the logic and keep it slice-wise (`groupby(["cell_line","compound","time_h"])`), but there is no incremental fit, no sliding window, no thinning of history.

**Verdict:**

* Problem acknowledged, not solved yet.
* Fine for toy loops like 146 records. This will hurt once you start doing real scale.

---

## 2. Smarter acquisition

**Original:**
`AcquisitionFunction.propose()` was falling back to random because `ActiveLearner.predict_on_grid()` was a stub.

**What we have now:**

* `Phase0WorldModel` has been split into a proper posterior (`DoseResponsePosterior` in `posteriors.py`).

* `ActiveLearner` now rebuilds a `Phase0WorldModel(gp_models=...)` from history.

* Acquisition is called as:

  ```python
  proposal = acquisition.propose(
      model=learner.posterior,
      assay=assay,
      budget=campaign.budget,
      n_experiments=batch_size,
  )
  ```

* Inside `AcquisitionFunction.propose` (per your test and behavior):

  * It looks up the specific GP for `(assay.cell_line, assay.compound, time_h)` in `posterior.gp_models`.
  * It runs a proper uncertainty-based scan over a log dose grid.
  * It prints a ranked table with `priority_score`.

Empirically you saw that:

* Step 1 and 2: you get a single "anchor" dose at 1 µM.
* From step 3 onward: it starts fanning out around low doses, then high doses, then bracketed around the apparent IC50.
* Scores shrink as uncertainty drops.

**Verdict:**

* This item is effectively done.
* Could be refined later (multi-timepoints, incorporating noise_df/drift_df in the score) but the big gap is closed.

---

## 3. Multi-fidelity learning

**Original:**
Roadmap: use cheap assays to guide expensive ones.

**Current state:**

* No code that distinguishes low vs high fidelity inside the loop.
* Simulation supports multiple "assay types" conceptually (you have legacy low fidelity simulation), but the loop always picks from one assay library and treats it as single-fidelity.
* No transfer of information between assay types in acquisition.

**Verdict:**

* Still a pure future feature. Nothing implemented.

---

## 4. Inventory depletion tracking

**Original:**
Simulation does not track consumption.

**Current state:**

* `Inventory` exists and is used to compute costs (pricing.yaml).
* Each record now has `cost_usd` and the loop debits `campaign.budget` from the sum of `cost_usd`.
* `SimulationEngine.run` takes `inventory` as an argument but does not call `inv.consume()` or similar.
* No per-reagent consumption, no "out of stock" behavior.

**Verdict:**

* Budget is modeled, physical inventory is not.
* Still to be done.

---

## 5. Better test coverage

**Original:**
Add tests for `DoseResponseGP`, `Campaign`, `ActiveLearner`.

**Current state:**

* `tests/test_acquisition.py` exists and is green. That covers `AcquisitionFunction` reasonably well for max uncertainty behavior.
* I have seen no tests specific for:

  * `DoseResponseGP` (fit + predict_on_grid sanity)
  * `ActiveLearner` (given history, builds expected slice keys and GPs)
  * `Campaign` (goal logic, budget handling)
* So coverage improved only for acquisition.

**Verdict:**

* Only the acquisition part is tested. The rest is still a blind spot.

---

## Quick wins

### a) Logging / monitoring in `run_loop.py`

**Original:**
Add budget burn, info gain etc.

**Now:**

* Budget logging is in place:

  * Per-step budget prints.
  * Per-step `Step cost: $X - New budget: $Y`.

* We also log the top of the proposal table each step, which is a nice trace of what the acquisition is doing.

* We added a final learned-summary:

  ```text
  [summary] Posterior IC50 estimates
  cell_line  compound  time_h  ic50_uM
  ...
  ```

**Verdict:**

* Budget logging: done.
* Info gain per step: not computed yet (no explicit entropy or variance reduction metric).
* But the loop is now quite readable from the console.

### b) Formal `Campaign.budget`

**Original:**
Budget is just a loose attribute.

**Now:**

* You still set `campaign.budget` by hand after construction.
* The class itself does not "own" the budget logic: no methods like `spend(cost)` or protection against negative budget.

**Verdict:**

* Slightly better than before because the loop actually uses `campaign.budget` and updates it, but it is still an informal attribute rather than part of the core `Campaign` API.

### c) Visualization of GP fits

**Original:**
Add plots after each step.

**Now:**

* No plotting code present in `run_loop.py`.
* Only console summaries.

**Verdict:**

* Not started.

---

## Where we actually are

Short version:

* Smarter acquisition: in place and working.
* Loop logging and IC50 summary: in place.
* Budget is active, but campaign/inventory semantics are still light.
* Everything else on that list is still "to do".

If you want a recommended next move that fits your current state:

1. Make `Campaign` own the budget properly.
2. Add a tiny `ActiveLearner` unit test.
3. Then add a minimal inventory depletion hook in `SimulationEngine` that decrements one or two key items per well.

That would give you:

* A loop that is not only "smart" in where it points, but also disciplined about what it spends and what it has left.

If you want, I can pick one of those and give you the usual treatment: files, order, and full drop-in code.
