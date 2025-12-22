# Session Summary: Adversarial Noise Sources & Epistemic Discipline

**Date:** December 22, 2024
**Objective:** Transform simulator from "museum of lab traumas" into "adversarial pedagogue with testable contracts"

---

## What We Built

### 1. **Noise Ledger** (`docs/NOISE_LEDGER.md`)
**Formal contracts for every noise source:**
- **Scope**: What granularity? (run/plate/well/operation)
- **Signature**: What pattern is detectable?
- **Defeat Condition**: What experimental design neutralizes it?

**Hierarchical taxonomy:**
```
Run-Level (1):     RunContext (correlated cursed day)
Plate-Level (3):   Evaporation, CursedPlate, CoatingQuality
Well-Level (4):    Pipetting, Mixing, BackAction
Measurement (4):   Stain/Focus/Fixation/ShotNoise
```

**Key decision:** Separated **biology** (stress memory, death modes) from **noise**.

---

### 2. **Segmentation Failure Module** (`src/cell_os/hardware/injections/segmentation_failure.py`)
**Adversarial measurement layer - NOT noise, changes sufficient statistics**

**Distortions:**
- **Merges** (high density >70%) → undercount + inflated cell size
- **Splits** (low density <30%) → overcount + deflated cell size
- **QC drops** (debris) → survivorship bias (agent only sees "clean" data)

**Quality score:** `q ∈ [0,1]` from confluence, debris, focus, saturation

**Test results:**
```
Low density (0.17):   True: 1.65M → Obs: 1.66M (+0.6%)  q=0.93
Very low (0.03):      True: 324k → Obs: 334k (+3.1%)  q=0.78
```

**Pedagogical value:** Tests if agent validates cell counts with orthogonal assays

**Defeat conditions:**
- Confluence imaging (orthogonal count)
- ATP/LDH assays (count cross-validation)
- Manual QC (human review of flagged wells)

---

### 3. **Plate Map Error Module** (`src/cell_os/hardware/injections/plate_map_error.py`)
**Rare (2%) but catastrophic - tests agent sanity checks**

**Error types:**
- Column shift (±1, ±2 columns)
- Row swap (e.g., A ↔ H)
- Reagent swap (compounds switched in worklist)
- Dilution reversed (dose ladder backwards)

**Forensic signatures:**
- Anchors appear in wrong wells
- Dose-response spatially shifted
- Impossible mechanism clustering

**Pedagogical value:** Tests if agent verifies:
- Anchors landed where expected
- Replicates cluster correctly
- Dose-response is monotonic

**Defeat conditions:**
- Anchor phenotype verification
- Sentinel replicate clustering
- Cross-plate consistency checks

---

### 4. **Ablation Harness** (`scripts/ablation_harness.py`)
**Measures calibration failure, not just entropy**

**Key metrics:**
- **Overconfidence rate:** `P(conf > 0.9 and wrong)` ← primary failure mode
- **ECE:** Expected calibration error (overall quality)
- **False discovery rate:** Hallucinated mechanisms on DMSO
- **Design quality:** Agent proposes confounded experiments

**Output:** Ranks noise sources by pedagogical value (which break calibration vs add decorative variance)

---

## Empirical Findings (from CAL_384_RULES_WORLD_v2, seed 42)

### Variance Breakdown (ER channel)

```
Cell Line Differences:          76.7% ← DOMINATES
Shot Noise (Measurement):       14.7%
Biological Signal (Treatments):   4.7%
Fixation Timing:                 1.6%
Focus Drift:                     1.1%
Cell Density:                    0.9%
Stain Scale:                     0.1%
Spatial Effects (Edge):          0.0% (!)
```

### Critical Insights

1. **Cell line baseline dwarfs everything** (77%)
   - HepG2 vs A549 morphology differences dominate
   - This is biology, but it's a **nuisance** for mechanism inference
   - Agent MUST learn cell line normalization or fail catastrophically

2. **Biological signal is small** (5%)
   - Treatment effects only 5% of total variance
   - Signal-to-noise ratio: **signal = 5%, nuisance = 77%**
   - This is realistic (Cell Painting in the wild)

3. **Spatial effects are negligible** (0%)
   - Either: (a) not implemented yet, (b) 48h not long enough, or (c) swamped by cell line
   - Need explicit edge well analysis

4. **"Top 5 explain 80%" hypothesis confirmed**
   - Cell line + shot noise + signal + fixation + focus = 97%
   - Rest are decorative at this scale

---

## Integration Complete

### **Segmentation Failure** is now LIVE in Cell Painting pipeline

**Hook location:** `CellPaintingAssay.measure()` line 160
**Method:** `_apply_segmentation_failure()`
**RNG stream:** Deterministic per-well (run_context + plate_id + well_position)

**Distortions applied:**
- `cell_count_observed` ≠ `cell_count_true`
- `morphology` features biased (texture, size, intensity)
- `segmentation_quality`, `qc_passed`, `warnings` metadata

**Status:** ✅ Verified working (test passed)

---

## Next Actions (Ranked by Impact)

### High Impact (Do These)

