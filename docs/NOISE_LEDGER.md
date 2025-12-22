# Noise Ledger: Formal Contracts for Reality Injections

**Purpose:** Explicit specification of each noise source's scope, signature, and defeat condition.

**Hierarchy:** Three levels of latent factors generate the observed noise:
- **Run-level** (day/batch): Shared across all plates in session
- **Plate-level**: Shared within plate, varies between plates
- **Well-level**: Independent per well

---

## TIER 1: RUN-LEVEL LATENT FACTORS

### RunContext: Correlated "Cursed Day" Factors

**Scope:** All plates in a single run/batch session

**Latent Factor:** `cursed_latent` ~ N(0,1), generates:
- `incubator_shift` ∈ [-0.3, +0.3]: Growth rate, stress sensitivity (biological)
- `reagent_lot_shift[channel]` ∈ [-0.15, +0.15]: Channel-specific intensity biases (ER, Mito, DNA, Actin, RNA)
- `scalar_reagent_lot_shift[assay]` ∈ [-0.15, +0.15]: Biochemical assay biases (ATP, LDH, UPR, Trafficking)
- `instrument_shift` ∈ [-0.2, +0.2]: Illumination, focus, noise floor

**Signature:**
- Correlated failure across plates (correlation = 0.5)
- Channel-specific biases (ER high + Mito low = bad reagent lot)
- All plates from same day cluster together
- Different days cluster separately

**Defeat Condition:**
- **Calibration plate per run**: Sentinels + anchors measure day-specific bias
- **Batch normalization**: Run-level centering (requires ≥2 plates per run)
- **Longitudinal QC**: Track run-to-run drift with control plates

**Currently Active:** ✅ Fully implemented in RunContext

---

##

 TIER 2: PLATE-LEVEL FACTORS

### A. Volume Evaporation Field

**Scope:** Per-plate spatial field, affects all wells differently

**Parameters:**
- `evap_rate_center`: 0.2 µL/h baseline
- `evap_field[row, col]`: Position-dependent multiplier
  - Edge wells: 3-5× center
  - Corner wells: 8-10× center
  - Center wells: 1× baseline

**Affects:**
- Volume (direct): Edge wells lose ~20-40% volume over 48h
- Concentration (indirect): Dose creeps up as volume drops
- Osmolality (indirect): Hyperosmotic stress at edges
- Nutrients (indirect): Starvation accelerates

**Signature:**
- Spatial gradient (edge > center)
- Time-dependent (worse at later timepoints)
- Dose-agnostic (affects vehicle and treated equally)
- **NOT biology**: This is physics

**Defeat Condition:**
- **Spatial randomization**: Interleave treatments to break edge confound
- **Lid + humidification**: Reduces evaporation rate
- **Sentinel tiles**: Replicate tiles detect spatial bias
- **Volume normalization**: Measure final volume, correct concentration

**Currently Active:** ✅ Implemented

---

### B. Cursed Plate (Rare Tail Events)

**Scope:** Per-plate catastrophic failure (Bernoulli, p ≈ 0.01-0.05)

**Curse Types:**
- Contamination (bacteria/fungi)
- Instrument miscalibration (systematic volume error)
- Plate manufacturing defect (cracks, uneven coating)
- Incubator malfunction (temperature excursion)
- Reagent degradation (expired media)

**Affects:**
- Entire plate (not well-specific)
- Catastrophic (not gradual)
- Often undetectable until endpoint

**Signature:**
- Rare (1-5% of plates)
- All-or-nothing (whole plate fails)
- Failure mode specific (contamination ≠ miscalibration)

**Defeat Condition:**
- **QC gates**: Plate-level viability/confluence check before endpoint
- **Sentinel wells**: Background controls detect contamination
- **Replicate plates**: Technical replicates reveal systematic failures
- **CANNOT DEFEAT COMPLETELY**: This is reality's tail

**Currently Active:** ✅ Implemented

**Meta-Note:** This is NOT a "noise source" - it's a **failure mode**. Should it stay in ledger or move to QC?

---

### C. Coating Quality Variation

**Scope:** Per-well, sampled at plate manufacturing

**Parameters:**
- `coating_efficiency` ~ Beta(α=18, β=2) → mean=0.9, range=[0.7, 1.0]
- `degradation_rate`: Old plates worse (not implemented yet)

