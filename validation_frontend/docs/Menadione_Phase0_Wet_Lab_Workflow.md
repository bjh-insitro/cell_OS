# Menadione Phase 0: Wet Lab Workflow

**Date**: 2026-01-16
**Experiment**: Menadione dose-response in A549 cells
**Format**: 384-well plates
**Endpoints**: 24h and 48h post-dose

---

## Overview

This document describes the complete wet lab workflow for the Menadione Phase 0 experiment, including instrument usage, timing, and protocol details. The simulation (`menadione_phase0_runner.py`) is designed to mimic this workflow.

---

## Timeline Summary

| Time | Day | Step | Instrument | Notes |
|------|-----|------|------------|-------|
| PM | Day -1 | Seed cells | EL406 | Differential density by timepoint |
| Overnight | Day -1 → Day 0 | Attachment | STX220 incubator | 24h, 37°C, 5% CO2 |
| AM | Day 0 | Feed | EL406 | Aspirate + fresh medium |
| AM | Day 0 | Dose | Echo | Immediately after feed |
| 24h | Day 0 → Day 1 | Incubate | STX220 | 24h plates |
| 48h | Day 0 → Day 2 | Incubate | STX220 | 48h plates (no mid-feed) |
| AM | Day 1 / Day 2 | Endpoint assays | Multiple | See below |

---

## Day -1 (PM): Cell Seeding

### Cell Preparation

1. **Source**: A549 cells from culture flask (passage range: typically P5-P25)
2. **Harvest**: Trypsinize flask, neutralize, spin down (300g, 5 min)
3. **Resuspend**: Fresh growth medium
4. **Count**: Automated cell counter or hemocytometer
5. **Normalize**: Dilute to target concentration

### Seeding Densities

Different densities for different endpoint timepoints to achieve **~70-80% confluence at endpoint**:

| Endpoint | Seeding Density | Rationale |
|----------|-----------------|-----------|
| 24h post-dose | 2,000 cells/well | ~2 doublings (48h total) → ~8,000 cells |
| 48h post-dose | 1,000 cells/well | ~3 doublings (72h total) → ~8,000 cells |

**A549 doubling time**: ~22 hours

### Instrument: EL406

- **Volume**: 50 µL cell suspension per well
- **Source**: Single conical tube with normalized cell suspension
- **Dispensing**: EL406 manifold tubing into 384-well plate
- **Edge wells**: Seeded (per experimental design)

### Post-Seeding

- Plates go to **STX220 incubator**
- Conditions: 37°C, 5% CO2, humidity controlled
- Duration: Overnight (~24h attachment)

---

## Day 0 (AM): Feed + Dose

### Feed (EL406)

**Purpose**: Remove spent medium, provide fresh nutrients before compound exposure

| Parameter | Value |
|-----------|-------|
| Aspiration | Remove old medium |
| Residual volume | ~10-20 µL (typical for 384-well) |
| Fresh medium | 50 µL per well |
| Shear stress | Minimal ("dialed in" process) |

**Note**: The residual volume means a slight dilution of any secreted factors, but this is consistent across all wells.

### Dose (Echo)

**Timing**: Immediately after feed (no equilibration period needed)

| Parameter | Value |
|-----------|-------|
| Instrument | Echo acoustic dispenser (Labcyte/Beckman) |
| Source plate | Pre-made LDV (low dead volume) plate |
| Technology | Acoustic droplet ejection (contact-free) |
| Transfer volume | nL range (compound-dependent) |
| Final DMSO | ~0.1-0.3% |

**Dose range**: 0 (vehicle), 5, 15, 35, 75, 150 µM Menadione

**Artifacts**: None significant - acoustic dispensing is clean

### Post-Dose

- Plates return to **STX220 incubator**
- 24h plates: Incubate until Day 1
- 48h plates: Incubate until Day 2 (no mid-experiment feed)

---

## Day 0 → Endpoint: Incubation

### 24h Plates (Day 0 → Day 1)

- Single 24h incubation period
- No intermediate handling

### 48h Plates (Day 0 → Day 2)

- Single 48h incubation period
- **No feed at 24h post-dose**
- Rationale: Don't want to dilute/wash out compound, simpler protocol

### Incubator: STX220

- Temperature: 37°C
- CO2: 5%
- Humidity: Controlled
- Robotic access: KX-2 arm for plate transfer

---

## Day 1 / Day 2 (AM): Endpoint Assays

### Sequence

```
1. Remove plate from incubator
2. Pre-fixation brightfield imaging (Spark Cyto)
3. Transfer supernatant to assay plate
4. CytoTox protease assay on supernatant
5. Fix cells in original plate (PFA)
6. Stain: Cell Painting + γ-H2AX
7. Image (Nikon Ti2)
```

### Step 1: Pre-Fixation Brightfield QC (Spark Cyto)

**Purpose**: Capture confluence and gross morphology before fixation

| Parameter | Value |
|-----------|-------|
| Instrument | Spark Cyto |
| Mode | Brightfield |
| Output | Confluence estimate, morphology QC |

This step happens **right before** supernatant transfer.

### Step 2-3: Supernatant Transfer + CytoTox-Glo

**Purpose**: Measure dead-cell protease release (indicator of membrane damage / cell death)

