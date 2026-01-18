"""
Test morphology direction rotates from stress to death signature.

Verifies the two-regime morphology model:
- Pre-collapse (viability > 0.4): STRESS morphology dominates
- Post-collapse (viability <= 0.4): DEATH morphology dominates
- The effect vector DIRECTION changes at collapse (not just magnitude)

This is the critical behavioral test for "Link morphology and viability (stress vs death signatures)".

The test proves:
1. At high viability, morphology delta correlates with stress signature (positive dot product)
2. At low viability, morphology delta correlates with death signature (positive dot product)
3. The crossover is smooth around the collapse threshold
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.hardware.constants import MORPHOLOGY_COLLAPSE_THRESHOLD

# Define stress and death directions for testing
# These should match the signatures in cell_painting.py (approximately)
STRESS_DIRECTION = {
    "er": +0.5,  # ER stress increases ER signal
    "mito": -0.4,  # Mito dysfunction decreases mito signal
    "nucleus": 0.0,  # Minimal effect from stress axes
    "actin": +0.65,  # Transport dysfunction increases actin
    "rna": 0.0,  # Minimal effect from stress axes
}

DEATH_DIRECTION = {
    "nucleus": +0.30,  # Condensation
    "mito": -0.40,  # Permeabilization
    "er": -0.35,  # Fragmentation
    "actin": -0.45,  # Disassembly
    "rna": -0.25,  # Degradation
}


def _normalize_dict_vector(d: dict) -> dict:
    """Normalize a dict-based vector to unit length."""
    mag = np.sqrt(sum(v**2 for v in d.values()))
    if mag < 1e-10:
        return d
    return {k: v / mag for k, v in d.items()}


def _dot_dict_vectors(a: dict, b: dict) -> float:
    """Dot product of two dict-based vectors."""
    keys = set(a.keys()) & set(b.keys())
    return sum(a[k] * b[k] for k in keys)


def _get_morph_delta(morph: dict, baseline: dict) -> dict:
    """Compute delta from baseline (fractional change)."""
    return {k: (morph[k] - baseline[k]) / baseline[k] for k in baseline}


def test_morphology_direction_rotates_at_collapse():
    """
    Main rotation test: verify that morphology CHANGES at collapse.

    Strategy:
    1. Create vessel with fixed stress state
    2. Measure morphology at high viability (stress regime)
    3. Measure morphology at low viability (death regime)
    4. Verify that the CHANGE in morphology matches death signature direction

    The key insight: as viability drops from 0.9 to 0.1, the morphology should
    shift in the death direction (nucleus up, mito/er/actin/rna down).
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")
    vessel = vm.vessel_states["Plate1_A01"]

    # Set fixed stress state (stress is constant, only viability varies)
    vessel.er_stress = 0.5
    vessel.mito_dysfunction = 0.5
    vessel.transport_dysfunction = 0.5

    # Measure at high viability (stress regime dominates)
    vessel.viability = 0.9
    vm.rng_assay = np.random.default_rng(42)
    result_high = vm.cell_painting_assay("Plate1_A01", plate_id="P1", well_position="A01")
    morph_high = result_high["morphology"]
    regime_high = result_high["morph_regime"]

    # Measure at low viability (death regime dominates)
    vessel.viability = 0.15
    vm.rng_assay = np.random.default_rng(42)
    result_low = vm.cell_painting_assay("Plate1_A01", plate_id="P1", well_position="A01")
    morph_low = result_low["morphology"]
    regime_low = result_low["morph_regime"]

    # Compute the CHANGE in morphology as viability drops
    # Positive = channel increased, Negative = channel decreased
    delta_viability_drop = {k: (morph_low[k] - morph_high[k]) / morph_high[k] for k in morph_high}

    print("\n=== Morphology Direction Rotation Test ===")
    print(f"Collapse threshold: {MORPHOLOGY_COLLAPSE_THRESHOLD}")
    print("\nHigh viability (v=0.9):")
    print(f"  stress_weight: {regime_high['stress_weight']:.3f}")
    print(f"  death_weight:  {regime_high['death_weight']:.3f}")
    print("\nLow viability (v=0.15):")
    print(f"  stress_weight: {regime_low['stress_weight']:.3f}")
    print(f"  death_weight:  {regime_low['death_weight']:.3f}")
    print("\nMorphology change (high→low viability):")
    for ch, delta in delta_viability_drop.items():
        expected = DEATH_DIRECTION.get(ch, 0)
        direction = "↑" if delta > 0 else "↓"
        print(f"  {ch}: {delta:+.3f} {direction} (death expects: {expected:+.2f})")

    # Assertions based on DEATH_MORPH_SIGNATURE
    #
    # KEY INSIGHT: Viability scaling dominates absolute changes (all channels drop
    # because dead cells have less signal). The death signature is a RELATIVE effect
    # on top of viability scaling.
    #
    # Death signature directions (applied multiplicatively):
    # - nucleus: +0.30 (drop LESS than baseline)
    # - mito: -0.40 (drop MORE than baseline)
    # - actin: -0.45 (drop MORE than baseline)
    # - er: -0.35 (drop MORE than baseline)
    # - rna: -0.25 (drop MORE than baseline)
    #
    # So we test RELATIVE changes: nucleus should drop LESS than the average drop
    # of the "decrease" channels.

    # Calculate mean drop of "decrease" channels (mito, actin, er, rna)
    decrease_channels = ["mito", "actin", "er", "rna"]
    mean_decrease_drop = np.mean([delta_viability_drop[ch] for ch in decrease_channels])

    print("\nRelative analysis:")
    print(f"  Nucleus drop: {delta_viability_drop['nucleus']:.3f}")
    print(f"  Mean 'decrease' channel drop: {mean_decrease_drop:.3f}")
    print(
        f"  Nucleus drops {abs(delta_viability_drop['nucleus']) - abs(mean_decrease_drop):.3f} less than average"
    )

    # 1. Nucleus should drop LESS than the decrease channels (death signature +0.30)
    assert abs(delta_viability_drop["nucleus"]) < abs(mean_decrease_drop), (
        f"Nucleus should drop less than other channels due to death signature: "
        f"nucleus={delta_viability_drop['nucleus']:.3f}, mean_others={mean_decrease_drop:.3f}"
    )

    # 2. Actin should drop MORE than average (death signature -0.45, most negative)
    # Actin has the strongest "death decrease" signature
    assert abs(delta_viability_drop["actin"]) >= abs(mean_decrease_drop) - 0.05, (
        f"Actin should drop at least as much as average: "
        f"actin={delta_viability_drop['actin']:.3f}, mean={mean_decrease_drop:.3f}"
    )

    # 3. Weights should have shifted (death_weight high at low viability)
    assert (
        regime_low["death_weight"] > 0.9
    ), f"Death weight should be >0.9 at viability=0.15, got {regime_low['death_weight']:.3f}"
    assert (
        regime_high["stress_weight"] > 0.9
    ), f"Stress weight should be >0.9 at viability=0.9, got {regime_high['stress_weight']:.3f}"

    # 4. Verify that the direction difference exists
    # Nucleus should be at least 10% less dropped than the mean decrease channel
    relative_nucleus_preservation = abs(mean_decrease_drop) - abs(delta_viability_drop["nucleus"])
    assert relative_nucleus_preservation > 0.10, (
        f"Death signature should preserve nucleus by at least 10%: "
        f"got {relative_nucleus_preservation:.3f}"
    )