**Affects:**
- Seeding efficiency: Poor coating → fewer cells attach
- Growth rate: Cells sense bad substrate → slower growth
- Baseline stress: Bad surface → low-grade stress

**Signature:**
- Well-to-well variation (not spatial)
- Systematic (same well always poor)
- Affects cell count, not morphology directly

**Defeat Condition:**
- **Normalize by cell count**: Per-well morphology/cell count ratio
- **Replicate wells**: Average over technical replicates
- **Cannot defeat without imaging**: Count cells to measure coating quality

**Currently Active:** ✅ Implemented

**Overlap Warning:** Coating affects **seeding**, evaporation affects **nutrients**. Keep separate.

---

## TIER 3: WELL-LEVEL & OPERATION-LEVEL FACTORS

### D. Pipetting Variance

**Scope:** Per-dispense operation (systematic + random)

**Parameters:**
- `systematic_error`: ±1% per instrument (calibration drift)
- `per_dispense_noise`: ±0.5% per operation (shot noise)

**Affects:**
- Volume delivered: 200 µL → 198-202 µL
- Dose accuracy: 1.0 µM → 0.99-1.01 µM
- Nutrient concentration: Media feeds vary well-to-well

**Signature:**
- Technical replicate variation (not biological)
- Dose-dependent (larger volumes = larger absolute error)
- Instrument-specific (same robot = same bias)

**Defeat Condition:**
- **Gravimetric validation**: Weigh plates to measure actual volumes
- **Standard curve per plate**: Dose-response anchors calibrate pipetting
- **Cannot fully defeat**: Robots have spec limits

**Currently Active:** ✅ Implemented

---

### E. Mixing Gradients (Transient)

**Scope:** Per-well, post-dispense (decays with τ ≈ 5-10 min)

**Parameters:**
- `gradient_magnitude`: ±20% Z-axis concentration variation at t=0
- `mixing_tau`: 5-10 min decay constant

