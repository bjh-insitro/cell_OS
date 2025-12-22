"""
Run CAL_384_RULES_WORLD_v2 plate simulation

This script demonstrates parsing the plate design JSON and preparing it for execution.
Full execution through BiologicalVirtualMachine will require batch processing logic.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cell_os.plate_executor import parse_plate_design_v2, parsed_wells_to_wellspecs

def main():
    json_path = Path("validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v2.json")

    if not json_path.exists():
        print(f"✗ Plate design not found: {json_path}")
        return 1

    print("="*70)
    print("CAL_384_RULES_WORLD_v2 Plate Design Parser")
    print("="*70)

    # Parse plate design
    print(f"\nParsing {json_path.name}...")
    parsed_wells = parse_plate_design_v2(json_path)
    print(f"✓ Parsed {len(parsed_wells)} wells")

    # Convert to WellSpecs
    wellspecs = parsed_wells_to_wellspecs(parsed_wells)
    print(f"✓ Created {len(wellspecs)} WellSpec objects")

    # Summarize
    print(f"\n{'='*70}")
    print("PLATE SUMMARY")
    print("="*70)

    cell_lines = set(pw.cell_line for pw in parsed_wells)
    print(f"\nCell lines: {', '.join(sorted(cell_lines))}")

    # Treatment distribution
    treatments = {}
    for pw in parsed_wells:
        treatments[pw.treatment] = treatments.get(pw.treatment, 0) + 1

    print(f"\nTreatment distribution ({len(treatments)} unique):")
    for treatment, count in sorted(treatments.items(), key=lambda x: -x[1]):
        pct = 100 * count / len(parsed_wells)
        print(f"  {treatment:35s}: {count:3d} wells ({pct:5.1f}%)")

    # Compound distribution
    compounds = {}
    for pw in parsed_wells:
        if pw.reagent != "DMSO":
            compounds[pw.reagent] = compounds.get(pw.reagent, 0) + 1

    if compounds:
        print(f"\nBiological anchors:")
        for compound, count in sorted(compounds.items(), key=lambda x: -x[1]):
            print(f"  {compound}: {count} wells")

    # Density gradient
    densities = {}
    for pw in parsed_wells:
        densities[pw.cell_density] = densities.get(pw.cell_density, 0) + 1

    print(f"\nCell density distribution:")
    for density, count in sorted(densities.items()):
        pct = 100 * count / len(parsed_wells)
        print(f"  {density:10s}: {count:3d} wells ({pct:5.1f}%)")

    # Non-biological provocations summary
    stain_probes = sum(1 for pw in parsed_wells if pw.stain_scale != 1.0)
    timing_probes = sum(1 for pw in parsed_wells if pw.fixation_timing_offset_min != 0)
    focus_probes = sum(1 for pw in parsed_wells if pw.imaging_focus_offset_um != 0)

    print(f"\nNon-biological provocations:")
    print(f"  Stain scale probes: {stain_probes} wells")
    print(f"  Fixation timing probes: {timing_probes} wells")
    print(f"  Focus offset probes: {focus_probes} wells")

    # Show a few example wells
    print(f"\n{'='*70}")
    print("EXAMPLE WELLS")
    print("="*70)

    examples = [
        ("A1", "First well (corner)"),
        ("A2", "Background control (no cells)"),
        ("A6", "Stain scale probe (LOW)"),
        ("A9", "Biological anchor (MORPH)"),
        ("B2", "Contrastive tile (VEHICLE, NW)"),
        ("P24", "Last well (corner)"),
    ]

    for well_id, desc in examples:
        well = [pw for pw in parsed_wells if pw.well_id == well_id][0]
        print(f"\n{well_id} - {desc}:")
        print(f"  Cell line: {well.cell_line}")
        print(f"  Treatment: {well.treatment}")
        print(f"  Reagent: {well.reagent} @ {well.dose_uM} µM")
        print(f"  Density: {well.cell_density}")
        if well.stain_scale != 1.0:
            print(f"  Stain scale: {well.stain_scale}")
        if well.fixation_timing_offset_min != 0:
            print(f"  Fixation offset: {well.fixation_timing_offset_min:+.0f} min")
        if well.imaging_focus_offset_um != 0:
            print(f"  Focus offset: {well.imaging_focus_offset_um:+.1f} µm")

    print(f"\n{'='*70}")
    print("PARSER VALIDATION COMPLETE")
    print("="*70)
    print(f"\n✓ Plate design successfully parsed")
    print(f"✓ {len(wellspecs)} WellSpec objects ready for simulation")
    print(f"\nNext step: Integrate with ExperimentalWorld for full execution")

    return 0


if __name__ == "__main__":
    sys.exit(main())
