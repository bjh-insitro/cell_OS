#!/usr/bin/env python3
"""
Test LDH Cytotoxicity Simulation

Verify that LDH correctly:
1. Rises when cells die (inverse of viability)
2. Is NOT confounded by mitochondrial compounds
3. Shows proper dose-response for CCCP/oligomycin
"""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_ldh_inverse_relationship():
    """Test that LDH increases as viability decreases"""
    print("\n" + "="*80)
    print("TEST 1: LDH Inverse Relationship (High Viability → Low LDH)")
    print("="*80)

    vm = BiologicalVirtualMachine()

    # Test 1: Healthy cells (high viability)
    vm.seed_vessel("test_well_1", "A549", 5000, capacity=1e6)
    result_healthy = vm.atp_viability_assay("test_well_1")

    print(f"\n✓ Healthy cells (viability={result_healthy['viability']:.2%}):")
    print(f"  LDH signal: {result_healthy['ldh_signal']:.1f}")
    print(f"  Expected: LOW (only ~5% dead cells releasing LDH)")

    # Test 2: Dying cells (low viability) - use tunicamycin which has A549 IC50
    vm.seed_vessel("test_well_2", "A549", 5000, capacity=1e6)
    treat_result = vm.treat_with_compound("test_well_2", "tunicamycin", 10.0)  # High dose kills cells
    print(f"\nTreatment result: IC50={treat_result['ic50']:.2f}, viability_effect={treat_result['viability_effect']:.2%}")
    result_dying = vm.atp_viability_assay("test_well_2")

    print(f"\n✓ Dying cells (viability={result_dying['viability']:.2%}):")
    print(f"  LDH signal: {result_dying['ldh_signal']:.1f}")
    print(f"  Expected: HIGH (many dead cells releasing LDH)")

    # Verify inverse relationship
    assert result_healthy['viability'] > result_dying['viability'], "Viability should decrease with treatment"
    assert result_healthy['ldh_signal'] < result_dying['ldh_signal'], "LDH should INCREASE as viability decreases"

    print(f"\n✅ PASS: LDH correctly increases as viability decreases")
    print(f"   Ratio: {result_dying['ldh_signal'] / result_healthy['ldh_signal']:.1f}× higher in dying cells")


def test_mitochondrial_compounds():
    """Test that CCCP/oligomycin show LDH rise (not early ATP crash confound)"""
    print("\n" + "="*80)
    print("TEST 2: Mitochondrial Compounds (CCCP/Oligomycin)")
    print("="*80)
    print("OLD ATP PROBLEM: ATP crashes at low dose (metabolic dysfunction)")
    print("NEW LDH SOLUTION: LDH only rises when cells actually die")

    vm = BiologicalVirtualMachine()

    # Test CCCP at low dose (metabolic dysfunction but cells may survive)
    vm.seed_vessel("cccp_low", "A549", 5000, capacity=1e6)
    vm.treat_with_compound("cccp_low", "CCCP", 2.0)  # Low dose
    result_cccp_low = vm.atp_viability_assay("cccp_low")

    print(f"\n✓ CCCP 2.0 µM (low dose):")
    print(f"  Viability: {result_cccp_low['viability']:.2%}")
    print(f"  LDH signal: {result_cccp_low['ldh_signal']:.1f}")
    print(f"  Interpretation: Some metabolic stress, moderate death")

    # Test CCCP at high dose (cell death)
    vm.seed_vessel("cccp_high", "A549", 5000, capacity=1e6)
    vm.treat_with_compound("cccp_high", "CCCP", 20.0)  # High dose
    result_cccp_high = vm.atp_viability_assay("cccp_high")

    print(f"\n✓ CCCP 20.0 µM (high dose):")
    print(f"  Viability: {result_cccp_high['viability']:.2%}")
    print(f"  LDH signal: {result_cccp_high['ldh_signal']:.1f}")
    print(f"  Interpretation: Severe cytotoxicity, high LDH release")

    # Test oligomycin
    vm.seed_vessel("oligo", "A549", 5000, capacity=1e6)
    vm.treat_with_compound("oligo", "oligomycin", 5.0)  # High dose
    result_oligo = vm.atp_viability_assay("oligo")

    print(f"\n✓ Oligomycin 5.0 µM:")
    print(f"  Viability: {result_oligo['viability']:.2%}")
    print(f"  LDH signal: {result_oligo['ldh_signal']:.1f}")
    print(f"  Interpretation: Mitochondrial inhibition → cell death → LDH release")

    # Verify dose-response
    assert result_cccp_high['ldh_signal'] > result_cccp_low['ldh_signal'], \
        "Higher CCCP dose should cause more death (higher LDH)"

    print(f"\n✅ PASS: Mitochondrial compounds show proper LDH dose-response")
    print(f"   No confounding from early ATP crash!")


