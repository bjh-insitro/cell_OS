# scRNA-seq Hardening: Making scRNA Painful in the Loop

**Date**: 2025-12-20
**Status**: SHIPPED

## Philosophy

scRNA-seq is not a ground truth oracle. It's an expensive, slow, confounded measurement that should be **earned**, not defaulted to. This document describes the hardening applied to make scRNA feel painful enough that agents must justify its use.

## The Four Pillars

### 1. Cost and Time Model That Actually Bites

**Location**: `data/scrna_seq_params.yaml`, `biological_virtual.py:3139-3177`

```yaml
costs:
  time_cost_h: 4.0           # 4 hours (vs 2h for cell painting)
  reagent_cost_usd: 200.0    # 10× more expensive than imaging
  min_cells: 500             # Minimum for reliable estimates
  soft_penalty_if_underpowered: 0.25  # Penalty if agent ignores power requirements
```

**Implementation**:
- `time_cost_h` is applied via `_simulate_delay()`, increasing drift exposure
- Cost metrics are returned in assay result for planner consumption
- `is_underpowered` flag warns when n_cells < min_cells

**Critical**: Time cost should increase **nuisance risk** in your planner. The longer an assay takes, the more batch drift accumulates. This is not decorative morality—it's drift mechanics.

---

### 2. Cell Cycle Confounder That Is Not a Toy

**Location**: `data/scrna_seq_params.yaml:173-198`, `transcriptomics.py:255-285`

```yaml
cell_cycle:
  cycling_fraction_by_cell_line:
    A549: 0.55      # Lung cancer, proliferative
    HEK293: 0.60    # Highly proliferative
    iPSC_NGN2: 0.08 # Neurons, post-mitotic

  cycling_program:
    MKI67: 8.0   # Proliferation marker
    TOP2A: 6.0   # DNA replication
    PCNA: 3.0    # DNA synthesis

  stress_antagonism:
    # Cycling SUPPRESSES stress markers (resource competition)
    HSPA5: 0.70   # 30% reduction in ER stress marker
    DDIT3: 0.65   # 35% reduction
    ATF4: 0.75    # 25% reduction
```

**Why this matters**:
- Cycling cells show high MKI67/TOP2A (looks like "recovery")
- But stress markers are suppressed due to resource competition
- This creates **false recovery signals** in proliferating populations
- Naive averaging gives "low stress" even when ground truth is stressed

**Empirical validation** (from `test_scrna_is_not_ground_truth.py`):
```
Ground truth: ER stress = 0.6
Cycling cells:     HSPA5=256, DDIT3=83, ATF4=61
Non-cycling cells: HSPA5=373, DDIT3=124, ATF4=84
→ 30-35% suppression, exactly as specified
```

This is not a toy. This is a **confounder**: cycling explains away variance that would otherwise be attributed to stress programs.

---

### 3. Agent Must Refuse: Principled Gating

**Location**: `src/cell_os/hardware/assay_governance.py`

```python
@dataclass(frozen=True)
class AssayJustification:
    ambiguity: str                      # "ER vs oxidative crosstalk"
    failed_modalities: Tuple[str, ...]  # ("cell_painting", "atp")
    expected_information_gain: float    # Bits
    min_cells: int
    replicate_strategy: Optional[str]   # Required if drift is high
```

**Refusal criteria**:
1. **Underpowered**: `min_cells < params["costs"]["min_cells"]`
2. **No cheaper alternatives**: `len(failed_modalities) < 1`
3. **Poor info gain per dollar**: `info_gain / cost < 0.002 bits/$`
4. **High drift without replicate plan**: `drift_score > 0.7` and no replicate strategy

This is **not** a confidence threshold. It's a **justification schema** that must be satisfied. You can't game it by adjusting your confidence—you must demonstrate that:
- You tried cheaper assays first
- The information gain justifies the cost
- You have a plan for dealing with batch effects

---

### 4. Disagreement Must Widen Posteriors

**Status**: Schema defined, integration pending

**Philosophy**: When morphology says "ER stress" and scRNA says "oxidative stress," your posterior should **widen** (increase uncertainty), not narrow to whichever assay is fancier.

**Current implementation**:
- Batch drift is **stronger** in scRNA than imaging (by design)
- Cell cycle confounder creates **systematic disagreement**
- Cost model ensures scRNA is **expensive enough to regret**

**Next step**: Integrate with `mechanism_posterior_v2.py`:
- Track residuals when modalities disagree
- Penalize models that can't explain disagreement
- Widen posterior entropy when residual is high
- Only narrow when disagreement is attributable to modeled nuisance

