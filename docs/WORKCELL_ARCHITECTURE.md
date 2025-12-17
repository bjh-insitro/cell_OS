# Workcell Architecture

Last Updated: December 16, 2025

## Overview

Cell OS Lab operates a **hub-and-spoke automation architecture** with the Liconic StoreX STX220 (220-plate capacity) as the central plate hotel. KX-2 robotic arms transfer plates between the central hub and multiple specialized workcells.

## System Architecture

```
                    ┌──────────────────────────────────────┐
                    │   Liconic StoreX STX220 (220 MTP)   │
                    │                                      │
                    │  Central Plate Hotel & Incubator    │
                    │  • 37°C, 5% CO2, Humidity Control   │
                    │  • Robotic Access (KX-2 arms)       │
                    │  • 220-plate capacity                │
                    └──────────────┬───────────────────────┘
                                   │
                                   │ KX-2 Robotic Arms
                                   │ (Plate Transfer)
                                   │
       ┌───────────────────────────┼───────────────────────────┐
       │                           │                           │
       ▼                           ▼                           ▼
┌─────────────────┐      ┌─────────────────┐       ┌──────────────────┐
│  LIQUID HANDLING│      │    IMAGING      │       │  COMPOUND DOSING │
│    WORKCELLS    │      │   WORKCELLS     │       │    WORKCELLS     │
└─────────────────┘      └─────────────────┘       └──────────────────┘
       │                           │                           │
       ├─ Hamilton Vantage         ├─ Nikon Ti2               ├─ Echo
       │  + Cytation 5 (QC)        │  (Cell Painting)         │  (Acoustic)
       │                           │                           │
       ├─ Hamilton STAR            ├─ Opera Phenix            ├─ Certus Flex
       │                           │  (Legacy HCS)            │  (8-channel)
       │                           │                           │
       ├─ Hamilton STARlet         ├─ Cytation 5              │
       │                           │  (Workcell QC)           │
       ├─ BioTek EL406             │                           │
       │  (Cell seeding)           ├─ Spark Cyto              │
       │                           │  (QC + LDH assay)        │
       └─ BioTek MultiFlo          │                           │
          (Multi-format)           │                           │
```

## Central Hub: Liconic StoreX STX220

**Role:** Central plate storage and incubation for all workcells

**Capacity:** 220 microplates

**Environmental Control:**
- Temperature: 37°C (range: -30°C to 200°C)
- CO2: 5%
- Humidity: Controlled
- Cell culture grade environment

**Integration:**
- KX-2 robotic arms provide access
- All workcells route plates through STX220
- Plates queue for processing at different stations
- Spring-loaded handling for fast access

**Use Cases:**
- Incubate plates between processing steps
- Queue plates for multiple workcells
- Store plates during multi-day experiments
- Coordinate workflows across stations

## Robotic Plate Transfer: KX-2 Arms

**Function:** Move plates between STX220 and all workcells

**Connected Equipment:**
- Liconic STX220 (central hub)
- Hamilton Vantage, STAR, STARlet
- Nikon Ti2
- Opera Phenix
- Cytation 5
- Spark Cyto
- Echo acoustic dispenser
- Certus Flex

**Operation:**
- Automated plate routing
- No manual intervention for plate movement
- Enables 24/7 operation
- Coordinates access to shared resources

## Workcell 1: Cell Culture & Passaging

**Primary Equipment:**
- Hamilton Vantage (liquid handling)
- Cytation 5 (QC imaging)
- Liconic STX220 (via KX-2)

**Capabilities:**
- Automated cell passaging
- Pre/post-passage QC imaging
- Confluence assessment
- Cell line maintenance

**Workflow:**
```
STX220 → KX-2 → Cytation 5 (pre-passage QC)
              → Hamilton Vantage (trypsinize, split, reseed)
              → Cytation 5 (post-passage QC)
              → KX-2 → STX220 (incubate)
```

**Integration:**
- Cytation 5 images feed custom confluence analysis software
- Hamilton Vantage performs passaging operations
- STX220 provides environmental control between steps

## Workcell 2: Cell Seeding

**Primary Equipment:**
- BioTek EL406 (high-throughput cell seeding)
- BioTek MultiFlo (multi-format)
- Hamilton STAR/Vantage/STARlet (complex patterns)
- Liconic STX220 (via KX-2)

**Capabilities:**
- Bulk cell seeding (96/384-well)
- Multi-format seeding (6/12/24-well)
- Complex spatial patterns (checkerboard, gradients)

