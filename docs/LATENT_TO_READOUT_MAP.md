# Latent-to-Readout Map

This document defines the ontology for latent biological states and their observable readouts in the BiologicalVirtualMachine.

## Design Principles

1. **Latents are hidden states** - Not directly observable, inferred from readouts
2. **Morphology-first, death-later** - Readouts shift early, death hazard kicks in later
3. **Multiple sensors per latent** - Each latent should affect 2+ readouts for triangulation
4. **No one-to-one mapping** - Prevents "latent is just readout with extra steps"

## Latent States

### ER Stress (`vessel.er_stress`, 0-1)

**Induction:**
- Compounds with `stress_axis="er_stress"` or `stress_axis="proteostasis"`
- Dynamics: `dS/dt = k_on * f(dose) * (1-S) - k_off * S`
- Timescale: 12-24h to saturation

**Readouts:**
1. **ER morphology channel** (Cell Painting)
   - Effect: `morph['er'] *= (1.0 + 0.5 * er_stress)`
   - Early signal: 31% increase at 12h
   - Location: `cell_painting_assay()`, line ~1612

2. **UPR marker** (scalar biochemistry)
   - Effect: `upr_marker = 100 * (1.0 + 2.0 * er_stress)`
   - Baseline: 100, saturates at 300
   - Location: `atp_viability_assay()`, line ~1866

**Death hazard:**
- Threshold: θ = 0.7 (70% stress level)
- Function: `h_max * sigmoid((S - θ)/width)`
- Max rate: 0.03 deaths/hour at full stress
- Bucket: `vessel.death_er_stress`

---

## Death Mechanisms (No Latent State)

### Nutrient Depletion

**State:** `vessel.media_glucose_mM`, `vessel.media_glutamine_mM`

**Readouts:**
- None (nutrients not directly measured in current assays)
- Could add: glucose/glutamine sensor readouts if needed

**Death hazard:**
- Function: Linear ramp below threshold
- Glucose threshold: 5.0 mM
- Glutamine threshold: 1.0 mM
- Max rate: 0.05 deaths/hour at full depletion
- Bucket: `vessel.death_starvation`

### Mitotic Catastrophe

**No latent state** - Instantaneous function of:
- Doubling time (proliferation rate)
- Compound dose (microtubule stress)

**Death hazard:**
- Function: `hazard = (ln(2)/doubling_time) * (dose/(dose+IC50))`
- Only active for `stress_axis="microtubule"` compounds
- Spares quiescent cells (72h doubling time → 4× less death than 18h)
- Bucket: `vessel.death_mitotic_catastrophe`

### Compound Attrition

**No latent state** - Direct dose-response function

**Readouts:**
- Transport dysfunction score (computed from morphology)
- Location: `cell_painting_assay()`, line ~1625

**Death hazard:**
- Function: `biology_core.compute_attrition_rate()`
- Depends on: dose, IC50, transport dysfunction, time since treatment
- Bucket: `vessel.death_compound`

---

## Morphology Features (Cell Painting)

Available channels in `morph` dict:
- `er`: Endoplasmic reticulum
- `mito`: Mitochondria
- `nucleus`: Nuclear morphology
- `actin`: Cytoskeleton
- `rna`: Translation sites

Current latent → morphology mappings:
- `er_stress` → `morph['er']` (already implemented)
- (Next: `mito_dysfunction` → `morph['mito']`)

---

## Scalar Readouts (Biochemistry)

Available in `atp_viability_assay()`:
- `ldh_signal`: Membrane integrity (inversely proportional to viability)
- `upr_marker`: ER stress proxy (100 baseline → 300 at stress=1.0)
- (Future: Could add ATP, ROS, caspase markers)

Current latent → scalar mappings:
- `er_stress` → `upr_marker` (already implemented)
- (Next: `mito_dysfunction` → ATP signal? ROS marker?)

---

## Conservation Laws

**Death accounting:**
```
Σ (death_compound + death_starvation + death_mitotic_catastrophe +
   death_er_stress + death_confluence + death_unknown) = 1 - viability ± ε
```

Enforced in `_update_death_mode()` with ε = 1e-5.

**Competing risks:**
All death mechanisms propose hazards (deaths/hour), combined via:
```
survival_total = exp(-Σ hazard_i * hours)
```

Realized death allocated proportionally to hazard contribution.

### Mito Dysfunction (`vessel.mito_dysfunction`, 0-1)

**Induction:**
- Compounds with `stress_axis="mitochondrial"` (CCCP, oligomycin, rotenone)
- Dynamics: `dS/dt = k_on * f(dose) * (1-S) - k_off * S`
- Timescale: 12-24h to saturation (same as ER stress)

**Readouts:**
1. **Mito morphology channel** (Cell Painting)
   - Effect: `morph['mito'] *= max(0.1, 1.0 - 0.4 * mito_dysfunction)`
   - Contrast with ER: Mito **decreases** (ER increases)
   - Early signal: 27% decrease at 12h
   - Location: `cell_painting_assay()`, line ~1721

2. **ATP signal** (scalar biochemistry)
   - Effect: `atp_signal = 100 * max(0.3, 1.0 - 0.7 * mito_dysfunction)`
   - Baseline: 100, drops to ~30 at full dysfunction
   - Location: `atp_viability_assay()`, line ~1988

**Death hazard:**
- Threshold: θ = 0.6 (60% dysfunction level, lower than ER)
- Function: `h_max * sigmoid((S - θ)/width)`
- Max rate: 0.05 deaths/hour at full dysfunction (nastier than ER's 0.03)
- Bucket: `vessel.death_mito_dysfunction`

**Orthogonality:**
- ER stress and mito dysfunction are independent (different stress axes)
- Test: `test_mito_dysfunction_orthogonal_to_er_stress()` verifies separation

---

## Future Latents (Not Yet Implemented)

### Transport Dysfunction (Proposed Phase 2)

Only add this AFTER verifying ER/mito identifiability.

**Latent state:** `vessel.transport_dysfunction` (0-1)

**Induction:**
- Compounds with `stress_axis="microtubule"` (paclitaxel, nocodazole)
- Second-order coupling (touches multiple channels)

**Readouts:**
1. Morphology: `morph['actin']` (primary), mild `morph['mito']` (secondary)
2. Modulates mitotic catastrophe hazard

**Design constraint:** Don't smear into mito dysfunction—keep causal graph legible.
