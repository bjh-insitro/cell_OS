"""
Phase 2D.1: Contamination Events - Integration Test

Validates core functionality without running full identifiability suite.
Tests: backward compat, event occurrence, determinism, morphology signature.
"""

import sys
import numpy as np
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False


CONTAM_CONFIG_STRESS = {
    'enabled': True,
    'baseline_rate_per_vessel_day': 0.05,  # 10× baseline
    'type_probs': {'bacterial': 0.5, 'fungal': 0.2, 'mycoplasma': 0.3},
    'severity_lognormal_cv': 0.5,
    'min_severity': 0.25,
    'max_severity': 3.0,
    'phase_params': {
        'bacterial': {'latent_h': 6, 'arrest_h': 6, 'death_rate_per_h': 0.4},
        'fungal': {'latent_h': 12, 'arrest_h': 12, 'death_rate_per_h': 0.2},
        'mycoplasma': {'latent_h': 24, 'arrest_h': 48, 'death_rate_per_h': 0.05},
    },
    'growth_arrest_multiplier': 0.05,
    'morphology_signature_strength': 1.0,
}


def test_backward_compatibility():
    """Contamination disabled by default (backward compat)."""
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel('test_A01', 'A549', vessel_type='96-well', initial_count=5000)
    vm.advance_time(24.0)

    vessel = vm.vessel_states['test_A01']
    assert vessel.contaminated == False
    assert vessel.death_contamination == 0.0


def test_events_occur_when_enabled():
    """Events occur when contamination enabled."""
    vm = BiologicalVirtualMachine(seed=42)
    vm.contamination_config = CONTAM_CONFIG_STRESS

    vessel_ids = [f"Plate1_{chr(65 + i // 12)}{(i % 12) + 1:02d}" for i in range(16)]
    for vessel_id in vessel_ids:
        vm.seed_vessel(vessel_id, "A549", vessel_type="96-well", initial_count=5000)

    vm.advance_time(168.0)  # 7 days

    contaminated = [v for v in vm.vessel_states.values() if v.contaminated]
    assert len(contaminated) >= 1, "Expected at least 1 event with 10× rate"


def test_determinism():
    """Same seed → identical event identity."""
    vessel_ids = [f"Plate1_{chr(65 + i // 12)}{(i % 12) + 1:02d}" for i in range(4)]

    # Run 1
    vm1 = BiologicalVirtualMachine(seed=999)
    vm1.contamination_config = CONTAM_CONFIG_STRESS
    for vessel_id in vessel_ids:
        vm1.seed_vessel(vessel_id, "A549", vessel_type="96-well", initial_count=5000)
    vm1.advance_time(168.0)

    # Run 2
    vm2 = BiologicalVirtualMachine(seed=999)
    vm2.contamination_config = CONTAM_CONFIG_STRESS
    for vessel_id in vessel_ids:
        vm2.seed_vessel(vessel_id, "A549", vessel_type="96-well", initial_count=5000)
    vm2.advance_time(168.0)

    # Compare event identity
    for vessel_id in vessel_ids:
        v1 = vm1.vessel_states[vessel_id]
        v2 = vm2.vessel_states[vessel_id]

        assert v1.contaminated == v2.contaminated
        if v1.contaminated:
            assert v1.contamination_type == v2.contamination_type
            assert v1.contamination_onset_h == v2.contamination_onset_h
            assert v1.contamination_severity == v2.contamination_severity


def test_morphology_signature():
    """Contaminated vessels have different morphology."""
    vm = BiologicalVirtualMachine(seed=42)
    vm.contamination_config = CONTAM_CONFIG_STRESS

    vessel_ids = [f"Plate1_{chr(65 + i // 12)}{(i % 12) + 1:02d}" for i in range(16)]
    for vessel_id in vessel_ids:
        vm.seed_vessel(vessel_id, "A549", vessel_type="96-well", initial_count=5000)

    vm.advance_time(168.0)

    contaminated = [v for v in vm.vessel_states.values() if v.contaminated]
    clean = [v for v in vm.vessel_states.values() if not v.contaminated]

    if len(contaminated) > 0 and len(clean) > 0:
        morph_contam = vm.cell_painting_assay(contaminated[0].vessel_id, well_position='A01')
        morph_clean = vm.cell_painting_assay(clean[0].vessel_id, well_position='B01')

        if morph_contam['status'] == 'success' and morph_clean['status'] == 'success':
            m_c = morph_contam['morphology']
            m_cl = morph_clean['morphology']

            # Morphology should differ (signature is deterministic)
            diff = sum(abs(m_c[k] - m_cl[k]) for k in ['er', 'mito', 'nucleus', 'actin', 'rna'])
            assert diff > 0.1, "Expected morphology signature to differ"


if __name__ == "__main__":
    if HAS_PYTEST:
        pytest.main([__file__, "-v"])
    else:
        print("Running integration tests manually...")
        tests = [
            ("Backward compatibility", test_backward_compatibility),
            ("Events occur when enabled", test_events_occur_when_enabled),
            ("Determinism", test_determinism),
            ("Morphology signature", test_morphology_signature),
        ]

        passed = 0
        for name, test_func in tests:
            print(f"\n=== {name} ===")
            try:
                test_func()
                print("✅ PASS")
                passed += 1
            except Exception as e:
                print(f"❌ FAIL: {e}")

        print(f"\nResults: {passed}/{len(tests)} passed")
        sys.exit(0 if passed == len(tests) else 1)
