# Test Migration Guide - Seeding Densities

## Quick Reference

### OLD (Hardcoded) ❌
```python
def test_something():
    vm = BiologicalVirtualMachine()
    vm.seed_vessel("test_vessel", "A549", 1e6)  # WRONG!
```

### NEW (Database) ✅
```python
def test_something(get_seeding_density):
    vm = BiologicalVirtualMachine()
    cells = get_seeding_density("A549", "384-well", "NOMINAL")
    vm.seed_vessel("test_vessel", "A549", initial_count=cells)
```

### BETTER (Using vessel_type parameter) ✅✅
```python
def test_something():
    vm = BiologicalVirtualMachine()
    vm.seed_vessel("test_vessel", "A549", vessel_type="384-well", density_level="NOMINAL")
```

---

## Available Fixtures

All fixtures are defined in `tests/conftest.py` and automatically available in all tests.

### Quick Fixtures (Pre-defined Densities)
```python
def test_with_fixtures(seed_384_well_a549, seed_96_well_hepg2, seed_t75_a549):
    # Use pre-computed values
    assert seed_384_well_a549 == 3000
    assert seed_96_well_hepg2 == 15000
    assert seed_t75_a549 == 1000000
```

Available quick fixtures:
- `seed_384_well_a549` → 3,000 cells
- `seed_384_well_hepg2` → 5,000 cells
- `seed_96_well_a549` → 10,000 cells
- `seed_96_well_hepg2` → 15,000 cells
- `seed_t75_a549` → 1,000,000 cells
- `seed_t75_hepg2` → 1,200,000 cells

### Flexible Fixture (Any Cell Line / Vessel)
```python
def test_with_lookup(get_seeding_density):
    # Lookup any combination
    cells = get_seeding_density("U2OS", "96-well", "HIGH")
    assert cells > 0
```

### Repository Fixture (Advanced)
```python
def test_with_repository(seeding_repository):
    # Full repository access
    density = seeding_repository.get_seeding_density("A549", "384-well")
    assert density.nominal_cells_per_well == 3000
    assert density.low_multiplier == 0.7
    assert density.high_multiplier == 1.3
```

---

## Migration Patterns

### Pattern 1: Simple Hardcoded Value

**BEFORE**:
```python
def test_cell_painting():
    vm = BiologicalVirtualMachine()
    vm.seed_vessel("test", "A549", 1e6)  # WRONG!
    # ... rest of test
```

**AFTER (Option A - Use fixture)**:
```python
def test_cell_painting(seed_384_well_a549):
    vm = BiologicalVirtualMachine()
    vm.seed_vessel("test", "A549", initial_count=seed_384_well_a549)
    # ... rest of test
```

**AFTER (Option B - Use vessel_type parameter - RECOMMENDED)**:
```python
def test_cell_painting():
    vm = BiologicalVirtualMachine()
    vm.seed_vessel("test", "A549", vessel_type="384-well")
    # ... rest of test
```

### Pattern 2: Multiple Cell Lines

**BEFORE**:
```python
def test_multiple_lines():
    vm = BiologicalVirtualMachine()
    vm.seed_vessel("well1", "A549", 1e6)
    vm.seed_vessel("well2", "HepG2", 1e6)  # WRONG! Same density for both
```

**AFTER**:
```python
def test_multiple_lines():
    vm = BiologicalVirtualMachine()
    vm.seed_vessel("well1", "A549", vessel_type="384-well")
    vm.seed_vessel("well2", "HepG2", vessel_type="384-well")
    # Now correctly uses 3K for A549, 5K for HepG2
```

### Pattern 3: Different Vessel Types

**BEFORE**:
```python
def test_flask_vs_plate():
    vm = BiologicalVirtualMachine()
    vm.seed_vessel("plate_well", "A549", 1e6)  # TOO HIGH!
    vm.seed_vessel("flask", "A549", 1e6)       # Correct for T75
```

**AFTER**:
```python
def test_flask_vs_plate():
    vm = BiologicalVirtualMachine()
    vm.seed_vessel("plate_well", "A549", vessel_type="384-well")  # 3K cells
    vm.seed_vessel("flask", "A549", vessel_type="T75")            # 1M cells
    # Now both are correct!
```

### Pattern 4: Density Levels (LOW/NOMINAL/HIGH)

**BEFORE**:
```python
def test_density_gradient():
    vm = BiologicalVirtualMachine()
    vm.seed_vessel("low", "A549", 0.7e6)   # Scaled hardcoded
    vm.seed_vessel("nom", "A549", 1.0e6)
    vm.seed_vessel("high", "A549", 1.3e6)
```

**AFTER**:
```python
def test_density_gradient():
    vm = BiologicalVirtualMachine()
    vm.seed_vessel("low", "A549", vessel_type="384-well", density_level="LOW")
    vm.seed_vessel("nom", "A549", vessel_type="384-well", density_level="NOMINAL")
    vm.seed_vessel("high", "A549", vessel_type="384-well", density_level="HIGH")
    # Now: 2100, 3000, 3900 cells respectively
```

### Pattern 5: Using get_seeding_density Fixture

**BEFORE**:
```python
def test_custom_logic():
    vm = BiologicalVirtualMachine()
    base = 1e6
    cells = int(base * 1.3)  # HIGH density calculation
    vm.seed_vessel("test", "A549", cells)
```