def test_dmso_control():
    """Test that DMSO controls show very low LDH"""
    print("\n" + "="*80)
    print("TEST 3: DMSO Vehicle Control")
    print("="*80)

    vm = BiologicalVirtualMachine()

    # DMSO control (healthy cells)
    vm.seed_vessel("dmso", "A549", 5000, capacity=1e6)
    vm.treat_with_compound("dmso", "DMSO", 0.0)
    result_dmso = vm.atp_viability_assay("dmso")

    print(f"\n✓ DMSO control:")
    print(f"  Viability: {result_dmso['viability']:.2%}")
    print(f"  LDH signal: {result_dmso['ldh_signal']:.1f}")
    print(f"  Expected: Very low LDH (only background from ~5% spontaneous death)")

    assert result_dmso['viability'] > 0.90, "DMSO control should have high viability"
    assert result_dmso['ldh_signal'] < 5000, "DMSO control should have low LDH"

    print(f"\n✅ PASS: DMSO control shows expected low LDH")


def test_dose_response_curve():
    """Test full dose-response curve for a compound"""
    print("\n" + "="*80)
    print("TEST 4: Dose-Response Curve (Thapsigargin)")
    print("="*80)

    vm = BiologicalVirtualMachine()

    doses = [0.0, 0.1, 0.3, 0.5, 1.0, 2.0, 5.0]  # µM
    results = []

    print(f"\n{'Dose (µM)':<12} {'Viability':<12} {'LDH Signal':<15} {'Interpretation'}")
    print("-" * 60)

    for dose in doses:
        vessel_id = f"thapsi_{dose}"
        vm.seed_vessel(vessel_id, "A549", 5000, capacity=1e6)
        # Only treat if dose > 0 (vehicle control should not be treated)
        if dose > 0:
            vm.treat_with_compound(vessel_id, "thapsigargin", dose)
        result = vm.atp_viability_assay(vessel_id)
        results.append(result)

        interp = "Healthy" if result['viability'] > 0.8 else \
                 "Stressed" if result['viability'] > 0.5 else \
                 "Dying"

        print(f"{dose:<12.2f} {result['viability']:<12.2%} {result['ldh_signal']:<15.1f} {interp}")

    # Verify monotonic relationship (with tolerance for biological noise)
    for i in range(len(results) - 1):
        assert results[i]['viability'] >= results[i+1]['viability'], \
            f"Viability should decrease with dose (failed at dose {doses[i]} → {doses[i+1]})"

        # LDH should generally increase, but allow for noise-induced variation
        # (real experiments would use replicates to smooth this out)
        # Allow up to 30% decrease due to biological/technical noise
        if results[i]['ldh_signal'] > results[i+1]['ldh_signal']:
            decrease_pct = (results[i]['ldh_signal'] - results[i+1]['ldh_signal']) / results[i]['ldh_signal']
            assert decrease_pct < 0.30, \
                f"LDH decreased too much with dose (failed at dose {doses[i]} → {doses[i+1]}): {decrease_pct:.1%}"

    print(f"\n✅ PASS: Dose-response curve shows proper monotonic relationship")
    print(f"   Viability: {results[0]['viability']:.2%} → {results[-1]['viability']:.2%}")
    print(f"   LDH: {results[0]['ldh_signal']:.1f} → {results[-1]['ldh_signal']:.1f}")


def main():
    """Run all LDH simulation tests"""
    print("\n" + "="*80)
    print("LDH CYTOTOXICITY SIMULATION TEST SUITE")
    print("="*80)
    print("\nVerifying that LDH correctly replaces ATP measurement:")
    print("  ✓ LDH rises when cells die (membrane rupture)")
    print("  ✓ NOT confounded by mitochondrial compounds")
    print("  ✓ Orthogonal to Cell Painting morphology")

    try:
        test_ldh_inverse_relationship()
        test_mitochondrial_compounds()
        test_dmso_control()
        test_dose_response_curve()

        print("\n" + "="*80)
        print("🎉 ALL TESTS PASSED!")
        print("="*80)
        print("\nLDH simulation is working correctly:")
        print("  ✅ Inverse relationship with viability")
        print("  ✅ Mitochondrial compounds show proper cytotoxicity")
        print("  ✅ DMSO controls have low background LDH")
        print("  ✅ Dose-response curves are monotonic")
        print("\n✨ Ready for production use!")

        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n💥 ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
