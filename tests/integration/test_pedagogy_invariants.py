"""
Pedagogy Invariant Tests - Governance Layer for RL Agent Teaching

These tests enforce what lessons become rational for RL agents to learn.
They are NOT unit tests for biological correctness - they are contracts
about pedagogical objectives.

Invariants tested:
1. Continuous subthreshold cost (prevents threshold surfing)
2. Two paths to same state (history matters, not just current state)
3. Synergistic coupling (combinations are risky)
4. Washout memory (recovery is gradual, not instant reset)
5. Chronic vs acute (different damage patterns despite similar viability)

Boundary tests:
- Death threshold boundaries
- Subthreshold growth penalty regime
- Stress response dynamics
- Bio random effects determinism
- Dt-independence
- Synergy gate threshold
- State aliasing (partial observability)
- Damage accumulation/repair

Feature flags required:
- ENABLE_CONTINUOUS_SUBTHRESHOLD_COST = True
- ENABLE_ADAPTIVE_MEMORY = True (ER damage dynamics)
- ENABLE_SYNERGISTIC_COUPLING = True
"""

import pytest
import numpy as np
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.constants import (
    ENABLE_CONTINUOUS_SUBTHRESHOLD_COST,
    ENABLE_SYNERGISTIC_COUPLING,
    ER_STRESS_K_ON,
    ER_STRESS_K_OFF,
    ER_DAMAGE_K_ACCUM,
    ER_DAMAGE_K_REPAIR,
    ER_DAMAGE_BOOST,
    ER_DAMAGE_RECOVERY_SLOW,
    SYNERGY_GATE_S0,
    SYNERGY_K_HAZARD,
    SUBTHRESHOLD_STRESS_GROWTH_PENALTY,
)


class PedagogyCalibration:
    """Centralized dose/duration calibration for pedagogy tests."""

    # Subthreshold regime (S ~0.3-0.5, no death)
    SUBTHRESHOLD_DOSE_uM = 0.12  # Increased from 0.08 (damage boost makes stress build faster)
    SUBTHRESHOLD_DURATION_H = 24

    # Death threshold regime (S ~0.7-0.8, death starts)
    DEATH_THRESHOLD_DOSE_uM = 0.20  # Reduced from 0.25 (damage boost increases death)
    DEATH_THRESHOLD_DURATION_H = 24

    # Synergy sublethal doses (alone: S ~0.4-0.5, together: death)
    ER_SUBLETHAL_DOSE_uM = 0.3
    MITO_SUBLETHAL_DOSE_uM = 1.8  # Increased from 1.0 (need mito stress >gate threshold)
    SYNERGY_DURATION_H = 24

    # Memory/priming doses (accumulate damage, recover observables)
    PRIMING_DOSE_uM = 0.15  # Reduced from 0.18 (recovery slowdown keeps stress elevated longer)
    PRIMING_DURATION_H = 24
    RECOVERY_DURATION_H = 48  # Increased from 36h (need more time for stress to decay with slowdown)
    RECHALLENGE_DOSE_uM = 0.3
    RECHALLENGE_DURATION_H = 24

    # Chronic vs acute (same viability loss, different patterns)
    CHRONIC_LOW_DOSE_uM = 0.10  # Reduced from 0.12
    CHRONIC_DURATION_H = 48
    ACUTE_HIGH_DOSE_uM = 0.28  # Reduced from 0.35
    ACUTE_DURATION_H = 12


@pytest.fixture
def vm_factory():
    """Factory for creating VMs with consistent config."""
    def _make_vm(seed=0, bio_noise_enabled=False):
        bio_noise_config = {
            'enabled': bio_noise_enabled,
            'growth_cv': 0.15,
            'stress_sensitivity_cv': 0.20,
            'hazard_scale_cv': 0.25,
            'ic50_shift_cv': 0.20,
            'death_threshold_shift_cv': 0.15,
            'plate_level_fraction': 0.3,
        } if bio_noise_enabled else {'enabled': False}

        vm = BiologicalVirtualMachine(
            seed=seed,
            bio_noise_config=bio_noise_config
        )
        return vm
    return _make_vm


# =============================================================================
# Config Validation
# =============================================================================