**AFTER**:
```python
def test_custom_logic(get_seeding_density):
    vm = BiologicalVirtualMachine()
    cells = get_seeding_density("A549", "384-well", "HIGH")
    vm.seed_vessel("test", "A549", initial_count=cells)
```

---

## Common Test Scenarios

### Scenario 1: Testing Plate Executor
```python
def test_plate_executor():
    # The plate executor now handles vessel_type internally
    # No changes needed to tests that call execute_plate_design()
    result = execute_plate_design(plate_json, seed=42)
    assert result["n_success"] > 0
```

### Scenario 2: Testing BiologicalVirtualMachine Directly
```python
def test_bio_vm_seed_vessel():
    vm = BiologicalVirtualMachine()

    # NEW way
    vm.seed_vessel("well_A1", "A549", vessel_type="384-well")

    # OLD way still works (backward compatible)
    vm.seed_vessel("well_A1", "A549", initial_count=3000)
```

### Scenario 3: Testing With Multiple Vessel Types
```python
def test_multiple_vessel_types(get_seeding_density):
    vm = BiologicalVirtualMachine()

    # Get densities for different vessel types
    plate_384 = get_seeding_density("A549", "384-well", "NOMINAL")
    plate_96 = get_seeding_density("A549", "96-well", "NOMINAL")
    flask_t75 = get_seeding_density("A549", "T75", "NOMINAL")

    assert plate_384 == 3000      # 384-well
    assert plate_96 == 10000      # 96-well
    assert flask_t75 == 1000000   # T75 flask
```

### Scenario 4: Testing Cell-Line-Specific Behavior
```python
def test_cell_line_differences():
    vm = BiologicalVirtualMachine()

    # Different cell lines get different densities automatically
    vm.seed_vessel("a549", "A549", vessel_type="384-well")   # 3K cells
    vm.seed_vessel("hepg2", "HepG2", vessel_type="384-well") # 5K cells

    # Both reach ~90% confluence at 48h despite different starting densities
    vm.advance_time(48)
    # ... assertions
```

---

## Priority Files to Update

### HIGH PRIORITY (Core functionality)
These tests directly test seeding logic and should be updated:
- `tests/unit/test_biological_virtual_machine.py`
- `tests/unit/test_bio_vm_*.py`
- `tests/integration/test_plate_executor*.py`
- `tests/phase6a/test_*confluence*.py`

### MEDIUM PRIORITY (Important but not critical)
- Other `tests/phase6a/test_*.py` files
- `tests/simulation/test_*.py` files
- `tests/unit/test_*.py` files

### LOW PRIORITY (Can defer)
- Demo/example scripts in `scripts/demos/`
- One-off test scripts
- Old/archived tests

---

## Testing Your Changes

After updating a test file, run it to verify:
```bash
# Single test file
pytest tests/unit/test_biological_virtual_machine.py -v

# With fixture debugging
pytest tests/unit/test_biological_virtual_machine.py -v -s

# Check fixture is available
pytest tests/unit/test_biological_virtual_machine.py --fixtures | grep seeding
```

---

## When NOT to Change

### Leave These Alone:
1. **Abstract Episode/Beam Search Tests**
   - Files in `tests/unit/test_exploration.py`, `test_policy*.py`
   - These may intentionally use 1e6 as abstract units, not real cells
   - Only change if test explicitly models a real vessel type

2. **Capacity/Confluence Tests**
   - If test is specifically testing capacity overflow at 1e7 cells
   - The 1e6 might be intentional to test near-capacity scenarios

3. **Already Correct T-Flask Tests**
   - If test uses T75/T175 flasks, 1e6 might already be correct
   - Check context before changing

---

## Examples of Updated Tests

### Example 1: Basic Test
```python
# BEFORE
def test_cell_growth():
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test", "A549", 1e6)
    vm.advance_time(24)
    vessel = vm.vessel_states["test"]
    assert vessel.cell_count > 1e6

# AFTER
def test_cell_growth():
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test", "A549", vessel_type="384-well")
    vm.advance_time(24)
    vessel = vm.vessel_states["test"]
    initial_cells = 3000  # A549 in 384-well
    assert vessel.cell_count > initial_cells
```

### Example 2: Using Fixtures
```python
# BEFORE
def test_viability():
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test", "A549", 1e6)
    vm.treat_with_compound("test", "cccp", 5.0)
    vm.advance_time(48)
    vessel = vm.vessel_states["test"]
    assert vessel.viability < 0.5

# AFTER
def test_viability(seed_384_well_a549):
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test", "A549", initial_count=seed_384_well_a549)
    vm.treat_with_compound("test", "cccp", 5.0)
    vm.advance_time(48)
    vessel = vm.vessel_states["test"]
    assert vessel.viability < 0.5
```

---

## Getting Help

If you're unsure whether a test needs updating:

1. **Check the context**: Is it testing a real plate/flask or abstract units?
2. **Check the vessel type**: What format is being tested?
3. **Run the test**: Does it still pass with the new system?
4. **Ask**: When in doubt, ask in #cell-os channel

For questions about specific tests, tag the relevant expert:
- Plate execution: @plate-team
- BiologicalVM: @vm-team
- Confluence/growth: @realism-team
