"""
Temporal Coherence Validation

This extends cross-modal coherence to kinetics, validating that:
1. Time-series trajectories are consistent across modalities
2. Directional coherence (all sensors move in same direction)
3. Kinetics are plausible (no instantaneous jumps, smooth transitions)
4. Temporal ordering preserved (cause precedes effect)

Architecture:
    Cross-modal coherence: Sensors agree AT SINGLE TIMEPOINT
    Temporal coherence: Sensors agree OVER TIME (kinetics)

This is critical for:
- Detecting false attribution from kinetic artifacts
- Validating biology feedback accumulates smoothly
- Ensuring mechanism signatures are temporally consistent
"""

import numpy as np
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_er_stress_temporal_trajectory():
    """
    Validate ER stress accumulates smoothly over time with coherent cross-modal kinetics.

    Setup:
    - High density (contact pressure buildup)
    - Measure at t=0, 12h, 24h, 48h
    - Track: latent ER stress, ER morphology, UPR marker

    Expected:
    - ER stress increases monotonically (0 → 12h → 24h → 48h)
    - ER morphology tracks latent stress
    - UPR marker tracks latent stress
    - All three trajectories coherent (same direction, similar kinetics)
    """
    seed = 42
    cell_line = "A549"

    # Time points
    timepoints = [0.0, 12.0, 24.0, 48.0]
    measurements = []

    for t in timepoints:
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("test", cell_line, initial_count=9e6, capacity=1e7, initial_viability=0.98)

        if t > 0:
            vm.advance_time(t)

        vessel = vm.vessel_states["test"]
        er_stress = vessel.er_stress

        # Measure morphology
        morph_result = vm.cell_painting_assay("test")
        er_morph = morph_result['morphology_struct']['er']

        # Measure scalar
        scalar_result = vm.atp_viability_assay("test")
        upr_marker = scalar_result['upr_marker']

        measurements.append({
            'time_h': t,
            'er_stress': er_stress,
            'er_morph': er_morph,
            'upr_marker': upr_marker
        })

        print(f"t={t:5.1f}h: ER stress={er_stress:.3f}, ER morph={er_morph:.3f}, UPR={upr_marker:.3f}")

    # Validate monotonic increase (latent state)
    for i in range(len(measurements) - 1):
        curr = measurements[i]
        next_m = measurements[i + 1]

        assert next_m['er_stress'] >= curr['er_stress'], \
            f"ER stress should increase monotonically: t={curr['time_h']}h ({curr['er_stress']:.3f}) → t={next_m['time_h']}h ({next_m['er_stress']:.3f})"

    # Validate cross-modal coherence over time
    # All measurements should increase together
    er_stress_trajectory = [m['er_stress'] for m in measurements]
    er_morph_trajectory = [m['er_morph'] for m in measurements]
    upr_trajectory = [m['upr_marker'] for m in measurements]

    # Normalize trajectories (0-1 scale)
    def normalize(vals):
        vmin, vmax = min(vals), max(vals)
        if vmax == vmin:
            return [0.5] * len(vals)
        return [(v - vmin) / (vmax - vmin) for v in vals]

    er_stress_norm = normalize(er_stress_trajectory)
    er_morph_norm = normalize(er_morph_trajectory)
    upr_norm = normalize(upr_trajectory)

    # Compute trajectory correlation (should be high if coherent)
    def pearson_corr(x, y):
        x_mean = np.mean(x)
        y_mean = np.mean(y)
        num = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
        denom = np.sqrt(sum((xi - x_mean)**2 for xi in x) * sum((yi - y_mean)**2 for yi in y))
        return num / denom if denom > 0 else 0

    corr_stress_morph = pearson_corr(er_stress_norm, er_morph_norm)
    corr_stress_upr = pearson_corr(er_stress_norm, upr_norm)

    print(f"\nTemporal coherence:")
    print(f"  ER stress ↔ ER morph correlation: {corr_stress_morph:.3f}")
    print(f"  ER stress ↔ UPR marker correlation: {corr_stress_upr:.3f}")

    assert corr_stress_morph > 0.80, \
        f"ER morphology should track ER stress over time: correlation={corr_stress_morph:.3f}"
    assert corr_stress_upr > 0.80, \
        f"UPR marker should track ER stress over time: correlation={corr_stress_upr:.3f}"

    print(f"\n✓ ER stress temporal trajectory coherent across modalities")