def test_pedagogy_config_enabled():
    """Verify all pedagogy feature flags are enabled."""
    assert ENABLE_CONTINUOUS_SUBTHRESHOLD_COST, "Continuous subthreshold cost must be enabled"
    assert ENABLE_SYNERGISTIC_COUPLING, "Synergistic coupling must be enabled"

    # Verify ER damage dynamics are configured (adaptive memory)
    assert ER_DAMAGE_K_ACCUM > 0, "ER damage accumulation must be enabled"
    assert ER_DAMAGE_K_REPAIR > 0, "ER damage repair must be enabled"
    assert ER_DAMAGE_BOOST > 0, "ER damage boost must be enabled"
    assert ER_DAMAGE_RECOVERY_SLOW >= 0, "ER damage recovery slow must be configured"


# =============================================================================
# Pedagogy Invariant Tests
# =============================================================================

def test_continuous_subthreshold_cost(vm_factory):
    """
    Invariant: Stress reduces growth BEFORE death threshold.

    Prevents agents from surfing at cliff edges where stress is high
    but death hasn't started yet.
    """
    seed = 42
    cal = PedagogyCalibration

    # Control: no stress
    vm_control = vm_factory(seed=seed)
    vm_control.seed_vessel("Plate1_A01", "U2OS", vessel_type="384-well")
    for _ in range(4):  # 4×6h steps to resolve one-timestep lag
        vm_control.advance_time(cal.SUBTHRESHOLD_DURATION_H / 4)
    control = vm_control.vessel_states["Plate1_A01"]

    # Stressed: subthreshold dose
    vm_stress = vm_factory(seed=seed)
    vm_stress.seed_vessel("Plate1_A01", "U2OS", vessel_type="384-well")
    vm_stress.treat_with_compound("Plate1_A01", "tunicamycin", cal.SUBTHRESHOLD_DOSE_uM)
    for _ in range(4):  # 4×6h steps to resolve one-timestep lag
        vm_stress.advance_time(cal.SUBTHRESHOLD_DURATION_H / 4)
    stress = vm_stress.vessel_states["Plate1_A01"]

    # Verify subthreshold regime (stress high, no death)
    assert stress.er_stress > 0.3, f"Stress too low: {stress.er_stress:.3f}"
    assert stress.er_stress < 0.6, f"Stress too high: {stress.er_stress:.3f}"
    assert stress.viability > 0.90, f"Unexpected death: {stress.viability:.3f}"

    # INVARIANT: Stressed vessel grows slower despite no death
    growth_ratio = stress.cell_count / control.cell_count
    assert growth_ratio < 0.95, (
        f"Growth penalty too weak: {growth_ratio:.3f}. "
        f"Subthreshold cost not effective. "
        f"(Note: penalty averages over stress ramp-up, not just final stress)"
    )

    # Verify cost is proportional to stress (at FINAL stress level)
    expected_penalty_factor = 1.0 - (SUBTHRESHOLD_STRESS_GROWTH_PENALTY * stress.er_stress)
    assert 0.7 < expected_penalty_factor < 0.9, "Stress penalty out of expected range"

    # Pedagogy check: growth penalty exists and is non-trivial (>3%)
    assert growth_ratio < 0.97, "Growth penalty too weak to teach lesson"


def test_two_paths_same_state(vm_factory):
    """
    Invariant: Two different stress histories produce different futures
    even if current observables match.

    This tests that history matters, not just current state snapshot.
    """
    seed = 99
    cal = PedagogyCalibration

    # Path A: Primed (stress + washout + recovery)
    vm_A = vm_factory(seed=seed)
    vm_A.seed_vessel("Plate1_E01", "U2OS", vessel_type="384-well")
    vm_A.treat_with_compound("Plate1_E01", "tunicamycin", cal.PRIMING_DOSE_uM)
    vm_A.advance_time(cal.PRIMING_DURATION_H)
    vm_A.washout_compound("Plate1_E01")
    vm_A.advance_time(cal.RECOVERY_DURATION_H)
    A_before = vm_A.vessel_states["Plate1_E01"]

    # Path B: Naive (no stress history)
    total_time = cal.PRIMING_DURATION_H + cal.RECOVERY_DURATION_H
    vm_B = vm_factory(seed=seed)
    vm_B.seed_vessel("Plate1_E01", "U2OS", vessel_type="384-well")
    vm_B.advance_time(total_time)
    B_before = vm_B.vessel_states["Plate1_E01"]

    # Verify hidden state divergence (damage gap)
    damage_gap = abs(A_before.er_damage - B_before.er_damage)
    assert damage_gap > 0.20, (
        f"Damage gap too small: {damage_gap:.3f}. "
        f"History not leaving persistent trace."
    )

    # Apply identical rechallenge
    vm_A.treat_with_compound("Plate1_E01", "tunicamycin", cal.RECHALLENGE_DOSE_uM)
    vm_A.advance_time(cal.RECHALLENGE_DURATION_H)
    A_after = vm_A.vessel_states["Plate1_E01"]

    vm_B.treat_with_compound("Plate1_E01", "tunicamycin", cal.RECHALLENGE_DOSE_uM)
    vm_B.advance_time(cal.RECHALLENGE_DURATION_H)
    B_after = vm_B.vessel_states["Plate1_E01"]

    # INVARIANT: Futures diverge (primed vessel more sensitive)
    via_divergence = abs(A_after.viability - B_after.viability)
    assert via_divergence > 0.08, (
        f"Future divergence too small: {via_divergence:.3f}. "
        f"History not affecting rechallenge response."
    )

    # Verify primed vessel is MORE sensitive (not less)
    assert A_after.viability < B_after.viability, "Primed vessel should be more sensitive"


