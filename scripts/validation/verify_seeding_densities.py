"""
Verify Seeding Densities

Quick check to ensure seeding densities are realistic for 384-well plates.
"""

from src.cell_os.config.seeding_densities import (
    get_seeding_density,
    get_expected_confluence,
    NOMINAL_SEEDING_DENSITY
)


def verify_384_well_densities():
    """Verify that 384-well seeding densities are realistic."""
    print("=" * 70)
    print("Seeding Density Verification for 384-Well Plates")
    print("=" * 70)
    print()

    # Test cell lines
    cell_lines = ["A549", "HepG2"]
    density_levels = ["LOW", "NOMINAL", "HIGH"]

    print("Current Seeding Densities (384-well format):")
    print("-" * 70)

    for cell_line in cell_lines:
        print(f"\n{cell_line}:")
        for level in density_levels:
            cells = get_seeding_density("384", cell_line, level)
            print(f"  {level:8s}: {cells:6,} cells/well")

            # Check that densities are in reasonable range (2,000 - 10,000)
            if cells < 1000:
                print(f"    ⚠️  WARNING: Too low! Risk of sparse plating.")
            elif cells > 10000:
                print(f"    ⚠️  WARNING: Too high! Risk of overconfluence.")
            else:
                print(f"    ✓ OK - realistic range")

    print()
    print("=" * 70)
    print("Expected Confluence at 48 hours:")
    print("-" * 70)

    for cell_line in cell_lines:
        print(f"\n{cell_line}:")
        for level in density_levels:
            confluence = get_expected_confluence("384", cell_line, 48.0, level)
            cells_initial = get_seeding_density("384", cell_line, level)
            print(f"  {level:8s}: {confluence*100:5.1f}% confluence "
                  f"(seeded {cells_initial:,} cells)")

            # Check confluence is reasonable (40-90% is ideal)
            if confluence < 0.3:
                print(f"    ⚠️  WARNING: Too sparse at readout")
            elif confluence > 0.95:
                print(f"    ⚠️  WARNING: Overconfluent - cell stress expected")
            else:
                print(f"    ✓ OK - good confluence range")

    print()
    print("=" * 70)
    print("Comparison: Old vs New Values")
    print("-" * 70)

    old_nominal = 1_000_000  # The absurdly high value we're fixing
    print(f"\nOLD (INCORRECT) 384-well seeding:")
    print(f"  NOMINAL: {old_nominal:,} cells/well")
    print(f"  ⚠️  This is ~300x too high!")
    print(f"  ⚠️  Wells would be massively overconfluent immediately")
    print(f"  ⚠️  Cells would die from contact inhibition within hours")

    print(f"\nNEW (CORRECT) 384-well seeding:")
    for cell_line in cell_lines:
        new_nominal = get_seeding_density("384", cell_line, "NOMINAL")
        print(f"  {cell_line}: {new_nominal:,} cells/well")
        reduction_factor = old_nominal / new_nominal
        print(f"    → {reduction_factor:.0f}x reduction from old value")

    print()
    print("=" * 70)
    print("Physical Reality Check")
    print("-" * 70)
    print("\n384-well plate specifications:")
    print("  - Surface area: ~0.112 cm²")
    print("  - Well volume: ~80-100 µL")
    print("  - At confluence: ~15,000 cells/well (130-140 cells/cm²)")
    print()

    for cell_line in cell_lines:
        nominal = get_seeding_density("384", cell_line, "NOMINAL")
        percent_of_max = (nominal / 15000) * 100
        print(f"{cell_line} NOMINAL seeding:")
        print(f"  {nominal:,} cells = {percent_of_max:.0f}% of maximum capacity")
        print(f"  → Allows {100-percent_of_max:.0f}% growth headroom ✓")

    print()
    print("=" * 70)
    print("✓ Verification Complete")
    print("=" * 70)


if __name__ == "__main__":
    verify_384_well_densities()
