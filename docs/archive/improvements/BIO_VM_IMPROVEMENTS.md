# BiologicalVirtualMachine Improvements

## Overview

The `BiologicalVirtualMachine` has been enhanced with two new realistic biological features that make simulations more accurate and force better experimental design:

1. **Lag Phase Dynamics** - Cells don't grow immediately after seeding
2. **Spatial Edge Effects** - Edge wells suffer from evaporation and temperature gradients

## 1. Lag Phase Dynamics

### What It Is

In real cell culture, cells experience a "lag phase" after being seeded or passaged. During this time, they:
- Attach to the surface
- Recover from trypsinization stress
- Adapt to new media conditions
- Resume normal metabolism

Growth rate starts at 0 and ramps up linearly over the lag duration (default: 12 hours).

### Implementation

```python
# In VesselState
self.seed_time = 0.0  # Tracks when vessel was seeded

# In _update_vessel_growth
lag_duration = params.get("lag_duration_h", 12.0)
time_since_seed = self.simulated_time - vessel.seed_time

lag_factor = 1.0
if time_since_seed < lag_duration:
    lag_factor = max(0.0, time_since_seed / lag_duration)
    
effective_growth_rate = growth_rate * lag_factor
```

### Impact on Experiments

- **Short passages are penalized**: If you passage cells and immediately count them 4 hours later, you'll get fewer cells than expected
- **Timing matters**: Experiments need to account for recovery time
- **Realistic schedules**: Forces planners to use biologically realistic timelines

### Example

```python
vm = BiologicalVirtualMachine()

# Seed a flask
vm.seed_vessel("T75_1", "HEK293T", 1e6)

# Count immediately (t=0)
result_0h = vm.count_cells("T75_1", vessel_id="T75_1")
print(f"At t=0h: {result_0h['count']:.2e} cells")

# Advance 6 hours (mid-lag)
vm.advance_time(6.0)
result_6h = vm.count_cells("T75_1", vessel_id="T75_1")
print(f"At t=6h: {result_6h['count']:.2e} cells")  # Minimal growth

# Advance to 24 hours (past lag)
vm.advance_time(18.0)
result_24h = vm.count_cells("T75_1", vessel_id="T75_1")
print(f"At t=24h: {result_24h['count']:.2e} cells")  # Normal doubling
```

## 2. Spatial Edge Effects

### What It Is

Wells on the edge of a plate experience:
- **Evaporation** (especially rows A/H)
- **Temperature gradients** (especially columns 1/12)
- **Uneven gas exchange**

This results in reduced growth rate and viability.

### Implementation

```python
def _is_edge_well(self, vessel_id: str) -> bool:
    """Check if vessel is an edge well (Rows A/H, Cols 1/12)."""
    import re
    match = re.search(r'([A-P])(\d{1,2})$', vessel_id)
    if match:
        row = match.group(1)
        col = int(match.group(2))
        
        is_row_edge = (row == 'A') or (row == 'H')
        is_col_edge = (col == 1) or (col == 12)
        
        return is_row_edge or is_col_edge
    return False

# In _update_vessel_growth
edge_penalty = 0.0
if self._is_edge_well(vessel.vessel_id):
    edge_penalty = params.get("edge_penalty", 0.15)  # 15% reduction
    
effective_growth_rate = growth_rate * (1.0 - edge_penalty)
```

### Impact on Experiments

- **Layout optimization**: Planners must avoid edge wells or randomize across them
- **Replicates matter**: Can't just use A01, A02, A03 for triplicates
- **Real-world practice**: Mirrors actual lab protocols that exclude edge wells

### Example

```python
vm = BiologicalVirtualMachine()

# Seed center well vs edge well
vm.seed_vessel("Plate1_B06", "HEK293T", 1e5)  # Center
vm.seed_vessel("Plate1_A01", "HEK293T", 1e5)  # Edge

# Skip lag phase for comparison
vm.vessel_states["Plate1_B06"].seed_time = -24.0
vm.vessel_states["Plate1_A01"].seed_time = -24.0

# Grow for 24 hours
vm.advance_time(24.0)

center = vm.count_cells("Plate1_B06", vessel_id="Plate1_B06")
edge = vm.count_cells("Plate1_A01", vessel_id="Plate1_A01")

print(f"Center well: {center['count']:.2e} cells")
print(f"Edge well: {edge['count']:.2e} cells")
# Edge will be ~15% lower
```

## Configuration

Both features are configurable via `simulation_parameters.yaml`:

```yaml
defaults:
  lag_duration_h: 12.0    # Hours for lag phase (0-24 typical)
  edge_penalty: 0.15      # Growth rate reduction for edge wells (0.0-0.3)
```

You can also set cell-line-specific values:

```yaml
cell_lines:
  iPSC:
    lag_duration_h: 24.0    # iPSCs take longer to recover
    edge_penalty: 0.25      # More sensitive to edge effects
```

## Testing

Run the test suite to verify:

```bash
pytest tests/unit/test_bio_vm_improvements.py -v
```

Tests verify:
1. Lag phase reduces growth in first 12 hours
2. Edge wells grow slower than center wells
3. Edge detection regex works correctly

## Future Enhancements

Potential additions:
1. **Metabolic modeling** - Track glucose/lactate, require media changes
2. **Plate position effects** - Incubator shelf position matters
3. **Batch effects** - Different reagent lots have different performance
4. **Contamination risk** - Probabilistic contamination events

## References

- Lag phase duration: Freshney, R.I. (2010). Culture of Animal Cells
- Edge effects: Lundholt et al. (2003). J Biomol Screen 8(5):566-70