def test_synergistic_coupling(vm_factory):
    """
    Invariant: Combinations are riskier than sum of individual risks.

    Teaches that multi-target interventions create synergy, not just
    additive badness.
    """
    seed = 77
    cal = PedagogyCalibration

    # ER alone
    vm_er = vm_factory(seed=seed)
    vm_er.seed_vessel("Plate1_A01", "U2OS", vessel_type="384-well")
    vm_er.treat_with_compound("Plate1_A01", "tunicamycin", cal.ER_SUBLETHAL_DOSE_uM)
    vm_er.advance_time(cal.SYNERGY_DURATION_H)
    er_alone = vm_er.vessel_states["Plate1_A01"]

    # Mito alone
    vm_mito = vm_factory(seed=seed)
    vm_mito.seed_vessel("Plate1_A01", "U2OS", vessel_type="384-well")
    vm_mito.treat_with_compound("Plate1_A01", "oligomycin", cal.MITO_SUBLETHAL_DOSE_uM)
    vm_mito.advance_time(cal.SYNERGY_DURATION_H)
    mito_alone = vm_mito.vessel_states["Plate1_A01"]

    # Combination
    vm_combo = vm_factory(seed=seed)
    vm_combo.seed_vessel("Plate1_A01", "U2OS", vessel_type="384-well")
    vm_combo.treat_with_compound("Plate1_A01", "tunicamycin", cal.ER_SUBLETHAL_DOSE_uM)
    vm_combo.treat_with_compound("Plate1_A01", "oligomycin", cal.MITO_SUBLETHAL_DOSE_uM)
    vm_combo.advance_time(cal.SYNERGY_DURATION_H)
    combo = vm_combo.vessel_states["Plate1_A01"]

    # Verify sublethal regime (alone: no significant death)
    assert er_alone.viability > 0.85, f"ER dose too high: via={er_alone.viability:.3f}"
    assert mito_alone.viability > 0.85, f"Mito dose too high: via={mito_alone.viability:.3f}"

    # Verify stress activation (synergy gate check)
    assert er_alone.er_stress > SYNERGY_GATE_S0, "ER stress below synergy gate"
    assert mito_alone.mito_dysfunction > SYNERGY_GATE_S0, "Mito stress below synergy gate"

    # INVARIANT: Combination worse than additive expectation
    additive_survival = er_alone.viability * mito_alone.viability
    synergy_ratio = combo.viability / additive_survival

    assert synergy_ratio < 0.90, (
        f"Synergy too weak: ratio={synergy_ratio:.3f}. "
        f"Combination not teaching risk amplification."
    )