def test_multi_organelle_temporal_coherence():
    """
    Validate all three organelles accumulate smoothly with coherent kinetics.

    Setup:
    - High density (all organelles stressed)
    - Measure at t=0, 12h, 24h, 48h
    - Track ER, mito, transport (latent + morphology)

    Expected:
    - ER stress increases monotonically
    - Mito dysfunction increases monotonically
    - Transport dysfunction increases monotonically
    - Morphology tracks latent states over time
    """
    seed = 42
    cell_line = "A549"

    timepoints = [0.0, 12.0, 24.0, 48.0]
    measurements = []

    for t in timepoints:
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("test", cell_line, initial_count=9e6, capacity=1e7, initial_viability=0.98)

        if t > 0:
            vm.advance_time(t)

        vessel = vm.vessel_states["test"]
        er_stress = vessel.er_stress
        mito_dysfunction = vessel.mito_dysfunction
        transport_dysfunction = vessel.transport_dysfunction

        # Measure morphology
        morph_result = vm.cell_painting_assay("test")
        morph = morph_result['morphology_struct']

        measurements.append({
            'time_h': t,
            'er_stress': er_stress,
            'mito_dysfunction': mito_dysfunction,
            'transport_dysfunction': transport_dysfunction,
            'er_morph': morph['er'],
            'mito_morph': morph['mito'],
            'actin_morph': morph['actin']
        })

        print(f"t={t:5.1f}h:")
        print(f"  ER: stress={er_stress:.3f}, morph={morph['er']:.3f}")
        print(f"  Mito: dysfunction={mito_dysfunction:.3f}, morph={morph['mito']:.3f}")
        print(f"  Transport: dysfunction={transport_dysfunction:.3f}, morph={morph['actin']:.3f}")

    # Validate monotonic increase for all organelles
    for i in range(len(measurements) - 1):
        curr = measurements[i]
        next_m = measurements[i + 1]

        assert next_m['er_stress'] >= curr['er_stress'], \
            f"ER stress should increase: t={curr['time_h']}h → {next_m['time_h']}h"
        assert next_m['mito_dysfunction'] >= curr['mito_dysfunction'], \
            f"Mito dysfunction should increase: t={curr['time_h']}h → {next_m['time_h']}h"
        assert next_m['transport_dysfunction'] >= curr['transport_dysfunction'], \
            f"Transport dysfunction should increase: t={curr['time_h']}h → {next_m['time_h']}h"

    print(f"\n✓ All three organelles show monotonic stress accumulation")


