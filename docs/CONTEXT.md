# Cell OS - System Context

**What you're building, where it's at, and how the pieces fit together.**

Last updated: December 20, 2025

---

## What Is This?

Cell OS is a **world model for cell biology experiments**, not just a simulation.

**Phase 0 (Complete):** We proved the simulation encodes real biological mechanism. Mid-dose (0.5-2×IC50) at 12h shows 300× better stress class separation than all-doses mixed. Key finding: **mechanistic information moves earlier in time and lower in dose**.

**Phase 5 (Complete):** Population heterogeneity keystone fix. Implemented 3-bucket subpopulation model (sensitive/typical/resistant) with shifted IC50 and stress thresholds. This creates natural variance in stress response and prevents overconfident early classification. Mixture width captures biological uncertainty → confidence collapses when populations disagree.

**Phase 5B (Complete):** Realism layer with 3 injections to make epistemic control strategies robust:
1. **RunContext** - Correlated batch/lot/instrument effects (today is cursed)
2. **Plating artifacts** - Post-dissociation stress decays over 6-16h (early timepoints unreliable)
3. **Pipeline drift** - Batch-dependent feature extraction failures (prevents feature overtrust)

Result: Same compound can give different conclusions under different contexts. Forces calibration plate workflows, delayed commitment strategies, and batch normalization.

**Phase 6A (Complete):** Epistemic control - Agent learns to actively resolve biological uncertainty through strategic intervention. Achieved:
1. **Data-driven signature learning** - Learned mechanism signatures from 200 simulation runs per mechanism. Cosplay detector ratio = ∞ (perfect separation via covariance structure)
2. **Calibrated confidence** - Three-layer architecture (inference, reality, decision) with logistic regression calibrator. ECE = 0.0626 < 0.1 (well-calibrated)
3. **Semantic honesty enforcement** - Fixed death accounting, conservation violations, plate factor seeding to ensure no "quiet lies"
4. **Beam search integration** - COMMIT action gated by calibrated confidence (≥0.75 threshold), enabling early termination when justified

**Next:** Phase 6B - Realism improvements (volume/evaporation, plate-level correlated fields, waste/pH dynamics)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     USER INTERFACES                          │
├─────────────────────────────────────────────────────────────┤
│  React Dashboard (localhost:5173)                           │
│  ├── Run Simulation Tab                                      │
│  ├── Experiments Browser                                     │
│  ├── Dose-Response Explorer (log scale, multi-timepoint)    │
│  ├── Morphology Manifold (PCA)                              │
│  ├── Mechanism Recovery ⭐ (Phase 0 key results)            │
│  └── Variance/Sentinel/Plate tabs                           │
└─────────────────────────────────────────────────────────────┘
                            ↕ HTTP
┌─────────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND                           │
│                  (localhost:8000/api/thalamus)              │
├─────────────────────────────────────────────────────────────┤
│  Endpoints:                                                  │
│  • POST /run                    - Start simulation           │
│  • GET  /designs                - List all experiments       │
│  • GET  /designs/{id}/results   - Get well data             │
│  • GET  /designs/{id}/dose-response - Dose-response curves  │
│  • GET  /designs/{id}/mechanism-recovery - PCA stats        │
│  • GET  /designs/{id}/morphology - 5-channel matrix         │
│  • GET  /designs/{id}/variance   - Statistical analysis     │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│                  SIMULATION ENGINE                           │
├─────────────────────────────────────────────────────────────┤
│  src/cell_os/modeling.py                                    │
│  └── generate_experimental_results()                        │
│      • Dose-response curves (4-parameter Hill equation)     │
│      • Time-dependent attrition (ER/proteostasis)           │
│      • 5-channel morphology (ER, mito, nucleus, actin, RNA) │
│      • LDH cytotoxicity (inverse of viability)              │
│      • Stress-axis-specific signatures                      │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│                      DATABASE                                │
├─────────────────────────────────────────────────────────────┤
│  cell_thalamus.db (SQLite)                                  │
│  ├── designs           - Experiment metadata                │
│  ├── experimental_results - Wells (compound, dose, time)    │
│  ├── simulation_params - Compound IC50s, stress axes        │
│  └── cell_lines        - A549, HepG2 protocols              │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Concepts

### 1. Cell Thalamus (Current System)