def test_washout_memory(vm_factory):
    """
    Invariant: Washout doesn't instantly reset stress state.

    Recovery is gradual with persistent damage trace, not magic reset.
    """
    seed = 33
    cal = PedagogyCalibration

    vm = vm_factory(seed=seed)
    vm.seed_vessel("Plate1_D05", "U2OS", vessel_type="384-well")

    # Build up stress
    vm.treat_with_compound("Plate1_D05", "tunicamycin", 0.20)  # Reduced from 0.25 (damage boost increases death)
    vm.advance_time(24)
    vessel = vm.vessel_states["Plate1_D05"]
    stress_before_washout = vessel.er_stress
    damage_before_washout = vessel.er_damage

    assert stress_before_washout > 0.5, "Stress too low before washout"
    assert damage_before_washout > 0.2, "Damage too low before washout"
    assert vessel.viability > 0.70, f"Too much death before washout: {vessel.viability:.3f}"

    # Washout
    vm.washout_compound("Plate1_D05")
    vm.advance_time(6)  # Short recovery
    vessel = vm.vessel_states["Plate1_D05"]

    # INVARIANT: Stress decays but damage persists (may even increase due to slow recovery trap)
    assert vessel.er_stress < stress_before_washout * 0.8, "Stress not decaying"
    assert vessel.er_damage > damage_before_washout * 0.75, (
        f"Damage decaying too fast: {vessel.er_damage:.3f} vs {damage_before_washout:.3f}. "
        f"Memory trace not persistent."
    )

    # INVARIANT: Recovery is gradual (not instant)
    assert vessel.er_stress > 0.15, "Stress recovered too fast"


def test_chronic_vs_acute(vm_factory):
    """
    Invariant: Chronic low-dose and acute high-dose create different
    damage patterns despite similar viability loss.

    Teaches that dose schedule matters, not just total exposure.
    """
    seed = 55
    cal = PedagogyCalibration

    # Chronic: low dose, long duration
    vm_chronic = vm_factory(seed=seed)
    vm_chronic.seed_vessel("Plate1_F01", "U2OS", vessel_type="384-well")
    vm_chronic.treat_with_compound("Plate1_F01", "tunicamycin", cal.CHRONIC_LOW_DOSE_uM)
    vm_chronic.advance_time(cal.CHRONIC_DURATION_H)
    chronic = vm_chronic.vessel_states["Plate1_F01"]

    # Acute: high dose, short duration + recovery
    vm_acute = vm_factory(seed=seed)
    vm_acute.seed_vessel("Plate1_F01", "U2OS", vessel_type="384-well")
    vm_acute.treat_with_compound("Plate1_F01", "tunicamycin", cal.ACUTE_HIGH_DOSE_uM)
    vm_acute.advance_time(cal.ACUTE_DURATION_H)
    vm_acute.washout_compound("Plate1_F01")
    vm_acute.advance_time(cal.CHRONIC_DURATION_H - cal.ACUTE_DURATION_H)
    acute = vm_acute.vessel_states["Plate1_F01"]

    # Verify similar viability loss (within 15%)
    via_diff = abs(chronic.viability - acute.viability)
    assert via_diff < 0.15, (
        f"Viability divergence too large: {via_diff:.3f}. "
        f"Doses need recalibration."
    )

    # INVARIANT: Different damage accumulation patterns
    damage_diff = abs(chronic.er_damage - acute.er_damage)
    assert damage_diff > 0.10, (
        f"Damage patterns too similar: {damage_diff:.3f}. "
        f"Chronic vs acute not creating distinct trajectories."
    )

    # Typically: chronic accumulates more damage (longer exposure)
    # But verify the pattern exists, don't hardcode which is higher


# =============================================================================
# Boundary Tests (Define Operating Regimes)
# =============================================================================

def test_boundary_death_threshold(vm_factory):
    """Verify death threshold regime is calibrated correctly."""
    seed = 10
    cal = PedagogyCalibration

    vm = vm_factory(seed=seed)
    vm.seed_vessel("Plate1_A01", "U2OS", vessel_type="384-well")
    vm.treat_with_compound("Plate1_A01", "tunicamycin", cal.DEATH_THRESHOLD_DOSE_uM)
    vm.advance_time(cal.DEATH_THRESHOLD_DURATION_H)
    vessel = vm.vessel_states["Plate1_A01"]

    # Verify death onset regime
    assert 0.60 < vessel.er_stress < 0.85, f"Stress out of threshold range: {vessel.er_stress:.3f}"
    assert 0.70 < vessel.viability < 0.92, f"Viability out of threshold range: {vessel.viability:.3f}"
    assert vessel.death_er_stress > 0.02, "Death channel not active"


def test_boundary_subthreshold_regime(vm_factory):
    """Verify subthreshold regime has stress without death."""
    seed = 11
    cal = PedagogyCalibration

    vm = vm_factory(seed=seed)
    vm.seed_vessel("Plate1_B02", "U2OS", vessel_type="384-well")
    vm.treat_with_compound("Plate1_B02", "tunicamycin", cal.SUBTHRESHOLD_DOSE_uM)
    for _ in range(4):  # 4×6h steps to resolve one-timestep lag
        vm.advance_time(cal.SUBTHRESHOLD_DURATION_H / 4)
    vessel = vm.vessel_states["Plate1_B02"]

    # Verify subthreshold regime
    assert 0.30 < vessel.er_stress < 0.60, f"Stress out of subthreshold range: {vessel.er_stress:.3f}"
    assert vessel.viability > 0.90, f"Unexpected death: {vessel.viability:.3f}"
    assert vessel.death_er_stress < 0.01, "Death channel active in subthreshold regime"


