from cell_os.inventory import Inventory
from cell_os.unit_ops import VesselLibrary, ParametricOps
from cell_os.automation_analysis import (
    analyze_unit_op_automation,
    compare_automation_methods,
    generate_automation_report
)

print("=== AUTOMATION FEASIBILITY ANALYSIS ===\n")

# Initialize
inv = Inventory('data/raw/pricing.yaml')
vessel_lib = VesselLibrary('data/raw/vessels.yaml')
ops = ParametricOps(vessel_lib, inv)

# Test 1: Compare dissociation methods for automation
print("Test 1: Dissociation Methods Automation Comparison")
print("=" * 60)

trypsin_passage = ops.op_passage("plate_6well", dissociation_method="trypsin")
scraping_passage = ops.op_passage("plate_6well", dissociation_method="scraping")

print(compare_automation_methods(trypsin_passage, scraping_passage, "Trypsin", "Scraping"))
print()

# Test 2: Detailed automation report for a complex operation
print("\nTest 2: Detailed Automation Report")
print("=" * 60)

freeze_op = ops.op_freeze(10, freezing_media="fbs_dmso")
print(generate_automation_report(freeze_op))
print()

# Test 3: Cell counting methods comparison
print("\nTest 3: Cell Counting Methods")
print("=" * 60)

counting_methods = ["automated", "hemocytometer", "flow_cytometer"]

for method in counting_methods:
    count_op = ops.op_count("tube", method=method)
    analysis = analyze_unit_op_automation(count_op)
    total_cost = count_op.material_cost_usd + count_op.instrument_cost_usd
    
    automation_status = "✓ Automatable" if count_op.automation_fit >= 1 else "✗ Manual"
    
    print(f"{method.upper():20s}: ${total_cost:5.2f} | {automation_status} | "
          f"Time: {count_op.time_score} | Staff: {count_op.staff_attention}")

print()

# Test 4: Centrifugation presets
print("\nTest 4: Centrifugation Presets")
print("=" * 60)

presets = [
    ("soft", "Fragile cells"),
    ("standard", "Most cells"),
    ("hard", "Pellet compaction")
]

for preset, use_case in presets:
    spin_op = ops.op_centrifuge("tube", preset=preset)
    print(f"{preset.upper():10s} ({use_case:20s}): {spin_op.name}")

print()

# Test 5: Automation feasibility by cell type
print("\nTest 5: Automation Feasibility by Cell Type")
print("=" * 60)

from cell_os.cell_line_database import get_cell_line_profile

cell_lines = ["HEK293", "iPSC", "Primary_Neurons"]

for cell_line in cell_lines:
    profile = get_cell_line_profile(cell_line)
    passage_op = ops.op_passage("plate_6well", dissociation_method=profile.dissociation_method)
    analysis = analyze_unit_op_automation(passage_op)
    
    print(f"{cell_line:20s} ({profile.dissociation_method:10s}):")
    print(f"  Automation: {analysis.automation_percentage:5.1f}% | "
          f"Manual steps: {analysis.manual_steps} | "
          f"Labor: ${analysis.labor_cost_usd:.2f}")
    
    if analysis.manual_bottlenecks:
        print(f"  Bottlenecks: {', '.join(analysis.manual_bottlenecks)}")

print()

# Test 6: Cost-benefit analysis
print("\nTest 6: Labor vs Automation Cost Analysis")
print("=" * 60)

operations = [
    ("Passage (Trypsin)", ops.op_passage("plate_6well", dissociation_method="trypsin")),
    ("Passage (Scraping)", ops.op_passage("plate_6well", dissociation_method="scraping")),
    ("Freeze (10 vials)", ops.op_freeze(10, freezing_media="fbs_dmso")),
    ("Count (Automated)", ops.op_count("tube", method="automated")),
    ("Count (Hemocytometer)", ops.op_count("tube", method="hemocytometer")),
]

for name, op in operations:
    analysis = analyze_unit_op_automation(op)
    total_cost = op.material_cost_usd + op.instrument_cost_usd
    
    print(f"{name:25s}:")
    print(f"  Material + Instrument: ${total_cost:6.2f}")
    print(f"  Labor cost:            ${analysis.labor_cost_usd:6.2f}")
    print(f"  Total cost:            ${total_cost + analysis.labor_cost_usd:6.2f}")
    print(f"  Automation:            {analysis.automation_percentage:5.1f}%")
    print()
