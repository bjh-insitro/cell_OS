"""
Quick test for Phase 5 population heterogeneity implementation.

Tests:
1. Subpopulations initialized correctly
2. Per-subpopulation stress dynamics with shifted IC50
3. Mixture width captures heterogeneity
4. Death distributed proportionally to stress
"""

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_subpopulation_initialization():
    """Verify 3-bucket subpopulation model is initialized."""
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test_vessel", "A549", initial_count=1e6)

    vessel = vm.vessel_states["test_vessel"]

    # Check subpopulations exist
    assert 'sensitive' in vessel.subpopulations
    assert 'typical' in vessel.subpopulations
    assert 'resistant' in vessel.subpopulations

    # Check fractions sum to 1.0
    total_fraction = sum(subpop['fraction'] for subpop in vessel.subpopulations.values())
    assert abs(total_fraction - 1.0) < 1e-6

    # Check IC50 shifts are correct
    assert vessel.subpopulations['sensitive']['ic50_shift'] == 0.5  # More sensitive
    assert vessel.subpopulations['typical']['ic50_shift'] == 1.0  # Normal
    assert vessel.subpopulations['resistant']['ic50_shift'] == 2.0  # More resistant

    # Check initial viabilities are equal
    for subpop in vessel.subpopulations.values():
        assert abs(subpop['viability'] - 0.98) < 1e-6

    print("✓ Subpopulation initialization: PASS")


def test_heterogeneous_stress_dynamics():
    """Verify stress dynamics differ across subpopulations."""
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test_vessel", "A549", initial_count=1e6)

    # Apply weak ER stress compound (tunicamycin)
    vm.treat_with_compound("test_vessel", "tunicamycin", dose_uM=0.5, potency_scalar=0.7)

    vessel = vm.vessel_states["test_vessel"]

    # Advance time to build up stress
    vm.advance_time(12.0)

    # Check that subpopulations have DIFFERENT stress levels
    sensitive_stress = vessel.subpopulations['sensitive']['er_stress']
    typical_stress = vessel.subpopulations['typical']['er_stress']
    resistant_stress = vessel.subpopulations['resistant']['er_stress']

    print(f"ER stress @ 12h: sensitive={sensitive_stress:.3f}, typical={typical_stress:.3f}, resistant={resistant_stress:.3f}")

    # Sensitive should be most stressed (lowest IC50)
    assert sensitive_stress > typical_stress
    assert typical_stress > resistant_stress

    # Check mixture width is non-zero (captures heterogeneity)
    mixture_width = vessel.get_mixture_width('er_stress')
    print(f"Mixture width: {mixture_width:.3f}")
    assert mixture_width > 0.01  # Should have meaningful spread

    print("✓ Heterogeneous stress dynamics: PASS")


def test_mixture_properties():
    """Verify mixture properties compute correctly."""
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test_vessel", "A549", initial_count=1e6)

    vessel = vm.vessel_states["test_vessel"]

    # Check initial mixture viability matches aggregate
    initial_mixture = vessel.viability_mixture
    assert abs(initial_mixture - 0.98) < 1e-6

    # Apply compound and let stress build
    vm.treat_with_compound("test_vessel", "tunicamycin", dose_uM=1.0, potency_scalar=0.7)
    vm.advance_time(24.0)

    # Check that mixture viability is weighted average
    manual_mixture = sum(
        subpop['fraction'] * subpop['viability']
        for subpop in vessel.subpopulations.values()
    )
    computed_mixture = vessel.viability_mixture
    assert abs(manual_mixture - computed_mixture) < 1e-6

    print(f"Viability after 24h: mixture={computed_mixture:.3f}")
    print("✓ Mixture properties: PASS")


def test_differential_death():
    """Verify stressed subpopulations die more than unstressed ones."""
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test_vessel", "A549", initial_count=1e6)

    # Apply very gentle dose to create differential stress (not kill everyone)
    vm.treat_with_compound("test_vessel", "tunicamycin", dose_uM=0.3, potency_scalar=0.5, toxicity_scalar=1.0)

    vessel = vm.vessel_states["test_vessel"]

    # Advance time to build stress and induce some death (shorter to avoid total wipeout)
    vm.advance_time(24.0)

    # Check that sensitive subpopulation has lower viability
    sensitive_viab = vessel.subpopulations['sensitive']['viability']
    typical_viab = vessel.subpopulations['typical']['viability']
    resistant_viab = vessel.subpopulations['resistant']['viability']

    print(f"Viability @ 24h: sensitive={sensitive_viab:.3f}, typical={typical_viab:.3f}, resistant={resistant_viab:.3f}")

    # Sensitive should have died more (lowest viability)
    assert sensitive_viab < typical_viab
    assert typical_viab < resistant_viab

    # Aggregate viability should be mixture
    agg_viab = vessel.viability
    mixture_viab = vessel.viability_mixture
    print(f"Aggregate viability: {agg_viab:.3f}, mixture: {mixture_viab:.3f}")

    # Should match closely (within 5%)
    assert abs(agg_viab - mixture_viab) / mixture_viab < 0.05

    print("✓ Differential death: PASS")


if __name__ == "__main__":
    test_subpopulation_initialization()
    test_heterogeneous_stress_dynamics()
    test_mixture_properties()
    test_differential_death()

    print("\n✅ All heterogeneity tests PASSED")
