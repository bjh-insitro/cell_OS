# Hardware Inventory Guide

Last Updated: December 16, 2025

## Overview

The hardware inventory system tracks all physical resources available in your lab, enabling Cell OS to:
- Plan experiments based on available equipment
- Estimate throughput and feasibility
- Calculate resource costs
- Identify bottlenecks

## Files

- **Inventory Data**: `/Users/bjh/cell_OS/data/hardware_inventory.yaml`
- **Registry Module**: `src/cell_os/lab_world_model/hardware_registry.py`
- **CLI Tool**: `scripts/inventory_manager.py`

## Quick Start

### 1. View Current Inventory

```bash
python3 scripts/inventory_manager.py summary
```

This shows:
- Total hardware items
- Available cell lines
- Compound libraries
- Lab capabilities
- Estimated throughput

### 2. List Equipment by Category

```bash
# List all categories
python3 scripts/inventory_manager.py list

# List specific category
python3 scripts/inventory_manager.py list liquid_handlers
python3 scripts/inventory_manager.py list imaging_systems
```

### 3. Check Capabilities

```bash
python3 scripts/inventory_manager.py capabilities
```

Shows whether your lab can perform:
- Liquid handling
- High-content imaging
- Cell Painting (5-channel)
- LDH cytotoxicity assays

### 4. Check Experimental Feasibility

```bash
python3 scripts/inventory_manager.py feasibility phase0
```

Estimates:
- Automation level
- Plates per day
- Operator hours needed
- Bottlenecks

### 5. View Cell Lines & Compounds

```bash
python3 scripts/inventory_manager.py cell-lines
python3 scripts/inventory_manager.py compounds
```

## Populating Your Inventory

Edit `/Users/bjh/cell_OS/data/hardware_inventory.yaml` to add your equipment.

### Example: Adding a Liquid Handler

```yaml
liquid_handlers:
  - id: "hamilton_star_01"
    manufacturer: "Hamilton"
    model: "Microlab STAR"
    channels: 8
    volume_range_ul: [0.5, 1000]
    status: "operational"  # operational | maintenance | offline
    location: "Main Lab Bench"
    acquisition_date: "2024-01-01"
    notes: "Primary liquid handler for plate setup"
    capabilities:
      - aspirate
      - dispense
      - mix
      - plate_transfer
    limitations:
      - "Cannot handle 1536-well plates"
```

### Example: Adding an Imaging System

```yaml
imaging_systems:
  - id: "imagexpress_01"
    manufacturer: "Molecular Devices"
    model: "ImageXpress Micro Confocal"
    channels: 6
    objectives:
      - magnification: "10x"
        na: 0.45
      - magnification: "20x"
        na: 0.75
    plate_formats: ["96-well", "384-well"]
    status: "operational"
    location: "Imaging Room"
    capabilities:
      - "confocal"
      - "widefield"
      - "live_cell"
    throughput:
      time_per_96well_4sites: "10 minutes"
```

### Example: Adding a Plate Reader

```yaml
plate_readers:
  - id: "synergy_h1_01"
    manufacturer: "BioTek"
    model: "Synergy H1"
    detection_modes:
      - "luminescence"
      - "fluorescence"
      - "absorbance"
    plate_formats: ["96-well", "384-well"]
    status: "operational"
    location: "Main Lab"
```

## Equipment Categories

The inventory supports these categories:

### Core Automation
- `liquid_handlers` - Automated pipetting systems
- `imaging_systems` - High-content imagers
- `plate_readers` - Luminescence/fluorescence/absorbance readers
- `plate_washers` - Automated wash stations

### Environmental Control
- `incubators` - CO₂ incubators for cell culture
- `plate_hotels` - Automated plate storage with environmental control
- `shakers` - Microplate shakers for mixing

### Compound Management
- `compound_dispensers` - Acoustic/digital dispensers
- `compound_storage` - -80°C freezers, compound vaults

### Other Equipment
- `centrifuges` - Plate and tube centrifuges
- `cell_counters` - Automated cell counters
- `microscopes` - Benchtop microscopes
- `pipettes` - Manual single-channel pipettes
- `multichannel_pipettes` - Manual multichannel pipettes

### Compute Resources
- `compute.local_workstations` - Local machines
- `compute.cloud_resources` - AWS, GCP, Azure services
- `compute.storage` - NAS, SAN, cloud storage

### Biological Resources
- `cell_lines` - Available cell lines with passage numbers
- `compound_libraries` - Compound plates with well locations

