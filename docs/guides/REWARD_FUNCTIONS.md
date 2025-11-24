# REWARD_FUNCTIONS.md

# Reward Functions in cell_OS

This guide defines how cell_OS scores experiments when choosing what to do next.

The OS does not “want” one thing. It trades off three:

1. Information gain
2. Practical gain (better protocols, better protection, better EC50)
3. Cost and automation burden

The reward function is how those collide into a single number the acquisition layer can use.

---

## 1. Objectives and Signals

cell_OS currently optimizes around viability under stress, subject to budget and automation constraints.

Core signals:

* `viability`
  Primary readout, normalized between 0 and 1

* `uncertainty`
  Posterior standard deviation from the GP model

* `cost_usd`
  Total cost from UnitOps plus labor plus instrument cost

* `automation_score`
  Fraction of the workflow that is automatable between 0 and 1

* `info_gain`
  Expected reduction in uncertainty at candidate points

Any reward function is built from these and possibly higher level derived metrics such as EC50.

---

## 2. Base Acquisition: Expected Improvement

The current acquisition building block is Expected Improvement (EI).

For a candidate `(cell_line, compound, dose)` with predictive mean `mu(x)` and standard deviation `sigma(x)`:

* Let `f_best` be the best observed value for the objective so far
* The improvement is `I(x) = max(0, f(x) − f_best)`
* EI is `E[I(x)]` under the GP posterior

cell_OS uses EI on one of the following objective choices:

1. Direct viability at a fixed time
2. Negative EC50 (lower EC50 is better, so maximize `−EC50`)
3. Any scalar objective derived from the GP fit

The acquisition module exposes at least:

```python
class AcquisitionFunction:
    def __init__(self, objective="viability"):
        ...

    def ei(self, model, x):
        """Compute Expected Improvement at candidate x."""
```

EI by itself ignores cost and automation. It only cares about likely performance.

---

## 3. Cost Aware Acquisition

To bring reality into the loop, EI is scaled by cost and optionally by automation.

### 3.1 Cost scaling

Define a cost weight `lambda_cost` in units of inverse dollars.

We define a cost adjusted acquisition:

```text
A_cost(x) = EI(x) / (1 + lambda_cost * cost_usd(x))
```

Properties:

* If cost is small, `A_cost` is close to EI
* If cost is large, the term shrinks
* `lambda_cost` controls how aggressive the penalty is

This connects `src.acquisition` with:

* `src.unit_ops`
* `data/raw/pricing.yaml`
* `data/raw/unit_op_world_model.csv`

### 3.2 Automation scaling

Optionally, automation is a positive factor. More automation is better.

Define `automation_score(x)` between 0 and 1.

```text
A_cost_auto(x) = A_cost(x) * (alpha + (1 - alpha) * automation_score(x))
```

with `alpha` in `[0, 1]`:

* `alpha = 1` means automation is ignored
* `alpha = 0` means low automation heavily suppresses the score

This gives you a dial between “I do not care about automation” and “I very much care about automation”.

---

## 4. Epistemic Gain vs Geometric Gain

You can think of experiments in two categories.

1. Epistemic gain
   Reduce uncertainty in the dose response curve.
   This improves the model, even if the specific dose is not useful for a final protocol.

2. Geometric gain
   Push performance in a region that is already promising.
   For example, refine around the EC50 or optimal protection window.

cell_OS can blend these with:

```text
reward(x) = w_epi * epistemic_gain(x) + w_geo * geometric_gain(x)
```

Where:

* `epistemic_gain(x)` can be approximated by `sigma(x)` or by entropy reduction
* `geometric_gain(x)` can be based on EI around a target region

Weights `w_epi` and `w_geo` define whether a campaign is in exploration or optimization mode.

The AcquisitionFunction can expose this as:

```python
def score(self, model, candidate, mode="balanced"):
    ...
```

With presets:

* `"explore"`: higher `w_epi`
* `"exploit"`: higher `w_geo`
* `"balanced"`: default blend

---

## 5. Full Reward with Cost and Automation

Putting it together, the effective acquisition value for a candidate `x` is:

```text
1. Compute epistemic_gain(x) and geometric_gain(x)
2. Combine:
   base = w_epi * epistemic_gain(x) + w_geo * geometric_gain(x)

3. Apply cost scaling:
   A_cost(x) = base / (1 + lambda_cost * cost_usd(x))

4. Apply automation scaling:
   reward(x) = A_cost(x) * (alpha + (1 - alpha) * automation_score(x))
```

The loop then selects the candidate with the highest `reward(x)` under the current constraints.

This scalar `reward(x)` is what drives the actual choice of experiments in `AssaySelector` or an equivalent selection layer.

---

## 6. Campaign Level Constraints

Rewards sit inside campaign rules.

Even if a candidate has high `reward(x)`, it can be rejected if:

* Budget would go negative
* Cell supply is insufficient
* Plate capacity is exceeded
* A safety or sanity constraint is violated

These constraints live in the campaign and world model modules:

* `src.campaign`
* `src.core.world_model`

The pattern is:

1. Acquisition proposes a batch of high reward candidates
2. Campaign filters them through constraints
3. The top feasible set is executed

---

## 7. Tuning and Configuration

All the knobs above need to be configurable, not baked into code.

Recommended config fields (for example in `config/phase0.yaml`):

```yaml
reward:
  objective: "viability"          # or "neg_ec50"
  mode: "balanced"                # explore, exploit, balanced
  w_epi: 0.5
  w_geo: 0.5
  lambda_cost: 0.01               # inverse dollars
  automation_alpha: 0.6           # 0 = strongly prioritize automation
```

The acquisition object should read these values and compute `reward(x)` accordingly.

---

## 8. Future Extensions

This framework is intentionally minimal and extensible.

Possible additions:

* Multi objective Pareto front analysis for cost vs performance
* Risk aware terms that penalize regions with high predicted toxicity
* Time aware reward that penalizes long protocols even if they are cheap
* Library stage specific reward presets (Phase 0, production screens, follow ups)

All of these should still reduce to a scalar `reward(x)` at the selection boundary.

---

