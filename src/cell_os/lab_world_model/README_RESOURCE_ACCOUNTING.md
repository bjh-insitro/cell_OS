# Resource Accounting - Quick Reference

## Purpose
Calculate costs from resource usage logs using `pricing.yaml` as the single source of truth.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ LabWorldModel                                               │
│  ├─ resource_costs: ResourceCosts                           │
│  │   └─ pricing: DataFrame (from pricing.yaml)             │
│  └─ resource_accounting: ResourceAccounting                 │
│      └─ Uses resource_costs for price lookups               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Inventory                                                    │
│  └─ usage_log: List[Dict]                                   │
│      - Automatically populated by consume()                  │
│      - Format: {resource_id, quantity, unit, timestamp}     │
└─────────────────────────────────────────────────────────────┘
```

## Usage

### 1. Basic Cost Calculation
```python
from cell_os.lab_world_model import LabWorldModel
from cell_os.inventory import Inventory

# Load inventory (has pricing data)
inventory = Inventory("data/raw/pricing.yaml")

# Create LabWorldModel with pricing
lwm = LabWorldModel.from_static_tables(
    pricing=inventory.to_dataframe()
)

# Resources are consumed during experiments
# (automatically logged in inventory.usage_log)

# Calculate costs
cost_report = lwm.compute_cost(inventory.usage_log)

print(f"Total: ${cost_report['total_cost_usd']:.2f}")
for resource_id, cost in cost_report['breakdown'].items():
    print(f"  {resource_id}: ${cost:.2f}")
```

### 2. Direct ResourceAccounting Usage
```python
from cell_os.lab_world_model.resource_accounting import ResourceAccounting
from cell_os.lab_world_model.resource_costs import ResourceCosts
import pandas as pd

# Create pricing DataFrame
pricing_df = pd.DataFrame([
    {"resource_id": "plate_6well", "unit_price_usd": 3.0},
    {"resource_id": "dmem_high_glucose", "unit_price_usd": 0.05},
])

# Initialize
costs = ResourceCosts(pricing=pricing_df)
accounting = ResourceAccounting(resource_costs=costs)

# Calculate cost for specific usage
cost = accounting.calculate_cost("plate_6well", 10)  # $30.00

# Or aggregate from a log
usage_log = [
    {"resource_id": "plate_6well", "quantity": 5},
    {"resource_id": "dmem_high_glucose", "quantity": 100},
]
report = accounting.aggregate_costs(usage_log)
# {'total_cost_usd': 20.0, 'breakdown': {'plate_6well': 15.0, 'dmem_high_glucose': 5.0}}
```

## Key Features

### ✅ Pure Logic
- No I/O operations
- Deterministic calculations
- Easy to test

### ✅ Automatic Logging
- `Inventory.consume()` automatically logs usage
- No manual tracking required
- Timestamp included for audit trail

### ✅ Flexible Reporting
- Total cost
- Per-resource breakdown
- Easy to extend for additional metrics

## Integration Points

### Inventory
- `usage_log` attribute stores all consumption
- Populated automatically by `consume(resource_id, quantity, unit)`

### LabWorldModel
- `resource_accounting` component
- `compute_cost(usage_log)` method for easy access

### Scenarios
- `run_scenario.py` automatically generates cost reports
- Appears after campaign summary

## Testing

```bash
# Unit tests
pytest tests/unit/test_resource_accounting.py -v

# Integration test (run a scenario)
python -m src.run_scenario --name cheap_pilot
# Look for "COST ACCOUNTING REPORT" section
```

## Common Patterns

### Pattern 1: Cost-Aware Experiment Planning
```python
# Estimate cost before running
estimated_usage = [
    {"resource_id": "plate_6well", "quantity": 20},
    {"resource_id": "dmem_high_glucose", "quantity": 400},
]
estimate = lwm.compute_cost(estimated_usage)

if estimate['total_cost_usd'] > budget:
    print("Experiment exceeds budget!")
```

### Pattern 2: Post-Experiment Cost Analysis
```python
# After experiments complete
actual_cost = lwm.compute_cost(inventory.usage_log)

# Compare to budget
print(f"Spent: ${actual_cost['total_cost_usd']:.2f}")
print(f"Budget: ${campaign.budget_total_usd:.2f}")
```

### Pattern 3: Resource-Specific Analysis
```python
report = lwm.compute_cost(inventory.usage_log)

# Find most expensive resource
most_expensive = max(
    report['breakdown'].items(),
    key=lambda x: x[1]
)
print(f"Highest cost: {most_expensive[0]} at ${most_expensive[1]:.2f}")
```

## Notes

- **Resource IDs must match `pricing.yaml`** - Use lowercase keys (e.g., `plate_6well`, not `PLATE_6WELL`)
- **Units must match** - `consume()` validates units against `pricing.yaml`
- **Unknown resources return $0** - No error, just zero cost (allows graceful degradation)