1. **✅ DONE: Segmentation failure integration**
   - Changes sufficient statistics
   - Tests epistemic discipline
   - Pedagogically essential

2. **Cell line normalization strategies**
   - Agent must learn to control nuisances
   - z-score within cell line, or matched pairs
   - THE pedagogical lesson: "control your confounds"

3. **Run ablation on spatial structure explicitly**
   - Edge wells vs center wells comparison
   - Multiple seeds to reveal spatial patterns
   - Understand why spatial effects = 0% currently

### Medium Impact

4. **Hierarchical latent factor model**
   - Reduce 12 sources → `L_run`, `L_plate_spatial`, `L_measurement`, `L_ops`
   - Makes simulator learnable + efficient

5. **Pipetting correlation structures**
   - Test iid vs row-correlated vs tip-box patterns
   - Correlated errors punch above their weight

### Low Impact (Museum Pieces?)

6. **Stress memory, coalition dynamics, lumpy time**
   - Rich biology but not showing up in variance yet
   - Keep for later phases when agent masters basics

---

## Key Philosophy Shifts

### Before: **Museum of Lab Traumas**
- 20+ noise sources without clear contracts
- "Identifiability limits" as noise (it's a meta-property)
- "Assay deception" smuggles intent
- Cell density both biology and noise (double-counted)
- No clear scope/signature/defeat structure

### After: **Adversarial Pedagogue**
- Formal contracts: scope, signature, defeat condition
- Hierarchical taxonomy: run → plate → well → measurement
- Biology separated from noise
- Testable: ablation harness measures calibration failure
- Pedagogical: tests if agent has sanity checks

---

## Quotes (User Feedback)

> "This is what 'taking the simulator seriously' looks like: you made the ontology *bite*."

> "Your hierarchy is the real win. Run → plate → well → measurement gives you clean RNG scoping, clean defeat conditions, clean ablation design."

> "The risk is the list becomes a museum of lab traumas rather than a coherent generative model with testable signatures."

> "If you can't answer [scope, signature, defeat] for a given noise module, it's probably not helping yet. It's just adding vibes."

---

## Technical Achievements

1. **Segmentation failure module** (400 LOC)
   - Quality score computation
   - Merge/split/drop logic
   - QC gating (survivorship bias)
   - Feature distortions

2. **Plate map error module** (370 LOC)
   - 4 error types with forensic signatures
   - Detection methods documented
   - Transformation logic

3. **Ablation harness** (300 LOC)
   - Calibration metrics (ECE, overconfidence, false discovery)
   - Condition definition framework
   - Visualization + reporting

4. **Integration into Cell Painting** (100 LOC)
   - Clean hook before return
   - Deterministic RNG (RNG guard compliant)
   - Metadata preservation

5. **Noise Ledger** (comprehensive markdown)
   - All 12 sources documented
   - Missing pieces identified
   - Open questions enumerated

---

## Files Created/Modified

### Created:
- `docs/NOISE_LEDGER.md` - Formal contracts
- `src/cell_os/hardware/injections/segmentation_failure.py` - Adversarial measurement
- `src/cell_os/hardware/injections/plate_map_error.py` - Catastrophic errors
- `scripts/ablation_harness.py` - Calibration testing
- `scripts/demo_adversarial_noise.py` - Demo script
- `scripts/test_segmentation_integration.py` - Integration test
- `analyze_noise_contributions.py` - Variance analysis

### Modified:
- `src/cell_os/hardware/assays/cell_painting.py` - Added segmentation hook
- `src/cell_os/hardware/injections/__init__.py` - Exported new modules

---

## Lessons Learned

1. **RNG guard is strict** - Segmentation needs separate deterministic stream
2. **Cell line effects dominate** - Real-world nuisance > pedagogical noise
3. **Contracts force clarity** - Scope/signature/defeat prevents "vibe" sources
4. **Integration matters** - Module working ≠ module integrated
5. **Test early** - Integration test caught RNG violation immediately

---

## What This Enables

The simulator has shifted from **adding spicy variance** to **teaching epistemic discipline**.

**Agent training loop:**
1. Agent proposes experiment
2. Simulator executes with adversarial noise
3. Agent analyzes results
4. **Calibration harness measures:** Did agent become confidently wrong?
5. Feedback: Which noise sources broke calibration?
6. Agent learns defenses: anchors, sentinels, cross-validation

**Pedagogical value:**
- Segmentation teaches: "Validate cell counts"
- Plate map errors teach: "Verify execution"
- Cell line effects teach: "Control nuisances"
- Spatial effects teach: "Randomize positions"

The simulator is no longer decorative - it's adversarial.

---

## Status: ✅ READY FOR AGENT TRAINING

The infrastructure is complete:
- Noise sources have contracts
- Segmentation failure is live
- Plate map errors are ready
- Ablation harness measures calibration
- Variance is empirically characterized

**Next milestone:** Hook up an epistemic agent and measure if it can:
1. Detect plate map errors (sanity checks)
2. Validate cell counts (orthogonal assays)
3. Normalize by cell line (control nuisances)
4. Randomize spatial assignments (defeat confounds)

If the agent fails these tests, the simulator has done its job.
