"""
Phase 2D.1: Contamination Events - Contract Tests

These tests enforce hard invariants that must hold before identifiability.

NOT NEGOTIABLE:
- Determinism (same seed → identical outcomes, order-independent)
- RNG isolation (bio/assay noise changes → contamination unchanged)
- Rarity sanity (baseline rate → Poisson-reasonable event count)
- No hallucination (disabled → contamination fields clean)

DISCIPLINE:
- Use real config pathway (vm.contamination_config assignment is test API)
- Compare event identity (onset/type/severity), not just viability
- Exercise tripwires (assert at least one event occurred in stress tests)
- Float comparison via np.isclose where needed
- Multi-seed rarity checks with Poisson quantiles
- No fake detectors - assert simulator ground truth
"""

import numpy as np
from scipy import stats
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False


# Contamination config for stress testing (10× baseline → ~30% events over 7 days)
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


# ============================================================================
# Contract 1: Determinism (Order Independence)
# ============================================================================

def test_contamination_determinism_same_seed():
    """
    Same seed, same config, same vessel IDs → identical contamination EVENT IDENTITY.

    EXACT EQUALITY:
    - contaminated (bool)
    - contamination_type (str)
    - contamination_onset_h (float, discrete)
    - contamination_phase (str)

    CLOSE EQUALITY (float tolerance):
    - contamination_severity (lognormal draw, stored once)
    - death_contamination (accumulated float)
    - viability (accumulated float)

    If this fails, STOP. Foundation is broken.
    """
    seed = 42
    duration_h = 168.0  # 7 days
    vessel_ids = ["Plate1_A01", "Plate1_B02", "Plate1_C03", "Plate1_D04"]

    def run_experiment(seed):
        vm = BiologicalVirtualMachine(seed=seed)
        vm.contamination_config = CONTAM_CONFIG_STRESS

        # Seed vessels
        for vessel_id in vessel_ids:
            vm.seed_vessel(vessel_id, "A549", vessel_type="96-well", initial_count=5000)

        # Advance time
        vm.advance_time(duration_h)

        # Collect contamination event identity
        outcomes = {}
        for vessel_id in vessel_ids:
            vessel = vm.vessel_states[vessel_id]
            outcomes[vessel_id] = {
                'contaminated': vessel.contaminated,
                'contamination_type': vessel.contamination_type,
                'contamination_onset_h': vessel.contamination_onset_h,
                'contamination_phase': vessel.contamination_phase,
                'contamination_severity': vessel.contamination_severity,
                'death_contamination': vessel.death_contamination,
                'viability': vessel.viability,
            }
        return outcomes

    # Run twice with same seed
    outcomes1 = run_experiment(seed)
    outcomes2 = run_experiment(seed)

    # Assert event identity identical
    for vessel_id in vessel_ids:
        o1 = outcomes1[vessel_id]
        o2 = outcomes2[vessel_id]

        # Exact equality for discrete values
        assert o1['contaminated'] == o2['contaminated'], \
            f"{vessel_id}: contaminated flag differs"
        assert o1['contamination_type'] == o2['contamination_type'], \
            f"{vessel_id}: contamination_type differs"
        assert o1['contamination_phase'] == o2['contamination_phase'], \
            f"{vessel_id}: contamination_phase differs"

        if o1['contaminated']:
            # Onset is discrete (step-based), should be exact
            assert o1['contamination_onset_h'] == o2['contamination_onset_h'], \
                f"{vessel_id}: onset_h differs"

            # Severity is sampled once and stored, should be exact
            assert o1['contamination_severity'] == o2['contamination_severity'], \
                f"{vessel_id}: severity differs"

            # Death/viability are accumulated, use close equality
            assert np.isclose(o1['death_contamination'], o2['death_contamination'], rtol=0, atol=1e-12), \
                f"{vessel_id}: death_contamination differs beyond tolerance"
            assert np.isclose(o1['viability'], o2['viability'], rtol=0, atol=1e-12), \
                f"{vessel_id}: viability differs beyond tolerance"

    # Exercise tripwire: at least one event should have occurred (stress test config)
    n_contaminated = sum(1 for o in outcomes1.values() if o['contaminated'])
    assert n_contaminated >= 1, \
        f"Stress test produced zero events (expected ~30% of {len(vessel_ids)} vessels). Config may be broken."

    print(f"✅ Determinism: {n_contaminated}/{len(vessel_ids)} vessels contaminated, all bitwise identical")


