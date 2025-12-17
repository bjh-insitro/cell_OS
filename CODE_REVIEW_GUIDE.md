# Cell Line Simulation Logic - Code Review Guide

## Overview
This guide identifies the key code files that implement neuron (iPSC_NGN2) and microglia (iPSC_Microglia) simulation logic for cross-validation with ChatGPT.

## Key Files for Review

### 1. **Standalone Simulation Script** (Primary Implementation)
**File:** `/Users/bjh/cell_OS/standalone_cell_thalamus.py`

**Lines to Review:**
- **Lines 420-448:** Compound parameter definitions (EC50, hill slope, stress axis mapping)
- **Lines 455-464:** Cell-line-specific baseline morphology (neurons: high mito/actin, microglia: high ER/RNA)
- **Lines 643-650:** Proliferation index (neurons: 0.1 post-mitotic, microglia: 0.6 moderate)
- **Lines 652-658:** LDH baseline (neurons: 70k high ATP, microglia: 65k)
- **Lines 660-683:** **CRITICAL: Cell-line-specific IC50 modifiers** (captures biological differences)
  - Neurons: 0.4× H2O2, 0.3× CCCP (extremely sensitive), 2.0-2.5× microtubule (resistant)
  - Microglia: 1.5× H2O2 (resistant, produce ROS), 0.6× MG132 (sensitive, high protein turnover)

**Simulation Logic:**
- **Lines 688-924:** `simulate_well()` function
  - **Lines 692-810:** Morphology calculation (adaptive vs damage model)
  - **Lines 812-904:** LDH cytotoxicity calculation
  - **Lines 713-724:** IC50 adjustment logic:
```python
if stress_axis == 'microtubule':
    prolif = PROLIF_INDEX.get(well.cell_line, 1.0)
    ic50_mult = 1.0 / max(prolif, 1e-9)  # Lower prolif = higher IC50 (resistant)
    hill_v = hill_slope * (0.8 + 0.4 * prolif)
else:
    ic50_mult = CELL_LINE_SENSITIVITY.get(well.compound, {}).get(well.cell_line, 1.0)
    hill_v = hill_slope

ic50_viability = max(1e-9, ec50 * ic50_mult)
viability_effect = 1.0 / (1.0 + (well.dose_uM / ic50_viability) ** hill_v)
```

- **Lines 842-875:** Time-dependent death continuation (ER/proteostasis stress accumulation)

---

### 2. **YAML Parameter Definitions** (Biological Ground Truth)
**File:** `/Users/bjh/cell_OS/data/cell_thalamus_params.yaml`

**Lines to Review:**
- **Lines 218-224:** Neuron (iPSC_NGN2) baseline morphology
  - Low ER (85), very high mito (220), high actin (160, neurite outgrowth)
- **Lines 225-231:** Microglia (iPSC_Microglia) baseline morphology
  - High ER (140, cytokine secretion), high RNA (190, inflammatory proteins)
- **Lines 237-238:** ATP baselines (neurons: 70k, microglia: 65k)

**Cell-Line IC50 Modifiers (Biological Differences):**
- **Lines 349-360:** Neurons (iPSC_NGN2):
```yaml
tBHQ: 0.5          # Very sensitive to oxidative stress
H2O2: 0.4          # Extremely sensitive (accumulate oxidative damage)
CCCP: 0.3          # Extremely sensitive (total OXPHOS dependence)
oligomycin: 0.3    # Extremely sensitive (ATP-starved neurons die quickly)
MG132: 0.7         # Sensitive (accumulate misfolded proteins)
nocodazole: 2.0    # Resistant (need functional microtubules for axonal transport)
paclitaxel: 2.5    # Resistant (stabilizing microtubules less toxic to post-mitotic)
```

- **Lines 362-373:** Microglia (iPSC_Microglia):
```yaml
tBHQ: 1.2          # Resistant (produce ROS as defense mechanism)
H2O2: 1.5          # More resistant (ROS is their weapon)
tunicamycin: 0.8   # Somewhat sensitive (high ER protein synthesis for cytokines)
CCCP: 0.9          # Moderately sensitive (not neuron-level dependent)
etoposide: 1.3     # Resistant (immune cells resist DNA damage)
MG132: 0.6         # Sensitive (high protein turnover, cytokine production)
```

---

### 3. **Main Codebase Simulation** (BiologicalVirtualMachine)
**File:** `/Users/bjh/cell_OS/src/cell_os/hardware/biological_virtual.py`

**Lines to Review:**
- **Lines 350-400:** `treat_with_compound()` method
- **Lines 363-372:** **IC50 modifier application** (loads from YAML, applies to dose-response)
```python
# Apply cell-line-specific IC50 modifier (captures biological differences)
if not hasattr(self, 'thalamus_params') or self.thalamus_params is None:
    self._load_cell_thalamus_params()

ic50_modifiers = self.thalamus_params.get('cell_line_ic50_modifiers', {})
cell_line_modifiers = ic50_modifiers.get(vessel.cell_line, {})
modifier = cell_line_modifiers.get(compound, 1.0)  # Default to no modification
ic50 = base_ic50 * modifier

# Apply dose-response model (4-parameter logistic)
viability_effect = 1.0 / (1.0 + (dose_uM / ic50) ** hill_slope)
```

- **Lines 714-862:** `cell_painting_assay()` - morphology simulation
- **Lines 864-997:** `atp_viability_assay()` - LDH cytotoxicity (orthogonal scalar readout)

---