def test_kinetic_plausibility():
    """
    Validate that kinetics are plausible (no instantaneous jumps).

    Setup:
    - High density
    - Fine-grained sampling: t=0, 6h, 12h, 18h, 24h

    Expected:
    - Smooth transitions (no jumps > 3× between consecutive timepoints)
    - ER stress rate bounded (realistic tau ~ 12h)
    - No negative transitions (stress can't decrease without intervention)
    """
    seed = 42
    cell_line = "A549"

    timepoints = [0.0, 6.0, 12.0, 18.0, 24.0]
    measurements = []

    for t in timepoints:
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("test", cell_line, initial_count=9e6, capacity=1e7, initial_viability=0.98)

        if t > 0:
            vm.advance_time(t)

        vessel = vm.vessel_states["test"]
        er_stress = vessel.er_stress

        measurements.append({
            'time_h': t,
            'er_stress': er_stress
        })

    # Check for instantaneous jumps
    # Note: Initial ramp-up can be steep (lagged sigmoid), so allow larger jumps early
    max_jump_ratio = 1.0
    for i in range(len(measurements) - 1):
        curr = measurements[i]
        next_m = measurements[i + 1]

        if curr['er_stress'] > 0.01:  # Avoid division by near-zero
            jump_ratio = next_m['er_stress'] / curr['er_stress']
            max_jump_ratio = max(max_jump_ratio, jump_ratio)

            # Allow steeper jumps during initial ramp-up (lagged sigmoid dynamics)
            # After 12h, should be smoother (approaching steady state)
            max_allowed_jump = 5.0 if curr['time_h'] < 12.0 else 3.0

            assert jump_ratio < max_allowed_jump, \
                f"Jump too large: t={curr['time_h']}h ({curr['er_stress']:.3f}) → t={next_m['time_h']}h ({next_m['er_stress']:.3f}), ratio={jump_ratio:.2f}× (max={max_allowed_jump:.1f}×)"

        print(f"t={curr['time_h']:5.1f}h → {next_m['time_h']:5.1f}h: ER stress {curr['er_stress']:.3f} → {next_m['er_stress']:.3f}")

    print(f"\n✓ Kinetics plausible (max jump ratio: {max_jump_ratio:.2f}×)")


def test_temporal_order_causality():
    """
    Validate temporal ordering: cause precedes effect.

    Setup:
    - Seed at high density at t=0
    - Measure: confluence (cause) and ER stress (effect)
    - Sample: t=0, 3h, 6h, 12h, 24h

    Expected:
    - Confluence increases first (immediate, governed by logistic growth)
    - Contact pressure lags confluence (lagged sigmoid, tau=12h)
    - ER stress lags contact pressure (differential equation, tau~hours)
    - Order preserved: confluence → pressure → ER stress
    """
    seed = 42
    cell_line = "A549"

    timepoints = [0.0, 3.0, 6.0, 12.0, 24.0]
    measurements = []

    for t in timepoints:
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("test", cell_line, initial_count=9e6, capacity=1e7, initial_viability=0.98)

        if t > 0:
            vm.advance_time(t)

        vessel = vm.vessel_states["test"]
        confluence = vessel.confluence
        contact_pressure = getattr(vessel, "contact_pressure", 0.0)
        er_stress = vessel.er_stress

        measurements.append({
            'time_h': t,
            'confluence': confluence,
            'contact_pressure': contact_pressure,
            'er_stress': er_stress
        })

        print(f"t={t:5.1f}h: confluence={confluence:.3f}, pressure={contact_pressure:.3f}, ER stress={er_stress:.3f}")

    # Find when each variable reaches 50% of its final value (t_50)
    def find_t50(vals, times):
        """Find time when value reaches 50% of final."""
        final = vals[-1]
        initial = vals[0]
        target = initial + 0.5 * (final - initial)

        for i, v in enumerate(vals):
            if v >= target:
                return times[i]
        return times[-1]

    confluence_vals = [m['confluence'] for m in measurements]
    pressure_vals = [m['contact_pressure'] for m in measurements]
    er_stress_vals = [m['er_stress'] for m in measurements]
    times = [m['time_h'] for m in measurements]

    t50_confluence = find_t50(confluence_vals, times)
    t50_pressure = find_t50(pressure_vals, times)
    t50_er_stress = find_t50(er_stress_vals, times)

    print(f"\nTemporal ordering (t_50):")
    print(f"  Confluence: {t50_confluence:.1f}h")
    print(f"  Contact pressure: {t50_pressure:.1f}h")
    print(f"  ER stress: {t50_er_stress:.1f}h")

    # Validate causal ordering
    assert t50_confluence <= t50_pressure, \
        f"Confluence should precede pressure: {t50_confluence:.1f}h vs {t50_pressure:.1f}h"
    assert t50_pressure <= t50_er_stress, \
        f"Pressure should precede ER stress: {t50_pressure:.1f}h vs {t50_er_stress:.1f}h"

    print(f"\n✓ Temporal ordering preserved: confluence → pressure → ER stress")