**Decision Logic:**
```
IF seeding >= 5 plates AND format in [96, 384] AND cell_line in [A549, HepG2]:
    → Use EL406 (fast, validated for A549/HepG2)

ELIF format in [6, 12, 24]:
    → Use MultiFlo (multi-format, easy setup)

ELIF complex_pattern (e.g., checkerboard):
    → Use Hamilton STAR (variable volume per well)

ELSE (1-2 plates):
    → Manual 8-channel pipette
```

## Workcell 3: Compound Dosing

**Primary Equipment:**
- Echo acoustic dispenser (library transfer)
- Certus Flex (gradient generation)
- Hamilton systems (backup)
- Liconic STX220 (via KX-2)

**Capabilities:**
- Ultra-precise compound dosing (2.5 nL droplets)
- Transfer from compound library plates
- Dose-response curve generation
- Multi-compound parallel dosing

**Decision Logic:**
```
IF compound_library_screening:
    → Use Echo (transfer from source plates, CV <5%)

ELIF need_parallel_gradients:
    → Use Certus Flex (8 independent channels)

ELSE:
    → Use Hamilton (tip-based, flexible)
```

**Phase 0 Workflow:**
```
Compound library plates (384-well) → Echo
                                   → Transfer to assay plates (96-well)
                                   → 10 compounds × dose-response
                                   → KX-2 → STX220 (incubate)
```

## Workcell 4: High-Content Imaging

**Primary Equipment:**
- Nikon Ti2 (primary Cell Painting system)
- Opera Phenix (legacy, being phased out)
- Liconic STX220 (via KX-2)

**Capabilities:**
- 5-channel Cell Painting
- Live cell time-lapse (Ti2 only)
- High-resolution imaging (10×, 20×, 40×, 60×)
- Custom software analysis

**Decision Logic:**
```
IF cell_painting OR live_cell:
    → Use Nikon Ti2 (5+ channels, custom software, environmental control)

ELIF legacy_protocol:
    → Use Opera Phenix (being phased out)

ELSE (QC imaging):
    → Use Spark Cyto (quick checks)
```

**Nikon Ti2 Features:**
- Environmental control (37°C, CO2) for live imaging
- 10×/20×/40×/60× objectives
- Custom software (no vendor lock-in)
- Automated stage for plate scanning

## Workcell 5: Plate Reading & QC

**Primary Equipment:**
- Tecan Spark Cyto (LDH assay, QC imaging)
- Cytation 5 (workcell QC)
- Liconic STX220 (via KX-2)

**Capabilities:**
- LDH cytotoxicity assay (absorbance 490 nm)
- Quick QC imaging (3 fluorescence + BF)
- Confluence checks
- Fluorescence/absorbance plate reading

**Decision Logic:**
```
IF ldh_viability_measurement:
    → Use Spark Cyto (absorbance at 490 nm)

ELIF quick_qc_check:
    → Use Spark Cyto (fast imaging, 3 channels)

ELIF workcell_qc (during passaging):
    → Use Cytation 5 (integrated with Hamilton Vantage)
```

## Phase 0 Screening Workflow

Complete automated workflow for 24-plate Phase 0 screen (v2 design):

### Day 0: Cell Seeding
```
1. Operator prepares cell suspensions
2. EL406 dispenses cells to 24 × 96-well plates
   └─ Pre-fill 50 µL media, then add 50 µL cells
3. KX-2 → STX220 (37°C, CO2)
4. Incubate 4h for cell attachment
```

### Day 1: Compound Dosing
```
1. KX-2 retrieves plates from STX220
2. Echo transfers compounds from library plates
   └─ 10 compounds × dose-response curves
   └─ 2.5 nL droplets for precise dosing
3. KX-2 → STX220
4. Incubate to first timepoint
```

### Days 1-3: Timepoint Sampling (12h, 24h, 48h)

For each timepoint:

```
1. KX-2 retrieves 8 plates from STX220 (1 timepoint batch)

2. LDH Sampling:
   ├─ Hamilton transfers 50 µL supernatant to fresh plate
   ├─ Add LDH detection reagent
   └─ Spark Cyto reads absorbance (490 nm)

3. Fix Cells:
   ├─ Hamilton adds 4% PFA to original plates
   └─ Incubate 20 minutes

4. Cell Painting:
   ├─ Hamilton performs wash steps
   ├─ Add Cell Painting dyes (5 channels)
   ├─ Wash 3×
   └─ Nikon Ti2 images all plates (5 channels, 4 sites/well)

5. Data Storage:
   ├─ LDH values → SQLite database
   └─ Images → S3 storage (1-2 GB/plate)

6. KX-2 → plates to storage/disposal
```