def test_contamination_order_invariance():
    """
    Different vessel creation order → identical per-vessel event identity.

    Contamination for vessel A must be independent of:
    - Whether vessel B exists
    - Order in which vessels are created

    RNG is keyed by lineage_id (run_seed + vessel_id), not creation order.
    """
    seed = 42
    duration_h = 168.0
    # Use 16 vessels for sufficient power (λ ≈ 5.6 → P(0 events) < 0.5%)
    vessel_ids = [f"Plate1_{chr(65 + i // 12)}{(i % 12) + 1:02d}" for i in range(16)]

    def run_with_order(vessel_order):
        vm = BiologicalVirtualMachine(seed=seed)
        vm.contamination_config = CONTAM_CONFIG_STRESS

        for vessel_id in vessel_order:
            vm.seed_vessel(vessel_id, "A549", vessel_type="96-well", initial_count=5000)

        vm.advance_time(duration_h)

        return {
            vessel_id: {
                'contaminated': vm.vessel_states[vessel_id].contaminated,
                'contamination_type': vm.vessel_states[vessel_id].contamination_type,
                'contamination_onset_h': vm.vessel_states[vessel_id].contamination_onset_h,
                'contamination_severity': vm.vessel_states[vessel_id].contamination_severity,
                'contamination_phase': vm.vessel_states[vessel_id].contamination_phase,
            }
            for vessel_id in vessel_ids
        }

    # Order 1: Forward order
    outcomes1 = run_with_order(vessel_ids)

    # Order 2: Reverse order
    outcomes2 = run_with_order(list(reversed(vessel_ids)))

    # Order 3: Shuffled order (deterministic shuffle from seed)
    import random
    rng_shuffle = random.Random(12345)
    shuffled = vessel_ids.copy()
    rng_shuffle.shuffle(shuffled)
    outcomes3 = run_with_order(shuffled)

    # Assert per-vessel event identity identical across all orderings
    for vessel_id in vessel_ids:
        o1 = outcomes1[vessel_id]
        o2 = outcomes2[vessel_id]
        o3 = outcomes3[vessel_id]

        assert o1['contaminated'] == o2['contaminated'] == o3['contaminated'], \
            f"{vessel_id}: contaminated differs between orderings"
        assert o1['contamination_type'] == o2['contamination_type'] == o3['contamination_type'], \
            f"{vessel_id}: type differs between orderings"
        assert o1['contamination_phase'] == o2['contamination_phase'] == o3['contamination_phase'], \
            f"{vessel_id}: phase differs between orderings"

        if o1['contaminated']:
            assert o1['contamination_onset_h'] == o2['contamination_onset_h'] == o3['contamination_onset_h'], \
                f"{vessel_id}: onset_h differs between orderings"
            assert o1['contamination_severity'] == o2['contamination_severity'] == o3['contamination_severity'], \
                f"{vessel_id}: severity differs between orderings"

    # Exercise tripwire
    n_contaminated = sum(1 for o in outcomes1.values() if o['contaminated'])
    assert n_contaminated >= 1, "Order invariance test produced zero events (config may be broken)"

    print(f"✅ Order invariance: {n_contaminated}/{len(vessel_ids)} vessels, identical across 3 orderings")


# ============================================================================
# Contract 2: RNG Isolation
# ============================================================================