**What it does:**
- Simulates high-content imaging experiments (fluorescent microscopy)
- 10 compounds × 2 cell lines × 4 doses × 2 timepoints = 2,304 wells
- Generates realistic dose-response + morphology data

**Stress Axes (6 categories):**
| Stress Axis | Compounds | Primary Morphology Signature |
|-------------|-----------|------------------------------|
| ER Stress | tunicamycin, thapsigargin | ER expansion, fragmentation |
| Mitochondrial | CCCP, oligomycin | Network fragmentation, depolarization |
| Oxidative | tBHQ, H2O2 | ROS damage, multi-organelle |
| DNA Damage | etoposide | Nuclear foci, condensation |
| Proteasome | MG132 | Protein aggregates, ER stress |
| Microtubule | nocodazole, paclitaxel | Spindle disruption, actin changes |

### 2. Morphology Scores (5 channels)

**Pipeline:** Fluorescent images → AI segmentation → 200+ features → z-score

| Channel | Dye | What It Measures |
|---------|-----|------------------|
| `morph_er` | ER-Tracker | Network connectivity, fragmentation, whorl formation |
| `morph_mito` | MitoTracker | Tubule length, fission/fusion, depolarization |
| `morph_nucleus` | Hoechst 33342 | Size, chromatin condensation, foci (DNA damage) |
| `morph_actin` | Phalloidin | Stress fiber alignment, cortical actin |
| `morph_rna` | SYTO RNASelect | Stress granules, nucleolar changes |

**Score formula:** `(treated - DMSO_mean) / DMSO_std` = z-score deviation

Higher score = more perturbation from vehicle controls.

### 3. Dose-Response Modeling

**Hill Equation (4-parameter):**
```
viability = bottom + (top - bottom) / (1 + (IC50/dose)^hill_slope)
```

- **IC50:** Dose that kills 50% of cells
- **Hill slope:** Steepness (steep = switch-like, shallow = graded)
- **Top/Bottom:** Maximum/minimum response

**Critical insight:** Mid-dose (0.5-2×IC50) shows adaptive stress responses. High-dose (>5×IC50) shows death signature (less mechanistic information).

### 4. Mechanism Recovery (Phase 0 Key Finding)

**Separation Ratio:** `between_class_variance / within_class_variance` in PCA space

| Condition | Separation Ratio | n_wells |
|-----------|------------------|---------|
| All doses mixed | 0.018 | 1,920 |
| Mid-dose 12h | 5.372 | 320 |
| High-dose 48h | 2.065 | 320 |

**Improvement factor:** 300× (mid-dose vs all-doses)

**Why?** Adaptive stress responses visible at mid-dose before death dominates. High-dose collapse to common death signature. Mixing doses creates trajectory overlap (class collapse).

### 5. Time-Dependent Attrition

**Implementation:** `src/cell_os/modeling.py`

```python
# ER/proteostasis stresses accumulate over time
prob_death = base_prob * (1 + time_hours/24)
```

**Rationale:** ER stress (unfolded proteins) shows cumulative toxicity. Cells don't adapt, they gradually die. Contrast: DNA damage = sudden commitment to apoptosis.

**Validation:** Matches Cell Painting Consortium temporal profiles.

---

## File Layout

```
cell_OS/
├── src/cell_os/
│   ├── modeling.py                       # ⭐ Simulation logic
│   ├── posteriors.py                     # Dose-response curve math
│   ├── api/thalamus_api.py               # ⭐ FastAPI backend
│   ├── database/
│   │   ├── cell_thalamus_db.py           # SQLite interface
│   │   └── repositories/                 # Data access layer
│   ├── cell_thalamus/
│   │   ├── agent.py                      # Agent scaffold (Phase 1)
│   │   ├── variance_analysis.py          # Statistical QC
│   │   └── boundary_detection.py         # Sentinel monitoring
│   └── hardware/
│       └── biological_virtual.py         # Virtual lab hardware
│
├── frontend/
│   └── src/
│       ├── pages/CellThalamus/
│       │   ├── CellThalamusPage.tsx           # Main dashboard
│       │   └── components/
│       │       ├── MechanismRecoveryTab.tsx   # ⭐ Phase 0 results
│       │       ├── DoseResponseTab.tsx        # Log-scale curves
│       │       ├── MorphologyTab.tsx          # PCA manifold
│       │       └── [8 other tabs]
│       └── services/CellThalamusService.ts    # API client
│
├── docs/
│   ├── QUICKSTART.md                     # ⭐ Start here
│   ├── CONTEXT.md                        # ⭐ You are here
│   ├── TODO.md                           # ⭐ Detailed task list
│   └── guides/USER_GUIDE.md              # Full user guide
│
├── scripts/
│   ├── sync_aws_db.sh                    # Download DB from S3
│   ├── watch_s3_db.sh                    # Auto-sync live
│   └── upload_db_to_s3.py                # Upload after JupyterHub run
│
├── standalone_cell_thalamus.py           # ⭐ Run simulations CLI
├── RUN_FULL_CAMPAIGN.sh                  # JupyterHub runner
├── cell_thalamus.db                      # SQLite database
└── TODO.md                               # ⭐ Current priorities
```

