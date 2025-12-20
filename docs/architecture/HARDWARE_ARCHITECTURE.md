# Cell Thalamus Hardware Architecture

Last Updated: December 16, 2025

## Overview

This document maps the physical hardware required to implement Cell Thalamus - an autonomous experimental platform for high-content phenotypic screening.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     CELL THALAMUS PLATFORM                       │
│                                                                   │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │   Compute    │      │  Orchestration│      │   Database   │  │
│  │   Server     │◄────►│    Software   │◄────►│   (SQLite/   │  │
│  │  (MacBook/   │      │ (CellThalamusDB│      │   PostgreSQL)│  │
│  │  AWS Lambda) │      │   + API)      │      │              │  │
│  └──────────────┘      └───────┬───────┘      └──────────────┘  │
│                                │                                  │
│                    ┌───────────▼───────────┐                     │
│                    │  Hardware Controllers  │                     │
│                    │  (Python + Drivers)    │                     │
│                    └───────────┬───────────┘                     │
└────────────────────────────────┼─────────────────────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    │     Physical Lab        │
                    │      Automation         │
                    └────────────┬────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
    ┌───▼───┐              ┌─────▼─────┐          ┌──────▼──────┐
    │ Liquid │              │  Imaging  │          │  Incubation │
    │Handler │              │  System   │          │  & Storage  │
    │        │              │           │          │             │
    └───┬───┘              └─────┬─────┘          └──────┬──────┘
        │                        │                        │
    ┌───▼──────────────┐   ┌─────▼──────────────┐  ┌─────▼────────┐
    │ • Dispenser      │   │ • High-content     │  │ • CO₂ incubator│
    │ • Pipettor       │   │   microscope       │  │ • Plate hotel  │
    │ • Plate washer   │   │ • Plate reader     │  │ • Shaker       │
    └──────────────────┘   └────────────────────┘  └────────────────┘