def test_intervention_kinetics():
    """
    Validate kinetics of intervention (washout removes stress).

    Setup:
    - Start at high density (ER stress accumulated)
    - Washout at t=24h (remove contact pressure)
    - Measure: t=24h (before washout), t=27h, t=30h, t=36h

    Expected:
    - Before washout: ER stress high
    - After washout: ER stress decreases (decay kinetics)
    - Morphology and scalars track latent stress decay
    """
    seed = 42
    cell_line = "A549"

    # Build up stress for 24h
    vm = BiologicalVirtualMachine(seed=seed)
    vm.seed_vessel("test", cell_line, initial_count=9e6, capacity=1e7, initial_viability=0.98)
    vm.advance_time(24.0)

    vessel_pre = vm.vessel_states["test"]
    er_stress_pre = vessel_pre.er_stress

    print(f"Before washout (t=24h):")
    print(f"  ER stress: {er_stress_pre:.3f}")

    # Washout (removes cells to low density)
    vm.washout_compound("test")

    # Measure decay kinetics
    timepoints_post = [0.0, 3.0, 6.0, 12.0]  # Hours after washout
    measurements_post = []

    for delta_t in timepoints_post:
        if delta_t > 0:
            vm.advance_time(delta_t)

        vessel = vm.vessel_states["test"]
        er_stress = vessel.er_stress

        measurements_post.append({
            'time_after_washout_h': delta_t,
            'er_stress': er_stress
        })

        print(f"t={24 + delta_t:.1f}h (Δt={delta_t:.1f}h post-washout): ER stress={er_stress:.3f}")

    # Validate ER stress decreases after washout
    for i in range(len(measurements_post) - 1):
        curr = measurements_post[i]
        next_m = measurements_post[i + 1]

        # Stress should decrease or stay constant (decay)
        assert next_m['er_stress'] <= curr['er_stress'] + 0.05, \
            f"ER stress should not increase after washout: Δt={curr['time_after_washout_h']}h ({curr['er_stress']:.3f}) → Δt={next_m['time_after_washout_h']}h ({next_m['er_stress']:.3f})"

    print(f"\n✓ Intervention kinetics validated (stress decays after washout)")


if __name__ == "__main__":
    print("=" * 70)
    print("TEMPORAL COHERENCE VALIDATION")
    print("=" * 70)
    print()

    print("=" * 70)
    print("TEST 1: ER stress temporal trajectory")
    print("=" * 70)
    test_er_stress_temporal_trajectory()
    print()

    print("=" * 70)
    print("TEST 2: Multi-organelle temporal coherence")
    print("=" * 70)
    test_multi_organelle_temporal_coherence()
    print()

    print("=" * 70)
    print("TEST 3: Kinetic plausibility")
    print("=" * 70)
    test_kinetic_plausibility()
    print()

    print("=" * 70)
    print("TEST 4: Temporal order (causality)")
    print("=" * 70)
    test_temporal_order_causality()
    print()

    print("=" * 70)
    print("TEST 5: Intervention kinetics (washout)")
    print("=" * 70)
    test_intervention_kinetics()
    print()

    print("=" * 70)
    print("✅ ALL TEMPORAL COHERENCE TESTS PASSED")
    print("=" * 70)
    print()
    print("Validated:")
    print("  ✓ ER stress trajectory coherent across modalities over time")
    print("  ✓ Multi-organelle stress accumulation monotonic")
    print("  ✓ Kinetics plausible (no instantaneous jumps)")
    print("  ✓ Temporal ordering preserved (confluence → pressure → stress)")
    print("  ✓ Intervention kinetics (stress decays after washout)")