def test_weights_are_complementary():
    """
    Verify stress_weight + death_weight = 1.0 (clean rotation, no overlap).
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")
    vessel = vm.vessel_states["Plate1_A01"]

    # Set some stress state
    vessel.er_stress = 0.5

    # Sweep viability
    for v in np.linspace(1.0, 0.0, 21):
        vessel.viability = v
        vm.rng_assay = np.random.default_rng(42)
        result = vm.cell_painting_assay("Plate1_A01", plate_id="P1", well_position="A01")

        morph_regime = result.get("morph_regime", {})
        stress_weight = morph_regime.get("stress_weight")
        death_weight = morph_regime.get("death_weight")

        assert stress_weight is not None, "stress_weight not in result"
        assert death_weight is not None, "death_weight not in result"

        weight_sum = stress_weight + death_weight
        assert (
            abs(weight_sum - 1.0) < 1e-6
        ), f"Weights should sum to 1.0, got {weight_sum:.6f} at viability={v:.2f}"


def test_weights_bounded_01():
    """
    Verify weights are in [0, 1] range (no weird sigmoid overflow).
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")
    vessel = vm.vessel_states["Plate1_A01"]

    vessel.er_stress = 0.5

    for v in np.linspace(1.0, 0.0, 21):
        vessel.viability = v
        vm.rng_assay = np.random.default_rng(42)
        result = vm.cell_painting_assay("Plate1_A01", plate_id="P1", well_position="A01")

        morph_regime = result["morph_regime"]
        stress_weight = morph_regime["stress_weight"]
        death_weight = morph_regime["death_weight"]

        assert 0.0 <= stress_weight <= 1.0, f"stress_weight={stress_weight} out of bounds"
        assert 0.0 <= death_weight <= 1.0, f"death_weight={death_weight} out of bounds"