---

## Current State (Phase 0 Complete ✅)

### What Works
✅ Simulation generates realistic dose-response + morphology data
✅ Dashboard visualizes all readouts (dose-response, PCA, variance, sentinels)
✅ Mechanism recovery analysis proves 300× separation improvement
✅ Time-dependent attrition for ER/proteostasis stresses
✅ Log-scale dose-response plots with error bars
✅ Live mode (watch running simulations update in real-time)
✅ AWS S3 sync for JupyterHub → Mac workflow

### What's Next (Phase 1)
🎯 **Epistemic Agency** - Agent learns experimental design autonomously
🎯 **Transfer Learning** - Validate mechanism generalizes to held-out compounds
🎯 **Documentation** - Write design principles doc capturing insights

See `TODO.md` for full task breakdown with implementation notes.

---

## Data Flow

### Running a Simulation

```
User clicks "Run Simulation" in dashboard
    ↓
React → POST /api/thalamus/run
    ↓
FastAPI starts background task
    ↓
CellThalamusAgent.run_simulation()
    ↓
Generate well list (compound, dose, timepoint combos)
    ↓
For each well: modeling.generate_experimental_results()
    ├── Compute viability from Hill equation
    ├── Generate 5-channel morphology (stress-specific)
    ├── Add realistic noise (2-5% CV)
    └── Apply time-dependent attrition (if ER stress)
    ↓
Insert all results into cell_thalamus.db
    ↓
Return design_id to frontend
    ↓
Dashboard polls /designs/{id}/status every 2s
    ↓
When complete, display results in tabs
```

### Viewing Results

```
User selects design from dropdown
    ↓
Dashboard calls:
    • GET /designs/{id}/results           - Raw well data
    • GET /designs/{id}/dose-response     - Aggregated by dose
    • GET /designs/{id}/mechanism-recovery - PCA + separation ratios
    • GET /designs/{id}/morphology        - 5-channel matrix
    ↓
React components render charts (recharts library)
```

---

## Database Schema (Key Tables)

### `designs`
```sql
CREATE TABLE designs (
    design_id TEXT PRIMARY KEY,
    status TEXT,              -- 'running' | 'completed' | 'failed'
    mode TEXT,                -- 'demo' | 'quick' | 'full'
    well_count INTEGER,
    created_at TIMESTAMP
);
```

### `experimental_results`
```sql
CREATE TABLE experimental_results (
    result_id INTEGER PRIMARY KEY,
    design_id TEXT,
    compound TEXT,
    dose_um REAL,
    timepoint_hours INTEGER,
    cell_line TEXT,
    stress_axis TEXT,         -- 'er_stress' | 'mitochondrial' | etc.
    viability_pct REAL,       -- 0-100 (from DMSO normalization)
    atp_signal REAL,          -- LDH cytotoxicity (raw)
    morph_er REAL,            -- z-score
    morph_mito REAL,
    morph_nucleus REAL,
    morph_actin REAL,
    morph_rna REAL,
    plate_id TEXT,
    well_position TEXT        -- 'A1', 'B2', etc.
);
```

### `simulation_params`
```sql
CREATE TABLE simulation_params (
    compound TEXT PRIMARY KEY,
    cell_line TEXT,
    stress_axis TEXT,
    ic50_um REAL,
    hill_slope REAL,
    max_effect REAL
);
```

---

## Key Insights to Remember

