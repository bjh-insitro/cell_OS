"""
Test that all plate formats work with the database system.
"""

from src.cell_os.database.repositories.seeding_density import get_cells_to_seed

print("=" * 70)
print("Testing All Plate Formats")
print("=" * 70)
print()

plate_formats = ["384-well", "96-well", "24-well", "12-well", "6-well"]
cell_lines = ["A549", "HepG2"]

for plate_format in plate_formats:
    print(f"\n{plate_format}:")
    print("-" * 40)
    for cell_line in cell_lines:
        for level in ["LOW", "NOMINAL", "HIGH"]:
            cells = get_cells_to_seed(cell_line, plate_format, level)
            print(f"  {cell_line:8s} {level:8s}: {cells:8,} cells")

print()
print("=" * 70)
print("✅ All plate formats working!")
print("=" * 70)