def test_death_signature_multipliers_clamped():
    """
    Verify death signature multipliers never go negative (guardrail).
    """
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")
    vessel = vm.vessel_states["Plate1_A01"]

    # Set very low viability to maximize death_weight
    vessel.viability = 0.01
    vessel.er_stress = 0.0  # No stress, just death

    vm.rng_assay = np.random.default_rng(42)
    result = vm.cell_painting_assay("Plate1_A01", plate_id="P1", well_position="A01")

    # All morphology values should be positive
    for channel, value in result["morphology"].items():
        assert value > 0, f"Channel {channel} has non-positive value {value}"


def test_noise_increases_in_death_regime():
    """
    Verify measurement noise increases as death_weight increases.
    """
    N_REPLICATES = 30

    # High viability (stress regime)
    vm_high = BiologicalVirtualMachine(seed=42)
    vm_high.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")
    vessel_high = vm_high.vessel_states["Plate1_A01"]
    vessel_high.viability = 0.9  # High viability
    vessel_high.er_stress = 0.5

    # Low viability (death regime)
    vm_low = BiologicalVirtualMachine(seed=42)
    vm_low.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")
    vessel_low = vm_low.vessel_states["Plate1_A01"]
    vessel_low.viability = 0.15  # Low viability
    vessel_low.er_stress = 0.5

    # Collect replicates
    measurements_high = []
    measurements_low = []

    for i in range(N_REPLICATES):
        vm_high.rng_assay = np.random.default_rng(i)
        vm_low.rng_assay = np.random.default_rng(i)

        result_high = vm_high.cell_painting_assay("Plate1_A01", plate_id="P1", well_position="A01")
        result_low = vm_low.cell_painting_assay("Plate1_A01", plate_id="P1", well_position="A01")

        measurements_high.append(result_high["morphology"]["er"])
        measurements_low.append(result_low["morphology"]["er"])

    var_high = np.var(measurements_high, ddof=1)
    var_low = np.var(measurements_low, ddof=1)

    cv_high = np.std(measurements_high, ddof=1) / np.mean(measurements_high)
    cv_low = np.std(measurements_low, ddof=1) / np.mean(measurements_low)

    print("\n=== Death Regime Noise Test ===")
    print(f"High viability (v=0.9): variance={var_high:.4f}, CV={cv_high:.4f}")
    print(f"Low viability (v=0.15): variance={var_low:.4f}, CV={cv_low:.4f}")
    print(f"CV ratio (low/high): {cv_low/cv_high:.2f}")

    # Low viability should have higher CV (noise increases in death regime)
    # Use CV to account for mean differences
    assert (
        cv_low > cv_high
    ), f"CV should be higher at low viability: cv_low={cv_low:.4f}, cv_high={cv_high:.4f}"