### Design Principle: Information Moves Early and Low
- **Mid-dose (0.5-2×IC50):** Adaptive stress responses visible
- **High-dose (>5×IC50):** Death signature dominates (all roads lead to apoptosis)
- **Low-dose (<0.1×IC50):** No signal (too close to vehicle)
- **12h timepoint:** Stress responses before irreversible commitment
- **48h timepoint:** Cumulative attrition, less mechanistic information

### Why All-Doses-Mixed Fails
When mixing all dose levels in PCA:
1. **Low dose:** Near-baseline, overlaps with vehicle
2. **Mid dose:** Stress-specific signatures visible (good!)
3. **High dose:** Converges to common death phenotype
4. **Result:** Dose-dependent trajectories overlap → class collapse

**Solution:** Analyze mid-dose only (0.5-2×IC50 at 12h) for mechanism discovery.

### Non-Sigmoidal Responses
Some readouts don't follow classic Hill curves:
- **morph_rna (stress granules):** Threshold-like (sudden appearance)
- **morph_mito (low dose):** Potential hormesis (hyperfusion → fragmentation)
- **morph_er (ER stressors):** Biphasic (expansion → collapse)

Characterizing these patterns reveals mechanism-specific signatures.

---

## Common Workflows

### 1. Explore Existing Data
```bash
# Start system
python -m uvicorn src.cell_os.api.thalamus_api:app --reload &
cd frontend && npm run dev

# Dashboard → Experiments tab → select design
# Switch tabs to view dose-response, PCA, variance
```

### 2. Run New Simulation
```bash
# Option A: Dashboard UI
# Run Simulation tab → select mode → click Run

# Option B: CLI
python standalone_cell_thalamus.py --mode demo  # 8 wells, ~10 seconds
python standalone_cell_thalamus.py --mode quick # 96 wells, ~1 minute
python standalone_cell_thalamus.py --mode full  # 2,304 wells, ~10 minutes
```

### 3. Run on JupyterHub (72 cores)
```bash
# On JupyterHub
./RUN_FULL_CAMPAIGN.sh  # 2,304 wells, ~5 minutes

# Results auto-upload to S3
# On Mac, download:
./scripts/sync_aws_db.sh
```

### 4. Analyze Mechanism Recovery
```bash
# Dashboard → Mechanism Recovery tab
# See 3-panel PCA comparison
# All-doses (0.018) vs Mid-dose (5.372) vs High-dose (2.065)
```

---

## Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/static/test_code_analysis.py

