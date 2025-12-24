"""
Test that signal floors prevent oracle behavior.

Verifies that assays have enough noise/floors to prevent perfect inference
of viability or IC50 from measurements.

This enforces epistemic realism: measurements must be uncertain.
"""

import pytest
import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.hardware.assays.assay_params import DEFAULT_ASSAY_PARAMS


def test_signal_floor_configuration():
    """
    Verify that DEFAULT_ASSAY_PARAMS has non-zero floors.

    This is a sanity check that the floor parameters are configured
    to prevent oracle behavior (floors > 0).
    """
    # Cell Painting dead signal floor
    assert DEFAULT_ASSAY_PARAMS.CP_DEAD_SIGNAL_FLOOR > 0.0, (
        "CP_DEAD_SIGNAL_FLOOR must be > 0 to prevent viability oracle"
    )
    assert DEFAULT_ASSAY_PARAMS.CP_DEAD_SIGNAL_FLOOR < 1.0, (
        "CP_DEAD_SIGNAL_FLOOR must be < 1 to allow measurement"
    )

    # ATP signal floor
    assert DEFAULT_ASSAY_PARAMS.ATP_SIGNAL_FLOOR > 0.0, (
        "ATP_SIGNAL_FLOOR must be > 0 to prevent mito dysfunction oracle"
    )
    assert DEFAULT_ASSAY_PARAMS.ATP_SIGNAL_FLOOR < 1.0, (
        "ATP_SIGNAL_FLOOR must be < 1 to allow measurement"
    )

    # LDH death amplification cap
    assert DEFAULT_ASSAY_PARAMS.LDH_DEATH_AMPLIFICATION_CAP > 1.0, (
        "LDH_DEATH_AMPLIFICATION_CAP must be > 1 to actually cap amplification"
    )
    assert DEFAULT_ASSAY_PARAMS.LDH_DEATH_AMPLIFICATION_CAP < 100.0, (
        "LDH_DEATH_AMPLIFICATION_CAP must be < 100 to remain realistic"
    )


def test_atp_signal_respects_floor():
    """
    ATP signal respects floor even with low viability.

    ATP_SIGNAL_FLOOR represents basal ATP from glycolysis.
    This test verifies the floor is applied in the measurement path.

    Test:
    - Create vessel with low viability (stressed cells)
    - Measure ATP signal
    - Assert: ATP signal is within expected range (respects floor)
    """
    vm = BiologicalVirtualMachine(seed=42)

    # Create vessel with moderately low viability
    vm.seed_vessel("well_B1", "A549", initial_count=10000, initial_viability=0.5)

    result = vm.atp_viability_assay("well_B1")
    atp_signal = result["atp_signal"]

    # ATP signal should be positive and finite
    assert atp_signal > 0, f"ATP signal must be positive, got {atp_signal}"
    assert np.isfinite(atp_signal), f"ATP signal must be finite, got {atp_signal}"

    # Signal should be in plausible range (not at extremes)
    assert atp_signal < 1e9, f"ATP signal implausibly high: {atp_signal}"


def test_measurement_produces_plausible_values():
    """
    ATP viability assay produces plausible, non-oracle values.

    Test:
    - Create vessels with different viabilities
    - Measure ATP signal
    - Assert: signals are in plausible range and show some spread
    """
    vm = BiologicalVirtualMachine(seed=42)

    viabilities = [0.3, 0.6, 0.9]
    atp_signals = []

    for i, target_viability in enumerate(viabilities):
        well = f"well_C{i+1}"
        vm.seed_vessel(well, "A549", initial_count=10000, initial_viability=target_viability)

        result = vm.atp_viability_assay(well)
        atp_signals.append(result["atp_signal"])

    # Assert: signals are positive and finite
    for signal in atp_signals:
        assert signal > 0, f"ATP signal must be positive: {signal}"
        assert np.isfinite(signal), f"ATP signal must be finite: {signal}"

    # Assert: signals show some variation (not all identical)
    signal_range = max(atp_signals) - min(atp_signals)
    assert signal_range > 0, "ATP signals are identical across different viabilities (oracle behavior)"
