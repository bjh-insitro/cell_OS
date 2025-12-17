# Cell OS - System Context

**What you're building, where it's at, and how the pieces fit together.**

Last updated: December 16, 2025

---

## What Is This?

Cell OS is a **world model for cell biology experiments**, not just a simulation.

**Phase 0 (Complete):** We proved the simulation encodes real biological mechanism. Mid-dose (0.5-2×IC50) at 12h shows 300× better stress class separation than all-doses mixed. Key finding: **mechanistic information moves earlier in time and lower in dose**.

**Phase 1 (Next):** Build an agent that discovers this on its own through active learning (epistemic agency).

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