**Total processing time per timepoint:** ~8-12 hours for 24 plates (automated)

**Operator intervention:** Minimal (load reagents, empty waste)

## Automation Level

**Fully Automated Steps:**
- Plate movement (KX-2 → STX220 ↔ all workcells)
- Cell seeding (EL406 or Hamilton)
- Compound dosing (Echo)
- Incubation (STX220 environmental control)
- LDH supernatant sampling (Hamilton)
- Cell Painting staining (Hamilton)
- Imaging (Nikon Ti2)
- Data storage (automated pipelines)

**Manual Steps:**
- Cell culture preparation (trypsinize, count, dilute)
- Reagent loading (media, compounds, dyes, LDH kit)
- Waste removal
- System monitoring

**Automation Level:** ~90% (minimal operator intervention)

**Operator Time:** ~2 hours/day for 24-plate Phase 0 screen

## Bottlenecks & Capacity

**Current Capacity:**
- STX220: 220 plates (far exceeds Phase 0 needs of 24 plates)
- Nikon Ti2: ~10 plates/day for Cell Painting (bottleneck)
- LDH assays: ~30 plates/day (Spark Cyto)
- Compound dosing: ~20 plates/day (Echo)

**Limiting Factor:** Nikon Ti2 imaging throughput

**Scale-up Options:**
- Add second Nikon Ti2
- Use Opera Phenix in parallel (has plate hotel)
- Stagger timepoints across multiple days

## Future Enhancements

**Potential Additions:**
1. Additional Nikon Ti2 for increased imaging throughput
2. CellProfiler cluster for parallel image analysis
3. Additional KX-2 arms for parallel plate movement
4. Integration with cloud analysis pipelines
5. Real-time data visualization dashboard

## Equipment Summary

**Liquid Handling (7 systems):**
- Hamilton Vantage (passaging, complex patterns)
- Hamilton STAR (complex patterns, high precision)
- Hamilton STARlet (compact STAR)
- BioTek EL406 (bulk cell seeding, 96/384)
- BioTek MultiFlo (multi-format, 6/12/24/96/384)
- Certus Flex (8-channel acoustic, gradients)
- Manual 8-channel pipettes

**Compound Dosing (2 systems):**
- Echo acoustic (library transfer, ultra-precise)
- Certus Flex (parallel gradients)

**Imaging (4 systems):**
- Nikon Ti2 (primary Cell Painting, live cell)
- Opera Phenix (legacy HCS, plate hotel)
- Cytation 5 (workcell QC)
- Spark Cyto (QC imaging, LDH assay)

**Plate Management:**
- Liconic StoreX STX220 (220-plate hotel, 37°C, CO2)
- KX-2 robotic arms (plate transfer)

**Total Automation Investment:** Estimated $3-5M (Configuration C from HARDWARE_ARCHITECTURE.md)

## Decision Tree: Equipment Selection

Cell OS uses this logic to choose equipment for each operation:

```python
def select_equipment(operation, parameters):
    if operation == "cell_seeding":
        if parameters.plates >= 5 and parameters.format in [96, 384]:
            if parameters.cell_line in ["A549", "HepG2"]:
                return "EL406"  # Fast, validated
        elif parameters.format in [6, 12, 24]:
            return "MultiFlo"  # Multi-format
        elif parameters.complex_pattern:
            return "Hamilton_STAR"  # Variable volumes
        else:
            return "Manual_8ch"  # 1-2 plates

    elif operation == "compound_dosing":
        if parameters.library_screening:
            return "Echo"  # Ultra-precise, library transfer
        elif parameters.parallel_gradients:
            return "Certus_Flex"  # 8 independent channels
        else:
            return "Hamilton_STAR"  # Flexible

    elif operation == "imaging":
        if parameters.cell_painting or parameters.live_cell:
            return "Nikon_Ti2"  # 5+ channels, custom software
        elif parameters.quick_qc:
            return "Spark_Cyto"  # Fast QC

    elif operation == "viability_assay":
        return "LDH_on_Spark_Cyto"  # Orthogonal to Cell Painting
```

## Next Steps

1. **Characterize Nikon Ti2 throughput** - Measure actual plates/day for Cell Painting
2. **Map data pipelines** - Image storage → CellProfiler → analysis → database
3. **Document CellProfiler workflows** - Feature extraction from Cell Painting images
4. **Build scheduling system** - Coordinate plate movement across workcells
5. **Integrate with Cell OS agent** - Autonomous experiment planning and execution
