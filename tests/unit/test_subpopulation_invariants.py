"""
Test subpopulation structural invariants.

These are ENFORCED invariants - changes that violate them should fail loudly.
The specific default values (25/50/25) are CONFESSED as non-biological in docs.

NOTE: VesselState.subpopulations was designed but not yet implemented.
These tests are skipped until the feature is added.
"""

import pytest
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


@pytest.mark.skip(reason="VesselState.subpopulations not yet implemented")
def test_subpop_fractions_sum_to_unity():
    """Subpopulation fractions must sum to 1.0 ± eps."""
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test", "A549", 10000)
    vessel = vm.vessel_states["test"]

    total_frac = sum(sp['fraction'] for sp in vessel.subpopulations.values())
    assert abs(total_frac - 1.0) < 1e-6, f"Subpop fractions must sum to 1.0, got {total_frac}"


@pytest.mark.skip(reason="VesselState.subpopulations not yet implemented")
def test_subpop_fractions_in_valid_range():
    """Each subpopulation fraction must be in [0, 1]."""
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test", "A549", 10000)
    vessel = vm.vessel_states["test"]

    for sp in vessel.subpopulations.values():
        assert 0.0 <= sp['fraction'] <= 1.0, f"Fraction {sp['fraction']} out of [0, 1]"


@pytest.mark.skip(reason="VesselState.subpopulations not yet implemented")
def test_ic50_shifts_monotonic():
    """IC50 shifts must be monotonically ordered: sensitive < typical < resistant."""
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test", "A549", 10000)
    vessel = vm.vessel_states["test"]

    shifts = [sp['ic50_shift'] for sp in vessel.subpopulations.values()]
    for i in range(len(shifts) - 1):
        assert shifts[i] <= shifts[i+1], f"IC50 shifts not monotonic: {shifts}"


@pytest.mark.skip(reason="VesselState.subpopulations not yet implemented")
def test_subpop_count_matches_structure():
    """Number of subpops must match expected structure (currently 3: sensitive/typical/resistant)."""
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test", "A549", 10000)
    vessel = vm.vessel_states["test"]

    # Current implementation has 3 subpops (configurable in future)
    assert len(vessel.subpopulations) == 3, f"Expected 3 subpops, got {len(vessel.subpopulations)}"