# Lint
make lint
```

---

## Deployment (AWS)

### Architecture
- **JupyterHub (c5.18xlarge):** 72-core server for parallel simulations
- **S3 bucket:** `cell-os-databases` stores `cell_thalamus.db`
- **Local Mac:** Dashboard + analysis

### Workflow
1. SSH to JupyterHub
2. Run campaign: `./RUN_FULL_CAMPAIGN.sh`
3. Results auto-upload to S3
4. Mac syncs: `./scripts/sync_aws_db.sh`
5. View in dashboard

---

## Key Design Decisions

### Why SQLite?
- Single-file database (easy to sync via S3)
- No server setup required
- Fast enough for current scale (<100K wells)
- Phase 2+: migrate to PostgreSQL if needed

### Why FastAPI + React?
- FastAPI: async, auto-docs, type hints
- React: component reusability, recharts integration
- Decoupled: can swap frontend/backend independently

### Why Virtual Hardware?
- Phase 0: prove mechanism recovery in simulation
- Phase 1+: same code runs on real lab hardware (just swap HAL)
- Enables rapid iteration without lab access

### Why Not Cell Painting Images?
- Current: 200+ features → 5 z-scores (lightweight)
- Future: pixel-level images for deep learning (Phase 3+)
- Trade-off: features interpretable, images more realistic

---

## Phase 5 & 5B: Population Heterogeneity and Realism Layer

### Phase 5: Population Heterogeneity (Keystone Fix)

**Problem:** Phase 4 policies overconfident in early classification (12h probe → commit). No mechanism to capture biological variance.

**Solution:** 3-bucket subpopulation model with shifted parameters:

| Subpopulation | Fraction | IC50 Shift | Death Threshold Shift |
|---------------|----------|------------|----------------------|
| Sensitive | 25% | 0.5× (more sensitive) | 0.8× (die earlier) |
| Typical | 50% | 1.0× (normal) | 1.0× (normal) |
| Resistant | 25% | 2.0× (more resistant) | 1.2× (die later) |

**Implementation:**
- `VesselState.subpopulations` dict tracking per-subpop stress levels
- Mixture properties (`er_stress_mixture`, `mito_dysfunction_mixture`)
- `get_mixture_width()` computes std dev across subpopulations
- Death distributed proportionally to subpop stress (sensitive die first)

**Key File:** `src/cell_os/hardware/biological_virtual.py` (lines 167-251)

**Confidence Accounting:**
```python
confidence = base_confidence * max(0, 1 - mixture_width / 0.3)
```

Wide mixture (subpopulations disagree) → low confidence → delayed commitment

**Test:** `tests/unit/test_epistemic_control.py` validates confidence collapse

### Phase 5B: Realism Layer (3 Injections)

**Goal:** Make epistemic control strategies robust by injecting correlated context effects that create "same compound, different conclusion" outcomes.

#### Injection #1: RunContext (Correlated Batch/Lot/Instrument Effects)

**Implementation:** `src/cell_os/hardware/run_context.py` (~300 lines)

**Correlated factors** (correlation=0.5 with shared "cursed day" latent):
- `incubator_shift`: ±0.3 → EC50 multiplier 0.86-1.16×
- `reagent_lot_shift`: Per-channel biases ±15%
- `instrument_shift`: ±0.2 → illumination bias 0.82-1.22×

**Biology hooks** (5 locations in `biological_virtual.py`):
1. Line 1591: EC50 multiplier in `treat_with_compound`
2. Lines 760-761: Stress sensitivity in `_update_er_stress`
3. Lines 853-854: Stress sensitivity in `_update_mito_dysfunction`
4. Lines 929-930: Stress sensitivity in `_update_transport_dysfunction`
5. Lines 1041-1042: Growth rate multiplier in `_update_vessel_growth`

**Measurement hooks** (1 location):
6. Lines 2200-2210: Channel biases + illumination in `cell_painting_assay`

**Test results:** Same compound under two contexts shows 73-155% channel intensity differences (Test 3 in `test_run_context.py`)

#### Injection #2: Plating Artifacts (Post-Dissociation Stress)

**Implementation:** `biological_virtual.py` (lines 197-200, 277-315, 1307-1308, 2133-2157)

**Sampled per vessel:**
- `post_dissociation_stress`: 0.0-0.3 (initial stress level)
- `clumpiness`: 0.0-0.3 (spatial heterogeneity)
- `tau_recovery_h`: 6-16h (exponential decay time constant)

**Temporal decay:**
```python
artifact(t) = A * exp(-t / tau_recovery)
```

**Mixture width inflation:**
```python
total_width = sqrt(base_width² + artifact_width²)  # Quadrature sum
```

**Impact:** Early timepoints (6-12h) unreliable, late timepoints (24-36h) reveal true biology

**Test results:** Artifact inflation decays from 0.036 @ 6h to 0.011 @ 24h (Test 2 in `test_plating_artifacts.py`)

#### Injection #3: Pipeline Drift (Batch-Dependent Feature Extraction)

**Implementation:** `run_context.py` (lines 200-301), integrated at `biological_virtual.py` lines 2220-2229

**Transforms applied:**
1. **Channel-specific segmentation bias** (correlation=0.3 with reagent lot)
   - 30% correlated + 70% independent component
   - When reagent lot bad → segmentation also bad (cursed day coherence)

2. **Affine transforms in feature space** (per batch)
   - ER and mito scaled independently
   - Some batches compress ER-mito separation, others amplify

3. **Discrete failure modes** (5% of plates)
   - `focus_off`: All channels 0.7-0.9× dimmer
   - `illumination_wrong`: Per-channel 0.8-1.3× shifts
   - `segmentation_fail`: Nucleus/actin ratio skewed

**Impact:** Same biology measured in Batch A vs Batch B gives 1.8-5.9% feature differences

**Test results:** Tunicamycin ER/mito ratio differs by 0.06 between batches (enough to flip classification)

### Layered Uncertainty Formula

**Total confidence:**
```python
confidence = (
    base_confidence
    * (1 - mixture_width / 0.3)        # Heterogeneity (Phase 5)
    * (1 - context_uncertainty)         # RunContext (Phase 5B.1)
    * artifact_decay(t)                 # Plating (Phase 5B.2)
    * pipeline_trust(batch)             # Pipeline drift (Phase 5B.3)
)
```

Result: Confidence collapses naturally when any uncertainty source is high.

### Testing

**Phase 5B Test Suite:**
- `test_run_context.py` - 4/4 tests pass
- `test_plating_artifacts.py` - 6/6 tests pass
- `test_pipeline_drift.py` - 6/6 tests pass

**Key validation:**
- Context affects biology: 2.5% viability difference between good/cursed days
- Context affects measurement: 73-155% channel intensity differences
- Plating artifacts decay correctly: 6h → 24h exponential decay verified
- Pipeline drift creates batch disagreement: 1.8-5.9% feature differences

### Files Reference

**Core implementation:**
- `src/cell_os/hardware/run_context.py` - RunContext + plating + pipeline (~300 lines)
- `src/cell_os/hardware/biological_virtual.py` - Integration hooks (9 locations)

**Documentation:**
- `docs/PHASE_5B_REALISM_LAYER.md` - Complete design and implementation guide
- `docs/PHASE_5_EPISTEMIC_CONTROL.md` - Epistemic control system design
- `docs/LATENT_TO_READOUT_MAP.md` - Morphology readout architecture

**Tests:**
- `src/cell_os/hardware/test_run_context.py`
- `src/cell_os/hardware/test_plating_artifacts.py`
- `src/cell_os/hardware/test_pipeline_drift.py`
- `tests/unit/test_epistemic_control.py`

---

## Phase 6A: Epistemic Control (December 2025)

**Goal:** Enable agents to actively resolve biological uncertainty through strategic intervention with calibrated confidence.

### Key Achievements

#### 1. Data-Driven Signature Learning

**Implementation:** `learn_mechanism_signatures.py`, `src/cell_os/hardware/mechanism_posterior_v2.py`

**What changed:**
- Learned mechanism-specific mean (μ_m) and covariance (Σ_m) from 200 simulation runs
- 3D feature space [actin, mito, ER] sufficient for discrimination
- Per-mechanism covariance captures variance structure (not just centroids)

**Validation:**
- **Cosplay detector test**: ratio = ∞ (perfect separation)
- Proves real likelihood evaluation (not nearest-neighbor with Bayes paint)

**Files:**
- `data/learned_mechanism_signatures_quick.pkl` - Frozen signatures (treat like labware)
- `docs/results/SIGNATURE_LEARNING_RESULTS.md` - Full validation report

#### 2. Calibrated Confidence Architecture

**Implementation:** `src/cell_os/hardware/confidence_calibrator.py`, `train_confidence_calibrator.py`

**Three-layer separation:**

1. **Inference Layer** (`mechanism_posterior_v2.py`)
   - Bayesian posterior with per-mechanism covariance
   - Nuisance model: mean-shift + variance inflation
   - Outputs: P(mechanism | features)
   - **Stays clean**: No ad-hoc penalties

2. **Reality Layer** (`confidence_calibrator.py`)
   - Maps belief_state → P(correct)
   - Learns from empirical correctness rates
   - **Allows inversions**: 80% posterior + 53% nuisance → 52% confidence

3. **Decision Layer** (beam search integration)
   - Uses calibrated confidence for COMMIT/WAIT/RESCUE
   - Not just "data favors X" but "allowed to trust that"

**Training:**
- Stratified dataset: 150 runs across 3 nuisance levels (low/medium/high)
- ECE = 0.0626 < 0.1 (well-calibrated)
- High-nuisance bins conservative (confidence 0.899 vs accuracy 0.958)

**Files:**
- `data/confidence_calibrator_v1.pkl` - Frozen calibrator (treat like labware)
- `docs/results/CALIBRATION_RESULTS.md` - Training metrics and analysis
- `docs/architecture/CALIBRATION_ARCHITECTURE.md` - Design documentation

#### 3. Semantic Honesty Enforcement

**Problem:** "Quiet lies" that undermine calibration trust

**Fixes applied:**
1. ✓ **death_unknown vs death_unattributed split** - No silent laundering of contamination
2. ✓ **Remove silent renormalization** - Conservation violations crash loudly (ConservationViolationError)
3. ✓ **Passaging clock resets** - Reset temporal state, resample plating_context
4. ✓ **Plate factor seeding with run_context** - "Cursed day" varies per run, not globally constant
5. ⚠ **Epistemic particle guards** - Documented semantics, guards recommended (medium priority)

**Files:**
- `docs/archive/sessions/2025-12-20-semantic-fixes.md` - Complete fix verification
- `docs/designs/EPISTEMIC_HONESTY_PHILOSOPHY.md` - Design philosophy

#### 4. Beam Search Integration

**Implementation:** `src/cell_os/hardware/beam_search.py`

**What changed:**
- COMMIT action added as first-class terminal decision
- Gated by calibrated_confidence ≥ 0.75 threshold
- Early termination when epistemic state justifies commitment
- Forensic logging for COMMIT decisions

**Expected behavior:**
- Fewer early commits in high-nuisance runs
- No collapse in easy cases (clean context still commits)
- Rescue plans for right reasons (targets dominant uncertainty source)

**Files:**
- `docs/architecture/BEAM_SEARCH_CALIBRATION_INTEGRATION.md` - Integration recipe
- `docs/results/BEAM_COMMIT_TEST_RESULTS.md` - Test validation

### Key Insights

**"The geometry doesn't lie anymore"**
- Before: Nearest-neighbor with Bayes paint (threshold classifier cosplay)
- After: Real likelihood evaluation with learned covariance structure

**"Three-layer separation works"**
- Inference: "What does the data say?" (Bayesian posterior)
- Reality: "How often is that actually correct?" (Calibrated confidence)
- Decision: "What should I do about it?" (Governance)

**"Inversions are not bugs"**
- High posterior + high nuisance → reduced confidence (conservative)
- Moderate posterior + low nuisance → maintained confidence (justified)
- Calibrator learns: "high nuisance → lower trust" explicitly

### Files Reference

**Core implementation:**
- `src/cell_os/hardware/mechanism_posterior_v2.py` - Bayesian inference layer
- `src/cell_os/hardware/confidence_calibrator.py` - Calibration layer (~350 lines)
- `src/cell_os/hardware/beam_search.py` - COMMIT integration

**Data artifacts (frozen):**
- `data/learned_mechanism_signatures_quick.pkl`
- `data/confidence_calibrator_v1.pkl`

**Documentation:**
- `docs/milestones/PHASE_6A_EPISTEMIC_CONTROL_SESSION.md` - Session summary
- `docs/designs/EPISTEMIC_HONESTY_PHILOSOPHY.md` - Design principles
- `docs/designs/EPISTEMIC_CHARTER.md` - Epistemic governance

**Tests:**
- `test_calibrated_posterior.py` - Full pipeline integration test
- `test_context_mimic.py` - Context shift robustness
- `test_messy_boundary.py` - Ambiguous case handling

---

## Troubleshooting

### Database locked error
```bash
# Close all connections
lsof cell_thalamus.db
kill -9 <PID>
```

### Frontend shows "No designs found"
- Check backend logs: is database found?
- Run a demo simulation to populate
- Or sync from S3

### Simulation hangs
- Check Python version (need 3.9+, you have 3.13)
- Check workers count (don't exceed CPU cores)
- Reduce mode (full → quick → demo)

### S3 sync fails
- Check AWS credentials: `aws s3 ls s3://cell-os-databases/`
- Verify bucket permissions
- Run: `./scripts/sync_aws_db.sh` with verbose logging

---

## Next Steps

**New here?**
1. Read `docs/QUICKSTART.md` - get system running
2. Run a demo simulation
3. Explore Mechanism Recovery tab

**Ready to build?**
1. Pick a task from `TODO.md`
2. Quick win: Write design principles doc
3. Big goal: Phase 1 epistemic agency

**Want deep dive?**
1. Read `src/cell_os/modeling.py` - understand simulation
2. Check `frontend/src/pages/CellThalamus/` - see React components
3. Review `TODO.md` detailed implementation notes

---

## Questions?

- Check `TODO.md` for current priorities
- See `docs/guides/USER_GUIDE.md` for full guide
- Read mechanism recovery tab explainer (in dashboard)

**Key principle to remember:**
*Mechanistic information moves earlier in time and lower in dose.*
Mid-dose 12h = optimal window for stress class discrimination.