```

## Core Hardware Components

### 1. Liquid Handling System

**Purpose:** Seed cells, dispense compounds, add reagents

**Options:**

#### Entry Level ($50k-$150k)
- **Hamilton Microlab STAR** (4-channel)
  - 96-well pipetting
  - ~10 plates/hour throughput
  - Compact footprint (2' × 3')

- **Tecan Freedom EVO 75**
  - Modular design
  - Multiple pipetting heads
  - Good for Cell Painting reagent additions

#### Mid-Range ($150k-$300k)
- **Hamilton Microlab STAR** (8-16 channel)
  - 384-well capable
  - Integrated plate handling
  - ~20 plates/hour throughput

- **Beckman Coulter Biomek i7**
  - Gripper + multichannel head
  - Automated tip handling
  - Good software ecosystem

#### High-End ($300k-$500k+)
- **Tecan Fluent Automation Workstation**
  - Full automation integration
  - Multiple liquid handling modes
  - Scheduler for 24/7 operation

**Key Specs Required:**
- 96-well and 384-well compatible
- 0.5 µL - 200 µL volume range
- <5% CV at 2 µL (for compound dosing)
- Tip tracking and waste management
- Integration with plate hotel/incubator

---

### 2. High-Content Imaging System

**Purpose:** Cell Painting - capture 5-channel morphology per well

**Options:**

#### Entry Level ($200k-$400k)
- **Molecular Devices ImageXpress Micro Confocal**
  - 4-6 channels
  - Confocal optics
  - ~10 min per 96-well plate (4 sites/well)
  - Good for morphology

#### Mid-Range ($400k-$800k)
- **PerkinElmer Opera Phenix**
  - High-speed confocal
  - 5-channel Cell Painting optimized
  - ~5 min per 96-well plate
  - Water immersion objectives

- **Molecular Devices ImageXpress Confocal HT.ai**
  - AI-assisted focusing
  - 7-channel capable
  - Faster acquisition

#### High-End ($800k-$1.5M)
- **Yokogawa CQ1**
  - Spinning disk confocal
  - Ultra-fast acquisition
  - Live cell imaging capable

**Key Specs Required:**
- 5 fluorescent channels minimum (DAPI, FITC, TRITC, Cy5, Cy7)
- Confocal or widefield with deconvolution
- 20× objective (0.75 NA minimum)
- Autofocus (laser or image-based)
- Environmental control (37°C, 5% CO₂)
- Plate hotel integration (10-50 plate capacity)

**Cell Painting Channels:**
1. **Hoechst 33342** → DAPI (Nucleus)
2. **Concanavalin A (Alexa 488)** → FITC (ER)
3. **Phalloidin (Alexa 568)** → TRITC (Actin)
4. **MitoTracker Deep Red** → Cy5 (Mitochondria)
5. **SYTO 14** → Cy7 (RNA/Nucleoli)

---

### 3. Plate Reader (LDH Cytotoxicity Assay)

**Purpose:** LDH cytotoxicity measurement (orthogonal scalar viability)

**Options:**

#### Entry Level ($30k-$60k)
- **BioTek Synergy H1**
  - Luminescence, fluorescence, absorbance
  - 96/384 well
  - Manual plate loading

#### Mid-Range ($60k-$120k)
- **PerkinElmer EnVision**
  - Fast luminescence
  - Integrated with liquid handler
  - Stacker for automation

- **BMG Labtech CLARIOstar Plus**
  - Multi-mode reader
  - LVF (Linear Variable Filter) for flexibility
  - Good dynamic range

#### High-End ($120k-$250k)
- **Molecular Devices SpectraMax i3x**
  - Fully automated with stacker
  - Multi-mode detection
  - Schedulable for 24/7

**Key Specs Required:**
- Absorbance detection at 490 nm (for LDH assay)
- Sensitivity: <10 cells/well detection
- 96-well and 384-well compatible
- Integration with automation (stacker)
- Temperature control (37°C for kinetic reads)

---

### 4. Incubation & Environmental Control

**Purpose:** Cell culture maintenance, plate storage during workflow

**Components:**

#### CO₂ Incubator
- **Thermo Fisher Heracell VIOS 160i** ($10k-$15k)
  - 37°C, 5% CO₂
  - HEPA filtration
  - 3-4 shelf capacity (~50 plates)

#### Automated Plate Hotel
- **Liconic STX44** ($40k-$80k)
  - 44-plate capacity
  - Controlled environment (37°C, 5% CO₂)
  - Robotic plate handling
  - Integration with liquid handler + imager

- **Hamilton HEPAfiltered Plate Hotel** ($60k-$100k)
  - HEPA-filtered
  - Temperature and CO₂control
  - Stackers for 100+ plates

#### Plate Shaker (for staining)
- **VWR Advanced Digital Shaker** ($2k-$5k)
  - Microplate compatible
  - Variable speed (100-1500 RPM)
  - For wash steps and reagent mixing

---

### 5. Plate Washer (Cell Painting Workflow)

**Purpose:** Remove staining reagents between steps

**Options:**

- **BioTek 405 TS Microplate Washer** ($15k-$25k)
  - 96-well
  - Vacuum aspiration
  - 8-channel manifold

- **Molecular Devices AquaMax DW4** ($25k-$40k)
  - Integrated with automation
  - Cell-based assay optimized
  - Gentle aspiration

**Key Requirements:**
- Gentle aspiration (don't detach cells)
- Precise volume dispensing
- 96-well and 384-well heads
- Integration with liquid handler

---

### 6. Compound Storage & Management

**Purpose:** Store compound libraries, manage dose preparation

**Components:**

#### Compound Freezer
- **Thermo Fisher -80°C Freezer** ($8k-$15k)
  - For DMSO stock storage
  - Racked tube storage

#### Automated Compound Dispenser
- **Tecan D300e Digital Dispenser** ($150k-$250k)
  - Acoustic dispensing
  - nL-µL volumes
  - No tips required
  - Direct-to-plate compound addition

- **HP D300e** (Alternative)
  - Inkjet-based dispensing
  - Very low dead volume

**Alternative (Manual):**
- Echo 655 Acoustic Liquid Handler ($200k-$300k)
  - Gold standard for compound management
  - Transfers from source plates
  - 2.5 nL droplet resolution

---

### 7. Robotic Integration (Optional - High-End)

**Purpose:** Integrate all instruments into unified workflow

**Options:**

#### Entry Level Integration
- **Hamilton Venus Software** (included with STAR)
  - Schedule liquid handler tasks
  - Basic integration with imager/reader

#### Mid-Range Integration
- **Thermo Fisher Momentum** ($150k-$300k + instruments)
  - Modular integration platform
  - Gantry robot moves plates between stations
  - Works with multiple vendors

#### High-End Integration
- **PerkinElmer Janus G3 Workstation** ($300k-$500k)
  - Full walkaway automation
  - Scheduler for 24/7 operation
  - Environmental control throughout

- **Custom Robotic System** ($500k-$1M+)
  - ABB or KUKA robotic arm
  - Fully custom workflow
  - Maximum flexibility

---

## Recommended Configurations

### Configuration A: "Founder Dataset" ($300k-$500k)

**Goal:** Execute Phase 0-1 screens with manual intervention

**Hardware:**
- **Liquid Handler:** Hamilton Microlab STAR 4-channel ($80k)
- **Imager:** Molecular Devices ImageXpress Micro Confocal ($250k)
- **Plate Reader:** BioTek Synergy H1 ($40k)
- **Incubator:** Thermo Heracell VIOS ($12k)
- **Washer:** BioTek 405 TS ($20k)
- **Compound Management:** Manual (384-well mother plates)

**Throughput:** 5-10 plates/day
**Operator Time:** ~4 hours/day
**Suitable For:** Academic labs, small biotech

---

### Configuration B: "Semi-Automated" ($800k-$1.2M)

**Goal:** Execute Phase 0-2 screens with minimal manual steps

**Hardware:**
- **Liquid Handler:** Hamilton Microlab STAR 8-channel ($180k)
- **Imager:** PerkinElmer Opera Phenix + 20-plate hotel ($600k)
- **Plate Reader:** PerkinElmer EnVision with stacker ($100k)
- **Incubator/Hotel:** Liconic STX44 ($60k)
- **Washer:** Molecular Devices AquaMax DW4 ($35k)
- **Compound Dispenser:** Tecan D300e ($200k)
- **Integration:** Hamilton Venus + custom scripts ($50k)

**Throughput:** 20-30 plates/day
**Operator Time:** ~2 hours/day
**Suitable For:** Mid-size biotech, pharma research groups

---

### Configuration C: "Fully Autonomous" ($2M-$3M+)

**Goal:** 24/7 autonomous operation (Phase 0-3)

**Hardware:**
- **Liquid Handler:** Tecan Fluent with gripper ($350k)
- **Imager:** Yokogawa CQ1 + 50-plate hotel ($1.2M)
- **Plate Reader:** Molecular Devices SpectraMax i3x ($150k)
- **Incubator/Hotel:** Hamilton Plate Hotel ($80k)
- **Washer:** Integrated with Fluent ($included)
- **Compound Dispenser:** Echo 655 ($250k)
- **Integration:** Thermo Momentum or custom robotic arm ($400k)
- **Environmental Control:** Walk-in incubator room ($200k)

**Throughput:** 100+ plates/day
**Operator Time:** ~30 min/day (restocking)
**Suitable For:** Large pharma, high-throughput screening cores

---

## Data Flow Architecture

```
┌────────────────────────────────────────────────────────────┐
│                     Physical Workflow                       │
└────────────────────────────────────────────────────────────┘
                               │
                               ▼
    ┌─────────────────────────────────────────────────────┐
    │  1. SEEDING (Liquid Handler)                        │
    │     - Dispense cells → 96-well plates               │
    │     - 5,000 cells/well in 100 µL media             │
    └─────────────────┬───────────────────────────────────┘
                      │
                      ▼
    ┌─────────────────────────────────────────────────────┐
    │  2. ATTACHMENT (Incubator)                          │
    │     - 4h at 37°C, 5% CO₂                           │
    └─────────────────┬───────────────────────────────────┘
                      │
                      ▼
    ┌─────────────────────────────────────────────────────┐
    │  3. COMPOUND DOSING (Liquid Handler or D300e)       │
    │     - Add 1 µL compound in DMSO (1% final)         │
    │     - 10-point dose-response curves                │
    └─────────────────┬───────────────────────────────────┘
                      │
                      ▼
    ┌─────────────────────────────────────────────────────┐
    │  4. INCUBATION (Incubator/Hotel)                    │
    │     - 12h, 24h, 48h timepoints                     │
    └─────────────────┬───────────────────────────────────┘
                      │
                      ▼
    ┌─────────────────────────────────────────────────────┐
    │  5A. LDH ASSAY (Plate Reader)                       │
    │     - Sample 50 µL supernatant to fresh plate     │
    │     - Add LDH detection reagent                   │
    │     - Wait 10 min, read absorbance at 490 nm     │
    └─────────────────┬───────────────────────────────────┘
                      │
                      ▼
    ┌─────────────────────────────────────────────────────┐
    │  5B. CELL PAINTING (Imager)                         │
    │     Step 1: Fix (4% PFA, 20 min)                   │
    │     Step 2: Permeabilize (0.1% Triton, 15 min)    │
    │     Step 3: Stain (5 dyes, 30 min)                │
    │     Step 4: Wash 3× (plate washer)                │
    │     Step 5: Image (5 channels, 4 sites/well)      │
    └─────────────────┬───────────────────────────────────┘
                      │
                      ▼
    ┌─────────────────────────────────────────────────────┐
    │  6. DATA STORAGE                                    │
    │     - Images → S3 (1-2 GB/plate)                   │
    │     - LDH values → SQLite/PostgreSQL               │
    └─────────────────┬───────────────────────────────────┘
                      │
                      ▼
    ┌─────────────────────────────────────────────────────┐
    │  7. ANALYSIS (Cloud Compute)                        │
    │     - CellProfiler: segment cells, extract features│
    │     - Python: PCA, variance analysis, charts       │
    │     - Dashboard: visualize results                 │
    └─────────────────────────────────────────────────────┘