def test_boundary_stress_response(vm_factory):
    """Verify stress response dynamics are in expected ranges."""
    seed = 12

    vm = vm_factory(seed=seed)
    vm.seed_vessel("Plate1_C03", "U2OS", vessel_type="384-well")
    vm.treat_with_compound("Plate1_C03", "tunicamycin", 0.5)
    vm.advance_time(12)
    vessel = vm.vessel_states["Plate1_C03"]

    # Verify stress builds up
    assert vessel.er_stress > 0.5, f"Stress too low: {vessel.er_stress:.3f}"

    # Verify damage accumulates
    assert vessel.er_damage > 0.1, f"Damage too low: {vessel.er_damage:.3f}"


def test_boundary_bio_random_effects_determinism(vm_factory):
    """Verify bio random effects are deterministic given seed."""
    seed = 13

    vm1 = vm_factory(seed=seed, bio_noise_enabled=True)
    vm1.seed_vessel("Plate1_A01", "U2OS", vessel_type="384-well")
    vessel1 = vm1.vessel_states["Plate1_A01"]

    vm2 = vm_factory(seed=seed, bio_noise_enabled=True)
    vm2.seed_vessel("Plate1_A01", "U2OS", vessel_type="384-well")
    vessel2 = vm2.vessel_states["Plate1_A01"]

    # Verify determinism
    assert vessel1.bio_random_effects == vessel2.bio_random_effects, "Bio RE not deterministic"


def test_boundary_dt_independence(vm_factory):
    """Verify stress dynamics are independent of timestep size."""
    seed = 14
    dose = 0.3
    total_time = 24

    # Coarse timestep (24h)
    vm_coarse = vm_factory(seed=seed)
    vm_coarse.seed_vessel("Plate1_A01", "U2OS", vessel_type="384-well")
    vm_coarse.treat_with_compound("Plate1_A01", "tunicamycin", dose)
    vm_coarse.advance_time(total_time)
    vessel_coarse = vm_coarse.vessel_states["Plate1_A01"]

    # Fine timestep (12 × 2h)
    vm_fine = vm_factory(seed=seed)
    vm_fine.seed_vessel("Plate1_A01", "U2OS", vessel_type="384-well")
    vm_fine.treat_with_compound("Plate1_A01", "tunicamycin", dose)
    for _ in range(12):
        vm_fine.advance_time(2)
    vessel_fine = vm_fine.vessel_states["Plate1_A01"]

    # Verify dt-independence (within numerical tolerance)
    stress_diff = abs(vessel_coarse.er_stress - vessel_fine.er_stress)
    via_diff = abs(vessel_coarse.viability - vessel_fine.viability)

    assert stress_diff < 0.02, f"Stress dt-dependent: {stress_diff:.4f}"
    assert via_diff < 0.02, f"Viability dt-dependent: {via_diff:.4f}"


def test_boundary_synergy_gate(vm_factory):
    """Verify synergy gate suppresses noise below threshold."""
    seed = 15

    vm = vm_factory(seed=seed)
    vm.seed_vessel("Plate1_D04", "U2OS", vessel_type="384-well")

    # Low stress (below gate)
    vm.treat_with_compound("Plate1_D04", "tunicamycin", 0.05)
    vm.advance_time(12)
    vessel = vm.vessel_states["Plate1_D04"]

    # Verify stress below gate threshold
    assert vessel.er_stress < SYNERGY_GATE_S0, f"Stress above gate: {vessel.er_stress:.3f}"

    # Verify no synergy effect (hard to test directly, but death should be minimal)
    assert vessel.viability > 0.95, "Unexpected death in low-stress regime"


