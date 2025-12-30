#!/bin/bash
set -e

echo "=== Phase 0 Pre-Execution Validation ==="
echo ""

echo "1. Checking TRACKED_DEATH_FIELDS exists..."
python3 - <<'PY'
from cell_os.hardware.biological_virtual import TRACKED_DEATH_FIELDS
print(f"  ✓ Found {len(TRACKED_DEATH_FIELDS)} tracked fields")
PY

echo ""
echo "2. Checking death_unattributed is NOT in TRACKED_DEATH_FIELDS..."
python3 - <<'PY'
from cell_os.hardware.biological_virtual import TRACKED_DEATH_FIELDS
if "death_unattributed" in TRACKED_DEATH_FIELDS:
    print("  ✗ death_unattributed should NOT be tracked (residual only)")
    raise SystemExit(1)
else:
    print("  ✓ death_unattributed correctly excluded")
PY

echo ""
echo "3. Checking _propose_hazard validation..."
python3 - <<'PY'
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

vm = BiologicalVirtualMachine(seed=42)
vm.seed_vessel('P1_A01', 'A549', initial_count=1e6, vessel_type='96-well')
vessel = vm.vessel_states['P1_A01']
vessel._step_hazard_proposals = {}

try:
    vm._propose_hazard(vessel, 0.01, 'er_stress')
    print("  ✗ Validation not working!")
    raise SystemExit(1)
except ValueError as e:
    if "Unknown death_field" in str(e):
        print("  ✓ Validation raises correctly")
    else:
        print(f"  ✗ Wrong error: {e}")
        raise SystemExit(1)
PY

echo ""
echo "4. Checking death_unattributed raises if proposed..."
python3 - <<'PY'
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

vm = BiologicalVirtualMachine(seed=42)
vm.seed_vessel('P1_A01', 'A549', initial_count=1e6, vessel_type='96-well')
vessel = vm.vessel_states['P1_A01']
vessel._step_hazard_proposals = {}

try:
    vm._propose_hazard(vessel, 0.01, 'death_unattributed')
    print("  ✗ death_unattributed should not be proposable!")
    raise SystemExit(1)
except ValueError as e:
    if "Unknown death_field" in str(e):
        print("  ✓ death_unattributed correctly rejected")
    else:
        print(f"  ✗ Wrong error: {e}")
        raise SystemExit(1)
PY

echo ""
echo "5. Running Phase 0 contracts (expecting 5 failures, 3 passes)..."
echo ""

pytest tests/contracts/test_no_subpop_structure.py -v --tb=no

echo ""
echo "=== Expected: 5 FAILED (deletions pending), 3 PASSED (validation works) ==="