**Affects:**
- Immediate post-treatment: Cells at bottom ≠ cells at top
- False heterogeneity: Looks like subpopulations (it's mixing)
- Decays exponentially → uniform after ~30 min

**Signature:**
- **Timing-dependent**: Strong at t=0-10min, gone by t=30min
- Z-axis only (lateral mixing instant)
- Compound-specific (DMSO sinks, hydrophobic aggregates)

**Defeat Condition:**
- **Wait 30 minutes** post-treatment before measurement
- **Shaking step**: Orbital shaker after dispense
- **Cannot defeat in high-throughput**: No time to mix properly

**Currently Active:** ✅ Implemented

**Question:** Does this matter for 48h endpoint? Mixing completes within 1h, so negligible at t=48h.

---

### F. Measurement Back-Action

**Scope:** Per-imaging event (cumulative)

**Parameters:**
- `cumulative_imaging_stress` ∈ [0,1]: Photo-bleaching + phototoxicity
- `cumulative_handling_stress` ∈ [0,1]: Mechanical stress from washes/feeds

**Affects:**
- Live imaging: ROS generation, phototoxicity
- Repeated imaging: Signal loss (bleaching) + cell stress
- Wash operations: Shear stress, trajectory reset
- scRNA sampling: Cells removed (destructive)

**Signature:**
- Time-dependent (cumulative)
- Measurement-dependent (more imaging = more stress)
- Observable: Viability drops with imaging frequency

**Defeat Condition:**
- **Minimize imaging frequency**: Only measure when needed
- **Low-light imaging**: Reduce excitation power
- **Parallel arms**: Image vs non-imaged controls
- **Endpoint assays**: Avoids cumulative stress

**Currently Active:** ✅ Implemented

**Note:** Only matters for live-cell imaging. Endpoint Cell Painting = single snapshot (no cumulative effect).

---

## TIER 4: BIOLOGICAL REALITY (NOT "NOISE")

These are **not noise** - they're **biology being hard**. Moving out of noise ledger.

### G. Stress Memory

**What it is:** Cells remember past insults. Prior stress → altered response.

**Why it's not noise:** It's biology. The system has memory. This is **state**, not **noise**.

**Move to:** Biological State Complexity

---

### H. Lumpy Time (Commitment Points)

**What it is:** Discrete state transitions (healthy → apoptotic). Not gradual.

**Why it's not noise:** Phase transitions are real. Biology is discrete, not smooth.

**Move to:** Biological State Complexity

---

### I. Death Modes

**What it is:** Apoptosis ≠ necrosis ≠ autophagy. Different signatures.

**Why it's not noise:** Different death pathways are biology, not artifacts.

**Move to:** Biological State Complexity

---

### J. Assay Deception

**What it is:** ATP ≠ viability (glycolysis compensates). Assays lie.

**Why it's not noise:** This is **measurement vs ground truth mismatch**. It's a property of the assay, not a noise source.

**Rename to:** "Assay-Biology Decoupling" or "Observable vs Latent States"

**Move to:** Measurement System Design

---

### K. Coalition Dynamics

**What it is:** Subpopulations interact. Minority can dominate.

**Why it's not noise:** Heterogeneity + paracrine signaling = biology.

**Move to:** Biological State Complexity

---

### L. Identifiability Limits

**What it is:** Structural non-identifiability. Different mechanisms → same output.

**Why it's not noise:** This is a **property of the model**, not a noise source.

**Move to:** Meta-Constraint (not an injection)

---

## SUMMARY: CLEANED NOISE LEDGER

### Run-Level (Correlated)
1. **RunContext**: Cursed day latent → incubator/reagent/instrument shifts

### Plate-Level (Spatial)
2. **Volume Evaporation**: Edge wells lose volume → concentration drift
3. **Cursed Plate**: Rare catastrophic failures (contamination, instrument failure)
4. **Coating Quality**: Per-well surface treatment variation

### Well/Operation-Level (Independent)
5. **Pipetting Variance**: ±1-2% volume error per dispense
6. **Mixing Gradients**: Transient ±20% Z-axis concentration variation (τ=5-10min)
7. **Measurement Back-Action**: Cumulative imaging stress (phototoxicity, bleaching)

### Cell Painting Specific (Measurement)
8. **Stain Scale**: ±10% antibody/dye concentration variation
9. **Focus Offset**: ±2-5 µm defocus → attenuation + noise inflation
10. **Fixation Timing**: ±5-10 min fixation offset → channel-specific biases
11. **Shot Noise**: ~10% CV Poisson-like per-pixel noise

### Missing (Add These)
12. **Segmentation Failure**: Over/under-segmentation, debris, clumping (TODO)
13. **Plate Map Error**: Swapped reagents, column shift, off-by-one (TODO)
14. **Carryover Contamination**: Tip reuse → trace amounts in wrong wells (TODO)

---

## ABLATION TEST PLAN

For each noise source, measure:
1. **Mechanism posterior entropy**: Does this noise source confuse mechanism inference?
2. **False positive rate**: Does it create false hits?
3. **Calibration curve shift**: Does it shift dose-response?

**Method:**
- Run same plate design with each noise toggled on/off
- Measure variance explained by each source
- Identify which sources actually matter (vs museum pieces)

**Hypothesis:** Top 5 sources will explain 80% of variance. Rest are decorative.

---

## NEXT STEPS

1. **Implement segmentation failure module** (CRITICAL - this is the biggest real-world pain)
2. **Implement plate map error module** (rare but catastrophic)
3. **Run ablation harness** (measure which noise sources matter)
4. **Refactor "biology" modules** out of "noise" ledger
5. **Hierarchical latent factor model**: Reduce 12 sources → 3-4 shared latents

---

## OPEN QUESTIONS

1. **Cell density**: Is this a noise source or a biological state? It's both - how do we model?
2. **Temporal drift**: Within-run drift (early wells vs late wells) - where does it live?
3. **Batch effects**: RunContext handles day-to-day. What about week-to-week, operator-to-operator?
4. **Carryover**: How much matters? Is it worth modeling explicitly vs folding into pipetting variance?

---

**Meta:** This ledger is a **contract**. Each noise source must answer:
- **Scope**: What granularity? (run/plate/well/operation)
- **Signature**: What pattern would a smart analyst detect?
- **Defeat**: What experimental design neutralizes it?

If we can't answer all three, it doesn't belong in the ledger yet.
