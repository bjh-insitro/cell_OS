"""
Comprehensive verification of cost-aware decision support system.

Tests:
1. Recipe Optimizer - Budget tier comparison
2. Workflow Optimizer - Cost-saving analysis
3. Cost-Constrained Selector - Budget-aware assay selection
"""

from cell_os.inventory import Inventory
from cell_os.unit_ops import VesselLibrary, ParametricOps
from cell_os.recipe_optimizer import RecipeOptimizer, RecipeConstraints, generate_optimization_report
from cell_os.workflow_optimizer import WorkflowOptimizer
from cell_os.assay_selector import CostConstrainedSelector, AssayCandidate, AssayRecipe

print("=" * 70)
print("COST-AWARE DECISION SUPPORT SYSTEM VERIFICATION")
print("=" * 70)

# Initialize
inv = Inventory('data/raw/pricing.yaml')
vessel_lib = VesselLibrary('data/raw/vessels.yaml')
ops = ParametricOps(vessel_lib, inv)

# ============================================================================
# TEST 1: Recipe Optimizer
# ============================================================================

print("\n" + "=" * 70)
print("TEST 1: RECIPE OPTIMIZER - Budget Tier Comparison")
print("=" * 70)

optimizer = RecipeOptimizer(ops)

# Test with HEK293 (immortalized)
print("\n--- HEK293 Spin-Up (Immortalized Cell Line) ---\n")
print(generate_optimization_report(optimizer, "HEK293", "spin_up"))

# Test with iPSC (stem cells)
print("\n--- iPSC Spin-Up (Pluripotent Stem Cells) ---\n")
print(generate_optimization_report(optimizer, "iPSC", "spin_up"))

# Test automation requirement
print("\n--- iPSC with Automation Required ---\n")
constraints_auto = RecipeConstraints(
    cell_line="iPSC",
    budget_tier="standard",
    automation_required=True
)
ops_list, methods = optimizer.get_optimized_spin_up_recipe(constraints_auto)
costs = optimizer.calculate_recipe_cost(ops_list)

print(f"Total Cost: ${costs['total_cost_usd']:.2f}")
print(f"Methods Used:")
for method_type, method_name in methods.items():
    print(f"  {method_type}: {method_name}")

# ============================================================================
# TEST 2: Workflow Optimizer
# ============================================================================

print("\n" + "=" * 70)
print("TEST 2: WORKFLOW OPTIMIZER - Cost-Saving Analysis")
print("=" * 70)

workflow_opt = WorkflowOptimizer(ops)

# Create a sample workflow (iPSC maintenance)
workflow_ops = [
    ops.op_passage("plate_6well", dissociation_method="accutase"),
    ops.op_feed("plate_6well", media="mtesr_plus_kit"),
    ops.op_freeze(10, freezing_media="cryostor")
]

print("\n--- Workflow Analysis (10x per month) ---\n")
report = workflow_opt.generate_optimization_report(
    workflow_ops,
    cell_type="iPSC",
    frequency_per_month=10
)
print(report)

# ============================================================================
# TEST 3: Cost-Constrained Assay Selector
# ============================================================================

print("\n" + "=" * 70)
print("TEST 3: COST-CONSTRAINED ASSAY SELECTOR")
print("=" * 70)

selector = CostConstrainedSelector(cell_line="iPSC")

# Create mock assay candidates
mock_candidates = [
    AssayCandidate(
        recipe=AssayRecipe(
            name="POSH_Screening",
            layers={}
        ),
        cost_usd=50.0,
        information_score=1.0
    ),
    AssayCandidate(
        recipe=AssayRecipe(
            name="Flow_Cytometry",
            layers={}
        ),
        cost_usd=150.0,
        information_score=10.0
    ),
    AssayCandidate(
        recipe=AssayRecipe(
            name="Bulk_RNA_Seq",
            layers={}
        ),
        cost_usd=500.0,
        information_score=100.0
    ),
    AssayCandidate(
        recipe=AssayRecipe(
            name="Single_Cell_RNA_Seq",
            layers={}
        ),
        cost_usd=2000.0,
        information_score=1000.0
    )
]

# Test with different budgets
budgets = [100, 200, 600, 3000]

for budget in budgets:
    print(f"\n--- Budget: ${budget} ---\n")
    
    # Prioritize information
    selected = selector.select(mock_candidates, budget, prioritize_info=True)
    
    if selected:
        explanation = selector.explain_selection(selected, mock_candidates, budget)
        print(explanation)
    else:
        print("No assay fits within budget!")

# ============================================================================
# TEST 4: Integration Example
# ============================================================================

print("\n" + "=" * 70)
print("TEST 4: INTEGRATED DECISION-MAKING EXAMPLE")
print("=" * 70)

print("\nScenario: Lab wants to spin up iPSC line with $500 budget\n")

# Step 1: Optimize recipe for budget
constraints = RecipeConstraints(
    cell_line="iPSC",
    budget_tier="budget",  # Use budget methods
    max_cost_usd=500
)

ops_list, methods = optimizer.get_optimized_spin_up_recipe(constraints, num_vials=10)
costs = optimizer.calculate_recipe_cost(ops_list)

print(f"Optimized Spin-Up Recipe:")
print(f"  Total Cost: ${costs['total_cost_usd']:.2f}")
print(f"  Methods:")
for method_type, method_name in methods.items():
    print(f"    {method_type}: {method_name}")

# Step 2: Check if we can afford an assay with remaining budget
remaining_budget = 500 - costs['total_cost_usd']
print(f"\nRemaining Budget: ${remaining_budget:.2f}")

if remaining_budget > 0:
    print("\nChecking what assays we can afford...")
    selected_assay = selector.select(mock_candidates, remaining_budget, prioritize_info=True)
    
    if selected_assay:
        print(f"\nRecommended Assay: {selected_assay.recipe.name}")
        print(f"  Cost: ${selected_assay.cost_usd:.2f}")
        print(f"  Information: {selected_assay.information_score:.1f} bits")
        print(f"  ROI: {selected_assay.roi:.2f} bits/$")
    else:
        print("\nNo assays fit remaining budget. Consider:")
        print("  1. Increase total budget")
        print("  2. Use even cheaper spin-up methods")
        print("  3. Reduce number of vials frozen")

print("\n" + "=" * 70)
print("VERIFICATION COMPLETE")
print("=" * 70)