| Parameter | Value |
|-----------|-------|
| Assay | CytoTox-Glo Cytotoxicity Assay (Promega) |
| Sample | Supernatant (transferred to separate assay plate) |
| Substrate | AAF-Glo (aminoluciferin) |
| Readout | Luminescence (protease activity from dead cells) |
| Reader | Spark Cyto or plate reader |

**Mechanism**: Dead/dying cells release proteases into the medium. The AAF-Glo substrate is cleaved by these proteases, generating luminescent signal proportional to cell death.

**Key property**: Signal accumulates from dead cells since last media change. The feed step on Day 0 clears the baseline, so the signal at endpoint represents death during the treatment period only.

**Note**: This is done BEFORE fixation because fixing kills all cells and releases everything.

### Step 4-5: Fix + Stain

**Fixation**:
- Reagent: PFA (paraformaldehyde)
- Cells are now dead/fixed

**Staining**: Cell Painting + γ-H2AX (TBD - protocol details to be confirmed)

| Channel | Target | Dye/Antibody |
|---------|--------|--------------|
| Hoechst | Nucleus | Hoechst 33342 |
| Mito | Mitochondria | MitoTracker |
| ER | Endoplasmic reticulum | Concanavalin A |
| AGP | Golgi/Plasma membrane | WGA |
| Phalloidin | Actin cytoskeleton | Phalloidin |
| γ-H2AX | DNA damage foci | Anti-γ-H2AX antibody |

### Step 6: Imaging (Nikon Ti2)

**Instrument**: Nikon Ti2 high-content imager

| Parameter | Value |
|-----------|-------|
| Channels | 5 (Cell Painting) + 1 (γ-H2AX) |
| Fields per well | TBD |
| Magnification | TBD (likely 20x) |

---

## Instruments Summary

| Instrument | Role | Steps |
|------------|------|-------|
| **EL406** | Bulk liquid handling | Cell seeding, Feed |
| **Echo** | Compound dosing | Dose (nL acoustic) |
| **STX220** | Incubation | Attachment, Post-dose |
| **Spark Cyto** | Plate reader/imager | Pre-fix brightfield QC |
| **Nikon Ti2** | High-content imaging | Cell Painting + γ-H2AX |

---

## Plate Design

See: `Menadione_Phase0_Plate_Design_Analysis.md`

| Component | Count per Plate |
|-----------|-----------------|
| Total wells | 382 |
| Sentinel wells | 64 (40 vehicle + 24 treatment) |
| Experimental wells | 318 |
| Doses | 6 (0, 5, 15, 35, 75, 150 µM) |
| Reps per dose | ~53 |

**Templates**: A, B, C (different randomization seeds, fixed sentinel positions)

---

## Simulation Mapping

The simulation (`menadione_phase0_runner.py`) maps to this workflow:

| Real World | Simulation | Output Field |
|------------|------------|--------------|
| Seed cells (EL406) | `hardware.seed_vessel()` with `initial_count` | `seeding_density` |
| 24h attachment | `hardware.advance_time(24.0)` | - |
| Feed (EL406) | Not explicitly modeled (cells in "fresh" state) | - |
| Dose (Echo) | `hardware.treat_with_compound()` | `dose_uM` |
| Incubate to endpoint | `hardware.advance_time(timepoint_h)` | `timepoint_h` |
| Brightfield QC (Spark Cyto) | `vessel.confluence` | `brightfield_confluence` |
| CytoTox-Glo (supernatant) | `hardware.cytotox_assay()` | `cytotox_signal` |
| Cell Painting | `hardware.cell_painting_assay()` | `morphology` |
| γ-H2AX IF | `hardware.supplemental_if_assay()` | `gamma_h2ax_*` |

---

## Open Items (TBD)

- [ ] Exact Cell Painting + γ-H2AX staining protocol (antibody, dilution, incubation)
- [ ] Echo source plate preparation details (concentration scheme, transfer volumes)
- [ ] Imaging parameters (fields/well, magnification, exposure times)
- [x] ~~Protease assay substrate and readout details~~ → CytoTox-Glo (AAF-Glo substrate, luminescence)

---

## Biology Chain: Menadione → Readouts

```
Menadione (redox cycler, Vitamin K3)
    │
    ▼
NQO1 metabolism → Superoxide generation (O₂⁻)
    │
    ├─────────────────────────────────────┐
    ▼                                     ▼
Mitochondrial dysfunction           DNA damage (DSBs)
    │                                     │
    ▼                                     ▼
ATP depletion, ROS amplification    γ-H2AX phosphorylation (Ser139)
    │                                     │
    ▼                                     ▼
Membrane permeabilization           Nuclear foci formation
    │                                     │
    ▼                                     ▼
Dead-cell protease release          γ-H2AX IF signal
    │                                     │
    ▼                                     │
CytoTox-Glo signal (luminescence)   │
    │                                     │
    └─────────────┬───────────────────────┘
                  │
                  ▼
    Morphology changes (Cell Painting)
    - ER stress (Concanavalin A)
    - Mito fragmentation (MitoTracker)
    - Cytoskeleton collapse (Phalloidin)
    - Nuclear condensation (Hoechst)
                  │
                  ▼
    Cell death (viability loss)
```

---

## References

- `src/cell_os/cell_thalamus/menadione_phase0_runner.py` - Simulation runner
- `src/cell_os/cell_thalamus/menadione_phase0_design.py` - Plate design generator
- `data/cell_thalamus_params.yaml` - Compound parameters (menadione EC50, etc.)
- `data/hardware_inventory.yaml` - Instrument specifications