```

---

## Control Software Architecture

```
┌──────────────────────────────────────────────────────────┐
│          Cell Thalamus Orchestration Layer               │
│                                                           │
│  ┌─────────────────────────────────────────────────┐    │
│  │  CellThalamusAgent (Python)                     │    │
│  │  - Generates experimental designs               │    │
│  │  - Schedules instrument operations              │    │
│  │  - Monitors progress                            │    │
│  └────────────┬────────────────────────────────────┘    │
│               │                                          │
│  ┌────────────▼────────────────────────────────────┐    │
│  │  Hardware Abstraction Layer                     │    │
│  │  - Translate Cell Thalamus commands → drivers   │    │
│  └────────────┬────────────────────────────────────┘    │
└───────────────┼──────────────────────────────────────────┘
                │
    ┌───────────┼───────────────────────┐
    │           │                       │
┌───▼────┐  ┌──▼──────┐  ┌──────▼──────┐
│Hamilton│  │Molecular│  │PerkinElmer  │
│Venus   │  │Devices  │  │Columbus/    │
│        │  │MetaXpress│ │Harmony      │
└────┬───┘  └────┬────┘  └──────┬──────┘
     │           │               │
┌────▼─────┐ ┌──▼─────┐  ┌──────▼──────┐
│ STAR     │ │ImageXpr│  │Opera Phenix │
│ Liquid   │ │ess     │  │             │
│ Handler  │ │ Imager │  │             │
└──────────┘ └────────┘  └─────────────┘
```

**Key Software Components:**

1. **Vendor Drivers** (Proprietary)
   - Hamilton Venus (liquid handler)
   - MetaXpress / Columbus (imaging)
   - Plate reader software

2. **Cell Thalamus Hardware Layer** (Custom Python)
   - `hardware/hamilton.py` - Control STAR via Venus API
   - `hardware/imager.py` - Trigger imaging runs
   - `hardware/reader.py` - Collect LDH data
   - `hardware/hotel.py` - Manage plate storage/retrieval

3. **Orchestration** (Cell Thalamus Agent)
   - Generate worklist files for liquid handler
   - Schedule imaging at correct timepoints
   - Monitor plate locations (hotel → imager → reader)
   - Collect data → database

4. **Analysis Pipeline**
   - CellProfiler (image segmentation)
   - Python (statistical analysis)
   - React dashboard (visualization)

---

## Physical Space Requirements

### Minimal Setup (Config A)
- **Lab Space:** 200-300 sq ft
- **Layout:** Linear bench (6' × 12')
- **Climate Control:** Standard lab HVAC
- **Power:** 2× 20A circuits
- **Network:** 1 Gbps Ethernet

### Mid-Scale Setup (Config B)
- **Lab Space:** 400-600 sq ft
- **Layout:** U-shaped bench or separate automation bay
- **Climate Control:** Temperature-controlled room (20-22°C)
- **Power:** 4× 20A circuits
- **Network:** 10 Gbps fiber (for image transfer)

### High-Throughput Setup (Config C)
- **Lab Space:** 800-1200 sq ft
- **Layout:** Dedicated automation room + walk-in incubator
- **Climate Control:** HVAC with backup, humidity control
- **Power:** Dedicated 200A panel
- **Network:** 10-40 Gbps fiber
- **Data Storage:** NAS (100+ TB for images)

---

## Cost Breakdown Summary

| Configuration | Hardware Cost | Annual Consumables | Operator Time | Throughput |
|--------------|---------------|-------------------|---------------|------------|
| **A (Founder)** | $300k-$500k | $50k-$100k | 4 hr/day | 5-10 plates/day |
| **B (Semi-Auto)** | $800k-$1.2M | $100k-$200k | 2 hr/day | 20-30 plates/day |
| **C (Full Auto)** | $2M-$3M+ | $200k-$500k | 0.5 hr/day | 100+ plates/day |

**Consumables Include:**
- Tissue culture plastics (plates, tips)
- Cell culture media and reagents
- Compound libraries
- Cell Painting dyes
- LDH cytotoxicity kits (Promega CytoTox 96 or equivalent)

---

## Next Steps

1. **Define Use Case**
   - What throughput is needed? (plates/week)
   - What budget constraints?
   - Manual vs automated priority?

2. **Vendor Evaluation**
   - Request demos from Hamilton, Tecan, Molecular Devices
   - Visit existing installations
   - Get quotes

3. **Pilot Study**
   - Rent time on existing systems (CRO, core facility)
   - Validate Cell Painting protocol
   - Test integration feasibility

4. **Integration Plan**
   - Write hardware drivers (Python)
   - Build worklist generators
   - Test end-to-end workflow

5. **Validation**
   - Run Phase 0 founder screen
   - Validate variance metrics match simulations
   - Iterate on protocol

---

## References

- Broad Institute Cell Painting protocol: https://github.com/carpenterlab/2016_bray_natprot
- Hamilton Automation: https://www.hamiltoncompany.com
- Molecular Devices: https://www.moleculardevices.com
- PerkinElmer: https://www.perkinelmer.com
- Tecan: https://www.tecan.com

