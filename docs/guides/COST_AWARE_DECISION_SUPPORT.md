# Cost-Aware Decision Support System

Complete implementation of intelligent cost optimization for cell culture workflows.

## Components

### 1. Recipe Optimizer (`src/recipe_optimizer.py`)

Generates optimized recipes based on constraints:
- **Cell type**: Uses cell line database for optimal methods
- **Budget tier**: "budget", "standard", "premium"
- **Automation**: Avoids manual steps if required
- **Max cost**: Hard budget limit

**Example**:
```python
optimizer = RecipeOptimizer(ops)
constraints = RecipeConstraints(
    cell_line="iPSC",
    budget_tier="budget",
    automation_required=True
)
ops_list, methods = optimizer.get_optimized_spin_up_recipe(constraints)
```

**Results**:
- HEK293 spin-up: $199.71 (budget) vs $199.71 (premium) - No difference (hardy cells)
- iPSC spin-up: $200.80 (budget) vs $215.97 (premium) - 7% savings with budget tier

---

### 2. Workflow Optimizer (`src/workflow_optimizer.py`)

Analyzes workflows and suggests cost-saving alternatives:
- Identifies expensive operations
- Suggests cheaper methods with tradeoff analysis
- Calculates ROI for changes
- Provides annual savings estimates

**Example**:
```python
workflow_opt = WorkflowOptimizer(ops)
report = workflow_opt.generate_optimization_report(
    operations=workflow_ops,
    cell_type="iPSC",
    frequency_per_month=10
)
```

**Key Finding**:
- Switching from CryoStor to FBS+DMSO saves **$3,636/year** (45.7% savings)
- Switching from Accutase to Versene saves **$395/year** (18.1% savings)

---

### 3. Cost-Constrained Assay Selector (`src/assay_selector.py`)

Budget-aware assay selection for active learning:
- Filters assays by budget
- Prioritizes information gain or ROI
- Provides explanations for selections
- Shows excluded alternatives

**Example**:
```python
selector = CostConstrainedSelector(cell_line="iPSC")
selected = selector.select(
    candidates=assay_candidates,
    budget_usd=200,
    prioritize_info=True
)
explanation = selector.explain_selection(selected, candidates, budget)
```

**Results** (Budget-dependent selection):
- $100 budget → POSH Screening ($50, 1 bit)
- $200 budget → Flow Cytometry ($150, 10 bits)
- $600 budget → Bulk RNA-Seq ($500, 100 bits)
- $3000 budget → Single-Cell RNA-Seq ($2000, 1000 bits)

---

## Integration Example

**Scenario**: Lab wants to spin up iPSC line with $500 budget

1. **Optimize spin-up recipe** (budget tier):
   - Cost: $200.80
   - Methods: TrypLE + FBS/DMSO
   - Remaining: $299.20

2. **Select affordable assay**:
   - Recommended: Flow Cytometry ($150, 10 bits)
   - Fits within remaining budget
   - Maximizes information gain

**Total**: $350.80 for spin-up + flow cytometry (under $500 budget)

---

## Cost Savings Summary

| Optimization | Annual Savings | % Savings |
|--------------|----------------|-----------|
| CryoStor → FBS+DMSO | $3,637 | 45.7% |
| Accutase → Versene | $395 | 18.1% |
| Budget vs Premium iPSC | $182 | 7.0% |

**Total potential savings**: $4,214/year for a lab doing 10 iPSC passages/month

---

## Usage

See `verify_cost_aware_system.py` for comprehensive examples of all three components.