def test_contamination_rng_isolation_from_biology():
    """
    Perturb intrinsic biology CVs → contamination event identity unchanged.

    Operational events use separate RNG seed space (run_context.seed, not vm RNG streams).
    Biology heterogeneity should not leak into contamination.

    EXACT EQUALITY for event identity (onset/type/severity/phase).
    """
    seed = 42
    duration_h = 168.0
    # Use 16 vessels for sufficient power (λ ≈ 5.6 → P(0 events) < 0.5%)
    vessel_ids = [f"Plate1_{chr(65 + i // 12)}{(i % 12) + 1:02d}" for i in range(16)]

    def run_with_bio_noise(bio_noise_config):
        vm = BiologicalVirtualMachine(seed=seed, bio_noise_config=bio_noise_config)
        vm.contamination_config = CONTAM_CONFIG_STRESS

        for vessel_id in vessel_ids:
            vm.seed_vessel(vessel_id, "A549", vessel_type="96-well", initial_count=5000)

        vm.advance_time(duration_h)

        return {
            vessel_id: {
                'contaminated': vm.vessel_states[vessel_id].contaminated,
                'contamination_type': vm.vessel_states[vessel_id].contamination_type,
                'contamination_onset_h': vm.vessel_states[vessel_id].contamination_onset_h,
                'contamination_severity': vm.vessel_states[vessel_id].contamination_severity,
            }
            for vessel_id in vessel_ids
        }

    # Run 1: No biology noise
    outcomes_no_noise = run_with_bio_noise({'enabled': False})

    # Run 2: High biology noise
    outcomes_high_noise = run_with_bio_noise({
        'enabled': True,
        'growth_cv': 0.2,
        'stress_sensitivity_cv': 0.3,
        'hazard_scale_cv': 0.25,
        'plate_level_fraction': 0.5,
    })

    # Assert contamination event identity EXACTLY identical (biology noise must not leak)
    for vessel_id in vessel_ids:
        o1 = outcomes_no_noise[vessel_id]
        o2 = outcomes_high_noise[vessel_id]

        assert o1['contaminated'] == o2['contaminated'], \
            f"{vessel_id}: biology noise leaked into contamination RNG (contaminated differs)"
        assert o1['contamination_type'] == o2['contamination_type'], \
            f"{vessel_id}: biology noise leaked (type differs)"

        if o1['contaminated']:
            assert o1['contamination_onset_h'] == o2['contamination_onset_h'], \
                f"{vessel_id}: biology noise leaked (onset_h differs)"
            assert o1['contamination_severity'] == o2['contamination_severity'], \
                f"{vessel_id}: biology noise leaked (severity differs)"

    # Exercise tripwire
    n_contaminated = sum(1 for o in outcomes_no_noise.values() if o['contaminated'])
    assert n_contaminated >= 1, "RNG isolation test produced zero events (config may be broken)"

    print(f"✅ RNG isolation: {n_contaminated}/{len(vessel_ids)} events, identical despite bio noise perturbation")


# ============================================================================
# Contract 3: Rarity Sanity (Multi-Seed, Poisson Quantiles)
# ============================================================================

