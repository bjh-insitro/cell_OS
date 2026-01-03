# tests/phase6a/test_hazard_scaling_once.py
"""
Hazard scaling integrity tests: ensure hazard_scale_mult is applied exactly once.

These tests fail if:
- Scaling is applied twice (mechanism + commit)
- Scaling is applied zero times (both skip)
- Survival formula deviates from exp(-scaled_hazard * dt)

This is the single highest leverage regression test for epistemic honesty.
If this breaks, someone reintroduced "helpful" scaling inside a mechanism.
"""

import math
import numpy as np
import pytest


def _mk_vm_and_vessel(seed: int = 1):
    # Adjust import path if needed in your repo.
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

    vm = BiologicalVirtualMachine(seed=seed)
    vm.seed_vessel("P1_A01", "A549", initial_count=1e6, vessel_type='96-well')
    vessel = vm.vessel_states["P1_A01"]
    return vm, vessel


def test_hazard_scale_mult_applied_once_propose_hazard():
    """
    If hazard_scale_mult is applied exactly once in _commit_step_death, then:
      v_after = v_before * exp(-(sum(raw_hazards) * hazard_scale_mult) * dt)

    This should hold independent of allocation logic.
    """
    from cell_os.hardware.biological_virtual import DEATH_EPS

    vm, vessel = _mk_vm_and_vessel(seed=42)

    # Clean start - reset viability AND all death ledgers
    vessel.viability = 1.0
    vessel._step_hazard_proposals = {}
    vessel.death_compound = 0.0
    vessel.death_unknown = 0.0
    vessel.death_starvation = 0.0
    vessel.death_mitotic_catastrophe = 0.0
    vessel.death_er_stress = 0.0
    vessel.death_mito_dysfunction = 0.0
    vessel.death_confluence = 0.0
    vessel.death_contamination = 0.0

    # Raw hazard proposals
    h1 = 0.10
    h2 = 0.05
    dt = 2.0

    # Vessel-level scaling
    vessel.bio_random_effects = {"hazard_scale_mult": 3.0}

    vm._propose_hazard(vessel, h1, "death_compound")
    vm._propose_hazard(vessel, h2, "death_er_stress")

    v_before = float(vessel.viability)

    vm._commit_step_death(vessel, dt)

    expected = v_before * math.exp(-((h1 + h2) * 3.0) * dt)
    assert abs(vessel.viability - expected) <= 1e-12, (
        f"hazard_scale_mult not applied exactly once (or survival not exponential)\n"
        f"  got={vessel.viability:.15f}\n"
        f"  expected={expected:.15f}\n"
        f"  delta={vessel.viability - expected:.3e}"
    )

    # Also ensure the step total hazard is the scaled one (your current behavior)
    assert abs(float(vessel._step_total_hazard) - ((h1 + h2) * 3.0)) <= 1e-12
    assert float(vessel._step_total_kill) >= -DEATH_EPS


def test_hazard_scale_mult_not_double_applied_sentinel():
    """
    A regression trap: if someone multiplies hazards by hazard_scale_mult in a mechanism
    AND _commit_step_death multiplies again, survival becomes exp(-(H_raw * m^2) dt).

    We assert the result is far from that double-scaled survival.
    """
    vm, vessel = _mk_vm_and_vessel(seed=7)

    # Clean start - reset viability AND all death ledgers
    vessel.viability = 1.0
    vessel._step_hazard_proposals = {}
    vessel.death_compound = 0.0
    vessel.death_unknown = 0.0
    vessel.death_starvation = 0.0
    vessel.death_mitotic_catastrophe = 0.0
    vessel.death_er_stress = 0.0
    vessel.death_mito_dysfunction = 0.0
    vessel.death_confluence = 0.0
    vessel.death_contamination = 0.0

    h_raw = 0.20
    m = 4.0
    dt = 1.5

    vessel.bio_random_effects = {"hazard_scale_mult": m}

    # We only propose raw hazard here. If the codebase later "helpfully" pre-scales somewhere,
    # this test will start matching the double-scaled expected and fail.
    vm._propose_hazard(vessel, h_raw, "death_compound")

    v_before = float(vessel.viability)
    vm._commit_step_death(vessel, dt)

    expected_once = v_before * math.exp(-(h_raw * m) * dt)
    expected_double = v_before * math.exp(-(h_raw * (m * m)) * dt)

    assert abs(vessel.viability - expected_once) <= 1e-12, (
        f"Single-scale survival mismatch\n"
        f"  got={vessel.viability:.15f}\n"
        f"  expected_once={expected_once:.15f}"
    )

    # This margin is intentionally generous; the gap between m and m^2 scaling is huge.
    assert abs(vessel.viability - expected_double) >= 1e-6, (
        f"Looks double-scaled (mechanism pre-scaling + commit scaling?)\n"
        f"  got={vessel.viability:.15f}\n"
        f"  expected_double={expected_double:.15f}"
    )