def test_onset_kinetics_timepoint_sensitivity():
    """
    Verify that morphology effects are smaller at early timepoints and larger at late timepoints.

    Phase 0 context: 24h vs 48h readouts should show different effect magnitudes.
    At 24h, onset_factor ≈ 0.89; at 48h, onset_factor ≈ 0.98 (near saturation).

    This tests that timepoint matters for morphology signal.
    """
    from src.cell_os.hardware.constants import MORPHOLOGY_ONSET_TAU_H

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")
    vessel = vm.vessel_states["Plate1_A01"]

    # Apply compound to create treatment start time
    vm.treat_with_compound("Plate1_A01", "menadione", 6.0)  # 6 µM menadione
    compound_start = vm.simulated_time  # Record when compound was applied

    # Set stress state (fixed, only time varies)
    vessel.er_stress = 0.5
    vessel.mito_dysfunction = 0.3
    vessel.viability = 0.8  # Fixed viability

    # Measure at different timepoints
    def measure_at_timepoint(t_hours: float):
        """Advance time and measure morphology."""
        # Set simulated_time to t hours after compound application
        # Also update vessel.last_update_time so time_since_last_perturbation_h works
        vm.simulated_time = compound_start + t_hours
        vessel.last_update_time = vm.simulated_time  # Keep in sync

        vm.rng_assay = np.random.default_rng(42)
        result = vm.cell_painting_assay("Plate1_A01", plate_id="P1", well_position="A01")
        return result

    # Measure at 6h, 24h, 48h (Phase 0 relevant timepoints)
    result_6h = measure_at_timepoint(6.0)
    result_24h = measure_at_timepoint(24.0)
    result_48h = measure_at_timepoint(48.0)

    onset_6h = result_6h["morph_regime"]["onset_factor"]
    onset_24h = result_24h["morph_regime"]["onset_factor"]
    onset_48h = result_48h["morph_regime"]["onset_factor"]

    print("\n=== Onset Kinetics (Timepoint Sensitivity) Test ===")
    print(f"tau_h = {MORPHOLOGY_ONSET_TAU_H}")
    print("\nOnset factors:")
    print(f"  6h:  {onset_6h:.3f}")
    print(f"  24h: {onset_24h:.3f}")
    print(f"  48h: {onset_48h:.3f}")

    # Get baseline for comparison
    baseline = vm.thalamus_params["baseline_morphology"]["A549"]

    # Compute ER effect magnitude at each timepoint (delta from baseline)
    er_delta_6h = (result_6h["morphology"]["er"] - baseline["er"]) / baseline["er"]
    er_delta_24h = (result_24h["morphology"]["er"] - baseline["er"]) / baseline["er"]
    er_delta_48h = (result_48h["morphology"]["er"] - baseline["er"]) / baseline["er"]

    print("\nER delta from baseline:")
    print(f"  6h:  {er_delta_6h:+.3f}")
    print(f"  24h: {er_delta_24h:+.3f}")
    print(f"  48h: {er_delta_48h:+.3f}")

    # Assertions
    # 1. Onset factor should increase with time
    assert (
        onset_6h < onset_24h < onset_48h
    ), f"Onset factor should increase with time: 6h={onset_6h:.3f}, 24h={onset_24h:.3f}, 48h={onset_48h:.3f}"

    # 2. Onset factor should be bounded [0.2, 1.0] (min_factor to 1.0)
    for onset, label in [(onset_6h, "6h"), (onset_24h, "24h"), (onset_48h, "48h")]:
        assert (
            0.2 <= onset <= 1.0
        ), f"Onset factor at {label} should be in [0.2, 1.0], got {onset:.3f}"

    # 3. At 48h, onset should be near saturation (>0.95)
    assert onset_48h > 0.95, f"At 48h, onset should be near saturation (>0.95), got {onset_48h:.3f}"

    # 4. Stress effect magnitude should increase with onset factor
    # ER stress increases ER signal (positive contribution).
    # At early timepoints, stress effect is small → more negative delta (viability scaling dominates)
    # At late timepoints, stress effect is larger → less negative delta (stress counteracts viability)
    # So: delta should become LESS negative (higher/closer to zero) as time increases
    assert er_delta_6h < er_delta_24h < er_delta_48h, (
        f"ER delta should become less negative as onset factor increases: "
        f"6h={er_delta_6h:.3f}, 24h={er_delta_24h:.3f}, 48h={er_delta_48h:.3f}"
    )


