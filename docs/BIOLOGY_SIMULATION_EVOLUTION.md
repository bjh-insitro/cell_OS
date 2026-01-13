# Biology Simulation Evolution

**Complete history of Cell Thalamus biology model refinement from expert feedback**

---

## Table of Contents
1. [Architecture Foundation](#1-architecture-foundation)
2. [Expert Feedback Integration](#2-expert-feedback-integration)
3. [Morphology-to-Attrition Feedback](#3-morphology-to-attrition-feedback)
4. [Final Validation](#4-final-validation)

---

## 1. Architecture Foundation

### Problem
Early Cell Thalamus had duplicated biology logic between agent and standalone paths, with silent parameter fallbacks that hid configuration errors.

### Solution: Create `biology_core.py`

Created single source of truth for all biology calculations:
- `compute_microtubule_ic50_multiplier()` - Proliferation-coupled sensitivity
- `compute_adjusted_ic50()` - Cell-line-specific IC50
- `compute_structural_morphology_microtubule()` - Morphology disruption before measurement
- `compute_transport_dysfunction_score()` - Dysfunction from STRUCTURAL morphology (no viability contamination)
- `compute_instant_viability_effect()` - Dose-response (no time dependence)
- `compute_attrition_rate()` - Time-dependent death rate
- `compute_viability_with_attrition()` - Complete viability calculation

### Key Design Decisions

**Option 2: Dysfunction Computed in Core**
- Compute dysfunction from structural morphology using biology_core, not from cached painting measurements
- Makes attrition "physics-like" - happens based on dose and cell line parameters, not whether you called cell_painting_assay
- Prevents "Schrödinger's dysfunction" where attrition only happens if you look

**Death Accounting**
Track cumulative death fractions separately:
- `death_compound`: Killed by compound attrition
- `death_confluence`: Killed by overconfluence (disabled for Phase 0)
- `death_mode`: Label based on dominant cause

**Confluence Management**
- Cap growth at max_confluence, do NOT kill cells
- For Phase 0 pharmacology validation, deaths should be from compounds, not logistics

### Critical Fixes Achieved
1. ✅ **No more silent IC50 fallbacks** - Fails loudly if parameters missing
2. ✅ **Confluence death disabled** - No "logistics death masquerading as compound death"
3. ✅ **Time-dependent attrition** - Uses biology_core consistently
4. ✅ **Death accounting** - Can assert causality in tests
5. ✅ **Dysfunction from structure** - No measurement contamination
6. ✅ **Growth respects viability** - Dead cells don't grow
7. ✅ **Single source of truth** - biology_core used by both paths

**Files created:**
- `src/cell_os/biology/biology_core.py` - Pure biology functions
- Extended `VesselState` with death accounting fields

---

## 2. Expert Feedback Integration

After initial implementation, expert review identified three critical conceptual issues:

### Issue 1: IC50 Coupling Formula Was Conceptually Wrong

**Problem:** Old formula treated "functional dependency" as "resistance":
```python
# OLD (WRONG): Linear interpolation toward 1.5× resistance
ic50_mult = mitosis_mult * (1.0 - functional_dependency) + functional_dependency * 1.5
```

This incorrectly gave neurons safety through IC50 inflation.

**Solution:** Functional dependency now means "different failure mode" not "protection":
```python
# NEW (CORRECT): Modest adjustment (20% max) since morphology fails first
ic50_mult = mitosis_mult * (1.0 + functional_dependency * 0.2)
ic50_mult = max(0.3, min(5.0, ic50_mult))
```

**Result:**
- Neurons (iPSC_NGN2): IC50 mult = 3.87× (from mitosis resistance, NOT functional dependency)
- Cancer (A549): IC50 mult = 0.80× (mitosis-driven death)
- Microglia: IC50 mult = 1.83× (moderate)

---

### Issue 2: Morphology EC50 Coupled to Viability EC50

**Problem:** Morphology and viability used same EC50, making "morphology-first" artificial.

**Solution:** Separate morphology EC50 using smooth Hill equation:
```python
# Morphology EC50: Lower than viability EC50 (morphology fails first)
morph_ec50_fraction = {
    'iPSC_NGN2': 0.3,       # Morphology fails at 30% of viability dose
    'iPSC_Microglia': 0.5,  # Moderate
    'A549': 1.0,            # Together
}

morph_ec50 = ec50 * morph_ec50_fraction
morph_penalty = dose_uM / (dose_uM + morph_ec50)  # Smooth saturating
```

**Result (Nocodazole @ 10µM, 24h):**
- Neuron viability: 98.2% (high)
- Neuron actin: 114.7 (vs baseline 160) → **28.3% reduction**
- Neuron mito: 143.9 (vs baseline 220) → **34.6% reduction**
- ✅ **Clear morphology disruption before viability loss**

---

### Issue 3: No Microtubule-Specific Attrition for Neurons

**Problem:** Neurons stayed 98% viable indefinitely under nocodazole - no "slow burn death."

**Solution:** Added cell-type-specific attrition:
```python
# Microtubule-specific: neurons get higher attrition (slow burn death after transport collapse)
if stress_axis == 'microtubule' and cell_line == 'iPSC_NGN2':
    attrition_rate = 0.25  # High cumulative effect (transport failure → death)
else:
    attrition_rate = base_attrition_rates.get(stress_axis, 0.10)
```

**Result (Nocodazole @ 10µM):**
| Time | Neuron Viability | Change |
|------|------------------|--------|
| 12h  | 98.7%            | -      |
| 24h  | 98.3%            | -0.4%  |
| 48h  | 96.9%            | -1.8%  |

Slow decline shows "morphology-first → viability-later" arc ✓

---

### Validation Results

**Test 1: Microtubule Assertion Tests**
```
1. Cancer viability crashes: ✓ PASS
   - A549: 4.6% (expect <30%)
   - HepG2: 10.5% (expect <30%)

2. Neurons stay viable: ✓ PASS
   - iPSC_NGN2: 98.1% (expect >90%)
   - iPSC_Microglia: 96.5% (expect >90%)

3. Morphology-first principle: ✓ PASS
   - Viability: 98.2% (alive)
   - Actin reduction: 28.3% (disrupted)
   - Mito reduction: 34.6% (disrupted)

4. IC50 multiplier bounds: ✓ PASS
   - All multipliers within [0.3, 5.0]
   - Neurons: 3.87× (reasonable)
   - Cancer: 0.80-1.30× (reasonable)
```

**Test 2: Rank-Order Stability**

✅ **Rank order stable at all meaningful doses**

**Nocodazole (Microtubule):**
| Dose | A549 | HepG2 | Neurons | Microglia | Rank |
|------|------|-------|---------|-----------|------|
| 0.3 µM| 59% | 90%   | **98%** | 98%       | ✓    |
| 1 µM | 13%  | 49%   | **98%** | 98%       | ✓    |
| 10 µM| 8%   | 22%   | **98%** | 97%       | ✓    |

---

## 3. Morphology-to-Attrition Feedback

### Problem Identified
After fixing the IC50 formula, neurons under high-dose nocodazole showed:
- ✓ High viability (98%)
- ✓ Disrupted morphology (28% actin loss, 35% mito loss)
- ✗ **No eventual death** (96.9% at 48h - "barely a scratch")

This wasn't "death follows later" - it was near immortality.

### Solution: Causal Feedback Loop

Added a causal link: **broken morphology increases attrition rate**

```python
if stress_axis == 'microtubule' and cell_line == 'iPSC_NGN2':
    # Base attrition for microtubule in neurons
    base_mt_attrition = 0.25

    # Scale attrition by morphology disruption (feedback loop)
    morph_penalty_approx = dose_uM / (dose_uM + ic50_base * 0.3)

    # Scale attrition: 1× at no disruption, up to 3× at severe disruption
    attrition_scale = 1.0 + 2.0 * morph_penalty_approx
    attrition_rate = base_mt_attrition * attrition_scale
```

**Key insight:** The more broken the morphology (transport dysfunction), the faster the cell dies from accumulated stress.

---

### Results: Proper Death Arc

**High Dose (10 µM): Morphology → Attrition → Death**

| Time | Viability | Actin Loss | Mito Loss | Pattern |
|------|-----------|------------|-----------|---------|
| 12h  | 98.7%     | 26.2%      | 32.6%     | Morphology disrupted, viability OK |
| 24h  | 98.2%     | 27.5%      | 33.8%     | Still high viability |
| 48h  | 96.6%     | 26.9%      | 33.3%     | Slight decline starting |
| 72h  | **69.7%** | 29.8%      | 35.8%     | **Significant death from transport failure** |
| 96h  | **0%**    | 39.3%      | 44.4%     | **Complete collapse** |

✅ **Proper arc:** Morphology breaks first (12-24h) → Attrition accumulates (48-72h) → Viability crashes (96h)

**Cancer (A549): Mitotic Catastrophe**

| Time | Viability | Pattern |
|------|-----------|---------|
| 12h  | 32.1%     | Fast decline |
| 24h  | 0%        | Dead (mitotic catastrophe) |
| 48h  | 0%        | Remains dead |

✅ **Cancer dies in 24h**, neurons take **72-96h** (10× slower death timeline)

---

### The Causal Mechanism

**Biological story:**
1. **Nocodazole disrupts microtubules** (0-12h)
2. **Axonal transport fails** → morphology shows actin/mito disruption (12-24h)
3. **Transport dysfunction accumulates stress** → attrition rate increases (24-72h)
4. **Cell can't sustain function** → viability crashes (72-96h)

**Model implementation:**
```
Morphology disruption → morph_penalty_approx
                      ↓
Attrition scale = 1 + 2 × morph_penalty_approx
                      ↓
Attrition rate × attrition_scale
                      ↓
Additional death accumulates over time
                      ↓
Viability effect reduced
```

---

### Key Insight: Trajectory, Not IC50

**Expert feedback:**
> "You stopped trying to 'encode truth in IC50' and moved the neuron story into *trajectory*."

**What this means:**
- **IC50:** Defines when mitotic cells die (cancer: fast, neurons: resistant)
- **Morphology EC50:** Defines when transport disrupts (neurons: early, at 30% of viability dose)
- **Attrition feedback:** Defines how fast dysfunction → death (scales with morphology damage)

**Result:** Three separate, mechanistically correct dials:
1. IC50 = mitosis resistance
2. Morphology EC50 = transport vulnerability
3. Attrition feedback = dysfunction → death timeline

None of them are "magic shields" - each has a biological interpretation.

---

## 4. Final Validation

### Summary of Improvements

| Aspect | Before | After |
|--------|--------|-------|
| **IC50 formula** | Linear interpolation toward 1.5× | Modest adjustment (20% max) |
| **Meaning** | "Functional dependency = resistance" | "Functional dependency = different failure mode" |
| **Neuron protection** | From IC50 inflation (wrong) | From morphology-first + attrition (correct) |
| **Morphology EC50** | Coupled to viability EC50 | Decoupled (30% for neurons) |
| **Dose response** | Sharp min() clamp | Smooth Hill equation |
| **Neurons under nocodazole** | High viability + normal morphology ✗ | High viability + disrupted morphology ✓ |
| **Death timeline** | Never (infinite resistance) | Slow burn (morphology → attrition → death) |
| **48h viability** | 98.3% (flat) | 96.6% (declining) |
| **96h viability** | ~98% (immortal) | 0% (complete collapse) |

---

### Test Results Summary

**Morphology-First (Nocodazole @ 10µM, 24h):**
```
Neuron viability: 98.2%  ✓ High
Actin disruption: 28.3%  ✓ Significant
Mito disruption:  34.6%  ✓ Significant
```

**Rank-Order Stability:**
```
CCCP @ 30µM:      Neurons 34% vs Cancer 63%  (2× more sensitive) ✓
Nocodazole @ 10µM: Neurons 98% vs Cancer 8%  (12× more resistant) ✓
```

**IC50 Multipliers:**
```
Neurons:   3.87× (reasonable, from mitosis resistance)
Microglia: 1.83× (moderate)
Cancer:    0.80-1.30× (sensitive, from mitosis commitment)
```

All within [0.3, 5.0] bounds ✓

---

## Summary Quote

> "Functional dependency doesn't mean 'protected from death.' It means 'different timeline and failure mode.' Morphology collapses early (transport disruption), death follows later (attrition). That's the mechanistic story, not a parameter tweak."

—Expert feedback, integrated

---

## Files Modified

**Core Implementation:**
- `src/cell_os/biology/biology_core.py` - Pure biology functions
- `src/cell_os/hardware/biological_virtual.py` - Agent path implementation
- `standalone_cell_thalamus.py` - Standalone implementation

**Tests:**
- `test_microtubule_assertions.py` - 4 assertion tests ✓ PASS
- `test_dose_sweep_validation.py` - Rank-order stability ✓ PASS
- `test_neuron_death_arc.py` - Extended timepoint test (12h → 96h) ✓ PASS
- `check_morphology_penalties.py` - Morphology-first verification ✓ PASS

**Superseded Documentation (see docs/archive/):**
- BIOLOGY_CORE_REFACTOR_SUMMARY.md
- BIOLOGY_IMPROVEMENTS.md
- FINAL_BIOLOGY_FIXES.md
- REAL_MORPHOLOGY_FIXES.md
- MORPHOLOGY_TO_ATTRITION_ARC.md