### Consumables
- `consumables.plates` - Tissue culture plates
- `consumables.tips` - Pipette tips
- `consumables.reagents` - Media, buffers, assay kits

## Status Values

Hardware can have these status values:
- **`operational`** - Fully functional, available for use
- **`maintenance`** - Under repair or calibration
- **`offline`** - Not available (broken, retired, or missing parts)

Only `operational` equipment is included in feasibility calculations.

## Using the Inventory in Code

```python
from cell_os.lab_world_model import load_hardware_registry

# Load registry
registry = load_hardware_registry()

# Query hardware
liquid_handlers = registry.get_by_category('liquid_handlers')
for hw in liquid_handlers:
    print(f"{hw.id}: {hw.manufacturer} {hw.model}")

# Check capabilities
if registry.can_perform_cell_painting():
    print("Lab can perform Cell Painting!")

# Get cell lines
cell_lines = registry.get_cell_lines()
for cl in cell_lines:
    print(f"{cl['name']} - {cl['vials_available']} vials available")

# Estimate throughput
throughput = registry.estimate_throughput('phase0')
print(f"Estimated: {throughput['plates_per_day']} plates/day")
```

## Integration with Lab World Model

The hardware registry integrates with Cell OS's lab world model:

```python
from cell_os.lab_world_model import LabWorldModel, load_hardware_registry

# Create world model
world = LabWorldModel.empty()

# Load hardware registry
hardware = load_hardware_registry()

# Use both together for planning
if hardware.can_perform_cell_painting():
    # Plan Cell Painting experiment
    design = generate_cell_painting_design(
        plates_per_day=hardware.estimate_throughput()['plates_per_day'],
        cell_lines=hardware.get_cell_lines(),
        compounds=hardware.get_available_compounds()
    )
```

## Updating the Inventory

1. Edit `data/hardware_inventory.yaml` directly
2. Add new equipment under the appropriate category
3. Test with `python3 scripts/inventory_manager.py summary`
4. Commit changes to git

The registry automatically reloads on each access, so no restart needed.

## Best Practices

1. **Keep it current**: Update weekly or after equipment changes
2. **Mark maintenance**: Set status to `maintenance` when equipment is down
3. **Track calibration**: Use `notes` field to record calibration dates
4. **Document limitations**: List any known limitations or quirks
5. **Track consumables**: Update stock levels when running low

## Example: Minimal Working Lab

Here's what a minimal Phase 0 lab inventory might look like:

```yaml
liquid_handlers:
  - id: "manual_multichannel"
    manufacturer: "Rainin"
    model: "Pipet-Lite Multi"
    channels: 8
    status: "operational"

imaging_systems:
  - id: "contractor_imaging"
    manufacturer: "External CRO"
    model: "ImageXpress (remote)"
    channels: 5
    status: "operational"
    notes: "Outsourced to CRO XYZ"

plate_readers:
  - id: "synergy_h1"
    manufacturer: "BioTek"
    model: "Synergy H1"
    detection_modes: ["luminescence"]
    status: "operational"

incubators:
  - id: "heracell_01"
    manufacturer: "Thermo Fisher"
    model: "Heracell VIOS"
    capacity_plates: 50
    status: "operational"

cell_lines:
  - name: "A549"
    tissue: "lung carcinoma"
    vials_available: 5

  - name: "HepG2"
    tissue: "hepatocellular carcinoma"
    vials_available: 3

compound_libraries:
  - library_id: "phase0_compounds"
    description: "10 compounds for Phase 0"
    compounds:
      - name: "tBHQ"
        target_pathway: "oxidative stress"
      - name: "H2O2"
        target_pathway: "oxidative stress"
      # ... 8 more compounds
```

This minimal setup allows:
- Manual liquid handling (multichannel pipette)
- Outsourced imaging (CRO contract)
- In-house LDH cytotoxicity assays (plate reader)
- Basic incubation capacity

Estimated throughput: **2-5 plates/day** (manual workflow)

## Next Steps

1. Fill in your available hardware in `data/hardware_inventory.yaml`
2. Run `python3 scripts/inventory_manager.py summary` to verify
3. Use `python3 scripts/inventory_manager.py feasibility phase0` to estimate what you can do
4. Use the hardware registry in your Cell OS workflows

## Questions?

- Check the examples in `data/hardware_inventory.yaml` (commented out)
- See `HARDWARE_ARCHITECTURE.md` for equipment recommendations
- Review `src/cell_os/lab_world_model/hardware_registry.py` for API reference