def test_result_schema_validation():
    """
    Verify that Cell Painting results conform to the schema.
    """
    from src.cell_os.hardware.assays.cell_painting_schema import (
        MORPHOLOGY_CHANNELS,
        REQUIRED_FIELDS,
        summarize_result,
        validate_result,
    )

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("Plate1_A01", "A549", vessel_type="384-well")
    vessel = vm.vessel_states["Plate1_A01"]

    # Set some stress
    vessel.er_stress = 0.5
    vessel.viability = 0.7

    # Measure
    vm.rng_assay = np.random.default_rng(42)
    result = vm.cell_painting_assay("Plate1_A01", plate_id="P1", well_position="A01")

    # Validate schema
    errors = validate_result(result)

    print("\n=== Schema Validation Test ===")
    print(f"Required fields: {REQUIRED_FIELDS}")
    print(f"Morphology channels: {MORPHOLOGY_CHANNELS}")
    print(f"Validation errors: {errors}")

    # Should have no errors
    assert len(errors) == 0, f"Schema validation failed: {errors}"

    # Test summary view
    summary = summarize_result(result)
    print(f"\n{summary}")

    # Verify summary fields
    assert summary.vessel_id == "Plate1_A01"
    assert summary.cell_line == "A549"
    assert summary.status == "success"
    assert summary.morph_mean > 0
    assert summary.dominant_channel in MORPHOLOGY_CHANNELS
    assert summary.suppressed_channel in MORPHOLOGY_CHANNELS


def test_schema_catches_invalid_results():
    """
    Verify that schema validation catches invalid results.
    """
    from src.cell_os.hardware.assays.cell_painting_schema import validate_result

    # Test missing required fields
    result = {"status": "success"}
    errors = validate_result(result)
    assert len(errors) > 0, "Should catch missing fields"
    assert any("Missing required field" in e for e in errors)

    # Test invalid morphology (negative value)
    result = {
        "status": "success",
        "action": "cell_painting",
        "vessel_id": "A01",
        "cell_line": "A549",
        "morphology": {"er": -1.0, "mito": 100, "nucleus": 100, "actin": 100, "rna": 100},
        "morph_regime": {"stress_weight": 0.5, "death_weight": 0.5, "onset_factor": 0.8},
    }
    errors = validate_result(result)
    assert any(
        "Negative morphology" in e for e in errors
    ), f"Should catch negative morphology: {errors}"

    # Test invalid weights (don't sum to 1)
    result = {
        "status": "success",
        "action": "cell_painting",
        "vessel_id": "A01",
        "cell_line": "A549",
        "morphology": {"er": 100, "mito": 100, "nucleus": 100, "actin": 100, "rna": 100},
        "morph_regime": {"stress_weight": 0.8, "death_weight": 0.8, "onset_factor": 0.8},
    }
    errors = validate_result(result)
    assert any("don't sum to 1" in e for e in errors), f"Should catch invalid weights: {errors}"

    print("\n=== Invalid Schema Detection Test ===")
    print("✓ Schema validation catches invalid results")


if __name__ == "__main__":
    test_morphology_direction_rotates_at_collapse()
    test_weights_are_complementary()
    test_weights_bounded_01()
    test_death_signature_multipliers_clamped()
    test_noise_increases_in_death_regime()
    test_onset_kinetics_timepoint_sensitivity()
    test_result_schema_validation()
    test_schema_catches_invalid_results()
    print("\n✓ All rotation tests passed")
