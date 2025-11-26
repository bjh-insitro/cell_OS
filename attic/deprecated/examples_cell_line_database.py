"""
Cell Line Database Usage Examples

This script demonstrates how to use the cell line database to automatically
select optimal methods for different cell types.
"""

from src.cell_line_database import get_cell_line_profile, get_optimal_methods
from src.inventory import Inventory
from src.unit_ops import VesselLibrary, ParametricOps

# Initialize
inv = Inventory('data/raw/pricing.yaml')
vessel_lib = VesselLibrary('data/raw/vessels.yaml')
ops = ParametricOps(vessel_lib, inv)

print("=== CELL LINE DATABASE USAGE EXAMPLES ===\n")

# Example 1: Get optimal methods for a cell line
print("Example 1: Get optimal methods for HEK293")
print("-" * 50)
hek293_methods = get_optimal_methods("HEK293")
print(f"Optimal methods: {hek293_methods}")
print()

# Example 2: Use cell line profile to create operations
print("Example 2: Create operations using cell line defaults")
print("-" * 50)

cell_line = "iPSC"
profile = get_cell_line_profile(cell_line)

print(f"Cell Line: {profile.name}")
print(f"Cost Tier: {profile.cost_tier}")
print()

# Create operations using the profile's recommended methods
passage_op = ops.op_passage(
    "plate_6well",
    dissociation_method=profile.dissociation_method
)
print(f"Passage ({profile.dissociation_method}): ${passage_op.material_cost_usd + passage_op.instrument_cost_usd:.2f}")
print(f"  Rationale: {profile.dissociation_notes}")
print()

freeze_op = ops.op_freeze(
    10,
    freezing_media=profile.freezing_media
)
print(f"Freeze ({profile.freezing_media}): ${freeze_op.material_cost_usd + freeze_op.instrument_cost_usd:.2f}")
print(f"  Rationale: {profile.freezing_notes}")
print()

transfect_op = ops.op_transfect(
    "flask_t175",
    method=profile.transfection_method
)
print(f"Transfection ({profile.transfection_method}): ${transfect_op.material_cost_usd + transfect_op.instrument_cost_usd:.2f}")
print(f"  Efficiency: {profile.transfection_efficiency}")
print(f"  Rationale: {profile.transfection_notes}")
print()

# Example 3: Compare budget vs premium approaches
print("Example 3: Budget vs Premium comparison for the same experiment")
print("-" * 50)

# Budget approach (HEK293)
hek293_profile = get_cell_line_profile("HEK293")
budget_passage = ops.op_passage("plate_6well", dissociation_method=hek293_profile.dissociation_method)
budget_freeze = ops.op_freeze(10, freezing_media=hek293_profile.freezing_media)
budget_total = (budget_passage.material_cost_usd + budget_passage.instrument_cost_usd +
                budget_freeze.material_cost_usd + budget_freeze.instrument_cost_usd)

# Premium approach (iPSC)
ipsc_profile = get_cell_line_profile("iPSC")
premium_passage = ops.op_passage("plate_6well", dissociation_method=ipsc_profile.dissociation_method)
premium_freeze = ops.op_freeze(10, freezing_media=ipsc_profile.freezing_media)
premium_total = (premium_passage.material_cost_usd + premium_passage.instrument_cost_usd +
                 premium_freeze.material_cost_usd + premium_freeze.instrument_cost_usd)

print(f"Budget (HEK293): ${budget_total:.2f}")
print(f"  Methods: {hek293_profile.dissociation_method} + {hek293_profile.freezing_media}")
print()
print(f"Premium (iPSC): ${premium_total:.2f}")
print(f"  Methods: {ipsc_profile.dissociation_method} + {ipsc_profile.freezing_media}")
print()
print(f"Cost difference: ${premium_total - budget_total:.2f} ({((premium_total - budget_total) / premium_total * 100):.1f}% more)")
print()

# Example 4: Helper function usage
print("Example 4: Using the helper function in ParametricOps")
print("-" * 50)

defaults = ops.get_cell_line_defaults("Primary_Neurons")
print(f"Primary Neurons defaults: {defaults}")
print()

# Example 5: Decision making based on cell type
print("Example 5: Automated decision making")
print("-" * 50)

def recommend_protocol(cell_line: str, budget_constraint: float):
    """Recommend protocol based on cell line and budget."""
    profile = get_cell_line_profile(cell_line)
    
    # Calculate cost with recommended methods
    passage = ops.op_passage("plate_6well", dissociation_method=profile.dissociation_method)
    freeze = ops.op_freeze(10, freezing_media=profile.freezing_media)
    total = passage.material_cost_usd + passage.instrument_cost_usd + freeze.material_cost_usd + freeze.instrument_cost_usd
    
    if total <= budget_constraint:
        return f"✓ Recommended protocol fits budget (${total:.2f} ≤ ${budget_constraint:.2f})"
    else:
        # Try to find cheaper alternatives
        cheaper_passage = ops.op_passage("plate_6well", dissociation_method="trypsin")
        cheaper_freeze = ops.op_freeze(10, freezing_media="fbs_dmso")
        cheaper_total = (cheaper_passage.material_cost_usd + cheaper_passage.instrument_cost_usd +
                        cheaper_freeze.material_cost_usd + cheaper_freeze.instrument_cost_usd)
        
        if cheaper_total <= budget_constraint:
            return (f"⚠ Recommended protocol (${total:.2f}) exceeds budget. "
                   f"Consider budget alternative: trypsin + fbs_dmso (${cheaper_total:.2f})")
        else:
            return f"✗ Even budget protocol (${cheaper_total:.2f}) exceeds budget (${budget_constraint:.2f})"

print(recommend_protocol("HEK293", 60.0))
print(recommend_protocol("iPSC", 60.0))
print(recommend_protocol("iPSC", 120.0))