### 4. **Validation Tests**
**File:** `/Users/bjh/cell_OS/test_neuron_simulation.py` (89 lines)
- Tests neuron sensitivity to oxidative, mitochondrial, and microtubule stress

**File:** `/Users/bjh/cell_OS/test_microglia_simulation.py` (97 lines)
- Tests microglia resistance to oxidative, sensitivity to proteasome, resistance to DNA damage

---

## Key Biological Questions for Review

### 1. Are the IC50 modifiers biologically realistic?
**Neurons (iPSC_NGN2):**
- Should neurons be 2-3× MORE sensitive to oxidative stress than cancer? (0.4-0.5× IC50)
- Should neurons be 3× MORE sensitive to mitochondrial stress? (0.3× IC50)
- Should neurons be 2-2.5× LESS sensitive to microtubule drugs? (2.0-2.5× IC50)

**Microglia:**
- Should microglia be 1.5× MORE resistant to oxidative stress than cancer? (1.5× IC50)
- Should microglia be 1.67× MORE sensitive to proteasome inhibition? (0.6× IC50)
- Should microglia be 1.3× MORE resistant to DNA damage? (1.3× IC50)

### 2. Are the baseline morphology values realistic?
**Neurons:**
- Very high mito (220 vs 150 for A549): Neurons have extreme metabolic rate
- Low ER (85 vs 100): No high secretory load (post-mitotic)
- High actin (160 vs 120): Neurite outgrowth, complex cytoskeleton

**Microglia:**
- High ER (140 vs 100): Cytokine/protein secretion (inflammatory cells)
- High RNA (190 vs 180): Inflammatory protein synthesis
- High actin (150 vs 120): Phagocytosis, migration

### 3. Is the proliferation index correct?
- Neurons: 0.1 (post-mitotic, barely divide)
- Microglia: 0.6 (moderate, can divide but slower than cancer)
- A549: 1.3 (fast cycling lung cancer)
- HepG2: 0.8 (slower cycling hepatoma)

### 4. Does the microtubule sensitivity coupling make sense?
Code logic: `ic50_mult = 1.0 / prolif`
- Neurons (prolif=0.1): IC50 × 10 = highly resistant (need functional microtubules)
- Cancer (prolif=1.3): IC50 × 0.77 = more sensitive (fast cycling)

### 5. Are the stress-axis-specific morphology effects realistic?
**Oxidative stress:**
- Mito: +0.6 adapt, -0.8 damage (remodel then fail)
- ER: +0.2 adapt, -0.4 damage (secondary stress)

**Proteasome inhibition:**
- ER: +0.7 adapt, -1.0 damage (protein accumulation then collapse)
- RNA: +0.6 adapt, -0.8 damage (stress response then shutdown)

---

## Expected Validation Results

### From Comparison Table (see above):

**H2O2 @ 100µM (oxidative):**
- Neurons (iPSC_NGN2): 13.4% viability at 24h → **Most sensitive** ✓
- Microglia: 31.5% at 24h → **More resistant than neurons** ✓
- Cancer: 23-44% → **Intermediate** ✓

**CCCP @ 30µM (mitochondrial):**
- Neurons: 27.0% at 24h, 0% at 48h → **Extremely sensitive** ✓
- Microglia: 60.4% at 24h, 25.4% at 48h → **Moderate** ✓
- Cancer: 62% at 24h → **Similar to microglia** ✓

**MG132 @ 10µM (proteasome):**
- Microglia: 81.1% at 24h, 63.0% at 48h → **Most sensitive** ✓
- Neurons: 84.1% at 24h → **Second most sensitive** ✓
- Cancer: 89-90% at 24h → **Least sensitive** ✓

**Nocodazole @ 10µM (microtubule):**
- Neurons: 98.3% at 24h, 96.6% at 48h → **Highly resistant** ✓
- Microglia: 96.4% at 24h, 93.4% at 48h → **Also resistant** ✓
- Cancer: 0-22% at 24h, 0% at 48h → **Very sensitive** ✓

---

## Summary for ChatGPT Review

**Request:**
"Please review the following code files to validate that the neuron (iPSC_NGN2) and microglia (iPSC_Microglia) sensitivities are biologically realistic:

1. **Standalone script:** `standalone_cell_thalamus.py` (lines 660-683: IC50 modifiers)
2. **Parameter file:** `cell_thalamus_params.yaml` (lines 218-231, 349-373)
3. **Main simulation:** `biological_virtual.py` (lines 363-372: IC50 application)

**Key questions:**
- Are the IC50 modifiers biologically justified?
- Are the baseline morphology values realistic for these cell types?
- Does the proliferation-coupled microtubule sensitivity make sense?
- Are there any cell type-specific sensitivities we're missing?
- Do the validation results (comparison table above) match expected biology?"

---

## Additional Context

**Why these cell types matter:**
- **Neurons:** Model neurological disease (Alzheimer's, Parkinson's), drug neurotoxicity testing
- **Microglia:** Model neuroinflammation, understand immune response in brain
- **Cancer cells (A549, HepG2):** Oncology drug screening, toxicity testing

**Orthogonal measurements:**
- **Cell Painting (morphology):** 5-channel imaging (ER, mito, nucleus, actin, RNA)
- **LDH cytotoxicity:** Scalar viability (membrane integrity, inverse of ATP)

**Key innovation:**
- IC50 modifiers capture biological differences WITHOUT changing compound MOA
- Same compound (e.g., H2O2) hits same target (oxidative stress) but cells respond differently based on their biology