**Test coverage**: `tests/phase6a/test_scrna_is_not_ground_truth.py`
- Test 1: Disagreement scenario constructed (morphology vs scRNA)
- Test 2: Cell cycle confounder creates false recovery signal

---

## Empirical Validation

### Test 1: Cell Cycle Confounding Works

```bash
$ python tests/phase6a/test_scrna_is_not_ground_truth.py

Ground truth: ER stress = 0.6
Cycling cells:     HSPA5=256, DDIT3=83, ATF4=61
Non-cycling cells: HSPA5=373, DDIT3=124, ATF4=84
Cycling fraction: 80.31%

✓ Cycling cells show 30-35% suppressed stress markers
✓ Naive averaging would conclude "low stress" (FALSE)
✓ Correct interpretation: cycling confounds scRNA
```

### Test 2: Disagreement Scenario Exists

```bash
Morphology ER fold: 2.80  (strong ER signal)
scRNA ER markers: 119.23  (moderate)
scRNA oxidative: 72.71    (mild)
Ground truth ER: 0.85     (high)

✓ scRNA does not perfectly reveal ground truth
✓ Batch drift + cell cycle create realistic noise
✓ Planner must handle disagreement, not blindly trust scRNA
```

---

## Integration Checklist

- [x] Cost model added to YAML
- [x] Time cost applied in `biological_virtual.py`
- [x] Cell cycle confounder implemented in `transcriptomics.py`
- [x] Cycling metadata returned in assay results
- [x] Assay governance module created
- [x] Justification schema defined
- [x] Test coverage for confounding
- [x] Test coverage for disagreement
- [ ] **TODO**: Wire `allow_scrna_seq()` into planner
- [ ] **TODO**: Integrate disagreement handling into `mechanism_posterior_v2`
- [ ] **TODO**: Add cost ledger to track budget depletion
- [ ] **TODO**: Make drift risk scale with `time_cost_h`

---

## Design Decisions

### Why 4 hours for time_cost_h?

- Cell painting: ~2h (sample, fix, stain, image)
- scRNA-seq: ~4h (dissociate, count, load, sequence)
- 2× longer → 2× more drift exposure
- This is realistic and painful enough to matter

### Why 0.002 bits/$ for info gain threshold?

- $200 reagent cost → minimum 0.4 bits expected info gain
- ~0.4 bits ≈ resolving 1-2 mechanism ambiguities
- Calibrate to your reward scale; this is a starter heuristic

### Why cell cycle, not batch alone?

- Batch drift: "your measurement is noisy"
- Cell cycle: "your biology is confounded"
- Batch you can replicate away. Cell cycle you must **model**.
- Confounding forces the agent to think about biology, not just "sequence more."

---

## What This Prevents

### Before hardening:
- Agent defaults to scRNA whenever uncertain
- scRNA becomes "emotional support assay"
- No cost pressure → no strategic thinking
- Disagreement → "trust the fancier assay"

### After hardening:
- Agent must justify scRNA with failed alternatives
- Time cost increases drift risk (self-harm if used carelessly)
- Cell cycle confounder punishes naive interpretation
- Disagreement → widen posterior, don't launder

---

## How to Use This

### For planners:
1. Check `expected_information_gain` before requesting scRNA
2. Use `allow_scrna_seq()` gating function
3. Track cumulative cost and time in your ledger
4. Scale nuisance risk by `time_cost_h`

### For Bayesian updates:
1. Don't treat scRNA as ground truth
2. Model cell cycle as a latent confounder
3. Check residuals when modalities disagree
4. Widen posterior if residual is high and unexplained

### For evaluation:
1. Reward agents that use scRNA sparingly
2. Penalize agents that ignore cost
3. Test on scenarios where scRNA misleads (cell cycle, batch drift)
4. Measure posterior calibration on disagreement cases

---

## Philosophy Lock-In

This is the same "no laundering" spirit as your death accounting:
- You can't create cells from nothing
- You can't dissolve disagreement into confidence
- You can't use the fancier assay to override physics
- **Uncertainty is conserved unless you earn the reduction**

scRNA is not a cheat code. It's a measurement with its own failure modes. Use it when justified. Suffer the cost when you do. Learn from the confounders when you fail.

That's the whole point.

---

## References

- **Injection B boundary semantics**: `docs/INJECTION_B_BOUNDARY_SEMANTICS_COMPLETE.md`
- **Death accounting**: Conservation laws for cell count (no laundering)
- **Batch drift**: `biological_virtual.py:2324-2450`
- **Mechanism posterior**: `mechanism_posterior_v2.py` (integrate disagreement handling)

---

**Shipped**: 2025-12-20
**Next**: Wire gating into planner, integrate disagreement into Bayesian update