def test_contamination_rarity_baseline_poisson():
    """
    Baseline rate (0.005/vessel-day) → event count within Poisson quantiles.

    NOT TIGHT. Just "not insane."

    Expected λ = rate × n_vessels × days
    Accept: [poisson.ppf(0.001, λ), poisson.ppf(0.999, λ)]

    Run across 5 seeds to avoid single-seed flukes.

    This prevents silent rate inflation.
    """
    duration_h = 168.0  # 7 days
    n_vessels = 96
    n_seeds = 5

    contam_config_baseline = {
        'enabled': True,
        'baseline_rate_per_vessel_day': 0.005,  # BASELINE (not stress test)
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

    # Expected event count (Poisson λ)
    rate_per_day = contam_config_baseline['baseline_rate_per_vessel_day']
    days = duration_h / 24.0
    lambda_expected = rate_per_day * n_vessels * days

    # Poisson quantiles (very wide tolerance: 0.1% to 99.9%)
    lower_bound = int(stats.poisson.ppf(0.001, lambda_expected))
    upper_bound = int(stats.poisson.ppf(0.999, lambda_expected))

    print(f"Expected λ={lambda_expected:.2f}, bounds=[{lower_bound}, {upper_bound}]")

    event_counts = []

    for seed in range(42, 42 + n_seeds):
        vm = BiologicalVirtualMachine(seed=seed)
        vm.contamination_config = contam_config_baseline

        vessel_ids = [f"Plate1_{chr(65 + i // 12)}{(i % 12) + 1:02d}" for i in range(n_vessels)]
        for vessel_id in vessel_ids:
            vm.seed_vessel(vessel_id, "A549", vessel_type="96-well", initial_count=5000)

        vm.advance_time(duration_h)

        # Count contamination events
        n_contaminated = sum(
            1 for vessel_id in vessel_ids
            if vm.vessel_states[vessel_id].contaminated
        )

        event_counts.append(n_contaminated)

        # Assert this seed's count within bounds
        assert lower_bound <= n_contaminated <= upper_bound, \
            f"Seed {seed}: event count {n_contaminated} outside Poisson bounds [{lower_bound}, {upper_bound}] (λ={lambda_expected:.2f})"

    print(f"✅ Rarity sanity: counts across {n_seeds} seeds = {event_counts}, all within [{lower_bound}, {upper_bound}]")


# ============================================================================
# Contract 4: No Hallucination When Disabled
# ============================================================================

def test_contamination_no_hallucination_when_disabled():
    """
    With contamination DISABLED, simulator ground truth must be clean.

    NO FAKE DETECTORS. Assert simulator fields directly:
    - contaminated == False
    - death_contamination == 0.0

    This is the most important psychological test.
    Prevents trusting a detector that always finds ghosts.

    Run across multiple seeds to catch stochastic leaks.
    """
    duration_h = 168.0
    n_vessels = 48
    n_seeds = 3

    for seed in range(42, 42 + n_seeds):
        # Contamination DISABLED (vm.contamination_config remains None)
        vm = BiologicalVirtualMachine(seed=seed)
        # Do NOT set contamination_config - it should remain None

        vessel_ids = [f"Plate1_{chr(65 + i // 12)}{(i % 12) + 1:02d}" for i in range(n_vessels)]
        for vessel_id in vessel_ids:
            vm.seed_vessel(vessel_id, "A549", vessel_type="96-well", initial_count=5000)

        vm.advance_time(duration_h)

        # Assert ground truth: NO contamination events
        for vessel_id in vessel_ids:
            vessel = vm.vessel_states[vessel_id]

            assert vessel.contaminated == False, \
                f"Seed {seed}, {vessel_id}: contaminated=True when disabled (hallucination)"
            assert vessel.death_contamination == 0.0, \
                f"Seed {seed}, {vessel_id}: death_contamination={vessel.death_contamination} when disabled"
            assert vessel.contamination_type is None, \
                f"Seed {seed}, {vessel_id}: contamination_type={vessel.contamination_type} when disabled"

    print(f"✅ No hallucination: {n_seeds} seeds × {n_vessels} vessels, all clean when disabled")


if __name__ == "__main__":
    if HAS_PYTEST:
        pytest.main([__file__, "-v"])
    else:
        # Manual test runner
        print("Running contract tests manually (pytest not available)...")
        print()

        tests = [
            ("Determinism (same seed)", test_contamination_determinism_same_seed),
            ("Order invariance", test_contamination_order_invariance),
            ("RNG isolation (biology)", test_contamination_rng_isolation_from_biology),
            ("Rarity sanity (Poisson)", test_contamination_rarity_baseline_poisson),
            ("No hallucination (disabled)", test_contamination_no_hallucination_when_disabled),
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            print(f"=== {name} ===")
            try:
                test_func()
                print(f"✅ PASS\n")
                passed += 1
            except Exception as e:
                print(f"❌ FAIL: {e}\n")
                failed += 1

        print(f"Results: {passed} passed, {failed} failed")
        if failed > 0:
            exit(1)