def test_boundary_state_aliasing(vm_factory):
    """
    CRITICAL REGRESSION TEST: Verify state aliasing crack is fixed.

    This is the test that exposed the sufficient statistic problem.
    Two histories with similar observables but different damage must
    produce divergent futures.
    """
    seed = 17
    cal = PedagogyCalibration

    # Path A: Primed (build damage, recover observables)
    vm_A = vm_factory(seed=seed)
    vm_A.seed_vessel("Plate1_E01", "U2OS", vessel_type="384-well")
    vm_A.treat_with_compound("Plate1_E01", "tunicamycin", cal.PRIMING_DOSE_uM)
    vm_A.advance_time(cal.PRIMING_DURATION_H)
    vm_A.washout_compound("Plate1_E01")
    vm_A.advance_time(cal.RECOVERY_DURATION_H)
    A_before = vm_A.vessel_states["Plate1_E01"]

    # Path B: Naive (no stress history)
    total_time = cal.PRIMING_DURATION_H + cal.RECOVERY_DURATION_H
    vm_B = vm_factory(seed=seed)
    vm_B.seed_vessel("Plate1_E01", "U2OS", vessel_type="384-well")
    vm_B.advance_time(total_time)
    B_before = vm_B.vessel_states["Plate1_E01"]

    # Verify observable aliasing (similar viability, similar stress)
    via_diff = abs(A_before.viability - B_before.viability)
    stress_diff = abs(A_before.er_stress - B_before.er_stress)

    assert via_diff <= 0.08, f"Viability gap too large: {via_diff:.3f}"
    assert stress_diff <= 0.15, f"Stress gap too large: {stress_diff:.3f}"  # Relaxed from 0.10 (recovery slowdown is intentional)

    # Verify hidden state divergence (damage gap)
    damage_gap = abs(A_before.er_damage - B_before.er_damage)
    assert damage_gap > 0.25, (
        f"REGRESSION: Damage gap collapsed to {damage_gap:.3f}. "
        f"State aliasing crack has returned!"
    )

    # Apply identical rechallenge
    vm_A.treat_with_compound("Plate1_E01", "tunicamycin", cal.RECHALLENGE_DOSE_uM)
    vm_A.advance_time(cal.RECHALLENGE_DURATION_H)
    A_after = vm_A.vessel_states["Plate1_E01"]

    vm_B.treat_with_compound("Plate1_E01", "tunicamycin", cal.RECHALLENGE_DOSE_uM)
    vm_B.advance_time(cal.RECHALLENGE_DURATION_H)
    B_after = vm_B.vessel_states["Plate1_E01"]

    # CRITICAL INVARIANT: Futures must diverge
    via_divergence = abs(A_after.viability - B_after.viability)
    assert via_divergence > 0.08, (
        f"REGRESSION: Future divergence collapsed to {via_divergence:.3f}. "
        f"Observables are becoming sufficient statistic again!"
    )

    # Verify primed vessel is more sensitive (not less)
    assert A_after.viability < B_after.viability, (
        "Primed vessel should be MORE sensitive due to damage"
    )


def test_boundary_damage_accumulation_repair(vm_factory):
    """Verify damage accumulation and repair dynamics.

    With recovery slowdown, damage creates a slow-recovery trap:
    - High damage → slow stress recovery → continued damage accumulation
    - Damage peaks after washout, then repairs slowly
    """
    seed = 18

    vm = vm_factory(seed=seed)
    vm.seed_vessel("Plate1_F05", "U2OS", vessel_type="384-well")

    # Phase 1: Accumulate damage
    vm.treat_with_compound("Plate1_F05", "tunicamycin", 0.3)
    vm.advance_time(24)
    vessel = vm.vessel_states["Plate1_F05"]
    damage_start = vessel.er_damage

    assert damage_start > 0.25, f"Damage accumulation too weak: {damage_start:.3f}"

    # Phase 2: Washout - damage may INCREASE before repair (slow stress recovery)
    vm.washout_compound("Plate1_F05")
    vm.advance_time(24)
    vessel = vm.vessel_states["Plate1_F05"]
    damage_peak = vessel.er_damage

    # Verify damage increased or stayed high (recovery slowdown trap)
    assert damage_peak >= damage_start * 0.9, "Damage dropped too fast (recovery slowdown not working)"

    # Phase 3: Long recovery - damage finally repairs
    vm.advance_time(24)  # Total 48h post-washout
    vessel = vm.vessel_states["Plate1_F05"]
    damage_after_repair = vessel.er_damage

    # Verify repair happens from PEAK, not initial (24h half-life from peak)
    assert damage_after_repair < damage_peak * 0.6, "Damage not repairing from peak"
    assert damage_after_repair > damage_peak * 0.3, "Damage repairing too fast"
